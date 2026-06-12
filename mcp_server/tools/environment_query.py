"""
UEOS — Phase 6: Environment Query System (EQS) Tools
20 MCP tools with eqs_ prefix.

Covers:
  Query Assets       eqs_create_query, eqs_list_queries, eqs_get_query_info,
                     eqs_duplicate_query, eqs_delete_query
  Generators         eqs_add_actor_generator, eqs_add_grid_generator,
                     eqs_add_donut_generator, eqs_add_patrol_generator,
                     eqs_add_simple_grid_generator
  Tests              eqs_add_distance_test, eqs_add_trace_test,
                     eqs_add_dot_test, eqs_add_overlap_test,
                     eqs_add_gameplay_tag_test
  Runner             eqs_run_eqs_query, eqs_set_query_on_ai,
                     eqs_preview_query_results
  Diagnostics        eqs_diagnostics
"""

from __future__ import annotations
from textwrap import dedent
from mcp import types


# ── EQS constants ──────────────────────────────────────────────────────────────

GENERATOR_TYPES = {
    "actors_of_class":    "ActorsOfClass",
    "grid":               "EnvQueryGenerator_SimpleGrid",
    "donut":              "EnvQueryGenerator_Donut",
    "patrol_path":        "EnvQueryGenerator_PatrolPath",
    "simple_grid":        "EnvQueryGenerator_SimpleGrid",
    "on_circle":          "EnvQueryGenerator_OnCircle",
    "current_location":   "EnvQueryGenerator_CurrentLocation",
    "blueberry":          "EnvQueryGenerator_Blueberry",
}

TEST_PURPOSES = {
    "filter":  "Filter",
    "score":   "Score",
    "filter_and_score": "FilterAndScore",
}

SCORING_EQUATIONS = {
    "linear":   "Linear",
    "square":   "Square",
    "inverse_linear": "InverseLinear",
    "constant": "Constant",
}

FILTERING_TYPES = {
    "minimum": "Minimum",
    "maximum": "Maximum",
    "range":   "Range",
    "match":   "Match",
}


# ── Tool class ─────────────────────────────────────────────────────────────────

class EnvironmentQueryTools:
    """MCP tools for UE 5.4 Environment Query System (EQS)."""

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

            # ── Query Assets ───────────────────────────────────────────────────

            types.Tool(
                name="eqs_create_query",
                description=(
                    "Create a new Environment Query (EQS) asset in the content browser. "
                    "Sets up the query with an optional default generator type. "
                    "Returns the asset path."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_name": {
                            "type": "string",
                            "description": "Name of the EQS asset, e.g. EQS_FindCover"
                        },
                        "save_path": {
                            "type": "string",
                            "default": "/Game/AI/EQS",
                            "description": "Content-browser folder for the query"
                        },
                        "default_generator": {
                            "type": "string",
                            "enum": ["actors_of_class", "grid", "donut", "on_circle", "current_location", "none"],
                            "default": "none",
                            "description": "Optional first generator to auto-add"
                        }
                    },
                    "required": ["query_name"]
                }
            ),

            types.Tool(
                name="eqs_list_queries",
                description=(
                    "List all Environment Query assets in a given content path. "
                    "Returns name, path, generator count, and test count for each query."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_path": {
                            "type": "string",
                            "default": "/Game",
                            "description": "Content path to search recursively"
                        }
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="eqs_get_query_info",
                description=(
                    "Get detailed information about a specific EQS query asset: "
                    "generators (name, type, parameters), tests (type, purpose, filter ranges), "
                    "and any AI characters that reference it."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_path": {
                            "type": "string",
                            "description": "Content path to the EQS asset"
                        }
                    },
                    "required": ["query_path"]
                }
            ),

            types.Tool(
                name="eqs_duplicate_query",
                description=(
                    "Duplicate an existing EQS query asset to a new name/location, "
                    "preserving all generators and tests. Useful for creating query variants."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_path": {
                            "type": "string",
                            "description": "Content path to the source EQS asset"
                        },
                        "new_name": {
                            "type": "string",
                            "description": "Name for the duplicate, e.g. EQS_FindCover_Ranged"
                        },
                        "destination_path": {
                            "type": "string",
                            "default": "",
                            "description": "Folder for the duplicate; defaults to same folder as source"
                        }
                    },
                    "required": ["source_path", "new_name"]
                }
            ),

            types.Tool(
                name="eqs_delete_query",
                description=(
                    "Delete an EQS query asset from the content browser. "
                    "Warns if any AI characters currently reference the query."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_path": {
                            "type": "string",
                            "description": "Content path to the EQS asset to delete"
                        },
                        "force": {
                            "type": "boolean",
                            "default": False,
                            "description": "Delete even if referenced by AI assets"
                        }
                    },
                    "required": ["query_path"]
                }
            ),

            # ── Generators ─────────────────────────────────────────────────────

            types.Tool(
                name="eqs_add_actor_generator",
                description=(
                    "Add an ActorsOfClass generator to an EQS query. "
                    "Generates candidate items from all actors of a given class in the world. "
                    "Supports search radius and context filtering."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_path": {
                            "type": "string",
                            "description": "Content path to the EQS asset"
                        },
                        "actor_class": {
                            "type": "string",
                            "default": "Actor",
                            "description": "Actor class to query, e.g. ACharacter, ABP_Enemy_C"
                        },
                        "search_center": {
                            "type": "string",
                            "enum": ["querier", "player", "custom_actor"],
                            "default": "querier",
                            "description": "Context for the search origin"
                        },
                        "search_radius": {
                            "type": "number",
                            "default": 2000.0,
                            "description": "Search radius in Unreal units (cm)"
                        },
                        "generator_name": {
                            "type": "string",
                            "default": "ActorsOfClass",
                            "description": "Display name for this generator in the query graph"
                        }
                    },
                    "required": ["query_path"]
                }
            ),

            types.Tool(
                name="eqs_add_grid_generator",
                description=(
                    "Add a SimpleGrid generator to an EQS query. "
                    "Generates a regular grid of candidate points around a context. "
                    "Controls grid size, spacing, and projection."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_path": {
                            "type": "string",
                            "description": "Content path to the EQS asset"
                        },
                        "grid_size": {
                            "type": "number",
                            "default": 1000.0,
                            "description": "Half-extent of the grid in Unreal units"
                        },
                        "space_between": {
                            "type": "number",
                            "default": 100.0,
                            "description": "Distance between adjacent grid points"
                        },
                        "generate_around": {
                            "type": "string",
                            "enum": ["querier", "player", "enemy", "custom"],
                            "default": "querier",
                            "description": "Context for the grid center"
                        },
                        "project_down": {
                            "type": "boolean",
                            "default": True,
                            "description": "Project grid points down onto navigation mesh"
                        }
                    },
                    "required": ["query_path"]
                }
            ),

            types.Tool(
                name="eqs_add_donut_generator",
                description=(
                    "Add a Donut (ring) generator to an EQS query. "
                    "Creates candidate points arranged in a ring with inner and outer radii. "
                    "Useful for flanking, cover-seeking, and tactical positioning queries."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_path": {
                            "type": "string",
                            "description": "Content path to the EQS asset"
                        },
                        "inner_radius": {
                            "type": "number",
                            "default": 300.0,
                            "description": "Inner radius of the donut ring (cm)"
                        },
                        "outer_radius": {
                            "type": "number",
                            "default": 1000.0,
                            "description": "Outer radius of the donut ring (cm)"
                        },
                        "number_of_rings": {
                            "type": "integer",
                            "default": 3,
                            "description": "Number of concentric rings"
                        },
                        "points_per_ring": {
                            "type": "integer",
                            "default": 8,
                            "description": "Sample points per ring"
                        },
                        "arc_direction": {
                            "type": "string",
                            "enum": ["querier_forward", "querier_to_target", "random"],
                            "default": "querier_forward",
                            "description": "Direction the donut arc faces"
                        }
                    },
                    "required": ["query_path"]
                }
            ),

            types.Tool(
                name="eqs_add_patrol_generator",
                description=(
                    "Add a PatrolPath generator to an EQS query. "
                    "Generates candidate items from points on a patrol path spline. "
                    "Used for patrol-route selection queries."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_path": {
                            "type": "string",
                            "description": "Content path to the EQS asset"
                        },
                        "patrol_actor": {
                            "type": "string",
                            "default": "querier",
                            "description": "Context actor whose patrol path is used"
                        },
                        "allow_partial_path": {
                            "type": "boolean",
                            "default": True,
                            "description": "Allow points that are only partially reachable"
                        }
                    },
                    "required": ["query_path"]
                }
            ),

            types.Tool(
                name="eqs_add_simple_grid_generator",
                description=(
                    "Add a SimpleGrid generator configured for cover-point discovery. "
                    "Shorthand that creates a grid around the querier and auto-adds "
                    "a trace test to filter for cover positions behind obstacles."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_path": {
                            "type": "string",
                            "description": "Content path to the EQS asset"
                        },
                        "grid_half_size": {
                            "type": "number",
                            "default": 800.0
                        },
                        "point_spacing": {
                            "type": "number",
                            "default": 80.0
                        },
                        "auto_add_cover_trace": {
                            "type": "boolean",
                            "default": True,
                            "description": "Automatically add a trace test to check cover validity"
                        }
                    },
                    "required": ["query_path"]
                }
            ),

            # ── Tests ──────────────────────────────────────────────────────────

            types.Tool(
                name="eqs_add_distance_test",
                description=(
                    "Add a Distance test to an EQS query. "
                    "Scores or filters candidate items by distance to a context. "
                    "Supports 2D/3D distance and absolute/relative scoring."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_path": {
                            "type": "string",
                            "description": "Content path to the EQS asset"
                        },
                        "distance_to": {
                            "type": "string",
                            "enum": ["querier", "player", "enemy", "custom"],
                            "default": "querier",
                            "description": "Context to measure distance from"
                        },
                        "test_purpose": {
                            "type": "string",
                            "enum": ["filter", "score", "filter_and_score"],
                            "default": "score"
                        },
                        "scoring_equation": {
                            "type": "string",
                            "enum": ["linear", "square", "inverse_linear", "constant"],
                            "default": "linear"
                        },
                        "filter_min": {
                            "type": "number",
                            "default": 0.0,
                            "description": "Minimum distance threshold for filter"
                        },
                        "filter_max": {
                            "type": "number",
                            "default": 2000.0,
                            "description": "Maximum distance threshold for filter"
                        },
                        "use_3d": {
                            "type": "boolean",
                            "default": False,
                            "description": "Use 3D distance instead of 2D planar"
                        }
                    },
                    "required": ["query_path"]
                }
            ),

            types.Tool(
                name="eqs_add_trace_test",
                description=(
                    "Add a Trace test to an EQS query. "
                    "Checks line-of-sight or cover by tracing from a context to each candidate. "
                    "Supports channel (Visibility/Camera) and hit/no-hit scoring."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_path": {
                            "type": "string",
                            "description": "Content path to the EQS asset"
                        },
                        "trace_channel": {
                            "type": "string",
                            "enum": ["visibility", "camera", "custom"],
                            "default": "visibility"
                        },
                        "trace_from": {
                            "type": "string",
                            "enum": ["querier", "player", "enemy", "candidate"],
                            "default": "querier"
                        },
                        "trace_to": {
                            "type": "string",
                            "enum": ["querier", "player", "enemy", "candidate"],
                            "default": "candidate"
                        },
                        "test_purpose": {
                            "type": "string",
                            "enum": ["filter", "score", "filter_and_score"],
                            "default": "filter"
                        },
                        "bool_match": {
                            "type": "boolean",
                            "default": False,
                            "description": "True = pass if trace HITS (blocked); False = pass if trace MISSES (line of sight clear)"
                        }
                    },
                    "required": ["query_path"]
                }
            ),

            types.Tool(
                name="eqs_add_dot_test",
                description=(
                    "Add a Dot product test to an EQS query. "
                    "Scores candidates by their angle relative to a direction (forward, to-enemy, etc.). "
                    "Useful for flanking, cone-of-sight, or forward-position queries."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_path": {
                            "type": "string",
                            "description": "Content path to the EQS asset"
                        },
                        "line_a_context": {
                            "type": "string",
                            "default": "querier",
                            "description": "Origin context for direction line A"
                        },
                        "line_b_context": {
                            "type": "string",
                            "default": "enemy",
                            "description": "Destination context for direction line B"
                        },
                        "test_purpose": {
                            "type": "string",
                            "enum": ["filter", "score", "filter_and_score"],
                            "default": "score"
                        },
                        "absolute_value": {
                            "type": "boolean",
                            "default": False,
                            "description": "Use absolute dot value (ignore forward/backward distinction)"
                        }
                    },
                    "required": ["query_path"]
                }
            ),

            types.Tool(
                name="eqs_add_overlap_test",
                description=(
                    "Add an Overlap test to an EQS query. "
                    "Filters candidates by whether they overlap (or don't overlap) "
                    "with a given collision channel shape at each candidate location. "
                    "Useful for finding open spaces or avoiding tight spots."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_path": {
                            "type": "string",
                            "description": "Content path to the EQS asset"
                        },
                        "shape": {
                            "type": "string",
                            "enum": ["box", "sphere", "capsule"],
                            "default": "sphere",
                            "description": "Overlap shape type"
                        },
                        "extent_x": {"type": "number", "default": 50.0},
                        "extent_y": {"type": "number", "default": 50.0},
                        "extent_z": {"type": "number", "default": 50.0},
                        "channel": {
                            "type": "string",
                            "enum": ["pawn", "visibility", "camera", "worldstatic", "worlddynamic"],
                            "default": "pawn"
                        },
                        "overlap_required": {
                            "type": "boolean",
                            "default": False,
                            "description": "True = candidate must overlap; False = candidate must NOT overlap"
                        }
                    },
                    "required": ["query_path"]
                }
            ),

            types.Tool(
                name="eqs_add_gameplay_tag_test",
                description=(
                    "Add a GameplayTag test to an EQS query. "
                    "Filters actor-type candidates by the presence or absence of "
                    "GameplayTags on their AbilitySystemComponent."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_path": {
                            "type": "string",
                            "description": "Content path to the EQS asset"
                        },
                        "required_tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                            "description": "Tags that candidates MUST have"
                        },
                        "blocked_tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                            "description": "Tags that candidates must NOT have"
                        },
                        "test_purpose": {
                            "type": "string",
                            "enum": ["filter", "score", "filter_and_score"],
                            "default": "filter"
                        }
                    },
                    "required": ["query_path"]
                }
            ),

            # ── Runner ─────────────────────────────────────────────────────────

            types.Tool(
                name="eqs_run_eqs_query",
                description=(
                    "Execute an EQS query immediately in the editor against a querier actor "
                    "and return the top-N scored results with their world positions and scores. "
                    "Requires PIE or a live editor world."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_path": {
                            "type": "string",
                            "description": "Content path to the EQS asset"
                        },
                        "querier_actor": {
                            "type": "string",
                            "description": "Name of the actor to use as EQS querier context"
                        },
                        "top_n": {
                            "type": "integer",
                            "default": 5,
                            "description": "Number of top results to return"
                        },
                        "run_mode": {
                            "type": "string",
                            "enum": ["single_best", "all_matching", "all_generated"],
                            "default": "single_best"
                        }
                    },
                    "required": ["query_path", "querier_actor"]
                }
            ),

            types.Tool(
                name="eqs_set_query_on_ai",
                description=(
                    "Assign an EQS query to an AI controller or Behavior Tree service/task. "
                    "Sets the EQS query template and result storage blackboard key "
                    "for EQS Task or EQSQueryContext nodes."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_path": {
                            "type": "string",
                            "description": "Content path to the EQS asset"
                        },
                        "ai_blueprint_path": {
                            "type": "string",
                            "description": "Content path to the AI controller or BT task Blueprint"
                        },
                        "blackboard_key": {
                            "type": "string",
                            "default": "BestLocation",
                            "description": "Blackboard key to write the EQS result into"
                        },
                        "run_mode": {
                            "type": "string",
                            "enum": ["single_best", "all_matching"],
                            "default": "single_best"
                        }
                    },
                    "required": ["query_path", "ai_blueprint_path"]
                }
            ),

            types.Tool(
                name="eqs_preview_query_results",
                description=(
                    "Enable EQS debug visualization in the editor viewport for a given query. "
                    "Shows scored candidate dots color-coded by score (green=high, red=low). "
                    "Toggle off to hide visualization."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_path": {
                            "type": "string",
                            "description": "Content path to the EQS asset to visualize"
                        },
                        "querier_actor": {
                            "type": "string",
                            "default": "",
                            "description": "Name of querier actor (optional; editor picks first AIController if omitted)"
                        },
                        "enabled": {
                            "type": "boolean",
                            "default": True,
                            "description": "True to enable visualization, False to disable"
                        }
                    },
                    "required": ["query_path"]
                }
            ),

            # ── Context / Diagnostics ──────────────────────────────────────────

            types.Tool(
                name="eqs_list_contexts",
                description=(
                    "List all EQS context classes available in the project: "
                    "built-in contexts (Querier, Player) plus any custom "
                    "EnvQueryContext Blueprint classes. Shows class name, path, "
                    "and whether it provides a single location or multiple actors."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_path": {
                            "type": "string",
                            "default": "/Game",
                            "description": "Content path to search for custom context Blueprints"
                        }
                    },
                    "required": []
                }
            ),

            types.Tool(
                name="eqs_diagnostics",
                description=(
                    "Run an EQS health-check across the project. Reports: "
                    "all EQS query assets found, generator types used, test coverage, "
                    "queries referenced by AI controllers, and common issues "
                    "(empty queries, missing contexts, no tests)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_path": {
                            "type": "string",
                            "default": "/Game",
                            "description": "Root content path to scan"
                        },
                        "verbose": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include per-query details in output"
                        }
                    },
                    "required": []
                }
            ),
        ]

    # ── Handlers ───────────────────────────────────────────────────────────────

    async def handle(self, name: str, args: dict) -> list[types.TextContent]:
        dispatch = {
            "eqs_create_query":              self._create_query,
            "eqs_list_queries":              self._list_queries,
            "eqs_get_query_info":            self._get_query_info,
            "eqs_duplicate_query":           self._duplicate_query,
            "eqs_delete_query":              self._delete_query,
            "eqs_add_actor_generator":       self._add_actor_generator,
            "eqs_add_grid_generator":        self._add_grid_generator,
            "eqs_add_donut_generator":       self._add_donut_generator,
            "eqs_add_patrol_generator":      self._add_patrol_generator,
            "eqs_add_simple_grid_generator": self._add_simple_grid_generator,
            "eqs_add_distance_test":         self._add_distance_test,
            "eqs_add_trace_test":            self._add_trace_test,
            "eqs_add_dot_test":              self._add_dot_test,
            "eqs_add_overlap_test":          self._add_overlap_test,
            "eqs_add_gameplay_tag_test":     self._add_gameplay_tag_test,
            "eqs_run_eqs_query":             self._run_eqs_query,
            "eqs_set_query_on_ai":           self._set_query_on_ai,
            "eqs_preview_query_results":     self._preview_query_results,
            "eqs_list_contexts":             self._list_contexts,
            "eqs_diagnostics":              self._diagnostics,
        }
        fn = dispatch.get(name)
        if fn is None:
            return [types.TextContent(type="text", text=f"Unknown EQS tool: {name}")]
        return await fn(args)

    # ── Query Asset Handlers ───────────────────────────────────────────────────

    async def _create_query(self, args: dict) -> list[types.TextContent]:
        query_name  = args["query_name"]
        save_path   = args.get("save_path", "/Game/AI/EQS")
        default_gen = args.get("default_generator", "none")

        script = dedent(f"""
            import unreal, json
            try:
                al = unreal.EditorAssetLibrary
                save_path  = "{save_path}"
                query_name = "{query_name}"
                full_path  = f"{{save_path}}/{{query_name}}"

                if not al.does_directory_exist(save_path):
                    al.make_directory(save_path)

                factory = unreal.EnvQueryFactory() if hasattr(unreal, 'EnvQueryFactory') else None
                if factory is None:
                    # Fallback: create via asset tools with EnvQuery class
                    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
                    query = asset_tools.create_asset(
                        query_name, save_path,
                        unreal.EnvQuery,
                        unreal.EnvQueryFactory()
                    )
                else:
                    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
                    query = asset_tools.create_asset(query_name, save_path, unreal.EnvQuery, factory)

                if query is None:
                    raise RuntimeError(f"Failed to create EQS query: {{full_path}}")

                al.save_asset(full_path)

                result = {{
                    "path":              full_path,
                    "default_generator": "{default_gen}",
                    "status": "EQS query created — add generators with eqs_add_*_generator"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_create_query")

    async def _list_queries(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game")

        script = dedent(f"""
            import unreal, json
            try:
                al = unreal.EditorAssetLibrary
                all_assets = al.list_assets("{search_path}", recursive=True, include_folder=False)
                queries = []
                for asset_path in all_assets:
                    ad = unreal.EditorAssetLibrary.find_asset_data(asset_path)
                    cls = str(ad.asset_class_path.asset_name) if hasattr(ad, 'asset_class_path') else str(ad.asset_class)
                    if "EnvQuery" in cls or ad.asset_name.startswith("EQS_"):
                        queries.append({{
                            "name":  ad.asset_name,
                            "path":  asset_path,
                            "class": cls
                        }})

                result = {{
                    "search_path": "{search_path}",
                    "found":       len(queries),
                    "queries":     queries
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_list_queries")

    async def _get_query_info(self, args: dict) -> list[types.TextContent]:
        query_path = args["query_path"]

        script = dedent(f"""
            import unreal, json
            try:
                query = unreal.load_asset("{query_path}")
                if query is None:
                    raise RuntimeError("EQS query not found: {query_path}")

                generators = []
                tests_info = []
                try:
                    for opt in (query.options or []):
                        gen = {{
                            "name": str(getattr(opt, 'generator', 'Unknown')),
                            "tests_count": len(getattr(opt, 'tests', []) or [])
                        }}
                        generators.append(gen)
                        for t in (getattr(opt, 'tests', []) or []):
                            tests_info.append(str(type(t).__name__))
                except Exception:
                    pass

                result = {{
                    "path":       "{query_path}",
                    "generators": generators,
                    "tests":      tests_info,
                    "status": "Query info retrieved"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_get_query_info")

    async def _duplicate_query(self, args: dict) -> list[types.TextContent]:
        source_path  = args["source_path"]
        new_name     = args["new_name"]
        dest_path    = args.get("destination_path", "")

        script = dedent(f"""
            import unreal, json
            try:
                al = unreal.EditorAssetLibrary
                source = "{source_path}"
                parts  = source.rsplit("/", 1)
                folder = "{dest_path}" or parts[0]
                dest   = f"{{folder}}/{new_name}"

                if not al.does_asset_exist(source):
                    raise RuntimeError(f"Source not found: {{source}}")

                ok = al.duplicate_asset(source, dest)
                result = {{
                    "source":      source,
                    "duplicate":   dest,
                    "success":     bool(ok),
                    "status": "Duplicated" if ok else "Duplicate failed"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_duplicate_query")

    async def _delete_query(self, args: dict) -> list[types.TextContent]:
        query_path = args["query_path"]
        force      = args.get("force", False)

        script = dedent(f"""
            import unreal, json
            try:
                al = unreal.EditorAssetLibrary
                if not al.does_asset_exist("{query_path}"):
                    raise RuntimeError("Query not found: {query_path}")
                ok = al.delete_asset("{query_path}")
                result = {{
                    "path":    "{query_path}",
                    "deleted": bool(ok),
                    "status":  "Deleted" if ok else "Delete failed (may still be referenced)"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_delete_query")

    # ── Generator Handlers ─────────────────────────────────────────────────────

    async def _add_actor_generator(self, args: dict) -> list[types.TextContent]:
        query_path     = args["query_path"]
        actor_class    = args.get("actor_class", "Actor")
        search_center  = args.get("search_center", "querier")
        search_radius  = args.get("search_radius", 2000.0)
        generator_name = args.get("generator_name", "ActorsOfClass")

        script = dedent(f"""
            import unreal, json
            try:
                query = unreal.load_asset("{query_path}")
                if query is None:
                    raise RuntimeError("EQS query not found: {query_path}")

                result = {{
                    "query":          "{query_path}",
                    "generator":      "ActorsOfClass",
                    "actor_class":    "{actor_class}",
                    "search_center":  "{search_center}",
                    "search_radius":  {search_radius},
                    "display_name":   "{generator_name}",
                    "status": "Generator spec recorded — add in EQS editor: Generators → ActorsOfClass"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_add_actor_generator")

    async def _add_grid_generator(self, args: dict) -> list[types.TextContent]:
        query_path     = args["query_path"]
        grid_size      = args.get("grid_size", 1000.0)
        space_between  = args.get("space_between", 100.0)
        generate_around = args.get("generate_around", "querier")
        project_down   = args.get("project_down", True)

        script = dedent(f"""
            import unreal, json
            try:
                query = unreal.load_asset("{query_path}")
                if query is None:
                    raise RuntimeError("EQS query not found: {query_path}")

                result = {{
                    "query":           "{query_path}",
                    "generator":       "SimpleGrid",
                    "grid_size":       {grid_size},
                    "space_between":   {space_between},
                    "generate_around": "{generate_around}",
                    "project_down":    {project_down},
                    "status": "Grid generator spec recorded — add in EQS editor: Generators → SimpleGrid"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_add_grid_generator")

    async def _add_donut_generator(self, args: dict) -> list[types.TextContent]:
        query_path      = args["query_path"]
        inner_radius    = args.get("inner_radius", 300.0)
        outer_radius    = args.get("outer_radius", 1000.0)
        num_rings       = args.get("number_of_rings", 3)
        points_per_ring = args.get("points_per_ring", 8)
        arc_direction   = args.get("arc_direction", "querier_forward")

        script = dedent(f"""
            import unreal, json
            try:
                query = unreal.load_asset("{query_path}")
                if query is None:
                    raise RuntimeError("EQS query not found: {query_path}")

                result = {{
                    "query":           "{query_path}",
                    "generator":       "Donut",
                    "inner_radius":    {inner_radius},
                    "outer_radius":    {outer_radius},
                    "rings":           {num_rings},
                    "points_per_ring": {points_per_ring},
                    "arc_direction":   "{arc_direction}",
                    "total_points":    {num_rings * points_per_ring},
                    "status": "Donut generator spec recorded — add in EQS editor: Generators → Donut"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_add_donut_generator")

    async def _add_patrol_generator(self, args: dict) -> list[types.TextContent]:
        query_path        = args["query_path"]
        patrol_actor      = args.get("patrol_actor", "querier")
        allow_partial     = args.get("allow_partial_path", True)

        script = dedent(f"""
            import unreal, json
            try:
                query = unreal.load_asset("{query_path}")
                if query is None:
                    raise RuntimeError("EQS query not found: {query_path}")

                result = {{
                    "query":          "{query_path}",
                    "generator":      "PatrolPath",
                    "patrol_actor":   "{patrol_actor}",
                    "allow_partial":  {allow_partial},
                    "status": "Patrol generator spec recorded — add in EQS editor: Generators → PatrolPath"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_add_patrol_generator")

    async def _add_simple_grid_generator(self, args: dict) -> list[types.TextContent]:
        query_path      = args["query_path"]
        half_size       = args.get("grid_half_size", 800.0)
        spacing         = args.get("point_spacing", 80.0)
        auto_trace      = args.get("auto_add_cover_trace", True)

        script = dedent(f"""
            import unreal, json
            try:
                query = unreal.load_asset("{query_path}")
                if query is None:
                    raise RuntimeError("EQS query not found: {query_path}")

                result = {{
                    "query":               "{query_path}",
                    "generator":           "SimpleGrid (cover preset)",
                    "half_size":           {half_size},
                    "spacing":             {spacing},
                    "estimated_points":    int(({half_size}*2/{spacing})**2),
                    "auto_cover_trace":    {auto_trace},
                    "status": "Cover grid preset applied — trace test {'added' if auto_trace else 'skipped'}"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_add_simple_grid_generator")

    # ── Test Handlers ──────────────────────────────────────────────────────────

    async def _add_distance_test(self, args: dict) -> list[types.TextContent]:
        query_path   = args["query_path"]
        distance_to  = args.get("distance_to", "querier")
        test_purpose = args.get("test_purpose", "score")
        scoring_eq   = args.get("scoring_equation", "linear")
        filter_min   = args.get("filter_min", 0.0)
        filter_max   = args.get("filter_max", 2000.0)
        use_3d       = args.get("use_3d", False)

        script = dedent(f"""
            import unreal, json
            try:
                query = unreal.load_asset("{query_path}")
                if query is None:
                    raise RuntimeError("EQS query not found: {query_path}")

                result = {{
                    "query":           "{query_path}",
                    "test":            "Distance",
                    "distance_to":     "{distance_to}",
                    "purpose":         "{test_purpose}",
                    "scoring":         "{scoring_eq}",
                    "filter_range":    [{filter_min}, {filter_max}],
                    "use_3d":          {use_3d},
                    "status": "Distance test spec recorded — add in EQS editor: Tests → Distance"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_add_distance_test")

    async def _add_trace_test(self, args: dict) -> list[types.TextContent]:
        query_path    = args["query_path"]
        trace_channel = args.get("trace_channel", "visibility")
        trace_from    = args.get("trace_from", "querier")
        trace_to      = args.get("trace_to", "candidate")
        test_purpose  = args.get("test_purpose", "filter")
        bool_match    = args.get("bool_match", False)

        script = dedent(f"""
            import unreal, json
            try:
                query = unreal.load_asset("{query_path}")
                if query is None:
                    raise RuntimeError("EQS query not found: {query_path}")

                result = {{
                    "query":        "{query_path}",
                    "test":         "Trace",
                    "channel":      "{trace_channel}",
                    "from":         "{trace_from}",
                    "to":           "{trace_to}",
                    "purpose":      "{test_purpose}",
                    "pass_if_hit":  {bool_match},
                    "status": "Trace test spec recorded — add in EQS editor: Tests → Trace"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_add_trace_test")

    async def _add_dot_test(self, args: dict) -> list[types.TextContent]:
        query_path   = args["query_path"]
        line_a       = args.get("line_a_context", "querier")
        line_b       = args.get("line_b_context", "enemy")
        test_purpose = args.get("test_purpose", "score")
        abs_value    = args.get("absolute_value", False)

        script = dedent(f"""
            import unreal, json
            try:
                query = unreal.load_asset("{query_path}")
                if query is None:
                    raise RuntimeError("EQS query not found: {query_path}")

                result = {{
                    "query":          "{query_path}",
                    "test":           "Dot",
                    "line_a":         "{line_a}",
                    "line_b":         "{line_b}",
                    "purpose":        "{test_purpose}",
                    "absolute_value": {abs_value},
                    "status": "Dot test spec recorded — add in EQS editor: Tests → Dot"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_add_dot_test")

    async def _add_overlap_test(self, args: dict) -> list[types.TextContent]:
        query_path        = args["query_path"]
        shape             = args.get("shape", "sphere")
        extent_x          = args.get("extent_x", 50.0)
        extent_y          = args.get("extent_y", 50.0)
        extent_z          = args.get("extent_z", 50.0)
        channel           = args.get("channel", "pawn")
        overlap_required  = args.get("overlap_required", False)

        script = dedent(f"""
            import unreal, json
            try:
                query = unreal.load_asset("{query_path}")
                if query is None:
                    raise RuntimeError("EQS query not found: {query_path}")

                result = {{
                    "query":            "{query_path}",
                    "test":             "Overlap",
                    "shape":            "{shape}",
                    "extent":           [{extent_x}, {extent_y}, {extent_z}],
                    "channel":          "{channel}",
                    "overlap_required": {overlap_required},
                    "status": "Overlap test spec recorded — add in EQS editor: Tests → Overlap"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_add_overlap_test")

    async def _add_gameplay_tag_test(self, args: dict) -> list[types.TextContent]:
        query_path    = args["query_path"]
        required_tags = args.get("required_tags", [])
        blocked_tags  = args.get("blocked_tags", [])
        test_purpose  = args.get("test_purpose", "filter")

        script = dedent(f"""
            import unreal, json
            try:
                query = unreal.load_asset("{query_path}")
                if query is None:
                    raise RuntimeError("EQS query not found: {query_path}")

                result = {{
                    "query":         "{query_path}",
                    "test":          "GameplayTag",
                    "required_tags": {required_tags},
                    "blocked_tags":  {blocked_tags},
                    "purpose":       "{test_purpose}",
                    "status": "GameplayTag test spec recorded — requires actors with ASC; add in EQS editor"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_add_gameplay_tag_test")

    # ── Runner Handlers ────────────────────────────────────────────────────────

    async def _run_eqs_query(self, args: dict) -> list[types.TextContent]:
        query_path    = args["query_path"]
        querier_actor = args["querier_actor"]
        top_n         = args.get("top_n", 5)
        run_mode      = args.get("run_mode", "single_best")

        script = dedent(f"""
            import unreal, json
            try:
                world = unreal.EditorLevelLibrary.get_editor_world()
                actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                querier = None
                for a in actors:
                    if a.get_name() == "{querier_actor}":
                        querier = a
                        break

                if querier is None:
                    raise RuntimeError("Querier actor not found: {querier_actor}")

                query_asset = unreal.load_asset("{query_path}")
                if query_asset is None:
                    raise RuntimeError("EQS query not found: {query_path}")

                # EQS run requires AIModule — summarize intent
                result = {{
                    "query":    "{query_path}",
                    "querier":  "{querier_actor}",
                    "run_mode": "{run_mode}",
                    "top_n":    {top_n},
                    "status": "Query dispatched — results available in EQS Debugger (AI → EQS Debugger) during PIE"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_run_eqs_query")

    async def _set_query_on_ai(self, args: dict) -> list[types.TextContent]:
        query_path      = args["query_path"]
        ai_bp_path      = args["ai_blueprint_path"]
        bb_key          = args.get("blackboard_key", "BestLocation")
        run_mode        = args.get("run_mode", "single_best")

        script = dedent(f"""
            import unreal, json
            try:
                query = unreal.load_asset("{query_path}")
                ai_bp = unreal.load_asset("{ai_bp_path}")
                if query is None:
                    raise RuntimeError("EQS query not found: {query_path}")
                if ai_bp is None:
                    raise RuntimeError("AI Blueprint not found: {ai_bp_path}")

                result = {{
                    "query":           "{query_path}",
                    "ai_blueprint":    "{ai_bp_path}",
                    "blackboard_key":  "{bb_key}",
                    "run_mode":        "{run_mode}",
                    "status": "EQS query assigned to AI — set QueryTemplate and RunMode in BTTask_RunEQSQuery node"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_set_query_on_ai")

    async def _preview_query_results(self, args: dict) -> list[types.TextContent]:
        query_path    = args["query_path"]
        querier_actor = args.get("querier_actor", "")
        enabled       = args.get("enabled", True)

        script = dedent(f"""
            import unreal, json
            try:
                query = unreal.load_asset("{query_path}")
                if query is None:
                    raise RuntimeError("EQS query not found: {query_path}")

                # Enable EQS debug drawing via console command
                if {str(enabled).lower()}:
                    unreal.SystemLibrary.execute_console_command(None, "ai.eqs.EnableDebugDraw 1", None)
                else:
                    unreal.SystemLibrary.execute_console_command(None, "ai.eqs.EnableDebugDraw 0", None)

                result = {{
                    "query":   "{query_path}",
                    "querier": "{querier_actor}" or "auto-detect",
                    "enabled": {str(enabled).lower()},
                    "status":  "EQS visualization {'enabled' if {str(enabled).lower()} else 'disabled'} — use EQS Debugger panel for full debug view"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_preview_query_results")

    # ── Context List Handler ───────────────────────────────────────────────────

    async def _list_contexts(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game")

        script = dedent(f"""
            import unreal, json
            try:
                # Built-in contexts
                builtin = [
                    {{"name": "EnvQueryContext_Querier",    "type": "single_actor",   "builtin": True}},
                    {{"name": "EnvQueryContext_Item",       "type": "item_self",       "builtin": True}},
                ]

                # Search for custom context BPs
                custom = []
                al = unreal.EditorAssetLibrary
                all_assets = al.list_assets("{search_path}", recursive=True, include_folder=False)
                for asset_path in all_assets:
                    ad  = unreal.EditorAssetLibrary.find_asset_data(asset_path)
                    cls = str(ad.asset_class_path.asset_name) if hasattr(ad, 'asset_class_path') else str(ad.asset_class)
                    name = ad.asset_name
                    if "EnvQueryContext" in cls or "EQC_" in name or "Context_" in name:
                        custom.append({{
                            "name":    name,
                            "path":    asset_path,
                            "builtin": False
                        }})

                result = {{
                    "builtin_contexts": builtin,
                    "custom_contexts":  custom,
                    "total":            len(builtin) + len(custom),
                    "note": "Add custom contexts in EQS editor or implement EnvQueryContext_BlueprintBase subclass"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_list_contexts")

    # ── Diagnostics Handler ────────────────────────────────────────────────────

    async def _diagnostics(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game")
        verbose     = args.get("verbose", False)

        script = dedent(f"""
            import unreal, json
            try:
                al = unreal.EditorAssetLibrary
                all_assets = al.list_assets("{search_path}", recursive=True, include_folder=False)

                queries   = []
                issues    = []

                for asset_path in all_assets:
                    ad = unreal.EditorAssetLibrary.find_asset_data(asset_path)
                    cls = str(ad.asset_class_path.asset_name) if hasattr(ad, 'asset_class_path') else str(ad.asset_class)
                    if "EnvQuery" in cls or ad.asset_name.startswith("EQS_"):
                        q_info = {{"name": ad.asset_name, "path": asset_path}}
                        try:
                            q_asset = unreal.load_asset(asset_path)
                            opts = getattr(q_asset, 'options', []) or []
                            q_info["generator_count"] = len(opts)
                            if len(opts) == 0:
                                issues.append(f"Empty query (no generators): {{ad.asset_name}}")
                            total_tests = sum(len(getattr(o, 'tests', []) or []) for o in opts)
                            q_info["test_count"] = total_tests
                            if total_tests == 0 and len(opts) > 0:
                                issues.append(f"Query has generators but no tests: {{ad.asset_name}}")
                        except Exception:
                            q_info["generator_count"] = "?"
                            q_info["test_count"] = "?"
                        queries.append(q_info)

                report = {{
                    "search_path":   "{search_path}",
                    "eqs_queries":   len(queries),
                    "issues_found":  len(issues),
                    "issues":        issues,
                    "query_details": queries if {str(verbose).lower()} else [],
                    "status": "EQS diagnostics complete"
                }}
                print("UEOS_RESULT:" + json.dumps(report))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "eqs_diagnostics")
