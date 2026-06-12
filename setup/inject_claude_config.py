#!/usr/bin/env python3
"""
inject_claude_config.py
Called by SETUP.bat to safely inject the UEOS MCP entry into
claude_desktop_config.json.

Exit codes:
  0 — written successfully
  1 — Claude Desktop not found / error
  2 — already configured (no change needed)
"""

import json
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
SERVER_PY = ROOT / "mcp_server" / "server.py"

CLAUDE_CONFIGS = [
    Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json",
    Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
    Path.home() / ".config" / "Claude" / "claude_desktop_config.json",
]

def find_claude_config() -> Path | None:
    for p in CLAUDE_CONFIGS:
        if p.exists():
            return p
    # Return platform default path even if it doesn't exist yet
    # so we can create it — but only if the parent dir exists
    # (meaning Claude Desktop was installed)
    for p in CLAUDE_CONFIGS:
        if p.parent.exists():
            return p
    return None

def main() -> int:
    config_path = find_claude_config()

    if config_path is None:
        # Claude Desktop directory doesn't exist at all
        return 1

    # Build the MCP entry
    mcp_entry = {
        "command": sys.executable,
        "args": [str(SERVER_PY)],
        "cwd": str(SERVER_PY.parent),
    }

    # Read existing config (or start fresh)
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    # Check if already configured
    if "mcpServers" in data and "ueos" in data["mcpServers"]:
        existing = data["mcpServers"]["ueos"]
        if existing.get("args") == mcp_entry["args"]:
            # Already correct — no change needed
            return 2

    # Inject
    if "mcpServers" not in data:
        data["mcpServers"] = {}
    data["mcpServers"]["ueos"] = mcp_entry

    # Write back
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return 0
    except Exception as e:
        print(f"  Error writing config: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
