#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraphPin.h"
#include "Engine/UserDefinedStruct.h"
#include "Engine/UserDefinedEnum.h"
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

	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Structs")
	static bool AddStructField(
		UUserDefinedStruct* Struct,
		FName FieldName,
		FString PinCategory,
		FString PinSubCategory,
		FString PinSubCategoryObjectPath
	);

	// ── Enum Operations ──────────────────────────────────────────────────────

	/** Returns the number of enum entries (including the MAX sentinel). */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Enums")
	static int32 EnumNumEnums(UUserDefinedEnum* Enum);

	/** Set metadata on an enum (e.g. DisplayName_NewEnumerator0 = "MyValue"). */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Enums")
	static void EnumSetMetaData(UUserDefinedEnum* Enum, FName Key, FString Value);

	/** Add a new enumerator entry and return its slot index. */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Enums")
	static int32 EnumAddEntry(UUserDefinedEnum* Enum, FString EntryName);

	// ── DataTable Operations ─────────────────────────────────────────────────

	/** Convert a DataTable asset to a JSON string. */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|DataTable")
	static FString DataTableToJsonString(UDataTable* DataTable);

	/** Get all row names from a DataTable. */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|DataTable")
	static TArray<FName> DataTableGetRowNames(UDataTable* DataTable);

	/** Fill a DataTable from a CSV string. Returns true on success. */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|DataTable")
	static bool DataTableFillFromCsv(UDataTable* DataTable, FString CsvString);

	// ── Struct Field Iteration ───────────────────────────────────────────────

	/** Get all field names and types from a UserDefinedStruct as JSON string.
	 *  Returns: [{"name":"FieldName","type":"float"}, ...] */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Structs")
	static FString StructGetFields(UUserDefinedStruct* Struct);

	// ── Node Creation ────────────────────────────────────────────────────────

	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString AddCustomEvent(
		UBlueprint* Blueprint,
		FName EventName,
		int32 NodeX,
		int32 NodeY
	);

	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString AddEventNode(
		UBlueprint* Blueprint,
		FString GraphName,
		FString EventFunctionName,
		int32 NodeX,
		int32 NodeY
	);

	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString AddFunctionCallNode(
		UBlueprint* Blueprint,
		FString GraphName,
		FString ClassName,
		FString FunctionName,
		int32 NodeX,
		int32 NodeY
	);

	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString AddVariableGetNode(
		UBlueprint* Blueprint,
		FString GraphName,
		FName VarName,
		int32 NodeX,
		int32 NodeY
	);

	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString AddVariableSetNode(
		UBlueprint* Blueprint,
		FString GraphName,
		FName VarName,
		int32 NodeX,
		int32 NodeY
	);

	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString AddBranchNode(
		UBlueprint* Blueprint,
		FString GraphName,
		int32 NodeX,
		int32 NodeY
	);

	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString AddSequenceNode(
		UBlueprint* Blueprint,
		FString GraphName,
		int32 NodeX,
		int32 NodeY
	);

	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString AddCastNode(
		UBlueprint* Blueprint,
		FString GraphName,
		FString TargetClassName,
		int32 NodeX,
		int32 NodeY
	);

	// ── Pin Connection ───────────────────────────────────────────────────────

	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Pins")
	static bool ConnectPins(
		UBlueprint* Blueprint,
		FString GraphName,
		FString FromNodeGuid,
		FString FromPinName,
		FString ToNodeGuid,
		FString ToPinName
	);

	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Pins")
	static bool SetPinDefaultValue(
		UBlueprint* Blueprint,
		FString GraphName,
		FString NodeGuid,
		FString PinName,
		FString Value
	);

	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Nodes")
	static FString GetGraphNodes(
		UBlueprint* Blueprint,
		FString GraphName
	);

	// ── Component & Interface ────────────────────────────────────────────────

	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Components")
	static bool AddComponent(
		UBlueprint* Blueprint,
		UClass* ComponentClass,
		FName ComponentName
	);

	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Components")
	static bool AddInterface(
		UBlueprint* Blueprint,
		UClass* InterfaceClass
	);

	// ── Animation Blueprint ──────────────────────────────────────────────────

	/** Compile an Animation Blueprint. Returns true on success. */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Animation")
	static bool CompileAnimBlueprint(UBlueprint* AnimBlueprint);

	/** Add an Animation Graph node by class name. Returns node GUID string. */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Animation")
	static FString AddAnimGraphNode(
		UBlueprint* AnimBlueprint,
		FString NodeClassName,
		int32 NodeX,
		int32 NodeY
	);

	/** Add a state to a state machine in an anim graph. Returns state GUID. */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Animation")
	static FString AddStateToStateMachine(
		UBlueprint* AnimBlueprint,
		FString StateMachineName,
		FString StateName,
		int32 NodeX,
		int32 NodeY
	);

	/** Set the entry state of a state machine. */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Animation")
	static bool SetEntryState(
		UBlueprint* AnimBlueprint,
		FString StateMachineName,
		FString StateName
	);

	/** Add a transition between two states. */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Animation")
	static bool AddTransition(
		UBlueprint* AnimBlueprint,
		FString StateMachineName,
		FString FromState,
		FString ToState
	);

	/** Set the animation sequence played in a state. */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Animation")
	static bool SetStateAnimation(
		UBlueprint* AnimBlueprint,
		FString StateMachineName,
		FString StateName,
		FString AnimSequencePath
	);

	// ── Material ─────────────────────────────────────────────────────────────

	/** Get all expression node GUIDs in a material as JSON string. */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|Material")
	static FString GetMaterialExpressions(UMaterial* Material);

	// ── Enhanced Input Asset Creation ────────────────────────────────────────

	/** Create an InputAction asset at the given path. Returns asset path or empty on failure. */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|EnhancedInput")
	static FString CreateInputAction(FString AssetName, FString SavePath);

	/** Create an InputMappingContext asset at the given path. Returns asset path or empty on failure. */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|EnhancedInput")
	static FString CreateInputMappingContext(FString AssetName, FString SavePath);

	// ── PCG Graph Asset Creation ─────────────────────────────────────────────

	/** Create a PCGGraph asset at the given path. Returns asset path or empty on failure. */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP|PCG")
	static FString CreatePCGGraph(FString AssetName, FString SavePath);

	// ── UMG Widget Designer ──────────────────────────────────────────────────

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
