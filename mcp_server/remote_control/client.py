"""
Unreal Engine 5.4 Remote Control Client

ALL Python execution goes through the PhotonExecBridge HTTP endpoint
(port 30010). No UDP, no multicast, no sockets required.

The bridge (ue_http_bridge.py) must be loaded in UE:
  - Copy to <Project>/Content/Python/ue_http_bridge.py
  - In UE Output Log (Python mode): import ue_http_bridge
  - Bridge object path: /Engine/PythonTypes.Default__PhotonExecBridge

Property get/set and batch calls also use the HTTP Remote Control API.
"""

import asyncio
import json
import logging
import time
from typing import Any, Optional

import aiohttp

from remote_control.remote_execution import (
    UnrealRemoteExecution,
    EXEC_MODE_EXEC_STATEMENT,
    _parse_exec_result,
)

log = logging.getLogger("ueos.rc")


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

UEOS_PREFIXES = (
    "UEOS_RESULT:",
    "UEOS_ERROR:",
    "UEOS_INFO:",
    "UEOS_ASSETS:",
    "UEOS_EXISTS:",
    "UEOS_IMPORT_RESULT:",
    "UEOS_WARN:",
)

# UE 5.4 Remote Control API endpoints
EP_CALL   = "/remote/object/call"
EP_PROP   = "/remote/object/property"
EP_BATCH  = "/remote/batch"
EP_PRESET = "/remote/preset"
EP_INFO   = "/remote/info"

# Python script plugin object path (unchanged in 5.4)
PY_PLUGIN_PATH = "/Script/PythonScriptPlugin.Default__PythonScriptLibrary"


# ─────────────────────────────────────────────────────────────────────────────
# Client
# ─────────────────────────────────────────────────────────────────────────────

class UnrealRemoteControl:
    """
    Dual-protocol client for Unreal Engine 5.4.

    Python execution  → Remote Execution (UDP discovery + TCP)
    Property access   → HTTP Remote Control API (port 30010)

    All public methods are coroutines (use with await).
    """

    def __init__(
        self,
        host:          str = "127.0.0.1",
        port:          int = 30010,
        timeout:       int = 30,
        max_retries:   int = 3,
        retry_delay:   float = 1.0,
        verbose:       bool = False,
    ):
        self.host        = host
        self.port        = port
        self.base_url    = f"http://{host}:{port}"
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.verbose     = verbose
        self._set_timeout(timeout)

        # Remote Execution client (UDP/TCP — for Python)
        self._re = UnrealRemoteExecution(command_timeout=timeout)

    def _set_timeout(self, seconds: int):
        self.timeout = aiohttp.ClientTimeout(
            total=seconds,
            connect=5,
            sock_read=seconds
        )

    # ──────────────────────────────────────────────────────────────────────
    # Low-level HTTP
    # ──────────────────────────────────────────────────────────────────────

    async def _request(
        self,
        method:   str,
        endpoint: str,
        payload:  dict | None = None,
        retries:  int | None  = None,
    ) -> dict:
        """
        Core HTTP request with retry logic.
        UE Remote Control always returns JSON (or empty body on success).
        """
        url     = f"{self.base_url}{endpoint}"
        tries   = retries if retries is not None else self.max_retries
        delay   = self.retry_delay
        last_ex = None

        for attempt in range(tries):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    meth = getattr(session, method.lower())
                    kwargs: dict[str, Any] = {}
                    if payload is not None:
                        kwargs["json"] = payload

                    if self.verbose:
                        log.debug(f"{method.upper()} {url} | attempt {attempt+1}/{tries}")

                    async with meth(url, **kwargs) as resp:
                        text = await resp.text()

                        # 200/201 = success
                        if resp.status in (200, 201):
                            return json.loads(text) if text.strip() else {}

                        # 422 = UE validation error — don't retry
                        if resp.status == 422:
                            raise RuntimeError(f"UE RC 422 Unprocessable: {text[:400]}")

                        # 503 = UE not ready — retry
                        if resp.status == 503 and attempt < tries - 1:
                            log.warning(f"UE RC 503 (not ready), retry in {delay}s…")
                            await asyncio.sleep(delay)
                            delay *= 2
                            continue

                        raise RuntimeError(f"UE RC HTTP {resp.status}: {text}")

            except aiohttp.ClientConnectorError as e:
                last_ex = e
                if attempt < tries - 1:
                    log.warning(f"RC connection error, retry in {delay}s: {e}")
                    await asyncio.sleep(delay)
                    delay *= 2
            except asyncio.TimeoutError as e:
                last_ex = e
                if attempt < tries - 1:
                    log.warning(f"RC timeout, retry in {delay}s")
                    await asyncio.sleep(delay)
                    delay *= 2

        raise ConnectionError(
            f"UE Remote Control unreachable at {self.base_url} after {tries} attempts. "
            f"Last error: {last_ex}"
        )

    async def _post(self, endpoint: str, payload: dict) -> dict:
        return await self._request("POST", endpoint, payload)

    async def _put(self, endpoint: str, payload: dict) -> dict:
        return await self._request("PUT", endpoint, payload)

    async def _get(self, endpoint: str) -> dict:
        return await self._request("GET", endpoint)

    # ──────────────────────────────────────────────────────────────────────
    # Python script execution — via Remote Execution (UDP/TCP)
    # ──────────────────────────────────────────────────────────────────────

    async def execute_python(self, script: str, timeout: int = 30) -> dict:
        """
        Execute a Python script inside UE via the PhotonExecBridge HTTP endpoint.
        Captures stdout and returns it as a string.

        Returns: { "output": "<all stdout lines joined>", "success": bool }
        """
        self._re.command_timeout = timeout
        loop = asyncio.get_event_loop()

        raw = await loop.run_in_executor(
            None,
            lambda: self._re.run(script.strip(), timeout=timeout)
        )

        # Extract output from the bridge result
        output_entries = raw.get("output", [])
        if isinstance(output_entries, list):
            output_text = "\n".join(
                e.get("output", "") for e in output_entries if isinstance(e, dict)
            )
        elif isinstance(output_entries, str):
            output_text = output_entries
        else:
            output_text = str(output_entries)

        # Also pull from _bridge_result if present (direct stdout capture)
        bridge = raw.get("_bridge_result", {})
        if bridge.get("output"):
            output_text = bridge["output"]

        if self.verbose:
            log.debug(f"Bridge output: {output_text[:500]}")
        return {"output": output_text, "success": raw.get("success", True)}

    async def execute_python_ex(self, script: str, timeout: int = 30) -> dict:
        """
        Like execute_python() but parses UEOS_RESULT / UEOS_ERROR markers.
        Returns: { "ok": bool, "result": Any, "error": str | None, "raw_output": str }
        """
        self._re.command_timeout = timeout
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(
            None,
            lambda: self._re.run_ex(script, timeout=timeout)
        )
        # run_ex already returns {"ok", "output", "error"} — parse UEOS markers
        parsed = self._parse_output_ex({"output": raw.get("output", "")})
        if raw.get("error") and not parsed.get("error"):
            parsed["error"] = raw["error"]
            parsed["ok"] = False
        return parsed

    def _parse_output_ex(self, raw_result: dict) -> dict:
        """
        Parse all UEOS_ prefixed lines from a Python execution result.
        Returns structured dict with ok/result/error/raw_output.
        """
        output  = raw_result.get("output", "")
        result  = None
        error   = None
        info    = []
        warns   = []

        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("UEOS_RESULT:"):
                try:
                    result = json.loads(line[len("UEOS_RESULT:"):])
                except json.JSONDecodeError:
                    result = line[len("UEOS_RESULT:"):]
            elif line.startswith("UEOS_ERROR:"):
                error = line[len("UEOS_ERROR:"):]
            elif line.startswith("UEOS_INFO:"):
                try:
                    info.append(json.loads(line[len("UEOS_INFO:"):]))
                except Exception:
                    info.append(line[len("UEOS_INFO:"):])
            elif line.startswith("UEOS_WARN:"):
                warns.append(line[len("UEOS_WARN:"):])

        return {
            "ok":         error is None,
            "result":     result,
            "error":      error,
            "info":       info,
            "warnings":   warns,
            "raw_output": output
        }

    def parse_output(self, result: dict, prefix: str) -> Optional[str]:
        """
        Parse the FIRST line matching the given prefix from Python output.
        Compatible with Phase 1 usage patterns.
        """
        output = result.get("output", "")
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith(prefix):
                return line[len(prefix):].strip()
        return None

    def parse_all_outputs(self, result: dict, prefix: str) -> list[str]:
        """Parse ALL lines matching the given prefix (for multi-value returns)."""
        output = result.get("output", "")
        matches = []
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith(prefix):
                matches.append(line[len(prefix):].strip())
        return matches

    # ──────────────────────────────────────────────────────────────────────
    # Engine info
    # ──────────────────────────────────────────────────────────────────────

    async def get_engine_info(self) -> dict:
        """Get UE 5.4 version, project name, and paths."""
        script = """
import unreal, json

try:
    proj_file   = unreal.Paths.get_project_file_path()
    proj_dir    = unreal.Paths.project_dir()
    content_dir = unreal.Paths.project_content_dir()

    # NOTE: unreal.Paths returns relative paths (../../../../../../...) — this is normal UE behaviour.
    # The .uproject FILENAME is always correct regardless of relative prefix — use it directly.
    # Example: "../../../../../../Users/AVIAT/.../photonbptestproject/photonbptestproject.uproject"
    #   → split on "/" → last element → "photonbptestproject.uproject" → strip suffix → "photonbptestproject"
    def _parse_name(path):
        p = path.replace("\\\\\\\\", "/").replace("\\\\", "/")
        last = p.split("/")[-1]
        return last[:-len(".uproject")] if last.endswith(".uproject") else last

    proj_name = _parse_name(proj_file)

    info = {
        "engineVersion": str(unreal.SystemLibrary.get_engine_version()),
        "projectName":   proj_name,
        "projectFile":   proj_file,
        "projectDir":    proj_dir,
        "contentDir":    content_dir,
        "platform":      str(unreal.SystemLibrary.get_platform_name()),
    }
    print("UEOS_INFO:" + json.dumps(info))
except Exception as _e:
    print("UEOS_ERROR:" + str(_e))
"""
        result = await self.execute_python(script)
        raw = self.parse_output(result, "UEOS_INFO:")
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                pass
        err = self.parse_output(result, "UEOS_ERROR:")
        raise RuntimeError(f"get_engine_info failed: {err or result.get('output', '')[:200]}")

    # ──────────────────────────────────────────────────────────────────────
    # Object / property access
    # ──────────────────────────────────────────────────────────────────────

    async def get_property(self, object_path: str, property_name: str) -> Any:
        """Read a property from a UObject via Remote Control."""
        payload = {
            "objectPath":  object_path,
            "access":      "READ_ACCESS",
            "propertyName": property_name
        }
        return await self._put(EP_PROP, payload)

    async def set_property(self, object_path: str, property_name: str, value: Any) -> dict:
        """Write a property to a UObject via Remote Control."""
        payload = {
            "objectPath":   object_path,
            "access":       "WRITE_ACCESS",
            "propertyName": property_name,
            "propertyValue": {property_name: value}
        }
        return await self._put(EP_PROP, payload)

    async def call_function(
        self,
        object_path:   str,
        function_name: str,
        parameters:    dict | None = None,
        transaction:   bool = True
    ) -> dict:
        """Call a Blueprint-callable function on a UObject."""
        payload = {
            "objectPath":        object_path,
            "functionName":      function_name,
            "parameters":        parameters or {},
            "generateTransaction": transaction
        }
        return await self._put(EP_CALL, payload)

    # ──────────────────────────────────────────────────────────────────────
    # Asset registry helpers
    # ──────────────────────────────────────────────────────────────────────

    async def get_assets_in_path(
        self,
        content_path: str,
        recursive:    bool = True,
        filter_class: str | None = None
    ) -> list[dict]:
        """
        Get all assets in a content path.
        Optional filter_class (e.g. "Blueprint", "StaticMesh", "Material").
        """
        class_filter = f", class_names=['{filter_class}']" if filter_class else ""
        script = f"""
import unreal, json
registry = unreal.AssetRegistryHelpers.get_asset_registry()
assets = registry.get_assets_by_path('{content_path}', recursive={str(recursive)}{class_filter})
out = []
for a in assets:
    out.append({{
        "name":    str(a.asset_name),
        "path":    str(a.object_path),
        "class":   str(a.asset_class_path.asset_name),
        "package": str(a.package_name)
    }})
print("UEOS_ASSETS:" + json.dumps(out))
"""
        result = await self.execute_python(script)
        raw    = self.parse_output(result, "UEOS_ASSETS:")
        return json.loads(raw) if raw else []

    async def asset_exists(self, asset_path: str) -> bool:
        """Check whether an asset exists in the Content Browser."""
        script = f"""
import unreal
e = unreal.EditorAssetLibrary.does_asset_exist('{asset_path}')
print("UEOS_EXISTS:" + str(e))
"""
        result = await self.execute_python(script)
        raw    = self.parse_output(result, "UEOS_EXISTS:")
        return raw is not None and "True" in raw

    async def find_assets_by_class(
        self,
        class_name:   str,
        search_path:  str = "/Game",
        recursive:    bool = True
    ) -> list[dict]:
        """Find all assets of a given class in the project."""
        return await self.get_assets_in_path(search_path, recursive=recursive, filter_class=class_name)

    # ──────────────────────────────────────────────────────────────────────
    # Level / actor helpers
    # ──────────────────────────────────────────────────────────────────────

    async def get_selected_actors(self) -> list[dict]:
        """Get all currently selected actors in the UE editor."""
        script = """
import unreal, json
selected = unreal.EditorLevelLibrary.get_selected_level_actors()
out = []
for a in selected:
    out.append({
        "name":     a.get_name(),
        "class":    a.get_class().get_name(),
        "location": list(a.get_actor_location()),
        "label":    a.get_actor_label()
    })
print("UEOS_RESULT:" + json.dumps(out))
"""
        result = await self.execute_python(script)
        raw    = self.parse_output(result, "UEOS_RESULT:")
        return json.loads(raw) if raw else []

    async def get_level_actors_by_class(self, class_name: str) -> list[dict]:
        """Get all actors of a given class in the current level."""
        script = f"""
import unreal, json
all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
out = []
for a in all_actors:
    if a.get_class().get_name() == "{class_name}" or "{class_name}" in a.get_class().get_name():
        out.append({{
            "name":     a.get_name(),
            "label":    a.get_actor_label(),
            "location": list(a.get_actor_location()),
            "class":    a.get_class().get_name()
        }})
print("UEOS_RESULT:" + json.dumps(out))
"""
        result = await self.execute_python(script)
        raw    = self.parse_output(result, "UEOS_RESULT:")
        return json.loads(raw) if raw else []

    async def get_current_level_name(self) -> str:
        """Get the name of the currently open level."""
        script = """
import unreal
world = unreal.EditorLevelLibrary.get_editor_world()
print("UEOS_RESULT:" + world.get_name())
"""
        result = await self.execute_python(script)
        return self.parse_output(result, "UEOS_RESULT:") or "Unknown"

    # ──────────────────────────────────────────────────────────────────────
    # Batch operations
    # ──────────────────────────────────────────────────────────────────────

    async def batch_call(self, requests: list[dict]) -> list[dict]:
        """
        Execute multiple Remote Control object-call requests in a single HTTP roundtrip.
        Each request dict must have: objectPath, functionName, parameters.
        """
        payload = {"requests": requests}
        return await self._put(EP_BATCH, payload)

    async def execute_python_batch(
        self,
        scripts:       list[str],
        stop_on_error: bool = True
    ) -> list[dict]:
        """
        Execute multiple Python scripts sequentially inside UE.
        Returns list of structured result dicts (same shape as execute_python_ex).
        """
        results = []
        for script in scripts:
            try:
                raw = await self.execute_python(script)
                parsed = self._parse_output_ex(raw)
                results.append(parsed)
                if stop_on_error and not parsed["ok"]:
                    break
            except Exception as e:
                results.append({"ok": False, "error": str(e), "result": None})
                if stop_on_error:
                    break
        return results

    # ──────────────────────────────────────────────────────────────────────
    # File execution
    # ──────────────────────────────────────────────────────────────────────

    async def execute_python_file(self, file_path: str) -> dict:
        """
        Execute a Python script file already on disk (accessible to the UE process).
        The file must be readable by the UE editor process — use absolute Windows paths.
        """
        payload = {
            "objectPath":   PY_PLUGIN_PATH,
            "functionName": "ExecutePythonScript",
            "parameters":   {
                "PythonScript": f'exec(open(r"{file_path}", encoding="utf-8").read())'
            }
        }
        # Use Remote Execution for file execution too
        script = f'exec(open(r"{file_path}", encoding="utf-8").read())'
        return await self.execute_python(script)

    # ──────────────────────────────────────────────────────────────────────
    # Connectivity
    # ──────────────────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        """Return True if UE Remote Control HTTP API is reachable (port 30010)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._re.ping)

    async def wait_for_ue(self, timeout: int = 60, poll_interval: float = 2.0) -> bool:
        """
        Block until UE Remote Control becomes available or timeout expires.
        Useful at server startup when UE may still be loading.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if await self.ping():
                return True
            log.info(f"Waiting for UE Remote Control ({int(deadline - time.monotonic())}s left)…")
            await asyncio.sleep(poll_interval)
        return False

    # ──────────────────────────────────────────────────────────────────────
    # UE 5.4 specific convenience scripts
    # ──────────────────────────────────────────────────────────────────────

    async def compile_all_blueprints(self) -> dict:
        """
        Force-compile all Blueprint assets in the project.
        Slow on large projects — use only when needed.
        """
        script = """
import unreal, json
result = unreal.EditorAssetLibrary.consolidate_assets(unreal.load_asset("/Game"), True)
# Proper approach: use KismetEditorUtilities
compiled = []
failed = []
registry = unreal.AssetRegistryHelpers.get_asset_registry()
bps = registry.get_assets_by_class(unreal.TopLevelAssetPath("/Script/Engine", "Blueprint"), True)
for bp_data in bps:
    bp = unreal.EditorAssetLibrary.load_asset(str(bp_data.object_path))
    if bp and isinstance(bp, unreal.Blueprint):
        ok = unreal.KismetEditorUtilities.compile_blueprint(bp)
        (compiled if ok else failed).append(str(bp_data.asset_name))
print("UEOS_RESULT:" + json.dumps({"compiled": len(compiled), "failed": len(failed), "failed_list": failed}))
"""
        result = await self.execute_python(script)
        raw    = self.parse_output(result, "UEOS_RESULT:")
        return json.loads(raw) if raw else {}

    async def save_all_assets(self, path: str = "/Game") -> dict:
        """Save all dirty assets under the given content path."""
        script = f"""
import unreal, json
saved = unreal.EditorAssetLibrary.save_directory("{path}", only_if_is_dirty=True, recursive=True)
print("UEOS_RESULT:" + json.dumps({{"saved": saved, "path": "{path}"}}))
"""
        result = await self.execute_python(script)
        raw    = self.parse_output(result, "UEOS_RESULT:")
        return json.loads(raw) if raw else {}

    async def get_project_stats(self) -> dict:
        """Return asset count, Blueprint count, Material count from the project registry."""
        script = """
import unreal, json
registry = unreal.AssetRegistryHelpers.get_asset_registry()
all_assets = registry.get_assets_by_path("/Game", recursive=True)
counts = {}
for a in all_assets:
    cls = str(a.asset_class_path.asset_name)
    counts[cls] = counts.get(cls, 0) + 1
top = sorted(counts.items(), key=lambda x: -x[1])[:20]
print("UEOS_RESULT:" + json.dumps({
    "total_assets": len(all_assets),
    "by_class":     dict(top)
}))
"""
        result = await self.execute_python(script)
        raw    = self.parse_output(result, "UEOS_RESULT:")
        return json.loads(raw) if raw else {}
