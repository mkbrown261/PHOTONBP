"""
bridge_server.py — UEOS Universal AI Bridge
Exposes all 339 UEOS tools via a local HTTP server that any AI platform
can call using standard OpenAI function-calling format.

Runs on http://localhost:8080 alongside the MCP server (port stays separate).

Endpoints:
  GET  /                      → health check + tool count
  GET  /tools                 → full OpenAI function schema (JSON array)
  GET  /openapi.json          → OpenAPI 3.1 spec (for ChatGPT Actions import)
  POST /call                  → execute a tool  { "tool": "...", "args": {...} }
  GET  /system-prompt         → copy-paste system prompt for any AI
  GET  /status                → UE connection + tool count status

Usage:
  python mcp_server/bridge_server.py
  python mcp_server/bridge_server.py --port 8080  (default)
  python mcp_server/bridge_server.py --host 0.0.0.0  (expose on LAN)
"""

from __future__ import annotations
import sys
import os
import asyncio
import logging
import argparse
import json
import time
import urllib.request
from pathlib import Path
from typing import Any

# ── Path setup ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "mcp_server"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# ── FastAPI ───────────────────────────────────────────────────────────────────
try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse, PlainTextResponse
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
except ImportError:
    print("ERROR: FastAPI not installed.")
    print("Run:  pip install fastapi uvicorn")
    sys.exit(1)

# ── UEOS internals ────────────────────────────────────────────────────────────
from remote_control.client import UnrealRemoteControl
from tools.schema_export import get_openai_schema_cached, _collect_all_tool_definitions, mcp_tool_to_openai

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  BRIDGE  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ueos.bridge")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="UEOS — Universal AI Bridge",
    description="Control Unreal Engine 5.4 from any AI platform. 339 tools available.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # local only in practice; user can lock this down
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── UE client + tool registry (built once on startup) ────────────────────────
_ue: UnrealRemoteControl | None = None
_tool_handlers: dict[str, Any] = {}   # tool_name → tool class instance
_mcp_tools:     list[Any]      = []   # mcp.types.Tool objects
_start_time = time.time()


async def _build_registry():
    """Import all tool classes, build name→handler map."""
    global _ue, _tool_handlers, _mcp_tools

    _ue = UnrealRemoteControl(
        host=os.getenv("UE_REMOTE_CONTROL_HOST", "127.0.0.1"),
        port=int(os.getenv("UE_REMOTE_CONTROL_PORT", 30010)),
    )

    from tools.blueprint        import BlueprintTools
    from tools.material         import MaterialTools
    from tools.niagara          import NiagaraTools
    from tools.inspection       import InspectionTools
    from tools.scene            import SceneTools
    from tools.data             import DataTools
    from tools.animation        import AnimationTools
    from tools.umg              import UMGTools
    from tools.sequencer        import SequencerTools
    from tools.behavior_tree    import BehaviorTreeTools
    from tools.editor_widget    import EditorWidgetTools
    from tools.gameplay_ability import GameplayAbilityTools
    from tools.environment_query import EnvironmentQueryTools
    from tools.navmesh          import NavMeshTools
    from tools.chaos_physics    import ChaosPhysicsTools
    from tools.pcg              import PCGTools
    from tools.enhanced_input   import EnhancedInputTools
    from tools.metasound        import MetaSoundTools

    instances = [
        BlueprintTools(_ue),
        MaterialTools(_ue),
        NiagaraTools(_ue),
        InspectionTools(_ue),
        SceneTools(_ue),
        DataTools(_ue),
        AnimationTools(_ue),
        UMGTools(_ue),
        SequencerTools(_ue),
        BehaviorTreeTools(_ue),
        EditorWidgetTools(_ue),
        GameplayAbilityTools(_ue),
        EnvironmentQueryTools(_ue),
        NavMeshTools(_ue),
        ChaosPhysicsTools(_ue),
        PCGTools(_ue),
        EnhancedInputTools(_ue),
        MetaSoundTools(_ue),
    ]

    for inst in instances:
        defs = await inst.get_tool_definitions()
        _mcp_tools.extend(defs)
        for tool_def in defs:
            _tool_handlers[tool_def.name] = inst

    log.info(f"Bridge ready — {len(_mcp_tools)} tools registered")


@app.on_event("startup")
async def on_startup():
    await _build_registry()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=JSONResponse)
async def root():
    uptime = int(time.time() - _start_time)
    return {
        "service":    "UEOS Universal AI Bridge",
        "version":    "1.0.0",
        "tools":      len(_mcp_tools),
        "uptime_sec": uptime,
        "endpoints": {
            "tool_schema":    "GET /tools",
            "execute_tool":   "POST /call",
            "openapi_spec":   "GET /openapi.json",
            "system_prompt":  "GET /system-prompt",
            "status":         "GET /status",
            "interactive_docs": "GET /docs",
        },
    }


@app.get("/tools", response_class=JSONResponse)
async def get_tools():
    """
    Returns all UEOS tools in OpenAI function-calling format.
    Paste this URL into any AI platform that supports tool/function calling.
    """
    return [mcp_tool_to_openai(t) for t in _mcp_tools]


@app.get("/status", response_class=JSONResponse)
async def get_status():
    """Check UE connection and bridge health."""
    ue_ok = False
    ue_msg = "Not connected"
    try:
        payload = json.dumps({
            "objectPath": "/Script/PythonScriptPlugin.Default__PythonScriptLibrary",
            "functionName": "ExecutePythonScript",
            "parameters": {"PythonScript": "print('UEOS_PING:OK')"},
        }).encode()
        req = urllib.request.Request(
            f"http://{os.getenv('UE_REMOTE_CONTROL_HOST','127.0.0.1')}:{os.getenv('UE_REMOTE_CONTROL_PORT',30010)}/remote/object/call",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=4):
            ue_ok  = True
            ue_msg = "Connected"
    except Exception as e:
        ue_msg = f"Not reachable — start UE 5.4 with Remote Control API plugin enabled"

    return {
        "bridge":       "running",
        "tools":        len(_mcp_tools),
        "ue_connected": ue_ok,
        "ue_status":    ue_msg,
        "uptime_sec":   int(time.time() - _start_time),
    }


@app.post("/call", response_class=JSONResponse)
async def call_tool(request: Request):
    """
    Execute a UEOS tool.

    Body: { "tool": "blueprint_create", "args": { "name": "BP_Hero", "path": "/Game/Characters" } }
    Returns: { "success": true, "result": "..." }
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    tool_name = body.get("tool") or body.get("name") or body.get("function")
    args      = body.get("args") or body.get("arguments") or body.get("parameters") or {}

    if not tool_name:
        raise HTTPException(status_code=400, detail="Missing 'tool' field. Body: { \"tool\": \"tool_name\", \"args\": {...} }")

    handler = _tool_handlers.get(tool_name)
    if handler is None:
        available = sorted(_tool_handlers.keys())[:10]
        raise HTTPException(
            status_code=404,
            detail=f"Unknown tool '{tool_name}'. First 10 available: {available}"
        )

    try:
        result_contents = await handler.handle(tool_name, args)
        # result_contents is a list of mcp.types.TextContent
        result_text = "\n".join(
            c.text if hasattr(c, "text") else str(c)
            for c in result_contents
        )
        return {"success": True, "tool": tool_name, "result": result_text}
    except Exception as e:
        log.error(f"Tool '{tool_name}' error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Tool execution error: {e}")


@app.get("/openapi.json", response_class=JSONResponse)
async def openapi_spec():
    """
    OpenAPI 3.1 spec — import this URL directly into ChatGPT Actions
    or any platform that accepts OpenAPI specs.
    """
    tools = [mcp_tool_to_openai(t) for t in _mcp_tools]

    # Build OpenAPI paths from tools
    paths = {}
    for tool in tools:
        fn     = tool["function"]
        path   = f"/call/{fn['name']}"
        paths[path] = {
            "post": {
                "operationId": fn["name"],
                "summary":     fn["description"][:120] if fn["description"] else fn["name"],
                "description": fn["description"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": fn["parameters"]
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Tool executed successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean"},
                                        "result":  {"type": "string"},
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

    return {
        "openapi": "3.1.0",
        "info": {
            "title":       "UEOS — Universal AI Bridge",
            "description": f"Control Unreal Engine 5.4 with any AI. {len(_mcp_tools)} tools available.",
            "version":     "1.0.0",
        },
        "servers": [{"url": "http://localhost:8080"}],
        "paths": paths,
    }


@app.get("/system-prompt", response_class=PlainTextResponse)
async def system_prompt():
    """
    Returns a ready-to-paste system prompt for any AI.
    The prompt tells the AI it has access to UEOS tools and how to use them.
    """
    tool_names_sample = [t.name for t in _mcp_tools[:20]]
    prompt = f"""You are an Unreal Engine 5.4 development assistant with access to UEOS — the Unreal Engine Operating System.

You can control the UE editor directly by calling UEOS tools via HTTP POST to http://localhost:8080/call

To call a tool:
POST http://localhost:8080/call
{{ "tool": "tool_name", "args": {{ ...parameters... }} }}

You have {len(_mcp_tools)} tools available covering:
- Blueprint creation and editing (blueprint_*)
- Materials and shaders (material_*)
- Niagara particle systems (niagara_*)
- Scene management — lights, fog, cameras (scene_*)
- Data assets — Structs, Enums, DataTables (data_*)
- Animation — AnimBP, State Machines, Montages (animation_*)
- UI/UMG widgets and HUDs (umg_*)
- Level Sequences and cinematics (sequencer_*)
- Behavior Trees and AI (bt_*)
- Gameplay Ability System (gas_*)
- Environment Query System (eqs_*)
- NavMesh and AI navigation (nav_*)
- Chaos Physics and destruction (phys_*)
- Procedural Content Generation (pcg_*)
- Enhanced Input system (inp_*)
- MetaSound audio (snd_*)
- Editor Utility Widgets (ew_*)
- Asset inspection (inspect_*)
- Pipeline — 3D generation, rigging (tripo_*, pipeline_*)

Sample tool names: {', '.join(tool_names_sample)}

Always check /status first to confirm UE is connected.
When the user asks you to do something in Unreal Engine, call the appropriate tool directly.
Return the result clearly. If a tool fails, explain why and suggest fixes.
"""
    return prompt


# ── Per-tool shortcut routes ──────────────────────────────────────────────────
# Allow POST /call/{tool_name} with just the args as the body
# so platforms like ChatGPT Actions can call individual endpoints

@app.post("/call/{tool_name}", response_class=JSONResponse)
async def call_tool_by_path(tool_name: str, request: Request):
    """Execute tool by path — body is just the args dict."""
    try:
        args = await request.json()
    except Exception:
        args = {}

    handler = _tool_handlers.get(tool_name)
    if handler is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool '{tool_name}'")

    try:
        result_contents = await handler.handle(tool_name, args)
        result_text = "\n".join(
            c.text if hasattr(c, "text") else str(c)
            for c in result_contents
        )
        return {"success": True, "tool": tool_name, "result": result_text}
    except Exception as e:
        log.error(f"Tool '{tool_name}' error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Tool execution error: {e}")


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="UEOS Universal AI Bridge")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Host to bind to (default: 127.0.0.1 — localhost only)")
    parser.add_argument("--port", type=int, default=8080,
                        help="Port to listen on (default: 8080)")
    parser.add_argument("--log-level", default="info",
                        choices=["debug", "info", "warning", "error"])
    args = parser.parse_args()

    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║     UEOS — Universal AI Bridge               ║")
    print("  ║     Any AI → Unreal Engine 5.4               ║")
    print("  ╚══════════════════════════════════════════════╝")
    print()
    print(f"  Bridge URL  :  http://{args.host}:{args.port}")
    print(f"  Tool schema :  http://{args.host}:{args.port}/tools")
    print(f"  System prompt: http://{args.host}:{args.port}/system-prompt")
    print(f"  OpenAPI spec:  http://{args.host}:{args.port}/openapi.json")
    print(f"  Interactive :  http://{args.host}:{args.port}/docs")
    print()

    uvicorn.run(
        "bridge_server:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=False,
    )


if __name__ == "__main__":
    main()
