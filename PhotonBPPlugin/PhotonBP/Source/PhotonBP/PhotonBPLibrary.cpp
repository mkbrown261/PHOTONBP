#include "PhotonBPLibrary.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphSchema.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "K2Node_CustomEvent.h"
#include "K2Node_Event.h"
#include "K2Node_VariableGet.h"
#include "K2Node_VariableSet.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_ExecutionSequence.h"
#include "K2Node_DynamicCast.h"
#include "Engine/Blueprint.h"
#include "UObject/UnrealType.h"
#include "UObject/UObjectGlobals.h"
// UserDefinedStruct editing
#include "UserDefinedStructure/UserDefinedStructEditorData.h"
#include "Kismet2/StructureEditorUtils.h"
// UMG designer support
#include "Blueprint/WidgetTree.h"
#include "Components/Widget.h"
#include "Components/PanelWidget.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/TextBlock.h"
#include "Components/Button.h"
#include "Components/Image.h"
#include "Components/ProgressBar.h"
#include "Components/Slider.h"
#include "Components/CheckBox.h"
#include "Components/EditableTextBox.h"
#include "Components/ScrollBox.h"
#include "Components/HorizontalBox.h"
#include "Components/VerticalBox.h"
#include "Components/Overlay.h"
#include "WidgetBlueprint.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/SCS_Node.h"
// Enum editing
#include "Engine/UserDefinedEnum.h"
// DataTable
#include "Engine/DataTable.h"
// Material
#include "Materials/Material.h"
#include "Materials/MaterialExpression.h"
// Asset tools for factory-based creation
#include "AssetToolsModule.h"
#include "IAssetTools.h"
#include "FileHelpers.h"

// ─── Internal helpers ─────────────────────────────────────────────────────────

static UEdGraph* FindGraph(UBlueprint* BP, const FString& GraphName)
{
	if (!BP) return nullptr;

	// EventGraph shortcut
	if (GraphName.IsEmpty() || GraphName == TEXT("EventGraph"))
		return FBlueprintEditorUtils::FindEventGraph(BP);

	// Search all graphs
	TArray<UEdGraph*> AllGraphs;
	BP->GetAllGraphs(AllGraphs);
	for (UEdGraph* G : AllGraphs)
	{
		if (G && G->GetName() == GraphName)
			return G;
	}
	return nullptr;
}

static UEdGraphNode* FindNodeByGuid(UEdGraph* Graph, const FString& GuidStr)
{
	if (!Graph) return nullptr;
	FGuid TargetGuid;
	FGuid::Parse(GuidStr, TargetGuid);
	for (UEdGraphNode* Node : Graph->Nodes)
	{
		if (Node && Node->NodeGuid == TargetGuid)
			return Node;
	}
	return nullptr;
}

static FEdGraphPinType BuildPinType(
	const FString& PinCategory,
	const FString& PinSubCategory,
	const FString& PinSubCategoryObjectPath)
{
	FEdGraphPinType PinType;

	if      (PinCategory == TEXT("bool"))   PinType.PinCategory = UEdGraphSchema_K2::PC_Boolean;
	else if (PinCategory == TEXT("int"))    PinType.PinCategory = UEdGraphSchema_K2::PC_Int;
	else if (PinCategory == TEXT("int64"))  PinType.PinCategory = UEdGraphSchema_K2::PC_Int64;
	else if (PinCategory == TEXT("real"))   PinType.PinCategory = UEdGraphSchema_K2::PC_Real;
	else if (PinCategory == TEXT("string")) PinType.PinCategory = UEdGraphSchema_K2::PC_String;
	else if (PinCategory == TEXT("name"))   PinType.PinCategory = UEdGraphSchema_K2::PC_Name;
	else if (PinCategory == TEXT("text"))   PinType.PinCategory = UEdGraphSchema_K2::PC_Text;
	else if (PinCategory == TEXT("object")) PinType.PinCategory = UEdGraphSchema_K2::PC_Object;
	else if (PinCategory == TEXT("struct")) PinType.PinCategory = UEdGraphSchema_K2::PC_Struct;
	else if (PinCategory == TEXT("class"))  PinType.PinCategory = UEdGraphSchema_K2::PC_Class;
	else                                    PinType.PinCategory = FName(*PinCategory);

	if (!PinSubCategory.IsEmpty())
	{
		if      (PinSubCategory == TEXT("float"))  PinType.PinSubCategory = UEdGraphSchema_K2::PC_Float;
		else if (PinSubCategory == TEXT("double")) PinType.PinSubCategory = UEdGraphSchema_K2::PC_Double;
		else                                       PinType.PinSubCategory = FName(*PinSubCategory);
	}

	if (!PinSubCategoryObjectPath.IsEmpty())
	{
		if (PinCategory == TEXT("struct"))
		{
			UScriptStruct* Struct = FindObject<UScriptStruct>(nullptr, *PinSubCategoryObjectPath);
			if (!Struct) Struct = LoadObject<UScriptStruct>(nullptr, *PinSubCategoryObjectPath);
			PinType.PinSubCategoryObject = Struct;
		}
		else
		{
			UClass* Class = FindObject<UClass>(nullptr, *PinSubCategoryObjectPath);
			if (!Class) Class = LoadObject<UClass>(nullptr, *PinSubCategoryObjectPath);
			PinType.PinSubCategoryObject = Class;
		}
	}

	return PinType;
}

// ─── AddStructField ───────────────────────────────────────────────────────────

bool UPhotonBPLibrary::AddStructField(
	UUserDefinedStruct* Struct,
	FName FieldName,
	FString PinCategory,
	FString PinSubCategory,
	FString PinSubCategoryObjectPath)
{
	if (!Struct) return false;

	// Build the pin type
	FEdGraphPinType PinType = BuildPinType(PinCategory, PinSubCategory, PinSubCategoryObjectPath);

	// Add the variable — FStructureEditorUtils::AddVariable auto-generates a GUID name
	FStructureEditorUtils::AddVariable(Struct, PinType);

	// Grab the entry that was just appended (it is always Last())
	TArray<FStructVariableDescription>& VarDesc = FStructureEditorUtils::GetVarDesc(Struct);
	if (VarDesc.Num() == 0) return false;

	FGuid NewVarGuid = VarDesc.Last().VarGuid;

	// Rename it to the requested name — RenameVariable takes FString, not FName
	FStructureEditorUtils::RenameVariable(Struct, NewVarGuid, FieldName.ToString());

	// Notify the editor that the struct layout changed
	FStructureEditorUtils::OnStructureChanged(Struct,
		FStructureEditorUtils::EStructureEditorChangeInfo::AddedVariable);

	return true;
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

	FBPVariableDescription NewVar;
	NewVar.VarName = DispatcherName;
	NewVar.VarType.PinCategory = UEdGraphSchema_K2::PC_MCDelegate;
	NewVar.PropertyFlags |= CPF_BlueprintAssignable | CPF_BlueprintCallable;
	Blueprint->NewVariables.Add(NewVar);

	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return true;
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

	if (bInstanceEditable)
		Blueprint->NewVariables[VarIndex].PropertyFlags |= CPF_Edit;
	else
		Blueprint->NewVariables[VarIndex].PropertyFlags &= ~CPF_Edit;

	if (bExposeOnSpawn)
		Blueprint->NewVariables[VarIndex].PropertyFlags |= CPF_ExposeOnSpawn;
	else
		Blueprint->NewVariables[VarIndex].PropertyFlags &= ~CPF_ExposeOnSpawn;

	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return true;
}

// ─── AddCustomEvent ───────────────────────────────────────────────────────────

FString UPhotonBPLibrary::AddCustomEvent(
	UBlueprint* Blueprint,
	FName EventName,
	int32 NodeX,
	int32 NodeY)
{
	if (!Blueprint) return TEXT("");

	UEdGraph* EventGraph = FBlueprintEditorUtils::FindEventGraph(Blueprint);
	if (!EventGraph) return TEXT("");

	UK2Node_CustomEvent* Node = NewObject<UK2Node_CustomEvent>(EventGraph);
	Node->CustomFunctionName = EventName;
	Node->NodePosX = NodeX;
	Node->NodePosY = NodeY;
	Node->CreateNewGuid();
	EventGraph->AddNode(Node, false, false);
	Node->PostPlacedNewNode();
	Node->AllocateDefaultPins();

	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return Node->NodeGuid.ToString();
}

// ─── AddEventNode ─────────────────────────────────────────────────────────────

FString UPhotonBPLibrary::AddEventNode(
	UBlueprint* Blueprint,
	FString GraphName,
	FString EventFunctionName,
	int32 NodeX,
	int32 NodeY)
{
	if (!Blueprint) return TEXT("");

	UEdGraph* Graph = FindGraph(Blueprint, GraphName);
	if (!Graph) return TEXT("");

	// Find the function on the Blueprint's generated class or parent classes
	UClass* SearchClass = Blueprint->ParentClass;
	UFunction* EventFunc = nullptr;
	while (SearchClass && !EventFunc)
	{
		EventFunc = SearchClass->FindFunctionByName(FName(*EventFunctionName));
		SearchClass = SearchClass->GetSuperClass();
	}
	if (!EventFunc) return TEXT("");

	UK2Node_Event* Node = NewObject<UK2Node_Event>(Graph);
	Node->EventReference.SetExternalMember(FName(*EventFunctionName), EventFunc->GetOwnerClass());
	Node->bOverrideFunction = true;
	Node->NodePosX = NodeX;
	Node->NodePosY = NodeY;
	Node->CreateNewGuid();
	Graph->AddNode(Node, false, false);
	Node->PostPlacedNewNode();
	Node->AllocateDefaultPins();

	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return Node->NodeGuid.ToString();
}

// ─── AddFunctionCallNode ──────────────────────────────────────────────────────

FString UPhotonBPLibrary::AddFunctionCallNode(
	UBlueprint* Blueprint,
	FString GraphName,
	FString ClassName,
	FString FunctionName,
	int32 NodeX,
	int32 NodeY)
{
	if (!Blueprint) return TEXT("");

	UEdGraph* Graph = FindGraph(Blueprint, GraphName);
	if (!Graph) return TEXT("");

	// Find the UFunction
	UFunction* Func = nullptr;

	// Try common module paths
	TArray<FString> ClassPaths = {
		FString::Printf(TEXT("/Script/Engine.%s"), *ClassName),
		FString::Printf(TEXT("/Script/KismetSystemLibrary.%s"), *ClassName),
		FString::Printf(TEXT("/Script/BlueprintFunctionLibrary.%s"), *ClassName),
		FString::Printf(TEXT("/Script/GameplayStatics.%s"), *ClassName),
	};

	UClass* FoundClass = nullptr;
	for (const FString& Path : ClassPaths)
	{
		FoundClass = FindObject<UClass>(nullptr, *Path);
		if (!FoundClass) FoundClass = LoadObject<UClass>(nullptr, *Path);
		if (FoundClass) break;
	}

	// Also try searching all loaded classes
	if (!FoundClass)
	{
		for (TObjectIterator<UClass> It; It; ++It)
		{
			if (It->GetName() == ClassName)
			{
				FoundClass = *It;
				break;
			}
		}
	}

	if (!FoundClass) return TEXT("");
	Func = FoundClass->FindFunctionByName(FName(*FunctionName));
	if (!Func) return TEXT("");

	UK2Node_CallFunction* Node = NewObject<UK2Node_CallFunction>(Graph);
	Node->SetFromFunction(Func);
	Node->NodePosX = NodeX;
	Node->NodePosY = NodeY;
	Node->CreateNewGuid();
	Graph->AddNode(Node, false, false);
	Node->PostPlacedNewNode();
	Node->AllocateDefaultPins();

	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return Node->NodeGuid.ToString();
}

// ─── AddVariableGetNode ───────────────────────────────────────────────────────

FString UPhotonBPLibrary::AddVariableGetNode(
	UBlueprint* Blueprint,
	FString GraphName,
	FName VarName,
	int32 NodeX,
	int32 NodeY)
{
	if (!Blueprint) return TEXT("");

	UEdGraph* Graph = FindGraph(Blueprint, GraphName);
	if (!Graph) return TEXT("");

	UK2Node_VariableGet* Node = NewObject<UK2Node_VariableGet>(Graph);
	Node->VariableReference.SetSelfMember(VarName);
	Node->NodePosX = NodeX;
	Node->NodePosY = NodeY;
	Node->CreateNewGuid();
	Graph->AddNode(Node, false, false);
	Node->PostPlacedNewNode();
	Node->AllocateDefaultPins();

	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return Node->NodeGuid.ToString();
}

// ─── AddVariableSetNode ───────────────────────────────────────────────────────

FString UPhotonBPLibrary::AddVariableSetNode(
	UBlueprint* Blueprint,
	FString GraphName,
	FName VarName,
	int32 NodeX,
	int32 NodeY)
{
	if (!Blueprint) return TEXT("");

	UEdGraph* Graph = FindGraph(Blueprint, GraphName);
	if (!Graph) return TEXT("");

	UK2Node_VariableSet* Node = NewObject<UK2Node_VariableSet>(Graph);
	Node->VariableReference.SetSelfMember(VarName);
	Node->NodePosX = NodeX;
	Node->NodePosY = NodeY;
	Node->CreateNewGuid();
	Graph->AddNode(Node, false, false);
	Node->PostPlacedNewNode();
	Node->AllocateDefaultPins();

	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return Node->NodeGuid.ToString();
}

// ─── AddBranchNode ───────────────────────────────────────────────────────────

FString UPhotonBPLibrary::AddBranchNode(
	UBlueprint* Blueprint,
	FString GraphName,
	int32 NodeX,
	int32 NodeY)
{
	if (!Blueprint) return TEXT("");

	UEdGraph* Graph = FindGraph(Blueprint, GraphName);
	if (!Graph) return TEXT("");

	UK2Node_IfThenElse* Node = NewObject<UK2Node_IfThenElse>(Graph);
	Node->NodePosX = NodeX;
	Node->NodePosY = NodeY;
	Node->CreateNewGuid();
	Graph->AddNode(Node, false, false);
	Node->PostPlacedNewNode();
	Node->AllocateDefaultPins();

	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return Node->NodeGuid.ToString();
}

// ─── AddSequenceNode ──────────────────────────────────────────────────────────

FString UPhotonBPLibrary::AddSequenceNode(
	UBlueprint* Blueprint,
	FString GraphName,
	int32 NodeX,
	int32 NodeY)
{
	if (!Blueprint) return TEXT("");

	UEdGraph* Graph = FindGraph(Blueprint, GraphName);
	if (!Graph) return TEXT("");

	UK2Node_ExecutionSequence* Node = NewObject<UK2Node_ExecutionSequence>(Graph);
	Node->NodePosX = NodeX;
	Node->NodePosY = NodeY;
	Node->CreateNewGuid();
	Graph->AddNode(Node, false, false);
	Node->PostPlacedNewNode();
	Node->AllocateDefaultPins();

	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return Node->NodeGuid.ToString();
}

// ─── AddCastNode ─────────────────────────────────────────────────────────────

FString UPhotonBPLibrary::AddCastNode(
	UBlueprint* Blueprint,
	FString GraphName,
	FString TargetClassName,
	int32 NodeX,
	int32 NodeY)
{
	if (!Blueprint) return TEXT("");

	UEdGraph* Graph = FindGraph(Blueprint, GraphName);
	if (!Graph) return TEXT("");

	UClass* TargetClass = nullptr;
	for (TObjectIterator<UClass> It; It; ++It)
	{
		if (It->GetName() == TargetClassName)
		{
			TargetClass = *It;
			break;
		}
	}
	if (!TargetClass) return TEXT("");

	UK2Node_DynamicCast* Node = NewObject<UK2Node_DynamicCast>(Graph);
	Node->TargetType = TargetClass;
	Node->NodePosX = NodeX;
	Node->NodePosY = NodeY;
	Node->CreateNewGuid();
	Graph->AddNode(Node, false, false);
	Node->PostPlacedNewNode();
	Node->AllocateDefaultPins();

	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return Node->NodeGuid.ToString();
}

// ─── ConnectPins ─────────────────────────────────────────────────────────────

bool UPhotonBPLibrary::ConnectPins(
	UBlueprint* Blueprint,
	FString GraphName,
	FString FromNodeGuid,
	FString FromPinName,
	FString ToNodeGuid,
	FString ToPinName)
{
	if (!Blueprint) return false;

	UEdGraph* Graph = FindGraph(Blueprint, GraphName);
	if (!Graph) return false;

	UEdGraphNode* FromNode = FindNodeByGuid(Graph, FromNodeGuid);
	UEdGraphNode* ToNode   = FindNodeByGuid(Graph, ToNodeGuid);
	if (!FromNode || !ToNode) return false;

	UEdGraphPin* FromPin = FromNode->FindPin(FName(*FromPinName), EGPD_Output);
	UEdGraphPin* ToPin   = ToNode->FindPin(FName(*ToPinName),   EGPD_Input);

	if (!FromPin || !ToPin) return false;

	const UEdGraphSchema* Schema = Graph->GetSchema();
	if (!Schema) return false;

	const FPinConnectionResponse Response = Schema->CanCreateConnection(FromPin, ToPin);
	if (Response.Response == CONNECT_RESPONSE_DISALLOW) return false;

	Schema->TryCreateConnection(FromPin, ToPin);
	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return true;
}

// ─── SetPinDefaultValue ───────────────────────────────────────────────────────

bool UPhotonBPLibrary::SetPinDefaultValue(
	UBlueprint* Blueprint,
	FString GraphName,
	FString NodeGuid,
	FString PinName,
	FString Value)
{
	if (!Blueprint) return false;

	UEdGraph* Graph = FindGraph(Blueprint, GraphName);
	if (!Graph) return false;

	UEdGraphNode* Node = FindNodeByGuid(Graph, NodeGuid);
	if (!Node) return false;

	UEdGraphPin* Pin = Node->FindPin(FName(*PinName));
	if (!Pin) return false;

	Pin->DefaultValue = Value;
	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return true;
}

// ─── GetGraphNodes ────────────────────────────────────────────────────────────

FString UPhotonBPLibrary::GetGraphNodes(
	UBlueprint* Blueprint,
	FString GraphName)
{
	if (!Blueprint) return TEXT("[]");

	UEdGraph* Graph = FindGraph(Blueprint, GraphName);
	if (!Graph) return TEXT("[]");

	FString Result = TEXT("[");
	bool bFirst = true;
	for (UEdGraphNode* Node : Graph->Nodes)
	{
		if (!Node) continue;
		if (!bFirst) Result += TEXT(",");
		bFirst = false;

		// Get pin names
		FString PinList = TEXT("[");
		bool bFirstPin = true;
		for (UEdGraphPin* Pin : Node->Pins)
		{
			if (!Pin) continue;
			if (!bFirstPin) PinList += TEXT(",");
			bFirstPin = false;
			FString Dir = Pin->Direction == EGPD_Input ? TEXT("in") : TEXT("out");
			PinList += FString::Printf(TEXT("{\"name\":\"%s\",\"dir\":\"%s\"}"),
				*Pin->PinName.ToString(), *Dir);
		}
		PinList += TEXT("]");

		Result += FString::Printf(
			TEXT("{\"guid\":\"%s\",\"type\":\"%s\",\"name\":\"%s\",\"x\":%d,\"y\":%d,\"pins\":%s}"),
			*Node->NodeGuid.ToString(),
			*Node->GetClass()->GetName(),
			*Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString(),
			Node->NodePosX,
			Node->NodePosY,
			*PinList
		);
	}
	Result += TEXT("]");
	return Result;
}

// ─── AddWidgetToDesigner ──────────────────────────────────────────────────────

FString UPhotonBPLibrary::AddWidgetToDesigner(
	UBlueprint* WidgetBlueprint,
	FString WidgetClassName,
	FString WidgetName,
	int32 PosX,
	int32 PosY,
	int32 SizeX,
	int32 SizeY)
{
	if (!WidgetBlueprint) return TEXT("");

	// Must be a WidgetBlueprint
	UWidgetBlueprint* WBP = Cast<UWidgetBlueprint>(WidgetBlueprint);
	if (!WBP) return TEXT("");

	UWidgetTree* Tree = WBP->WidgetTree;
	if (!Tree) return TEXT("");

	// ── Resolve the widget class ──────────────────────────────────────────────
	// Try common UMG module paths
	UClass* WidgetClass = nullptr;
	TArray<FString> SearchPaths = {
		FString::Printf(TEXT("/Script/UMG.%s"), *WidgetClassName),
		FString::Printf(TEXT("/Script/UMG.U%s"), *WidgetClassName),
	};
	for (const FString& Path : SearchPaths)
	{
		WidgetClass = FindObject<UClass>(nullptr, *Path);
		if (!WidgetClass) WidgetClass = LoadObject<UClass>(nullptr, *Path);
		if (WidgetClass) break;
	}
	// Fallback: search all loaded classes by name
	if (!WidgetClass)
	{
		for (TObjectIterator<UClass> It; It; ++It)
		{
			FString ClsName = It->GetName();
			if (ClsName.Equals(WidgetClassName, ESearchCase::IgnoreCase) ||
				ClsName.Equals(FString(TEXT("U")) + WidgetClassName, ESearchCase::IgnoreCase))
			{
				if (It->IsChildOf(UWidget::StaticClass()))
				{
					WidgetClass = *It;
					break;
				}
			}
		}
	}
	if (!WidgetClass) return TEXT("");

	// ── Ensure a CanvasPanel root exists ─────────────────────────────────────
	UCanvasPanel* Canvas = nullptr;
	if (Tree->RootWidget)
	{
		Canvas = Cast<UCanvasPanel>(Tree->RootWidget);
	}
	if (!Canvas)
	{
		Canvas = Tree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("CanvasPanel_Root"));
		Tree->RootWidget = Canvas;
	}
	if (!Canvas) return TEXT("");

	// ── Create the new widget ─────────────────────────────────────────────────
	UWidget* NewWidget = Tree->ConstructWidget<UWidget>(WidgetClass, FName(*WidgetName));
	if (!NewWidget) return TEXT("");

	// ── Add to canvas and set position/size ──────────────────────────────────
	UCanvasPanelSlot* Slot = Canvas->AddChildToCanvas(NewWidget);
	if (Slot)
	{
		Slot->SetPosition(FVector2D(PosX, PosY));
		Slot->SetSize(FVector2D(SizeX, SizeY));
	}

	FBlueprintEditorUtils::MarkBlueprintAsModified(WBP);

	// Return a stable identifier: widget name + slot index
	int32 SlotIndex = Canvas->GetChildrenCount() - 1;
	return FString::Printf(TEXT("%s:%d"), *WidgetName, SlotIndex);
}


// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENT & INTERFACE
// ═══════════════════════════════════════════════════════════════════════════════

bool UPhotonBPLibrary::AddComponent(UBlueprint* Blueprint, UClass* ComponentClass, FName ComponentName)
{
	if (!Blueprint || !ComponentClass) return false;
	if (!Blueprint->SimpleConstructionScript) return false;
	USCS_Node* NewNode = Blueprint->SimpleConstructionScript->CreateNode(ComponentClass, ComponentName);
	if (!NewNode) return false;
	Blueprint->SimpleConstructionScript->AddNode(NewNode);
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	return true;
}

bool UPhotonBPLibrary::AddInterface(UBlueprint* Blueprint, UClass* InterfaceClass)
{
	if (!Blueprint || !InterfaceClass) return false;
	for (const FBPInterfaceDescription& Desc : Blueprint->ImplementedInterfaces)
	{
		if (Desc.Interface == InterfaceClass) return true;
	}
	FBPInterfaceDescription NewInterface;
	NewInterface.Interface = InterfaceClass;
	Blueprint->ImplementedInterfaces.Add(NewInterface);
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	return true;
}

// ═══════════════════════════════════════════════════════════════════════════════
// ENUM OPERATIONS
// ═══════════════════════════════════════════════════════════════════════════════

int32 UPhotonBPLibrary::EnumNumEnums(UUserDefinedEnum* Enum)
{
	if (!Enum) return 0;
	return Enum->NumEnums();
}

void UPhotonBPLibrary::EnumSetMetaData(UUserDefinedEnum* Enum, FName Key, FString Value)
{
	if (!Enum) return;
	Enum->SetMetaData(*Key.ToString(), *Value);
}

int32 UPhotonBPLibrary::EnumAddEntry(UUserDefinedEnum* Enum, FString EntryName)
{
	if (!Enum) return -1;
	int32 SlotIndex = Enum->NumEnums() - 1;
	FString DisplayKey = FString::Printf(TEXT("DisplayName_NewEnumerator%d"), SlotIndex);
	Enum->SetMetaData(*DisplayKey, *EntryName);
	Enum->MarkPackageDirty();
	return SlotIndex;
}

// ═══════════════════════════════════════════════════════════════════════════════
// DATATABLE OPERATIONS
// ═══════════════════════════════════════════════════════════════════════════════

FString UPhotonBPLibrary::DataTableToJsonString(UDataTable* DataTable)
{
	if (!DataTable) return TEXT("[]");
	return DataTable->GetTableAsJSON();
}

TArray<FName> UPhotonBPLibrary::DataTableGetRowNames(UDataTable* DataTable)
{
	if (!DataTable) return TArray<FName>();
	return DataTable->GetRowNames();
}

bool UPhotonBPLibrary::DataTableFillFromCsv(UDataTable* DataTable, FString CsvString)
{
	if (!DataTable) return false;
	TArray<FString> Errors = DataTable->CreateTableFromCSVString(CsvString);
	if (Errors.Num() > 0) return false;
	DataTable->MarkPackageDirty();
	return true;
}

// ═══════════════════════════════════════════════════════════════════════════════
// STRUCT FIELD ITERATION
// ═══════════════════════════════════════════════════════════════════════════════

FString UPhotonBPLibrary::StructGetFields(UUserDefinedStruct* Struct)
{
	if (!Struct) return TEXT("[]");
	FString Result = TEXT("[");
	bool bFirst = true;
	for (TFieldIterator<FProperty> It(Struct); It; ++It)
	{
		FProperty* Prop = *It;
		if (!bFirst) Result += TEXT(",");
		bFirst = false;
		Result += FString::Printf(TEXT("{\"name\":\"%s\",\"type\":\"%s\"}"),
			*Prop->GetName(), *Prop->GetCPPType());
	}
	Result += TEXT("]");
	return Result;
}

// ═══════════════════════════════════════════════════════════════════════════════
// ANIMATION BLUEPRINT
// ═══════════════════════════════════════════════════════════════════════════════

bool UPhotonBPLibrary::CompileAnimBlueprint(UBlueprint* AnimBlueprint)
{
	if (!AnimBlueprint) return false;
	FKismetEditorUtilities::CompileBlueprint(AnimBlueprint);
	return (AnimBlueprint->Status != BS_Error);
}

FString UPhotonBPLibrary::AddAnimGraphNode(UBlueprint* AnimBlueprint, FString NodeClassName, int32 NodeX, int32 NodeY)
{
	// Requires AnimationGraph editor module internals not exposed at this level.
	// Return empty — Python layer should fall back to manual approach.
	return TEXT("");
}

FString UPhotonBPLibrary::AddStateToStateMachine(UBlueprint* AnimBlueprint, FString StateMachineName, FString StateName, int32 NodeX, int32 NodeY)
{
	return TEXT("");
}

bool UPhotonBPLibrary::SetEntryState(UBlueprint* AnimBlueprint, FString StateMachineName, FString StateName)
{
	return false;
}

bool UPhotonBPLibrary::AddTransition(UBlueprint* AnimBlueprint, FString StateMachineName, FString FromState, FString ToState)
{
	return false;
}

bool UPhotonBPLibrary::SetStateAnimation(UBlueprint* AnimBlueprint, FString StateMachineName, FString StateName, FString AnimSequencePath)
{
	return false;
}

// ═══════════════════════════════════════════════════════════════════════════════
// MATERIAL
// ═══════════════════════════════════════════════════════════════════════════════

FString UPhotonBPLibrary::GetMaterialExpressions(UMaterial* Material)
{
	if (!Material) return TEXT("[]");
	FString Result = TEXT("[");
	bool bFirst = true;
	for (UMaterialExpression* Expr : Material->GetExpressions())
	{
		if (!Expr) continue;
		if (!bFirst) Result += TEXT(",");
		bFirst = false;
		Result += FString::Printf(
			TEXT("{\"type\":\"%s\",\"desc\":\"%s\",\"x\":%d,\"y\":%d}"),
			*Expr->GetClass()->GetName(),
			*Expr->Desc,
			Expr->MaterialExpressionEditorX,
			Expr->MaterialExpressionEditorY
		);
	}
	Result += TEXT("]");
	return Result;
}

// ═══════════════════════════════════════════════════════════════════════════════
// ENHANCED INPUT & PCG ASSET CREATION
// ═══════════════════════════════════════════════════════════════════════════════

static UObject* CreateAssetByClassName(FString AssetName, FString SavePath, FString ClassName, FString ScriptPath)
{
	IAssetTools& AssetTools = FModuleManager::LoadModuleChecked<FAssetToolsModule>("AssetTools").Get();
	UClass* AssetClass = LoadObject<UClass>(nullptr, *ScriptPath);
	if (!AssetClass) return nullptr;
	UObject* Asset = AssetTools.CreateAsset(AssetName, SavePath, AssetClass, nullptr);
	if (Asset)
	{
		TArray<UPackage*> Pkgs;
		Pkgs.Add(Asset->GetOutermost());
		FEditorFileUtils::PromptForCheckoutAndSave(Pkgs, false, false);
	}
	return Asset;
}

FString UPhotonBPLibrary::CreateInputAction(FString AssetName, FString SavePath)
{
	UObject* Asset = CreateAssetByClassName(AssetName, SavePath, TEXT("InputAction"), TEXT("/Script/EnhancedInput.InputAction"));
	if (!Asset) return TEXT("");
	return FString::Printf(TEXT("%s/%s.%s"), *SavePath, *AssetName, *AssetName);
}

FString UPhotonBPLibrary::CreateInputMappingContext(FString AssetName, FString SavePath)
{
	UObject* Asset = CreateAssetByClassName(AssetName, SavePath, TEXT("InputMappingContext"), TEXT("/Script/EnhancedInput.InputMappingContext"));
	if (!Asset) return TEXT("");
	return FString::Printf(TEXT("%s/%s.%s"), *SavePath, *AssetName, *AssetName);
}

FString UPhotonBPLibrary::CreatePCGGraph(FString AssetName, FString SavePath)
{
	UObject* Asset = CreateAssetByClassName(AssetName, SavePath, TEXT("PCGGraph"), TEXT("/Script/PCG.PCGGraph"));
	if (!Asset) return TEXT("");
	return FString::Printf(TEXT("%s/%s.%s"), *SavePath, *AssetName, *AssetName);
}
