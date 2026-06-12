"""
pcg_utils.py — UEOS UE-side PCG utility library (Phase 7)
Run directly from the UE Python console or import as a module.

Quick install:
    import sys, importlib
    sys.path.insert(0, r"C:/UEOS/ue_scripts")
    import pcg_utils as pcg; importlib.reload(pcg)

    # Create a full forest biome + place a PCG Volume:
    pcg.ueos_pcg_quick_setup(
        mesh_paths=["/Game/Meshes/SM_Oak", "/Game/Meshes/SM_Pine"],
        save_path="/Game/PCG",
        location=[0, 0, 0],
        extent=[2000, 2000, 500]
    )
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

def ueos_pcg_quick_setup(
    mesh_paths: list,
    save_path: str = "/Game/PCG",
    biome_name: str = "ForestBiome",
    density: float = 2.0,
    scale_min: float = 0.8,
    scale_max: float = 1.2,
    location: list = None,
    extent: list = None,
) -> dict:
    """
    One-call PCG biome setup:
      1. Create PCG Graph with surface sampler + transform jitter + mesh spawner
      2. Place a PCG Volume in the level

    Returns: dict with graph path and volume actor label.
    """
    import unreal
    try:
        # 1. Create graph
        graph_result = ueos_create_biome_graph(biome_name, save_path, mesh_paths, density, scale_min, scale_max)
        if graph_result.get("status") == "error":
            return graph_result

        # 2. Place volume
        loc = location or [0.0, 0.0, 0.0]
        ext = extent  or [2000.0, 2000.0, 500.0]
        vol_result = ueos_place_pcg_volume(graph_result["path"], loc, ext, f"PCGVol_{biome_name}")
        if vol_result.get("status") == "error":
            return vol_result

        result = _ok({
            "graph_path":   graph_result["path"],
            "volume_actor": vol_result.get("actor"),
            "biome_name":   biome_name,
            "mesh_count":   len(mesh_paths),
        })
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_create_biome_graph(
    name: str,
    save_path: str,
    mesh_paths: list,
    density: float = 2.0,
    scale_min: float = 0.8,
    scale_max: float = 1.2,
) -> dict:
    """Create a PCG Graph configured as a biome (sampler + jitter + mesh spawner)."""
    import unreal
    try:
        factory = unreal.PCGGraphFactory()
        graph = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, save_path, unreal.PCGGraph, factory
        )
        if not graph:
            return _err(f"Failed to create PCGGraph: {name}")

        # Surface sampler
        sampler_node = graph.add_node(unreal.PCGSurfaceSamplerSettings)
        if sampler_node:
            ss = sampler_node.get_settings()
            if ss:
                ss.set_editor_property("points_per_squared_meter", density)
                ss.set_editor_property("seed", 42)

        # Transform jitter
        xform_node = graph.add_node(unreal.PCGTransformPointsSettings)
        if xform_node:
            xs = xform_node.get_settings()
            if xs:
                xs.set_editor_property("rotation_min", unreal.Rotator(0, 0, 0))
                xs.set_editor_property("rotation_max", unreal.Rotator(0, 360, 0))
                xs.set_editor_property("scale_min", unreal.Vector(scale_min, scale_min, scale_min))
                xs.set_editor_property("scale_max", unreal.Vector(scale_max, scale_max, scale_max))
                xs.set_editor_property("uniform_scale", True)

        # Static mesh spawner
        spawn_node = graph.add_node(unreal.PCGStaticMeshSpawnerSettings)
        if spawn_node:
            sps = spawn_node.get_settings()
            if sps:
                entries = []
                for mp in mesh_paths:
                    mesh = unreal.load_asset(mp)
                    if mesh:
                        entry = unreal.PCGSoftISMComponentDescriptor()
                        entry.set_editor_property("static_mesh", mesh)
                        entries.append(entry)
                sps.set_editor_property("mesh_entries", entries)

        unreal.EditorAssetLibrary.save_asset(graph.get_path_name())
        result = _ok({
            "path": graph.get_path_name(),
            "name": name,
            "mesh_count": len(mesh_paths),
            "density": density,
        })
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_create_pcg_graph(name: str, save_path: str) -> dict:
    """Create a blank PCG Graph asset."""
    import unreal
    try:
        factory = unreal.PCGGraphFactory()
        graph = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, save_path, unreal.PCGGraph, factory
        )
        if not graph:
            return _err(f"Failed to create PCGGraph: {name}")
        unreal.EditorAssetLibrary.save_asset(graph.get_path_name())
        result = _ok({"path": graph.get_path_name(), "name": name})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_place_pcg_volume(
    graph_path: str,
    location: list,
    extent: list = None,
    actor_name: str = "PCGVolume",
) -> dict:
    """Place a PCG Volume actor in the level and assign a PCG Graph."""
    import unreal
    try:
        graph = unreal.load_asset(graph_path)
        if not graph:
            return _err(f"PCGGraph not found: {graph_path}")

        ext = extent or [1000.0, 1000.0, 500.0]
        pos = unreal.Vector(location[0], location[1], location[2])
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.PCGVolume, pos, unreal.Rotator(0, 0, 0)
        )
        if not actor:
            return _err("Failed to spawn PCGVolume")
        actor.set_actor_label(actor_name)
        actor.set_actor_scale3d(unreal.Vector(ext[0] / 100, ext[1] / 100, ext[2] / 100))
        pcg_comp = actor.get_component_by_class(unreal.PCGComponent)
        if pcg_comp:
            pcg_comp.set_editor_property("graph", graph)
            pcg_comp.generate(True)
        result = _ok({"actor": actor_name, "graph": graph_path, "location": location, "extent": ext})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_execute_pcg_volume(volume_actor_name: str, cleanup_first: bool = True) -> dict:
    """Force (re)generation of a PCG Volume actor."""
    import unreal
    try:
        actors = {a.get_actor_label(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()}
        actor = actors.get(volume_actor_name)
        if not actor:
            return _err(f"PCGVolume actor not found: {volume_actor_name}")
        pcg_comp = actor.get_component_by_class(unreal.PCGComponent)
        if not pcg_comp:
            return _err("No PCGComponent on actor")
        if cleanup_first:
            pcg_comp.cleanup_local(True, True)
        pcg_comp.generate(True)
        result = _ok({"actor": volume_actor_name, "regenerated": True})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_list_pcg_graphs(search_path: str = "/Game") -> dict:
    """List all PCG Graph assets."""
    import unreal
    try:
        reg = unreal.AssetRegistryHelpers.get_asset_registry()
        assets = reg.get_assets_by_path(search_path, recursive=True)
        graphs = [{"name": str(a.asset_name), "path": str(a.object_path)}
                  for a in assets if "PCGGraph" in str(a.asset_class_path)]
        result = _ok({"pcg_graphs": graphs, "count": len(graphs)})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_list_pcg_volumes() -> dict:
    """List all PCG Volume actors in the current level."""
    import unreal
    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
        volumes = []
        for a in actors:
            if isinstance(a, unreal.PCGVolume):
                pcg_comp = a.get_component_by_class(unreal.PCGComponent)
                graph_name = ""
                if pcg_comp:
                    g = pcg_comp.get_editor_property("graph")
                    if g:
                        graph_name = g.get_name()
                volumes.append({
                    "label":    a.get_actor_label(),
                    "graph":    graph_name,
                    "location": list(a.get_actor_location()),
                })
        result = _ok({"pcg_volumes": volumes, "count": len(volumes)})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_cleanup_pcg_volume(volume_actor_name: str) -> dict:
    """Remove all generated content from a PCG Volume."""
    import unreal
    try:
        actors = {a.get_actor_label(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()}
        actor = actors.get(volume_actor_name)
        if not actor:
            return _err(f"PCGVolume actor not found: {volume_actor_name}")
        pcg_comp = actor.get_component_by_class(unreal.PCGComponent)
        if not pcg_comp:
            return _err("No PCGComponent on actor")
        pcg_comp.cleanup_local(True, True)
        result = _ok({"actor": volume_actor_name, "cleaned_up": True})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_pcg_diagnostics(search_path: str = "/Game") -> dict:
    """Print a full PCG diagnostics report."""
    import unreal
    try:
        reg = unreal.AssetRegistryHelpers.get_asset_registry()
        all_assets = reg.get_assets_by_path(search_path, recursive=True)
        pcg_graphs = sum(1 for a in all_assets if "PCGGraph" in str(a.asset_class_path))
        level_actors = unreal.EditorLevelLibrary.get_all_level_actors()
        pcg_volumes  = sum(1 for a in level_actors if isinstance(a, unreal.PCGVolume))
        result = _ok({
            "pcg_graph_assets":  pcg_graphs,
            "level_pcg_volumes": pcg_volumes,
        })
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))
