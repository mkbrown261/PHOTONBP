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
        path = args["path"]
        parent_class = args.get("parent_class", "Actor")
        bp_type = args.get("blueprint_type", "Normal")

        # Map friendly parent class names to UE class paths
        class_map = {
            "Actor":                   "/Script/Engine.Actor",
            "Character":               "/Script/Engine.Character",
            "Pawn":                    "/Script/Engine.Pawn",
            "ActorComponent":          "/Script/Engine.ActorComponent",
            "SceneComponent":          "/Script/Engine.SceneComponent",
            "GameMode":                "/Script/Engine.GameModeBase",
            "GameModeBase":            "/Script/Engine.GameModeBase",
            "GameState":               "/Script/Engine.GameStateBase",
            "PlayerController":        "/Script/Engine.PlayerController",
            "AIController":            "/Script/AIModule.AIController",
            "AnimInstance":            "/Script/Engine.AnimInstance",
            "UserWidget":              "/Script/UMG.UserWidget",
            "BlueprintFunctionLibrary":"/Script/Engine.BlueprintFunctionLibrary",
            "GameInstance":            "/Script/Engine.GameInstance",
            "PlayerState":             "/Script/Engine.PlayerState",
        }

        ue_class = class_map.get(parent_class, parent_class)

        script = f"""
import unreal
import json

# Ensure path exists
unreal.EditorAssetLibrary.make_directory("{path}")

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

# Resolve parent class
parent_class = unreal.load_class(None, "{ue_class}")
if parent_class is None:
    # Try loading as asset (custom BP parent)
    parent_obj = unreal.EditorAssetLibrary.load_asset("{ue_class}")
    if parent_obj:
        parent_class = unreal.EditorAssetLibrary.load_asset("{ue_class}").generated_class()

if parent_class is None:
    print("UEOS_ERROR:Could not resolve parent class: {ue_class}")
else:
    bp_factory = unreal.BlueprintFactory()
    bp_factory.parent_class = parent_class

    asset_path = "{path}/{name}"
    existing = unreal.EditorAssetLibrary.does_asset_exist(asset_path)

    if existing:
        print("UEOS_RESULT:" + json.dumps({{"status": "exists", "path": asset_path, "message": "Blueprint already exists"}}))
    else:
        new_bp = asset_tools.create_asset("{name}", "{path}", None, bp_factory)
        if new_bp:
            unreal.EditorAssetLibrary.save_asset(asset_path)
            print("UEOS_RESULT:" + json.dumps({{
                "status": "created",
                "path": asset_path,
                "class": str(new_bp.get_class().get_name()),
                "parent": "{ue_class}",
                "message": "Blueprint created successfully"
            }}))
        else:
            print("UEOS_ERROR:Failed to create Blueprint at {path}/{name}")
"""

        result = await self.ue.execute_python(script)
        output = result.get("output", "")

        for line in output.split("\n"):
            if line.startswith("UEOS_RESULT:"):
                data = json.loads(line.replace("UEOS_RESULT:", ""))
                return [types.TextContent(type="text", text=json.dumps(data, indent=2))]
            if line.startswith("UEOS_ERROR:"):
                error = line.replace("UEOS_ERROR:", "")
                return [types.TextContent(type="text", text=json.dumps({"status": "error", "message": error}, indent=2))]

        return [types.TextContent(type="text", text=json.dumps({"status": "error", "message": f"No output received. Raw: {output}"}, indent=2))]

    async def _add_variable(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        var_name = args["name"]
        var_type = args["type"]
        default_value = args.get("default_value")
        is_exposed = args.get("is_exposed", False)
        is_replicated = args.get("is_replicated", False)
        category = args.get("category", "Default")

        # Map type strings to UE pin type data
        type_map = {
            "bool":      ("bool", ""),
            "int":       ("int", ""),
            "int64":     ("int64", ""),
            "float":     ("real", "float"),
            "double":    ("real", "double"),
            "string":    ("string", ""),
            "name":      ("name", ""),
            "text":      ("text", ""),
            "vector":    ("struct", "/Script/CoreUObject.Vector"),
            "rotator":   ("struct", "/Script/CoreUObject.Rotator"),
            "transform": ("struct", "/Script/CoreUObject.Transform"),
            "color":     ("struct", "/Script/CoreUObject.LinearColor"),
            "vector2d":  ("struct", "/Script/CoreUObject.Vector2D"),
        }

        script = f"""
import unreal
import json

bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
if bp is None:
    print("UEOS_ERROR:Blueprint not found: {bp_path}")
else:
    # Add variable
    result = unreal.BlueprintEditorLibrary.add_member_variable(
        bp,
        "{var_name}",
        "{var_type}"
    )

    # Set properties
    var = unreal.BlueprintEditorLibrary.get_member_variable_by_name(bp, "{var_name}")
    if var:
        if {str(is_exposed).lower()}:
            var.property_flags |= unreal.PropertyFlags.CPF_EDIT
        if {str(is_replicated).lower()}:
            var.property_flags |= unreal.PropertyFlags.CPF_NET
        bp.mark_package_dirty()

    unreal.EditorAssetLibrary.save_asset("{bp_path}")
    print("UEOS_RESULT:" + json.dumps({{
        "status": "success",
        "variable": "{var_name}",
        "type": "{var_type}",
        "blueprint": "{bp_path}"
    }}))
"""

        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _add_function(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        func_name = args["name"]
        inputs = args.get("inputs", [])
        outputs = args.get("outputs", [])
        is_pure = args.get("is_pure", False)

        inputs_json = json.dumps(inputs)
        outputs_json = json.dumps(outputs)

        script = f"""
import unreal
import json

bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
if bp is None:
    print("UEOS_ERROR:Blueprint not found: {bp_path}")
else:
    new_graph = unreal.BlueprintEditorLibrary.add_function_graph(bp, "{func_name}")
    if new_graph:
        bp.mark_package_dirty()
        unreal.EditorAssetLibrary.save_asset("{bp_path}")
        print("UEOS_RESULT:" + json.dumps({{
            "status": "success",
            "function": "{func_name}",
            "blueprint": "{bp_path}",
            "graph": str(new_graph.get_name())
        }}))
    else:
        print("UEOS_ERROR:Failed to create function {func_name}")
"""

        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _add_event(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        event_name = args["name"]
        parameters = args.get("parameters", [])

        script = f"""
import unreal
import json

bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
if bp is None:
    print("UEOS_ERROR:Blueprint not found: {bp_path}")
else:
    # Get the event graph
    event_graph = unreal.BlueprintEditorLibrary.get_event_graph(bp)
    if event_graph is None:
        event_graph = unreal.BlueprintEditorLibrary.add_event_graph(bp)

    # Add custom event node
    node = unreal.BlueprintEditorLibrary.add_custom_event(bp, "{event_name}")

    bp.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{bp_path}")
    print("UEOS_RESULT:" + json.dumps({{
        "status": "success",
        "event": "{event_name}",
        "blueprint": "{bp_path}"
    }}))
"""

        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _add_node(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        graph_name = args.get("graph", "EventGraph")
        node_type = args["node_type"]
        pos_x = args.get("position_x", 0)
        pos_y = args.get("position_y", 0)

        # Build the node via Python using KismetEditorUtilities / BlueprintEditorLibrary
        script = f"""
import unreal
import json

bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
if bp is None:
    print("UEOS_ERROR:Blueprint not found: {bp_path}")
else:
    # Find target graph
    target_graph = None
    for graph in bp.get_all_graphs():
        if graph.get_name() == "{graph_name}":
            target_graph = graph
            break

    if target_graph is None and "{graph_name}" == "EventGraph":
        target_graph = unreal.BlueprintEditorLibrary.get_event_graph(bp)

    if target_graph is None:
        print("UEOS_ERROR:Graph not found: {graph_name}")
    else:
        node_type = "{node_type}"
        node_id = None

        if node_type == "event":
            event_name = "{args.get('event', 'BeginPlay')}"
            node = unreal.BlueprintEditorLibrary.add_event_node(
                bp, target_graph, f"Event{{event_name}}"
            )
            if node:
                node.node_pos_x = {pos_x}
                node.node_pos_y = {pos_y}
                node_id = str(node.get_node_title(unreal.NodeTitleType.FULL_TITLE))

        elif node_type == "function":
            func_name = "{args.get('function', '')}"
            target = "{args.get('target', 'self')}"
            node = unreal.BlueprintEditorLibrary.add_function_call_node(
                bp, target_graph, func_name
            )
            if node:
                node.node_pos_x = {pos_x}
                node.node_pos_y = {pos_y}
                node_id = func_name

        elif node_type in ("variable_get", "variable_set"):
            var_name = "{args.get('variable_name', '')}"
            is_set = node_type == "variable_set"
            node = unreal.BlueprintEditorLibrary.add_variable_get_set_node(
                bp, target_graph, var_name, is_set
            )
            if node:
                node.node_pos_x = {pos_x}
                node.node_pos_y = {pos_y}
                node_id = f"{{var_name}}_{'set' if is_set else 'get'}"

        elif node_type == "branch":
            node = unreal.BlueprintEditorLibrary.add_branch_node(bp, target_graph)
            if node:
                node.node_pos_x = {pos_x}
                node.node_pos_y = {pos_y}
                node_id = "Branch"

        elif node_type == "print_string":
            node = unreal.BlueprintEditorLibrary.add_function_call_node(
                bp, target_graph, "PrintString"
            )
            if node:
                node.node_pos_x = {pos_x}
                node.node_pos_y = {pos_y}
                node_id = "PrintString"

        elif node_type == "comment":
            comment_text = "{args.get('comment_text', 'Comment')}"
            node = unreal.BlueprintEditorLibrary.add_comment_node(
                bp, target_graph, comment_text
            )
            if node:
                node.node_pos_x = {pos_x}
                node.node_pos_y = {pos_y}
                node_id = f"Comment_{comment_text[:20]}"

        if node_id:
            bp.mark_package_dirty()
            print("UEOS_RESULT:" + json.dumps({{
                "status": "success",
                "node_id": node_id,
                "node_type": node_type,
                "graph": "{graph_name}",
                "blueprint": "{bp_path}"
            }}))
        else:
            print("UEOS_ERROR:Failed to add node of type {node_type}")
"""

        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _connect_pins(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        graph = args.get("graph", "EventGraph")
        from_node = args["from_node"]
        from_pin = args["from_pin"]
        to_node = args["to_node"]
        to_pin = args["to_pin"]

        script = f"""
import unreal
import json

bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
if bp is None:
    print("UEOS_ERROR:Blueprint not found: {bp_path}")
else:
    result = unreal.BlueprintEditorLibrary.connect_graph_pins(
        bp, "{graph}", "{from_node}", "{from_pin}", "{to_node}", "{to_pin}"
    )
    bp.mark_package_dirty()
    print("UEOS_RESULT:" + json.dumps({{
        "status": "success" if result else "failed",
        "from": "{from_node}.{from_pin}",
        "to": "{to_node}.{to_pin}"
    }}))
"""

        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _add_component(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        component_class = args["component_class"]
        component_name = args["component_name"]
        attach_to = args.get("attach_to", "RootComponent")
        properties = args.get("properties", {})

        props_json = json.dumps(properties)

        script = f"""
import unreal
import json

bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
if bp is None:
    print("UEOS_ERROR:Blueprint not found: {bp_path}")
else:
    # Find the component class
    comp_class = unreal.load_class(None, f"/Script/Engine.{{'{component_class}'}}")
    if comp_class is None:
        comp_class = unreal.load_class(None, f"/Script/UMG.{{'{component_class}'}}")
    if comp_class is None:
        print("UEOS_ERROR:Component class not found: {component_class}")
    else:
        new_comp = unreal.BlueprintEditorLibrary.add_component(
            bp, comp_class, "{component_name}"
        )
        if new_comp:
            bp.mark_package_dirty()
            unreal.EditorAssetLibrary.save_asset("{bp_path}")
            print("UEOS_RESULT:" + json.dumps({{
                "status": "success",
                "component": "{component_name}",
                "class": "{component_class}",
                "blueprint": "{bp_path}"
            }}))
        else:
            print("UEOS_ERROR:Failed to add component {component_name}")
"""

        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _add_interface(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        interface_path = args["interface_path"]

        script = f"""
import unreal
import json

bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
interface = unreal.EditorAssetLibrary.load_asset("{interface_path}")
if bp is None:
    print("UEOS_ERROR:Blueprint not found: {bp_path}")
elif interface is None:
    print("UEOS_ERROR:Interface not found: {interface_path}")
else:
    unreal.BlueprintEditorLibrary.add_interface(bp, interface.generated_class())
    bp.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{bp_path}")
    print("UEOS_RESULT:" + json.dumps({{"status": "success", "interface": "{interface_path}"}}))
"""

        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _add_dispatcher(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        name = args["name"]
        parameters = args.get("parameters", [])

        script = f"""
import unreal
import json

bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
if bp is None:
    print("UEOS_ERROR:Blueprint not found: {bp_path}")
else:
    dispatcher = unreal.BlueprintEditorLibrary.add_event_dispatcher(bp, "{name}")
    bp.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{bp_path}")
    print("UEOS_RESULT:" + json.dumps({{"status": "success", "dispatcher": "{name}", "blueprint": "{bp_path}"}}))
"""

        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _set_construction_script(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        setup_leader_pose = args.get("setup_leader_pose", False)
        leader_mesh = args.get("leader_mesh_variable", "BodyMesh")
        followers = args.get("follower_mesh_variables", [])
        followers_json = json.dumps(followers)

        script = f"""
import unreal
import json

bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
if bp is None:
    print("UEOS_ERROR:Blueprint not found: {bp_path}")
else:
    # Get construction script graph
    construction_graph = None
    for graph in bp.get_all_graphs():
        if "ConstructionScript" in graph.get_name():
            construction_graph = graph
            break

    if construction_graph is None:
        print("UEOS_ERROR:Construction script graph not found")
    else:
        nodes_added = []

        setup_leader = {str(setup_leader_pose).lower()}
        if setup_leader:
            # Add nodes for Leader Pose Component setup
            # 1. Get leader mesh component
            leader_get = unreal.BlueprintEditorLibrary.add_variable_get_set_node(
                bp, construction_graph, "{leader_mesh}", False
            )
            if leader_get:
                leader_get.node_pos_x = 200
                leader_get.node_pos_y = 200
                nodes_added.append("Get_{leader_mesh}")

            # 2. For each follower, call SetLeaderPoseComponent
            followers = {followers_json}
            y_offset = 300
            for i, follower in enumerate(followers):
                # Get follower mesh
                follower_get = unreal.BlueprintEditorLibrary.add_variable_get_set_node(
                    bp, construction_graph, follower, False
                )
                if follower_get:
                    follower_get.node_pos_x = 200
                    follower_get.node_pos_y = y_offset

                # Add SetLeaderPoseComponent function call
                set_leader_node = unreal.BlueprintEditorLibrary.add_function_call_node(
                    bp, construction_graph, "SetLeaderPoseComponent"
                )
                if set_leader_node:
                    set_leader_node.node_pos_x = 450
                    set_leader_node.node_pos_y = y_offset
                    nodes_added.append(f"SetLeaderPose_{{follower}}")

                y_offset += 150

        bp.mark_package_dirty()
        unreal.EditorAssetLibrary.save_asset("{bp_path}")
        print("UEOS_RESULT:" + json.dumps({{
            "status": "success",
            "nodes_added": nodes_added,
            "leader_pose_setup": setup_leader,
            "blueprint": "{bp_path}"
        }}))
"""

        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _compile(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        save_on_success = args.get("save_on_success", True)

        script = f"""
import unreal
import json

bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
if bp is None:
    print("UEOS_ERROR:Blueprint not found: {bp_path}")
else:
    # Compile
    unreal.KismetEditorUtilities.compile_blueprint(bp)

    # Check compile status
    compile_status = bp.status
    status_str = str(compile_status)

    errors = []
    warnings = []

    # Get compiler results
    for msg in bp.get_all_compile_errors():
        errors.append(str(msg))
    for msg in bp.get_all_compile_warnings():
        warnings.append(str(msg))

    success = len(errors) == 0

    if success and {str(save_on_success).lower()}:
        unreal.EditorAssetLibrary.save_asset("{bp_path}")

    print("UEOS_RESULT:" + json.dumps({{
        "compile_result": "Success" if success else "Failed",
        "status": status_str,
        "errors": errors,
        "warnings": warnings,
        "saved": success and {str(save_on_success).lower()},
        "blueprint": "{bp_path}"
    }}))
"""

        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _save(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]

        script = f"""
import unreal
import json

success = unreal.EditorAssetLibrary.save_asset("{bp_path}")
print("UEOS_RESULT:" + json.dumps({{"status": "saved" if success else "failed", "path": "{bp_path}"}}))
"""

        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _read(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]

        script = f"""
import unreal
import json

bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
if bp is None:
    print("UEOS_ERROR:Blueprint not found: {bp_path}")
else:
    data = {{
        "path": "{bp_path}",
        "name": bp.get_name(),
        "parent_class": str(bp.generated_class().get_super_class().get_name()) if bp.generated_class() else "Unknown",
        "variables": [],
        "functions": [],
        "components": [],
        "interfaces": [],
        "graphs": [],
        "compile_status": str(bp.status)
    }}

    # Variables
    for var in bp.get_all_member_variables():
        data["variables"].append({{
            "name": str(var.variable_name),
            "type": str(var.variable_type.category),
            "editable": bool(var.property_flags & unreal.PropertyFlags.CPF_EDIT)
        }})

    # Functions / Graphs
    for graph in bp.get_all_graphs():
        gname = graph.get_name()
        data["graphs"].append(gname)
        if gname not in ("EventGraph", "ConstructionScript"):
            data["functions"].append(gname)

    # Components
    for comp in bp.get_editor_only_data().component_templates:
        data["components"].append({{
            "name": str(comp.get_name()),
            "class": str(comp.get_class().get_name())
        }})

    # Interfaces
    for iface in bp.implemented_interfaces:
        data["interfaces"].append(str(iface.interface_class.get_name() if iface.interface_class else "Unknown"))

    print("UEOS_RESULT:" + json.dumps(data))
"""

        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _validate(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]

        script = f"""
import unreal
import json

bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
if bp is None:
    print("UEOS_ERROR:Blueprint not found: {bp_path}")
else:
    issues = []

    # Check parent class
    if bp.generated_class() is None:
        issues.append({{"severity": "error", "message": "Blueprint has no generated class"}})

    # Check compile status
    if str(bp.status) in ("BS_Error", "BS_Unknown"):
        issues.append({{"severity": "error", "message": f"Blueprint compile status: {{bp.status}}"}})

    # Check for empty functions
    for graph in bp.get_all_graphs():
        nodes = graph.nodes
        if len(nodes) <= 1 and graph.get_name() not in ("EventGraph", "ConstructionScript"):
            issues.append({{"severity": "warning", "message": f"Function '{{graph.get_name()}}' appears empty"}})

    result = {{
        "blueprint": "{bp_path}",
        "issues": issues,
        "issue_count": len(issues),
        "valid": len([i for i in issues if i["severity"] == "error"]) == 0
    }}
    print("UEOS_RESULT:" + json.dumps(result))
"""

        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _delete(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        confirm = args.get("confirm", False)

        if not confirm:
            return [types.TextContent(type="text", text=json.dumps({"status": "cancelled", "message": "Set confirm=true to delete"}))]

        script = f"""
import unreal
import json

success = unreal.EditorAssetLibrary.delete_asset("{bp_path}")
print("UEOS_RESULT:" + json.dumps({{"status": "deleted" if success else "failed", "path": "{bp_path}"}}))
"""

        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _reparent(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        new_parent = args["new_parent_class"]

        script = f"""
import unreal
import json

bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
new_class = unreal.load_class(None, "{new_parent}")
if bp and new_class:
    unreal.BlueprintEditorLibrary.reparent_blueprint(bp, new_class)
    bp.mark_package_dirty()
    unreal.EditorAssetLibrary.save_asset("{bp_path}")
    print("UEOS_RESULT:" + json.dumps({{"status": "success", "new_parent": "{new_parent}"}}))
else:
    print("UEOS_ERROR:Could not reparent - Blueprint or class not found")
"""

        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    async def _add_timeline(self, args: dict) -> list[types.TextContent]:
        bp_path = args["blueprint_path"]
        graph_name = args.get("graph", "EventGraph")
        timeline_name = args["timeline_name"]
        length = args.get("length", 1.0)
        loop = args.get("loop", False)
        tracks = args.get("tracks", [])
        tracks_json = json.dumps(tracks)

        script = f"""
import unreal
import json

bp = unreal.EditorAssetLibrary.load_asset("{bp_path}")
if bp is None:
    print("UEOS_ERROR:Blueprint not found: {bp_path}")
else:
    target_graph = None
    for graph in bp.get_all_graphs():
        if graph.get_name() == "{graph_name}":
            target_graph = graph
            break

    if target_graph is None:
        target_graph = unreal.BlueprintEditorLibrary.get_event_graph(bp)

    if target_graph:
        timeline_node = unreal.BlueprintEditorLibrary.add_timeline_node(
            bp, target_graph, "{timeline_name}"
        )
        if timeline_node:
            # Configure timeline
            timeline_node.timeline_length = {length}
            timeline_node.loop = {str(loop).lower()}

            # Add tracks
            tracks = {tracks_json}
            for track in tracks:
                track_type = track.get("type", "float")
                track_name = track.get("name", "Track")
                keyframes = track.get("keyframes", [])

                if track_type == "float":
                    unreal.BlueprintEditorLibrary.add_timeline_float_track(timeline_node, track_name)
                elif track_type == "vector":
                    unreal.BlueprintEditorLibrary.add_timeline_vector_track(timeline_node, track_name)
                elif track_type == "color":
                    unreal.BlueprintEditorLibrary.add_timeline_linear_color_track(timeline_node, track_name)
                elif track_type == "event":
                    unreal.BlueprintEditorLibrary.add_timeline_event_track(timeline_node, track_name)

            bp.mark_package_dirty()
            unreal.EditorAssetLibrary.save_asset("{bp_path}")
            print("UEOS_RESULT:" + json.dumps({{
                "status": "success",
                "timeline": "{timeline_name}",
                "length": {length},
                "loop": {str(loop).lower()},
                "tracks": {tracks_json}
            }}))
        else:
            print("UEOS_ERROR:Failed to create timeline node")
    else:
        print("UEOS_ERROR:Could not find or create target graph")
"""

        result = await self.ue.execute_python(script)
        return self._parse_result(result)

    # ─────────────────────────────────────────────
    # Shared output parser
    # ─────────────────────────────────────────────

    def _parse_result(self, result: dict) -> list[types.TextContent]:
        output = result.get("output", "")
        for line in output.split("\n"):
            if line.startswith("UEOS_RESULT:"):
                data = json.loads(line.replace("UEOS_RESULT:", ""))
                return [types.TextContent(type="text", text=json.dumps(data, indent=2))]
            if line.startswith("UEOS_ERROR:"):
                error = line.replace("UEOS_ERROR:", "")
                return [types.TextContent(type="text", text=json.dumps({"status": "error", "message": error}, indent=2))]
        return [types.TextContent(type="text", text=json.dumps({"status": "error", "raw_output": output}, indent=2))]
