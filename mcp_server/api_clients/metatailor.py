"""
MetaTailor API Client
Auto-rigging, clothing simulation, character customization
"""

import aiohttp
import logging
import os

log = logging.getLogger("ueos.metatailor")

METATAILOR_BASE = "https://api.metatailor.io/v1"


class MetaTailorClient:

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = METATAILOR_BASE
        self.timeout = aiohttp.ClientTimeout(total=120)

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def ping(self) -> bool:
        """Check if MetaTailor API is reachable."""
        if not self.api_key or self.api_key == "your_metatailor_api_key_here":
            return False
        try:
            async with aiohttp.ClientSession(headers=self.headers, timeout=aiohttp.ClientTimeout(total=5)) as s:
                async with s.get(f"{self.base_url}/ping") as resp:
                    return resp.status in (200, 404)
        except Exception:
            return False

    async def rig_character(
        self,
        mesh_path: str = None,
        mesh_url: str = None,
        add_clothing: bool = False,
        clothing_description: str = ""
    ) -> dict:
        """
        Send a character mesh to MetaTailor for auto-rigging.
        Returns task_id.
        """
        import aiohttp as _aiohttp

        if mesh_path:
            # Upload the mesh file
            form = _aiohttp.FormData()
            with open(mesh_path, "rb") as f:
                ext = os.path.splitext(mesh_path)[1]
                form.add_field("file", f.read(), filename=f"character{ext}")

            if add_clothing and clothing_description:
                form.add_field("clothing", clothing_description)

            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with aiohttp.ClientSession(timeout=self.timeout) as s:
                async with s.post(f"{self.base_url}/rig", data=form, headers=headers) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        raise Exception(f"MetaTailor rig error {resp.status}: {data}")
                    return {
                        "task_id": data.get("task_id") or data.get("id"),
                        "status": data.get("status", "queued")
                    }

        elif mesh_url:
            payload = {
                "mesh_url": mesh_url,
                "add_clothing": add_clothing,
                "clothing_description": clothing_description
            }
            async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as s:
                async with s.post(f"{self.base_url}/rig", json=payload) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        raise Exception(f"MetaTailor rig error {resp.status}: {data}")
                    return {
                        "task_id": data.get("task_id") or data.get("id"),
                        "status": data.get("status", "queued")
                    }
        else:
            raise ValueError("Must provide mesh_path or mesh_url")

    async def get_task(self, task_id: str) -> dict:
        """Get rigging task status."""
        async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as s:
            async with s.get(f"{self.base_url}/tasks/{task_id}") as resp:
                data = await resp.json()
                return data

    async def download_result(self, task_id: str, output_dir: str) -> str:
        """Download rigged character FBX."""
        task = await self.get_task(task_id)
        download_url = task.get("result", {}).get("fbx_url") or task.get("download_url")

        if not download_url:
            raise Exception(f"No download URL: {task}")

        os.makedirs(output_dir, exist_ok=True)
        local_path = os.path.join(output_dir, f"metatailor_{task_id}.fbx")

        async with aiohttp.ClientSession() as s:
            async with s.get(download_url) as resp:
                with open(local_path, "wb") as f:
                    f.write(await resp.read())

        log.info(f"Downloaded MetaTailor result: {local_path}")
        return local_path
