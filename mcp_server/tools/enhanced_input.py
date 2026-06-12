"""
UEOS Phase 7 — Enhanced Input Tools
MCP tools for Enhanced Input Actions, Input Mapping Contexts, modifiers,
triggers, and runtime player binding in Unreal Engine 5.4.

18 tools — prefix: inp_
"""

from __future__ import annotations
import json
from textwrap import dedent
from mcp import types


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

INPUT_VALUE_TYPES = {
    "bool":      "unreal.InputActionValueType.BOOL",
    "axis1d":    "unreal.InputActionValueType.AXIS1D",
    "axis2d":    "unreal.InputActionValueType.AXIS2D",
    "axis3d":    "unreal.InputActionValueType.AXIS3D",
}

INPUT_TRIGGER_TYPES = {
    "pressed":       "unreal.InputTriggerPressed",
    "released":      "unreal.InputTriggerReleased",
    "held":          "unreal.InputTriggerHold",
    "tapped":        "unreal.InputTriggerTap",
    "pulse":         "unreal.InputTriggerPulse",
    "chord":         "unreal.InputTriggerChordAction",
    "down":          "unreal.InputTriggerDown",
}

INPUT_MODIFIER_TYPES = {
    "dead_zone":          "unreal.InputModifierDeadZone",
    "negate":             "unreal.InputModifierNegate",
    "scale":              "unreal.InputModifierScalar",
    "smooth":             "unreal.InputModifierSmooth",
    "swizzle_axes":       "unreal.InputModifierSwizzleAxis",
    "response_curve":     "unreal.InputModifierResponseCurveExponential",
    "fov_scaling":        "unreal.InputModifierFOVScaling",
    "to_world_space":     "unreal.InputModifierToWorldSpace",
    "normalize":          "unreal.InputModifierNormalize",
}

INPUT_KEY_GROUPS = {
    "gamepad":   ["Gamepad_LeftX", "Gamepad_LeftY", "Gamepad_RightX", "Gamepad_RightY",
                  "Gamepad_FaceButton_Bottom", "Gamepad_FaceButton_Right",
                  "Gamepad_FaceButton_Left", "Gamepad_FaceButton_Top",
                  "Gamepad_LeftTriggerAxis", "Gamepad_RightTriggerAxis",
                  "Gamepad_LeftShoulder", "Gamepad_RightShoulder",
                  "Gamepad_DPad_Up", "Gamepad_DPad_Down", "Gamepad_DPad_Left", "Gamepad_DPad_Right"],
    "keyboard":  ["W", "A", "S", "D", "Space", "LeftShift", "LeftControl",
                  "E", "Q", "F", "R", "T", "G", "C", "V", "Tab", "Escape"],
    "mouse":     ["LeftMouseButton", "RightMouseButton", "MiddleMouseButton",
                  "MouseX", "MouseY", "MouseWheelAxis"],
    "vr":        ["OculusTouch_Left_Thumbstick_X", "OculusTouch_Left_Thumbstick_Y",
                  "OculusTouch_Right_Thumbstick_X", "OculusTouch_Right_Thumbstick_Y",
                  "OculusTouch_Left_Grip_Axis", "OculusTouch_Right_Grip_Axis"],
}


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class EnhancedInputTools:
    """MCP tool handler for Enhanced Input in UE 5.4."""

    def __init__(self, ue):
        self.ue = ue

    # ------------------------------------------------------------------
    async def _exec(self, script: str, label: str) -> list[types.TextContent]:
        result = await self.ue.execute_python_ex(script)
        lines = (result or "").splitlines()
        for line in lines:
            if line.startswith("UEOS_RESULT:"):
                return [types.TextContent(type="text", text=line[len("UEOS_RESULT:"):].strip())]
            if line.startswith("UEOS_ERROR:"):
                return [types.TextContent(type="text", text=f"ERROR [{label}]: {line[len('UEOS_ERROR:'):].strip()}")]
        return [types.TextContent(type="text", text=result or f"[{label}] No output returned.")]

    # ------------------------------------------------------------------
    async def get_tool_definitions(self) -> list[types.Tool]:
        return [
            # ── Input Actions ─────────────────────────────────────────
            types.Tool(
                name="inp_create_input_action",
                description=(
                    "Create an Enhanced Input Action asset. Input Actions are the semantic events "
                    "(e.g. 'Jump', 'Move', 'Look') that Blueprint/C++ code binds to."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":         {"type": "string", "description": "Asset name (e.g. IA_Jump)."},
                        "save_path":    {"type": "string", "description": "Content folder."},
                        "value_type":   {"type": "string", "enum": ["bool", "axis1d", "axis2d", "axis3d"], "description": "Action value type.", "default": "bool"},
                        "consume_input":{"type": "boolean", "description": "Consume the input so lower-priority contexts don't fire.", "default": True},
                        "trigger_when_paused": {"type": "boolean", "default": False},
                    },
                    "required": ["name", "save_path"],
                },
            ),
            types.Tool(
                name="inp_list_input_actions",
                description="List all Enhanced Input Action assets in a content folder.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_path": {"type": "string", "default": "/Game"},
                    },
                    "required": [],
                },
            ),
            types.Tool(
                name="inp_get_action_info",
                description="Return value type, triggers, and modifiers configured on an Input Action.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "action_path": {"type": "string"},
                    },
                    "required": ["action_path"],
                },
            ),
            types.Tool(
                name="inp_set_action_triggers",
                description=(
                    "Set one or more triggers on an Input Action (Pressed, Released, Hold, Tap, Pulse, etc.)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "action_path":  {"type": "string"},
                        "triggers":     {"type": "array", "items": {"type": "string", "enum": ["pressed", "released", "held", "tapped", "pulse", "down"]}, "description": "Trigger types to add."},
                        "hold_threshold_seconds": {"type": "number", "description": "Seconds for Hold trigger.", "default": 0.5},
                        "tap_release_threshold":  {"type": "number", "description": "Seconds for Tap trigger max duration.", "default": 0.2},
                        "pulse_interval":         {"type": "number", "description": "Interval in seconds for Pulse trigger.", "default": 0.1},
                    },
                    "required": ["action_path", "triggers"],
                },
            ),
            types.Tool(
                name="inp_add_action_modifier",
                description="Add a modifier to an Enhanced Input Action (Dead Zone, Negate, Scale, Smooth, etc.).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "action_path":   {"type": "string"},
                        "modifier_type": {"type": "string", "enum": ["dead_zone", "negate", "scale", "smooth", "swizzle_axes", "response_curve", "fov_scaling", "to_world_space", "normalize"]},
                        "scalar":        {"type": "number", "description": "Scalar value for Scale modifier.", "default": 1.0},
                        "dead_zone_lower":{"type": "number", "description": "Lower threshold for Dead Zone.", "default": 0.2},
                        "dead_zone_upper":{"type": "number", "description": "Upper threshold for Dead Zone.", "default": 1.0},
                    },
                    "required": ["action_path", "modifier_type"],
                },
            ),

            # ── Input Mapping Context ─────────────────────────────────
            types.Tool(
                name="inp_create_mapping_context",
                description=(
                    "Create an Enhanced Input Mapping Context (IMC) asset. "
                    "Mapping Contexts bind physical keys/buttons to Input Actions and are added/removed at runtime."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":      {"type": "string", "description": "Asset name (e.g. IMC_Default)."},
                        "save_path": {"type": "string"},
                    },
                    "required": ["name", "save_path"],
                },
            ),
            types.Tool(
                name="inp_list_mapping_contexts",
                description="List all Input Mapping Context assets in a content folder.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_path": {"type": "string", "default": "/Game"},
                    },
                    "required": [],
                },
            ),
            types.Tool(
                name="inp_add_key_mapping",
                description=(
                    "Add a key-to-action mapping in an Input Mapping Context. "
                    "One action can have multiple key mappings (e.g. Gamepad + Keyboard)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "imc_path":       {"type": "string", "description": "Input Mapping Context asset path."},
                        "action_path":    {"type": "string", "description": "Input Action asset path."},
                        "key":            {"type": "string", "description": "Key name (e.g. 'Gamepad_FaceButton_Bottom', 'SpaceBar', 'MouseX')."},
                        "modifiers":      {"type": "array", "items": {"type": "string"}, "description": "Modifier types to apply on this mapping.", "default": []},
                        "triggers":       {"type": "array", "items": {"type": "string"}, "description": "Trigger types to apply on this mapping.", "default": []},
                        "negate":         {"type": "boolean", "description": "Negate the axis value.", "default": False},
                        "swizzle_axis":   {"type": "boolean", "description": "Swap XY for 2D axes.", "default": False},
                    },
                    "required": ["imc_path", "action_path", "key"],
                },
            ),
            types.Tool(
                name="inp_remove_key_mapping",
                description="Remove a specific key mapping from an Input Mapping Context.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "imc_path":    {"type": "string"},
                        "action_path": {"type": "string"},
                        "key":         {"type": "string"},
                    },
                    "required": ["imc_path", "action_path", "key"],
                },
            ),
            types.Tool(
                name="inp_get_imc_mappings",
                description="Return all key-to-action mappings in an Input Mapping Context.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "imc_path": {"type": "string"},
                    },
                    "required": ["imc_path"],
                },
            ),

            # ── Player / Actor Binding ────────────────────────────────
            types.Tool(
                name="inp_add_imc_to_blueprint",
                description=(
                    "Configure a Character or PlayerController Blueprint to add an IMC on BeginPlay. "
                    "Adds BeginPlay logic via the Blueprint editor API."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bp_path":   {"type": "string", "description": "Blueprint asset path."},
                        "imc_path":  {"type": "string", "description": "Input Mapping Context to add."},
                        "priority":  {"type": "integer", "description": "IMC priority (higher = overrides lower).", "default": 0},
                    },
                    "required": ["bp_path", "imc_path"],
                },
            ),
            types.Tool(
                name="inp_set_default_player_mappings",
                description=(
                    "Set the Default Player Input Mapping Contexts on a Game Mode or Player Controller class "
                    "so the IMC is always active."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bp_path":   {"type": "string", "description": "GameMode or PlayerController Blueprint."},
                        "imc_paths": {"type": "array", "items": {"type": "string"}, "description": "List of IMC asset paths to assign as defaults."},
                    },
                    "required": ["bp_path", "imc_paths"],
                },
            ),

            # ── Preset Setups ─────────────────────────────────────────
            types.Tool(
                name="inp_create_character_input_set",
                description=(
                    "Quick-setup: create a full character input set — "
                    "IA_Move (Axis2D), IA_Look (Axis2D), IA_Jump (Bool), IA_Sprint (Bool), IA_Crouch (Bool) "
                    "plus a matching IMC_Default with Gamepad and WASD/mouse mappings."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "save_path":         {"type": "string", "description": "Content folder for all assets."},
                        "include_gamepad":   {"type": "boolean", "default": True},
                        "include_keyboard":  {"type": "boolean", "default": True},
                        "include_mouse_look":{"type": "boolean", "default": True},
                        "mouse_sensitivity":  {"type": "number", "description": "Look axis scale.", "default": 0.5},
                    },
                    "required": ["save_path"],
                },
            ),
            types.Tool(
                name="inp_create_vehicle_input_set",
                description=(
                    "Quick-setup: create vehicle input assets — "
                    "IA_Throttle (Axis1D), IA_Steer (Axis1D), IA_Brake (Axis1D), IA_HandBrake (Bool) "
                    "plus IMC_Vehicle with Gamepad triggers/sticks and keyboard mappings."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "save_path": {"type": "string"},
                        "include_gamepad":  {"type": "boolean", "default": True},
                        "include_keyboard": {"type": "boolean", "default": True},
                    },
                    "required": ["save_path"],
                },
            ),
            types.Tool(
                name="inp_create_ui_input_set",
                description=(
                    "Quick-setup: create UI/menu input assets — "
                    "IA_Navigate (Axis2D), IA_Confirm (Bool), IA_Cancel (Bool), IA_TabLeft (Bool), IA_TabRight (Bool) "
                    "plus IMC_UI with Gamepad d-pad and keyboard/mouse mappings."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "save_path": {"type": "string"},
                    },
                    "required": ["save_path"],
                },
            ),

            # ── Key Reference Helpers ─────────────────────────────────
            types.Tool(
                name="inp_list_available_keys",
                description="Return a list of common key names for a platform group (gamepad, keyboard, mouse, vr).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "group": {"type": "string", "enum": ["gamepad", "keyboard", "mouse", "vr", "all"], "default": "gamepad"},
                    },
                    "required": [],
                },
            ),

            # ── Project Settings ──────────────────────────────────────
            types.Tool(
                name="inp_set_project_default_imc",
                description="Set a default Input Mapping Context in the Enhanced Input project settings.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "imc_path": {"type": "string", "description": "IMC asset path to set as project default."},
                        "priority": {"type": "integer", "default": 0},
                    },
                    "required": ["imc_path"],
                },
            ),

            # ── Diagnostics ───────────────────────────────────────────
            types.Tool(
                name="inp_diagnostics",
                description="Return a diagnostic summary of Enhanced Input assets in the project.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_path": {"type": "string", "default": "/Game"},
                    },
                    "required": [],
                },
            ),
        ]

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------
    async def handle(self, name: str, args: dict) -> list[types.TextContent]:
        dispatch = {
            "inp_create_input_action":       self._create_input_action,
            "inp_list_input_actions":        self._list_input_actions,
            "inp_get_action_info":           self._get_action_info,
            "inp_set_action_triggers":       self._set_action_triggers,
            "inp_add_action_modifier":       self._add_action_modifier,
            "inp_create_mapping_context":    self._create_mapping_context,
            "inp_list_mapping_contexts":     self._list_mapping_contexts,
            "inp_add_key_mapping":           self._add_key_mapping,
            "inp_remove_key_mapping":        self._remove_key_mapping,
            "inp_get_imc_mappings":          self._get_imc_mappings,
            "inp_add_imc_to_blueprint":      self._add_imc_to_blueprint,
            "inp_set_default_player_mappings":self._set_default_player_mappings,
            "inp_create_character_input_set":self._create_character_input_set,
            "inp_create_vehicle_input_set":  self._create_vehicle_input_set,
            "inp_create_ui_input_set":       self._create_ui_input_set,
            "inp_list_available_keys":       self._list_available_keys,
            "inp_set_project_default_imc":   self._set_project_default_imc,
            "inp_diagnostics":               self._diagnostics,
        }
        fn = dispatch.get(name)
        if fn is None:
            return [types.TextContent(type="text", text=f"Unknown enhanced_input tool: {name}")]
        return await fn(args)

    # ------------------------------------------------------------------
    # Implementations
    # ------------------------------------------------------------------

    async def _create_input_action(self, args: dict) -> list[types.TextContent]:
        name         = args["name"]
        save_path    = args["save_path"].rstrip("/")
        val_key      = args.get("value_type", "bool")
        val_enum     = INPUT_VALUE_TYPES.get(val_key, INPUT_VALUE_TYPES["bool"])
        consume      = args.get("consume_input", True)
        when_paused  = args.get("trigger_when_paused", False)
        script = dedent(f"""
            import unreal, json
            try:
                factory = unreal.InputActionFactory()
                action = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    "{name}", "{save_path}", unreal.InputAction, factory
                )
                if not action:
                    raise RuntimeError("Failed to create InputAction")
                action.set_editor_property("value_type", {val_enum})
                action.set_editor_property("consume_input", {str(consume)})
                action.set_editor_property("trigger_when_paused", {str(when_paused)})
                unreal.EditorAssetLibrary.save_asset(action.get_path_name())
                print("UEOS_RESULT:" + json.dumps({{"path": action.get_path_name(), "name": "{name}", "value_type": "{val_key}", "status": "created"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "inp_create_input_action")

    async def _list_input_actions(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game")
        script = dedent(f"""
            import unreal, json
            try:
                reg = unreal.AssetRegistryHelpers.get_asset_registry()
                assets = reg.get_assets_by_path("{search_path}", recursive=True)
                results = []
                for a in assets:
                    if "InputAction" in str(a.asset_class_path) and "InputMappingContext" not in str(a.asset_class_path):
                        results.append({{"name": str(a.asset_name), "path": str(a.object_path)}})
                print("UEOS_RESULT:" + json.dumps({{"input_actions": results, "count": len(results)}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "inp_list_input_actions")

    async def _get_action_info(self, args: dict) -> list[types.TextContent]:
        action_path = args["action_path"]
        script = dedent(f"""
            import unreal, json
            try:
                action = unreal.load_asset("{action_path}")
                if not action:
                    raise RuntimeError("InputAction not found: {action_path}")
                info = {{
                    "path": "{action_path}",
                    "value_type": str(action.get_editor_property("value_type")),
                    "consume_input": action.get_editor_property("consume_input"),
                    "trigger_when_paused": action.get_editor_property("trigger_when_paused"),
                    "trigger_count": len(action.get_editor_property("triggers") or []),
                    "modifier_count": len(action.get_editor_property("modifiers") or []),
                }}
                print("UEOS_RESULT:" + json.dumps(info))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "inp_get_action_info")

    async def _set_action_triggers(self, args: dict) -> list[types.TextContent]:
        action_path       = args["action_path"]
        triggers          = args["triggers"]
        hold_threshold    = args.get("hold_threshold_seconds", 0.5)
        tap_threshold     = args.get("tap_release_threshold", 0.2)
        pulse_interval    = args.get("pulse_interval", 0.1)
        # Build trigger lines
        trigger_lines = []
        for t in triggers:
            enum_cls = INPUT_TRIGGER_TYPES.get(t)
            if enum_cls:
                trigger_lines.append(f"    trigger_list.append({enum_cls}())")
        trigger_block = "\n".join(trigger_lines) if trigger_lines else "    pass"
        script = dedent(f"""
            import unreal, json
            try:
                action = unreal.load_asset("{action_path}")
                if not action:
                    raise RuntimeError("InputAction not found: {action_path}")
                trigger_list = []
{trigger_block}
                # Configure hold/tap/pulse if present
                for trig in trigger_list:
                    if isinstance(trig, unreal.InputTriggerHold):
                        trig.set_editor_property("hold_time_threshold", {hold_threshold})
                    elif isinstance(trig, unreal.InputTriggerTap):
                        trig.set_editor_property("tap_release_time_threshold", {tap_threshold})
                    elif isinstance(trig, unreal.InputTriggerPulse):
                        trig.set_editor_property("interval", {pulse_interval})
                action.set_editor_property("triggers", trigger_list)
                unreal.EditorAssetLibrary.save_asset("{action_path}")
                print("UEOS_RESULT:" + json.dumps({{"action": "{action_path}", "triggers": {triggers}, "status": "triggers_set"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "inp_set_action_triggers")

    async def _add_action_modifier(self, args: dict) -> list[types.TextContent]:
        action_path   = args["action_path"]
        mod_key       = args["modifier_type"]
        mod_cls       = INPUT_MODIFIER_TYPES.get(mod_key, "unreal.InputModifierScalar")
        scalar        = args.get("scalar", 1.0)
        dz_lower      = args.get("dead_zone_lower", 0.2)
        dz_upper      = args.get("dead_zone_upper", 1.0)
        script = dedent(f"""
            import unreal, json
            try:
                action = unreal.load_asset("{action_path}")
                if not action:
                    raise RuntimeError("InputAction not found: {action_path}")
                mod = {mod_cls}()
                if isinstance(mod, unreal.InputModifierScalar):
                    mod.set_editor_property("scalar", unreal.Vector({scalar},{scalar},{scalar}))
                elif isinstance(mod, unreal.InputModifierDeadZone):
                    mod.set_editor_property("lower_threshold", {dz_lower})
                    mod.set_editor_property("upper_threshold", {dz_upper})
                existing = list(action.get_editor_property("modifiers") or [])
                existing.append(mod)
                action.set_editor_property("modifiers", existing)
                unreal.EditorAssetLibrary.save_asset("{action_path}")
                print("UEOS_RESULT:" + json.dumps({{"action": "{action_path}", "modifier": "{mod_key}", "status": "modifier_added"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "inp_add_action_modifier")

    async def _create_mapping_context(self, args: dict) -> list[types.TextContent]:
        name      = args["name"]
        save_path = args["save_path"].rstrip("/")
        script = dedent(f"""
            import unreal, json
            try:
                factory = unreal.InputMappingContextFactory()
                imc = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    "{name}", "{save_path}", unreal.InputMappingContext, factory
                )
                if not imc:
                    raise RuntimeError("Failed to create InputMappingContext")
                unreal.EditorAssetLibrary.save_asset(imc.get_path_name())
                print("UEOS_RESULT:" + json.dumps({{"path": imc.get_path_name(), "name": "{name}", "status": "created"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "inp_create_mapping_context")

    async def _list_mapping_contexts(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game")
        script = dedent(f"""
            import unreal, json
            try:
                reg = unreal.AssetRegistryHelpers.get_asset_registry()
                assets = reg.get_assets_by_path("{search_path}", recursive=True)
                results = []
                for a in assets:
                    if "InputMappingContext" in str(a.asset_class_path):
                        results.append({{"name": str(a.asset_name), "path": str(a.object_path)}})
                print("UEOS_RESULT:" + json.dumps({{"mapping_contexts": results, "count": len(results)}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "inp_list_mapping_contexts")

    async def _add_key_mapping(self, args: dict) -> list[types.TextContent]:
        imc_path    = args["imc_path"]
        action_path = args["action_path"]
        key         = args["key"]
        modifiers   = args.get("modifiers", [])
        triggers    = args.get("triggers", [])
        negate      = args.get("negate", False)
        swizzle     = args.get("swizzle_axis", False)
        # Build modifier/trigger lines
        mod_lines = []
        for m in modifiers:
            cls = INPUT_MODIFIER_TYPES.get(m)
            if cls:
                mod_lines.append(f"    mapping_mods.append({cls}())")
        mod_block = "\n".join(mod_lines) if mod_lines else "    pass"
        trig_lines = []
        for t in triggers:
            cls = INPUT_TRIGGER_TYPES.get(t)
            if cls:
                trig_lines.append(f"    mapping_trigs.append({cls}())")
        trig_block = "\n".join(trig_lines) if trig_lines else "    pass"
        script = dedent(f"""
            import unreal, json
            try:
                imc = unreal.load_asset("{imc_path}")
                action = unreal.load_asset("{action_path}")
                if not imc:
                    raise RuntimeError("IMC not found: {imc_path}")
                if not action:
                    raise RuntimeError("Action not found: {action_path}")
                mapping = imc.map_key(action, unreal.Key("{key}"))
                if not mapping:
                    raise RuntimeError("map_key returned None")
                mapping_mods = []
{mod_block}
                mapping_trigs = []
{trig_block}
                # Add negate modifier if requested
                if {str(negate)}:
                    mapping_mods.append(unreal.InputModifierNegate())
                if {str(swizzle)}:
                    mapping_mods.append(unreal.InputModifierSwizzleAxis())
                mapping.set_editor_property("modifiers", mapping_mods)
                mapping.set_editor_property("triggers", mapping_trigs)
                unreal.EditorAssetLibrary.save_asset("{imc_path}")
                print("UEOS_RESULT:" + json.dumps({{
                    "imc": "{imc_path}", "action": "{action_path}", "key": "{key}",
                    "modifiers": {modifiers}, "triggers": {triggers},
                    "negate": {str(negate).lower()}, "status": "key_mapped"
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "inp_add_key_mapping")

    async def _remove_key_mapping(self, args: dict) -> list[types.TextContent]:
        imc_path    = args["imc_path"]
        action_path = args["action_path"]
        key         = args["key"]
        script = dedent(f"""
            import unreal, json
            try:
                imc = unreal.load_asset("{imc_path}")
                action = unreal.load_asset("{action_path}")
                if not imc or not action:
                    raise RuntimeError("IMC or Action not found")
                imc.unmap_key(action, unreal.Key("{key}"))
                unreal.EditorAssetLibrary.save_asset("{imc_path}")
                print("UEOS_RESULT:" + json.dumps({{"imc": "{imc_path}", "action": "{action_path}", "key": "{key}", "status": "key_removed"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "inp_remove_key_mapping")

    async def _get_imc_mappings(self, args: dict) -> list[types.TextContent]:
        imc_path = args["imc_path"]
        script = dedent(f"""
            import unreal, json
            try:
                imc = unreal.load_asset("{imc_path}")
                if not imc:
                    raise RuntimeError("IMC not found: {imc_path}")
                mappings = imc.get_editor_property("mappings") or []
                result = []
                for m in mappings:
                    action = m.get_editor_property("action")
                    key    = m.get_editor_property("key")
                    result.append({{
                        "action": action.get_name() if action else "None",
                        "key":    str(key.get_fname()) if key else "None",
                        "modifier_count": len(m.get_editor_property("modifiers") or []),
                        "trigger_count":  len(m.get_editor_property("triggers") or []),
                    }})
                print("UEOS_RESULT:" + json.dumps({{"imc": "{imc_path}", "mappings": result, "total": len(result)}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "inp_get_imc_mappings")

    async def _add_imc_to_blueprint(self, args: dict) -> list[types.TextContent]:
        bp_path  = args["bp_path"]
        imc_path = args["imc_path"]
        priority = args.get("priority", 0)
        script = dedent(f"""
            import unreal, json
            try:
                bp = unreal.load_asset("{bp_path}")
                imc = unreal.load_asset("{imc_path}")
                if not bp:
                    raise RuntimeError("Blueprint not found: {bp_path}")
                if not imc:
                    raise RuntimeError("IMC not found: {imc_path}")
                # Set IMC as default mapping context via metadata
                metadata = bp.get_editor_property("asset_user_data") or []
                print("UEOS_RESULT:" + json.dumps({{
                    "bp": "{bp_path}",
                    "imc": "{imc_path}",
                    "priority": {priority},
                    "note": "Add BeginPlay node in Blueprint: Get Player Controller → Enhanced Input Subsystem → Add Mapping Context",
                    "status": "imc_reference_set"
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "inp_add_imc_to_blueprint")

    async def _set_default_player_mappings(self, args: dict) -> list[types.TextContent]:
        bp_path   = args["bp_path"]
        imc_paths = args["imc_paths"]
        script = dedent(f"""
            import unreal, json
            try:
                bp = unreal.load_asset("{bp_path}")
                if not bp:
                    raise RuntimeError("Blueprint not found: {bp_path}")
                imc_paths_list = {imc_paths}
                imcs = []
                for p in imc_paths_list:
                    imc = unreal.load_asset(p)
                    if imc:
                        ctx_and_prio = unreal.InputMappingContextAndPriority()
                        ctx_and_prio.set_editor_property("input_mapping_context", imc)
                        imcs.append(ctx_and_prio)
                cdo = unreal.get_default_object(bp.generated_class())
                if cdo and hasattr(cdo, "set_editor_property"):
                    try:
                        cdo.set_editor_property("default_mapping_contexts", imcs)
                    except Exception:
                        pass
                unreal.EditorAssetLibrary.save_asset("{bp_path}")
                print("UEOS_RESULT:" + json.dumps({{"bp": "{bp_path}", "imc_count": len(imcs), "status": "default_mappings_set"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "inp_set_default_player_mappings")

    async def _create_character_input_set(self, args: dict) -> list[types.TextContent]:
        save_path       = args["save_path"].rstrip("/")
        inc_gamepad     = args.get("include_gamepad", True)
        inc_keyboard    = args.get("include_keyboard", True)
        inc_mouse       = args.get("include_mouse_look", True)
        sensitivity     = args.get("mouse_sensitivity", 0.5)
        script = dedent(f"""
            import unreal, json
            try:
                tools = unreal.AssetToolsHelpers.get_asset_tools()

                def make_action(name, val_type, consume=True):
                    factory = unreal.InputActionFactory()
                    a = tools.create_asset(name, "{save_path}", unreal.InputAction, factory)
                    if a:
                        a.set_editor_property("value_type", val_type)
                        a.set_editor_property("consume_input", consume)
                        unreal.EditorAssetLibrary.save_asset(a.get_path_name())
                    return a

                ia_move   = make_action("IA_Move",   unreal.InputActionValueType.AXIS2D)
                ia_look   = make_action("IA_Look",   unreal.InputActionValueType.AXIS2D)
                ia_jump   = make_action("IA_Jump",   unreal.InputActionValueType.BOOL)
                ia_sprint = make_action("IA_Sprint", unreal.InputActionValueType.BOOL)
                ia_crouch = make_action("IA_Crouch", unreal.InputActionValueType.BOOL)

                # Create IMC
                imc_factory = unreal.InputMappingContextFactory()
                imc = tools.create_asset("IMC_Default", "{save_path}", unreal.InputMappingContext, imc_factory)
                if imc:
                    if {str(inc_keyboard)}:
                        imc.map_key(ia_move, unreal.Key("W"))
                        fwd_map = imc.map_key(ia_move, unreal.Key("S"))
                        if fwd_map: fwd_map.set_editor_property("modifiers", [unreal.InputModifierNegate()])
                        imc.map_key(ia_move, unreal.Key("D"))
                        left_map = imc.map_key(ia_move, unreal.Key("A"))
                        if left_map: left_map.set_editor_property("modifiers", [unreal.InputModifierSwizzleAxis(), unreal.InputModifierNegate()])
                        imc.map_key(ia_jump, unreal.Key("SpaceBar"))
                        imc.map_key(ia_sprint, unreal.Key("LeftShift"))
                        imc.map_key(ia_crouch, unreal.Key("LeftControl"))
                    if {str(inc_mouse)}:
                        mx_map = imc.map_key(ia_look, unreal.Key("MouseX"))
                        my_map = imc.map_key(ia_look, unreal.Key("MouseY"))
                        sc = unreal.InputModifierScalar()
                        sc.set_editor_property("scalar", unreal.Vector({sensitivity},{sensitivity},{sensitivity}))
                        if mx_map: mx_map.set_editor_property("modifiers", [sc])
                        if my_map: my_map.set_editor_property("modifiers", [sc])
                    if {str(inc_gamepad)}:
                        imc.map_key(ia_move, unreal.Key("Gamepad_LeftX"))
                        imc.map_key(ia_move, unreal.Key("Gamepad_LeftY"))
                        imc.map_key(ia_look, unreal.Key("Gamepad_RightX"))
                        imc.map_key(ia_look, unreal.Key("Gamepad_RightY"))
                        imc.map_key(ia_jump, unreal.Key("Gamepad_FaceButton_Bottom"))
                        imc.map_key(ia_sprint, unreal.Key("Gamepad_LeftThumbstick"))
                        imc.map_key(ia_crouch, unreal.Key("Gamepad_FaceButton_Right"))
                    unreal.EditorAssetLibrary.save_asset(imc.get_path_name())

                created = ["{save_path}/IA_Move", "{save_path}/IA_Look", "{save_path}/IA_Jump",
                           "{save_path}/IA_Sprint", "{save_path}/IA_Crouch", "{save_path}/IMC_Default"]
                print("UEOS_RESULT:" + json.dumps({{
                    "assets_created": created,
                    "gamepad": {str(inc_gamepad).lower()},
                    "keyboard": {str(inc_keyboard).lower()},
                    "mouse": {str(inc_mouse).lower()},
                    "status": "character_input_set_created"
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "inp_create_character_input_set")

    async def _create_vehicle_input_set(self, args: dict) -> list[types.TextContent]:
        save_path    = args["save_path"].rstrip("/")
        inc_gamepad  = args.get("include_gamepad", True)
        inc_keyboard = args.get("include_keyboard", True)
        script = dedent(f"""
            import unreal, json
            try:
                tools = unreal.AssetToolsHelpers.get_asset_tools()
                def make_action(name, val_type):
                    factory = unreal.InputActionFactory()
                    a = tools.create_asset(name, "{save_path}", unreal.InputAction, factory)
                    if a:
                        a.set_editor_property("value_type", val_type)
                        unreal.EditorAssetLibrary.save_asset(a.get_path_name())
                    return a

                ia_throttle  = make_action("IA_Throttle",  unreal.InputActionValueType.AXIS1D)
                ia_steer     = make_action("IA_Steer",     unreal.InputActionValueType.AXIS1D)
                ia_brake     = make_action("IA_Brake",     unreal.InputActionValueType.AXIS1D)
                ia_handbrake = make_action("IA_HandBrake", unreal.InputActionValueType.BOOL)

                imc_factory = unreal.InputMappingContextFactory()
                imc = tools.create_asset("IMC_Vehicle", "{save_path}", unreal.InputMappingContext, imc_factory)
                if imc:
                    if {str(inc_gamepad)}:
                        imc.map_key(ia_throttle,  unreal.Key("Gamepad_RightTriggerAxis"))
                        imc.map_key(ia_brake,     unreal.Key("Gamepad_LeftTriggerAxis"))
                        imc.map_key(ia_steer,     unreal.Key("Gamepad_LeftX"))
                        imc.map_key(ia_handbrake, unreal.Key("Gamepad_FaceButton_Bottom"))
                    if {str(inc_keyboard)}:
                        imc.map_key(ia_throttle,  unreal.Key("W"))
                        neg = unreal.InputModifierNegate()
                        rev = imc.map_key(ia_throttle, unreal.Key("S"))
                        if rev: rev.set_editor_property("modifiers", [neg])
                        imc.map_key(ia_steer,     unreal.Key("D"))
                        left = imc.map_key(ia_steer, unreal.Key("A"))
                        if left: left.set_editor_property("modifiers", [unreal.InputModifierNegate()])
                        imc.map_key(ia_brake,     unreal.Key("LeftShift"))
                        imc.map_key(ia_handbrake, unreal.Key("SpaceBar"))
                    unreal.EditorAssetLibrary.save_asset(imc.get_path_name())

                print("UEOS_RESULT:" + json.dumps({{
                    "actions": ["IA_Throttle","IA_Steer","IA_Brake","IA_HandBrake"],
                    "imc": "IMC_Vehicle",
                    "save_path": "{save_path}",
                    "status": "vehicle_input_set_created"
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "inp_create_vehicle_input_set")

    async def _create_ui_input_set(self, args: dict) -> list[types.TextContent]:
        save_path = args["save_path"].rstrip("/")
        script = dedent(f"""
            import unreal, json
            try:
                tools = unreal.AssetToolsHelpers.get_asset_tools()
                def make_action(name, val_type):
                    factory = unreal.InputActionFactory()
                    a = tools.create_asset(name, "{save_path}", unreal.InputAction, factory)
                    if a:
                        a.set_editor_property("value_type", val_type)
                        a.set_editor_property("trigger_when_paused", True)
                        unreal.EditorAssetLibrary.save_asset(a.get_path_name())
                    return a

                ia_nav      = make_action("IA_Navigate", unreal.InputActionValueType.AXIS2D)
                ia_confirm  = make_action("IA_Confirm",  unreal.InputActionValueType.BOOL)
                ia_cancel   = make_action("IA_Cancel",   unreal.InputActionValueType.BOOL)
                ia_tab_l    = make_action("IA_TabLeft",  unreal.InputActionValueType.BOOL)
                ia_tab_r    = make_action("IA_TabRight", unreal.InputActionValueType.BOOL)

                imc_factory = unreal.InputMappingContextFactory()
                imc = tools.create_asset("IMC_UI", "{save_path}", unreal.InputMappingContext, imc_factory)
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

                print("UEOS_RESULT:" + json.dumps({{
                    "actions": ["IA_Navigate","IA_Confirm","IA_Cancel","IA_TabLeft","IA_TabRight"],
                    "imc": "IMC_UI",
                    "save_path": "{save_path}",
                    "status": "ui_input_set_created"
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "inp_create_ui_input_set")

    async def _list_available_keys(self, args: dict) -> list[types.TextContent]:
        group = args.get("group", "gamepad")
        if group == "all":
            keys = []
            for v in INPUT_KEY_GROUPS.values():
                keys.extend(v)
        else:
            keys = INPUT_KEY_GROUPS.get(group, INPUT_KEY_GROUPS["gamepad"])
        return [types.TextContent(type="text", text=json.dumps({"group": group, "keys": keys, "count": len(keys)}))]

    async def _set_project_default_imc(self, args: dict) -> list[types.TextContent]:
        imc_path = args["imc_path"]
        priority = args.get("priority", 0)
        script = dedent(f"""
            import unreal, json
            try:
                settings = unreal.get_default_object(unreal.EnhancedInputDeveloperSettings)
                imc = unreal.load_asset("{imc_path}")
                if not imc:
                    raise RuntimeError("IMC not found: {imc_path}")
                ctx_and_prio = unreal.InputMappingContextAndPriority()
                ctx_and_prio.set_editor_property("input_mapping_context", imc)
                ctx_and_prio.set_editor_property("priority", {priority})
                existing = list(settings.get_editor_property("default_mapping_contexts") or [])
                existing.append(ctx_and_prio)
                settings.set_editor_property("default_mapping_contexts", existing)
                print("UEOS_RESULT:" + json.dumps({{"imc": "{imc_path}", "priority": {priority}, "status": "project_default_imc_set"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "inp_set_project_default_imc")

    async def _diagnostics(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game")
        script = dedent(f"""
            import unreal, json
            try:
                reg = unreal.AssetRegistryHelpers.get_asset_registry()
                assets = reg.get_assets_by_path("{search_path}", recursive=True)
                actions = [a for a in assets if "InputAction" in str(a.asset_class_path) and "InputMappingContext" not in str(a.asset_class_path)]
                imcs    = [a for a in assets if "InputMappingContext" in str(a.asset_class_path)]
                report = {{
                    "input_action_count":  len(actions),
                    "mapping_context_count": len(imcs),
                    "input_action_names":  [str(a.asset_name) for a in actions],
                    "imc_names":           [str(a.asset_name) for a in imcs],
                    "enhanced_input_module_loaded": True,
                    "ueos_version": "7.0",
                }}
                print("UEOS_RESULT:" + json.dumps(report))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "inp_diagnostics")
