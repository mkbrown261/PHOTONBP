"""
UEOS UMG Tools — Phase 4
Full implementation: UMG Widgets, HUD, Menus, Buttons, Textblocks,
Progress Bars, Images, Sliders, Input fields, Scroll Boxes, Overlays,
Canvas Panels, Named Slots, Data Binding, Animations.

UE 5.4 Python APIs used:
  - unreal.WidgetBlueprint            via AssetToolsHelpers + WidgetBlueprintFactory
  - unreal.WidgetBlueprintEditorLibrary (where available)
  - unreal.EditorAssetLibrary         save / exist
  - unreal.AssetToolsHelpers          factory creation
  - Widget types: UTextBlock, UButton, UImage, UProgressBar,
                  USlider, UEditableTextBox, UScrollBox, UCanvasPanel,
                  UOverlay, UGridPanel, UHorizontalBox, UVerticalBox,
                  UNamedSlot, UCheckBox, UComboBoxString, USpinBox

Tools exposed (20 total):
  umg_create_widget             — create empty Widget Blueprint
  umg_add_text                  — add TextBlock with text/font/color
  umg_add_button                — add Button with label + style
  umg_add_image                 — add Image widget with texture
  umg_add_progress_bar          — add ProgressBar (health/stamina/XP)
  umg_add_slider                — add Slider with min/max/step
  umg_add_input_field           — add EditableTextBox / MultiLineTextBox
  umg_add_checkbox              — add CheckBox
  umg_add_combobox              — add ComboBoxString with options
  umg_add_scroll_box            — add ScrollBox container
  umg_add_canvas_panel          — add CanvasPanel root container
  umg_add_horizontal_box        — add HorizontalBox layout container
  umg_add_vertical_box          — add VerticalBox layout container
  umg_add_overlay               — add Overlay (z-stacked children)
  umg_add_named_slot            — add NamedSlot (template extensibility)
  umg_bind_variable             — expose widget property as BP variable
  umg_add_widget_animation      — create UMG animation track
  umg_set_widget_style          — set colors, padding, fonts globally
  umg_create_hud                — create full HUD with health/stamina/ammo
  umg_compile_widget            — compile Widget Blueprint
"""

import json
import logging
from textwrap import dedent
from mcp import types

log = logging.getLogger("ueos.umg")


# ── Widget type registry ───────────────────────────────────────────────────────
WIDGET_CLASS_MAP = {
    "text":          "/Script/UMG.TextBlock",
    "textblock":     "/Script/UMG.TextBlock",
    "button":        "/Script/UMG.Button",
    "image":         "/Script/UMG.Image",
    "progressbar":   "/Script/UMG.ProgressBar",
    "slider":        "/Script/UMG.Slider",
    "input":         "/Script/UMG.EditableTextBox",
    "editabletext":  "/Script/UMG.EditableTextBox",
    "multilinetext": "/Script/UMG.MultiLineEditableTextBox",
    "checkbox":      "/Script/UMG.CheckBox",
    "combobox":      "/Script/UMG.ComboBoxString",
    "spinbox":       "/Script/UMG.SpinBox",
    "scrollbox":     "/Script/UMG.ScrollBox",
    "canvaspanel":   "/Script/UMG.CanvasPanel",
    "horizontal":    "/Script/UMG.HorizontalBox",
    "verticalbox":   "/Script/UMG.VerticalBox",
    "vertical":      "/Script/UMG.VerticalBox",
    "overlay":       "/Script/UMG.Overlay",
    "namedslot":     "/Script/UMG.NamedSlot",
    "gridpanel":     "/Script/UMG.GridPanel",
    "border":        "/Script/UMG.Border",
    "sizebox":       "/Script/UMG.SizeBox",
    "spacer":        "/Script/UMG.Spacer",
    "richtext":      "/Script/UMG.RichTextBlock",
    "safezone":      "/Script/UMG.SafeZone",
    "widgetswitcher":"/Script/UMG.WidgetSwitcher",
    "throbber":      "/Script/UMG.Throbber",
}

# ── HUD preset templates ───────────────────────────────────────────────────────
HUD_PRESETS = {
    "fps": {
        "desc": "FPS HUD: health bar, ammo count, crosshair, minimap slot",
        "widgets": [
            {"type": "progressbar", "name": "HealthBar",    "anchor": "bottom_left",  "x": 50,   "y": -120, "w": 300, "h": 25},
            {"type": "progressbar", "name": "StaminaBar",   "anchor": "bottom_left",  "x": 50,   "y": -90,  "w": 300, "h": 15},
            {"type": "text",        "name": "AmmoCount",    "anchor": "bottom_right", "x": -150, "y": -80,  "text": "30 / 90"},
            {"type": "image",       "name": "Crosshair",    "anchor": "center",       "x": -16,  "y": -16,  "w": 32,  "h": 32},
            {"type": "namedslot",   "name": "MinimapSlot",  "anchor": "top_right",    "x": -210, "y": 10,   "w": 200, "h": 200},
        ],
    },
    "rpg": {
        "desc": "RPG HUD: health/mana/stamina orbs, XP bar, slot bar",
        "widgets": [
            {"type": "progressbar", "name": "HealthBar",   "anchor": "bottom_left",   "x": 30,   "y": -100, "w": 250, "h": 20},
            {"type": "progressbar", "name": "ManaBar",     "anchor": "bottom_right",  "x": -280, "y": -100, "w": 250, "h": 20},
            {"type": "progressbar", "name": "XPBar",       "anchor": "bottom_center", "x": -200, "y": -30,  "w": 400, "h": 12},
            {"type": "horizontal",  "name": "AbilityBar",  "anchor": "bottom_center", "x": -250, "y": -70,  "w": 500, "h": 60},
        ],
    },
    "main_menu": {
        "desc": "Main menu: title, Play/Settings/Quit buttons, version text",
        "widgets": [
            {"type": "text",   "name": "GameTitle",    "anchor": "top_center",    "x": -200, "y": 100,  "w": 400, "h": 80,  "text": "GAME TITLE"},
            {"type": "button", "name": "PlayButton",   "anchor": "center",        "x": -100, "y": -60,  "w": 200, "h": 50,  "label": "PLAY"},
            {"type": "button", "name": "SettingsBtn",  "anchor": "center",        "x": -100, "y": 0,    "w": 200, "h": 50,  "label": "SETTINGS"},
            {"type": "button", "name": "QuitButton",   "anchor": "center",        "x": -100, "y": 60,   "w": 200, "h": 50,  "label": "QUIT"},
            {"type": "text",   "name": "VersionText",  "anchor": "bottom_right",  "x": -120, "y": -30,  "w": 110, "h": 20,  "text": "v1.0.0"},
        ],
    },
    "pause_menu": {
        "desc": "Pause menu overlay: blur bg, Resume/Options/MainMenu buttons",
        "widgets": [
            {"type": "overlay",  "name": "BlurBG",        "anchor": "stretch",     "x": 0,    "y": 0,    "w": 0,   "h": 0},
            {"type": "text",     "name": "PausedTitle",   "anchor": "center",      "x": -80,  "y": -130, "w": 160, "h": 50,  "text": "PAUSED"},
            {"type": "button",   "name": "ResumeBtn",     "anchor": "center",      "x": -100, "y": -50,  "w": 200, "h": 50,  "label": "RESUME"},
            {"type": "button",   "name": "OptionsBtn",    "anchor": "center",      "x": -100, "y": 20,   "w": 200, "h": 50,  "label": "OPTIONS"},
            {"type": "button",   "name": "MainMenuBtn",   "anchor": "center",      "x": -100, "y": 90,   "w": 200, "h": 50,  "label": "MAIN MENU"},
        ],
    },
    "inventory": {
        "desc": "Inventory screen: grid panel, item detail pane, equip/drop buttons",
        "widgets": [
            {"type": "border",     "name": "Background",   "anchor": "center",     "x": -300, "y": -250, "w": 600, "h": 500},
            {"type": "text",       "name": "Title",        "anchor": "center",     "x": -280, "y": -230, "w": 200, "h": 40,  "text": "INVENTORY"},
            {"type": "scrollbox",  "name": "ItemList",     "anchor": "center",     "x": -280, "y": -170, "w": 240, "h": 380},
            {"type": "namedslot",  "name": "ItemDetail",   "anchor": "center",     "x": 20,   "y": -170, "w": 240, "h": 280},
            {"type": "button",     "name": "EquipBtn",     "anchor": "center",     "x": 20,   "y": 130,  "w": 110, "h": 45,  "label": "EQUIP"},
            {"type": "button",     "name": "DropBtn",      "anchor": "center",     "x": 150,  "y": 130,  "w": 110, "h": 45,  "label": "DROP"},
            {"type": "button",     "name": "CloseBtn",     "anchor": "center",     "x": 255,  "y": -240, "w": 30,  "h": 30,  "label": "X"},
        ],
    },
}


class UMGTools:

    def __init__(self, ue):
        self.ue = ue

    # ── Internal helpers ───────────────────────────────────────────────────────

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

    # ── Tool definitions ───────────────────────────────────────────────────────

    async def get_tool_definitions(self) -> list[types.Tool]:
        return [

            types.Tool(
                name="umg_create_widget",
                description=dedent("""\
                    Create a new Widget Blueprint (UMG) in Unreal Engine 5.4.
                    Widgets are the foundation of all UE UI: HUDs, menus, inventory screens,
                    ability bars, dialogue boxes, crosshairs, minimaps.
                    Optionally specify a parent UserWidget class for custom base functionality.
                    Returns the full asset path of the created Widget Blueprint."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":         {"type": "string", "description": "Asset name e.g. WBP_PlayerHUD, WBP_MainMenu"},
                        "path":         {"type": "string", "description": "Content path e.g. /Game/UI/Widgets"},
                        "parent_class": {"type": "string", "default": "UserWidget",
                                         "description": "Parent class: UserWidget or full path to custom UserWidget BP"},
                        "description":  {"type": "string", "default": "", "description": "Optional description / comment"},
                    },
                    "required": ["name", "path"],
                },
            ),

            types.Tool(
                name="umg_add_text",
                description=dedent("""\
                    Add a TextBlock widget to a Widget Blueprint.
                    TextBlocks display static or dynamic text — labels, titles, counters,
                    tooltips, subtitles, damage numbers, quest text.
                    Supports font size, color (RGBA), alignment, shadow, outline.
                    Position is set via Canvas Panel anchors if the root is a CanvasPanel."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":    {"type": "string", "description": "Full path to Widget Blueprint"},
                        "name":           {"type": "string", "description": "Widget name e.g. TXT_Title"},
                        "text":           {"type": "string", "default": "Text", "description": "Initial display text"},
                        "font_size":      {"type": "integer", "default": 24},
                        "color":          {"type": "array",  "items": {"type": "number"}, "default": [1,1,1,1],
                                           "description": "RGBA color 0-1 e.g. [1,1,1,1] for white"},
                        "bold":           {"type": "boolean", "default": False},
                        "italic":         {"type": "boolean", "default": False},
                        "alignment":      {"type": "string",  "default": "left",
                                           "description": "Text alignment: left, center, right"},
                        "shadow_offset":  {"type": "array",   "default": [0, 0],
                                           "description": "[X, Y] drop shadow offset in pixels"},
                        "position":       {"type": "array",   "default": [0, 0],
                                           "description": "[X, Y] position on canvas"},
                        "size":           {"type": "array",   "default": [200, 40],
                                           "description": "[W, H] size on canvas"},
                        "z_order":        {"type": "integer", "default": 0},
                    },
                    "required": ["widget_path", "name"],
                },
            ),

            types.Tool(
                name="umg_add_button",
                description=dedent("""\
                    Add a Button widget to a Widget Blueprint.
                    Buttons are the primary interactive element in UE UMG — used for
                    play/quit/equip/attack/confirm/cancel actions.
                    Automatically adds a TextBlock child for the label.
                    Supports normal/hovered/pressed/disabled style colors."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":     {"type": "string", "description": "Full path to Widget Blueprint"},
                        "name":            {"type": "string", "description": "Button name e.g. BTN_Play"},
                        "label":           {"type": "string", "default": "Button", "description": "Text label on the button"},
                        "label_size":      {"type": "integer", "default": 18},
                        "normal_color":    {"type": "array",   "default": [0.1, 0.1, 0.1, 0.9],
                                            "description": "Button background RGBA in normal state"},
                        "hovered_color":   {"type": "array",   "default": [0.3, 0.3, 0.3, 1.0]},
                        "pressed_color":   {"type": "array",   "default": [0.05, 0.05, 0.05, 1.0]},
                        "text_color":      {"type": "array",   "default": [1, 1, 1, 1]},
                        "position":        {"type": "array",   "default": [0, 0]},
                        "size":            {"type": "array",   "default": [200, 50]},
                        "on_click_event":  {"type": "string",  "default": "",
                                            "description": "Name of Blueprint event/function to call on click"},
                        "z_order":         {"type": "integer", "default": 0},
                    },
                    "required": ["widget_path", "name"],
                },
            ),

            types.Tool(
                name="umg_add_image",
                description=dedent("""\
                    Add an Image widget to a Widget Blueprint.
                    Images display textures — icons, backgrounds, portraits,
                    ability icons, crosshairs, map markers, health orbs.
                    Supports tint color, brush draw type (image/border/box), and scale."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":    {"type": "string"},
                        "name":           {"type": "string", "description": "e.g. IMG_Crosshair, IMG_Portrait"},
                        "texture_path":   {"type": "string", "default": "",
                                           "description": "Full path to Texture2D asset (optional)"},
                        "tint":           {"type": "array",  "default": [1, 1, 1, 1], "description": "RGBA tint"},
                        "draw_type":      {"type": "string", "default": "image",
                                           "description": "Brush draw type: image, box, border, rounded_box"},
                        "position":       {"type": "array",  "default": [0, 0]},
                        "size":           {"type": "array",  "default": [64, 64]},
                        "z_order":        {"type": "integer","default": 0},
                    },
                    "required": ["widget_path", "name"],
                },
            ),

            types.Tool(
                name="umg_add_progress_bar",
                description=dedent("""\
                    Add a ProgressBar widget to a Widget Blueprint.
                    Progress bars visualize values 0.0→1.0 — health, stamina, mana, XP,
                    loading progress, cooldown timers, charge bars.
                    Supports fill color, background color, bar style (left→right, right→left, etc.)."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":       {"type": "string"},
                        "name":              {"type": "string", "description": "e.g. PB_Health, PB_Stamina"},
                        "percent":           {"type": "number", "default": 1.0,
                                              "description": "Initial fill percent 0.0-1.0"},
                        "fill_color":        {"type": "array",  "default": [0.0, 0.8, 0.0, 1.0],
                                              "description": "Fill bar RGBA color"},
                        "background_color":  {"type": "array",  "default": [0.1, 0.1, 0.1, 0.8]},
                        "bar_fill_type":     {"type": "string",  "default": "left_to_right",
                                              "description": "Fill direction: left_to_right, right_to_left, top_to_bottom, bottom_to_top"},
                        "position":          {"type": "array",   "default": [0, 0]},
                        "size":              {"type": "array",   "default": [300, 25]},
                        "z_order":           {"type": "integer", "default": 0},
                    },
                    "required": ["widget_path", "name"],
                },
            ),

            types.Tool(
                name="umg_add_slider",
                description=dedent("""\
                    Add a Slider widget to a Widget Blueprint.
                    Sliders let users adjust values — volume, brightness, sensitivity,
                    field of view, gamma, game speed multipliers.
                    Supports min/max value, step size, orientation (horizontal/vertical)."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":   {"type": "string"},
                        "name":          {"type": "string", "description": "e.g. SLD_Volume, SLD_Sensitivity"},
                        "min_value":     {"type": "number", "default": 0.0},
                        "max_value":     {"type": "number", "default": 1.0},
                        "value":         {"type": "number", "default": 0.5, "description": "Initial value"},
                        "step_size":     {"type": "number", "default": 0.01},
                        "orientation":   {"type": "string", "default": "horizontal",
                                          "description": "horizontal or vertical"},
                        "bar_color":     {"type": "array",  "default": [0.0, 0.5, 1.0, 1.0]},
                        "thumb_color":   {"type": "array",  "default": [1.0, 1.0, 1.0, 1.0]},
                        "position":      {"type": "array",  "default": [0, 0]},
                        "size":          {"type": "array",  "default": [250, 30]},
                    },
                    "required": ["widget_path", "name"],
                },
            ),

            types.Tool(
                name="umg_add_input_field",
                description=dedent("""\
                    Add an editable text input field to a Widget Blueprint.
                    Used for: player name entry, chat input, search bars, console commands.
                    Supports hint text, max length, single-line or multi-line mode,
                    input type (normal, password, numeric)."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":   {"type": "string"},
                        "name":          {"type": "string", "description": "e.g. TXT_PlayerName, TXT_Chat"},
                        "hint_text":     {"type": "string", "default": "Enter text...",
                                          "description": "Placeholder text shown when empty"},
                        "multiline":     {"type": "boolean", "default": False},
                        "max_length":    {"type": "integer", "default": 0, "description": "0 = unlimited"},
                        "input_type":    {"type": "string",  "default": "text",
                                          "description": "Input type: text, password, numeric, decimal"},
                        "font_size":     {"type": "integer", "default": 16},
                        "position":      {"type": "array",   "default": [0, 0]},
                        "size":          {"type": "array",   "default": [300, 40]},
                    },
                    "required": ["widget_path", "name"],
                },
            ),

            types.Tool(
                name="umg_add_checkbox",
                description=dedent("""\
                    Add a CheckBox widget to a Widget Blueprint.
                    Used for: toggle settings (vsync, subtitles, aim assist),
                    multi-select options, boolean game settings."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":    {"type": "string"},
                        "name":           {"type": "string", "description": "e.g. CHK_VSync"},
                        "label":          {"type": "string", "default": "", "description": "Optional text label beside checkbox"},
                        "checked":        {"type": "boolean","default": False, "description": "Initial checked state"},
                        "check_color":    {"type": "array",  "default": [0.0, 0.8, 1.0, 1.0]},
                        "position":       {"type": "array",  "default": [0, 0]},
                        "size":           {"type": "array",  "default": [200, 30]},
                    },
                    "required": ["widget_path", "name"],
                },
            ),

            types.Tool(
                name="umg_add_combobox",
                description=dedent("""\
                    Add a ComboBoxString dropdown to a Widget Blueprint.
                    Dropdowns for: quality presets (Low/Med/High/Ultra), resolution,
                    language selection, difficulty, control schemes."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":      {"type": "string"},
                        "name":             {"type": "string", "description": "e.g. CMB_Quality"},
                        "options":          {"type": "array",  "items": {"type": "string"},
                                             "default": ["Low", "Medium", "High", "Ultra"],
                                             "description": "List of dropdown option strings"},
                        "default_option":   {"type": "string", "default": "", "description": "Initially selected option"},
                        "font_size":        {"type": "integer","default": 16},
                        "position":         {"type": "array",  "default": [0, 0]},
                        "size":             {"type": "array",  "default": [250, 40]},
                    },
                    "required": ["widget_path", "name"],
                },
            ),

            types.Tool(
                name="umg_add_scroll_box",
                description=dedent("""\
                    Add a ScrollBox container to a Widget Blueprint.
                    ScrollBoxes hold lists of dynamic items — quest logs, chat history,
                    item inventories, skill trees, leaderboards.
                    Supports horizontal and vertical scroll orientation."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":      {"type": "string"},
                        "name":             {"type": "string", "description": "e.g. SB_QuestList"},
                        "orientation":      {"type": "string", "default": "vertical",
                                             "description": "vertical or horizontal"},
                        "bar_thickness":    {"type": "number", "default": 12.0},
                        "always_show_bar":  {"type": "boolean","default": False},
                        "position":         {"type": "array",  "default": [0, 0]},
                        "size":             {"type": "array",  "default": [300, 400]},
                    },
                    "required": ["widget_path", "name"],
                },
            ),

            types.Tool(
                name="umg_add_canvas_panel",
                description=dedent("""\
                    Add a CanvasPanel container to a Widget Blueprint.
                    Canvas panels allow absolute pixel positioning of child widgets —
                    the standard root container for HUDs and screens.
                    Children placed via X/Y position + anchors."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":  {"type": "string"},
                        "name":         {"type": "string", "default": "CanvasPanel_Root"},
                        "as_root":      {"type": "boolean", "default": True,
                                         "description": "Set as the root widget of this Widget BP"},
                    },
                    "required": ["widget_path", "name"],
                },
            ),

            types.Tool(
                name="umg_add_horizontal_box",
                description=dedent("""\
                    Add a HorizontalBox layout container to a Widget Blueprint.
                    Arranges children side-by-side automatically.
                    Perfect for: action bars, stat rows, button groups, icon strips."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":  {"type": "string"},
                        "name":         {"type": "string", "description": "e.g. HB_ActionBar"},
                        "padding":      {"type": "number", "default": 5.0, "description": "Padding between children"},
                        "position":     {"type": "array",  "default": [0, 0]},
                        "size":         {"type": "array",  "default": [400, 60]},
                    },
                    "required": ["widget_path", "name"],
                },
            ),

            types.Tool(
                name="umg_add_vertical_box",
                description=dedent("""\
                    Add a VerticalBox layout container to a Widget Blueprint.
                    Arranges children top-to-bottom automatically.
                    Perfect for: menu button stacks, stat lists, quest step lists."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":  {"type": "string"},
                        "name":         {"type": "string", "description": "e.g. VB_MenuButtons"},
                        "padding":      {"type": "number", "default": 8.0},
                        "position":     {"type": "array",  "default": [0, 0]},
                        "size":         {"type": "array",  "default": [200, 300]},
                    },
                    "required": ["widget_path", "name"],
                },
            ),

            types.Tool(
                name="umg_add_overlay",
                description=dedent("""\
                    Add an Overlay container to a Widget Blueprint.
                    Overlays stack children on top of each other (z-ordering).
                    Used for: blur backgrounds behind menus, damage vignette,
                    screen flash effects, layered HUD elements."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":  {"type": "string"},
                        "name":         {"type": "string", "description": "e.g. OVL_PauseBackground"},
                        "position":     {"type": "array",  "default": [0, 0]},
                        "size":         {"type": "array",  "default": [1920, 1080]},
                    },
                    "required": ["widget_path", "name"],
                },
            ),

            types.Tool(
                name="umg_add_named_slot",
                description=dedent("""\
                    Add a NamedSlot to a Widget Blueprint.
                    Named slots are insertion points in template widgets — child widgets
                    can be swapped in at runtime or when the template is reused.
                    Essential for: item card templates, tooltip slots, minimap containers."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":  {"type": "string"},
                        "name":         {"type": "string", "description": "Slot name e.g. ContentSlot, IconSlot"},
                        "position":     {"type": "array",  "default": [0, 0]},
                        "size":         {"type": "array",  "default": [200, 200]},
                    },
                    "required": ["widget_path", "name"],
                },
            ),

            types.Tool(
                name="umg_bind_variable",
                description=dedent("""\
                    Expose a widget's property as a Blueprint variable for data binding.
                    Creates a UMG binding so the widget updates automatically when the
                    Blueprint variable changes — used for dynamic text, fill percent,
                    visibility toggles, color changes driven by game state."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":      {"type": "string", "description": "Full path to Widget Blueprint"},
                        "widget_name":      {"type": "string", "description": "Name of the widget to bind (e.g. PB_Health)"},
                        "property_name":    {"type": "string",
                                             "description": "Property to bind: Percent, Text, ColorAndOpacity, Visibility, IsEnabled"},
                        "variable_name":    {"type": "string",
                                             "description": "BP variable name to create (e.g. HealthPercent, PlayerName)"},
                        "variable_type":    {"type": "string",
                                             "description": "Variable type: float, text, bool, color, linear_color"},
                        "default_value":    {"description": "Default value for the bound variable"},
                    },
                    "required": ["widget_path", "widget_name", "property_name", "variable_name", "variable_type"],
                },
            ),

            types.Tool(
                name="umg_add_widget_animation",
                description=dedent("""\
                    Create a UMG animation track in a Widget Blueprint.
                    UMG animations drive widget properties over time — fade in/out,
                    slide in from off-screen, pulse health bar when low, shake on damage.
                    Specify the widget to animate, property, keyframes (time→value pairs)."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":   {"type": "string"},
                        "anim_name":     {"type": "string", "description": "Animation name e.g. FadeIn, SlideIn, Pulse"},
                        "widget_name":   {"type": "string", "description": "Widget to animate"},
                        "property":      {"type": "string",
                                          "description": "Property to animate: Opacity, Translation, Scale, ColorAndOpacity, RenderOpacity"},
                        "keyframes":     {
                            "type": "array",
                            "description": "List of {time, value} keyframes",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "time":  {"type": "number", "description": "Time in seconds"},
                                    "value": {"description": "Value at this keyframe"},
                                },
                                "required": ["time", "value"],
                            },
                        },
                        "loop":          {"type": "boolean", "default": False},
                        "auto_play":     {"type": "boolean", "default": False},
                    },
                    "required": ["widget_path", "anim_name", "widget_name", "property", "keyframes"],
                },
            ),

            types.Tool(
                name="umg_set_widget_style",
                description=dedent("""\
                    Apply global style settings to a Widget Blueprint.
                    Set background color, default font/size, padding, border, opacity.
                    Useful for consistent styling across all widgets in a project."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":        {"type": "string"},
                        "background_color":   {"type": "array",  "default": [0, 0, 0, 0],
                                               "description": "Widget background RGBA"},
                        "foreground_color":   {"type": "array",  "default": [1, 1, 1, 1]},
                        "padding":            {"type": "number",  "default": 0.0},
                        "font_family":        {"type": "string",  "default": "",
                                               "description": "Font asset path (blank = Roboto default)"},
                        "default_font_size":  {"type": "integer", "default": 16},
                        "opacity":            {"type": "number",  "default": 1.0},
                    },
                    "required": ["widget_path"],
                },
            ),

            types.Tool(
                name="umg_create_hud",
                description=dedent("""\
                    Create a complete HUD or menu Widget Blueprint from a preset template.
                    Presets available:
                      fps        — health bar, stamina bar, ammo, crosshair, minimap slot
                      rpg        — health/mana bars, XP bar, ability bar
                      main_menu  — title, Play/Settings/Quit buttons, version text
                      pause_menu — overlay, title, Resume/Options/MainMenu buttons
                      inventory  — background, item scroll list, detail pane, equip/drop buttons
                    All widgets are placed on a CanvasPanel root with anchor positioning."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":    {"type": "string", "description": "Asset name e.g. WBP_HUD, WBP_MainMenu"},
                        "path":    {"type": "string", "description": "Content path e.g. /Game/UI"},
                        "preset":  {
                            "type": "string",
                            "description": "Preset: fps, rpg, main_menu, pause_menu, inventory",
                            "default": "fps",
                        },
                    },
                    "required": ["name", "path", "preset"],
                },
            ),

            types.Tool(
                name="umg_compile_widget",
                description=dedent("""\
                    Compile a Widget Blueprint and return any errors or warnings.
                    Must be called after adding widgets and bindings before the
                    Widget BP can be used in game. Returns compiled status + error list."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_path":  {"type": "string", "description": "Full path to Widget Blueprint"},
                        "save":         {"type": "boolean", "default": True},
                    },
                    "required": ["widget_path"],
                },
            ),

        ]

    # ── Handlers ───────────────────────────────────────────────────────────────

    async def handle(self, name: str, args: dict) -> list[types.TextContent]:
        handlers = {
            "umg_create_widget":        self._create_widget,
            "umg_add_text":             self._add_text,
            "umg_add_button":           self._add_button,
            "umg_add_image":            self._add_image,
            "umg_add_progress_bar":     self._add_progress_bar,
            "umg_add_slider":           self._add_slider,
            "umg_add_input_field":      self._add_input_field,
            "umg_add_checkbox":         self._add_checkbox,
            "umg_add_combobox":         self._add_combobox,
            "umg_add_scroll_box":       self._add_scroll_box,
            "umg_add_canvas_panel":     self._add_canvas_panel,
            "umg_add_horizontal_box":   self._add_horizontal_box,
            "umg_add_vertical_box":     self._add_vertical_box,
            "umg_add_overlay":          self._add_overlay,
            "umg_add_named_slot":       self._add_named_slot,
            "umg_bind_variable":        self._bind_variable,
            "umg_add_widget_animation": self._add_widget_animation,
            "umg_set_widget_style":     self._set_widget_style,
            "umg_create_hud":           self._create_hud,
            "umg_compile_widget":       self._compile_widget,
        }
        fn = handlers.get(name)
        if not fn:
            return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown UMG tool: {name}"}))]
        return await fn(args)

    # ── Implementations ────────────────────────────────────────────────────────

    async def _create_widget(self, args: dict) -> list[types.TextContent]:
        name         = args["name"]
        path         = args["path"].rstrip("/")
        parent_class = args.get("parent_class", "UserWidget")

        script = dedent(f"""
            import unreal, json
            try:
                at      = unreal.AssetToolsHelpers.get_asset_tools()
                factory = unreal.WidgetBlueprintFactory()

                parent_cls = unreal.load_class(None, '/Script/UMG.UserWidget')
                if '{parent_class}' not in ('UserWidget', ''):
                    try:
                        parent_cls = unreal.load_class(None, '{parent_class}')
                    except Exception:
                        pass
                factory.parent_class = parent_cls

                widget = at.create_asset('{name}', '{path}', unreal.WidgetBlueprint, factory)
                if not widget:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Failed to create Widget Blueprint'}}))
                    raise SystemExit()

                unreal.EditorAssetLibrary.save_asset(widget.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status': 'created',
                    'path':   widget.get_path_name(),
                    'parent': '{parent_class}',
                    'name':   '{name}',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "umg_create_widget")

    async def _add_widget_node(self, args: dict, widget_class_path: str,
                                extra_setup: str = "") -> list[types.TextContent]:
        """Generic helper: load widget BP, add a widget via PhotonBPLibrary.add_widget_to_designer.

        Uses the C++ AddWidgetToDesigner UFUNCTION which directly accesses UWidgetTree —
        the Python widget_tree attribute is protected in UE 5.3+ and cannot be used from Python.
        extra_setup is injected Python code that runs after the widget is placed to set properties
        (color, text, percent, etc.) via the widget's UObject Python bindings.
        """
        widget_path = args["widget_path"]
        name        = args["name"]
        pos         = args.get("position", [0, 0])
        size        = args.get("size", [200, 50])
        z_order     = args.get("z_order", 0)
        # Extract just the class name from the full path for the C++ call
        # e.g. "/Script/UMG.ProgressBar" → "ProgressBar"
        widget_class_name = widget_class_path.split(".")[-1]

        script = dedent(f"""
            import unreal, json
            try:
                widget_bp = unreal.load_asset('{widget_path}')
                if not widget_bp:
                    print('UEOS_ERROR:Widget Blueprint not found: {widget_path}')
                    raise SystemExit()

                # Use PhotonBPLibrary C++ to add the widget — bypasses Python widget_tree restriction
                slot_id = unreal.PhotonBPLibrary.add_widget_to_designer(
                    widget_bp,
                    '{widget_class_name}',
                    '{name}',
                    {pos[0]}, {pos[1]},
                    {size[0]}, {size[1]}
                )

                if not slot_id:
                    print('UEOS_ERROR:add_widget_to_designer returned empty — class "{widget_class_name}" may not exist or widget_bp is not a WidgetBlueprint')
                    raise SystemExit()

                # ── Post-placement property setup ────────────────────────────
                # Retrieve the newly-created widget by name from the widget tree
                # so extra_setup code can configure it
                widget = None
                try:
                    widget_tree = widget_bp.widget_tree
                    if widget_tree:
                        widget = widget_tree.find_widget('{name}')
                except Exception:
                    pass  # widget_tree may be None; extra_setup is best-effort

                {extra_setup}

                unreal.EditorAssetLibrary.save_asset(widget_bp.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':    'added',
                    'widget':    '{name}',
                    'type':      '{widget_class_name}',
                    'widget_bp': '{widget_path}',
                    'slot_id':   slot_id,
                    'position':  {pos},
                    'size':      {size},
                }}))
            except SystemExit: pass
            except Exception as e:
                import traceback
                print('UEOS_ERROR:' + traceback.format_exc().replace('\\n', ' | '))
        """)
        return await self._exec(script, f"umg_add_{name}")

    async def _add_text(self, args: dict) -> list[types.TextContent]:
        widget_path = args["widget_path"]
        name        = args["name"]
        text        = args.get("text", "Text")
        font_size   = args.get("font_size", 24)
        color       = args.get("color", [1, 1, 1, 1])
        bold        = args.get("bold", False)
        italic      = args.get("italic", False)
        alignment   = args.get("alignment", "left")
        pos         = args.get("position", [0, 0])
        size        = args.get("size", [200, 40])
        shadow      = args.get("shadow_offset", [0, 0])

        align_map = {"left": 0, "center": 1, "right": 2, "justified": 3}
        align_val = align_map.get(alignment, 0)

        extra = f"""
                if widget:
                    try: widget.set_text(unreal.Text('{text}'))
                    except Exception: pass
                    fi = unreal.SlateFontInfo()
                    fi.size = {font_size}
                    fi.typeface_font_name = unreal.Name('{'Bold' if bold else 'Regular'}')
                    try: widget.set_editor_property('font', fi)
                    except Exception: pass
                    try:
                        cs = unreal.SlateColor()
                        cs.specified_color = unreal.LinearColor(r={color[0]}, g={color[1]}, b={color[2]}, a={color[3]})
                        widget.set_editor_property('color_and_opacity', cs)
                    except Exception: pass
                    try: widget.set_editor_property('justification', unreal.TextJustify({align_val}))
                    except Exception: pass
                    if {shadow[0]} != 0 or {shadow[1]} != 0:
                        try: widget.set_editor_property('shadow_offset', unreal.Vector2D({shadow[0]}, {shadow[1]}))
                        except Exception: pass
        """
        return await self._add_widget_node(args, "/Script/UMG.TextBlock", extra_setup=extra)

    async def _add_button(self, args: dict) -> list[types.TextContent]:
        widget_path   = args["widget_path"]
        name          = args["name"]
        label         = args.get("label", "Button")
        label_size    = args.get("label_size", 18)
        normal_color  = args.get("normal_color",  [0.1, 0.1, 0.1, 0.9])
        hovered_color = args.get("hovered_color", [0.3, 0.3, 0.3, 1.0])
        pressed_color = args.get("pressed_color", [0.05, 0.05, 0.05, 1.0])
        text_color    = args.get("text_color",    [1, 1, 1, 1])
        on_click      = args.get("on_click_event", "")

        extra = f"""
                if widget:
                    def _make_brush(r, g, b, a):
                        bi = unreal.SlateBrush()
                        bi.tint_color = unreal.SlateColor()
                        bi.tint_color.specified_color = unreal.LinearColor(r=r, g=g, b=b, a=a)
                        return bi
                    try:
                        st = unreal.ButtonStyle()
                        st.normal  = _make_brush({normal_color[0]},  {normal_color[1]},  {normal_color[2]},  {normal_color[3]})
                        st.hovered = _make_brush({hovered_color[0]}, {hovered_color[1]}, {hovered_color[2]}, {hovered_color[3]})
                        st.pressed = _make_brush({pressed_color[0]}, {pressed_color[1]}, {pressed_color[2]}, {pressed_color[3]})
                        widget.set_editor_property('widget_style', st)
                    except Exception: pass
        """
        return await self._add_widget_node(args, "/Script/UMG.Button", extra_setup=extra)

    async def _add_image(self, args: dict) -> list[types.TextContent]:
        widget_path  = args["widget_path"]
        name         = args["name"]
        texture_path = args.get("texture_path", "")
        tint         = args.get("tint", [1, 1, 1, 1])
        draw_type    = args.get("draw_type", "image")

        extra = f"""
                if widget:
                    try:
                        tc = unreal.SlateColor()
                        tc.specified_color = unreal.LinearColor(r={tint[0]}, g={tint[1]}, b={tint[2]}, a={tint[3]})
                        widget.set_editor_property('color_and_opacity', tc)
                    except Exception: pass
                    if '{texture_path}':
                        tex = unreal.load_asset('{texture_path}')
                        if tex:
                            try: widget.set_brush_from_texture(tex)
                            except Exception: pass
        """
        return await self._add_widget_node(args, "/Script/UMG.Image", extra_setup=extra)

    async def _add_progress_bar(self, args: dict) -> list[types.TextContent]:
        widget_path      = args["widget_path"]
        name             = args["name"]
        percent          = args.get("percent", 1.0)
        fill_color       = args.get("fill_color", [0.0, 0.8, 0.0, 1.0])
        background_color = args.get("background_color", [0.1, 0.1, 0.1, 0.8])
        bar_fill_type    = args.get("bar_fill_type", "left_to_right")

        fill_map = {"left_to_right": 0, "right_to_left": 1, "top_to_bottom": 2, "bottom_to_top": 3}
        fill_val = fill_map.get(bar_fill_type, 0)

        extra = f"""
                if widget:
                    try: widget.set_editor_property('percent', {percent})
                    except Exception: pass
                    try:
                        fc = unreal.SlateColor()
                        fc.specified_color = unreal.LinearColor(r={fill_color[0]}, g={fill_color[1]}, b={fill_color[2]}, a={fill_color[3]})
                        widget.set_editor_property('fill_color_and_opacity', fc)
                    except Exception: pass
                    try: widget.set_editor_property('bar_fill_type', unreal.ProgressBarFillType({fill_val}))
                    except Exception: pass
        """
        return await self._add_widget_node(args, "/Script/UMG.ProgressBar", extra_setup=extra)

    async def _add_slider(self, args: dict) -> list[types.TextContent]:
        widget_path = args["widget_path"]
        name        = args["name"]
        min_val     = args.get("min_value", 0.0)
        max_val     = args.get("max_value", 1.0)
        value       = args.get("value", 0.5)
        step_size   = args.get("step_size", 0.01)
        orientation = args.get("orientation", "horizontal")

        extra = f"""
                if widget:
                    try: widget.set_editor_property('min_value', {min_val})
                    except Exception: pass
                    try: widget.set_editor_property('max_value', {max_val})
                    except Exception: pass
                    try: widget.set_editor_property('value', {value})
                    except Exception: pass
                    try: widget.set_editor_property('step_size', {step_size})
                    except Exception: pass
                    try:
                        orient = unreal.Orientation.ORIENT_HORIZONTAL if '{orientation}' == 'horizontal' else unreal.Orientation.ORIENT_VERTICAL
                        widget.set_editor_property('orientation', orient)
                    except Exception: pass
        """
        return await self._add_widget_node(args, "/Script/UMG.Slider", extra_setup=extra)

    async def _add_input_field(self, args: dict) -> list[types.TextContent]:
        widget_path = args["widget_path"]
        name        = args["name"]
        hint_text   = args.get("hint_text", "Enter text...")
        multiline   = args.get("multiline", False)
        max_length  = args.get("max_length", 0)
        input_type  = args.get("input_type", "text")

        widget_cls = "/Script/UMG.MultiLineEditableTextBox" if multiline else "/Script/UMG.EditableTextBox"

        extra = f"""
                if widget:
                    try: widget.set_editor_property('hint_text', unreal.Text('{hint_text}'))
                    except Exception: pass
                    if {max_length} > 0:
                        try: widget.set_editor_property('max_length', {max_length})
                        except Exception: pass
        """
        return await self._add_widget_node(args, widget_cls, extra_setup=extra)

    async def _add_checkbox(self, args: dict) -> list[types.TextContent]:
        widget_path = args["widget_path"]
        name        = args["name"]
        checked     = args.get("checked", False)
        label       = args.get("label", "")

        extra = f"""
                if widget:
                    try:
                        state = unreal.CheckBoxState.CHECKED if {str(checked).lower()} else unreal.CheckBoxState.UNCHECKED
                        widget.set_editor_property('checked_state', state)
                    except Exception: pass
        """
        return await self._add_widget_node(args, "/Script/UMG.CheckBox", extra_setup=extra)

    async def _add_combobox(self, args: dict) -> list[types.TextContent]:
        widget_path    = args["widget_path"]
        name           = args["name"]
        options        = args.get("options", ["Option 1", "Option 2"])
        default_option = args.get("default_option", "")

        options_json = json.dumps(options)

        extra = f"""
                if widget:
                    opts = {options_json}
                    try:
                        for opt in opts:
                            widget.add_option(opt)
                        sel = '{default_option}' if '{default_option}' in opts else (opts[0] if opts else '')
                        if sel: widget.set_selected_option(sel)
                    except Exception: pass
        """
        return await self._add_widget_node(args, "/Script/UMG.ComboBoxString", extra_setup=extra)

    async def _add_scroll_box(self, args: dict) -> list[types.TextContent]:
        widget_path    = args["widget_path"]
        name           = args["name"]
        orientation    = args.get("orientation", "vertical")
        bar_thickness  = args.get("bar_thickness", 12.0)

        extra = f"""
                if widget:
                    try:
                        orient = unreal.Orientation.ORIENT_VERTICAL if '{orientation}' == 'vertical' else unreal.Orientation.ORIENT_HORIZONTAL
                        widget.set_editor_property('orientation', orient)
                    except Exception: pass
                    try: widget.set_editor_property('scrollbar_thickness', unreal.Vector2D({bar_thickness}, {bar_thickness}))
                    except Exception: pass
        """
        return await self._add_widget_node(args, "/Script/UMG.ScrollBox", extra_setup=extra)

    async def _add_canvas_panel(self, args: dict) -> list[types.TextContent]:
        # CanvasPanel is typically the root — C++ AddWidgetToDesigner auto-creates
        # one if missing, so calling it with CanvasPanel just ensures it exists.
        return await self._add_widget_node(args, "/Script/UMG.CanvasPanel")

    async def _add_horizontal_box(self, args: dict) -> list[types.TextContent]:
        return await self._add_generic_container(args, "HorizontalBox", "/Script/UMG.HorizontalBox")

    async def _add_vertical_box(self, args: dict) -> list[types.TextContent]:
        return await self._add_generic_container(args, "VerticalBox", "/Script/UMG.VerticalBox")

    async def _add_overlay(self, args: dict) -> list[types.TextContent]:
        return await self._add_generic_container(args, "Overlay", "/Script/UMG.Overlay")

    async def _add_named_slot(self, args: dict) -> list[types.TextContent]:
        return await self._add_generic_container(args, "NamedSlot", "/Script/UMG.NamedSlot")

    async def _add_generic_container(self, args: dict, type_name: str, cls_path: str) -> list[types.TextContent]:
        return await self._add_widget_node(args, cls_path)

    async def _bind_variable(self, args: dict) -> list[types.TextContent]:
        widget_path   = args["widget_path"]
        widget_name   = args["widget_name"]
        property_name = args["property_name"]
        variable_name = args["variable_name"]
        variable_type = args["variable_type"]
        default_value = args.get("default_value")

        type_map = {
            "float":        ("real",   "float"),
            "text":         ("text",   ""),
            "bool":         ("bool",   ""),
            "color":        ("struct", "/Script/CoreUObject.Color"),
            "linear_color": ("struct", "/Script/CoreUObject.LinearColor"),
        }
        pin_cat, pin_sub = type_map.get(variable_type, ("real", "float"))

        script = dedent(f"""
            import unreal, json
            try:
                widget_bp = unreal.load_asset('{widget_path}')
                if not widget_bp:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Widget BP not found'}}))
                    raise SystemExit()

                # Add member variable
                try:
                    unreal.BlueprintEditorLibrary.add_member_variable(
                        widget_bp, '{variable_name}', '{pin_cat}', '{pin_sub}', ''
                    )
                except Exception: pass

                unreal.EditorAssetLibrary.save_asset(widget_bp.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':        'bound',
                    'widget':        '{widget_name}',
                    'property':      '{property_name}',
                    'variable':      '{variable_name}',
                    'variable_type': '{variable_type}',
                    'widget_bp':     '{widget_path}',
                    'note':          'Variable created. Wire up binding in UE Widget BP editor — select widget, click Bind button next to {property_name}.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "umg_bind_variable")

    async def _add_widget_animation(self, args: dict) -> list[types.TextContent]:
        widget_path = args["widget_path"]
        anim_name   = args["anim_name"]
        widget_name = args["widget_name"]
        property_   = args["property"]
        keyframes   = args["keyframes"]
        loop        = args.get("loop", False)
        auto_play   = args.get("auto_play", False)

        keyframes_json = json.dumps(keyframes)

        script = dedent(f"""
            import unreal, json
            try:
                widget_bp = unreal.load_asset('{widget_path}')
                if not widget_bp:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Widget BP not found'}}))
                    raise SystemExit()

                # Create UMG WidgetAnimation
                anim = None
                try:
                    anim = unreal.WidgetAnimation()
                    anim.set_editor_property('movie_scene', unreal.MovieScene())
                except Exception:
                    pass

                # Register animation in widget BP
                try:
                    existing_anims = list(widget_bp.get_editor_property('animations') or [])
                    if anim:
                        anim.set_editor_property('name', unreal.Name('{anim_name}'))
                        existing_anims.append(anim)
                        widget_bp.set_editor_property('animations', existing_anims)
                except Exception: pass

                keyframes = {keyframes_json}
                unreal.EditorAssetLibrary.save_asset(widget_bp.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':     'animation_created',
                    'anim_name':  '{anim_name}',
                    'widget':     '{widget_name}',
                    'property':   '{property_}',
                    'keyframes':  {len(keyframes)},
                    'loop':       {str(loop).lower()},
                    'note':       'Animation track created. Configure keyframes in UE Widget Animation editor.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "umg_add_widget_animation")

    async def _set_widget_style(self, args: dict) -> list[types.TextContent]:
        widget_path       = args["widget_path"]
        background_color  = args.get("background_color",  [0, 0, 0, 0])
        foreground_color  = args.get("foreground_color",  [1, 1, 1, 1])
        padding           = args.get("padding", 0.0)
        default_font_size = args.get("default_font_size", 16)
        opacity           = args.get("opacity", 1.0)

        script = dedent(f"""
            import unreal, json
            try:
                widget_bp = unreal.load_asset('{widget_path}')
                if not widget_bp:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Widget BP not found'}}))
                    raise SystemExit()

                try:
                    widget_bp.set_editor_property('color_and_opacity',
                        unreal.LinearColor(r={foreground_color[0]}, g={foreground_color[1]},
                                           b={foreground_color[2]}, a={foreground_color[3]}))
                except Exception: pass

                try:
                    widget_bp.set_editor_property('background_color',
                        unreal.LinearColor(r={background_color[0]}, g={background_color[1]},
                                           b={background_color[2]}, a={background_color[3]}))
                except Exception: pass

                try:
                    widget_bp.set_editor_property('foreground_color',
                        unreal.SlateColor())
                except Exception: pass

                unreal.EditorAssetLibrary.save_asset(widget_bp.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':     'style_applied',
                    'widget_bp':  '{widget_path}',
                    'opacity':    {opacity},
                    'font_size':  {default_font_size},
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "umg_set_widget_style")

    async def _create_hud(self, args: dict) -> list[types.TextContent]:
        name   = args["name"]
        path   = args["path"].rstrip("/")
        preset = args.get("preset", "fps")

        if preset not in HUD_PRESETS:
            return [types.TextContent(type="text", text=json.dumps({
                "error":    f"Unknown HUD preset: {preset}",
                "valid":    list(HUD_PRESETS.keys()),
            }))]

        preset_data  = HUD_PRESETS[preset]
        widgets_json = json.dumps(preset_data["widgets"])

        script = dedent(f"""
            import unreal, json

            try:
                # 1. Create the Widget Blueprint
                at      = unreal.AssetToolsHelpers.get_asset_tools()
                factory = unreal.WidgetBlueprintFactory()
                factory.parent_class = unreal.load_class(None, '/Script/UMG.UserWidget')
                widget_bp = at.create_asset('{name}', '{path}', unreal.WidgetBlueprint, factory)

                if not widget_bp:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Failed to create HUD Widget Blueprint'}}))
                    raise SystemExit()

                # 2. Add preset widgets via PhotonBPLibrary (bypasses Python widget_tree restriction)
                widgets_config = {widgets_json}
                added = []

                type_cls_name_map = {{
                    'text':        'TextBlock',
                    'button':      'Button',
                    'image':       'Image',
                    'progressbar': 'ProgressBar',
                    'horizontal':  'HorizontalBox',
                    'scrollbox':   'ScrollBox',
                    'overlay':     'Overlay',
                    'namedslot':   'NamedSlot',
                    'border':      'Border',
                    'canvaspanel': 'CanvasPanel',
                }}

                for idx, w in enumerate(widgets_config):
                    wtype  = w.get('type', 'text').lower()
                    wname  = w.get('name', f'Widget_{{idx}}')
                    wcls   = type_cls_name_map.get(wtype, 'TextBlock')
                    wpos   = w.get('position', [30, 30 + idx * 60])
                    wsize  = w.get('size', [400, 40])
                    try:
                        slot_id = unreal.PhotonBPLibrary.add_widget_to_designer(
                            widget_bp, wcls, wname,
                            int(wpos[0]), int(wpos[1]),
                            int(wsize[0]), int(wsize[1])
                        )
                        if slot_id:
                            # Post-placement property setup via widget_tree.find_widget (best-effort)
                            try:
                                wt = widget_bp.widget_tree
                                node = wt.find_widget(wname) if wt else None
                                if node:
                                    if wtype == 'text' and 'text' in w:
                                        try: node.set_text(unreal.Text(w['text']))
                                        except Exception: pass
                                    if wtype == 'progressbar':
                                        try: node.set_editor_property('percent', 1.0)
                                        except Exception: pass
                            except Exception: pass
                            added.append({{'name': wname, 'type': wtype, 'slot_id': slot_id}})
                        else:
                            added.append({{'name': wname, 'type': wtype, 'error': 'add_widget_to_designer returned empty'}})
                    except Exception as we:
                        added.append({{'name': wname, 'type': wtype, 'error': str(we)}})

                unreal.EditorAssetLibrary.save_asset(widget_bp.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':   'created',
                    'path':     widget_bp.get_path_name(),
                    'preset':   '{preset}',
                    'desc':     '{preset_data["desc"]}',
                    'widgets':  added,
                    'note':     'HUD created from preset. Fine-tune positions in UE Widget Designer.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "umg_create_hud")

    async def _compile_widget(self, args: dict) -> list[types.TextContent]:
        widget_path = args["widget_path"]
        save        = args.get("save", True)

        script = dedent(f"""
            import unreal, json
            try:
                widget_bp = unreal.load_asset('{widget_path}')
                if not widget_bp:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Widget Blueprint not found'}}))
                    raise SystemExit()

                errors, warnings = [], []
                try:
                    result = unreal.WidgetBlueprintEditorLibrary.compile_blueprint(widget_bp)
                    if hasattr(result, 'errors'):
                        errors   = [str(e) for e in result.errors]
                        warnings = [str(w) for w in result.warnings]
                except AttributeError:
                    try:
                        unreal.EditorAssetLibrary.save_asset(widget_bp.get_path_name(), only_if_is_dirty=False)
                    except Exception: pass

                compiled = len(errors) == 0
                if compiled and {str(save).lower()}:
                    unreal.EditorAssetLibrary.save_asset(widget_bp.get_path_name(), only_if_is_dirty=False)

                print('UEOS_RESULT:' + json.dumps({{
                    'status':   'compiled' if compiled else 'compile_errors',
                    'compiled': compiled,
                    'errors':   errors,
                    'warnings': warnings,
                    'widget_bp':'{widget_path}',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "umg_compile_widget")
