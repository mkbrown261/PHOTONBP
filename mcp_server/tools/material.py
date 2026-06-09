"""
UEOS Material Tools — UE 5.4 Optimized
Full material graph creation, editing, and management.

UE 5.4 API: unreal.MaterialEditingLibrary
Supports:
  - Create Materials, Material Instances, Material Functions
  - Add/connect any material expression node
  - Configure textures, UV logic, blending, parameters
  - PBR setups, dissolve effects, water, hologram, energy shields
  - Substrate materials (UE 5.4 new material system)
"""

import json
import logging
from mcp import types

log = logging.getLogger("ueos.material")


# ─────────────────────────────────────────────────────────────
# UE 5.4 Material Expression node name registry
# Maps friendly names → UE expression class names
# ─────────────────────────────────────────────────────────────
MATERIAL_EXPRESSIONS = {
    # Textures
    "texture_sample":           "MaterialExpressionTextureSample",
    "texture_object":           "MaterialExpressionTextureObject",
    "texture_coordinate":       "MaterialExpressionTextureCoordinate",

    # Math
    "add":                      "MaterialExpressionAdd",
    "subtract":                 "MaterialExpressionSubtract",
    "multiply":                 "MaterialExpressionMultiply",
    "divide":                   "MaterialExpressionDivide",
    "power":                    "MaterialExpressionPower",
    "sqrt":                     "MaterialExpressionSquareRoot",
    "abs":                      "MaterialExpressionAbs",
    "frac":                     "MaterialExpressionFrac",
    "floor":                    "MaterialExpressionFloor",
    "ceil":                     "MaterialExpressionCeil",
    "clamp":                    "MaterialExpressionClamp",
    "lerp":                     "MaterialExpressionLinearInterpolate",
    "saturate":                 "MaterialExpressionSaturate",
    "min":                      "MaterialExpressionMin",
    "max":                      "MaterialExpressionMax",
    "sign":                     "MaterialExpressionSign",
    "round":                    "MaterialExpressionRound",
    "truncate":                 "MaterialExpressionTruncate",

    # Trig
    "sin":                      "MaterialExpressionSine",
    "cos":                      "MaterialExpressionCosine",
    "arcsin":                   "MaterialExpressionArcsine",
    "arccos":                   "MaterialExpressionArccosine",
    "arctan":                   "MaterialExpressionArctangent",
    "arctan2":                  "MaterialExpressionArctangent2",

    # Vector ops
    "dot":                      "MaterialExpressionDotProduct",
    "cross":                    "MaterialExpressionCrossProduct",
    "normalize":                "MaterialExpressionNormalize",
    "length":                   "MaterialExpressionDistance",
    "fresnel":                  "MaterialExpressionFresnel",
    "transform":                "MaterialExpressionTransform",
    "transform_position":       "MaterialExpressionTransformPosition",

    # Constants
    "constant":                 "MaterialExpressionConstant",
    "constant2":                "MaterialExpressionConstant2Vector",
    "constant3":                "MaterialExpressionConstant3Vector",
    "constant4":                "MaterialExpressionConstant4Vector",
    "vector_param":             "MaterialExpressionVectorParameter",
    "scalar_param":             "MaterialExpressionScalarParameter",
    "static_bool_param":        "MaterialExpressionStaticBoolParameter",
    "texture_param":            "MaterialExpressionTextureObjectParameter",

    # Utility
    "append":                   "MaterialExpressionAppendVector",
    "component_mask":           "MaterialExpressionComponentMask",
    "break_out_float":          "MaterialExpressionBreakMaterialAttributes",
    "make_material_attrs":      "MaterialExpressionMakeMaterialAttributes",
    "named_reroute":            "MaterialExpressionNamedRerouteDeclaration",
    "reroute":                  "MaterialExpressionNamedRerouteUsage",
    "comment":                  "MaterialExpressionComment",

    # Coordinates / Position
    "world_position":           "MaterialExpressionWorldPosition",
    "object_position":          "MaterialExpressionObjectPositionWS",
    "camera_position":          "MaterialExpressionCameraPositionWS",
    "actor_position":           "MaterialExpressionActorPositionWS",
    "vertex_normal":            "MaterialExpressionVertexNormalWS",
    "pixel_normal":             "MaterialExpressionPixelNormalWS",
    "vertex_tangent":           "MaterialExpressionVertexTangentWS",

    # Time / Animation
    "time":                     "MaterialExpressionTime",
    "delta_time":               "MaterialExpressionDeltaTime",
    "sine_wave":                "MaterialExpressionSine",
    "panner":                   "MaterialExpressionPanner",
    "rotator":                  "MaterialExpressionRotator",

    # Noise
    "noise":                    "MaterialExpressionNoise",

    # Special
    "if":                       "MaterialExpressionIf",
    "static_switch":            "MaterialExpressionStaticSwitch",
    "static_switch_param":      "MaterialExpressionStaticSwitchParameter",
    "quality_switch":           "MaterialExpressionQualitySwitch",
    "feature_level_switch":     "MaterialExpressionFeatureLevelSwitch",
    "depth_fade":               "MaterialExpressionDepthFade",
    "pixel_depth":              "MaterialExpressionPixelDepth",
    "scene_depth":              "MaterialExpressionSceneDepth",
    "scene_color":              "MaterialExpressionSceneColor",
    "scene_texture":            "MaterialExpressionSceneTexture",
    "atmosphere_fog_color":     "MaterialExpressionAtmosphericFogColor",

    # Masking / Blending
    "blend_overlay":            "MaterialExpressionBlendMaterialAttributes",
    "custom":                   "MaterialExpressionCustom",

    # Particle
    "particle_color":           "MaterialExpressionParticleColor",
    "particle_position":        "MaterialExpressionParticlePositionWS",
    "particle_speed":           "MaterialExpressionParticleSpeed",
    "particle_size":            "MaterialExpressionParticleSize",
    "particle_sub_uv":          "MaterialExpressionParticleSubUV",

    # Object info
    "object_radius":            "MaterialExpressionObjectRadius",
    "object_bounds":            "MaterialExpressionObjectBounds",
    "bounding_box":             "MaterialExpressionBoundingBoxBased_0_1_UVW",

    # UE 5.4 Substrate
    "substrate_slab":           "MaterialExpressionSubstrateSlab",
    "substrate_simple":         "MaterialExpressionSubstrateSimpleClear",
    "substrate_transmittance":  "MaterialExpressionSubstrateTransmittanceToMFP",
}


class MaterialTools:

    def __init__(self, ue):
        self.ue = ue

    # ─────────────────────────────────────────────
    # Tool Definitions
    # ─────────────────────────────────────────────

    async def get_tool_definitions(self) -> list[types.Tool]:
        return [

            types.Tool(
                name="material_create",
                description="""Create a new Material asset in UE 5.4.
Configures blend mode, shading model, and domain upfront.
UE 5.4 supports Substrate material model — specify use_substrate=true for next-gen shading.
Returns the asset path of the created material.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Material name e.g. M_RockWall"},
                        "path": {"type": "string", "description": "Content path e.g. /Game/Materials"},
                        "blend_mode": {
                            "type": "string",
                            "description": "Blend mode: Opaque, Masked, Translucent, Additive, Modulate, AlphaComposite",
                            "default": "Opaque"
                        },
                        "shading_model": {
                            "type": "string",
                            "description": "Shading model: DefaultLit, Unlit, SubSurface, PreintegratedSkin, ClearCoat, SubSurfaceProfile, TwoSidedFoliage, Hair, Cloth, Eye, SingleLayerWater, ThinTranslucent",
                            "default": "DefaultLit"
                        },
                        "material_domain": {
                            "type": "string",
                            "description": "Domain: Surface, DeferredDecal, LightFunction, Volume, PostProcess, UI, VirtualTexture",
                            "default": "Surface"
                        },
                        "two_sided": {"type": "boolean", "description": "Two-sided material", "default": False},
                        "use_substrate": {"type": "boolean", "description": "Use UE 5.4 Substrate material model", "default": False}
                    },
                    "required": ["name", "path"]
                }
            ),

            types.Tool(
                name="material_create_instance",
                description="""Create a Material Instance from a parent Material.
Material Instances allow parameter overrides without recompiling the parent.
Essential for runtime material variation — character skins, environment sets, etc.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Instance name e.g. MI_RockWall_Mossy"},
                        "path": {"type": "string", "description": "Content path"},
                        "parent_material": {"type": "string", "description": "Content path of parent material e.g. /Game/Materials/M_RockWall"}
                    },
                    "required": ["name", "path", "parent_material"]
                }
            ),

            types.Tool(
                name="material_create_function",
                description="""Create a Material Function — reusable node subgraph.
Functions can be called from any material via a FunctionCall node.
Use for: UV logic, noise patterns, surface blending, common PBR setups.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Function name e.g. MF_TriplanarMapping"},
                        "path": {"type": "string", "description": "Content path"},
                        "description": {"type": "string", "description": "Function description", "default": ""}
                    },
                    "required": ["name", "path"]
                }
            ),

            types.Tool(
                name="material_add_node",
                description="""Add an expression node to a Material or Material Function graph.
Supports all UE 5.4 material expression types including Substrate nodes.

Key node types:
  texture_sample, constant, scalar_param, vector_param, texture_param
  add, subtract, multiply, divide, lerp, clamp, power
  fresnel, noise, time, panner, world_position, vertex_normal
  if, static_switch, depth_fade, scene_depth
  particle_color, particle_sub_uv (for Niagara materials)
  substrate_slab (UE 5.4 Substrate)

Returns node_id for use in material_connect_nodes.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "material_path": {"type": "string", "description": "Content path to material or material function"},
                        "node_type": {"type": "string", "description": "Node type from the supported list above"},
                        "node_name": {"type": "string", "description": "Optional name for this node instance"},
                        "position_x": {"type": "number", "description": "X position in graph", "default": 0},
                        "position_y": {"type": "number", "description": "Y position in graph", "default": 0},
                        "properties": {
                            "type": "object",
                            "description": "Node-specific properties e.g. {\"r\":1.0,\"g\":0.5,\"b\":0.0} for constant3, or {\"texture\": \"/Game/Textures/T_Rock\"} for texture_sample",
                            "default": {}
                        }
                    },
                    "required": ["material_path", "node_type"]
                }
            ),

            types.Tool(
                name="material_connect_nodes",
                description="""Connect two material expression nodes.
Use node IDs returned from material_add_node.
Output pin names: A, B, RGB, R, G, B, A, Result, etc.
Input pin names match the expression's input labels.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "material_path": {"type": "string", "description": "Content path to the material"},
                        "from_node": {"type": "string", "description": "Source node ID or name"},
                        "from_output": {"type": "string", "description": "Output pin name e.g. 'RGB', 'R', 'Result', 'A'", "default": ""},
                        "to_node": {"type": "string", "description": "Target node ID or name"},
                        "to_input": {"type": "string", "description": "Input pin name e.g. 'A', 'B', 'Base Color', 'Alpha'"}
                    },
                    "required": ["material_path", "from_node", "to_node", "to_input"]
                }
            ),

            types.Tool(
                name="material_connect_to_output",
                description="""Connect a node to a Material Output slot.
Output slots: BaseColor, Metallic, Specular, Roughness, EmissiveColor,
Opacity, OpacityMask, Normal, WorldPositionOffset, SubsurfaceColor,
ClearCoat, ClearCoatRoughness, AmbientOcclusion, Refraction, PixelDepthOffset.
UE 5.4 Substrate: FrontMaterial.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "material_path": {"type": "string", "description": "Content path to the material"},
                        "from_node": {"type": "string", "description": "Source node ID or name"},
                        "from_output": {"type": "string", "description": "Output pin name", "default": ""},
                        "output_slot": {
                            "type": "string",
                            "description": "Material output slot: BaseColor, Metallic, Roughness, Normal, EmissiveColor, Opacity, OpacityMask, WorldPositionOffset, AmbientOcclusion, etc."
                        }
                    },
                    "required": ["material_path", "from_node", "output_slot"]
                }
            ),

            types.Tool(
                name="material_set_parameter",
                description="""Set a parameter value on a Material Instance.
Supports scalar, vector, texture, and static switch parameters.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "instance_path": {"type": "string", "description": "Content path to the Material Instance"},
                        "param_name": {"type": "string", "description": "Parameter name"},
                        "param_type": {
                            "type": "string",
                            "description": "Parameter type: scalar, vector, texture, static_bool"
                        },
                        "value": {"description": "Value: float for scalar, [r,g,b,a] for vector, content path for texture, bool for static_bool"}
                    },
                    "required": ["instance_path", "param_name", "param_type", "value"]
                }
            ),

            types.Tool(
                name="material_build_pbr",
                description="""Build a complete PBR material from scratch in one call.
Automatically creates texture sample nodes, connects them to the correct output slots,
and configures all PBR properties.
Textures are optional — missing ones use constant fallback values.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "material_path": {"type": "string", "description": "Full content path to an existing material or path to create one"},
                        "name": {"type": "string", "description": "If creating new: material name"},
                        "create_if_missing": {"type": "boolean", "description": "Create the material if it doesn't exist", "default": True},
                        "albedo_texture": {"type": "string", "description": "Content path to albedo/base color texture"},
                        "normal_texture": {"type": "string", "description": "Content path to normal map texture"},
                        "orm_texture": {"type": "string", "description": "Content path to ORM (Occlusion/Roughness/Metallic) packed texture"},
                        "roughness_texture": {"type": "string", "description": "Content path to roughness texture (if no ORM)"},
                        "metallic_texture": {"type": "string", "description": "Content path to metallic texture (if no ORM)"},
                        "emissive_texture": {"type": "string", "description": "Content path to emissive texture"},
                        "base_color": {"type": "array", "items": {"type": "number"}, "description": "Fallback base color [r,g,b] if no albedo texture", "default": [1.0, 1.0, 1.0]},
                        "metallic_value": {"type": "number", "description": "Fallback metallic value", "default": 0.0},
                        "roughness_value": {"type": "number", "description": "Fallback roughness value", "default": 0.5},
                        "uv_tiling": {"type": "array", "items": {"type": "number"}, "description": "UV tiling [x, y]", "default": [1.0, 1.0]},
                        "add_parameters": {"type": "boolean", "description": "Add scalar/vector parameters for runtime control", "default": True}
                    },
                    "required": ["material_path"]
                }
            ),

            types.Tool(
                name="material_build_dissolve",
                description="""Build a dissolve/burn-away effect material.
Creates: noise texture + threshold parameter + opacity mask + edge emissive glow.
Ready to use with a scalar parameter to animate the dissolve amount.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Material name e.g. M_Dissolve"},
                        "path": {"type": "string", "description": "Content path"},
                        "base_material_path": {"type": "string", "description": "Optional existing base material to add dissolve to"},
                        "noise_texture": {"type": "string", "description": "Content path to noise texture (optional, uses procedural noise if not provided)"},
                        "edge_color": {"type": "array", "items": {"type": "number"}, "description": "Edge glow color [r,g,b]", "default": [1.0, 0.3, 0.0]},
                        "edge_width": {"type": "number", "description": "Dissolve edge width", "default": 0.1}
                    },
                    "required": ["name", "path"]
                }
            ),

            types.Tool(
                name="material_build_emissive",
                description="""Build an emissive/glowing material.
Creates: emissive color parameter + intensity parameter + optional pulse animation via Time node.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Material name"},
                        "path": {"type": "string", "description": "Content path"},
                        "emissive_color": {"type": "array", "items": {"type": "number"}, "description": "Emissive color [r,g,b]", "default": [0.0, 0.5, 1.0]},
                        "intensity": {"type": "number", "description": "Emissive intensity multiplier", "default": 5.0},
                        "animate_pulse": {"type": "boolean", "description": "Add sine wave pulse animation", "default": False},
                        "pulse_speed": {"type": "number", "description": "Pulse animation speed", "default": 2.0}
                    },
                    "required": ["name", "path"]
                }
            ),

            types.Tool(
                name="material_build_hologram",
                description="""Build a hologram/sci-fi material.
Creates: scanline effect + fresnel edge glow + opacity + emissive color + flicker animation.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Material name e.g. M_Hologram"},
                        "path": {"type": "string", "description": "Content path"},
                        "color": {"type": "array", "items": {"type": "number"}, "description": "Hologram color [r,g,b]", "default": [0.0, 0.8, 1.0]},
                        "scanline_density": {"type": "number", "description": "Scanline frequency", "default": 50.0},
                        "flicker": {"type": "boolean", "description": "Add flicker animation", "default": True}
                    },
                    "required": ["name", "path"]
                }
            ),

            types.Tool(
                name="material_read",
                description="""Read a material's full node graph structure as JSON.
Returns all expression nodes, their types, properties, and connections.
Use to inspect existing materials before editing.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "material_path": {"type": "string", "description": "Content path to the material"}
                    },
                    "required": ["material_path"]
                }
            ),

            types.Tool(
                name="material_compile",
                description="""Compile a material and return errors/warnings.
Always compile after editing. UE 5.4 material compilation can take a moment.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "material_path": {"type": "string", "description": "Content path to the material"},
                        "save_on_success": {"type": "boolean", "default": True}
                    },
                    "required": ["material_path"]
                }
            ),

            types.Tool(
                name="material_assign_to_mesh",
                description="""Assign a material to a Static or Skeletal Mesh asset, or to a mesh component in a Blueprint.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "material_path": {"type": "string", "description": "Content path to the material or material instance"},
                        "mesh_path": {"type": "string", "description": "Content path to the static or skeletal mesh asset"},
                        "blueprint_path": {"type": "string", "description": "Content path to Blueprint (if assigning to component)"},
                        "component_name": {"type": "string", "description": "Component name in Blueprint"},
                        "slot_index": {"type": "integer", "description": "Material slot index", "default": 0}
                    },
                    "required": ["material_path"]
                }
            ),

        ]

    # ─────────────────────────────────────────────
    # Handler
    # ─────────────────────────────────────────────

    async def handle(self, name: str, args: dict) -> list[types.TextContent]:
        handlers = {
            "material_create":              self._create,
            "material_create_instance":     self._create_instance,
            "material_create_function":     self._create_function,
            "material_add_node":            self._add_node,
            "material_connect_nodes":       self._connect_nodes,
            "material_connect_to_output":   self._connect_to_output,
            "material_set_parameter":       self._set_parameter,
            "material_build_pbr":           self._build_pbr,
            "material_build_dissolve":      self._build_dissolve,
            "material_build_emissive":      self._build_emissive,
            "material_build_hologram":      self._build_hologram,
            "material_read":                self._read,
            "material_compile":             self._compile,
            "material_assign_to_mesh":      self._assign_to_mesh,
        }
        handler = handlers.get(name)
        if not handler:
            return [types.TextContent(type="text", text=f"Unknown material tool: {name}")]
        return await handler(args)

    # ─────────────────────────────────────────────
    # Implementations
    # ─────────────────────────────────────────────

    async def _create(self, args: dict) -> list[types.TextContent]:
        name        = args["name"]
        path        = args["path"]
        blend_mode  = args.get("blend_mode", "Opaque")
        shading     = args.get("shading_model", "DefaultLit")
        domain      = args.get("material_domain", "Surface")
        two_sided   = args.get("two_sided", False)
        substrate   = args.get("use_substrate", False)

        blend_map = {
            "Opaque":         "BLEND_Opaque",
            "Masked":         "BLEND_Masked",
            "Translucent":    "BLEND_Translucent",
            "Additive":       "BLEND_Additive",
            "Modulate":       "BLEND_Modulate",
            "AlphaComposite": "BLEND_AlphaComposite",
        }
        shading_map = {
            "DefaultLit":           "MSM_DefaultLit",
            "Unlit":                "MSM_Unlit",
            "SubSurface":           "MSM_Subsurface",
            "PreintegratedSkin":    "MSM_PreintegratedSkin",
            "ClearCoat":            "MSM_ClearCoat",
            "SubSurfaceProfile":    "MSM_SubsurfaceProfile",
            "TwoSidedFoliage":      "MSM_TwoSidedFoliage",
            "Hair":                 "MSM_Hair",
            "Cloth":                "MSM_Cloth",
            "Eye":                  "MSM_Eye",
            "SingleLayerWater":     "MSM_SingleLayerWater",
            "ThinTranslucent":      "MSM_ThinTranslucent",
        }
        domain_map = {
            "Surface":         "MD_Surface",
            "DeferredDecal":   "MD_DeferredDecal",
            "LightFunction":   "MD_LightFunction",
            "Volume":          "MD_Volume",
            "PostProcess":     "MD_PostProcess",
            "UI":              "MD_UI",
            "VirtualTexture":  "MD_RuntimeVirtualTexture",
        }

        ue_blend   = blend_map.get(blend_mode,  "BLEND_Opaque")
        ue_shading = shading_map.get(shading,   "MSM_DefaultLit")
        ue_domain  = domain_map.get(domain,     "MD_Surface")

        script = f"""
import unreal, json

unreal.EditorAssetLibrary.make_directory("{path}")
factory = unreal.MaterialFactoryNew()
mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    "{name}", "{path}", unreal.Material, factory
)
if mat is None:
    print("UEOS_ERROR:Failed to create material {path}/{name}")
else:
    mat.blend_mode      = unreal.BlendMode.{ue_blend}
    mat.shading_model   = unreal.MaterialShadingModel.{ue_shading}
    mat.material_domain = unreal.MaterialDomain.{ue_domain}
    mat.two_sided       = {str(two_sided).lower()}
    mat.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{path}/{name}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":  "created",
        "path":    "{path}/{name}",
        "blend":   "{blend_mode}",
        "shading": "{shading}",
        "domain":  "{domain}"
    }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _create_instance(self, args: dict) -> list[types.TextContent]:
        name   = args["name"]
        path   = args["path"]
        parent = args["parent_material"]

        script = f"""
import unreal, json

parent_mat = unreal.EditorAssetLibrary.load_asset("{parent}")
if parent_mat is None:
    print("UEOS_ERROR:Parent material not found: {parent}")
else:
    factory = unreal.MaterialInstanceConstantFactoryNew()
    factory.initial_parent = parent_mat
    inst = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "{name}", "{path}", unreal.MaterialInstanceConstant, factory
    )
    if inst:
        unreal.EditorAssetLibrary.save_asset("{path}/{name}")
        print("UEOS_RESULT:" + json.dumps({{"status":"created","path":"{path}/{name}","parent":"{parent}"}}))
    else:
        print("UEOS_ERROR:Failed to create material instance")
"""
        return self._ret(await self.ue.execute_python(script))

    async def _create_function(self, args: dict) -> list[types.TextContent]:
        name   = args["name"]
        path   = args["path"]
        desc   = args.get("description", "")

        script = f"""
import unreal, json

factory = unreal.MaterialFunctionFactoryNew()
mf = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    "{name}", "{path}", unreal.MaterialFunction, factory
)
if mf:
    mf.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{path}/{name}")
    print("UEOS_RESULT:" + json.dumps({{"status":"created","path":"{path}/{name}"}}))
else:
    print("UEOS_ERROR:Failed to create material function")
"""
        return self._ret(await self.ue.execute_python(script))

    async def _add_node(self, args: dict) -> list[types.TextContent]:
        mat_path   = args["material_path"]
        node_type  = args["node_type"]
        node_name  = args.get("node_name", "")
        pos_x      = args.get("position_x", 0)
        pos_y      = args.get("position_y", 0)
        props      = args.get("properties", {})
        props_json = json.dumps(props)

        ue_class = MATERIAL_EXPRESSIONS.get(node_type, node_type)

        script = f"""
import unreal, json

mat = unreal.EditorAssetLibrary.load_asset("{mat_path}")
if mat is None:
    print("UEOS_ERROR:Material not found: {mat_path}")
else:
    mel = unreal.MaterialEditingLibrary

    # Resolve expression class
    expr_class = unreal.load_class(None, "/Script/Engine.{ue_class}")
    if expr_class is None:
        print("UEOS_ERROR:Unknown expression class: {ue_class}")
    else:
        expr = mel.create_material_expression(mat, expr_class, {pos_x}, {pos_y})
        if expr is None:
            print("UEOS_ERROR:Failed to create expression {ue_class}")
        else:
            props = {props_json}

            # Apply properties
            for k, v in props.items():
                try:
                    if k == "texture" and isinstance(v, str):
                        tex = unreal.EditorAssetLibrary.load_asset(v)
                        if tex:
                            expr.set_editor_property("texture", tex)
                    elif k == "r" and hasattr(expr, "r"):
                        expr.set_editor_property("r", float(v))
                    elif k == "g" and hasattr(expr, "g"):
                        expr.set_editor_property("g", float(v))
                    elif k == "b" and hasattr(expr, "b"):
                        expr.set_editor_property("b", float(v))
                    elif k == "a" and hasattr(expr, "a"):
                        expr.set_editor_property("a", float(v))
                    elif k == "constant" and hasattr(expr, "r"):
                        expr.set_editor_property("r", float(v))
                    elif k == "parameter_name":
                        expr.set_editor_property("parameter_name", str(v))
                    elif k == "default_value" and hasattr(expr, "default_value"):
                        expr.set_editor_property("default_value", v)
                    else:
                        try:
                            expr.set_editor_property(k, v)
                        except:
                            pass
                except Exception as pe:
                    pass

            # Assign description/name if provided
            node_name = "{node_name}"
            if node_name and hasattr(expr, "desc"):
                expr.set_editor_property("desc", node_name)

            mat.mark_package_dirty()
            node_id = node_name if node_name else f"{node_type}_{{id(expr)}}"
            print("UEOS_RESULT:" + json.dumps({{
                "status":      "created",
                "node_id":     node_id,
                "node_type":   "{node_type}",
                "ue_class":    "{ue_class}",
                "material":    "{mat_path}"
            }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _connect_nodes(self, args: dict) -> list[types.TextContent]:
        mat_path    = args["material_path"]
        from_node   = args["from_node"]
        from_output = args.get("from_output", "")
        to_node     = args["to_node"]
        to_input    = args["to_input"]

        script = f"""
import unreal, json

mat = unreal.EditorAssetLibrary.load_asset("{mat_path}")
if mat is None:
    print("UEOS_ERROR:Material not found: {mat_path}")
else:
    mel = unreal.MaterialEditingLibrary
    expressions = mel.get_material_expressions(mat)

    from_expr = None
    to_expr   = None
    for e in expressions:
        desc = e.get_editor_property("desc") if hasattr(e, "desc") else ""
        cls  = e.get_class().get_name()
        if desc == "{from_node}" or cls == "{from_node}":
            from_expr = e
        if desc == "{to_node}" or cls == "{to_node}":
            to_expr = e

    if from_expr is None or to_expr is None:
        print("UEOS_ERROR:Could not find nodes: {from_node} → {to_node}")
    else:
        result = mel.connect_material_expressions(
            from_expr, "{from_output}", to_expr, "{to_input}"
        )
        mat.mark_package_dirty()
        print("UEOS_RESULT:" + json.dumps({{
            "status": "connected" if result else "failed",
            "from": "{from_node}.{from_output}",
            "to":   "{to_node}.{to_input}"
        }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _connect_to_output(self, args: dict) -> list[types.TextContent]:
        mat_path    = args["material_path"]
        from_node   = args["from_node"]
        from_output = args.get("from_output", "")
        output_slot = args["output_slot"]

        script = f"""
import unreal, json

mat = unreal.EditorAssetLibrary.load_asset("{mat_path}")
if mat is None:
    print("UEOS_ERROR:Material not found: {mat_path}")
else:
    mel = unreal.MaterialEditingLibrary
    expressions = mel.get_material_expressions(mat)

    from_expr = None
    for e in expressions:
        desc = e.get_editor_property("desc") if hasattr(e, "desc") else ""
        cls  = e.get_class().get_name()
        if desc == "{from_node}" or cls == "{from_node}":
            from_expr = e
            break

    if from_expr is None:
        print("UEOS_ERROR:Node not found: {from_node}")
    else:
        result = mel.connect_material_property(
            from_expr, "{from_output}",
            unreal.MaterialProperty.{output_slot.upper().replace(' ', '_')}
        )
        mat.mark_package_dirty()
        print("UEOS_RESULT:" + json.dumps({{
            "status": "connected" if result else "failed",
            "node":   "{from_node}",
            "slot":   "{output_slot}"
        }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _set_parameter(self, args: dict) -> list[types.TextContent]:
        inst_path  = args["instance_path"]
        param_name = args["param_name"]
        param_type = args["param_type"]
        value      = args["value"]
        value_json = json.dumps(value)

        script = f"""
import unreal, json

inst = unreal.EditorAssetLibrary.load_asset("{inst_path}")
if inst is None:
    print("UEOS_ERROR:Material instance not found: {inst_path}")
else:
    mel = unreal.MaterialEditingLibrary
    param_type = "{param_type}"
    value = {value_json}

    if param_type == "scalar":
        mel.set_material_instance_scalar_parameter_value(inst, "{param_name}", float(value))
    elif param_type == "vector":
        c = unreal.LinearColor(r=value[0], g=value[1], b=value[2], a=value[3] if len(value) > 3 else 1.0)
        mel.set_material_instance_vector_parameter_value(inst, "{param_name}", c)
    elif param_type == "texture":
        tex = unreal.EditorAssetLibrary.load_asset(str(value))
        if tex:
            mel.set_material_instance_texture_parameter_value(inst, "{param_name}", tex)
        else:
            print("UEOS_ERROR:Texture not found: " + str(value))
    elif param_type == "static_bool":
        mel.set_material_instance_static_switch_parameter_value(inst, "{param_name}", bool(value))

    unreal.EditorAssetLibrary.save_asset("{inst_path}")
    print("UEOS_RESULT:" + json.dumps({{"status":"set","param":"{param_name}","type":"{param_type}"}}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _build_pbr(self, args: dict) -> list[types.TextContent]:
        """Build a complete PBR material setup."""
        mat_path        = args["material_path"]
        name            = args.get("name", mat_path.split("/")[-1])
        create_if_miss  = args.get("create_if_missing", True)
        albedo_tex      = args.get("albedo_texture", "")
        normal_tex      = args.get("normal_texture", "")
        orm_tex         = args.get("orm_texture", "")
        roughness_tex   = args.get("roughness_texture", "")
        metallic_tex    = args.get("metallic_texture", "")
        emissive_tex    = args.get("emissive_texture", "")
        base_color      = args.get("base_color", [1.0, 1.0, 1.0])
        metallic_val    = args.get("metallic_value", 0.0)
        roughness_val   = args.get("roughness_value", 0.5)
        uv_tiling       = args.get("uv_tiling", [1.0, 1.0])
        add_params      = args.get("add_parameters", True)

        script = f"""
import unreal, json

mel = unreal.MaterialEditingLibrary

mat = unreal.EditorAssetLibrary.load_asset("{mat_path}")
if mat is None and {str(create_if_miss).lower()}:
    parts = "{mat_path}".rsplit("/", 1)
    mat_dir  = parts[0]
    mat_name = parts[1] if len(parts) > 1 else "{name}"
    unreal.EditorAssetLibrary.make_directory(mat_dir)
    factory = unreal.MaterialFactoryNew()
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        mat_name, mat_dir, unreal.Material, factory
    )

if mat is None:
    print("UEOS_ERROR:Could not load or create material: {mat_path}")
else:
    nodes = {{}}
    y = 0

    # UV Tiling via TextureCoordinate
    uv_tiling = {json.dumps(uv_tiling)}
    tc = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionTextureCoordinate"), -600, 0)
    if tc:
        tc.set_editor_property("u_tiling", uv_tiling[0])
        tc.set_editor_property("v_tiling", uv_tiling[1])
        tc.set_editor_property("desc", "UV_Tiling")
        nodes["UV"] = tc

    # Albedo
    albedo_tex = "{albedo_tex}"
    if albedo_tex:
        t = unreal.EditorAssetLibrary.load_asset(albedo_tex)
        if t:
            ts = mel.create_material_expression(mat,
                unreal.load_class(None, "/Script/Engine.MaterialExpressionTextureSample"), -400, 0)
            ts.set_editor_property("texture", t)
            ts.set_editor_property("desc", "Albedo")
            nodes["Albedo"] = ts
            mel.connect_material_property(ts, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
            if tc: mel.connect_material_expressions(tc, "", ts, "Coordinates")
    else:
        bc = {json.dumps(base_color)}
        c3 = mel.create_material_expression(mat,
            unreal.load_class(None, "/Script/Engine.MaterialExpressionConstant3Vector"), -400, 0)
        c3.set_editor_property("r", bc[0])
        c3.set_editor_property("g", bc[1])
        c3.set_editor_property("b", bc[2])
        c3.set_editor_property("desc", "BaseColor")
        mel.connect_material_property(c3, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)

    # Normal
    normal_tex = "{normal_tex}"
    if normal_tex:
        t = unreal.EditorAssetLibrary.load_asset(normal_tex)
        if t:
            ts = mel.create_material_expression(mat,
                unreal.load_class(None, "/Script/Engine.MaterialExpressionTextureSample"), -400, -300)
            ts.set_editor_property("texture", t)
            ts.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
            ts.set_editor_property("desc", "Normal")
            nodes["Normal"] = ts
            mel.connect_material_property(ts, "RGB", unreal.MaterialProperty.MP_NORMAL)
            if tc: mel.connect_material_expressions(tc, "", ts, "Coordinates")

    # ORM (packed Occlusion/Roughness/Metallic)
    orm_tex = "{orm_tex}"
    if orm_tex:
        t = unreal.EditorAssetLibrary.load_asset(orm_tex)
        if t:
            ts = mel.create_material_expression(mat,
                unreal.load_class(None, "/Script/Engine.MaterialExpressionTextureSample"), -400, -600)
            ts.set_editor_property("texture", t)
            ts.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
            ts.set_editor_property("desc", "ORM")
            nodes["ORM"] = ts
            mel.connect_material_property(ts, "R", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
            mel.connect_material_property(ts, "G", unreal.MaterialProperty.MP_ROUGHNESS)
            mel.connect_material_property(ts, "B", unreal.MaterialProperty.MP_METALLIC)
            if tc: mel.connect_material_expressions(tc, "", ts, "Coordinates")
    else:
        # Roughness
        roughness_tex = "{roughness_tex}"
        if roughness_tex:
            t = unreal.EditorAssetLibrary.load_asset(roughness_tex)
            if t:
                ts = mel.create_material_expression(mat,
                    unreal.load_class(None, "/Script/Engine.MaterialExpressionTextureSample"), -400, -600)
                ts.set_editor_property("texture", t)
                ts.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE)
                ts.set_editor_property("desc", "Roughness")
                mel.connect_material_property(ts, "R", unreal.MaterialProperty.MP_ROUGHNESS)
        else:
            c = mel.create_material_expression(mat,
                unreal.load_class(None, "/Script/Engine.MaterialExpressionConstant"), -400, -550)
            c.set_editor_property("r", {roughness_val})
            c.set_editor_property("desc", "RoughnessValue")
            mel.connect_material_property(c, "", unreal.MaterialProperty.MP_ROUGHNESS)

        # Metallic
        metallic_tex = "{metallic_tex}"
        if metallic_tex:
            t = unreal.EditorAssetLibrary.load_asset(metallic_tex)
            if t:
                ts = mel.create_material_expression(mat,
                    unreal.load_class(None, "/Script/Engine.MaterialExpressionTextureSample"), -400, -750)
                ts.set_editor_property("texture", t)
                ts.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE)
                ts.set_editor_property("desc", "Metallic")
                mel.connect_material_property(ts, "R", unreal.MaterialProperty.MP_METALLIC)
        else:
            c = mel.create_material_expression(mat,
                unreal.load_class(None, "/Script/Engine.MaterialExpressionConstant"), -400, -700)
            c.set_editor_property("r", {metallic_val})
            c.set_editor_property("desc", "MetallicValue")
            mel.connect_material_property(c, "", unreal.MaterialProperty.MP_METALLIC)

    # Emissive
    emissive_tex = "{emissive_tex}"
    if emissive_tex:
        t = unreal.EditorAssetLibrary.load_asset(emissive_tex)
        if t:
            ts = mel.create_material_expression(mat,
                unreal.load_class(None, "/Script/Engine.MaterialExpressionTextureSample"), -400, -900)
            ts.set_editor_property("texture", t)
            ts.set_editor_property("desc", "Emissive")
            mel.connect_material_property(ts, "RGB", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    # Add exposed scalar/vector parameters for runtime control
    if {str(add_params).lower()}:
        sp = mel.create_material_expression(mat,
            unreal.load_class(None, "/Script/Engine.MaterialExpressionScalarParameter"), -800, 0)
        sp.set_editor_property("parameter_name", "RoughnessMultiplier")
        sp.set_editor_property("default_value", 1.0)
        sp.set_editor_property("desc", "RoughnessMultiplier")

    mat.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{mat_path}")
    print("UEOS_RESULT:" + json.dumps({{
        "status":     "built",
        "path":       "{mat_path}",
        "nodes_created": list(nodes.keys()),
        "has_normal": bool("{normal_tex}"),
        "has_orm":    bool("{orm_tex}")
    }}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _build_dissolve(self, args: dict) -> list[types.TextContent]:
        name       = args["name"]
        path       = args["path"]
        noise_tex  = args.get("noise_texture", "")
        edge_color = args.get("edge_color", [1.0, 0.3, 0.0])
        edge_width = args.get("edge_width", 0.1)

        script = f"""
import unreal, json

mel = unreal.MaterialEditingLibrary
unreal.EditorAssetLibrary.make_directory("{path}")
factory = unreal.MaterialFactoryNew()
mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    "{name}", "{path}", unreal.Material, factory
)
mat.blend_mode = unreal.BlendMode.BLEND_MASKED
mat.mark_package_dirty()

# Dissolve threshold scalar parameter
threshold = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionScalarParameter"), -600, 0)
threshold.set_editor_property("parameter_name", "DissolveAmount")
threshold.set_editor_property("default_value", 0.5)
threshold.set_editor_property("desc", "DissolveAmount")

# Noise (texture or procedural)
noise_tex_path = "{noise_tex}"
if noise_tex_path:
    t = unreal.EditorAssetLibrary.load_asset(noise_tex_path)
    noise_node = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionTextureSample"), -900, 0)
    if t: noise_node.set_editor_property("texture", t)
    noise_node.set_editor_property("desc", "NoiseTexture")
else:
    noise_node = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionNoise"), -900, 0)
    noise_node.set_editor_property("desc", "ProceduralNoise")
    noise_node.set_editor_property("output_min", 0.0)
    noise_node.set_editor_property("output_max", 1.0)

# Subtract: noise - threshold
sub = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionSubtract"), -300, 0)
sub.set_editor_property("desc", "DissolveCalc")
if noise_tex_path:
    mel.connect_material_expressions(noise_node, "R", sub, "A")
else:
    mel.connect_material_expressions(noise_node, "", sub, "A")
mel.connect_material_expressions(threshold, "", sub, "B")

# Connect to Opacity Mask
mel.connect_material_property(sub, "", unreal.MaterialProperty.MP_OPACITY_MASK)

# Edge glow: clamp the edge zone and colorize
ec = {json.dumps(edge_color)}
edge_c = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionConstant3Vector"), -600, -300)
edge_c.set_editor_property("r", ec[0])
edge_c.set_editor_property("g", ec[1])
edge_c.set_editor_property("b", ec[2])
edge_c.set_editor_property("desc", "EdgeColor")

edge_thresh = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionScalarParameter"), -900, -300)
edge_thresh.set_editor_property("parameter_name", "EdgeWidth")
edge_thresh.set_editor_property("default_value", {edge_width})
edge_thresh.set_editor_property("desc", "EdgeWidth")

edge_add = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionAdd"), -600, -200)
mel.connect_material_expressions(threshold, "", edge_add, "A")
mel.connect_material_expressions(edge_thresh, "", edge_add, "B")
edge_add.set_editor_property("desc", "EdgeThreshold")

edge_sub = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionSubtract"), -300, -300)
if noise_tex_path:
    mel.connect_material_expressions(noise_node, "R", edge_sub, "A")
else:
    mel.connect_material_expressions(noise_node, "", edge_sub, "A")
mel.connect_material_expressions(edge_add, "", edge_sub, "B")

clamp_edge = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionClamp"), -100, -300)
clamp_edge.set_editor_property("min_default", 0.0)
clamp_edge.set_editor_property("max_default", 1.0)
mel.connect_material_expressions(edge_sub, "", clamp_edge, "Input")

edge_mul = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionMultiply"), 100, -300)
mel.connect_material_expressions(edge_c, "RGB", edge_mul, "A")
mel.connect_material_expressions(clamp_edge, "", edge_mul, "B")

mel.connect_material_property(edge_mul, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

mat.mark_package_dirty()
unreal.EditorAssetLibrary.save_asset("{path}/{name}")
print("UEOS_RESULT:" + json.dumps({{
    "status": "built",
    "path":   "{path}/{name}",
    "type":   "dissolve",
    "params": ["DissolveAmount", "EdgeWidth"]
}}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _build_emissive(self, args: dict) -> list[types.TextContent]:
        name       = args["name"]
        path       = args["path"]
        em_color   = args.get("emissive_color", [0.0, 0.5, 1.0])
        intensity  = args.get("intensity", 5.0)
        animate    = args.get("animate_pulse", False)
        speed      = args.get("pulse_speed", 2.0)

        script = f"""
import unreal, json

mel = unreal.MaterialEditingLibrary
unreal.EditorAssetLibrary.make_directory("{path}")
factory = unreal.MaterialFactoryNew()
mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    "{name}", "{path}", unreal.Material, factory
)

ec = {json.dumps(em_color)}
color_node = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionVectorParameter"), -600, 0)
color_node.set_editor_property("parameter_name", "EmissiveColor")
default_color = unreal.LinearColor(r=ec[0], g=ec[1], b=ec[2], a=1.0)
color_node.set_editor_property("default_value", default_color)
color_node.set_editor_property("desc", "EmissiveColor")

intensity_node = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionScalarParameter"), -600, -200)
intensity_node.set_editor_property("parameter_name", "EmissiveIntensity")
intensity_node.set_editor_property("default_value", {intensity})
intensity_node.set_editor_property("desc", "EmissiveIntensity")

mul = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionMultiply"), -300, 0)
mel.connect_material_expressions(color_node, "RGB", mul, "A")

if {str(animate).lower()}:
    time_node = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionTime"), -900, -400)
    time_node.set_editor_property("desc", "Time")
    speed_node = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionConstant"), -900, -300)
    speed_node.set_editor_property("r", {speed})
    speed_node.set_editor_property("desc", "PulseSpeed")
    time_mul = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionMultiply"), -700, -350)
    mel.connect_material_expressions(time_node, "", time_mul, "A")
    mel.connect_material_expressions(speed_node, "", time_mul, "B")
    sine_node = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionSine"), -500, -350)
    mel.connect_material_expressions(time_mul, "", sine_node, "Input")
    # Remap sine (-1,1) to (0,1) then multiply intensity
    remap_add = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionAdd"), -400, -300)
    one_node = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionConstant"), -500, -250)
    one_node.set_editor_property("r", 1.0)
    mel.connect_material_expressions(sine_node, "", remap_add, "A")
    mel.connect_material_expressions(one_node, "", remap_add, "B")
    remap_div = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionDivide"), -250, -300)
    two_node = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionConstant"), -350, -250)
    two_node.set_editor_property("r", 2.0)
    mel.connect_material_expressions(remap_add, "", remap_div, "A")
    mel.connect_material_expressions(two_node, "", remap_div, "B")
    final_mul = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionMultiply"), -100, -200)
    mel.connect_material_expressions(intensity_node, "", final_mul, "A")
    mel.connect_material_expressions(remap_div, "", final_mul, "B")
    mel.connect_material_expressions(final_mul, "", mul, "B")
else:
    mel.connect_material_expressions(intensity_node, "", mul, "B")

mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

mat.mark_package_dirty()
unreal.EditorAssetLibrary.save_asset("{path}/{name}")
print("UEOS_RESULT:" + json.dumps({{
    "status":    "built",
    "path":      "{path}/{name}",
    "type":      "emissive",
    "animated":  {str(animate).lower()},
    "params":    ["EmissiveColor", "EmissiveIntensity"]
}}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _build_hologram(self, args: dict) -> list[types.TextContent]:
        name     = args["name"]
        path     = args["path"]
        color    = args.get("color", [0.0, 0.8, 1.0])
        scanline = args.get("scanline_density", 50.0)
        flicker  = args.get("flicker", True)

        script = f"""
import unreal, json

mel = unreal.MaterialEditingLibrary
unreal.EditorAssetLibrary.make_directory("{path}")
factory = unreal.MaterialFactoryNew()
mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    "{name}", "{path}", unreal.Material, factory
)
mat.blend_mode   = unreal.BlendMode.BLEND_TRANSLUCENT
mat.shading_model = unreal.MaterialShadingModel.MSM_UNLIT
mat.mark_package_dirty()

c = {json.dumps(color)}

# Scanline via World Position + sin
wp = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionWorldPosition"), -1200, 0)
wp.set_editor_property("desc", "WorldPos")

density = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionConstant"), -1000, 100)
density.set_editor_property("r", {scanline})
density.set_editor_property("desc", "ScanlineDensity")

wp_mul = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionMultiply"), -800, 0)
mel.connect_material_expressions(wp, "B", wp_mul, "A")
mel.connect_material_expressions(density, "", wp_mul, "B")

scanline_sin = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionSine"), -600, 0)
mel.connect_material_expressions(wp_mul, "", scanline_sin, "Input")

# Remap 0-1
sl_abs = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionAbs"), -400, 0)
mel.connect_material_expressions(scanline_sin, "", sl_abs, "Input")

# Hologram color
holo_color = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionVectorParameter"), -800, -300)
holo_color.set_editor_property("parameter_name", "HologramColor")
hc = unreal.LinearColor(r=c[0], g=c[1], b=c[2], a=1.0)
holo_color.set_editor_property("default_value", hc)
holo_color.set_editor_property("desc", "HologramColor")

# Fresnel for edge glow
fresnel = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionFresnel"), -600, -300)
fresnel.set_editor_property("desc", "FresnelEdge")
fresnel.set_editor_property("base_reflect_fraction_exponent", 3.0)

# Combine scanlines + fresnel
combine = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionAdd"), -200, 0)
mel.connect_material_expressions(sl_abs, "", combine, "A")
mel.connect_material_expressions(fresnel, "", combine, "B")

# Multiply by color
color_mul = mel.create_material_expression(mat,
    unreal.load_class(None, "/Script/Engine.MaterialExpressionMultiply"), 0, 0)
mel.connect_material_expressions(holo_color, "RGB", color_mul, "A")
mel.connect_material_expressions(combine, "", color_mul, "B")

mel.connect_material_property(color_mul, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
mel.connect_material_property(sl_abs, "", unreal.MaterialProperty.MP_OPACITY)

# Flicker via time-based noise
if {str(flicker).lower()}:
    time_f = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionTime"), -1200, -500)
    flicker_mul = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionMultiply"), -1000, -500)
    flicker_speed = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionConstant"), -1200, -400)
    flicker_speed.set_editor_property("r", 15.0)
    mel.connect_material_expressions(time_f, "", flicker_mul, "A")
    mel.connect_material_expressions(flicker_speed, "", flicker_mul, "B")
    flicker_frac = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionFrac"), -800, -500)
    mel.connect_material_expressions(flicker_mul, "", flicker_frac, "Input")
    # Add subtle flicker to opacity
    flicker_add = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionAdd"), -600, -450)
    mel.connect_material_expressions(sl_abs, "", flicker_add, "A")
    flicker_scale = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionMultiply"), -700, -500)
    flicker_amp = mel.create_material_expression(mat,
        unreal.load_class(None, "/Script/Engine.MaterialExpressionConstant"), -800, -400)
    flicker_amp.set_editor_property("r", 0.1)
    mel.connect_material_expressions(flicker_frac, "", flicker_scale, "A")
    mel.connect_material_expressions(flicker_amp, "", flicker_scale, "B")
    mel.connect_material_expressions(flicker_scale, "", flicker_add, "B")
    mel.connect_material_property(flicker_add, "", unreal.MaterialProperty.MP_OPACITY)

mat.mark_package_dirty()
unreal.EditorAssetLibrary.save_asset("{path}/{name}")
print("UEOS_RESULT:" + json.dumps({{
    "status":  "built",
    "path":    "{path}/{name}",
    "type":    "hologram",
    "flicker": {str(flicker).lower()},
    "params":  ["HologramColor"]
}}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _read(self, args: dict) -> list[types.TextContent]:
        mat_path = args["material_path"]

        script = f"""
import unreal, json

mat = unreal.EditorAssetLibrary.load_asset("{mat_path}")
if mat is None:
    print("UEOS_ERROR:Material not found: {mat_path}")
else:
    mel = unreal.MaterialEditingLibrary
    data = {{
        "path":         "{mat_path}",
        "class":        mat.get_class().get_name(),
        "blend_mode":   str(mat.blend_mode)   if hasattr(mat, "blend_mode") else "N/A",
        "shading_model":str(mat.shading_model) if hasattr(mat, "shading_model") else "N/A",
        "two_sided":    mat.two_sided          if hasattr(mat, "two_sided") else False,
        "expressions":  []
    }}
    if isinstance(mat, unreal.Material):
        exprs = mel.get_material_expressions(mat)
        for e in exprs:
            entry = {{
                "class": e.get_class().get_name(),
                "desc":  e.get_editor_property("desc") if hasattr(e, "desc") else ""
            }}
            if hasattr(e, "parameter_name"):
                entry["parameter_name"] = str(e.get_editor_property("parameter_name"))
            data["expressions"].append(entry)
    print("UEOS_RESULT:" + json.dumps(data))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _compile(self, args: dict) -> list[types.TextContent]:
        mat_path = args["material_path"]
        save     = args.get("save_on_success", True)

        script = f"""
import unreal, json

mat = unreal.EditorAssetLibrary.load_asset("{mat_path}")
if mat is None:
    print("UEOS_ERROR:Material not found: {mat_path}")
else:
    # Recompile shader
    unreal.MaterialEditingLibrary.recompile_material(mat)
    if {str(save).lower()}:
        unreal.EditorAssetLibrary.save_asset("{mat_path}")
    print("UEOS_RESULT:" + json.dumps({{"status":"compiled","path":"{mat_path}"}}))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _assign_to_mesh(self, args: dict) -> list[types.TextContent]:
        mat_path    = args["material_path"]
        mesh_path   = args.get("mesh_path", "")
        bp_path     = args.get("blueprint_path", "")
        comp_name   = args.get("component_name", "")
        slot_index  = args.get("slot_index", 0)

        script = f"""
import unreal, json

mat = unreal.EditorAssetLibrary.load_asset("{mat_path}")
if mat is None:
    print("UEOS_ERROR:Material not found: {mat_path}")
else:
    mesh_path = "{mesh_path}"
    bp_path   = "{bp_path}"

    if mesh_path:
        mesh = unreal.EditorAssetLibrary.load_asset(mesh_path)
        if mesh and isinstance(mesh, (unreal.StaticMesh, unreal.SkeletalMesh)):
            unreal.StaticMeshEditorSubsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem) if isinstance(mesh, unreal.StaticMesh) else None
            if isinstance(mesh, unreal.StaticMesh):
                mesh.set_material({slot_index}, mat)
            else:
                mesh.set_material({slot_index}, mat)
            mesh.mark_package_dirty()
            unreal.EditorAssetLibrary.save_asset(mesh_path)
            print("UEOS_RESULT:" + json.dumps({{"status":"assigned","mesh":mesh_path,"material":"{mat_path}","slot":{slot_index}}}))
        else:
            print("UEOS_ERROR:Mesh not found or wrong type: " + mesh_path)
    elif bp_path:
        print("UEOS_RESULT:" + json.dumps({{"status":"bp_assignment_requires_component_edit","note":"Use blueprint_add_node to set material on component"}}))
    else:
        print("UEOS_ERROR:Provide mesh_path or blueprint_path")
"""
        return self._ret(await self.ue.execute_python(script))

    # ─────────────────────────────────────────────
    # Shared parser
    # ─────────────────────────────────────────────

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
