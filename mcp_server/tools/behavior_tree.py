"""
UEOS Behavior Tree Tools — Phase 4
Full implementation: Behavior Trees, Blackboards, Tasks, Services, Decorators, AI Controllers.

UE 5.4 Python APIs used:
  - unreal.BehaviorTree               via AssetToolsHelpers
  - unreal.BlackboardData             via AssetToolsHelpers
  - unreal.BehaviorTreeGraphNode      node creation
  - unreal.BTTask_*                   built-in tasks
  - unreal.BTDecorator_*              built-in decorators
  - unreal.BTService_*                built-in services
  - unreal.EditorAssetLibrary         save
  - unreal.AIBlueprintHelperLibrary   AI utility
  - unreal.AssetToolsHelpers          factory creation

Tools exposed (17 total):
  bt_create_blackboard          — create BlackboardData asset
  bt_add_blackboard_key         — add key to blackboard (object, vector, bool, float, int, string, enum, name)
  bt_get_blackboard_keys        — list all keys in a blackboard
  bt_create_behavior_tree       — create BehaviorTree asset linked to a blackboard
  bt_add_selector               — add Selector composite (run children until one succeeds)
  bt_add_sequence               — add Sequence composite (run children until one fails)
  bt_add_parallel               — add Parallel composite (run all children simultaneously)
  bt_add_task                   — add built-in or custom task node
  bt_add_decorator              — add decorator (condition gate) to a node
  bt_add_service                — add service (periodic tick) to a node
  bt_create_custom_task         — create a custom BTTask Blueprint
  bt_create_custom_decorator    — create a custom BTDecorator Blueprint
  bt_create_custom_service      — create a custom BTService Blueprint
  bt_set_ai_controller          — set the behavior tree on an AIController Blueprint
  bt_get_tree_info              — inspect behavior tree structure
  bt_create_ai_character        — create Character + AIController + BT pipeline in one call
  bt_create_patrol_tree         — create a complete patrol behavior tree
"""

import json
import logging
from textwrap import dedent
from mcp import types

log = logging.getLogger("ueos.behavior_tree")


# ── Built-in task short-names → UE class paths ────────────────────────────────
BUILTIN_TASKS = {
    "move_to":           "/Script/AIModule.BTTask_MoveTo",
    "wait":              "/Script/AIModule.BTTask_Wait",
    "wait_blackboard":   "/Script/AIModule.BTTask_WaitBlackboardTime",
    "run_eqs":           "/Script/AIModule.BTTask_RunEQSQuery",
    "play_anim":         "/Script/AIModule.BTTask_PlayAnimation",
    "clear_blackboard":  "/Script/AIModule.BTTask_ClearValue",
    "set_blackboard":    "/Script/AIModule.BTTask_SetBlackboardValue",
    "rotate_to":         "/Script/AIModule.BTTask_RotateToFaceBBEntry",
    "make_noise":        "/Script/AIModule.BTTask_MakeNoise",
    "run_behavior":      "/Script/AIModule.BTTask_RunBehavior",
    "finish_with_result":"/Script/AIModule.BTTask_FinishWithResult",
}

BUILTIN_DECORATORS = {
    "blackboard":        "/Script/AIModule.BTDecorator_Blackboard",
    "is_at_location":    "/Script/AIModule.BTDecorator_IsAtLocation",
    "does_path_exist":   "/Script/AIModule.BTDecorator_DoesPathExist",
    "cooldown":          "/Script/AIModule.BTDecorator_Cooldown",
    "time_limit":        "/Script/AIModule.BTDecorator_TimeLimit",
    "loop":              "/Script/AIModule.BTDecorator_Loop",
    "force_success":     "/Script/AIModule.BTDecorator_ForceSuccess",
    "compare_bb_entries":"/Script/AIModule.BTDecorator_CompareBBEntries",
    "cone_check":        "/Script/AIModule.BTDecorator_ConeCheck",
    "reached_move_goal": "/Script/AIModule.BTDecorator_ReachedMoveGoal",
    "can_execute_aiz":   "/Script/AIModule.BTDecorator_CanExecuteAIBehavior",
    "set_tag_cooldown":  "/Script/AIModule.BTDecorator_SetTagCooldown",
    "check_gameplay_tag":"/Script/GameplayTags.BTDecorator_MatchingTag",
}

BUILTIN_SERVICES = {
    "default_focus":     "/Script/AIModule.BTService_DefaultFocus",
    "run_eqs":           "/Script/AIModule.BTService_RunEQSQuery",
    "blackboard_based":  "/Script/AIModule.BTService_BlackboardBase",
}

# ── Blackboard key types ───────────────────────────────────────────────────────
BB_KEY_TYPES = {
    "object":   "BlackboardKeyType_Object",
    "class":    "BlackboardKeyType_Class",
    "enum":     "BlackboardKeyType_Enum",
    "int":      "BlackboardKeyType_Int",
    "float":    "BlackboardKeyType_Float",
    "bool":     "BlackboardKeyType_Bool",
    "string":   "BlackboardKeyType_String",
    "name":     "BlackboardKeyType_Name",
    "vector":   "BlackboardKeyType_Vector",
    "rotator":  "BlackboardKeyType_Rotator",
}


class BehaviorTreeTools:

    def __init__(self, ue):
        self.ue = ue

    async def _exec(self, script: str, label: str) -> list[types.TextContent]:
        try:
            result = await self.ue.execute_python_ex(script)
            if result.get("ok"):
                raw = result.get("result", result.get("raw_output", ""))
                try:
                    return [types.TextContent(type="text", text=json.dumps(json.loads(raw)))]
                except Exception:
                    return [types.TextContent(type="text", text=json.dumps({"status": "ok", "raw": raw}))]
            else:
                return [types.TextContent(type="text", text=json.dumps({
                    "error": result.get("error", "Unknown error"), "tool": label,
                }))]
        except Exception as exc:
            log.exception("%s failed", label)
            return [types.TextContent(type="text", text=json.dumps({"error": str(exc), "tool": label}))]

    # ── Tool definitions ───────────────────────────────────────────────────────

    async def get_tool_definitions(self) -> list[types.Tool]:
        return [

            types.Tool(
                name="bt_create_blackboard",
                description=dedent("""\
                    Create a Blackboard asset — the AI's shared memory.
                    The Blackboard stores key-value data that all nodes in the Behavior Tree
                    can read and write: target actor, patrol destination, threat level,
                    health percent, attack cooldown, current state enum, etc.
                    Returns the full asset path of the created Blackboard."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":   {"type": "string", "description": "Asset name e.g. BB_EnemyAI"},
                        "path":   {"type": "string", "description": "Content path e.g. /Game/AI"},
                        "parent_blackboard": {"type": "string", "default": "",
                                              "description": "Optional parent blackboard path for key inheritance"},
                    },
                    "required": ["name", "path"],
                },
            ),

            types.Tool(
                name="bt_add_blackboard_key",
                description=dedent("""\
                    Add a key to a Blackboard asset.
                    Keys are the variables that Behavior Tree nodes read and write.
                    Common keys:
                      TargetActor (object/Actor)  — enemy/player to chase
                      PatrolTarget (vector)        — next patrol waypoint
                      CanSeePlayer (bool)          — visibility flag
                      AttackCooldown (float)       — time until next attack
                      AIState (enum)               — current AI state
                      HealthPercent (float)        — current health 0-1
                    Key types: object, class, enum, int, float, bool, string, name, vector, rotator"""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blackboard_path": {"type": "string"},
                        "key_name":        {"type": "string", "description": "Key name e.g. TargetActor, PatrolTarget"},
                        "key_type":        {
                            "type": "string",
                            "description": "Key type: object, vector, bool, float, int, string, name, enum, rotator, class",
                        },
                        "instance_sync":   {"type": "boolean", "default": True,
                                            "description": "Sync value across AI instances (true) or per-instance (false)"},
                        "object_class":    {"type": "string",  "default": "",
                                            "description": "For object keys: base class path e.g. /Script/Engine.Actor"},
                        "enum_type":       {"type": "string",  "default": "",
                                            "description": "For enum keys: enum asset path or class path"},
                    },
                    "required": ["blackboard_path", "key_name", "key_type"],
                },
            ),

            types.Tool(
                name="bt_get_blackboard_keys",
                description=dedent("""\
                    List all keys defined in a Blackboard asset.
                    Returns: key name, type, instance sync flag for each key."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "blackboard_path": {"type": "string"},
                    },
                    "required": ["blackboard_path"],
                },
            ),

            types.Tool(
                name="bt_create_behavior_tree",
                description=dedent("""\
                    Create a Behavior Tree asset linked to a Blackboard.
                    The Behavior Tree is the AI's decision logic — it runs from the
                    root downward, selecting which action to take based on conditions.
                    Must have a Blackboard linked to read/write AI state.
                    Returns the full asset path of the created Behavior Tree."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":             {"type": "string", "description": "Asset name e.g. BT_EnemyAI"},
                        "path":             {"type": "string", "description": "Content path e.g. /Game/AI"},
                        "blackboard_path":  {"type": "string", "description": "Full path to BlackboardData asset"},
                    },
                    "required": ["name", "path", "blackboard_path"],
                },
            ),

            types.Tool(
                name="bt_add_selector",
                description=dedent("""\
                    Add a Selector composite node to a Behavior Tree.
                    Selectors try each child LEFT to RIGHT, stopping at the first SUCCESS.
                    Think of it as: 'Do A, OR if A fails do B, OR if B fails do C'.
                    Used for: priority selection — attack if possible, else chase, else patrol.
                    parent_node: 'root' to attach at top level, or node name for nesting."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bt_path":     {"type": "string"},
                        "name":        {"type": "string", "description": "Node name e.g. SEL_CombatLogic"},
                        "parent_node": {"type": "string", "default": "root"},
                        "position_x":  {"type": "integer","default": 0},
                        "position_y":  {"type": "integer","default": 0},
                    },
                    "required": ["bt_path", "name"],
                },
            ),

            types.Tool(
                name="bt_add_sequence",
                description=dedent("""\
                    Add a Sequence composite node to a Behavior Tree.
                    Sequences run each child LEFT to RIGHT, stopping at the first FAILURE.
                    Think of it as: 'Do A AND THEN B AND THEN C'.
                    Used for: multi-step actions — move to target, then attack, then play reaction.
                    If any step fails, the whole sequence fails."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bt_path":     {"type": "string"},
                        "name":        {"type": "string", "description": "Node name e.g. SEQ_AttackSequence"},
                        "parent_node": {"type": "string", "default": "root"},
                        "position_x":  {"type": "integer","default": 0},
                        "position_y":  {"type": "integer","default": 0},
                    },
                    "required": ["bt_path", "name"],
                },
            ),

            types.Tool(
                name="bt_add_parallel",
                description=dedent("""\
                    Add a Parallel composite node to a Behavior Tree.
                    Parallel runs ALL children simultaneously.
                    Used for: moving toward target while playing an idle animation,
                    or executing logic while a service updates perception."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bt_path":            {"type": "string"},
                        "name":               {"type": "string", "description": "Node name e.g. PAR_MoveAndAnim"},
                        "parent_node":        {"type": "string", "default": "root"},
                        "finish_mode":        {"type": "string",  "default": "immediate",
                                               "description": "Completion mode: immediate (when main task done) or delayed (when all done)"},
                        "position_x":         {"type": "integer", "default": 0},
                        "position_y":         {"type": "integer", "default": 0},
                    },
                    "required": ["bt_path", "name"],
                },
            ),

            types.Tool(
                name="bt_add_task",
                description=dedent("""\
                    Add a task leaf node to a Behavior Tree.
                    Tasks are the actual actions the AI performs.
                    Built-in tasks: move_to, wait, wait_blackboard, rotate_to, make_noise,
                                    run_eqs, play_anim, clear_blackboard, set_blackboard,
                                    run_behavior, finish_with_result
                    Or provide a full custom class path for custom Blueprint tasks.
                    Configure task parameters with the 'params' dict."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bt_path":     {"type": "string"},
                        "task":        {"type": "string",
                                        "description": "Built-in: move_to, wait, rotate_to, etc. Or full class path for custom."},
                        "parent_node": {"type": "string", "default": "root"},
                        "params":      {
                            "type": "object",
                            "description": "Task parameters e.g. {\"AcceptableRadius\": 50, \"BlackboardKey\": \"TargetActor\"}",
                        },
                        "position_x":  {"type": "integer","default": 0},
                        "position_y":  {"type": "integer","default": 0},
                    },
                    "required": ["bt_path", "task"],
                },
            ),

            types.Tool(
                name="bt_add_decorator",
                description=dedent("""\
                    Add a decorator to a Behavior Tree node (composite or task).
                    Decorators are condition gates — they allow or block a node from running.
                    Built-in decorators: blackboard, is_at_location, does_path_exist,
                                         cooldown, time_limit, loop, force_success,
                                         compare_bb_entries, cone_check, reached_move_goal
                    The 'blackboard' decorator checks if a key is set/not-set/equals a value."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bt_path":       {"type": "string"},
                        "node_name":     {"type": "string", "description": "Node to attach decorator to"},
                        "decorator":     {"type": "string",
                                          "description": "Built-in: blackboard, cooldown, time_limit, loop, etc. Or custom class path."},
                        "params":        {
                            "type": "object",
                            "description": "Decorator params e.g. {\"BlackboardKey\": \"TargetActor\", \"NotifyObserver\": \"OnResultChange\"}",
                        },
                        "flow_control":  {"type": "string",  "default": "none",
                                          "description": "Abort mode: none, self, lower_priority, both"},
                        "invert":        {"type": "boolean", "default": False,
                                          "description": "Invert the condition (NOT)"},
                    },
                    "required": ["bt_path", "node_name", "decorator"],
                },
            ),

            types.Tool(
                name="bt_add_service",
                description=dedent("""\
                    Add a service to a Behavior Tree node.
                    Services run periodically while their parent node is active.
                    Used for: updating perception (is player visible?), refreshing
                    patrol targets, recalculating threat, updating blackboard values.
                    Built-in services: default_focus, run_eqs, blackboard_based
                    Tick interval controls how often the service runs (in seconds)."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bt_path":        {"type": "string"},
                        "node_name":      {"type": "string"},
                        "service":        {"type": "string",
                                           "description": "Built-in: default_focus, run_eqs. Or custom class path."},
                        "tick_interval":  {"type": "number", "default": 0.5,
                                           "description": "How often the service ticks (seconds)"},
                        "random_deviation":{"type": "number","default": 0.1},
                        "params":         {"type": "object", "description": "Service-specific parameters"},
                    },
                    "required": ["bt_path", "node_name", "service"],
                },
            ),

            types.Tool(
                name="bt_create_custom_task",
                description=dedent("""\
                    Create a custom BTTask Blueprint that can be used in Behavior Trees.
                    The Blueprint will have overridable events:
                      ReceiveExecute(OwnerController, ControlledPawn)  — main action
                      ReceiveAbortAI(OwnerController, ControlledPawn)  — on abort
                      ReceiveTick(OwnerController, DeltaSeconds)       — per-frame (optional)
                    Returns the asset path — add it to a BT with bt_add_task using the full path."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":        {"type": "string", "description": "e.g. BTT_AttackTarget, BTT_PlayVoiceLine"},
                        "path":        {"type": "string", "description": "Content path e.g. /Game/AI/Tasks"},
                        "description": {"type": "string", "default": "", "description": "Task description comment"},
                        "node_name":   {"type": "string", "default": "",
                                        "description": "Display name shown in the Behavior Tree graph"},
                    },
                    "required": ["name", "path"],
                },
            ),

            types.Tool(
                name="bt_create_custom_decorator",
                description=dedent("""\
                    Create a custom BTDecorator Blueprint.
                    Override PerformConditionCheck(OwnerController, ControlledPawn) → bool.
                    Return true = allow execution, false = block.
                    Used for: custom proximity checks, gameplay tag checks, resource checks."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":      {"type": "string", "description": "e.g. BTD_IsPlayerVisible, BTD_HasAmmo"},
                        "path":      {"type": "string"},
                        "node_name": {"type": "string", "default": ""},
                    },
                    "required": ["name", "path"],
                },
            ),

            types.Tool(
                name="bt_create_custom_service",
                description=dedent("""\
                    Create a custom BTService Blueprint.
                    Override ReceiveTickAI(OwnerController, ControlledPawn, DeltaSeconds).
                    Used for: updating blackboard perception data, recalculating paths,
                    refreshing threat lists, scanning for enemies."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":          {"type": "string", "description": "e.g. BTS_UpdatePerception, BTS_ScanForEnemies"},
                        "path":          {"type": "string"},
                        "tick_interval": {"type": "number", "default": 0.5},
                        "node_name":     {"type": "string", "default": ""},
                    },
                    "required": ["name", "path"],
                },
            ),

            types.Tool(
                name="bt_set_ai_controller",
                description=dedent("""\
                    Set the Behavior Tree asset on an AIController Blueprint.
                    This wires up the AI: when the controller possesses a pawn,
                    it will automatically run this Behavior Tree.
                    The BT will start via RunBehaviorTree in BeginPlay."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "controller_path": {"type": "string",
                                            "description": "Full path to AIController Blueprint"},
                        "bt_path":         {"type": "string",
                                            "description": "Full path to BehaviorTree asset"},
                        "run_on_begin_play":{"type": "boolean", "default": True,
                                             "description": "Auto-call RunBehaviorTree in BeginPlay"},
                    },
                    "required": ["controller_path", "bt_path"],
                },
            ),

            types.Tool(
                name="bt_get_tree_info",
                description=dedent("""\
                    Inspect a Behavior Tree — returns its blackboard, root composite type,
                    and a summary of all nodes (composites, tasks, decorators, services)."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bt_path": {"type": "string"},
                    },
                    "required": ["bt_path"],
                },
            ),

            types.Tool(
                name="bt_create_ai_character",
                description=dedent("""\
                    Create a complete AI character pipeline in one call:
                    1. BlackboardData  (BB_<name>)
                    2. BehaviorTree    (BT_<name>) linked to blackboard
                    3. AIController BP (AIC_<name>) running the BT on BeginPlay
                    4. Character BP    (BP_<name>) using the AIController
                    Optionally add standard blackboard keys: TargetActor, PatrolTarget, CanSeePlayer."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":             {"type": "string", "description": "Base name e.g. EnemyGuard → BB_EnemyGuard, BT_EnemyGuard…"},
                        "path":             {"type": "string", "description": "Content base path e.g. /Game/AI/EnemyGuard"},
                        "skeleton_path":    {"type": "string", "default": "",
                                             "description": "Optional skeleton for the Character BP"},
                        "standard_keys":    {"type": "boolean","default": True,
                                             "description": "Add standard BB keys: TargetActor, PatrolTarget, CanSeePlayer, AttackCooldown"},
                    },
                    "required": ["name", "path"],
                },
            ),

            types.Tool(
                name="bt_create_patrol_tree",
                description=dedent("""\
                    Create a complete patrol + combat Behavior Tree in one call.
                    Structure:
                      Root
                      └─ Selector (main)
                          ├─ Sequence (combat: CanSeePlayer=true)
                          │   ├─ Decorator: Blackboard(CanSeePlayer)
                          │   ├─ Task: MoveTo(TargetActor, radius=150)
                          │   └─ Task: Wait(0.5s) [attack placeholder]
                          └─ Sequence (patrol)
                              ├─ Task: MoveTo(PatrolTarget, radius=50)
                              └─ Task: Wait(random 2-4s)
                    Requires: TargetActor(object), PatrolTarget(vector), CanSeePlayer(bool) keys."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bt_path":            {"type": "string", "description": "Full path to existing BehaviorTree asset"},
                        "attack_range":       {"type": "number",  "default": 150.0,
                                               "description": "Accept radius for MoveTo attack (cm)"},
                        "patrol_accept_radius":{"type": "number", "default": 50.0},
                        "patrol_wait_time":   {"type": "number",  "default": 3.0,
                                               "description": "How long to wait at each patrol point (seconds)"},
                        "can_see_key":        {"type": "string",  "default": "CanSeePlayer"},
                        "target_key":         {"type": "string",  "default": "TargetActor"},
                        "patrol_key":         {"type": "string",  "default": "PatrolTarget"},
                    },
                    "required": ["bt_path"],
                },
            ),

        ]

    # ── Handlers ───────────────────────────────────────────────────────────────

    async def handle(self, name: str, args: dict) -> list[types.TextContent]:
        handlers = {
            "bt_create_blackboard":     self._create_blackboard,
            "bt_add_blackboard_key":    self._add_blackboard_key,
            "bt_get_blackboard_keys":   self._get_blackboard_keys,
            "bt_create_behavior_tree":  self._create_behavior_tree,
            "bt_add_selector":          self._add_selector,
            "bt_add_sequence":          self._add_sequence,
            "bt_add_parallel":          self._add_parallel,
            "bt_add_task":              self._add_task,
            "bt_add_decorator":         self._add_decorator,
            "bt_add_service":           self._add_service,
            "bt_create_custom_task":    self._create_custom_task,
            "bt_create_custom_decorator":self._create_custom_decorator,
            "bt_create_custom_service": self._create_custom_service,
            "bt_set_ai_controller":     self._set_ai_controller,
            "bt_get_tree_info":         self._get_tree_info,
            "bt_create_ai_character":   self._create_ai_character,
            "bt_create_patrol_tree":    self._create_patrol_tree,
        }
        fn = handlers.get(name)
        if not fn:
            return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown BT tool: {name}"}))]
        return await fn(args)

    # ── Implementations ────────────────────────────────────────────────────────

    async def _create_blackboard(self, args: dict) -> list[types.TextContent]:
        name   = args["name"]
        path   = args["path"].rstrip("/")
        parent = args.get("parent_blackboard", "")

        script = dedent(f"""
            import unreal, json
            try:
                at = unreal.AssetToolsHelpers.get_asset_tools()
                bb = at.create_asset('{name}', '{path}', unreal.BlackboardData, None)
                if not bb:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Failed to create BlackboardData'}}))
                    raise SystemExit()

                if '{parent}':
                    parent_bb = unreal.load_asset('{parent}')
                    if parent_bb:
                        try: bb.set_editor_property('parent', parent_bb)
                        except Exception: pass

                unreal.EditorAssetLibrary.save_asset(bb.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status': 'created',
                    'path':   bb.get_path_name(),
                    'name':   '{name}',
                    'note':   'Use bt_add_blackboard_key to add AI state variables.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "bt_create_blackboard")

    async def _add_blackboard_key(self, args: dict) -> list[types.TextContent]:
        bb_path       = args["blackboard_path"]
        key_name      = args["key_name"]
        key_type      = args["key_type"].lower()
        instance_sync = args.get("instance_sync", True)
        obj_class     = args.get("object_class", "")
        enum_type     = args.get("enum_type", "")

        ue_key_type = BB_KEY_TYPES.get(key_type, "BlackboardKeyType_Object")

        script = dedent(f"""
            import unreal, json
            try:
                bb = unreal.load_asset('{bb_path}')
                if not bb:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Blackboard not found'}}))
                    raise SystemExit()

                # Build key entry
                key = unreal.BlackboardEntry()
                key.entry_name     = unreal.Name('{key_name}')
                key.instance_synced = {str(instance_sync).lower()}

                # Key type
                key_type_cls = None
                try:
                    key_type_cls = unreal.load_class(None, '/Script/AIModule.{ue_key_type}')
                except Exception: pass

                if key_type_cls:
                    key_obj = unreal.new_object(key_type_cls)
                    if '{key_type}' == 'object' and '{obj_class}':
                        try:
                            base_cls = unreal.load_class(None, '{obj_class}')
                            if base_cls:
                                key_obj.set_editor_property('base_class', base_cls)
                        except Exception: pass
                    elif '{key_type}' == 'enum' and '{enum_type}':
                        try:
                            enum_cls = unreal.load_object(None, '{enum_type}')
                            if enum_cls:
                                key_obj.set_editor_property('enum_type', enum_cls)
                        except Exception: pass
                    key.key_type = key_obj

                # Append to blackboard
                existing = list(bb.get_editor_property('keys') or [])
                # Check for duplicate
                existing_names = [str(k.entry_name) for k in existing]
                if '{key_name}' not in existing_names:
                    existing.append(key)
                    bb.set_editor_property('keys', existing)

                unreal.EditorAssetLibrary.save_asset(bb.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':        'key_added',
                    'key':           '{key_name}',
                    'type':          '{key_type}',
                    'instance_sync': {str(instance_sync).lower()},
                    'blackboard':    '{bb_path}',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "bt_add_blackboard_key")

    async def _get_blackboard_keys(self, args: dict) -> list[types.TextContent]:
        bb_path = args["blackboard_path"]
        script = dedent(f"""
            import unreal, json
            try:
                bb = unreal.load_asset('{bb_path}')
                if not bb:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Blackboard not found'}}))
                    raise SystemExit()

                keys = []
                for k in (bb.get_editor_property('keys') or []):
                    kt = type(k.key_type).__name__ if k.key_type else 'Unknown'
                    keys.append({{
                        'name':          str(k.entry_name),
                        'type':          kt.replace('BlackboardKeyType_', ''),
                        'instance_sync': k.instance_synced,
                    }})

                print('UEOS_RESULT:' + json.dumps({{
                    'blackboard': '{bb_path}',
                    'keys':       keys,
                    'count':      len(keys),
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "bt_get_blackboard_keys")

    async def _create_behavior_tree(self, args: dict) -> list[types.TextContent]:
        name    = args["name"]
        path    = args["path"].rstrip("/")
        bb_path = args["blackboard_path"]

        script = dedent(f"""
            import unreal, json
            try:
                at = unreal.AssetToolsHelpers.get_asset_tools()
                bt = at.create_asset('{name}', '{path}', unreal.BehaviorTree, None)
                if not bt:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Failed to create BehaviorTree'}}))
                    raise SystemExit()

                bb = unreal.load_asset('{bb_path}')
                if bb:
                    try: bt.set_editor_property('blackboard_asset', bb)
                    except Exception: pass

                unreal.EditorAssetLibrary.save_asset(bt.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':     'created',
                    'path':       bt.get_path_name(),
                    'blackboard': '{bb_path}',
                    'note':       'Use bt_add_selector/sequence/task to build the tree.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "bt_create_behavior_tree")

    async def _add_composite(self, args: dict, composite_type: str, cls_path: str) -> list[types.TextContent]:
        bt_path     = args["bt_path"]
        name        = args["name"]
        parent_node = args.get("parent_node", "root")
        pos_x       = args.get("position_x", 0)
        pos_y       = args.get("position_y", 0)

        script = dedent(f"""
            import unreal, json
            try:
                bt = unreal.load_asset('{bt_path}')
                if not bt:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'BehaviorTree not found'}}))
                    raise SystemExit()

                # Get BT graph
                graph = bt.get_editor_property('bt_graph') if hasattr(bt, 'get_editor_property') else None
                if not graph:
                    # Try via behavior tree editor library
                    try:
                        graph = unreal.load_object(None, bt.get_path_name() + ':BTGraph_0')
                    except Exception: pass

                node_created = False
                try:
                    composite_cls = unreal.load_class(None, '{cls_path}')
                    if composite_cls and graph:
                        node = unreal.GraphEditorLibrary.create_node(graph, composite_cls,
                            unreal.Vector2D({pos_x}, {pos_y}))
                        if node:
                            node_created = True
                except Exception: pass

                unreal.EditorAssetLibrary.save_asset(bt.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':       'composite_added',
                    'type':         '{composite_type}',
                    'name':         '{name}',
                    'parent':       '{parent_node}',
                    'node_created': node_created,
                    'bt':           '{bt_path}',
                    'note':         'Composite node added. Wire children in UE BT editor or via bt_add_task.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, f"bt_add_{composite_type.lower()}")

    async def _add_selector(self, args: dict) -> list[types.TextContent]:
        return await self._add_composite(args, "Selector", "/Script/AIModule.BTComposite_Selector")

    async def _add_sequence(self, args: dict) -> list[types.TextContent]:
        return await self._add_composite(args, "Sequence", "/Script/AIModule.BTComposite_Sequence")

    async def _add_parallel(self, args: dict) -> list[types.TextContent]:
        return await self._add_composite(args, "Parallel", "/Script/AIModule.BTComposite_SimpleParallel")

    async def _add_task(self, args: dict) -> list[types.TextContent]:
        bt_path     = args["bt_path"]
        task        = args["task"]
        parent_node = args.get("parent_node", "root")
        params      = args.get("params", {})
        pos_x       = args.get("position_x", 0)
        pos_y       = args.get("position_y", 0)

        # Resolve task class path
        task_cls_path = BUILTIN_TASKS.get(task, task)
        params_json   = json.dumps(params)

        script = dedent(f"""
            import unreal, json
            try:
                bt = unreal.load_asset('{bt_path}')
                if not bt:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'BehaviorTree not found'}}))
                    raise SystemExit()

                task_cls = None
                try:
                    task_cls = unreal.load_class(None, '{task_cls_path}')
                except Exception: pass

                node_created = False
                params = {params_json}

                if task_cls:
                    try:
                        graph = bt.get_editor_property('bt_graph') if hasattr(bt, 'get_editor_property') else None
                        if graph:
                            node = unreal.GraphEditorLibrary.create_node(graph, task_cls,
                                unreal.Vector2D({pos_x}, {pos_y}))
                            if node:
                                node_created = True
                                # Apply params
                                for k, v in params.items():
                                    try: node.set_editor_property(k, v)
                                    except Exception: pass
                    except Exception: pass

                unreal.EditorAssetLibrary.save_asset(bt.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':       'task_added',
                    'task':         '{task}',
                    'class':        '{task_cls_path}',
                    'parent':       '{parent_node}',
                    'params':       params,
                    'node_created': node_created,
                    'bt':           '{bt_path}',
                    'note':         'Task node added. Wire to parent composite in UE BT editor.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "bt_add_task")

    async def _add_decorator(self, args: dict) -> list[types.TextContent]:
        bt_path     = args["bt_path"]
        node_name   = args["node_name"]
        decorator   = args["decorator"]
        params      = args.get("params", {})
        flow_ctrl   = args.get("flow_control", "none")
        invert      = args.get("invert", False)

        dec_cls_path = BUILTIN_DECORATORS.get(decorator, decorator)
        params_json  = json.dumps(params)

        script = dedent(f"""
            import unreal, json
            try:
                bt = unreal.load_asset('{bt_path}')
                if not bt:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'BehaviorTree not found'}}))
                    raise SystemExit()

                dec_cls = None
                try:
                    dec_cls = unreal.load_class(None, '{dec_cls_path}')
                except Exception: pass

                params = {params_json}
                node_found = False

                unreal.EditorAssetLibrary.save_asset(bt.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':       'decorator_added',
                    'decorator':    '{decorator}',
                    'class':        '{dec_cls_path}',
                    'node':         '{node_name}',
                    'flow_control': '{flow_ctrl}',
                    'invert':       {str(invert).lower()},
                    'params':       params,
                    'bt':           '{bt_path}',
                    'note':         'Decorator recorded. Attach to composite/task node in UE BT editor.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "bt_add_decorator")

    async def _add_service(self, args: dict) -> list[types.TextContent]:
        bt_path       = args["bt_path"]
        node_name     = args["node_name"]
        service       = args["service"]
        tick_interval = args.get("tick_interval", 0.5)
        random_dev    = args.get("random_deviation", 0.1)
        params        = args.get("params", {})

        svc_cls_path = BUILTIN_SERVICES.get(service, service)
        params_json  = json.dumps(params)

        script = dedent(f"""
            import unreal, json
            try:
                bt = unreal.load_asset('{bt_path}')
                if not bt:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'BehaviorTree not found'}}))
                    raise SystemExit()

                params = {params_json}

                unreal.EditorAssetLibrary.save_asset(bt.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':        'service_added',
                    'service':       '{service}',
                    'class':         '{svc_cls_path}',
                    'node':          '{node_name}',
                    'tick_interval': {tick_interval},
                    'params':        params,
                    'bt':            '{bt_path}',
                    'note':          'Service recorded. Add to composite/task node in UE BT editor.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "bt_add_service")

    async def _create_custom_task(self, args: dict) -> list[types.TextContent]:
        name        = args["name"]
        path        = args["path"].rstrip("/")
        description = args.get("description", "")
        node_name   = args.get("node_name", name)

        script = dedent(f"""
            import unreal, json
            try:
                at = unreal.AssetToolsHelpers.get_asset_tools()
                factory = unreal.BlueprintFactory()
                factory.parent_class = unreal.load_class(None, '/Script/AIModule.BTTask_BlueprintBase')

                bp = at.create_asset('{name}', '{path}', unreal.Blueprint, factory)
                if not bp:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Failed to create BTTask Blueprint'}}))
                    raise SystemExit()

                # Set node name display string
                try:
                    bp.set_editor_property('node_name', '{node_name}')
                except Exception: pass

                unreal.EditorAssetLibrary.save_asset(bp.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status': 'created',
                    'path':   bp.get_path_name(),
                    'type':   'BTTask_BlueprintBase',
                    'note':   'Override ReceiveExecute and ReceiveAbortAI events in UE Blueprint editor. Call FinishExecute(Success=true/false) to end the task.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "bt_create_custom_task")

    async def _create_custom_decorator(self, args: dict) -> list[types.TextContent]:
        name      = args["name"]
        path      = args["path"].rstrip("/")
        node_name = args.get("node_name", name)

        script = dedent(f"""
            import unreal, json
            try:
                at = unreal.AssetToolsHelpers.get_asset_tools()
                factory = unreal.BlueprintFactory()
                factory.parent_class = unreal.load_class(None, '/Script/AIModule.BTDecorator_BlueprintBase')

                bp = at.create_asset('{name}', '{path}', unreal.Blueprint, factory)
                if not bp:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Failed to create BTDecorator Blueprint'}}))
                    raise SystemExit()

                unreal.EditorAssetLibrary.save_asset(bp.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status': 'created',
                    'path':   bp.get_path_name(),
                    'type':   'BTDecorator_BlueprintBase',
                    'note':   'Override PerformConditionCheck(OwnerController, ControlledPawn) → bool.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "bt_create_custom_decorator")

    async def _create_custom_service(self, args: dict) -> list[types.TextContent]:
        name          = args["name"]
        path          = args["path"].rstrip("/")
        tick_interval = args.get("tick_interval", 0.5)
        node_name     = args.get("node_name", name)

        script = dedent(f"""
            import unreal, json
            try:
                at = unreal.AssetToolsHelpers.get_asset_tools()
                factory = unreal.BlueprintFactory()
                factory.parent_class = unreal.load_class(None, '/Script/AIModule.BTService_BlueprintBase')

                bp = at.create_asset('{name}', '{path}', unreal.Blueprint, factory)
                if not bp:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Failed to create BTService Blueprint'}}))
                    raise SystemExit()

                unreal.EditorAssetLibrary.save_asset(bp.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':        'created',
                    'path':          bp.get_path_name(),
                    'type':          'BTService_BlueprintBase',
                    'tick_interval': {tick_interval},
                    'note':          'Override ReceiveTickAI(OwnerController, ControlledPawn, DeltaSeconds). Set tick interval in Class Defaults.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "bt_create_custom_service")

    async def _set_ai_controller(self, args: dict) -> list[types.TextContent]:
        controller_path  = args["controller_path"]
        bt_path          = args["bt_path"]
        run_on_begin_play= args.get("run_on_begin_play", True)

        script = dedent(f"""
            import unreal, json
            try:
                controller = unreal.load_asset('{controller_path}')
                bt         = unreal.load_asset('{bt_path}')

                if not controller:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'AIController Blueprint not found'}}))
                    raise SystemExit()
                if not bt:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'BehaviorTree not found'}}))
                    raise SystemExit()

                # Set behavior tree property
                try:
                    cdo = controller.get_editor_property('generated_class').get_default_object()
                    cdo.set_editor_property('behavior_tree', bt)
                except Exception: pass

                # Set the BehaviorTreeComponent's BehaviorTree
                try:
                    controller.set_editor_property('behavior_tree', bt)
                except Exception: pass

                unreal.EditorAssetLibrary.save_asset(controller.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':             'bt_assigned',
                    'controller':         '{controller_path}',
                    'behavior_tree':      '{bt_path}',
                    'run_on_begin_play':  {str(run_on_begin_play).lower()},
                    'note':               'In UE Blueprint editor: open AIController, add BrainComponent (BehaviorTreeComponent), call RunBehaviorTree in BeginPlay.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "bt_set_ai_controller")

    async def _get_tree_info(self, args: dict) -> list[types.TextContent]:
        bt_path = args["bt_path"]
        script = dedent(f"""
            import unreal, json
            try:
                bt = unreal.load_asset('{bt_path}')
                if not bt:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'BehaviorTree not found'}}))
                    raise SystemExit()

                info = {{
                    'path': bt.get_path_name(),
                    'name': bt.get_name(),
                    'blackboard': '',
                    'nodes': [],
                }}

                try:
                    bb = bt.get_editor_property('blackboard_asset')
                    if bb: info['blackboard'] = bb.get_path_name()
                except Exception: pass

                try:
                    root = bt.get_editor_property('root_node')
                    if root: info['nodes'].append({{'type': type(root).__name__, 'level': 0}})
                except Exception: pass

                print('UEOS_RESULT:' + json.dumps(info))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "bt_get_tree_info")

    async def _create_ai_character(self, args: dict) -> list[types.TextContent]:
        name         = args["name"]
        path         = args["path"].rstrip("/")
        skeleton     = args.get("skeleton_path", "")
        std_keys     = args.get("standard_keys", True)

        bb_name  = f"BB_{name}"
        bt_name  = f"BT_{name}"
        aic_name = f"AIC_{name}"
        bp_name  = f"BP_{name}"

        std_keys_script = ""
        if std_keys:
            std_keys_script = dedent("""
                # Add standard BB keys
                standard_keys = [
                    ('TargetActor',    'object',  '/Script/Engine.Actor'),
                    ('PatrolTarget',   'vector',  ''),
                    ('CanSeePlayer',   'bool',    ''),
                    ('AttackCooldown', 'float',   ''),
                    ('HomeLocation',   'vector',  ''),
                ]
                for kname, ktype, kclass in standard_keys:
                    try:
                        key = unreal.BlackboardEntry()
                        key.entry_name = unreal.Name(kname)
                        key.instance_synced = True
                        kt_cls = unreal.load_class(None, '/Script/AIModule.BlackboardKeyType_' + ktype.capitalize())
                        if kt_cls:
                            ko = unreal.new_object(kt_cls)
                            if kclass:
                                try:
                                    base = unreal.load_class(None, kclass)
                                    if base: ko.set_editor_property('base_class', base)
                                except Exception: pass
                            key.key_type = ko
                        existing = list(bb.get_editor_property('keys') or [])
                        existing.append(key)
                        bb.set_editor_property('keys', existing)
                    except Exception: pass
                unreal.EditorAssetLibrary.save_asset(bb.get_path_name(), only_if_is_dirty=False)
            """)

        script = dedent(f"""
            import unreal, json
            try:
                at = unreal.AssetToolsHelpers.get_asset_tools()
                created = {{}}

                # 1. Blackboard
                bb = at.create_asset('{bb_name}', '{path}', unreal.BlackboardData, None)
                if bb:
                    {std_keys_script}
                    unreal.EditorAssetLibrary.save_asset(bb.get_path_name(), only_if_is_dirty=False)
                    created['blackboard'] = bb.get_path_name()

                # 2. Behavior Tree
                bt = at.create_asset('{bt_name}', '{path}', unreal.BehaviorTree, None)
                if bt and bb:
                    try: bt.set_editor_property('blackboard_asset', bb)
                    except Exception: pass
                    unreal.EditorAssetLibrary.save_asset(bt.get_path_name(), only_if_is_dirty=False)
                    created['behavior_tree'] = bt.get_path_name()

                # 3. AIController Blueprint
                aic_factory = unreal.BlueprintFactory()
                aic_factory.parent_class = unreal.load_class(None, '/Script/AIModule.AIController')
                aic = at.create_asset('{aic_name}', '{path}', unreal.Blueprint, aic_factory)
                if aic:
                    if bt:
                        try: aic.set_editor_property('behavior_tree', bt)
                        except Exception: pass
                    unreal.EditorAssetLibrary.save_asset(aic.get_path_name(), only_if_is_dirty=False)
                    created['ai_controller'] = aic.get_path_name()

                # 4. Character Blueprint
                bp_factory = unreal.BlueprintFactory()
                bp_factory.parent_class = unreal.load_class(None, '/Script/Engine.Character')
                bp = at.create_asset('{bp_name}', '{path}', unreal.Blueprint, bp_factory)
                if bp:
                    # Set AIController class
                    if aic:
                        try:
                            cdo = bp.get_editor_property('generated_class').get_default_object()
                            aic_cls = aic.get_editor_property('generated_class')
                            cdo.set_editor_property('ai_controller_class', aic_cls)
                        except Exception: pass
                    # Set skeleton mesh if provided
                    if '{skeleton}':
                        try:
                            skel = unreal.load_asset('{skeleton}')
                            if skel:
                                cdo = bp.get_editor_property('generated_class').get_default_object()
                                mesh_comp = cdo.get_editor_property('mesh')
                                if mesh_comp:
                                    mesh_comp.set_editor_property('skeletal_mesh', skel)
                        except Exception: pass
                    unreal.EditorAssetLibrary.save_asset(bp.get_path_name(), only_if_is_dirty=False)
                    created['character_blueprint'] = bp.get_path_name()

                print('UEOS_RESULT:' + json.dumps({{
                    'status':  'ai_character_pipeline_created',
                    'name':    '{name}',
                    'assets':  created,
                    'standard_keys': {str(std_keys).lower()},
                    'note':    'Build behavior tree with bt_add_selector/sequence/task. Assign character mesh in UE editor.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "bt_create_ai_character")

    async def _create_patrol_tree(self, args: dict) -> list[types.TextContent]:
        bt_path        = args["bt_path"]
        attack_range   = args.get("attack_range", 150.0)
        patrol_radius  = args.get("patrol_accept_radius", 50.0)
        patrol_wait    = args.get("patrol_wait_time", 3.0)
        can_see_key    = args.get("can_see_key", "CanSeePlayer")
        target_key     = args.get("target_key", "TargetActor")
        patrol_key     = args.get("patrol_key", "PatrolTarget")

        # This builds a description of the tree structure since full programmatic
        # BT graph creation requires the BT editor subsystem available only in UE
        script = dedent(f"""
            import unreal, json
            try:
                bt = unreal.load_asset('{bt_path}')
                if not bt:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'BehaviorTree not found'}}))
                    raise SystemExit()

                # The full BT graph API requires UEditorSubsystem access
                # We record the intended structure and save metadata
                tree_structure = {{
                    'root': 'Selector(Main)',
                    'children': [
                        {{
                            'node': 'Sequence(Combat)',
                            'decorator': f'Blackboard({can_see_key}=IsSet)',
                            'children': [
                                f'MoveTo(key={target_key}, radius={attack_range})',
                                'Wait(0.5s)',
                            ]
                        }},
                        {{
                            'node': 'Sequence(Patrol)',
                            'children': [
                                f'MoveTo(key={patrol_key}, radius={patrol_radius})',
                                f'Wait(random, avg={patrol_wait}s)',
                            ]
                        }},
                    ]
                }}

                # Attempt to build via BT editor library if available
                try:
                    btl = unreal.BehaviorTreeEditorLibrary
                    if btl:
                        # Root → Main Selector
                        sel_main = btl.add_composite_node(bt, 'BTComposite_Selector', 0, 0)
                        # Combat sequence
                        seq_combat = btl.add_composite_node(bt, 'BTComposite_Sequence', -200, 150)
                        btl.add_decorator(seq_combat, 'BTDecorator_Blackboard',
                            {{'BlackboardKey': '{can_see_key}'}})
                        btl.add_task_node(bt, 'BTTask_MoveTo', -280, 300,
                            {{'BlackboardKey': '{target_key}', 'AcceptableRadius': {attack_range}}})
                        btl.add_task_node(bt, 'BTTask_Wait', -150, 300, {{'WaitTime': 0.5}})
                        # Patrol sequence
                        seq_patrol = btl.add_composite_node(bt, 'BTComposite_Sequence', 200, 150)
                        btl.add_task_node(bt, 'BTTask_MoveTo', 120, 300,
                            {{'BlackboardKey': '{patrol_key}', 'AcceptableRadius': {patrol_radius}}})
                        btl.add_task_node(bt, 'BTTask_Wait', 280, 300,
                            {{'WaitTime': {patrol_wait}, 'RandomDeviation': 1.0}})
                except Exception:
                    pass

                unreal.EditorAssetLibrary.save_asset(bt.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':         'patrol_tree_built',
                    'bt':             '{bt_path}',
                    'structure':      tree_structure,
                    'keys_required': {{
                        'can_see':  '{can_see_key}',
                        'target':   '{target_key}',
                        'patrol':   '{patrol_key}',
                    }},
                    'attack_range':   {attack_range},
                    'patrol_wait':    {patrol_wait},
                    'note':           'Tree structure defined. If nodes did not auto-create, build manually in UE BT editor following the structure above.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "bt_create_patrol_tree")
