"""
UEOS Blueprint Tools
Full Blueprint creation, graph editing, compilation, and validation.
No C++. Pure Python via UE Remote Control + Python Editor Scripting.

Supported Blueprint types:
  Actor, ActorComponent, Character, Pawn, GameMode, GameState,
  PlayerController, AIController, AnimBlueprint, Widget,
  FunctionLibrary, Interface, GameInstance
"""

import json
import logging
from typing import Any
from mcp import types

log = logging.getLogger("ueos.blueprint")


class BlueprintTools:

    def __init__(self, ue):
        self.ue = ue  # UnrealRemoteControl instance

    # ─────────────────────────────────────────────
    # Tool Definitions (what Claude sees)
    # ─────────────────────────────────────────────

    async def get_tool_definitions(self) -> list[types.Tool]:
        return [

            types.Tool(
                name="blueprint_create",
                description="""Create a new Blueprint asset in Unreal Engine 5.4.
Supports all Blueprint types: Actor, Character, Pawn, ActorComponent, GameMode,
GameState, PlayerController, AIController, AnimBlueprint, Widget, FunctionLibrary, Interface.
Returns the full asset path of the created Blueprint.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Blueprint name e.g. BP_PlayerCharacter"},
                        "path": {"type": "string", "description": "Content path e.g. /Game/Blueprints/Characters"},
                        "parent_class": {
                            "type": "string",
                            "description": "Parent class: Actor, Character, Pawn, ActorComponent, SceneComponent, GameMode, GameState, PlayerController, AIController, AnimInstance, UserWidget, BlueprintFunctionLibrary, Interface, GameInstance, or a full class path like /Game/Blueprints/BP_BaseCharacter",
                            "default": "Actor"
                        },
                        "blueprint_type": {
                            "type": "string",
                            "description": "Blueprint type: Normal, Interface, FunctionLibrary, MacroLibrary",
                            "default": "Normal"
                        }
                    },
                    "required": ["name", "path"]
                }
            ),

            types.Tool(
                name="blueprint_add_variable",
                description="""Add a variable to a Blueprint.
Supports all variable types: Boolean, Integer, Integer64, Float, Double, String, Name, Text,
Vector, Rotator, Transform, Object references, Class references, Arrays, Maps, Sets,
Struct references, and custom struct/enum types.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"},
                        "name": {"type": "string", "description": "Variable name (use PascalCase for UE convention)"},
                        "type": {
                            "type": "string",
                            "description": "Variable type: bool, int, int64, float, double, string, name, text, vector, rotator, transform, Actor, Character, StaticMeshComponent, SkeletalMeshComponent, or any UE class name"
                        },
                        "default_value": {"description": "Default value for the variable (type-appropriate)"},
                        "is_exposed": {"type": "boolean", "description": "Expose to editor (instance editable)", "default": False},
                        "is_replicated": {"type": "boolean", "description": "Replicate this variable over network", "default": False},
                        "category": {"type": "string", "description": "Editor category for organization", "default": "Default"},
                        "tooltip": {"type": "string", "description": "Tooltip shown in editor", "default": ""}
                    },
                    "required": ["blueprint_path", "name", "type"]
                }
            ),

            types.Tool(
                name="blueprint_add_function",
                description="""Add a new custom function to a Blueprint.
Creates the function graph with optional input and output parameters.
The function body can be populated with blueprint_add_node calls afterward.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"},
                        "name": {"type": "string", "description": "Function name"},
                        "inputs": {
                            "type": "array",
                            "description": "Input parameters",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {"type": "string"}
                                }
                            },
                            "default": []
                        },
                        "outputs": {
                            "type": "array",
                            "description": "Output parameters (return values)",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {"type": "string"}
                                }
                            },
                            "default": []
                        },
                        "is_pure": {"type": "boolean", "description": "Pure function (no execution pins)", "default": False},
                        "category": {"type": "string", "description": "Function category", "default": "Default"}
                    },
                    "required": ["blueprint_path", "name"]
                }
            ),

            types.Tool(
                name="blueprint_add_event",
                description="""Add a custom event to a Blueprint's Event Graph.
Custom events can be called from other Blueprints or triggered by gameplay code.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"},
                        "name": {"type": "string", "description": "Event name e.g. OnPlayerDamaged"},
                        "parameters": {
                            "type": "array",
                            "description": "Event parameters",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {"type": "string"}
                                }
                            },
                            "default": []
                        },
                        "graph": {"type": "string", "description": "Graph to add event to", "default": "EventGraph"}
                    },
                    "required": ["blueprint_path", "name"]
                }
            ),

            types.Tool(
                name="blueprint_add_node",
                description="""Add a node to a Blueprint graph.
This is the core graph editing tool. Supports:
- Function calls: node_type='function', function='ActorHasTag', target='self'
- Variable get/set: node_type='variable_get' or 'variable_set', variable_name='Health'  
- Events: node_type='event', event='BeginPlay'
- Flow control: node_type='branch', 'sequence', 'for_each', 'while', 'gate', 'do_once'
- Math: node_type='math', operation='add/subtract/multiply/divide/clamp/lerp'
- Cast: node_type='cast', target_class='AMyCharacter'
- Macros: node_type='macro'
- Comments: node_type='comment', comment_text='Player Movement Logic'
Returns node_id for use in blueprint_connect_pins.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"},
                        "graph": {"type": "string", "description": "Graph name: EventGraph, or a function name", "default": "EventGraph"},
                        "node_type": {
                            "type": "string",
                            "description": "Node type: event, function, variable_get, variable_set, branch, sequence, for_each, cast, math, return, print_string, delay, timeline, spawn_actor, get_component, add_component, comment, macro, custom_event"
                        },
                        "function": {"type": "string", "description": "Function name for function nodes"},
                        "target": {"type": "string", "description": "Target object: 'self', variable name, or class name"},
                        "variable_name": {"type": "string", "description": "Variable name for get/set nodes"},
                        "event": {"type": "string", "description": "Event name: BeginPlay, Tick, EndPlay, ActorBeginOverlap, etc."},
                        "class_name": {"type": "string", "description": "Class name for cast/spawn nodes"},
                        "value": {"description": "Literal value for literal nodes"},
                        "comment_text": {"type": "string", "description": "Comment text for comment nodes"},
                        "position_x": {"type": "number", "description": "Node X position in graph", "default": 0},
                        "position_y": {"type": "number", "description": "Node Y position in graph", "default": 0}
                    },
                    "required": ["blueprint_path", "node_type"]
                }
            ),

            types.Tool(
                name="blueprint_connect_pins",
                description="""Connect two pins between nodes in a Blueprint graph.
Use node IDs returned from blueprint_add_node.
Pin names follow UE conventions: exec pins are 'execute'/'then',
data pins use their parameter names.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"},
                        "graph": {"type": "string", "description": "Graph name", "default": "EventGraph"},
                        "from_node": {"type": "string", "description": "Source node ID or node name"},
                        "from_pin": {"type": "string", "description": "Source pin name e.g. 'then', 'ReturnValue', 'Health'"},
                        "to_node": {"type": "string", "description": "Target node ID or node name"},
                        "to_pin": {"type": "string", "description": "Target pin name e.g. 'execute', 'NewHealth', 'Target'"}
                    },
                    "required": ["blueprint_path", "from_node", "from_pin", "to_node", "to_pin"]
                }
            ),

            types.Tool(
                name="blueprint_add_component",
                description="""Add a component to a Blueprint (Components panel).
Supports all standard UE components: StaticMeshComponent, SkeletalMeshComponent,
CapsuleComponent, SphereComponent, BoxComponent, CharacterMovementComponent,
SpringArmComponent, CameraComponent, AudioComponent, ParticleSystemComponent,
NiagaraComponent, PointLightComponent, SpotLightComponent, WidgetComponent, etc.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"},
                        "component_class": {"type": "string", "description": "Component class name e.g. StaticMeshComponent, CameraComponent"},
                        "component_name": {"type": "string", "description": "Name for this component instance"},
                        "attach_to": {"type": "string", "description": "Parent component name to attach to", "default": "RootComponent"},
                        "properties": {
                            "type": "object",
                            "description": "Initial property values e.g. {\"RelativeLocation\": {\"X\": 0, \"Y\": 0, \"Z\": 90}}",
                            "default": {}
                        }
                    },
                    "required": ["blueprint_path", "component_class", "component_name"]
                }
            ),

            types.Tool(
                name="blueprint_add_interface",
                description="Add a Blueprint Interface to a Blueprint class.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"},
                        "interface_path": {"type": "string", "description": "Full content path to the Blueprint Interface asset"}
                    },
                    "required": ["blueprint_path", "interface_path"]
                }
            ),

            types.Tool(
                name="blueprint_add_dispatcher",
                description="Add an Event Dispatcher to a Blueprint.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"},
                        "name": {"type": "string", "description": "Dispatcher name e.g. OnHealthChanged"},
                        "parameters": {
                            "type": "array",
                            "items": {"type": "object", "properties": {"name": {"type": "string"}, "type": {"type": "string"}}},
                            "default": []
                        }
                    },
                    "required": ["blueprint_path", "name"]
                }
            ),

            types.Tool(
                name="blueprint_set_construction_script",
                description="""Build the Construction Script for a Blueprint.
The construction script runs when the actor is placed in the world or properties change.
Use this for Leader Pose Component setup, mesh assignment, component configuration, etc.
Provide node instructions as a structured list — this tool builds the entire graph.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"},
                        "nodes": {
                            "type": "array",
                            "description": "List of node operations to build the construction script",
                            "items": {"type": "object"}
                        },
                        "setup_leader_pose": {"type": "boolean", "description": "Auto-add Leader Pose Component setup nodes", "default": False},
                        "leader_mesh_variable": {"type": "string", "description": "Variable name of the leader skeletal mesh component"},
                        "follower_mesh_variables": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Variable names of follower mesh components that copy pose from leader"
                        }
                    },
                    "required": ["blueprint_path"]
                }
            ),

            types.Tool(
                name="blueprint_compile",
                description="""Compile a Blueprint and return all errors and warnings.
Always compile after making changes. If errors are returned, fix them before saving.
Returns: compile_result (Success/Failed), errors list, warnings list.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"},
                        "save_on_success": {"type": "boolean", "description": "Save the Blueprint if compilation succeeds", "default": True}
                    },
                    "required": ["blueprint_path"]
                }
            ),

            types.Tool(
                name="blueprint_save",
                description="Save a Blueprint asset to disk.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"}
                    },
                    "required": ["blueprint_path"]
                }
            ),

            types.Tool(
                name="blueprint_read",
                description="""Read a Blueprint and return its full structure as JSON.
Returns: parent class, variables, functions, components, interfaces, dispatchers,
event graph nodes, and compile status. Use this to inspect existing Blueprints.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"}
                    },
                    "required": ["blueprint_path"]
                }
            ),

            types.Tool(
                name="blueprint_validate",
                description="""Validate a Blueprint for common issues without compiling.
Checks: broken pins, missing references, unused variables, unconnected exec nodes,
circular dependencies, missing parent class, empty functions.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"}
                    },
                    "required": ["blueprint_path"]
                }
            ),

            types.Tool(
                name="blueprint_delete",
                description="Delete a Blueprint asset from the content browser.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"},
                        "confirm": {"type": "boolean", "description": "Must be true to confirm deletion", "default": False}
                    },
                    "required": ["blueprint_path", "confirm"]
                }
            ),

            types.Tool(
                name="blueprint_reparent",
                description="Change the parent class of a Blueprint.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"},
                        "new_parent_class": {"type": "string", "description": "New parent class name or content path"}
                    },
                    "required": ["blueprint_path", "new_parent_class"]
                }
            ),

            types.Tool(
                name="blueprint_add_timeline",
                description="""Add a Timeline node to a Blueprint graph.
Timelines handle interpolated value changes over time.
Use for: door opening, elevator movement, light flickering, platform movement, camera effects.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"},
                        "graph": {"type": "string", "description": "Graph to add timeline to", "default": "EventGraph"},
                        "timeline_name": {"type": "string", "description": "Timeline name e.g. DoorOpenTimeline"},
                        "length": {"type": "number", "description": "Timeline length in seconds", "default": 1.0},
                        "loop": {"type": "boolean", "description": "Loop the timeline", "default": False},
                        "tracks": {
                            "type": "array",
                            "description": "Tracks to add: float, vector, color, event",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "description": "Track type: float, vector, color, event"},
                                    "name": {"type": "string", "description": "Track name"},
                                    "keyframes": {
                                        "type": "array",
                                        "description": "Keyframes as [{time: 0.0, value: 0.0}, {time: 1.0, value: 1.0}]",
                                        "items": {"type": "object"}
                                    }
                                }
                            },
                            "default": []
                        }
                    },
                    "required": ["blueprint_path", "timeline_name"]
                }
            ),

        ]

    # ─────────────────────────────────────────────
    # Tool Handler (routes to correct method)
    # ─────────────────────────────────────────────

    async def handle(self, name: str, args: dict) -> list[types.TextContent]:
        handlers = {
            "blueprint_create":             self._create,
            "blueprint_add_variable":       self._add_variable,
            "blueprint_add_function":       self._add_function,
            "blueprint_add_event":          self._add_event,
            "blueprint_add_node":           self._add_node,
            "blueprint_connect_pins":       self._connect_pins,
            "blueprint_add_component":      self._add_component,
            "blueprint_add_interface":      self._add_interface,
            "blueprint_add_dispatcher":     self._add_dispatcher,
            "blueprint_set_construction_script": self._set_construction_script,
            "blueprint_compile":            self._compile,
            "blueprint_save":               self._save,
            "blueprint_read":               self._read,
            "blueprint_validate":           self._validate,
            "blueprint_delete":             self._delete,
            "blueprint_reparent":           self._reparent,
            "blueprint_add_timeline":       self._add_timeline,
        }
        handler = handlers.get(name)
        if not handler:
            return [types.TextContent(type="text", text=f"Unknown Blueprint tool: {name}")]
        return await handler(args)


    # ─────────────────────────────────────────────
    # Implementations
    # ─────────────────────────────────────────────

    async def _create(self, args: dict) -> list[types.TextContent]:
        name = args["name"]
        path = args["path"].rstrip("/")
        parent_class = args.get("parent_class", "Actor")

        class_map = {
            "Actor":                    "/Script/Engine.Actor",
            "Character":                "/Script/Engine.Character",
            "Pawn":                     "/Script/Engine.Pawn",
            "ActorComponent":           "/Script/Engine.ActorComponent",
            "SceneComponent":           "/Script/Engine.SceneComponent",
            "GameMode":                 "/Script/Engine.GameModeBase",
            "GameModeBase":             "/Script/Engine.GameModeBase",
            "GameState":                "/Script/Engine.GameStateBase",
            "GameStateBase":            "/Script/Engine.GameStateBase",
            "PlayerController":         "/Script/Engine.PlayerController",
            "AIController":             "/Script/AIModule.AIController",
            "AnimInstance":             "/Script/Engine.AnimInstance",
            "UserWidget":               "/Script/UMG.UserWidget",
            "BlueprintFunctionLibrary": "/Script/Engine.BlueprintFunctionLibrary",
            "GameInstance":             "/Script/Engine.GameInstance",
            "PlayerState":              "/Script/Engine.PlayerState",
            "SaveGame":                 "/Script/Engine.SaveGame",
        }
        ue_class = class_map.get(parent_class, parent_class)

        script = f"""
import unreal, json, traceback
try:
    unreal.EditorAssetLibrary.make_directory("{path}")
    asset_path = "{path}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        print("UEOS_RESULT:" + json.dumps({{"status": "exists", "path": asset_path, "message": "Blueprint already exists"}}))
    else:
        parent_cls = unreal.load_class(None, "{ue_class}")
        if parent_cls is None:
            parent_obj = unreal.EditorAssetLibrary.load_asset("{ue_class}")
            if parent_obj:
                parent_cls = parent_obj.generated_class()
        if parent_cls is None:
            print("UEOS_ERROR:Could not resolve parent class: {ue_class}")
        else:
            factory = unreal.BlueprintFactory()
            factory.parent_class = parent_cls
            at = unreal.AssetToolsHelpers.get_asset_tools()
            bp = at.create_asset("{name}", "{path}", None, factory)
            if bp:
                unreal.BlueprintEditorLibrary.compile_blueprint(bp)
                unreal.EditorAssetLibrary.save_asset(asset_path)
                print("UEOS_RESULT:" + json.dumps({{"status": "created", "path": asset_path, "parent": "{ue_class}"}}))
            else:
                print("UEOS_ERROR:create_asset returned None — check UE output log for details")
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _add_variable(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        var_name = args["name"]
        var_type = args["type"].lower()
        is_exposed = args.get("is_exposed", False)
        category = args.get("category", "Default")

        # Map to (pin_category, pin_sub_category_object_path)
        # These are the exact values UE's FEdGraphPinType uses
        type_map = {
            "bool":       ("bool",   ""),
            "boolean":    ("bool",   ""),
            "int":        ("int",    ""),
            "integer":    ("int",    ""),
            "int64":      ("int64",  ""),
            "float":      ("real",   "float"),
            "double":     ("real",   "double"),
            "string":     ("string", ""),
            "name":       ("name",   ""),
            "text":       ("text",   ""),
            "vector":     ("struct", "/Script/CoreUObject.Vector"),
            "rotator":    ("struct", "/Script/CoreUObject.Rotator"),
            "transform":  ("struct", "/Script/CoreUObject.Transform"),
            "linearcolor":("struct", "/Script/CoreUObject.LinearColor"),
            "color":      ("struct", "/Script/CoreUObject.LinearColor"),
            "vector2d":   ("struct", "/Script/CoreUObject.Vector2D"),
            "actor":      ("object", "/Script/Engine.Actor"),
            "staticmeshcomponent": ("object", "/Script/Engine.StaticMeshComponent"),
            "skeletalmeshcomponent":("object","/Script/Engine.SkeletalMeshComponent"),
        }

        pin_cat, pin_sub = type_map.get(var_type, ("bool", ""))
        # If not in map, treat as object reference to class path
        if var_type not in type_map:
            pin_cat = "object"
            pin_sub = var_type  # pass raw — user might give full path

        script = f"""
import unreal, json, traceback
try:
    bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
    if bp is None:
        print("UEOS_ERROR:Blueprint not found: {bp_path}")
    else:
        pin_type = unreal.EdGraphPinType()
        pin_type.pin_category = "{pin_cat}"
        sub_path = "{pin_sub}"
        if sub_path:
            if sub_path.startswith("/Script/"):
                if "{pin_cat}" == "struct":
                    pin_type.pin_sub_category_object = unreal.load_struct(None, sub_path)
                else:
                    pin_type.pin_sub_category_object = unreal.load_class(None, sub_path)
        result = unreal.BlueprintEditorLibrary.add_member_variable(bp, "{var_name}", pin_type)
        if result:
            unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(bp, "{var_name}", {str(is_exposed).lower()})
            unreal.BlueprintEditorLibrary.set_blueprint_variable_expose_on_spawn(bp, "{var_name}", {str(is_exposed).lower()})
            bp.modify()
            unreal.EditorAssetLibrary.save_asset("{bp_path}")
            print("UEOS_RESULT:" + json.dumps({{"status": "success", "variable": "{var_name}", "type": "{var_type}", "blueprint": "{bp_path}"}}))
        else:
            print("UEOS_ERROR:add_member_variable returned False for {var_name} — variable may already exist")
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _add_function(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        func_name = args["name"]

        script = f"""
import unreal, json, traceback
try:
    bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
    if bp is None:
        print("UEOS_ERROR:Blueprint not found: {bp_path}")
    else:
        graph = unreal.BlueprintEditorLibrary.add_function_graph(bp, "{func_name}")
        if graph:
            bp.modify()
            unreal.EditorAssetLibrary.save_asset("{bp_path}")
            print("UEOS_RESULT:" + json.dumps({{"status": "success", "function": "{func_name}", "blueprint": "{bp_path}"}}))
        else:
            print("UEOS_ERROR:add_function_graph returned None for {func_name}")
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _add_event(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        event_name = args["name"]

        script = f"""
import unreal, json, traceback
try:
    bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
    if bp is None:
        print("UEOS_ERROR:Blueprint not found: {bp_path}")
    else:
        node = unreal.BlueprintEditorLibrary.add_custom_event(bp, "{event_name}")
        if node:
            bp.modify()
            unreal.EditorAssetLibrary.save_asset("{bp_path}")
            print("UEOS_RESULT:" + json.dumps({{"status": "success", "event": "{event_name}", "blueprint": "{bp_path}"}}))
        else:
            print("UEOS_ERROR:add_custom_event returned None for {event_name}")
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _add_component(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        component_class = args["component_class"]
        component_name = args["component_name"]

        # Try multiple known module paths for the component class
        script = f"""
import unreal, json, traceback
try:
    bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
    if bp is None:
        print("UEOS_ERROR:Blueprint not found: {bp_path}")
    else:
        comp_class = None
        for module in ["/Script/Engine", "/Script/UMG", "/Script/AIModule", "/Script/NavigationSystem"]:
            comp_class = unreal.load_class(None, module + ".{component_class}")
            if comp_class:
                break
        if comp_class is None:
            print("UEOS_ERROR:Component class not found: {component_class} — tried Engine, UMG, AIModule, NavigationSystem")
        else:
            comp = unreal.BlueprintEditorLibrary.add_component(bp, comp_class, "{component_name}")
            if comp:
                bp.modify()
                unreal.EditorAssetLibrary.save_asset("{bp_path}")
                print("UEOS_RESULT:" + json.dumps({{"status": "success", "component": "{component_name}", "class": "{component_class}", "blueprint": "{bp_path}"}}))
            else:
                print("UEOS_ERROR:add_component returned None for {component_name}")
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _add_interface(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        interface_path = args["interface_path"]

        script = f"""
import unreal, json, traceback
try:
    bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
    iface = unreal.EditorAssetLibrary.load_asset("{interface_path}")
    if bp is None:
        print("UEOS_ERROR:Blueprint not found: {bp_path}")
    elif iface is None:
        print("UEOS_ERROR:Interface not found: {interface_path}")
    else:
        unreal.BlueprintEditorLibrary.add_interface(bp, iface.generated_class())
        bp.modify()
        unreal.EditorAssetLibrary.save_asset("{bp_path}")
        print("UEOS_RESULT:" + json.dumps({{"status": "success", "interface": "{interface_path}", "blueprint": "{bp_path}"}}))
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _add_dispatcher(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        name = args["name"]

        script = f"""
import unreal, json, traceback
try:
    bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
    if bp is None:
        print("UEOS_ERROR:Blueprint not found: {bp_path}")
    else:
        dispatcher = unreal.BlueprintEditorLibrary.add_event_dispatcher(bp, "{name}")
        if dispatcher:
            bp.modify()
            unreal.EditorAssetLibrary.save_asset("{bp_path}")
            print("UEOS_RESULT:" + json.dumps({{"status": "success", "dispatcher": "{name}", "blueprint": "{bp_path}"}}))
        else:
            print("UEOS_ERROR:add_event_dispatcher returned None for {name}")
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _add_node(self, args: dict) -> list[types.TextContent]:
        # Node editing via Python is severely limited in UE 5.4 — BlueprintEditorLibrary
        # exposes only high-level operations. Return clear info about what's possible.
        bp_path = args["blueprint_path"]
        node_type = args.get("node_type", "")
        return [types.TextContent(type="text", text=json.dumps({
            "status": "info",
            "message": (
                "blueprint_add_node is limited in UE 5.4 Python API. "
                "Use ueos_run_python with BlueprintEditorLibrary for specific node operations. "
                f"Requested: {node_type} in {bp_path}"
            )
        }, indent=2))]

    async def _connect_pins(self, args: dict) -> list[types.TextContent]:
        return [types.TextContent(type="text", text=json.dumps({
            "status": "info",
            "message": "Pin connection requires KismetEditorUtilities which is not exposed to Python in UE 5.4. Use ueos_run_python for graph-level operations."
        }, indent=2))]

    async def _set_construction_script(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        return [types.TextContent(type="text", text=json.dumps({
            "status": "info",
            "message": f"Construction script graph editing via Python is limited in UE 5.4. Blueprint at {bp_path} must be opened in editor to add construction script nodes."
        }, indent=2))]

    async def _compile(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        save_on_success = args.get("save_on_success", True)

        script = f"""
import unreal, json, traceback
try:
    bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
    if bp is None:
        print("UEOS_ERROR:Blueprint not found: {bp_path}")
    else:
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        if {str(save_on_success).lower()}:
            unreal.EditorAssetLibrary.save_asset("{bp_path}")
        print("UEOS_RESULT:" + json.dumps({{"status": "compiled", "saved": {str(save_on_success).lower()}, "blueprint": "{bp_path}"}}))
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _save(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]

        script = f"""
import unreal, json, traceback
try:
    ok = unreal.EditorAssetLibrary.save_asset("{bp_path}")
    print("UEOS_RESULT:" + json.dumps({{"status": "saved" if ok else "failed", "path": "{bp_path}"}}))
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _read(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]

        script = f"""
import unreal, json, traceback
try:
    bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
    if bp is None:
        print("UEOS_ERROR:Blueprint not found: {bp_path}")
    else:
        data = {{"path": "{bp_path}", "name": bp.get_name(), "variables": [], "functions": [], "components": [], "graphs": []}}
        try:
            gen = bp.generated_class()
            if gen:
                parent = gen.get_super_class()
                data["parent_class"] = parent.get_name() if parent else "Unknown"
        except:
            data["parent_class"] = "Unknown"
        try:
            for v in bp.get_all_member_variables():
                vt = v.variable_type
                data["variables"].append({{"name": str(v.variable_name), "category": str(vt.pin_category)}})
        except:
            pass
        try:
            for g in bp.get_all_graphs():
                gname = g.get_name()
                data["graphs"].append(gname)
                if gname not in ("EventGraph", "ConstructionScript"):
                    data["functions"].append(gname)
        except:
            pass
        try:
            eod = bp.get_editor_only_data()
            for c in eod.component_templates:
                data["components"].append({{"name": c.get_name(), "class": c.get_class().get_name()}})
        except:
            pass
        print("UEOS_RESULT:" + json.dumps(data))
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _validate(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]

        script = f"""
import unreal, json, traceback
try:
    bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
    if bp is None:
        print("UEOS_ERROR:Blueprint not found: {bp_path}")
    else:
        issues = []
        try:
            gen = bp.generated_class()
            if gen is None:
                issues.append({{"severity": "error", "message": "No generated class"}})
        except Exception as ex:
            issues.append({{"severity": "error", "message": str(ex)}})
        print("UEOS_RESULT:" + json.dumps({{"blueprint": "{bp_path}", "issues": issues, "valid": len(issues) == 0}}))
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _delete(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        confirm = args.get("confirm", False)
        if not confirm:
            return [types.TextContent(type="text", text=json.dumps({"status": "cancelled", "message": "Set confirm=true to delete"}))]

        script = f"""
import unreal, json, traceback
try:
    ok = unreal.EditorAssetLibrary.delete_asset("{bp_path}")
    print("UEOS_RESULT:" + json.dumps({{"status": "deleted" if ok else "failed", "path": "{bp_path}"}}))
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _reparent(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        new_parent = args["new_parent_class"]

        script = f"""
import unreal, json, traceback
try:
    bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
    new_cls = unreal.load_class(None, "{new_parent}")
    if bp and new_cls:
        unreal.BlueprintEditorLibrary.reparent_blueprint(bp, new_cls)
        bp.modify()
        unreal.EditorAssetLibrary.save_asset("{bp_path}")
        print("UEOS_RESULT:" + json.dumps({{"status": "success", "new_parent": "{new_parent}", "blueprint": "{bp_path}"}}))
    else:
        print("UEOS_ERROR:Blueprint or parent class not found: {bp_path} / {new_parent}")
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _add_timeline(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        timeline_name = args["timeline_name"]
        return [types.TextContent(type="text", text=json.dumps({
            "status": "info",
            "message": f"Timeline nodes require direct editor interaction in UE 5.4. Blueprint at {bp_path} — open the Blueprint Editor, right-click EventGraph, search 'Add Timeline' and name it '{timeline_name}'."
        }, indent=2))]

    # ─────────────────────────────────────────────
    # Shared output parser
    # ─────────────────────────────────────────────

    def _parse_result(self, result: dict) -> list[types.TextContent]:
        output = result.get("output", "")
        for line in output.replace("\r", "").split("\n"):
            line = line.strip()
            if line.startswith("UEOS_RESULT:"):
                try:
                    data = json.loads(line[len("UEOS_RESULT:"):])
                except Exception:
                    data = {"raw": line[len("UEOS_RESULT:"):]}
                return [types.TextContent(type="text", text=json.dumps(data, indent=2))]
            if line.startswith("UEOS_ERROR:"):
                error = line[len("UEOS_ERROR:"):]
                return [types.TextContent(type="text", text=json.dumps({"status": "error", "message": error}, indent=2))]
        # No marker found — return raw output so the error is visible
        return [types.TextContent(type="text", text=json.dumps({
            "status": "error",
            "message": "No output received from UE",
            "raw_output": output[:1000],
            "success": result.get("success", False)
        }, indent=2))]
