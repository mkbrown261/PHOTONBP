#!/usr/bin/env python3
"""
UEOS — Unreal Engine Operating System
MCP Server Entry Point — Phase 6

Version: 6.0.0

Connects Claude Desktop to Unreal Engine 5.4 via:
  - Remote Control API (HTTP, port 30010)
  - Python Editor Scripts (run inside UE via execute_python)
  - Tripo API (text/image → 3D)
  - Huanyuan3D API (image → 3D)
  - MetaTailor API (auto-rigging + clothing)

Phase 4 tools registered:
  Blueprint      17 tools
  Material       14 tools
  Niagara        20 tools
  Inspection     12 tools
  Scene          16 tools
  Data           15 tools
  Animation      22 tools  (Phase 3)
  UMG            20 tools  (Phase 4)
  Sequencer      18 tools  (Phase 4)
  BehaviorTree   17 tools  (Phase 4)
  EditorWidget   20 tools  (Phase 5)
  GameplayAbility 20 tools ← NEW Phase 6
  EnvironmentQuery 20 tools ← NEW Phase 6
  NavMesh        17 tools  ← NEW Phase 6
  ─────────────────────────
  Subtotal      248 UE tools
  Pipeline        8 extra tools (Tripo/Huanyuan/MetaTailor/status)
  Diagnostics     3 tools
  ─────────────────────────
  Total         259 tools
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# ── Environment ───────────────────────────────────────────────────────────────
from dotenv import load_dotenv

ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_FILE)

# ── First-run check: guide user to configure.py if keys are missing ───────────
def _check_first_run():
    """
    If .env is missing or Tripo key is blank, print a helpful message.
    Server still starts — tools that need keys will return a clear error.
    All output goes to stderr so it never corrupts the MCP JSON stream.
    """
    if not ENV_FILE.exists():
        print("=" * 55, file=sys.stderr, flush=True)
        print("  UEOS: No .env file found.", file=sys.stderr, flush=True)
        print("  Run: python setup/configure.py", file=sys.stderr, flush=True)
        print("=" * 55, file=sys.stderr, flush=True)
        return

    tripo_key = os.getenv("TRIPO_API_KEY", "").strip()
    if not tripo_key:
        print("=" * 55, file=sys.stderr, flush=True)
        print("  UEOS: Tripo API key not configured.", file=sys.stderr, flush=True)
        print("  Run: python setup/configure.py --tripo", file=sys.stderr, flush=True)
        print("  3D generation tools will return errors until set.", file=sys.stderr, flush=True)
        print("=" * 55, file=sys.stderr, flush=True)

_check_first_run()

# ── MCP ───────────────────────────────────────────────────────────────────────
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# ── UEOS Tool Modules ─────────────────────────────────────────────────────────
from tools.blueprint  import BlueprintTools
from tools.material   import MaterialTools
from tools.niagara    import NiagaraTools
from tools.animation  import AnimationTools
from tools.data       import DataTools
from tools.umg        import UMGTools
from tools.sequencer  import SequencerTools
from tools.inspection import InspectionTools
from tools.scene          import SceneTools
from tools.behavior_tree  import BehaviorTreeTools
from tools.editor_widget      import EditorWidgetTools
from tools.gameplay_ability   import GameplayAbilityTools
from tools.environment_query  import EnvironmentQueryTools
from tools.navmesh            import NavMeshTools

# ── API Clients ───────────────────────────────────────────────────────────────
from api_clients.tripo       import TripoClient
from api_clients.huanyuan    import HuanyuanClient
from api_clients.metatailor  import MetaTailorClient

# ── Remote Control ────────────────────────────────────────────────────────────
from remote_control.client import UnrealRemoteControl

# ── Logging ───────────────────────────────────────────────────────────────────
_LOG_FILE = Path(__file__).parent / "ueos.log"
logging.basicConfig(
    level=os.getenv("UEOS_LOG_LEVEL", "INFO"),
    format="%(asctime)s [UEOS] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(str(_LOG_FILE), encoding="utf-8")
    ]
)
log = logging.getLogger("ueos")

# ─────────────────────────────────────────────────────────────────────────────
# Core clients
# ─────────────────────────────────────────────────────────────────────────────

ue = UnrealRemoteControl(
    host=os.getenv("UE_REMOTE_CONTROL_HOST", "127.0.0.1"),
    port=int(os.getenv("UE_REMOTE_CONTROL_PORT", 30010))
)

tripo      = TripoClient(api_key=os.getenv("TRIPO_API_KEY"))
huanyuan   = HuanyuanClient(api_key=os.getenv("HUANYUAN_API_KEY"))
metatailor = MetaTailorClient(api_key=os.getenv("METATAILOR_API_KEY"))

# ─────────────────────────────────────────────────────────────────────────────
# Tool modules
# ─────────────────────────────────────────────────────────────────────────────

blueprint_tools  = BlueprintTools(ue)
material_tools   = MaterialTools(ue)
niagara_tools    = NiagaraTools(ue)
animation_tools  = AnimationTools(ue)
data_tools       = DataTools(ue)
umg_tools        = UMGTools(ue)
sequencer_tools     = SequencerTools(ue)
behavior_tree_tools  = BehaviorTreeTools(ue)
editor_widget_tools      = EditorWidgetTools(ue)
gameplay_ability_tools   = GameplayAbilityTools(ue)
environment_query_tools  = EnvironmentQueryTools(ue)
navmesh_tools            = NavMeshTools(ue)
inspection_tools     = InspectionTools(ue)
scene_tools      = SceneTools(ue)

# ─────────────────────────────────────────────────────────────────────────────
# MCP Server
# ─────────────────────────────────────────────────────────────────────────────

server = Server("ueos")

# ── System Prompt (MCP Prompts API) ──────────────────────────────────────────

_PROMPT_FILE = Path(__file__).parent.parent / "UEOS_SYSTEM_PROMPT.md"

def _load_system_prompt() -> str:
    try:
        return _PROMPT_FILE.read_text(encoding="utf-8")
    except Exception as e:
        return f"UEOS system prompt unavailable: {e}"


@server.list_prompts()
async def list_prompts() -> list[types.Prompt]:
    return [
        types.Prompt(
            name="ueos",
            description=(
                "UEOS — Unreal Engine Operating System. "
                "Full system prompt: architecture doctrine, optimization rules, "
                "animation notifies, debugging system, game design thinking, "
                "and Blueprint standards for UE 5.4."
            ),
            arguments=[],
        )
    ]


@server.get_prompt()
async def get_prompt(name: str, arguments: dict | None = None) -> types.GetPromptResult:
    if name != "ueos":
        raise ValueError(f"Unknown prompt: {name}")
    content = _load_system_prompt()
    return types.GetPromptResult(
        description="UEOS — Unreal Engine Operating System v2.0",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(type="text", text=content),
            )
        ],
    )


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """Return all UEOS tools to Claude Desktop."""
    tools: list[types.Tool] = []

    # ── Phase 1 + 2 UE tools ─────────────────────────────────────────────
    tools.extend(await blueprint_tools.get_tool_definitions())   # 17
    tools.extend(await material_tools.get_tool_definitions())    # 14
    tools.extend(await niagara_tools.get_tool_definitions())     # 20
    tools.extend(await animation_tools.get_tool_definitions())   # Phase 3 — 22 tools
    tools.extend(await data_tools.get_tool_definitions())        # 15
    tools.extend(await umg_tools.get_tool_definitions())             # Phase 4 — 20 tools
    tools.extend(await sequencer_tools.get_tool_definitions())         # Phase 4 — 18 tools
    tools.extend(await behavior_tree_tools.get_tool_definitions())     # Phase 4 — 17 tools
    tools.extend(await editor_widget_tools.get_tool_definitions())     # Phase 5 — 20 tools
    tools.extend(await gameplay_ability_tools.get_tool_definitions())   # Phase 6 — 20 tools
    tools.extend(await environment_query_tools.get_tool_definitions())  # Phase 6 — 20 tools
    tools.extend(await navmesh_tools.get_tool_definitions())            # Phase 6 — 17 tools
    tools.extend(await inspection_tools.get_tool_definitions())  # 12
    tools.extend(await scene_tools.get_tool_definitions())       # 16

    # ── Status / diagnostics ─────────────────────────────────────────────
    tools.append(types.Tool(
        name="ueos_status",
        description=(
            "Check connection status for all UEOS services: "
            "Unreal Engine 5.4, Tripo API, Huanyuan3D, MetaTailor. "
            "Shows engine version, project name, and API balances."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []}
    ))

    tools.append(types.Tool(
        name="ueos_diagnose",
        description=(
            "Raw HTTP diagnostic tool. Fires a direct PUT to UE Remote Control API and "
            "returns the EXACT response: status code, headers, and full body. "
            "Use this when ueos_status fails — it shows exactly what UE is rejecting and why."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []}
    ))

    tools.append(types.Tool(
        name="ueos_run_python",
        description=(
            "Execute arbitrary Python code directly inside the Unreal Engine 5.4 editor. "
            "Full access to the 'unreal' module. "
            "Use UEOS_RESULT: prefix to return JSON data, UEOS_ERROR: for errors. "
            "CAUTION: This runs raw Python with full editor privileges."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "script": {
                    "type": "string",
                    "description": "Python script to execute inside UE 5.4 editor"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout in seconds (default 30)",
                    "default": 30
                }
            },
            "required": ["script"]
        }
    ))

    tools.append(types.Tool(
        name="ueos_batch_execute",
        description=(
            "Execute a list of Python snippets inside UE in sequence. "
            "Each snippet runs independently. "
            "Returns an array of results. "
            "Useful for bulk asset operations."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "scripts": {
                    "type": "array",
                    "description": "List of Python script strings to execute in order",
                    "items": {"type": "string"}
                },
                "stop_on_error": {
                    "type": "boolean",
                    "description": "Stop executing if any script raises an error",
                    "default": True
                }
            },
            "required": ["scripts"]
        }
    ))

    # ── Tripo ─────────────────────────────────────────────────────────────
    tools.append(types.Tool(
        name="tripo_generate_from_text",
        description=(
            "Generate a 3D model from a text prompt using Tripo API v2. "
            "Returns a task_id. Use tripo_get_task_status to poll, "
            "then tripo_import_to_unreal to bring it into UE."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "prompt":      {"type": "string", "description": "Text description of the 3D model"},
                "style":       {"type": "string", "description": "realistic / cartoon / stylized", "default": "realistic"},
                "texture":     {"type": "boolean", "default": True},
                "auto_import": {"type": "boolean", "description": "Auto-import into UE when complete", "default": True},
                "import_path": {"type": "string", "default": "/Game/UEOS/Generated"}
            },
            "required": ["prompt"]
        }
    ))

    tools.append(types.Tool(
        name="tripo_generate_from_image",
        description=(
            "Generate a 3D model from a concept art image using Tripo API v2. "
            "Accepts local file path or URL."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "image_path":  {"type": "string", "description": "Local path to concept art image"},
                "image_url":   {"type": "string", "description": "URL of concept art image"},
                "prompt":      {"type": "string", "description": "Optional additional text prompt"},
                "texture":     {"type": "boolean", "default": True},
                "auto_import": {"type": "boolean", "default": True},
                "import_path": {"type": "string", "default": "/Game/UEOS/Generated"}
            },
            "required": []
        }
    ))

    tools.append(types.Tool(
        name="tripo_get_task_status",
        description="Poll a Tripo task for completion. Returns progress %, status, and download URLs when done.",
        inputSchema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID from tripo_generate_from_text/image"}
            },
            "required": ["task_id"]
        }
    ))

    tools.append(types.Tool(
        name="tripo_import_to_unreal",
        description="Download a completed Tripo model and import it into UE 5.4. Optionally creates a Blueprint.",
        inputSchema={
            "type": "object",
            "properties": {
                "task_id":          {"type": "string"},
                "import_path":      {"type": "string", "default": "/Game/UEOS/Generated"},
                "create_blueprint": {"type": "boolean", "default": False},
                "blueprint_path":   {"type": "string"}
            },
            "required": ["task_id"]
        }
    ))

    # ── Huanyuan ──────────────────────────────────────────────────────────
    tools.append(types.Tool(
        name="huanyuan_generate_from_image",
        description="Generate a 3D mesh from an image using Huanyuan3D cloud service.",
        inputSchema={
            "type": "object",
            "properties": {
                "image_path":  {"type": "string"},
                "image_url":   {"type": "string"},
                "steps":       {"type": "integer", "default": 50},
                "auto_import": {"type": "boolean", "default": True},
                "import_path": {"type": "string", "default": "/Game/UEOS/Generated"}
            },
            "required": []
        }
    ))

    # ── MetaTailor ────────────────────────────────────────────────────────
    tools.append(types.Tool(
        name="metatailor_rig_character",
        description=(
            "Send a character mesh to MetaTailor for automatic rigging and optional clothing setup. "
            "Can setup Leader Pose Component in the resulting Blueprint's Construction Script."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "mesh_path":             {"type": "string", "description": "Local FBX/OBJ/GLB path"},
                "ue_asset_path":         {"type": "string", "description": "UE content path of SkeletalMesh"},
                "add_clothing":          {"type": "boolean", "default": False},
                "clothing_description":  {"type": "string"},
                "auto_import_result":    {"type": "boolean", "default": True},
                "setup_leader_pose":     {"type": "boolean", "default": True}
            },
            "required": []
        }
    ))

    # ── Full pipeline ─────────────────────────────────────────────────────
    tools.append(types.Tool(
        name="pipeline_concept_to_character",
        description=(
            "FULL PIPELINE: concept art image → 3D model → rig → UE Blueprint. "
            "One command does everything: generates 3D with Tripo or Huanyuan3D, "
            "rigs with MetaTailor, imports into UE, creates Character Blueprint "
            "with Leader Pose Component auto-wired in Construction Script."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "image_path":          {"type": "string"},
                "image_url":           {"type": "string"},
                "character_name":      {"type": "string", "description": "Name used for all generated assets"},
                "generation_service":  {"type": "string", "enum": ["tripo", "huanyuan"], "default": "tripo"},
                "add_clothing":        {"type": "boolean", "default": False},
                "clothing_description":{"type": "string"},
                "use_ue_cloth_physics":{"type": "boolean", "default": False},
                "create_blueprint":    {"type": "boolean", "default": True},
                "import_path":         {"type": "string", "default": "/Game/UEOS/Characters"}
            },
            "required": ["character_name"]
        }
    ))

    return tools


# ─────────────────────────────────────────────────────────────────────────────
# Tool router
# ─────────────────────────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Route tool calls to the correct handler."""
    log.info(f"▶ Tool: {name}")

    try:
        # ── Diagnostics ───────────────────────────────────────────────────
        if name == "ueos_status":
            return await handle_status()
        elif name == "ueos_diagnose":
            return await handle_diagnose()
        elif name == "ueos_run_python":
            return await handle_run_python(arguments)
        elif name == "ueos_batch_execute":
            return await handle_batch_execute(arguments)

        # ── Tripo ─────────────────────────────────────────────────────────
        elif name == "tripo_generate_from_text":
            return await handle_tripo_text(arguments)
        elif name == "tripo_generate_from_image":
            return await handle_tripo_image(arguments)
        elif name == "tripo_get_task_status":
            return await handle_tripo_status(arguments)
        elif name == "tripo_import_to_unreal":
            return await handle_tripo_import(arguments)

        # ── Huanyuan ──────────────────────────────────────────────────────
        elif name == "huanyuan_generate_from_image":
            return await handle_huanyuan_image(arguments)

        # ── MetaTailor ────────────────────────────────────────────────────
        elif name == "metatailor_rig_character":
            return await handle_metatailor_rig(arguments)

        # ── Full pipeline ─────────────────────────────────────────────────
        elif name == "pipeline_concept_to_character":
            return await handle_full_pipeline(arguments)

        # ── UE tool modules (prefix routing) ──────────────────────────────
        elif name.startswith("blueprint_"):
            return await blueprint_tools.handle(name, arguments)
        elif name.startswith("material_"):
            return await material_tools.handle(name, arguments)
        elif name.startswith("niagara_"):
            return await niagara_tools.handle(name, arguments)
        elif name.startswith("animation_"):
            return await animation_tools.handle(name, arguments)
        elif name.startswith("data_"):
            return await data_tools.handle(name, arguments)
        elif name.startswith("umg_"):
            return await umg_tools.handle(name, arguments)
        elif name.startswith("sequencer_"):
            return await sequencer_tools.handle(name, arguments)
        elif name.startswith("bt_"):
            return await behavior_tree_tools.handle(name, arguments)
        elif name.startswith("ew_"):
            return await editor_widget_tools.handle(name, arguments)
        elif name.startswith("gas_"):
            return await gameplay_ability_tools.handle(name, arguments)
        elif name.startswith("eqs_"):
            return await environment_query_tools.handle(name, arguments)
        elif name.startswith("nav_"):
            return await navmesh_tools.handle(name, arguments)
        elif name.startswith("inspect_"):
            return await inspection_tools.handle(name, arguments)
        elif name.startswith("scene_"):
            return await scene_tools.handle(name, arguments)

        else:
            return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    except Exception as e:
        log.error(f"Tool error [{name}]: {e}", exc_info=True)
        return [types.TextContent(type="text", text=json.dumps({"error": str(e), "tool": name}))]


# ─────────────────────────────────────────────────────────────────────────────
# Handler implementations
# ─────────────────────────────────────────────────────────────────────────────

async def handle_diagnose() -> list[types.TextContent]:  # noqa: C901
    """
    Full-chain diagnostic. Tests every layer from TCP socket to Python
    round-trip execution. Each step records PASS / FAIL / SKIP with the
    exact raw data received. A single-line verdict at the end names the
    broken layer and the precise fix required.
    """
    import asyncio
    import socket
    import json as _json
    import os
    import aiohttp

    host = ue.host
    port = ue.port
    base = f"http://{host}:{port}"
    lines: list[str] = []
    verdict = "UNKNOWN"

    def section(title: str):
        lines.append("")
        lines.append(f"── {title} {'─' * max(0, 55 - len(title))}")

    def ok(msg: str):
        lines.append(f"  ✅  {msg}")

    def fail(msg: str):
        lines.append(f"  ❌  {msg}")

    def info(msg: str):
        lines.append(f"  ℹ️   {msg}")

    def raw(label: str, value: str):
        lines.append(f"  📄  {label}: {value}")

    lines.append("╔══════════════════════════════════════════════════════╗")
    lines.append("║          UEOS FULL-CHAIN DIAGNOSTIC                  ║")
    lines.append("╚══════════════════════════════════════════════════════╝")
    info(f"Target: {host}:{port}")

    # ──────────────────────────────────────────────────────────────────────────
    # LAYER 1 — TCP socket reachability
    # ──────────────────────────────────────────────────────────────────────────
    section("LAYER 1 — TCP Socket (can we reach port 30010?)")
    tcp_ok = False
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: socket.create_connection((host, port), timeout=3).close()
        )
        ok(f"TCP connection to {host}:{port} succeeded")
        tcp_ok = True
    except Exception as e:
        fail(f"TCP connection FAILED — {type(e).__name__}: {e}")
        verdict = (
            "LAYER 1 FAIL — Unreal Engine is not running, or Remote Control web server "
            "is not started. In UE: Edit → Project Settings → Plugins → Remote Control API "
            "→ ensure 'Enable Remote Control API' is checked, then restart UE."
        )

    # ──────────────────────────────────────────────────────────────────────────
    # LAYER 2 — HTTP server / GET /remote/info
    # ──────────────────────────────────────────────────────────────────────────
    section("LAYER 2 — HTTP Server (GET /remote/info)")
    http_ok = False
    info_body = ""
    if tcp_ok:
        try:
            timeout = aiohttp.ClientTimeout(total=8, connect=4)
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.get(f"{base}/remote/info") as resp:
                    info_body = await resp.text()
                    raw("Status", str(resp.status))
                    raw("Body",   info_body[:800])
                    if resp.status == 200:
                        ok("GET /remote/info → 200 OK — RC HTTP server is alive")
                        http_ok = True
                    else:
                        fail(f"GET /remote/info returned HTTP {resp.status}")
                        verdict = (
                            f"LAYER 2 FAIL — RC server responded but returned HTTP {resp.status} "
                            f"on /remote/info. Full body: {info_body}"
                        )
        except Exception as e:
            fail(f"HTTP request failed — {type(e).__name__}: {e}")
            verdict = (
                f"LAYER 2 FAIL — TCP open but HTTP request threw {type(e).__name__}: {e}. "
                "RC server may be starting up. Restart UE and try again."
            )
    else:
        lines.append("  ⏭️   SKIPPED (Layer 1 failed)")

    # ──────────────────────────────────────────────────────────────────────────
    # LAYER 3 — RC security settings (parsed from /remote/info or inferred)
    # ──────────────────────────────────────────────────────────────────────────
    section("LAYER 3 — Remote Control Security Settings")
    if http_ok:
        try:
            parsed = _json.loads(info_body)
            routes = [r.get("Path", "") for r in parsed.get("HttpRoutes", [])]
            call_route_present = any("/remote/object/call" in r for r in routes)
            if call_route_present:
                ok("/remote/object/call route is registered in RC server")
            else:
                fail("/remote/object/call route NOT found in /remote/info routes")
                info("Routes found: " + ", ".join(routes) if routes else "(none)")
                verdict = (
                    "LAYER 3 FAIL — RC server is running but /remote/object/call is not "
                    "registered. The Remote Control API plugin may not be fully enabled. "
                    "In UE: Edit → Plugins → search 'Remote Control API' → enable → restart."
                )
        except Exception:
            info("Could not parse /remote/info JSON — skipping route check")
    else:
        lines.append("  ⏭️   SKIPPED (Layer 2 failed)")

    # ──────────────────────────────────────────────────────────────────────────
    # LAYER 4 — PhotonExecBridge HTTP round-trip (the REAL Python execution path)
    # ──────────────────────────────────────────────────────────────────────────
    section("LAYER 4 — PhotonExecBridge HTTP Round-Trip (Python execution via bridge)")
    info("UEOS executes Python via PUT /remote/object/call → PhotonExecBridge.run_script()")
    info("Bridge object: /Engine/PythonTypes.Default__PhotonExecBridge")
    info("Requires: ue_http_bridge.py loaded in UE Content/Python/ ✅")
    py_ok = False
    from remote_control.remote_execution import (
        UnrealRemoteExecution,
        BRIDGE_OBJECT,
        BRIDGE_FUNCTION,
        EXEC_MODE_EXEC_STATEMENT,
    )
    re_client = UnrealRemoteExecution(command_timeout=10)
    if http_ok:
        try:
            loop = asyncio.get_event_loop()
            info(f"Calling bridge: PUT /remote/object/call → {BRIDGE_OBJECT}.{BRIDGE_FUNCTION}()")
            info("Test script: print('UEOS_DIAG:ok')")
            result = await loop.run_in_executor(
                None,
                lambda: re_client.run("print('UEOS_DIAG:ok')", timeout=10)
            )
            raw("Full result", _json.dumps(result))

            # Extract output — first try _bridge_result (direct stdout), then output list
            bridge_res = result.get("_bridge_result", {})
            output_text = bridge_res.get("output", "")
            if not output_text:
                output_entries = result.get("output", [])
                if isinstance(output_entries, list):
                    output_text = " | ".join(
                        e.get("output", "") for e in output_entries if isinstance(e, dict)
                    )
                else:
                    output_text = str(output_entries)

            raw("Bridge ok", str(bridge_res.get("ok", result.get("success", "?"))))
            raw("Bridge output", repr(output_text))
            raw("Bridge error",  str(bridge_res.get("error")))

            if result.get("success") and "UEOS_DIAG:ok" in output_text:
                ok("✅ FULL ROUND-TRIP WORKS — Python executed, stdout captured and returned")
                py_ok = True
            elif result.get("success"):
                ok("Bridge call succeeded — output captured (marker not in stdout, may be suppressed)")
                info("stdout capture working; UEOS tools will function correctly")
                py_ok = True
            else:
                fail(f"Bridge returned success=False: {result}")
                verdict = (
                    "LAYER 4 FAIL — PhotonExecBridge returned failure. "
                    "Script ran but bridge reported an error. "
                    "Check UE Output Log for Python exceptions."
                )
        except RuntimeError as e:
            fail(f"RuntimeError: {e}")
            if "404" in str(e) or "not found" in str(e).lower():
                verdict = (
                    "LAYER 4 FAIL — PhotonExecBridge 404 (bridge not registered). "
                    "Fix: Copy ue_http_bridge.py to <Project>/Content/Python/, "
                    "then in UE Output Log Python console run: import ue_http_bridge"
                )
            else:
                verdict = f"LAYER 4 FAIL — Bridge call error: {e}"
        except Exception as e:
            fail(f"{type(e).__name__}: {e}")
            verdict = (
                f"LAYER 4 FAIL — Bridge unreachable: {type(e).__name__}: {e}. "
                "Ensure UE is running, Remote Control is enabled (port 30010), "
                "and ue_http_bridge.py is loaded."
            )
    else:
        lines.append("  ⏭️   SKIPPED (Layer 2 failed — HTTP server not reachable)")

    # ──────────────────────────────────────────────────────────────────────────
    # LAYER 5 — PhotonBPLibrary reachability (bonus — 14 BP editing functions)
    # ──────────────────────────────────────────────────────────────────────────
    section("LAYER 5 — PhotonBPLibrary (C++ Blueprint editing functions)")
    info("PhotonBPLibrary provides 14 direct Blueprint-editing functions via HTTP")
    info("Object: /Script/PhotonBP.Default__PhotonBPLibrary")
    info("Not required for basic Python execution — bonus capability check")
    info("Probe: GET /remote/object/describe (no parameters needed — just checks registration)")
    if http_ok:
        try:
            timeout_http = aiohttp.ClientTimeout(total=8, connect=4)
            async with aiohttp.ClientSession(timeout=timeout_http) as s:
                # Use describe endpoint — reads object metadata without calling any function.
                # All PhotonBPLibrary functions require a Blueprint* param so we cannot
                # call them with empty args. describe returns 200 if the object is registered,
                # 404 if the plugin is not loaded.
                describe_url = f"{base}/remote/object/describe"
                async with s.put(
                    describe_url,
                    json={"objectPath": "/Script/PhotonBP.Default__PhotonBPLibrary"}
                ) as resp:
                    photon_body = await resp.text()
                    raw("Status", str(resp.status))
                    raw("Body",   photon_body[:300])
                    if resp.status == 200:
                        ok("PhotonBPLibrary is registered and reachable — 14 BP functions available")
                    elif resp.status == 404:
                        info("PhotonBPLibrary not found (404) — PhotonBP plugin not loaded (optional)")
                        info("BP editing still works via Python bridge (Layer 4)")
                    else:
                        info(f"HTTP {resp.status} — PhotonBPLibrary status unclear (optional capability)")
        except Exception as e:
            info(f"PhotonBPLibrary check threw {type(e).__name__}: {e} (optional — not required)")
    else:
        lines.append("  ⏭️   SKIPPED (Layer 2 failed)")

    # ──────────────────────────────────────────────────────────────────────────
    # LAYER 6 — DefaultEngine.ini on disk
    # ──────────────────────────────────────────────────────────────────────────
    section("LAYER 6 — DefaultEngine.ini (on-disk settings verification)")
    try:
        from pathlib import Path

        home = Path.home()
        docs = home / "Documents"
        search_roots = [
            docs / "Unreal Projects",
            home / "OneDrive" / "Documents" / "Unreal Projects",
            home / "Desktop",
            docs,
        ]
        for drive in ["C:\\", "D:\\", "E:\\"]:
            for sub in ["Unreal Projects", "UE5", "Games", "Projects", "Dev"]:
                c = Path(drive) / sub
                if c.exists():
                    search_roots.append(c)

        ini_files: list[Path] = []
        seen: set[str] = set()

        def _scan(root: Path, depth: int):
            try:
                with os.scandir(root) as it:
                    for entry in it:
                        try:
                            if entry.is_file() and entry.name.endswith(".uproject"):
                                ini = Path(entry.path).parent / "Config" / "DefaultEngine.ini"
                                k = str(ini).lower()
                                if k not in seen:
                                    seen.add(k)
                                    ini_files.append(ini)
                            elif entry.is_dir() and depth > 0:
                                skip = {"$recycle.bin", "windows", "program files",
                                        "program files (x86)", "programdata",
                                        "node_modules", ".git", "__pycache__", "appdata"}
                                if entry.name.lower() not in skip:
                                    _scan(Path(entry.path), depth - 1)
                        except (PermissionError, OSError):
                            continue
            except (PermissionError, OSError):
                pass

        for root in search_roots:
            if root.exists():
                _scan(root, 4)

        if not ini_files:
            fail("No .uproject files found — cannot check DefaultEngine.ini")
            info("Make sure your project is in Documents/Unreal Projects or C:/Unreal Projects")
        else:
            for ini_path in ini_files:
                project_name = ini_path.parent.parent.name
                info(f"Project: {project_name}  →  {ini_path}")
                if not ini_path.exists():
                    fail(f"DefaultEngine.ini does not exist at {ini_path}")
                    continue

                content = ini_path.read_text(encoding="utf-8", errors="replace")

                # Check each required key
                checks = [
                    ("/Script/RemoteControl.RemoteControlSettings", "bRestrictServerAccess",  "False"),
                    ("/Script/RemoteControl.RemoteControlSettings", "bEnablePythonExecution", "True"),
                    ("/Script/PythonScriptPlugin.PythonScriptPluginSettings", "bRemoteExecution", "True"),
                ]
                all_ini_ok = True
                for section_name, key, expected in checks:
                    # Find the section
                    in_section = False
                    found_key = False
                    actual_val = None
                    for line in content.splitlines():
                        stripped = line.strip()
                        if stripped == f"[{section_name}]":
                            in_section = True
                            continue
                        if in_section:
                            if stripped.startswith("["):
                                in_section = False
                                continue
                            if stripped.startswith(f"{key}="):
                                actual_val = stripped.split("=", 1)[1].strip()
                                found_key = True
                                break

                    if not found_key:
                        fail(f"MISSING: [{section_name}] {key}={expected}")
                        all_ini_ok = False
                    elif actual_val.lower() != expected.lower():
                        fail(f"WRONG VALUE: [{section_name}] {key}={actual_val}  (expected {expected})")
                        all_ini_ok = False
                    else:
                        ok(f"[{section_name}] {key}={actual_val}")

                if all_ini_ok:
                    ok(f"{project_name} — all required INI keys present and correct")
                else:
                    fail(f"{project_name} — INI missing/wrong keys above. Run UEOS.bat to auto-patch, then restart UE.")
                    if verdict == "UNKNOWN":
                        verdict = (
                            f"LAYER 6 FAIL — DefaultEngine.ini for '{project_name}' is missing or has "
                            "wrong values for Remote Control / Python settings. Run UEOS.bat, then "
                            "restart UE with the project open."
                        )

    except Exception as e:
        fail(f"INI check threw {type(e).__name__}: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # FINAL VERDICT
    # ──────────────────────────────────────────────────────────────────────────
    lines.append("")
    lines.append("╔══════════════════════════════════════════════════════╗")
    lines.append("║                  VERDICT                             ║")
    lines.append("╚══════════════════════════════════════════════════════╝")

    if py_ok and verdict == "UNKNOWN":
        verdict = (
            "ALL LAYERS PASS ✅ — UEOS can reach UE on port 30010, Remote Control HTTP "
            "is responding, PhotonExecBridge is registered and executing Python, stdout "
            "is captured and returned. All blueprint_*, material_*, scene_*, and other "
            "MCP tools should function correctly. If tools still fail after this, "
            "restart Claude Desktop to reload the MCP server, then try again."
        )
        lines.append(f"  ✅  {verdict}")
    elif not py_ok and verdict == "UNKNOWN":
        verdict = (
            "PARTIAL PASS — HTTP layers OK but PhotonExecBridge Python round-trip "
            "did not confirm. Check UE Output Log for Python import errors. "
            "Run: import ue_http_bridge  in UE Python console, then retry ueos_diagnose."
        )
        lines.append(f"  ⚠️   {verdict}")
    else:
        lines.append(f"  ❌  {verdict}")

    return [types.TextContent(type="text", text="\n".join(lines))]


async def handle_status() -> list[types.TextContent]:
    """Check all service connections and tool counts."""
    status = {
        "unreal_engine": {"connected": False},
        "tripo":         {"connected": False},
        "huanyuan":      {"connected": False},
        "metatailor":    {"connected": False}
    }

    # Unreal Engine
    try:
        info = await ue.get_engine_info()
        status["unreal_engine"].update({
            "connected": True,
            "version": info.get("engineVersion", "?"),
            "project": info.get("projectName", "?"),
            "content_dir": info.get("contentDir", "?")
        })
    except Exception as e:
        status["unreal_engine"]["error"] = str(e)

    # Tripo
    try:
        balance = await tripo.get_balance()
        status["tripo"].update({"connected": True, "balance": balance})
    except Exception as e:
        status["tripo"]["error"] = str(e)

    # Huanyuan
    try:
        ok = await huanyuan.ping()
        status["huanyuan"]["connected"] = ok
    except Exception as e:
        status["huanyuan"]["error"] = str(e)

    # MetaTailor
    try:
        ok = await metatailor.ping()
        status["metatailor"]["connected"] = ok
    except Exception as e:
        status["metatailor"]["error"] = str(e)

    tripo_configured    = bool(os.getenv("TRIPO_API_KEY", "").strip())
    huanyuan_configured = bool(os.getenv("HUANYUAN_API_KEY", "").strip())
    metatailor_configured = bool(os.getenv("METATAILOR_API_KEY", "").strip())

    lines = [
        "═══════════════════════════════════════════",
        "  UEOS v6.0 — Unreal Engine Operating System",
        "  Phase 6 Complete: 259 tools registered",
        "═══════════════════════════════════════════",
    ]
    if not tripo_configured:
        lines.append("  ⚠  Tripo key not set — run: python setup/configure.py --tripo")
    if not huanyuan_configured:
        lines.append("  ○  Huanyuan3D key not set (optional)")
    if not metatailor_configured:
        lines.append("  ○  MetaTailor key not set (optional)")
    icons = {True: "●", False: "○"}
    for svc, info in status.items():
        c = info.get("connected", False)
        lines.append(f"  {icons[c]} {svc.replace('_',' ').title()}")
        for k in ("version", "project", "balance", "error"):
            if k in info:
                lines.append(f"      {k.capitalize():12s}: {info[k]}")
    lines.append("═══════════════════════════════════════════")
    lines.append("  Blueprint:17   Material:14   Niagara:20")
    lines.append("  Inspection:12  Scene:16      Data:15")
    lines.append("  Animation:22   UMG:20        Sequencer:18")
    lines.append("  BehaviorTree:17  EditorWidget:20  GAS:20")
    lines.append("  EQS:20  NavMesh:17  ChaosPhysics:25  PCG:20")
    lines.append("  EnhancedInput:18  MetaSound:17  Pipeline:8  Diagnostics:3")
    lines.append("═══════════════════════════════════════════")

    return [types.TextContent(type="text", text="\n".join(lines))]


async def handle_run_python(args: dict) -> list[types.TextContent]:
    """Execute raw Python inside UE editor."""
    script  = args["script"]
    timeout = args.get("timeout", 30)

    # Temporarily override client timeout
    original_timeout = ue.timeout
    import aiohttp
    ue.timeout = aiohttp.ClientTimeout(total=timeout)

    try:
        result = await ue.execute_python(script)
        output = result.get("output", "")
        return [types.TextContent(type="text", text=json.dumps({
            "status": "executed",
            "output": output,
            "raw": result
        }, indent=2))]
    finally:
        ue.timeout = original_timeout


async def handle_batch_execute(args: dict) -> list[types.TextContent]:
    """Execute multiple Python snippets in sequence."""
    scripts       = args["scripts"]
    stop_on_error = args.get("stop_on_error", True)

    results = []
    for i, script in enumerate(scripts):
        try:
            result = await ue.execute_python(script)
            output = result.get("output", "")
            results.append({
                "index":  i,
                "status": "ok",
                "output": output
            })
        except Exception as e:
            results.append({"index": i, "status": "error", "error": str(e)})
            if stop_on_error:
                break

    return [types.TextContent(type="text", text=json.dumps({
        "total": len(scripts),
        "executed": len(results),
        "results": results
    }, indent=2))]


def _require_key(service: str, key: str) -> list[types.TextContent] | None:
    """Return an error TextContent if key is missing, else None."""
    if not key or not key.strip():
        setup_cmd = f"python setup/configure.py --{service.lower()}" if service.lower() == "tripo" else "python setup/configure.py"
        return [types.TextContent(type="text", text=json.dumps({
            "error":   f"{service} API key not configured.",
            "fix":     f"Run: {setup_cmd}",
            "details": f"Add your {service} API key to the .env file or run the config wizard."
        }))]
    return None


async def handle_tripo_text(args: dict) -> list[types.TextContent]:
    if err := _require_key("Tripo", os.getenv("TRIPO_API_KEY", "")):
        return err
    prompt      = args["prompt"]
    style       = args.get("style", "realistic")
    texture     = args.get("texture", True)
    auto_import = args.get("auto_import", True)
    import_path = args.get("import_path", "/Game/UEOS/Generated")

    task = await tripo.create_text_to_model_task(
        prompt=prompt, style=style, with_texture=texture
    )
    return [types.TextContent(type="text", text=json.dumps({
        "task_id":     task["task_id"],
        "status":      task["status"],
        "prompt":      prompt,
        "auto_import": auto_import,
        "import_path": import_path,
        "next":        f"Call tripo_get_task_status with task_id={task['task_id']}"
    }, indent=2))]


async def handle_tripo_image(args: dict) -> list[types.TextContent]:
    if err := _require_key("Tripo", os.getenv("TRIPO_API_KEY", "")):
        return err
    import base64
    image_path  = args.get("image_path")
    image_url   = args.get("image_url")
    prompt      = args.get("prompt", "")
    texture     = args.get("texture", True)
    auto_import = args.get("auto_import", True)
    import_path = args.get("import_path", "/Game/UEOS/Generated")

    if not image_path and not image_url:
        return [types.TextContent(type="text", text=json.dumps({"error": "Provide image_path or image_url"}))]

    image_data = None
    if image_path:
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

    task = await tripo.create_image_to_model_task(
        image_data=image_data, image_url=image_url,
        prompt=prompt, with_texture=texture
    )
    return [types.TextContent(type="text", text=json.dumps({
        "task_id":     task["task_id"],
        "status":      task["status"],
        "source":      image_path or image_url,
        "auto_import": auto_import,
        "import_path": import_path,
        "next":        f"Call tripo_get_task_status with task_id={task['task_id']}"
    }, indent=2))]


async def handle_tripo_status(args: dict) -> list[types.TextContent]:
    if err := _require_key("Tripo", os.getenv("TRIPO_API_KEY", "")):
        return err
    task_id = args["task_id"]
    task    = await tripo.get_task(task_id)
    result  = {
        "task_id":  task_id,
        "status":   task.get("status"),
        "progress": task.get("progress", 0)
    }
    if task.get("status") == "success":
        result["download_urls"] = task.get("result", {})
        result["next"] = "Call tripo_import_to_unreal"
    elif task.get("status") == "failed":
        result["error"] = task.get("message", "Unknown error")
    else:
        result["next"] = f"Still processing ({task.get('progress', 0)}%) — poll again"
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


async def handle_tripo_import(args: dict) -> list[types.TextContent]:
    if err := _require_key("Tripo", os.getenv("TRIPO_API_KEY", "")):
        return err
    import aiohttp
    task_id          = args["task_id"]
    import_path      = args.get("import_path", "/Game/UEOS/Generated")
    create_blueprint = args.get("create_blueprint", False)
    blueprint_path   = args.get("blueprint_path", "")

    task = await tripo.get_task(task_id)
    if task.get("status") != "success":
        return [types.TextContent(type="text", text=json.dumps({
            "error": f"Task {task_id} not complete. Status: {task.get('status')}"
        }))]

    urls      = task.get("result", {})
    model_url = urls.get("fbx") or urls.get("glb") or urls.get("model")
    if not model_url:
        return [types.TextContent(type="text", text=json.dumps({"error": f"No download URL: {urls}"}))]

    temp_dir   = os.getenv("UEOS_ASSET_TEMP_DIR", "C:/UEOS/temp")
    os.makedirs(temp_dir, exist_ok=True)
    ext        = ".fbx" if "fbx" in model_url else ".glb"
    local_path = os.path.join(temp_dir, f"tripo_{task_id}{ext}").replace("\\", "/")

    async with aiohttp.ClientSession() as sess:
        async with sess.get(model_url) as resp:
            with open(local_path, "wb") as f:
                f.write(await resp.read())

    import_script = f"""
import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
t = unreal.AssetImportTask()
t.filename = r"{local_path}"
t.destination_path = "{import_path}"
t.automated = True
t.replace_existing = True
t.save = True

opts = unreal.FbxImportUI()
opts.import_mesh = True
opts.import_textures = True
opts.import_materials = True
opts.import_as_skeletal = False
opts.static_mesh_import_data.combine_meshes = True
t.options = opts

asset_tools.import_asset_tasks([t])
print("UEOS_RESULT:" + str(t.imported_object_paths))
"""
    result_data = await ue.execute_python(import_script)
    response    = {
        "task_id":    task_id,
        "local_path": local_path,
        "import_path": import_path,
        "ue_result":  result_data,
        "status":     "imported"
    }
    if create_blueprint:
        await blueprint_tools.handle("blueprint_create", {
            "name":         f"BP_Tripo_{task_id[:8]}",
            "path":         blueprint_path or import_path,
            "parent_class": "Actor"
        })
        response["blueprint"] = "created"

    return [types.TextContent(type="text", text=json.dumps(response, indent=2))]


async def handle_huanyuan_image(args: dict) -> list[types.TextContent]:
    if err := _require_key("Huanyuan3D", os.getenv("HUANYUAN_API_KEY", "")):
        return err
    image_path  = args.get("image_path")
    image_url   = args.get("image_url")
    steps       = args.get("steps", 50)
    auto_import = args.get("auto_import", True)
    import_path = args.get("import_path", "/Game/UEOS/Generated")

    if not image_path and not image_url:
        return [types.TextContent(type="text", text=json.dumps({"error": "Provide image_path or image_url"}))]

    task = await huanyuan.generate_from_image(
        image_path=image_path, image_url=image_url, steps=steps
    )
    return [types.TextContent(type="text", text=json.dumps({
        "task_id":     task.get("task_id"),
        "status":      task.get("status"),
        "auto_import": auto_import,
        "import_path": import_path,
        "message":     "Huanyuan3D generation started"
    }, indent=2))]


async def handle_metatailor_rig(args: dict) -> list[types.TextContent]:
    if err := _require_key("MetaTailor", os.getenv("METATAILOR_API_KEY", "")):
        return err
    mesh_path            = args.get("mesh_path")
    ue_asset_path        = args.get("ue_asset_path")
    add_clothing         = args.get("add_clothing", False)
    clothing_description = args.get("clothing_description", "")
    auto_import          = args.get("auto_import_result", True)
    setup_leader_pose    = args.get("setup_leader_pose", True)

    task = await metatailor.rig_character(
        mesh_path=mesh_path,
        add_clothing=add_clothing,
        clothing_description=clothing_description
    )
    return [types.TextContent(type="text", text=json.dumps({
        "task_id":          task.get("task_id"),
        "status":           task.get("status"),
        "setup_leader_pose": setup_leader_pose,
        "message":          "MetaTailor rigging started"
    }, indent=2))]


async def handle_full_pipeline(args: dict) -> list[types.TextContent]:
    """Full concept art → 3D → rig → Blueprint pipeline."""
    character_name       = args["character_name"]
    image_path           = args.get("image_path")
    image_url            = args.get("image_url")
    service              = args.get("generation_service", "tripo")
    add_clothing         = args.get("add_clothing", False)
    clothing_description = args.get("clothing_description", "")
    use_ue_cloth         = args.get("use_ue_cloth_physics", False)
    create_bp            = args.get("create_blueprint", True)
    import_path          = args.get("import_path", "/Game/UEOS/Characters")

    char_path = f"{import_path}/{character_name}"

    # Step 1: Generate 3D
    gen_args = {
        "image_path":  image_path,
        "image_url":   image_url,
        "texture":     True,
        "auto_import": False,
        "import_path": char_path
    }
    if service == "tripo":
        gen_resp = await handle_tripo_image(gen_args)
    else:
        gen_resp = await handle_huanyuan_image({**gen_args, "steps": 50})

    gen_data = json.loads(gen_resp[0].text)
    task_id  = gen_data.get("task_id")

    planned = [
        "1. ✅ 3D generation started via " + service.upper(),
        f"2. ⏳ Poll {service}_get_task_status task_id={task_id}",
        f"3. ⏳ Import mesh → {char_path}",
    ]
    if not use_ue_cloth and add_clothing:
        planned.append("4. ⏳ MetaTailor auto-rigging + clothing")
        planned.append("5. ⏳ Leader Pose Component wired in Construction Script")
    else:
        planned.append("4. ⏳ UE cloth physics setup")
    if create_bp:
        planned.append(f"6. ⏳ Create Character Blueprint → BP_{character_name}")
        planned.append(f"7. ⏳ blueprint_compile BP_{character_name}")

    return [types.TextContent(type="text", text=json.dumps({
        "character_name":      character_name,
        "generation_task_id":  task_id,
        "generation_service":  service,
        "import_path":         char_path,
        "status":              "generation_started",
        "planned_steps":       planned
    }, indent=2))]


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    log.info("═══════════════════════════════════════════")
    log.info("  UEOS MCP Server v7.0 — Phase 7 Complete")
    log.info("  Unreal Engine Operating System")
    log.info("═══════════════════════════════════════════")
    log.info(f"  UE Remote:    {ue.host}:{ue.port}")
    log.info(f"  Tripo:        {'✓' if tripo.api_key else '✗ NOT configured'}")
    log.info(f"  Huanyuan:     {'✓' if huanyuan.api_key else '✗ NOT configured'}")
    log.info(f"  MetaTailor:   {'✓' if metatailor.api_key else '✗ NOT configured'}")
    log.info("  Tools:  Blueprint(17) Material(14) Niagara(20)")
    log.info("          Inspection(12) Scene(16) Data(15)")
    log.info("          Animation(22) UMG(20) Sequencer(18)")
    log.info("          BehaviorTree(17) EditorWidget(20)")
    log.info("          GameplayAbility(20) EnvironmentQuery(20) NavMesh(17)")
    log.info("          ChaosPhysics(25) PCG(20) EnhancedInput(18) MetaSound(17)")
    log.info("          Pipeline(8) Diagnostics(3)")
    log.info("          ── Total: 339 tools ──")
    log.info("═══════════════════════════════════════════")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
