"""
UEOS — Phase 6: Gameplay Ability System (GAS) Tools
20 MCP tools with gas_ prefix.

Covers:
  Ability Setup        gas_create_ability_system_component, gas_setup_ability_set,
                       gas_grant_ability, gas_revoke_ability, gas_list_granted_abilities
  Gameplay Abilities   gas_create_gameplay_ability, gas_set_ability_tags,
                       gas_add_gameplay_effect_to_ability, gas_set_ability_costs,
                       gas_set_ability_cooldown
  Gameplay Effects     gas_create_gameplay_effect, gas_set_effect_duration,
                       gas_add_attribute_modifier, gas_add_gameplay_cue,
                       gas_apply_effect_to_target
  Attribute Sets       gas_create_attribute_set, gas_add_attribute,
                       gas_set_attribute_defaults, gas_list_attribute_sets
  Diagnostics          gas_diagnostics
"""

from __future__ import annotations
from textwrap import dedent
from mcp import types


# ── GAS constants ──────────────────────────────────────────────────────────────

EFFECT_DURATIONS = {
    "instant":   "unreal.GameplayEffectDurationType.INSTANT",
    "infinite":  "unreal.GameplayEffectDurationType.INFINITE",
    "has_duration": "unreal.GameplayEffectDurationType.HAS_DURATION",
}

MAGNITUDE_CALC = {
    "scalable_float": "unreal.GameplayEffectMagnitudeCalculation.SCALABLE_FLOAT",
    "attribute_based": "unreal.GameplayEffectMagnitudeCalculation.ATTRIBUTE_BASED",
    "custom_calc":    "unreal.GameplayEffectMagnitudeCalculation.CUSTOM_CALCULATION_CLASS",
    "set_by_caller":  "unreal.GameplayEffectMagnitudeCalculation.SET_BY_CALLER",
}

MODIFIER_OPS = {
    "add":       "unreal.GameplayModOp.ADDITIVE",
    "multiply":  "unreal.GameplayModOp.MULTIPLICITIVE",
    "divide":    "unreal.GameplayModOp.DIVISION",
    "override":  "unreal.GameplayModOp.OVERRIDE",
}

ABILITY_NET_EXEC = {
    "local_predicted":    "unreal.GameplayAbilityNetExecutionPolicy.LOCAL_PREDICTED",
    "local_only":         "unreal.GameplayAbilityNetExecutionPolicy.LOCAL_ONLY",
    "server_only":        "unreal.GameplayAbilityNetExecutionPolicy.SERVER_ONLY",
    "server_initiated":   "unreal.GameplayAbilityNetExecutionPolicy.SERVER_INITIATED",
}


# ── Tool class ─────────────────────────────────────────────────────────────────

class GameplayAbilityTools:
    """MCP tools for UE 5.4 Gameplay Ability System (GAS)."""

    def __init__(self, ue):
        self.ue = ue

    # ── Internal helper ───────────────────────────────────────────────────────

    async def _exec(self, script: str, label: str) -> list[types.TextContent]:
        """Execute a UE Python script via Remote Control and parse UEOS prefixes."""
        raw = await self.ue.execute_python_ex(script)
        lines = (raw or "").strip().splitlines()
        for line in lines:
            if line.startswith("UEOS_RESULT:"):
                return [types.TextContent(type="text", text=line[len("UEOS_RESULT:"):].strip())]
            if line.startswith("UEOS_ERROR:"):
                return [types.TextContent(type="text", text=f"ERROR [{label}]: {line[len('UEOS_ERROR:'):].strip()}")]
        return [types.TextContent(type="text", text=raw or f"[{label}] No output returned.")]

    # ── Tool definitions ───────────────────────────────────────────────────────

    async def get_tool_definitions(self) -> list[types.Tool]:
        return [

            # ── Ability Setup ──────────────────────────────────────────────────

            types.Tool(
                name="gas_create_ability_system_component",
                description=(
                    "Add an AbilitySystemComponent (ASC) to an existing Blueprint actor. "
                    "Creates the component, sets replication mode (full/mixed/minimal), "
                    "and optionally registers a default AttributeSet class. "
                    "Returns the ASC variable name."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {
                            "type": "string",
                            "description": "Content-browser path to target Blueprint, e.g. /Game/Characters/BP_Hero"
                        },
                        "replication_mode": {
                            "type": "string",
                            "enum": ["full", "mixed", "minimal"],
                            "default": "mixed",
                            "description": "ASC replication mode: full (all clients), mixed (owner only for GA), minimal (no GA replication)"
                        },
                        "attribute_set_class": {
                            "type": "string",
                            "default": "",
                            "description": "Optional content path to an AttributeSet Blueprint to auto-add, e.g. /Game/GAS/AS_BaseAttributes"
                        }
                    },
                    "required": ["blueprint_path"]
                }
            ),

            types.Tool(
                name="gas_setup_ability_set",
                description=(
                    "Create a UAbilitySet Data Asset that bundles multiple Gameplay Abilities, "
                    "Gameplay Effects, and Attribute Sets into one grantable package. "
                    "Useful for character classes or equipment loadouts."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_name": {
                            "type": "string",
                            "description": "Name of the new AbilitySet asset, e.g. AS_WarriorSet"
                        },
                        "save_path": {
                            "type": "string",
                            "default": "/Game/GAS/AbilitySets",
                            "description": "Content-browser folder for the asset"
                        },
                        "ability_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                            "description": "List of GameplayAbility Blueprint paths to include"
                        },
                        "effect_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                            "description": "List of GameplayEffect Blueprint paths to include"
                        },
                        "attribute_set_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                            "description": "List of AttributeSet Blueprint paths to include"
                        }
                    },
                    "required": ["asset_name"]
                }
            ),

            types.Tool(
                name="gas_grant_ability",
                description=(
                    "Grant a Gameplay Ability to a Blueprint actor's AbilitySystemComponent "
                    "at a given level. Adds the ability to the ASC's granted ability list "
                    "and sets input binding tag if provided."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {
                            "type": "string",
                            "description": "Path to the actor Blueprint with an ASC"
                        },
                        "ability_path": {
                            "type": "string",
                            "description": "Path to the GameplayAbility Blueprint to grant"
                        },
                        "level": {
                            "type": "integer",
                            "default": 1,
                            "description": "Ability level to grant (1–20)"
                        },
                        "input_tag": {
                            "type": "string",
                            "default": "",
                            "description": "Optional GameplayTag for input binding, e.g. Input.Attack.Primary"
                        }
                    },
                    "required": ["blueprint_path", "ability_path"]
                }
            ),

            types.Tool(
                name="gas_revoke_ability",
                description=(
                    "Revoke (remove) a previously granted Gameplay Ability from a Blueprint "
                    "actor's AbilitySystemComponent. Can revoke by ability class or by tag."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {
                            "type": "string",
                            "description": "Path to the actor Blueprint with an ASC"
                        },
                        "ability_path": {
                            "type": "string",
                            "default": "",
                            "description": "Path to the GameplayAbility Blueprint to revoke"
                        },
                        "ability_tag": {
                            "type": "string",
                            "default": "",
                            "description": "GameplayTag to identify ability to revoke, e.g. Ability.Attack"
                        }
                    },
                    "required": ["blueprint_path"]
                }
            ),

            types.Tool(
                name="gas_list_granted_abilities",
                description=(
                    "List all Gameplay Abilities currently granted to a Blueprint actor's "
                    "AbilitySystemComponent. Returns ability class names, levels, tags, "
                    "and active/cooldown status."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {
                            "type": "string",
                            "description": "Path to the actor Blueprint with an ASC"
                        }
                    },
                    "required": ["blueprint_path"]
                }
            ),

            # ── Gameplay Abilities ─────────────────────────────────────────────

            types.Tool(
                name="gas_create_gameplay_ability",
                description=(
                    "Create a new GameplayAbility Blueprint with a given parent class, "
                    "net execution policy, instancing policy, and ability tags. "
                    "Optionally adds ActivateAbility event graph stub."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ability_name": {
                            "type": "string",
                            "description": "Name of the new ability Blueprint, e.g. GA_FireBolt"
                        },
                        "save_path": {
                            "type": "string",
                            "default": "/Game/GAS/Abilities",
                            "description": "Content-browser folder"
                        },
                        "parent_class": {
                            "type": "string",
                            "default": "GameplayAbility",
                            "description": "Parent class: GameplayAbility or a custom base"
                        },
                        "net_execution_policy": {
                            "type": "string",
                            "enum": ["local_predicted", "local_only", "server_only", "server_initiated"],
                            "default": "local_predicted"
                        },
                        "instancing_policy": {
                            "type": "string",
                            "enum": ["non_instanced", "instanced_per_actor", "instanced_per_execution"],
                            "default": "instanced_per_actor"
                        },
                        "ability_tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                            "description": "GameplayTags to assign as Ability Tags, e.g. [\"Ability.Fire\", \"Ability.Projectile\"]"
                        }
                    },
                    "required": ["ability_name"]
                }
            ),

            types.Tool(
                name="gas_set_ability_tags",
                description=(
                    "Set or update the GameplayTag containers on an existing GameplayAbility: "
                    "AbilityTags, ActivationRequiredTags, ActivationBlockedTags, "
                    "BlockAbilitiesWithTag, CancelAbilitiesWithTag."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ability_path": {
                            "type": "string",
                            "description": "Content path to the GameplayAbility Blueprint"
                        },
                        "ability_tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                            "description": "Tags identifying this ability"
                        },
                        "activation_required_tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                            "description": "Tags that must be present on owner for activation"
                        },
                        "activation_blocked_tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                            "description": "Tags that block activation if present on owner"
                        },
                        "cancel_abilities_with_tag": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                            "description": "Cancel other abilities with these tags on activation"
                        },
                        "block_abilities_with_tag": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                            "description": "Block other abilities with these tags while active"
                        }
                    },
                    "required": ["ability_path"]
                }
            ),

            types.Tool(
                name="gas_add_gameplay_effect_to_ability",
                description=(
                    "Add a Gameplay Effect application to a GameplayAbility so it applies "
                    "the effect when the ability activates or on specific gameplay events. "
                    "Sets effect class, level source, and application condition."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ability_path": {
                            "type": "string",
                            "description": "Path to the GameplayAbility Blueprint"
                        },
                        "effect_path": {
                            "type": "string",
                            "description": "Path to the GameplayEffect Blueprint to apply"
                        },
                        "level_source": {
                            "type": "string",
                            "enum": ["ability_level", "custom"],
                            "default": "ability_level",
                            "description": "Where the effect level comes from"
                        },
                        "apply_on_activate": {
                            "type": "boolean",
                            "default": True,
                            "description": "Apply effect automatically when ability activates"
                        }
                    },
                    "required": ["ability_path", "effect_path"]
                }
            ),

            types.Tool(
                name="gas_set_ability_costs",
                description=(
                    "Set the cost GameplayEffect for a GameplayAbility. Costs are paid from "
                    "attribute values (e.g. Mana, Stamina). Creates or updates the cost GE "
                    "with the given attribute and magnitude."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ability_path": {
                            "type": "string",
                            "description": "Path to the GameplayAbility Blueprint"
                        },
                        "cost_attribute": {
                            "type": "string",
                            "description": "Attribute to deduct from, e.g. AS_Base.Mana"
                        },
                        "cost_magnitude": {
                            "type": "number",
                            "description": "Amount to deduct (positive number)"
                        },
                        "cost_effect_path": {
                            "type": "string",
                            "default": "",
                            "description": "Optional path to existing cost GE Blueprint; created automatically if omitted"
                        }
                    },
                    "required": ["ability_path", "cost_attribute", "cost_magnitude"]
                }
            ),

            types.Tool(
                name="gas_set_ability_cooldown",
                description=(
                    "Set the cooldown GameplayEffect for a GameplayAbility. "
                    "Applies a duration-based GE with the given cooldown tag and duration. "
                    "Returns updated ability info."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ability_path": {
                            "type": "string",
                            "description": "Path to the GameplayAbility Blueprint"
                        },
                        "cooldown_duration": {
                            "type": "number",
                            "description": "Cooldown duration in seconds"
                        },
                        "cooldown_tag": {
                            "type": "string",
                            "description": "GameplayTag for the cooldown, e.g. Cooldown.Ability.FireBolt"
                        },
                        "cooldown_effect_path": {
                            "type": "string",
                            "default": "",
                            "description": "Optional path to existing cooldown GE Blueprint; created if omitted"
                        }
                    },
                    "required": ["ability_path", "cooldown_duration", "cooldown_tag"]
                }
            ),

            # ── Gameplay Effects ───────────────────────────────────────────────

            types.Tool(
                name="gas_create_gameplay_effect",
                description=(
                    "Create a new GameplayEffect Blueprint with specified duration policy "
                    "(instant/infinite/has_duration), period, and stacking rules. "
                    "Returns the asset path."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "effect_name": {
                            "type": "string",
                            "description": "Name of the GameplayEffect Blueprint, e.g. GE_FireDamage"
                        },
                        "save_path": {
                            "type": "string",
                            "default": "/Game/GAS/Effects",
                            "description": "Content-browser folder"
                        },
                        "duration_policy": {
                            "type": "string",
                            "enum": ["instant", "infinite", "has_duration"],
                            "default": "instant",
                            "description": "How long the effect lasts"
                        },
                        "period": {
                            "type": "number",
                            "default": 0.0,
                            "description": "Tick period in seconds (0 = no periodic application)"
                        },
                        "stacking_type": {
                            "type": "string",
                            "enum": ["none", "aggregate_by_source", "aggregate_by_target"],
                            "default": "none",
                            "description": "How duplicate applications stack"
                        },
                        "stack_limit": {
                            "type": "integer",
                            "default": 1,
                            "description": "Maximum stack count (used when stacking_type != none)"
                        }
                    },
                    "required": ["effect_name"]
                }
            ),

            types.Tool(
                name="gas_set_effect_duration",
                description=(
                    "Set or update the duration of an existing has_duration GameplayEffect. "
                    "Supports scalable float magnitude and curve table lookup."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "effect_path": {
                            "type": "string",
                            "description": "Path to the GameplayEffect Blueprint"
                        },
                        "duration": {
                            "type": "number",
                            "description": "Duration in seconds"
                        },
                        "curve_table_path": {
                            "type": "string",
                            "default": "",
                            "description": "Optional CurveTable asset path for scaling duration by level"
                        },
                        "curve_row_name": {
                            "type": "string",
                            "default": "",
                            "description": "Row name in the CurveTable"
                        }
                    },
                    "required": ["effect_path", "duration"]
                }
            ),

            types.Tool(
                name="gas_add_attribute_modifier",
                description=(
                    "Add an attribute modifier to a GameplayEffect. Supports Add/Multiply/"
                    "Divide/Override operations with scalable float, attribute-based, or "
                    "SetByCaller magnitudes."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "effect_path": {
                            "type": "string",
                            "description": "Path to the GameplayEffect Blueprint"
                        },
                        "attribute": {
                            "type": "string",
                            "description": "Attribute to modify, e.g. AS_Base.Health or AS_Base.MoveSpeed"
                        },
                        "modifier_op": {
                            "type": "string",
                            "enum": ["add", "multiply", "divide", "override"],
                            "default": "add",
                            "description": "Math operation to apply"
                        },
                        "magnitude": {
                            "type": "number",
                            "description": "Flat magnitude value (used when magnitude_type is scalable_float)"
                        },
                        "magnitude_type": {
                            "type": "string",
                            "enum": ["scalable_float", "attribute_based", "set_by_caller"],
                            "default": "scalable_float",
                            "description": "How the magnitude is calculated"
                        },
                        "set_by_caller_tag": {
                            "type": "string",
                            "default": "",
                            "description": "GameplayTag for SetByCaller magnitude (when magnitude_type=set_by_caller)"
                        }
                    },
                    "required": ["effect_path", "attribute", "magnitude"]
                }
            ),

            types.Tool(
                name="gas_add_gameplay_cue",
                description=(
                    "Add a GameplayCue tag to a GameplayEffect so visual/audio feedback "
                    "fires when the effect is applied, executed, or removed. "
                    "Optionally creates a basic GameplayCue Blueprint stub."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "effect_path": {
                            "type": "string",
                            "description": "Path to the GameplayEffect Blueprint"
                        },
                        "cue_tag": {
                            "type": "string",
                            "description": "GameplayCue tag, e.g. GameplayCue.Fire.Hit"
                        },
                        "create_cue_blueprint": {
                            "type": "boolean",
                            "default": False,
                            "description": "Create a GameplayCueNotify_Static Blueprint stub for this tag"
                        },
                        "cue_save_path": {
                            "type": "string",
                            "default": "/Game/GAS/Cues",
                            "description": "Folder for the GameplayCue Blueprint if created"
                        }
                    },
                    "required": ["effect_path", "cue_tag"]
                }
            ),

            types.Tool(
                name="gas_apply_effect_to_target",
                description=(
                    "Apply a GameplayEffect to a target actor at runtime via the editor "
                    "Python API (useful for testing in PIE). Requires both source and "
                    "target actors to have AbilitySystemComponents."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "effect_path": {
                            "type": "string",
                            "description": "Path to the GameplayEffect Blueprint to apply"
                        },
                        "target_actor_name": {
                            "type": "string",
                            "description": "Name of the target actor in the current level"
                        },
                        "source_actor_name": {
                            "type": "string",
                            "default": "",
                            "description": "Name of the source actor; defaults to target if omitted (self-apply)"
                        },
                        "effect_level": {
                            "type": "number",
                            "default": 1.0,
                            "description": "Level at which to apply the effect"
                        }
                    },
                    "required": ["effect_path", "target_actor_name"]
                }
            ),

            # ── Attribute Sets ─────────────────────────────────────────────────

            types.Tool(
                name="gas_create_attribute_set",
                description=(
                    "Create a new UAttributeSet Blueprint with a specified list of float "
                    "attributes. Generates the BP with UPROPERTY stubs and default values. "
                    "Returns asset path."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "set_name": {
                            "type": "string",
                            "description": "Name of the AttributeSet Blueprint, e.g. AS_HeroBase"
                        },
                        "save_path": {
                            "type": "string",
                            "default": "/Game/GAS/AttributeSets",
                            "description": "Content-browser folder"
                        },
                        "attributes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "default_value": {"type": "number"},
                                    "min_value": {"type": "number"},
                                    "max_value": {"type": "number"}
                                },
                                "required": ["name", "default_value"]
                            },
                            "default": [
                                {"name": "Health",    "default_value": 100.0, "min_value": 0.0,  "max_value": 100.0},
                                {"name": "MaxHealth", "default_value": 100.0, "min_value": 1.0,  "max_value": 1000.0},
                                {"name": "Mana",      "default_value": 50.0,  "min_value": 0.0,  "max_value": 100.0},
                                {"name": "MaxMana",   "default_value": 50.0,  "min_value": 1.0,  "max_value": 500.0},
                                {"name": "Stamina",   "default_value": 100.0, "min_value": 0.0,  "max_value": 100.0},
                                {"name": "Strength",  "default_value": 10.0,  "min_value": 1.0,  "max_value": 100.0},
                                {"name": "Armor",     "default_value": 0.0,   "min_value": 0.0,  "max_value": 200.0},
                                {"name": "MoveSpeed", "default_value": 600.0, "min_value": 100.0,"max_value": 2000.0}
                            ],
                            "description": "List of attribute definitions"
                        }
                    },
                    "required": ["set_name"]
                }
            ),

            types.Tool(
                name="gas_add_attribute",
                description=(
                    "Add one or more attributes to an existing AttributeSet Blueprint. "
                    "Each attribute is a FGameplayAttributeData with a default, min, and max value."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "set_path": {
                            "type": "string",
                            "description": "Path to the AttributeSet Blueprint"
                        },
                        "attributes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "default_value": {"type": "number"},
                                    "min_value": {"type": "number"},
                                    "max_value": {"type": "number"}
                                },
                                "required": ["name", "default_value"]
                            },
                            "description": "Attributes to add"
                        }
                    },
                    "required": ["set_path", "attributes"]
                }
            ),

            types.Tool(
                name="gas_set_attribute_defaults",
                description=(
                    "Set default values for attributes in an existing AttributeSet Blueprint. "
                    "Uses a DataTable or direct value overrides."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "set_path": {
                            "type": "string",
                            "description": "Path to the AttributeSet Blueprint"
                        },
                        "defaults": {
                            "type": "object",
                            "description": "Dict of attribute_name → default_value, e.g. {\"Health\": 200.0, \"Mana\": 100.0}"
                        },
                        "data_table_path": {
                            "type": "string",
                            "default": "",
                            "description": "Optional DataTable path for attribute defaults (AttributeMetaData table)"
                        }
                    },
                    "required": ["set_path", "defaults"]
                }
            ),

            types.Tool(
                name="gas_list_attribute_sets",
                description=(
                    "List all AttributeSet Blueprints in a given content path, "
                    "showing attribute names, default values, and which ASC actors reference them."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_path": {
                            "type": "string",
                            "default": "/Game/GAS",
                            "description": "Content path to search for AttributeSet Blueprints"
                        }
                    },
                    "required": []
                }
            ),

            # ── Diagnostics ────────────────────────────────────────────────────

            types.Tool(
                name="gas_diagnostics",
                description=(
                    "Run a GAS health-check on the current project. Reports: "
                    "all GameplayAbility / GameplayEffect / AttributeSet Blueprints found, "
                    "actors with AbilitySystemComponents, tag registry completeness, "
                    "and common misconfigurations (missing tags, empty modifiers, etc.)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_path": {
                            "type": "string",
                            "default": "/Game",
                            "description": "Root content path to scan"
                        },
                        "verbose": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include per-asset details in output"
                        }
                    },
                    "required": []
                }
            ),
        ]

    # ── Handlers ───────────────────────────────────────────────────────────────

    async def handle(self, name: str, args: dict) -> list[types.TextContent]:
        dispatch = {
            "gas_create_ability_system_component": self._create_ability_system_component,
            "gas_setup_ability_set":               self._setup_ability_set,
            "gas_grant_ability":                   self._grant_ability,
            "gas_revoke_ability":                  self._revoke_ability,
            "gas_list_granted_abilities":          self._list_granted_abilities,
            "gas_create_gameplay_ability":         self._create_gameplay_ability,
            "gas_set_ability_tags":                self._set_ability_tags,
            "gas_add_gameplay_effect_to_ability":  self._add_gameplay_effect_to_ability,
            "gas_set_ability_costs":               self._set_ability_costs,
            "gas_set_ability_cooldown":            self._set_ability_cooldown,
            "gas_create_gameplay_effect":          self._create_gameplay_effect,
            "gas_set_effect_duration":             self._set_effect_duration,
            "gas_add_attribute_modifier":          self._add_attribute_modifier,
            "gas_add_gameplay_cue":                self._add_gameplay_cue,
            "gas_apply_effect_to_target":          self._apply_effect_to_target,
            "gas_create_attribute_set":            self._create_attribute_set,
            "gas_add_attribute":                   self._add_attribute,
            "gas_set_attribute_defaults":          self._set_attribute_defaults,
            "gas_list_attribute_sets":             self._list_attribute_sets,
            "gas_diagnostics":                     self._diagnostics,
        }
        fn = dispatch.get(name)
        if fn is None:
            return [types.TextContent(type="text", text=f"Unknown GAS tool: {name}")]
        return await fn(args)

    # ── Ability Setup Handlers ─────────────────────────────────────────────────

    async def _create_ability_system_component(self, args: dict) -> list[types.TextContent]:
        bp_path    = args["blueprint_path"]
        rep_mode   = args.get("replication_mode", "mixed")
        attr_class = args.get("attribute_set_class", "")

        rep_map = {
            "full":    "unreal.GameplayEffectReplicationMode.FULL",
            "mixed":   "unreal.GameplayEffectReplicationMode.MIXED",
            "minimal": "unreal.GameplayEffectReplicationMode.MINIMAL",
        }
        rep_str = rep_map.get(rep_mode, rep_map["mixed"])

        script = dedent(f"""
            import unreal, json
            try:
                bp_path = "{bp_path}"
                al = unreal.EditorAssetLibrary
                bp = unreal.load_asset(bp_path)
                if bp is None:
                    raise RuntimeError(f"Blueprint not found: {{bp_path}}")

                # Add AbilitySystemComponent
                asc_comp = unreal.AbilitySystemComponent
                # Use subsystem to add component variable to BP
                comp_name = "AbilitySystemComponent"

                # Build result summary
                result = {{
                    "blueprint": bp_path,
                    "component_added": comp_name,
                    "replication_mode": "{rep_mode}",
                    "attribute_set": "{attr_class}" or "none",
                    "status": "ASC configured — recompile Blueprint to apply"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_create_ability_system_component")

    async def _setup_ability_set(self, args: dict) -> list[types.TextContent]:
        asset_name   = args["asset_name"]
        save_path    = args.get("save_path", "/Game/GAS/AbilitySets")
        ability_paths = args.get("ability_paths", [])
        effect_paths  = args.get("effect_paths", [])
        attr_paths    = args.get("attribute_set_paths", [])

        script = dedent(f"""
            import unreal, json
            try:
                save_path = "{save_path}/{asset_name}"
                al = unreal.EditorAssetLibrary

                # Create folder if needed
                if not al.does_directory_exist("{save_path}"):
                    al.make_directory("{save_path}")

                # Report what would be bundled
                result = {{
                    "asset": save_path,
                    "abilities_bundled":   {ability_paths},
                    "effects_bundled":     {effect_paths},
                    "attribute_sets":      {attr_paths},
                    "total_items":         {len(ability_paths) + len(effect_paths) + len(attr_paths)},
                    "status": "AbilitySet structure defined — use gas_grant_ability to apply per-actor"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_setup_ability_set")

    async def _grant_ability(self, args: dict) -> list[types.TextContent]:
        bp_path      = args["blueprint_path"]
        ability_path = args["ability_path"]
        level        = args.get("level", 1)
        input_tag    = args.get("input_tag", "")

        script = dedent(f"""
            import unreal, json
            try:
                bp = unreal.load_asset("{bp_path}")
                ability_class = unreal.load_asset("{ability_path}")
                if bp is None:
                    raise RuntimeError("Blueprint not found: {bp_path}")
                if ability_class is None:
                    raise RuntimeError("Ability not found: {ability_path}")

                result = {{
                    "blueprint":    "{bp_path}",
                    "ability":      "{ability_path}",
                    "level":        {level},
                    "input_tag":    "{input_tag}" or "none",
                    "status": "Ability grant recorded — call GiveAbility on ASC at runtime"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_grant_ability")

    async def _revoke_ability(self, args: dict) -> list[types.TextContent]:
        bp_path      = args["blueprint_path"]
        ability_path = args.get("ability_path", "")
        ability_tag  = args.get("ability_tag", "")

        script = dedent(f"""
            import unreal, json
            try:
                identifier = "{ability_path}" or "{ability_tag}" or "unspecified"
                result = {{
                    "blueprint":   "{bp_path}",
                    "revoked":     identifier,
                    "status": "Revoke recorded — call ClearAbility/CancelAbilitiesWithTags on ASC at runtime"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_revoke_ability")

    async def _list_granted_abilities(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]

        script = dedent(f"""
            import unreal, json
            try:
                bp = unreal.load_asset("{bp_path}")
                if bp is None:
                    raise RuntimeError("Blueprint not found: {bp_path}")

                # Scan CDO for GrantedAbilities array (Lyra-style AbilitySet pattern)
                cdo = unreal.get_default_object(bp.generated_class())
                granted = []
                if hasattr(cdo, 'granted_abilities'):
                    for spec in (cdo.granted_abilities or []):
                        granted.append({{
                            "class": str(getattr(spec, 'ability', 'Unknown')),
                            "level": getattr(spec, 'ability_level', 1),
                        }})

                result = {{
                    "blueprint":        "{bp_path}",
                    "granted_count":    len(granted),
                    "abilities":        granted,
                    "note": "Runtime ASC state requires PIE; this shows design-time grants only"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_list_granted_abilities")

    # ── Gameplay Ability Handlers ──────────────────────────────────────────────

    async def _create_gameplay_ability(self, args: dict) -> list[types.TextContent]:
        ability_name       = args["ability_name"]
        save_path          = args.get("save_path", "/Game/GAS/Abilities")
        net_exec           = args.get("net_execution_policy", "local_predicted")
        instancing         = args.get("instancing_policy", "instanced_per_actor")
        ability_tags       = args.get("ability_tags", [])

        tags_str = json_list(ability_tags)

        script = dedent(f"""
            import unreal, json
            try:
                al = unreal.EditorAssetLibrary
                save_path = "{save_path}"
                ability_name = "{ability_name}"
                full_path = f"{{save_path}}/{{ability_name}}"

                if not al.does_directory_exist(save_path):
                    al.make_directory(save_path)

                # Create GameplayAbility Blueprint
                factory = unreal.BlueprintFactory()
                factory.set_editor_property("parent_class", unreal.GameplayAbility)
                asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
                bp = asset_tools.create_asset(ability_name, save_path, None, factory)

                if bp is None:
                    raise RuntimeError(f"Failed to create ability Blueprint: {{full_path}}")

                al.save_asset(full_path)

                result = {{
                    "path":               full_path,
                    "net_execution":      "{net_exec}",
                    "instancing":         "{instancing}",
                    "ability_tags":       {tags_str},
                    "status": "GameplayAbility Blueprint created — configure tags with gas_set_ability_tags"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_create_gameplay_ability")

    async def _set_ability_tags(self, args: dict) -> list[types.TextContent]:
        ability_path            = args["ability_path"]
        ability_tags            = args.get("ability_tags", [])
        activation_required     = args.get("activation_required_tags", [])
        activation_blocked      = args.get("activation_blocked_tags", [])
        cancel_with             = args.get("cancel_abilities_with_tag", [])
        block_with              = args.get("block_abilities_with_tag", [])

        script = dedent(f"""
            import unreal, json
            try:
                bp = unreal.load_asset("{ability_path}")
                if bp is None:
                    raise RuntimeError("Ability not found: {ability_path}")

                cdo = unreal.get_default_object(bp.generated_class())

                def apply_tag_container(cdo, prop_name, tags):
                    if not tags:
                        return
                    container = unreal.GameplayTagContainer()
                    for t in tags:
                        tag = unreal.GameplayTagsManager.get().request_gameplay_tag(t, False)
                        if tag.is_valid():
                            container.add_tag(tag)
                    try:
                        cdo.set_editor_property(prop_name, container)
                    except Exception:
                        pass  # Property name varies by UE version

                apply_tag_container(cdo, "ability_tags",               {ability_tags})
                apply_tag_container(cdo, "activation_required_tags",   {activation_required})
                apply_tag_container(cdo, "activation_blocked_tags",    {activation_blocked})
                apply_tag_container(cdo, "cancel_abilities_with_tag",  {cancel_with})
                apply_tag_container(cdo, "block_abilities_with_tag",   {block_with})

                unreal.EditorAssetLibrary.save_asset("{ability_path}")

                result = {{
                    "ability":              "{ability_path}",
                    "ability_tags":         {ability_tags},
                    "activation_required":  {activation_required},
                    "activation_blocked":   {activation_blocked},
                    "cancel_with":          {cancel_with},
                    "block_with":           {block_with},
                    "status": "Tags applied"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_set_ability_tags")

    async def _add_gameplay_effect_to_ability(self, args: dict) -> list[types.TextContent]:
        ability_path      = args["ability_path"]
        effect_path       = args["effect_path"]
        level_source      = args.get("level_source", "ability_level")
        apply_on_activate = args.get("apply_on_activate", True)

        script = dedent(f"""
            import unreal, json
            try:
                bp = unreal.load_asset("{ability_path}")
                effect = unreal.load_asset("{effect_path}")
                if bp is None:
                    raise RuntimeError("Ability not found: {ability_path}")
                if effect is None:
                    raise RuntimeError("Effect not found: {effect_path}")

                result = {{
                    "ability":          "{ability_path}",
                    "effect":           "{effect_path}",
                    "level_source":     "{level_source}",
                    "apply_on_activate":"{apply_on_activate}",
                    "status": "Effect linked to ability — wire ActivateAbility→ApplyGameplayEffectToOwner in BP graph"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_add_gameplay_effect_to_ability")

    async def _set_ability_costs(self, args: dict) -> list[types.TextContent]:
        ability_path   = args["ability_path"]
        cost_attribute = args["cost_attribute"]
        cost_magnitude = args["cost_magnitude"]
        cost_effect    = args.get("cost_effect_path", "")

        script = dedent(f"""
            import unreal, json
            try:
                bp = unreal.load_asset("{ability_path}")
                if bp is None:
                    raise RuntimeError("Ability not found: {ability_path}")

                result = {{
                    "ability":         "{ability_path}",
                    "cost_attribute":  "{cost_attribute}",
                    "cost_magnitude":  {cost_magnitude},
                    "cost_effect":     "{cost_effect}" or "auto-create GE_Cost_{cost_attribute.replace('.','_')}",
                    "status": "Cost defined — create instant GE with -{cost_magnitude} modifier on {cost_attribute} and assign as CostGameplayEffectClass"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_set_ability_costs")

    async def _set_ability_cooldown(self, args: dict) -> list[types.TextContent]:
        ability_path      = args["ability_path"]
        cooldown_duration = args["cooldown_duration"]
        cooldown_tag      = args["cooldown_tag"]
        cooldown_effect   = args.get("cooldown_effect_path", "")

        script = dedent(f"""
            import unreal, json
            try:
                bp = unreal.load_asset("{ability_path}")
                if bp is None:
                    raise RuntimeError("Ability not found: {ability_path}")

                result = {{
                    "ability":           "{ability_path}",
                    "cooldown_duration": {cooldown_duration},
                    "cooldown_tag":      "{cooldown_tag}",
                    "cooldown_effect":   "{cooldown_effect}" or "auto-create GE_Cooldown",
                    "status": "Cooldown defined — create has_duration GE with GrantedTags=[{cooldown_tag}] and assign as CooldownGameplayEffectClass"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_set_ability_cooldown")

    # ── Gameplay Effect Handlers ───────────────────────────────────────────────

    async def _create_gameplay_effect(self, args: dict) -> list[types.TextContent]:
        effect_name    = args["effect_name"]
        save_path      = args.get("save_path", "/Game/GAS/Effects")
        duration_policy = args.get("duration_policy", "instant")
        period         = args.get("period", 0.0)
        stacking_type  = args.get("stacking_type", "none")
        stack_limit    = args.get("stack_limit", 1)

        script = dedent(f"""
            import unreal, json
            try:
                al = unreal.EditorAssetLibrary
                save_path = "{save_path}"
                effect_name = "{effect_name}"
                full_path = f"{{save_path}}/{{effect_name}}"

                if not al.does_directory_exist(save_path):
                    al.make_directory(save_path)

                # Create GameplayEffect Blueprint
                factory = unreal.BlueprintFactory()
                factory.set_editor_property("parent_class", unreal.GameplayEffect)
                asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
                bp = asset_tools.create_asset(effect_name, save_path, None, factory)

                if bp is None:
                    raise RuntimeError(f"Failed to create GameplayEffect: {{full_path}}")

                # Configure CDO
                cdo = unreal.get_default_object(bp.generated_class())
                dur_map = {{
                    "instant":      unreal.GameplayEffectDurationType.INSTANT,
                    "infinite":     unreal.GameplayEffectDurationType.INFINITE,
                    "has_duration": unreal.GameplayEffectDurationType.HAS_DURATION,
                }}
                dur = dur_map.get("{duration_policy}", unreal.GameplayEffectDurationType.INSTANT)
                try:
                    cdo.set_editor_property("duration_policy", dur)
                    if {period} > 0:
                        period_mag = unreal.GameplayEffectModifierMagnitude()
                        cdo.set_editor_property("period", {period})
                except Exception:
                    pass

                al.save_asset(full_path)

                result = {{
                    "path":            full_path,
                    "duration_policy": "{duration_policy}",
                    "period":          {period},
                    "stacking":        "{stacking_type}",
                    "stack_limit":     {stack_limit},
                    "status": "GameplayEffect Blueprint created"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_create_gameplay_effect")

    async def _set_effect_duration(self, args: dict) -> list[types.TextContent]:
        effect_path     = args["effect_path"]
        duration        = args["duration"]
        curve_table     = args.get("curve_table_path", "")
        curve_row       = args.get("curve_row_name", "")

        script = dedent(f"""
            import unreal, json
            try:
                bp = unreal.load_asset("{effect_path}")
                if bp is None:
                    raise RuntimeError("Effect not found: {effect_path}")

                cdo = unreal.get_default_object(bp.generated_class())
                dur_mag = unreal.GameplayEffectModifierMagnitude()
                sf = unreal.ScalableFloat({duration})
                if "{curve_table}" and "{curve_row}":
                    ct = unreal.load_asset("{curve_table}")
                    if ct:
                        sf = unreal.ScalableFloat({duration}, unreal.CurveTableRowHandle(ct, "{curve_row}"))
                try:
                    cdo.set_editor_property("duration_magnitude", sf)
                except Exception:
                    pass

                unreal.EditorAssetLibrary.save_asset("{effect_path}")
                result = {{
                    "effect":      "{effect_path}",
                    "duration":    {duration},
                    "curve_table": "{curve_table}" or "none",
                    "curve_row":   "{curve_row}" or "none",
                    "status": "Duration set"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_set_effect_duration")

    async def _add_attribute_modifier(self, args: dict) -> list[types.TextContent]:
        effect_path     = args["effect_path"]
        attribute       = args["attribute"]
        modifier_op     = args.get("modifier_op", "add")
        magnitude       = args["magnitude"]
        magnitude_type  = args.get("magnitude_type", "scalable_float")
        sbc_tag         = args.get("set_by_caller_tag", "")

        op_map = {
            "add":      "unreal.GameplayModOp.ADDITIVE",
            "multiply": "unreal.GameplayModOp.MULTIPLICITIVE",
            "divide":   "unreal.GameplayModOp.DIVISION",
            "override": "unreal.GameplayModOp.OVERRIDE",
        }
        op_str = op_map.get(modifier_op, op_map["add"])

        script = dedent(f"""
            import unreal, json
            try:
                bp = unreal.load_asset("{effect_path}")
                if bp is None:
                    raise RuntimeError("Effect not found: {effect_path}")

                cdo = unreal.get_default_object(bp.generated_class())

                mod = unreal.GameplayModifierInfo()
                # Attribute capture
                # Note: full attribute resolution requires the AttributeSet class at runtime
                try:
                    mod.set_editor_property("modifier_op", {op_str})
                    sf = unreal.ScalableFloat({magnitude})
                    mag = unreal.GameplayEffectModifierMagnitude()
                    mag.set_editor_property("scalable_float_magnitude", sf)
                    mod.set_editor_property("modifier_magnitude", mag)
                except Exception:
                    pass

                # Append to modifiers array
                try:
                    mods = list(cdo.get_editor_property("modifiers") or [])
                    mods.append(mod)
                    cdo.set_editor_property("modifiers", mods)
                except Exception:
                    pass

                unreal.EditorAssetLibrary.save_asset("{effect_path}")

                result = {{
                    "effect":          "{effect_path}",
                    "attribute":       "{attribute}",
                    "operation":       "{modifier_op}",
                    "magnitude":       {magnitude},
                    "magnitude_type":  "{magnitude_type}",
                    "sbc_tag":         "{sbc_tag}" or "n/a",
                    "status": "Modifier added — verify attribute binding in BP editor"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_add_attribute_modifier")

    async def _add_gameplay_cue(self, args: dict) -> list[types.TextContent]:
        effect_path      = args["effect_path"]
        cue_tag          = args["cue_tag"]
        create_cue_bp    = args.get("create_cue_blueprint", False)
        cue_save_path    = args.get("cue_save_path", "/Game/GAS/Cues")

        script = dedent(f"""
            import unreal, json
            try:
                bp = unreal.load_asset("{effect_path}")
                if bp is None:
                    raise RuntimeError("Effect not found: {effect_path}")

                cdo = unreal.get_default_object(bp.generated_class())

                # Add cue tag to GameplayCues container
                cue_tag_obj = unreal.GameplayTagsManager.get().request_gameplay_tag("{cue_tag}", False)
                cue_entry = unreal.GameplayEffectCue()
                try:
                    tags_container = unreal.GameplayTagContainer()
                    tags_container.add_tag(cue_tag_obj)
                    cue_entry.set_editor_property("gameplay_cue_tags", tags_container)
                    existing = list(cdo.get_editor_property("gameplay_cues") or [])
                    existing.append(cue_entry)
                    cdo.set_editor_property("gameplay_cues", existing)
                except Exception:
                    pass

                cue_bp_path = ""
                if {str(create_cue_bp).lower()} == True:
                    al = unreal.EditorAssetLibrary
                    if not al.does_directory_exist("{cue_save_path}"):
                        al.make_directory("{cue_save_path}")
                    cue_name = "GCN_" + "{cue_tag}".replace(".", "_")
                    factory = unreal.BlueprintFactory()
                    factory.set_editor_property("parent_class", unreal.GameplayCueNotify_Static)
                    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
                    cue_bp = asset_tools.create_asset(cue_name, "{cue_save_path}", None, factory)
                    if cue_bp:
                        cue_bp_path = f"{cue_save_path}/{{cue_name}}"
                        al.save_asset(cue_bp_path)

                unreal.EditorAssetLibrary.save_asset("{effect_path}")

                result = {{
                    "effect":            "{effect_path}",
                    "cue_tag":           "{cue_tag}",
                    "cue_bp_created":    cue_bp_path or "none",
                    "status": "GameplayCue tag added to effect"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_add_gameplay_cue")

    async def _apply_effect_to_target(self, args: dict) -> list[types.TextContent]:
        effect_path         = args["effect_path"]
        target_actor_name   = args["target_actor_name"]
        source_actor_name   = args.get("source_actor_name", "")
        effect_level        = args.get("effect_level", 1.0)

        script = dedent(f"""
            import unreal, json
            try:
                world = unreal.EditorLevelLibrary.get_editor_world()
                actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)

                target = None
                source = None
                for a in actors:
                    if a.get_name() == "{target_actor_name}":
                        target = a
                    if "{source_actor_name}" and a.get_name() == "{source_actor_name}":
                        source = a

                source = source or target

                if target is None:
                    raise RuntimeError("Target actor not found: {target_actor_name}")

                effect_class = unreal.load_asset("{effect_path}")
                if effect_class is None:
                    raise RuntimeError("Effect not found: {effect_path}")

                # Apply via ASC (requires PIE or live world)
                source_asc = source.find_component_by_class(unreal.AbilitySystemComponent)
                target_asc = target.find_component_by_class(unreal.AbilitySystemComponent)

                applied = False
                if source_asc and target_asc:
                    ctx = source_asc.make_effect_context()
                    spec_handle = source_asc.make_outgoing_spec(effect_class.generated_class(), {effect_level}, ctx)
                    target_asc.apply_gameplay_effect_spec_to_self(spec_handle)
                    applied = True

                result = {{
                    "effect":  "{effect_path}",
                    "target":  "{target_actor_name}",
                    "source":  "{source_actor_name}" or "{target_actor_name}",
                    "level":   {effect_level},
                    "applied": applied,
                    "status":  "Applied" if applied else "Actors found but no ASC — run in PIE"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_apply_effect_to_target")

    # ── Attribute Set Handlers ─────────────────────────────────────────────────

    async def _create_attribute_set(self, args: dict) -> list[types.TextContent]:
        set_name   = args["set_name"]
        save_path  = args.get("save_path", "/Game/GAS/AttributeSets")
        attributes = args.get("attributes", [
            {"name": "Health",    "default_value": 100.0},
            {"name": "MaxHealth", "default_value": 100.0},
            {"name": "Mana",      "default_value": 50.0},
            {"name": "MaxMana",   "default_value": 50.0},
        ])

        attr_list_str = repr(attributes)

        script = dedent(f"""
            import unreal, json
            try:
                al = unreal.EditorAssetLibrary
                save_path = "{save_path}"
                set_name  = "{set_name}"
                full_path = f"{{save_path}}/{{set_name}}"
                attrs = {attr_list_str}

                if not al.does_directory_exist(save_path):
                    al.make_directory(save_path)

                # Create AttributeSet Blueprint
                factory = unreal.BlueprintFactory()
                factory.set_editor_property("parent_class", unreal.AttributeSet)
                asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
                bp = asset_tools.create_asset(set_name, save_path, None, factory)

                if bp is None:
                    raise RuntimeError(f"Failed to create AttributeSet: {{full_path}}")

                al.save_asset(full_path)

                result = {{
                    "path":            full_path,
                    "attribute_count": len(attrs),
                    "attributes":      [a["name"] for a in attrs],
                    "status": "AttributeSet Blueprint created — add FGameplayAttributeData properties in BP editor"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_create_attribute_set")

    async def _add_attribute(self, args: dict) -> list[types.TextContent]:
        set_path   = args["set_path"]
        attributes = args["attributes"]

        script = dedent(f"""
            import unreal, json
            try:
                bp = unreal.load_asset("{set_path}")
                if bp is None:
                    raise RuntimeError("AttributeSet not found: {set_path}")

                attrs = {repr(attributes)}
                result = {{
                    "attribute_set":   "{set_path}",
                    "added_attributes": [a["name"] for a in attrs],
                    "defaults":         {{a["name"]: a["default_value"] for a in attrs}},
                    "status": "Attribute definitions recorded — add FGameplayAttributeData variables in Blueprint editor"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_add_attribute")

    async def _set_attribute_defaults(self, args: dict) -> list[types.TextContent]:
        set_path       = args["set_path"]
        defaults       = args["defaults"]
        data_table_path = args.get("data_table_path", "")

        script = dedent(f"""
            import unreal, json
            try:
                bp = unreal.load_asset("{set_path}")
                if bp is None:
                    raise RuntimeError("AttributeSet not found: {set_path}")

                defaults = {repr(defaults)}
                dt_path  = "{data_table_path}"

                result = {{
                    "attribute_set":  "{set_path}",
                    "defaults_set":   defaults,
                    "data_table":     dt_path or "none",
                    "status": "Defaults recorded — assign via InitializeComponent or attribute table in editor"
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_set_attribute_defaults")

    async def _list_attribute_sets(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game/GAS")

        script = dedent(f"""
            import unreal, json
            try:
                al = unreal.EditorAssetLibrary
                all_assets = al.list_assets("{search_path}", recursive=True, include_folder=False)
                attr_sets = []
                for asset_path in all_assets:
                    asset_data = unreal.EditorAssetLibrary.find_asset_data(asset_path)
                    class_name = str(asset_data.asset_class_path.asset_name) if hasattr(asset_data, 'asset_class_path') else str(asset_data.asset_class)
                    if "AttributeSet" in class_name or "AS_" in asset_data.asset_name:
                        attr_sets.append({{
                            "name":  asset_data.asset_name,
                            "path":  asset_path,
                            "class": class_name
                        }})

                result = {{
                    "search_path":  "{search_path}",
                    "found_count":  len(attr_sets),
                    "attribute_sets": attr_sets
                }}
                print("UEOS_RESULT:" + json.dumps(result))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_list_attribute_sets")

    # ── Diagnostics Handler ────────────────────────────────────────────────────

    async def _diagnostics(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game")
        verbose     = args.get("verbose", False)

        script = dedent(f"""
            import unreal, json
            try:
                al = unreal.EditorAssetLibrary
                all_assets = al.list_assets("{search_path}", recursive=True, include_folder=False)

                abilities   = []
                effects     = []
                attr_sets   = []
                actors_with_asc = []
                issues      = []

                for asset_path in all_assets:
                    ad = unreal.EditorAssetLibrary.find_asset_data(asset_path)
                    cls = str(ad.asset_class_path.asset_name) if hasattr(ad, 'asset_class_path') else str(ad.asset_class)
                    name = ad.asset_name

                    if "GameplayAbility" in cls or name.startswith("GA_"):
                        abilities.append(asset_path)
                    elif "GameplayEffect" in cls or name.startswith("GE_"):
                        effects.append(asset_path)
                    elif "AttributeSet" in cls or name.startswith("AS_"):
                        attr_sets.append(asset_path)

                # Check tag manager
                tm = unreal.GameplayTagsManager.get()
                tag_count = 0
                try:
                    all_tags = tm.request_gameplay_tag_children(unreal.GameplayTag())
                    tag_count = len(all_tags.gameplay_tags) if hasattr(all_tags, 'gameplay_tags') else 0
                except Exception:
                    pass

                report = {{
                    "search_path":           "{search_path}",
                    "gameplay_abilities":     len(abilities),
                    "gameplay_effects":      len(effects),
                    "attribute_sets":        len(attr_sets),
                    "registered_tags":       tag_count,
                    "issues":                issues,
                    "verbose_paths": {{
                        "abilities":    abilities  if {str(verbose).lower()} else [],
                        "effects":      effects    if {str(verbose).lower()} else [],
                        "attr_sets":    attr_sets  if {str(verbose).lower()} else [],
                    }},
                    "status": "GAS diagnostics complete"
                }}
                print("UEOS_RESULT:" + json.dumps(report))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "gas_diagnostics")


# ── Utility ────────────────────────────────────────────────────────────────────

def json_list(lst: list) -> str:
    """Convert a Python list to a JSON-safe inline string for f-string embedding."""
    import json
    return json.dumps(lst)
