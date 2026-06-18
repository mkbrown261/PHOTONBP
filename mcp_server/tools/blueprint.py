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
                name="blueprint_get_graph_nodes",
                description="""Inspect all nodes in a Blueprint graph.
Returns a JSON list with each node's GUID, type, title, and all pin names/directions.
Use this BEFORE connecting pins to find the correct GUID and pin names.
Always call this after blueprint_add_node to get the node_id for connections.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"},
                        "graph": {"type": "string", "description": "Graph name: EventGraph, or a function graph name", "default": "EventGraph"}
                    },
                    "required": ["blueprint_path"]
                }
            ),

            types.Tool(
                name="blueprint_set_pin_value",
                description="""Set the default/literal value of a pin on a Blueprint node.
Use for pins that have no incoming connection (e.g. a float literal, string default).
The node_id is the GUID string returned by blueprint_add_node or blueprint_get_graph_nodes.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blueprint_path": {"type": "string", "description": "Full content path to the Blueprint"},
                        "graph": {"type": "string", "description": "Graph name", "default": "EventGraph"},
                        "node_id": {"type": "string", "description": "Node GUID from blueprint_add_node or blueprint_get_graph_nodes"},
                        "pin_name": {"type": "string", "description": "Pin name e.g. 'PrintString', 'Duration', 'NewValue'"},
                        "value": {"type": "string", "description": "Value as string e.g. '3.14', 'Hello World', 'true'"}
                    },
                    "required": ["blueprint_path", "node_id", "pin_name", "value"]
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
            "blueprint_get_graph_nodes":    self._get_graph_nodes,
            "blueprint_set_pin_value":      self._set_pin_value,
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
            factory.set_editor_property("ParentClass", parent_cls)
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

        # Map type string to (PinCategory, PinSubCategory, PinSubCategoryObjectPath)
        type_map = {
            "bool":               ("bool",   "",       ""),
            "boolean":            ("bool",   "",       ""),
            "int":                ("int",    "",       ""),
            "integer":            ("int",    "",       ""),
            "int64":              ("int64",  "",       ""),
            "float":              ("real",   "float",  ""),
            "double":             ("real",   "double", ""),
            "string":             ("string", "",       ""),
            "name":               ("name",   "",       ""),
            "text":               ("text",   "",       ""),
            "vector":             ("struct", "",       "/Script/CoreUObject.Vector"),
            "rotator":            ("struct", "",       "/Script/CoreUObject.Rotator"),
            "transform":          ("struct", "",       "/Script/CoreUObject.Transform"),
            "linearcolor":        ("struct", "",       "/Script/CoreUObject.LinearColor"),
            "color":              ("struct", "",       "/Script/CoreUObject.LinearColor"),
            "vector2d":           ("struct", "",       "/Script/CoreUObject.Vector2D"),
            "actor":              ("object", "",       "/Script/Engine.Actor"),
            "animsequencebase":   ("object", "",       "/Script/Engine.AnimSequenceBase"),
            "soundbase":          ("object", "",       "/Script/Engine.SoundBase"),
            "staticmeshcomponent":("object", "",       "/Script/Engine.StaticMeshComponent"),
            "skeletalmeshcomponent":("object","",      "/Script/Engine.SkeletalMeshComponent"),
        }

        if var_type in type_map:
            pin_cat, pin_sub_cat, pin_sub_obj = type_map[var_type]
        else:
            pin_cat, pin_sub_cat, pin_sub_obj = "object", "", var_type

        ie_str = "True" if is_exposed else "False"

        script = f"""
import unreal, json, traceback
try:
    bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
    if bp is None:
        print("UEOS_ERROR:Blueprint not found: {bp_path}")
    else:
        result = unreal.PhotonBPLibrary.add_member_variable(bp, "{var_name}", "{pin_cat}", "{pin_sub_cat}", "{pin_sub_obj}")
        if result:
            unreal.PhotonBPLibrary.set_variable_flags(bp, "{var_name}", {ie_str}, {ie_str})
            unreal.BlueprintEditorLibrary.compile_blueprint(bp)
            unreal.EditorAssetLibrary.save_asset("{bp_path}")
            print("UEOS_RESULT:" + json.dumps({{"status": "success", "variable": "{var_name}", "type": "{var_type}", "blueprint": "{bp_path}"}}))
        else:
            print("UEOS_ERROR:add_member_variable returned False for {var_name}")
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
        result = unreal.PhotonBPLibrary.add_custom_event(bp, "{event_name}")
        if result:
            unreal.BlueprintEditorLibrary.compile_blueprint(bp)
            unreal.EditorAssetLibrary.save_asset("{bp_path}")
            print("UEOS_RESULT:" + json.dumps({{"status": "success", "event": "{event_name}", "blueprint": "{bp_path}"}}))
        else:
            print("UEOS_ERROR:add_custom_event returned False for {event_name}")
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
        disp_name = args["name"]

        script = f"""
import unreal, json, traceback
try:
    bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
    if bp is None:
        print("UEOS_ERROR:Blueprint not found: {bp_path}")
    else:
        result = unreal.PhotonBPLibrary.add_event_dispatcher(bp, "{disp_name}")
        if result:
            unreal.BlueprintEditorLibrary.compile_blueprint(bp)
            unreal.EditorAssetLibrary.save_asset("{bp_path}")
            print("UEOS_RESULT:" + json.dumps({{"status": "success", "dispatcher": "{disp_name}", "blueprint": "{bp_path}"}}))
        else:
            print("UEOS_ERROR:add_event_dispatcher returned False for {disp_name}")
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _add_node(self, args: dict) -> list[types.TextContent]:
        bp_path    = args["blueprint_path"]
        graph      = args.get("graph", "EventGraph")
        node_type  = args.get("node_type", "")
        # Track whether caller supplied explicit positions
        has_x      = "position_x" in args
        has_y      = "position_y" in args
        x          = int(args.get("position_x", 0))
        y          = int(args.get("position_y", 0))

        # ── Duplicate-identity key ─────────────────────────────────────────────
        # Used to detect an already-existing equivalent node so we never stack.
        # Format: a string that uniquely identifies this logical node.
        func        = args.get("function", "")
        event_name  = args.get("event", func or "ReceiveBeginPlay")
        var         = args.get("variable_name", func or "")
        target      = args.get("target", "")
        cls_map = {
            # System / debug
            "PrintString":                    "KismetSystemLibrary",
            "DrawDebugString":                "KismetSystemLibrary",
            "DrawDebugSphere":                "KismetSystemLibrary",
            "DrawDebugLine":                  "KismetSystemLibrary",
            "IsValid":                        "KismetSystemLibrary",
            "GetObjectName":                  "KismetSystemLibrary",
            # Gameplay
            "GetGameInstance":                "GameplayStatics",
            "GetPlayerPawn":                  "GameplayStatics",
            "GetPlayerController":            "GameplayStatics",
            "GetPlayerCharacter":             "GameplayStatics",
            "SpawnActor":                     "GameplayStatics",
            "SpawnActorFromClass":            "GameplayStatics",
            "ApplyDamage":                    "GameplayStatics",
            "ApplyPointDamage":               "GameplayStatics",
            "GetAllActorsOfClass":            "GameplayStatics",
            "OpenLevel":                      "GameplayStatics",
            "GetWorldDeltaSeconds":           "GameplayStatics",
            "SetTimerByFunctionName":         "GameplayStatics",
            "ClearAndInvalidateTimerByHandle":"GameplayStatics",
            # Math — float (all in KismetMathLibrary)
            "Add_FloatFloat":                 "KismetMathLibrary",
            "Subtract_FloatFloat":            "KismetMathLibrary",
            "Multiply_FloatFloat":            "KismetMathLibrary",
            "Divide_FloatFloat":              "KismetMathLibrary",
            "SafeDivide":                     "KismetMathLibrary",
            "FClamp":                         "KismetMathLibrary",
            "FMin":                           "KismetMathLibrary",
            "FMax":                           "KismetMathLibrary",
            "FInterpTo":                      "KismetMathLibrary",
            "FInterpConstantTo":              "KismetMathLibrary",
            "Lerp":                           "KismetMathLibrary",
            "NormalizeToRange":               "KismetMathLibrary",
            "MapRangeClamped":                "KismetMathLibrary",
            "MapRangeUnclamped":              "KismetMathLibrary",
            "Abs":                            "KismetMathLibrary",
            "FMod":                           "KismetMathLibrary",
            "Square":                         "KismetMathLibrary",
            "Sqrt":                           "KismetMathLibrary",
            "Pow":                            "KismetMathLibrary",
            # Math — int
            "Add_IntInt":                     "KismetMathLibrary",
            "Subtract_IntInt":                "KismetMathLibrary",
            "Multiply_IntInt":                "KismetMathLibrary",
            "Divide_IntInt":                  "KismetMathLibrary",
            "Clamp":                          "KismetMathLibrary",
            "Min":                            "KismetMathLibrary",
            "Max":                            "KismetMathLibrary",
            # Math — vector
            "Add_VectorVector":               "KismetMathLibrary",
            "Subtract_VectorVector":          "KismetMathLibrary",
            "Multiply_VectorFloat":           "KismetMathLibrary",
            "VSize":                          "KismetMathLibrary",
            "Normal":                         "KismetMathLibrary",
            "Dot_VectorVector":               "KismetMathLibrary",
            "Cross_VectorVector":             "KismetMathLibrary",
            "VLerp":                          "KismetMathLibrary",
            "MakeVector":                     "KismetMathLibrary",
            "BreakVector":                    "KismetMathLibrary",
            # Math — rotator
            "MakeRotator":                    "KismetMathLibrary",
            "BreakRotator":                   "KismetMathLibrary",
            "ComposeRotators":                "KismetMathLibrary",
            "RInterpTo":                      "KismetMathLibrary",
            "FindLookAtRotation":             "KismetMathLibrary",
            # Math — bool/comparison
            "Greater_FloatFloat":             "KismetMathLibrary",
            "Less_FloatFloat":                "KismetMathLibrary",
            "GreaterEqual_FloatFloat":        "KismetMathLibrary",
            "LessEqual_FloatFloat":           "KismetMathLibrary",
            "EqualEqual_FloatFloat":          "KismetMathLibrary",
            "NotEqual_FloatFloat":            "KismetMathLibrary",
            "BooleanAND":                     "KismetMathLibrary",
            "BooleanOR":                      "KismetMathLibrary",
            "NOT_PreBool":                    "KismetMathLibrary",
            # String
            "Conv_FloatToString":             "KismetStringLibrary",
            "Conv_IntToString":               "KismetStringLibrary",
            "Conv_BoolToString":              "KismetStringLibrary",
            "Append":                         "KismetStringLibrary",
            "BuildString_Float":              "KismetStringLibrary",
            # Widget
            "CreateWidget":                   "WidgetBlueprintLibrary",
            "GetAllWidgetsOfClass":           "WidgetBlueprintLibrary",
        }
        class_name = args.get("class_name", cls_map.get(func, target or "KismetMathLibrary"))

        # identity_fragment is matched against GetGraphNodes "name" field
        if node_type in ("event", "custom_event"):
            identity_fragment = event_name          # e.g. "ReceiveBeginPlay"
        elif node_type == "function":
            identity_fragment = func                # e.g. "PrintString"
        elif node_type in ("variable_get", "variable_set"):
            identity_fragment = var                 # e.g. "Health"
        else:
            identity_fragment = ""                  # branch/sequence/cast: never dedup

        # ── Build the PhotonBPLibrary placement call ───────────────────────────
        if node_type == "custom_event":
            call = f'unreal.PhotonBPLibrary.add_custom_event(bp, "{event_name}", _x, _y)'

        elif node_type == "event":
            call = f'unreal.PhotonBPLibrary.add_event_node(bp, "{graph}", "{event_name}", _x, _y)'

        elif node_type == "function":
            call = f'unreal.PhotonBPLibrary.add_function_call_node(bp, "{graph}", "{class_name}", "{func}", _x, _y)'

        elif node_type == "variable_get":
            call = f'unreal.PhotonBPLibrary.add_variable_get_node(bp, "{graph}", "{var}", _x, _y)'

        elif node_type == "variable_set":
            call = f'unreal.PhotonBPLibrary.add_variable_set_node(bp, "{graph}", "{var}", _x, _y)'

        elif node_type in ("branch", "if", "if_then_else"):
            call = f'unreal.PhotonBPLibrary.add_branch_node(bp, "{graph}", _x, _y)'

        elif node_type == "sequence":
            call = f'unreal.PhotonBPLibrary.add_sequence_node(bp, "{graph}", _x, _y)'

        elif node_type == "cast":
            cls = args.get("class_name", args.get("target", ""))
            call = f'unreal.PhotonBPLibrary.add_cast_node(bp, "{graph}", "{cls}", _x, _y)'

        else:
            return [types.TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": (
                    f"Unsupported node_type: '{node_type}'. "
                    "Supported: custom_event, event, function, variable_get, variable_set, "
                    "branch, sequence, cast"
                )
            }, indent=2))]

        # ── Python script — dedup check + auto-position + placement ───────────
        script = f"""
import unreal, json, traceback
try:
    bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
    if bp is None:
        print("UEOS_ERROR:Blueprint not found: {bp_path}")
    else:
        # ── Step 1: scan existing nodes for a duplicate ──────────────────────
        existing_guid  = None
        existing_nodes = json.loads(unreal.PhotonBPLibrary.get_graph_nodes(bp, "{graph}") or "[]")
        identity       = "{identity_fragment}".lower()

        if identity:
            for n in existing_nodes:
                node_name = n.get("name", "").lower()
                node_type_str = n.get("type", "").lower()
                # Match event nodes by their title containing the event name
                if identity in node_name:
                    # For variable_get vs variable_set, check UE node type string
                    if "{node_type}" == "variable_get" and "get" not in node_type_str:
                        continue
                    if "{node_type}" == "variable_set" and "set" not in node_type_str:
                        continue
                    existing_guid = n["guid"]
                    break

        if existing_guid:
            # Return the existing node — no duplicate created
            print("UEOS_RESULT:" + json.dumps({{
                "status":    "already_exists",
                "node_id":   existing_guid,
                "node_type": "{node_type}",
                "graph":     "{graph}",
                "blueprint": "{bp_path}",
                "note":      "Returned existing node GUID — no duplicate created",
            }}))
        else:
            # ── Step 2: auto-calculate position if not supplied ──────────────
            # Spread nodes 400px apart in X, 200px rows every 8 nodes
            # Caller-supplied positions always take priority.
            _has_x = {str(has_x).lower()}
            _has_y = {str(has_y).lower()}
            if _has_x:
                _x = {x}
            else:
                n_nodes = len(existing_nodes)
                col     = n_nodes % 8          # wrap to new row every 8
                row     = n_nodes // 8
                _x      = col * 400
                _y      = row * 250 if not _has_y else {y}

            if _has_y:
                _y = {y}
            elif not _has_x:
                pass  # _y already set above
            else:
                # x was supplied but y was not — keep y=0 unless nodes exist
                n_nodes = len(existing_nodes)
                row     = n_nodes // 8
                _y      = row * 250

            # ── Step 3: place the node ───────────────────────────────────────
            node_guid = {call}
            if node_guid:
                unreal.BlueprintEditorLibrary.compile_blueprint(bp)
                unreal.EditorAssetLibrary.save_asset("{bp_path}")
                print("UEOS_RESULT:" + json.dumps({{
                    "status":    "success",
                    "node_id":   node_guid,
                    "node_type": "{node_type}",
                    "graph":     "{graph}",
                    "blueprint": "{bp_path}",
                    "position":  {{"x": _x, "y": _y}},
                }}))
            else:
                print("UEOS_ERROR:add node returned empty GUID — node_type={node_type}, graph={graph}")
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _connect_pins(self, args: dict) -> list[types.TextContent]:
        bp_path   = args["blueprint_path"]
        graph     = args.get("graph", "EventGraph")
        from_node = args["from_node"]
        from_pin  = args["from_pin"]
        to_node   = args["to_node"]
        to_pin    = args["to_pin"]

        script = f"""
import unreal, json, traceback
try:
    bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
    if bp is None:
        print("UEOS_ERROR:Blueprint not found: {bp_path}")
    else:
        ok = unreal.PhotonBPLibrary.connect_pins(
            bp, "{graph}",
            "{from_node}", "{from_pin}",
            "{to_node}",   "{to_pin}"
        )
        if ok:
            unreal.BlueprintEditorLibrary.compile_blueprint(bp)
            unreal.EditorAssetLibrary.save_asset("{bp_path}")
            print("UEOS_RESULT:" + json.dumps({{"status": "connected", "from": "{from_node}.{from_pin}", "to": "{to_node}.{to_pin}", "graph": "{graph}", "blueprint": "{bp_path}"}}  ))
        else:
            print("UEOS_ERROR:connect_pins failed — check node GUIDs and pin names are correct")
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _get_graph_nodes(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        graph   = args.get("graph", "EventGraph")

        script = f"""
import unreal, json, traceback
try:
    bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
    if bp is None:
        print("UEOS_ERROR:Blueprint not found: {bp_path}")
    else:
        raw = unreal.PhotonBPLibrary.get_graph_nodes(bp, "{graph}")
        print("UEOS_RESULT:" + raw)
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        # _parse_result looks for UEOS_RESULT: prefix, but raw is already a JSON array.
        # Wrap it for consistent output.
        output = result.get("output", "")
        for line in output.replace("\r", "").split("\n"):
            line = line.strip()
            if line.startswith("UEOS_RESULT:"):
                raw = line[len("UEOS_RESULT:"):]
                try:
                    nodes = json.loads(raw)
                    return [types.TextContent(type="text", text=json.dumps(
                        {"status": "success", "graph": graph, "blueprint": bp_path, "nodes": nodes},
                        indent=2
                    ))]
                except Exception:
                    return [types.TextContent(type="text", text=raw)]
            if line.startswith("UEOS_ERROR:"):
                return [types.TextContent(type="text", text=json.dumps(
                    {"status": "error", "message": line[len("UEOS_ERROR:"):]}, indent=2
                ))]
        return [types.TextContent(type="text", text=json.dumps(
            {"status": "error", "message": "No output from UE", "raw": output[:500]}, indent=2
        ))]

    async def _set_pin_value(self, args: dict) -> list[types.TextContent]:
        bp_path  = args["blueprint_path"]
        graph    = args.get("graph", "EventGraph")
        node_id  = args["node_id"]
        pin_name = args["pin_name"]
        value    = args["value"]

        script = f"""
import unreal, json, traceback
try:
    bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
    if bp is None:
        print("UEOS_ERROR:Blueprint not found: {bp_path}")
    else:
        ok = unreal.PhotonBPLibrary.set_pin_default_value(bp, "{graph}", "{node_id}", "{pin_name}", "{value}")
        if ok:
            unreal.BlueprintEditorLibrary.compile_blueprint(bp)
            unreal.EditorAssetLibrary.save_asset("{bp_path}")
            print("UEOS_RESULT:" + json.dumps({{"status": "success", "node": "{node_id}", "pin": "{pin_name}", "value": "{value}"}}  ))
        else:
            print("UEOS_ERROR:set_pin_default_value failed — check node GUID and pin name")
except Exception as e:
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
"""
        result = await self.ue.execute_python(script)
        return self._parse_result(result)

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
