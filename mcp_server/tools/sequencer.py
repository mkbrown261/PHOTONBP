"""
UEOS Sequencer Tools - Phase 2+
Full implementation coming in next build phase.
"""
import json
import logging
from mcp import types

log = logging.getLogger("ueos.sequencer")


class SequencerTools:
    def __init__(self, ue):
        self.ue = ue

    async def get_tool_definitions(self) -> list[types.Tool]:
        return []

    async def handle(self, name: str, args: dict) -> list[types.TextContent]:
        return [types.TextContent(type="text", text=json.dumps({"status": "coming_soon", "tool": name, "phase": "Phase 2+"}))]
