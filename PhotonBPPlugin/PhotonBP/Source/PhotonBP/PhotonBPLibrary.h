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

	/**
	 * Add a member variable to a Blueprint.
	 * @param Blueprint		The Blueprint asset to modify
	 * @param VarName		Name of the new variable
	 * @param PinCategory	"bool", "int", "int64", "real", "string", "name", "text", "object", "struct"
	 * @param PinSubCategory	For "real": "float" or "double". Otherwise empty.
	 * @param PinSubCategoryObjectPath	For object/struct: full path e.g. "/Script/Engine.Actor"
	 * @return True if the variable was added successfully
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP")
	static bool AddMemberVariable(
		UBlueprint* Blueprint,
		FName VarName,
		FString PinCategory,
		FString PinSubCategory,
		FString PinSubCategoryObjectPath
	);

	/**
	 * Add an Event Dispatcher to a Blueprint.
	 * @param Blueprint		The Blueprint asset to modify
	 * @param DispatcherName	Name of the dispatcher
	 * @return True if added successfully
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP")
	static bool AddEventDispatcher(
		UBlueprint* Blueprint,
		FName DispatcherName
	);

	/**
	 * Add a Custom Event node to a Blueprint's Event Graph.
	 * @param Blueprint		The Blueprint asset to modify
	 * @param EventName		Name of the custom event
	 * @return True if added successfully
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP")
	static bool AddCustomEvent(
		UBlueprint* Blueprint,
		FName EventName
	);

	/**
	 * Set a variable's instance editable and expose on spawn flags.
	 * @param Blueprint		The Blueprint asset
	 * @param VarName		Variable name
	 * @param bInstanceEditable		Show in Details panel
	 * @param bExposeOnSpawn		Show on spawn node
	 */
	UFUNCTION(BlueprintCallable, Category = "PhotonBP")
	static bool SetVariableFlags(
		UBlueprint* Blueprint,
		FName VarName,
		bool bInstanceEditable,
		bool bExposeOnSpawn
	);
};
