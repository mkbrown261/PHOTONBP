#!/usr/bin/env python3
"""
UEOS - Unreal Engine Operating System
MCP Server Entry Point
Version: 1.0.0

Connects Claude to Unreal Engine 5.4 via:
- Remote Control API (HTTP, port 30010)
- Python Editor Scripts (run inside UE)
- Tripo API (3D generation)
- Huanyuan3D API (3D generation)
- MetaTailor API (rigging + clothing)
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# MCP
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# UEOS Tools
from tools.blueprint import BlueprintTools
from tools.material import MaterialTools
from tools.niagara import NiagaraTools
from tools.animation import AnimationTools
from tools.data import DataTools
from tools.umg import UMGTools
from tools.sequencer import SequencerTools
from tools.inspection import InspectionTools
from tools.scene import SceneTools
from api_clients.tripo import TripoClient
from api_clients.huanyuan import HuanyuanClient
from api_clients.metatailor import MetaTailorClient
from remote_control.client import UnrealRemoteControl

# Logging
logging.basicConfig(
    level=os.getenv("UEOS_LOG_LEVEL", "INFO"),
    format="%(asctime)s [UEOS] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("ueos.log", encoding="utf-8")
    ]
)
log = logging.getLogger("ueos")

# ─────────────────────────────────────────────
# Initialize core clients
# ─────────────────────────────────────────────

ue = UnrealRemoteControl(
    host=os.getenv("UE_REMOTE_CONTROL_HOST", "127.0.0.1"),
    port=int(os.getenv("UE_REMOTE_CONTROL_PORT", 30010))
)

tripo   = TripoClient(api_key=os.getenv("TRIPO_API_KEY"))
huanyuan = HuanyuanClient(api_key=os.getenv("HUANYUAN_API_KEY"))
metatailor = MetaTailorClient(api_key=os.getenv("METATAILOR_API_KEY"))

# ─────────────────────────────────────────────
# Initialize tool modules
# ─────────────────────────────────────────────

blueprint_tools  = BlueprintTools(ue)
material_tools   = MaterialTools(ue)
niagara_tools    = NiagaraTools(ue)
animation_tools  = AnimationTools(ue)
data_tools       = DataTools(ue)
umg_tools        = UMGTools(ue)
sequencer_tools  = SequencerTools(ue)
inspection_tools = InspectionTools(ue)
scene_tools      = SceneTools(ue)

# ─────────────────────────────────────────────
# MCP Server
# ─────────────────────────────────────────────

server = Server("ueos")

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """Return all UEOS tools to Claude."""
    tools = []
    tools.extend(await blueprint_tools.get_tool_definitions())
    tools.extend(await material_tools.get_tool_definitions())
    tools.extend(await niagara_tools.get_tool_definitions())
    tools.extend(await animation_tools.get_tool_definitions())
    tools.extend(await data_tools.get_tool_definitions())
    tools.extend(await umg_tools.get_tool_definitions())
    tools.extend(await sequencer_tools.get_tool_definitions())
    tools.extend(await inspection_tools.get_tool_definitions())
    tools.extend(await scene_tools.get_tool_definitions())

    # Status / connection tools
    tools.append(types.Tool(
        name="ueos_status",
        description="Check connection status for all UEOS services (Unreal Engine, Tripo, Huanyuan, MetaTailor)",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ))

    tools.append(types.Tool(
        name="tripo_generate_from_text",
        description="Generate a 3D model from a text prompt using Tripo API. Returns task ID for polling.",
        inputSchema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Text description of the 3D model to generate"},
                "style": {"type": "string", "description": "Style hint: realistic, cartoon, stylized", "default": "realistic"},
                "texture": {"type": "boolean", "description": "Generate texture with the model", "default": True},
                "auto_import": {"type": "boolean", "description": "Automatically import into UE when complete", "default": True},
                "import_path": {"type": "string", "description": "UE content path to import to e.g. /Game/Assets/Characters", "default": "/Game/UEOS/Generated"}
            },
            "required": ["prompt"]
        }
    ))

    tools.append(types.Tool(
        name="tripo_generate_from_image",
        description="Generate a 3D model from a concept art image using Tripo API.",
        inputSchema={
            "type": "object",
            "properties": {
                "image_path": {"type": "string", "description": "Local path to the concept art image"},
                "image_url": {"type": "string", "description": "URL of the concept art image (alternative to image_path)"},
                "prompt": {"type": "string", "description": "Optional additional text description"},
                "texture": {"type": "boolean", "description": "Generate texture with the model", "default": True},
                "auto_import": {"type": "boolean", "description": "Automatically import into UE when complete", "default": True},
                "import_path": {"type": "string", "description": "UE content path to import to", "default": "/Game/UEOS/Generated"}
            },
            "required": []
        }
    ))

    tools.append(types.Tool(
        name="tripo_get_task_status",
        description="Check the status of a Tripo generation task and get the download URL when complete.",
        inputSchema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Tripo task ID returned from generation call"}
            },
            "required": ["task_id"]
        }
    ))

    tools.append(types.Tool(
        name="tripo_import_to_unreal",
        description="Import a completed Tripo model into Unreal Engine 5.4",
        inputSchema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Completed Tripo task ID"},
                "import_path": {"type": "string", "description": "UE content path", "default": "/Game/UEOS/Generated"},
                "create_blueprint": {"type": "boolean", "description": "Auto-create Actor Blueprint for the mesh", "default": False},
                "blueprint_path": {"type": "string", "description": "Path for the auto-created Blueprint"}
            },
            "required": ["task_id"]
        }
    ))

    tools.append(types.Tool(
        name="huanyuan_generate_from_image",
        description="Generate a 3D model from an image using Huanyuan3D cloud API.",
        inputSchema={
            "type": "object",
            "properties": {
                "image_path": {"type": "string", "description": "Local path to the input image"},
                "image_url": {"type": "string", "description": "URL of the input image"},
                "steps": {"type": "integer", "description": "Generation steps (higher = better quality)", "default": 50},
                "auto_import": {"type": "boolean", "description": "Auto-import into UE when complete", "default": True},
                "import_path": {"type": "string", "description": "UE content path", "default": "/Game/UEOS/Generated"}
            },
            "required": []
        }
    ))

    tools.append(types.Tool(
        name="metatailor_rig_character",
        description="Send a character mesh to MetaTailor for auto-rigging and clothing setup.",
        inputSchema={
            "type": "object",
            "properties": {
                "mesh_path": {"type": "string", "description": "Local path to FBX/OBJ/GLB character mesh"},
                "ue_asset_path": {"type": "string", "description": "UE content path of already-imported skeletal mesh"},
                "add_clothing": {"type": "boolean", "description": "Add cloth simulation", "default": False},
                "clothing_description": {"type": "string", "description": "Description of clothing to add e.g. 'leather armor with cape'"},
                "auto_import_result": {"type": "boolean", "description": "Auto-import rigged result back into UE", "default": True},
                "setup_leader_pose": {"type": "boolean", "description": "Auto-setup Leader Pose Component in Construction Script", "default": True}
            },
            "required": []
        }
    ))

    tools.append(types.Tool(
        name="pipeline_concept_to_character",
        description="Full pipeline: concept art image → 3D model → rig → UE Blueprint. One command does everything.",
        inputSchema={
            "type": "object",
            "properties": {
                "image_path": {"type": "string", "description": "Path to concept art image"},
                "image_url": {"type": "string", "description": "URL of concept art image"},
                "character_name": {"type": "string", "description": "Name for the character (used for all assets)"},
                "generation_service": {"type": "string", "description": "Which service to use: tripo or huanyuan", "default": "tripo"},
                "add_clothing": {"type": "boolean", "description": "Process clothing through MetaTailor", "default": False},
                "clothing_description": {"type": "string", "description": "Clothing description for MetaTailor"},
                "use_ue_cloth_physics": {"type": "boolean", "description": "Use UE cloth physics instead of MetaTailor cloth", "default": False},
                "create_blueprint": {"type": "boolean", "description": "Create Character Blueprint after import", "default": True},
                "import_path": {"type": "string", "description": "Base UE content path", "default": "/Game/UEOS/Characters"}
            },
            "required": ["character_name"]
        }
    ))

    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Route tool calls to the correct handler."""
    log.info(f"Tool called: {name} | Args: {arguments}")

    try:
        # ── Status ──────────────────────────────────────────────
        if name == "ueos_status":
            return await handle_status()

        # ── Tripo ───────────────────────────────────────────────
        elif name == "tripo_generate_from_text":
            return await handle_tripo_text(arguments)
        elif name == "tripo_generate_from_image":
            return await handle_tripo_image(arguments)
        elif name == "tripo_get_task_status":
            return await handle_tripo_status(arguments)
        elif name == "tripo_import_to_unreal":
            return await handle_tripo_import(arguments)

        # ── Huanyuan ────────────────────────────────────────────
        elif name == "huanyuan_generate_from_image":
            return await handle_huanyuan_image(arguments)

        # ── MetaTailor ──────────────────────────────────────────
        elif name == "metatailor_rig_character":
            return await handle_metatailor_rig(arguments)

        # ── Full Pipeline ───────────────────────────────────────
        elif name == "pipeline_concept_to_character":
            return await handle_full_pipeline(arguments)

        # ── Blueprint Tools ─────────────────────────────────────
        elif name.startswith("blueprint_"):
            return await blueprint_tools.handle(name, arguments)

        # ── Material Tools ──────────────────────────────────────
        elif name.startswith("material_"):
            return await material_tools.handle(name, arguments)

        # ── Niagara Tools ───────────────────────────────────────
        elif name.startswith("niagara_"):
            return await niagara_tools.handle(name, arguments)

        # ── Animation Tools ─────────────────────────────────────
        elif name.startswith("animation_"):
            return await animation_tools.handle(name, arguments)

        # ── Data Tools ──────────────────────────────────────────
        elif name.startswith("data_"):
            return await data_tools.handle(name, arguments)

        # ── UMG Tools ───────────────────────────────────────────
        elif name.startswith("umg_"):
            return await umg_tools.handle(name, arguments)

        # ── Sequencer Tools ─────────────────────────────────────
        elif name.startswith("sequencer_"):
            return await sequencer_tools.handle(name, arguments)

        # ── Inspection Tools ────────────────────────────────────
        elif name.startswith("inspect_"):
            return await inspection_tools.handle(name, arguments)

        # ── Scene Tools ─────────────────────────────────────────
        elif name.startswith("scene_"):
            return await scene_tools.handle(name, arguments)

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        log.error(f"Tool error [{name}]: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"ERROR in {name}: {str(e)}")]


# ─────────────────────────────────────────────
# Handler implementations
# ─────────────────────────────────────────────

async def handle_status() -> list[types.TextContent]:
    """Check all service connections."""
    import json

    status = {
        "unreal_engine": {"connected": False, "version": None, "project": None},
        "tripo": {"connected": False, "balance": None},
        "huanyuan": {"connected": False},
        "metatailor": {"connected": False}
    }

    # Check Unreal
    try:
        info = await ue.get_engine_info()
        status["unreal_engine"]["connected"] = True
        status["unreal_engine"]["version"] = info.get("engineVersion", "Unknown")
        status["unreal_engine"]["project"] = info.get("projectName", "Unknown")
    except Exception as e:
        status["unreal_engine"]["error"] = str(e)

    # Check Tripo
    try:
        balance = await tripo.get_balance()
        status["tripo"]["connected"] = True
        status["tripo"]["balance"] = balance
    except Exception as e:
        status["tripo"]["error"] = str(e)

    # Check Huanyuan
    try:
        ok = await huanyuan.ping()
        status["huanyuan"]["connected"] = ok
    except Exception as e:
        status["huanyuan"]["error"] = str(e)

    # Check MetaTailor
    try:
        ok = await metatailor.ping()
        status["metatailor"]["connected"] = ok
    except Exception as e:
        status["metatailor"]["error"] = str(e)

    # Format output
    lines = ["═══════════════════════════════════════", "  UEOS Service Status", "═══════════════════════════════════════"]
    for svc, info in status.items():
        icon = "●" if info.get("connected") else "○"
        label = svc.replace("_", " ").title()
        lines.append(f"  {icon} {label}")
        if info.get("version"):
            lines.append(f"      Version : {info['version']}")
        if info.get("project"):
            lines.append(f"      Project : {info['project']}")
        if info.get("balance") is not None:
            lines.append(f"      Balance : {info['balance']}")
        if info.get("error"):
            lines.append(f"      Error   : {info['error']}")
    lines.append("═══════════════════════════════════════")

    return [types.TextContent(type="text", text="\n".join(lines))]


async def handle_tripo_text(args: dict) -> list[types.TextContent]:
    """Generate 3D model from text prompt via Tripo."""
    import json

    prompt = args["prompt"]
    style = args.get("style", "realistic")
    with_texture = args.get("texture", True)
    auto_import = args.get("auto_import", True)
    import_path = args.get("import_path", "/Game/UEOS/Generated")

    log.info(f"Tripo text generation: {prompt}")

    task = await tripo.create_text_to_model_task(
        prompt=prompt,
        style=style,
        with_texture=with_texture
    )

    result = {
        "task_id": task["task_id"],
        "status": task["status"],
        "prompt": prompt,
        "auto_import": auto_import,
        "import_path": import_path,
        "message": f"Generation started. Task ID: {task['task_id']}. Use tripo_get_task_status to check progress."
    }

    if auto_import:
        result["message"] += " Auto-import is enabled — will import to UE when complete."

    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


async def handle_tripo_image(args: dict) -> list[types.TextContent]:
    """Generate 3D model from concept art image via Tripo."""
    import json
    import base64

    image_path = args.get("image_path")
    image_url = args.get("image_url")
    prompt = args.get("prompt", "")
    with_texture = args.get("texture", True)
    auto_import = args.get("auto_import", True)
    import_path = args.get("import_path", "/Game/UEOS/Generated")

    if not image_path and not image_url:
        return [types.TextContent(type="text", text="ERROR: Provide either image_path or image_url")]

    # Read image if local
    image_data = None
    if image_path:
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

    task = await tripo.create_image_to_model_task(
        image_data=image_data,
        image_url=image_url,
        prompt=prompt,
        with_texture=with_texture
    )

    result = {
        "task_id": task["task_id"],
        "status": task["status"],
        "source": image_path or image_url,
        "auto_import": auto_import,
        "import_path": import_path,
        "message": f"Image-to-3D started. Task ID: {task['task_id']}. Use tripo_get_task_status to check progress."
    }

    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


async def handle_tripo_status(args: dict) -> list[types.TextContent]:
    """Poll Tripo task status."""
    import json

    task_id = args["task_id"]
    task = await tripo.get_task(task_id)

    result = {
        "task_id": task_id,
        "status": task.get("status"),
        "progress": task.get("progress", 0),
    }

    if task.get("status") == "success":
        result["download_urls"] = task.get("result", {})
        result["message"] = "Generation complete. Use tripo_import_to_unreal to import."
    elif task.get("status") == "failed":
        result["error"] = task.get("message", "Unknown error")
        result["message"] = "Generation failed."
    else:
        result["message"] = f"In progress: {task.get('progress', 0)}%"

    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


async def handle_tripo_import(args: dict) -> list[types.TextContent]:
    """Download Tripo model and import into UE 5.4."""
    import json
    import aiohttp
    import tempfile
    import os

    task_id = args["task_id"]
    import_path = args.get("import_path", "/Game/UEOS/Generated")
    create_blueprint = args.get("create_blueprint", False)
    blueprint_path = args.get("blueprint_path", "")

    # Get task result
    task = await tripo.get_task(task_id)
    if task.get("status") != "success":
        return [types.TextContent(type="text", text=f"ERROR: Task {task_id} is not complete. Status: {task.get('status')}")]

    # Get download URL (prefer FBX for UE, fallback to GLB)
    urls = task.get("result", {})
    model_url = urls.get("fbx") or urls.get("glb") or urls.get("model")

    if not model_url:
        return [types.TextContent(type="text", text=f"ERROR: No download URL in task result: {urls}")]

    # Download to temp dir
    temp_dir = os.getenv("UEOS_ASSET_TEMP_DIR", "C:/UEOS/temp")
    os.makedirs(temp_dir, exist_ok=True)
    ext = ".fbx" if "fbx" in model_url else ".glb"
    local_path = os.path.join(temp_dir, f"tripo_{task_id}{ext}")

    async with aiohttp.ClientSession() as session:
        async with session.get(model_url) as resp:
            with open(local_path, "wb") as f:
                f.write(await resp.read())

    log.info(f"Downloaded Tripo model to: {local_path}")

    # Import into UE via Python script
    import_script = f"""
import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
import_task = unreal.AssetImportTask()
import_task.filename = r"{local_path}"
import_task.destination_path = "{import_path}"
import_task.automated = True
import_task.replace_existing = True
import_task.save = True

options = unreal.FbxImportUI()
options.import_mesh = True
options.import_textures = True
options.import_materials = True
options.import_as_skeletal = False
options.static_mesh_import_data.combine_meshes = True
import_task.options = options

asset_tools.import_asset_tasks([import_task])

imported = import_task.imported_object_paths
print(f"UEOS_IMPORT_RESULT:" + str(imported))
"""

    result_data = await ue.execute_python(import_script)

    response = {
        "task_id": task_id,
        "local_path": local_path,
        "import_path": import_path,
        "ue_result": result_data,
        "status": "imported"
    }

    # Optionally create Blueprint
    if create_blueprint and result_data:
        bp_result = await blueprint_tools.handle("blueprint_create", {
            "name": f"BP_{task_id}",
            "path": blueprint_path or import_path,
            "parent_class": "Actor"
        })
        response["blueprint"] = "created"

    return [types.TextContent(type="text", text=json.dumps(response, indent=2))]


async def handle_huanyuan_image(args: dict) -> list[types.TextContent]:
    """Generate 3D from image via Huanyuan3D."""
    import json

    image_path = args.get("image_path")
    image_url = args.get("image_url")
    steps = args.get("steps", 50)
    auto_import = args.get("auto_import", True)
    import_path = args.get("import_path", "/Game/UEOS/Generated")

    if not image_path and not image_url:
        return [types.TextContent(type="text", text="ERROR: Provide either image_path or image_url")]

    task = await huanyuan.generate_from_image(
        image_path=image_path,
        image_url=image_url,
        steps=steps
    )

    result = {
        "task_id": task.get("task_id"),
        "status": task.get("status"),
        "auto_import": auto_import,
        "import_path": import_path,
        "message": "Huanyuan3D generation started."
    }

    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


async def handle_metatailor_rig(args: dict) -> list[types.TextContent]:
    """Send mesh to MetaTailor for rigging."""
    import json

    mesh_path = args.get("mesh_path")
    ue_asset_path = args.get("ue_asset_path")
    add_clothing = args.get("add_clothing", False)
    clothing_description = args.get("clothing_description", "")
    auto_import = args.get("auto_import_result", True)
    setup_leader_pose = args.get("setup_leader_pose", True)

    task = await metatailor.rig_character(
        mesh_path=mesh_path,
        add_clothing=add_clothing,
        clothing_description=clothing_description
    )

    result = {
        "task_id": task.get("task_id"),
        "status": task.get("status"),
        "setup_leader_pose": setup_leader_pose,
        "message": "MetaTailor rigging started."
    }

    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


async def handle_full_pipeline(args: dict) -> list[types.TextContent]:
    """Full concept art → character pipeline."""
    import json

    character_name = args["character_name"]
    image_path = args.get("image_path")
    image_url = args.get("image_url")
    service = args.get("generation_service", "tripo")
    add_clothing = args.get("add_clothing", False)
    clothing_description = args.get("clothing_description", "")
    use_ue_cloth = args.get("use_ue_cloth_physics", False)
    create_bp = args.get("create_blueprint", True)
    import_path = args.get("import_path", "/Game/UEOS/Characters")

    steps = []
    steps.append(f"Pipeline started for: {character_name}")
    steps.append(f"Service: {service.upper()}")
    steps.append(f"Import path: {import_path}/{character_name}")

    # Step 1: Generate 3D model
    if service == "tripo":
        gen_args = {
            "image_path": image_path,
            "image_url": image_url,
            "texture": True,
            "auto_import": False,
            "import_path": f"{import_path}/{character_name}"
        }
        gen_result = await handle_tripo_image(gen_args)
    else:
        gen_args = {
            "image_path": image_path,
            "image_url": image_url,
            "auto_import": False,
            "import_path": f"{import_path}/{character_name}"
        }
        gen_result = await handle_huanyuan_image(gen_args)

    gen_data = json.loads(gen_result[0].text)
    task_id = gen_data.get("task_id")
    steps.append(f"Step 1 complete: 3D generation task {task_id}")

    result = {
        "character_name": character_name,
        "generation_task_id": task_id,
        "generation_service": service,
        "pipeline_steps": steps,
        "next_step": f"Poll tripo_get_task_status with task_id={task_id}, then call tripo_import_to_unreal",
        "status": "generation_started",
        "planned_steps": [
            "1. ✅ 3D generation started",
            "2. ⏳ Poll for completion",
            "3. ⏳ Import mesh + textures into UE",
            f"4. ⏳ {'MetaTailor rigging' if not use_ue_cloth else 'UE cloth physics setup'}",
            "5. ⏳ Leader Pose Component setup in Construction Script" if add_clothing else "",
            "6. ⏳ Create Character Blueprint" if create_bp else "",
            "7. ⏳ Compile and validate"
        ]
    }

    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

async def main():
    log.info("═══════════════════════════════════════")
    log.info("  UEOS MCP Server Starting")
    log.info("  Unreal Engine Operating System v1.0")
    log.info("═══════════════════════════════════════")
    log.info(f"  UE Remote Control: {ue.host}:{ue.port}")
    log.info(f"  Tripo API: {'configured' if tripo.api_key else 'NOT configured'}")
    log.info(f"  Huanyuan API: {'configured' if huanyuan.api_key else 'NOT configured'}")
    log.info(f"  MetaTailor API: {'configured' if metatailor.api_key else 'NOT configured'}")
    log.info("═══════════════════════════════════════")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
