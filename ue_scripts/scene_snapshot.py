"""
UEOS Utility Script — Scene Snapshot
Runs INSIDE Unreal Engine 5.4 via Remote Control execute_python.

Captures a complete snapshot of the current level:
  - All actors with transforms, components, tags
  - All lights with properties
  - PostProcessVolume settings
  - Sky/fog settings
  - World settings

Output: UEOS_RESULT: with full scene JSON
Can also save snapshot to disk (UEOS_SNAPSHOT_PATH).

Usage:
    UEOS_SNAPSHOT_PATH = "C:/UEOS/snapshots/level_snapshot.json"
    exec(open(r"C:/UEOS/ue_scripts/scene_snapshot.py").read())
"""

import unreal, json, os

SNAPSHOT_PATH = globals().get("UEOS_SNAPSHOT_PATH", "")
INCLUDE_COMPS  = globals().get("UEOS_INCLUDE_COMPONENTS", True)
INCLUDE_LIGHTS = globals().get("UEOS_INCLUDE_LIGHTS", True)
MAX_ACTORS     = globals().get("UEOS_MAX_ACTORS", 1000)

try:
    world   = unreal.EditorLevelLibrary.get_editor_world()
    actors  = unreal.EditorLevelLibrary.get_all_level_actors()
    snapshot = {
        "level_name": world.get_name(),
        "actor_count": len(actors),
        "actors":  [],
        "lights":  [],
        "ppv":     [],
        "cameras": [],
        "sky":     None,
        "fog":     None
    }

    light_classes = (
        unreal.PointLight, unreal.SpotLight,
        unreal.DirectionalLight, unreal.RectLight, unreal.SkyLight
    )

    for i, actor in enumerate(actors[:MAX_ACTORS]):
        loc   = actor.get_actor_location()
        rot   = actor.get_actor_rotation()
        scale = actor.get_actor_scale3d()

        entry = {
            "label":    actor.get_actor_label(),
            "class":    actor.get_class().get_name(),
            "location": [round(loc.x,2), round(loc.y,2), round(loc.z,2)],
            "rotation": [round(rot.pitch,2), round(rot.yaw,2), round(rot.roll,2)],
            "scale":    [round(scale.x,2), round(scale.y,2), round(scale.z,2)],
            "hidden":   actor.is_hidden_editor(),
            "tags":     [str(t) for t in actor.tags],
        }

        if INCLUDE_COMPS:
            comps = actor.get_components_by_class(unreal.ActorComponent)
            entry["components"] = [c.get_class().get_name() for c in comps]

        # Categorise
        if isinstance(actor, light_classes) and INCLUDE_LIGHTS:
            snapshot["lights"].append(entry)
        elif isinstance(actor, unreal.PostProcessVolume):
            snapshot["ppv"].append({
                "label":    actor.get_actor_label(),
                "infinite": actor.unbound,
                "priority": actor.priority,
                "enabled":  actor.is_actor_tick_enabled()
            })
        elif isinstance(actor, unreal.CameraActor):
            cam_comp = actor.get_component_by_class(unreal.CameraComponent)
            fov = cam_comp.field_of_view if cam_comp else 90
            snapshot["cameras"].append({**entry, "fov": fov})
        elif isinstance(actor, unreal.SkyAtmosphere):
            snapshot["sky"] = entry
        elif isinstance(actor, unreal.ExponentialHeightFog):
            snapshot["fog"] = entry
        else:
            snapshot["actors"].append(entry)

    # World settings
    ws = world.get_world_settings()
    snapshot["world_settings"] = {
        "gravity_z":          ws.global_gravity_z,
        "default_gravity_z":  ws.default_gravity_z,
        "kill_z":             ws.kill_z,
        "paused":             ws.paused_with_bots,
    }

    if SNAPSHOT_PATH:
        os.makedirs(os.path.dirname(SNAPSHOT_PATH) or ".", exist_ok=True)
        with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
        snapshot["saved_to"] = SNAPSHOT_PATH

    print("UEOS_RESULT:" + json.dumps(snapshot))

except Exception as ex:
    import traceback
    print("UEOS_ERROR:" + traceback.format_exc().replace("\n", " | "))
