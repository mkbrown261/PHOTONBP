"""
Huanyuan3D API Client (Tencent Cloud)
Image-to-3D model generation
"""

import aiohttp
import logging
import base64
import os

log = logging.getLogger("ueos.huanyuan")

HUANYUAN_BASE = "https://api.hunyuan.cloud.tencent.com/v1"


class HuanyuanClient:

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = HUANYUAN_BASE
        self.timeout = aiohttp.ClientTimeout(total=120)

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def ping(self) -> bool:
        """Check if Huanyuan API is reachable."""
        if not self.api_key or self.api_key == "your_huanyuan_api_key_here":
            return False
        try:
            async with aiohttp.ClientSession(headers=self.headers, timeout=aiohttp.ClientTimeout(total=5)) as s:
                async with s.get(f"{self.base_url}/models") as resp:
                    return resp.status in (200, 404)
        except Exception:
            return False

    async def generate_from_image(
        self,
        image_path: str = None,
        image_url: str = None,
        steps: int = 50,
        seed: int = -1
    ) -> dict:
        """
        Generate a 3D model from an image.
        Returns task_id for polling.
        """
        payload = {
            "model": "hunyuan3d-2",
            "steps": steps,
        }

        if image_path:
            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
            payload["image"] = img_b64
        elif image_url:
            payload["image_url"] = image_url
        else:
            raise ValueError("Must provide image_path or image_url")

        if seed >= 0:
            payload["seed"] = seed

        async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as s:
            async with s.post(f"{self.base_url}/3d/generations", json=payload) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise Exception(f"Huanyuan error {resp.status}: {data}")
                return {
                    "task_id": data.get("id") or data.get("task_id"),
                    "status": data.get("status", "queued")
                }

    async def get_task(self, task_id: str) -> dict:
        """Get generation task status."""
        async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as s:
            async with s.get(f"{self.base_url}/3d/generations/{task_id}") as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise Exception(f"Huanyuan get_task error {resp.status}: {data}")
                return data

    async def download_model(self, task_id: str, output_dir: str) -> str:
        """Download completed model."""
        task = await self.get_task(task_id)
        model_url = task.get("output", {}).get("model_url") or task.get("model_url")

        if not model_url:
            raise Exception(f"No model URL in task: {task}")

        os.makedirs(output_dir, exist_ok=True)
        local_path = os.path.join(output_dir, f"huanyuan_{task_id}.glb")

        async with aiohttp.ClientSession() as s:
            async with s.get(model_url) as resp:
                with open(local_path, "wb") as f:
                    f.write(await resp.read())

        log.info(f"Downloaded Huanyuan model: {local_path}")
        return local_path
