#!/usr/bin/env python3
"""
UEOS Configuration Wizard
Run this to set up your API keys and settings interactively.

Usage:
    python setup/configure.py          # full setup
    python setup/configure.py --tripo  # update Tripo key only
    python setup/configure.py --reset  # wipe and start fresh
"""

import os
import sys
import argparse
import shutil
import asyncio
import urllib.request
import urllib.error
import json
from pathlib import Path

ROOT    = Path(__file__).parent.parent
ENV     = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"

# ─────────────────────────────────────────────────────────────────────────────
# Terminal colors (work on Windows 10+/11 with ANSI enabled)
# ─────────────────────────────────────────────────────────────────────────────

def _ansi(code): return f"\033[{code}m"
RESET  = _ansi(0)
BOLD   = _ansi(1)
GREEN  = _ansi(32)
YELLOW = _ansi(33)
RED    = _ansi(31)
CYAN   = _ansi(36)
DIM    = _ansi(2)

def ok(msg):    print(f"  {GREEN}✓{RESET} {msg}")
def err(msg):   print(f"  {RED}✗{RESET} {msg}")
def warn(msg):  print(f"  {YELLOW}!{RESET} {msg}")
def info(msg):  print(f"  {CYAN}→{RESET} {msg}")
def header(msg):
    print()
    print(f"{BOLD}{CYAN}{'═'*50}{RESET}")
    print(f"{BOLD}{CYAN}  {msg}{RESET}")
    print(f"{BOLD}{CYAN}{'═'*50}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# .env reader / writer
# ─────────────────────────────────────────────────────────────────────────────

def read_env() -> dict:
    """Read current .env into a dict."""
    values = {}
    if not ENV.exists():
        return values
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            values[k.strip()] = v.strip()
    return values

def write_env(values: dict):
    """Write dict back to .env, preserving comments from .env.example."""
    # Start from the example template to keep comments/structure
    template = EXAMPLE.read_text(encoding="utf-8") if EXAMPLE.exists() else ""
    lines = []
    written = set()

    for line in template.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            lines.append(line)
        elif "=" in stripped:
            k, _, _ = stripped.partition("=")
            k = k.strip()
            written.add(k)
            v = values.get(k, "")
            lines.append(f"{k}={v}")
        else:
            lines.append(line)

    # Append any keys in values not in template
    for k, v in values.items():
        if k not in written:
            lines.append(f"{k}={v}")

    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")

def update_env_key(key: str, value: str):
    """Update a single key in .env without touching the rest."""
    values = read_env()
    values[key] = value
    write_env(values)


# ─────────────────────────────────────────────────────────────────────────────
# API key validators
# ─────────────────────────────────────────────────────────────────────────────

def validate_tripo_key(key: str) -> tuple[bool, str]:
    """Hit Tripo balance endpoint to verify key."""
    if not key or not key.startswith("tsk_"):
        return False, "Tripo keys start with 'tsk_' — check your key"
    try:
        req = urllib.request.Request(
            "https://api.tripo3d.ai/v2/openapi/user/balance",
            headers={"Authorization": f"Bearer {key}"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
            balance = data.get("data", {}).get("balance", "?")
            return True, f"Valid ✓  Balance: {balance} credits"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Invalid key — Tripo returned 401 Unauthorized"
        return False, f"Tripo API error {e.code}"
    except Exception as e:
        return False, f"Could not reach Tripo API: {e}"

def validate_ue_connection(host: str, port: int) -> tuple[bool, str]:
    """Check if UE Remote Control is reachable."""
    try:
        payload = json.dumps({
            "objectPath": "/Script/PythonScriptPlugin.Default__PythonScriptLibrary",
            "functionName": "ExecutePythonScript",
            "parameters": {"PythonScript": "import unreal; print('UEOS_PING:OK')"}
        }).encode()
        req = urllib.request.Request(
            f"http://{host}:{port}/remote/object/call",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="PUT"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return True, f"Connected — UE Remote Control at {host}:{port}"
    except Exception as e:
        return False, f"UE not reachable at {host}:{port} — start UE 5.4 first"


# ─────────────────────────────────────────────────────────────────────────────
# Prompt helpers
# ─────────────────────────────────────────────────────────────────────────────

def prompt(label: str, current: str = "", secret: bool = False, required: bool = True) -> str:
    """Interactive prompt. Shows current value, supports blank=keep."""
    display_current = ("*" * 8 + current[-4:]) if secret and current else (current or "not set")
    hint = f"{DIM}[current: {display_current}]{RESET}" if current else f"{DIM}[required]{RESET}" if required else f"{DIM}[optional — press Enter to skip]{RESET}"
    try:
        val = input(f"  {BOLD}{label}{RESET} {hint}\n  > ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)
    # Blank = keep current
    if not val and current:
        return current
    return val

def prompt_yn(label: str, default: bool = True) -> bool:
    default_str = "Y/n" if default else "y/N"
    try:
        val = input(f"  {label} [{default_str}]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)
    if not val:
        return default
    return val.startswith("y")


# ─────────────────────────────────────────────────────────────────────────────
# Section configurators
# ─────────────────────────────────────────────────────────────────────────────

def configure_tripo(values: dict) -> dict:
    header("Tripo API — 3D Generation")
    print(f"  Get your key at: {CYAN}https://platform.tripo3d.ai{RESET}")
    print(f"  (Account → API Keys → Create Key)")
    print()

    while True:
        key = prompt("Tripo API Key", values.get("TRIPO_API_KEY", ""), secret=True)
        if not key:
            warn("Tripo key skipped — 3D generation tools will not work")
            break
        print(f"  {DIM}Validating...{RESET}", end="", flush=True)
        valid, msg = validate_tripo_key(key)
        print(f"\r  ", end="")
        if valid:
            ok(msg)
            values["TRIPO_API_KEY"] = key
            break
        else:
            err(msg)
            if not prompt_yn("  Try a different key?"):
                warn("Skipping Tripo — you can run this wizard again later")
                break
    return values

def configure_huanyuan(values: dict) -> dict:
    header("Huanyuan3D API — Optional")
    print(f"  Get your key at: {CYAN}https://hunyuan.cloud.tencent.com{RESET}")
    print(f"  {DIM}(Optional — skip if you don't have one){RESET}")
    print()
    key = prompt("Huanyuan API Key", values.get("HUANYUAN_API_KEY", ""), secret=True, required=False)
    if key:
        values["HUANYUAN_API_KEY"] = key
        ok("Huanyuan key saved")
    else:
        info("Skipped")
    return values

def configure_metatailor(values: dict) -> dict:
    header("MetaTailor API — Optional (Auto-Rigging)")
    print(f"  Get your key at: {CYAN}https://metatailor.io{RESET}")
    print(f"  {DIM}(Optional — skip if you don't have one){RESET}")
    print()
    key = prompt("MetaTailor API Key", values.get("METATAILOR_API_KEY", ""), secret=True, required=False)
    if key:
        values["METATAILOR_API_KEY"] = key
        ok("MetaTailor key saved")
    else:
        info("Skipped")
    return values

def configure_ue(values: dict) -> dict:
    header("Unreal Engine 5.4 Remote Control")
    print(f"  Default port is 30010.")
    print(f"  UE must be running with Remote Control API plugin enabled.")
    print()

    host = prompt("UE Host", values.get("UE_REMOTE_CONTROL_HOST", "127.0.0.1"), required=False) or "127.0.0.1"
    port_str = prompt("UE Port", values.get("UE_REMOTE_CONTROL_PORT", "30010"), required=False) or "30010"

    values["UE_REMOTE_CONTROL_HOST"] = host
    values["UE_REMOTE_CONTROL_PORT"] = port_str

    print(f"  {DIM}Testing connection...{RESET}", end="", flush=True)
    valid, msg = validate_ue_connection(host, int(port_str))
    print(f"\r  ", end="")
    if valid:
        ok(msg)
    else:
        warn(msg)
        info("Settings saved — start UE 5.4 and enable Remote Control API plugin")

    return values

def configure_paths(values: dict) -> dict:
    header("Asset Storage Settings")
    print(f"  Where downloaded 3D models land before being imported into UE.")
    print()

    default_temp = "C:/UEOS/temp" if sys.platform == "win32" else str(ROOT / "temp")
    temp = prompt("Temp directory for asset downloads",
                  values.get("UEOS_ASSET_TEMP_DIR", default_temp),
                  required=False) or default_temp

    values["UEOS_ASSET_TEMP_DIR"] = temp

    # Create it
    try:
        Path(temp).mkdir(parents=True, exist_ok=True)
        ok(f"Directory ready: {temp}")
    except Exception as e:
        warn(f"Could not create {temp}: {e}")

    return values

def configure_claude(values: dict):
    """Print Claude Desktop config instructions."""
    header("Claude Desktop MCP Config")
    server_path = ROOT / "mcp_server" / "server.py"

    # Windows path with escaped backslashes for JSON
    win_path = str(server_path).replace("\\", "\\\\")
    unix_path = str(server_path)

    print(f"  Add this to your Claude Desktop config:\n")
    print(f'  {BOLD}"mcpServers"{RESET}: {{')
    print(f'    {BOLD}"ueos"{RESET}: {{')
    print(f'      "command": "python",')
    print(f'      "args": ["{win_path}"],')
    print(f'      "cwd": "{str(ROOT / "mcp_server").replace(chr(92), chr(92)*2)}"')
    print(f'    }}')
    print(f'  }}')
    print()
    print(f"  Config file location:")
    print(f"    {YELLOW}Windows{RESET} : %APPDATA%\\Claude\\claude_desktop_config.json")
    print(f"    {YELLOW}macOS  {RESET} : ~/Library/Application Support/Claude/claude_desktop_config.json")


# ─────────────────────────────────────────────────────────────────────────────
# Main wizard
# ─────────────────────────────────────────────────────────────────────────────

def run_full_wizard():
    print()
    print(f"{BOLD}{CYAN}{'═'*50}{RESET}")
    print(f"{BOLD}{CYAN}  UEOS — Configuration Wizard{RESET}")
    print(f"{BOLD}{CYAN}  Unreal Engine Operating System{RESET}")
    print(f"{BOLD}{CYAN}{'═'*50}{RESET}")
    print()
    print(f"  This wizard sets up your API keys and saves them")
    print(f"  to {YELLOW}.env{RESET} (never committed to git).")
    print(f"  Press {BOLD}Enter{RESET} to keep the current value.")
    print(f"  Press {BOLD}Ctrl+C{RESET} to quit at any time.")

    # Ensure .env exists
    if not ENV.exists():
        if EXAMPLE.exists():
            shutil.copy(EXAMPLE, ENV)
        else:
            ENV.write_text("", encoding="utf-8")

    values = read_env()

    # Run each section
    values = configure_tripo(values)
    values = configure_huanyuan(values)
    values = configure_metatailor(values)
    values = configure_ue(values)
    values = configure_paths(values)

    # Save
    write_env(values)

    header("Configuration Saved")
    ok(f".env written to: {ENV}")
    print()

    # Claude config instructions
    configure_claude(values)

    # Summary
    header("Setup Summary")
    checks = [
        ("Tripo API",     bool(values.get("TRIPO_API_KEY"))),
        ("Huanyuan3D",    bool(values.get("HUANYUAN_API_KEY"))),
        ("MetaTailor",    bool(values.get("METATAILOR_API_KEY"))),
        ("UE Connection", bool(values.get("UE_REMOTE_CONTROL_HOST"))),
        ("Temp Dir",      bool(values.get("UEOS_ASSET_TEMP_DIR"))),
    ]
    for label, configured in checks:
        if configured:
            ok(label)
        else:
            warn(f"{label} — not configured (optional)")

    print()
    print(f"  {BOLD}Next steps:{RESET}")
    print(f"  1. Configure Claude Desktop config (shown above)")
    print(f"  2. Open UE 5.4 with Remote Control API enabled")
    print(f"  3. Restart Claude Desktop")
    print(f"  4. Ask Claude: {CYAN}ueos_status{RESET}")
    print()


def run_tripo_only():
    """Quick update for Tripo key only."""
    print()
    print(f"{BOLD}{CYAN}  UEOS — Update Tripo API Key{RESET}")
    print()
    if not ENV.exists():
        shutil.copy(EXAMPLE, ENV) if EXAMPLE.exists() else ENV.write_text("", encoding="utf-8")
    values = read_env()
    values = configure_tripo(values)
    write_env(values)
    ok(f"Saved to {ENV}")
    print()


def run_reset():
    """Wipe .env and start fresh."""
    if prompt_yn(f"  {RED}Reset .env to blank template?{RESET} This clears all API keys", default=False):
        if EXAMPLE.exists():
            shutil.copy(EXAMPLE, ENV)
        else:
            ENV.write_text("", encoding="utf-8")
        ok(".env reset to blank template")
        run_full_wizard()
    else:
        info("Reset cancelled")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Enable ANSI colors on Windows
    if sys.platform == "win32":
        os.system("")

    parser = argparse.ArgumentParser(description="UEOS Configuration Wizard")
    parser.add_argument("--tripo",  action="store_true", help="Update Tripo key only")
    parser.add_argument("--reset",  action="store_true", help="Reset to blank config")
    parser.add_argument("--claude", action="store_true", help="Show Claude Desktop config")
    args = parser.parse_args()

    if args.tripo:
        run_tripo_only()
    elif args.reset:
        run_reset()
    elif args.claude:
        values = read_env()
        configure_claude(values)
    else:
        run_full_wizard()
