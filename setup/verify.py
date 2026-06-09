#!/usr/bin/env python3
"""
UEOS Verification Script
Run this to confirm everything is connected before using Claude.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mcp_server"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from remote_control.client import UnrealRemoteControl
from api_clients.tripo import TripoClient


async def verify():
    print("\n═══════════════════════════════════════")
    print("  UEOS Connection Verification")
    print("═══════════════════════════════════════")

    all_ok = True

    # 1. Unreal Engine
    print("\n[1] Unreal Engine Remote Control...")
    ue = UnrealRemoteControl(
        host=os.getenv("UE_REMOTE_CONTROL_HOST", "127.0.0.1"),
        port=int(os.getenv("UE_REMOTE_CONTROL_PORT", 30010))
    )
    try:
        info = await ue.get_engine_info()
        print(f"  ✓ Connected")
        print(f"    Version : {info.get('engineVersion', 'Unknown')}")
        print(f"    Project : {info.get('projectName', 'Unknown')}")
    except Exception as e:
        print(f"  ✗ Not connected: {e}")
        print("    Make sure UE 5.4 is running with Remote Control plugin enabled")
        all_ok = False

    # 2. Tripo
    print("\n[2] Tripo API...")
    tripo_key = os.getenv("TRIPO_API_KEY", "")
    if not tripo_key or tripo_key == "your_tripo_api_key_here":
        print("  ✗ API key not configured in .env")
        all_ok = False
    else:
        tripo = TripoClient(api_key=tripo_key)
        try:
            balance = await tripo.get_balance()
            print(f"  ✓ Connected")
            print(f"    Balance : {balance}")
        except Exception as e:
            print(f"  ✗ Connection failed: {e}")
            all_ok = False

    # 3. Huanyuan
    print("\n[3] Huanyuan3D API...")
    hy_key = os.getenv("HUANYUAN_API_KEY", "")
    if not hy_key or hy_key == "your_huanyuan_api_key_here":
        print("  ⚠ Not configured (optional)")
    else:
        print(f"  ✓ Key configured")

    # 4. MetaTailor
    print("\n[4] MetaTailor API...")
    mt_key = os.getenv("METATAILOR_API_KEY", "")
    if not mt_key or mt_key == "your_metatailor_api_key_here":
        print("  ⚠ Not configured (optional)")
    else:
        print(f"  ✓ Key configured")

    # 5. Temp directory
    print("\n[5] Temp directory...")
    temp_dir = os.getenv("UEOS_ASSET_TEMP_DIR", "C:/UEOS/temp")
    if os.path.isdir(temp_dir):
        print(f"  ✓ {temp_dir}")
    else:
        print(f"  ✗ Not found: {temp_dir}")
        print("    Run setup/install.py to create it")
        all_ok = False

    print("\n═══════════════════════════════════════")
    if all_ok:
        print("  ✓ All systems ready. Start Claude.")
    else:
        print("  ✗ Some systems not ready. Fix issues above.")
    print("═══════════════════════════════════════\n")


if __name__ == "__main__":
    asyncio.run(verify())
