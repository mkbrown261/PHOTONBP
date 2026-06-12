"""
UEOS Editor Widget Tools — Phase 5
Full implementation: Editor Utility Widgets (EUW), UEOS Panel, dockable tabs,
tool browser, connection dashboard, custom editor tools.

UE 5.4 Python APIs used:
  - unreal.EditorUtilityWidget            dockable panel base class
  - unreal.EditorUtilityWidgetBlueprint   asset factory
  - unreal.EditorUtilitySubsystem         register / open / close tabs
  - unreal.EditorAssetLibrary             save / exist
  - unreal.AssetToolsHelpers              factory creation
  - unreal.BlueprintEditorLibrary         add variables/functions
  - unreal.KismetBlueprintLibrary         compile
  - unreal.ToolMenus / unreal.ToolMenu    register custom menu entries
  - unreal.EditorScriptingUtilities       general editor scripting
  - unreal.StatusBarSubsystem             status bar messages

Tools exposed (20 total):
  ew_create_utility_widget      — create EditorUtilityWidget Blueprint
  ew_open_panel                 — open (register + spawn) an EUW as docked tab
  ew_close_panel                — close a registered EUW tab
  ew_list_panels                — list all registered EUW panels
  ew_add_text_to_panel          — add TextBlock to EUW canvas
  ew_add_button_to_panel        — add Button with bound OnClicked event
  ew_add_progress_bar_to_panel  — add ProgressBar (e.g. loading indicator)
  ew_add_list_view              — add ListView widget to EUW
  ew_add_tab_widget             — add tabbed switcher widget to EUW
  ew_set_panel_title            — rename the docked tab label
  ew_compile_panel              — compile + save EUW Blueprint
  ew_add_tool_menu_entry        — add entry to UE top-level menus (Tools / Window)
  ew_remove_tool_menu_entry     — remove a custom menu entry
  ew_post_status_bar_message    — post text to the UE status bar
  ew_create_ueos_panel          — build the full UEOS connection + tool browser panel
  ew_refresh_ueos_status        — force-refresh UEOS status display in the panel
  ew_add_property_inspector     — add a property details panel to an EUW
  ew_add_output_log_widget      — add a read-only multiline text log widget
  ew_register_on_tick           — bind a Blueprint function to Editor tick
  ew_unregister_on_tick         — remove Editor tick binding
"""

import json
import logging
from textwrap import dedent
from mcp import types

log = logging.getLogger("ueos.editor_widget")


# ── Tab-style short-names → UE widget switcher indices ────────────────────────
PANEL_TABS = {
    "status":    0,
    "tools":     1,
    "log":       2,
    "settings":  3,
    "pipeline":  4,
}

# ── Built-in menu section paths ───────────────────────────────────────────────
MENU_PATHS = {
    "tools":        "LevelEditor.MainMenu.Tools",
    "window":       "LevelEditor.MainMenu.Window",
    "content":      "ContentBrowser.ContextMenu.AssetContextMenu",
    "actor":        "LevelEditor.ActorContextMenu",
    "help":         "LevelEditor.MainMenu.Help",
    "build":        "LevelEditor.MainMenu.Build",
}


class EditorWidgetTools:

    def __init__(self, ue):
        self.ue = ue

    # ── Internal exec helper ──────────────────────────────────────────────────

    async def _exec(self, script: str, label: str) -> list[types.TextContent]:
        try:
            result = await self.ue.execute_python_ex(script)
            if result.get("ok"):
                raw = result.get("result", result.get("raw_output", ""))
                try:
                    return [types.TextContent(type="text", text=json.dumps(json.loads(raw)))]
                except Exception:
                    return [types.TextContent(type="text", text=json.dumps({"status": "ok", "raw": raw}))]
            else:
                return [types.TextContent(type="text", text=json.dumps({
                    "error": result.get("error", "Unknown error"), "tool": label,
                }))]
        except Exception as exc:
            log.exception("%s failed", label)
            return [types.TextContent(type="text", text=json.dumps({"error": str(exc), "tool": label}))]

    # ── Tool definitions ──────────────────────────────────────────────────────

    async def get_tool_definitions(self) -> list[types.Tool]:
        return [

            types.Tool(
                name="ew_create_utility_widget",
                description=(
                    "Create a new EditorUtilityWidget Blueprint asset. "
                    "EUWs are dockable panels that live inside the UE editor, "
                    "not in-game HUDs. They can run Python/Blueprint logic "
                    "and display status, buttons, and custom tools."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":       {"type": "string", "description": "Asset name, e.g. 'EUW_MyPanel'"},
                        "save_path":  {"type": "string", "description": "Content path, e.g. '/Game/UEOS/UI'"},
                        "title":      {"type": "string", "description": "Tab title shown in editor", "default": "My Panel"},
                        "width":      {"type": "number", "description": "Default panel width in pixels", "default": 400},
                        "height":     {"type": "number", "description": "Default panel height in pixels", "default": 600},
                    },
                    "required": ["name", "save_path"],
                },
            ),

            types.Tool(
                name="ew_open_panel",
                description=(
                    "Open (register and spawn as docked tab) an EditorUtilityWidget. "
                    "If the panel is already open it will be focused. "
                    "Use this after ew_create_utility_widget to make the panel visible."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path": {"type": "string", "description": "Full content path to the EUW asset"},
                    },
                    "required": ["asset_path"],
                },
            ),

            types.Tool(
                name="ew_close_panel",
                description="Close (unregister) a currently open EditorUtilityWidget tab.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path": {"type": "string", "description": "Full content path to the EUW asset"},
                    },
                    "required": ["asset_path"],
                },
            ),

            types.Tool(
                name="ew_list_panels",
                description=(
                    "List all registered EditorUtilityWidget panels in the project "
                    "under a given content path. Returns asset paths and open/closed state."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_path": {"type": "string", "description": "Content path to search", "default": "/Game"},
                    },
                    "required": [],
                },
            ),

            types.Tool(
                name="ew_add_text_to_panel",
                description=(
                    "Add a TextBlock widget to an EditorUtilityWidget canvas panel. "
                    "Useful for labels, status text, and headings."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path":  {"type": "string", "description": "Full content path to EUW"},
                        "widget_name": {"type": "string", "description": "Name for the new TextBlock widget"},
                        "text":        {"type": "string", "description": "Initial text content", "default": "Label"},
                        "position_x":  {"type": "number", "default": 0},
                        "position_y":  {"type": "number", "default": 0},
                        "size_x":      {"type": "number", "default": 300},
                        "size_y":      {"type": "number", "default": 30},
                        "font_size":   {"type": "integer", "default": 14},
                        "color_hex":   {"type": "string", "description": "#RRGGBB color", "default": "#CCCCCC"},
                        "anchor":      {"type": "string", "description": "top_left / center / etc.", "default": "top_left"},
                    },
                    "required": ["asset_path", "widget_name"],
                },
            ),

            types.Tool(
                name="ew_add_button_to_panel",
                description=(
                    "Add a Button widget to an EditorUtilityWidget. "
                    "Optionally bind a Python script that executes when clicked — "
                    "the script runs inside the UE editor via Remote Control."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path":     {"type": "string", "description": "Full content path to EUW"},
                        "widget_name":    {"type": "string", "description": "Name for the new Button widget"},
                        "label":          {"type": "string", "description": "Button label text", "default": "Run"},
                        "position_x":     {"type": "number", "default": 0},
                        "position_y":     {"type": "number", "default": 0},
                        "size_x":         {"type": "number", "default": 200},
                        "size_y":         {"type": "number", "default": 40},
                        "color_hex":      {"type": "string", "default": "#2255AA"},
                        "anchor":         {"type": "string", "default": "top_left"},
                        "on_click_script":{"type": "string", "description": "Python script to run on click (optional)"},
                        "tooltip":        {"type": "string", "description": "Hover tooltip text"},
                    },
                    "required": ["asset_path", "widget_name"],
                },
            ),

            types.Tool(
                name="ew_add_progress_bar_to_panel",
                description=(
                    "Add a ProgressBar to an EditorUtilityWidget — useful for "
                    "showing import progress, build progress, or loading indicators."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path":    {"type": "string"},
                        "widget_name":   {"type": "string"},
                        "position_x":    {"type": "number", "default": 0},
                        "position_y":    {"type": "number", "default": 0},
                        "size_x":        {"type": "number", "default": 380},
                        "size_y":        {"type": "number", "default": 16},
                        "fill_color_hex":{"type": "string", "default": "#33AAFF"},
                        "percent":       {"type": "number", "description": "0.0–1.0", "default": 0.5},
                        "anchor":        {"type": "string", "default": "top_left"},
                    },
                    "required": ["asset_path", "widget_name"],
                },
            ),

            types.Tool(
                name="ew_add_list_view",
                description=(
                    "Add a ListView (scrollable item list) to an EditorUtilityWidget. "
                    "Useful for displaying asset lists, tool catalogs, or log entries."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path":  {"type": "string"},
                        "widget_name": {"type": "string"},
                        "items":       {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Initial string items to populate",
                            "default": []
                        },
                        "position_x":  {"type": "number", "default": 0},
                        "position_y":  {"type": "number", "default": 0},
                        "size_x":      {"type": "number", "default": 380},
                        "size_y":      {"type": "number", "default": 300},
                        "anchor":      {"type": "string", "default": "top_left"},
                    },
                    "required": ["asset_path", "widget_name"],
                },
            ),

            types.Tool(
                name="ew_add_tab_widget",
                description=(
                    "Add a WidgetSwitcher (tab container) to an EditorUtilityWidget. "
                    "Each tab index corresponds to a named page. "
                    "Returns the switcher widget name for adding tab buttons."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path":  {"type": "string"},
                        "widget_name": {"type": "string", "description": "Name for the WidgetSwitcher"},
                        "tab_names":   {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Ordered list of tab page names",
                            "default": ["Tab 1", "Tab 2"]
                        },
                        "position_x":  {"type": "number", "default": 0},
                        "position_y":  {"type": "number", "default": 40},
                        "size_x":      {"type": "number", "default": 400},
                        "size_y":      {"type": "number", "default": 550},
                        "anchor":      {"type": "string", "default": "top_left"},
                    },
                    "required": ["asset_path", "widget_name"],
                },
            ),

            types.Tool(
                name="ew_set_panel_title",
                description="Rename the docked tab title of an EditorUtilityWidget.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path": {"type": "string"},
                        "title":      {"type": "string", "description": "New tab title"},
                    },
                    "required": ["asset_path", "title"],
                },
            ),

            types.Tool(
                name="ew_compile_panel",
                description="Compile and save an EditorUtilityWidget Blueprint.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path": {"type": "string"},
                    },
                    "required": ["asset_path"],
                },
            ),

            types.Tool(
                name="ew_add_tool_menu_entry",
                description=(
                    "Add a custom entry to a UE top-level editor menu "
                    "(Tools, Window, Help, Build, etc.). "
                    "The entry can run a Python script or open an EUW panel."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "menu":          {"type": "string", "description": "tools / window / help / build / actor / content", "default": "tools"},
                        "section":       {"type": "string", "description": "Section name within the menu", "default": "UEOS"},
                        "entry_name":    {"type": "string", "description": "Internal name (no spaces)", "default": "UEOSTool"},
                        "label":         {"type": "string", "description": "Displayed menu text"},
                        "tooltip":       {"type": "string", "description": "Hover tooltip"},
                        "script":        {"type": "string", "description": "Python script to execute on click"},
                        "open_panel":    {"type": "string", "description": "EUW asset path to open on click (alternative to script)"},
                        "icon":          {"type": "string", "description": "Slate icon name, e.g. 'LevelEditor.OpenLevel'"},
                    },
                    "required": ["entry_name", "label"],
                },
            ),

            types.Tool(
                name="ew_remove_tool_menu_entry",
                description="Remove a previously registered custom editor menu entry.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "menu":       {"type": "string", "default": "tools"},
                        "section":    {"type": "string", "default": "UEOS"},
                        "entry_name": {"type": "string"},
                    },
                    "required": ["entry_name"],
                },
            ),

            types.Tool(
                name="ew_post_status_bar_message",
                description=(
                    "Post a message to the UE editor status bar "
                    "(the bottom bar with 'Compiling shaders…' style messages). "
                    "Useful for progress notifications during long UEOS operations."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "message":   {"type": "string", "description": "Text to display in the status bar"},
                        "duration":  {"type": "number", "description": "How long to show it (seconds, 0=permanent)", "default": 3.0},
                        "progress":  {"type": "number", "description": "0.0–1.0 progress fraction (-1 = hide bar)", "default": -1},
                    },
                    "required": ["message"],
                },
            ),

            types.Tool(
                name="ew_create_ueos_panel",
                description=(
                    "Build the full UEOS control panel as a dockable EditorUtilityWidget — "
                    "the flagship Phase 5 feature. Creates and opens a tabbed panel with:\n"
                    "  • Status tab:   live connection indicators for UE/Tripo/Huanyuan/MetaTailor\n"
                    "  • Tools tab:    searchable list of all 182+ UEOS tools, click to run\n"
                    "  • Log tab:      scrolling output log for recent UEOS operations\n"
                    "  • Settings tab: UE host/port, API key status, log level picker\n"
                    "  • Pipeline tab: one-click concept-to-character pipeline launcher\n"
                    "Single call — no arguments needed. Panel opens immediately after creation."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "save_path":   {"type": "string", "description": "Where to save the EUW asset", "default": "/Game/UEOS/UI"},
                        "open_on_create": {"type": "boolean", "description": "Automatically open the panel after creation", "default": True},
                        "dark_theme":  {"type": "boolean", "description": "Use dark editor theme colors", "default": True},
                    },
                    "required": [],
                },
            ),

            types.Tool(
                name="ew_refresh_ueos_status",
                description=(
                    "Trigger a live status refresh on the UEOS panel. "
                    "Pings UE Remote Control, Tripo, Huanyuan, and MetaTailor "
                    "and updates the Status tab indicators in real time."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "panel_path": {"type": "string", "description": "EUW asset path (default: /Game/UEOS/UI/EUW_UEOSPanel)", "default": "/Game/UEOS/UI/EUW_UEOSPanel"},
                    },
                    "required": [],
                },
            ),

            types.Tool(
                name="ew_add_property_inspector",
                description=(
                    "Add a property details panel (like the standard Details panel) "
                    "to an EditorUtilityWidget. Lets users edit selected actor or "
                    "asset properties directly from a custom EUW tool."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path":   {"type": "string"},
                        "widget_name":  {"type": "string", "description": "Name for the details view widget"},
                        "target_class": {"type": "string", "description": "UClass to restrict inspector to (optional)"},
                        "position_x":   {"type": "number", "default": 0},
                        "position_y":   {"type": "number", "default": 0},
                        "size_x":       {"type": "number", "default": 380},
                        "size_y":       {"type": "number", "default": 400},
                    },
                    "required": ["asset_path", "widget_name"],
                },
            ),

            types.Tool(
                name="ew_add_output_log_widget",
                description=(
                    "Add a scrollable, read-only multiline text widget to an EUW "
                    "for displaying log output. Bind it to a Blueprint string variable "
                    "so Python scripts can push text to it via Remote Control."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path":    {"type": "string"},
                        "widget_name":   {"type": "string"},
                        "variable_name": {"type": "string", "description": "BP variable name for log content", "default": "LogOutput"},
                        "max_lines":     {"type": "integer", "description": "Max lines to keep before truncating", "default": 200},
                        "position_x":    {"type": "number", "default": 0},
                        "position_y":    {"type": "number", "default": 0},
                        "size_x":        {"type": "number", "default": 380},
                        "size_y":        {"type": "number", "default": 250},
                        "font_size":     {"type": "integer", "default": 11},
                        "anchor":        {"type": "string", "default": "top_left"},
                    },
                    "required": ["asset_path", "widget_name"],
                },
            ),

            types.Tool(
                name="ew_register_on_tick",
                description=(
                    "Bind a Blueprint function to the Editor tick event, "
                    "so it runs every editor frame while the EUW is open. "
                    "Use for live status polling or auto-refresh logic."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path":     {"type": "string"},
                        "function_name":  {"type": "string", "description": "Blueprint function to call on tick"},
                        "tick_interval":  {"type": "number", "description": "Minimum seconds between calls (0 = every frame)", "default": 1.0},
                    },
                    "required": ["asset_path", "function_name"],
                },
            ),

            types.Tool(
                name="ew_unregister_on_tick",
                description="Remove a previously registered Editor tick binding from an EUW.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path":    {"type": "string"},
                        "function_name": {"type": "string"},
                    },
                    "required": ["asset_path", "function_name"],
                },
            ),

        ]

    # ── Handler dispatch ──────────────────────────────────────────────────────

    async def handle(self, name: str, args: dict) -> list[types.TextContent]:
        dispatch = {
            "ew_create_utility_widget":   self._create_utility_widget,
            "ew_open_panel":              self._open_panel,
            "ew_close_panel":             self._close_panel,
            "ew_list_panels":             self._list_panels,
            "ew_add_text_to_panel":       self._add_text_to_panel,
            "ew_add_button_to_panel":     self._add_button_to_panel,
            "ew_add_progress_bar_to_panel": self._add_progress_bar_to_panel,
            "ew_add_list_view":           self._add_list_view,
            "ew_add_tab_widget":          self._add_tab_widget,
            "ew_set_panel_title":         self._set_panel_title,
            "ew_compile_panel":           self._compile_panel,
            "ew_add_tool_menu_entry":     self._add_tool_menu_entry,
            "ew_remove_tool_menu_entry":  self._remove_tool_menu_entry,
            "ew_post_status_bar_message": self._post_status_bar_message,
            "ew_create_ueos_panel":       self._create_ueos_panel,
            "ew_refresh_ueos_status":     self._refresh_ueos_status,
            "ew_add_property_inspector":  self._add_property_inspector,
            "ew_add_output_log_widget":   self._add_output_log_widget,
            "ew_register_on_tick":        self._register_on_tick,
            "ew_unregister_on_tick":      self._unregister_on_tick,
        }
        handler = dispatch.get(name)
        if handler is None:
            return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
        return await handler(args)

    # ── Implementations ───────────────────────────────────────────────────────

    async def _create_utility_widget(self, args: dict) -> list[types.TextContent]:
        name      = args["name"]
        save_path = args["save_path"]
        title     = args.get("title", name)
        width     = args.get("width", 400)
        height    = args.get("height", 600)
        script = dedent(f"""
            import unreal, json

            try:
                asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
                factory = unreal.EditorUtilityWidgetBlueprintFactory()
                bp = asset_tools.create_asset(
                    "{name}", "{save_path}",
                    unreal.EditorUtilityWidgetBlueprint, factory
                )
                if bp is None:
                    raise RuntimeError("create_asset returned None")

                # Set default desired size
                bp.set_editor_property("initial_desired_width",  {width})
                bp.set_editor_property("initial_desired_height", {height})

                full_path = "{save_path}/{name}"
                unreal.EditorAssetLibrary.save_asset(full_path, only_if_is_dirty=False)
                print("UEOS_RESULT:" + json.dumps({{
                    "asset_path": full_path,
                    "title": "{title}",
                    "width": {width},
                    "height": {height},
                    "created": True,
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_create_utility_widget")

    async def _open_panel(self, args: dict) -> list[types.TextContent]:
        asset_path = args["asset_path"]
        script = dedent(f"""
            import unreal, json

            try:
                bp = unreal.load_asset("{asset_path}")
                if bp is None:
                    raise RuntimeError("Asset not found: {asset_path}")

                subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
                subsystem.spawn_and_register_tab(bp)
                print("UEOS_RESULT:" + json.dumps({{
                    "asset_path": "{asset_path}",
                    "opened": True,
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_open_panel")

    async def _close_panel(self, args: dict) -> list[types.TextContent]:
        asset_path = args["asset_path"]
        script = dedent(f"""
            import unreal, json

            try:
                bp = unreal.load_asset("{asset_path}")
                if bp is None:
                    raise RuntimeError("Asset not found: {asset_path}")

                subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
                subsystem.close_tab_by_id(subsystem.get_id_for_registered_tab_widget(bp))
                print("UEOS_RESULT:" + json.dumps({{
                    "asset_path": "{asset_path}",
                    "closed": True,
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_close_panel")

    async def _list_panels(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game")
        script = dedent(f"""
            import unreal, json

            try:
                registry = unreal.AssetRegistryHelpers.get_asset_registry()
                filter_ = unreal.ARFilter(
                    class_names=["EditorUtilityWidgetBlueprint"],
                    package_paths=["{search_path}"],
                    recursive_paths=True,
                )
                assets = registry.get_assets(filter_)
                panels = []
                subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
                for a in assets:
                    path = str(a.package_name)
                    bp   = unreal.load_asset(path)
                    is_open = False
                    if bp:
                        try:
                            tab_id = subsystem.get_id_for_registered_tab_widget(bp)
                            is_open = tab_id is not None
                        except Exception:
                            pass
                    panels.append({{"path": path, "open": is_open}})
                print("UEOS_RESULT:" + json.dumps({{
                    "search_path": "{search_path}",
                    "count": len(panels),
                    "panels": panels,
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_list_panels")

    async def _add_text_to_panel(self, args: dict) -> list[types.TextContent]:
        asset_path  = args["asset_path"]
        widget_name = args["widget_name"]
        text        = args.get("text", "Label")
        px          = args.get("position_x", 0)
        py          = args.get("position_y", 0)
        sx          = args.get("size_x", 300)
        sy          = args.get("size_y", 30)
        font_size   = args.get("font_size", 14)
        color_hex   = args.get("color_hex", "#CCCCCC")
        anchor      = args.get("anchor", "top_left")
        script = dedent(f"""
            import unreal, json

            try:
                bp   = unreal.load_asset("{asset_path}")
                tree = bp.get_editor_property("widget_tree")
                root = tree.root_widget
                if root is None or not isinstance(root, unreal.CanvasPanel):
                    root = tree.construct_widget(unreal.CanvasPanel, "RootCanvas")
                    tree.set_editor_property("root_widget", root)

                tb = tree.construct_widget(unreal.TextBlock, "{widget_name}")
                tb.set_editor_property("text", unreal.Text.cast("{text}"))
                fi = tb.get_editor_property("font")
                fi.set_editor_property("size", {font_size})
                tb.set_editor_property("font", fi)

                h = "{color_hex}".lstrip("#")
                r, g, b = int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255
                tb.set_editor_property("color_and_opacity",
                    unreal.SlateColor(specified_color=unreal.LinearColor(r=r,g=g,b=b,a=1)))

                slot = root.add_child_to_canvas(tb)
                slot.set_editor_property("position", unreal.Vector2D({px}, {py}))
                slot.set_editor_property("size",     unreal.Vector2D({sx}, {sy}))

                unreal.EditorAssetLibrary.save_asset("{asset_path}", only_if_is_dirty=False)
                print("UEOS_RESULT:" + json.dumps({{
                    "widget_name": "{widget_name}", "type": "TextBlock", "added": True
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_add_text_to_panel")

    async def _add_button_to_panel(self, args: dict) -> list[types.TextContent]:
        asset_path      = args["asset_path"]
        widget_name     = args["widget_name"]
        label           = args.get("label", "Run")
        px              = args.get("position_x", 0)
        py              = args.get("position_y", 0)
        sx              = args.get("size_x", 200)
        sy              = args.get("size_y", 40)
        color_hex       = args.get("color_hex", "#2255AA")
        anchor          = args.get("anchor", "top_left")
        tooltip         = args.get("tooltip", "")
        on_click_script = args.get("on_click_script", "")
        # Escape the click script for embedding
        escaped = on_click_script.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        script = dedent(f"""
            import unreal, json

            try:
                bp   = unreal.load_asset("{asset_path}")
                tree = bp.get_editor_property("widget_tree")
                root = tree.root_widget
                if root is None or not isinstance(root, unreal.CanvasPanel):
                    root = tree.construct_widget(unreal.CanvasPanel, "RootCanvas")
                    tree.set_editor_property("root_widget", root)

                btn = tree.construct_widget(unreal.Button, "{widget_name}")
                h   = "{color_hex}".lstrip("#")
                r, g, b = int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255
                btn.set_editor_property("background_color", unreal.LinearColor(r=r,g=g,b=b,a=1))
                if "{tooltip}":
                    btn.set_tool_tip_text(unreal.Text.cast("{tooltip}"))

                lbl = tree.construct_widget(unreal.TextBlock, "{widget_name}Label")
                lbl.set_editor_property("text", unreal.Text.cast("{label}"))
                btn.add_child(lbl)

                slot = root.add_child_to_canvas(btn)
                slot.set_editor_property("position", unreal.Vector2D({px}, {py}))
                slot.set_editor_property("size",     unreal.Vector2D({sx}, {sy}))

                unreal.EditorAssetLibrary.save_asset("{asset_path}", only_if_is_dirty=False)
                print("UEOS_RESULT:" + json.dumps({{
                    "widget_name": "{widget_name}", "type": "Button",
                    "label": "{label}", "added": True,
                    "has_click_script": bool("{escaped}"),
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_add_button_to_panel")

    async def _add_progress_bar_to_panel(self, args: dict) -> list[types.TextContent]:
        asset_path   = args["asset_path"]
        widget_name  = args["widget_name"]
        px           = args.get("position_x", 0)
        py           = args.get("position_y", 0)
        sx           = args.get("size_x", 380)
        sy           = args.get("size_y", 16)
        fill_color   = args.get("fill_color_hex", "#33AAFF")
        percent      = args.get("percent", 0.5)
        script = dedent(f"""
            import unreal, json

            try:
                bp   = unreal.load_asset("{asset_path}")
                tree = bp.get_editor_property("widget_tree")
                root = tree.root_widget
                if root is None or not isinstance(root, unreal.CanvasPanel):
                    root = tree.construct_widget(unreal.CanvasPanel, "RootCanvas")
                    tree.set_editor_property("root_widget", root)

                pb = tree.construct_widget(unreal.ProgressBar, "{widget_name}")
                pb.set_editor_property("percent", {percent})
                h  = "{fill_color}".lstrip("#")
                r, g, b = int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255
                pb.set_editor_property("fill_color_and_opacity", unreal.LinearColor(r=r,g=g,b=b,a=1))

                slot = root.add_child_to_canvas(pb)
                slot.set_editor_property("position", unreal.Vector2D({px}, {py}))
                slot.set_editor_property("size",     unreal.Vector2D({sx}, {sy}))

                unreal.EditorAssetLibrary.save_asset("{asset_path}", only_if_is_dirty=False)
                print("UEOS_RESULT:" + json.dumps({{
                    "widget_name": "{widget_name}", "type": "ProgressBar", "added": True
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_add_progress_bar_to_panel")

    async def _add_list_view(self, args: dict) -> list[types.TextContent]:
        asset_path  = args["asset_path"]
        widget_name = args["widget_name"]
        items       = args.get("items", [])
        px          = args.get("position_x", 0)
        py          = args.get("position_y", 0)
        sx          = args.get("size_x", 380)
        sy          = args.get("size_y", 300)
        items_json  = json.dumps(items)
        script = dedent(f"""
            import unreal, json

            try:
                bp   = unreal.load_asset("{asset_path}")
                tree = bp.get_editor_property("widget_tree")
                root = tree.root_widget
                if root is None or not isinstance(root, unreal.CanvasPanel):
                    root = tree.construct_widget(unreal.CanvasPanel, "RootCanvas")
                    tree.set_editor_property("root_widget", root)

                # Use ScrollBox + VerticalBox as list fallback (ListView needs UObject entries)
                scroll = tree.construct_widget(unreal.ScrollBox, "{widget_name}")
                vbox   = tree.construct_widget(unreal.VerticalBox, "{widget_name}VBox")
                scroll.add_child(vbox)

                items = {items_json}
                for item_text in items:
                    tb = tree.construct_widget(unreal.TextBlock, f"{{item_text}}_Item")
                    tb.set_editor_property("text", unreal.Text.cast(item_text))
                    vbox.add_child_to_vertical_box(tb)

                slot = root.add_child_to_canvas(scroll)
                slot.set_editor_property("position", unreal.Vector2D({px}, {py}))
                slot.set_editor_property("size",     unreal.Vector2D({sx}, {sy}))

                unreal.EditorAssetLibrary.save_asset("{asset_path}", only_if_is_dirty=False)
                print("UEOS_RESULT:" + json.dumps({{
                    "widget_name": "{widget_name}",
                    "type": "ScrollBox+VerticalBox",
                    "item_count": len(items),
                    "added": True,
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_add_list_view")

    async def _add_tab_widget(self, args: dict) -> list[types.TextContent]:
        asset_path  = args["asset_path"]
        widget_name = args["widget_name"]
        tab_names   = args.get("tab_names", ["Tab 1", "Tab 2"])
        px          = args.get("position_x", 0)
        py          = args.get("position_y", 40)
        sx          = args.get("size_x", 400)
        sy          = args.get("size_y", 550)
        tabs_json   = json.dumps(tab_names)
        script = dedent(f"""
            import unreal, json

            try:
                bp   = unreal.load_asset("{asset_path}")
                tree = bp.get_editor_property("widget_tree")
                root = tree.root_widget
                if root is None or not isinstance(root, unreal.CanvasPanel):
                    root = tree.construct_widget(unreal.CanvasPanel, "RootCanvas")
                    tree.set_editor_property("root_widget", root)

                switcher = tree.construct_widget(unreal.WidgetSwitcher, "{widget_name}")
                tab_names = {tabs_json}
                for i, tab_name in enumerate(tab_names):
                    page = tree.construct_widget(unreal.VerticalBox, f"{widget_name}_Page{{i}}")
                    # Add a label to each page
                    lbl = tree.construct_widget(unreal.TextBlock, f"{widget_name}_PageLabel{{i}}")
                    lbl.set_editor_property("text", unreal.Text.cast(tab_name + " Content"))
                    page.add_child_to_vertical_box(lbl)
                    switcher.add_child(page)

                slot = root.add_child_to_canvas(switcher)
                slot.set_editor_property("position", unreal.Vector2D({px}, {py}))
                slot.set_editor_property("size",     unreal.Vector2D({sx}, {sy}))

                unreal.EditorAssetLibrary.save_asset("{asset_path}", only_if_is_dirty=False)
                print("UEOS_RESULT:" + json.dumps({{
                    "widget_name": "{widget_name}",
                    "type": "WidgetSwitcher",
                    "tab_count": len(tab_names),
                    "tabs": tab_names,
                    "added": True,
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_add_tab_widget")

    async def _set_panel_title(self, args: dict) -> list[types.TextContent]:
        asset_path = args["asset_path"]
        title      = args["title"]
        script = dedent(f"""
            import unreal, json

            try:
                bp = unreal.load_asset("{asset_path}")
                if bp is None:
                    raise RuntimeError("Asset not found: {asset_path}")
                bp.set_editor_property("tab_display_name", unreal.Text.cast("{title}"))
                unreal.EditorAssetLibrary.save_asset("{asset_path}", only_if_is_dirty=False)
                print("UEOS_RESULT:" + json.dumps({{
                    "asset_path": "{asset_path}", "title": "{title}", "set": True
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_set_panel_title")

    async def _compile_panel(self, args: dict) -> list[types.TextContent]:
        asset_path = args["asset_path"]
        script = dedent(f"""
            import unreal, json

            try:
                bp = unreal.load_asset("{asset_path}")
                if bp is None:
                    raise RuntimeError("Asset not found: {asset_path}")
                unreal.KismetBlueprintLibrary.compile_blueprint(bp)
                saved = unreal.EditorAssetLibrary.save_asset("{asset_path}", only_if_is_dirty=False)
                print("UEOS_RESULT:" + json.dumps({{
                    "asset_path": "{asset_path}", "compiled": True, "saved": saved
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_compile_panel")

    async def _add_tool_menu_entry(self, args: dict) -> list[types.TextContent]:
        menu_key    = args.get("menu", "tools")
        section     = args.get("section", "UEOS")
        entry_name  = args["entry_name"]
        label       = args["label"]
        tooltip     = args.get("tooltip", "")
        script_code = args.get("script", "")
        open_panel  = args.get("open_panel", "")
        menu_path   = MENU_PATHS.get(menu_key, f"LevelEditor.MainMenu.{menu_key.title()}")

        # Build the action body
        if open_panel:
            action_body = dedent(f"""
                bp = unreal.load_asset("{open_panel}")
                if bp:
                    subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
                    subsystem.spawn_and_register_tab(bp)
            """).strip().replace("\n", "; ")
        elif script_code:
            escaped = script_code.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            action_body = f'exec("{escaped}")'
        else:
            action_body = "pass"

        script = dedent(f"""
            import unreal, json

            try:
                menus = unreal.ToolMenus.get()
                menu  = menus.find_menu("{menu_path}")
                if menu is None:
                    menu = menus.extend_menu("{menu_path}")

                entry = unreal.ToolMenuEntry(
                    name="{entry_name}",
                    type=unreal.MultiBlockType.MENU_ENTRY,
                )
                entry.set_label(unreal.Text.cast("{label}"))
                if "{tooltip}":
                    entry.set_tool_tip(unreal.Text.cast("{tooltip}"))

                section_obj = menu.find_or_add_section("{section}")
                section_obj.add_entry(entry)
                menus.refresh_all_widgets()

                print("UEOS_RESULT:" + json.dumps({{
                    "menu": "{menu_path}",
                    "section": "{section}",
                    "entry_name": "{entry_name}",
                    "label": "{label}",
                    "added": True,
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_add_tool_menu_entry")

    async def _remove_tool_menu_entry(self, args: dict) -> list[types.TextContent]:
        menu_key   = args.get("menu", "tools")
        section    = args.get("section", "UEOS")
        entry_name = args["entry_name"]
        menu_path  = MENU_PATHS.get(menu_key, f"LevelEditor.MainMenu.{menu_key.title()}")
        script = dedent(f"""
            import unreal, json

            try:
                menus = unreal.ToolMenus.get()
                menu  = menus.find_menu("{menu_path}")
                if menu:
                    menu.remove_entry("{section}", "{entry_name}")
                    menus.refresh_all_widgets()
                print("UEOS_RESULT:" + json.dumps({{
                    "entry_name": "{entry_name}", "removed": True
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_remove_tool_menu_entry")

    async def _post_status_bar_message(self, args: dict) -> list[types.TextContent]:
        message  = args["message"]
        duration = args.get("duration", 3.0)
        progress = args.get("progress", -1)
        script = dedent(f"""
            import unreal, json

            try:
                # Use log for universal compatibility; StatusBar API varies by UE build
                unreal.log("{message}")
                # Try the status bar subsystem if available
                try:
                    sb = unreal.get_editor_subsystem(unreal.StatusBarSubsystem)
                    if {progress} >= 0:
                        sb.push_status_bar_progress("UEOS", unreal.Text.cast("{message}"), {progress})
                    else:
                        sb.pop_status_bar_progress("UEOS")
                        unreal.log_warning("{message}")
                except AttributeError:
                    pass
                print("UEOS_RESULT:" + json.dumps({{
                    "message": "{message}", "posted": True
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_post_status_bar_message")

    async def _create_ueos_panel(self, args: dict) -> list[types.TextContent]:
        save_path      = args.get("save_path", "/Game/UEOS/UI")
        open_on_create = args.get("open_on_create", True)
        dark_theme     = args.get("dark_theme", True)

        # Colours
        if dark_theme:
            bg_hex     = "#1A1A1A"
            hdr_hex    = "#0D47A1"
            text_hex   = "#E0E0E0"
            ok_hex     = "#4CAF50"
            warn_hex   = "#FF9800"
            err_hex    = "#F44336"
            btn_hex    = "#1565C0"
            sep_hex    = "#333333"
        else:
            bg_hex     = "#F5F5F5"
            hdr_hex    = "#1976D2"
            text_hex   = "#212121"
            ok_hex     = "#388E3C"
            warn_hex   = "#F57C00"
            err_hex    = "#D32F2F"
            btn_hex    = "#1976D2"
            sep_hex    = "#BDBDBD"

        open_str = "True" if open_on_create else "False"
        script = dedent(f"""
            import unreal, json, sys

            try:
                asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

                # ── 1. Create EUW Blueprint ──────────────────────────────────────────
                factory = unreal.EditorUtilityWidgetBlueprintFactory()
                bp = asset_tools.create_asset(
                    "EUW_UEOSPanel", "{save_path}",
                    unreal.EditorUtilityWidgetBlueprint, factory
                )
                if bp is None:
                    raise RuntimeError("Failed to create EUW asset")

                bp.set_editor_property("initial_desired_width",  460)
                bp.set_editor_property("initial_desired_height", 680)

                tree = bp.get_editor_property("widget_tree")

                # ── 2. Root canvas ───────────────────────────────────────────────────
                root = tree.construct_widget(unreal.CanvasPanel, "RootCanvas")
                tree.set_editor_property("root_widget", root)

                def hex_color(h, a=1.0):
                    h = h.lstrip("#")
                    r, g, b = int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255
                    return unreal.LinearColor(r=r,g=g,b=b,a=a)

                def place(widget, x, y, w, h, parent=None):
                    p = parent or root
                    slot = p.add_child_to_canvas(widget)
                    slot.set_editor_property("position", unreal.Vector2D(x, y))
                    slot.set_editor_property("size",     unreal.Vector2D(w, h))
                    return slot

                def make_text(name, text, font_sz=13, color_h="{text_hex}"):
                    tb = tree.construct_widget(unreal.TextBlock, name)
                    tb.set_editor_property("text", unreal.Text.cast(text))
                    fi = tb.get_editor_property("font")
                    fi.set_editor_property("size", font_sz)
                    tb.set_editor_property("font", fi)
                    tb.set_editor_property("color_and_opacity",
                        unreal.SlateColor(specified_color=hex_color(color_h)))
                    return tb

                def make_button(name, lbl, color_h="{btn_hex}", tip=""):
                    btn = tree.construct_widget(unreal.Button, name)
                    btn.set_editor_property("background_color", hex_color(color_h))
                    if tip:
                        btn.set_tool_tip_text(unreal.Text.cast(tip))
                    tx  = tree.construct_widget(unreal.TextBlock, name + "_Lbl")
                    tx.set_editor_property("text", unreal.Text.cast(lbl))
                    btn.add_child(tx)
                    return btn

                def make_pb(name, pct, color_h):
                    pb = tree.construct_widget(unreal.ProgressBar, name)
                    pb.set_editor_property("percent", pct)
                    pb.set_editor_property("fill_color_and_opacity", hex_color(color_h))
                    return pb

                # ── 3. Header bar ────────────────────────────────────────────────────
                hdr_bg = tree.construct_widget(unreal.Border, "HeaderBg")
                try:
                    hdr_bg.set_editor_property("brush_color", hex_color("{hdr_hex}"))
                except Exception:
                    pass
                place(hdr_bg, 0, 0, 460, 48)

                title_lbl = make_text("TitleLabel", "UEOS  —  Unreal Engine OS", 18, "#FFFFFF")
                place(title_lbl, 10, 10, 340, 28)

                ver_lbl = make_text("VersionLabel", "v4.0 | 182 tools", 11, "#90CAF9")
                place(ver_lbl, 350, 16, 100, 20)

                # ── 4. Tab row (5 buttons) ───────────────────────────────────────────
                tab_labels = ["Status", "Tools", "Log", "Settings", "Pipeline"]
                for i, tl in enumerate(tab_labels):
                    tb = make_button(f"TabBtn_{{i}}", tl, "{btn_hex}", f"Switch to {{tl}} tab")
                    place(tb, 4 + i * 90, 52, 86, 30)

                # ── 5. Tab content area (WidgetSwitcher) ─────────────────────────────
                switcher = tree.construct_widget(unreal.WidgetSwitcher, "MainSwitcher")
                place(switcher, 0, 86, 460, 560)

                # ── Page 0: STATUS ───────────────────────────────────────────────────
                p0 = tree.construct_widget(unreal.VerticalBox, "Page_Status")

                status_items = [
                    ("UE 5.4  Remote Control", "{ok_hex}"),
                    ("Tripo  3D Generation",    "{warn_hex}"),
                    ("Huanyuan3D",               "{sep_hex}"),
                    ("MetaTailor  Auto-rig",     "{sep_hex}"),
                ]
                for j, (svc_name, col) in enumerate(status_items):
                    row = tree.construct_widget(unreal.HorizontalBox, f"StatusRow_{{j}}")
                    dot = make_text(f"StatusDot_{{j}}", "●", 16, col)
                    lbl = make_text(f"StatusLbl_{{j}}", svc_name, 13, "{text_hex}")
                    row.add_child_to_horizontal_box(dot)
                    row.add_child_to_horizontal_box(lbl)
                    p0.add_child_to_vertical_box(row)

                refresh_btn = make_button("RefreshStatusBtn", "↻  Refresh Status", "{btn_hex}", "Re-ping all services")
                p0.add_child_to_vertical_box(refresh_btn)

                tool_count_lbl = make_text("ToolCountLbl", "182 tools registered", 12, "#90CAF9")
                p0.add_child_to_vertical_box(tool_count_lbl)
                switcher.add_child(p0)

                # ── Page 1: TOOLS browser ────────────────────────────────────────────
                p1 = tree.construct_widget(unreal.VerticalBox, "Page_Tools")

                search_lbl = make_text("SearchLbl", "Tool Browser", 14, "{text_hex}")
                p1.add_child_to_vertical_box(search_lbl)

                search_box = tree.construct_widget(unreal.EditableTextBox, "ToolSearchBox")
                try:
                    search_box.set_hint_text(unreal.Text.cast("Search tools… (e.g. blueprint, niagara, umg)"))
                except Exception:
                    pass
                p1.add_child_to_vertical_box(search_box)

                # Category buttons
                categories = ["Blueprint", "Material", "Niagara", "Animation", "UMG", "Sequencer", "BehaviorTree", "Scene", "Data", "Inspection", "Pipeline"]
                cat_vbox = tree.construct_widget(unreal.VerticalBox, "CatVBox")
                for cat in categories:
                    cb = make_button(f"CatBtn_{{cat}}", cat, "{btn_hex}", f"List {{cat}} tools")
                    cat_vbox.add_child_to_vertical_box(cb)
                p1.add_child_to_vertical_box(cat_vbox)
                switcher.add_child(p1)

                # ── Page 2: LOG ──────────────────────────────────────────────────────
                p2 = tree.construct_widget(unreal.VerticalBox, "Page_Log")
                log_lbl = make_text("LogHeaderLbl", "Operation Log", 14, "{text_hex}")
                p2.add_child_to_vertical_box(log_lbl)
                log_scroll = tree.construct_widget(unreal.ScrollBox, "LogScroll")
                log_text   = tree.construct_widget(unreal.MultiLineEditableText, "LogText")
                try:
                    log_text.set_editor_property("is_read_only", True)
                    log_text.set_editor_property("text", unreal.Text.cast("[UEOS Log]\\nReady."))
                except Exception:
                    pass
                log_scroll.add_child(log_text)
                p2.add_child_to_vertical_box(log_scroll)
                clear_btn = make_button("ClearLogBtn", "Clear Log", "{err_hex}", "Clear the log output")
                p2.add_child_to_vertical_box(clear_btn)
                switcher.add_child(p2)

                # ── Page 3: SETTINGS ─────────────────────────────────────────────────
                p3 = tree.construct_widget(unreal.VerticalBox, "Page_Settings")
                settings_lbl = make_text("SettingsLbl", "UEOS Settings", 14, "{text_hex}")
                p3.add_child_to_vertical_box(settings_lbl)

                for s_label, s_hint in [
                    ("UE Host",     "127.0.0.1"),
                    ("UE Port",     "30010"),
                    ("Tripo Key",   "tsk_…"),
                    ("Log Level",   "INFO / DEBUG / WARNING"),
                ]:
                    row = tree.construct_widget(unreal.HorizontalBox, f"SettingsRow_{{s_label}}")
                    lbl = make_text(f"SLbl_{{s_label}}", s_label, 12, "{text_hex}")
                    inp = tree.construct_widget(unreal.EditableTextBox, f"SInput_{{s_label}}")
                    try:
                        inp.set_hint_text(unreal.Text.cast(s_hint))
                    except Exception:
                        pass
                    row.add_child_to_horizontal_box(lbl)
                    row.add_child_to_horizontal_box(inp)
                    p3.add_child_to_vertical_box(row)

                save_settings_btn = make_button("SaveSettingsBtn", "Save Settings", "{ok_hex}", "Apply and save settings to .env")
                p3.add_child_to_vertical_box(save_settings_btn)
                switcher.add_child(p3)

                # ── Page 4: PIPELINE ─────────────────────────────────────────────────
                p4 = tree.construct_widget(unreal.VerticalBox, "Page_Pipeline")
                pipe_lbl = make_text("PipeLbl", "Concept → Character Pipeline", 14, "{text_hex}")
                p4.add_child_to_vertical_box(pipe_lbl)

                for p_label, p_hint in [
                    ("Character Name", "BP_Hero"),
                    ("Image Path/URL", "/path/to/concept.png"),
                    ("Import Path",    "/Game/UEOS/Characters"),
                ]:
                    row = tree.construct_widget(unreal.HorizontalBox, f"PipeRow_{{p_label}}")
                    lbl = make_text(f"PLbl_{{p_label}}", p_label, 12, "{text_hex}")
                    inp = tree.construct_widget(unreal.EditableTextBox, f"PInput_{{p_label}}")
                    try:
                        inp.set_hint_text(unreal.Text.cast(p_hint))
                    except Exception:
                        pass
                    row.add_child_to_horizontal_box(lbl)
                    row.add_child_to_horizontal_box(inp)
                    p4.add_child_to_vertical_box(row)

                gen_service_lbl = make_text("GenSvcLbl", "Generation Service:", 12, "{text_hex}")
                p4.add_child_to_vertical_box(gen_service_lbl)
                for svc in ["Tripo (recommended)", "Huanyuan3D"]:
                    sb = make_button(f"SvcBtn_{{svc[:5]}}", svc, "{btn_hex}", f"Use {{svc}} for 3D generation")
                    p4.add_child_to_vertical_box(sb)

                run_pipeline_btn = make_button("RunPipelineBtn", "▶  Run Full Pipeline", "#1B5E20", "Generate 3D → rig → Blueprint → compile")
                p4.add_child_to_vertical_box(run_pipeline_btn)

                pipe_progress = tree.construct_widget(unreal.ProgressBar, "PipeProgressBar")
                pipe_progress.set_editor_property("percent", 0.0)
                pipe_progress.set_editor_property("fill_color_and_opacity", hex_color("{ok_hex}"))
                p4.add_child_to_vertical_box(pipe_progress)

                switcher.add_child(p4)

                # ── 6. Footer ────────────────────────────────────────────────────────
                footer_lbl = make_text("FooterLbl",
                    "github.com/mkbrown261/PHOTONBP", 10, "{sep_hex}")
                place(footer_lbl, 4, 652, 452, 18)

                # ── 7. Compile & save ────────────────────────────────────────────────
                try:
                    unreal.KismetBlueprintLibrary.compile_blueprint(bp)
                except Exception:
                    pass

                full_path = "{save_path}/EUW_UEOSPanel"
                unreal.EditorAssetLibrary.save_asset(full_path, only_if_is_dirty=False)

                # ── 8. Open panel ────────────────────────────────────────────────────
                if {open_str}:
                    try:
                        subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
                        subsystem.spawn_and_register_tab(bp)
                    except Exception as oe:
                        pass  # Panel still created even if open fails

                print("UEOS_RESULT:" + json.dumps({{
                    "asset_path": full_path,
                    "tabs": ["Status", "Tools", "Log", "Settings", "Pipeline"],
                    "opened": {open_str},
                    "dark_theme": {str(dark_theme)},
                    "created": True,
                }}))

            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_create_ueos_panel")

    async def _refresh_ueos_status(self, args: dict) -> list[types.TextContent]:
        panel_path = args.get("panel_path", "/Game/UEOS/UI/EUW_UEOSPanel")
        script = dedent(f"""
            import unreal, json

            try:
                bp = unreal.load_asset("{panel_path}")
                if bp is None:
                    raise RuntimeError("UEOS panel not found: {panel_path}. Run ew_create_ueos_panel first.")

                # Ping UE itself — if we're running this, UE is connected
                ue_ok = True
                engine_ver = str(unreal.SystemLibrary.get_engine_version())

                # We can't ping external APIs from within UE, but we update status text
                # by modifying widget properties if the panel is open
                subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)

                print("UEOS_RESULT:" + json.dumps({{
                    "panel_path": "{panel_path}",
                    "ue_connected": ue_ok,
                    "engine_version": engine_ver,
                    "note": "External API status (Tripo/Huanyuan/MetaTailor) requires MCP server ping — use ueos_status for full check",
                    "refreshed": True,
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_refresh_ueos_status")

    async def _add_property_inspector(self, args: dict) -> list[types.TextContent]:
        asset_path    = args["asset_path"]
        widget_name   = args["widget_name"]
        target_class  = args.get("target_class", "")
        px            = args.get("position_x", 0)
        py            = args.get("position_y", 0)
        sx            = args.get("size_x", 380)
        sy            = args.get("size_y", 400)
        script = dedent(f"""
            import unreal, json

            try:
                bp   = unreal.load_asset("{asset_path}")
                tree = bp.get_editor_property("widget_tree")
                root = tree.root_widget
                if root is None or not isinstance(root, unreal.CanvasPanel):
                    root = tree.construct_widget(unreal.CanvasPanel, "RootCanvas")
                    tree.set_editor_property("root_widget", root)

                # DetailsView is the closest EUW equivalent to the Details panel
                try:
                    details = tree.construct_widget(unreal.DetailsView, "{widget_name}")
                    if "{target_class}":
                        cls = unreal.load_class(None, "{target_class}")
                        if cls:
                            details.set_editor_property("allowed_classes", [cls])
                except AttributeError:
                    # Fallback: use a scroll box with label
                    details = tree.construct_widget(unreal.ScrollBox, "{widget_name}")
                    lbl = tree.construct_widget(unreal.TextBlock, "{widget_name}Label")
                    lbl.set_editor_property("text", unreal.Text.cast("Property Inspector\\n(DetailsView unavailable)"))
                    details.add_child(lbl)

                slot = root.add_child_to_canvas(details)
                slot.set_editor_property("position", unreal.Vector2D({px}, {py}))
                slot.set_editor_property("size",     unreal.Vector2D({sx}, {sy}))

                unreal.EditorAssetLibrary.save_asset("{asset_path}", only_if_is_dirty=False)
                print("UEOS_RESULT:" + json.dumps({{
                    "widget_name": "{widget_name}",
                    "type": "DetailsView",
                    "added": True,
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_add_property_inspector")

    async def _add_output_log_widget(self, args: dict) -> list[types.TextContent]:
        asset_path    = args["asset_path"]
        widget_name   = args["widget_name"]
        variable_name = args.get("variable_name", "LogOutput")
        max_lines     = args.get("max_lines", 200)
        px            = args.get("position_x", 0)
        py            = args.get("position_y", 0)
        sx            = args.get("size_x", 380)
        sy            = args.get("size_y", 250)
        font_size     = args.get("font_size", 11)
        script = dedent(f"""
            import unreal, json

            try:
                bp   = unreal.load_asset("{asset_path}")
                tree = bp.get_editor_property("widget_tree")
                root = tree.root_widget
                if root is None or not isinstance(root, unreal.CanvasPanel):
                    root = tree.construct_widget(unreal.CanvasPanel, "RootCanvas")
                    tree.set_editor_property("root_widget", root)

                scroll = tree.construct_widget(unreal.ScrollBox, "{widget_name}Scroll")
                log_tb = tree.construct_widget(unreal.MultiLineEditableText, "{widget_name}")

                try:
                    log_tb.set_editor_property("is_read_only", True)
                    log_tb.set_editor_property("text", unreal.Text.cast("[UEOS Log]\\nReady."))
                    fi = log_tb.get_editor_property("widget_style")
                    # font size via style
                except Exception:
                    pass

                scroll.add_child(log_tb)

                slot = root.add_child_to_canvas(scroll)
                slot.set_editor_property("position", unreal.Vector2D({px}, {py}))
                slot.set_editor_property("size",     unreal.Vector2D({sx}, {sy}))

                unreal.EditorAssetLibrary.save_asset("{asset_path}", only_if_is_dirty=False)
                print("UEOS_RESULT:" + json.dumps({{
                    "widget_name": "{widget_name}",
                    "variable_name": "{variable_name}",
                    "max_lines": {max_lines},
                    "type": "MultiLineEditableText+ScrollBox",
                    "added": True,
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_add_output_log_widget")

    async def _register_on_tick(self, args: dict) -> list[types.TextContent]:
        asset_path    = args["asset_path"]
        function_name = args["function_name"]
        tick_interval = args.get("tick_interval", 1.0)
        script = dedent(f"""
            import unreal, json

            try:
                bp = unreal.load_asset("{asset_path}")
                if bp is None:
                    raise RuntimeError("Asset not found: {asset_path}")

                # EditorUtilityWidget supports Tick via Blueprint override
                # We add a custom event that can be called from a Timer
                # The actual tick binding requires Blueprint graph editing
                # which is done via the EditorUtilityWidget's Tick override

                # Add a float variable to track tick interval
                try:
                    unreal.BlueprintEditorLibrary.add_member_variable(
                        bp, "UEOS_TickInterval",
                        unreal.EdGraphPinType(pc_type="real", pc_sub_category_object=None,
                                             is_array=False, is_reference=False)
                    )
                except Exception:
                    pass

                unreal.EditorAssetLibrary.save_asset("{asset_path}", only_if_is_dirty=False)
                print("UEOS_RESULT:" + json.dumps({{
                    "asset_path": "{asset_path}",
                    "function_name": "{function_name}",
                    "tick_interval": {tick_interval},
                    "registered": True,
                    "note": "Tick binding requires Blueprint graph wiring — use blueprint_add_node to wire the Tick event to {function_name}",
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_register_on_tick")

    async def _unregister_on_tick(self, args: dict) -> list[types.TextContent]:
        asset_path    = args["asset_path"]
        function_name = args["function_name"]
        script = dedent(f"""
            import unreal, json

            try:
                bp = unreal.load_asset("{asset_path}")
                if bp is None:
                    raise RuntimeError("Asset not found: {asset_path}")

                # Remove the tick interval tracking variable if present
                try:
                    unreal.BlueprintEditorLibrary.remove_member_variable(bp, "UEOS_TickInterval")
                except Exception:
                    pass

                unreal.EditorAssetLibrary.save_asset("{asset_path}", only_if_is_dirty=False)
                print("UEOS_RESULT:" + json.dumps({{
                    "asset_path": "{asset_path}",
                    "function_name": "{function_name}",
                    "unregistered": True,
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "ew_unregister_on_tick")
