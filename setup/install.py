#!/usr/bin/env python3
"""
UEOS Setup Script
Run this once on your machine to set everything up.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent

def run(cmd, **kwargs):
    print(f"  → {cmd}")
    result = subprocess.run(cmd, shell=True, **kwargs)
    if result.returncode != 0:
        print(f"  ✗ Command failed: {cmd}")
        return False
    return True

def check_python():
    print("\n[1/5] Checking Python version...")
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 10):
        print(f"  ✗ Python 3.10+ required. You have {v.major}.{v.minor}")
        sys.exit(1)
    print(f"  ✓ Python {v.major}.{v.minor}.{v.micro}")

def install_deps():
    print("\n[2/5] Installing Python dependencies...")
    ok = run(f"{sys.executable} -m pip install -r {ROOT}/requirements.txt")
    if ok:
        print("  ✓ Dependencies installed")
    else:
        print("  ✗ Dependency installation failed. Try: pip install -r requirements.txt manually")

def setup_env():
    print("\n[3/5] Setting up .env file...")
    env_file = ROOT / ".env"
    example_file = ROOT / ".env.example"

    if env_file.exists():
        print("  ✓ .env already exists")
        return

    if example_file.exists():
        shutil.copy(example_file, env_file)
        print("  ✓ Created .env from .env.example")
        print("  ! Open .env and fill in your API keys")
    else:
        print("  ✗ .env.example not found")

def setup_temp_dir():
    print("\n[4/5] Creating temp directory for asset downloads...")
    temp_dir = Path("C:/UEOS/temp")
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ Temp dir created: {temp_dir}")
    except Exception as e:
        # Non-Windows
        fallback = ROOT / "temp"
        fallback.mkdir(exist_ok=True)
        print(f"  ✓ Temp dir created: {fallback}")
        print(f"  ! Update UEOS_ASSET_TEMP_DIR in .env to: {fallback}")

def print_claude_config():
    print("\n[5/5] Claude Desktop MCP Configuration")
    print("  Add this to your claude_desktop_config.json:")
    print()
    server_path = ROOT / "mcp_server" / "server.py"
    print('  {')
    print('    "mcpServers": {')
    print('      "ueos": {')
    print('        "command": "python",')
    print(f'        "args": ["{server_path}"],')
    print('        "env": {}')
    print('      }')
    print('    }')
    print('  }')
    print()
    print("  Config file locations:")
    print("    Windows : %APPDATA%\\Claude\\claude_desktop_config.json")
    print("    macOS   : ~/Library/Application Support/Claude/claude_desktop_config.json")

def print_ue_plugins():
    print("\n═══════════════════════════════════════")
    print("  Required Unreal Engine 5.4 Plugins")
    print("═══════════════════════════════════════")
    plugins = [
        "Python Editor Script Plugin",
        "Remote Control API",
        "Remote Control Logic",
        "Editor Scripting Utilities",
        "Niagara",
    ]
    for p in plugins:
        print(f"  ✓ {p}")
    print()
    print("  Enable via: Edit → Plugins → search for each")
    print("  Restart editor after enabling all plugins")
    print()
    print("  Remote Control settings:")
    print("  Edit → Project Settings → Plugins → Remote Control")
    print("  Enable: 'Allow remote control of editor' = ON")
    print("  Port: 30010 (default)")

def main():
    print("═══════════════════════════════════════")
    print("  UEOS Setup - Unreal Engine OS v1.0")
    print("═══════════════════════════════════════")

    check_python()
    install_deps()
    setup_env()
    setup_temp_dir()
    print_claude_config()
    print_ue_plugins()

    print("\n═══════════════════════════════════════")
    print("  Setup Complete!")
    print("  Next steps:")
    print("  1. Fill in .env with your API keys")
    print("  2. Enable UE plugins listed above")
    print("  3. Add MCP config to Claude Desktop")
    print("  4. Start Unreal Engine 5.4")
    print("  5. Ask Claude: ueos_status")
    print("═══════════════════════════════════════")

if __name__ == "__main__":
    main()
