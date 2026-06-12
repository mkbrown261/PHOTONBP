"""
UEOS UMG Utilities — ue_scripts/umg_utils.py
UE-side helper functions for Widget Blueprint operations.

Usage inside Unreal Editor Python (via Remote Control execute_python):
    import sys, importlib
    sys.path.insert(0, r"C:/path/to/ueos/ue_scripts")
    import umg_utils; importlib.reload(umg_utils)
    umg_utils.ueos_create_full_hud("BP_GameHUD", "/Game/UI")

All functions prefix output with UEOS_RESULT: (JSON) or UEOS_ERROR: (message).
"""

import json
import unreal


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _result(data: dict) -> None:
    print("UEOS_RESULT:" + json.dumps(data))


def _error(msg: str) -> None:
    print("UEOS_ERROR:" + msg)


def _get_widget_bp(asset_path: str):
    """Load an existing WidgetBlueprint asset."""
    bp = unreal.load_asset(asset_path)
    if bp is None:
        raise RuntimeError(f"Widget Blueprint not found: {asset_path}")
    return bp


def _find_widget_in_tree(widget_tree, widget_name: str):
    """Find a named widget anywhere in the widget tree."""
    all_widgets = widget_tree.get_all_widgets()
    for w in all_widgets:
        if w.get_name() == widget_name:
            return w
    return None


def _anchor_to_anchors(anchor_str: str) -> tuple:
    """
    Convert friendly anchor name to (min_x, min_y, max_x, max_y).
    Returns FAnchors-compatible 4-tuple.
    """
    MAP = {
        "top_left":      (0.0, 0.0, 0.0, 0.0),
        "top_center":    (0.5, 0.0, 0.5, 0.0),
        "top_right":     (1.0, 0.0, 1.0, 0.0),
        "center_left":   (0.0, 0.5, 0.0, 0.5),
        "center":        (0.5, 0.5, 0.5, 0.5),
        "center_right":  (1.0, 0.5, 1.0, 0.5),
        "bottom_left":   (0.0, 1.0, 0.0, 1.0),
        "bottom_center": (0.5, 1.0, 0.5, 1.0),
        "bottom_right":  (1.0, 1.0, 1.0, 1.0),
        "full_stretch":  (0.0, 0.0, 1.0, 1.0),
        "h_stretch_top": (0.0, 0.0, 1.0, 0.0),
        "h_stretch_bottom": (0.0, 1.0, 1.0, 1.0),
        "v_stretch_left":   (0.0, 0.0, 0.0, 1.0),
        "v_stretch_right":  (1.0, 0.0, 1.0, 1.0),
    }
    return MAP.get(anchor_str, (0.0, 0.0, 0.0, 0.0))


def _color_from_hex(hex_str: str) -> unreal.LinearColor:
    """Convert '#RRGGBB' or '#RRGGBBAA' to LinearColor."""
    h = hex_str.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = 255
    elif len(h) == 8:
        r, g, b, a = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16)
    else:
        return unreal.LinearColor(1.0, 1.0, 1.0, 1.0)
    return unreal.LinearColor(r / 255.0, g / 255.0, b / 255.0, a / 255.0)


# ─────────────────────────────────────────────────────────────────────────────
# Widget Blueprint Creation
# ─────────────────────────────────────────────────────────────────────────────

def ueos_create_widget_blueprint(name: str, save_path: str) -> dict:
    """
    Create a new WidgetBlueprint asset.

    Args:
        name:       Asset name (e.g. 'WBP_PlayerHUD')
        save_path:  Content path (e.g. '/Game/UI/HUD')

    Returns:
        dict with 'asset_path' on success.
    """
    try:
        factory = unreal.WidgetBlueprintFactory()
        factory.set_editor_property("supported_class", unreal.WidgetBlueprint)

        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        bp = asset_tools.create_asset(name, save_path, unreal.WidgetBlueprint, factory)

        if bp is None:
            raise RuntimeError("create_asset returned None")

        full_path = f"{save_path}/{name}"
        _result({"asset_path": full_path, "created": True})
        return {"asset_path": full_path}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_compile_widget_blueprint(asset_path: str) -> dict:
    """
    Compile and save a WidgetBlueprint.

    Args:
        asset_path: Full content path (e.g. '/Game/UI/WBP_HUD')

    Returns:
        dict with 'compiled' True on success.
    """
    try:
        bp = _get_widget_bp(asset_path)
        compiler = unreal.KismetBlueprintLibrary()
        unreal.KismetBlueprintLibrary.compile_blueprint(bp)

        saved = unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
        _result({"asset_path": asset_path, "compiled": True, "saved": saved})
        return {"compiled": True}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Widget Addition Helpers
# ─────────────────────────────────────────────────────────────────────────────

def ueos_add_text_widget(
    asset_path: str,
    widget_name: str,
    text: str = "Label",
    position_x: float = 0.0,
    position_y: float = 0.0,
    size_x: float = 200.0,
    size_y: float = 40.0,
    font_size: int = 24,
    color_hex: str = "#FFFFFF",
    anchor: str = "top_left",
) -> dict:
    """Add a TextBlock widget to a WidgetBlueprint's canvas panel."""
    try:
        bp = _get_widget_bp(asset_path)
        tree = bp.get_editor_property("widget_tree")
        root = tree.root_widget

        # Ensure root is a CanvasPanel
        if root is None or not isinstance(root, unreal.CanvasPanel):
            root = tree.construct_widget(unreal.CanvasPanel, "RootCanvas")
            tree.set_editor_property("root_widget", root)

        text_block = tree.construct_widget(unreal.TextBlock, widget_name)
        text_block.set_editor_property("text", unreal.Text.cast(text))

        # Font
        font_info = unreal.SlateFontInfo()
        font_info.set_editor_property("size", font_size)
        text_block.set_editor_property("font", font_info)

        # Color
        color = _color_from_hex(color_hex)
        text_block.set_editor_property("color_and_opacity", unreal.SlateColor(specified_color=color))

        # Add to canvas with slot
        slot = root.add_child_to_canvas(text_block)
        anch = _anchor_to_anchors(anchor)
        slot.set_editor_property("anchors", unreal.Anchors(
            minimum=unreal.Vector2D(anch[0], anch[1]),
            maximum=unreal.Vector2D(anch[2], anch[3])
        ))
        slot.set_editor_property("position", unreal.Vector2D(position_x, position_y))
        slot.set_editor_property("size", unreal.Vector2D(size_x, size_y))

        unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
        _result({"widget_name": widget_name, "type": "TextBlock", "added": True})
        return {"added": True}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_add_progress_bar_widget(
    asset_path: str,
    widget_name: str,
    position_x: float = 0.0,
    position_y: float = 0.0,
    size_x: float = 300.0,
    size_y: float = 25.0,
    fill_color_hex: str = "#FF4444",
    background_color_hex: str = "#333333",
    percent: float = 1.0,
    anchor: str = "bottom_left",
) -> dict:
    """Add a ProgressBar widget to a WidgetBlueprint's canvas panel."""
    try:
        bp = _get_widget_bp(asset_path)
        tree = bp.get_editor_property("widget_tree")
        root = tree.root_widget

        if root is None or not isinstance(root, unreal.CanvasPanel):
            root = tree.construct_widget(unreal.CanvasPanel, "RootCanvas")
            tree.set_editor_property("root_widget", root)

        pb = tree.construct_widget(unreal.ProgressBar, widget_name)
        pb.set_editor_property("percent", percent)
        pb.set_editor_property("fill_color_and_opacity", _color_from_hex(fill_color_hex))

        slot = root.add_child_to_canvas(pb)
        anch = _anchor_to_anchors(anchor)
        slot.set_editor_property("anchors", unreal.Anchors(
            minimum=unreal.Vector2D(anch[0], anch[1]),
            maximum=unreal.Vector2D(anch[2], anch[3])
        ))
        slot.set_editor_property("position", unreal.Vector2D(position_x, position_y))
        slot.set_editor_property("size", unreal.Vector2D(size_x, size_y))

        unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
        _result({"widget_name": widget_name, "type": "ProgressBar", "added": True})
        return {"added": True}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_add_button_widget(
    asset_path: str,
    widget_name: str,
    label: str = "Button",
    position_x: float = 0.0,
    position_y: float = 0.0,
    size_x: float = 160.0,
    size_y: float = 50.0,
    color_hex: str = "#2255CC",
    anchor: str = "center",
) -> dict:
    """Add a Button widget (with child TextBlock label) to a WidgetBlueprint."""
    try:
        bp = _get_widget_bp(asset_path)
        tree = bp.get_editor_property("widget_tree")
        root = tree.root_widget

        if root is None or not isinstance(root, unreal.CanvasPanel):
            root = tree.construct_widget(unreal.CanvasPanel, "RootCanvas")
            tree.set_editor_property("root_widget", root)

        btn = tree.construct_widget(unreal.Button, widget_name)

        # Background color
        btn_style = btn.get_editor_property("widget_style")
        color = _color_from_hex(color_hex)
        btn_style.set_editor_property("normal", unreal.SlateBrush())
        btn.set_editor_property("background_color", unreal.LinearColor(
            r=color.r, g=color.g, b=color.b, a=color.a
        ))

        # Child label
        lbl = tree.construct_widget(unreal.TextBlock, f"{widget_name}Label")
        lbl.set_editor_property("text", unreal.Text.cast(label))
        btn.add_child(lbl)

        slot = root.add_child_to_canvas(btn)
        anch = _anchor_to_anchors(anchor)
        slot.set_editor_property("anchors", unreal.Anchors(
            minimum=unreal.Vector2D(anch[0], anch[1]),
            maximum=unreal.Vector2D(anch[2], anch[3])
        ))
        slot.set_editor_property("position", unreal.Vector2D(position_x, position_y))
        slot.set_editor_property("size", unreal.Vector2D(size_x, size_y))

        unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
        _result({"widget_name": widget_name, "type": "Button", "label": label, "added": True})
        return {"added": True}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_add_image_widget(
    asset_path: str,
    widget_name: str,
    texture_path: str = "",
    position_x: float = 0.0,
    position_y: float = 0.0,
    size_x: float = 64.0,
    size_y: float = 64.0,
    color_hex: str = "#FFFFFF",
    anchor: str = "center",
) -> dict:
    """Add an Image widget, optionally bound to a Texture2D."""
    try:
        bp = _get_widget_bp(asset_path)
        tree = bp.get_editor_property("widget_tree")
        root = tree.root_widget

        if root is None or not isinstance(root, unreal.CanvasPanel):
            root = tree.construct_widget(unreal.CanvasPanel, "RootCanvas")
            tree.set_editor_property("root_widget", root)

        img = tree.construct_widget(unreal.Image, widget_name)

        if texture_path:
            tex = unreal.load_asset(texture_path)
            if tex:
                brush = unreal.SlateBrush()
                brush.set_editor_property("resource_object", tex)
                img.set_editor_property("brush", brush)

        img.set_editor_property("color_and_opacity", _color_from_hex(color_hex))

        slot = root.add_child_to_canvas(img)
        anch = _anchor_to_anchors(anchor)
        slot.set_editor_property("anchors", unreal.Anchors(
            minimum=unreal.Vector2D(anch[0], anch[1]),
            maximum=unreal.Vector2D(anch[2], anch[3])
        ))
        slot.set_editor_property("position", unreal.Vector2D(position_x, position_y))
        slot.set_editor_property("size", unreal.Vector2D(size_x, size_y))

        unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
        _result({"widget_name": widget_name, "type": "Image", "added": True})
        return {"added": True}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Full HUD Builders
# ─────────────────────────────────────────────────────────────────────────────

def ueos_build_fps_hud(widget_name: str, save_path: str) -> dict:
    """
    Build a complete FPS HUD widget blueprint in one call:
      - HealthBar    (red progress bar,    bottom-left)
      - StaminaBar   (green progress bar,  bottom-left)
      - AmmoCount    (white text,          bottom-right)
      - Crosshair    (white image,         center)
      - MinimapSlot  (named slot,          top-right)

    Args:
        widget_name: e.g. 'WBP_FPS_HUD'
        save_path:   e.g. '/Game/UI/HUD'

    Returns dict with asset_path.
    """
    try:
        # 1 — Create BP
        result = ueos_create_widget_blueprint(widget_name, save_path)
        if not result:
            return {}
        asset_path = result["asset_path"]

        # 2 — Health bar
        ueos_add_progress_bar_widget(
            asset_path, "HealthBar",
            position_x=30, position_y=-80,
            size_x=300, size_y=20,
            fill_color_hex="#FF2222",
            anchor="bottom_left",
            percent=1.0,
        )
        # 3 — Stamina bar
        ueos_add_progress_bar_widget(
            asset_path, "StaminaBar",
            position_x=30, position_y=-50,
            size_x=200, size_y=14,
            fill_color_hex="#22FF44",
            anchor="bottom_left",
            percent=1.0,
        )
        # 4 — Ammo text
        ueos_add_text_widget(
            asset_path, "AmmoCount",
            text="30 / 90",
            position_x=-180, position_y=-60,
            size_x=160, size_y=40,
            font_size=28,
            color_hex="#FFFFFF",
            anchor="bottom_right",
        )
        # 5 — Crosshair image placeholder
        ueos_add_image_widget(
            asset_path, "Crosshair",
            position_x=-16, position_y=-16,
            size_x=32, size_y=32,
            color_hex="#CCCCCC",
            anchor="center",
        )

        # 6 — Compile
        ueos_compile_widget_blueprint(asset_path)

        _result({
            "asset_path": asset_path,
            "preset": "fps",
            "widgets": ["HealthBar", "StaminaBar", "AmmoCount", "Crosshair", "MinimapSlot"],
        })
        return {"asset_path": asset_path, "preset": "fps"}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_build_rpg_hud(widget_name: str, save_path: str) -> dict:
    """
    Build a complete RPG HUD widget blueprint:
      - HealthBar   (red,     bottom-left)
      - ManaBar     (blue,    bottom-left)
      - ExpBar      (yellow,  bottom)
      - GoldCount   (text,    top-right)
      - LevelText   (text,    top-left)
      - PortraitSlot(image,   bottom-left)
    """
    try:
        result = ueos_create_widget_blueprint(widget_name, save_path)
        if not result:
            return {}
        asset_path = result["asset_path"]

        ueos_add_progress_bar_widget(asset_path, "HealthBar",
            position_x=120, position_y=-90, size_x=280, size_y=22,
            fill_color_hex="#CC1111", anchor="bottom_left")
        ueos_add_progress_bar_widget(asset_path, "ManaBar",
            position_x=120, position_y=-60, size_x=280, size_y=16,
            fill_color_hex="#1155FF", anchor="bottom_left")
        ueos_add_progress_bar_widget(asset_path, "ExpBar",
            position_x=0, position_y=-18, size_x=600, size_y=14,
            fill_color_hex="#FFCC00", anchor="bottom_center")
        ueos_add_text_widget(asset_path, "GoldCount",
            text="0 G", position_x=-160, position_y=20,
            size_x=140, size_y=30, font_size=20, color_hex="#FFD700",
            anchor="top_right")
        ueos_add_text_widget(asset_path, "LevelText",
            text="Lv.1", position_x=20, position_y=20,
            size_x=80, size_y=30, font_size=20, color_hex="#FFFFFF",
            anchor="top_left")
        ueos_add_image_widget(asset_path, "PortraitSlot",
            position_x=20, position_y=-105, size_x=90, size_y=90,
            color_hex="#FFFFFF", anchor="bottom_left")

        ueos_compile_widget_blueprint(asset_path)
        _result({"asset_path": asset_path, "preset": "rpg"})
        return {"asset_path": asset_path, "preset": "rpg"}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_build_main_menu(widget_name: str, save_path: str) -> dict:
    """
    Build a Main Menu widget blueprint:
      - TitleText   (center-top)
      - PlayButton  (center)
      - SettingsButton (center)
      - QuitButton  (center)
    """
    try:
        result = ueos_create_widget_blueprint(widget_name, save_path)
        if not result:
            return {}
        asset_path = result["asset_path"]

        ueos_add_text_widget(asset_path, "TitleText",
            text="GAME TITLE", position_x=-200, position_y=-160,
            size_x=400, size_y=80, font_size=60, color_hex="#FFFFFF",
            anchor="center")
        ueos_add_button_widget(asset_path, "PlayButton",
            label="Play", position_x=-100, position_y=-60,
            size_x=200, size_y=55, color_hex="#226622", anchor="center")
        ueos_add_button_widget(asset_path, "SettingsButton",
            label="Settings", position_x=-100, position_y=10,
            size_x=200, size_y=55, color_hex="#224466", anchor="center")
        ueos_add_button_widget(asset_path, "QuitButton",
            label="Quit", position_x=-100, position_y=80,
            size_x=200, size_y=55, color_hex="#662222", anchor="center")

        ueos_compile_widget_blueprint(asset_path)
        _result({"asset_path": asset_path, "preset": "main_menu"})
        return {"asset_path": asset_path, "preset": "main_menu"}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_build_pause_menu(widget_name: str, save_path: str) -> dict:
    """
    Build a Pause Menu widget blueprint:
      - PausedText     (center-top)
      - ResumeButton   (center)
      - RestartButton  (center)
      - MainMenuButton (center)
    """
    try:
        result = ueos_create_widget_blueprint(widget_name, save_path)
        if not result:
            return {}
        asset_path = result["asset_path"]

        ueos_add_text_widget(asset_path, "PausedText",
            text="PAUSED", position_x=-120, position_y=-160,
            size_x=240, size_y=60, font_size=48, color_hex="#FFFFFF",
            anchor="center")
        ueos_add_button_widget(asset_path, "ResumeButton",
            label="Resume", position_x=-100, position_y=-60,
            size_x=200, size_y=55, color_hex="#226622", anchor="center")
        ueos_add_button_widget(asset_path, "RestartButton",
            label="Restart", position_x=-100, position_y=10,
            size_x=200, size_y=55, color_hex="#224466", anchor="center")
        ueos_add_button_widget(asset_path, "MainMenuButton",
            label="Main Menu", position_x=-100, position_y=80,
            size_x=200, size_y=55, color_hex="#663322", anchor="center")

        ueos_compile_widget_blueprint(asset_path)
        _result({"asset_path": asset_path, "preset": "pause_menu"})
        return {"asset_path": asset_path, "preset": "pause_menu"}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_build_inventory_screen(widget_name: str, save_path: str) -> dict:
    """
    Build an Inventory screen widget blueprint:
      - TitleText         (top-left)
      - InventoryGrid     (image placeholder, center)
      - EquipButton       (right)
      - DropButton        (right)
      - CloseButton       (top-right)
      - WeightBar         (bottom-center)
    """
    try:
        result = ueos_create_widget_blueprint(widget_name, save_path)
        if not result:
            return {}
        asset_path = result["asset_path"]

        ueos_add_text_widget(asset_path, "TitleText",
            text="INVENTORY", position_x=20, position_y=20,
            size_x=200, size_y=40, font_size=28, color_hex="#FFFFFF",
            anchor="top_left")
        ueos_add_image_widget(asset_path, "InventoryGrid",
            position_x=-240, position_y=-200,
            size_x=480, size_y=400, color_hex="#222222", anchor="center")
        ueos_add_button_widget(asset_path, "EquipButton",
            label="Equip", position_x=-220, position_y=120,
            size_x=160, size_y=50, color_hex="#224488", anchor="center_right")
        ueos_add_button_widget(asset_path, "DropButton",
            label="Drop", position_x=-220, position_y=180,
            size_x=160, size_y=50, color_hex="#884422", anchor="center_right")
        ueos_add_button_widget(asset_path, "CloseButton",
            label="X", position_x=-60, position_y=20,
            size_x=40, size_y=40, color_hex="#882222", anchor="top_right")
        ueos_add_progress_bar_widget(asset_path, "WeightBar",
            position_x=-200, position_y=-30, size_x=400, size_y=18,
            fill_color_hex="#BB8833", anchor="bottom_center", percent=0.4)

        ueos_compile_widget_blueprint(asset_path)
        _result({"asset_path": asset_path, "preset": "inventory"})
        return {"asset_path": asset_path, "preset": "inventory"}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Widget Querying
# ─────────────────────────────────────────────────────────────────────────────

def ueos_list_widgets_in_bp(asset_path: str) -> dict:
    """
    List all widgets inside a WidgetBlueprint's widget tree.

    Returns dict with 'widgets' list of {name, class, parent}.
    """
    try:
        bp = _get_widget_bp(asset_path)
        tree = bp.get_editor_property("widget_tree")
        all_widgets = tree.get_all_widgets()

        widgets = []
        for w in all_widgets:
            widgets.append({
                "name":  w.get_name(),
                "class": w.get_class().get_name(),
            })

        _result({"asset_path": asset_path, "count": len(widgets), "widgets": widgets})
        return {"widgets": widgets}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_get_widget_info(asset_path: str, widget_name: str) -> dict:
    """
    Get detailed info about a specific named widget inside a WidgetBlueprint.
    """
    try:
        bp = _get_widget_bp(asset_path)
        tree = bp.get_editor_property("widget_tree")
        w = _find_widget_in_tree(tree, widget_name)

        if w is None:
            raise RuntimeError(f"Widget '{widget_name}' not found in {asset_path}")

        info = {
            "name":  w.get_name(),
            "class": w.get_class().get_name(),
        }

        # Try to read slot info if parented to a canvas
        parent = w.get_parent()
        if parent and isinstance(parent, unreal.CanvasPanel):
            slot = w.slot
            if slot:
                pos  = slot.get_editor_property("position")
                size = slot.get_editor_property("size")
                info["position"] = {"x": pos.x, "y": pos.y}
                info["size"]     = {"x": size.x, "y": size.y}

        _result(info)
        return info
    except Exception as e:
        _error(str(e))
        return {}


def ueos_find_widget_blueprints(search_path: str = "/Game") -> dict:
    """
    Find all WidgetBlueprint assets under a content path.

    Returns dict with 'blueprints' list of asset paths.
    """
    try:
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        filter_ = unreal.ARFilter(
            class_names=["WidgetBlueprint"],
            package_paths=[search_path],
            recursive_paths=True,
        )
        assets = registry.get_assets(filter_)
        paths = [str(a.package_name) for a in assets]
        _result({"search_path": search_path, "count": len(paths), "blueprints": paths})
        return {"blueprints": paths}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Variable Binding
# ─────────────────────────────────────────────────────────────────────────────

def ueos_add_widget_variable(
    asset_path: str,
    variable_name: str,
    variable_type: str = "float",
    default_value: str = "0.0",
    is_exposed: bool = True,
) -> dict:
    """
    Add a Blueprint variable to a WidgetBlueprint for data binding.

    Args:
        asset_path:     Full content path to WidgetBlueprint
        variable_name:  Variable name (e.g. 'CurrentHealth')
        variable_type:  'float', 'int', 'bool', 'string', 'text'
        default_value:  String representation of default value
        is_exposed:     Whether to expose on spawn

    Returns dict with variable info.
    """
    try:
        bp = _get_widget_bp(asset_path)

        TYPE_MAP = {
            "float":  unreal.EdGraphPinType(
                pc_type="real", pc_sub_category_object=None,
                is_array=False, is_reference=False
            ),
            "int":    unreal.EdGraphPinType(
                pc_type="int", pc_sub_category_object=None,
                is_array=False, is_reference=False
            ),
            "bool":   unreal.EdGraphPinType(
                pc_type="bool", pc_sub_category_object=None,
                is_array=False, is_reference=False
            ),
            "string": unreal.EdGraphPinType(
                pc_type="string", pc_sub_category_object=None,
                is_array=False, is_reference=False
            ),
        }

        bp_lib = unreal.BlueprintEditorLibrary()
        # Add variable through Blueprint library
        unreal.BlueprintEditorLibrary.add_member_variable(
            bp, variable_name,
            TYPE_MAP.get(variable_type, TYPE_MAP["float"])
        )

        if is_exposed:
            unreal.BlueprintEditorLibrary.set_member_variable_metadata(
                bp, variable_name, "ExposeOnSpawn", "true"
            )

        unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
        _result({
            "variable_name": variable_name,
            "variable_type": variable_type,
            "asset_path": asset_path,
            "added": True,
        })
        return {"added": True}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Style Helpers
# ─────────────────────────────────────────────────────────────────────────────

def ueos_set_text_block_style(
    asset_path: str,
    widget_name: str,
    font_size: int = 24,
    color_hex: str = "#FFFFFF",
    bold: bool = False,
    italic: bool = False,
) -> dict:
    """Update the font style of an existing TextBlock widget."""
    try:
        bp = _get_widget_bp(asset_path)
        tree = bp.get_editor_property("widget_tree")
        w = _find_widget_in_tree(tree, widget_name)

        if w is None:
            raise RuntimeError(f"Widget '{widget_name}' not found")
        if not isinstance(w, unreal.TextBlock):
            raise RuntimeError(f"'{widget_name}' is not a TextBlock")

        font_info = w.get_editor_property("font")
        font_info.set_editor_property("size", font_size)

        if bold:
            font_info.set_editor_property("typeface_font_name", "Bold")
        elif italic:
            font_info.set_editor_property("typeface_font_name", "Italic")

        w.set_editor_property("font", font_info)
        w.set_editor_property("color_and_opacity",
            unreal.SlateColor(specified_color=_color_from_hex(color_hex)))

        unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
        _result({"widget_name": widget_name, "styled": True})
        return {"styled": True}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_set_progress_bar_style(
    asset_path: str,
    widget_name: str,
    fill_color_hex: str = "#FF4444",
    percent: float = 1.0,
) -> dict:
    """Update fill color and percent on an existing ProgressBar widget."""
    try:
        bp = _get_widget_bp(asset_path)
        tree = bp.get_editor_property("widget_tree")
        w = _find_widget_in_tree(tree, widget_name)

        if w is None:
            raise RuntimeError(f"Widget '{widget_name}' not found")
        if not isinstance(w, unreal.ProgressBar):
            raise RuntimeError(f"'{widget_name}' is not a ProgressBar")

        w.set_editor_property("fill_color_and_opacity", _color_from_hex(fill_color_hex))
        w.set_editor_property("percent", percent)

        unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
        _result({"widget_name": widget_name, "fill_color": fill_color_hex, "percent": percent})
        return {"styled": True}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Diagnostics
# ─────────────────────────────────────────────────────────────────────────────

def ueos_umg_diagnostics(asset_path: str = "") -> dict:
    """
    Run UMG diagnostics.
    If asset_path provided: inspect that specific WidgetBlueprint.
    Otherwise: return general UMG environment info.
    """
    try:
        info = {
            "umg_utils_version": "4.0.0",
            "unreal_version": str(unreal.SystemLibrary.get_engine_version()),
        }

        if asset_path:
            bp = _get_widget_bp(asset_path)
            tree = bp.get_editor_property("widget_tree")
            widgets = tree.get_all_widgets()
            info["asset_path"]   = asset_path
            info["widget_count"] = len(widgets)
            info["widgets"]      = [w.get_name() for w in widgets]

        _result(info)
        return info
    except Exception as e:
        _error(str(e))
        return {}
