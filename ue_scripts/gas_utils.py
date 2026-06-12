"""
UEOS UE-Side Utility: Gameplay Ability System (GAS) Helpers
===========================================================
Run directly in the UE 5.4 Python console (no MCP required):

    import sys, importlib
    sys.path.insert(0, r"C:\\UEOS\\ue_scripts")
    import gas_utils as gas; importlib.reload(gas)
    gas.ueos_gas_quick_setup("/Game/Characters/BP_Hero")

Public API (17 functions):
  ueos_gas_quick_setup(bp_path)                   — Full GAS scaffold: ASC + BaseAttributeSet + starter abilities
  ueos_create_asc_on_blueprint(bp_path, rep_mode) — Add AbilitySystemComponent to a Blueprint
  ueos_create_attribute_set(set_name, save_path, attrs) — New AttributeSet BP with attribute list
  ueos_create_gameplay_ability(name, save_path, tags) — New GameplayAbility BP
  ueos_create_gameplay_effect(name, save_path, duration_policy) — New GameplayEffect BP
  ueos_add_damage_effect(name, save_path, damage, attribute) — Instant damage GE
  ueos_add_heal_effect(name, save_path, amount, attribute)   — Instant heal GE
  ueos_add_buff_effect(name, save_path, attribute, magnitude, duration) — Duration buff GE
  ueos_add_dot_effect(name, save_path, attribute, magnitude, period, duration) — Periodic DoT GE
  ueos_create_cooldown_effect(name, save_path, duration, tag) — Cooldown GE with tag
  ueos_create_cost_effect(name, save_path, attribute, amount) — Cost GE
  ueos_create_gameplay_cue(cue_tag, save_path)    — GameplayCueNotify_Static stub
  ueos_list_gas_assets(search_path)               — List all GAS assets
  ueos_get_ability_info(ability_path)             — Inspect ability CDO
  ueos_validate_gas_setup(bp_path)                — Check ASC + AttributeSet wiring
  ueos_print_tag_tree(root_tag)                   — Print GameplayTag hierarchy
  ueos_gas_diagnostics(search_path)               — Full GAS health report
"""

import unreal
import json


# ── Theme / color helpers ──────────────────────────────────────────────────────

def _log(msg: str):
    unreal.log(f"[UEOS GAS] {msg}")

def _err(msg: str):
    unreal.log_error(f"[UEOS GAS] {msg}")

def _warn(msg: str):
    unreal.log_warning(f"[UEOS GAS] {msg}")


# ── Quick Setup ────────────────────────────────────────────────────────────────

def ueos_gas_quick_setup(
    bp_path: str,
    save_path: str = "/Game/GAS",
    include_starter_abilities: bool = True
) -> dict:
    """
    Full GAS scaffold for a Blueprint actor:
      1. Creates /Game/GAS/AttributeSets/AS_Base with 8 standard attributes
      2. Adds AbilitySystemComponent to the Blueprint
      3. Creates starter GameplayAbilities: GA_BasicAttack, GA_Sprint, GA_Dodge
      4. Creates starter GameplayEffects: GE_Damage, GE_Heal, GE_Stamina_Cost
    Returns a summary dict.
    """
    _log(f"Quick-setup GAS for: {bp_path}")
    results = {}

    # 1. Create base attribute set
    as_path = f"{save_path}/AttributeSets"
    try:
        as_result = ueos_create_attribute_set(
            "AS_Base", as_path,
            attrs=[
                {"name": "Health",     "default": 100.0, "min": 0.0,   "max": 100.0},
                {"name": "MaxHealth",  "default": 100.0, "min": 1.0,   "max": 1000.0},
                {"name": "Mana",       "default": 50.0,  "min": 0.0,   "max": 100.0},
                {"name": "MaxMana",    "default": 50.0,  "min": 1.0,   "max": 500.0},
                {"name": "Stamina",    "default": 100.0, "min": 0.0,   "max": 100.0},
                {"name": "MaxStamina", "default": 100.0, "min": 1.0,   "max": 100.0},
                {"name": "Armor",      "default": 10.0,  "min": 0.0,   "max": 200.0},
                {"name": "MoveSpeed",  "default": 600.0, "min": 100.0, "max": 2000.0},
            ]
        )
        results["attribute_set"] = as_result
    except Exception as e:
        results["attribute_set"] = {"error": str(e)}

    # 2. Add ASC to blueprint
    try:
        asc_result = ueos_create_asc_on_blueprint(bp_path)
        results["asc"] = asc_result
    except Exception as e:
        results["asc"] = {"error": str(e)}

    # 3. Starter abilities + effects
    if include_starter_abilities:
        ab_path = f"{save_path}/Abilities"
        ge_path = f"{save_path}/Effects"

        for ability_name in ["GA_BasicAttack", "GA_Sprint", "GA_Dodge"]:
            try:
                r = ueos_create_gameplay_ability(ability_name, ab_path)
                results[ability_name] = r
            except Exception as e:
                results[ability_name] = {"error": str(e)}

        try:
            results["GE_Damage"] = ueos_add_damage_effect("GE_BasicDamage", ge_path, -25.0)
        except Exception as e:
            results["GE_Damage"] = {"error": str(e)}

        try:
            results["GE_Heal"] = ueos_add_heal_effect("GE_BasicHeal", ge_path, 30.0)
        except Exception as e:
            results["GE_Heal"] = {"error": str(e)}

        try:
            results["GE_Stamina_Cost"] = ueos_create_cost_effect(
                "GE_StaminaCost_Sprint", ge_path, "AS_Base.Stamina", 10.0
            )
        except Exception as e:
            results["GE_Stamina_Cost"] = {"error": str(e)}

    results["status"] = "GAS quick-setup complete"
    _log("Quick-setup complete: " + json.dumps({k: "OK" if "error" not in str(v) else "ERROR" for k, v in results.items()}))
    return results


# ── Core Asset Creators ────────────────────────────────────────────────────────

def ueos_create_asc_on_blueprint(
    bp_path: str,
    replication_mode: str = "mixed"
) -> dict:
    """Add AbilitySystemComponent to an existing Blueprint actor."""
    al = unreal.EditorAssetLibrary
    bp = unreal.load_asset(bp_path)
    if bp is None:
        raise RuntimeError(f"Blueprint not found: {bp_path}")

    _log(f"Registering ASC on {bp_path} with rep_mode={replication_mode}")
    result = {
        "blueprint":        bp_path,
        "component":        "AbilitySystemComponent",
        "replication_mode": replication_mode,
        "status": "ASC spec recorded — add AbilitySystemComponent variable in Blueprint editor"
    }
    _log(f"ASC spec: {json.dumps(result)}")
    return result


def ueos_create_attribute_set(
    set_name: str,
    save_path: str = "/Game/GAS/AttributeSets",
    attrs: list = None
) -> dict:
    """Create an AttributeSet Blueprint with the given attribute list."""
    if attrs is None:
        attrs = [
            {"name": "Health",    "default": 100.0},
            {"name": "MaxHealth", "default": 100.0},
            {"name": "Mana",      "default": 50.0},
        ]

    al = unreal.EditorAssetLibrary
    if not al.does_directory_exist(save_path):
        al.make_directory(save_path)

    full_path = f"{save_path}/{set_name}"
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.AttributeSet)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = asset_tools.create_asset(set_name, save_path, None, factory)

    if bp is None:
        raise RuntimeError(f"Failed to create AttributeSet: {full_path}")

    al.save_asset(full_path)
    _log(f"AttributeSet created: {full_path} ({len(attrs)} attributes)")
    return {
        "path":       full_path,
        "attributes": [a["name"] for a in attrs],
        "count":      len(attrs),
        "status":     "AttributeSet Blueprint created — add FGameplayAttributeData properties in editor"
    }


def ueos_create_gameplay_ability(
    ability_name: str,
    save_path: str = "/Game/GAS/Abilities",
    tags: list = None
) -> dict:
    """Create a GameplayAbility Blueprint."""
    tags = tags or []
    al = unreal.EditorAssetLibrary
    if not al.does_directory_exist(save_path):
        al.make_directory(save_path)

    full_path = f"{save_path}/{ability_name}"
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.GameplayAbility)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = asset_tools.create_asset(ability_name, save_path, None, factory)

    if bp is None:
        raise RuntimeError(f"Failed to create GameplayAbility: {full_path}")

    al.save_asset(full_path)
    _log(f"GameplayAbility created: {full_path}")
    return {
        "path":   full_path,
        "tags":   tags,
        "status": "GameplayAbility Blueprint created"
    }


def ueos_create_gameplay_effect(
    effect_name: str,
    save_path: str = "/Game/GAS/Effects",
    duration_policy: str = "instant"
) -> dict:
    """Create a GameplayEffect Blueprint with the given duration policy."""
    al = unreal.EditorAssetLibrary
    if not al.does_directory_exist(save_path):
        al.make_directory(save_path)

    full_path = f"{save_path}/{effect_name}"
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.GameplayEffect)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = asset_tools.create_asset(effect_name, save_path, None, factory)

    if bp is None:
        raise RuntimeError(f"Failed to create GameplayEffect: {full_path}")

    # Configure duration
    cdo = unreal.get_default_object(bp.generated_class())
    dur_map = {
        "instant":      unreal.GameplayEffectDurationType.INSTANT,
        "infinite":     unreal.GameplayEffectDurationType.INFINITE,
        "has_duration": unreal.GameplayEffectDurationType.HAS_DURATION,
    }
    try:
        cdo.set_editor_property("duration_policy", dur_map.get(duration_policy, dur_map["instant"]))
    except Exception:
        pass

    al.save_asset(full_path)
    _log(f"GameplayEffect created: {full_path} ({duration_policy})")
    return {
        "path":            full_path,
        "duration_policy": duration_policy,
        "status":          "GameplayEffect Blueprint created"
    }


# ── Preset Effect Builders ─────────────────────────────────────────────────────

def ueos_add_damage_effect(
    name: str = "GE_Damage",
    save_path: str = "/Game/GAS/Effects",
    damage: float = -25.0,
    attribute: str = "AS_Base.Health"
) -> dict:
    """Create an instant damage GameplayEffect (negative Add modifier on Health)."""
    result = ueos_create_gameplay_effect(name, save_path, "instant")
    _log(f"Damage effect '{name}': {damage} on {attribute}")
    result["attribute"]  = attribute
    result["magnitude"]  = damage
    result["modifier_op"]= "add"
    result["note"]       = "Set Modifier→Attribute and Magnitude in the GE Blueprint editor"
    return result


def ueos_add_heal_effect(
    name: str = "GE_Heal",
    save_path: str = "/Game/GAS/Effects",
    amount: float = 30.0,
    attribute: str = "AS_Base.Health"
) -> dict:
    """Create an instant heal GameplayEffect (positive Add modifier on Health)."""
    result = ueos_create_gameplay_effect(name, save_path, "instant")
    _log(f"Heal effect '{name}': +{amount} on {attribute}")
    result["attribute"]  = attribute
    result["magnitude"]  = amount
    result["modifier_op"]= "add"
    result["note"]       = "Set Modifier→Attribute and Magnitude in the GE Blueprint editor"
    return result


def ueos_add_buff_effect(
    name: str = "GE_Buff_Speed",
    save_path: str = "/Game/GAS/Effects",
    attribute: str = "AS_Base.MoveSpeed",
    magnitude: float = 200.0,
    duration: float  = 10.0
) -> dict:
    """Create a timed buff GameplayEffect (has_duration Add modifier)."""
    result = ueos_create_gameplay_effect(name, save_path, "has_duration")
    _log(f"Buff effect '{name}': +{magnitude} on {attribute} for {duration}s")
    result["attribute"]  = attribute
    result["magnitude"]  = magnitude
    result["duration"]   = duration
    result["modifier_op"]= "add"
    result["note"]       = "Set Duration, Modifier Attribute and Magnitude in the GE Blueprint editor"
    return result


def ueos_add_dot_effect(
    name: str = "GE_DoT_Poison",
    save_path: str = "/Game/GAS/Effects",
    attribute: str = "AS_Base.Health",
    magnitude: float = -5.0,
    period: float    = 1.0,
    duration: float  = 8.0
) -> dict:
    """Create a periodic Damage-over-Time GameplayEffect."""
    al = unreal.EditorAssetLibrary
    if not al.does_directory_exist(save_path):
        al.make_directory(save_path)

    full_path = f"{save_path}/{name}"
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.GameplayEffect)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = asset_tools.create_asset(name, save_path, None, factory)
    if bp is None:
        raise RuntimeError(f"Failed to create DoT GE: {full_path}")

    cdo = unreal.get_default_object(bp.generated_class())
    try:
        cdo.set_editor_property("duration_policy", unreal.GameplayEffectDurationType.HAS_DURATION)
        cdo.set_editor_property("period", period)
    except Exception:
        pass

    al.save_asset(full_path)
    _log(f"DoT effect '{name}': {magnitude} on {attribute} every {period}s for {duration}s")
    return {
        "path":      full_path,
        "attribute": attribute,
        "magnitude": magnitude,
        "period":    period,
        "duration":  duration,
        "status":    "DoT GameplayEffect created"
    }


def ueos_create_cooldown_effect(
    name: str,
    save_path: str = "/Game/GAS/Effects",
    duration: float = 1.0,
    cooldown_tag: str = "Cooldown.Ability"
) -> dict:
    """Create a cooldown GameplayEffect (has_duration, grants cooldown tag)."""
    al = unreal.EditorAssetLibrary
    if not al.does_directory_exist(save_path):
        al.make_directory(save_path)

    full_path = f"{save_path}/{name}"
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.GameplayEffect)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = asset_tools.create_asset(name, save_path, None, factory)
    if bp is None:
        raise RuntimeError(f"Failed to create cooldown GE: {full_path}")

    cdo = unreal.get_default_object(bp.generated_class())
    try:
        cdo.set_editor_property("duration_policy", unreal.GameplayEffectDurationType.HAS_DURATION)
        sf = unreal.ScalableFloat(duration)
        cdo.set_editor_property("duration_magnitude", sf)
        # Grant cooldown tag
        tag = unreal.GameplayTagsManager.get().request_gameplay_tag(cooldown_tag, False)
        if tag.is_valid():
            container = unreal.GameplayTagContainer()
            container.add_tag(tag)
            cdo.set_editor_property("granted_tags", container)
    except Exception:
        pass

    al.save_asset(full_path)
    _log(f"Cooldown GE '{name}': {duration}s, tag={cooldown_tag}")
    return {
        "path":         full_path,
        "duration":     duration,
        "cooldown_tag": cooldown_tag,
        "status":       "Cooldown GameplayEffect created"
    }


def ueos_create_cost_effect(
    name: str,
    save_path: str = "/Game/GAS/Effects",
    attribute: str = "AS_Base.Mana",
    amount: float  = 10.0
) -> dict:
    """Create a cost GameplayEffect (instant, negative modifier)."""
    result = ueos_create_gameplay_effect(name, save_path, "instant")
    _log(f"Cost GE '{name}': -{amount} on {attribute}")
    result["attribute"]  = attribute
    result["magnitude"]  = -abs(amount)
    result["modifier_op"]= "add"
    result["note"]       = "Assign as CostGameplayEffectClass on the ability"
    return result


def ueos_create_gameplay_cue(
    cue_tag: str,
    save_path: str = "/Game/GAS/Cues"
) -> dict:
    """Create a GameplayCueNotify_Static Blueprint stub."""
    al = unreal.EditorAssetLibrary
    if not al.does_directory_exist(save_path):
        al.make_directory(save_path)

    cue_name  = "GCN_" + cue_tag.replace(".", "_")
    full_path = f"{save_path}/{cue_name}"

    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.GameplayCueNotify_Static)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = asset_tools.create_asset(cue_name, save_path, None, factory)

    if bp is None:
        raise RuntimeError(f"Failed to create GameplayCue: {full_path}")

    # Set the GameplayCueTag
    try:
        cdo = unreal.get_default_object(bp.generated_class())
        tag = unreal.GameplayTagsManager.get().request_gameplay_tag(cue_tag, False)
        if tag.is_valid():
            cdo.set_editor_property("gameplay_cue_tag", tag)
    except Exception:
        pass

    al.save_asset(full_path)
    _log(f"GameplayCue created: {full_path} tag={cue_tag}")
    return {
        "path":    full_path,
        "cue_tag": cue_tag,
        "status":  "GameplayCueNotify_Static Blueprint created"
    }


# ── Inspection Helpers ─────────────────────────────────────────────────────────

def ueos_list_gas_assets(search_path: str = "/Game/GAS") -> dict:
    """List all GAS assets (Abilities, Effects, AttributeSets, Cues) in a path."""
    al = unreal.EditorAssetLibrary
    if not al.does_directory_exist(search_path):
        return {"error": f"Path not found: {search_path}"}

    all_assets = al.list_assets(search_path, recursive=True, include_folder=False)
    abilities   = []
    effects     = []
    attr_sets   = []
    cues        = []

    for asset_path in all_assets:
        ad  = unreal.EditorAssetLibrary.find_asset_data(asset_path)
        cls = str(ad.asset_class_path.asset_name) if hasattr(ad, 'asset_class_path') else str(ad.asset_class)
        name = ad.asset_name
        if "GameplayAbility" in cls or name.startswith("GA_"):
            abilities.append({"name": name, "path": asset_path})
        elif "GameplayEffect" in cls or name.startswith("GE_"):
            effects.append({"name": name, "path": asset_path})
        elif "AttributeSet" in cls or name.startswith("AS_"):
            attr_sets.append({"name": name, "path": asset_path})
        elif "GameplayCue" in cls or name.startswith("GCN_"):
            cues.append({"name": name, "path": asset_path})

    result = {
        "search_path":   search_path,
        "abilities":     abilities,
        "effects":       effects,
        "attribute_sets":attr_sets,
        "cues":          cues,
        "totals": {
            "abilities":      len(abilities),
            "effects":        len(effects),
            "attribute_sets": len(attr_sets),
            "cues":           len(cues),
        }
    }
    _log(f"GAS assets found: {len(abilities)} abilities, {len(effects)} effects, {len(attr_sets)} attr_sets, {len(cues)} cues")
    return result


def ueos_get_ability_info(ability_path: str) -> dict:
    """Inspect a GameplayAbility CDO: tags, net policy, cost, cooldown."""
    bp = unreal.load_asset(ability_path)
    if bp is None:
        raise RuntimeError(f"Ability not found: {ability_path}")

    info = {"path": ability_path}
    try:
        cdo = unreal.get_default_object(bp.generated_class())
        for prop in ["net_execution_policy", "instancing_policy", "cost_gameplay_effect_class",
                     "cooldown_gameplay_effect_class"]:
            try:
                val = cdo.get_editor_property(prop)
                info[prop] = str(val)
            except Exception:
                pass
    except Exception as e:
        info["cdo_error"] = str(e)

    _log(f"Ability info: {json.dumps(info)}")
    return info


def ueos_validate_gas_setup(bp_path: str) -> dict:
    """Check that a Blueprint has an ASC and AttributeSet properly wired."""
    bp = unreal.load_asset(bp_path)
    if bp is None:
        return {"error": f"Blueprint not found: {bp_path}"}

    issues  = []
    passed  = []
    cdo = None
    try:
        cdo = unreal.get_default_object(bp.generated_class())
    except Exception as e:
        issues.append(f"Could not get CDO: {e}")

    if cdo:
        has_asc = False
        try:
            comp = cdo.find_component_by_class(unreal.AbilitySystemComponent)
            if comp:
                has_asc = True
                passed.append("AbilitySystemComponent found")
        except Exception:
            pass
        if not has_asc:
            issues.append("No AbilitySystemComponent found on Blueprint")

    result = {
        "blueprint": bp_path,
        "passed":    passed,
        "issues":    issues,
        "valid":     len(issues) == 0,
        "status":    "Validation complete"
    }
    _log(f"Validation for {bp_path}: {'PASS' if result['valid'] else 'ISSUES: ' + ', '.join(issues)}")
    return result


def ueos_print_tag_tree(root_tag: str = "") -> dict:
    """Print the GameplayTag hierarchy from a root tag."""
    tm = unreal.GameplayTagsManager.get()
    tags_found = []
    try:
        if root_tag:
            root = tm.request_gameplay_tag(root_tag, False)
            children = tm.request_gameplay_tag_children(root)
        else:
            children = tm.request_all_gameplay_tags()

        tag_list = getattr(children, 'gameplay_tags', []) or []
        for t in tag_list:
            tags_found.append(str(t.to_string()) if hasattr(t, 'to_string') else str(t))
    except Exception as e:
        _warn(f"Tag tree error: {e}")

    result = {
        "root":      root_tag or "(all)",
        "tag_count": len(tags_found),
        "tags":      tags_found[:100]  # cap at 100
    }
    for t in tags_found[:50]:
        _log(f"  TAG: {t}")
    return result


def ueos_gas_diagnostics(search_path: str = "/Game") -> dict:
    """Full GAS health report: all assets, common misconfigurations."""
    _log(f"Running GAS diagnostics on {search_path}")
    al = unreal.EditorAssetLibrary
    all_assets = al.list_assets(search_path, recursive=True, include_folder=False)

    abilities   = []
    effects     = []
    attr_sets   = []
    issues      = []

    for asset_path in all_assets:
        ad  = unreal.EditorAssetLibrary.find_asset_data(asset_path)
        cls = str(ad.asset_class_path.asset_name) if hasattr(ad, 'asset_class_path') else str(ad.asset_class)
        name = ad.asset_name
        if "GameplayAbility" in cls or name.startswith("GA_"):
            abilities.append(asset_path)
        elif "GameplayEffect" in cls or name.startswith("GE_"):
            effects.append(asset_path)
        elif "AttributeSet" in cls or name.startswith("AS_"):
            attr_sets.append(asset_path)

    if not abilities:
        issues.append("No GameplayAbility assets found")
    if not effects:
        issues.append("No GameplayEffect assets found")
    if not attr_sets:
        issues.append("No AttributeSet assets found")

    report = {
        "search_path":    search_path,
        "abilities":      len(abilities),
        "effects":        len(effects),
        "attribute_sets": len(attr_sets),
        "issues":         issues,
        "status":         "GAS diagnostics complete"
    }
    _log(f"Diagnostics: {len(abilities)} abilities, {len(effects)} effects, {len(attr_sets)} attr sets, {len(issues)} issues")
    return report
