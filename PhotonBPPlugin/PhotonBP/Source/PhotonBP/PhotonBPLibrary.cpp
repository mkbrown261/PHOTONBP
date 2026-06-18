#include "PhotonBPLibrary.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphSchema.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CustomEvent.h"
#include "Engine/Blueprint.h"
#include "UObject/UnrealType.h"
#include "UObject/UObjectGlobals.h"
#include "Engine/UserDefinedStruct.h"

// ─── Helper: build FEdGraphPinType from string args ──────────────────────────
static FEdGraphPinType BuildPinType(
	const FString& PinCategory,
	const FString& PinSubCategory,
	const FString& PinSubCategoryObjectPath)
{
	FEdGraphPinType PinType;

	// Category
	if (PinCategory == TEXT("bool"))         PinType.PinCategory = UEdGraphSchema_K2::PC_Boolean;
	else if (PinCategory == TEXT("int"))     PinType.PinCategory = UEdGraphSchema_K2::PC_Int;
	else if (PinCategory == TEXT("int64"))   PinType.PinCategory = UEdGraphSchema_K2::PC_Int64;
	else if (PinCategory == TEXT("real"))    PinType.PinCategory = UEdGraphSchema_K2::PC_Real;
	else if (PinCategory == TEXT("string"))  PinType.PinCategory = UEdGraphSchema_K2::PC_String;
	else if (PinCategory == TEXT("name"))    PinType.PinCategory = UEdGraphSchema_K2::PC_Name;
	else if (PinCategory == TEXT("text"))    PinType.PinCategory = UEdGraphSchema_K2::PC_Text;
	else if (PinCategory == TEXT("object"))  PinType.PinCategory = UEdGraphSchema_K2::PC_Object;
	else if (PinCategory == TEXT("struct"))  PinType.PinCategory = UEdGraphSchema_K2::PC_Struct;
	else if (PinCategory == TEXT("class"))   PinType.PinCategory = UEdGraphSchema_K2::PC_Class;
	else                                     PinType.PinCategory = FName(*PinCategory);

	// SubCategory (float vs double for real)
	if (!PinSubCategory.IsEmpty())
	{
		if (PinSubCategory == TEXT("float"))       PinType.PinSubCategory = UEdGraphSchema_K2::PC_Float;
		else if (PinSubCategory == TEXT("double")) PinType.PinSubCategory = UEdGraphSchema_K2::PC_Double;
		else                                       PinType.PinSubCategory = FName(*PinSubCategory);
	}

	// SubCategoryObject (for object/struct references)
	if (!PinSubCategoryObjectPath.IsEmpty())
	{
		if (PinCategory == TEXT("struct"))
		{
			UScriptStruct* Struct = FindObject<UScriptStruct>(nullptr, *PinSubCategoryObjectPath);
			if (!Struct)
				Struct = LoadObject<UScriptStruct>(nullptr, *PinSubCategoryObjectPath);
			PinType.PinSubCategoryObject = Struct;
		}
		else
		{
			UClass* Class = FindObject<UClass>(nullptr, *PinSubCategoryObjectPath);
			if (!Class)
				Class = LoadObject<UClass>(nullptr, *PinSubCategoryObjectPath);
			PinType.PinSubCategoryObject = Class;
		}
	}

	return PinType;
}

// ─── AddMemberVariable ────────────────────────────────────────────────────────
bool UPhotonBPLibrary::AddMemberVariable(
	UBlueprint* Blueprint,
	FName VarName,
	FString PinCategory,
	FString PinSubCategory,
	FString PinSubCategoryObjectPath)
{
	if (!Blueprint) return false;

	FEdGraphPinType PinType = BuildPinType(PinCategory, PinSubCategory, PinSubCategoryObjectPath);

	FBlueprintEditorUtils::AddMemberVariable(Blueprint, VarName, PinType);
	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return true;
}

// ─── AddEventDispatcher ───────────────────────────────────────────────────────
bool UPhotonBPLibrary::AddEventDispatcher(
	UBlueprint* Blueprint,
	FName DispatcherName)
{
	if (!Blueprint) return false;

	// Add dispatcher as a variable with delegate pin type
	FBPVariableDescription NewVar;
	NewVar.VarName = DispatcherName;
	NewVar.VarType.PinCategory = UEdGraphSchema_K2::PC_MCDelegate;
	NewVar.PropertyFlags |= CPF_BlueprintAssignable | CPF_BlueprintCallable;
	Blueprint->NewVariables.Add(NewVar);

	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return true;
}

// ─── AddCustomEvent ───────────────────────────────────────────────────────────
bool UPhotonBPLibrary::AddCustomEvent(
	UBlueprint* Blueprint,
	FName EventName)
{
	if (!Blueprint) return false;

	// Get or create EventGraph
	UEdGraph* EventGraph = FBlueprintEditorUtils::FindEventGraph(Blueprint);
	if (!EventGraph) return false;

	// Create the custom event node directly
	UK2Node_CustomEvent* CustomEventNode = nullptr;
	{
		// Fallback: create node directly
		CustomEventNode = NewObject<UK2Node_CustomEvent>(EventGraph);
		CustomEventNode->CustomFunctionName = EventName;
		CustomEventNode->NodePosX = 0;
		CustomEventNode->NodePosY = 0;
		EventGraph->AddNode(CustomEventNode, false, false);
		CustomEventNode->CreateNewGuid();
		CustomEventNode->PostPlacedNewNode();
		CustomEventNode->AllocateDefaultPins();
	}

	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return CustomEventNode != nullptr;
}

// ─── SetVariableFlags ─────────────────────────────────────────────────────────
bool UPhotonBPLibrary::SetVariableFlags(
	UBlueprint* Blueprint,
	FName VarName,
	bool bInstanceEditable,
	bool bExposeOnSpawn)
{
	if (!Blueprint) return false;

	const int32 VarIndex = FBlueprintEditorUtils::FindNewVariableIndex(Blueprint, VarName);
	if (VarIndex == INDEX_NONE) return false;

	FBlueprintEditorUtils::SetBlueprintVariableMetaData(
		Blueprint, VarName, nullptr,
		FBlueprintMetadata::MD_ExposeOnSpawn,
		bExposeOnSpawn ? TEXT("true") : TEXT("false")
	);

	if (bInstanceEditable)
		Blueprint->NewVariables[VarIndex].PropertyFlags |= CPF_Edit;
	else
		Blueprint->NewVariables[VarIndex].PropertyFlags &= ~CPF_Edit;

	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return true;
}
