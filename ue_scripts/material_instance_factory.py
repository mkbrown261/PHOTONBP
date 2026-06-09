"""
UEOS Utility Script — Material Instance Factory
Runs INSIDE Unreal Engine 5.4 via Remote Control execute_python.

Creates Material Instance assets from a parent Material and sets parameters.

Configure via globals:

    UEOS_PARENT_MAT     = "/Game/Materials/M_Character"
    UEOS_INSTANCES      = [
        {
            "name":   "MI_Hero",
            "path":   "/Game/Characters/Hero",
            "scalar": {"Roughness": 0.4, "Metallic": 0.8},
            "vector": {"BaseColor": [0.1, 0.2, 0.8, 1.0]},
            "texture": {"AlbedoMap": "/Game/Textures/T_Hero_D"}
        }
    ]
    exec(open(r"C:/UEOS/ue_scripts/material_instance_factory.py").read())
"""

import unreal, json

PARENT_MAT = globals().get("UEOS_PARENT_MAT", "")
INSTANCES  = globals().get("UEOS_INSTANCES",  [])

try:
    if not PARENT_MAT:
        print("UEOS_ERROR:UEOS_PARENT_MAT not set")
    elif not INSTANCES:
        print("UEOS_ERROR:UEOS_INSTANCES list is empty")
    else:
        parent = unreal.load_object(None, PARENT_MAT)
        if parent is None:
            print(f"UEOS_ERROR:Parent material not found: {PARENT_MAT}")
        else:
            asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
            created = []
            failed  = []

            for inst_def in INSTANCES:
                inst_name = inst_def.get("name",    "MI_Instance")
                inst_path = inst_def.get("path",    "/Game/Materials")
                scalars   = inst_def.get("scalar",  {})
                vectors   = inst_def.get("vector",  {})
                textures  = inst_def.get("texture", {})
                switches  = inst_def.get("switch",  {})

                try:
                    factory = unreal.MaterialInstanceConstantFactoryNew()
                    factory.initial_parent = parent
                    mi = asset_tools.create_asset(
                        inst_name, inst_path,
                        unreal.MaterialInstanceConstant, factory
                    )
                    if mi is None:
                        failed.append({"name": inst_name, "error": "create_asset returned None"})
                        continue

                    # Set scalar params
                    for param, val in scalars.items():
                        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
                            mi, param, float(val)
                        )

                    # Set vector params
                    for param, val in vectors.items():
                        if isinstance(val, (list, tuple)) and len(val) >= 3:
                            color = unreal.LinearColor(float(val[0]), float(val[1]), float(val[2]),
                                                       float(val[3]) if len(val) > 3 else 1.0)
                        else:
                            color = unreal.LinearColor(float(val), float(val), float(val), 1.0)
                        unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
                            mi, param, color
                        )

                    # Set texture params
                    for param, tex_path in textures.items():
                        tex = unreal.load_object(None, tex_path)
                        if tex:
                            unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
                                mi, param, tex
                            )

                    # Set static switch params
                    for param, val in switches.items():
                        unreal.MaterialEditingLibrary.set_material_instance_static_switch_parameter_value(
                            mi, param, bool(val)
                        )

                    unreal.MaterialEditingLibrary.update_material_instance(mi)
                    unreal.EditorAssetLibrary.save_asset(mi.get_path_name(), only_if_is_dirty=False)
                    created.append({"name": inst_name, "path": mi.get_path_name()})

                except Exception as e:
                    failed.append({"name": inst_name, "error": str(e)})

            print("UEOS_RESULT:" + json.dumps({
                "status":  "complete",
                "parent":  PARENT_MAT,
                "created": len(created),
                "failed":  len(failed),
                "results": created,
                "errors":  failed
            }))

except Exception as ex:
    import traceback
    print("UEOS_ERROR:" + traceback.format_exc().replace("\n", " | "))
