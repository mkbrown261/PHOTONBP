"""
ue_http_bridge.py
=================
Drop this file into your UE project's Content/Python/ folder.
UE loads all Python files in that folder on startup automatically.

What it does:
  Registers an @unreal.uclass() called PhotonExecBridge with one callable method:
    run_script(Script: str) -> str
  This lets the Remote Control HTTP API (port 30010) execute ARBITRARY Python
  inside UE — bypassing the multicast/UDP discovery entirely.

How to install:
  Copy this file to:
    <YourProject>/Content/Python/ue_http_bridge.py
  Then either:
    - Restart UE, OR
    - Run in UE's Python console:
        import importlib, sys
        if 'ue_http_bridge' in sys.modules:
            importlib.reload(sys.modules['ue_http_bridge'])
        else:
            import ue_http_bridge

How to call from outside UE (PowerShell / Python):
  PUT http://127.0.0.1:30010/remote/object/call
  Body:
  {
    "objectPath": "/Engine/PhotonExecBridge.Default__PhotonExecBridge_C",
    "functionName": "RunScript",
    "parameters": { "Script": "print('hello')" },
    "generateTransaction": false
  }
"""

import unreal
import sys
import io
import traceback
import json


@unreal.uclass()
class PhotonExecBridge(unreal.Object):
    """HTTP-callable bridge: executes arbitrary Python and returns stdout."""

    @unreal.ufunction(
        override=False,
        ret=str,
        params=[str],
        meta=dict(DisplayName="RunScript", Category="PhotonBridge")
    )
    def run_script(self, script: str) -> str:
        """
        Execute `script` in UE's Python interpreter.
        Returns JSON: {"ok": true/false, "output": "...", "error": "..."}
        """
        buf = io.StringIO()
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = buf
        sys.stderr = buf
        err_msg = None
        try:
            # Inject both 'unreal' and 'json' so probe scripts never need to
            # "import unreal" (which could reset sys.stdout via UE hooks) or
            # "import json" (harmless but redundant).  Any script that does
            # "import unreal" will shadow this injected binding — safe because
            # unreal is already in sys.modules and won't re-run module code.
            import json as _json_mod
            # Inject sys explicitly so scripts can use sys.stdout.write() directly
            # against the already-redirected buf — bypasses any UE print() override.
            exec(script, {"unreal": unreal, "json": _json_mod, "sys": sys})  # noqa: S102
        except Exception:
            err_msg = traceback.format_exc()
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        output = buf.getvalue()
        result = {"ok": err_msg is None, "output": output, "error": err_msg}
        return json.dumps(result)


# Register so UE Remote Control can discover the object path
_bridge_instance = None

def _register():
    global _bridge_instance
    try:
        _bridge_instance = PhotonExecBridge()
        unreal.log("[PhotonBridge] ue_http_bridge loaded — HTTP exec bridge is ACTIVE")
        unreal.log("[PhotonBridge] Object path: /Engine/PhotonExecBridge.Default__PhotonExecBridge_C")
    except Exception as e:
        unreal.log_warning(f"[PhotonBridge] Failed to instantiate bridge: {e}")

_register()
