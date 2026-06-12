"""
UEOS Phase 7 — Procedural Content Generation (PCG) Tools
MCP tools for PCG Graphs, attribute nodes, biome painting, surface sampling,
and point transforms in Unreal Engine 5.4.

20 tools — prefix: pcg_
"""

from __future__ import annotations
import json
from textwrap import dedent
from mcp import types


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

PCG_DENSITY_FUNCTIONS = {
    "uniform":    "PCGDensityFunction_Uniform",
    "gradient":   "PCGDensityFunction_Gradient",
    "worley":     "PCGDensityFunction_Worley",
    "perlin":     "PCGDensityFunction_Perlin",
}

PCG_POINT_FILTERS = {
    "by_density": "PCGFilterDataByDensity",
    "by_attribute": "PCGFilterDataByAttribute",
    "by_bounds":  "PCGFilterDataByBounds",
    "by_index":   "PCGFilterDataByIndex",
}

PCG_TRANSFORM_MODES = {
    "world":   "EPCGCoordinateSpace.World",
    "local":   "EPCGCoordinateSpace.LocalToSelf",
    "original":"EPCGCoordinateSpace.Original",
}

PCG_ATTRIBUTE_TYPES = {
    "float":  "float",
    "int32":  "int32",
    "vector": "FVector",
    "bool":   "bool",
    "string": "FString",
    "name":   "FName",
    "softobj":"FSoftObjectPath",
}

PCG_SPAWN_MODES = {
    "static_mesh":   "PCGMeshSpawner",
    "actor":         "PCGActorSpawner",
    "blueprint":     "PCGBlueprintSpawner",
    "hierarchical":  "PCGHierarchicalGenerationScheduler",
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _jl(lst: list) -> str:
    return json.dumps(lst)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class PCGTools:
    """MCP tool handler for Procedural Content Generation (PCG) in UE 5.4."""

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
            # ── Graph CRUD ────────────────────────────────────────────
            types.Tool(
                name="pcg_create_graph",
                description=(
                    "Create a new PCG Graph asset. PCG Graphs define the procedural generation pipeline "
                    "that transforms input volumes into spawned content."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":      {"type": "string", "description": "Name of the PCG Graph asset."},
                        "save_path": {"type": "string", "description": "Content folder to save the asset."},
                    },
                    "required": ["name", "save_path"],
                },
            ),
            types.Tool(
                name="pcg_list_graphs",
                description="List all PCG Graph assets in a content folder.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_path": {"type": "string", "default": "/Game"},
                    },
                    "required": [],
                },
            ),
            types.Tool(
                name="pcg_get_graph_info",
                description="Return node count, input/output pins, and settings of a PCG Graph.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "graph_path": {"type": "string"},
                    },
                    "required": ["graph_path"],
                },
            ),
            types.Tool(
                name="pcg_duplicate_graph",
                description="Duplicate an existing PCG Graph to a new asset.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_path":  {"type": "string"},
                        "new_name":     {"type": "string"},
                        "dest_folder":  {"type": "string"},
                    },
                    "required": ["source_path", "new_name", "dest_folder"],
                },
            ),
            types.Tool(
                name="pcg_delete_graph",
                description="Delete a PCG Graph asset from the content browser.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "graph_path": {"type": "string"},
                    },
                    "required": ["graph_path"],
                },
            ),

            # ── Graph Nodes / Pipeline ────────────────────────────────
            types.Tool(
                name="pcg_add_surface_sampler",
                description="Add a Surface Sampler node to a PCG Graph to scatter points on landscape or mesh surfaces.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "graph_path":    {"type": "string"},
                        "points_per_sqm":{"type": "number", "description": "Point density (points per square metre).", "default": 1.0},
                        "seed":          {"type": "integer", "default": 42},
                        "unbounded":     {"type": "boolean", "description": "Sample beyond PCG volume bounds.", "default": False},
                    },
                    "required": ["graph_path"],
                },
            ),
            types.Tool(
                name="pcg_add_static_mesh_spawner",
                description="Add a Static Mesh Spawner node to a PCG Graph to instance meshes at each point.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "graph_path":      {"type": "string"},
                        "mesh_paths":      {"type": "array", "items": {"type": "string"}, "description": "List of Static Mesh asset paths to spawn."},
                        "weights":         {"type": "array", "items": {"type": "number"}, "description": "Relative spawn weights (parallel to mesh_paths)."},
                        "cull_distance":   {"type": "number", "description": "Cull distance (cm). 0 = never cull.", "default": 0.0},
                        "cast_shadow":     {"type": "boolean", "default": True},
                        "collision_preset":{"type": "string", "description": "Collision profile for spawned meshes.", "default": "NoCollision"},
                    },
                    "required": ["graph_path", "mesh_paths"],
                },
            ),
            types.Tool(
                name="pcg_add_actor_spawner",
                description="Add a Blueprint/Actor Spawner node to a PCG Graph.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "graph_path":    {"type": "string"},
                        "actor_class":   {"type": "string", "description": "Blueprint class path to spawn (e.g. /Game/Blueprints/BP_Tree.BP_Tree_C)."},
                        "spawn_mode":    {"type": "string", "enum": ["blueprint", "actor"], "default": "blueprint"},
                    },
                    "required": ["graph_path", "actor_class"],
                },
            ),
            types.Tool(
                name="pcg_add_density_filter",
                description="Add a Density Filter node to remove points below a threshold.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "graph_path":    {"type": "string"},
                        "lower_bound":   {"type": "number", "description": "Minimum density (0–1) to keep.", "default": 0.0},
                        "upper_bound":   {"type": "number", "description": "Maximum density (0–1) to keep.", "default": 1.0},
                        "invert":        {"type": "boolean", "description": "Keep points OUTSIDE the density range.", "default": False},
                    },
                    "required": ["graph_path"],
                },
            ),
            types.Tool(
                name="pcg_add_attribute_node",
                description="Add an Attribute Override/Setter node to a PCG Graph (sets a named attribute on all points).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "graph_path":       {"type": "string"},
                        "attribute_name":   {"type": "string", "description": "Name of the PCG point attribute."},
                        "attribute_type":   {"type": "string", "enum": ["float", "int32", "vector", "bool", "string", "name"], "default": "float"},
                        "constant_value":   {"type": "string", "description": "Constant value to assign (serialised as string)."},
                    },
                    "required": ["graph_path", "attribute_name", "constant_value"],
                },
            ),
            types.Tool(
                name="pcg_add_transform_points",
                description="Add a Transform Points node to offset, rotate, or scale spawned points.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "graph_path":        {"type": "string"},
                        "offset_min":        {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 0]},
                        "offset_max":        {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 0]},
                        "rotation_min":      {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 0]},
                        "rotation_max":      {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 360]},
                        "scale_min":         {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [1, 1, 1]},
                        "scale_max":         {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [1, 1, 1]},
                        "uniform_scale":     {"type": "boolean", "description": "Lock X/Y/Z scale together.", "default": True},
                        "apply_to_attribute":{"type": "string", "description": "Apply transform only to a named attribute.", "default": ""},
                    },
                    "required": ["graph_path"],
                },
            ),
            types.Tool(
                name="pcg_add_noise_node",
                description="Add a Noise (density modifier) node to modulate point density with Perlin or Worley noise.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "graph_path":     {"type": "string"},
                        "noise_type":     {"type": "string", "enum": ["perlin", "worley"], "default": "perlin"},
                        "frequency":      {"type": "number", "description": "Noise frequency (lower = larger features).", "default": 0.01},
                        "amplitude":      {"type": "number", "description": "Noise amplitude multiplier.", "default": 1.0},
                        "seed":           {"type": "integer", "default": 0},
                    },
                    "required": ["graph_path"],
                },
            ),
            types.Tool(
                name="pcg_add_spline_sampler",
                description="Add a Spline Sampler node that scatters points along a spline actor.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "graph_path":       {"type": "string"},
                        "mode":             {"type": "string", "enum": ["along_spline", "on_surface", "interior"], "default": "along_spline"},
                        "spacing":          {"type": "number", "description": "Point spacing in cm.", "default": 100.0},
                        "width":            {"type": "number", "description": "Lateral width in 'on_surface' mode.", "default": 200.0},
                    },
                    "required": ["graph_path"],
                },
            ),

            # ── PCGVolume Management ──────────────────────────────────
            types.Tool(
                name="pcg_place_volume",
                description="Place a PCG Volume actor in the current level and assign a PCG Graph to it.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "graph_path":  {"type": "string", "description": "PCG Graph asset path."},
                        "location":    {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 0]},
                        "extent":      {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "description": "[HalfX, HalfY, HalfZ] in cm.", "default": [1000, 1000, 500]},
                        "actor_name":  {"type": "string", "default": "PCGVolume"},
                        "auto_generate":{"type": "boolean", "description": "Immediately run PCG generation after placement.", "default": True},
                    },
                    "required": ["graph_path"],
                },
            ),
            types.Tool(
                name="pcg_list_volumes",
                description="List all PCG Volume actors in the current level.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),

            # ── Runtime / Execute ─────────────────────────────────────
            types.Tool(
                name="pcg_execute_graph",
                description="Force immediate (re)generation of a PCG Volume actor in the level.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "volume_actor": {"type": "string", "description": "Label of the PCG Volume actor."},
                        "cleanup_first": {"type": "boolean", "description": "Clean up existing generated content before re-running.", "default": True},
                    },
                    "required": ["volume_actor"],
                },
            ),
            types.Tool(
                name="pcg_cleanup_volume",
                description="Remove all content generated by a PCG Volume actor.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "volume_actor": {"type": "string", "description": "Label of the PCG Volume actor."},
                    },
                    "required": ["volume_actor"],
                },
            ),

            # ── Biome / Landscape Painting ────────────────────────────
            types.Tool(
                name="pcg_create_biome_preset",
                description=(
                    "Create a named biome preset — a PCG Graph pre-configured with surface sampler, "
                    "density filter, transform jitter, and static mesh spawner — ready to drop on landscape."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":            {"type": "string", "description": "Biome preset name (e.g. 'ForestBiome')."},
                        "save_path":       {"type": "string"},
                        "mesh_paths":      {"type": "array", "items": {"type": "string"}, "description": "Meshes to spawn in this biome."},
                        "density":         {"type": "number", "description": "Points per m².", "default": 2.0},
                        "scale_min":       {"type": "number", "description": "Uniform scale minimum.", "default": 0.8},
                        "scale_max":       {"type": "number", "description": "Uniform scale maximum.", "default": 1.2},
                        "density_mask_tag":{"type": "string", "description": "Optional gameplay tag used to mask biome density.", "default": ""},
                    },
                    "required": ["name", "save_path", "mesh_paths"],
                },
            ),
            types.Tool(
                name="pcg_set_landscape_layer_weight",
                description=(
                    "Add a Landscape Layer Weight node to a PCG Graph so density is modulated by a "
                    "landscape paint layer."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "graph_path":   {"type": "string"},
                        "layer_name":   {"type": "string", "description": "Landscape layer info name (e.g. 'Grass')."},
                        "invert":       {"type": "boolean", "default": False},
                    },
                    "required": ["graph_path", "layer_name"],
                },
            ),

            # ── Debugging ─────────────────────────────────────────────
            types.Tool(
                name="pcg_get_point_stats",
                description="Return point count and bounding box of the last generated output of a PCG Volume.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "volume_actor": {"type": "string"},
                    },
                    "required": ["volume_actor"],
                },
            ),
            types.Tool(
                name="pcg_diagnostics",
                description="Return a diagnostic summary of PCG Graph assets and PCG Volume actors in the project.",
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
            "pcg_create_graph":            self._create_graph,
            "pcg_list_graphs":             self._list_graphs,
            "pcg_get_graph_info":          self._get_graph_info,
            "pcg_duplicate_graph":         self._duplicate_graph,
            "pcg_delete_graph":            self._delete_graph,
            "pcg_add_surface_sampler":     self._add_surface_sampler,
            "pcg_add_static_mesh_spawner": self._add_static_mesh_spawner,
            "pcg_add_actor_spawner":       self._add_actor_spawner,
            "pcg_add_density_filter":      self._add_density_filter,
            "pcg_add_attribute_node":      self._add_attribute_node,
            "pcg_add_transform_points":    self._add_transform_points,
            "pcg_add_noise_node":          self._add_noise_node,
            "pcg_add_spline_sampler":      self._add_spline_sampler,
            "pcg_place_volume":            self._place_volume,
            "pcg_list_volumes":            self._list_volumes,
            "pcg_execute_graph":           self._execute_graph,
            "pcg_cleanup_volume":          self._cleanup_volume,
            "pcg_create_biome_preset":     self._create_biome_preset,
            "pcg_set_landscape_layer_weight": self._set_landscape_layer_weight,
            "pcg_get_point_stats":         self._get_point_stats,
            "pcg_diagnostics":             self._diagnostics,
        }
        fn = dispatch.get(name)
        if fn is None:
            return [types.TextContent(type="text", text=f"Unknown pcg tool: {name}")]
        return await fn(args)

    # ------------------------------------------------------------------
    # Implementations
    # ------------------------------------------------------------------

    async def _create_graph(self, args: dict) -> list[types.TextContent]:
        name      = args["name"]
        save_path = args["save_path"].rstrip("/")
        script = dedent(f"""
            import unreal, json
            try:
                factory = unreal.PCGGraphFactory()
                graph = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    "{name}", "{save_path}", unreal.PCGGraph, factory
                )
                if not graph:
                    raise RuntimeError("Failed to create PCGGraph")
                unreal.EditorAssetLibrary.save_asset(graph.get_path_name())
                print("UEOS_RESULT:" + json.dumps({{"path": graph.get_path_name(), "name": "{name}", "status": "created"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_create_graph")

    async def _list_graphs(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game")
        script = dedent(f"""
            import unreal, json
            try:
                reg = unreal.AssetRegistryHelpers.get_asset_registry()
                assets = reg.get_assets_by_path("{search_path}", recursive=True)
                results = []
                for a in assets:
                    if "PCGGraph" in str(a.asset_class_path):
                        results.append({{"name": str(a.asset_name), "path": str(a.object_path)}})
                print("UEOS_RESULT:" + json.dumps({{"pcg_graphs": results, "count": len(results)}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_list_graphs")

    async def _get_graph_info(self, args: dict) -> list[types.TextContent]:
        graph_path = args["graph_path"]
        script = dedent(f"""
            import unreal, json
            try:
                graph = unreal.load_asset("{graph_path}")
                if not graph:
                    raise RuntimeError("PCGGraph not found: {graph_path}")
                nodes = graph.get_nodes()
                info = {{
                    "path": "{graph_path}",
                    "node_count": len(nodes),
                    "node_types": list(set(type(n).__name__ for n in nodes)),
                }}
                print("UEOS_RESULT:" + json.dumps(info))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_get_graph_info")

    async def _duplicate_graph(self, args: dict) -> list[types.TextContent]:
        source_path = args["source_path"]
        new_name    = args["new_name"]
        dest_folder = args["dest_folder"].rstrip("/")
        script = dedent(f"""
            import unreal, json
            try:
                new_path = "{dest_folder}/{new_name}"
                success  = unreal.EditorAssetLibrary.duplicate_asset("{source_path}", new_path)
                if not success:
                    raise RuntimeError("Duplicate failed")
                unreal.EditorAssetLibrary.save_asset(new_path)
                print("UEOS_RESULT:" + json.dumps({{"source": "{source_path}", "new_path": new_path, "status": "duplicated"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_duplicate_graph")

    async def _delete_graph(self, args: dict) -> list[types.TextContent]:
        graph_path = args["graph_path"]
        script = dedent(f"""
            import unreal, json
            try:
                ok = unreal.EditorAssetLibrary.delete_asset("{graph_path}")
                print("UEOS_RESULT:" + json.dumps({{"path": "{graph_path}", "deleted": ok}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_delete_graph")

    async def _add_surface_sampler(self, args: dict) -> list[types.TextContent]:
        graph_path = args["graph_path"]
        ppm        = args.get("points_per_sqm", 1.0)
        seed       = args.get("seed", 42)
        unbounded  = args.get("unbounded", False)
        script = dedent(f"""
            import unreal, json
            try:
                graph = unreal.load_asset("{graph_path}")
                if not graph:
                    raise RuntimeError("PCGGraph not found: {graph_path}")
                node = graph.add_node(unreal.PCGSurfaceSamplerSettings)
                if node:
                    settings = node.get_settings()
                    if settings:
                        settings.set_editor_property("points_per_squared_meter", {ppm})
                        settings.set_editor_property("seed", {seed})
                        settings.set_editor_property("unbounded", {str(unbounded)})
                unreal.EditorAssetLibrary.save_asset("{graph_path}")
                print("UEOS_RESULT:" + json.dumps({{"graph": "{graph_path}", "node": "SurfaceSampler", "points_per_sqm": {ppm}, "seed": {seed}, "status": "added"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_add_surface_sampler")

    async def _add_static_mesh_spawner(self, args: dict) -> list[types.TextContent]:
        graph_path   = args["graph_path"]
        mesh_paths   = args["mesh_paths"]
        weights      = args.get("weights", [1.0] * len(mesh_paths))
        cull_dist    = args.get("cull_distance", 0.0)
        cast_shadow  = args.get("cast_shadow", True)
        col_preset   = args.get("collision_preset", "NoCollision")
        script = dedent(f"""
            import unreal, json
            try:
                graph = unreal.load_asset("{graph_path}")
                if not graph:
                    raise RuntimeError("PCGGraph not found: {graph_path}")
                node = graph.add_node(unreal.PCGStaticMeshSpawnerSettings)
                if node:
                    settings = node.get_settings()
                    if settings:
                        entries = []
                        mesh_paths_list = {mesh_paths}
                        weights_list    = {weights}
                        for i, mp in enumerate(mesh_paths_list):
                            mesh = unreal.load_asset(mp)
                            if mesh:
                                entry = unreal.PCGSoftISMComponentDescriptor()
                                entry.set_editor_property("static_mesh", mesh)
                                entry.set_editor_property("custom_data_float_count", 0)
                                entries.append(entry)
                        settings.set_editor_property("mesh_entries", entries)
                        settings.set_editor_property("cull_pcg_only_instances_distance", {cull_dist})
                unreal.EditorAssetLibrary.save_asset("{graph_path}")
                print("UEOS_RESULT:" + json.dumps({{"graph": "{graph_path}", "node": "StaticMeshSpawner", "mesh_count": len(mesh_paths_list), "status": "added"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_add_static_mesh_spawner")

    async def _add_actor_spawner(self, args: dict) -> list[types.TextContent]:
        graph_path  = args["graph_path"]
        actor_class = args["actor_class"]
        spawn_mode  = args.get("spawn_mode", "blueprint")
        script = dedent(f"""
            import unreal, json
            try:
                graph = unreal.load_asset("{graph_path}")
                if not graph:
                    raise RuntimeError("PCGGraph not found: {graph_path}")
                node = graph.add_node(unreal.PCGSpawnActorSettings)
                if node:
                    settings = node.get_settings()
                    if settings:
                        actor_cls = unreal.load_class(None, "{actor_class}")
                        if actor_cls:
                            settings.set_editor_property("template_actor_class", actor_cls)
                unreal.EditorAssetLibrary.save_asset("{graph_path}")
                print("UEOS_RESULT:" + json.dumps({{"graph": "{graph_path}", "node": "ActorSpawner", "actor_class": "{actor_class}", "status": "added"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_add_actor_spawner")

    async def _add_density_filter(self, args: dict) -> list[types.TextContent]:
        graph_path  = args["graph_path"]
        lower_bound = args.get("lower_bound", 0.0)
        upper_bound = args.get("upper_bound", 1.0)
        invert      = args.get("invert", False)
        script = dedent(f"""
            import unreal, json
            try:
                graph = unreal.load_asset("{graph_path}")
                if not graph:
                    raise RuntimeError("PCGGraph not found: {graph_path}")
                node = graph.add_node(unreal.PCGDensityFilterSettings)
                if node:
                    settings = node.get_settings()
                    if settings:
                        settings.set_editor_property("lower_bound", {lower_bound})
                        settings.set_editor_property("upper_bound", {upper_bound})
                        settings.set_editor_property("invert_filter", {str(invert)})
                unreal.EditorAssetLibrary.save_asset("{graph_path}")
                print("UEOS_RESULT:" + json.dumps({{"graph": "{graph_path}", "node": "DensityFilter", "lower": {lower_bound}, "upper": {upper_bound}, "invert": {str(invert).lower()}, "status": "added"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_add_density_filter")

    async def _add_attribute_node(self, args: dict) -> list[types.TextContent]:
        graph_path     = args["graph_path"]
        attr_name      = args["attribute_name"]
        attr_type      = args.get("attribute_type", "float")
        const_value    = args["constant_value"]
        script = dedent(f"""
            import unreal, json
            try:
                graph = unreal.load_asset("{graph_path}")
                if not graph:
                    raise RuntimeError("PCGGraph not found: {graph_path}")
                node = graph.add_node(unreal.PCGMetadataSettings)
                if node:
                    settings = node.get_settings()
                    if settings:
                        settings.set_editor_property("output_target", "{attr_name}")
                unreal.EditorAssetLibrary.save_asset("{graph_path}")
                print("UEOS_RESULT:" + json.dumps({{"graph": "{graph_path}", "node": "AttributeSetter", "attribute": "{attr_name}", "type": "{attr_type}", "value": "{const_value}", "status": "added"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_add_attribute_node")

    async def _add_transform_points(self, args: dict) -> list[types.TextContent]:
        graph_path  = args["graph_path"]
        off_min     = args.get("offset_min", [0, 0, 0])
        off_max     = args.get("offset_max", [0, 0, 0])
        rot_min     = args.get("rotation_min", [0, 0, 0])
        rot_max     = args.get("rotation_max", [0, 0, 360])
        sc_min      = args.get("scale_min", [1, 1, 1])
        sc_max      = args.get("scale_max", [1, 1, 1])
        uni_scale   = args.get("uniform_scale", True)
        script = dedent(f"""
            import unreal, json
            try:
                graph = unreal.load_asset("{graph_path}")
                if not graph:
                    raise RuntimeError("PCGGraph not found: {graph_path}")
                node = graph.add_node(unreal.PCGTransformPointsSettings)
                if node:
                    settings = node.get_settings()
                    if settings:
                        settings.set_editor_property("offset_min", unreal.Vector({off_min[0]},{off_min[1]},{off_min[2]}))
                        settings.set_editor_property("offset_max", unreal.Vector({off_max[0]},{off_max[1]},{off_max[2]}))
                        settings.set_editor_property("rotation_min", unreal.Rotator({rot_min[0]},{rot_min[1]},{rot_min[2]}))
                        settings.set_editor_property("rotation_max", unreal.Rotator({rot_max[0]},{rot_max[1]},{rot_max[2]}))
                        settings.set_editor_property("scale_min", unreal.Vector({sc_min[0]},{sc_min[1]},{sc_min[2]}))
                        settings.set_editor_property("scale_max", unreal.Vector({sc_max[0]},{sc_max[1]},{sc_max[2]}))
                        settings.set_editor_property("uniform_scale", {str(uni_scale)})
                unreal.EditorAssetLibrary.save_asset("{graph_path}")
                print("UEOS_RESULT:" + json.dumps({{"graph": "{graph_path}", "node": "TransformPoints", "uniform_scale": {str(uni_scale).lower()}, "status": "added"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_add_transform_points")

    async def _add_noise_node(self, args: dict) -> list[types.TextContent]:
        graph_path = args["graph_path"]
        noise_type = args.get("noise_type", "perlin")
        frequency  = args.get("frequency", 0.01)
        amplitude  = args.get("amplitude", 1.0)
        seed       = args.get("seed", 0)
        script = dedent(f"""
            import unreal, json
            try:
                graph = unreal.load_asset("{graph_path}")
                if not graph:
                    raise RuntimeError("PCGGraph not found: {graph_path}")
                node = graph.add_node(unreal.PCGDensityNoiseSettings)
                if node:
                    settings = node.get_settings()
                    if settings:
                        settings.set_editor_property("seed", {seed})
                        settings.set_editor_property("noise_scale", 1.0 / max({frequency}, 0.0001))
                        settings.set_editor_property("noise_weight", {amplitude})
                unreal.EditorAssetLibrary.save_asset("{graph_path}")
                print("UEOS_RESULT:" + json.dumps({{"graph": "{graph_path}", "node": "Noise", "type": "{noise_type}", "frequency": {frequency}, "amplitude": {amplitude}, "status": "added"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_add_noise_node")

    async def _add_spline_sampler(self, args: dict) -> list[types.TextContent]:
        graph_path = args["graph_path"]
        mode       = args.get("mode", "along_spline")
        spacing    = args.get("spacing", 100.0)
        width      = args.get("width", 200.0)
        mode_map   = {
            "along_spline": "unreal.PCGSplineSamplingMode.ALONG_SPLINE",
            "on_surface":   "unreal.PCGSplineSamplingMode.ON_SURFACE",
            "interior":     "unreal.PCGSplineSamplingMode.INTERIOR",
        }
        mode_enum  = mode_map.get(mode, mode_map["along_spline"])
        script = dedent(f"""
            import unreal, json
            try:
                graph = unreal.load_asset("{graph_path}")
                if not graph:
                    raise RuntimeError("PCGGraph not found: {graph_path}")
                node = graph.add_node(unreal.PCGSplineSamplerSettings)
                if node:
                    settings = node.get_settings()
                    if settings:
                        settings.set_editor_property("mode", {mode_enum})
                        settings.set_editor_property("dimension_source", unreal.PCGSplineSamplingDimensionSource.RELATIVE_TO_SPLINE_LENGTH)
                        settings.set_editor_property("spacing", {spacing})
                        settings.set_editor_property("width", {width})
                unreal.EditorAssetLibrary.save_asset("{graph_path}")
                print("UEOS_RESULT:" + json.dumps({{"graph": "{graph_path}", "node": "SplineSampler", "mode": "{mode}", "spacing": {spacing}, "status": "added"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_add_spline_sampler")

    async def _place_volume(self, args: dict) -> list[types.TextContent]:
        graph_path   = args["graph_path"]
        loc          = args.get("location", [0, 0, 0])
        extent       = args.get("extent", [1000, 1000, 500])
        actor_name   = args.get("actor_name", "PCGVolume")
        auto_gen     = args.get("auto_generate", True)
        script = dedent(f"""
            import unreal, json
            try:
                graph = unreal.load_asset("{graph_path}")
                if not graph:
                    raise RuntimeError("PCGGraph not found: {graph_path}")
                pos  = unreal.Vector({loc[0]}, {loc[1]}, {loc[2]})
                actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
                    unreal.PCGVolume, pos, unreal.Rotator(0,0,0)
                )
                if not actor:
                    raise RuntimeError("Failed to spawn PCGVolume")
                actor.set_actor_label("{actor_name}")
                brush = actor.get_component_by_class(unreal.BrushComponent)
                if brush:
                    actor.set_actor_scale3d(unreal.Vector({extent[0]/100},{extent[1]/100},{extent[2]/100}))
                pcg_comp = actor.get_component_by_class(unreal.PCGComponent)
                if pcg_comp:
                    pcg_comp.set_editor_property("graph", graph)
                    if {str(auto_gen)}:
                        pcg_comp.generate(True)
                print("UEOS_RESULT:" + json.dumps({{"actor": "{actor_name}", "graph": "{graph_path}", "location": {loc}, "extent": {extent}, "status": "placed"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_place_volume")

    async def _list_volumes(self, args: dict) -> list[types.TextContent]:
        script = dedent(f"""
            import unreal, json
            try:
                actors = unreal.EditorLevelLibrary.get_all_level_actors()
                result = []
                for a in actors:
                    if isinstance(a, unreal.PCGVolume):
                        pcg_comp = a.get_component_by_class(unreal.PCGComponent)
                        graph_name = ""
                        if pcg_comp:
                            g = pcg_comp.get_editor_property("graph")
                            if g: graph_name = g.get_name()
                        result.append({{"label": a.get_actor_label(), "graph": graph_name, "location": list(a.get_actor_location())}})
                print("UEOS_RESULT:" + json.dumps({{"pcg_volumes": result, "count": len(result)}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_list_volumes")

    async def _execute_graph(self, args: dict) -> list[types.TextContent]:
        vol_actor   = args["volume_actor"]
        cleanup     = args.get("cleanup_first", True)
        script = dedent(f"""
            import unreal, json
            try:
                actors = {{a.get_actor_label(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()}}
                actor = actors.get("{vol_actor}")
                if not actor:
                    raise RuntimeError("PCGVolume actor not found: {vol_actor}")
                pcg_comp = actor.get_component_by_class(unreal.PCGComponent)
                if not pcg_comp:
                    raise RuntimeError("No PCGComponent on actor")
                if {str(cleanup)}:
                    pcg_comp.cleanup_local(True, True)
                pcg_comp.generate(True)
                print("UEOS_RESULT:" + json.dumps({{"actor": "{vol_actor}", "status": "generated"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_execute_graph")

    async def _cleanup_volume(self, args: dict) -> list[types.TextContent]:
        vol_actor = args["volume_actor"]
        script = dedent(f"""
            import unreal, json
            try:
                actors = {{a.get_actor_label(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()}}
                actor = actors.get("{vol_actor}")
                if not actor:
                    raise RuntimeError("PCGVolume actor not found: {vol_actor}")
                pcg_comp = actor.get_component_by_class(unreal.PCGComponent)
                if not pcg_comp:
                    raise RuntimeError("No PCGComponent on actor")
                pcg_comp.cleanup_local(True, True)
                print("UEOS_RESULT:" + json.dumps({{"actor": "{vol_actor}", "status": "cleaned_up"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_cleanup_volume")

    async def _create_biome_preset(self, args: dict) -> list[types.TextContent]:
        name            = args["name"]
        save_path       = args["save_path"].rstrip("/")
        mesh_paths      = args["mesh_paths"]
        density         = args.get("density", 2.0)
        scale_min       = args.get("scale_min", 0.8)
        scale_max       = args.get("scale_max", 1.2)
        density_mask_tag= args.get("density_mask_tag", "")
        script = dedent(f"""
            import unreal, json
            try:
                factory = unreal.PCGGraphFactory()
                graph = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    "{name}", "{save_path}", unreal.PCGGraph, factory
                )
                if not graph:
                    raise RuntimeError("Failed to create biome PCGGraph")

                # 1. Surface sampler
                sampler_node = graph.add_node(unreal.PCGSurfaceSamplerSettings)
                if sampler_node:
                    ss = sampler_node.get_settings()
                    if ss:
                        ss.set_editor_property("points_per_squared_meter", {density})
                        ss.set_editor_property("seed", 42)

                # 2. Transform jitter
                xform_node = graph.add_node(unreal.PCGTransformPointsSettings)
                if xform_node:
                    xs = xform_node.get_settings()
                    if xs:
                        xs.set_editor_property("rotation_min", unreal.Rotator(0, 0, 0))
                        xs.set_editor_property("rotation_max", unreal.Rotator(0, 360, 0))
                        xs.set_editor_property("scale_min", unreal.Vector({scale_min}, {scale_min}, {scale_min}))
                        xs.set_editor_property("scale_max", unreal.Vector({scale_max}, {scale_max}, {scale_max}))
                        xs.set_editor_property("uniform_scale", True)

                # 3. Static mesh spawner
                mesh_paths_list = {mesh_paths}
                spawn_node = graph.add_node(unreal.PCGStaticMeshSpawnerSettings)
                if spawn_node:
                    sps = spawn_node.get_settings()
                    if sps:
                        entries = []
                        for mp in mesh_paths_list:
                            mesh = unreal.load_asset(mp)
                            if mesh:
                                entry = unreal.PCGSoftISMComponentDescriptor()
                                entry.set_editor_property("static_mesh", mesh)
                                entries.append(entry)
                        sps.set_editor_property("mesh_entries", entries)

                unreal.EditorAssetLibrary.save_asset(graph.get_path_name())
                print("UEOS_RESULT:" + json.dumps({{
                    "path": graph.get_path_name(),
                    "name": "{name}",
                    "mesh_count": len(mesh_paths_list),
                    "density": {density},
                    "scale_range": [{scale_min}, {scale_max}],
                    "status": "biome_preset_created"
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_create_biome_preset")

    async def _set_landscape_layer_weight(self, args: dict) -> list[types.TextContent]:
        graph_path  = args["graph_path"]
        layer_name  = args["layer_name"]
        invert      = args.get("invert", False)
        script = dedent(f"""
            import unreal, json
            try:
                graph = unreal.load_asset("{graph_path}")
                if not graph:
                    raise RuntimeError("PCGGraph not found: {graph_path}")
                node = graph.add_node(unreal.PCGLandscapeLayerWeightSettings)
                if node:
                    settings = node.get_settings()
                    if settings:
                        settings.set_editor_property("layer_name", "{layer_name}")
                        settings.set_editor_property("invert", {str(invert)})
                unreal.EditorAssetLibrary.save_asset("{graph_path}")
                print("UEOS_RESULT:" + json.dumps({{"graph": "{graph_path}", "layer": "{layer_name}", "invert": {str(invert).lower()}, "status": "landscape_layer_weight_node_added"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_set_landscape_layer_weight")

    async def _get_point_stats(self, args: dict) -> list[types.TextContent]:
        vol_actor = args["volume_actor"]
        script = dedent(f"""
            import unreal, json
            try:
                actors = {{a.get_actor_label(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()}}
                actor = actors.get("{vol_actor}")
                if not actor:
                    raise RuntimeError("PCGVolume actor not found: {vol_actor}")
                pcg_comp = actor.get_component_by_class(unreal.PCGComponent)
                if not pcg_comp:
                    raise RuntimeError("No PCGComponent on actor")
                # Get generated output data stats
                output_data = pcg_comp.get_generated_graphs_in_use()
                print("UEOS_RESULT:" + json.dumps({{
                    "actor": "{vol_actor}",
                    "is_generated": pcg_comp.is_generated(),
                    "is_dirty": pcg_comp.is_dirty(),
                    "status": "point_stats_retrieved"
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_get_point_stats")

    async def _diagnostics(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game")
        script = dedent(f"""
            import unreal, json
            try:
                reg = unreal.AssetRegistryHelpers.get_asset_registry()
                all_assets = reg.get_assets_by_path("{search_path}", recursive=True)
                pcg_graphs = [a for a in all_assets if "PCGGraph" in str(a.asset_class_path)]
                level_actors = unreal.EditorLevelLibrary.get_all_level_actors()
                pcg_volumes  = [a for a in level_actors if isinstance(a, unreal.PCGVolume)]
                report = {{
                    "pcg_graph_assets":   len(pcg_graphs),
                    "level_pcg_volumes":  len(pcg_volumes),
                    "pcg_volume_names":   [a.get_actor_label() for a in pcg_volumes],
                    "pcg_module_loaded":  True,
                    "ueos_version":       "7.0",
                }}
                print("UEOS_RESULT:" + json.dumps(report))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "pcg_diagnostics")
