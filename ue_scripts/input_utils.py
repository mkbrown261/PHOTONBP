"""
input_utils.py — UEOS UE-side Enhanced Input utility library (Phase 7)
Run directly from the UE Python console or import as a module.

Quick install:
    import sys, importlib
    sys.path.insert(0, r"C:/UEOS/ue_scripts")
    import input_utils as inp; importlib.reload(inp)

    # Full character input setup (WASD + mouse + gamepad):
    inp.ueos_input_quick_setup("/Game/Input")

    # Vehicle input setup:
    inp.ueos_create_vehicle_inputs("/Game/Input")

    # UI input setup:
    inp.ueos_create_ui_inputs("/Game/Input")
"""

from __future__ import annotations
import json


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ok(data: dict) -> dict:
    data.setdefault("status", "ok")
    return data

def _err(msg: str) -> dict:
    return {"status": "error", "message": str(msg)}

def _log(data: dict) -> None:
    print(json.dumps(data, indent=2))


def _make_action(tools, name: str, save_path: str, val_type, consume: bool = True):
    """Helper: create and save an InputAction asset."""
    import unreal
    factory = unreal.InputActionFactory()
    a = tools.create_asset(name, save_path, unreal.InputAction, factory)
    if a:
        a.set_editor_property("value_type", val_type)
        a.set_editor_property("consume_input", consume)
        unreal.EditorAssetLibrary.save_asset(a.get_path_name())
    return a


def _make_imc(tools, name: str, save_path: str):
    """Helper: create and return an InputMappingContext asset."""
    import unreal
    factory = unreal.InputMappingContextFactory()
    imc = tools.create_asset(name, save_path, unreal.InputMappingContext, factory)
    return imc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ueos_input_quick_setup(
    save_path: str = "/Game/Input",
    mouse_sensitivity: float = 0.5,
    include_gamepad: bool = True,
    include_keyboard: bool = True,
    include_mouse: bool = True,
) -> dict:
    """
    One-call character input setup:
      - IA_Move (Axis2D), IA_Look (Axis2D), IA_Jump (Bool), IA_Sprint (Bool), IA_Crouch (Bool)
      - IMC_Default with WASD + mouse look + gamepad mappings

    Returns: dict with paths of all created assets.
    """
    import unreal
    try:
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        vt    = unreal.InputActionValueType

        ia_move   = _make_action(tools, "IA_Move",   save_path, vt.AXIS2D)
        ia_look   = _make_action(tools, "IA_Look",   save_path, vt.AXIS2D)
        ia_jump   = _make_action(tools, "IA_Jump",   save_path, vt.BOOL)
        ia_sprint = _make_action(tools, "IA_Sprint", save_path, vt.BOOL)
        ia_crouch = _make_action(tools, "IA_Crouch", save_path, vt.BOOL)

        imc = _make_imc(tools, "IMC_Default", save_path)
        if imc:
            sc = unreal.InputModifierScalar()
            sc.set_editor_property("scalar", unreal.Vector(mouse_sensitivity, mouse_sensitivity, mouse_sensitivity))
            neg = unreal.InputModifierNegate()
            swz = unreal.InputModifierSwizzleAxis()

            if include_keyboard:
                imc.map_key(ia_move,   unreal.Key("W"))
                s_map = imc.map_key(ia_move, unreal.Key("S"))
                if s_map: s_map.set_editor_property("modifiers", [neg])
                imc.map_key(ia_move,   unreal.Key("D"))
                a_map = imc.map_key(ia_move, unreal.Key("A"))
                if a_map: a_map.set_editor_property("modifiers", [swz, unreal.InputModifierNegate()])
                imc.map_key(ia_jump,   unreal.Key("SpaceBar"))
                imc.map_key(ia_sprint, unreal.Key("LeftShift"))
                imc.map_key(ia_crouch, unreal.Key("LeftControl"))

            if include_mouse:
                mx = imc.map_key(ia_look, unreal.Key("MouseX"))
                my = imc.map_key(ia_look, unreal.Key("MouseY"))
                if mx: mx.set_editor_property("modifiers", [sc])
                if my: my.set_editor_property("modifiers", [sc])

            if include_gamepad:
                imc.map_key(ia_move,   unreal.Key("Gamepad_LeftX"))
                imc.map_key(ia_move,   unreal.Key("Gamepad_LeftY"))
                imc.map_key(ia_look,   unreal.Key("Gamepad_RightX"))
                imc.map_key(ia_look,   unreal.Key("Gamepad_RightY"))
                imc.map_key(ia_jump,   unreal.Key("Gamepad_FaceButton_Bottom"))
                imc.map_key(ia_sprint, unreal.Key("Gamepad_LeftThumbstick"))
                imc.map_key(ia_crouch, unreal.Key("Gamepad_FaceButton_Right"))

            unreal.EditorAssetLibrary.save_asset(imc.get_path_name())

        assets = [
            f"{save_path}/IA_Move", f"{save_path}/IA_Look",
            f"{save_path}/IA_Jump", f"{save_path}/IA_Sprint",
            f"{save_path}/IA_Crouch", f"{save_path}/IMC_Default",
        ]
        result = _ok({"assets_created": assets, "gamepad": include_gamepad,
                       "keyboard": include_keyboard, "mouse": include_mouse})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_create_vehicle_inputs(save_path: str = "/Game/Input") -> dict:
    """Create IA_Throttle, IA_Steer, IA_Brake, IA_HandBrake + IMC_Vehicle."""
    import unreal
    try:
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        vt    = unreal.InputActionValueType

        ia_throttle  = _make_action(tools, "IA_Throttle",  save_path, vt.AXIS1D)
        ia_steer     = _make_action(tools, "IA_Steer",     save_path, vt.AXIS1D)
        ia_brake     = _make_action(tools, "IA_Brake",     save_path, vt.AXIS1D)
        ia_handbrake = _make_action(tools, "IA_HandBrake", save_path, vt.BOOL)

        imc = _make_imc(tools, "IMC_Vehicle", save_path)
        if imc:
            neg = unreal.InputModifierNegate()
            imc.map_key(ia_throttle,  unreal.Key("Gamepad_RightTriggerAxis"))
            imc.map_key(ia_brake,     unreal.Key("Gamepad_LeftTriggerAxis"))
            imc.map_key(ia_steer,     unreal.Key("Gamepad_LeftX"))
            imc.map_key(ia_handbrake, unreal.Key("Gamepad_FaceButton_Bottom"))
            imc.map_key(ia_throttle,  unreal.Key("W"))
            s_rev = imc.map_key(ia_throttle, unreal.Key("S"))
            if s_rev: s_rev.set_editor_property("modifiers", [neg])
            imc.map_key(ia_steer,     unreal.Key("D"))
            a_map = imc.map_key(ia_steer, unreal.Key("A"))
            if a_map: a_map.set_editor_property("modifiers", [unreal.InputModifierNegate()])
            imc.map_key(ia_brake,     unreal.Key("LeftShift"))
            imc.map_key(ia_handbrake, unreal.Key("SpaceBar"))
            unreal.EditorAssetLibrary.save_asset(imc.get_path_name())

        result = _ok({
            "actions": ["IA_Throttle", "IA_Steer", "IA_Brake", "IA_HandBrake"],
            "imc": "IMC_Vehicle",
            "save_path": save_path,
        })
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_create_ui_inputs(save_path: str = "/Game/Input") -> dict:
    """Create IA_Navigate, IA_Confirm, IA_Cancel, IA_TabLeft, IA_TabRight + IMC_UI."""
    import unreal
    try:
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        vt    = unreal.InputActionValueType

        ia_nav     = _make_action(tools, "IA_Navigate", save_path, vt.AXIS2D, consume=True)
        ia_confirm = _make_action(tools, "IA_Confirm",  save_path, vt.BOOL)
        ia_cancel  = _make_action(tools, "IA_Cancel",   save_path, vt.BOOL)
        ia_tab_l   = _make_action(tools, "IA_TabLeft",  save_path, vt.BOOL)
        ia_tab_r   = _make_action(tools, "IA_TabRight", save_path, vt.BOOL)

        for ia in [ia_nav, ia_confirm, ia_cancel, ia_tab_l, ia_tab_r]:
            if ia:
                ia.set_editor_property("trigger_when_paused", True)
                unreal.EditorAssetLibrary.save_asset(ia.get_path_name())

        imc = _make_imc(tools, "IMC_UI", save_path)
        if imc:
            imc.map_key(ia_nav,     unreal.Key("Gamepad_DPad_Up"))
            imc.map_key(ia_nav,     unreal.Key("Gamepad_DPad_Down"))
            imc.map_key(ia_nav,     unreal.Key("Up"))
            imc.map_key(ia_nav,     unreal.Key("Down"))
            imc.map_key(ia_confirm, unreal.Key("Gamepad_FaceButton_Bottom"))
            imc.map_key(ia_confirm, unreal.Key("Enter"))
            imc.map_key(ia_cancel,  unreal.Key("Gamepad_FaceButton_Right"))
            imc.map_key(ia_cancel,  unreal.Key("Escape"))
            imc.map_key(ia_tab_l,   unreal.Key("Gamepad_LeftShoulder"))
            imc.map_key(ia_tab_r,   unreal.Key("Gamepad_RightShoulder"))
            unreal.EditorAssetLibrary.save_asset(imc.get_path_name())

        result = _ok({
            "actions": ["IA_Navigate", "IA_Confirm", "IA_Cancel", "IA_TabLeft", "IA_TabRight"],
            "imc": "IMC_UI",
            "save_path": save_path,
        })
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_create_input_action(
    name: str,
    save_path: str,
    value_type: str = "bool",
    consume_input: bool = True,
    trigger_when_paused: bool = False,
) -> dict:
    """Create a single Enhanced Input Action asset."""
    import unreal
    try:
        vt_map = {
            "bool":   unreal.InputActionValueType.BOOL,
            "axis1d": unreal.InputActionValueType.AXIS1D,
            "axis2d": unreal.InputActionValueType.AXIS2D,
            "axis3d": unreal.InputActionValueType.AXIS3D,
        }
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        action = _make_action(tools, name, save_path, vt_map.get(value_type, unreal.InputActionValueType.BOOL), consume_input)
        if not action:
            return _err(f"Failed to create InputAction: {name}")
        if trigger_when_paused:
            action.set_editor_property("trigger_when_paused", True)
            unreal.EditorAssetLibrary.save_asset(action.get_path_name())
        result = _ok({"path": action.get_path_name(), "name": name, "value_type": value_type})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_create_imc(name: str, save_path: str) -> dict:
    """Create a blank Input Mapping Context asset."""
    import unreal
    try:
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        imc = _make_imc(tools, name, save_path)
        if not imc:
            return _err(f"Failed to create IMC: {name}")
        unreal.EditorAssetLibrary.save_asset(imc.get_path_name())
        result = _ok({"path": imc.get_path_name(), "name": name})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_add_key_mapping(
    imc_path: str,
    action_path: str,
    key: str,
    negate: bool = False,
    swizzle: bool = False,
) -> dict:
    """Add a key mapping to an IMC."""
    import unreal
    try:
        imc    = unreal.load_asset(imc_path)
        action = unreal.load_asset(action_path)
        if not imc or not action:
            return _err("IMC or Action not found")
        mapping = imc.map_key(action, unreal.Key(key))
        if mapping:
            mods = []
            if negate:  mods.append(unreal.InputModifierNegate())
            if swizzle: mods.append(unreal.InputModifierSwizzleAxis())
            if mods:    mapping.set_editor_property("modifiers", mods)
        unreal.EditorAssetLibrary.save_asset(imc_path)
        result = _ok({"imc": imc_path, "action": action_path, "key": key})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_list_input_assets(search_path: str = "/Game") -> dict:
    """List all InputAction and InputMappingContext assets."""
    import unreal
    try:
        reg = unreal.AssetRegistryHelpers.get_asset_registry()
        assets = reg.get_assets_by_path(search_path, recursive=True)
        actions = [{"name": str(a.asset_name), "path": str(a.object_path)}
                   for a in assets if "InputAction" in str(a.asset_class_path) and "InputMappingContext" not in str(a.asset_class_path)]
        imcs    = [{"name": str(a.asset_name), "path": str(a.object_path)}
                   for a in assets if "InputMappingContext" in str(a.asset_class_path)]
        result = _ok({
            "input_actions":     actions,
            "mapping_contexts":  imcs,
            "action_count":      len(actions),
            "imc_count":         len(imcs),
        })
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_get_imc_mappings(imc_path: str) -> dict:
    """Return all key-to-action mappings in an IMC."""
    import unreal
    try:
        imc = unreal.load_asset(imc_path)
        if not imc:
            return _err(f"IMC not found: {imc_path}")
        mappings = imc.get_editor_property("mappings") or []
        result_mappings = []
        for m in mappings:
            action = m.get_editor_property("action")
            key    = m.get_editor_property("key")
            result_mappings.append({
                "action":          action.get_name() if action else "None",
                "key":             str(key.get_fname()) if key else "None",
                "modifier_count":  len(m.get_editor_property("modifiers") or []),
                "trigger_count":   len(m.get_editor_property("triggers") or []),
            })
        result = _ok({"imc": imc_path, "mappings": result_mappings, "total": len(result_mappings)})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_input_diagnostics(search_path: str = "/Game") -> dict:
    """Print full Enhanced Input diagnostics."""
    import unreal
    try:
        reg = unreal.AssetRegistryHelpers.get_asset_registry()
        assets = reg.get_assets_by_path(search_path, recursive=True)
        actions = [a for a in assets if "InputAction" in str(a.asset_class_path) and "InputMappingContext" not in str(a.asset_class_path)]
        imcs    = [a for a in assets if "InputMappingContext" in str(a.asset_class_path)]
        result = _ok({
            "input_action_count":     len(actions),
            "mapping_context_count":  len(imcs),
            "action_names":           [str(a.asset_name) for a in actions],
            "imc_names":              [str(a.asset_name) for a in imcs],
        })
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))
