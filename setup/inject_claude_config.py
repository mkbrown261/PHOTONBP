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

def _get_claude_configs() -> list[Path]:
    """
    Return all possible claude_desktop_config.json locations.
    Includes Microsoft Store version (LocalCache path) and direct install (Roaming path).
    """
    configs = []

    # Windows — direct install (Roaming)
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        configs.append(Path(appdata) / "Claude" / "claude_desktop_config.json")

    # Windows — Microsoft Store install (LocalCache inside Packages)
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if localappdata:
        packages_dir = Path(localappdata) / "Packages"
        if packages_dir.exists():
            try:
                for entry in packages_dir.iterdir():
                    if entry.is_dir() and entry.name.lower().startswith("claude_"):
                        configs.append(
                            entry / "LocalCache" / "Roaming" / "Claude" / "claude_desktop_config.json"
                        )
            except (PermissionError, OSError):
                pass

    # macOS
    configs.append(
        Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    )

    # Linux
    configs.append(Path.home() / ".config" / "Claude" / "claude_desktop_config.json")

    return configs


def find_claude_config() -> Path | None:
    configs = _get_claude_configs()
    # First: find an existing file
    for p in configs:
        if p.exists():
            return p
    # Second: find a directory that exists (Claude installed but config not yet created)
    for p in configs:
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
