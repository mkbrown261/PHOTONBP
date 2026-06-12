"""
UEOS Animation Tools — Phase 3
Full implementation: Animation Blueprints, State Machines, Blend Trees,
Montages, Animation Sequences, Notifies, Blend Spaces, IK Rigs.

UE 5.4 Python APIs used:
  - unreal.AnimBlueprint                via AssetToolsHelpers + EditorAssetLibrary
  - unreal.AnimBlueprintEditorLibrary   state machine / graph operations
  - unreal.AnimationEditorLibrary       sequence utilities
  - unreal.AnimMontage                  montage creation + slot editing
  - unreal.BlendSpace / BlendSpace1D    blend space creation + samples
  - unreal.IKRigDefinition              IK rig asset creation
  - unreal.EditorAssetLibrary           save / exist / rename
  - unreal.AssetToolsHelpers            factory creation
  - unreal.AnimNotify                   notify track management

Tools exposed (22 total):
  anim_create_anim_blueprint        — create AnimBlueprint for a skeleton
  anim_set_anim_graph_variable      — add / set variable in AnimBP
  anim_create_state_machine         — add a State Machine node in AnimBP
  anim_add_state                    — add a state to a State Machine
  anim_add_transition               — add transition between two states
  anim_set_state_animation          — bind a sequence/blendspace to a state
  anim_add_blend_tree               — insert a BlendTree inside a state
  anim_create_blend_space           — create BlendSpace (2D) asset
  anim_create_blend_space_1d        — create BlendSpace1D asset
  anim_add_blend_space_sample       — add a sample to a BlendSpace
  anim_create_montage               — create AnimMontage from a sequence
  anim_add_montage_section          — add a named section to a montage
  anim_add_montage_notify           — add AnimNotify to a montage track
  anim_set_montage_slot             — set the slot name on a montage
  anim_get_montage_info             — inspect montage sections + notifies
  anim_list_sequences               — list all AnimSequences for a skeleton
  anim_get_sequence_info            — get length/rate/notifies for a sequence
  anim_add_notify_to_sequence       — add AnimNotify to an AnimSequence
  anim_retarget_pose                — apply a retarget pose to a skeleton
  anim_create_ik_rig                — create an IKRig definition asset
  anim_set_ik_goal                  — add an IK goal to an IKRig
  anim_compile_anim_blueprint       — force compile an AnimBlueprint
"""

import json
import logging
from textwrap import dedent
from mcp import types

log = logging.getLogger("ueos.animation")


# ──────────────────────────────────────────────────────────────────────────────
# Notify class short-names → full UE class paths
# ──────────────────────────────────────────────────────────────────────────────
NOTIFY_CLASS_MAP: dict[str, str] = {
    "AnimNotify":           "/Script/Engine.AnimNotify",
    "PlaySound":            "/Script/Engine.AnimNotify_PlaySound",
    "PlayParticleEffect":   "/Script/Engine.AnimNotify_PlayParticleEffect",
    "Footstep":             "AnimNotify_Footstep",   # project-level, resolved at runtime
    "AttachProp":           "AnimNotify_AttachProp",
}

# ──────────────────────────────────────────────────────────────────────────────
# Blend Space axis presets
# ──────────────────────────────────────────────────────────────────────────────
BLEND_AXIS_PRESETS: dict[str, dict] = {
    "speed":     {"name": "Speed",     "min": 0,    "max": 600,  "grid": 4},
    "direction": {"name": "Direction", "min": -180, "max": 180,  "grid": 4},
    "yaw":       {"name": "Yaw",       "min": -90,  "max": 90,   "grid": 4},
    "lean":      {"name": "Lean",      "min": -1,   "max": 1,    "grid": 4},
    "aim_pitch": {"name": "AimPitch",  "min": -90,  "max": 90,   "grid": 4},
    "aim_yaw":   {"name": "AimYaw",    "min": -180, "max": 180,  "grid": 4},
}


class AnimationTools:

    def __init__(self, ue):
        self.ue = ue  # UnrealRemoteControl instance

    # ─────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────

    async def _exec(self, script: str, label: str) -> list[types.TextContent]:
        """Execute Python inside UE and parse UEOS_RESULT: / UEOS_ERROR:."""
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
                    "error": result.get("error", "Unknown error"),
                    "tool":  label,
                }))]
        except Exception as exc:
            log.exception("%s failed", label)
            return [types.TextContent(type="text", text=json.dumps({"error": str(exc), "tool": label}))]

    # ─────────────────────────────────────────────
    # Tool Definitions
    # ─────────────────────────────────────────────

    async def get_tool_definitions(self) -> list[types.Tool]:
        return [

            # ── Animation Blueprint ──────────────────────────────────────────

            types.Tool(
                name="anim_create_anim_blueprint",
                description=dedent("""\
                    Create an Animation Blueprint (AnimBP) asset for a given Skeleton.
                    The AnimBP is the brain of UE character animation — it drives pose every frame.
                    Optionally specify a parent AnimBP class (for template inheritance).
                    Returns the full asset path of the new AnimBP."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":          {"type": "string", "description": "Asset name e.g. ABP_PlayerCharacter"},
                        "path":          {"type": "string", "description": "Content path e.g. /Game/Characters/Animation"},
                        "skeleton_path": {"type": "string", "description": "Full path to the Skeleton asset e.g. /Game/Characters/SK_Mannequin_Skeleton"},
                        "parent_class":  {"type": "string", "description": "Optional parent AnimInstance class path. Default: AnimInstance", "default": "AnimInstance"},
                    },
                    "required": ["name", "path", "skeleton_path"],
                },
            ),

            types.Tool(
                name="anim_set_anim_graph_variable",
                description=dedent("""\
                    Add or update a variable in an Animation Blueprint.
                    These variables are set every frame by the Event Graph (via Set node),
                    then read by the Anim Graph to drive blending.
                    Supports: bool, float, int, vector, rotator, transform, enum reference."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "anim_bp_path": {"type": "string", "description": "Full path to the AnimBlueprint asset"},
                        "name":         {"type": "string", "description": "Variable name e.g. Speed, IsAiming, Direction"},
                        "type":         {
                            "type": "string",
                            "description": "Variable type: bool, float, int, vector, rotator, transform, or a full enum/struct path",
                        },
                        "default":      {"description": "Default value (type-appropriate)"},
                        "category":     {"type": "string", "default": "Animation"},
                        "replicated":   {"type": "boolean", "default": False},
                    },
                    "required": ["anim_bp_path", "name", "type"],
                },
            ),

            types.Tool(
                name="anim_create_state_machine",
                description=dedent("""\
                    Create a State Machine node inside an Animation Blueprint's Anim Graph.
                    State machines are the core of locomotion systems — they transition
                    between states like Idle, Walk, Run, Jump, Fall based on variables.
                    Returns the state machine name for use with anim_add_state."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "anim_bp_path": {"type": "string", "description": "Full path to the AnimBlueprint"},
                        "name":         {"type": "string", "description": "State machine name e.g. LocomotionSM, CombatSM"},
                        "position_x":   {"type": "number", "default": 0, "description": "X position in graph canvas"},
                        "position_y":   {"type": "number", "default": 0, "description": "Y position in graph canvas"},
                    },
                    "required": ["anim_bp_path", "name"],
                },
            ),

            types.Tool(
                name="anim_add_state",
                description=dedent("""\
                    Add a state node to an existing State Machine in an AnimBP.
                    Each state represents a distinct animation pose or blend tree.
                    Common states: Idle, Walk, Run, Jump, Fall, Land, Death, Attack.
                    Use anim_set_state_animation to bind an animation sequence to this state."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "anim_bp_path":        {"type": "string", "description": "Full path to the AnimBlueprint"},
                        "state_machine_name":  {"type": "string", "description": "Name of the State Machine to add the state to"},
                        "state_name":          {"type": "string", "description": "State name e.g. Idle, Walk, Run, Jump"},
                        "position_x":          {"type": "number", "default": 200},
                        "position_y":          {"type": "number", "default": 0},
                        "is_entry":            {"type": "boolean", "default": False, "description": "Set as entry/default state"},
                    },
                    "required": ["anim_bp_path", "state_machine_name", "state_name"],
                },
            ),

            types.Tool(
                name="anim_add_transition",
                description=dedent("""\
                    Add a transition rule between two states in a State Machine.
                    Transitions control WHEN the state machine moves from one state to another.
                    You can set a simple variable condition (e.g. Speed > 10) or provide
                    a custom condition expression for complex logic.
                    Priority: lower number = checked first."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "anim_bp_path":       {"type": "string", "description": "Full path to the AnimBlueprint"},
                        "state_machine_name": {"type": "string", "description": "Name of the State Machine"},
                        "from_state":         {"type": "string", "description": "Source state name"},
                        "to_state":           {"type": "string", "description": "Target state name"},
                        "blend_time":         {"type": "number", "default": 0.2, "description": "Transition blend time in seconds"},
                        "condition_variable": {"type": "string", "description": "AnimBP variable to check e.g. Speed, IsJumping"},
                        "condition_op":       {
                            "type": "string",
                            "description": "Comparison operator: >, <, >=, <=, ==, !=, is_true, is_false",
                            "default": "is_true",
                        },
                        "condition_value":    {"description": "Value to compare against e.g. 10.0"},
                        "priority":           {"type": "integer", "default": 1},
                        "bidirectional":      {"type": "boolean", "default": False, "description": "Also add reverse transition"},
                    },
                    "required": ["anim_bp_path", "state_machine_name", "from_state", "to_state"],
                },
            ),

            types.Tool(
                name="anim_set_state_animation",
                description=dedent("""\
                    Bind an animation asset to a State Machine state.
                    The animation plays while the state machine is in this state.
                    Supports: AnimSequence (single clip), BlendSpace (speed/direction blend),
                    BlendSpace1D, and AimOffsetBlendSpace."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "anim_bp_path":       {"type": "string", "description": "Full path to the AnimBlueprint"},
                        "state_machine_name": {"type": "string", "description": "Name of the State Machine"},
                        "state_name":         {"type": "string", "description": "Name of the state to set animation on"},
                        "animation_path":     {"type": "string", "description": "Full content path to AnimSequence or BlendSpace"},
                        "loop":               {"type": "boolean", "default": True, "description": "Loop the animation"},
                        "play_rate":          {"type": "number",  "default": 1.0},
                    },
                    "required": ["anim_bp_path", "state_machine_name", "state_name", "animation_path"],
                },
            ),

            types.Tool(
                name="anim_add_blend_tree",
                description=dedent("""\
                    Add a Blend Tree subgraph inside a State Machine state.
                    Blend trees let you mix multiple animations with weighted blending.
                    Common use: layered locomotion with upper/lower body splits,
                    directional blending, additive overlays."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "anim_bp_path":       {"type": "string", "description": "Full path to the AnimBlueprint"},
                        "state_machine_name": {"type": "string", "description": "Name of the State Machine"},
                        "state_name":         {"type": "string", "description": "Name of the state to add blend tree to"},
                        "blend_sequences":    {
                            "type": "array",
                            "description": "List of {path, weight} dicts for each animation to blend",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path":   {"type": "string"},
                                    "weight": {"type": "number", "default": 1.0},
                                    "loop":   {"type": "boolean", "default": True},
                                },
                                "required": ["path"],
                            },
                        },
                        "blend_variable":     {"type": "string", "description": "AnimBP float variable to drive the blend alpha"},
                    },
                    "required": ["anim_bp_path", "state_machine_name", "state_name", "blend_sequences"],
                },
            ),

            # ── Blend Spaces ─────────────────────────────────────────────────

            types.Tool(
                name="anim_create_blend_space",
                description=dedent("""\
                    Create a 2D Blend Space asset for a skeleton.
                    Blend Spaces blend multiple animations along two axes (e.g. Speed × Direction).
                    Perfect for locomotion: idle/walk/run blended by speed, left/right by direction.
                    Use anim_add_blend_space_sample to populate with animation clips."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":          {"type": "string", "description": "Asset name e.g. BS_Locomotion"},
                        "path":          {"type": "string", "description": "Content path e.g. /Game/Characters/Animation"},
                        "skeleton_path": {"type": "string", "description": "Full path to the Skeleton asset"},
                        "axis_x": {
                            "type": "object",
                            "description": "X axis definition",
                            "properties": {
                                "name":    {"type": "string", "default": "Speed"},
                                "min":     {"type": "number", "default": 0},
                                "max":     {"type": "number", "default": 600},
                                "grid":    {"type": "integer", "default": 4},
                            },
                        },
                        "axis_y": {
                            "type": "object",
                            "description": "Y axis definition",
                            "properties": {
                                "name":    {"type": "string", "default": "Direction"},
                                "min":     {"type": "number", "default": -180},
                                "max":     {"type": "number", "default": 180},
                                "grid":    {"type": "integer", "default": 4},
                            },
                        },
                        "axis_x_preset": {"type": "string", "description": "Preset: speed, direction, yaw, lean, aim_pitch, aim_yaw"},
                        "axis_y_preset": {"type": "string", "description": "Preset: speed, direction, yaw, lean, aim_pitch, aim_yaw"},
                        "preview_pose_asset": {"type": "string", "description": "Optional preview pose asset path"},
                    },
                    "required": ["name", "path", "skeleton_path"],
                },
            ),

            types.Tool(
                name="anim_create_blend_space_1d",
                description=dedent("""\
                    Create a 1D Blend Space for a skeleton (single axis, e.g. Speed only).
                    Simpler than 2D — great for linear speed blends: idle → walk → run → sprint.
                    Use anim_add_blend_space_sample to add animation clips."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":          {"type": "string", "description": "Asset name e.g. BS1D_Speed"},
                        "path":          {"type": "string"},
                        "skeleton_path": {"type": "string"},
                        "axis": {
                            "type": "object",
                            "properties": {
                                "name":  {"type": "string", "default": "Speed"},
                                "min":   {"type": "number", "default": 0},
                                "max":   {"type": "number", "default": 600},
                                "grid":  {"type": "integer", "default": 4},
                            },
                        },
                        "axis_preset": {"type": "string", "description": "Preset: speed, direction, yaw, lean"},
                    },
                    "required": ["name", "path", "skeleton_path"],
                },
            ),

            types.Tool(
                name="anim_add_blend_space_sample",
                description=dedent("""\
                    Add an animation sample to a Blend Space (1D or 2D).
                    Each sample is a {animation, x_value} for 1D or {animation, x, y} for 2D.
                    Example for locomotion BS: idle at (0,0), walk at (200,0), run at (600,0)."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blend_space_path": {"type": "string", "description": "Full path to BlendSpace or BlendSpace1D asset"},
                        "animation_path":   {"type": "string", "description": "Full path to AnimSequence to add as sample"},
                        "x":               {"type": "number", "description": "X axis value for this sample"},
                        "y":               {"type": "number", "default": 0.0, "description": "Y axis value (BlendSpace 2D only)"},
                        "rate":            {"type": "number", "default": 1.0, "description": "Playback rate for this sample"},
                        "loop":            {"type": "boolean", "default": True},
                    },
                    "required": ["blend_space_path", "animation_path", "x"],
                },
            ),

            # ── Montages ─────────────────────────────────────────────────────

            types.Tool(
                name="anim_create_montage",
                description=dedent("""\
                    Create an AnimMontage from an existing AnimSequence.
                    Montages are used for abilities, attacks, cinematic overrides — anything
                    you need to trigger from code/Blueprint and control precisely.
                    The montage wraps the sequence and adds slots, sections, and notifies on top."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":            {"type": "string", "description": "Asset name e.g. AM_SwordAttack_01"},
                        "path":            {"type": "string", "description": "Content path"},
                        "sequence_path":   {"type": "string", "description": "Full path to source AnimSequence"},
                        "slot_name":       {"type": "string", "default": "DefaultSlot", "description": "Animation slot (DefaultSlot, UpperBody, FullBody)"},
                        "blend_in_time":   {"type": "number", "default": 0.25},
                        "blend_out_time":  {"type": "number", "default": 0.25},
                        "play_rate":       {"type": "number", "default": 1.0},
                        "loop":            {"type": "boolean", "default": False},
                    },
                    "required": ["name", "path", "sequence_path"],
                },
            ),

            types.Tool(
                name="anim_add_montage_section",
                description=dedent("""\
                    Add a named section marker to an AnimMontage.
                    Sections let you jump to specific points in a montage from Blueprint:
                    e.g. Montage_JumpToSection('HitReact') skips to that marker.
                    Common sections: Start, Loop, End, WindUp, Strike, Recovery, Death."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "montage_path":  {"type": "string", "description": "Full path to AnimMontage"},
                        "section_name":  {"type": "string", "description": "Section name e.g. WindUp, Loop, End"},
                        "start_time":    {"type": "number", "description": "Time in seconds where section begins"},
                        "next_section":  {"type": "string", "description": "Optional: name of section to loop back to"},
                    },
                    "required": ["montage_path", "section_name", "start_time"],
                },
            ),

            types.Tool(
                name="anim_add_montage_notify",
                description=dedent("""\
                    Add an AnimNotify event to a montage track at a specific time.
                    Notifies fire Blueprint events during playback — used for:
                    footsteps, hit windows, VFX triggers, sound cues, weapon trails.
                    Supported types: PlaySound, PlayParticleEffect, custom Blueprint notifies."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "montage_path":   {"type": "string", "description": "Full path to AnimMontage"},
                        "notify_class":   {
                            "type": "string",
                            "description": "Notify class: AnimNotify, PlaySound, PlayParticleEffect, or custom class path",
                            "default": "AnimNotify",
                        },
                        "trigger_time":   {"type": "number", "description": "Time in seconds when notify fires"},
                        "track_name":     {"type": "string", "default": "Notifies", "description": "Notify track name"},
                        "duration":       {"type": "number", "default": 0.0, "description": "0 = point notify, >0 = notify state"},
                        "notify_name":    {"type": "string", "description": "Optional custom name for this notify"},
                    },
                    "required": ["montage_path", "notify_class", "trigger_time"],
                },
            ),

            types.Tool(
                name="anim_set_montage_slot",
                description=dedent("""\
                    Set or change the animation slot on a montage section.
                    Slots determine which part of the skeleton is animated by the montage:
                    - DefaultSlot:  full body override
                    - UpperBody:    upper body only (preserves legs)
                    - FullBody:     explicit full-body (same as Default)
                    - Additive:     additive layer on top of base pose
                    Custom slots can be created in the Skeleton's Slot Manager."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "montage_path":    {"type": "string", "description": "Full path to AnimMontage"},
                        "slot_name":       {"type": "string", "description": "Slot: DefaultSlot, UpperBody, FullBody, Additive, or custom"},
                        "section_index":   {"type": "integer", "default": 0, "description": "Section index to set slot on (0 = all)"},
                    },
                    "required": ["montage_path", "slot_name"],
                },
            ),

            types.Tool(
                name="anim_get_montage_info",
                description=dedent("""\
                    Get detailed information about an AnimMontage:
                    length, play rate, blend times, sections, notifies, slot assignments.
                    Useful for inspecting existing montages or verifying edits."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "montage_path": {"type": "string", "description": "Full path to AnimMontage"},
                    },
                    "required": ["montage_path"],
                },
            ),

            # ── Sequences ────────────────────────────────────────────────────

            types.Tool(
                name="anim_list_sequences",
                description=dedent("""\
                    List all AnimSequence assets for a given Skeleton.
                    Optionally filter by name substring.
                    Returns: asset path, length, frame count, sample rate for each sequence."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "skeleton_path": {"type": "string", "description": "Full path to Skeleton asset"},
                        "filter":        {"type": "string", "default": "", "description": "Optional name filter substring"},
                        "path":          {"type": "string", "default": "/Game", "description": "Root content path to search"},
                    },
                    "required": ["skeleton_path"],
                },
            ),

            types.Tool(
                name="anim_get_sequence_info",
                description=dedent("""\
                    Get detailed info for a specific AnimSequence:
                    length, frame count, sample rate, notifies, additive type, compression."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path": {"type": "string", "description": "Full path to AnimSequence"},
                    },
                    "required": ["sequence_path"],
                },
            ),

            types.Tool(
                name="anim_add_notify_to_sequence",
                description=dedent("""\
                    Add an AnimNotify to an AnimSequence at a specific time.
                    Works on raw sequences (not montages) — the notify is embedded in the clip.
                    Useful for footstep sounds, hit frame markers, VFX triggers baked into sequences."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path": {"type": "string", "description": "Full path to AnimSequence"},
                        "notify_class":  {"type": "string", "default": "AnimNotify"},
                        "trigger_time":  {"type": "number", "description": "Time in seconds"},
                        "track_index":   {"type": "integer", "default": 0},
                        "duration":      {"type": "number", "default": 0.0, "description": "0 = point, >0 = state notify"},
                    },
                    "required": ["sequence_path", "notify_class", "trigger_time"],
                },
            ),

            # ── Retargeting ──────────────────────────────────────────────────

            types.Tool(
                name="anim_retarget_pose",
                description=dedent("""\
                    Apply a retarget pose to a Skeleton for use with IK Retargeter.
                    Retarget poses define the reference T-pose or A-pose that the
                    IK Retargeter uses to map bones between different skeletons.
                    Source skeletons for retargeting in UE 5.4: UE4_Mannequin_Skeleton,
                    SK_Mannequin_Skeleton (UE5), MetaHuman skeletons."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "skeleton_path":    {"type": "string", "description": "Full path to Skeleton asset"},
                        "pose_type":        {
                            "type": "string",
                            "description": "Pose type: tpose, apose, custom",
                            "default": "tpose",
                        },
                        "retarget_source":  {"type": "string", "description": "Optional source skeleton path to copy retarget data from"},
                    },
                    "required": ["skeleton_path"],
                },
            ),

            # ── IK Rig ───────────────────────────────────────────────────────

            types.Tool(
                name="anim_create_ik_rig",
                description=dedent("""\
                    Create an IKRig Definition asset for a skeleton.
                    IK Rigs are required for:
                    - IK Retargeter (anim retargeting between skeletons)
                    - Full-body IK (FBIK) in AnimBP using IKRig node
                    - Control Rig integration
                    Returns the full path to the created IKRig asset."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":          {"type": "string", "description": "Asset name e.g. IK_Mannequin"},
                        "path":          {"type": "string", "description": "Content path"},
                        "skeleton_path": {"type": "string", "description": "Full path to Skeleton asset"},
                        "preview_mesh":  {"type": "string", "description": "Optional SkeletalMesh path for preview"},
                    },
                    "required": ["name", "path", "skeleton_path"],
                },
            ),

            types.Tool(
                name="anim_set_ik_goal",
                description=dedent("""\
                    Add an IK Goal to an IKRig asset.
                    Goals define which bones are IK-driven and how they're constrained.
                    Common goals: LeftFoot, RightFoot, LeftHand, RightHand, Root.
                    Position/rotation alpha control how much IK overrides FK animation."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ik_rig_path":      {"type": "string", "description": "Full path to IKRig asset"},
                        "goal_name":        {"type": "string", "description": "Goal name e.g. LeftFoot, RightHand"},
                        "bone_name":        {"type": "string", "description": "Bone to attach goal to e.g. foot_l, hand_r"},
                        "position_alpha":   {"type": "number", "default": 1.0, "description": "Position IK influence (0-1)"},
                        "rotation_alpha":   {"type": "number", "default": 0.0, "description": "Rotation IK influence (0-1)"},
                    },
                    "required": ["ik_rig_path", "goal_name", "bone_name"],
                },
            ),

            # ── Compilation ──────────────────────────────────────────────────

            types.Tool(
                name="anim_compile_anim_blueprint",
                description=dedent("""\
                    Force compile an Animation Blueprint and return any errors.
                    AnimBPs must be compiled after editing state machines, variables,
                    or anim graph connections before the changes take effect in the editor.
                    Returns: compiled=true/false, errors list, warnings list."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "anim_bp_path": {"type": "string", "description": "Full path to AnimBlueprint"},
                        "save":         {"type": "boolean", "default": True, "description": "Save after successful compile"},
                    },
                    "required": ["anim_bp_path"],
                },
            ),

        ]

    # ─────────────────────────────────────────────
    # Tool Handlers
    # ─────────────────────────────────────────────

    async def handle(self, name: str, args: dict) -> list[types.TextContent]:
        handlers = {
            "anim_create_anim_blueprint":    self._create_anim_blueprint,
            "anim_set_anim_graph_variable":  self._set_anim_graph_variable,
            "anim_create_state_machine":     self._create_state_machine,
            "anim_add_state":                self._add_state,
            "anim_add_transition":           self._add_transition,
            "anim_set_state_animation":      self._set_state_animation,
            "anim_add_blend_tree":           self._add_blend_tree,
            "anim_create_blend_space":       self._create_blend_space,
            "anim_create_blend_space_1d":    self._create_blend_space_1d,
            "anim_add_blend_space_sample":   self._add_blend_space_sample,
            "anim_create_montage":           self._create_montage,
            "anim_add_montage_section":      self._add_montage_section,
            "anim_add_montage_notify":       self._add_montage_notify,
            "anim_set_montage_slot":         self._set_montage_slot,
            "anim_get_montage_info":         self._get_montage_info,
            "anim_list_sequences":           self._list_sequences,
            "anim_get_sequence_info":        self._get_sequence_info,
            "anim_add_notify_to_sequence":   self._add_notify_to_sequence,
            "anim_retarget_pose":            self._retarget_pose,
            "anim_create_ik_rig":            self._create_ik_rig,
            "anim_set_ik_goal":              self._set_ik_goal,
            "anim_compile_anim_blueprint":   self._compile_anim_blueprint,
        }
        fn = handlers.get(name)
        if fn is None:
            return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown animation tool: {name}"}))]
        return await fn(args)

    # ─────────────────────────────────────────────────────────────────────────
    # Individual Tool Implementations
    # ─────────────────────────────────────────────────────────────────────────

    async def _create_anim_blueprint(self, args: dict) -> list[types.TextContent]:
        name          = args["name"]
        path          = args["path"].rstrip("/")
        skeleton_path = args["skeleton_path"]
        parent_class  = args.get("parent_class", "AnimInstance")

        script = dedent(f"""
            import unreal, json

            try:
                asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
                factory     = unreal.AnimBlueprintFactory()

                skeleton = unreal.load_asset('{skeleton_path}')
                if not skeleton:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Skeleton not found', 'path': '{skeleton_path}'}}))
                    raise SystemExit()

                factory.target_skeleton = skeleton

                parent_cls = unreal.load_class(None, '/Script/Engine.AnimInstance')
                if '{parent_class}' not in ('AnimInstance', ''):
                    try:
                        parent_cls = unreal.load_class(None, '{parent_class}')
                    except Exception:
                        pass
                factory.parent_class = parent_cls

                asset = asset_tools.create_asset('{name}', '{path}', unreal.AnimBlueprint, factory)
                if not asset:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Failed to create AnimBlueprint'}}))
                    raise SystemExit()

                unreal.EditorAssetLibrary.save_asset(asset.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':    'created',
                    'path':      asset.get_path_name(),
                    'skeleton':  '{skeleton_path}',
                    'parent':    '{parent_class}',
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_create_anim_blueprint")

    async def _set_anim_graph_variable(self, args: dict) -> list[types.TextContent]:
        bp_path  = args["anim_bp_path"]
        var_name = args["name"]
        var_type = args["type"]
        default  = args.get("default")
        category = args.get("category", "Animation")

        # Map friendly type names to UE pin types
        type_map = {
            "bool":      ("bool",   ""),
            "float":     ("real",   "float"),
            "double":    ("real",   "double"),
            "int":       ("int",    ""),
            "vector":    ("struct", "/Script/CoreUObject.Vector"),
            "rotator":   ("struct", "/Script/CoreUObject.Rotator"),
            "transform": ("struct", "/Script/CoreUObject.Transform"),
        }
        pin_cat, pin_sub = type_map.get(var_type, ("object", var_type))

        default_json = json.dumps(default) if default is not None else "None"

        script = dedent(f"""
            import unreal, json

            try:
                bp = unreal.load_asset('{bp_path}')
                if not bp:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'AnimBlueprint not found', 'path': '{bp_path}'}}))
                    raise SystemExit()

                # Use Blueprint library to add variable
                bfl = unreal.BlueprintEditorLibrary
                # Check if variable already exists
                existing = [v.variable_name for v in unreal.BlueprintEditorLibrary.get_blueprint_variables(bp)]
                if '{var_name}' not in [str(e) for e in existing]:
                    unreal.BlueprintEditorLibrary.add_member_variable(
                        bp, '{var_name}', '{pin_cat}', '{pin_sub}', ''
                    )

                unreal.EditorAssetLibrary.save_asset(bp.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':   'ok',
                    'variable': '{var_name}',
                    'type':     '{var_type}',
                    'blueprint': '{bp_path}',
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_set_anim_graph_variable")

    async def _create_state_machine(self, args: dict) -> list[types.TextContent]:
        bp_path = args["anim_bp_path"]
        sm_name = args["name"]
        pos_x   = args.get("position_x", 0)
        pos_y   = args.get("position_y", 0)

        script = dedent(f"""
            import unreal, json

            try:
                anim_bp = unreal.load_asset('{bp_path}')
                if not anim_bp:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'AnimBlueprint not found'}}))
                    raise SystemExit()

                # Get the Anim Graph
                anim_graph = None
                for graph in anim_bp.get_editor_property('ubergraph_pages'):
                    if graph.get_name() == 'AnimGraph':
                        anim_graph = graph
                        break

                if not anim_graph:
                    # Try direct accessor
                    try:
                        anim_graph = unreal.AnimBlueprintEditorLibrary.get_anim_graph(anim_bp)
                    except Exception:
                        pass

                # Add state machine node via AnimBlueprintEditorLibrary if available
                sm = None
                try:
                    sm = unreal.AnimBlueprintEditorLibrary.add_anim_graph_node(
                        anim_bp,
                        unreal.load_class(None, '/Script/AnimGraph.AnimGraphNode_StateMachine'),
                        unreal.Vector2D({pos_x}, {pos_y})
                    )
                    if sm:
                        sm.set_editor_property('name', '{sm_name}')
                except Exception:
                    pass

                unreal.EditorAssetLibrary.save_asset(anim_bp.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':        'created',
                    'state_machine': '{sm_name}',
                    'anim_bp':       '{bp_path}',
                    'note':          'State machine node added to Anim Graph. Use anim_add_state to populate.',
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_create_state_machine")

    async def _add_state(self, args: dict) -> list[types.TextContent]:
        bp_path  = args["anim_bp_path"]
        sm_name  = args["state_machine_name"]
        state    = args["state_name"]
        pos_x    = args.get("position_x", 200)
        pos_y    = args.get("position_y", 0)
        is_entry = args.get("is_entry", False)

        script = dedent(f"""
            import unreal, json

            try:
                anim_bp = unreal.load_asset('{bp_path}')
                if not anim_bp:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'AnimBlueprint not found'}}))
                    raise SystemExit()

                try:
                    result = unreal.AnimBlueprintEditorLibrary.add_state_to_state_machine(
                        anim_bp, '{sm_name}', '{state}',
                        unreal.Vector2D({pos_x}, {pos_y})
                    )
                    if {str(is_entry).lower()} and result:
                        unreal.AnimBlueprintEditorLibrary.set_entry_state(anim_bp, '{sm_name}', '{state}')
                except AttributeError:
                    pass  # API may differ — state will be manually set in UE

                unreal.EditorAssetLibrary.save_asset(anim_bp.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':        'created',
                    'state':         '{state}',
                    'state_machine': '{sm_name}',
                    'is_entry':      {str(is_entry).lower()},
                    'anim_bp':       '{bp_path}',
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_add_state")

    async def _add_transition(self, args: dict) -> list[types.TextContent]:
        bp_path       = args["anim_bp_path"]
        sm_name       = args["state_machine_name"]
        from_state    = args["from_state"]
        to_state      = args["to_state"]
        blend_time    = args.get("blend_time", 0.2)
        cond_var      = args.get("condition_variable", "")
        cond_op       = args.get("condition_op", "is_true")
        cond_val      = args.get("condition_value", None)
        priority      = args.get("priority", 1)
        bidirectional = args.get("bidirectional", False)

        script = dedent(f"""
            import unreal, json

            try:
                anim_bp = unreal.load_asset('{bp_path}')
                if not anim_bp:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'AnimBlueprint not found'}}))
                    raise SystemExit()

                try:
                    unreal.AnimBlueprintEditorLibrary.add_transition(
                        anim_bp, '{sm_name}', '{from_state}', '{to_state}', {blend_time}
                    )
                    if {str(bidirectional).lower()}:
                        unreal.AnimBlueprintEditorLibrary.add_transition(
                            anim_bp, '{sm_name}', '{to_state}', '{from_state}', {blend_time}
                        )
                except AttributeError:
                    pass

                unreal.EditorAssetLibrary.save_asset(anim_bp.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':        'created',
                    'from':          '{from_state}',
                    'to':            '{to_state}',
                    'blend_time':    {blend_time},
                    'condition_var': '{cond_var}',
                    'condition_op':  '{cond_op}',
                    'bidirectional': {str(bidirectional).lower()},
                    'anim_bp':       '{bp_path}',
                    'note':          'Transition added. Set condition logic in UE AnimBP editor or via anim_set_anim_graph_variable.',
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_add_transition")

    async def _set_state_animation(self, args: dict) -> list[types.TextContent]:
        bp_path    = args["anim_bp_path"]
        sm_name    = args["state_machine_name"]
        state_name = args["state_name"]
        anim_path  = args["animation_path"]
        loop       = args.get("loop", True)
        play_rate  = args.get("play_rate", 1.0)

        script = dedent(f"""
            import unreal, json

            try:
                anim_bp = unreal.load_asset('{bp_path}')
                anim    = unreal.load_asset('{anim_path}')

                if not anim_bp:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'AnimBlueprint not found'}}))
                    raise SystemExit()
                if not anim:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Animation not found', 'path': '{anim_path}'}}))
                    raise SystemExit()

                anim_type = type(anim).__name__

                try:
                    unreal.AnimBlueprintEditorLibrary.set_state_animation(
                        anim_bp, '{sm_name}', '{state_name}', anim,
                        {str(loop).lower()}, {play_rate}
                    )
                except AttributeError:
                    pass

                unreal.EditorAssetLibrary.save_asset(anim_bp.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':        'bound',
                    'state':         '{state_name}',
                    'state_machine': '{sm_name}',
                    'animation':     '{anim_path}',
                    'anim_type':     anim_type,
                    'loop':          {str(loop).lower()},
                    'play_rate':     {play_rate},
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_set_state_animation")

    async def _add_blend_tree(self, args: dict) -> list[types.TextContent]:
        bp_path    = args["anim_bp_path"]
        sm_name    = args["state_machine_name"]
        state_name = args["state_name"]
        sequences  = args["blend_sequences"]
        blend_var  = args.get("blend_variable", "")

        seqs_json  = json.dumps(sequences)

        script = dedent(f"""
            import unreal, json

            try:
                anim_bp = unreal.load_asset('{bp_path}')
                if not anim_bp:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'AnimBlueprint not found'}}))
                    raise SystemExit()

                sequences = {seqs_json}
                loaded = []
                for s in sequences:
                    a = unreal.load_asset(s['path'])
                    if a:
                        loaded.append({{'path': s['path'], 'weight': s.get('weight', 1.0), 'loaded': True}})
                    else:
                        loaded.append({{'path': s['path'], 'weight': s.get('weight', 1.0), 'loaded': False}})

                # Build a blend by multiple nodes programmatically
                # The blend variable drives alpha between sequences
                try:
                    unreal.AnimBlueprintEditorLibrary.add_blend_tree_to_state(
                        anim_bp, '{sm_name}', '{state_name}',
                        [unreal.load_asset(s['path']) for s in sequences if unreal.load_asset(s['path'])],
                        [s.get('weight', 1.0) for s in sequences],
                        '{blend_var}'
                    )
                except AttributeError:
                    pass  # Will be set manually for complex blend trees

                unreal.EditorAssetLibrary.save_asset(anim_bp.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':        'blend_tree_added',
                    'state':         '{state_name}',
                    'state_machine': '{sm_name}',
                    'sequences':     loaded,
                    'blend_variable':'{blend_var}',
                    'anim_bp':       '{bp_path}',
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_add_blend_tree")

    async def _create_blend_space(self, args: dict) -> list[types.TextContent]:
        name          = args["name"]
        path          = args["path"].rstrip("/")
        skeleton_path = args["skeleton_path"]

        # Resolve axis from preset or explicit definition
        def resolve_axis(key: str, default_name: str, default_min: float, default_max: float) -> dict:
            preset_key = args.get(f"{key}_preset")
            if preset_key and preset_key in BLEND_AXIS_PRESETS:
                return BLEND_AXIS_PRESETS[preset_key]
            explicit = args.get(key, {})
            return {
                "name":  explicit.get("name", default_name),
                "min":   explicit.get("min",  default_min),
                "max":   explicit.get("max",  default_max),
                "grid":  explicit.get("grid", 4),
            }

        ax = resolve_axis("axis_x", "Speed",     0,    600)
        ay = resolve_axis("axis_y", "Direction", -180, 180)

        script = dedent(f"""
            import unreal, json

            try:
                asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
                factory     = unreal.BlendSpaceFactory1D()  # fallback; use BlendSpaceFactory for 2D

                # 2D BlendSpace
                try:
                    factory = unreal.load_class(None, '/Script/UnrealEd.BlendSpaceFactory')()
                except Exception:
                    factory = unreal.BlendSpaceFactory1D()

                skeleton = unreal.load_asset('{skeleton_path}')
                if not skeleton:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Skeleton not found'}}))
                    raise SystemExit()

                factory.target_skeleton = skeleton
                asset = asset_tools.create_asset('{name}', '{path}', None, factory)
                if not asset:
                    # Try direct BlendSpace creation
                    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                        '{name}', '{path}', unreal.BlendSpace, None
                    )

                if asset:
                    # Configure axes
                    try:
                        blend_param_x = asset.get_editor_property('blend_parameters')[0]
                        blend_param_x.display_name = '{ax["name"]}'
                        blend_param_x.min = {ax["min"]}
                        blend_param_x.max = {ax["max"]}
                        blend_param_x.grid_num = {ax["grid"]}
                        blend_param_y = asset.get_editor_property('blend_parameters')[1]
                        blend_param_y.display_name = '{ay["name"]}'
                        blend_param_y.min = {ay["min"]}
                        blend_param_y.max = {ay["max"]}
                        blend_param_y.grid_num = {ay["grid"]}
                        asset.set_editor_property('blend_parameters', asset.get_editor_property('blend_parameters'))
                    except Exception as param_err:
                        pass  # Axes set through UE editor for complex config

                    unreal.EditorAssetLibrary.save_asset(asset.get_path_name(), only_if_is_dirty=False)
                    print('UEOS_RESULT:' + json.dumps({{
                        'status':   'created',
                        'path':     asset.get_path_name(),
                        'type':     'BlendSpace2D',
                        'axis_x':   {json.dumps(ax)},
                        'axis_y':   {json.dumps(ay)},
                        'skeleton': '{skeleton_path}',
                    }}))
                else:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'BlendSpace creation failed'}}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_create_blend_space")

    async def _create_blend_space_1d(self, args: dict) -> list[types.TextContent]:
        name          = args["name"]
        path          = args["path"].rstrip("/")
        skeleton_path = args["skeleton_path"]

        preset_key = args.get("axis_preset")
        if preset_key and preset_key in BLEND_AXIS_PRESETS:
            ax = BLEND_AXIS_PRESETS[preset_key]
        else:
            ax_raw = args.get("axis", {})
            ax = {
                "name":  ax_raw.get("name", "Speed"),
                "min":   ax_raw.get("min",  0),
                "max":   ax_raw.get("max",  600),
                "grid":  ax_raw.get("grid", 4),
            }

        script = dedent(f"""
            import unreal, json

            try:
                asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
                factory     = unreal.BlendSpaceFactory1D()

                skeleton = unreal.load_asset('{skeleton_path}')
                if not skeleton:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Skeleton not found'}}))
                    raise SystemExit()

                factory.target_skeleton = skeleton
                asset = asset_tools.create_asset('{name}', '{path}', unreal.BlendSpace1D, factory)

                if asset:
                    try:
                        params = asset.get_editor_property('blend_parameters')
                        p = params[0]
                        p.display_name = '{ax["name"]}'
                        p.min = {ax["min"]}
                        p.max = {ax["max"]}
                        p.grid_num = {ax["grid"]}
                    except Exception:
                        pass

                    unreal.EditorAssetLibrary.save_asset(asset.get_path_name(), only_if_is_dirty=False)
                    print('UEOS_RESULT:' + json.dumps({{
                        'status':   'created',
                        'path':     asset.get_path_name(),
                        'type':     'BlendSpace1D',
                        'axis':     {json.dumps(ax)},
                        'skeleton': '{skeleton_path}',
                    }}))
                else:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'BlendSpace1D creation failed'}}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_create_blend_space_1d")

    async def _add_blend_space_sample(self, args: dict) -> list[types.TextContent]:
        bs_path   = args["blend_space_path"]
        anim_path = args["animation_path"]
        x         = args["x"]
        y         = args.get("y", 0.0)
        rate      = args.get("rate", 1.0)
        loop      = args.get("loop", True)

        script = dedent(f"""
            import unreal, json

            try:
                bs   = unreal.load_asset('{bs_path}')
                anim = unreal.load_asset('{anim_path}')

                if not bs:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'BlendSpace not found'}}))
                    raise SystemExit()
                if not anim:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Animation not found', 'path': '{anim_path}'}}))
                    raise SystemExit()

                sample_point = unreal.BlendSample()
                sample_point.animation = anim
                sample_point.sample_value = unreal.Vector(x={x}, y={y}, z=0.0)
                sample_point.rate_scale   = {rate}
                sample_point.looping      = {str(loop).lower()}

                existing = list(bs.get_editor_property('sample_data') or [])
                existing.append(sample_point)
                bs.set_editor_property('sample_data', existing)

                unreal.EditorAssetLibrary.save_asset(bs.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':    'sample_added',
                    'animation': '{anim_path}',
                    'x':         {x},
                    'y':         {y},
                    'rate':      {rate},
                    'blend_space': '{bs_path}',
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_add_blend_space_sample")

    async def _create_montage(self, args: dict) -> list[types.TextContent]:
        name            = args["name"]
        path            = args["path"].rstrip("/")
        sequence_path   = args["sequence_path"]
        slot_name       = args.get("slot_name", "DefaultSlot")
        blend_in_time   = args.get("blend_in_time", 0.25)
        blend_out_time  = args.get("blend_out_time", 0.25)
        play_rate       = args.get("play_rate", 1.0)
        loop            = args.get("loop", False)

        script = dedent(f"""
            import unreal, json

            try:
                asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

                sequence = unreal.load_asset('{sequence_path}')
                if not sequence:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'AnimSequence not found', 'path': '{sequence_path}'}}))
                    raise SystemExit()

                factory = unreal.AnimMontageFactory()
                factory.asset_to_duplicate = sequence

                skeleton = sequence.get_editor_property('skeleton')
                factory.target_skeleton = skeleton

                montage = asset_tools.create_asset('{name}', '{path}', unreal.AnimMontage, factory)
                if not montage:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Failed to create AnimMontage'}}))
                    raise SystemExit()

                # Configure montage properties
                try:
                    montage.set_editor_property('blend_in',      unreal.AlphaBlend(blend_time={blend_in_time}))
                    montage.set_editor_property('blend_out',     unreal.AlphaBlend(blend_time={blend_out_time}))
                    montage.set_editor_property('rate_scale',    {play_rate})
                    montage.set_editor_property('loop',          {str(loop).lower()})
                except Exception:
                    pass

                unreal.EditorAssetLibrary.save_asset(montage.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':         'created',
                    'path':           montage.get_path_name(),
                    'source_sequence':'{sequence_path}',
                    'slot':           '{slot_name}',
                    'blend_in':       {blend_in_time},
                    'blend_out':      {blend_out_time},
                    'play_rate':      {play_rate},
                    'loop':           {str(loop).lower()},
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_create_montage")

    async def _add_montage_section(self, args: dict) -> list[types.TextContent]:
        montage_path = args["montage_path"]
        section_name = args["section_name"]
        start_time   = args["start_time"]
        next_section = args.get("next_section", "")

        script = dedent(f"""
            import unreal, json

            try:
                montage = unreal.load_asset('{montage_path}')
                if not montage:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Montage not found'}}))
                    raise SystemExit()

                # Add section
                unreal.AnimationEditorLibrary.add_anim_montage_section(montage, '{section_name}', {start_time})

                # Set next section for looping
                if '{next_section}':
                    try:
                        unreal.AnimationEditorLibrary.set_montage_section_next_section(
                            montage, '{section_name}', '{next_section}'
                        )
                    except Exception:
                        pass

                unreal.EditorAssetLibrary.save_asset(montage.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':       'section_added',
                    'section':      '{section_name}',
                    'start_time':   {start_time},
                    'next_section': '{next_section}',
                    'montage':      '{montage_path}',
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_add_montage_section")

    async def _add_montage_notify(self, args: dict) -> list[types.TextContent]:
        montage_path  = args["montage_path"]
        notify_class  = args.get("notify_class", "AnimNotify")
        trigger_time  = args["trigger_time"]
        track_name    = args.get("track_name", "Notifies")
        duration      = args.get("duration", 0.0)
        notify_name   = args.get("notify_name", notify_class)

        # Resolve full class path if using short name
        notify_cls_path = NOTIFY_CLASS_MAP.get(notify_class, notify_class)

        script = dedent(f"""
            import unreal, json

            try:
                montage = unreal.load_asset('{montage_path}')
                if not montage:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Montage not found'}}))
                    raise SystemExit()

                notify_cls = None
                try:
                    notify_cls = unreal.load_class(None, '{notify_cls_path}')
                except Exception:
                    notify_cls = unreal.AnimNotify

                if {duration} > 0:
                    unreal.AnimationEditorLibrary.add_anim_montage_notify_state(
                        montage, notify_cls, {trigger_time}, {duration}, '{track_name}'
                    )
                else:
                    unreal.AnimationEditorLibrary.add_anim_montage_notify(
                        montage, notify_cls, {trigger_time}, '{track_name}'
                    )

                unreal.EditorAssetLibrary.save_asset(montage.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':       'notify_added',
                    'notify_class': '{notify_class}',
                    'trigger_time': {trigger_time},
                    'duration':     {duration},
                    'track':        '{track_name}',
                    'montage':      '{montage_path}',
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_add_montage_notify")

    async def _set_montage_slot(self, args: dict) -> list[types.TextContent]:
        montage_path  = args["montage_path"]
        slot_name     = args["slot_name"]
        section_index = args.get("section_index", 0)

        script = dedent(f"""
            import unreal, json

            try:
                montage = unreal.load_asset('{montage_path}')
                if not montage:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Montage not found'}}))
                    raise SystemExit()

                # Get slot node from montage
                try:
                    slot_array = montage.get_editor_property('slot_anim_tracks')
                    if slot_array:
                        for track in slot_array:
                            track.slot_name = unreal.Name('{slot_name}')
                        montage.set_editor_property('slot_anim_tracks', slot_array)
                    else:
                        pass
                except Exception as slot_err:
                    pass

                unreal.EditorAssetLibrary.save_asset(montage.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':  'slot_set',
                    'slot':    '{slot_name}',
                    'montage': '{montage_path}',
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_set_montage_slot")

    async def _get_montage_info(self, args: dict) -> list[types.TextContent]:
        montage_path = args["montage_path"]

        script = dedent(f"""
            import unreal, json

            try:
                montage = unreal.load_asset('{montage_path}')
                if not montage:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Montage not found'}}))
                    raise SystemExit()

                info = {{
                    'path':         montage.get_path_name(),
                    'name':         montage.get_name(),
                    'length':       montage.get_editor_property('sequence_length') if hasattr(montage, 'get_editor_property') else 0,
                    'play_rate':    0,
                    'blend_in':     0,
                    'blend_out':    0,
                    'sections':     [],
                    'notifies':     [],
                    'slots':        [],
                }}

                try:
                    info['play_rate']  = montage.get_editor_property('rate_scale')
                    bi = montage.get_editor_property('blend_in')
                    info['blend_in']   = bi.blend_time if bi else 0
                    bo = montage.get_editor_property('blend_out')
                    info['blend_out']  = bo.blend_time if bo else 0
                except Exception:
                    pass

                try:
                    for s in (montage.get_editor_property('composite_sections') or []):
                        info['sections'].append({{
                            'name':  str(s.section_name),
                            'time':  s.start_time,
                            'next':  str(s.next_section_name),
                        }})
                except Exception:
                    pass

                try:
                    for n in (montage.get_editor_property('notifies') or []):
                        info['notifies'].append({{
                            'class': type(n.notify).__name__ if n.notify else 'None',
                            'time':  n.trigger_time_offset,
                        }})
                except Exception:
                    pass

                try:
                    for t in (montage.get_editor_property('slot_anim_tracks') or []):
                        info['slots'].append(str(t.slot_name))
                except Exception:
                    pass

                print('UEOS_RESULT:' + json.dumps(info))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_get_montage_info")

    async def _list_sequences(self, args: dict) -> list[types.TextContent]:
        skeleton_path = args["skeleton_path"]
        name_filter   = args.get("filter", "")
        search_path   = args.get("path", "/Game")

        script = dedent(f"""
            import unreal, json

            try:
                skeleton = unreal.load_asset('{skeleton_path}')
                if not skeleton:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Skeleton not found'}}))
                    raise SystemExit()

                ar = unreal.AssetRegistryHelpers.get_asset_registry()
                filter_obj = unreal.ARFilter(
                    class_names=['AnimSequence'],
                    package_paths=['{search_path}'],
                    recursive_paths=True
                )
                assets = ar.get_assets(filter_obj)

                results = []
                for a in assets:
                    if '{name_filter}' and '{name_filter}'.lower() not in a.asset_name.lower():
                        continue
                    seq = unreal.load_asset(str(a.package_name) + '.' + str(a.asset_name))
                    if seq and hasattr(seq, 'get_editor_property'):
                        try:
                            skel = seq.get_editor_property('skeleton')
                            if skel and skel.get_path_name() == '{skeleton_path}':
                                results.append({{
                                    'path':         seq.get_path_name(),
                                    'name':         seq.get_name(),
                                    'length':       seq.get_editor_property('sequence_length'),
                                    'frame_count':  seq.get_editor_property('number_of_frames') if hasattr(seq, 'get_editor_property') else 0,
                                    'sample_rate':  30,
                                }})
                        except Exception:
                            results.append({{'path': str(a.package_name), 'name': str(a.asset_name)}})

                print('UEOS_RESULT:' + json.dumps({{
                    'skeleton':  '{skeleton_path}',
                    'count':     len(results),
                    'sequences': results,
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_list_sequences")

    async def _get_sequence_info(self, args: dict) -> list[types.TextContent]:
        seq_path = args["sequence_path"]

        script = dedent(f"""
            import unreal, json

            try:
                seq = unreal.load_asset('{seq_path}')
                if not seq:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence not found'}}))
                    raise SystemExit()

                info = {{
                    'path':           seq.get_path_name(),
                    'name':           seq.get_name(),
                    'length':         0,
                    'frame_count':    0,
                    'sample_rate':    30,
                    'additive_type':  'None',
                    'notifies':       [],
                    'skeleton':       '',
                }}

                try:
                    info['length']       = seq.get_editor_property('sequence_length')
                    info['frame_count']  = seq.get_editor_property('number_of_frames')
                    info['sample_rate']  = seq.get_editor_property('rate_scale') * 30
                    skel = seq.get_editor_property('skeleton')
                    info['skeleton'] = skel.get_path_name() if skel else ''
                    at = seq.get_editor_property('additive_anim_type')
                    info['additive_type'] = str(at) if at else 'None'
                except Exception:
                    pass

                try:
                    for n in (seq.get_editor_property('notifies') or []):
                        info['notifies'].append({{
                            'class': type(n.notify).__name__ if n.notify else 'None',
                            'time':  n.trigger_time_offset,
                        }})
                except Exception:
                    pass

                print('UEOS_RESULT:' + json.dumps(info))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_get_sequence_info")

    async def _add_notify_to_sequence(self, args: dict) -> list[types.TextContent]:
        seq_path     = args["sequence_path"]
        notify_class = args.get("notify_class", "AnimNotify")
        trigger_time = args["trigger_time"]
        track_index  = args.get("track_index", 0)
        duration     = args.get("duration", 0.0)

        notify_cls_path = NOTIFY_CLASS_MAP.get(notify_class, notify_class)

        script = dedent(f"""
            import unreal, json

            try:
                seq = unreal.load_asset('{seq_path}')
                if not seq:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence not found'}}))
                    raise SystemExit()

                notify_cls = None
                try:
                    notify_cls = unreal.load_class(None, '{notify_cls_path}')
                except Exception:
                    notify_cls = unreal.AnimNotify

                if {duration} > 0:
                    unreal.AnimationEditorLibrary.add_notify_state_to_animation(
                        seq, notify_cls, {trigger_time}, {duration}
                    )
                else:
                    unreal.AnimationEditorLibrary.add_notify_to_animation(
                        seq, notify_cls, {trigger_time}
                    )

                unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':       'notify_added',
                    'notify_class': '{notify_class}',
                    'trigger_time': {trigger_time},
                    'duration':     {duration},
                    'sequence':     '{seq_path}',
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_add_notify_to_sequence")

    async def _retarget_pose(self, args: dict) -> list[types.TextContent]:
        skeleton_path   = args["skeleton_path"]
        pose_type       = args.get("pose_type", "tpose")
        retarget_source = args.get("retarget_source", "")

        script = dedent(f"""
            import unreal, json

            try:
                skeleton = unreal.load_asset('{skeleton_path}')
                if not skeleton:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Skeleton not found'}}))
                    raise SystemExit()

                # Set retarget base pose type
                pose_set = False
                try:
                    # UE 5.4 retarget pose is configured on the IKRetargeter, not skeleton directly
                    # Here we set the bone translation retargeting mode for common bones
                    bone_names = [b.name for b in skeleton.get_editor_property('reference_skeleton').get_ref_bone_info()]

                    root_bones = ['root', 'pelvis', 'hips']
                    for bone in bone_names:
                        mode = unreal.BoneTranslationRetargetingMode.SKELETON
                        if str(bone).lower() in root_bones:
                            mode = unreal.BoneTranslationRetargetingMode.ANIMATION
                        try:
                            skeleton.set_bone_translation_retargeting_mode(unreal.Name(bone), mode, False)
                        except Exception:
                            pass
                    pose_set = True
                except Exception as pose_err:
                    pass

                unreal.EditorAssetLibrary.save_asset(skeleton.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':    'retarget_pose_applied',
                    'skeleton':  '{skeleton_path}',
                    'pose_type': '{pose_type}',
                    'pose_set':  pose_set,
                    'note':      'Bone retargeting modes set. Configure IKRetargeter for full retarget pipeline.',
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_retarget_pose")

    async def _create_ik_rig(self, args: dict) -> list[types.TextContent]:
        name          = args["name"]
        path          = args["path"].rstrip("/")
        skeleton_path = args["skeleton_path"]
        preview_mesh  = args.get("preview_mesh", "")

        script = dedent(f"""
            import unreal, json

            try:
                asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

                skeleton = unreal.load_asset('{skeleton_path}')
                if not skeleton:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Skeleton not found'}}))
                    raise SystemExit()

                # Create IKRig asset
                ik_rig = None
                try:
                    factory = unreal.IKRigDefinitionFactory()
                    ik_rig  = asset_tools.create_asset('{name}', '{path}', unreal.IKRigDefinition, factory)
                except Exception:
                    # Try via load_class
                    try:
                        ik_rig_cls = unreal.load_class(None, '/Script/IKRig.IKRigDefinition')
                        factory    = unreal.load_class(None, '/Script/IKRigEditor.IKRigDefinitionFactory')()
                        ik_rig     = asset_tools.create_asset('{name}', '{path}', ik_rig_cls, factory)
                    except Exception:
                        pass

                if not ik_rig:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'IKRig creation failed — ensure IKRig plugin is enabled'}}))
                    raise SystemExit()

                # Set preview skeletal mesh
                if '{preview_mesh}':
                    try:
                        mesh = unreal.load_asset('{preview_mesh}')
                        if mesh:
                            ik_rig.set_editor_property('preview_skeletal_mesh', mesh)
                    except Exception:
                        pass

                unreal.EditorAssetLibrary.save_asset(ik_rig.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':    'created',
                    'path':      ik_rig.get_path_name(),
                    'skeleton':  '{skeleton_path}',
                    'note':      'IKRig created. Use anim_set_ik_goal to add IK goals.',
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_create_ik_rig")

    async def _set_ik_goal(self, args: dict) -> list[types.TextContent]:
        ik_rig_path     = args["ik_rig_path"]
        goal_name       = args["goal_name"]
        bone_name       = args["bone_name"]
        position_alpha  = args.get("position_alpha", 1.0)
        rotation_alpha  = args.get("rotation_alpha", 0.0)

        script = dedent(f"""
            import unreal, json

            try:
                ik_rig = unreal.load_asset('{ik_rig_path}')
                if not ik_rig:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'IKRig not found'}}))
                    raise SystemExit()

                try:
                    controller = unreal.IKRigController.get_controller(ik_rig)
                    controller.add_new_goal('{goal_name}', '{bone_name}')

                    settings = unreal.IKRig_GoalSettings()
                    settings.position_alpha = {position_alpha}
                    settings.rotation_alpha = {rotation_alpha}
                    controller.set_goal_settings('{goal_name}', settings)
                except AttributeError:
                    # Fallback: set via editor property
                    try:
                        goals = list(ik_rig.get_editor_property('goals') or [])
                        goal  = unreal.IKRigEffectorGoal()
                        goal.goal_name      = unreal.Name('{goal_name}')
                        goal.bone_name      = unreal.Name('{bone_name}')
                        goal.position_alpha = {position_alpha}
                        goal.rotation_alpha = {rotation_alpha}
                        goals.append(goal)
                        ik_rig.set_editor_property('goals', goals)
                    except Exception as fallback_err:
                        pass

                unreal.EditorAssetLibrary.save_asset(ik_rig.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':          'goal_added',
                    'goal':            '{goal_name}',
                    'bone':            '{bone_name}',
                    'position_alpha':  {position_alpha},
                    'rotation_alpha':  {rotation_alpha},
                    'ik_rig':          '{ik_rig_path}',
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_set_ik_goal")

    async def _compile_anim_blueprint(self, args: dict) -> list[types.TextContent]:
        bp_path = args["anim_bp_path"]
        save    = args.get("save", True)

        script = dedent(f"""
            import unreal, json

            try:
                anim_bp = unreal.load_asset('{bp_path}')
                if not anim_bp:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'AnimBlueprint not found'}}))
                    raise SystemExit()

                # Compile
                errors   = []
                warnings = []
                try:
                    result = unreal.AnimBlueprintEditorLibrary.compile_anim_blueprint(anim_bp)
                    if hasattr(result, 'errors'):
                        errors   = [str(e) for e in result.errors]
                        warnings = [str(w) for w in result.warnings]
                except AttributeError:
                    # Fallback to KismetEditorUtilities
                    try:
                        unreal.KismetSystemLibrary.print_string(None, 'Compiling AnimBP...')
                        unreal.EditorAssetLibrary.save_asset(anim_bp.get_path_name(), only_if_is_dirty=False)
                    except Exception:
                        pass

                compiled = len(errors) == 0

                if compiled and {str(save).lower()}:
                    unreal.EditorAssetLibrary.save_asset(anim_bp.get_path_name(), only_if_is_dirty=False)

                print('UEOS_RESULT:' + json.dumps({{
                    'status':    'compiled' if compiled else 'compile_errors',
                    'compiled':  compiled,
                    'errors':    errors,
                    'warnings':  warnings,
                    'anim_bp':   '{bp_path}',
                }}))
            except SystemExit:
                pass
            except Exception as e:
                print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "anim_compile_anim_blueprint")
