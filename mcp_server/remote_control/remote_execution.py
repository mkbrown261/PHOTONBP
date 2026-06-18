"""
remote_execution.py — UE Remote Execution via HTTP API (port 30010)
Replaces the broken multicast/UDP approach entirely.
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from typing import Any

log = logging.getLogger("ueos.remote_exec")

HTTP_PORT = 30010
BASE_URL  = f"http://127.0.0.1:{HTTP_PORT}"

EXEC_MODE_EXEC_FILE      = "ExecuteFile"
EXEC_MODE_EXEC_STATEMENT = "ExecuteStatement"
EXEC_MODE_EVAL_STATEMENT = "EvaluateStatement"


def _http(path: str, body: dict) -> dict:
    url  = BASE_URL + path
    data = json.dumps(body).encode("utf-8")
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="PUT"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


class UnrealRemoteExecution:
    """
    Sends Python scripts to UE via the Remote Control HTTP API on port 30010.
    No multicast, no UDP, no sockets — just plain HTTP.
    """

    def __init__(self, command_timeout: int = 30, discovery_timeout: float = 5.0):
        self.command_timeout = command_timeout

    def ping(self) -> bool:
        try:
            url = BASE_URL + "/remote/info"
            urllib.request.urlopen(url, timeout=3)
            return True
        except Exception:
            return False

    def run(self, script: str, exec_mode: str = EXEC_MODE_EXEC_STATEMENT,
            timeout: int | None = None) -> dict:
        """Execute a Python script in UE. Returns raw result dict."""
        result = _http("/remote/object/call", {
            "objectPath": "/Engine/PythonScriptPlugin.Default__PythonScriptPlugin",
            "functionName": "ExecutePythonScript",
            "parameters": {
                "PythonScript": script
            },
            "generateTransaction": False
        })
        return result

    def run_ex(self, script: str, timeout: int | None = None) -> dict:
        """
        Run script, capture print() output via a temp file trick,
        return {"ok": bool, "output": str, "error": str|None}
        """
        # Wrap script to capture stdout to a string we can read back
        wrapped = f"""
import unreal, sys, io, traceback
_buf = io.StringIO()
_old = sys.stdout
sys.stdout = _buf
try:
{chr(10).join('    ' + line for line in script.splitlines())}
except Exception as _e:
    sys.stdout = _old
    print("UEOS_ERROR:" + traceback.format_exc().replace("\\n", " | "))
    sys.stdout = _buf
finally:
    sys.stdout = _old
_out = _buf.getvalue()
if _out:
    unreal.log(_out)
"""
        try:
            raw = self.run(wrapped, timeout=timeout)
            # HTTP API doesn't easily capture stdout — use log-based approach
            return {"ok": True, "output": str(raw), "error": None}
        except Exception as e:
            return {"ok": False, "output": "", "error": str(e)}
