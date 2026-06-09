# UEOS — Unreal Engine Operating System

**Version 2.0.0 — Phase 2 Complete**

AI-driven Unreal Engine 5.4 development system. Claude controls the UE editor
through 105 MCP tools via the Remote Control API. Zero C++. Pure Python.

---

## Quick Start

```bash
# 1. Copy environment config
cp .env.example .env
# Edit .env — add your Tripo API key

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run setup (installs UE plugin config, creates temp dirs)
python setup/install.py

# 4. Verify all connections
python setup/verify.py

# 5. Point Claude Desktop at this server
# Edit claude_desktop_config.json path in config/claude_desktop_config.json
```

**In Unreal Engine 5.4:**
- Enable: Remote Control API plugin
- Enable: Python Editor Script Plugin
- Start the server (Remote Control API auto-starts on port 30010)

---

## Architecture

```
Claude Desktop
     │
     │ MCP (stdio)
     ▼
mcp_server/server.py          ← 105 tools registered
     │
     ├── tools/blueprint.py   ← 17 tools: graph editing, compile, validate
     ├── tools/material.py    ← 14 tools: PBR, dissolve, hologram, Substrate
     ├── tools/niagara.py     ← 20 tools: fire, explosion, trail, magic
     ├── tools/inspection.py  ← 12 tools: deep JSON inspection of any asset
     ├── tools/scene.py       ← 16 tools: lights, fog, PPV, camera, actors
     ├── tools/data.py        ← 15 tools: Structs, Enums, DataTables, Curves ← NEW
     ├── tools/animation.py   ← stub (Phase 3)
     ├── tools/umg.py         ← stub (Phase 4)
     └── tools/sequencer.py   ← stub (Phase 4)
     │
     ├── remote_control/client.py  ← UE 5.4 HTTP client w/ retry logic
     ├── api_clients/tripo.py      ← Tripo REST API
     ├── api_clients/huanyuan.py   ← Huanyuan3D
     └── api_clients/metatailor.py ← MetaTailor rigging
     │
     │ HTTP port 30010
     ▼
Unreal Engine 5.4
     └── Python Editor Script Plugin
```

---

## Tool Inventory

### 🔵 Blueprint Tools (17)

| Tool | Description |
|------|-------------|
| `blueprint_create` | Create Blueprint asset with any parent class |
| `blueprint_add_variable` | Add typed variable (bool/int/float/string/vector/object/struct/enum…) |
| `blueprint_add_function` | Add a named function to a Blueprint |
| `blueprint_add_node` | Add any K2Node to a Blueprint graph |
| `blueprint_connect_pins` | Wire two node pins together |
| `blueprint_add_component` | Add component (Mesh, Camera, Light, Physics, Audio…) |
| `blueprint_set_construction_script` | Full construction script builder w/ Leader Pose auto-wiring |
| `blueprint_compile` | Compile a Blueprint, returns errors |
| `blueprint_validate` | Validate without compiling |
| `blueprint_add_timeline` | Add Timeline node with float/vector/color tracks |
| `blueprint_set_defaults` | Set class default property values |
| `blueprint_add_interface` | Implement a Blueprint Interface |
| `blueprint_add_event_dispatcher` | Add Event Dispatcher |
| `blueprint_add_macro` | Add a Blueprint Macro |
| `blueprint_get_info` | Read variables, functions, components |
| `blueprint_list` | List all Blueprints under a path |
| `blueprint_delete` | Delete a Blueprint asset |

### 🟠 Material Tools (14)

| Tool | Description |
|------|-------------|
| `material_create` | Create empty Material with domain/blend mode |
| `material_add_node` | Add any expression node (80+ types including Substrate) |
| `material_connect` | Connect two expression pins |
| `material_set_property` | Connect node to output property (BaseColor, Roughness…) |
| `material_set_param` | Set scalar/vector/texture parameter |
| `material_build_pbr` | Build complete PBR from texture paths in one call |
| `material_build_dissolve` | Noise-based dissolve with edge emissive glow |
| `material_build_emissive` | Emissive with optional sine-wave pulse |
| `material_build_hologram` | Scanline + Fresnel + flicker hologram |
| `material_recompile` | Force-recompile a material |
| `material_get_info` | Read all nodes, parameters, properties |
| `material_create_instance` | Create MaterialInstance from parent |
| `material_set_instance_param` | Set scalar/vector/texture/switch on MI |
| `material_list` | List all materials in a path |

### 🟡 Niagara Tools (20)

| Tool | Description |
|------|-------------|
| `niagara_create_system` | Create empty NiagaraSystem |
| `niagara_add_emitter` | Add emitter to system |
| `niagara_set_parameter` | Set system/emitter parameter |
| `niagara_set_renderer` | Configure sprite/mesh/ribbon renderer |
| `niagara_set_spawn_rate` | Set particles per second |
| `niagara_set_lifetime` | Set particle lifetime range |
| `niagara_set_color` | Set color with optional gradient |
| `niagara_set_size` | Set initial size + size by life |
| `niagara_set_velocity` | Set initial velocity |
| `niagara_set_gravity` | Set gravity scale |
| `niagara_add_module` | Add any Niagara module |
| `niagara_build_fire` | Fire preset: small/medium/large/inferno + smoke + embers |
| `niagara_build_trail` | Ribbon weapon/projectile trail |
| `niagara_build_explosion` | Explosion: small/medium/large/massive with shockwave |
| `niagara_build_magic_effect` | 8 magic types: fire/ice/healing/lightning/arcane/dark/wind/earth |
| `niagara_compile` | Compile NiagaraSystem |
| `niagara_get_info` | Read emitters, parameters, modules |
| `niagara_list` | List all Niagara systems in path |
| `niagara_duplicate` | Duplicate system as new asset |
| `niagara_delete` | Delete Niagara system |

### 🔍 Inspection Tools (12)

| Tool | Description |
|------|-------------|
| `inspect_asset` | Deep JSON inspection of any UE asset |
| `inspect_blueprint` | Full BP info: variables, functions, components, graphs |
| `inspect_material` | Material nodes, params, properties |
| `inspect_mesh` | StaticMesh/SkeletalMesh LODs, materials, sockets |
| `inspect_skeleton` | Bone hierarchy, socket positions |
| `inspect_datatable` | All rows as JSON |
| `inspect_anim` | AnimSequence/Montage/BlendSpace metadata |
| `inspect_niagara` | Niagara system structure |
| `inspect_physics_asset` | PhysicsAsset bodies and constraints |
| `inspect_folder` | Browse content folder (name, class, size) |
| `inspect_find_by_class` | Find all assets of a class in path |
| `inspect_find_references` | Find all assets that reference a given asset |

### 🌍 Scene Tools (16)

| Tool | Description |
|------|-------------|
| `scene_place_actor` | Spawn any actor class at location |
| `scene_move_actor` | Set location/rotation/scale |
| `scene_delete_actor` | Delete actor by label |
| `scene_duplicate_actor` | Duplicate actor with offset |
| `scene_select_actor` | Set editor selection |
| `scene_get_actors` | List all actors in level |
| `scene_add_point_light` | Add PointLight with intensity/color/radius |
| `scene_add_spot_light` | Add SpotLight with cone angles |
| `scene_add_directional_light` | Add DirectionalLight (sun) |
| `scene_add_sky_atmosphere` | Add SkyAtmosphere component |
| `scene_add_fog` | Add ExponentialHeightFog with volumetric options |
| `scene_add_post_process` | Add PostProcessVolume with all settings |
| `scene_add_camera` | Add CameraActor with DOF and FOV |
| `scene_set_world_settings` | Edit gravity, kill-z, game mode |
| `scene_add_trigger` | Add BoxTriggerVolume |
| `scene_save_level` | Save current level |

### 🗄️ Data Tools (15) — NEW Phase 2

| Tool | Description |
|------|-------------|
| `data_create_struct` | Create UserDefinedStruct with typed fields |
| `data_add_struct_field` | Add field to existing struct |
| `data_get_struct_fields` | Read all fields from a struct |
| `data_create_enum` | Create UserDefinedEnum with values |
| `data_add_enum_value` | Append value to existing enum |
| `data_get_enum_values` | Read all values from an enum |
| `data_create_datatable` | Create empty DataTable with row struct |
| `data_add_row` | Add/update row in DataTable |
| `data_get_row` | Read one row as JSON |
| `data_get_all_rows` | Dump entire DataTable as JSON |
| `data_delete_row` | Remove a row |
| `data_import_csv` | Import CSV file as DataTable |
| `data_create_curve_table` | Create CurveTable with float curves |
| `data_get_curve` | Read curve keys from CurveTable |
| `data_create_data_asset` | Create PrimaryDataAsset instance |

**Supported struct field types:**
`bool` `byte` `int` `int32` `int64` `float` `double` `string` `name` `text`
`vector` `vector2d` `vector4` `rotator` `transform` `color` `linear_color` `quat`
`soft_object` `soft_class` `object` `class` `actor` `gameplay_tag` `datetime` `guid`

### 🚀 Pipeline Tools (8)

| Tool | Description |
|------|-------------|
| `tripo_generate_from_text` | Text → 3D model (Tripo API v2) |
| `tripo_generate_from_image` | Concept art → 3D model |
| `tripo_get_task_status` | Poll Tripo task progress |
| `tripo_import_to_unreal` | Download + import model into UE 5.4 |
| `huanyuan_generate_from_image` | Image → 3D (Huanyuan3D) |
| `metatailor_rig_character` | Auto-rig + clothing (MetaTailor) |
| `pipeline_concept_to_character` | **Full pipeline**: image → 3D → rig → Blueprint |
| `ueos_status` | Check all service connections |

### 🔧 Diagnostics (3)

| Tool | Description |
|------|-------------|
| `ueos_status` | All service connection status + tool counts |
| `ueos_run_python` | Execute raw Python inside UE 5.4 (with timeout) |
| `ueos_batch_execute` | Run multiple Python scripts sequentially |

---

## UE Scripts Utility Library

Pre-built scripts in `ue_scripts/` that run INSIDE the UE editor:

| Script | Purpose |
|--------|---------|
| `ueos_utils.py` | 40+ helper functions (assets, BPs, materials, actors, data) |
| `bulk_compile_blueprints.py` | Compile all BPs under path |
| `import_fbx_batch.py` | Batch FBX import with full options |
| `setup_character_bp.py` | Complete Character BP with mesh/anim/clothing |
| `material_instance_factory.py` | Batch Material Instance creation |
| `datatable_batch_ops.py` | Merge/export/import/search DataTables |
| `scene_snapshot.py` | Full level JSON snapshot |

**Using from a UEOS tool:**
```python
# Load script, prepend to your inline code
utils = open("C:/UEOS/ue_scripts/ueos_utils.py").read()
script = utils + "\n" + my_code
await ue.execute_python(script)
```

---

## Configuration

### .env
```ini
# Unreal Engine Remote Control
UE_REMOTE_CONTROL_HOST=127.0.0.1
UE_REMOTE_CONTROL_PORT=30010

# 3D Generation APIs
TRIPO_API_KEY=tsk_xxx
HUANYUAN_API_KEY=
METATAILOR_API_KEY=

# Asset temp directory (where downloaded models land before UE import)
UEOS_ASSET_TEMP_DIR=C:/UEOS/temp

# Logging
UEOS_LOG_LEVEL=INFO
```

### Claude Desktop (claude_desktop_config.json)
```json
{
  "mcpServers": {
    "ueos": {
      "command": "python",
      "args": ["C:/UEOS/mcp_server/server.py"],
      "cwd": "C:/UEOS/mcp_server"
    }
  }
}
```

---

## Data Architecture

| Layer | Technology | Purpose |
|-------|------------|---------|
| Transport | HTTP REST port 30010 | Remote Control API |
| Execution | UE Python Editor Plugin | Asset creation/editing |
| Output parse | `UEOS_RESULT:` / `UEOS_ERROR:` prefixes | Structured data extraction |
| Storage | Unreal Content Browser | All assets (.uasset) |
| Config | `.env` + `python-dotenv` | API keys + config |
| Secrets | `.env` in `.gitignore` | Never committed |

---

## Phase Status

| Phase | Status | Scope |
|-------|--------|-------|
| Phase 1 | ✅ Complete | Blueprint (17), Tripo, Huanyuan3D, MetaTailor, Pipeline |
| Phase 2 | ✅ Complete | Material (14), Niagara (20), Inspection (12), Scene (16), Data (15) |
| Phase 3 | ⏳ Next | Animation Blueprints, State Machines, Montages, AnimNotify |
| Phase 4 | ⏳ Planned | UMG Widgets, Sequencer, Behavior Trees, Blackboards |
| Phase 5 | ⏳ Planned | Native UE Editor Utility Widget panel (connection status, tool browser) |

---

## Example Prompts

```
"Create a Character Blueprint BP_Soldier at /Game/Characters with 
 SkeletalMeshComponent, SpringArm, and Camera. Compile it."

"Build a PBR material M_RockWall at /Game/Materials using:
 T_Rock_D for base color, T_Rock_N for normal map, 
 roughness 0.85, metallic 0.0"

"Create a DataTable DT_Weapons at /Game/Data with struct FWeaponData 
 fields: Name(string), Damage(float), FireRate(float), Ammo(int).
 Add rows: Pistol(25,2.5,12), Rifle(15,8.0,30), Shotgun(80,0.8,8)"

"Generate a fire particle system NS_Bonfire at /Game/VFX.
 Large intensity, with smoke and embers enabled."

"Scene: add a warm point light 'Campfire_Light' at (0,0,50),
 intensity 2000, temperature 2800K, radius 500cm"

"Full pipeline: take this concept art URL → generate 3D with Tripo →
 rig with MetaTailor → create Character Blueprint BP_Hero at 
 /Game/Characters → compile"
```

---

## File Structure

```
ueos/
├── .env                       ← Live config (never committed)
├── .env.example               ← Template
├── .gitignore
├── requirements.txt
├── README.md
├── mcp_server/
│   ├── server.py              ← MCP entry point (105 tools)
│   ├── remote_control/
│   │   └── client.py          ← UE 5.4 HTTP client w/ retry
│   ├── api_clients/
│   │   ├── tripo.py
│   │   ├── huanyuan.py
│   │   └── metatailor.py
│   └── tools/
│       ├── blueprint.py       ← 17 tools ✅
│       ├── material.py        ← 14 tools ✅
│       ├── niagara.py         ← 20 tools ✅
│       ├── inspection.py      ← 12 tools ✅
│       ├── scene.py           ← 16 tools ✅
│       ├── data.py            ← 15 tools ✅ NEW
│       ├── animation.py       ← stub (Phase 3)
│       ├── umg.py             ← stub (Phase 4)
│       └── sequencer.py       ← stub (Phase 4)
├── ue_scripts/                ← Run INSIDE UE editor ✅ NEW
│   ├── ueos_utils.py          ← 40+ helper functions
│   ├── bulk_compile_blueprints.py
│   ├── import_fbx_batch.py
│   ├── setup_character_bp.py
│   ├── material_instance_factory.py
│   ├── datatable_batch_ops.py
│   └── scene_snapshot.py
├── setup/
│   ├── install.py
│   └── verify.py
└── config/
    └── claude_desktop_config.json
```

---

*Last updated: Phase 2 complete — commit b52fa8b*
