"""
Tripo API Client
REST API for 3D model generation (text-to-3D, image-to-3D, texture generation)
Docs: https://platform.tripo3d.ai/docs/introduction
"""

import asyncio
import base64
import json
import logging
import os
import aiohttp
from pathlib import Path

log = logging.getLogger("ueos.tripo")

TRIPO_BASE = "https://api.tripo3d.ai/v2/openapi"


class TripoClient:

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = TRIPO_BASE
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.timeout = aiohttp.ClientTimeout(total=60)

    # ─────────────────────────────────────────────
    # Account
    # ─────────────────────────────────────────────

    async def get_balance(self) -> dict:
        """Get account balance / credits."""
        async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as s:
            async with s.get(f"{self.base_url}/user/balance") as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise Exception(f"Tripo balance error {resp.status}: {data}")
                return data.get("data", {})

    # ─────────────────────────────────────────────
    # Text to 3D Model
    # ─────────────────────────────────────────────

    async def create_text_to_model_task(
        self,
        prompt: str,
        style: str = "realistic",
        with_texture: bool = True,
        pbr: bool = True
    ) -> dict:
        """
        Create a text-to-3D model generation task.
        Returns task_id for polling.
        """
        payload = {
            "type": "text_to_model",
            "prompt": prompt,
            "model_version": "v2.5-20250123",
            "texture": with_texture,
            "pbr": pbr
        }

        if style and style != "realistic":
            payload["style"] = style

        log.info(f"Tripo text_to_model: {prompt[:80]}")

        async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as s:
            async with s.post(f"{self.base_url}/task", json=payload) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise Exception(f"Tripo text_to_model error {resp.status}: {data}")
                return {
                    "task_id": data["data"]["task_id"],
                    "status": data["data"].get("status", "queued")
                }

    # ─────────────────────────────────────────────
    # Image to 3D Model
    # ─────────────────────────────────────────────

    async def create_image_to_model_task(
        self,
        image_data: str = None,
        image_url: str = None,
        prompt: str = "",
        with_texture: bool = True,
        pbr: bool = True
    ) -> dict:
        """
        Create an image-to-3D model generation task.
        Provide either base64 image_data or image_url.
        """
        if not image_data and not image_url:
            raise ValueError("Must provide image_data (base64) or image_url")

        # Upload image first if base64
        file_token = None
        if image_data:
            file_token = await self._upload_image(image_data)

        payload = {
            "type": "image_to_model",
            "model_version": "v2.5-20250123",
            "texture": with_texture,
            "pbr": pbr
        }

        if file_token:
            payload["file"] = {"type": "png", "file_token": file_token}
        elif image_url:
            payload["file"] = {"type": "png", "url": image_url}

        if prompt:
            payload["prompt"] = prompt

        log.info(f"Tripo image_to_model: {'base64 image' if image_data else image_url}")

        async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as s:
            async with s.post(f"{self.base_url}/task", json=payload) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise Exception(f"Tripo image_to_model error {resp.status}: {data}")
                return {
                    "task_id": data["data"]["task_id"],
                    "status": data["data"].get("status", "queued")
                }

    # ─────────────────────────────────────────────
    # Texture Generation
    # ─────────────────────────────────────────────

    async def create_texture_task(
        self,
        original_task_id: str,
        prompt: str = "",
        style: str = "realistic"
    ) -> dict:
        """
        Generate/regenerate texture for an existing model task.
        """
        payload = {
            "type": "texture_model",
            "original_model_task_id": original_task_id,
            "prompt": prompt,
            "style": style
        }

        async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as s:
            async with s.post(f"{self.base_url}/task", json=payload) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise Exception(f"Tripo texture error {resp.status}: {data}")
                return {
                    "task_id": data["data"]["task_id"],
                    "status": data["data"].get("status", "queued")
                }

    # ─────────────────────────────────────────────
    # Stylize Model
    # ─────────────────────────────────────────────

    async def create_stylize_task(
        self,
        original_task_id: str,
        style: str
    ) -> dict:
        """Apply a style to an existing model."""
        payload = {
            "type": "stylize_model",
            "original_model_task_id": original_task_id,
            "style": style
        }

        async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as s:
            async with s.post(f"{self.base_url}/task", json=payload) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise Exception(f"Tripo stylize error {resp.status}: {data}")
                return {
                    "task_id": data["data"]["task_id"],
                    "status": data["data"].get("status", "queued")
                }

    # ─────────────────────────────────────────────
    # Task Management
    # ─────────────────────────────────────────────

    async def get_task(self, task_id: str) -> dict:
        """Get task status and result."""
        async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as s:
            async with s.get(f"{self.base_url}/task/{task_id}") as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise Exception(f"Tripo get_task error {resp.status}: {data}")
                return data.get("data", {})

    async def wait_for_task(
        self,
        task_id: str,
        poll_interval: float = 3.0,
        timeout: float = 300.0
    ) -> dict:
        """
        Poll a task until complete or failed.
        Returns the final task data.
        """
        elapsed = 0.0
        while elapsed < timeout:
            task = await self.get_task(task_id)
            status = task.get("status", "")

            log.info(f"Tripo task {task_id}: {status} ({task.get('progress', 0)}%)")

            if status == "success":
                return task
            elif status in ("failed", "cancelled", "error"):
                raise Exception(f"Tripo task {task_id} failed: {task.get('message', 'Unknown')}")

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"Tripo task {task_id} timed out after {timeout}s")

    # ─────────────────────────────────────────────
    # Download
    # ─────────────────────────────────────────────

    async def download_model(
        self,
        task_id: str,
        output_dir: str,
        prefer_format: str = "fbx"
    ) -> str:
        """
        Download a completed model to local disk.
        Returns the local file path.
        """
        task = await self.get_task(task_id)
        if task.get("status") != "success":
            raise Exception(f"Task {task_id} not complete: {task.get('status')}")

        result = task.get("result", {})

        # Format preference order for UE
        format_priority = [prefer_format, "fbx", "glb", "obj"]
        model_url = None
        chosen_ext = None

        for fmt in format_priority:
            if fmt in result:
                model_url = result[fmt].get("url") if isinstance(result[fmt], dict) else result[fmt]
                chosen_ext = fmt
                break

        if not model_url:
            raise Exception(f"No downloadable model URL in task result: {list(result.keys())}")

        os.makedirs(output_dir, exist_ok=True)
        local_path = os.path.join(output_dir, f"tripo_{task_id}.{chosen_ext}")

        async with aiohttp.ClientSession() as s:
            async with s.get(model_url) as resp:
                if resp.status != 200:
                    raise Exception(f"Download failed {resp.status}")
                with open(local_path, "wb") as f:
                    f.write(await resp.read())

        log.info(f"Downloaded Tripo model: {local_path} ({os.path.getsize(local_path)} bytes)")
        return local_path

    async def download_textures(self, task_id: str, output_dir: str) -> list[str]:
        """Download all textures from a completed task."""
        task = await self.get_task(task_id)
        result = task.get("result", {})

        downloaded = []
        texture_keys = ["base_color", "metallic", "roughness", "normal", "albedo"]

        for key in texture_keys:
            if key in result:
                url = result[key].get("url") if isinstance(result[key], dict) else result[key]
                if url:
                    local_path = os.path.join(output_dir, f"tripo_{task_id}_{key}.png")
                    async with aiohttp.ClientSession() as s:
                        async with s.get(url) as resp:
                            if resp.status == 200:
                                with open(local_path, "wb") as f:
                                    f.write(await resp.read())
                                downloaded.append(local_path)

        return downloaded

    # ─────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────

    async def _upload_image(self, image_data: str) -> str:
        """Upload a base64 image to Tripo and get a file_token."""
        # Decode base64 to bytes
        image_bytes = base64.b64decode(image_data)

        form = aiohttp.FormData()
        form.add_field("file", image_bytes, filename="image.png", content_type="image/png")

        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with aiohttp.ClientSession(timeout=self.timeout) as s:
            async with s.post(f"{self.base_url}/upload", data=form, headers=headers) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise Exception(f"Tripo upload error {resp.status}: {data}")
                return data["data"]["image_token"]
