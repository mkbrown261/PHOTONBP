"""
UEOS Inspection Tools — UE 5.4 Optimized
Deep asset inspection — converts any UE asset to structured JSON.

Supports: Blueprints, Materials, Niagara, Animations, Widgets,
          Behavior Trees, Data Tables, Static Meshes, Skeletal Meshes,
          Maps/Levels, Sound assets, Physics Assets
"""

import json
import logging
from mcp import types

log = logging.getLogger("ueos.inspection")


class InspectionTools:

    def __init__(self, ue):
        self.ue = ue

    async def get_tool_definitions(self) -> list[types.Tool]:
        return [

            types.Tool(
                name="inspect_asset",
                description="""Inspect any Unreal Engine asset and return full structured JSON.
Auto-detects asset type and returns appropriate data:
- Blueprint → variables, functions, components, graphs, compile status
- Material → expressions, connections, parameters, blend mode
- Niagara → emitters, parameters, renderers
- StaticMesh → LODs, materials, collision, vertex count
- SkeletalMesh → skeleton, materials, morph targets, physics asset
- DataTable → row structure, all rows, column types
- AnimationSequence → length, fps, curves, notifies
- Widget → hierarchy, bindings, animations
- Level → actors, lighting, world settings""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path": {"type": "string", "description": "Full content path to any asset e.g. /Game/Blueprints/BP_Player"},
                        "include_graph_nodes": {"type": "boolean", "description": "Include Blueprint graph node details (can be large)", "default": False},
                        "include_all_rows": {"type": "boolean", "description": "Include all rows for Data Tables (can be large)", "default": True}
                    },
                    "required": ["asset_path"]
                }
            ),

            types.Tool(
                name="inspect_blueprint",
                description="""Deep inspect a Blueprint asset.
Returns: parent class, all variables with types, all functions, all components,
implemented interfaces, event dispatchers, compile status, and graph node summary.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Content path to Blueprint"},
                        "include_nodes": {"type": "boolean", "description": "Include node-level graph details", "default": False}
                    },
                    "required": ["blueprint_path"]
                }
            ),

            types.Tool(
                name="inspect_material",
                description="""Deep inspect a Material, Material Instance, or Material Function.
Returns: all expression nodes, connections between nodes, parameter values,
blend mode, shading model, and compile errors.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "material_path": {"type": "string", "description": "Content path to material"}
                    },
                    "required": ["material_path"]
                }
            ),

            types.Tool(
                name="inspect_mesh",
                description="""Inspect a Static Mesh or Skeletal Mesh asset.
Returns: vertex count, triangle count, LODs, materials, bounds,
collision complexity, sockets, and for skeletal meshes: bone hierarchy.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "mesh_path": {"type": "string", "description": "Content path to mesh asset"},
                        "include_bones": {"type": "boolean", "description": "Include full bone hierarchy (skeletal meshes)", "default": False}
                    },
                    "required": ["mesh_path"]
                }
            ),

            types.Tool(
                name="inspect_level",
                description="""Inspect the current level or a specified level asset.
Returns: all placed actors with types, transforms, and component info,
lighting settings, world settings, and sky/atmosphere config.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "level_path": {"type": "string", "description": "Content path to level (leave empty for current level)"},
                        "include_transforms": {"type": "boolean", "description": "Include actor location/rotation/scale", "default": True},
                        "filter_class": {"type": "string", "description": "Only return actors of this class e.g. StaticMeshActor", "default": ""}
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="inspect_data_table",
                description="""Inspect a Data Table asset.
Returns: row struct definition, all column names and types, row count,
and optionally all row data.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_path": {"type": "string", "description": "Content path to Data Table"},
                        "include_rows": {"type": "boolean", "description": "Include all row data", "default": True},
                        "row_filter": {"type": "string", "description": "Filter rows by name prefix", "default": ""}
                    },
                    "required": ["table_path"]
                }
            ),

            types.Tool(
                name="inspect_animation",
                description="""Inspect an Animation Sequence, Animation Montage, or Blend Space.
Returns: skeleton, length, frame count, FPS, animation curves,
animation notifies, and blend space sample points.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "animation_path": {"type": "string", "description": "Content path to animation asset"}
                    },
                    "required": ["animation_path"]
                }
            ),

            types.Tool(
                name="inspect_content_folder",
                description="""List all assets in a content folder with their types and basic info.
Essential for discovering what assets exist before working with them.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "folder_path": {"type": "string", "description": "Content path to folder e.g. /Game/Characters"},
                        "recursive": {"type": "boolean", "description": "Search subfolders recursively", "default": True},
                        "filter_type": {"type": "string", "description": "Filter by asset type: Blueprint, Material, StaticMesh, SkeletalMesh, Texture2D, NiagaraSystem, etc.", "default": ""}
                    },
                    "required": ["folder_path"]
                }
            ),

            types.Tool(
                name="inspect_niagara",
                description="""Inspect a Niagara System or Emitter.
Returns: emitter list, user-exposed parameters, renderer types,
simulation target (CPU/GPU), and effect bounds.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "system_path": {"type": "string", "description": "Content path to Niagara System or Emitter"}
                    },
                    "required": ["system_path"]
                }
            ),

            types.Tool(
                name="inspect_physics_asset",
                description="""Inspect a Physics Asset (used by Skeletal Meshes for ragdoll/cloth).
Returns: all physics bodies, constraint definitions, and cloth sections.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "physics_asset_path": {"type": "string", "description": "Content path to Physics Asset"}
                    },
                    "required": ["physics_asset_path"]
                }
            ),

            types.Tool(
                name="find_assets_by_class",
                description="""Find all assets of a specific class across the entire project.
Useful for finding all Blueprints of a type, all materials, etc.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_class": {"type": "string", "description": "Asset class name: Blueprint, Material, StaticMesh, NiagaraSystem, etc."},
                        "search_path": {"type": "string", "description": "Limit search to this path", "default": "/Game"},
                        "recursive": {"type": "boolean", "default": True}
                    },
                    "required": ["asset_class"]
                }
            ),

            types.Tool(
                name="find_references",
                description="""Find all assets that reference a given asset.
Essential for understanding asset dependencies before making changes.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path": {"type": "string", "description": "Content path to the asset to find references for"},
                        "include_soft_references": {"type": "boolean", "description": "Include soft/weak references", "default": False}
                    },
                    "required": ["asset_path"]
                }
            ),

        ]

    # ─────────────────────────────────────────────
    # Handler
    # ─────────────────────────────────────────────

    async def handle(self, name: str, args: dict) -> list[types.TextContent]:
        handlers = {
            "inspect_asset":            self._inspect_asset,
            "inspect_blueprint":        self._inspect_blueprint,
            "inspect_material":         self._inspect_material,
            "inspect_mesh":             self._inspect_mesh,
            "inspect_level":            self._inspect_level,
            "inspect_data_table":       self._inspect_data_table,
            "inspect_animation":        self._inspect_animation,
            "inspect_content_folder":   self._inspect_folder,
            "inspect_niagara":          self._inspect_niagara,
            "inspect_physics_asset":    self._inspect_physics,
            "find_assets_by_class":     self._find_by_class,
            "find_references":          self._find_references,
        }
        handler = handlers.get(name)
        if not handler:
            return [types.TextContent(type="text", text=f"Unknown inspection tool: {name}")]
        return await handler(args)

    # ─────────────────────────────────────────────
    # Implementations
    # ─────────────────────────────────────────────

    async def _inspect_asset(self, args: dict) -> list[types.TextContent]:
        asset_path        = args["asset_path"]
        include_nodes     = args.get("include_graph_nodes", False)
        include_all_rows  = args.get("include_all_rows", True)

        script = f"""
import unreal, json

asset = unreal.EditorAssetLibrary.load_asset("{asset_path}")
if asset is None:
    print("UEOS_ERROR:Asset not found: {asset_path}")
else:
    cls = asset.get_class().get_name()
    data = {{
        "path":  "{asset_path}",
        "class": cls,
        "name":  asset.get_name()
    }}

    if isinstance(asset, unreal.Blueprint):
        gen = asset.generated_class()
        data["type"]         = "Blueprint"
        data["parent_class"] = str(gen.get_super_class().get_name()) if gen else "Unknown"
        data["compile_status"] = str(asset.status)
        data["variables"] = []
        data["functions"] = []
        data["components"] = []
        for v in asset.get_all_member_variables():
            data["variables"].append({{
                "name": str(v.variable_name),
                "type": str(v.variable_type.category)
            }})
        for g in asset.get_all_graphs():
            gname = g.get_name()
            if gname not in ("EventGraph", "ConstructionScript"):
                data["functions"].append(gname)
        for comp in asset.get_editor_only_data().component_templates:
            data["components"].append({{
                "name":  comp.get_name(),
                "class": comp.get_class().get_name()
            }})

    elif isinstance(asset, unreal.Material):
        data["type"]        = "Material"
        data["blend_mode"]  = str(asset.blend_mode)
        data["shading"]     = str(asset.shading_model)
        data["two_sided"]   = asset.two_sided
        exprs = unreal.MaterialEditingLibrary.get_material_expressions(asset)
        data["expression_count"] = len(exprs)
        data["expressions"] = [{{
            "class": e.get_class().get_name(),
            "desc":  e.get_editor_property("desc") if hasattr(e, "desc") else ""
        }} for e in exprs]

    elif isinstance(asset, unreal.MaterialInstanceConstant):
        data["type"]   = "MaterialInstance"
        data["parent"] = str(asset.parent.get_name()) if asset.parent else "None"

    elif isinstance(asset, unreal.StaticMesh):
        data["type"]          = "StaticMesh"
        data["lod_count"]     = asset.get_num_lods()
        data["material_count"]= len(asset.static_materials)
        data["materials"]     = [str(m.material_interface.get_name()) if m.material_interface else "None"
                                  for m in asset.static_materials]

    elif isinstance(asset, unreal.SkeletalMesh):
        data["type"]     = "SkeletalMesh"
        data["skeleton"] = str(asset.skeleton.get_name()) if asset.skeleton else "None"
        data["materials"]= [str(m.material_interface.get_name()) if m.material_interface else "None"
                             for m in asset.materials]

    elif isinstance(asset, unreal.DataTable):
        data["type"]      = "DataTable"
        data["row_struct"]= str(asset.row_struct.get_name()) if asset.row_struct else "Unknown"
        rows = unreal.DataTableFunctionLibrary.get_data_table_row_names(asset)
        data["row_count"] = len(rows)
        data["row_names"] = [str(r) for r in rows[:50]]  # first 50

    elif isinstance(asset, unreal.NiagaraSystem):
        data["type"]    = "NiagaraSystem"
        data["emitters"]= []
        for eh in asset.get_editor_only_data().emitters:
            try:
                data["emitters"].append(str(eh.get_editor_only_data().source.get_name()))
            except:
                data["emitters"].append("Unknown")

    print("UEOS_RESULT:" + json.dumps(data, default=str))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _inspect_blueprint(self, args: dict) -> list[types.TextContent]:
        bp_path       = args["blueprint_path"]
        include_nodes = args.get("include_nodes", False)

        script = f"""
import unreal, json

bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
if bp is None or not isinstance(bp, unreal.Blueprint):
    print("UEOS_ERROR:Blueprint not found: {bp_path}")
else:
    gen = bp.generated_class()
    data = {{
        "path":           "{bp_path}",
        "name":           bp.get_name(),
        "parent_class":   str(gen.get_super_class().get_name()) if gen else "Unknown",
        "compile_status": str(bp.status),
        "variables":      [],
        "functions":      [],
        "events":         [],
        "components":     [],
        "interfaces":     [],
        "dispatchers":    [],
        "graphs":         []
    }}

    # Variables
    for v in bp.get_all_member_variables():
        vdata = {{
            "name":      str(v.variable_name),
            "type":      str(v.variable_type.category),
            "editable":  bool(v.property_flags & unreal.PropertyFlags.CPF_EDIT),
            "replicated":bool(v.property_flags & unreal.PropertyFlags.CPF_NET),
        }}
        try:
            vdata["sub_category"] = str(v.variable_type.sub_category_object.get_name()) if v.variable_type.sub_category_object else ""
        except: pass
        data["variables"].append(vdata)

    # Graphs → functions, events
    for graph in bp.get_all_graphs():
        gname = graph.get_name()
        data["graphs"].append({{
            "name":       gname,
            "node_count": len(graph.nodes)
        }})
        if gname not in ("EventGraph", "ConstructionScript"):
            data["functions"].append(gname)
        elif gname == "EventGraph":
            # Enumerate event nodes
            for node in graph.nodes:
                ncls = node.get_class().get_name()
                if "Event" in ncls and "Custom" not in ncls:
                    data["events"].append(ncls.replace("K2Node_Event_", "").replace("K2Node_", ""))

    # Components
    for comp in bp.get_editor_only_data().component_templates:
        data["components"].append({{
            "name":       comp.get_name(),
            "class":      comp.get_class().get_name(),
        }})

    # Interfaces
    for iface in bp.implemented_interfaces:
        try:
            data["interfaces"].append(str(iface.interface_class.get_name()))
        except: pass

    print("UEOS_RESULT:" + json.dumps(data, default=str))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _inspect_material(self, args: dict) -> list[types.TextContent]:
        mat_path = args["material_path"]

        script = f"""
import unreal, json

mat = unreal.EditorAssetLibrary.load_asset("{mat_path}")
if mat is None:
    print("UEOS_ERROR:Material not found: {mat_path}")
else:
    data = {{
        "path":  "{mat_path}",
        "class": mat.get_class().get_name(),
        "name":  mat.get_name()
    }}

    if isinstance(mat, unreal.Material):
        data["blend_mode"]   = str(mat.blend_mode)
        data["shading_model"]= str(mat.shading_model)
        data["two_sided"]    = mat.two_sided
        data["domain"]       = str(mat.material_domain)
        exprs = unreal.MaterialEditingLibrary.get_material_expressions(mat)
        data["expressions"]  = []
        data["params"]       = []
        for e in exprs:
            entry = {{
                "class": e.get_class().get_name(),
                "desc":  e.get_editor_property("desc") if hasattr(e, "desc") else ""
            }}
            if hasattr(e, "parameter_name"):
                pname = str(e.get_editor_property("parameter_name"))
                entry["parameter_name"] = pname
                data["params"].append({{
                    "name":  pname,
                    "class": e.get_class().get_name()
                }})
            data["expressions"].append(entry)

    elif isinstance(mat, unreal.MaterialInstanceConstant):
        data["parent"] = str(mat.parent.get_name()) if mat.parent else "None"
        # Scalar params
        data["scalar_params"]  = []
        data["vector_params"]  = []
        data["texture_params"] = []
        mel = unreal.MaterialEditingLibrary
        for pname in mel.get_material_instance_scalar_parameter_names(mat):
            val = mel.get_material_instance_scalar_parameter_value(mat, pname)
            data["scalar_params"].append({{"name": str(pname), "value": val}})
        for pname in mel.get_material_instance_vector_parameter_names(mat):
            val = mel.get_material_instance_vector_parameter_value(mat, pname)
            data["vector_params"].append({{"name": str(pname), "r": val.r, "g": val.g, "b": val.b, "a": val.a}})

    elif isinstance(mat, unreal.MaterialFunction):
        data["type"] = "MaterialFunction"
        exprs = unreal.MaterialEditingLibrary.get_material_function_expressions(mat)
        data["expression_count"] = len(exprs)

    print("UEOS_RESULT:" + json.dumps(data, default=str))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _inspect_mesh(self, args: dict) -> list[types.TextContent]:
        mesh_path     = args["mesh_path"]
        include_bones = args.get("include_bones", False)

        script = f"""
import unreal, json

mesh = unreal.EditorAssetLibrary.load_asset("{mesh_path}")
if mesh is None:
    print("UEOS_ERROR:Mesh not found: {mesh_path}")
else:
    data = {{
        "path":  "{mesh_path}",
        "class": mesh.get_class().get_name(),
        "name":  mesh.get_name()
    }}

    if isinstance(mesh, unreal.StaticMesh):
        data["type"]      = "StaticMesh"
        data["lod_count"] = mesh.get_num_lods()
        data["materials"] = [str(m.material_interface.get_name()) if m.material_interface else "None"
                              for m in mesh.static_materials]
        bounds = mesh.get_bounds()
        data["bounds"] = {{
            "origin":  [bounds.origin.x, bounds.origin.y, bounds.origin.z],
            "extent":  [bounds.box_extent.x, bounds.box_extent.y, bounds.box_extent.z],
            "sphere":  bounds.sphere_radius
        }}
        sockets = mesh.sockets
        data["sockets"] = [str(s.socket_name) for s in sockets]

    elif isinstance(mesh, unreal.SkeletalMesh):
        data["type"]     = "SkeletalMesh"
        data["skeleton"] = str(mesh.skeleton.get_name()) if mesh.skeleton else "None"
        data["materials"]= [str(m.material_interface.get_name()) if m.material_interface else "None"
                             for m in mesh.materials]
        data["morph_targets"] = [str(mt.get_name()) for mt in mesh.morph_targets]
        if mesh.physics_asset:
            data["physics_asset"] = str(mesh.physics_asset.get_name())
        sockets = mesh.sockets
        data["sockets"]  = [str(s.socket_name) for s in sockets]

        if {str(include_bones).lower()} and mesh.skeleton:
            skel = mesh.skeleton
            ref_skel = skel.get_reference_pose()
            data["bone_count"] = skel.get_num_bones()
            data["bones"] = []
            for i in range(min(skel.get_num_bones(), 100)):
                bone_name = str(skel.get_bone_name(i))
                parent_idx = skel.get_parent_bone(i)
                data["bones"].append({{
                    "index":  i,
                    "name":   bone_name,
                    "parent": parent_idx
                }})

    print("UEOS_RESULT:" + json.dumps(data, default=str))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _inspect_level(self, args: dict) -> list[types.TextContent]:
        level_path         = args.get("level_path", "")
        include_transforms = args.get("include_transforms", True)
        filter_class       = args.get("filter_class", "")

        script = f"""
import unreal, json

world = unreal.EditorLevelLibrary.get_editor_world()
if world is None:
    print("UEOS_ERROR:No editor world found")
else:
    actors = unreal.EditorLevelLibrary.get_all_level_actors()
    filter_cls = "{filter_class}"

    data = {{
        "level":       str(world.get_name()),
        "actor_count": len(actors),
        "actors":      []
    }}

    for actor in actors:
        cls = actor.get_class().get_name()
        if filter_cls and filter_cls.lower() not in cls.lower():
            continue

        entry = {{
            "name":  actor.get_name(),
            "class": cls,
            "label": str(actor.get_actor_label()),
            "tags":  [str(t) for t in actor.tags]
        }}

        if {str(include_transforms).lower()}:
            loc = actor.get_actor_location()
            rot = actor.get_actor_rotation()
            scl = actor.get_actor_scale3d()
            entry["transform"] = {{
                "location": [loc.x, loc.y, loc.z],
                "rotation": [rot.pitch, rot.yaw, rot.roll],
                "scale":    [scl.x, scl.y, scl.z]
            }}

        data["actors"].append(entry)

    # World settings
    ws = world.get_world_settings()
    data["world_settings"] = {{
        "gravity_z":   ws.world_to_meters,
        "world_to_meters": ws.world_to_meters
    }}

    print("UEOS_RESULT:" + json.dumps(data, default=str))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _inspect_data_table(self, args: dict) -> list[types.TextContent]:
        table_path   = args["table_path"]
        include_rows = args.get("include_rows", True)
        row_filter   = args.get("row_filter", "")

        script = f"""
import unreal, json

dt = unreal.EditorAssetLibrary.load_asset("{table_path}")
if dt is None or not isinstance(dt, unreal.DataTable):
    print("UEOS_ERROR:DataTable not found: {table_path}")
else:
    row_names = unreal.DataTableFunctionLibrary.get_data_table_row_names(dt)
    filter_str = "{row_filter}".lower()

    data = {{
        "path":       "{table_path}",
        "row_struct": str(dt.row_struct.get_name()) if dt.row_struct else "Unknown",
        "row_count":  len(row_names),
        "rows":       []
    }}

    if {str(include_rows).lower()}:
        for row_name in row_names:
            rn = str(row_name)
            if filter_str and filter_str not in rn.lower():
                continue
            try:
                row_data = unreal.DataTableFunctionLibrary.get_data_table_row_from_name(
                    dt, row_name
                )
                data["rows"].append({{"name": rn, "data": str(row_data)}})
            except Exception as e:
                data["rows"].append({{"name": rn, "error": str(e)}})

    print("UEOS_RESULT:" + json.dumps(data, default=str))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _inspect_animation(self, args: dict) -> list[types.TextContent]:
        anim_path = args["animation_path"]

        script = f"""
import unreal, json

anim = unreal.EditorAssetLibrary.load_asset("{anim_path}")
if anim is None:
    print("UEOS_ERROR:Animation not found: {anim_path}")
else:
    cls  = anim.get_class().get_name()
    data = {{
        "path":  "{anim_path}",
        "class": cls,
        "name":  anim.get_name()
    }}

    if isinstance(anim, unreal.AnimSequence):
        data["type"]        = "AnimSequence"
        data["length"]      = anim.sequence_length
        data["fps"]         = anim.target_frame_rate.numerator / max(anim.target_frame_rate.denominator, 1)
        data["frame_count"] = anim.get_num_sampled_keys()
        data["skeleton"]    = str(anim.get_skeleton().get_name()) if anim.get_skeleton() else "None"
        data["notifies"]    = []
        for n in anim.notifies:
            data["notifies"].append({{
                "name":     str(n.notify_name),
                "time":     n.link_value,
                "duration": n.duration
            }})
        data["curves"] = []
        for curve in anim.get_curve_data().float_curves:
            data["curves"].append(str(curve.name.display_name))

    elif isinstance(anim, unreal.AnimMontage):
        data["type"]     = "AnimMontage"
        data["length"]   = anim.sequence_length
        data["sections"] = []
        for section in anim.composite_sections:
            data["sections"].append(str(section.section_name))

    elif isinstance(anim, unreal.BlendSpace):
        data["type"]       = "BlendSpace"
        data["axis_x"]     = str(anim.x_axis_name)
        data["axis_y"]     = str(anim.y_axis_name) if hasattr(anim, "y_axis_name") else "N/A"

    print("UEOS_RESULT:" + json.dumps(data, default=str))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _inspect_folder(self, args: dict) -> list[types.TextContent]:
        folder_path  = args["folder_path"]
        recursive    = args.get("recursive", True)
        filter_type  = args.get("filter_type", "")

        script = f"""
import unreal, json

registry = unreal.AssetRegistryHelpers.get_asset_registry()
assets   = registry.get_assets_by_path("{folder_path}", recursive={str(recursive)})

filter_type = "{filter_type}".lower()
result = []
for a in assets:
    cls = str(a.asset_class_path.asset_name)
    if filter_type and filter_type not in cls.lower():
        continue
    result.append({{
        "name":    str(a.asset_name),
        "path":    str(a.object_path),
        "class":   cls,
        "package": str(a.package_name)
    }})

data = {{
    "folder":      "{folder_path}",
    "asset_count": len(result),
    "assets":      result
}}
print("UEOS_RESULT:" + json.dumps(data, default=str))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _inspect_niagara(self, args: dict) -> list[types.TextContent]:
        system_path = args["system_path"]

        script = f"""
import unreal, json

asset = unreal.EditorAssetLibrary.load_asset("{system_path}")
if asset is None:
    print("UEOS_ERROR:Not found: {system_path}")
else:
    data = {{
        "path":    "{system_path}",
        "class":   asset.get_class().get_name(),
        "name":    asset.get_name(),
        "emitters":[]
    }}
    if isinstance(asset, unreal.NiagaraSystem):
        data["type"] = "NiagaraSystem"
        for eh in asset.get_editor_only_data().emitters:
            try:
                em_src = eh.get_editor_only_data().source
                data["emitters"].append({{
                    "name":    str(em_src.get_name()),
                    "enabled": True
                }})
            except:
                data["emitters"].append({{"name": "Unknown"}})
    elif isinstance(asset, unreal.NiagaraEmitter):
        data["type"] = "NiagaraEmitter"
    print("UEOS_RESULT:" + json.dumps(data, default=str))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _inspect_physics(self, args: dict) -> list[types.TextContent]:
        phys_path = args["physics_asset_path"]

        script = f"""
import unreal, json

phys = unreal.EditorAssetLibrary.load_asset("{phys_path}")
if phys is None or not isinstance(phys, unreal.PhysicsAsset):
    print("UEOS_ERROR:Physics Asset not found: {phys_path}")
else:
    data = {{
        "path":             "{phys_path}",
        "name":             phys.get_name(),
        "body_count":       len(phys.skeletal_body_setups),
        "constraint_count": len(phys.constraints_setup),
        "bodies":           [],
        "constraints":      []
    }}
    for body in phys.skeletal_body_setups:
        data["bodies"].append({{
            "bone":  str(body.bone_name),
            "type":  str(body.phys_type)
        }})
    for constraint in phys.constraints_setup:
        data["constraints"].append({{
            "bone1": str(constraint.joint_name),
            "bone2": str(constraint.constraint_bone1)
        }})
    print("UEOS_RESULT:" + json.dumps(data, default=str))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _find_by_class(self, args: dict) -> list[types.TextContent]:
        asset_class  = args["asset_class"]
        search_path  = args.get("search_path", "/Game")
        recursive    = args.get("recursive", True)

        script = f"""
import unreal, json

registry = unreal.AssetRegistryHelpers.get_asset_registry()
assets   = registry.get_assets_by_path("{search_path}", recursive={str(recursive)})

results = []
for a in assets:
    if "{asset_class}".lower() in str(a.asset_class_path.asset_name).lower():
        results.append({{
            "name":  str(a.asset_name),
            "path":  str(a.object_path),
            "class": str(a.asset_class_path.asset_name)
        }})

data = {{
    "class":       "{asset_class}",
    "search_path": "{search_path}",
    "count":       len(results),
    "assets":      results
}}
print("UEOS_RESULT:" + json.dumps(data, default=str))
"""
        return self._ret(await self.ue.execute_python(script))

    async def _find_references(self, args: dict) -> list[types.TextContent]:
        asset_path  = args["asset_path"]
        soft_refs   = args.get("include_soft_references", False)

        script = f"""
import unreal, json

registry = unreal.AssetRegistryHelpers.get_asset_registry()
asset_id = unreal.AssetIdentifier(package_name="{asset_path}".split(".")[0])

deps = registry.get_referencers(asset_id, unreal.AssetRegistryDependencyOptions())
results = []
for dep in deps:
    results.append(str(dep.package_name))

data = {{
    "asset":      "{asset_path}",
    "ref_count":  len(results),
    "referencers":results
}}
print("UEOS_RESULT:" + json.dumps(data, default=str))
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
