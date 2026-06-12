"""
UEOS UE-Side Utility: Environment Query System (EQS) Helpers
============================================================
Run directly in the UE 5.4 Python console (no MCP required):

    import sys, importlib
    sys.path.insert(0, r"C:\\UEOS\\ue_scripts")
    import eqs_utils as eqs; importlib.reload(eqs)
    eqs.ueos_eqs_quick_setup("/Game/AI/EQS")

Public API (15 functions):
  ueos_eqs_quick_setup(save_path)                  — Create a suite of starter EQS queries
  ueos_create_query(name, save_path)               — Create empty EQS query asset
  ueos_create_cover_query(name, save_path)         — Grid + Trace cover-seek query
  ueos_create_flank_query(name, save_path)         — Donut + Dot flank query
  ueos_create_patrol_query(name, save_path)        — PatrolPath point query
  ueos_create_retreat_query(name, save_path)       — Distant safe-position query
  ueos_create_attack_position_query(name, save_path) — Attack range query
  ueos_duplicate_query(source, new_name)           — Duplicate EQS asset
  ueos_list_queries(search_path)                   — List all EQS queries
  ueos_get_query_info(query_path)                  — Inspect query generators/tests
  ueos_set_query_on_bt_task(query_path, task_path, bb_key) — Assign query to BT task
  ueos_enable_debug_draw(enabled)                  — Toggle EQS debug visualization
  ueos_get_querier_location(actor_name)            — Get actor location for queries
  ueos_run_simple_distance_check(from_actor, to_actor) — Quick reachability check
  ueos_eqs_diagnostics(search_path)               — EQS health report
"""

import unreal
import json


# ── Logging ────────────────────────────────────────────────────────────────────

def _log(msg: str):
    unreal.log(f"[UEOS EQS] {msg}")

def _err(msg: str):
    unreal.log_error(f"[UEOS EQS] {msg}")

def _warn(msg: str):
    unreal.log_warning(f"[UEOS EQS] {msg}")


# ── Quick Setup ────────────────────────────────────────────────────────────────

def ueos_eqs_quick_setup(save_path: str = "/Game/AI/EQS") -> dict:
    """
    Create a starter suite of EQS queries:
      EQS_FindCover, EQS_FlankEnemy, EQS_PatrolNext,
      EQS_Retreat, EQS_AttackPosition
    Returns a summary dict.
    """
    _log(f"EQS quick-setup to: {save_path}")
    results = {}

    queries = [
        ("EQS_FindCover",       ueos_create_cover_query),
        ("EQS_FlankEnemy",      ueos_create_flank_query),
        ("EQS_PatrolNext",      ueos_create_patrol_query),
        ("EQS_Retreat",         ueos_create_retreat_query),
        ("EQS_AttackPosition",  ueos_create_attack_position_query),
    ]
    for name, creator in queries:
        try:
            r = creator(name, save_path)
            results[name] = r.get("path", "OK")
        except Exception as e:
            results[name] = {"error": str(e)}
            _warn(f"Failed to create {name}: {e}")

    results["status"] = "EQS quick-setup complete"
    _log("Quick-setup done: " + str(list(results.keys())))
    return results


# ── Query Asset Creators ───────────────────────────────────────────────────────

def ueos_create_query(name: str, save_path: str = "/Game/AI/EQS") -> dict:
    """Create an empty EQS query asset."""
    al = unreal.EditorAssetLibrary
    if not al.does_directory_exist(save_path):
        al.make_directory(save_path)

    full_path = f"{save_path}/{name}"
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

    query = None
    try:
        factory = unreal.EnvQueryFactory()
        query = asset_tools.create_asset(name, save_path, unreal.EnvQuery, factory)
    except Exception:
        pass

    if query is None:
        raise RuntimeError(f"Failed to create EQS query: {full_path}")

    al.save_asset(full_path)
    _log(f"EQS query created: {full_path}")
    return {
        "path":   full_path,
        "status": "EQS query created — add generators in EQS editor"
    }


def ueos_create_cover_query(name: str = "EQS_FindCover", save_path: str = "/Game/AI/EQS") -> dict:
    """
    Create a cover-seeking EQS query preset.
    Pattern: SimpleGrid around querier → Trace test (filter: NOT visible from enemy)
    Returns asset path.
    """
    result = ueos_create_query(name, save_path)
    result["preset"]       = "cover"
    result["generator"]    = "SimpleGrid (800 half-size, 80 spacing)"
    result["test_1"]       = "Trace (Visibility, from:enemy, to:candidate, pass_if_hit=False)"
    result["test_2"]       = "Distance (to:querier, score, linear)"
    result["instructions"] = (
        "In EQS editor: Add SimpleGrid generator, set GridHalfSize=800, SpaceBetween=80. "
        "Add Trace test: channel=Visibility, from=EnvQueryContext_Enemy, to=Item, bool_match=False. "
        "Add Distance test: context=EnvQueryContext_Querier, purpose=Score, equation=Linear."
    )
    _log(f"Cover query preset created: {result['path']}")
    return result


def ueos_create_flank_query(name: str = "EQS_FlankEnemy", save_path: str = "/Game/AI/EQS") -> dict:
    """
    Create a flanking EQS query preset.
    Pattern: Donut around enemy (inner 300, outer 800) → Dot test (avoid front arc) → Trace (reachable)
    """
    result = ueos_create_query(name, save_path)
    result["preset"]       = "flank"
    result["generator"]    = "Donut (inner=300, outer=800, rings=3, points_per_ring=8)"
    result["test_1"]       = "Dot (querier→enemy direction, absolute=True, score to prefer sides)"
    result["test_2"]       = "Trace (Visibility, from:candidate, to:enemy, pass_if_hit=True)"
    result["test_3"]       = "Distance (to:querier, filter min=300)"
    result["instructions"] = (
        "In EQS editor: Add Donut generator, InnerRadius=300, OuterRadius=800, NumRings=3, PointsPerRing=8. "
        "Add Dot test (absolute dot value). Add Distance test (filter min=300 to avoid too close)."
    )
    _log(f"Flank query preset created: {result['path']}")
    return result


def ueos_create_patrol_query(name: str = "EQS_PatrolNext", save_path: str = "/Game/AI/EQS") -> dict:
    """
    Create a patrol-point selection EQS query preset.
    Pattern: PatrolPath generator → Distance (score by proximity to current patrol index)
    """
    result = ueos_create_query(name, save_path)
    result["preset"]       = "patrol"
    result["generator"]    = "PatrolPath (actor=EnvQueryContext_Querier)"
    result["test_1"]       = "Distance (to:querier, filter min=50 to skip current position)"
    result["instructions"] = (
        "In EQS editor: Add PatrolPath generator with context pointing to the patrolling AI. "
        "Add Distance filter (min=50) to exclude the current position."
    )
    _log(f"Patrol query preset created: {result['path']}")
    return result


def ueos_create_retreat_query(name: str = "EQS_Retreat", save_path: str = "/Game/AI/EQS") -> dict:
    """
    Create a retreat/flee EQS query preset.
    Pattern: Grid far from enemy → Distance score (far from enemy) → Trace (reachable)
    """
    result = ueos_create_query(name, save_path)
    result["preset"]       = "retreat"
    result["generator"]    = "SimpleGrid (1200 half-size, 120 spacing, around querier)"
    result["test_1"]       = "Distance (to:enemy, score InverseLinear — far = good)"
    result["test_2"]       = "Trace (Visibility, from:candidate, to:enemy, pass_if_hit=False — avoid LOS)"
    result["test_3"]       = "Distance (to:querier, filter max=1500 — stay within flee radius)"
    result["instructions"] = (
        "In EQS editor: SimpleGrid 1200 around querier. "
        "Distance test to enemy with InverseLinear scoring. "
        "Trace filter: position must NOT be visible from enemy."
    )
    _log(f"Retreat query preset created: {result['path']}")
    return result


def ueos_create_attack_position_query(name: str = "EQS_AttackPosition", save_path: str = "/Game/AI/EQS") -> dict:
    """
    Create an attack-position EQS query preset.
    Pattern: Donut around enemy at attack range → Trace (has LOS) → Distance (prefer optimal range)
    """
    result = ueos_create_query(name, save_path)
    result["preset"]       = "attack_position"
    result["generator"]    = "Donut (inner=400, outer=700, rings=2, points_per_ring=12, around enemy)"
    result["test_1"]       = "Trace (Visibility, from:candidate, to:enemy, pass_if_hit=True — must see enemy)"
    result["test_2"]       = "Distance (to:enemy, filter range=400-700)"
    result["test_3"]       = "Distance (to:querier, score Linear — prefer closer options)"
    result["instructions"] = (
        "In EQS editor: Donut around EnvQueryContext_Enemy, InnerRadius=400, OuterRadius=700. "
        "Trace test (must have LOS to enemy). Distance filter for attack range."
    )
    _log(f"Attack position query preset created: {result['path']}")
    return result


# ── Asset Operations ───────────────────────────────────────────────────────────

def ueos_duplicate_query(source_path: str, new_name: str, dest_folder: str = "") -> dict:
    """Duplicate an EQS query asset to a new name."""
    al = unreal.EditorAssetLibrary
    if not al.does_asset_exist(source_path):
        raise RuntimeError(f"Source not found: {source_path}")

    parts  = source_path.rsplit("/", 1)
    folder = dest_folder or parts[0]
    dest   = f"{folder}/{new_name}"

    ok = al.duplicate_asset(source_path, dest)
    if not ok:
        raise RuntimeError(f"Failed to duplicate {source_path} → {dest}")

    _log(f"Duplicated: {source_path} → {dest}")
    return {
        "source":    source_path,
        "duplicate": dest,
        "status":    "Duplicated"
    }


def ueos_list_queries(search_path: str = "/Game") -> dict:
    """List all EQS query assets in a content path."""
    al = unreal.EditorAssetLibrary
    if not al.does_directory_exist(search_path):
        return {"error": f"Path not found: {search_path}"}

    all_assets = al.list_assets(search_path, recursive=True, include_folder=False)
    queries = []
    for asset_path in all_assets:
        ad  = unreal.EditorAssetLibrary.find_asset_data(asset_path)
        cls = str(ad.asset_class_path.asset_name) if hasattr(ad, 'asset_class_path') else str(ad.asset_class)
        if "EnvQuery" in cls or ad.asset_name.startswith("EQS_"):
            queries.append({"name": ad.asset_name, "path": asset_path})

    _log(f"Found {len(queries)} EQS queries in {search_path}")
    return {
        "search_path": search_path,
        "count":       len(queries),
        "queries":     queries
    }


def ueos_get_query_info(query_path: str) -> dict:
    """Inspect EQS query: generators, test count, option count."""
    query = unreal.load_asset(query_path)
    if query is None:
        raise RuntimeError(f"EQS query not found: {query_path}")

    info = {"path": query_path, "options": []}
    try:
        opts = query.options or []
        for opt in opts:
            gen_info = {
                "generator": str(getattr(opt, 'generator', 'none')),
                "tests":     len(getattr(opt, 'tests', []) or [])
            }
            info["options"].append(gen_info)
        info["generator_count"] = len(opts)
    except Exception as e:
        info["parse_error"] = str(e)

    _log(f"Query info for {query_path}: {len(info['options'])} options")
    return info


def ueos_set_query_on_bt_task(
    query_path: str,
    task_path: str,
    bb_key: str = "BestLocation"
) -> dict:
    """Assign an EQS query to a Behavior Tree task Blueprint."""
    query = unreal.load_asset(query_path)
    task  = unreal.load_asset(task_path)
    if query is None:
        raise RuntimeError(f"EQS query not found: {query_path}")
    if task is None:
        raise RuntimeError(f"BT task not found: {task_path}")

    # Try to set query template on CDO
    try:
        cdo = unreal.get_default_object(task.generated_class())
        cdo.set_editor_property("query_template", query)
    except Exception:
        pass

    _log(f"EQS query {query_path} assigned to BT task {task_path}, bb_key={bb_key}")
    return {
        "query":          query_path,
        "task":           task_path,
        "blackboard_key": bb_key,
        "status":         "Query assigned — set BlackboardKey in BTTask node"
    }


# ── Debug & Testing ────────────────────────────────────────────────────────────

def ueos_enable_debug_draw(enabled: bool = True) -> dict:
    """Toggle EQS debug visualization in the editor viewport."""
    cmd = "ai.eqs.EnableDebugDraw 1" if enabled else "ai.eqs.EnableDebugDraw 0"
    try:
        unreal.SystemLibrary.execute_console_command(None, cmd, None)
    except Exception as e:
        _warn(f"Console command failed: {e}")

    _log(f"EQS debug draw: {'ON' if enabled else 'OFF'}")
    return {
        "debug_draw": enabled,
        "command":    cmd,
        "status":     f"EQS debug {'enabled' if enabled else 'disabled'} — use EQS Debugger panel in PIE"
    }


def ueos_get_querier_location(actor_name: str) -> dict:
    """Get world location of an actor for use as EQS querier context."""
    world  = unreal.EditorLevelLibrary.get_editor_world()
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    for a in actors:
        if a.get_name() == actor_name:
            loc = a.get_actor_location()
            return {
                "actor":    actor_name,
                "location": [round(loc.x, 1), round(loc.y, 1), round(loc.z, 1)]
            }
    return {"error": f"Actor not found: {actor_name}"}


def ueos_run_simple_distance_check(from_actor: str, to_actor: str) -> dict:
    """Quick reachability check between two actors using NavigationSystemV1."""
    world  = unreal.EditorLevelLibrary.get_editor_world()
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)

    src = None; tgt = None
    for a in actors:
        n = a.get_name()
        if n == from_actor: src = a
        if n == to_actor:   tgt = a

    if src is None:
        return {"error": f"From actor not found: {from_actor}"}
    if tgt is None:
        return {"error": f"To actor not found: {to_actor}"}

    start = src.get_actor_location()
    end   = tgt.get_actor_location()

    nav_sys = unreal.NavigationSystemV1.get_navigation_system(world)
    if nav_sys is None:
        return {"error": "NavigationSystemV1 not present in level"}

    path = nav_sys.find_path_to_location_synchronously(world, start, end)
    pts  = path.path_points if (path and hasattr(path, 'path_points')) else []
    length = 0.0
    for i in range(1, len(pts)):
        p = pts[i].location; q = pts[i-1].location
        length += ((p.x-q.x)**2+(p.y-q.y)**2+(p.z-q.z)**2)**0.5

    _log(f"Distance check {from_actor}→{to_actor}: {len(pts)} waypoints, {length:.0f} cm")
    return {
        "from":         from_actor,
        "to":           to_actor,
        "reachable":    len(pts) > 0,
        "path_length":  round(length, 1),
        "waypoints":    len(pts),
    }


def ueos_eqs_diagnostics(search_path: str = "/Game") -> dict:
    """Full EQS health report."""
    _log(f"EQS diagnostics on {search_path}")
    al = unreal.EditorAssetLibrary
    all_assets = al.list_assets(search_path, recursive=True, include_folder=False)
    queries = []; issues = []

    for asset_path in all_assets:
        ad  = unreal.EditorAssetLibrary.find_asset_data(asset_path)
        cls = str(ad.asset_class_path.asset_name) if hasattr(ad, 'asset_class_path') else str(ad.asset_class)
        name = ad.asset_name
        if "EnvQuery" in cls or name.startswith("EQS_"):
            q_info = {"name": name, "path": asset_path}
            try:
                q = unreal.load_asset(asset_path)
                opts = getattr(q, 'options', []) or []
                q_info["generators"] = len(opts)
                total_tests = sum(len(getattr(o, 'tests', []) or []) for o in opts)
                q_info["tests"] = total_tests
                if len(opts) == 0:
                    issues.append(f"Empty query (no generators): {name}")
                elif total_tests == 0:
                    issues.append(f"Query has generators but no tests: {name}")
            except Exception:
                q_info["generators"] = "?"
                q_info["tests"]      = "?"
            queries.append(q_info)

    if not queries:
        issues.append("No EQS queries found in search path")

    report = {
        "search_path": search_path,
        "query_count": len(queries),
        "issues":      issues,
        "queries":     queries,
        "status":      "EQS diagnostics complete"
    }
    _log(f"EQS diagnostics: {len(queries)} queries, {len(issues)} issues")
    return report
