#!/usr/bin/env python3
"""
check_ue.py
Called by SETUP.bat to test if UE Remote Control API is reachable.

Exit codes:
  0 — UE connected
  1 — not connected
"""

import sys
import json
import urllib.request
import urllib.error
import os
from pathlib import Path

def check_ue(host: str = "127.0.0.1", port: int = 30010) -> bool:
    payload = json.dumps({
        "objectPath": "/Script/PythonScriptPlugin.Default__PythonScriptLibrary",
        "functionName": "ExecutePythonScript",
        "parameters": {"PythonScript": "print('UEOS_PING:OK')"},
    }).encode()
    try:
        req = urllib.request.Request(
            f"http://{host}:{port}/remote/object/call",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            return True
    except Exception:
        return False

if __name__ == "__main__":
    # Read host/port from .env if available
    host, port = "127.0.0.1", 30010
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("UE_REMOTE_CONTROL_HOST="):
                host = line.split("=", 1)[1].strip()
            elif line.startswith("UE_REMOTE_CONTROL_PORT="):
                try:
                    port = int(line.split("=", 1)[1].strip())
                except ValueError:
                    pass

    sys.exit(0 if check_ue(host, port) else 1)
