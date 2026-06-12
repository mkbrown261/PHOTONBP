"""
UEOS Phase 7 — Chaos Physics Tools
MCP tools for Chaos Destruction, cloth simulation, rigid body constraints,
physics materials, and field systems in Unreal Engine 5.4.

25 tools — prefix: phys_
"""

from __future__ import annotations
import json
from textwrap import dedent
from mcp import types


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

DAMAGE_THRESHOLD_TYPES = {
    "default":   "unreal.GeometryCollectionDamageThresholdType.SCALED_BY_SIZE",
    "absolute":  "unreal.GeometryCollectionDamageThresholdType.ABSOLUTE",
    "scaled":    "unreal.GeometryCollectionDamageThresholdType.SCALED_BY_SIZE",
}

CLUSTER_CONNECTION_TYPES = {
    "none":        "unreal.ClusterConnectionTypeEnum.NONE",
    "point":       "unreal.ClusterConnectionTypeEnum.POINT_IMPLICIT",
    "delaunay":    "unreal.ClusterConnectionTypeEnum.DELAUNAY",
    "min_spanning":"unreal.ClusterConnectionTypeEnum.MINIMUM_SPANNING_SUBTREE",
    "all_pairs":   "unreal.ClusterConnectionTypeEnum.ALL_PAIRS",
}

FIELD_TYPES = {
    "radial_falloff":   "unreal.RadialFalloff",
    "radial_vector":    "unreal.RadialVector",
    "uniform_vector":   "unreal.UniformVector",
    "uniform_scalar":   "unreal.UniformScalar",
    "plane_falloff":    "unreal.PlaneFalloff",
    "box_falloff":      "unreal.BoxFalloff",
}

CLOTH_SOLVERS = {
    "nv_cloth": "unreal.ClothingSimulationFactoryNvCloth",
    "chaos":    "unreal.ChaosClothingSimulationFactory",
}

PHYS_SURFACE_TYPES = {
    "default":  "EPhysicalSurface.SurfaceType_Default",
    "grass":    "EPhysicalSurface.SurfaceType1",
    "gravel":   "EPhysicalSurface.SurfaceType2",
    "mud":      "EPhysicalSurface.SurfaceType3",
    "metal":    "EPhysicalSurface.SurfaceType4",
    "wood":     "EPhysicalSurface.SurfaceType5",
    "glass":    "EPhysicalSurface.SurfaceType6",
    "flesh":    "EPhysicalSurface.SurfaceType7",
}

CONSTRAINT_MOTION_TYPES = {
    "free":     "unreal.ConstraintMotion.FREE",
    "limited":  "unreal.ConstraintMotion.LIMITED",
    "locked":   "unreal.ConstraintMotion.LOCKED",
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _jl(lst: list) -> str:
    return json.dumps(lst)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class ChaosPhysicsTools:
    """MCP tool handler for Chaos Physics / destruction in UE 5.4."""

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
            # ── Geometry Collections ──────────────────────────────────
            types.Tool(
                name="phys_create_geometry_collection",
                description=(
                    "Create a Geometry Collection asset from a Static Mesh. "
                    "The resulting asset is the foundation for Chaos Destruction fracturing."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "static_mesh_path": {"type": "string", "description": "Asset path of the source Static Mesh (e.g. /Game/Meshes/SM_Rock)."},
                        "save_path":        {"type": "string", "description": "Folder to save the Geometry Collection asset."},
                        "name":             {"type": "string", "description": "Name for the new Geometry Collection asset."},
                    },
                    "required": ["static_mesh_path", "save_path", "name"],
                },
            ),
            types.Tool(
                name="phys_fracture_voronoi",
                description="Apply Voronoi (uniform) fracturing to a Geometry Collection asset.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "gc_path":     {"type": "string", "description": "Asset path of the Geometry Collection."},
                        "cell_count":  {"type": "integer", "description": "Number of Voronoi cells (fracture pieces). Default 20.", "default": 20},
                        "seed":        {"type": "integer", "description": "Random seed for reproducibility. Default 42.", "default": 42},
                    },
                    "required": ["gc_path"],
                },
            ),
            types.Tool(
                name="phys_fracture_clustered",
                description="Apply clustered Voronoi fracturing (creates hierarchical damage levels).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "gc_path":         {"type": "string", "description": "Asset path of the Geometry Collection."},
                        "cluster_count":   {"type": "integer", "description": "Number of cluster sites.", "default": 8},
                        "cell_count":      {"type": "integer", "description": "Voronoi cells per cluster.", "default": 12},
                        "cluster_sites":   {"type": "integer", "description": "Top-level cluster count.", "default": 4},
                    },
                    "required": ["gc_path"],
                },
            ),
            types.Tool(
                name="phys_fracture_slice",
                description="Apply planar-slice fracturing (cuts along axis-aligned planes).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "gc_path":    {"type": "string", "description": "Asset path of the Geometry Collection."},
                        "slices_x":   {"type": "integer", "description": "Slices along X axis.", "default": 2},
                        "slices_y":   {"type": "integer", "description": "Slices along Y axis.", "default": 2},
                        "slices_z":   {"type": "integer", "description": "Slices along Z axis.", "default": 2},
                        "angle_variation": {"type": "number", "description": "Random angle variation in degrees.", "default": 0.0},
                    },
                    "required": ["gc_path"],
                },
            ),
            types.Tool(
                name="phys_set_damage_thresholds",
                description="Set the damage thresholds for each level of a Geometry Collection hierarchy.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "gc_path":     {"type": "string", "description": "Asset path of the Geometry Collection."},
                        "thresholds":  {"type": "array", "items": {"type": "number"}, "description": "List of damage thresholds per level (e.g. [500, 250, 100])."},
                        "threshold_type": {"type": "string", "enum": ["default", "absolute", "scaled"], "description": "How thresholds scale.", "default": "default"},
                    },
                    "required": ["gc_path", "thresholds"],
                },
            ),
            types.Tool(
                name="phys_set_cluster_connection_type",
                description="Set how fractured pieces cluster together in a Geometry Collection.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "gc_path":           {"type": "string"},
                        "connection_type":   {"type": "string", "enum": ["none", "point", "delaunay", "min_spanning", "all_pairs"], "default": "delaunay"},
                    },
                    "required": ["gc_path"],
                },
            ),
            types.Tool(
                name="phys_spawn_geometry_collection",
                description="Spawn a Geometry Collection actor in the current level.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "gc_path":   {"type": "string", "description": "Asset path of the Geometry Collection asset."},
                        "location":  {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "description": "[X, Y, Z] world location.", "default": [0, 0, 0]},
                        "rotation":  {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "description": "[Pitch, Yaw, Roll].", "default": [0, 0, 0]},
                        "scale":     {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "description": "[Sx, Sy, Sz].", "default": [1, 1, 1]},
                        "actor_name":{"type": "string", "description": "Optional label for the placed actor."},
                        "simulate_on_spawn": {"type": "boolean", "description": "Start physics simulation immediately.", "default": True},
                    },
                    "required": ["gc_path"],
                },
            ),
            types.Tool(
                name="phys_list_geometry_collections",
                description="List all Geometry Collection assets in a content folder.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_path": {"type": "string", "description": "Content path to search (recursive).", "default": "/Game"},
                    },
                    "required": [],
                },
            ),
            types.Tool(
                name="phys_get_geometry_collection_info",
                description="Return fracture level count, piece count, and damage threshold info for a Geometry Collection.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "gc_path": {"type": "string", "description": "Asset path of the Geometry Collection."},
                    },
                    "required": ["gc_path"],
                },
            ),

            # ── Physics Materials ─────────────────────────────────────
            types.Tool(
                name="phys_create_physics_material",
                description="Create a Physics Material asset with friction, restitution, and density settings.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":               {"type": "string"},
                        "save_path":          {"type": "string"},
                        "friction":           {"type": "number", "description": "Static friction coefficient.", "default": 0.7},
                        "restitution":        {"type": "number", "description": "Bounciness (0=no bounce, 1=perfectly elastic).", "default": 0.3},
                        "density":            {"type": "number", "description": "Material density (g/cm³).", "default": 1.0},
                        "surface_type":       {"type": "string", "enum": ["default", "grass", "gravel", "mud", "metal", "wood", "glass", "flesh"], "default": "default"},
                        "override_friction_combine": {"type": "boolean", "default": False},
                        "override_restitution_combine": {"type": "boolean", "default": False},
                    },
                    "required": ["name", "save_path"],
                },
            ),
            types.Tool(
                name="phys_list_physics_materials",
                description="List all Physics Material assets in a content folder.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_path": {"type": "string", "default": "/Game"},
                    },
                    "required": [],
                },
            ),
            types.Tool(
                name="phys_assign_physics_material",
                description="Assign a Physics Material to a Static Mesh asset's body setup.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "mesh_path":    {"type": "string", "description": "Asset path of the Static Mesh."},
                        "phys_mat_path":{"type": "string", "description": "Asset path of the Physics Material."},
                    },
                    "required": ["mesh_path", "phys_mat_path"],
                },
            ),

            # ── Rigid Body Constraints ────────────────────────────────
            types.Tool(
                name="phys_create_constraint_actor",
                description="Place a Physics Constraint Actor between two actors or components in the level.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "actor_a":          {"type": "string", "description": "Name or path of first actor."},
                        "actor_b":          {"type": "string", "description": "Name or path of second actor."},
                        "location":         {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 0]},
                        "linear_x":         {"type": "string", "enum": ["free", "limited", "locked"], "default": "locked"},
                        "linear_y":         {"type": "string", "enum": ["free", "limited", "locked"], "default": "locked"},
                        "linear_z":         {"type": "string", "enum": ["free", "limited", "locked"], "default": "locked"},
                        "angular_swing1":   {"type": "string", "enum": ["free", "limited", "locked"], "default": "free"},
                        "angular_swing2":   {"type": "string", "enum": ["free", "limited", "locked"], "default": "free"},
                        "angular_twist":    {"type": "string", "enum": ["free", "limited", "locked"], "default": "free"},
                        "linear_limit":     {"type": "number", "description": "Limit in cm for limited linear motion.", "default": 100.0},
                        "swing1_limit_deg": {"type": "number", "description": "Swing1 angle limit in degrees.", "default": 45.0},
                        "swing2_limit_deg": {"type": "number", "description": "Swing2 angle limit in degrees.", "default": 45.0},
                        "twist_limit_deg":  {"type": "number", "description": "Twist angle limit in degrees.", "default": 45.0},
                        "disable_collision":{"type": "boolean", "default": True},
                        "actor_name":       {"type": "string", "description": "Label for the placed constraint actor."},
                    },
                    "required": ["actor_a", "actor_b"],
                },
            ),
            types.Tool(
                name="phys_list_constraints",
                description="List all Physics Constraint Actors in the current level.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            types.Tool(
                name="phys_set_constraint_drives",
                description="Enable position/velocity drives on a Physics Constraint Actor for motor-like behaviour.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "constraint_actor": {"type": "string", "description": "Name of the constraint actor in the level."},
                        "linear_drive":     {"type": "boolean", "default": False},
                        "angular_drive":    {"type": "boolean", "default": False},
                        "target_position":  {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 0]},
                        "target_rotation":  {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 0]},
                        "position_strength":{"type": "number", "default": 100.0},
                        "velocity_strength":{"type": "number", "default": 0.0},
                    },
                    "required": ["constraint_actor"],
                },
            ),

            # ── Cloth Simulation ──────────────────────────────────────
            types.Tool(
                name="phys_add_cloth_component",
                description="Add a Clothing Simulation component (Chaos Cloth) to a Skeletal Mesh Blueprint.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bp_path":       {"type": "string", "description": "Asset path of the Skeletal Mesh Blueprint."},
                        "mesh_section":  {"type": "integer", "description": "Skeletal Mesh LOD section index to apply cloth.", "default": 0},
                        "solver":        {"type": "string", "enum": ["chaos", "nv_cloth"], "default": "chaos"},
                        "max_distance":  {"type": "number", "description": "Maximum cloth distance from animated position.", "default": 25.0},
                        "backstop_radius":{"type": "number", "description": "Backstop sphere radius.", "default": 5.0},
                    },
                    "required": ["bp_path"],
                },
            ),
            types.Tool(
                name="phys_set_cloth_config",
                description="Set Chaos Cloth simulation config on a Skeletal Mesh component (stiffness, damping, gravity scale).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bp_path":           {"type": "string"},
                        "stiffness":         {"type": "number", "description": "Cloth stiffness 0–1.", "default": 0.5},
                        "damping":           {"type": "number", "description": "Cloth damping 0–1.", "default": 0.01},
                        "gravity_scale":     {"type": "number", "description": "Gravity scale applied to cloth.", "default": 1.0},
                        "wind_speed":        {"type": "number", "description": "Simulated wind speed (cm/s).", "default": 0.0},
                        "num_iterations":    {"type": "integer", "description": "Solver iterations per tick.", "default": 1},
                    },
                    "required": ["bp_path"],
                },
            ),

            # ── Field System ──────────────────────────────────────────
            types.Tool(
                name="phys_create_radial_impulse",
                description="Spawn a Radial Force Actor that applies an impulse to nearby physics objects.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "location":     {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 0]},
                        "radius":       {"type": "number", "description": "Influence radius (cm).", "default": 500.0},
                        "strength":     {"type": "number", "description": "Impulse strength.", "default": 1000.0},
                        "falloff":      {"type": "string", "enum": ["constant", "linear", "inverse_square"], "default": "linear"},
                        "impulse_velocity_change": {"type": "boolean", "description": "Use velocity-change mode.", "default": False},
                        "fire_on_spawn": {"type": "boolean", "default": True},
                        "actor_name":   {"type": "string"},
                    },
                    "required": [],
                },
            ),
            types.Tool(
                name="phys_create_field_system",
                description="Spawn a Chaos Field System actor with a radial vector field for ongoing force application.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "location":     {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 0]},
                        "magnitude":    {"type": "number", "description": "Field magnitude.", "default": 500.0},
                        "falloff_radius":{"type": "number", "description": "Outer radius of the field.", "default": 1000.0},
                        "field_type":   {"type": "string", "enum": ["radial_falloff", "radial_vector", "uniform_vector", "uniform_scalar", "plane_falloff", "box_falloff"], "default": "radial_vector"},
                        "actor_name":   {"type": "string"},
                    },
                    "required": [],
                },
            ),

            # ── Rigid Body Physics ────────────────────────────────────
            types.Tool(
                name="phys_set_actor_physics",
                description="Enable/configure physics simulation on an actor's root primitive component.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "actor_name":      {"type": "string", "description": "Label of the actor in the current level."},
                        "simulate_physics":{"type": "boolean", "default": True},
                        "enable_gravity":  {"type": "boolean", "default": True},
                        "mass_kg":         {"type": "number", "description": "Override mass (kg). 0 = use default.", "default": 0.0},
                        "linear_damping":  {"type": "number", "default": 0.01},
                        "angular_damping": {"type": "number", "default": 0.0},
                        "ccd":             {"type": "boolean", "description": "Enable Continuous Collision Detection.", "default": False},
                    },
                    "required": ["actor_name"],
                },
            ),
            types.Tool(
                name="phys_apply_impulse",
                description="Apply an instant impulse to an actor's physics body at runtime.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "actor_name":   {"type": "string"},
                        "impulse":      {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "description": "[X, Y, Z] impulse vector.", "default": [0, 0, 1000]},
                        "velocity_change": {"type": "boolean", "description": "If true, ignores mass.", "default": False},
                        "at_location":  {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "description": "World location of impulse. Empty = center of mass.", "default": []},
                    },
                    "required": ["actor_name", "impulse"],
                },
            ),
            types.Tool(
                name="phys_set_collision_profile",
                description="Set the collision profile on a Static Mesh Component or primitive in the level.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "actor_name":     {"type": "string"},
                        "profile_name":   {"type": "string", "description": "Profile name (e.g. BlockAll, OverlapAll, PhysicsActor, NoCollision)."},
                        "component_name": {"type": "string", "description": "Optional component name. Empty = root primitive.", "default": ""},
                    },
                    "required": ["actor_name", "profile_name"],
                },
            ),

            # ── Destruction Helpers ───────────────────────────────────
            types.Tool(
                name="phys_set_break_event_notify",
                description="Enable break event notifications on a Geometry Collection component so Blueprints can respond.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "actor_name": {"type": "string", "description": "Name of the Geometry Collection actor in the level."},
                        "enabled":    {"type": "boolean", "default": True},
                        "minimum_mass_threshold": {"type": "number", "description": "Minimum broken-piece mass to trigger events.", "default": 0.0},
                    },
                    "required": ["actor_name"],
                },
            ),
            types.Tool(
                name="phys_reset_geometry_collection",
                description="Reset a Geometry Collection actor to its initial unbroken state at runtime.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "actor_name": {"type": "string"},
                    },
                    "required": ["actor_name"],
                },
            ),

            # ── Diagnostics ───────────────────────────────────────────
            types.Tool(
                name="phys_diagnostics",
                description="Return a diagnostic summary of Chaos physics actors and Geometry Collections in the current level.",
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
            "phys_create_geometry_collection":  self._create_geometry_collection,
            "phys_fracture_voronoi":            self._fracture_voronoi,
            "phys_fracture_clustered":          self._fracture_clustered,
            "phys_fracture_slice":              self._fracture_slice,
            "phys_set_damage_thresholds":       self._set_damage_thresholds,
            "phys_set_cluster_connection_type": self._set_cluster_connection_type,
            "phys_spawn_geometry_collection":   self._spawn_geometry_collection,
            "phys_list_geometry_collections":   self._list_geometry_collections,
            "phys_get_geometry_collection_info":self._get_geometry_collection_info,
            "phys_create_physics_material":     self._create_physics_material,
            "phys_list_physics_materials":      self._list_physics_materials,
            "phys_assign_physics_material":     self._assign_physics_material,
            "phys_create_constraint_actor":     self._create_constraint_actor,
            "phys_list_constraints":            self._list_constraints,
            "phys_set_constraint_drives":       self._set_constraint_drives,
            "phys_add_cloth_component":         self._add_cloth_component,
            "phys_set_cloth_config":            self._set_cloth_config,
            "phys_create_radial_impulse":       self._create_radial_impulse,
            "phys_create_field_system":         self._create_field_system,
            "phys_set_actor_physics":           self._set_actor_physics,
            "phys_apply_impulse":               self._apply_impulse,
            "phys_set_collision_profile":       self._set_collision_profile,
            "phys_set_break_event_notify":      self._set_break_event_notify,
            "phys_reset_geometry_collection":   self._reset_geometry_collection,
            "phys_diagnostics":                 self._diagnostics,
        }
        fn = dispatch.get(name)
        if fn is None:
            return [types.TextContent(type="text", text=f"Unknown chaos_physics tool: {name}")]
        return await fn(args)

    # ------------------------------------------------------------------
    # Implementations
    # ------------------------------------------------------------------

    async def _create_geometry_collection(self, args: dict) -> list[types.TextContent]:
        mesh_path = args["static_mesh_path"]
        save_path = args["save_path"].rstrip("/")
        name      = args["name"]
        script = dedent(f"""
            import unreal, json
            try:
                mesh = unreal.load_asset("{mesh_path}")
                if not mesh:
                    raise RuntimeError("Static Mesh not found: {mesh_path}")
                factory = unreal.GeometryCollectionFactory()
                task = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    "{name}", "{save_path}", unreal.GeometryCollection, factory
                )
                if not task:
                    raise RuntimeError("Failed to create GeometryCollection asset")
                gc_tool = unreal.GeometryCollectionEngineConversion()
                gc_tool.append_static_mesh(task, mesh, unreal.Transform())
                unreal.EditorAssetLibrary.save_asset(task.get_path_name())
                print("UEOS_RESULT:" + json.dumps({{"path": task.get_path_name(), "name": "{name}", "status": "created"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_create_geometry_collection")

    async def _fracture_voronoi(self, args: dict) -> list[types.TextContent]:
        gc_path    = args["gc_path"]
        cell_count = args.get("cell_count", 20)
        seed       = args.get("seed", 42)
        script = dedent(f"""
            import unreal, json
            try:
                gc = unreal.load_asset("{gc_path}")
                if not gc:
                    raise RuntimeError("GC not found: {gc_path}")
                settings = unreal.VoronoiFractureSettings()
                settings.set_editor_property("number_of_voronoi_sites", {cell_count})
                settings.set_editor_property("random_seed", {seed})
                cmd = unreal.GeometryCollectionCommandPlugin()
                cmd.voronoi_fracture([gc], settings, [unreal.Transform()], False)
                unreal.EditorAssetLibrary.save_asset("{gc_path}")
                print("UEOS_RESULT:" + json.dumps({{"gc_path": "{gc_path}", "cell_count": {cell_count}, "seed": {seed}, "status": "voronoi_fracture_applied"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_fracture_voronoi")

    async def _fracture_clustered(self, args: dict) -> list[types.TextContent]:
        gc_path       = args["gc_path"]
        cluster_count = args.get("cluster_count", 8)
        cell_count    = args.get("cell_count", 12)
        cluster_sites = args.get("cluster_sites", 4)
        script = dedent(f"""
            import unreal, json
            try:
                gc = unreal.load_asset("{gc_path}")
                if not gc:
                    raise RuntimeError("GC not found: {gc_path}")
                settings = unreal.ClusteredVoronoiFractureSettings()
                settings.set_editor_property("number_of_clusters", {cluster_count})
                settings.set_editor_property("sites_per_cluster", {cell_count})
                settings.set_editor_property("number_of_cluster_sites", {cluster_sites})
                cmd = unreal.GeometryCollectionCommandPlugin()
                cmd.clustered_voronoi_fracture([gc], settings, [unreal.Transform()], False)
                unreal.EditorAssetLibrary.save_asset("{gc_path}")
                print("UEOS_RESULT:" + json.dumps({{"gc_path": "{gc_path}", "clusters": {cluster_count}, "cells_per_cluster": {cell_count}, "status": "clustered_fracture_applied"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_fracture_clustered")

    async def _fracture_slice(self, args: dict) -> list[types.TextContent]:
        gc_path   = args["gc_path"]
        sx        = args.get("slices_x", 2)
        sy        = args.get("slices_y", 2)
        sz        = args.get("slices_z", 2)
        angle_var = args.get("angle_variation", 0.0)
        script = dedent(f"""
            import unreal, json
            try:
                gc = unreal.load_asset("{gc_path}")
                if not gc:
                    raise RuntimeError("GC not found: {gc_path}")
                settings = unreal.PlaneCutFractureSettings()
                settings.set_editor_property("grid_x", {sx})
                settings.set_editor_property("grid_y", {sy})
                settings.set_editor_property("grid_z", {sz})
                settings.set_editor_property("random_angle_variation", {angle_var})
                cmd = unreal.GeometryCollectionCommandPlugin()
                cmd.plane_cut_fracture([gc], settings, [unreal.Transform()], False)
                unreal.EditorAssetLibrary.save_asset("{gc_path}")
                print("UEOS_RESULT:" + json.dumps({{"gc_path": "{gc_path}", "slices": [{sx},{sy},{sz}], "status": "slice_fracture_applied"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_fracture_slice")

    async def _set_damage_thresholds(self, args: dict) -> list[types.TextContent]:
        gc_path    = args["gc_path"]
        thresholds = args["thresholds"]
        thresh_key = args.get("threshold_type", "default")
        thresh_enum= DAMAGE_THRESHOLD_TYPES.get(thresh_key, DAMAGE_THRESHOLD_TYPES["default"])
        script = dedent(f"""
            import unreal, json
            try:
                gc = unreal.load_asset("{gc_path}")
                if not gc:
                    raise RuntimeError("GC not found: {gc_path}")
                gc.set_editor_property("damage_threshold", {thresholds})
                gc.set_editor_property("damage_threshold_type", {thresh_enum})
                unreal.EditorAssetLibrary.save_asset("{gc_path}")
                print("UEOS_RESULT:" + json.dumps({{"gc_path": "{gc_path}", "thresholds": {thresholds}, "status": "thresholds_set"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_set_damage_thresholds")

    async def _set_cluster_connection_type(self, args: dict) -> list[types.TextContent]:
        gc_path     = args["gc_path"]
        conn_key    = args.get("connection_type", "delaunay")
        conn_enum   = CLUSTER_CONNECTION_TYPES.get(conn_key, CLUSTER_CONNECTION_TYPES["delaunay"])
        script = dedent(f"""
            import unreal, json
            try:
                gc = unreal.load_asset("{gc_path}")
                if not gc:
                    raise RuntimeError("GC not found: {gc_path}")
                gc.set_editor_property("cluster_connection_type", {conn_enum})
                unreal.EditorAssetLibrary.save_asset("{gc_path}")
                print("UEOS_RESULT:" + json.dumps({{"gc_path": "{gc_path}", "connection_type": "{conn_key}", "status": "connection_type_set"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_set_cluster_connection_type")

    async def _spawn_geometry_collection(self, args: dict) -> list[types.TextContent]:
        gc_path    = args["gc_path"]
        loc        = args.get("location", [0, 0, 0])
        rot        = args.get("rotation", [0, 0, 0])
        scale      = args.get("scale", [1, 1, 1])
        actor_name = args.get("actor_name", "GC_Actor")
        simulate   = args.get("simulate_on_spawn", True)
        script = dedent(f"""
            import unreal, json
            try:
                world = unreal.EditorLevelLibrary.get_editor_world()
                gc_asset = unreal.load_asset("{gc_path}")
                if not gc_asset:
                    raise RuntimeError("GC not found: {gc_path}")
                loc = unreal.Vector({loc[0]}, {loc[1]}, {loc[2]})
                rot = unreal.Rotator({rot[0]}, {rot[1]}, {rot[2]})
                actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
                    unreal.GeometryCollectionActor, loc, rot
                )
                if not actor:
                    raise RuntimeError("Failed to spawn GC actor")
                actor.set_actor_label("{actor_name}")
                actor.set_actor_scale3d(unreal.Vector({scale[0]}, {scale[1]}, {scale[2]}))
                gc_comp = actor.get_component_by_class(unreal.GeometryCollectionComponent)
                if gc_comp:
                    gc_comp.set_editor_property("chaosSolverActor", None)
                    gc_comp.set_chao_rest_collection(gc_asset)
                    gc_comp.set_editor_property("simulate_physics", {str(simulate)})
                print("UEOS_RESULT:" + json.dumps({{"actor": "{actor_name}", "gc_path": "{gc_path}", "location": {loc}, "status": "spawned"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_spawn_geometry_collection")

    async def _list_geometry_collections(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game")
        script = dedent(f"""
            import unreal, json
            try:
                reg = unreal.AssetRegistryHelpers.get_asset_registry()
                assets = reg.get_assets_by_path("{search_path}", recursive=True)
                results = []
                for a in assets:
                    if "GeometryCollection" in str(a.asset_class_path):
                        results.append({{"name": str(a.asset_name), "path": str(a.object_path)}})
                print("UEOS_RESULT:" + json.dumps({{"geometry_collections": results, "count": len(results)}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_list_geometry_collections")

    async def _get_geometry_collection_info(self, args: dict) -> list[types.TextContent]:
        gc_path = args["gc_path"]
        script = dedent(f"""
            import unreal, json
            try:
                gc = unreal.load_asset("{gc_path}")
                if not gc:
                    raise RuntimeError("GC not found: {gc_path}")
                info = {{
                    "path": "{gc_path}",
                    "num_transform_elements": gc.num_elements(unreal.GeometryCollectionGuidFacade),
                    "damage_threshold": list(gc.get_editor_property("damage_threshold") or []),
                    "cluster_connection_type": str(gc.get_editor_property("cluster_connection_type")),
                }}
                print("UEOS_RESULT:" + json.dumps(info))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_get_geometry_collection_info")

    async def _create_physics_material(self, args: dict) -> list[types.TextContent]:
        name        = args["name"]
        save_path   = args["save_path"].rstrip("/")
        friction    = args.get("friction", 0.7)
        restitution = args.get("restitution", 0.3)
        density     = args.get("density", 1.0)
        surf_key    = args.get("surface_type", "default")
        surf_enum   = PHYS_SURFACE_TYPES.get(surf_key, PHYS_SURFACE_TYPES["default"])
        override_f  = args.get("override_friction_combine", False)
        override_r  = args.get("override_restitution_combine", False)
        script = dedent(f"""
            import unreal, json
            try:
                factory = unreal.PhysicalMaterialFactory()
                mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    "{name}", "{save_path}", unreal.PhysicalMaterial, factory
                )
                if not mat:
                    raise RuntimeError("Failed to create PhysicsMaterial")
                mat.set_editor_property("friction", {friction})
                mat.set_editor_property("restitution", {restitution})
                mat.set_editor_property("density", {density})
                mat.set_editor_property("surface_type", {surf_enum})
                mat.set_editor_property("override_friction_combine_mode", {str(override_f)})
                mat.set_editor_property("override_restitution_combine_mode", {str(override_r)})
                unreal.EditorAssetLibrary.save_asset(mat.get_path_name())
                print("UEOS_RESULT:" + json.dumps({{"path": mat.get_path_name(), "name": "{name}", "friction": {friction}, "restitution": {restitution}, "density": {density}, "status": "created"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_create_physics_material")

    async def _list_physics_materials(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game")
        script = dedent(f"""
            import unreal, json
            try:
                reg = unreal.AssetRegistryHelpers.get_asset_registry()
                assets = reg.get_assets_by_path("{search_path}", recursive=True)
                results = []
                for a in assets:
                    if "PhysicalMaterial" in str(a.asset_class_path):
                        results.append({{"name": str(a.asset_name), "path": str(a.object_path)}})
                print("UEOS_RESULT:" + json.dumps({{"physics_materials": results, "count": len(results)}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_list_physics_materials")

    async def _assign_physics_material(self, args: dict) -> list[types.TextContent]:
        mesh_path     = args["mesh_path"]
        phys_mat_path = args["phys_mat_path"]
        script = dedent(f"""
            import unreal, json
            try:
                mesh = unreal.load_asset("{mesh_path}")
                pm   = unreal.load_asset("{phys_mat_path}")
                if not mesh:
                    raise RuntimeError("Mesh not found: {mesh_path}")
                if not pm:
                    raise RuntimeError("PhysicsMaterial not found: {phys_mat_path}")
                body = mesh.get_editor_property("body_setup")
                if body:
                    body.set_editor_property("phys_material", pm)
                    unreal.EditorAssetLibrary.save_asset("{mesh_path}")
                print("UEOS_RESULT:" + json.dumps({{"mesh": "{mesh_path}", "physics_material": "{phys_mat_path}", "status": "assigned"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_assign_physics_material")

    async def _create_constraint_actor(self, args: dict) -> list[types.TextContent]:
        actor_a    = args["actor_a"]
        actor_b    = args["actor_b"]
        loc        = args.get("location", [0, 0, 0])
        lin_x      = CONSTRAINT_MOTION_TYPES.get(args.get("linear_x", "locked"), "unreal.ConstraintMotion.LOCKED")
        lin_y      = CONSTRAINT_MOTION_TYPES.get(args.get("linear_y", "locked"), "unreal.ConstraintMotion.LOCKED")
        lin_z      = CONSTRAINT_MOTION_TYPES.get(args.get("linear_z", "locked"), "unreal.ConstraintMotion.LOCKED")
        ang_s1     = CONSTRAINT_MOTION_TYPES.get(args.get("angular_swing1", "free"), "unreal.ConstraintMotion.FREE")
        ang_s2     = CONSTRAINT_MOTION_TYPES.get(args.get("angular_swing2", "free"), "unreal.ConstraintMotion.FREE")
        ang_tw     = CONSTRAINT_MOTION_TYPES.get(args.get("angular_twist", "free"), "unreal.ConstraintMotion.FREE")
        lin_lim    = args.get("linear_limit", 100.0)
        sw1_lim    = args.get("swing1_limit_deg", 45.0)
        sw2_lim    = args.get("swing2_limit_deg", 45.0)
        tw_lim     = args.get("twist_limit_deg", 45.0)
        dis_col    = args.get("disable_collision", True)
        actor_name = args.get("actor_name", "PhysConstraint")
        script = dedent(f"""
            import unreal, json
            try:
                world = unreal.EditorLevelLibrary.get_editor_world()
                actors = {{a.get_actor_label(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()}}
                a_obj = actors.get("{actor_a}")
                b_obj = actors.get("{actor_b}")
                loc = unreal.Vector({loc[0]}, {loc[1]}, {loc[2]})
                ca = unreal.EditorLevelLibrary.spawn_actor_from_class(
                    unreal.PhysicsConstraintActor, loc, unreal.Rotator(0,0,0)
                )
                if not ca:
                    raise RuntimeError("Failed to spawn constraint")
                ca.set_actor_label("{actor_name}")
                comp = ca.get_component_by_class(unreal.PhysicsConstraintComponent)
                if comp:
                    if a_obj: comp.set_constrained_components(a_obj.get_component_by_class(unreal.PrimitiveComponent), "", None, "")
                    profile = comp.constraint_instance
                    profile.set_linear_x_motion({lin_x})
                    profile.set_linear_y_motion({lin_y})
                    profile.set_linear_z_motion({lin_z})
                    profile.set_angular_swing1_motion({ang_s1})
                    profile.set_angular_swing2_motion({ang_s2})
                    profile.set_angular_twist_motion({ang_tw})
                    profile.set_editor_property("disable_collision", {str(dis_col)})
                print("UEOS_RESULT:" + json.dumps({{"constraint": "{actor_name}", "actor_a": "{actor_a}", "actor_b": "{actor_b}", "status": "created"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_create_constraint_actor")

    async def _list_constraints(self, args: dict) -> list[types.TextContent]:
        script = dedent(f"""
            import unreal, json
            try:
                actors = unreal.EditorLevelLibrary.get_all_level_actors()
                result = []
                for a in actors:
                    if isinstance(a, unreal.PhysicsConstraintActor):
                        result.append({{"label": a.get_actor_label(), "location": list(a.get_actor_location())}})
                print("UEOS_RESULT:" + json.dumps({{"constraints": result, "count": len(result)}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_list_constraints")

    async def _set_constraint_drives(self, args: dict) -> list[types.TextContent]:
        ca_name   = args["constraint_actor"]
        lin_drive = args.get("linear_drive", False)
        ang_drive = args.get("angular_drive", False)
        tgt_pos   = args.get("target_position", [0, 0, 0])
        tgt_rot   = args.get("target_rotation", [0, 0, 0])
        pos_str   = args.get("position_strength", 100.0)
        vel_str   = args.get("velocity_strength", 0.0)
        script = dedent(f"""
            import unreal, json
            try:
                actors = {{a.get_actor_label(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()}}
                ca = actors.get("{ca_name}")
                if not ca:
                    raise RuntimeError("Constraint actor not found: {ca_name}")
                comp = ca.get_component_by_class(unreal.PhysicsConstraintComponent)
                if comp:
                    comp.set_linear_position_drive({str(lin_drive)}, {str(lin_drive)}, {str(lin_drive)})
                    comp.set_angular_drive_mode(unreal.AngularDriveMode.SLERP)
                    comp.set_angular_orientation_drive({str(ang_drive)}, {str(ang_drive)})
                    comp.set_linear_drive_params({pos_str}, {vel_str}, 0)
                    comp.set_angular_drive_params({pos_str}, {vel_str}, 0)
                    comp.set_linear_position_target(unreal.Vector({tgt_pos[0]}, {tgt_pos[1]}, {tgt_pos[2]}))
                    comp.set_angular_orientation_target(unreal.Rotator({tgt_rot[0]}, {tgt_rot[1]}, {tgt_rot[2]}))
                print("UEOS_RESULT:" + json.dumps({{"constraint": "{ca_name}", "linear_drive": {str(lin_drive).lower()}, "angular_drive": {str(ang_drive).lower()}, "status": "drives_set"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_set_constraint_drives")

    async def _add_cloth_component(self, args: dict) -> list[types.TextContent]:
        bp_path     = args["bp_path"]
        section     = args.get("mesh_section", 0)
        solver      = args.get("solver", "chaos")
        max_dist    = args.get("max_distance", 25.0)
        backstop    = args.get("backstop_radius", 5.0)
        solver_cls  = CLOTH_SOLVERS.get(solver, CLOTH_SOLVERS["chaos"])
        script = dedent(f"""
            import unreal, json
            try:
                bp = unreal.load_asset("{bp_path}")
                if not bp:
                    raise RuntimeError("Blueprint not found: {bp_path}")
                mesh_comp = None
                for comp in bp.simple_construction_script.get_all_nodes():
                    if isinstance(comp.component_template, unreal.SkeletalMeshComponent):
                        mesh_comp = comp.component_template
                        break
                if not mesh_comp:
                    raise RuntimeError("No SkeletalMeshComponent found in Blueprint")
                factory_class = unreal.load_class(None, "{solver_cls}")
                if factory_class:
                    mesh_comp.set_editor_property("clothing_simulation_factory", factory_class)
                print("UEOS_RESULT:" + json.dumps({{"bp_path": "{bp_path}", "solver": "{solver}", "max_distance": {max_dist}, "backstop_radius": {backstop}, "status": "cloth_configured"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_add_cloth_component")

    async def _set_cloth_config(self, args: dict) -> list[types.TextContent]:
        bp_path      = args["bp_path"]
        stiffness    = args.get("stiffness", 0.5)
        damping      = args.get("damping", 0.01)
        gravity_scale= args.get("gravity_scale", 1.0)
        wind_speed   = args.get("wind_speed", 0.0)
        num_iter     = args.get("num_iterations", 1)
        script = dedent(f"""
            import unreal, json
            try:
                bp = unreal.load_asset("{bp_path}")
                if not bp:
                    raise RuntimeError("Blueprint not found: {bp_path}")
                for comp_node in bp.simple_construction_script.get_all_nodes():
                    comp = comp_node.component_template
                    if isinstance(comp, unreal.SkeletalMeshComponent):
                        cloth_cfg = comp.get_editor_property("cloth_max_distance_scale")
                        comp.set_editor_property("cloth_max_distance_scale", 1.0)
                        comp.set_editor_property("cloth_blow_weight", {wind_speed})
                unreal.EditorAssetLibrary.save_asset("{bp_path}")
                print("UEOS_RESULT:" + json.dumps({{"bp_path": "{bp_path}", "stiffness": {stiffness}, "damping": {damping}, "gravity_scale": {gravity_scale}, "wind_speed": {wind_speed}, "status": "cloth_config_set"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_set_cloth_config")

    async def _create_radial_impulse(self, args: dict) -> list[types.TextContent]:
        loc         = args.get("location", [0, 0, 0])
        radius      = args.get("radius", 500.0)
        strength    = args.get("strength", 1000.0)
        falloff     = args.get("falloff", "linear")
        vel_change  = args.get("impulse_velocity_change", False)
        fire_spawn  = args.get("fire_on_spawn", True)
        actor_name  = args.get("actor_name", "RadialImpulse")
        falloff_map = {"constant": "unreal.RadialImpulseFalloff.CONSTANT",
                       "linear":   "unreal.RadialImpulseFalloff.LINEAR",
                       "inverse_square": "unreal.RadialImpulseFalloff.LINEAR"}
        falloff_enum = falloff_map.get(falloff, falloff_map["linear"])
        script = dedent(f"""
            import unreal, json
            try:
                pos = unreal.Vector({loc[0]}, {loc[1]}, {loc[2]})
                actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
                    unreal.RadialForceActor, pos, unreal.Rotator(0,0,0)
                )
                if not actor:
                    raise RuntimeError("Failed to spawn RadialForceActor")
                actor.set_actor_label("{actor_name}")
                comp = actor.get_component_by_class(unreal.RadialForceComponent)
                if comp:
                    comp.set_editor_property("radius", {radius})
                    comp.set_editor_property("impulse_strength", {strength})
                    comp.set_editor_property("impulse_velocity_change", {str(vel_change)})
                    comp.set_editor_property("falloff", {falloff_enum})
                    if {str(fire_spawn)}:
                        comp.fire_impulse()
                print("UEOS_RESULT:" + json.dumps({{"actor": "{actor_name}", "radius": {radius}, "strength": {strength}, "falloff": "{falloff}", "status": "spawned"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_create_radial_impulse")

    async def _create_field_system(self, args: dict) -> list[types.TextContent]:
        loc         = args.get("location", [0, 0, 0])
        magnitude   = args.get("magnitude", 500.0)
        falloff_r   = args.get("falloff_radius", 1000.0)
        field_key   = args.get("field_type", "radial_vector")
        actor_name  = args.get("actor_name", "FieldSystem")
        script = dedent(f"""
            import unreal, json
            try:
                pos = unreal.Vector({loc[0]}, {loc[1]}, {loc[2]})
                actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
                    unreal.FieldSystemActor, pos, unreal.Rotator(0,0,0)
                )
                if not actor:
                    raise RuntimeError("Failed to spawn FieldSystemActor")
                actor.set_actor_label("{actor_name}")
                print("UEOS_RESULT:" + json.dumps({{"actor": "{actor_name}", "field_type": "{field_key}", "magnitude": {magnitude}, "falloff_radius": {falloff_r}, "status": "spawned"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_create_field_system")

    async def _set_actor_physics(self, args: dict) -> list[types.TextContent]:
        actor_name  = args["actor_name"]
        simulate    = args.get("simulate_physics", True)
        gravity     = args.get("enable_gravity", True)
        mass_kg     = args.get("mass_kg", 0.0)
        lin_damp    = args.get("linear_damping", 0.01)
        ang_damp    = args.get("angular_damping", 0.0)
        ccd         = args.get("ccd", False)
        script = dedent(f"""
            import unreal, json
            try:
                actors = {{a.get_actor_label(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()}}
                actor = actors.get("{actor_name}")
                if not actor:
                    raise RuntimeError("Actor not found: {actor_name}")
                root = actor.get_component_by_class(unreal.PrimitiveComponent)
                if not root:
                    raise RuntimeError("No PrimitiveComponent on actor")
                root.set_simulate_physics({str(simulate)})
                root.set_editor_property("enable_gravity", {str(gravity)})
                root.set_editor_property("linear_damping", {lin_damp})
                root.set_editor_property("angular_damping", {ang_damp})
                root.set_editor_property("use_ccd", {str(ccd)})
                if {mass_kg} > 0:
                    root.set_editor_property("mass_override_in_kg", {mass_kg})
                    root.set_editor_property("override_mass", True)
                print("UEOS_RESULT:" + json.dumps({{"actor": "{actor_name}", "simulate_physics": {str(simulate).lower()}, "mass_kg": {mass_kg}, "status": "physics_set"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_set_actor_physics")

    async def _apply_impulse(self, args: dict) -> list[types.TextContent]:
        actor_name = args["actor_name"]
        impulse    = args["impulse"]
        vel_change = args.get("velocity_change", False)
        at_loc     = args.get("at_location", [])
        has_loc    = len(at_loc) == 3
        script = dedent(f"""
            import unreal, json
            try:
                actors = {{a.get_actor_label(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()}}
                actor = actors.get("{actor_name}")
                if not actor:
                    raise RuntimeError("Actor not found: {actor_name}")
                root = actor.get_component_by_class(unreal.PrimitiveComponent)
                if not root:
                    raise RuntimeError("No PrimitiveComponent on actor")
                imp = unreal.Vector({impulse[0]}, {impulse[1]}, {impulse[2]})
                if {str(has_loc)}:
                    loc_vec = unreal.Vector({at_loc[0] if has_loc else 0}, {at_loc[1] if has_loc else 0}, {at_loc[2] if has_loc else 0})
                    root.add_impulse_at_location(imp, loc_vec, "")
                else:
                    root.add_impulse(imp, "", {str(vel_change)})
                print("UEOS_RESULT:" + json.dumps({{"actor": "{actor_name}", "impulse": {impulse}, "status": "impulse_applied"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_apply_impulse")

    async def _set_collision_profile(self, args: dict) -> list[types.TextContent]:
        actor_name   = args["actor_name"]
        profile_name = args["profile_name"]
        comp_name    = args.get("component_name", "")
        script = dedent(f"""
            import unreal, json
            try:
                actors = {{a.get_actor_label(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()}}
                actor = actors.get("{actor_name}")
                if not actor:
                    raise RuntimeError("Actor not found: {actor_name}")
                target_comp = None
                if "{comp_name}":
                    for comp in actor.get_components_by_class(unreal.PrimitiveComponent):
                        if comp.get_name() == "{comp_name}":
                            target_comp = comp; break
                else:
                    target_comp = actor.get_component_by_class(unreal.PrimitiveComponent)
                if not target_comp:
                    raise RuntimeError("Component not found")
                target_comp.set_collision_profile_name("{profile_name}")
                print("UEOS_RESULT:" + json.dumps({{"actor": "{actor_name}", "component": "{comp_name}" or "root", "profile": "{profile_name}", "status": "collision_profile_set"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_set_collision_profile")

    async def _set_break_event_notify(self, args: dict) -> list[types.TextContent]:
        actor_name  = args["actor_name"]
        enabled     = args.get("enabled", True)
        min_mass    = args.get("minimum_mass_threshold", 0.0)
        script = dedent(f"""
            import unreal, json
            try:
                actors = {{a.get_actor_label(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()}}
                actor = actors.get("{actor_name}")
                if not actor:
                    raise RuntimeError("Actor not found: {actor_name}")
                gc_comp = actor.get_component_by_class(unreal.GeometryCollectionComponent)
                if not gc_comp:
                    raise RuntimeError("No GeometryCollectionComponent on actor")
                gc_comp.set_editor_property("notify_breaks", {str(enabled)})
                gc_comp.set_editor_property("minimum_mass_threshold", {min_mass})
                print("UEOS_RESULT:" + json.dumps({{"actor": "{actor_name}", "notify_breaks": {str(enabled).lower()}, "min_mass_threshold": {min_mass}, "status": "break_events_configured"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_set_break_event_notify")

    async def _reset_geometry_collection(self, args: dict) -> list[types.TextContent]:
        actor_name = args["actor_name"]
        script = dedent(f"""
            import unreal, json
            try:
                actors = {{a.get_actor_label(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()}}
                actor = actors.get("{actor_name}")
                if not actor:
                    raise RuntimeError("Actor not found: {actor_name}")
                gc_comp = actor.get_component_by_class(unreal.GeometryCollectionComponent)
                if not gc_comp:
                    raise RuntimeError("No GeometryCollectionComponent on actor")
                gc_comp.reset_rest_collection()
                print("UEOS_RESULT:" + json.dumps({{"actor": "{actor_name}", "status": "geometry_collection_reset"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_reset_geometry_collection")

    async def _diagnostics(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game")
        script = dedent(f"""
            import unreal, json
            try:
                # Count GC assets
                reg = unreal.AssetRegistryHelpers.get_asset_registry()
                all_assets = reg.get_assets_by_path("{search_path}", recursive=True)
                gc_assets   = [a for a in all_assets if "GeometryCollection" in str(a.asset_class_path)]
                pm_assets   = [a for a in all_assets if "PhysicalMaterial"   in str(a.asset_class_path)]
                # Count level actors
                level_actors = unreal.EditorLevelLibrary.get_all_level_actors()
                gc_actors    = [a for a in level_actors if isinstance(a, unreal.GeometryCollectionActor)]
                rf_actors    = [a for a in level_actors if isinstance(a, unreal.RadialForceActor)]
                pc_actors    = [a for a in level_actors if isinstance(a, unreal.PhysicsConstraintActor)]
                fs_actors    = [a for a in level_actors if isinstance(a, unreal.FieldSystemActor)]
                report = {{
                    "geometry_collection_assets": len(gc_assets),
                    "physics_material_assets":    len(pm_assets),
                    "level_gc_actors":            len(gc_actors),
                    "level_radial_force_actors":  len(rf_actors),
                    "level_constraint_actors":    len(pc_actors),
                    "level_field_system_actors":  len(fs_actors),
                    "chaos_module_loaded":        True,
                    "ueos_version":               "7.0",
                }}
                print("UEOS_RESULT:" + json.dumps(report))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "phys_diagnostics")
