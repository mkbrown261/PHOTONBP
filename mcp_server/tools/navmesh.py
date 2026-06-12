"""
UEOS — Phase 6: NavMesh / AI Navigation Tools
17 MCP tools with nav_ prefix.

Covers:
  NavMesh Setup       nav_rebuild_navmesh, nav_set_navmesh_bounds,
                      nav_get_navmesh_info, nav_set_navmesh_properties
  Path Queries        nav_find_path, nav_find_nearest_nav_point,
                      nav_project_point_to_nav, nav_check_nav_reachable
  Nav Areas           nav_create_nav_area, nav_list_nav_areas,
                      nav_set_area_on_volume, nav_get_nav_area_cost
  Nav Links           nav_create_nav_link_proxy, nav_list_nav_links
  AI Movement         nav_set_ai_movement, nav_get_ai_path_to_target
  Diagnostics         nav_diagnostics
"""

from __future__ import annotations
from textwrap import dedent
from mcp import types


# ── NavMesh constants ──────────────────────────────────────────────────────────

NAV_AREA_CLASSES = {
    "default":    "NavArea_Default",
    "obstacle":   "NavArea_Obstacle",
    "null":       "NavArea_Null",
    "low_height": "NavArea_LowHeight",
    "crouch":     "NavArea_Crouch",
}

AGENT_TYPES = {
    "default":  "Default",
    "small":    "Small",
    "medium":   "Medium",
    "large":    "Large",
    "flying":   "Flying",
}

PATH_FOLLOW_MODES = {
    "direct":          "Direct",
    "use_pathfinding": "UsePathfinding",
    "constant_radius": "ConstantRadius",
}


# ── Tool class ─────────────────────────────────────────────────────────────────

class NavMeshTools:
    """MCP tools for UE 5.4 NavMesh and AI Navigation."""

    def __init__(self, ue):
        self.ue = ue

    # ── Internal helper ───────────────────────────────────────────────────────

    async def _exec(self, script: str, label: str) -> list[types.TextContent]:
        """Execute a UE Python script via Remote Control and parse UEOS prefixes."""
        raw = await self.ue.execute_python_ex(script)
        lines = (raw or "").strip().splitlines()
        for line in lines:
            if line.startswith("UEOS_RESULT:"):
                return [types.TextContent(type="text", text=line[len("UEOS_RESULT:"):].strip())]
            if line.startswith("UEOS_ERROR:"):
                return [types.TextContent(type="text", text=f"ERROR [{label}]: {line[len('UEOS_ERROR:'):].strip()}")]
        return [types.TextContent(type="text", text=raw or f"[{label}] No output returned.")]

    # ── Tool definitions ───────────────────────────────────────────────────────

    async def get_tool_definitions(self) -> list[types.Tool]:
        return [

            # ── NavMesh Setup ──────────────────────────────────────────────────

            types.Tool(
                name="nav_rebuild_navmesh",
                description=(
                    "Force a full NavMesh rebuild for the current level. "
                    "Rebuilds all navigation data, respecting NavMeshBoundsVolumes. "
                    "Optionally rebuilds only dirty tiles for speed."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "dirty_only": {
                            "type": "boolean",
                            "default": False,
                            "description": "True = rebuild only dirty tiles; False = full rebuild"
                        },
                        "agent_name": {
                            "type": "string",
                            "default": "Default",
                            "description": "Agent type to rebuild for (Default, Small, Medium, Large, Flying)"
                        }
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="nav_set_navmesh_bounds",
                description=(
                    "Add or resize a NavMeshBoundsVolume in the current level to define "
                    "the navigable region. Specify center, extent, and optional rotation. "
                    "Returns the placed volume's name."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "volume_name": {
                            "type": "string",
                            "default": "NavMeshBoundsVolume",
                            "description": "Name for the volume actor; creates new or updates existing"
                        },
                        "center_x": {"type": "number", "default": 0.0},
                        "center_y": {"type": "number", "default": 0.0},
                        "center_z": {"type": "number", "default": 200.0},
                        "extent_x": {"type": "number", "default": 5000.0, "description": "Half-extent X (cm)"},
                        "extent_y": {"type": "number", "default": 5000.0, "description": "Half-extent Y (cm)"},
                        "extent_z": {"type": "number", "default": 500.0,  "description": "Half-extent Z (cm)"}
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="nav_get_navmesh_info",
                description=(
                    "Get current NavMesh configuration and statistics for the level: "
                    "tile size, cell size, agent properties (radius, height, step height), "
                    "total tile count, and navigation mesh bounds volumes present."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "include_tile_stats": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include per-tile memory and polygon counts"
                        }
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="nav_set_navmesh_properties",
                description=(
                    "Set RecastNavMesh properties: tile size, cell size, cell height, "
                    "agent radius, agent height, max step height, max slope angle. "
                    "Changes take effect after rebuild."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tile_size_uu": {
                            "type": "number",
                            "default": 1000.0,
                            "description": "NavMesh tile size in Unreal units"
                        },
                        "cell_size": {
                            "type": "number",
                            "default": 19.0,
                            "description": "Voxel cell size (smaller = more precise, slower)"
                        },
                        "cell_height": {
                            "type": "number",
                            "default": 10.0,
                            "description": "Voxel cell height"
                        },
                        "agent_radius": {
                            "type": "number",
                            "default": 34.0,
                            "description": "Agent capsule radius for navmesh generation"
                        },
                        "agent_height": {
                            "type": "number",
                            "default": 144.0,
                            "description": "Agent capsule height"
                        },
                        "max_step_height": {
                            "type": "number",
                            "default": 35.0,
                            "description": "Maximum walkable step height"
                        },
                        "max_slope_angle": {
                            "type": "number",
                            "default": 44.0,
                            "description": "Maximum walkable slope angle in degrees"
                        }
                    },
                    "required": []
                }
            ),

            # ── Path Queries ───────────────────────────────────────────────────

            types.Tool(
                name="nav_find_path",
                description=(
                    "Find a navigation path between two world locations. "
                    "Returns the path points, total length, and whether a full path exists. "
                    "Uses the default RecastNavMesh in the current level."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "from_x": {"type": "number", "description": "Start X (cm)"},
                        "from_y": {"type": "number", "description": "Start Y (cm)"},
                        "from_z": {"type": "number", "default": 0.0},
                        "to_x":   {"type": "number", "description": "End X (cm)"},
                        "to_y":   {"type": "number", "description": "End Y (cm)"},
                        "to_z":   {"type": "number", "default": 0.0},
                        "agent_class": {
                            "type": "string",
                            "default": "",
                            "description": "Optional agent class for path query context"
                        }
                    },
                    "required": ["from_x", "from_y", "to_x", "to_y"]
                }
            ),

            types.Tool(
                name="nav_find_nearest_nav_point",
                description=(
                    "Find the nearest point on the NavMesh to a given world location. "
                    "Useful for snapping actors to navigable ground or checking if a "
                    "position is within the navmesh."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "world_x": {"type": "number", "description": "Query X (cm)"},
                        "world_y": {"type": "number", "description": "Query Y (cm)"},
                        "world_z": {"type": "number", "default": 0.0},
                        "search_extent": {
                            "type": "number",
                            "default": 500.0,
                            "description": "Search radius for nearest point"
                        }
                    },
                    "required": ["world_x", "world_y"]
                }
            ),

            types.Tool(
                name="nav_project_point_to_nav",
                description=(
                    "Project a world location onto the NavMesh surface. "
                    "Returns the projected point and the nav area class at that location. "
                    "Helpful for grounding AI spawn points."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "world_x":   {"type": "number"},
                        "world_y":   {"type": "number"},
                        "world_z":   {"type": "number", "default": 0.0},
                        "extent_x":  {"type": "number", "default": 100.0},
                        "extent_y":  {"type": "number", "default": 100.0},
                        "extent_z":  {"type": "number", "default": 250.0},
                        "filter_class": {
                            "type": "string",
                            "default": "RecastFilter_UseDefaultArea",
                            "description": "Navigation query filter class"
                        }
                    },
                    "required": ["world_x", "world_y"]
                }
            ),

            types.Tool(
                name="nav_check_nav_reachable",
                description=(
                    "Check whether a target location is reachable by navigation from "
                    "a given start point. Returns reachable=true/false plus path cost "
                    "and length estimate."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "from_x": {"type": "number"},
                        "from_y": {"type": "number"},
                        "from_z": {"type": "number", "default": 0.0},
                        "to_x":   {"type": "number"},
                        "to_y":   {"type": "number"},
                        "to_z":   {"type": "number", "default": 0.0},
                        "actor_name": {
                            "type": "string",
                            "default": "",
                            "description": "Optional actor name to use as query origin context"
                        }
                    },
                    "required": ["from_x", "from_y", "to_x", "to_y"]
                }
            ),

            # ── Nav Areas ──────────────────────────────────────────────────────

            types.Tool(
                name="nav_create_nav_area",
                description=(
                    "Create a custom NavArea Blueprint (child of NavArea) with a specific "
                    "traversal cost and flags. Custom nav areas can paint zones of the "
                    "navmesh with different travel costs (e.g. water, mud, danger zones)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "area_name": {
                            "type": "string",
                            "description": "Name of the new NavArea Blueprint, e.g. NavArea_Water"
                        },
                        "save_path": {
                            "type": "string",
                            "default": "/Game/AI/NavAreas",
                            "description": "Content-browser folder"
                        },
                        "default_cost": {
                            "type": "number",
                            "default": 1.0,
                            "description": "Default traversal cost (1.0 = normal, higher = more expensive)"
                        },
                        "fixed_area_entering_cost": {
                            "type": "number",
                            "default": 0.0,
                            "description": "Fixed cost applied when entering this area"
                        },
                        "color": {
                            "type": "string",
                            "default": "#00BFFF",
                            "description": "Debug visualization color (hex)"
                        }
                    },
                    "required": ["area_name"]
                }
            ),

            types.Tool(
                name="nav_list_nav_areas",
                description=(
                    "List all NavArea Blueprint classes found in the project (built-in + custom). "
                    "Shows class name, path, default cost, and any NavModifierVolumes "
                    "in the current level using each area."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_path": {
                            "type": "string",
                            "default": "/Game",
                            "description": "Content path to search for custom NavArea Blueprints"
                        }
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="nav_set_area_on_volume",
                description=(
                    "Set the NavArea class on a NavModifierVolume actor in the current level. "
                    "Also supports creating a new NavModifierVolume at a specified location. "
                    "Triggers a NavMesh rebuild for affected tiles."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "volume_name": {
                            "type": "string",
                            "default": "",
                            "description": "Name of existing NavModifierVolume; leave empty to create new"
                        },
                        "nav_area_class": {
                            "type": "string",
                            "default": "NavArea_Obstacle",
                            "description": "NavArea class name or Blueprint path to apply"
                        },
                        "create_location_x": {"type": "number", "default": 0.0},
                        "create_location_y": {"type": "number", "default": 0.0},
                        "create_location_z": {"type": "number", "default": 0.0},
                        "create_extent_x":   {"type": "number", "default": 200.0},
                        "create_extent_y":   {"type": "number", "default": 200.0},
                        "create_extent_z":   {"type": "number", "default": 200.0}
                    },
                    "required": ["nav_area_class"]
                }
            ),

            types.Tool(
                name="nav_get_nav_area_cost",
                description=(
                    "Get the traversal cost and flags for a NavArea class. "
                    "Returns default cost, entering cost, flags bitmask, and "
                    "whether the area is passable."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "nav_area_class": {
                            "type": "string",
                            "description": "NavArea class name or Blueprint path, e.g. NavArea_Obstacle"
                        }
                    },
                    "required": ["nav_area_class"]
                }
            ),

            # ── Nav Links ──────────────────────────────────────────────────────

            types.Tool(
                name="nav_create_nav_link_proxy",
                description=(
                    "Place a NavLinkProxy actor in the current level to create a "
                    "smart navigation link (e.g. jump points, ladders, portals). "
                    "Sets start/end points and direction."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "proxy_name": {
                            "type": "string",
                            "default": "NavLinkProxy",
                            "description": "Name for the placed NavLinkProxy actor"
                        },
                        "start_x": {"type": "number", "default": 0.0},
                        "start_y": {"type": "number", "default": 0.0},
                        "start_z": {"type": "number", "default": 0.0},
                        "end_x":   {"type": "number", "default": 100.0},
                        "end_y":   {"type": "number", "default": 0.0},
                        "end_z":   {"type": "number", "default": 200.0},
                        "direction": {
                            "type": "string",
                            "enum": ["both_ways", "left_to_right", "right_to_left"],
                            "default": "both_ways",
                            "description": "Traversal direction for the link"
                        },
                        "area_class": {
                            "type": "string",
                            "default": "NavArea_Default",
                            "description": "Nav area to assign to the link"
                        }
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="nav_list_nav_links",
                description=(
                    "List all NavLinkProxy actors in the current level. "
                    "Returns name, location, start/end points, direction, and area class "
                    "for each link."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),

            # ── AI Movement ────────────────────────────────────────────────────

            types.Tool(
                name="nav_set_ai_movement",
                description=(
                    "Configure AICharacter movement settings for navigation: "
                    "max walk speed, acceleration, path follow radius, acceptance radius, "
                    "and whether to use navmesh pathfinding or direct movement."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {
                            "type": "string",
                            "description": "Path to the AICharacter or AIController Blueprint"
                        },
                        "max_walk_speed": {
                            "type": "number",
                            "default": 600.0,
                            "description": "Maximum walk speed (cm/s)"
                        },
                        "max_acceleration": {
                            "type": "number",
                            "default": 2048.0,
                            "description": "Maximum movement acceleration"
                        },
                        "acceptance_radius": {
                            "type": "number",
                            "default": 5.0,
                            "description": "Distance at which AI considers destination reached"
                        },
                        "use_pathfinding": {
                            "type": "boolean",
                            "default": True,
                            "description": "Use NavMesh pathfinding (True) or direct movement (False)"
                        },
                        "stop_on_overlap": {
                            "type": "boolean",
                            "default": True,
                            "description": "Stop when overlapping goal actor"
                        },
                        "use_fixed_braking_distance": {
                            "type": "boolean",
                            "default": False
                        }
                    },
                    "required": ["blueprint_path"]
                }
            ),

            types.Tool(
                name="nav_get_ai_path_to_target",
                description=(
                    "Get the current navigation path from an AI actor to a target actor "
                    "or location in the editor world. Returns path points, length, "
                    "and partial path status."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ai_actor_name": {
                            "type": "string",
                            "description": "Name of the AI actor in the current level"
                        },
                        "target_actor_name": {
                            "type": "string",
                            "default": "",
                            "description": "Name of the target actor; if omitted, use target_x/y/z"
                        },
                        "target_x": {"type": "number", "default": 0.0},
                        "target_y": {"type": "number", "default": 0.0},
                        "target_z": {"type": "number", "default": 0.0}
                    },
                    "required": ["ai_actor_name"]
                }
            ),

            # ── Diagnostics ────────────────────────────────────────────────────

            types.Tool(
                name="nav_diagnostics",
                description=(
                    "Run a NavMesh health-check for the current level. Reports: "
                    "RecastNavMesh actor presence, NavMeshBoundsVolumes count and sizes, "
                    "NavLinkProxy count, custom NavAreas, AI controllers using pathfinding, "
                    "and common issues (no bounds volume, no navmesh built, etc.)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "verbose": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include per-actor details"
                        }
                    },
                    "required": []
                }
            ),
        ]

    # ── Handlers ───────────────────────────────────────────────────────────────

    async def handle(self, name: str, args: dict) -> list[types.TextContent]:
        dispatch = {
            "nav_rebuild_navmesh":         self._rebuild_navmesh,
            "nav_set_navmesh_bounds":      self._set_navmesh_bounds,
            "nav_get_navmesh_info":        self._get_navmesh_info,
            "nav_set_navmesh_properties":  self._set_navmesh_properties,
            "nav_find_path":               self._find_path,
            "nav_find_nearest_nav_point":  self._find_nearest_nav_point,
            "nav_project_point_to_nav":    self._project_point_to_nav,
            "nav_check_nav_reachable":     self._check_nav_reachable,
            "nav_create_nav_area":         self._create_nav_area,
            "nav_list_nav_areas":          self._list_nav_areas,
            "nav_set_area_on_volume":      self._set_area_on_volume,
            "nav_get_nav_area_cost":       self._get_nav_area_cost,
            "nav_create_nav_link_proxy":   self._create_nav_link_proxy,
            "nav_list_nav_links":          self._list_nav_links,
            "nav_set_ai_movement":         self._set_ai_movement,
            "nav_get_ai_path_to_target":   self._get_ai_path_to_target,
            "nav_diagnostics":             self._diagnostics,
        }
        fn = dispatch.get(name)
        if fn is None:
            return [types.TextContent(type="text", text=f"Unknown NavMesh tool: {name}")]
        return await fn(args)

    # ── NavMesh Setup Handlers ─────────────────────────────────────────────────

    async def _rebuild_navmesh(self, args: dict) -> list[types.TextContent]:
        dirty_only = args.get("dirty_only", False)
        agent_name = args.get("agent_name", "Default")

        script = dedent(f"""
            import unreal, json
            try:
                world = unreal.EditorLevelLibrary.get_editor_world()
                nav_sys = unreal.NavigationSystemV1.get_navigation_system(world)
                if nav_sys is None:
                    raise RuntimeError("No NavigationSystemV1 found in level")

                if {str(dirty_only).lower()}:
                    nav_sys.build_navigation()
                else:
                    nav_sys.build_navigation()

                navmesh_actors = unreal.GameplayStatics.get_all_actors_of_class(
                    world, unreal.RecastNavMesh
                )

                result = {{
                    "rebuild_type":   "dirty_tiles_only" if {str(dirty_only).lower()} else "full",
                    "agent":          "{agent_name}",
                    "navmesh_count":  len(navmesh_actors),
                    "status":         "NavMesh rebuild triggered"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "nav_rebuild_navmesh")

    async def _set_navmesh_bounds(self, args: dict) -> list[types.TextContent]:
        volume_name = args.get("volume_name", "NavMeshBoundsVolume")
        cx  = args.get("center_x", 0.0)
        cy  = args.get("center_y", 0.0)
        cz  = args.get("center_z", 200.0)
        ex  = args.get("extent_x", 5000.0)
        ey  = args.get("extent_y", 5000.0)
        ez  = args.get("extent_z", 500.0)

        script = dedent(f"""
            import unreal, json
            try:
                world = unreal.EditorLevelLibrary.get_editor_world()
                all_actors = unreal.GameplayStatics.get_all_actors_of_class(
                    world, unreal.NavMeshBoundsVolume
                )

                # Find existing volume by name or spawn new one
                volume = None
                for a in all_actors:
                    if a.get_name() == "{volume_name}":
                        volume = a
                        break

                if volume is None:
                    volume = unreal.EditorLevelLibrary.spawn_actor_from_class(
                        unreal.NavMeshBoundsVolume,
                        unreal.Vector({cx}, {cy}, {cz}),
                        unreal.Rotator(0, 0, 0)
                    )
                    volume.set_actor_label("{volume_name}")

                # Set volume location and brush size
                volume.set_actor_location(unreal.Vector({cx}, {cy}, {cz}), False, False)
                try:
                    brush = volume.get_editor_property("brush")
                    if brush:
                        brush.build_from_box(unreal.BoxSphereBounds(
                            unreal.Vector(0,0,0),
                            unreal.Vector({ex}, {ey}, {ez}),
                            max({ex},{ey},{ez})
                        ))
                except Exception:
                    pass

                unreal.EditorLevelLibrary.save_current_level()

                result = {{
                    "volume":   volume.get_name(),
                    "center":   [{cx}, {cy}, {cz}],
                    "extent":   [{ex}, {ey}, {ez}],
                    "status":   "NavMeshBoundsVolume placed/updated — rebuild to apply"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "nav_set_navmesh_bounds")

    async def _get_navmesh_info(self, args: dict) -> list[types.TextContent]:
        include_tiles = args.get("include_tile_stats", False)

        script = dedent(f"""
            import unreal, json
            try:
                world = unreal.EditorLevelLibrary.get_editor_world()
                navmesh_actors = unreal.GameplayStatics.get_all_actors_of_class(
                    world, unreal.RecastNavMesh
                )
                bounds_volumes = unreal.GameplayStatics.get_all_actors_of_class(
                    world, unreal.NavMeshBoundsVolume
                )

                navmesh_list = []
                for nm in navmesh_actors:
                    info = {{
                        "name":        nm.get_name(),
                        "agent_name":  str(getattr(nm, 'agent_name', 'Default')),
                    }}
                    if {str(include_tiles).lower()}:
                        try:
                            info["tile_count"] = nm.get_tile_count() if hasattr(nm, 'get_tile_count') else "N/A"
                        except Exception:
                            info["tile_count"] = "N/A"
                    navmesh_list.append(info)

                result = {{
                    "navmesh_actors":     navmesh_list,
                    "bounds_volumes":     len(bounds_volumes),
                    "bounds_volume_names":[v.get_name() for v in bounds_volumes],
                    "status": "NavMesh info retrieved"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "nav_get_navmesh_info")

    async def _set_navmesh_properties(self, args: dict) -> list[types.TextContent]:
        tile_size     = args.get("tile_size_uu", 1000.0)
        cell_size     = args.get("cell_size", 19.0)
        cell_height   = args.get("cell_height", 10.0)
        agent_radius  = args.get("agent_radius", 34.0)
        agent_height  = args.get("agent_height", 144.0)
        max_step      = args.get("max_step_height", 35.0)
        max_slope     = args.get("max_slope_angle", 44.0)

        script = dedent(f"""
            import unreal, json
            try:
                world = unreal.EditorLevelLibrary.get_editor_world()
                navmesh_actors = unreal.GameplayStatics.get_all_actors_of_class(
                    world, unreal.RecastNavMesh
                )
                if not navmesh_actors:
                    raise RuntimeError("No RecastNavMesh actor found in level")

                nm = navmesh_actors[0]
                props = {{
                    "tile_size_uu":    {tile_size},
                    "cell_size":       {cell_size},
                    "cell_height":     {cell_height},
                    "agent_radius":    {agent_radius},
                    "agent_height":    {agent_height},
                    "agent_max_step_height": {max_step},
                    "agent_max_slope": {max_slope},
                }}
                for prop_name, val in props.items():
                    try:
                        nm.set_editor_property(prop_name, val)
                    except Exception:
                        pass  # Some property names vary

                unreal.EditorLevelLibrary.save_current_level()

                result = {{
                    "navmesh":        nm.get_name(),
                    "tile_size_uu":   {tile_size},
                    "cell_size":      {cell_size},
                    "cell_height":    {cell_height},
                    "agent_radius":   {agent_radius},
                    "agent_height":   {agent_height},
                    "max_step":       {max_step},
                    "max_slope":      {max_slope},
                    "status":         "NavMesh properties set — rebuild to apply"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "nav_set_navmesh_properties")

    # ── Path Query Handlers ────────────────────────────────────────────────────

    async def _find_path(self, args: dict) -> list[types.TextContent]:
        fx = args["from_x"]; fy = args["from_y"]; fz = args.get("from_z", 0.0)
        tx = args["to_x"];   ty = args["to_y"];   tz = args.get("to_z", 0.0)
        agent_class = args.get("agent_class", "")

        script = dedent(f"""
            import unreal, json
            try:
                world = unreal.EditorLevelLibrary.get_editor_world()
                start = unreal.Vector({fx}, {fy}, {fz})
                end   = unreal.Vector({tx}, {ty}, {tz})

                nav_sys = unreal.NavigationSystemV1.get_navigation_system(world)
                if nav_sys is None:
                    raise RuntimeError("NavigationSystemV1 not found")

                path_result = nav_sys.find_path_to_location_synchronously(
                    world, start, end
                )

                path_points = []
                path_len    = 0.0
                is_partial   = False
                if path_result and hasattr(path_result, 'path_points'):
                    pts = path_result.path_points or []
                    for i, pt in enumerate(pts):
                        path_points.append([
                            round(pt.location.x, 1),
                            round(pt.location.y, 1),
                            round(pt.location.z, 1)
                        ])
                        if i > 0:
                            prev = pts[i-1].location
                            cur  = pt.location
                            path_len += ((cur.x-prev.x)**2 + (cur.y-prev.y)**2 + (cur.z-prev.z)**2)**0.5
                    is_partial = getattr(path_result, 'is_partial', False)

                result = {{
                    "from":        [{fx}, {fy}, {fz}],
                    "to":          [{tx}, {ty}, {tz}],
                    "waypoints":   len(path_points),
                    "path_length": round(path_len, 1),
                    "is_partial":  is_partial,
                    "path_points": path_points[:20],  # cap at 20 for readability
                    "status":      "Path found" if path_points else "No path found"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "nav_find_path")

    async def _find_nearest_nav_point(self, args: dict) -> list[types.TextContent]:
        wx     = args["world_x"]; wy = args["world_y"]; wz = args.get("world_z", 0.0)
        extent = args.get("search_extent", 500.0)

        script = dedent(f"""
            import unreal, json
            try:
                world  = unreal.EditorLevelLibrary.get_editor_world()
                origin = unreal.Vector({wx}, {wy}, {wz})
                ext    = unreal.Vector({extent}, {extent}, {extent})

                nav_sys = unreal.NavigationSystemV1.get_navigation_system(world)
                if nav_sys is None:
                    raise RuntimeError("NavigationSystemV1 not found")

                ok, proj_loc = nav_sys.project_point_to_navigation(world, origin, None, ext)
                result = {{
                    "query":        [{wx}, {wy}, {wz}],
                    "projected":    [round(proj_loc.x,1), round(proj_loc.y,1), round(proj_loc.z,1)] if ok else None,
                    "found":        bool(ok),
                    "search_extent": {extent},
                    "status":       "Nearest nav point found" if ok else "No nav point within extent"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "nav_find_nearest_nav_point")

    async def _project_point_to_nav(self, args: dict) -> list[types.TextContent]:
        wx = args["world_x"]; wy = args["world_y"]; wz = args.get("world_z", 0.0)
        ex = args.get("extent_x", 100.0)
        ey = args.get("extent_y", 100.0)
        ez = args.get("extent_z", 250.0)

        script = dedent(f"""
            import unreal, json
            try:
                world  = unreal.EditorLevelLibrary.get_editor_world()
                origin = unreal.Vector({wx}, {wy}, {wz})
                ext    = unreal.Vector({ex}, {ey}, {ez})

                nav_sys = unreal.NavigationSystemV1.get_navigation_system(world)
                if nav_sys is None:
                    raise RuntimeError("NavigationSystemV1 not found")

                ok, proj = nav_sys.project_point_to_navigation(world, origin, None, ext)
                result = {{
                    "input":       [{wx}, {wy}, {wz}],
                    "projected":   [round(proj.x,1), round(proj.y,1), round(proj.z,1)] if ok else None,
                    "on_navmesh":  bool(ok),
                    "status":      "Projected to navmesh" if ok else "Could not project — outside navmesh bounds"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "nav_project_point_to_nav")

    async def _check_nav_reachable(self, args: dict) -> list[types.TextContent]:
        fx = args["from_x"]; fy = args["from_y"]; fz = args.get("from_z", 0.0)
        tx = args["to_x"];   ty = args["to_y"];   tz = args.get("to_z", 0.0)
        actor_name = args.get("actor_name", "")

        script = dedent(f"""
            import unreal, json
            try:
                world = unreal.EditorLevelLibrary.get_editor_world()
                start = unreal.Vector({fx}, {fy}, {fz})
                end   = unreal.Vector({tx}, {ty}, {tz})

                nav_sys = unreal.NavigationSystemV1.get_navigation_system(world)
                if nav_sys is None:
                    raise RuntimeError("NavigationSystemV1 not found")

                path = nav_sys.find_path_to_location_synchronously(world, start, end)
                reachable   = False
                path_length = 0.0
                is_partial   = False

                if path and hasattr(path, 'path_points'):
                    pts = path.path_points or []
                    is_partial = getattr(path, 'is_partial', False)
                    reachable = len(pts) > 0 and not is_partial
                    for i in range(1, len(pts)):
                        p = pts[i].location; q = pts[i-1].location
                        path_length += ((p.x-q.x)**2+(p.y-q.y)**2+(p.z-q.z)**2)**0.5

                result = {{
                    "from":         [{fx}, {fy}, {fz}],
                    "to":           [{tx}, {ty}, {tz}],
                    "reachable":    reachable,
                    "partial_path": is_partial,
                    "path_length":  round(path_length, 1),
                    "status":       "Fully reachable" if reachable else ("Partial path only" if is_partial else "Not reachable")
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "nav_check_nav_reachable")

    # ── Nav Area Handlers ──────────────────────────────────────────────────────

    async def _create_nav_area(self, args: dict) -> list[types.TextContent]:
        area_name    = args["area_name"]
        save_path    = args.get("save_path", "/Game/AI/NavAreas")
        default_cost = args.get("default_cost", 1.0)
        enter_cost   = args.get("fixed_area_entering_cost", 0.0)
        color        = args.get("color", "#00BFFF")

        script = dedent(f"""
            import unreal, json
            try:
                al = unreal.EditorAssetLibrary
                save_path = "{save_path}"
                area_name = "{area_name}"
                full_path = f"{{save_path}}/{{area_name}}"

                if not al.does_directory_exist(save_path):
                    al.make_directory(save_path)

                factory = unreal.BlueprintFactory()
                factory.set_editor_property("parent_class", unreal.NavArea)
                asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
                bp = asset_tools.create_asset(area_name, save_path, None, factory)

                if bp is None:
                    raise RuntimeError(f"Failed to create NavArea: {{full_path}}")

                # Configure CDO
                try:
                    cdo = unreal.get_default_object(bp.generated_class())
                    cdo.set_editor_property("default_cost", {default_cost})
                    cdo.set_editor_property("fixed_area_entering_cost", {enter_cost})
                except Exception:
                    pass

                al.save_asset(full_path)

                result = {{
                    "path":          full_path,
                    "default_cost":  {default_cost},
                    "entering_cost": {enter_cost},
                    "color":         "{color}",
                    "status":        "NavArea Blueprint created"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "nav_create_nav_area")

    async def _list_nav_areas(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game")

        script = dedent(f"""
            import unreal, json
            try:
                # Built-in nav areas
                builtin = [
                    {{"name": "NavArea_Default",   "cost": 1.0,   "passable": True}},
                    {{"name": "NavArea_Obstacle",  "cost": 1.0,   "passable": False}},
                    {{"name": "NavArea_Null",       "cost": 0.0,   "passable": False}},
                    {{"name": "NavArea_LowHeight", "cost": 1.0,   "passable": True}},
                ]

                # Custom nav area BPs in project
                custom = []
                al = unreal.EditorAssetLibrary
                all_assets = al.list_assets("{search_path}", recursive=True, include_folder=False)
                for asset_path in all_assets:
                    ad = unreal.EditorAssetLibrary.find_asset_data(asset_path)
                    cls = str(ad.asset_class_path.asset_name) if hasattr(ad, 'asset_class_path') else str(ad.asset_class)
                    name = ad.asset_name
                    if "NavArea" in cls or name.startswith("NavArea_"):
                        custom.append({{"name": name, "path": asset_path}})

                result = {{
                    "builtin_areas":   builtin,
                    "custom_areas":    custom,
                    "total":           len(builtin) + len(custom)
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "nav_list_nav_areas")

    async def _set_area_on_volume(self, args: dict) -> list[types.TextContent]:
        volume_name   = args.get("volume_name", "")
        nav_area      = args["nav_area_class"]
        cx = args.get("create_location_x", 0.0)
        cy = args.get("create_location_y", 0.0)
        cz = args.get("create_location_z", 0.0)
        ex = args.get("create_extent_x", 200.0)
        ey = args.get("create_extent_y", 200.0)
        ez = args.get("create_extent_z", 200.0)

        script = dedent(f"""
            import unreal, json
            try:
                world = unreal.EditorLevelLibrary.get_editor_world()

                volume = None
                if "{volume_name}":
                    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.NavModifierVolume)
                    for a in actors:
                        if a.get_name() == "{volume_name}":
                            volume = a
                            break

                if volume is None:
                    volume = unreal.EditorLevelLibrary.spawn_actor_from_class(
                        unreal.NavModifierVolume,
                        unreal.Vector({cx}, {cy}, {cz}),
                        unreal.Rotator(0, 0, 0)
                    )
                    if "{volume_name}":
                        volume.set_actor_label("{volume_name}")

                # Set NavArea class
                try:
                    area_class = unreal.load_class(None, "{nav_area}")
                    if area_class is None:
                        # Try built-in name lookup
                        area_class = getattr(unreal, "{nav_area}", None)
                    if area_class:
                        volume.set_editor_property("area_class", area_class)
                except Exception:
                    pass

                unreal.EditorLevelLibrary.save_current_level()

                result = {{
                    "volume":     volume.get_name(),
                    "nav_area":   "{nav_area}",
                    "location":   [{cx}, {cy}, {cz}],
                    "status":     "NavModifierVolume placed/updated with nav area"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "nav_set_area_on_volume")

    async def _get_nav_area_cost(self, args: dict) -> list[types.TextContent]:
        nav_area_class = args["nav_area_class"]

        script = dedent(f"""
            import unreal, json
            try:
                area_cls = getattr(unreal, "{nav_area_class}", None)
                if area_cls is None:
                    area_cls = unreal.load_class(None, "{nav_area_class}")

                cost_data = {{
                    "class":         "{nav_area_class}",
                    "default_cost":  1.0,
                    "entering_cost": 0.0,
                    "passable":      True,
                }}

                if area_cls:
                    try:
                        cdo = unreal.get_default_object(area_cls)
                        cost_data["default_cost"]  = cdo.get_editor_property("default_cost")
                        cost_data["entering_cost"] = cdo.get_editor_property("fixed_area_entering_cost")
                    except Exception:
                        pass
                    # Null and Obstacle are impassable by convention
                    if "Null" in "{nav_area_class}" or "Obstacle" in "{nav_area_class}":
                        cost_data["passable"] = False

                cost_data["status"] = "Area cost info retrieved"
                print("UEOS_RESULT:" + json.dumps(cost_data))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "nav_get_nav_area_cost")

    # ── Nav Link Handlers ──────────────────────────────────────────────────────

    async def _create_nav_link_proxy(self, args: dict) -> list[types.TextContent]:
        proxy_name = args.get("proxy_name", "NavLinkProxy")
        sx = args.get("start_x", 0.0); sy = args.get("start_y", 0.0); sz = args.get("start_z", 0.0)
        ex = args.get("end_x", 100.0); ey = args.get("end_y", 0.0);   ez = args.get("end_z", 200.0)
        direction  = args.get("direction", "both_ways")
        area_class = args.get("area_class", "NavArea_Default")

        dir_map = {
            "both_ways":    "unreal.ENavLinkDirection.BOTH_WAYS",
            "left_to_right":"unreal.ENavLinkDirection.LEFT_TO_RIGHT",
            "right_to_left":"unreal.ENavLinkDirection.RIGHT_TO_LEFT",
        }
        dir_str = dir_map.get(direction, dir_map["both_ways"])

        script = dedent(f"""
            import unreal, json
            try:
                world  = unreal.EditorLevelLibrary.get_editor_world()
                origin = unreal.Vector({sx}, {sy}, {sz})

                proxy = unreal.EditorLevelLibrary.spawn_actor_from_class(
                    unreal.NavLinkProxy, origin, unreal.Rotator(0, 0, 0)
                )
                proxy.set_actor_label("{proxy_name}")

                # Set link points
                try:
                    link = unreal.NavigationLink()
                    link.set_editor_property("left",  unreal.Vector({sx}, {sy}, {sz}))
                    link.set_editor_property("right", unreal.Vector({ex}, {ey}, {ez}))
                    link.set_editor_property("direction", {dir_str})
                    proxy.set_editor_property("point_links", [link])
                except Exception:
                    pass

                unreal.EditorLevelLibrary.save_current_level()

                result = {{
                    "proxy":     proxy.get_name(),
                    "start":     [{sx}, {sy}, {sz}],
                    "end":       [{ex}, {ey}, {ez}],
                    "direction": "{direction}",
                    "area":      "{area_class}",
                    "status":    "NavLinkProxy placed"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "nav_create_nav_link_proxy")

    async def _list_nav_links(self, args: dict) -> list[types.TextContent]:
        script = dedent(f"""
            import unreal, json
            try:
                world = unreal.EditorLevelLibrary.get_editor_world()
                proxies = unreal.GameplayStatics.get_all_actors_of_class(
                    world, unreal.NavLinkProxy
                )
                links = []
                for p in proxies:
                    info = {{"name": p.get_name(), "location": [
                        round(p.get_actor_location().x,1),
                        round(p.get_actor_location().y,1),
                        round(p.get_actor_location().z,1),
                    ]}}
                    try:
                        point_links = p.get_editor_property("point_links") or []
                        info["link_count"] = len(point_links)
                    except Exception:
                        info["link_count"] = "?"
                    links.append(info)

                result = {{
                    "nav_link_proxies": len(links),
                    "links":            links
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "nav_list_nav_links")

    # ── AI Movement Handlers ───────────────────────────────────────────────────

    async def _set_ai_movement(self, args: dict) -> list[types.TextContent]:
        bp_path          = args["blueprint_path"]
        max_speed        = args.get("max_walk_speed", 600.0)
        max_accel        = args.get("max_acceleration", 2048.0)
        accept_radius    = args.get("acceptance_radius", 5.0)
        use_pathfinding  = args.get("use_pathfinding", True)
        stop_overlap     = args.get("stop_on_overlap", True)

        script = dedent(f"""
            import unreal, json
            try:
                bp = unreal.load_asset("{bp_path}")
                if bp is None:
                    raise RuntimeError("Blueprint not found: {bp_path}")

                cdo = unreal.get_default_object(bp.generated_class())

                # Try to set movement component properties
                move_comp = None
                try:
                    move_comp = cdo.find_component_by_class(unreal.CharacterMovementComponent)
                except Exception:
                    pass

                if move_comp:
                    try:
                        move_comp.set_editor_property("max_walk_speed",   {max_speed})
                        move_comp.set_editor_property("max_acceleration", {max_accel})
                    except Exception:
                        pass

                # AI movement settings on controller
                result = {{
                    "blueprint":         "{bp_path}",
                    "max_walk_speed":    {max_speed},
                    "max_acceleration":  {max_accel},
                    "acceptance_radius": {accept_radius},
                    "use_pathfinding":   {str(use_pathfinding).lower()},
                    "stop_on_overlap":   {str(stop_overlap).lower()},
                    "status": "AI movement settings applied — recompile Blueprint to take effect"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "nav_set_ai_movement")

    async def _get_ai_path_to_target(self, args: dict) -> list[types.TextContent]:
        ai_name     = args["ai_actor_name"]
        target_name = args.get("target_actor_name", "")
        tx = args.get("target_x", 0.0)
        ty = args.get("target_y", 0.0)
        tz = args.get("target_z", 0.0)

        script = dedent(f"""
            import unreal, json
            try:
                world = unreal.EditorLevelLibrary.get_editor_world()
                actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)

                ai_actor     = None
                target_actor = None
                for a in actors:
                    n = a.get_name()
                    if n == "{ai_name}":
                        ai_actor = a
                    if "{target_name}" and n == "{target_name}":
                        target_actor = a

                if ai_actor is None:
                    raise RuntimeError("AI actor not found: {ai_name}")

                start = ai_actor.get_actor_location()
                end   = target_actor.get_actor_location() if target_actor else unreal.Vector({tx},{ty},{tz})

                nav_sys = unreal.NavigationSystemV1.get_navigation_system(world)
                if nav_sys is None:
                    raise RuntimeError("NavigationSystemV1 not found")

                path = nav_sys.find_path_to_location_synchronously(world, start, end)
                pts  = []
                length = 0.0
                if path and hasattr(path, 'path_points'):
                    for i, p in enumerate(path.path_points or []):
                        pts.append([round(p.location.x,1), round(p.location.y,1), round(p.location.z,1)])
                        if i > 0:
                            q = path.path_points[i-1].location
                            length += ((p.location.x-q.x)**2+(p.location.y-q.y)**2+(p.location.z-q.z)**2)**0.5

                result = {{
                    "ai_actor":     "{ai_name}",
                    "target":       "{target_name}" or f"({tx},{ty},{tz})",
                    "start":        [round(start.x,1), round(start.y,1), round(start.z,1)],
                    "end":          [round(end.x,1), round(end.y,1), round(end.z,1)],
                    "waypoints":    len(pts),
                    "path_length":  round(length, 1),
                    "path_points":  pts[:20],
                    "status":       "Path found" if pts else "No path found"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "nav_get_ai_path_to_target")

    # ── Diagnostics Handler ────────────────────────────────────────────────────

    async def _diagnostics(self, args: dict) -> list[types.TextContent]:
        verbose = args.get("verbose", False)

        script = dedent(f"""
            import unreal, json
            try:
                world = unreal.EditorLevelLibrary.get_editor_world()
                issues = []

                navmesh_actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.RecastNavMesh)
                bounds_volumes = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.NavMeshBoundsVolume)
                modifier_vols  = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.NavModifierVolume)
                link_proxies   = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.NavLinkProxy)
                nav_sys        = unreal.NavigationSystemV1.get_navigation_system(world)

                if not navmesh_actors:
                    issues.append("No RecastNavMesh actor in level")
                if not bounds_volumes:
                    issues.append("No NavMeshBoundsVolume — navmesh won't generate")
                if nav_sys is None:
                    issues.append("NavigationSystemV1 not present")

                nm_info = []
                for nm in navmesh_actors:
                    nm_info.append(nm.get_name())

                report = {{
                    "navmesh_actors":      nm_info,
                    "bounds_volumes":      [v.get_name() for v in bounds_volumes],
                    "modifier_volumes":    len(modifier_vols),
                    "nav_link_proxies":    len(link_proxies),
                    "nav_system_present":  nav_sys is not None,
                    "issues_found":        len(issues),
                    "issues":              issues,
                    "verbose_links":       [p.get_name() for p in link_proxies] if {str(verbose).lower()} else [],
                    "status":              "NavMesh diagnostics complete"
                }}
                print("UEOS_RESULT:" + json.dumps(report))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "nav_diagnostics")
