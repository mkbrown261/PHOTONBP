#!/usr/bin/env python3
"""
inject_claude_config.py
Writes the correct UEOS MCP entry into claude_desktop_config.json.

Uses paths relative to THIS FILE's location so it always resolves
correctly no matter which machine it runs on — no hardcoded paths.

Exit codes:
  0 — written successfully
  1 — Claude Desktop not found / error
  2 — already configured and correct (no change needed)
"""

import json
import sys
import os
from pathlib import Path

# ── Resolve paths from THIS file's real location on disk ──────────────────────
# inject_claude_config.py lives at:  <ueos_root>/setup/inject_claude_config.py
# So ROOT is always two levels up from this file, regardless of OS or username.
THIS_FILE  = Path(__file__).resolve()
SETUP_DIR  = THIS_FILE.parent          # <ueos_root>/setup/
ROOT       = SETUP_DIR.parent          # <ueos_root>/
SERVER_PY  = ROOT / "mcp_server" / "server.py"
MCP_CWD    = ROOT / "mcp_server"

# On Windows we want "python" (uses PATH), not sys.executable which might
# be the sandbox's Linux python when this script is edited remotely.
# But if this script is actually running on the user's machine, sys.executable
# IS the right python — so we use it, since it will be a Windows path.
PYTHON_CMD = sys.executable

CLAUDE_CONFIGS = [
    Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json",   # Windows
    Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",  # macOS
    Path.home() / ".config" / "Claude" / "claude_desktop_config.json",               # Linux
]


def find_claude_config() -> Path | None:
    # First: find an existing file
    for p in CLAUDE_CONFIGS:
        if p.exists():
            return p
    # Second: find a directory that exists (Claude installed but config not yet created)
    for p in CLAUDE_CONFIGS:
        if p.parent.exists():
            return p
    return None


def main() -> int:
    config_path = find_claude_config()

    if config_path is None:
        print("  Claude Desktop not found (no config directory).", file=sys.stderr)
        return 1

    # Build the MCP entry using paths relative to THIS file
    mcp_entry = {
        "command": PYTHON_CMD,
        "args":    [str(SERVER_PY)],
        "cwd":     str(MCP_CWD),
    }

    # Read existing config
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    # Check if already correct
    existing_entry = data.get("mcpServers", {}).get("ueos", {})
    if (existing_entry.get("command") == mcp_entry["command"] and
            existing_entry.get("args")    == mcp_entry["args"] and
            existing_entry.get("cwd")     == mcp_entry["cwd"]):
        return 2  # already correct, no change needed

    # Inject / overwrite
    data.setdefault("mcpServers", {})
    data["mcpServers"]["ueos"] = mcp_entry

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"  Written to: {config_path}", flush=True)
        print(f"  command:    {PYTHON_CMD}", flush=True)
        print(f"  server.py:  {SERVER_PY}", flush=True)
        return 0
    except Exception as e:
        print(f"  Error writing config: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
