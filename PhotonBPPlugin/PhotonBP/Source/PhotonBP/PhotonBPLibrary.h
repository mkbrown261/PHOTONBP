#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraphPin.h"
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
	 * Returns JSON string: [{"guid":"...","type":"...","name":"..."}]
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString GetGraphNodes(
		UBlueprint* Blueprint,
		FString GraphName
	);
};
