"""
chaos_utils.py — UEOS UE-side Chaos Physics utility library (Phase 7)
Run directly from the UE Python console or import as a module.

Quick install:
    import sys, importlib
    sys.path.insert(0, r"C:/UEOS/ue_scripts")
    import chaos_utils as chaos; importlib.reload(chaos)

    # Full Chaos destruction setup in one call:
    chaos.ueos_chaos_quick_setup("/Game/Meshes/SM_Wall", "/Game/Chaos")
"""

from __future__ import annotations
import json


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ok(data: dict) -> dict:
    data.setdefault("status", "ok")
    return data

def _err(msg: str) -> dict:
    return {"status": "error", "message": str(msg)}

def _log(data: dict) -> None:
    print(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ueos_chaos_quick_setup(
    static_mesh_path: str,
    save_path: str = "/Game/Chaos",
    fracture_type: str = "voronoi",
    cell_count: int = 20,
    place_in_level: bool = True,
    location: list = None,
) -> dict:
    """
    One-call Chaos destruction setup:
      1. Create Geometry Collection from Static Mesh
      2. Apply fracturing (voronoi / clustered / slice)
      3. Set default damage thresholds
      4. Optionally place actor in level

    Returns: dict with paths of created assets and actor label.
    """
    import unreal
    try:
        mesh = unreal.load_asset(static_mesh_path)
        if not mesh:
            return _err(f"Static Mesh not found: {static_mesh_path}")

        mesh_name = mesh.get_name()
        gc_name   = f"GC_{mesh_name}"
        gc_path   = f"{save_path}/{gc_name}"

        # 1. Create Geometry Collection
        factory = unreal.GeometryCollectionFactory()
        gc = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            gc_name, save_path, unreal.GeometryCollection, factory
        )
        if not gc:
            return _err(f"Failed to create GeometryCollection for {static_mesh_path}")

        conv = unreal.GeometryCollectionEngineConversion()
        conv.append_static_mesh(gc, mesh, unreal.Transform())

        # 2. Fracture
        if fracture_type == "voronoi":
            settings = unreal.VoronoiFractureSettings()
            settings.set_editor_property("number_of_voronoi_sites", cell_count)
            settings.set_editor_property("random_seed", 42)
            cmd = unreal.GeometryCollectionCommandPlugin()
            cmd.voronoi_fracture([gc], settings, [unreal.Transform()], False)
        elif fracture_type == "clustered":
            settings = unreal.ClusteredVoronoiFractureSettings()
            settings.set_editor_property("number_of_clusters", max(cell_count // 4, 2))
            settings.set_editor_property("sites_per_cluster", 6)
            cmd = unreal.GeometryCollectionCommandPlugin()
            cmd.clustered_voronoi_fracture([gc], settings, [unreal.Transform()], False)
        elif fracture_type == "slice":
            settings = unreal.PlaneCutFractureSettings()
            settings.set_editor_property("grid_x", 2)
            settings.set_editor_property("grid_y", 2)
            settings.set_editor_property("grid_z", 2)
            cmd = unreal.GeometryCollectionCommandPlugin()
            cmd.plane_cut_fracture([gc], settings, [unreal.Transform()], False)

        # 3. Default damage thresholds
        gc.set_editor_property("damage_threshold", [500.0, 250.0, 100.0])
        unreal.EditorAssetLibrary.save_asset(gc.get_path_name())

        actor_label = None
        # 4. Optionally place in level
        if place_in_level:
            loc = location or [0.0, 0.0, 200.0]
            pos = unreal.Vector(loc[0], loc[1], loc[2])
            actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
                unreal.GeometryCollectionActor, pos, unreal.Rotator(0, 0, 0)
            )
            if actor:
                actor.set_actor_label(f"Dest_{mesh_name}")
                gc_comp = actor.get_component_by_class(unreal.GeometryCollectionComponent)
                if gc_comp:
                    gc_comp.set_chao_rest_collection(gc)
                    gc_comp.set_editor_property("simulate_physics", True)
                actor_label = actor.get_actor_label()

        result = _ok({
            "gc_path":      gc.get_path_name(),
            "fracture_type": fracture_type,
            "cell_count":   cell_count,
            "actor_label":  actor_label,
        })
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_create_geometry_collection(
    static_mesh_path: str,
    save_path: str,
    name: str = None,
) -> dict:
    """Create a Geometry Collection asset from a Static Mesh."""
    import unreal
    try:
        mesh = unreal.load_asset(static_mesh_path)
        if not mesh:
            return _err(f"Static Mesh not found: {static_mesh_path}")
        gc_name = name or f"GC_{mesh.get_name()}"
        factory = unreal.GeometryCollectionFactory()
        gc = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            gc_name, save_path, unreal.GeometryCollection, factory
        )
        if not gc:
            return _err("Failed to create GeometryCollection")
        conv = unreal.GeometryCollectionEngineConversion()
        conv.append_static_mesh(gc, mesh, unreal.Transform())
        unreal.EditorAssetLibrary.save_asset(gc.get_path_name())
        result = _ok({"path": gc.get_path_name(), "name": gc_name})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_fracture_voronoi(gc_path: str, cell_count: int = 20, seed: int = 42) -> dict:
    """Apply Voronoi fracturing to a Geometry Collection."""
    import unreal
    try:
        gc = unreal.load_asset(gc_path)
        if not gc:
            return _err(f"GC not found: {gc_path}")
        settings = unreal.VoronoiFractureSettings()
        settings.set_editor_property("number_of_voronoi_sites", cell_count)
        settings.set_editor_property("random_seed", seed)
        cmd = unreal.GeometryCollectionCommandPlugin()
        cmd.voronoi_fracture([gc], settings, [unreal.Transform()], False)
        unreal.EditorAssetLibrary.save_asset(gc_path)
        result = _ok({"gc_path": gc_path, "cell_count": cell_count, "seed": seed})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_fracture_clustered(
    gc_path: str,
    cluster_count: int = 4,
    cells_per_cluster: int = 8,
) -> dict:
    """Apply clustered Voronoi fracturing."""
    import unreal
    try:
        gc = unreal.load_asset(gc_path)
        if not gc:
            return _err(f"GC not found: {gc_path}")
        settings = unreal.ClusteredVoronoiFractureSettings()
        settings.set_editor_property("number_of_clusters", cluster_count)
        settings.set_editor_property("sites_per_cluster", cells_per_cluster)
        settings.set_editor_property("number_of_cluster_sites", cluster_count)
        cmd = unreal.GeometryCollectionCommandPlugin()
        cmd.clustered_voronoi_fracture([gc], settings, [unreal.Transform()], False)
        unreal.EditorAssetLibrary.save_asset(gc_path)
        result = _ok({"gc_path": gc_path, "clusters": cluster_count, "cells_per_cluster": cells_per_cluster})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_fracture_slice(
    gc_path: str,
    slices_x: int = 2,
    slices_y: int = 2,
    slices_z: int = 2,
) -> dict:
    """Apply planar-slice fracturing."""
    import unreal
    try:
        gc = unreal.load_asset(gc_path)
        if not gc:
            return _err(f"GC not found: {gc_path}")
        settings = unreal.PlaneCutFractureSettings()
        settings.set_editor_property("grid_x", slices_x)
        settings.set_editor_property("grid_y", slices_y)
        settings.set_editor_property("grid_z", slices_z)
        cmd = unreal.GeometryCollectionCommandPlugin()
        cmd.plane_cut_fracture([gc], settings, [unreal.Transform()], False)
        unreal.EditorAssetLibrary.save_asset(gc_path)
        result = _ok({"gc_path": gc_path, "slices": [slices_x, slices_y, slices_z]})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_set_damage_thresholds(gc_path: str, thresholds: list) -> dict:
    """Set damage thresholds on a Geometry Collection."""
    import unreal
    try:
        gc = unreal.load_asset(gc_path)
        if not gc:
            return _err(f"GC not found: {gc_path}")
        gc.set_editor_property("damage_threshold", thresholds)
        unreal.EditorAssetLibrary.save_asset(gc_path)
        result = _ok({"gc_path": gc_path, "thresholds": thresholds})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_create_physics_material(
    name: str,
    save_path: str,
    friction: float = 0.7,
    restitution: float = 0.3,
    density: float = 1.0,
) -> dict:
    """Create a Physics Material asset."""
    import unreal
    try:
        factory = unreal.PhysicalMaterialFactory()
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, save_path, unreal.PhysicalMaterial, factory
        )
        if not mat:
            return _err("Failed to create PhysicalMaterial")
        mat.set_editor_property("friction", friction)
        mat.set_editor_property("restitution", restitution)
        mat.set_editor_property("density", density)
        unreal.EditorAssetLibrary.save_asset(mat.get_path_name())
        result = _ok({"path": mat.get_path_name(), "friction": friction, "restitution": restitution, "density": density})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_create_constraint(
    actor_a: str,
    actor_b: str,
    location: list = None,
    linear_locked: bool = True,
    angular_free: bool = True,
    actor_name: str = "PhysConstraint",
) -> dict:
    """Place a Physics Constraint Actor between two level actors."""
    import unreal
    try:
        loc = location or [0.0, 0.0, 0.0]
        actors = {a.get_actor_label(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()}
        a_obj = actors.get(actor_a)
        b_obj = actors.get(actor_b)
        ca = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.PhysicsConstraintActor,
            unreal.Vector(loc[0], loc[1], loc[2]),
            unreal.Rotator(0, 0, 0)
        )
        if not ca:
            return _err("Failed to spawn PhysicsConstraintActor")
        ca.set_actor_label(actor_name)
        comp = ca.get_component_by_class(unreal.PhysicsConstraintComponent)
        if comp:
            if linear_locked:
                comp.constraint_instance.set_linear_x_motion(unreal.ConstraintMotion.LOCKED)
                comp.constraint_instance.set_linear_y_motion(unreal.ConstraintMotion.LOCKED)
                comp.constraint_instance.set_linear_z_motion(unreal.ConstraintMotion.LOCKED)
            if angular_free:
                comp.constraint_instance.set_angular_swing1_motion(unreal.ConstraintMotion.FREE)
                comp.constraint_instance.set_angular_swing2_motion(unreal.ConstraintMotion.FREE)
                comp.constraint_instance.set_angular_twist_motion(unreal.ConstraintMotion.FREE)
        result = _ok({"constraint": actor_name, "actor_a": actor_a, "actor_b": actor_b})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_apply_radial_impulse(
    location: list,
    radius: float = 500.0,
    strength: float = 1000.0,
    actor_name: str = "RadialImpulse",
) -> dict:
    """Spawn a RadialForceActor and fire an impulse."""
    import unreal
    try:
        pos = unreal.Vector(location[0], location[1], location[2])
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.RadialForceActor, pos, unreal.Rotator(0, 0, 0)
        )
        if not actor:
            return _err("Failed to spawn RadialForceActor")
        actor.set_actor_label(actor_name)
        comp = actor.get_component_by_class(unreal.RadialForceComponent)
        if comp:
            comp.set_editor_property("radius", radius)
            comp.set_editor_property("impulse_strength", strength)
            comp.fire_impulse()
        result = _ok({"actor": actor_name, "location": location, "radius": radius, "strength": strength})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_enable_actor_physics(
    actor_name: str,
    simulate: bool = True,
    mass_kg: float = 0.0,
) -> dict:
    """Enable/disable physics simulation on an actor."""
    import unreal
    try:
        actors = {a.get_actor_label(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()}
        actor = actors.get(actor_name)
        if not actor:
            return _err(f"Actor not found: {actor_name}")
        root = actor.get_component_by_class(unreal.PrimitiveComponent)
        if not root:
            return _err("No PrimitiveComponent on actor")
        root.set_simulate_physics(simulate)
        if mass_kg > 0:
            root.set_editor_property("mass_override_in_kg", mass_kg)
            root.set_editor_property("override_mass", True)
        result = _ok({"actor": actor_name, "simulate": simulate, "mass_kg": mass_kg})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_list_chaos_actors() -> dict:
    """List all Chaos/physics-related actors in the current level."""
    import unreal
    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
        gc_actors = [a.get_actor_label() for a in actors if isinstance(a, unreal.GeometryCollectionActor)]
        rf_actors = [a.get_actor_label() for a in actors if isinstance(a, unreal.RadialForceActor)]
        pc_actors = [a.get_actor_label() for a in actors if isinstance(a, unreal.PhysicsConstraintActor)]
        result = _ok({
            "geometry_collection_actors": gc_actors,
            "radial_force_actors":        rf_actors,
            "constraint_actors":          pc_actors,
        })
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_list_geometry_collections(search_path: str = "/Game") -> dict:
    """List all Geometry Collection assets."""
    import unreal
    try:
        reg = unreal.AssetRegistryHelpers.get_asset_registry()
        assets = reg.get_assets_by_path(search_path, recursive=True)
        gcs = [{"name": str(a.asset_name), "path": str(a.object_path)}
               for a in assets if "GeometryCollection" in str(a.asset_class_path)]
        result = _ok({"geometry_collections": gcs, "count": len(gcs)})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_get_gc_info(gc_path: str) -> dict:
    """Return info about a Geometry Collection asset."""
    import unreal
    try:
        gc = unreal.load_asset(gc_path)
        if not gc:
            return _err(f"GC not found: {gc_path}")
        result = _ok({
            "path": gc_path,
            "damage_threshold": list(gc.get_editor_property("damage_threshold") or []),
            "cluster_connection_type": str(gc.get_editor_property("cluster_connection_type")),
        })
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_chaos_diagnostics(search_path: str = "/Game") -> dict:
    """Print a full Chaos diagnostics report."""
    import unreal
    try:
        reg = unreal.AssetRegistryHelpers.get_asset_registry()
        all_assets = reg.get_assets_by_path(search_path, recursive=True)
        gc_count = sum(1 for a in all_assets if "GeometryCollection" in str(a.asset_class_path))
        pm_count = sum(1 for a in all_assets if "PhysicalMaterial"   in str(a.asset_class_path))
        actors   = unreal.EditorLevelLibrary.get_all_level_actors()
        result = _ok({
            "gc_assets":        gc_count,
            "physics_materials": pm_count,
            "gc_level_actors":  sum(1 for a in actors if isinstance(a, unreal.GeometryCollectionActor)),
            "rf_level_actors":  sum(1 for a in actors if isinstance(a, unreal.RadialForceActor)),
            "pc_level_actors":  sum(1 for a in actors if isinstance(a, unreal.PhysicsConstraintActor)),
        })
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))
