"""
UEOS Utility Library — runs INSIDE Unreal Engine 5.4 Python environment.

This file is meant to be exec()'d or run via Remote Control, NOT imported
from the MCP server side. It provides shared helpers for all UEOS tool scripts.

Usage from a tool script:
    exec(open(r"C:/UEOS/ue_scripts/ueos_utils.py").read())
    asset = ueos_load("/Game/Characters/Hero")

Or embed in a Remote Control execute_python call:
    script = open("ue_scripts/ueos_utils.py").read() + "\\n" + your_script
"""

import unreal
import json
import traceback


# ─────────────────────────────────────────────────────────────────────────────
# Output helpers
# ─────────────────────────────────────────────────────────────────────────────

def ueos_result(data):
    """Print a UEOS_RESULT: line that the MCP server will parse."""
    if not isinstance(data, str):
        data = json.dumps(data)
    print("UEOS_RESULT:" + data)

def ueos_error(msg):
    """Print a UEOS_ERROR: line that the MCP server will parse."""
    print("UEOS_ERROR:" + str(msg))

def ueos_info(data):
    """Print a UEOS_INFO: line for logging/diagnostics."""
    if not isinstance(data, str):
        data = json.dumps(data)
    print("UEOS_INFO:" + data)

def ueos_warn(msg):
    """Print a UEOS_WARN: line."""
    print("UEOS_WARN:" + str(msg))


# ─────────────────────────────────────────────────────────────────────────────
# Asset helpers
# ─────────────────────────────────────────────────────────────────────────────

def ueos_load(asset_path: str):
    """Load any UE asset by content path. Returns None on failure."""
    return unreal.EditorAssetLibrary.load_asset(asset_path)

def ueos_save(asset_path: str, only_dirty: bool = False) -> bool:
    """Save a UE asset. Returns True on success."""
    return unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=only_dirty)

def ueos_save_obj(obj) -> bool:
    """Save a loaded UObject (asset)."""
    if obj is None:
        return False
    return unreal.EditorAssetLibrary.save_asset(obj.get_path_name(), only_if_is_dirty=False)

def ueos_exists(asset_path: str) -> bool:
    """Check if a content-browser asset exists."""
    return unreal.EditorAssetLibrary.does_asset_exist(asset_path)

def ueos_ensure_path(content_path: str) -> bool:
    """Create a content-browser folder if it doesn't exist."""
    return unreal.EditorAssetLibrary.make_directory(content_path)

def ueos_delete(asset_path: str) -> bool:
    """Delete an asset. Returns True on success."""
    return unreal.EditorAssetLibrary.delete_asset(asset_path)

def ueos_rename(source: str, dest: str) -> bool:
    """Rename/move an asset in the content browser."""
    return unreal.EditorAssetLibrary.rename_asset(source, dest)

def ueos_duplicate(source: str, dest_path: str, dest_name: str):
    """Duplicate an asset to a new path/name."""
    return unreal.EditorAssetLibrary.duplicate_asset(source, dest_path, dest_name)

def ueos_asset_info(asset_path: str) -> dict:
    """Get metadata for any asset."""
    asset = ueos_load(asset_path)
    if asset is None:
        return {}
    return {
        "name":    asset.get_name(),
        "path":    asset.get_path_name(),
        "class":   asset.get_class().get_name(),
        "package": str(unreal.SystemLibrary.get_object_name(asset))
    }

def ueos_find_assets(search_path: str = "/Game", class_name: str = None, recursive: bool = True) -> list:
    """Find assets in a path, optionally filtered by class name."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    if class_name:
        assets = registry.get_assets_by_class(
            unreal.TopLevelAssetPath("/Script/Engine", class_name), True
        )
    else:
        assets = registry.get_assets_by_path(search_path, recursive=recursive)
    return [
        {
            "name":    str(a.asset_name),
            "path":    str(a.object_path),
            "class":   str(a.asset_class_path.asset_name),
            "package": str(a.package_name)
        }
        for a in assets
        if str(a.object_path).startswith(search_path)
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Blueprint helpers
# ─────────────────────────────────────────────────────────────────────────────

def ueos_create_blueprint(name: str, path: str, parent_class_path: str = "/Script/Engine.Actor"):
    """Create a Blueprint asset. Returns the Blueprint object or None."""
    parent = unreal.load_class(None, parent_class_path)
    if parent is None:
        ueos_error(f"Parent class not found: {parent_class_path}")
        return None
    factory = unreal.BlueprintFactory()
    factory.parent_class = parent
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = asset_tools.create_asset(name, path, unreal.Blueprint, factory)
    return bp

def ueos_compile_bp(bp) -> bool:
    """Compile a Blueprint. Returns True on success."""
    if bp is None:
        return False
    return unreal.KismetEditorUtilities.compile_blueprint(bp)

def ueos_get_bp_graph(bp, graph_name: str = "EventGraph"):
    """Get a named graph from a Blueprint."""
    graphs = unreal.BlueprintEditorLibrary.get_blueprint_graphs(bp)
    for g in graphs:
        if g.get_name() == graph_name:
            return g
    return None

def ueos_add_component_to_bp(bp, component_class_path: str, comp_name: str = None):
    """Add a component to a Blueprint's component list."""
    comp_class = unreal.load_class(None, component_class_path)
    if comp_class is None:
        ueos_error(f"Component class not found: {component_class_path}")
        return None
    return unreal.BlueprintEditorLibrary.add_component(bp, comp_class, comp_name or comp_class.get_name())


# ─────────────────────────────────────────────────────────────────────────────
# Material helpers
# ─────────────────────────────────────────────────────────────────────────────

def ueos_create_material(name: str, path: str):
    """Create a new Material asset."""
    factory = unreal.MaterialFactoryNew()
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    return asset_tools.create_asset(name, path, unreal.Material, factory)

def ueos_add_node(mat, expr_class_name: str, x: int, y: int):
    """Add a material expression node by class name string."""
    mel = unreal.MaterialEditingLibrary
    expr_class_str = expr_class_name if expr_class_name.startswith("unreal.") else None
    if expr_class_str:
        expr_class = getattr(unreal, expr_class_name, None)
    else:
        expr_class = unreal.load_class(None, f"/Script/Engine.{expr_class_name}")
    if expr_class is None:
        ueos_error(f"Material expression class not found: {expr_class_name}")
        return None
    return mel.create_material_expression(mat, expr_class, x, y)

def ueos_connect(from_node, from_pin: str, to_node, to_pin: str):
    """Connect two material expression nodes."""
    unreal.MaterialEditingLibrary.connect_material_expressions(
        from_node, from_pin, to_node, to_pin
    )

def ueos_connect_property(node, pin: str, prop: unreal.MaterialProperty):
    """Connect a material node to an output property."""
    unreal.MaterialEditingLibrary.connect_material_property(node, pin, prop)

def ueos_recompile_material(mat):
    """Recompile and save a material."""
    unreal.MaterialEditingLibrary.recompile_material(mat)
    ueos_save_obj(mat)


# ─────────────────────────────────────────────────────────────────────────────
# Actor / level helpers
# ─────────────────────────────────────────────────────────────────────────────

def ueos_spawn_actor(class_path: str, location=(0,0,0), rotation=(0,0,0), name: str = None):
    """Spawn an actor in the current level."""
    actor_class = unreal.load_class(None, class_path)
    if actor_class is None:
        ueos_error(f"Actor class not found: {class_path}")
        return None
    loc = unreal.Vector(*location)
    rot = unreal.Rotator(*rotation)
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(actor_class, loc, rot)
    if actor and name:
        actor.set_actor_label(name)
    return actor

def ueos_find_actor(label: str):
    """Find an actor in the current level by label."""
    for a in unreal.EditorLevelLibrary.get_all_level_actors():
        if a.get_actor_label() == label:
            return a
    return None

def ueos_delete_actor(label: str) -> bool:
    """Delete an actor from the level by label."""
    actor = ueos_find_actor(label)
    if actor:
        return unreal.EditorLevelLibrary.destroy_actor(actor)
    return False

def ueos_set_actor_transform(label: str, location=None, rotation=None, scale=None) -> bool:
    """Set an actor's location/rotation/scale."""
    actor = ueos_find_actor(label)
    if actor is None:
        ueos_error(f"Actor not found: {label}")
        return False
    if location:
        actor.set_actor_location(unreal.Vector(*location), False, False)
    if rotation:
        actor.set_actor_rotation(unreal.Rotator(*rotation), False)
    if scale:
        actor.set_actor_scale3d(unreal.Vector(*scale))
    return True

def ueos_get_all_actors() -> list:
    """Get all actors in the current level as dicts."""
    actors = unreal.EditorLevelLibrary.get_all_level_actors()
    result = []
    for a in actors:
        loc = a.get_actor_location()
        rot = a.get_actor_rotation()
        result.append({
            "label":    a.get_actor_label(),
            "class":    a.get_class().get_name(),
            "location": [loc.x, loc.y, loc.z],
            "rotation": [rot.pitch, rot.yaw, rot.roll]
        })
    return result

def ueos_get_selected_actors() -> list:
    """Get the current editor selection as a list of dicts."""
    selected = unreal.EditorLevelLibrary.get_selected_level_actors()
    result = []
    for a in selected:
        loc = a.get_actor_location()
        result.append({
            "label":    a.get_actor_label(),
            "class":    a.get_class().get_name(),
            "location": [loc.x, loc.y, loc.z]
        })
    return result

def ueos_save_level():
    """Save the current level."""
    return unreal.EditorLevelLibrary.save_current_level()


# ─────────────────────────────────────────────────────────────────────────────
# Import helpers
# ─────────────────────────────────────────────────────────────────────────────

def ueos_import_fbx(
    fbx_path:       str,
    dest_path:      str,
    as_skeletal:    bool = False,
    combine_meshes: bool = True,
    import_textures: bool = True,
    import_materials: bool = True
) -> list:
    """Import an FBX file into UE. Returns list of imported asset paths."""
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    task = unreal.AssetImportTask()
    task.filename         = fbx_path
    task.destination_path = dest_path
    task.automated        = True
    task.replace_existing = True
    task.save             = True

    opts = unreal.FbxImportUI()
    opts.import_mesh      = True
    opts.import_textures  = import_textures
    opts.import_materials = import_materials
    opts.import_as_skeletal = as_skeletal
    opts.static_mesh_import_data.combine_meshes = combine_meshes
    task.options = opts

    asset_tools.import_asset_tasks([task])
    return task.imported_object_paths or []

def ueos_import_texture(img_path: str, dest_path: str) -> list:
    """Import a PNG/JPG/TGA texture into UE."""
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    task = unreal.AssetImportTask()
    task.filename         = img_path
    task.destination_path = dest_path
    task.automated        = True
    task.replace_existing = True
    task.save             = True
    asset_tools.import_asset_tasks([task])
    return task.imported_object_paths or []


# ─────────────────────────────────────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────────────────────────────────────

def ueos_get_datatable_rows(table_path: str) -> list:
    """Get all rows from a DataTable as a list of dicts."""
    table = ueos_load(table_path)
    if table is None or not isinstance(table, unreal.DataTable):
        return []
    json_str = unreal.DataTableFunctionLibrary.conv_data_table_to_json_string(table)
    return json.loads(json_str) if json_str else []

def ueos_get_datatable_row_names(table_path: str) -> list:
    """Get all row name strings from a DataTable."""
    table = ueos_load(table_path)
    if table is None or not isinstance(table, unreal.DataTable):
        return []
    return [str(n) for n in unreal.DataTableFunctionLibrary.get_data_table_row_names(table)]


# ─────────────────────────────────────────────────────────────────────────────
# Diagnostic / project helpers
# ─────────────────────────────────────────────────────────────────────────────

def ueos_project_info() -> dict:
    """Return engine version, project name, paths."""
    return {
        "engine_version": str(unreal.SystemLibrary.get_engine_version()),
        "project_name":   unreal.Paths.get_project_file_path().split("/")[-1].replace(".uproject",""),
        "project_dir":    unreal.Paths.project_dir(),
        "content_dir":    unreal.Paths.project_content_dir(),
        "platform":       str(unreal.SystemLibrary.get_platform_name()),
    }

def ueos_asset_count(search_path: str = "/Game") -> dict:
    """Count assets by class under search_path."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    assets = registry.get_assets_by_path(search_path, recursive=True)
    counts = {}
    for a in assets:
        cls = str(a.asset_class_path.asset_name)
        counts[cls] = counts.get(cls, 0) + 1
    return {
        "total":    len(assets),
        "by_class": dict(sorted(counts.items(), key=lambda x: -x[1])[:30])
    }
