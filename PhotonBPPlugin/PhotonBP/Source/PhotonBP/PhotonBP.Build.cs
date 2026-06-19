using UnrealBuildTool;

public class PhotonBP : ModuleRules
{
	public PhotonBP(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"BlueprintGraph",
			"KismetCompiler",
			"UnrealEd",
			"EditorSubsystem",
			"Kismet",
			// UMG designer support
			"UMG",
			"UMGEditor",
			"SlateCore",
			"Slate",
			// Material editing
			"MaterialEditor",
			// Asset tools (CreateAsset)
			"AssetTools",
			// DataTable editing
			"DataTableEditor",
			// Animation BP
			"AnimGraph",
			"AnimGraphRuntime",
			// Editor save utils
			"EditorFramework",
		});
	}
}
