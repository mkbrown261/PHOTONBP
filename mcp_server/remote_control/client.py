"""
Unreal Engine 5.4 Remote Control HTTP Client
Handles all communication with the UE Remote Control API on port 30010
"""

import asyncio
import json
import logging
import aiohttp
from typing import Any, Optional

log = logging.getLogger("ueos.remote_control")


class UnrealRemoteControl:
    """
    HTTP client for Unreal Engine 5.4 Remote Control API.
    Endpoint: http://host:port/remote/...
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 30010):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.timeout = aiohttp.ClientTimeout(total=30)

    # ─────────────────────────────────────────────
    # Core HTTP methods
    # ─────────────────────────────────────────────

    async def _post(self, endpoint: str, payload: dict) -> dict:
        """POST to Remote Control API."""
        url = f"{self.base_url}{endpoint}"
        log.debug(f"POST {url} | {json.dumps(payload)[:200]}")

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.put(url, json=payload) as resp:
                text = await resp.text()
                if resp.status not in (200, 201):
                    raise Exception(f"Remote Control error {resp.status}: {text}")
                return json.loads(text) if text else {}

    async def _put(self, endpoint: str, payload: dict) -> dict:
        """PUT to Remote Control API."""
        url = f"{self.base_url}{endpoint}"
        log.debug(f"PUT {url}")

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.put(url, json=payload) as resp:
                text = await resp.text()
                if resp.status not in (200, 201):
                    raise Exception(f"Remote Control error {resp.status}: {text}")
                return json.loads(text) if text else {}

    async def _get(self, endpoint: str) -> dict:
        """GET from Remote Control API."""
        url = f"{self.base_url}{endpoint}"
        log.debug(f"GET {url}")

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url) as resp:
                text = await resp.text()
                if resp.status not in (200, 201):
                    raise Exception(f"Remote Control error {resp.status}: {text}")
                return json.loads(text) if text else {}

    # ─────────────────────────────────────────────
    # Python Script Execution (most powerful method)
    # ─────────────────────────────────────────────

    async def execute_python(self, script: str) -> dict:
        """
        Execute a Python script inside Unreal Engine editor.
        This is the primary method for complex asset operations.
        Returns stdout output from the script.
        """
        payload = {
            "objectPath": "/Script/PythonScriptPlugin.Default__PythonScriptLibrary",
            "functionName": "ExecutePythonScript",
            "parameters": {
                "PythonScript": script
            }
        }

        try:
            result = await self._put("/remote/object/call", payload)
            log.debug(f"Python execution result: {result}")
            return result
        except Exception as e:
            log.error(f"Python execution failed: {e}")
            raise

    async def execute_python_file(self, file_path: str) -> dict:
        """Execute a Python script file inside UE."""
        payload = {
            "objectPath": "/Script/PythonScriptPlugin.Default__PythonScriptLibrary",
            "functionName": "ExecutePythonScript",
            "parameters": {
                "PythonScript": f'import unreal; exec(open(r"{file_path}").read())'
            }
        }
        return await self._put("/remote/object/call", payload)

    # ─────────────────────────────────────────────
    # Engine Info
    # ─────────────────────────────────────────────

    async def get_engine_info(self) -> dict:
        """Get UE engine version and project info."""
        script = """
import unreal
import json

info = {
    "engineVersion": str(unreal.SystemLibrary.get_engine_version()),
    "projectName": unreal.Paths.get_project_file_path().split('/')[-1].replace('.uproject',''),
    "projectDir": unreal.Paths.project_dir(),
    "contentDir": unreal.Paths.project_content_dir()
}
print("UEOS_INFO:" + json.dumps(info))
"""
        result = await self.execute_python(script)
        # Parse the UEOS_INFO: line from output
        output = result.get("output", "")
        for line in output.split("\n"):
            if line.startswith("UEOS_INFO:"):
                return json.loads(line.replace("UEOS_INFO:", ""))
        return {"engineVersion": "Unknown", "projectName": "Unknown"}

    # ─────────────────────────────────────────────
    # Object Property Access
    # ─────────────────────────────────────────────

    async def get_property(self, object_path: str, property_name: str) -> Any:
        """Get a property value from a UObject."""
        payload = {
            "objectPath": object_path,
            "access": "READ_ACCESS",
            "propertyName": property_name
        }
        return await self._put("/remote/object/property", payload)

    async def set_property(self, object_path: str, property_name: str, value: Any) -> dict:
        """Set a property value on a UObject."""
        payload = {
            "objectPath": object_path,
            "access": "WRITE_ACCESS",
            "propertyName": property_name,
            "propertyValue": {property_name: value}
        }
        return await self._put("/remote/object/property", payload)

    # ─────────────────────────────────────────────
    # Function Calls
    # ─────────────────────────────────────────────

    async def call_function(self, object_path: str, function_name: str, parameters: dict = None) -> dict:
        """Call a function on a UObject."""
        payload = {
            "objectPath": object_path,
            "functionName": function_name,
            "parameters": parameters or {},
            "generateTransaction": True
        }
        return await self._put("/remote/object/call", payload)

    # ─────────────────────────────────────────────
    # Asset Registry
    # ─────────────────────────────────────────────

    async def get_assets_in_path(self, content_path: str, recursive: bool = True) -> list:
        """Get all assets in a content path."""
        script = f"""
import unreal
import json

registry = unreal.AssetRegistryHelpers.get_asset_registry()
assets = registry.get_assets_by_path('{content_path}', recursive={str(recursive)})
result = []
for asset in assets:
    result.append({{
        "name": str(asset.asset_name),
        "path": str(asset.object_path),
        "class": str(asset.asset_class_path.asset_name),
        "package": str(asset.package_name)
    }})
print("UEOS_ASSETS:" + json.dumps(result))
"""
        result = await self.execute_python(script)
        output = result.get("output", "")
        for line in output.split("\n"):
            if line.startswith("UEOS_ASSETS:"):
                return json.loads(line.replace("UEOS_ASSETS:", ""))
        return []

    async def asset_exists(self, asset_path: str) -> bool:
        """Check if an asset exists in the content browser."""
        script = f"""
import unreal
exists = unreal.EditorAssetLibrary.does_asset_exist('{asset_path}')
print("UEOS_EXISTS:" + str(exists))
"""
        result = await self.execute_python(script)
        output = result.get("output", "")
        for line in output.split("\n"):
            if line.startswith("UEOS_EXISTS:"):
                return "True" in line
        return False

    # ─────────────────────────────────────────────
    # Batch Operations
    # ─────────────────────────────────────────────

    async def batch_call(self, requests: list[dict]) -> list[dict]:
        """Execute multiple Remote Control calls in one request."""
        payload = {"requests": requests}
        return await self._put("/remote/batch", payload)

    # ─────────────────────────────────────────────
    # Utility
    # ─────────────────────────────────────────────

    async def ping(self) -> bool:
        """Check if Unreal Remote Control is available."""
        try:
            await self.get_engine_info()
            return True
        except Exception:
            return False

    def parse_output(self, result: dict, prefix: str) -> Optional[str]:
        """
        Parse a specific prefixed line from Python script output.
        e.g. parse_output(result, "UEOS_RESULT:") → the JSON after the prefix
        """
        output = result.get("output", "")
        for line in output.split("\n"):
            if line.startswith(prefix):
                return line.replace(prefix, "").strip()
        return None
