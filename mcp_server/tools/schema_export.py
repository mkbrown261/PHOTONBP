"""
schema_export.py — UEOS Tool Schema Exporter
Converts MCP types.Tool definitions into OpenAI-compatible function-calling
JSON schema. Used by bridge_server.py to serve any AI platform.

The MCP types.Tool format:
    types.Tool(name=..., description=..., inputSchema={...})

The OpenAI function schema format:
    {
        "type": "function",
        "function": {
            "name": ...,
            "description": ...,
            "parameters": { "type": "object", "properties": {...}, "required": [...] }
        }
    }

They map 1:1 — inputSchema IS the parameters object.
"""

from __future__ import annotations
import sys
import os
import asyncio
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("ueos.schema_export")

# Add parent dir so we can import the tool modules
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "mcp_server"))


async def _collect_all_tool_definitions() -> list[Any]:
    """
    Instantiate every tool class with a dummy UE handle and collect
    all tool definitions. Returns a flat list of mcp.types.Tool objects.
    """
    from mcp import types

    # Dummy UE client — schema export never calls UE
    class _DummyUE:
        async def execute_python_ex(self, *a, **kw):
            return "UEOS_RESULT: {}"

    ue = _DummyUE()

    # Import all tool modules (same list as server.py)
    from tools.blueprint       import BlueprintTools
    from tools.material        import MaterialTools
    from tools.niagara         import NiagaraTools
    from tools.inspection      import InspectionTools
    from tools.scene           import SceneTools
    from tools.data            import DataTools
    from tools.animation       import AnimationTools
    from tools.umg             import UMGTools
    from tools.sequencer       import SequencerTools
    from tools.behavior_tree   import BehaviorTreeTools
    from tools.editor_widget   import EditorWidgetTools
    from tools.gameplay_ability import GameplayAbilityTools
    from tools.environment_query import EnvironmentQueryTools
    from tools.navmesh         import NavMeshTools
    from tools.chaos_physics   import ChaosPhysicsTools
    from tools.pcg             import PCGTools
    from tools.enhanced_input  import EnhancedInputTools
    from tools.metasound       import MetaSoundTools

    instances = [
        BlueprintTools(ue),
        MaterialTools(ue),
        NiagaraTools(ue),
        InspectionTools(ue),
        SceneTools(ue),
        DataTools(ue),
        AnimationTools(ue),
        UMGTools(ue),
        SequencerTools(ue),
        BehaviorTreeTools(ue),
        EditorWidgetTools(ue),
        GameplayAbilityTools(ue),
        EnvironmentQueryTools(ue),
        NavMeshTools(ue),
        ChaosPhysicsTools(ue),
        PCGTools(ue),
        EnhancedInputTools(ue),
        MetaSoundTools(ue),
    ]

    all_tools = []
    for inst in instances:
        defs = await inst.get_tool_definitions()
        all_tools.extend(defs)

    return all_tools


def mcp_tool_to_openai(tool: Any) -> dict:
    """
    Convert a single mcp.types.Tool → OpenAI function schema dict.
    """
    # inputSchema is already a JSON-Schema-compatible dict
    params = dict(tool.inputSchema) if tool.inputSchema else {"type": "object", "properties": {}}
    # Ensure required field exists
    if "required" not in params:
        params["required"] = []

    return {
        "type": "function",
        "function": {
            "name":        tool.name,
            "description": (tool.description or "").strip(),
            "parameters":  params,
        },
    }


def get_openai_schema_sync() -> list[dict]:
    """
    Synchronous wrapper — returns the full OpenAI-format tool list.
    Safe to call from any context (creates its own event loop if needed).
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _collect_all_tool_definitions())
                mcp_tools = future.result(timeout=30)
        else:
            mcp_tools = loop.run_until_complete(_collect_all_tool_definitions())
    except RuntimeError:
        mcp_tools = asyncio.run(_collect_all_tool_definitions())

    return [mcp_tool_to_openai(t) for t in mcp_tools]


# Cache so we only build it once per process lifetime
_SCHEMA_CACHE: list[dict] | None = None

def get_openai_schema_cached() -> list[dict]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        _SCHEMA_CACHE = get_openai_schema_sync()
        log.info(f"Schema export: {len(_SCHEMA_CACHE)} tools cached")
    return _SCHEMA_CACHE


if __name__ == "__main__":
    import json
    schema = get_openai_schema_sync()
    print(f"Exported {len(schema)} tools")
    print(json.dumps(schema[:2], indent=2))
