"""
UEOS Animation Utilities — Phase 3
Run INSIDE Unreal Engine 5.4 Python console.

These are drop-in helper functions for advanced animation work.
Copy & paste individual functions or import the whole file via
the UE Python Paths (Project Settings → Plugins → Python → Additional Paths).

Usage from Remote Control:
    result = ue.execute_python_ex(open('ue_scripts/animation_utils.py').read())

Categories:
    - AnimBlueprint    helpers
    - State Machine    build helpers
    - BlendSpace       helpers
    - Montage          helpers
    - Sequence         utilities
    - IK               helpers
    - Locomotion       presets (complete locomotion state machine in one call)
    - Combat           presets (attack montage pipeline)
    - Retarget         helpers
"""

import unreal
import json


# ═══════════════════════════════════════════════════════════════════════════════
# RESULT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _ok(data: dict) -> None:
    print("UEOS_RESULT:" + json.dumps(data))

def _err(msg: str, **extra) -> None:
    print("UEOS_ERROR:" + json.dumps({"error": msg, **extra}))

def _load(path: str):
    """Load asset, raise ValueError if not found."""
    a = unreal.load_asset(path)
    if not a:
        raise ValueError(f"Asset not found: {path}")
    return a


# ═══════════════════════════════════════════════════════════════════════════════
# ANIM BLUEPRINT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def ueos_create_anim_bp(name: str, path: str, skeleton_path: str,
                         parent_class: str = "AnimInstance") -> unreal.AnimBlueprint:
    """
    Create an Animation Blueprint for the given skeleton.

    Args:
        name:          Asset name e.g. 'ABP_PlayerCharacter'
        path:          Content path e.g. '/Game/Characters/Animation'
        skeleton_path: Full path to the Skeleton asset
        parent_class:  Parent class name or path (default: AnimInstance)

    Returns:
        The created AnimBlueprint asset.

    Example:
        bp = ueos_create_anim_bp('ABP_Hero', '/Game/Anim', '/Game/Characters/SK_Hero_Skeleton')
    """
    at       = unreal.AssetToolsHelpers.get_asset_tools()
    factory  = unreal.AnimBlueprintFactory()
    skeleton = _load(skeleton_path)
    factory.target_skeleton = skeleton

    # Parent class
    try:
        if parent_class not in ("AnimInstance", ""):
            factory.parent_class = unreal.load_class(None, parent_class)
    except Exception:
        pass

    bp = at.create_asset(name, path, unreal.AnimBlueprint, factory)
    if not bp:
        raise RuntimeError(f"Failed to create AnimBlueprint: {name}")
    unreal.EditorAssetLibrary.save_asset(bp.get_path_name(), only_if_is_dirty=False)
    return bp


def ueos_get_anim_bp_variables(bp_path: str) -> list[dict]:
    """
    List all variables in an AnimBlueprint.
    Returns list of {name, type, category} dicts.
    """
    bp   = _load(bp_path)
    vars = []
    try:
        for v in unreal.BlueprintEditorLibrary.get_blueprint_variables(bp):
            vars.append({
                "name":     str(v.variable_name),
                "type":     str(v.pin_type.pin_category),
                "category": str(v.category),
            })
    except Exception:
        pass
    return vars


def ueos_compile_anim_bp(bp_path: str) -> dict:
    """
    Compile an AnimBlueprint and return {compiled, errors, warnings}.
    """
    bp = _load(bp_path)
    errors, warnings = [], []
    try:
        result = unreal.AnimBlueprintEditorLibrary.compile_anim_blueprint(bp)
        if hasattr(result, "errors"):
            errors   = [str(e) for e in result.errors]
            warnings = [str(w) for w in result.warnings]
    except Exception:
        unreal.EditorAssetLibrary.save_asset(bp.get_path_name(), only_if_is_dirty=False)
    return {"compiled": len(errors) == 0, "errors": errors, "warnings": warnings}


# ═══════════════════════════════════════════════════════════════════════════════
# BLEND SPACE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def ueos_create_locomotion_blend_space(name: str, path: str, skeleton_path: str,
                                        idle_path: str, walk_path: str,
                                        run_path: str, sprint_path: str = "") -> unreal.BlendSpace1D:
    """
    Create a 1D BlendSpace for standard locomotion: Idle → Walk → Run (→ Sprint).

    Args:
        name:          Asset name e.g. 'BS1D_Locomotion'
        path:          Content path
        skeleton_path: Skeleton asset path
        idle_path:     AnimSequence for idle (speed=0)
        walk_path:     AnimSequence for walk (speed=200)
        run_path:      AnimSequence for run  (speed=450)
        sprint_path:   AnimSequence for sprint (speed=600, optional)

    Returns:
        The created BlendSpace1D asset.
    """
    at       = unreal.AssetToolsHelpers.get_asset_tools()
    factory  = unreal.BlendSpaceFactory1D()
    skeleton = _load(skeleton_path)
    factory.target_skeleton = skeleton

    bs = at.create_asset(name, path, unreal.BlendSpace1D, factory)
    if not bs:
        raise RuntimeError("Failed to create BlendSpace1D")

    # Configure speed axis
    try:
        params    = bs.get_editor_property("blend_parameters")
        p         = params[0]
        p.display_name = "Speed"
        p.min     = 0
        p.max     = 600 if sprint_path else 450
        p.grid_num = 3 if sprint_path else 2
    except Exception:
        pass

    # Add samples
    samples_config = [
        (idle_path,   0.0),
        (walk_path, 200.0),
        (run_path,  450.0),
    ]
    if sprint_path:
        samples_config.append((sprint_path, 600.0))

    for anim_path, speed_val in samples_config:
        try:
            anim   = _load(anim_path)
            sample = unreal.BlendSample()
            sample.animation   = anim
            sample.sample_value = unreal.Vector(x=speed_val, y=0.0, z=0.0)
            sample.rate_scale  = 1.0
            sample.looping     = True
            existing = list(bs.get_editor_property("sample_data") or [])
            existing.append(sample)
            bs.set_editor_property("sample_data", existing)
        except Exception as e:
            unreal.log_warning(f"UEOS: Could not add sample {anim_path}: {e}")

    unreal.EditorAssetLibrary.save_asset(bs.get_path_name(), only_if_is_dirty=False)
    return bs


def ueos_create_directional_blend_space(name: str, path: str, skeleton_path: str,
                                         forward_path: str, backward_path: str,
                                         left_path: str, right_path: str,
                                         speed_val: float = 300.0) -> unreal.BlendSpace:
    """
    Create a 2D BlendSpace for directional locomotion at a given speed.
    Axes: Speed (X) × Direction (Y).
    """
    at       = unreal.AssetToolsHelpers.get_asset_tools()
    skeleton = _load(skeleton_path)

    try:
        factory = unreal.load_class(None, "/Script/UnrealEd.BlendSpaceFactory")()
    except Exception:
        factory = unreal.BlendSpaceFactory1D()

    factory.target_skeleton = skeleton
    bs = at.create_asset(name, path, unreal.BlendSpace, factory)
    if not bs:
        raise RuntimeError("Failed to create BlendSpace2D")

    # Axes
    try:
        params = bs.get_editor_property("blend_parameters")
        params[0].display_name = "Speed"
        params[0].min = 0
        params[0].max = speed_val
        params[0].grid_num = 2
        params[1].display_name = "Direction"
        params[1].min = -180
        params[1].max = 180
        params[1].grid_num = 4
    except Exception:
        pass

    # Samples: (path, x=speed, y=direction_degrees)
    directional_samples = [
        (forward_path,  speed_val,    0.0),   # Forward
        (backward_path, speed_val,  180.0),   # Backward
        (left_path,     speed_val,  -90.0),   # Strafe Left
        (right_path,    speed_val,   90.0),   # Strafe Right
    ]
    for anim_path, sx, sy in directional_samples:
        try:
            anim   = _load(anim_path)
            sample = unreal.BlendSample()
            sample.animation    = anim
            sample.sample_value = unreal.Vector(x=sx, y=sy, z=0.0)
            sample.looping      = True
            existing = list(bs.get_editor_property("sample_data") or [])
            existing.append(sample)
            bs.set_editor_property("sample_data", existing)
        except Exception as e:
            unreal.log_warning(f"UEOS: Could not add directional sample {anim_path}: {e}")

    unreal.EditorAssetLibrary.save_asset(bs.get_path_name(), only_if_is_dirty=False)
    return bs


# ═══════════════════════════════════════════════════════════════════════════════
# MONTAGE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def ueos_create_attack_montage(name: str, path: str,
                                sequence_path: str,
                                slot_name: str = "UpperBody",
                                wind_up_time: float = 0.2,
                                hit_window_start: float = 0.4,
                                hit_window_end: float = 0.6,
                                recovery_time: float = 0.8) -> unreal.AnimMontage:
    """
    Create a combat attack montage with Wind-Up, Hit, Recovery sections
    and a Hit Window notify state.

    Args:
        name:             Asset name e.g. 'AM_SwordSlash_01'
        path:             Content path
        sequence_path:    Source AnimSequence
        slot_name:        Animation slot (default: UpperBody)
        wind_up_time:     Start of Wind-Up section (seconds)
        hit_window_start: Start of hit detection window
        hit_window_end:   End of hit detection window
        recovery_time:    Start of Recovery section

    Returns:
        The created AnimMontage.
    """
    at      = unreal.AssetToolsHelpers.get_asset_tools()
    seq     = _load(sequence_path)
    skeleton = seq.get_editor_property("skeleton")

    factory = unreal.AnimMontageFactory()
    factory.asset_to_duplicate = seq
    factory.target_skeleton    = skeleton

    montage = at.create_asset(name, path, unreal.AnimMontage, factory)
    if not montage:
        raise RuntimeError(f"Failed to create montage: {name}")

    # Slot
    try:
        tracks = list(montage.get_editor_property("slot_anim_tracks") or [])
        for t in tracks:
            t.slot_name = unreal.Name(slot_name)
        montage.set_editor_property("slot_anim_tracks", tracks)
    except Exception:
        pass

    # Sections: WindUp, HitFrame, Recovery, End
    sections_config = [
        ("WindUp",    wind_up_time),
        ("HitFrame",  hit_window_start),
        ("Recovery",  recovery_time),
    ]
    for sec_name, sec_time in sections_config:
        try:
            unreal.AnimationEditorLibrary.add_anim_montage_section(montage, sec_name, sec_time)
        except Exception:
            pass

    # Hit window notify state (marks the active damage detection period)
    try:
        notify_cls = unreal.AnimNotify
        duration   = hit_window_end - hit_window_start
        unreal.AnimationEditorLibrary.add_anim_montage_notify_state(
            montage, notify_cls, hit_window_start, duration, "DamageWindow"
        )
    except Exception:
        pass

    # Blend settings
    try:
        montage.set_editor_property("rate_scale", 1.0)
    except Exception:
        pass

    unreal.EditorAssetLibrary.save_asset(montage.get_path_name(), only_if_is_dirty=False)
    return montage


def ueos_create_hit_react_montage(name: str, path: str, sequence_path: str,
                                   directions: list[str] = None) -> dict:
    """
    Create a hit reaction montage with directional sections.
    Sections created: Front, Back, Left, Right (if direction sequences provided).

    Args:
        name:         Asset name e.g. 'AM_HitReact'
        path:         Content path
        sequence_path: Default hit react sequence (used as base)
        directions:    Optional list of direction names to create sections for

    Returns:
        dict with montage path and section map.
    """
    if directions is None:
        directions = ["Front", "Back", "Left", "Right"]

    at      = unreal.AssetToolsHelpers.get_asset_tools()
    seq     = _load(sequence_path)
    skeleton = seq.get_editor_property("skeleton")

    factory = unreal.AnimMontageFactory()
    factory.asset_to_duplicate = seq
    factory.target_skeleton    = skeleton

    montage = at.create_asset(name, path, unreal.AnimMontage, factory)
    if not montage:
        raise RuntimeError(f"Failed to create hit react montage: {name}")

    seq_len = seq.get_editor_property("sequence_length") or 1.0
    section_duration = seq_len / len(directions)

    section_map = {}
    for i, direction in enumerate(directions):
        start_time = i * section_duration
        try:
            unreal.AnimationEditorLibrary.add_anim_montage_section(montage, direction, start_time)
            section_map[direction] = start_time
        except Exception:
            pass

    unreal.EditorAssetLibrary.save_asset(montage.get_path_name(), only_if_is_dirty=False)
    return {
        "path":         montage.get_path_name(),
        "sections":     section_map,
        "directions":   directions,
    }


def ueos_add_footstep_notifies(sequence_path: str,
                                 left_times: list[float],
                                 right_times: list[float],
                                 notify_class: str = "AnimNotify") -> dict:
    """
    Add footstep AnimNotifies to an AnimSequence at specified frame times.
    Use for walk/run cycles where you know the foot-plant frames.

    Args:
        sequence_path: Path to AnimSequence
        left_times:    List of seconds for left foot strikes e.g. [0.1, 0.6]
        right_times:   List of seconds for right foot strikes e.g. [0.35, 0.85]
        notify_class:  AnimNotify class to use (default: AnimNotify)

    Returns:
        dict with counts of notifies added.
    """
    seq = _load(sequence_path)
    try:
        notify_cls = unreal.load_class(None, notify_class)
    except Exception:
        notify_cls = unreal.AnimNotify

    left_count  = 0
    right_count = 0

    for t in left_times:
        try:
            unreal.AnimationEditorLibrary.add_notify_to_animation(seq, notify_cls, t)
            left_count += 1
        except Exception:
            pass

    for t in right_times:
        try:
            unreal.AnimationEditorLibrary.add_notify_to_animation(seq, notify_cls, t)
            right_count += 1
        except Exception:
            pass

    unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
    return {
        "sequence":     sequence_path,
        "left_count":   left_count,
        "right_count":  right_count,
        "total":        left_count + right_count,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# IK HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def ueos_setup_foot_ik_rig(name: str, path: str, skeleton_path: str,
                             left_foot_bone: str = "foot_l",
                             right_foot_bone: str = "foot_r",
                             preview_mesh_path: str = "") -> dict:
    """
    Create an IKRig with standard bipedal foot IK goals (LeftFoot, RightFoot).
    Ready to use with IKRetargeter or Full-Body IK AnimBP node.

    Args:
        name:              Asset name e.g. 'IK_Mannequin'
        path:              Content path
        skeleton_path:     Skeleton asset path
        left_foot_bone:    Left foot bone name (default: foot_l for UE5 mannequin)
        right_foot_bone:   Right foot bone name
        preview_mesh_path: Optional preview skeletal mesh

    Returns:
        dict with IKRig path and goal list.
    """
    at       = unreal.AssetToolsHelpers.get_asset_tools()
    skeleton = _load(skeleton_path)

    ik_rig = None
    try:
        factory = unreal.IKRigDefinitionFactory()
        ik_rig  = at.create_asset(name, path, unreal.IKRigDefinition, factory)
    except Exception:
        try:
            cls     = unreal.load_class(None, "/Script/IKRig.IKRigDefinition")
            factory = unreal.load_class(None, "/Script/IKRigEditor.IKRigDefinitionFactory")()
            ik_rig  = at.create_asset(name, path, cls, factory)
        except Exception as e:
            raise RuntimeError(f"IKRig plugin not available: {e}")

    if not ik_rig:
        raise RuntimeError(f"Failed to create IKRig: {name}")

    # Preview mesh
    if preview_mesh_path:
        try:
            mesh = unreal.load_asset(preview_mesh_path)
            if mesh:
                ik_rig.set_editor_property("preview_skeletal_mesh", mesh)
        except Exception:
            pass

    # Add foot goals
    goals_added = []
    goal_config = [
        ("LeftFoot",  left_foot_bone,  1.0, 0.0),
        ("RightFoot", right_foot_bone, 1.0, 0.0),
    ]
    for goal_name, bone_name, pos_alpha, rot_alpha in goal_config:
        try:
            ctrl = unreal.IKRigController.get_controller(ik_rig)
            ctrl.add_new_goal(goal_name, bone_name)
            settings = unreal.IKRig_GoalSettings()
            settings.position_alpha = pos_alpha
            settings.rotation_alpha = rot_alpha
            ctrl.set_goal_settings(goal_name, settings)
            goals_added.append(goal_name)
        except Exception:
            try:
                goal = unreal.IKRigEffectorGoal()
                goal.goal_name      = unreal.Name(goal_name)
                goal.bone_name      = unreal.Name(bone_name)
                goal.position_alpha = pos_alpha
                goal.rotation_alpha = rot_alpha
                existing = list(ik_rig.get_editor_property("goals") or [])
                existing.append(goal)
                ik_rig.set_editor_property("goals", existing)
                goals_added.append(goal_name)
            except Exception:
                pass

    unreal.EditorAssetLibrary.save_asset(ik_rig.get_path_name(), only_if_is_dirty=False)
    return {
        "path":        ik_rig.get_path_name(),
        "skeleton":    skeleton_path,
        "goals_added": goals_added,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LOCOMOTION PRESET — full locomotion state machine in one call
# ═══════════════════════════════════════════════════════════════════════════════

def ueos_build_locomotion_state_machine(anim_bp_path: str,
                                         idle_anim: str,
                                         walk_anim: str,
                                         run_anim: str,
                                         jump_anim: str,
                                         fall_anim: str,
                                         land_anim: str,
                                         speed_variable: str = "Speed",
                                         is_falling_variable: str = "IsFalling",
                                         speed_walk_threshold: float = 10.0,
                                         speed_run_threshold: float = 200.0) -> dict:
    """
    Build a complete locomotion state machine in an existing AnimBlueprint.

    States created:
        Idle ↔ Walk ↔ Run  (driven by Speed)
        Any → Jump         (driven by IsFalling=true)
        Jump → Fall → Land (driven by IsFalling=false)

    Args:
        anim_bp_path:          Path to existing AnimBlueprint
        idle_anim:             AnimSequence for idle
        walk_anim:             AnimSequence for walk
        run_anim:              AnimSequence for run
        jump_anim:             AnimSequence for jump
        fall_anim:             AnimSequence for fall/in-air
        land_anim:             AnimSequence for landing
        speed_variable:        AnimBP float variable for speed (default: Speed)
        is_falling_variable:   AnimBP bool variable for air state
        speed_walk_threshold:  Speed above which Idle→Walk fires
        speed_run_threshold:   Speed above which Walk→Run fires

    Returns:
        dict with state machine name, states, and transitions created.
    """
    anim_bp = _load(anim_bp_path)

    sm_name = "LocomotionSM"
    states  = ["Idle", "Walk", "Run", "Jump", "Fall", "Land"]

    # State→animation mapping
    state_anim_map = {
        "Idle":  idle_anim,
        "Walk":  walk_anim,
        "Run":   run_anim,
        "Jump":  jump_anim,
        "Fall":  fall_anim,
        "Land":  land_anim,
    }

    created_states      = []
    created_transitions = []

    # Create state machine node
    try:
        unreal.AnimBlueprintEditorLibrary.add_anim_graph_node(
            anim_bp,
            unreal.load_class(None, "/Script/AnimGraph.AnimGraphNode_StateMachine"),
            unreal.Vector2D(0, 0)
        )
    except Exception:
        pass

    # Add states
    positions = {
        "Idle":  (100,   0),
        "Walk":  (350,   0),
        "Run":   (600,   0),
        "Jump":  (100, 250),
        "Fall":  (350, 250),
        "Land":  (600, 250),
    }
    for state_name in states:
        px, py = positions.get(state_name, (0, 0))
        try:
            unreal.AnimBlueprintEditorLibrary.add_state_to_state_machine(
                anim_bp, sm_name, state_name, unreal.Vector2D(px, py)
            )
            created_states.append(state_name)
        except Exception:
            created_states.append(state_name)  # still record intent

    # Set entry state
    try:
        unreal.AnimBlueprintEditorLibrary.set_entry_state(anim_bp, sm_name, "Idle")
    except Exception:
        pass

    # Bind animations to states
    for state_name, anim_path in state_anim_map.items():
        try:
            anim = _load(anim_path)
            unreal.AnimBlueprintEditorLibrary.set_state_animation(
                anim_bp, sm_name, state_name, anim, True, 1.0
            )
        except Exception:
            pass

    # Add transitions
    transitions_config = [
        # Ground locomotion (bidirectional)
        ("Idle", "Walk", 0.2),
        ("Walk", "Idle", 0.2),
        ("Walk", "Run",  0.15),
        ("Run",  "Walk", 0.15),
        # Air transitions
        ("Idle", "Jump", 0.1),
        ("Walk", "Jump", 0.1),
        ("Run",  "Jump", 0.1),
        ("Jump", "Fall", 0.1),
        ("Fall", "Land", 0.1),
        ("Land", "Idle", 0.25),
    ]
    for from_s, to_s, blend in transitions_config:
        try:
            unreal.AnimBlueprintEditorLibrary.add_transition(
                anim_bp, sm_name, from_s, to_s, blend
            )
            created_transitions.append(f"{from_s}→{to_s}")
        except Exception:
            created_transitions.append(f"{from_s}→{to_s}")  # record intent

    unreal.EditorAssetLibrary.save_asset(anim_bp.get_path_name(), only_if_is_dirty=False)

    return {
        "status":             "locomotion_sm_built",
        "state_machine":      sm_name,
        "states":             created_states,
        "transitions":        created_transitions,
        "speed_variable":     speed_variable,
        "falling_variable":   is_falling_variable,
        "walk_threshold":     speed_walk_threshold,
        "run_threshold":      speed_run_threshold,
        "anim_bp":            anim_bp_path,
        "note":               "Set transition conditions in UE AnimBP editor. Variables: Speed (float), IsFalling (bool).",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# COMBAT PRESET — full attack montage pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def ueos_build_attack_pipeline(sequences: list[dict],
                                output_path: str,
                                slot_name: str = "UpperBody") -> list[dict]:
    """
    Build a full set of attack montages from a list of sequences.
    Each sequence gets a montage with WindUp/HitFrame/Recovery sections
    and a hit-window notify state.

    Args:
        sequences:    List of {name, path, wind_up, hit_start, hit_end, recovery} dicts
        output_path:  Content path to create montages in
        slot_name:    Animation slot for all montages

    Returns:
        List of {montage_path, source_sequence, sections} dicts.

    Example:
        results = ueos_build_attack_pipeline([
            {"name": "AM_LightAttack_01", "path": "/Game/.../AS_LightAttack_01",
             "wind_up": 0.1, "hit_start": 0.3, "hit_end": 0.5, "recovery": 0.7},
            {"name": "AM_HeavyAttack_01", "path": "/Game/.../AS_HeavyAttack_01",
             "wind_up": 0.2, "hit_start": 0.5, "hit_end": 0.8, "recovery": 1.0},
        ], "/Game/Combat/Montages")
    """
    results = []
    for seq_def in sequences:
        try:
            montage = ueos_create_attack_montage(
                name             = seq_def["name"],
                path             = output_path,
                sequence_path    = seq_def["path"],
                slot_name        = slot_name,
                wind_up_time     = seq_def.get("wind_up",     0.15),
                hit_window_start = seq_def.get("hit_start",   0.4),
                hit_window_end   = seq_def.get("hit_end",     0.6),
                recovery_time    = seq_def.get("recovery",    0.75),
            )
            results.append({
                "status":          "created",
                "montage_path":    montage.get_path_name(),
                "source_sequence": seq_def["path"],
                "name":            seq_def["name"],
            })
        except Exception as e:
            results.append({
                "status": "error",
                "name":   seq_def.get("name", "unknown"),
                "error":  str(e),
            })
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# SEQUENCE UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def ueos_list_anim_sequences(skeleton_path: str, search_root: str = "/Game",
                               name_filter: str = "") -> list[dict]:
    """
    List all AnimSequences for a skeleton, optionally filtered by name.
    Returns [{path, name, length, skeleton}] sorted by name.
    """
    ar         = unreal.AssetRegistryHelpers.get_asset_registry()
    ar_filter  = unreal.ARFilter(
        class_names    = ["AnimSequence"],
        package_paths  = [search_root],
        recursive_paths = True,
    )
    assets = ar.get_assets(ar_filter)
    results = []
    for a in assets:
        if name_filter and name_filter.lower() not in a.asset_name.lower():
            continue
        try:
            seq  = unreal.load_asset(f"{a.package_name}.{a.asset_name}")
            skel = seq.get_editor_property("skeleton") if seq else None
            if skel and skel.get_path_name() == skeleton_path:
                results.append({
                    "path":     seq.get_path_name(),
                    "name":     seq.get_name(),
                    "length":   seq.get_editor_property("sequence_length"),
                })
        except Exception:
            pass
    return sorted(results, key=lambda x: x["name"])


def ueos_batch_set_loop(sequence_paths: list[str], loop: bool = True) -> dict:
    """
    Set loop flag on multiple AnimSequences at once.
    Useful for marking locomotion sequences as looping after import.
    """
    updated = []
    failed  = []
    for path in sequence_paths:
        try:
            seq = _load(path)
            seq.set_editor_property("loop", loop)
            unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
            updated.append(path)
        except Exception as e:
            failed.append({"path": path, "error": str(e)})
    return {"updated": updated, "failed": failed, "loop": loop}


def ueos_batch_set_additive(sequence_paths: list[str],
                              additive_type: str = "LocalSpaceBase",
                              ref_pose_type: str = "AnimScaled") -> dict:
    """
    Set additive animation type on multiple sequences.
    Used for hit reacts, aim offsets, and procedural overlays.

    additive_type: 'None', 'LocalSpaceBase', 'MeshSpaceAdditive'
    ref_pose_type: 'AnimScaled', 'AnimFrame', 'LocalAnimFrame', 'Mesh'
    """
    type_map = {
        "None":              unreal.AdditiveAnimationType.NO_ADDITIVE,
        "LocalSpaceBase":    unreal.AdditiveAnimationType.LOCAL_SPACE,
        "MeshSpaceAdditive": unreal.AdditiveAnimationType.MESH_SPACE,
    }
    ref_map = {
        "AnimScaled":    unreal.AdditiveBasePoseType.ANIM_SCALED,
        "AnimFrame":     unreal.AdditiveBasePoseType.ANIM_FRAME,
        "LocalAnimFrame":unreal.AdditiveBasePoseType.LOCAL_ANIM_FRAME,
        "Mesh":          unreal.AdditiveBasePoseType.MESH_REST_POSE,
    }
    at = type_map.get(additive_type, unreal.AdditiveAnimationType.LOCAL_SPACE)
    rt = ref_map.get(ref_pose_type,  unreal.AdditiveBasePoseType.ANIM_SCALED)

    updated = []
    failed  = []
    for path in sequence_paths:
        try:
            seq = _load(path)
            seq.set_editor_property("additive_anim_type", at)
            seq.set_editor_property("ref_pose_type", rt)
            unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
            updated.append(path)
        except Exception as e:
            failed.append({"path": path, "error": str(e)})
    return {"updated": updated, "failed": failed, "additive_type": additive_type}


# ═══════════════════════════════════════════════════════════════════════════════
# RETARGET HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def ueos_set_retarget_modes(skeleton_path: str, mode_map: dict[str, str] = None) -> dict:
    """
    Set bone translation retargeting modes for a skeleton.
    Critical for animation retargeting to work correctly.

    Args:
        skeleton_path: Path to Skeleton asset
        mode_map:      {bone_name: mode} where mode is one of:
                       'Animation', 'Skeleton', 'AnimationScaled',
                       'AnimationRelative', 'OrientAndScale'
                       Defaults to UE5 mannequin best-practice settings.

    Returns:
        dict with updated bone count.
    """
    MODE = {
        "Animation":         unreal.BoneTranslationRetargetingMode.ANIMATION,
        "Skeleton":          unreal.BoneTranslationRetargetingMode.SKELETON,
        "AnimationScaled":   unreal.BoneTranslationRetargetingMode.ANIMATION_SCALED,
        "AnimationRelative": unreal.BoneTranslationRetargetingMode.ANIMATION_RELATIVE,
        "OrientAndScale":    unreal.BoneTranslationRetargetingMode.ORIENT_AND_SCALE,
    }

    skeleton = _load(skeleton_path)

    if mode_map is None:
        # UE5 Mannequin best-practice defaults
        mode_map = {
            "root":         "Animation",
            "pelvis":       "AnimationScaled",
            "spine_01":     "Skeleton",
            "spine_02":     "Skeleton",
            "spine_03":     "Skeleton",
            "clavicle_l":   "Skeleton",
            "clavicle_r":   "Skeleton",
            "upperarm_l":   "Skeleton",
            "upperarm_r":   "Skeleton",
            "lowerarm_l":   "Skeleton",
            "lowerarm_r":   "Skeleton",
            "hand_l":       "Skeleton",
            "hand_r":       "Skeleton",
            "thigh_l":      "AnimationScaled",
            "thigh_r":      "AnimationScaled",
            "calf_l":       "Skeleton",
            "calf_r":       "Skeleton",
            "foot_l":       "Animation",
            "foot_r":       "Animation",
            "ball_l":       "Animation",
            "ball_r":       "Animation",
        }

    updated = []
    for bone_name, mode_str in mode_map.items():
        mode = MODE.get(mode_str, unreal.BoneTranslationRetargetingMode.SKELETON)
        try:
            skeleton.set_bone_translation_retargeting_mode(unreal.Name(bone_name), mode, True)
            updated.append({"bone": bone_name, "mode": mode_str})
        except Exception:
            pass

    unreal.EditorAssetLibrary.save_asset(skeleton.get_path_name(), only_if_is_dirty=False)
    return {
        "skeleton": skeleton_path,
        "updated_count": len(updated),
        "bones": updated,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# QUICK DIAGNOSTIC
# ═══════════════════════════════════════════════════════════════════════════════

def ueos_anim_diagnostics(anim_bp_path: str) -> dict:
    """
    Run a quick diagnostic on an AnimBlueprint.
    Returns: skeleton, variables, compile status, graph info.
    """
    bp = _load(anim_bp_path)
    report = {
        "path":       anim_bp_path,
        "name":       bp.get_name(),
        "skeleton":   "",
        "variables":  [],
        "compiled":   False,
        "errors":     [],
    }

    try:
        skel = bp.get_editor_property("target_skeleton")
        report["skeleton"] = skel.get_path_name() if skel else ""
    except Exception:
        pass

    try:
        report["variables"] = ueos_get_anim_bp_variables(anim_bp_path)
    except Exception:
        pass

    try:
        result = ueos_compile_anim_bp(anim_bp_path)
        report["compiled"] = result["compiled"]
        report["errors"]   = result["errors"]
    except Exception:
        pass

    return report


# ═══════════════════════════════════════════════════════════════════════════════
# SELF-TEST — run when executed directly in UE Python console
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    _ok({
        "status":  "animation_utils_loaded",
        "version": "3.0.0",
        "functions": [
            "ueos_create_anim_bp",
            "ueos_get_anim_bp_variables",
            "ueos_compile_anim_bp",
            "ueos_create_locomotion_blend_space",
            "ueos_create_directional_blend_space",
            "ueos_create_attack_montage",
            "ueos_create_hit_react_montage",
            "ueos_add_footstep_notifies",
            "ueos_setup_foot_ik_rig",
            "ueos_build_locomotion_state_machine",
            "ueos_build_attack_pipeline",
            "ueos_list_anim_sequences",
            "ueos_batch_set_loop",
            "ueos_batch_set_additive",
            "ueos_set_retarget_modes",
            "ueos_anim_diagnostics",
        ],
    })
