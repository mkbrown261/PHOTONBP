"""
UEOS Utility Script — Bulk Blueprint Compiler
Runs INSIDE Unreal Engine 5.4 via Remote Control execute_python.

Compiles all Blueprint assets under a given path.
Output: UEOS_RESULT: JSON with compiled/failed counts.

Usage via MCP:
    await ue.execute_python_file("C:/UEOS/ue_scripts/bulk_compile_blueprints.py")

Or inline after setting UEOS_COMPILE_PATH:
    UEOS_COMPILE_PATH = "/Game/Characters"
    exec(open(r"C:/UEOS/ue_scripts/bulk_compile_blueprints.py").read())
"""

import unreal, json

# ── Config ────────────────────────────────────────────────────────────────────
COMPILE_PATH = globals().get("UEOS_COMPILE_PATH", "/Game")
RECURSIVE    = globals().get("UEOS_COMPILE_RECURSIVE", True)

# ── Execution ─────────────────────────────────────────────────────────────────
try:
    registry  = unreal.AssetRegistryHelpers.get_asset_registry()
    all_bps   = registry.get_assets_by_path(COMPILE_PATH, recursive=RECURSIVE)

    compiled  = []
    failed    = []
    skipped   = []

    with unreal.ScopedEditorTransaction("UEOS Bulk Compile") as trans:
        for bp_data in all_bps:
            if str(bp_data.asset_class_path.asset_name) not in ("Blueprint", "AnimBlueprint", "WidgetBlueprint"):
                continue
            try:
                bp = unreal.EditorAssetLibrary.load_asset(str(bp_data.object_path))
                if bp is None or not isinstance(bp, unreal.Blueprint):
                    skipped.append(str(bp_data.asset_name))
                    continue
                success = unreal.KismetEditorUtilities.compile_blueprint(bp)
                if success:
                    compiled.append(str(bp_data.asset_name))
                else:
                    failed.append(str(bp_data.asset_name))
            except Exception as e:
                failed.append(f"{bp_data.asset_name}: {e}")

    print("UEOS_RESULT:" + json.dumps({
        "status":        "complete",
        "search_path":   COMPILE_PATH,
        "compiled":      len(compiled),
        "failed":        len(failed),
        "skipped":       len(skipped),
        "failed_list":   failed[:20],
        "compiled_list": compiled[:20]
    }))

except Exception as ex:
    import traceback
    print("UEOS_ERROR:" + traceback.format_exc().replace("\n", " | "))
