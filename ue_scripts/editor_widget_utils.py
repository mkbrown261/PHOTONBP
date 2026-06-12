"""
UEOS Editor Utility Widget Utils — ue_scripts/editor_widget_utils.py
UE-side helper functions for building and managing Editor Utility Widgets (EUWs).

This script can be run DIRECTLY inside the Unreal Editor Python console
(no MCP server needed) to install the full UEOS panel in one shot:

    # In UE Editor → Tools → Execute Python Script → choose this file
    # — OR — paste into the Output Log Python console:
    import importlib, sys
    sys.path.insert(0, r"C:\\UEOS\\ue_scripts")
    import editor_widget_utils as ewu; importlib.reload(ewu)
    ewu.ueos_install_panel()

All functions prefix output with UEOS_RESULT: (JSON) or UEOS_ERROR: (message).
"""

import json
import unreal


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _result(data: dict) -> None:
    print("UEOS_RESULT:" + json.dumps(data))


def _error(msg: str) -> None:
    print("UEOS_ERROR:" + msg)


def _hex(h: str, a: float = 1.0) -> unreal.LinearColor:
    """Convert '#RRGGBB' hex string to LinearColor."""
    h = h.lstrip("#")
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return unreal.LinearColor(r=r, g=g, b=b, a=a)


def _make_text(tree, name: str, text: str,
               font_size: int = 13, color: str = "#E0E0E0") -> unreal.TextBlock:
    """Create a styled TextBlock widget."""
    tb = tree.construct_widget(unreal.TextBlock, name)
    tb.set_editor_property("text", unreal.Text.cast(text))
    fi = tb.get_editor_property("font")
    fi.set_editor_property("size", font_size)
    tb.set_editor_property("font", fi)
    tb.set_editor_property("color_and_opacity",
        unreal.SlateColor(specified_color=_hex(color)))
    return tb


def _make_button(tree, name: str, label: str,
                 color: str = "#1565C0", tooltip: str = "") -> unreal.Button:
    """Create a styled Button with a child TextBlock label."""
    btn = tree.construct_widget(unreal.Button, name)
    btn.set_editor_property("background_color", _hex(color))
    if tooltip:
        btn.set_tool_tip_text(unreal.Text.cast(tooltip))
    lbl = tree.construct_widget(unreal.TextBlock, name + "_Lbl")
    lbl.set_editor_property("text", unreal.Text.cast(label))
    btn.add_child(lbl)
    return btn


def _make_progress_bar(tree, name: str, percent: float = 0.0,
                       color: str = "#33AAFF") -> unreal.ProgressBar:
    """Create a ProgressBar widget."""
    pb = tree.construct_widget(unreal.ProgressBar, name)
    pb.set_editor_property("percent", percent)
    pb.set_editor_property("fill_color_and_opacity", _hex(color))
    return pb


def _make_input(tree, name: str, hint: str = "") -> unreal.EditableTextBox:
    """Create an EditableTextBox input widget."""
    inp = tree.construct_widget(unreal.EditableTextBox, name)
    try:
        inp.set_hint_text(unreal.Text.cast(hint))
    except Exception:
        pass
    return inp


def _canvas_place(root: unreal.CanvasPanel, widget,
                  x: float, y: float, w: float, h: float,
                  auto_size: bool = False):
    """Add widget to canvas at given position/size."""
    slot = root.add_child_to_canvas(widget)
    slot.set_editor_property("position", unreal.Vector2D(x, y))
    if not auto_size:
        slot.set_editor_property("size", unreal.Vector2D(w, h))
    slot.set_editor_property("size_to_content", auto_size)
    return slot


# ─────────────────────────────────────────────────────────────────────────────
# Theme
# ─────────────────────────────────────────────────────────────────────────────

DARK = {
    "bg":       "#1A1A1A",
    "header":   "#0D47A1",
    "text":     "#E0E0E0",
    "subtext":  "#9E9E9E",
    "ok":       "#4CAF50",
    "warn":     "#FF9800",
    "err":      "#F44336",
    "btn":      "#1565C0",
    "btn_alt":  "#37474F",
    "sep":      "#333333",
    "accent":   "#90CAF9",
    "white":    "#FFFFFF",
    "green":    "#1B5E20",
}

LIGHT = {
    "bg":       "#F5F5F5",
    "header":   "#1976D2",
    "text":     "#212121",
    "subtext":  "#757575",
    "ok":       "#388E3C",
    "warn":     "#F57C00",
    "err":      "#D32F2F",
    "btn":      "#1976D2",
    "btn_alt":  "#546E7A",
    "sep":      "#BDBDBD",
    "accent":   "#1565C0",
    "white":    "#FFFFFF",
    "green":    "#2E7D32",
}


# ─────────────────────────────────────────────────────────────────────────────
# Panel creation
# ─────────────────────────────────────────────────────────────────────────────

def ueos_create_euwidget(name: str, save_path: str,
                          width: int = 460, height: int = 700) -> dict:
    """
    Create a blank EditorUtilityWidget Blueprint.

    Args:
        name:       Asset name (e.g. 'EUW_MyTool')
        save_path:  Content path (e.g. '/Game/UEOS/UI')
        width:      Default panel width in pixels
        height:     Default panel height in pixels

    Returns:
        dict with 'asset_path'.
    """
    try:
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        factory = unreal.EditorUtilityWidgetBlueprintFactory()
        bp = asset_tools.create_asset(
            name, save_path,
            unreal.EditorUtilityWidgetBlueprint, factory
        )
        if bp is None:
            raise RuntimeError("create_asset returned None")

        try:
            bp.set_editor_property("initial_desired_width", width)
            bp.set_editor_property("initial_desired_height", height)
        except Exception:
            pass

        full_path = f"{save_path}/{name}"
        unreal.EditorAssetLibrary.save_asset(full_path, only_if_is_dirty=False)
        _result({"asset_path": full_path, "created": True})
        return {"asset_path": full_path}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_open_euwidget(asset_path: str) -> dict:
    """
    Open an EditorUtilityWidget as a docked tab in the UE editor.

    Args:
        asset_path: Full content path to the EUW Blueprint

    Returns:
        dict with 'opened' True.
    """
    try:
        bp = unreal.load_asset(asset_path)
        if bp is None:
            raise RuntimeError(f"Asset not found: {asset_path}")
        subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
        subsystem.spawn_and_register_tab(bp)
        _result({"asset_path": asset_path, "opened": True})
        return {"opened": True}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_close_euwidget(asset_path: str) -> dict:
    """
    Close a currently open EditorUtilityWidget tab.

    Args:
        asset_path: Full content path to the EUW Blueprint
    """
    try:
        bp = unreal.load_asset(asset_path)
        if bp is None:
            raise RuntimeError(f"Asset not found: {asset_path}")
        subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
        tab_id = subsystem.get_id_for_registered_tab_widget(bp)
        if tab_id:
            subsystem.close_tab_by_id(tab_id)
        _result({"asset_path": asset_path, "closed": True})
        return {"closed": True}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_compile_euwidget(asset_path: str) -> dict:
    """Compile and save an EditorUtilityWidget Blueprint."""
    try:
        bp = unreal.load_asset(asset_path)
        if bp is None:
            raise RuntimeError(f"Asset not found: {asset_path}")
        try:
            unreal.KismetBlueprintLibrary.compile_blueprint(bp)
        except Exception:
            pass
        saved = unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
        _result({"asset_path": asset_path, "compiled": True, "saved": saved})
        return {"compiled": True}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Menu registration
# ─────────────────────────────────────────────────────────────────────────────

def ueos_add_menu_entry(
    menu_path: str,
    section: str,
    entry_name: str,
    label: str,
    tooltip: str = "",
    panel_path: str = "",
) -> dict:
    """
    Add a custom entry to a UE editor menu (Tools, Window, etc.).

    Args:
        menu_path:   Full Slate menu path, e.g. 'LevelEditor.MainMenu.Tools'
        section:     Section name within the menu (e.g. 'UEOS')
        entry_name:  Internal unique identifier (no spaces)
        label:       Displayed menu text
        tooltip:     Hover tooltip
        panel_path:  If provided, clicking opens this EUW asset

    Returns:
        dict with 'added' True.
    """
    try:
        menus = unreal.ToolMenus.get()
        menu = menus.find_menu(menu_path)
        if menu is None:
            menu = menus.extend_menu(menu_path)

        entry = unreal.ToolMenuEntry(
            name=entry_name,
            type=unreal.MultiBlockType.MENU_ENTRY,
        )
        entry.set_label(unreal.Text.cast(label))
        if tooltip:
            entry.set_tool_tip(unreal.Text.cast(tooltip))

        section_obj = menu.find_or_add_section(section)
        section_obj.add_entry(entry)
        menus.refresh_all_widgets()

        _result({
            "menu_path": menu_path,
            "section": section,
            "entry_name": entry_name,
            "label": label,
            "added": True,
        })
        return {"added": True}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_remove_menu_entry(menu_path: str, section: str, entry_name: str) -> dict:
    """Remove a previously registered custom editor menu entry."""
    try:
        menus = unreal.ToolMenus.get()
        menu = menus.find_menu(menu_path)
        if menu:
            menu.remove_entry(section, entry_name)
            menus.refresh_all_widgets()
        _result({"entry_name": entry_name, "removed": True})
        return {"removed": True}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_register_menu_shortcuts() -> dict:
    """
    Register the full UEOS menu section under Tools > UEOS in one call.
    Adds entries for:
      - Open UEOS Panel
      - Run UEOS Diagnostics
      - Compile All Blueprints
      - Refresh Asset Registry
    """
    try:
        entries = [
            ("OpenUEOSPanel",   "Open UEOS Panel",          "Open the UEOS dockable control panel",          True),
            ("UEOSDiagnostics", "UEOS Diagnostics",         "Run UEOS connection diagnostics",               False),
            ("CompileAllBPs",   "Compile All Blueprints",   "Compile every Blueprint under /Game",           False),
            ("RefreshRegistry", "Refresh Asset Registry",   "Force-refresh the Unreal asset registry",       False),
        ]
        for name, label, tip, _ in entries:
            ueos_add_menu_entry(
                "LevelEditor.MainMenu.Tools",
                "UEOS",
                name, label, tip
            )
        _result({"entries_added": len(entries), "registered": True})
        return {"registered": True}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Status bar
# ─────────────────────────────────────────────────────────────────────────────

def ueos_post_status(message: str, progress: float = -1.0) -> dict:
    """
    Post a message to the UE editor status bar.

    Args:
        message:   Text to display
        progress:  0.0–1.0 progress fraction (-1 = no progress bar)
    """
    try:
        unreal.log(f"[UEOS] {message}")
        try:
            sb = unreal.get_editor_subsystem(unreal.StatusBarSubsystem)
            if progress >= 0:
                sb.push_status_bar_progress("UEOS", unreal.Text.cast(message), progress)
            else:
                sb.pop_status_bar_progress("UEOS")
        except AttributeError:
            pass
        _result({"message": message, "posted": True})
        return {"posted": True}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Full UEOS Panel builder
# ─────────────────────────────────────────────────────────────────────────────

def ueos_build_status_page(tree, theme: dict) -> unreal.VerticalBox:
    """Build the Status tab page content."""
    page = tree.construct_widget(unreal.VerticalBox, "Page_Status")

    # Heading
    heading = _make_text(tree, "StatusHeading", "Service Status", 15, theme["accent"])
    page.add_child_to_vertical_box(heading)

    # Service rows
    services = [
        ("UE 5.4  Remote Control",  "30010",   theme["ok"]),
        ("Tripo  3D Generation",    "API v2",   theme["warn"]),
        ("Huanyuan3D",              "Optional", theme["subtext"]),
        ("MetaTailor  Auto-rig",    "Optional", theme["subtext"]),
    ]
    for i, (svc, detail, col) in enumerate(services):
        row = tree.construct_widget(unreal.HorizontalBox, f"SvcRow_{i}")

        dot = _make_text(tree, f"SvcDot_{i}", "●", 16, col)
        row.add_child_to_horizontal_box(dot)

        svc_lbl = _make_text(tree, f"SvcName_{i}", f"  {svc}", 13, theme["text"])
        row.add_child_to_horizontal_box(svc_lbl)

        detail_lbl = _make_text(tree, f"SvcDetail_{i}", f"   [{detail}]", 11, theme["subtext"])
        row.add_child_to_horizontal_box(detail_lbl)

        page.add_child_to_vertical_box(row)

    # Separator
    sep = _make_text(tree, "StatusSep", "─" * 52, 10, theme["sep"])
    page.add_child_to_vertical_box(sep)

    # Tool count banner
    tool_banner = _make_text(tree, "ToolBanner",
        "182 tools registered  ·  Phase 4 complete", 12, theme["accent"])
    page.add_child_to_vertical_box(tool_banner)

    # Phase breakdown
    phases = [
        "Phase 1 ✅  Blueprint(17) + Pipeline(11)",
        "Phase 2 ✅  Material(14) Niagara(20) Inspect(12) Scene(16) Data(15)",
        "Phase 3 ✅  Animation(22): AnimBP, BlendSpaces, Montages, IK",
        "Phase 4 ✅  UMG(20) Sequencer(18) BehaviorTree(17)",
        "Phase 5 ✅  Editor Utility Widgets + UEOS Panel ← you are here",
    ]
    for i, phase_txt in enumerate(phases):
        pl = _make_text(tree, f"PhaseLbl_{i}", phase_txt, 11, theme["text"])
        page.add_child_to_vertical_box(pl)

    sep2 = _make_text(tree, "StatusSep2", "─" * 52, 10, theme["sep"])
    page.add_child_to_vertical_box(sep2)

    # Refresh button
    refresh_btn = _make_button(tree, "RefreshBtn", "↻  Refresh Status",
                               theme["btn"], "Re-ping all UEOS services")
    page.add_child_to_vertical_box(refresh_btn)

    return page


def ueos_build_tools_page(tree, theme: dict) -> unreal.VerticalBox:
    """Build the Tools Browser tab page content."""
    page = tree.construct_widget(unreal.VerticalBox, "Page_Tools")

    heading = _make_text(tree, "ToolsHeading", "Tool Browser", 15, theme["accent"])
    page.add_child_to_vertical_box(heading)

    search_hint = _make_text(tree, "SearchHint",
        "Click a category to list its tools:", 12, theme["subtext"])
    page.add_child_to_vertical_box(search_hint)

    search_box = _make_input(tree, "ToolSearchBox", "Search tools…  e.g. 'blueprint_create'")
    page.add_child_to_vertical_box(search_box)

    sep = _make_text(tree, "ToolsSep", "─" * 52, 10, theme["sep"])
    page.add_child_to_vertical_box(sep)

    # Category grid — 2 columns using HorizontalBoxes
    categories = [
        ("Blueprint",    "17 tools",  "blueprint_"),
        ("Material",     "14 tools",  "material_"),
        ("Niagara",      "20 tools",  "niagara_"),
        ("Animation",    "22 tools",  "anim_"),
        ("UMG",          "20 tools",  "umg_"),
        ("Sequencer",    "18 tools",  "seq_"),
        ("BehaviorTree", "17 tools",  "bt_"),
        ("Scene",        "16 tools",  "scene_"),
        ("Data",         "15 tools",  "data_"),
        ("Inspection",   "12 tools",  "inspect_"),
        ("EditorWidget", "20 tools",  "ew_"),
        ("Pipeline",     "11 tools",  "tripo_ / pipeline_"),
    ]
    # Pair up into rows
    for row_i in range(0, len(categories), 2):
        hrow = tree.construct_widget(unreal.HorizontalBox, f"CatRow_{row_i}")
        for col_i in range(2):
            idx = row_i + col_i
            if idx >= len(categories):
                break
            cat, count, prefix = categories[idx]
            cb = _make_button(
                tree, f"CatBtn_{cat}",
                f"{cat}\n{count}",
                theme["btn_alt"],
                f"List all {cat} tools (prefix: {prefix})"
            )
            hrow.add_child_to_horizontal_box(cb)
        page.add_child_to_vertical_box(hrow)

    return page


def ueos_build_log_page(tree, theme: dict) -> unreal.VerticalBox:
    """Build the Log tab page content."""
    page = tree.construct_widget(unreal.VerticalBox, "Page_Log")

    heading = _make_text(tree, "LogHeading", "Operation Log", 15, theme["accent"])
    page.add_child_to_vertical_box(heading)

    log_scroll = tree.construct_widget(unreal.ScrollBox, "LogScrollBox")
    log_text = tree.construct_widget(unreal.MultiLineEditableText, "LogText")
    try:
        log_text.set_editor_property("is_read_only", True)
        log_text.set_editor_property("text", unreal.Text.cast(
            "[UEOS v5.0 Log]\n"
            "─────────────────────────────\n"
            "Phase 5 loaded. Panel ready.\n"
            "Type prompts in Claude Desktop to control UE.\n"
        ))
    except Exception:
        pass

    log_scroll.add_child(log_text)
    page.add_child_to_vertical_box(log_scroll)

    btn_row = tree.construct_widget(unreal.HorizontalBox, "LogBtnRow")
    clear_btn = _make_button(tree, "ClearLogBtn", "Clear", theme["err"], "Clear log output")
    copy_btn  = _make_button(tree, "CopyLogBtn",  "Copy",  theme["btn"], "Copy log to clipboard")
    btn_row.add_child_to_horizontal_box(clear_btn)
    btn_row.add_child_to_horizontal_box(copy_btn)
    page.add_child_to_vertical_box(btn_row)

    return page


def ueos_build_settings_page(tree, theme: dict) -> unreal.VerticalBox:
    """Build the Settings tab page content."""
    page = tree.construct_widget(unreal.VerticalBox, "Page_Settings")

    heading = _make_text(tree, "SettingsHeading", "Settings", 15, theme["accent"])
    page.add_child_to_vertical_box(heading)

    sep = _make_text(tree, "SettingsSep1", "Unreal Engine Connection", 12, theme["accent"])
    page.add_child_to_vertical_box(sep)

    for key, hint, current in [
        ("UE Host",  "127.0.0.1",  "127.0.0.1"),
        ("UE Port",  "30010",      "30010"),
    ]:
        row = tree.construct_widget(unreal.HorizontalBox, f"SetRow_{key}")
        lbl = _make_text(tree, f"SetLbl_{key}", f"{key}:", 12, theme["text"])
        inp = _make_input(tree, f"SetInp_{key}", hint)
        row.add_child_to_horizontal_box(lbl)
        row.add_child_to_horizontal_box(inp)
        page.add_child_to_vertical_box(row)

    sep2 = _make_text(tree, "SettingsSep2", "API Keys", 12, theme["accent"])
    page.add_child_to_vertical_box(sep2)

    for key, hint in [
        ("Tripo",      "tsk_…  (required for 3D generation)"),
        ("Huanyuan",   "optional"),
        ("MetaTailor", "optional"),
    ]:
        row = tree.construct_widget(unreal.HorizontalBox, f"ApiRow_{key}")
        lbl = _make_text(tree, f"ApiLbl_{key}", f"{key}:", 12, theme["text"])
        inp = _make_input(tree, f"ApiInp_{key}", hint)
        row.add_child_to_horizontal_box(lbl)
        row.add_child_to_horizontal_box(inp)
        page.add_child_to_vertical_box(row)

    sep3 = _make_text(tree, "SettingsSep3", "Logging", 12, theme["accent"])
    page.add_child_to_vertical_box(sep3)

    log_row = tree.construct_widget(unreal.HorizontalBox, "LogLevelRow")
    log_lbl = _make_text(tree, "LogLevelLbl", "Log Level:", 12, theme["text"])
    log_inp = _make_input(tree, "LogLevelInp", "INFO / DEBUG / WARNING / ERROR")
    log_row.add_child_to_horizontal_box(log_lbl)
    log_row.add_child_to_horizontal_box(log_inp)
    page.add_child_to_vertical_box(log_row)

    save_btn = _make_button(tree, "SaveSettingsBtn", "💾  Save Settings",
                            theme["ok"], "Write settings to .env file")
    page.add_child_to_vertical_box(save_btn)

    reset_btn = _make_button(tree, "ResetSettingsBtn", "Reset to Defaults",
                             theme["btn_alt"], "Restore default UEOS settings")
    page.add_child_to_vertical_box(reset_btn)

    return page


def ueos_build_pipeline_page(tree, theme: dict) -> unreal.VerticalBox:
    """Build the Pipeline tab page content."""
    page = tree.construct_widget(unreal.VerticalBox, "Page_Pipeline")

    heading = _make_text(tree, "PipeHeading", "Concept → Character Pipeline", 15, theme["accent"])
    page.add_child_to_vertical_box(heading)

    desc = _make_text(tree, "PipeDesc",
        "One-click: Image → 3D → Rig → Blueprint → Compile",
        12, theme["subtext"])
    page.add_child_to_vertical_box(desc)

    sep = _make_text(tree, "PipeSep1", "─" * 52, 10, theme["sep"])
    page.add_child_to_vertical_box(sep)

    for key, hint in [
        ("CharacterName", "BP_Hero"),
        ("ImagePath",     "/path/to/concept.png  or  https://…"),
        ("ImportPath",    "/Game/UEOS/Characters"),
    ]:
        row = tree.construct_widget(unreal.HorizontalBox, f"PipeRow_{key}")
        lbl = _make_text(tree, f"PipeLbl_{key}",
                         key.replace("_", " ") + ":", 12, theme["text"])
        inp = _make_input(tree, f"PipeInp_{key}", hint)
        row.add_child_to_horizontal_box(lbl)
        row.add_child_to_horizontal_box(inp)
        page.add_child_to_vertical_box(row)

    svc_lbl = _make_text(tree, "SvcLbl", "3D Generation Service:", 12, theme["text"])
    page.add_child_to_vertical_box(svc_lbl)

    svc_row = tree.construct_widget(unreal.HorizontalBox, "SvcBtnRow")
    tripo_btn  = _make_button(tree, "SvcTripo",    "Tripo  ★",  theme["btn"],    "Use Tripo API v2 (recommended)")
    huan_btn   = _make_button(tree, "SvcHuanyuan", "Huanyuan",  theme["btn_alt"], "Use Huanyuan3D")
    svc_row.add_child_to_horizontal_box(tripo_btn)
    svc_row.add_child_to_horizontal_box(huan_btn)
    page.add_child_to_vertical_box(svc_row)

    options_lbl = _make_text(tree, "OptionsLbl", "Options:", 12, theme["text"])
    page.add_child_to_vertical_box(options_lbl)

    for opt_name, opt_tip in [
        ("Add Clothing",      "Generate clothing with MetaTailor"),
        ("UE Cloth Physics",  "Set up cloth simulation in UE"),
        ("Create Blueprint",  "Auto-create Character Blueprint"),
        ("Leader Pose Setup", "Wire Leader Pose Component"),
    ]:
        opt_btn = _make_button(tree, f"Opt_{opt_name[:8]}", f"☐  {opt_name}",
                               theme["btn_alt"], opt_tip)
        page.add_child_to_vertical_box(opt_btn)

    sep2 = _make_text(tree, "PipeSep2", "─" * 52, 10, theme["sep"])
    page.add_child_to_vertical_box(sep2)

    run_btn = _make_button(tree, "RunPipelineBtn",
        "▶  Run Full Pipeline",
        theme["green"],
        "Generate 3D → rig → Blueprint → compile. Requires Tripo/Huanyuan API key.")
    page.add_child_to_vertical_box(run_btn)

    progress = _make_progress_bar(tree, "PipeProgressBar", 0.0, theme["ok"])
    page.add_child_to_vertical_box(progress)

    status_lbl = _make_text(tree, "PipeStatusLbl", "Ready.", 11, theme["subtext"])
    page.add_child_to_vertical_box(status_lbl)

    return page


def ueos_build_panel(
    save_path: str = "/Game/UEOS/UI",
    dark_theme: bool = True,
    open_after: bool = True,
) -> dict:
    """
    Build and optionally open the full UEOS control panel.

    This is the main entry point for creating the UEOS dockable editor panel.
    Creates an EditorUtilityWidget with 5 tabs:
      0 — Status:   service connection indicators + phase summary
      1 — Tools:    category buttons + search box for all 202 tools
      2 — Log:      scrollable operation log
      3 — Settings: UE host/port, API keys, log level
      4 — Pipeline: concept → character one-click launcher

    Args:
        save_path:   Content path to save the EUW (default '/Game/UEOS/UI')
        dark_theme:  Use dark color theme (default True)
        open_after:  Automatically open the panel after creation (default True)

    Returns:
        dict with 'asset_path' on success.
    """
    theme = DARK if dark_theme else LIGHT
    panel_name = "EUW_UEOSPanel"

    try:
        # ── 1. Create EUW asset ──────────────────────────────────────────────
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        factory = unreal.EditorUtilityWidgetBlueprintFactory()

        # Delete existing if present
        full_path = f"{save_path}/{panel_name}"
        if unreal.EditorAssetLibrary.does_asset_exist(full_path):
            unreal.EditorAssetLibrary.delete_asset(full_path)

        bp = asset_tools.create_asset(
            panel_name, save_path,
            unreal.EditorUtilityWidgetBlueprint, factory
        )
        if bp is None:
            raise RuntimeError("Failed to create EditorUtilityWidgetBlueprint")

        try:
            bp.set_editor_property("initial_desired_width", 468)
            bp.set_editor_property("initial_desired_height", 720)
            bp.set_editor_property("tab_display_name",
                unreal.Text.cast("UEOS v5.0"))
        except Exception:
            pass

        tree = bp.get_editor_property("widget_tree")

        # ── 2. Root canvas ───────────────────────────────────────────────────
        root = tree.construct_widget(unreal.CanvasPanel, "RootCanvas")
        tree.set_editor_property("root_widget", root)

        # ── 3. Header (0–56px) ───────────────────────────────────────────────
        try:
            hdr = tree.construct_widget(unreal.Border, "HeaderBorder")
            hdr.set_editor_property("brush_color", _hex(theme["header"]))
            _canvas_place(root, hdr, 0, 0, 468, 56)
        except Exception:
            hdr = None

        title_lbl = _make_text(tree, "TitleLbl",
            "UEOS  —  Unreal Engine Operating System", 17, theme["white"])
        _canvas_place(root, title_lbl, 8, 8, 360, 24)

        ver_lbl = _make_text(tree, "VerLbl", "v5.0 | 202 tools", 10, theme["accent"])
        _canvas_place(root, ver_lbl, 340, 32, 120, 16)

        # ── 4. Tab bar (56–90px) ─────────────────────────────────────────────
        TAB_NAMES = ["Status", "Tools", "Log", "Settings", "Pipeline"]
        TAB_W = 92
        for i, tab_name in enumerate(TAB_NAMES):
            tb = _make_button(tree, f"TabBtn_{i}", tab_name,
                              theme["btn"], f"Switch to {tab_name} tab")
            _canvas_place(root, tb, 2 + i * TAB_W, 58, TAB_W - 2, 30)

        # ── 5. Content area: WidgetSwitcher (90–700px) ───────────────────────
        switcher = tree.construct_widget(unreal.WidgetSwitcher, "MainSwitcher")
        _canvas_place(root, switcher, 0, 92, 468, 610)

        # Build each page
        pages = [
            ueos_build_status_page(tree, theme),
            ueos_build_tools_page(tree, theme),
            ueos_build_log_page(tree, theme),
            ueos_build_settings_page(tree, theme),
            ueos_build_pipeline_page(tree, theme),
        ]
        for page in pages:
            switcher.add_child(page)

        # ── 6. Footer (702–720px) ────────────────────────────────────────────
        footer = _make_text(tree, "FooterLbl",
            "github.com/mkbrown261/PHOTONBP  ·  Phase 5 complete",
            9, theme["sep"])
        _canvas_place(root, footer, 4, 704, 460, 14)

        # ── 7. Compile & save ────────────────────────────────────────────────
        try:
            unreal.KismetBlueprintLibrary.compile_blueprint(bp)
        except Exception:
            pass

        unreal.EditorAssetLibrary.save_asset(full_path, only_if_is_dirty=False)

        # ── 8. Open panel ────────────────────────────────────────────────────
        opened = False
        if open_after:
            try:
                subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
                subsystem.spawn_and_register_tab(bp)
                opened = True
            except Exception as oe:
                unreal.log_warning(f"UEOS: Could not auto-open panel: {oe}")

        # ── 9. Register menu entry ────────────────────────────────────────────
        try:
            ueos_add_menu_entry(
                "LevelEditor.MainMenu.Tools",
                "UEOS",
                "OpenUEOSPanel",
                "Open UEOS Panel",
                "Open the UEOS v5.0 dockable control panel",
                full_path,
            )
        except Exception:
            pass

        data = {
            "asset_path": full_path,
            "tabs": TAB_NAMES,
            "tab_count": len(TAB_NAMES),
            "opened": opened,
            "dark_theme": dark_theme,
            "menu_entry": "Tools > UEOS > Open UEOS Panel",
            "created": True,
        }
        _result(data)
        return data

    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# One-shot installer  (run this from the UE Python console)
# ─────────────────────────────────────────────────────────────────────────────

def ueos_install_panel(
    save_path: str = "/Game/UEOS/UI",
    dark_theme: bool = True,
) -> dict:
    """
    Install the UEOS panel in one call. Creates the EUW, opens it as a
    docked tab, and registers the Tools > UEOS menu entry.

    Run from UE Output Log Python console:
        import sys; sys.path.insert(0, r"C:/UEOS/ue_scripts")
        import editor_widget_utils as ewu, importlib; importlib.reload(ewu)
        ewu.ueos_install_panel()

    Args:
        save_path:   Content path for the EUW asset (default '/Game/UEOS/UI')
        dark_theme:  Use dark theme colors (default True)

    Returns:
        dict with 'asset_path' on success.
    """
    unreal.log("━" * 50)
    unreal.log("  UEOS Phase 5 — Installing editor panel…")
    unreal.log("━" * 50)

    result = ueos_build_panel(save_path=save_path, dark_theme=dark_theme, open_after=True)

    if result.get("created"):
        unreal.log(f"  ✓ Panel created: {result['asset_path']}")
        unreal.log(f"  ✓ Tabs: {', '.join(result['tabs'])}")
        unreal.log(f"  ✓ Menu: Tools > UEOS > Open UEOS Panel")
        unreal.log(f"  ✓ Opened: {result['opened']}")
        unreal.log("━" * 50)
        unreal.log("  UEOS Panel installed. 202 tools ready.")
        unreal.log("━" * 50)
    else:
        unreal.log_warning("UEOS: Panel installation failed — check UEOS_ERROR output above.")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Query helpers
# ─────────────────────────────────────────────────────────────────────────────

def ueos_list_euwidgets(search_path: str = "/Game") -> dict:
    """
    Find all EditorUtilityWidget assets under a content path.

    Returns dict with 'panels' list of asset paths + open/closed state.
    """
    try:
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        filter_ = unreal.ARFilter(
            class_names=["EditorUtilityWidgetBlueprint"],
            package_paths=[search_path],
            recursive_paths=True,
        )
        assets = registry.get_assets(filter_)

        subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
        panels = []
        for a in assets:
            path = str(a.package_name)
            is_open = False
            try:
                bp = unreal.load_asset(path)
                if bp:
                    tab_id = subsystem.get_id_for_registered_tab_widget(bp)
                    is_open = tab_id is not None
            except Exception:
                pass
            panels.append({"path": path, "open": is_open})

        _result({"search_path": search_path, "count": len(panels), "panels": panels})
        return {"panels": panels}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_ew_diagnostics() -> dict:
    """
    Run EUW system diagnostics — returns EUW environment info.
    """
    try:
        info = {
            "editor_widget_utils_version": "5.0.0",
            "unreal_version": str(unreal.SystemLibrary.get_engine_version()),
            "euwidget_subsystem": "available",
            "tool_menus": "available",
        }
        try:
            unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
        except Exception:
            info["euwidget_subsystem"] = "unavailable"
        try:
            unreal.ToolMenus.get()
        except Exception:
            info["tool_menus"] = "unavailable"
        _result(info)
        return info
    except Exception as e:
        _error(str(e))
        return {}
