"""
UEOS Utility Script — Batch FBX Importer
Runs INSIDE Unreal Engine 5.4 via Remote Control execute_python.

Imports a list of FBX files into UE, with full options.
Configure via globals before exec():

    UEOS_FBX_FILES    = ["C:/models/hero.fbx", "C:/models/enemy.fbx"]
    UEOS_DEST_PATH    = "/Game/Characters"
    UEOS_AS_SKELETAL  = True
    UEOS_IMPORT_ANIM  = False
    exec(open(r"C:/UEOS/ue_scripts/import_fbx_batch.py").read())
"""

import unreal, json, os

FBX_FILES    = globals().get("UEOS_FBX_FILES",   [])
DEST_PATH    = globals().get("UEOS_DEST_PATH",    "/Game/UEOS/Imported")
AS_SKELETAL  = globals().get("UEOS_AS_SKELETAL",  False)
IMPORT_ANIM  = globals().get("UEOS_IMPORT_ANIM",  False)
IMPORT_TEX   = globals().get("UEOS_IMPORT_TEX",   True)
IMPORT_MAT   = globals().get("UEOS_IMPORT_MAT",   True)
COMBINE_MESH = globals().get("UEOS_COMBINE_MESH", True)

try:
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    imported_all = []
    failed_all   = []

    for fbx_path in FBX_FILES:
        fbx_path = fbx_path.replace("\\", "/")
        if not os.path.exists(fbx_path):
            failed_all.append({"file": fbx_path, "error": "File not found"})
            continue

        task = unreal.AssetImportTask()
        task.filename         = fbx_path
        task.destination_path = DEST_PATH
        task.automated        = True
        task.replace_existing = True
        task.save             = True

        opts = unreal.FbxImportUI()
        opts.import_mesh       = True
        opts.import_textures   = IMPORT_TEX
        opts.import_materials  = IMPORT_MAT
        opts.import_animations = IMPORT_ANIM
        opts.import_as_skeletal = AS_SKELETAL
        opts.static_mesh_import_data.combine_meshes = COMBINE_MESH
        task.options = opts

        try:
            asset_tools.import_asset_tasks([task])
            paths = task.imported_object_paths or []
            imported_all.append({
                "file":   fbx_path,
                "assets": [str(p) for p in paths]
            })
        except Exception as e:
            failed_all.append({"file": fbx_path, "error": str(e)})

    print("UEOS_RESULT:" + json.dumps({
        "status":     "complete",
        "dest_path":  DEST_PATH,
        "imported":   len(imported_all),
        "failed":     len(failed_all),
        "results":    imported_all,
        "errors":     failed_all
    }))

except Exception as ex:
    import traceback
    print("UEOS_ERROR:" + traceback.format_exc().replace("\n", " | "))
