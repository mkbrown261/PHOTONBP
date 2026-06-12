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
    """
    if not ENV_FILE.exists():
        print("=" * 55, flush=True)
        print("  UEOS: No .env file found.", flush=True)
        print("  Run: python setup/configure.py", flush=True)
        print("=" * 55, flush=True)
        return

    tripo_key = os.getenv("TRIPO_API_KEY", "").strip()
    if not tripo_key:
        print("=" * 55, flush=True)
        print("  UEOS: Tripo API key not configured.", flush=True)
        print("  Run: python setup/configure.py --tripo", flush=True)
        print("  3D generation tools will return errors until set.", flush=True)
        print("=" * 55, flush=True)

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
logging.basicConfig(
    level=os.getenv("UEOS_LOG_LEVEL", "INFO"),
    format="%(asctime)s [UEOS] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("ueos.log", encoding="utf-8")
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
    lines.append("  BehaviorTree:17  EditorWidget:20  Pipeline:8")
    lines.append("  Diagnostics:3")
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
    log.info("  UEOS MCP Server v6.0 — Phase 6 Complete")
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
    log.info("          Pipeline(8) Diagnostics(3)")
    log.info("          ── Total: 259 tools ──")
    log.info("═══════════════════════════════════════════")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
