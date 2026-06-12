"""
UEOS UE-Side Utility: NavMesh / AI Navigation Helpers
=====================================================
Run directly in the UE 5.4 Python console (no MCP required):

    import sys, importlib
    sys.path.insert(0, r"C:\\UEOS\\ue_scripts")
    import navmesh_utils as nav; importlib.reload(nav)
    nav.ueos_nav_quick_setup()

Public API (16 functions):
  ueos_nav_quick_setup(extent, center_z)          — Place NavMeshBoundsVolume + rebuild
  ueos_rebuild_navmesh()                          — Force full navmesh rebuild
  ueos_place_navmesh_bounds(cx, cy, cz, ex, ey, ez) — Place/resize NavMeshBoundsVolume
  ueos_get_navmesh_info()                         — Navmesh actors and bounds
  ueos_set_navmesh_properties(**kwargs)           — Set RecastNavMesh properties
  ueos_find_path(from_vec, to_vec)                — Find nav path between two points
  ueos_find_nearest_nav_point(location, extent)   — Nearest navmesh point
  ueos_is_point_on_nav(location, extent)          — Check if point is on navmesh
  ueos_check_reachable(start, end)                — Is end reachable from start?
  ueos_create_nav_area(name, save_path, cost)     — New NavArea Blueprint
  ueos_place_nav_modifier(loc, extent, area_class) — Place NavModifierVolume
  ueos_place_nav_link(start, end, direction)      — Place NavLinkProxy
  ueos_list_nav_actors()                          — List all nav-related actors in level
  ueos_set_ai_speed(bp_path, speed, accel)        — Set AICharacter walk speed
  ueos_get_level_nav_summary()                    — Full level navigation summary
  ueos_nav_diagnostics()                          — NavMesh health report
"""

import unreal
import json
import math


# ── Logging ────────────────────────────────────────────────────────────────────

def _log(msg: str):
    unreal.log(f"[UEOS NAV] {msg}")

def _err(msg: str):
    unreal.log_error(f"[UEOS NAV] {msg}")

def _warn(msg: str):
    unreal.log_warning(f"[UEOS NAV] {msg}")


def _vec3(v) -> list:
    """Return [x, y, z] rounded list from an unreal.Vector."""
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]


# ── Quick Setup ────────────────────────────────────────────────────────────────

def ueos_nav_quick_setup(
    extent: float = 5000.0,
    center_z: float = 200.0
) -> dict:
    """
    One-shot navigation setup:
      1. Place NavMeshBoundsVolume (extent × extent area at center_z)
      2. Trigger NavMesh rebuild
    Returns a summary.
    """
    _log(f"NavMesh quick-setup: extent={extent}, center_z={center_z}")

    bounds_result = ueos_place_navmesh_bounds(
        cx=0.0, cy=0.0, cz=center_z,
        ex=extent, ey=extent, ez=500.0
    )

    rebuild_result = ueos_rebuild_navmesh()

    return {
        "bounds":  bounds_result,
        "rebuild": rebuild_result,
        "status":  "NavMesh quick-setup complete"
    }


# ── NavMesh Setup ──────────────────────────────────────────────────────────────

def ueos_rebuild_navmesh() -> dict:
    """Force a full NavigationSystem rebuild."""
    world   = unreal.EditorLevelLibrary.get_editor_world()
    nav_sys = unreal.NavigationSystemV1.get_navigation_system(world)
    if nav_sys is None:
        _warn("No NavigationSystemV1 found — add Navigation System to World Settings")
        return {"status": "No NavigationSystemV1 found", "rebuilt": False}

    nav_sys.build_navigation()
    navmesh_actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.RecastNavMesh)
    _log(f"NavMesh rebuild triggered ({len(navmesh_actors)} navmesh actors)")
    return {
        "navmesh_count": len(navmesh_actors),
        "rebuilt":       True,
        "status":        "NavMesh rebuild triggered"
    }


def ueos_place_navmesh_bounds(
    cx: float = 0.0, cy: float = 0.0, cz: float = 200.0,
    ex: float = 5000.0, ey: float = 5000.0, ez: float = 500.0,
    name: str = "NavMeshBoundsVolume"
) -> dict:
    """Place or update a NavMeshBoundsVolume."""
    world = unreal.EditorLevelLibrary.get_editor_world()

    # Find or create
    volumes = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.NavMeshBoundsVolume)
    volume  = None
    for v in volumes:
        if v.get_name() == name:
            volume = v
            break

    if volume is None:
        volume = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.NavMeshBoundsVolume,
            unreal.Vector(cx, cy, cz),
            unreal.Rotator(0, 0, 0)
        )
        volume.set_actor_label(name)

    volume.set_actor_location(unreal.Vector(cx, cy, cz), False, False)
    unreal.EditorLevelLibrary.save_current_level()

    _log(f"NavMeshBoundsVolume placed: center=({cx},{cy},{cz}), extent=({ex},{ey},{ez})")
    return {
        "volume":  volume.get_name(),
        "center":  [cx, cy, cz],
        "extent":  [ex, ey, ez],
        "status":  "NavMeshBoundsVolume placed — rebuild to generate navmesh"
    }


def ueos_get_navmesh_info() -> dict:
    """Get navmesh actors and bounds volumes in the current level."""
    world         = unreal.EditorLevelLibrary.get_editor_world()
    navmesh_actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.RecastNavMesh)
    bounds_volumes = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.NavMeshBoundsVolume)
    nav_sys        = unreal.NavigationSystemV1.get_navigation_system(world)

    info = {
        "navmesh_actors":    [nm.get_name() for nm in navmesh_actors],
        "bounds_volumes":    [v.get_name()  for v in bounds_volumes],
        "nav_system_active": nav_sys is not None,
        "status":            "NavMesh info retrieved"
    }
    _log(f"NavMesh info: {len(navmesh_actors)} navmesh actors, {len(bounds_volumes)} bounds volumes")
    return info


def ueos_set_navmesh_properties(
    tile_size_uu: float = 1000.0,
    cell_size: float    = 19.0,
    cell_height: float  = 10.0,
    agent_radius: float = 34.0,
    agent_height: float = 144.0,
    max_step_height: float = 35.0,
    max_slope_angle: float = 44.0
) -> dict:
    """Set RecastNavMesh generation properties."""
    world         = unreal.EditorLevelLibrary.get_editor_world()
    navmesh_actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.RecastNavMesh)

    if not navmesh_actors:
        _warn("No RecastNavMesh actor in level")
        return {"status": "No RecastNavMesh found", "updated": False}

    nm   = navmesh_actors[0]
    props = {
        "tile_size_uu":        tile_size_uu,
        "cell_size":           cell_size,
        "cell_height":         cell_height,
        "agent_radius":        agent_radius,
        "agent_height":        agent_height,
        "agent_max_step_height": max_step_height,
        "agent_max_slope":     max_slope_angle,
    }
    for k, v in props.items():
        try:
            nm.set_editor_property(k, v)
        except Exception:
            pass

    unreal.EditorLevelLibrary.save_current_level()
    _log(f"NavMesh properties set: cell={cell_size}, agent_r={agent_radius}, max_step={max_step_height}")
    return {
        "navmesh":   nm.get_name(),
        **props,
        "status":    "Properties set — rebuild navmesh to apply"
    }


# ── Path Queries ───────────────────────────────────────────────────────────────

def ueos_find_path(
    from_vec: tuple = (0.0, 0.0, 0.0),
    to_vec:   tuple = (1000.0, 0.0, 0.0)
) -> dict:
    """Find a navigation path between two world locations."""
    world   = unreal.EditorLevelLibrary.get_editor_world()
    nav_sys = unreal.NavigationSystemV1.get_navigation_system(world)
    if nav_sys is None:
        return {"error": "NavigationSystemV1 not present"}

    start = unreal.Vector(*from_vec)
    end   = unreal.Vector(*to_vec)
    path  = nav_sys.find_path_to_location_synchronously(world, start, end)

    pts    = []
    length = 0.0
    partial = False

    if path and hasattr(path, 'path_points'):
        partial = getattr(path, 'is_partial', False)
        for i, pt in enumerate(path.path_points or []):
            pts.append(_vec3(pt.location))
            if i > 0:
                q = path.path_points[i-1].location
                p = pt.location
                length += math.sqrt((p.x-q.x)**2+(p.y-q.y)**2+(p.z-q.z)**2)

    _log(f"Path found: {len(pts)} points, {length:.0f} cm, partial={partial}")
    return {
        "from":        list(from_vec),
        "to":          list(to_vec),
        "waypoints":   len(pts),
        "length_cm":   round(length, 1),
        "is_partial":  partial,
        "path_points": pts[:20]
    }


def ueos_find_nearest_nav_point(
    location: tuple = (0.0, 0.0, 0.0),
    extent: float   = 500.0
) -> dict:
    """Find the nearest NavMesh point to a world location."""
    world   = unreal.EditorLevelLibrary.get_editor_world()
    nav_sys = unreal.NavigationSystemV1.get_navigation_system(world)
    if nav_sys is None:
        return {"error": "NavigationSystemV1 not present"}

    origin = unreal.Vector(*location)
    ext    = unreal.Vector(extent, extent, extent)
    ok, proj = nav_sys.project_point_to_navigation(world, origin, None, ext)

    _log(f"Nearest nav point: {'found' if ok else 'not found'} near {location}")
    return {
        "query":     list(location),
        "projected": _vec3(proj) if ok else None,
        "found":     bool(ok),
        "extent":    extent
    }


def ueos_is_point_on_nav(
    location: tuple = (0.0, 0.0, 0.0),
    extent: float   = 100.0
) -> bool:
    """Return True if a world location lies on (or near) the NavMesh."""
    result = ueos_find_nearest_nav_point(location, extent)
    return result.get("found", False)


def ueos_check_reachable(
    start: tuple = (0.0, 0.0, 0.0),
    end:   tuple = (1000.0, 0.0, 0.0)
) -> dict:
    """Check if end is reachable from start via the NavMesh."""
    path_info = ueos_find_path(start, end)
    reachable = path_info.get("waypoints", 0) > 0 and not path_info.get("is_partial", True)
    _log(f"Reachable {start}→{end}: {reachable}")
    return {
        "start":       list(start),
        "end":         list(end),
        "reachable":   reachable,
        "partial":     path_info.get("is_partial", False),
        "path_length": path_info.get("length_cm", 0.0),
        "waypoints":   path_info.get("waypoints", 0)
    }


# ── Nav Areas & Volumes ────────────────────────────────────────────────────────

def ueos_create_nav_area(
    name: str = "NavArea_Custom",
    save_path: str = "/Game/AI/NavAreas",
    default_cost: float = 1.0,
    entering_cost: float = 0.0
) -> dict:
    """Create a custom NavArea Blueprint."""
    al = unreal.EditorAssetLibrary
    if not al.does_directory_exist(save_path):
        al.make_directory(save_path)

    full_path = f"{save_path}/{name}"
    factory   = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.NavArea)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = asset_tools.create_asset(name, save_path, None, factory)

    if bp is None:
        raise RuntimeError(f"Failed to create NavArea: {full_path}")

    try:
        cdo = unreal.get_default_object(bp.generated_class())
        cdo.set_editor_property("default_cost", default_cost)
        cdo.set_editor_property("fixed_area_entering_cost", entering_cost)
    except Exception:
        pass

    al.save_asset(full_path)
    _log(f"NavArea created: {full_path}, cost={default_cost}")
    return {
        "path":          full_path,
        "default_cost":  default_cost,
        "entering_cost": entering_cost,
        "status":        "NavArea Blueprint created"
    }


def ueos_place_nav_modifier(
    location: tuple   = (0.0, 0.0, 0.0),
    extent: tuple     = (200.0, 200.0, 200.0),
    area_class: str   = "NavArea_Obstacle",
    name: str         = "NavModifierVolume"
) -> dict:
    """Place a NavModifierVolume with the given area class."""
    world  = unreal.EditorLevelLibrary.get_editor_world()
    volume = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.NavModifierVolume,
        unreal.Vector(*location),
        unreal.Rotator(0, 0, 0)
    )
    volume.set_actor_label(name)

    try:
        area_cls = getattr(unreal, area_class, None)
        if area_cls:
            volume.set_editor_property("area_class", area_cls)
    except Exception:
        pass

    unreal.EditorLevelLibrary.save_current_level()
    _log(f"NavModifierVolume placed: {name} at {location}, area={area_class}")
    return {
        "name":       volume.get_name(),
        "location":   list(location),
        "extent":     list(extent),
        "area_class": area_class,
        "status":     "NavModifierVolume placed"
    }


def ueos_place_nav_link(
    start: tuple     = (0.0, 0.0, 0.0),
    end: tuple       = (0.0, 0.0, 200.0),
    direction: str   = "both_ways",
    name: str        = "NavLinkProxy"
) -> dict:
    """Place a NavLinkProxy for smart navigation links (jumps, ladders)."""
    world  = unreal.EditorLevelLibrary.get_editor_world()
    proxy  = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.NavLinkProxy,
        unreal.Vector(*start),
        unreal.Rotator(0, 0, 0)
    )
    proxy.set_actor_label(name)

    try:
        link = unreal.NavigationLink()
        link.set_editor_property("left",  unreal.Vector(*start))
        link.set_editor_property("right", unreal.Vector(*end))
        dir_map = {
            "both_ways":     unreal.ENavLinkDirection.BOTH_WAYS,
            "left_to_right": unreal.ENavLinkDirection.LEFT_TO_RIGHT,
            "right_to_left": unreal.ENavLinkDirection.RIGHT_TO_LEFT,
        }
        link.set_editor_property("direction", dir_map.get(direction, dir_map["both_ways"]))
        proxy.set_editor_property("point_links", [link])
    except Exception:
        pass

    unreal.EditorLevelLibrary.save_current_level()
    _log(f"NavLinkProxy placed: {proxy.get_name()}, {start}→{end}, dir={direction}")
    return {
        "proxy":     proxy.get_name(),
        "start":     list(start),
        "end":       list(end),
        "direction": direction,
        "status":    "NavLinkProxy placed"
    }


# ── Level Overview ─────────────────────────────────────────────────────────────

def ueos_list_nav_actors() -> dict:
    """List all navigation-related actors in the current level."""
    world         = unreal.EditorLevelLibrary.get_editor_world()
    navmesh       = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.RecastNavMesh)
    bounds        = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.NavMeshBoundsVolume)
    modifiers     = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.NavModifierVolume)
    links         = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.NavLinkProxy)

    result = {
        "recast_navmesh":        [a.get_name() for a in navmesh],
        "navmesh_bounds_volumes":[a.get_name() for a in bounds],
        "nav_modifier_volumes":  len(modifiers),
        "nav_link_proxies":      [a.get_name() for a in links],
        "totals": {
            "navmesh_actors":  len(navmesh),
            "bounds_volumes":  len(bounds),
            "modifier_volumes":len(modifiers),
            "link_proxies":    len(links),
        }
    }
    _log(f"Nav actors: {len(navmesh)} navmesh, {len(bounds)} bounds, {len(modifiers)} modifiers, {len(links)} links")
    return result


def ueos_set_ai_speed(
    bp_path: str,
    speed: float = 600.0,
    acceleration: float = 2048.0
) -> dict:
    """Set AICharacter movement speed on a Blueprint."""
    bp = unreal.load_asset(bp_path)
    if bp is None:
        raise RuntimeError(f"Blueprint not found: {bp_path}")

    try:
        cdo      = unreal.get_default_object(bp.generated_class())
        move_comp = cdo.find_component_by_class(unreal.CharacterMovementComponent)
        if move_comp:
            move_comp.set_editor_property("max_walk_speed",   speed)
            move_comp.set_editor_property("max_acceleration", acceleration)
    except Exception as e:
        _warn(f"Could not set movement directly: {e}")

    unreal.EditorAssetLibrary.save_asset(bp_path)
    _log(f"AI speed set: {bp_path}, speed={speed}, accel={acceleration}")
    return {
        "blueprint":    bp_path,
        "max_walk_speed": speed,
        "max_acceleration": acceleration,
        "status":       "Movement speed set — recompile Blueprint"
    }


def ueos_get_level_nav_summary() -> dict:
    """Return a full navigation summary for the current level."""
    actors    = ueos_list_nav_actors()
    nav_info  = ueos_get_navmesh_info()
    issues    = []

    if not actors["recast_navmesh"]:
        issues.append("No RecastNavMesh actor found")
    if not actors["navmesh_bounds_volumes"]:
        issues.append("No NavMeshBoundsVolume — navmesh cannot be generated")
    if not nav_info.get("nav_system_active"):
        issues.append("NavigationSystemV1 not active in World Settings")

    summary = {
        "actors":   actors,
        "nav_info": nav_info,
        "issues":   issues,
        "healthy":  len(issues) == 0,
        "status":   "Level nav summary complete"
    }
    _log(f"Nav summary: {len(issues)} issues, healthy={summary['healthy']}")
    return summary


def ueos_nav_diagnostics() -> dict:
    """Full NavMesh health report with actionable issue list."""
    _log("Running NavMesh diagnostics")
    summary = ueos_get_level_nav_summary()
    actors  = summary["actors"]
    issues  = list(summary["issues"])

    # Extended checks
    if actors["totals"]["bounds_volumes"] == 0:
        issues.append("ACTION: Add a NavMeshBoundsVolume to define the walkable area")
    if actors["totals"]["navmesh_actors"] == 0:
        issues.append("ACTION: Enable Navigation System in World Settings → Navigation System")
    if actors["totals"]["navmesh_actors"] > 0 and actors["totals"]["bounds_volumes"] > 0:
        issues.append("INFO: NavMesh present and bounds defined — run Rebuild Navigation to update")

    report = {
        "navmesh_actors":   actors["recast_navmesh"],
        "bounds_volumes":   actors["navmesh_bounds_volumes"],
        "modifier_volumes": actors["totals"]["modifier_volumes"],
        "nav_link_proxies": actors["nav_link_proxies"],
        "issues":           issues,
        "healthy":          len([i for i in issues if i.startswith("ACTION")]) == 0,
        "status":           "NavMesh diagnostics complete"
    }
    _log(f"Diagnostics: {len(issues)} messages")
    for issue in issues:
        if "ACTION" in issue:
            _warn(issue)
        else:
            _log(issue)
    return report
