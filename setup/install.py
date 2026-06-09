#!/usr/bin/env python3
"""
UEOS Install Script
Run once after cloning to set up dependencies and configuration.

Usage:
    python setup/install.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Enable ANSI colors on Windows
if sys.platform == "win32":
    os.system("")

def ok(msg):   print(f"  \033[32m✓\033[0m {msg}")
def err(msg):  print(f"  \033[31m✗\033[0m {msg}")
def warn(msg): print(f"  \033[33m!\033[0m {msg}")
def info(msg): print(f"  \033[36m→\033[0m {msg}")

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0, result.stdout + result.stderr


def check_python():
    print("\n[1/4] Checking Python version...")
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 10):
        err(f"Python 3.10+ required. You have {v.major}.{v.minor}")
        sys.exit(1)
    ok(f"Python {v.major}.{v.minor}.{v.micro}")


def install_deps():
    print("\n[2/4] Installing Python dependencies...")
    req = ROOT / "requirements.txt"
    success, output = run(f'"{sys.executable}" -m pip install -r "{req}"')
    if success:
        ok("All dependencies installed")
    else:
        err("Dependency installation failed")
        print(output)
        warn(f"Try manually: pip install -r {req}")


def setup_temp_dir():
    print("\n[3/4] Creating temp directory for asset downloads...")
    temp_dir = Path("C:/UEOS/temp") if sys.platform == "win32" else ROOT / "temp"
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        ok(f"Temp dir ready: {temp_dir}")
    except Exception as e:
        warn(f"Could not create {temp_dir}: {e}")


def run_configure():
    print("\n[4/4] Launching configuration wizard...")
    print()
    configure = ROOT / "setup" / "configure.py"
    # Check if .env already has keys configured
    env_file = ROOT / ".env"
    already_configured = False
    if env_file.exists():
        content = env_file.read_text(encoding="utf-8")
        if "TRIPO_API_KEY=tsk_" in content:
            already_configured = True

    if already_configured:
        ok(".env already configured — skipping wizard")
        info("Run 'python setup/configure.py' to update keys")
    else:
        try:
            subprocess.run([sys.executable, str(configure)], check=False)
        except KeyboardInterrupt:
            print()
            warn("Configuration wizard skipped — run 'python setup/configure.py' later")


def print_ue_plugins():
    print()
    print("\033[1m\033[36m" + "═"*50 + "\033[0m")
    print("\033[1m\033[36m  Required Unreal Engine 5.4 Plugins\033[0m")
    print("\033[1m\033[36m" + "═"*50 + "\033[0m")
    plugins = [
        "Python Editor Script Plugin",
        "Remote Control API",
        "Remote Control Logic",
        "Editor Scripting Utilities",
        "Niagara",
    ]
    for p in plugins:
        ok(p)
    print()
    info("Enable via: Edit → Plugins → search for each")
    info("Restart UE editor after enabling all plugins")
    print()
    info("Remote Control: Edit → Project Settings → Plugins → Remote Control API")
    info("Enable: 'Allow remote control of editor' = ON  |  Port: 30010")


def main():
    print()
    print("\033[1m\033[36m" + "═"*50 + "\033[0m")
    print("\033[1m\033[36m  UEOS Install — Unreal Engine Operating System\033[0m")
    print("\033[1m\033[36m" + "═"*50 + "\033[0m")

    check_python()
    install_deps()
    setup_temp_dir()
    run_configure()
    print_ue_plugins()

    print()
    print("\033[1m\033[36m" + "═"*50 + "\033[0m")
    print("\033[1m  Install complete!\033[0m")
    print()
    info("After setup:")
    info("1. Enable UE plugins listed above")
    info("2. Update Claude Desktop config (shown in wizard)")
    info("3. Start Unreal Engine 5.4")
    info("4. Ask Claude: ueos_status")
    print()


if __name__ == "__main__":
    main()
