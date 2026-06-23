"""
remote_execution.py
===================
UE Python execution via HTTP bridge (PhotonExecBridge).

NO multicast. NO UDP. NO sockets. Plain HTTP to port 30010.

The bridge object is registered by ue_http_bridge.py which lives in
the UE project's Content/Python/ folder and loads automatically at
editor startup.

Confirmed working object path (discovered 2026-06-23):
    /Engine/Transient.PhotonExecBridge_0

All tools call execute_python() → this module → UE → stdout captured → returned.
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from typing import Any

log = logging.getLogger("ueos.remote_exec")

# ── Config ────────────────────────────────────────────────────────────────────

HTTP_PORT = 30010
BASE_URL  = f"http://127.0.0.1:{HTTP_PORT}"

# The @unreal.uclass() bridge that executes arbitrary Python and captures stdout
BRIDGE_OBJECT   = "/Engine/Transient.PhotonExecBridge_0"
BRIDGE_FUNCTION = "run_script"

# Legacy constants — kept so any old imports don't crash
EXEC_MODE_EXEC_FILE      = "ExecuteFile"
EXEC_MODE_EXEC_STATEMENT = "ExecuteStatement"
EXEC_MODE_EVAL_STATEMENT = "EvaluateStatement"


# ── Low-level HTTP ────────────────────────────────────────────────────────────

def _put(path: str, body: dict, timeout: int = 30) -> dict:
    """PUT request to UE Remote Control HTTP API."""
    url  = BASE_URL + path
    data = json.dumps(body).encode("utf-8")
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="PUT"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def _parse_bridge_response(raw: dict) -> dict:
    """
    Parse the HTTP bridge response into a standard result dict.
    Returns: {"ok": bool, "output": str, "error": str|None}
    """
    return_value = raw.get("ReturnValue") or raw.get("returnValue") or ""
    if isinstance(return_value, str) and return_value.startswith("{"):
        try:
            parsed = json.loads(return_value)
            if "ok" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass
    # Fallback — wrap whatever came back
    return {"ok": True, "output": str(raw), "error": None}


# ── Main execution class ──────────────────────────────────────────────────────

class UnrealRemoteExecution:
    """
    Executes Python inside UE via the PhotonExecBridge HTTP endpoint.
    Captures stdout and returns it — unlike ExecutePythonScript which is fire-and-forget.

    Usage:
        re = UnrealRemoteExecution()
        if re.ping():
            result = re.run("print('hello')")
            print(result["output"])  # → "hello"
    """

    def __init__(self, command_timeout: int = 30, discovery_timeout: float = 5.0):
        self.command_timeout = command_timeout

    def ping(self) -> bool:
        """Return True if UE Remote Control HTTP API is reachable."""
        try:
            urllib.request.urlopen(BASE_URL + "/remote/info", timeout=3)
            return True
        except Exception:
            return False

    def run(self, script: str, exec_mode: str = EXEC_MODE_EXEC_STATEMENT,
            timeout: int | None = None) -> dict:
        """
        Execute a Python script inside UE via the HTTP bridge.
        Returns legacy-compatible dict: {"output": str, "success": bool}

        The exec_mode parameter is accepted but ignored — the bridge always
        uses exec() which handles both single-line and multi-line scripts.
        """
        t = timeout or self.command_timeout
        try:
            raw = _put("/remote/object/call", {
                "objectPath":         BRIDGE_OBJECT,
                "functionName":       BRIDGE_FUNCTION,
                "parameters":         {"Script": script},
                "generateTransaction": False
            }, timeout=t)
            result = _parse_bridge_response(raw)
            # Return in legacy format so all callers keep working
            return {
                "output":  [{"output": result.get("output", ""), "type": "OUTPUT"}],
                "success": result.get("ok", True),
                "_bridge_result": result,
            }
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise RuntimeError(
                    "PhotonExecBridge not found (404). "
                    "Make sure ue_http_bridge.py is loaded in UE. "
                    "In UE Output Log (Python mode): import ue_http_bridge"
                ) from e
            raise RuntimeError(f"HTTP {e.code} calling bridge: {e}") from e
        except urllib.error.URLError as e:
            raise ConnectionError(
                f"Cannot reach UE on port {HTTP_PORT}. "
                f"Is UE running with Remote Control enabled? Error: {e}"
            ) from e

    def run_ex(self, script: str, timeout: int | None = None) -> dict:
        """
        Like run() but returns structured result:
        {"ok": bool, "output": str, "error": str|None}
        """
        t = timeout or self.command_timeout
        try:
            raw = _put("/remote/object/call", {
                "objectPath":         BRIDGE_OBJECT,
                "functionName":       BRIDGE_FUNCTION,
                "parameters":         {"Script": script},
                "generateTransaction": False
            }, timeout=t)
            return _parse_bridge_response(raw)
        except Exception as e:
            return {"ok": False, "output": "", "error": str(e)}


# ── Module-level convenience ──────────────────────────────────────────────────

def _parse_exec_result(raw: dict) -> dict:
    """
    Legacy helper — parses output entries list into a flat string.
    Kept for backwards compatibility with client.py imports.
    """
    output_entries = raw.get("output", [])
    if isinstance(output_entries, list):
        return "\n".join(
            e.get("output", "") for e in output_entries if isinstance(e, dict)
        )
    return str(output_entries)
