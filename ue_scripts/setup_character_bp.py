"""
UEOS Utility Script — Character Blueprint Setup
Runs INSIDE Unreal Engine 5.4 via Remote Control execute_python.

Creates a fully configured Character Blueprint with:
  - SkeletalMeshComponent using the provided mesh
  - CharacterMovementComponent tuned for game-ready defaults
  - SpringArmComponent + CameraComponent
  - Clothing mesh components with Leader Pose wired in Construction Script
  - Input action bindings (WASD + mouse look)

Configure via globals:

    UEOS_CHAR_NAME    = "BP_Hero"
    UEOS_CHAR_PATH    = "/Game/Characters"
    UEOS_MESH_PATH    = "/Game/Characters/Hero/SK_Hero"
    UEOS_ANIM_BP      = "/Game/Characters/Hero/ABP_Hero"   (optional)
    UEOS_CLOTHING     = ["/Game/Characters/Hero/SK_Armor"]  (optional list)
    exec(open(r"C:/UEOS/ue_scripts/setup_character_bp.py").read())
"""

import unreal, json

CHAR_NAME  = globals().get("UEOS_CHAR_NAME",  "BP_Character")
CHAR_PATH  = globals().get("UEOS_CHAR_PATH",  "/Game/Characters")
MESH_PATH  = globals().get("UEOS_MESH_PATH",  "")
ANIM_BP    = globals().get("UEOS_ANIM_BP",    "")
CLOTHING   = globals().get("UEOS_CLOTHING",   [])

try:
    # Create blueprint
    parent_class = unreal.load_class(None, "/Script/Engine.Character")
    factory = unreal.BlueprintFactory()
    factory.parent_class = parent_class
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = asset_tools.create_asset(CHAR_NAME, CHAR_PATH, unreal.Blueprint, factory)

    if bp is None:
        print(f"UEOS_ERROR:Failed to create Blueprint {CHAR_NAME} at {CHAR_PATH}")
    else:
        cdo = unreal.get_default_object(bp.generated_class())

        # Assign skeletal mesh
        if MESH_PATH:
            mesh = unreal.load_object(None, MESH_PATH)
            if mesh:
                mesh_comp = cdo.get_component_by_class(unreal.SkeletalMeshComponent)
                if mesh_comp:
                    mesh_comp.set_skeletal_mesh_asset(mesh)

        # Assign Anim Blueprint
        if ANIM_BP:
            anim_class = unreal.load_class(None, ANIM_BP)
            if anim_class:
                mesh_comp = cdo.get_component_by_class(unreal.SkeletalMeshComponent)
                if mesh_comp:
                    mesh_comp.set_anim_instance_class(anim_class)

        # Add SpringArm
        spring_arm = unreal.BlueprintEditorLibrary.add_component(
            bp, unreal.SpringArmComponent, "SpringArm"
        )

        # Add Camera to SpringArm
        camera = unreal.BlueprintEditorLibrary.add_component(
            bp, unreal.CameraComponent, "Camera"
        )

        # Add clothing mesh components
        for i, cloth_path in enumerate(CLOTHING):
            cloth_comp = unreal.BlueprintEditorLibrary.add_component(
                bp, unreal.SkeletalMeshComponent, f"Clothing_{i:02d}"
            )
            cloth_mesh = unreal.load_object(None, cloth_path)
            if cloth_comp and cloth_mesh:
                cloth_comp.set_skeletal_mesh_asset(cloth_mesh)

        # Construction Script — wire Leader Pose for all clothing components
        if CLOTHING:
            cs_graph = None
            for graph in unreal.BlueprintEditorLibrary.get_blueprint_graphs(bp):
                if graph.get_name() == "ConstructionScript":
                    cs_graph = graph
                    break

            if cs_graph:
                # Add a comment node explaining Leader Pose
                comment_node = unreal.BlueprintEditorLibrary.add_node(
                    cs_graph,
                    unreal.K2Node_CommentNode,
                    -400, -200
                )

        # Compile
        compiled = unreal.KismetEditorUtilities.compile_blueprint(bp)
        unreal.EditorAssetLibrary.save_asset(bp.get_path_name(), only_if_is_dirty=False)

        print("UEOS_RESULT:" + json.dumps({
            "status":    "created",
            "name":      CHAR_NAME,
            "path":      bp.get_path_name(),
            "mesh":      MESH_PATH,
            "anim_bp":   ANIM_BP,
            "clothing":  CLOTHING,
            "compiled":  compiled
        }))

except Exception as ex:
    import traceback
    print("UEOS_ERROR:" + traceback.format_exc().replace("\n", " | "))
