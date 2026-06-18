"""
http_exec.py
============
Sends Python scripts to UE via the HTTP bridge (ue_http_bridge.py).
No multicast. No UDP. No admin rights. Just plain HTTP on port 30010.

Prerequisites:
  1. UE is running with Remote Control Plugin enabled (port 30010).
  2. ue_http_bridge.py has been loaded in UE (see INSTALL_BRIDGE.ps1).

Usage:
    from mcp_server.remote_control.http_exec import UEHttpExec

    ue = UEHttpExec()
    if not ue.ping():
        print("UE not reachable on port 30010")
    else:
        result = ue.run('import unreal; print(unreal.SystemLibrary.get_engine_version())')
        print(result['output'])
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from typing import Any

log = logging.getLogger("ueos.http_exec")

HTTP_PORT = 30010
BASE_URL = f"http://127.0.0.1:{HTTP_PORT}"

# The object path for our bridge class.
# UE registers @unreal.uclass() objects under /Engine/<ClassName>.Default__<ClassName>_C
BRIDGE_OBJECT_PATH = "/Engine/PhotonExecBridge.Default__PhotonExecBridge_C"
BRIDGE_FUNCTION    = "RunScript"

# Fallback: PythonScriptPlugin's built-in ExecutePythonScript (no output capture)
FALLBACK_OBJECT_PATH = "/Engine/PythonScriptPlugin.Default__PythonScriptPlugin"
FALLBACK_FUNCTION    = "ExecutePythonScript"


def _http_put(path: str, body: dict, timeout: int = 30) -> dict:
    """Send a PUT request to UE Remote Control HTTP API."""
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


class UEHttpExec:
    """
    Execute arbitrary Python inside UE via the PhotonExecBridge HTTP endpoint.
    Falls back to ExecutePythonScript (no output) if bridge not loaded.
    """

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._bridge_available: bool | None = None  # None = not yet tested

    # ── Connectivity ───────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Return True if UE Remote Control HTTP API is reachable."""
        try:
            urllib.request.urlopen(BASE_URL + "/remote/info", timeout=3)
            return True
        except Exception:
            return False

    def check_bridge(self) -> bool:
        """
        Return True if PhotonExecBridge is loaded and callable.
        Caches result after first successful call.
        """
        if self._bridge_available is True:
            return True
        try:
            result = self._call_bridge("print('bridge_ok')")
            if result.get("ok") and "bridge_ok" in result.get("output", ""):
                self._bridge_available = True
                log.info("PhotonExecBridge: confirmed active")
                return True
        except Exception as e:
            log.debug(f"Bridge check failed: {e}")
        self._bridge_available = False
        return False

    # ── Execution ──────────────────────────────────────────────────────────

    def run(self, script: str, timeout: int | None = None) -> dict:
        """
        Execute `script` inside UE.
        Returns: {"ok": bool, "output": str, "error": str|None}

        Tries PhotonExecBridge first (captures stdout).
        Falls back to ExecutePythonScript if bridge not available (no stdout capture).
        """
        t = timeout or self.timeout

        # Try bridge first
        if self._bridge_available is not False:
            try:
                result = self._call_bridge(script, timeout=t)
                self._bridge_available = True
                return result
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    log.warning("PhotonExecBridge not found — bridge not installed in UE")
                    self._bridge_available = False
                else:
                    raise
            except Exception as e:
                log.warning(f"Bridge call failed: {e}")
                self._bridge_available = False

        # Fallback: ExecutePythonScript (fire-and-forget, no output)
        log.warning("Falling back to ExecutePythonScript (no stdout capture)")
        return self._call_fallback(script, timeout=t)

    def run_assert(self, label: str, script: str) -> dict:
        """
        Run script, print result, return result dict.
        Used in test scripts.
        """
        print(f"\n=== {label} ===")
        result = self.run(script)
        output = result.get("output", "").strip()
        error  = result.get("error")
        ok     = result.get("ok", False)

        if output:
            for line in output.splitlines():
                print(f"  {line}")
        if error:
            print(f"  ERROR: {error}")
        print(f"  success={ok}")
        return result

    # ── Internal ───────────────────────────────────────────────────────────

    def _call_bridge(self, script: str, timeout: int = 30) -> dict:
        """Call PhotonExecBridge.RunScript and parse JSON result."""
        raw = _http_put("/remote/object/call", {
            "objectPath": BRIDGE_OBJECT_PATH,
            "functionName": BRIDGE_FUNCTION,
            "parameters": {"Script": script},
            "generateTransaction": False
        }, timeout=timeout)

        # The HTTP API wraps return values like: {"ReturnValue": "<json string>"}
        return_value = raw.get("ReturnValue") or raw.get("returnValue") or ""
        if isinstance(return_value, str) and return_value.startswith("{"):
            try:
                return json.loads(return_value)
            except json.JSONDecodeError:
                pass
        # If we get here, try interpreting the whole response
        if isinstance(raw, dict) and "ok" in raw:
            return raw
        return {"ok": True, "output": str(raw), "error": None}

    def _call_fallback(self, script: str, timeout: int = 30) -> dict:
        """Call PythonScriptPlugin.ExecutePythonScript (no output capture)."""
        try:
            raw = _http_put("/remote/object/call", {
                "objectPath": FALLBACK_OBJECT_PATH,
                "functionName": FALLBACK_FUNCTION,
                "parameters": {"PythonScript": script},
                "generateTransaction": False
            }, timeout=timeout)
            return {"ok": True, "output": "(no stdout capture — bridge not installed)", "error": None}
        except Exception as e:
            return {"ok": False, "output": "", "error": str(e)}


# ── Module-level convenience ───────────────────────────────────────────────────

_default_instance: UEHttpExec | None = None

def get_executor() -> UEHttpExec:
    global _default_instance
    if _default_instance is None:
        _default_instance = UEHttpExec()
    return _default_instance


if __name__ == "__main__":
    # Quick connectivity test
    ue = UEHttpExec()
    if not ue.ping():
        print("ERROR: UE not reachable on port 30010")
        print("Make sure:")
        print("  1. UE is running")
        print("  2. Remote Control Plugin is enabled")
        print("  3. Edit > Project Settings > Plugins > Remote Control > Enable Remote Control API")
    else:
        print("OK: UE is reachable on port 30010")
        if ue.check_bridge():
            print("OK: PhotonExecBridge is loaded and working!")
        else:
            print("WARN: PhotonExecBridge not loaded.")
            print("      Run INSTALL_BRIDGE.ps1 then restart UE.")
            print("      Or in UE Python console: exec(open(r'<project>/Content/Python/ue_http_bridge.py').read())")
