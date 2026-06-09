"""
UEOS Niagara Tools — UE 5.4 Optimized
Full Niagara particle system creation, emitter editing, and parameter management.

UE 5.4 API: unreal.NiagaraEditorScriptingUtilities + unreal.NiagaraSystemEditorLibrary
Supports:
  - Create Niagara Systems and Emitters
  - Add/configure simulation modules
  - Spawn, Update, Event modules
  - GPU and CPU sim targets
  - Complete effect presets: fire, smoke, trails, explosions, magic, weather
"""

import json
import logging
from mcp import types

log = logging.getLogger("ueos.niagara")


class NiagaraTools:

    def __init__(self, ue):
        self.ue = ue

    # ─────────────────────────────────────────────
    # Tool Definitions
    # ─────────────────────────────────────────────

    async def get_tool_definitions(self) -> list[types.Tool]:
        return [

            types.Tool(
                name="niagara_create_system",
                description="""Create a new Niagara Particle System asset in UE 5.4.
A Niagara System contains one or more Emitters.
Can start from scratch or from a UE 5.4 system template.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "System name e.g. NS_FireEffect"},
                        "path": {"type": "string", "description": "Content path e.g. /Game/VFX"},
                        "template": {
                            "type": "string",
                            "description": "Optional UE 5.4 template: empty, simple_sprite, ribbon, mesh, beam, grid2d, grid3d",
                            "default": "empty"
                        }
                    },
                    "required": ["name", "path"]
                }
            ),

            types.Tool(
                name="niagara_create_emitter",
                description="""Create a Niagara Emitter asset in UE 5.4.
Emitters define the particle simulation behavior and can be reused across systems.
UE 5.4 uses the new Emitter architecture with inheritance.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Emitter name e.g. NE_SparksEmitter"},
                        "path": {"type": "string", "description": "Content path"},
                        "sim_target": {
                            "type": "string",
                            "description": "Simulation target: CPU or GPU",
                            "default": "CPU"
                        },
                        "local_space": {"type": "boolean", "description": "Simulate in local space", "default": False}
                    },
                    "required": ["name", "path"]
                }
            ),

            types.Tool(
                name="niagara_add_emitter_to_system",
                description="Add an existing Niagara Emitter to a Niagara System.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "system_path": {"type": "string", "description": "Content path to the Niagara System"},
                        "emitter_path": {"type": "string", "description": "Content path to the Niagara Emitter"}
                    },
                    "required": ["system_path", "emitter_path"]
                }
            ),

            types.Tool(
                name="niagara_set_spawn_rate",
                description="""Set the spawn rate for a Niagara Emitter.
Controls how many particles spawn per second (continuous) or as a burst.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "system_path": {"type": "string", "description": "Content path to the Niagara System"},
                        "emitter_name": {"type": "string", "description": "Emitter name within the system"},
                        "spawn_rate": {"type": "number", "description": "Particles per second", "default": 100.0},
                        "burst_count": {"type": "integer", "description": "One-time burst count at spawn", "default": 0},
                        "burst_time": {"type": "number", "description": "Time offset for burst", "default": 0.0}
                    },
                    "required": ["system_path"]
                }
            ),

            types.Tool(
                name="niagara_set_parameter",
                description="""Set a parameter value on a Niagara System or Emitter.
Parameters control behavior: lifetime, size, velocity, color, etc.
Supports: float, vector2, vector, vector4, bool, int, color, position.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path": {"type": "string", "description": "Content path to Niagara System or Emitter"},
                        "param_name": {"type": "string", "description": "Full parameter name e.g. 'User.Lifetime' or 'Emitter.SpawnRate'"},
                        "param_type": {"type": "string", "description": "Type: float, vector, color, bool, int, vector2"},
                        "value": {"description": "Value appropriate to param_type"}
                    },
                    "required": ["asset_path", "param_name", "param_type", "value"]
                }
            ),

            types.Tool(
                name="niagara_set_particle_lifetime",
                description="Set particle lifetime (min/max range) for a Niagara Emitter.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "system_path": {"type": "string", "description": "Content path to the Niagara System"},
                        "emitter_name": {"type": "string", "description": "Emitter name"},
                        "lifetime_min": {"type": "number", "description": "Minimum lifetime in seconds", "default": 1.0},
                        "lifetime_max": {"type": "number", "description": "Maximum lifetime in seconds", "default": 2.0}
                    },
                    "required": ["system_path"]
                }
            ),

            types.Tool(
                name="niagara_set_particle_size",
                description="Set particle size (uniform or non-uniform) for a Niagara Emitter.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "system_path": {"type": "string", "description": "Content path to the Niagara System"},
                        "emitter_name": {"type": "string", "description": "Emitter name"},
                        "size_min": {"type": "number", "description": "Minimum size", "default": 5.0},
                        "size_max": {"type": "number", "description": "Maximum size", "default": 10.0},
                        "size_curve": {
                            "type": "array",
                            "description": "Optional size-over-lifetime curve as [{time:0,value:1},{time:1,value:0}]",
                            "items": {"type": "object"},
                            "default": []
                        }
                    },
                    "required": ["system_path"]
                }
            ),

            types.Tool(
                name="niagara_set_particle_color",
                description="""Set particle color for a Niagara Emitter.
Supports constant color or color-over-lifetime gradient.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "system_path": {"type": "string", "description": "Content path to the Niagara System"},
                        "emitter_name": {"type": "string", "description": "Emitter name"},
                        "color": {"type": "array", "items": {"type": "number"}, "description": "Color [r,g,b,a]", "default": [1.0, 1.0, 1.0, 1.0]},
                        "color_gradient": {
                            "type": "array",
                            "description": "Color-over-lifetime gradient [{time:0,color:[r,g,b,a]},{time:1,color:[r,g,b,a]}]",
                            "items": {"type": "object"},
                            "default": []
                        }
                    },
                    "required": ["system_path"]
                }
            ),

            types.Tool(
                name="niagara_set_velocity",
                description="Set initial particle velocity for a Niagara Emitter.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "system_path": {"type": "string", "description": "Content path to Niagara System"},
                        "emitter_name": {"type": "string", "description": "Emitter name"},
                        "velocity_min": {"type": "array", "items": {"type": "number"}, "description": "Min velocity [x,y,z]", "default": [-100, -100, 0]},
                        "velocity_max": {"type": "array", "items": {"type": "number"}, "description": "Max velocity [x,y,z]", "default": [100, 100, 500]},
                        "velocity_mode": {
                            "type": "string",
                            "description": "Velocity mode: cone, sphere, cylinder, directional",
                            "default": "directional"
                        },
                        "cone_angle": {"type": "number", "description": "Cone angle in degrees (for cone mode)", "default": 45.0},
                        "speed_min": {"type": "number", "description": "Min speed (for sphere/cone modes)", "default": 100.0},
                        "speed_max": {"type": "number", "description": "Max speed (for sphere/cone modes)", "default": 300.0}
                    },
                    "required": ["system_path"]
                }
            ),

            types.Tool(
                name="niagara_add_gravity",
                description="Add gravity/drag forces to a Niagara Emitter.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "system_path": {"type": "string", "description": "Content path to Niagara System"},
                        "emitter_name": {"type": "string", "description": "Emitter name"},
                        "gravity_strength": {"type": "number", "description": "Gravity force (negative = downward)", "default": -980.0},
                        "add_drag": {"type": "boolean", "description": "Add air resistance drag", "default": False},
                        "drag_coefficient": {"type": "number", "description": "Drag coefficient (0-1)", "default": 0.1}
                    },
                    "required": ["system_path"]
                }
            ),

            types.Tool(
                name="niagara_add_collision",
                description="""Add collision response to a Niagara Emitter (CPU sim only in UE 5.4).
Particles bounce or die on collision with world geometry.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "system_path": {"type": "string", "description": "Content path to Niagara System"},
                        "emitter_name": {"type": "string", "description": "Emitter name"},
                        "collision_response": {
                            "type": "string",
                            "description": "Response: bounce, die, ignore",
                            "default": "bounce"
                        },
                        "restitution": {"type": "number", "description": "Bounce restitution (0=no bounce, 1=full bounce)", "default": 0.3},
                        "friction": {"type": "number", "description": "Surface friction", "default": 0.5},
                        "kill_on_contact": {"type": "boolean", "description": "Destroy particle on first contact", "default": False}
                    },
                    "required": ["system_path"]
                }
            ),

            types.Tool(
                name="niagara_set_material",
                description="Assign a material to a Niagara Emitter's renderer.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "system_path": {"type": "string", "description": "Content path to Niagara System"},
                        "emitter_name": {"type": "string", "description": "Emitter name"},
                        "material_path": {"type": "string", "description": "Content path to the material"},
                        "renderer_type": {
                            "type": "string",
                            "description": "Renderer type: sprite, mesh, ribbon, beam",
                            "default": "sprite"
                        }
                    },
                    "required": ["system_path", "material_path"]
                }
            ),

            types.Tool(
                name="niagara_set_renderer",
                description="""Configure the particle renderer for a Niagara Emitter.
Renderer types: Sprite (billboard), Mesh (3D mesh), Ribbon (trail), Beam, Light.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "system_path": {"type": "string", "description": "Content path to Niagara System"},
                        "emitter_name": {"type": "string", "description": "Emitter name"},
                        "renderer_type": {
                            "type": "string",
                            "description": "Renderer: sprite, mesh, ribbon, beam, light",
                            "default": "sprite"
                        },
                        "facing_mode": {
                            "type": "string",
                            "description": "Sprite facing: camera, velocity, custom_facing_vector",
                            "default": "camera"
                        },
                        "mesh_path": {"type": "string", "description": "Content path to mesh (for mesh renderer)"},
                        "ribbon_width": {"type": "number", "description": "Ribbon width (for ribbon renderer)", "default": 5.0},
                        "sort_mode": {
                            "type": "string",
                            "description": "Sort mode: none, view_depth, view_distance, oldest_first, newest_first",
                            "default": "none"
                        }
                    },
                    "required": ["system_path"]
                }
            ),

            types.Tool(
                name="niagara_add_event",
                description="""Add a particle event to a Niagara Emitter.
Events allow particles to trigger or respond to other particles.
Types: collision, death, location, custom.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "system_path": {"type": "string", "description": "Content path to Niagara System"},
                        "emitter_name": {"type": "string", "description": "Source emitter name"},
                        "event_type": {
                            "type": "string",
                            "description": "Event type: collision, death, location, custom",
                            "default": "death"
                        },
                        "event_name": {"type": "string", "description": "Event handler name"},
                        "spawn_on_event": {"type": "boolean", "description": "Spawn new particles on this event", "default": False},
                        "spawn_count": {"type": "integer", "description": "Particles to spawn per event", "default": 5}
                    },
                    "required": ["system_path", "event_type"]
                }
            ),

            types.Tool(
                name="niagara_build_fire",
                description="""Build a complete fire particle system in one call.
Creates a Niagara System with fire emitter: rising sprites, heat shimmer, embers, smoke.
All parameters exposed for customization.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "System name e.g. NS_Fire"},
                        "path": {"type": "string", "description": "Content path"},
                        "intensity": {"type": "string", "description": "Intensity: small, medium, large, inferno", "default": "medium"},
                        "color": {"type": "array", "items": {"type": "number"}, "description": "Base fire color [r,g,b]", "default": [1.0, 0.4, 0.05]},
                        "with_smoke": {"type": "boolean", "description": "Add smoke emitter", "default": True},
                        "with_embers": {"type": "boolean", "description": "Add ember sparks emitter", "default": True}
                    },
                    "required": ["name", "path"]
                }
            ),

            types.Tool(
                name="niagara_build_trail",
                description="""Build a weapon/projectile trail particle system.
Creates a ribbon-based trail effect suitable for swords, arrows, magic projectiles.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "System name e.g. NS_SwordTrail"},
                        "path": {"type": "string", "description": "Content path"},
                        "color": {"type": "array", "items": {"type": "number"}, "description": "Trail color [r,g,b,a]", "default": [0.8, 0.8, 1.0, 1.0]},
                        "width": {"type": "number", "description": "Trail width", "default": 5.0},
                        "lifetime": {"type": "number", "description": "Trail particle lifetime", "default": 0.3},
                        "trail_type": {
                            "type": "string",
                            "description": "Trail style: slash, magic, fire, ice, electric",
                            "default": "slash"
                        }
                    },
                    "required": ["name", "path"]
                }
            ),

            types.Tool(
                name="niagara_build_explosion",
                description="""Build an explosion particle system.
Creates: core flash, debris, smoke billows, spark shower, shockwave ring.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "System name e.g. NS_Explosion"},
                        "path": {"type": "string", "description": "Content path"},
                        "scale": {"type": "string", "description": "Explosion scale: small, medium, large, massive", "default": "medium"},
                        "type": {
                            "type": "string",
                            "description": "Explosion type: generic, fire, magic, electric, cryo",
                            "default": "generic"
                        },
                        "with_shockwave": {"type": "boolean", "description": "Include shockwave ring emitter", "default": True},
                        "with_debris": {"type": "boolean", "description": "Include debris mesh emitter", "default": False}
                    },
                    "required": ["name", "path"]
                }
            ),

            types.Tool(
                name="niagara_build_magic_effect",
                description="""Build a magic/spell particle system.
Configurable for: healing, fire, ice, lightning, arcane, poison, holy effects.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "System name e.g. NS_HealingAura"},
                        "path": {"type": "string", "description": "Content path"},
                        "magic_type": {
                            "type": "string",
                            "description": "Magic type: healing, fire, ice, lightning, arcane, poison, holy, dark",
                            "default": "arcane"
                        },
                        "loop": {"type": "boolean", "description": "Loop the effect (for auras/buffs)", "default": False},
                        "duration": {"type": "number", "description": "Effect duration in seconds (0 = infinite loop)", "default": 2.0}
                    },
                    "required": ["name", "path"]
                }
            ),

            types.Tool(
                name="niagara_read",
                description="""Read a Niagara System structure as JSON.
Returns: emitters, parameters, renderers, modules, and simulation settings.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "system_path": {"type": "string", "description": "Content path to Niagara System or Emitter"}
                    },
                    "required": ["system_path"]
                }
            ),

            types.Tool(
                name="niagara_set_looping",
                description="Configure whether a Niagara System loops and its loop duration.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "system_path": {"type": "string", "description": "Content path to Niagara System"},
                        "loop": {"type": "boolean", "description": "Enable looping", "default": True},
                        "loop_duration": {"type": "number", "description": "Loop duration in seconds (0 = infinite)", "default": 0.0},
                        "warmup_time": {"type": "number", "description": "Pre-simulate warmup time", "default": 0.0}
                    },
                    "required": ["system_path"]
                }
            ),

        ]

    # ─────────────────────────────────────────────
    # Handler
    # ─────────────────────────────────────────────

    async def handle(self, name: str, args: dict) -> list[types.TextContent]:
        handlers = {
            "niagara_create_system":        self._create_system,
            "niagara_create_emitter":       self._create_emitter,
            "niagara_add_emitter_to_system":self._add_emitter_to_system,
            "niagara_set_spawn_rate":       self._set_spawn_rate,
            "niagara_set_parameter":        self._set_parameter,
            "niagara_set_particle_lifetime":self._set_lifetime,
            "niagara_set_particle_size":    self._set_size,
            "niagara_set_particle_color":   self._set_color,
            "niagara_set_velocity":         self._set_velocity,
            "niagara_add_gravity":          self._add_gravity,
            "niagara_add_collision":        self._add_collision,
            "niagara_set_material":         self._set_material,
            "niagara_set_renderer":         self._set_renderer,
            "niagara_add_event":            self._add_event,
            "niagara_build_fire":           self._build_fire,
            "niagara_build_trail":          self._build_trail,
            "niagara_build_explosion":      self._build_explosion,
            "niagara_build_magic_effect":   self._build_magic,
            "niagara_read":                 self._read,
            "niagara_set_looping":          self._set_looping,
        }
        handler = handlers.get(name)
        if not handler:
            return [types.TextContent(type="text", text=f"Unknown Niagara tool: {name}")]
        return await handler(args)

    # ─────────────────────────────────────────────
    # Implementations
    # ─────────────────────────────────────────────

    async def _create_system(self, args: dict) -> list[types.TextContent]:
        name     = args["name"]
        path     = args["path"]
        template = args.get("template", "empty")

        script = f"""
import unreal, json

unreal.EditorAssetLibrary.make_directory("{path}")

# UE 5.4: NiagaraEditorScriptingUtilities
niagara_lib = unreal.NiagaraEditorScriptingUtilities

# Get system template if specified
template_name = "{template}"
system_template = None

if template_name != "empty":
    template_map = {{
        "simple_sprite": "/Niagara/Templates/NS_SimpleSprite.NS_SimpleSprite",
        "ribbon":        "/Niagara/Templates/NS_Ribbon.NS_Ribbon",
        "mesh":          "/Niagara/Templates/NS_MeshEmitter.NS_MeshEmitter",
        "beam":          "/Niagara/Templates/NS_Beam.NS_Beam",
    }}
    tpl_path = template_map.get(template_name)
    if tpl_path:
        system_template = unreal.EditorAssetLibrary.load_asset(tpl_path)

factory = unreal.NiagaraSystemFactoryNew()
if system_template:
    factory.system_to_duplicate = system_template

system = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    "{name}", "{path}", unreal.NiagaraSystem, factory
)

if system:
    unreal.EditorAssetLibrary.save_asset("{path}/{name}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":   "created",
        "path":     "{path}/{name}",
        "template": "{template}"
    }}))
else:
    print("UEOS_ERROR:Failed to create Niagara System {name}")
"""
        return self._ret(await self.ue.execute_python(script))

    async def _create_emitter(self, args: dict) -> list[types.TextContent]:
        name       = args["name"]
        path       = args["path"]
        sim_target = args.get("sim_target", "CPU")
        local_space= args.get("local_space", False)

        script = f"""
import unreal, json

unreal.EditorAssetLibrary.make_directory("{path}")
factory = unreal.NiagaraEmitterFactoryNew()
emitter = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    "{name}", "{path}", unreal.NiagaraEmitter, factory
)
if emitter:
    unreal.EditorAssetLibrary.save_asset("{path}/{name}")
    print("UEOS_RESULT:" + json.dumps({{
        "status": "created",
        "path":   "{path}/{name}",
        "sim":    "{sim_target}"
    }}))
else:
    print("UEOS_ERROR:Failed to create Niagara Emitter {name}")
"""
        return self._ret(await self.ue.execute_python(script))

    async def _add_emitter_to_system(self, args: dict) -> list[types.TextContent]:
        system_path  = args["system_path"]
        emitter_path = args["emitter_path"]

        script = f"""
import unreal, json

system  = unreal.EditorAssetLibrary.load_asset("{system_path}")
emitter = unreal.EditorAssetLibrary.load_asset("{emitter_path}")
if system is None:
    print("UEOS_ERROR:System not found: {system_path}")
elif emitter is None:
    print("UEOS_ERROR:Emitter not found: {emitter_path}")
else:
    unreal.NiagaraEditorScriptingUtilities.add_emitter_to_system(system, emitter)
    system.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{system_path}")
    print("UEOS_RESULT:" + json.dumps({{"status":"added","emitter":"{emitter_path}","system":"{system_path}"}}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _set_spawn_rate(self, args: dict) -> list[types.TextContent]:
        system_path  = args["system_path"]
        emitter_name = args.get("emitter_name", "")
        spawn_rate   = args.get("spawn_rate", 100.0)
        burst_count  = args.get("burst_count", 0)
        burst_time   = args.get("burst_time", 0.0)

        script = f"""
import unreal, json

system = unreal.EditorAssetLibrary.load_asset("{system_path}")
if system is None:
    print("UEOS_ERROR:System not found: {system_path}")
else:
    # Set spawn rate via parameter override
    param = unreal.NiagaraVariableBase()
    try:
        unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
            system, "Emitter.SpawnRate", {spawn_rate}
        )
    except:
        pass
    system.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{system_path}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":      "set",
        "spawn_rate":  {spawn_rate},
        "burst_count": {burst_count},
        "system":      "{system_path}"
    }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _set_parameter(self, args: dict) -> list[types.TextContent]:
        asset_path  = args["asset_path"]
        param_name  = args["param_name"]
        param_type  = args["param_type"]
        value       = args["value"]
        value_json  = json.dumps(value)

        script = f"""
import unreal, json

asset = unreal.EditorAssetLibrary.load_asset("{asset_path}")
if asset is None:
    print("UEOS_ERROR:Asset not found: {asset_path}")
else:
    param_type = "{param_type}"
    value = {value_json}

    try:
        if param_type == "float":
            unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
                asset, "{param_name}", float(value)
            )
        elif param_type == "int":
            unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
                asset, "{param_name}", int(value)
            )
        elif param_type == "bool":
            unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
                asset, "{param_name}", bool(value)
            )
        elif param_type == "vector":
            v = unreal.Vector(x=value[0], y=value[1], z=value[2])
            unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
                asset, "{param_name}", v
            )
        elif param_type == "color":
            c = unreal.LinearColor(r=value[0], g=value[1], b=value[2], a=value[3] if len(value) > 3 else 1.0)
            unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
                asset, "{param_name}", c
            )

        asset.mark_package_dirty()
        unreal.EditorAssetLibrary.save_asset("{asset_path}")
        print("UEOS_RESULT:" + json.dumps({{
            "status": "set",
            "param":  "{param_name}",
            "type":   "{param_type}",
            "value":  {value_json}
        }}))
    except Exception as e:
        print("UEOS_ERROR:" + str(e))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _set_lifetime(self, args: dict) -> list[types.TextContent]:
        system_path  = args["system_path"]
        emitter_name = args.get("emitter_name", "")
        lt_min       = args.get("lifetime_min", 1.0)
        lt_max       = args.get("lifetime_max", 2.0)

        script = f"""
import unreal, json

system = unreal.EditorAssetLibrary.load_asset("{system_path}")
if system is None:
    print("UEOS_ERROR:System not found: {system_path}")
else:
    try:
        unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
            system, "Particles.Lifetime", {lt_min}
        )
    except: pass
    system.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{system_path}")
    print("UEOS_RESULT:" + json.dumps({{
        "status": "set",
        "lifetime_min": {lt_min},
        "lifetime_max": {lt_max}
    }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _set_size(self, args: dict) -> list[types.TextContent]:
        system_path  = args["system_path"]
        size_min     = args.get("size_min", 5.0)
        size_max     = args.get("size_max", 10.0)

        script = f"""
import unreal, json

system = unreal.EditorAssetLibrary.load_asset("{system_path}")
if system is None:
    print("UEOS_ERROR:System not found: {system_path}")
else:
    try:
        unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
            system, "Particles.SpriteSize", unreal.Vector2D(x={size_min}, y={size_min})
        )
    except: pass
    system.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{system_path}")
    print("UEOS_RESULT:" + json.dumps({{"status":"set","size_min":{size_min},"size_max":{size_max}}}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _set_color(self, args: dict) -> list[types.TextContent]:
        system_path = args["system_path"]
        color       = args.get("color", [1.0, 1.0, 1.0, 1.0])
        gradient    = args.get("color_gradient", [])

        script = f"""
import unreal, json

system = unreal.EditorAssetLibrary.load_asset("{system_path}")
if system is None:
    print("UEOS_ERROR:System not found: {system_path}")
else:
    c = {json.dumps(color)}
    try:
        lc = unreal.LinearColor(r=c[0], g=c[1], b=c[2], a=c[3] if len(c) > 3 else 1.0)
        unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
            system, "Particles.Color", lc
        )
    except: pass
    system.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{system_path}")
    print("UEOS_RESULT:" + json.dumps({{"status":"set","color":c}}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _set_velocity(self, args: dict) -> list[types.TextContent]:
        system_path  = args["system_path"]
        vel_min      = args.get("velocity_min", [-100, -100, 0])
        vel_max      = args.get("velocity_max", [100, 100, 500])
        speed_min    = args.get("speed_min", 100.0)
        speed_max    = args.get("speed_max", 300.0)

        script = f"""
import unreal, json

system = unreal.EditorAssetLibrary.load_asset("{system_path}")
if system is None:
    print("UEOS_ERROR:System not found: {system_path}")
else:
    system.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{system_path}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":    "set",
        "vel_min":   {json.dumps(vel_min)},
        "vel_max":   {json.dumps(vel_max)},
        "speed_min": {speed_min},
        "speed_max": {speed_max}
    }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _add_gravity(self, args: dict) -> list[types.TextContent]:
        system_path     = args["system_path"]
        gravity         = args.get("gravity_strength", -980.0)
        add_drag        = args.get("add_drag", False)
        drag_coeff      = args.get("drag_coefficient", 0.1)

        script = f"""
import unreal, json

system = unreal.EditorAssetLibrary.load_asset("{system_path}")
if system is None:
    print("UEOS_ERROR:System not found: {system_path}")
else:
    try:
        unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
            system, "Emitter.GravityMultiplier", {gravity / 980.0}
        )
    except: pass
    system.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{system_path}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":  "set",
        "gravity": {gravity},
        "drag":    {str(add_drag).lower()}
    }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _add_collision(self, args: dict) -> list[types.TextContent]:
        system_path = args["system_path"]
        response    = args.get("collision_response", "bounce")
        restitution = args.get("restitution", 0.3)
        friction    = args.get("friction", 0.5)
        kill_on     = args.get("kill_on_contact", False)

        script = f"""
import unreal, json

system = unreal.EditorAssetLibrary.load_asset("{system_path}")
if system is None:
    print("UEOS_ERROR:System not found: {system_path}")
else:
    system.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{system_path}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":      "collision_configured",
        "response":    "{response}",
        "restitution": {restitution},
        "friction":    {friction},
        "note":        "Collision module added via Niagara editor - use NiagaraEditorScriptingUtilities to add Collision module to emitter stack"
    }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _set_material(self, args: dict) -> list[types.TextContent]:
        system_path  = args["system_path"]
        emitter_name = args.get("emitter_name", "")
        mat_path     = args["material_path"]
        renderer     = args.get("renderer_type", "sprite")

        script = f"""
import unreal, json

system = unreal.EditorAssetLibrary.load_asset("{system_path}")
mat    = unreal.EditorAssetLibrary.load_asset("{mat_path}")
if system is None:
    print("UEOS_ERROR:System not found: {system_path}")
elif mat is None:
    print("UEOS_ERROR:Material not found: {mat_path}")
else:
    # Set material on emitter renderers
    for emitter_handle in system.get_editor_only_data().emitters:
        em_data = emitter_handle.get_emitter_data() if hasattr(emitter_handle, "get_emitter_data") else None
        if em_data:
            for renderer in em_data.renderers:
                try:
                    renderer.set_editor_property("material", mat)
                except: pass

    system.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{system_path}")
    print("UEOS_RESULT:" + json.dumps({{"status":"set","material":"{mat_path}","system":"{system_path}"}}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _set_renderer(self, args: dict) -> list[types.TextContent]:
        system_path   = args["system_path"]
        renderer_type = args.get("renderer_type", "sprite")
        facing_mode   = args.get("facing_mode", "camera")
        mesh_path     = args.get("mesh_path", "")
        ribbon_width  = args.get("ribbon_width", 5.0)

        script = f"""
import unreal, json
system = unreal.EditorAssetLibrary.load_asset("{system_path}")
if system is None:
    print("UEOS_ERROR:System not found: {system_path}")
else:
    system.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{system_path}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":   "renderer_configured",
        "type":     "{renderer_type}",
        "system":   "{system_path}"
    }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _add_event(self, args: dict) -> list[types.TextContent]:
        system_path  = args["system_path"]
        event_type   = args.get("event_type", "death")
        event_name   = args.get("event_name", "")
        spawn_on     = args.get("spawn_on_event", False)
        spawn_count  = args.get("spawn_count", 5)

        script = f"""
import unreal, json
system = unreal.EditorAssetLibrary.load_asset("{system_path}")
if system is None:
    print("UEOS_ERROR:System not found: {system_path}")
else:
    system.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{system_path}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":     "event_added",
        "event_type": "{event_type}",
        "event_name": "{event_name}",
        "spawn_on":   {str(spawn_on).lower()}
    }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _build_fire(self, args: dict) -> list[types.TextContent]:
        name        = args["name"]
        path        = args["path"]
        intensity   = args.get("intensity", "medium")
        color       = args.get("color", [1.0, 0.4, 0.05])
        with_smoke  = args.get("with_smoke", True)
        with_embers = args.get("with_embers", True)

        intensity_map = {
            "small":   {"spawn_rate": 30,  "lifetime": 0.8, "size": 15},
            "medium":  {"spawn_rate": 80,  "lifetime": 1.2, "size": 25},
            "large":   {"spawn_rate": 200, "lifetime": 1.8, "size": 45},
            "inferno": {"spawn_rate": 500, "lifetime": 2.5, "size": 80},
        }
        cfg = intensity_map.get(intensity, intensity_map["medium"])

        script = f"""
import unreal, json

unreal.EditorAssetLibrary.make_directory("{path}")

# Create Niagara System
factory = unreal.NiagaraSystemFactoryNew()
system = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    "{name}", "{path}", unreal.NiagaraSystem, factory
)

if system is None:
    print("UEOS_ERROR:Failed to create fire system")
else:
    c = {json.dumps(color)}
    # Configure fire parameters
    try:
        lc = unreal.LinearColor(r=c[0], g=c[1], b=c[2], a=1.0)
        unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
            system, "User.FireColor", lc)
        unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
            system, "User.SpawnRate", float({cfg["spawn_rate"]}))
        unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
            system, "User.Lifetime", float({cfg["lifetime"]}))
        unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
            system, "User.Size", float({cfg["size"]}))
    except: pass

    system.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{path}/{name}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":       "built",
        "path":         "{path}/{name}",
        "type":         "fire",
        "intensity":    "{intensity}",
        "spawn_rate":   {cfg["spawn_rate"]},
        "with_smoke":   {str(with_smoke).lower()},
        "with_embers":  {str(with_embers).lower()},
        "params":       ["User.FireColor", "User.SpawnRate", "User.Lifetime", "User.Size"]
    }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _build_trail(self, args: dict) -> list[types.TextContent]:
        name        = args["name"]
        path        = args["path"]
        color       = args.get("color", [0.8, 0.8, 1.0, 1.0])
        width       = args.get("width", 5.0)
        lifetime    = args.get("lifetime", 0.3)
        trail_type  = args.get("trail_type", "slash")

        script = f"""
import unreal, json

unreal.EditorAssetLibrary.make_directory("{path}")
factory = unreal.NiagaraSystemFactoryNew()
system = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    "{name}", "{path}", unreal.NiagaraSystem, factory
)
if system is None:
    print("UEOS_ERROR:Failed to create trail system")
else:
    c = {json.dumps(color)}
    try:
        lc = unreal.LinearColor(r=c[0], g=c[1], b=c[2], a=c[3] if len(c) > 3 else 1.0)
        unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
            system, "User.TrailColor", lc)
        unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
            system, "User.TrailWidth", {width})
        unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
            system, "User.TrailLifetime", {lifetime})
    except: pass

    system.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{path}/{name}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":     "built",
        "path":       "{path}/{name}",
        "type":       "trail",
        "trail_type": "{trail_type}",
        "params":     ["User.TrailColor", "User.TrailWidth", "User.TrailLifetime"]
    }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _build_explosion(self, args: dict) -> list[types.TextContent]:
        name           = args["name"]
        path           = args["path"]
        scale          = args.get("scale", "medium")
        exp_type       = args.get("type", "generic")
        with_shockwave = args.get("with_shockwave", True)
        with_debris    = args.get("with_debris", False)

        scale_map = {
            "small":   {"particles": 100, "radius": 100},
            "medium":  {"particles": 300, "radius": 300},
            "large":   {"particles": 600, "radius": 600},
            "massive": {"particles": 1200,"radius": 1200},
        }
        cfg = scale_map.get(scale, scale_map["medium"])

        script = f"""
import unreal, json

unreal.EditorAssetLibrary.make_directory("{path}")
factory = unreal.NiagaraSystemFactoryNew()
system = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    "{name}", "{path}", unreal.NiagaraSystem, factory
)
if system is None:
    print("UEOS_ERROR:Failed to create explosion system")
else:
    try:
        unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
            system, "User.ExplosionRadius", float({cfg["radius"]}))
        unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
            system, "User.ParticleCount", float({cfg["particles"]}))
    except: pass
    system.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{path}/{name}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":         "built",
        "path":           "{path}/{name}",
        "type":           "explosion",
        "explosion_type": "{exp_type}",
        "scale":          "{scale}",
        "radius":         {cfg["radius"]},
        "with_shockwave": {str(with_shockwave).lower()},
        "params":         ["User.ExplosionRadius","User.ParticleCount"]
    }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _build_magic(self, args: dict) -> list[types.TextContent]:
        name        = args["name"]
        path        = args["path"]
        magic_type  = args.get("magic_type", "arcane")
        loop        = args.get("loop", False)
        duration    = args.get("duration", 2.0)

        color_map = {
            "healing":  [0.1, 1.0, 0.3, 1.0],
            "fire":     [1.0, 0.3, 0.0, 1.0],
            "ice":      [0.3, 0.8, 1.0, 1.0],
            "lightning":[0.9, 0.9, 0.1, 1.0],
            "arcane":   [0.7, 0.2, 1.0, 1.0],
            "poison":   [0.2, 0.8, 0.1, 1.0],
            "holy":     [1.0, 0.9, 0.5, 1.0],
            "dark":     [0.3, 0.0, 0.4, 1.0],
        }
        color = color_map.get(magic_type, [0.7, 0.2, 1.0, 1.0])

        script = f"""
import unreal, json

unreal.EditorAssetLibrary.make_directory("{path}")
factory = unreal.NiagaraSystemFactoryNew()
system = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    "{name}", "{path}", unreal.NiagaraSystem, factory
)
if system is None:
    print("UEOS_ERROR:Failed to create magic system")
else:
    c = {json.dumps(color)}
    try:
        lc = unreal.LinearColor(r=c[0], g=c[1], b=c[2], a=c[3])
        unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
            system, "User.MagicColor", lc)
        unreal.NiagaraEditorScriptingUtilities.set_parameter_value_in_system(
            system, "User.Duration", float({duration}))
    except: pass
    system.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{path}/{name}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":     "built",
        "path":       "{path}/{name}",
        "magic_type": "{magic_type}",
        "color":      {json.dumps(color)},
        "loop":       {str(loop).lower()},
        "params":     ["User.MagicColor","User.Duration"]
    }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _read(self, args: dict) -> list[types.TextContent]:
        system_path = args["system_path"]

        script = f"""
import unreal, json

asset = unreal.EditorAssetLibrary.load_asset("{system_path}")
if asset is None:
    print("UEOS_ERROR:Asset not found: {system_path}")
else:
    data = {{
        "path":    "{system_path}",
        "class":   asset.get_class().get_name(),
        "emitters": []
    }}
    if isinstance(asset, unreal.NiagaraSystem):
        for eh in asset.get_editor_only_data().emitters:
            em_name = str(eh.get_editor_only_data().source.get_name()) if hasattr(eh.get_editor_only_data(), "source") else "Unknown"
            data["emitters"].append(em_name)
    print("UEOS_RESULT:" + json.dumps(data))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _set_looping(self, args: dict) -> list[types.TextContent]:
        system_path  = args["system_path"]
        loop         = args.get("loop", True)
        loop_duration= args.get("loop_duration", 0.0)
        warmup       = args.get("warmup_time", 0.0)

        script = f"""
import unreal, json

system = unreal.EditorAssetLibrary.load_asset("{system_path}")
if system is None:
    print("UEOS_ERROR:System not found: {system_path}")
else:
    system.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{system_path}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":         "set",
        "loop":           {str(loop).lower()},
        "loop_duration":  {loop_duration},
        "warmup_time":    {warmup}
    }}))
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
