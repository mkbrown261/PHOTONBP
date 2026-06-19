#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraphPin.h"
#include "Engine/UserDefinedStruct.h"
#include "PhotonBPLibrary.generated.h"

UCLASS()
class UPhotonBPLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:

	// ── Variable Creation ────────────────────────────────────────────────────

	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Variables")
	static bool AddMemberVariable(
		UBlueprint* Blueprint,
		FName VarName,
		FString PinCategory,
		FString PinSubCategory,
		FString PinSubCategoryObjectPath
	);

	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Variables")
	static bool AddEventDispatcher(
		UBlueprint* Blueprint,
		FName DispatcherName
	);

	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Variables")
	static bool SetVariableFlags(
		UBlueprint* Blueprint,
		FName VarName,
		bool bInstanceEditable,
		bool bExposeOnSpawn
	);

	// ── Struct Field Creation ────────────────────────────────────────────────

	/**
	 * Add a typed field to a UserDefinedStruct asset.
	 * @param Struct                  The UserDefinedStruct asset
	 * @param FieldName               Name for the new field
	 * @param PinCategory             e.g. "bool","int","real","string","name","struct","object"
	 * @param PinSubCategory          e.g. "float","double" (for real), or "" for others
	 * @param PinSubCategoryObjectPath e.g. "/Script/CoreUObject.Vector" or "" for primitives
	 * @return True on success
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Structs")
	static bool AddStructField(
		UUserDefinedStruct* Struct,
		FName FieldName,
		FString PinCategory,
		FString PinSubCategory,
		FString PinSubCategoryObjectPath
	);

	// ── Node Creation ────────────────────────────────────────────────────────

	/**
	 * Add a Custom Event node to the EventGraph.
	 * Returns the node GUID string for use in ConnectPins.
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString AddCustomEvent(
		UBlueprint* Blueprint,
		FName EventName,
		int32 NodeX,
		int32 NodeY
	);

	/**
	 * Add a standard event node (e.g. ReceiveBeginPlay, ReceiveTick).
	 * Returns node GUID string.
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString AddEventNode(
		UBlueprint* Blueprint,
		FString GraphName,
		FString EventFunctionName,
		int32 NodeX,
		int32 NodeY
	);

	/**
	 * Add a function call node.
	 * @param ClassName		e.g. "KismetSystemLibrary"
	 * @param FunctionName	e.g. "PrintString"
	 * Returns node GUID string.
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString AddFunctionCallNode(
		UBlueprint* Blueprint,
		FString GraphName,
		FString ClassName,
		FString FunctionName,
		int32 NodeX,
		int32 NodeY
	);

	/**
	 * Add a variable GET node.
	 * Returns node GUID string.
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString AddVariableGetNode(
		UBlueprint* Blueprint,
		FString GraphName,
		FName VarName,
		int32 NodeX,
		int32 NodeY
	);

	/**
	 * Add a variable SET node.
	 * Returns node GUID string.
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString AddVariableSetNode(
		UBlueprint* Blueprint,
		FString GraphName,
		FName VarName,
		int32 NodeX,
		int32 NodeY
	);

	/**
	 * Add a Branch (if/then/else) node.
	 * Returns node GUID string.
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString AddBranchNode(
		UBlueprint* Blueprint,
		FString GraphName,
		int32 NodeX,
		int32 NodeY
	);

	/**
	 * Add a Sequence node.
	 * Returns node GUID string.
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString AddSequenceNode(
		UBlueprint* Blueprint,
		FString GraphName,
		int32 NodeX,
		int32 NodeY
	);

	/**
	 * Add a Cast node.
	 * @param TargetClassName	e.g. "ACharacter"
	 * Returns node GUID string.
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString AddCastNode(
		UBlueprint* Blueprint,
		FString GraphName,
		FString TargetClassName,
		int32 NodeX,
		int32 NodeY
	);

	// ── Pin Connection ───────────────────────────────────────────────────────

	/**
	 * Connect two pins between nodes in a graph.
	 * @param FromNodeGuid	GUID string returned from Add*Node
	 * @param FromPinName	e.g. "then", "ReturnValue", "Value"
	 * @param ToNodeGuid	GUID string returned from Add*Node
	 * @param ToPinName		e.g. "execute", "Condition", "NewValue"
	 * @return True if connection succeeded
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Pins")
	static bool ConnectPins(
		UBlueprint* Blueprint,
		FString GraphName,
		FString FromNodeGuid,
		FString FromPinName,
		FString ToNodeGuid,
		FString ToPinName
	);

	/**
	 * Set a literal value on a pin (for input pins with no connection).
	 * @param NodeGuid		GUID of the node
	 * @param PinName		Name of the pin
	 * @param Value			String representation of the value
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Pins")
	static bool SetPinDefaultValue(
		UBlueprint* Blueprint,
		FString GraphName,
		FString NodeGuid,
		FString PinName,
		FString Value
	);

	/**
	 * Get all node GUIDs and their types in a graph.
	 * Returns JSON string: [{"guid":"...","type":"...","name":"...","x":0,"y":0,"pins":[...]}]
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString GetGraphNodes(
		UBlueprint* Blueprint,
		FString GraphName
	);

	// ── Component & Interface ────────────────────────────────────────────────

	/**
	 * Add a component to a Blueprint's SimpleConstructionScript.
	 * @param Blueprint         The Blueprint asset
	 * @param ComponentClass    The component class (e.g. UBoxComponent)
	 * @param ComponentName     Name for the new component
	 * @return True on success
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Components")
	static bool AddComponent(
		UBlueprint* Blueprint,
		UClass* ComponentClass,
		FName ComponentName
	);

	/**
	 * Add an interface to a Blueprint.
	 * @param Blueprint         The Blueprint asset
	 * @param InterfaceClass    The interface class to implement
	 * @return True on success
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Components")
	static bool AddInterface(
		UBlueprint* Blueprint,
		UClass* InterfaceClass
	);

	// ── UMG Widget Designer ──────────────────────────────────────────────────

	/**
	 * Add a widget to a Widget Blueprint's designer canvas.
	 * @param WidgetBlueprint   The Widget Blueprint asset (cast to UWidgetBlueprint internally)
	 * @param WidgetClassName   e.g. "ProgressBar", "TextBlock", "Button", "Image"
	 * @param WidgetName        Desired name for the new widget slot
	 * @param PosX              Canvas position X (pixels from top-left)
	 * @param PosY              Canvas position Y (pixels from top-left)
	 * @param SizeX             Width in pixels
	 * @param SizeY             Height in pixels
	 * @return GUID string of the created widget slot, or empty string on failure
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|UMG")
	static FString AddWidgetToDesigner(
		UBlueprint* WidgetBlueprint,
		FString WidgetClassName,
		FString WidgetName,
		int32 PosX,
		int32 PosY,
		int32 SizeX,
		int32 SizeY
	);
};
