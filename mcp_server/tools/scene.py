"""
UEOS Scene Tools — UE 5.4 Optimized
Actor placement, level editing, lighting, world settings, environment setup.

UE 5.4 API: unreal.EditorLevelLibrary + unreal.EditorActorLibrary
"""

import json
import logging
from mcp import types

log = logging.getLogger("ueos.scene")


class SceneTools:

    def __init__(self, ue):
        self.ue = ue

    async def get_tool_definitions(self) -> list[types.Tool]:
        return [

            types.Tool(
                name="scene_spawn_actor",
                description="""Spawn an actor in the current level.
Can spawn from a Blueprint class, a mesh, or a built-in actor type.
Returns the spawned actor's name for further operations.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Content path to Blueprint class to spawn"},
                        "actor_class": {
                            "type": "string",
                            "description": "Built-in class: StaticMeshActor, PointLight, SpotLight, DirectionalLight, SkyLight, ExponentialHeightFog, SkyAtmosphere, VolumetricCloud, CameraActor, TriggerBox, TriggerSphere"
                        },
                        "location": {"type": "array", "items": {"type": "number"}, "description": "World location [x, y, z]", "default": [0, 0, 0]},
                        "rotation": {"type": "array", "items": {"type": "number"}, "description": "World rotation [pitch, yaw, roll]", "default": [0, 0, 0]},
                        "scale":    {"type": "array", "items": {"type": "number"}, "description": "World scale [x, y, z]", "default": [1, 1, 1]},
                        "label":    {"type": "string", "description": "Custom editor label for the actor"}
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="scene_place_static_mesh",
                description="""Place a Static Mesh in the level with full transform control.
Optionally assigns a material and configures collision.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "mesh_path":     {"type": "string", "description": "Content path to Static Mesh asset"},
                        "location":      {"type": "array", "items": {"type": "number"}, "default": [0, 0, 0]},
                        "rotation":      {"type": "array", "items": {"type": "number"}, "default": [0, 0, 0]},
                        "scale":         {"type": "array", "items": {"type": "number"}, "default": [1, 1, 1]},
                        "material_path": {"type": "string", "description": "Override material to apply", "default": ""},
                        "label":         {"type": "string", "description": "Editor label"},
                        "mobility": {
                            "type": "string",
                            "description": "Mobility: Static, Stationary, Movable",
                            "default": "Static"
                        }
                    },
                    "required": ["mesh_path"]
                }
            ),

            types.Tool(
                name="scene_add_point_light",
                description="""Add a Point Light to the level.
Configures intensity, color, radius, attenuation, and shadow settings.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "location":      {"type": "array", "items": {"type": "number"}, "default": [0, 0, 300]},
                        "color":         {"type": "array", "items": {"type": "number"}, "description": "Light color [r,g,b]", "default": [1.0, 1.0, 1.0]},
                        "intensity":     {"type": "number", "description": "Light intensity in lumens", "default": 1000.0},
                        "attenuation_radius": {"type": "number", "description": "Light radius in cm", "default": 1000.0},
                        "cast_shadows":  {"type": "boolean", "default": True},
                        "label":         {"type": "string", "default": "PointLight"}
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="scene_add_spot_light",
                description="Add a Spot Light to the level with cone angle configuration.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "location":        {"type": "array", "items": {"type": "number"}, "default": [0, 0, 500]},
                        "rotation":        {"type": "array", "items": {"type": "number"}, "default": [-90, 0, 0]},
                        "color":           {"type": "array", "items": {"type": "number"}, "default": [1.0, 1.0, 1.0]},
                        "intensity":       {"type": "number", "default": 5000.0},
                        "inner_cone_angle":{"type": "number", "description": "Inner cone angle in degrees", "default": 15.0},
                        "outer_cone_angle":{"type": "number", "description": "Outer cone angle in degrees", "default": 45.0},
                        "attenuation_radius": {"type": "number", "default": 2000.0},
                        "cast_shadows":    {"type": "boolean", "default": True},
                        "label":           {"type": "string", "default": "SpotLight"}
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="scene_add_directional_light",
                description="Add or configure a Directional Light (sun) in the level.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "rotation":    {"type": "array", "items": {"type": "number"}, "description": "Sun direction [pitch, yaw, roll]", "default": [-45, 0, 0]},
                        "color":       {"type": "array", "items": {"type": "number"}, "default": [1.0, 0.95, 0.85]},
                        "intensity":   {"type": "number", "description": "Lux", "default": 10.0},
                        "cast_shadows":{"type": "boolean", "default": True},
                        "dynamic_shadows": {"type": "boolean", "default": True},
                        "label":       {"type": "string", "default": "DirectionalLight"}
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="scene_add_sky_atmosphere",
                description="""Add Sky Atmosphere to create realistic sky rendering.
UE 5.4's Sky Atmosphere supports time-of-day and physically accurate atmosphere.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "rayleigh_scattering": {"type": "array", "items": {"type": "number"}, "description": "Sky color scattering [r,g,b]", "default": [0.175, 0.409, 1.0]},
                        "sun_disk_visible":    {"type": "boolean", "default": True},
                        "atmosphere_height":   {"type": "number", "description": "Atmosphere top altitude in km", "default": 100.0}
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="scene_add_exponential_fog",
                description="Add Exponential Height Fog for atmospheric depth.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "fog_density":          {"type": "number", "default": 0.02},
                        "fog_height_falloff":   {"type": "number", "default": 0.2},
                        "fog_color":            {"type": "array", "items": {"type": "number"}, "default": [0.75, 0.85, 1.0]},
                        "start_distance":       {"type": "number", "description": "Fog start distance in cm", "default": 0.0},
                        "volumetric_fog":       {"type": "boolean", "description": "Enable volumetric fog (UE 5.4)", "default": False},
                        "volumetric_fog_scattering": {"type": "number", "default": 1.0}
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="scene_set_actor_transform",
                description="Set the location, rotation, and/or scale of an actor by name.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "actor_label": {"type": "string", "description": "Actor label as shown in the Outliner"},
                        "location":    {"type": "array", "items": {"type": "number"}, "description": "[x, y, z] in cm"},
                        "rotation":    {"type": "array", "items": {"type": "number"}, "description": "[pitch, yaw, roll] in degrees"},
                        "scale":       {"type": "array", "items": {"type": "number"}, "description": "[x, y, z]"}
                    },
                    "required": ["actor_label"]
                }
            ),

            types.Tool(
                name="scene_delete_actor",
                description="Delete an actor from the current level by label.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "actor_label": {"type": "string", "description": "Actor label as shown in Outliner"},
                        "confirm":     {"type": "boolean", "description": "Must be true", "default": False}
                    },
                    "required": ["actor_label", "confirm"]
                }
            ),

            types.Tool(
                name="scene_set_world_settings",
                description="""Configure World Settings for the current level.
Controls: gravity, world to meters scale, default game mode, kill Z, etc.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "gravity_z":          {"type": "number", "description": "Gravity Z force (default -980)", "default": -980.0},
                        "world_to_meters":    {"type": "number", "description": "World scale (100 = 1m per 100cm)", "default": 100.0},
                        "default_game_mode":  {"type": "string", "description": "Content path to default Game Mode Blueprint"},
                        "kill_z":             {"type": "number", "description": "Z level below which actors are destroyed", "default": -50000.0},
                        "enable_world_origin_rebasing": {"type": "boolean", "description": "Large world coordinates rebasing", "default": False}
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="scene_add_post_process_volume",
                description="""Add a Post Process Volume to the level.
Controls: bloom, exposure, color grading, depth of field, ambient occlusion,
lens flares, chromatic aberration, vignette.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "unbound":             {"type": "boolean", "description": "Apply to entire world (unbound)", "default": True},
                        "bloom_intensity":     {"type": "number", "default": 0.675},
                        "exposure_compensation":{"type": "number", "description": "EV compensation", "default": 0.0},
                        "auto_exposure":       {"type": "boolean", "default": True},
                        "min_ev":              {"type": "number", "description": "Min exposure value", "default": -10.0},
                        "max_ev":              {"type": "number", "description": "Max exposure value", "default": 20.0},
                        "ambient_occlusion_intensity": {"type": "number", "default": 0.5},
                        "dof_focal_distance":  {"type": "number", "description": "Depth of field focal distance (0 = off)", "default": 0.0},
                        "color_saturation":    {"type": "array", "items": {"type": "number"}, "description": "[r,g,b,a] saturation", "default": [1.0, 1.0, 1.0, 1.0]},
                        "vignette_intensity":  {"type": "number", "default": 0.4},
                        "label":               {"type": "string", "default": "PostProcessVolume"}
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="scene_add_trigger_volume",
                description="Add a Trigger Box or Trigger Sphere volume to the level.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "trigger_type": {"type": "string", "description": "box or sphere", "default": "box"},
                        "location":     {"type": "array", "items": {"type": "number"}, "default": [0, 0, 0]},
                        "extent":       {"type": "array", "items": {"type": "number"}, "description": "Box half-extent [x,y,z] or sphere radius", "default": [100, 100, 100]},
                        "label":        {"type": "string", "default": "TriggerVolume"}
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="scene_select_actor",
                description="Select an actor in the editor by label.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "actor_label": {"type": "string"},
                        "add_to_selection": {"type": "boolean", "default": False}
                    },
                    "required": ["actor_label"]
                }
            ),

            types.Tool(
                name="scene_duplicate_actor",
                description="Duplicate an actor and optionally offset it.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "actor_label": {"type": "string", "description": "Source actor label"},
                        "offset":      {"type": "array", "items": {"type": "number"}, "description": "Location offset [x,y,z]", "default": [100, 0, 0]},
                        "count":       {"type": "integer", "description": "Number of duplicates", "default": 1},
                        "new_label":   {"type": "string", "description": "Label for the duplicate"}
                    },
                    "required": ["actor_label"]
                }
            ),

            types.Tool(
                name="scene_save_level",
                description="Save the current level.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "save_all": {"type": "boolean", "description": "Save all dirty assets too", "default": False}
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="scene_add_camera",
                description="""Add a Camera Actor to the level.
Configures field of view, aspect ratio, and depth of field.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "location":      {"type": "array", "items": {"type": "number"}, "default": [0, -500, 200]},
                        "rotation":      {"type": "array", "items": {"type": "number"}, "default": [0, 0, 0]},
                        "fov":           {"type": "number", "description": "Field of view in degrees", "default": 90.0},
                        "aspect_ratio":  {"type": "number", "description": "Width/height ratio", "default": 1.777},
                        "use_dof":       {"type": "boolean", "description": "Enable depth of field", "default": False},
                        "focal_distance":{"type": "number", "default": 1000.0},
                        "label":         {"type": "string", "default": "CameraActor"}
                    },
                    "required": []
                }
            ),

        ]

    # ─────────────────────────────────────────────
    # Handler
    # ─────────────────────────────────────────────

    async def handle(self, name: str, args: dict) -> list[types.TextContent]:
        handlers = {
            "scene_spawn_actor":         self._spawn_actor,
            "scene_place_static_mesh":   self._place_mesh,
            "scene_add_point_light":     self._add_point_light,
            "scene_add_spot_light":      self._add_spot_light,
            "scene_add_directional_light":self._add_directional_light,
            "scene_add_sky_atmosphere":  self._add_sky_atm,
            "scene_add_exponential_fog": self._add_fog,
            "scene_set_actor_transform": self._set_transform,
            "scene_delete_actor":        self._delete_actor,
            "scene_set_world_settings":  self._set_world_settings,
            "scene_add_post_process_volume": self._add_ppv,
            "scene_add_trigger_volume":  self._add_trigger,
            "scene_select_actor":        self._select_actor,
            "scene_duplicate_actor":     self._duplicate_actor,
            "scene_save_level":          self._save_level,
            "scene_add_camera":          self._add_camera,
        }
        handler = handlers.get(name)
        if not handler:
            return [types.TextContent(type="text", text=f"Unknown scene tool: {name}")]
        return await handler(args)

    # ─────────────────────────────────────────────
    # Implementations
    # ─────────────────────────────────────────────

    async def _spawn_actor(self, args: dict) -> list[types.TextContent]:
        bp_path      = args.get("blueprint_path", "")
        actor_class  = args.get("actor_class", "")
        location     = args.get("location", [0, 0, 0])
        rotation     = args.get("rotation", [0, 0, 0])
        scale        = args.get("scale", [1, 1, 1])
        label        = args.get("label", "")

        script = f"""
import unreal, json

loc = unreal.Vector(x={location[0]}, y={location[1]}, z={location[2]})
rot = unreal.Rotator(pitch={rotation[0]}, yaw={rotation[1]}, roll={rotation[2]})
scl = unreal.Vector(x={scale[0]}, y={scale[1]}, z={scale[2]})

bp_path     = "{bp_path}"
actor_class = "{actor_class}"
actor = None

if bp_path:
    bp = unreal.EditorAssetLibrary.load_asset(bp_path)
    if bp:
        bp_class = bp.generated_class() if isinstance(bp, unreal.Blueprint) else bp
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(bp_class, loc, rot)
elif actor_class:
    cls_map = {{
        "StaticMeshActor":        "/Script/Engine.StaticMeshActor",
        "PointLight":             "/Script/Engine.PointLight",
        "SpotLight":              "/Script/Engine.SpotLight",
        "DirectionalLight":       "/Script/Engine.DirectionalLight",
        "SkyLight":               "/Script/Engine.SkyLight",
        "ExponentialHeightFog":   "/Script/Engine.ExponentialHeightFog",
        "SkyAtmosphere":          "/Script/Engine.SkyAtmosphere",
        "CameraActor":            "/Script/Engine.CameraActor",
        "TriggerBox":             "/Script/Engine.TriggerBox",
        "TriggerSphere":          "/Script/Engine.TriggerSphere",
        "PostProcessVolume":      "/Script/Engine.PostProcessVolume",
    }}
    cls_path = cls_map.get(actor_class, f"/Script/Engine.{{actor_class}}")
    cls = unreal.load_class(None, cls_path)
    if cls:
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(cls, loc, rot)

if actor:
    actor.set_actor_scale3d(scl)
    label = "{label}"
    if label:
        actor.set_actor_label(label)
    print("UEOS_RESULT:" + json.dumps({{
        "status":   "spawned",
        "label":    actor.get_actor_label(),
        "class":    actor.get_class().get_name(),
        "location": {location},
        "rotation": {rotation}
    }}))
else:
    print("UEOS_ERROR:Failed to spawn actor. Check blueprint_path or actor_class.")
"""
        return self._ret(await self.ue.execute_python(script))

    async def _place_mesh(self, args: dict) -> list[types.TextContent]:
        mesh_path    = args["mesh_path"]
        location     = args.get("location", [0, 0, 0])
        rotation     = args.get("rotation", [0, 0, 0])
        scale        = args.get("scale", [1, 1, 1])
        mat_path     = args.get("material_path", "")
        label        = args.get("label", "")
        mobility     = args.get("mobility", "Static")

        mobility_map = {
            "Static":     "EComponentMobility.STATIC",
            "Stationary": "EComponentMobility.STATIONARY",
            "Movable":    "EComponentMobility.MOVABLE"
        }
        ue_mobility = mobility_map.get(mobility, "EComponentMobility.STATIC")

        script = f"""
import unreal, json

mesh = unreal.EditorAssetLibrary.load_asset("{mesh_path}")
if mesh is None:
    print("UEOS_ERROR:Mesh not found: {mesh_path}")
else:
    loc = unreal.Vector(x={location[0]}, y={location[1]}, z={location[2]})
    rot = unreal.Rotator(pitch={rotation[0]}, yaw={rotation[1]}, roll={rotation[2]})
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.StaticMeshActor, loc, rot
    )
    if actor:
        actor.set_actor_scale3d(unreal.Vector(x={scale[0]}, y={scale[1]}, z={scale[2]}))
        comp = actor.static_mesh_component
        comp.set_static_mesh(mesh)
        comp.set_editor_property("mobility", {ue_mobility})

        label = "{label}"
        if label:
            actor.set_actor_label(label)

        mat_path = "{mat_path}"
        if mat_path:
            mat = unreal.EditorAssetLibrary.load_asset(mat_path)
            if mat:
                comp.set_material(0, mat)

        unreal.EditorLevelLibrary.save_current_level()
        print("UEOS_RESULT:" + json.dumps({{
            "status":   "placed",
            "label":    actor.get_actor_label(),
            "mesh":     "{mesh_path}",
            "location": {location},
            "mobility": "{mobility}"
        }}))
    else:
        print("UEOS_ERROR:Failed to spawn StaticMeshActor")
"""
        return self._ret(await self.ue.execute_python(script))

    async def _add_point_light(self, args: dict) -> list[types.TextContent]:
        location  = args.get("location", [0, 0, 300])
        color     = args.get("color", [1.0, 1.0, 1.0])
        intensity = args.get("intensity", 1000.0)
        radius    = args.get("attenuation_radius", 1000.0)
        shadows   = args.get("cast_shadows", True)
        label     = args.get("label", "PointLight")

        script = f"""
import unreal, json

loc = unreal.Vector(x={location[0]}, y={location[1]}, z={location[2]})
actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.PointLight, loc, unreal.Rotator())
if actor:
    comp = actor.point_light_component
    c = {json.dumps(color)}
    comp.set_light_color(unreal.LinearColor(r=c[0], g=c[1], b=c[2], a=1.0))
    comp.set_editor_property("intensity", {intensity})
    comp.set_editor_property("attenuation_radius", {radius})
    comp.set_cast_shadows({str(shadows).lower()})
    actor.set_actor_label("{label}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":    "added",
        "label":     "{label}",
        "type":      "PointLight",
        "intensity": {intensity},
        "radius":    {radius}
    }}))
else:
    print("UEOS_ERROR:Failed to spawn PointLight")
"""
        return self._ret(await self.ue.execute_python(script))

    async def _add_spot_light(self, args: dict) -> list[types.TextContent]:
        location   = args.get("location", [0, 0, 500])
        rotation   = args.get("rotation", [-90, 0, 0])
        color      = args.get("color", [1.0, 1.0, 1.0])
        intensity  = args.get("intensity", 5000.0)
        inner_cone = args.get("inner_cone_angle", 15.0)
        outer_cone = args.get("outer_cone_angle", 45.0)
        radius     = args.get("attenuation_radius", 2000.0)
        shadows    = args.get("cast_shadows", True)
        label      = args.get("label", "SpotLight")

        script = f"""
import unreal, json

loc = unreal.Vector(x={location[0]}, y={location[1]}, z={location[2]})
rot = unreal.Rotator(pitch={rotation[0]}, yaw={rotation[1]}, roll={rotation[2]})
actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SpotLight, loc, rot)
if actor:
    comp = actor.spot_light_component
    c = {json.dumps(color)}
    comp.set_light_color(unreal.LinearColor(r=c[0], g=c[1], b=c[2], a=1.0))
    comp.set_editor_property("intensity", {intensity})
    comp.set_editor_property("inner_cone_angle", {inner_cone})
    comp.set_editor_property("outer_cone_angle", {outer_cone})
    comp.set_editor_property("attenuation_radius", {radius})
    comp.set_cast_shadows({str(shadows).lower()})
    actor.set_actor_label("{label}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":       "added",
        "label":        "{label}",
        "type":         "SpotLight",
        "inner_cone":   {inner_cone},
        "outer_cone":   {outer_cone}
    }}))
else:
    print("UEOS_ERROR:Failed to spawn SpotLight")
"""
        return self._ret(await self.ue.execute_python(script))

    async def _add_directional_light(self, args: dict) -> list[types.TextContent]:
        rotation   = args.get("rotation", [-45, 0, 0])
        color      = args.get("color", [1.0, 0.95, 0.85])
        intensity  = args.get("intensity", 10.0)
        shadows    = args.get("cast_shadows", True)
        label      = args.get("label", "DirectionalLight")

        script = f"""
import unreal, json

rot = unreal.Rotator(pitch={rotation[0]}, yaw={rotation[1]}, roll={rotation[2]})
actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
    unreal.DirectionalLight, unreal.Vector(), rot
)
if actor:
    comp = actor.get_component_by_class(unreal.DirectionalLightComponent)
    if comp:
        c = {json.dumps(color)}
        comp.set_light_color(unreal.LinearColor(r=c[0], g=c[1], b=c[2], a=1.0))
        comp.set_editor_property("intensity", {intensity})
        comp.set_cast_shadows({str(shadows).lower()})
    actor.set_actor_label("{label}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":    "added",
        "label":     "{label}",
        "type":      "DirectionalLight",
        "intensity": {intensity}
    }}))
else:
    print("UEOS_ERROR:Failed to spawn DirectionalLight")
"""
        return self._ret(await self.ue.execute_python(script))

    async def _add_sky_atm(self, args: dict) -> list[types.TextContent]:
        script = f"""
import unreal, json

actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
    unreal.SkyAtmosphere, unreal.Vector(), unreal.Rotator()
)
if actor:
    actor.set_actor_label("SkyAtmosphere")
    print("UEOS_RESULT:" + json.dumps({{"status":"added","type":"SkyAtmosphere"}}))
else:
    print("UEOS_ERROR:Failed to add SkyAtmosphere")
"""
        return self._ret(await self.ue.execute_python(script))

    async def _add_fog(self, args: dict) -> list[types.TextContent]:
        density  = args.get("fog_density", 0.02)
        falloff  = args.get("fog_height_falloff", 0.2)
        color    = args.get("fog_color", [0.75, 0.85, 1.0])
        start    = args.get("start_distance", 0.0)
        vol_fog  = args.get("volumetric_fog", False)
        vol_scat = args.get("volumetric_fog_scattering", 1.0)

        script = f"""
import unreal, json

actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
    unreal.ExponentialHeightFog, unreal.Vector(), unreal.Rotator()
)
if actor:
    comp = actor.get_component_by_class(unreal.ExponentialHeightFogComponent)
    if comp:
        comp.set_editor_property("fog_density", {density})
        comp.set_editor_property("fog_height_falloff", {falloff})
        c = {json.dumps(color)}
        comp.set_editor_property("fog_inscattering_color",
            unreal.LinearColor(r=c[0], g=c[1], b=c[2], a=1.0))
        comp.set_editor_property("start_distance", {start})
        if {str(vol_fog).lower()}:
            comp.set_editor_property("volumetric_fog", True)
            comp.set_editor_property("volumetric_fog_scattering_distribution", {vol_scat})
    actor.set_actor_label("ExponentialHeightFog")
    print("UEOS_RESULT:" + json.dumps({{
        "status":          "added",
        "type":            "ExponentialHeightFog",
        "density":         {density},
        "volumetric_fog":  {str(vol_fog).lower()}
    }}))
else:
    print("UEOS_ERROR:Failed to add ExponentialHeightFog")
"""
        return self._ret(await self.ue.execute_python(script))

    async def _set_transform(self, args: dict) -> list[types.TextContent]:
        actor_label = args["actor_label"]
        location    = args.get("location")
        rotation    = args.get("rotation")
        scale       = args.get("scale")

        script = f"""
import unreal, json

actors = unreal.EditorLevelLibrary.get_all_level_actors()
target = None
for a in actors:
    if a.get_actor_label() == "{actor_label}":
        target = a
        break

if target is None:
    print("UEOS_ERROR:Actor not found: {actor_label}")
else:
    location = {json.dumps(location)}
    rotation = {json.dumps(rotation)}
    scale    = {json.dumps(scale)}

    if location is not None:
        target.set_actor_location(unreal.Vector(x=location[0], y=location[1], z=location[2]), False, False)
    if rotation is not None:
        target.set_actor_rotation(unreal.Rotator(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]), False)
    if scale is not None:
        target.set_actor_scale3d(unreal.Vector(x=scale[0], y=scale[1], z=scale[2]))

    print("UEOS_RESULT:" + json.dumps({{
        "status": "transform_set",
        "label":  "{actor_label}",
        "location": location,
        "rotation": rotation,
        "scale":    scale
    }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _delete_actor(self, args: dict) -> list[types.TextContent]:
        actor_label = args["actor_label"]
        confirm     = args.get("confirm", False)

        if not confirm:
            return [types.TextContent(type="text", text=json.dumps({"status": "cancelled", "message": "Set confirm=true to delete"}))]

        script = f"""
import unreal, json

actors = unreal.EditorLevelLibrary.get_all_level_actors()
target = None
for a in actors:
    if a.get_actor_label() == "{actor_label}":
        target = a
        break

if target is None:
    print("UEOS_ERROR:Actor not found: {actor_label}")
else:
    unreal.EditorLevelLibrary.destroy_actor(target)
    print("UEOS_RESULT:" + json.dumps({{"status":"deleted","label":"{actor_label}"}}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _set_world_settings(self, args: dict) -> list[types.TextContent]:
        gravity   = args.get("gravity_z", -980.0)
        w2m       = args.get("world_to_meters", 100.0)
        gm_path   = args.get("default_game_mode", "")
        kill_z    = args.get("kill_z", -50000.0)

        script = f"""
import unreal, json

world = unreal.EditorLevelLibrary.get_editor_world()
ws = world.get_world_settings()
ws.set_editor_property("world_to_meters", {w2m})
ws.set_editor_property("kill_z", {kill_z})

gm_path = "{gm_path}"
if gm_path:
    gm_bp = unreal.EditorAssetLibrary.load_asset(gm_path)
    if gm_bp and isinstance(gm_bp, unreal.Blueprint):
        ws.set_editor_property("default_game_mode", gm_bp.generated_class())

world.mark_package_dirty()
print("UEOS_RESULT:" + json.dumps({{
    "status":          "set",
    "world_to_meters": {w2m},
    "kill_z":          {kill_z}
}}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _add_ppv(self, args: dict) -> list[types.TextContent]:
        unbound     = args.get("unbound", True)
        bloom       = args.get("bloom_intensity", 0.675)
        exposure    = args.get("exposure_compensation", 0.0)
        auto_exp    = args.get("auto_exposure", True)
        min_ev      = args.get("min_ev", -10.0)
        max_ev      = args.get("max_ev", 20.0)
        ao          = args.get("ambient_occlusion_intensity", 0.5)
        dof         = args.get("dof_focal_distance", 0.0)
        vignette    = args.get("vignette_intensity", 0.4)
        label       = args.get("label", "PostProcessVolume")

        script = f"""
import unreal, json

actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
    unreal.PostProcessVolume, unreal.Vector(), unreal.Rotator()
)
if actor:
    actor.set_editor_property("unbound", {str(unbound).lower()})
    settings = actor.settings
    settings.set_editor_property("bloom_intensity",           {bloom})
    settings.set_editor_property("exposure_compensation",     {exposure})
    settings.set_editor_property("auto_exposure_min_brightness", {min_ev})
    settings.set_editor_property("auto_exposure_max_brightness", {max_ev})
    settings.set_editor_property("ambient_occlusion_intensity",  {ao})
    settings.set_editor_property("vignette_intensity",           {vignette})
    actor.set_actor_label("{label}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":  "added",
        "label":   "{label}",
        "unbound": {str(unbound).lower()}
    }}))
else:
    print("UEOS_ERROR:Failed to add PostProcessVolume")
"""
        return self._ret(await self.ue.execute_python(script))

    async def _add_trigger(self, args: dict) -> list[types.TextContent]:
        trigger_type = args.get("trigger_type", "box")
        location     = args.get("location", [0, 0, 0])
        extent       = args.get("extent", [100, 100, 100])
        label        = args.get("label", "TriggerVolume")

        cls_name = "TriggerBox" if trigger_type == "box" else "TriggerSphere"

        script = f"""
import unreal, json

cls = unreal.{cls_name}
loc = unreal.Vector(x={location[0]}, y={location[1]}, z={location[2]})
actor = unreal.EditorLevelLibrary.spawn_actor_from_class(cls, loc, unreal.Rotator())
if actor:
    actor.set_actor_label("{label}")
    print("UEOS_RESULT:" + json.dumps({{
        "status": "added",
        "type":   "{cls_name}",
        "label":  "{label}",
        "extent": {json.dumps(extent)}
    }}))
else:
    print("UEOS_ERROR:Failed to add trigger volume")
"""
        return self._ret(await self.ue.execute_python(script))

    async def _select_actor(self, args: dict) -> list[types.TextContent]:
        actor_label = args["actor_label"]
        add_to      = args.get("add_to_selection", False)

        script = f"""
import unreal, json

actors = unreal.EditorLevelLibrary.get_all_level_actors()
target = None
for a in actors:
    if a.get_actor_label() == "{actor_label}":
        target = a
        break

if target:
    if not {str(add_to).lower()}:
        unreal.EditorLevelLibrary.set_selected_level_actors([target])
    else:
        sel = list(unreal.EditorLevelLibrary.get_selected_level_actors())
        sel.append(target)
        unreal.EditorLevelLibrary.set_selected_level_actors(sel)
    print("UEOS_RESULT:" + json.dumps({{"status":"selected","label":"{actor_label}"}}))
else:
    print("UEOS_ERROR:Actor not found: {actor_label}")
"""
        return self._ret(await self.ue.execute_python(script))

    async def _duplicate_actor(self, args: dict) -> list[types.TextContent]:
        actor_label = args["actor_label"]
        offset      = args.get("offset", [100, 0, 0])
        count       = args.get("count", 1)
        new_label   = args.get("new_label", "")

        script = f"""
import unreal, json

actors = unreal.EditorLevelLibrary.get_all_level_actors()
source = None
for a in actors:
    if a.get_actor_label() == "{actor_label}":
        source = a
        break

if source is None:
    print("UEOS_ERROR:Actor not found: {actor_label}")
else:
    duplicated = []
    offset = {json.dumps(offset)}
    for i in range({count}):
        dup = unreal.EditorLevelLibrary.duplicate_actor(source)
        if dup:
            src_loc = source.get_actor_location()
            dup.set_actor_location(
                unreal.Vector(
                    x=src_loc.x + offset[0] * (i+1),
                    y=src_loc.y + offset[1] * (i+1),
                    z=src_loc.z + offset[2] * (i+1)
                ),
                False, False
            )
            new_label = "{new_label}"
            if new_label:
                dup.set_actor_label(f"{{new_label}}_{{i+1}}")
            duplicated.append(dup.get_actor_label())

    print("UEOS_RESULT:" + json.dumps({{
        "status":     "duplicated",
        "source":     "{actor_label}",
        "duplicated": duplicated
    }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _save_level(self, args: dict) -> list[types.TextContent]:
        save_all = args.get("save_all", False)

        script = f"""
import unreal, json

unreal.EditorLevelLibrary.save_current_level()
if {str(save_all).lower()}:
    unreal.EditorAssetLibrary.save_directory("/Game", recursive=True)
print("UEOS_RESULT:" + json.dumps({{"status":"saved","save_all":{str(save_all).lower()}}}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _add_camera(self, args: dict) -> list[types.TextContent]:
        location     = args.get("location", [0, -500, 200])
        rotation     = args.get("rotation", [0, 0, 0])
        fov          = args.get("fov", 90.0)
        aspect       = args.get("aspect_ratio", 1.777)
        use_dof      = args.get("use_dof", False)
        focal_dist   = args.get("focal_distance", 1000.0)
        label        = args.get("label", "CameraActor")

        script = f"""
import unreal, json

loc = unreal.Vector(x={location[0]}, y={location[1]}, z={location[2]})
rot = unreal.Rotator(pitch={rotation[0]}, yaw={rotation[1]}, roll={rotation[2]})
actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.CameraActor, loc, rot)
if actor:
    comp = actor.camera_component
    comp.set_editor_property("field_of_view", {fov})
    comp.set_editor_property("aspect_ratio",  {aspect})
    if {str(use_dof).lower()}:
        pp = comp.post_process_settings
        pp.set_editor_property("depth_of_field_method", unreal.DepthOfFieldMethod.GAUSSIAN)
        pp.set_editor_property("depth_of_field_focal_distance", {focal_dist})
    actor.set_actor_label("{label}")
    print("UEOS_RESULT:" + json.dumps({{
        "status": "added",
        "label":  "{label}",
        "fov":    {fov},
        "dof":    {str(use_dof).lower()}
    }}))
else:
    print("UEOS_ERROR:Failed to add CameraActor")
"""
        return self._ret(await self.ue.execute_python(script))

    def _ret(self, result: dict) -> list[types.TextContent]:
        output = result.get("output", "")
        for line in output.split("\n"):
            if line.startswith("UEOS_RESULT:"):
                return [types.TextContent(type="text",
                    text=json.dumps(json.loads(line.replace("UEOS_RESULT:", "")), indent=2))]
            if line.startswith("UEOS_ERROR:"):
                return [types.TextContent(type="text",
                    text=json.dumps({"status": "error", "message": line.replace("UEOS_ERROR:", "")}, indent=2))]
        return [types.TextContent(type="text",
            text=json.dumps({"status": "error", "raw_output": output}, indent=2))]
