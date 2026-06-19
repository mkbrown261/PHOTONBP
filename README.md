# UEOS — Unreal Engine Operating System

**Version 7.0.0 — Phase 7 Complete: Chaos Physics + PCG + Enhanced Input + MetaSounds**

AI-driven Unreal Engine 5.4 development system. Claude controls the UE editor through **339 MCP tools** via the Remote Control API. Zero C++. Pure Python.

---

## ⚡ How It Works (Read This First)

UEOS connects **Claude Desktop** to **Unreal Engine 5.4** via three bridges:

```
Claude Desktop
     │
     │  MCP protocol (stdio)
     ▼
mcp_server/server.py  ←  339 tools registered here
     │
     │  HTTP PUT  port 30010
     ▼
Unreal Engine 5.4  ←  Remote Control API + Python Script Plugin
```

Claude sends commands → UEOS translates them to UE Python scripts → runs them live inside the editor.

### The System Prompt

UEOS has a full behavioral system prompt (`UEOS_SYSTEM_PROMPT.md` — 74KB of UE doctrine, optimization rules, Blueprint standards, and game design patterns). **Claude does not load this automatically.** You must activate it at the start of each conversation:

```
/ueos
```

Type `/ueos` in Claude Desktop chat to load the UEOS system prompt. Without this, Claude has all 339 tools available but no UEOS behavioral instructions.

> **Why not auto-inject?** `claude_desktop_config.json` only supports `command`, `args`, `cwd`, and `env` fields for MCP servers — there is no system prompt field in the MCP spec. The cleanest solution is the MCP Prompts API already implemented: type `/ueos` to load it, or paste the contents of `UEOS_SYSTEM_PROMPT.md` into Claude → Settings → Project Instructions for your UEOS project.

---

## 📋 Complete Setup Guide — Chronological Order

Follow these steps **in order**. Do not skip ahead.

---

### STEP 1 — Prerequisites

Before touching UEOS, verify you have:

| Requirement | Version | Where to get it |
|-------------|---------|-----------------|
| Windows 10/11 | Any | — |
| Unreal Engine | 5.4+ | Epic Games Launcher |
| Python | 3.10+ | https://www.python.org/downloads/ |
| Claude Desktop | Latest | https://claude.ai/download |

> **Python install tip:** On the Python installer, check **"Add Python to PATH"** before clicking Install. UEOS will not work without this.

---

### STEP 2 — Download / Clone UEOS

**Option A — Git:**
```bash
git clone https://github.com/your-repo/ueos.git C:\UEOS
```

**Option B — ZIP download:**
1. Download the ZIP from GitHub
2. Extract to `C:\UEOS` (or any path without spaces)

> The path must not contain spaces (e.g. `C:\Users\John Smith\UEOS` will break things). Use `C:\UEOS` or `C:\Dev\UEOS`.

---

### STEP 3 — Run Setup (Double-Click)

**Double-click `SETUP.bat`** in the UEOS root folder.

What it does automatically:
1. Checks Python version (3.10+ required)
2. Installs all pip dependencies (`mcp`, `aiohttp`, `python-dotenv`, etc.)
3. Writes the UEOS entry into your `claude_desktop_config.json`
4. Patches UE project settings if a UE project is open
5. Creates `.env` from template
6. Launches the GUI dashboard

If Python is missing, `SETUP.bat` downloads and installs Python 3.11.9 automatically, then re-runs itself.

**Expected output:**
```
[1/5] Checking Python...       OK: Python 3.11.9
[2/5] Installing dependencies... OK: All dependencies installed
[3/5] Configuring Claude Desktop... OK: Claude Desktop config written. Restart Claude Desktop.
[4/5] Configuring Unreal Engine projects... OK: UE project settings patched.
[5/5] Finalising...            OK: Setup complete
```

> If Step 3 shows `NOTE: Claude Desktop not found` — install Claude Desktop first, then run `FIX_CLAUDE_CONFIG.bat`.

---

### STEP 4 — Configure API Keys

After `SETUP.bat` finishes, the GUI launcher opens. Go to the **API Keys** tab.

#### 4a. Tripo API Key (Required for 3D generation)
1. Go to https://platform.tripo3d.ai
2. Account → API Keys → Create Key
3. Copy the key (starts with `tsk_`)
4. Paste into the **Tripo API Key** field in the GUI
5. Click **Validate** — it should show your credit balance

#### 4b. Huanyuan3D API Key (Optional)
1. Go to https://hunyuan.cloud.tencent.com
2. Create an API key
3. Paste into the **Huanyuan API Key** field

#### 4c. MetaTailor API Key (Optional — for auto-rigging)
1. Go to https://metatailor.io
2. Create an API key
3. Paste into the **MetaTailor API Key** field

**Or configure via command line:**
```bash
python setup/configure.py
```

This runs an interactive wizard that validates each key as you enter it.

**Where keys are stored:**  
Keys are saved to `.env` in the UEOS root. This file is git-ignored and never committed.

```bash
# .env (auto-generated — do not commit)
TRIPO_API_KEY=tsk_your_key_here
HUANYUAN_API_KEY=your_key_here
METATAILOR_API_KEY=your_key_here
UE_REMOTE_CONTROL_HOST=127.0.0.1
UE_REMOTE_CONTROL_PORT=30010
UEOS_ASSET_TEMP_DIR=C:/UEOS/temp
```

---

### STEP 5 — Configure Unreal Engine 5.4 Plugins

Open your Unreal Engine 5.4 project. Enable these plugins:

**Edit → Plugins → search and enable each:**

| Plugin | Required | Notes |
|--------|----------|-------|
| **Python Editor Script Plugin** | ✅ Required | Enables Python execution inside UE |
| **Remote Control API** | ✅ Required | Enables HTTP control on port 30010 |
| **Remote Control Logic** | ✅ Required | Supports Remote Control presets |
| **Editor Scripting Utilities** | ✅ Required | Extended editor scripting |
| **Niagara** | ✅ Required | Particle system tools |

After enabling all plugins, **restart the UE editor**.

---

### STEP 6 — Configure Remote Control API (Critical)

This step is what actually lets UEOS talk to UE. **Do not skip this.**

1. In UE: **Edit → Project Settings**
2. In the left panel, scroll to **Plugins → Remote Control API**
3. Set these values:

| Setting | Value | Why |
|---------|-------|-----|
| **Allow remote control of editor** | ✅ Enabled | Must be ON |
| **Remote Control HTTP Server Port** | `30010` | Default UEOS port |
| **HTTP Server Bind Address** | `0.0.0.0` | **CRITICAL — set this or connections fail** |

> **Why `0.0.0.0`?** By default UE binds to `127.0.0.1` (localhost only). Setting it to `0.0.0.0` allows connections from any address on the machine, which is required for UEOS to connect reliably across Python environments.

4. Click **Set as Default** to save to project config (not just session)
5. These settings are saved to `Config/DefaultEngine.ini` in your UE project

---

### STEP 7 — Enable Remote Execution for Python (for Bridge)

Remote Execution is what allows external Python processes to execute scripts inside the UE editor. This is separate from the Remote Control API.

1. In UE: **Edit → Project Settings**
2. Search for **Python** in the left panel
3. Find **Python Remote Execution**:

| Setting | Value |
|---------|-------|
| **Enable Remote Execution?** | ✅ Enabled |
| **Multicast Group Endpoint** | `239.0.0.1:6766` (default) |
| **Multicast Bind Address** | `0.0.0.0` |
| **Multicast TTL** | `0` |

4. **Restart the UE editor** after changing these settings.

---

### STEP 8 — Verify the Python Bridge is Active

After restarting UE with the plugins and settings enabled, verify the Python bridge is live.

**In UE: Window → Developer Tools → Output Log**

Run this command to confirm the bridge is active:

```python
import unreal; unreal.log("UEOS bridge active: OK")
```

**To run it:** In the UE Output Log, click the command bar at the bottom and type:
```
py import unreal; unreal.log("UEOS bridge active: OK")
```

You should see `LogPython: UEOS bridge active: OK` in the Output Log.

**Alternatively, from external Python:**
```python
import urllib.request, json

payload = json.dumps({
    "objectPath": "/Script/PythonScriptPlugin.Default__PythonScriptLibrary",
    "functionName": "ExecutePythonScript",
    "parameters": {"PythonScript": "import unreal; print('UEOS_PING:OK')"}
}).encode()

req = urllib.request.Request(
    "http://127.0.0.1:30010/remote/object/call",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="PUT"
)
with urllib.request.urlopen(req, timeout=5) as resp:
    print(resp.read().decode())
```

Expected response: `{"ReturnValue": "", "PythonScript": "import unreal; print('UEOS_PING:OK')"}`

---

### STEP 9 — Configure Claude Desktop

`SETUP.bat` should have already done this. To verify or fix manually:

**Double-click `FIX_CLAUDE_CONFIG.bat`** — it auto-detects your Claude Desktop install location and writes the correct config.

**Manual path:** `%APPDATA%\Claude\claude_desktop_config.json`

The entry UEOS writes looks like this:
```json
{
  "mcpServers": {
    "ueos": {
      "command": "C:\\Python311\\python.exe",
      "args": ["C:\\UEOS\\mcp_server\\server.py"],
      "cwd": "C:\\UEOS\\mcp_server"
    }
  }
}
```

> Paths are auto-generated based on your actual Python and UEOS locations. Do not hardcode these manually — always use `FIX_CLAUDE_CONFIG.bat` or `python setup/inject_claude_config.py`.

**After writing the config:**
1. **Fully quit Claude Desktop** — right-click the tray icon → Quit (not just close the window)
2. Reopen Claude Desktop
3. Look for the 🔌 MCP icon in the chat input — it should show UEOS tools

---

### STEP 10 — Verify Everything Works

#### 10a. Run UEOS Status

In Claude Desktop, ask:
```
run ueos_status
```

Expected output:
```
✓ Unreal Engine 5.4.x connected
  Project: YourProjectName
  Level: /Game/Maps/TestMap

✓ Tripo API connected
  Balance: 1234 credits

✓ UEOS MCP Server running
  Tools: 339 registered
```

If UE is not running, UE status shows as disconnected — that's fine, start UE and try again.

#### 10b. Run UEOS Diagnose (if ueos_status fails)

```
run ueos_diagnose
```

`ueos_diagnose` fires a raw HTTP PUT directly to UE's Remote Control API and shows you the **exact** response — status code, headers, and body. This tells you precisely what's failing:

| Error | Meaning | Fix |
|-------|---------|-----|
| `Connection refused` | UE not running or port wrong | Start UE, check port 30010 |
| `403 Forbidden` | Remote Control not enabled | Enable in Project Settings → Plugins → Remote Control API |
| `404 Not Found` | Wrong endpoint or UE version | Verify UE 5.4 |
| `400 Bad Request` | Python Plugin not enabled | Enable Python Editor Script Plugin |
| Timeout | Bind address wrong | Set Bind Address to `0.0.0.0` |

#### 10c. Load the UEOS System Prompt

At the start of any UEOS conversation, type:
```
/ueos
```

This loads the full 74KB UEOS behavioral system prompt via the MCP Prompts API. You'll see Claude acknowledge it and enter UEOS mode.

---

## 🖥️ GUI Launcher

After first-time setup, use **`UEOS.bat`** (not `SETUP.bat`) for daily use.

Double-click `UEOS.bat` → opens the UEOS dashboard with 5 tabs:

| Tab | Purpose |
|-----|---------|
| **Dashboard** | Live connection status (UE, Tripo, Huanyuan, MetaTailor). Start/Stop MCP server. |
| **API Keys** | Enter and validate all API keys. Values masked by default. |
| **Settings** | UE Remote Control host/port, temp dir for downloaded assets, log level. |
| **Claude Setup** | Auto-detects Claude Desktop config and writes/updates the UEOS entry. |
| **Log** | Live color-coded tail of `ueos.log`. Shows all tool calls in real time. |

---

## 🔧 Diagnostic Tools Reference

### `ueos_status`
High-level health check. Shows:
- UE connection state (host, port, engine version, project name)
- Tripo API (connected + credit balance)
- Huanyuan3D (connected or not configured)
- MetaTailor (connected or not configured)
- MCP server tool count

**When to use:** First check after opening Claude. Quick sanity test.

### `ueos_diagnose`
Raw HTTP diagnostic. Fires a direct `PUT /remote/object/call` to UE and returns:
- HTTP status code
- Response headers
- Full response body
- Timing

**When to use:** When `ueos_status` says UE is disconnected. Shows you exactly what UE is rejecting and why.

### `ueos_run_python`
Execute arbitrary Python code inside the UE 5.4 editor. Full access to `unreal` module.

```python
# Example: list all assets in /Game/Characters
import unreal
ar = unreal.AssetRegistryHelpers.get_asset_registry()
assets = ar.get_assets_by_path('/Game/Characters', recursive=True)
print(f"UEOS_RESULT:{[str(a.asset_name) for a in assets]}")
```

Use `UEOS_RESULT:` prefix for return values, `UEOS_ERROR:` for errors.

**When to use:** Custom operations not covered by existing tools. Advanced debugging.

---

## 🔑 System Prompt Delivery — Technical Details

### The Problem
`claude_desktop_config.json` only supports these MCP server fields:
```json
{
  "mcpServers": {
    "ueos": {
      "command": "...",
      "args": [...],
      "cwd": "...",
      "env": {}
    }
  }
}
```

There is **no `systemPrompt` field** in the MCP spec. Claude Desktop does not auto-inject system prompts from the config file.

### Current Solution — MCP Prompts API
UEOS serves its system prompt via the **MCP Prompts API** (`@server.list_prompts` / `@server.get_prompt` in `server.py` lines 156–196).

In Claude Desktop: type **`/ueos`** → Claude fetches `UEOS_SYSTEM_PROMPT.md` at runtime and loads it as context.

### Permanent Solution — Project Instructions
For automatic loading every conversation:

1. In Claude Desktop: **Settings → Projects → New Project** (or open your UEOS project)
2. Click **Project Instructions**
3. Paste the contents of `UEOS_SYSTEM_PROMPT.md`

This makes the system prompt load automatically for every conversation in that project — no `/ueos` required.

### Summary

| Method | Auto-loads? | How to use |
|--------|-------------|-----------|
| `/ueos` command | ❌ Manual | Type `/ueos` at start of each chat |
| Project Instructions | ✅ Automatic | Paste prompt into Claude project once |
| `claude_desktop_config.json` | ❌ Not possible | No system prompt field in MCP spec |

---

## ⚠️ Common Problems & Fixes

### "Claude doesn't see any UEOS tools"
1. Check that `claude_desktop_config.json` has the `ueos` entry → run `FIX_CLAUDE_CONFIG.bat`
2. **Fully quit and reopen** Claude Desktop (right-click tray → Quit)
3. Check the 🔌 MCP icon appears in the chat input bar

### "ueos_status shows UE disconnected"
1. Make sure Unreal Engine 5.4 is running with your project open
2. Run `ueos_diagnose` — check the exact error
3. Verify Remote Control API is enabled: **Edit → Project Settings → Remote Control API → Allow remote control of editor = ON**
4. Verify Bind Address is `0.0.0.0` (not `127.0.0.1`)
5. Verify port is `30010`
6. Check Windows Firewall isn't blocking port 30010

### "Python not found" during SETUP.bat
- Reinstall Python from https://www.python.org/downloads/
- **Check "Add Python to PATH"** during install
- Run `SETUP.bat` again

### "Permission denied" writing claude_desktop_config.json
- Run `FIX_CLAUDE_CONFIG.bat` as Administrator (right-click → Run as administrator)
- Or manually edit `%APPDATA%\Claude\claude_desktop_config.json`

### "Tripo validation fails"
- Keys start with `tsk_` — verify you copied the full key
- Check your Tripo account has credits remaining
- Run `python setup/configure.py --tripo` to re-enter the key

### "/ueos command not recognized in Claude"
- The MCP server is not connected — check steps above
- Try typing `/` in Claude Desktop to see all available prompts
- Run `ueos_status` to confirm server is running

### "Claude doesn't have UEOS context / acts confused"
- You forgot to type `/ueos` at the start of the conversation
- Or use Project Instructions (permanent fix — see above)

---

## 🚀 Daily Usage Workflow

Each day you use UEOS:

```
1. Open Unreal Engine 5.4 (with your project)
2. Open Claude Desktop
3. Start a new conversation
4. Type: /ueos    ← loads system prompt
5. Type: run ueos_status   ← confirms everything is connected
6. Start building
```

---

## 🛠️ Re-Configuration Commands

```bash
# Update API keys interactively
python setup/configure.py

# Update only Tripo key
python setup/configure.py --tripo

# Reset all keys and start fresh
python setup/configure.py --reset

# Show Claude Desktop config (without writing it)
python setup/configure.py --claude

# Auto-write Claude Desktop config
python setup/inject_claude_config.py

# Or double-click
FIX_CLAUDE_CONFIG.bat
```

---

## 📐 Architecture

```
Claude Desktop
     │
     │ MCP (stdio)
     ▼
mcp_server/server.py          ← 339 tools registered
     │
     ├── tools/blueprint.py   ← 17 tools: graph editing, compile, validate
     ├── tools/material.py    ← 14 tools: PBR, dissolve, hologram, Substrate
     ├── tools/niagara.py     ← 20 tools: fire, explosion, trail, magic
     ├── tools/inspection.py  ← 12 tools: deep JSON inspection of any asset
     ├── tools/scene.py       ← 16 tools: lights, fog, PPV, camera, actors
     ├── tools/data.py        ← 15 tools: Structs, Enums, DataTables, Curves
     ├── tools/animation.py   ← 22 tools: AnimBP, State Machines, Montages, BlendSpaces, IK
     ├── tools/umg.py         ← 20 tools: Widget BPs, HUDs, menus, 5 presets  (Phase 4)
     ├── tools/sequencer.py   ← 18 tools: Level Sequences, camera cuts, tracks (Phase 4)
     ├── tools/behavior_tree.py ← 17 tools: BT, Blackboard, Tasks, AI pipeline (Phase 4)
     ├── tools/editor_widget.py  ← 20 tools: EUW panels, menus, UEOS panel     (Phase 5)
     ├── tools/gameplay_ability.py ← 20 tools: GAS, AttributeSets, Effects, Cues (Phase 6)
     ├── tools/environment_query.py ← 20 tools: EQS queries, generators, tests  (Phase 6)
     ├── tools/navmesh.py         ← 17 tools: NavMesh, NavAreas, Links, AI move (Phase 6)
     ├── tools/chaos_physics.py   ← 25 tools: GeometryCollections, Fracture, Cloth, Fields (Phase 7)
     ├── tools/pcg.py             ← 21 tools: PCG Graphs, samplers, spawners, volumes       (Phase 7)
     ├── tools/enhanced_input.py  ← 18 tools: InputActions, IMCs, presets, player binding   (Phase 7)
     └── tools/metasound.py       ← 17 tools: MetaSound Source/Patch, attenuation, LFO, bus (Phase 7)
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

## 📦 Tool Inventory

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
| `scene_set_skylight` | Configure SkyLight with HDRI capture |
| `scene_add_decal` | Place DecalActor with material |
| `scene_add_camera` | Add CineCameraActor with lens settings |
| `scene_take_screenshot` | Capture viewport to PNG |

### 📊 Data Tools (15)

| Tool | Description |
|------|-------------|
| `data_create_struct` | Create UStruct with typed fields |
| `data_create_enum` | Create UEnum with named values |
| `data_create_datatable` | Create DataTable with row struct |
| `data_add_rows` | Add/update rows via JSON array |
| `data_get_rows` | Read all rows from DataTable |
| `data_delete_rows` | Delete rows by name |
| `data_create_curve` | Create CurveFloat/Vector/Color |
| `data_add_curve_keys` | Add keyframes to a curve |
| `data_create_primary_asset` | Create Primary Data Asset |
| `data_create_save_game` | Create SaveGame class |
| `data_create_game_instance` | Create GameInstance subclass |
| `data_set_variable` | Set variable on a Blueprint CDO |
| `data_get_variable` | Get variable from Blueprint CDO |
| `data_list` | List all data assets in path |
| `data_delete` | Delete data asset |

### 🎭 Animation Tools (22)

| Tool | Description |
|------|-------------|
| `anim_create_blueprint` | Create AnimBlueprint for skeleton |
| `anim_add_variable` | Add variable (float/bool/int/vector) |
| `anim_create_state_machine` | Create state machine in AnimBP |
| `anim_add_state` | Add state with animation asset |
| `anim_add_transition` | Add transition with condition |
| `anim_create_blendspace` | Create BlendSpace1D or 2D |
| `anim_add_blendspace_sample` | Add sample point to BlendSpace |
| `anim_create_montage` | Create AnimMontage from sequence |
| `anim_add_montage_section` | Add named section |
| `anim_add_notify` | Add AnimNotify at time point |
| `anim_add_notify_state` | Add notify state with begin/end |
| `anim_create_ikrig` | Create IK Rig for skeleton |
| `anim_add_ik_goal` | Add IK goal (foot, hand, head) |
| `anim_create_ikretargeter` | Create IK Retargeter |
| `anim_set_retarget_pose` | Set retarget reference pose |
| `anim_compile` | Compile AnimBlueprint |
| `anim_get_info` | Read AnimBP structure |
| `anim_list` | List animation assets |
| `anim_set_root_motion` | Enable/configure root motion |
| `anim_add_layered_blend` | Add Layered Blend per Bone node |
| `anim_add_aim_offset` | Add AimOffset asset and node |
| `anim_set_physics_blend` | Set physical animation blending |

### 🖼️ UMG Widget Tools (20)

| Tool | Description |
|------|-------------|
| `umg_create_widget` | Create Widget Blueprint |
| `umg_add_widget` | Add widget element (Button, Text, Image…) |
| `umg_set_property` | Set widget property |
| `umg_bind_event` | Bind widget event to function |
| `umg_add_animation` | Add UMG animation |
| `umg_set_anchors` | Set widget anchors and alignment |
| `umg_add_canvas_panel` | Add CanvasPanel root |
| `umg_add_vertical_box` | Add VerticalBox layout |
| `umg_add_horizontal_box` | Add HorizontalBox layout |
| `umg_add_overlay` | Add Overlay container |
| `umg_add_scroll_box` | Add ScrollBox |
| `umg_add_progress_bar` | Add ProgressBar |
| `umg_add_text_block` | Add TextBlock |
| `umg_add_image` | Add Image widget |
| `umg_add_button` | Add Button with text |
| `umg_build_hud` | Build full HUD preset (health/ammo/minimap) |
| `umg_build_menu` | Build main menu preset (Play/Settings/Quit) |
| `umg_build_inventory` | Build grid inventory preset |
| `umg_build_dialogue` | Build dialogue box preset |
| `umg_compile` | Compile Widget Blueprint |

### 🎬 Sequencer Tools (18)

| Tool | Description |
|------|-------------|
| `seq_create` | Create Level Sequence |
| `seq_add_camera_cut` | Add camera cut track |
| `seq_add_actor_track` | Add actor binding track |
| `seq_add_transform_track` | Add transform keyframe track |
| `seq_add_property_track` | Add property keyframe track |
| `seq_add_audio_track` | Add audio track |
| `seq_add_event_track` | Add event track |
| `seq_add_fade` | Add fade in/out |
| `seq_set_duration` | Set sequence duration |
| `seq_set_fps` | Set frame rate |
| `seq_add_subsequence` | Nest sub-sequence |
| `seq_add_camera` | Add CineCamera actor + track |
| `seq_set_camera_lens` | Set focal length, aperture, focus |
| `seq_add_cine_actor` | Add actor with cinematic movement |
| `seq_get_info` | Read sequence structure |
| `seq_render` | Trigger movie render |
| `seq_list` | List sequences in path |
| `seq_delete` | Delete sequence |

### 🤖 Behavior Tree Tools (17)

| Tool | Description |
|------|-------------|
| `bt_create` | Create BehaviorTree asset |
| `bt_create_blackboard` | Create Blackboard asset |
| `bt_add_key` | Add Blackboard key (object/vector/bool/float/int/string/enum) |
| `bt_add_selector` | Add Selector composite |
| `bt_add_sequence` | Add Sequence composite |
| `bt_add_parallel` | Add Parallel composite |
| `bt_add_task` | Add built-in task (MoveTo, Wait, PlaySound…) |
| `bt_add_service` | Add service (update rate, activation) |
| `bt_add_decorator` | Add decorator (condition, cooldown, loop…) |
| `bt_create_task` | Create custom BTTask Blueprint |
| `bt_create_service` | Create custom BTService Blueprint |
| `bt_create_decorator` | Create custom BTDecorator Blueprint |
| `bt_set_root` | Set root composite |
| `bt_assign_blackboard` | Assign Blackboard to BehaviorTree |
| `bt_get_info` | Read BT structure |
| `bt_list` | List all BTs in path |
| `bt_build_patrol` | Full patrol + alert pattern preset |

### 🛠️ Editor Widget Tools (20)

| Tool | Description |
|------|-------------|
| `euw_create` | Create Editor Utility Widget Blueprint |
| `euw_add_button` | Add button with label + onclick callback |
| `euw_add_text_input` | Add editable text input |
| `euw_add_dropdown` | Add dropdown selector |
| `euw_add_checkbox` | Add checkbox |
| `euw_add_slider` | Add float slider with range |
| `euw_add_label` | Add static text label |
| `euw_add_progress_bar` | Add progress bar |
| `euw_add_list_view` | Add list/tree view |
| `euw_add_tab_container` | Add tab strip container |
| `euw_bind_event` | Bind widget event to Python/BP function |
| `euw_add_menu_entry` | Add entry to top-level Editor menu |
| `euw_add_toolbar_button` | Add button to editor toolbar |
| `euw_register_tab` | Register as dockable tab panel |
| `euw_open` | Open/spawn the widget |
| `euw_post_status` | Post message to editor status bar |
| `euw_set_progress` | Update status bar progress value |
| `euw_build_ueos_panel` | Build the full UEOS control panel |
| `euw_get_info` | Read widget structure |
| `euw_list` | List all EUWs in path |

### ⚡ Gameplay Ability System Tools (20)

| Tool | Description |
|------|-------------|
| `gas_add_asc` | Add AbilitySystemComponent to actor |
| `gas_create_attribute_set` | Create AttributeSet with typed attributes |
| `gas_create_ability` | Create GameplayAbility Blueprint |
| `gas_create_effect` | Create GameplayEffect (instant/duration/infinite) |
| `gas_create_cue` | Create GameplayCue handler |
| `gas_add_attribute` | Add attribute to AttributeSet |
| `gas_set_effect_modifier` | Configure Modifier on GameplayEffect |
| `gas_set_effect_duration` | Set duration and period |
| `gas_add_tag` | Add GameplayTag to ability/effect |
| `gas_set_cost` | Set ability cost (GameplayEffect) |
| `gas_set_cooldown` | Set ability cooldown |
| `gas_grant_ability` | Grant ability to actor at runtime |
| `gas_apply_effect` | Apply GameplayEffect to actor |
| `gas_remove_effect` | Remove GameplayEffect from actor |
| `gas_get_attribute` | Get current attribute value |
| `gas_set_attribute` | Set attribute value directly |
| `gas_create_execution` | Create GameplayEffectExecutionCalculation |
| `gas_create_mmc` | Create ModifierMagnitudeCalculation |
| `gas_get_info` | Read GAS setup on actor |
| `gas_list` | List all GAS assets in path |

### 🎯 Environment Query System Tools (20)

| Tool | Description |
|------|-------------|
| `eqs_create` | Create EQS Query asset |
| `eqs_add_generator` | Add generator (ActorsOfClass, Grid, Donut, Circle, Cone) |
| `eqs_add_test` | Add test (Trace, Distance, Dot, Pathfinding, Overlap) |
| `eqs_set_test_filter` | Configure test as filter (pass/fail threshold) |
| `eqs_set_test_score` | Configure test as scorer (weight, clamp) |
| `eqs_add_context` | Add context (Querier, Target, AllActors, custom) |
| `eqs_set_generator_params` | Set generator parameters (radius, density, count) |
| `eqs_create_context` | Create custom EnvQueryContext Blueprint |
| `eqs_create_test` | Create custom EnvQueryTest Blueprint |
| `eqs_run_query` | Run EQS query on actor, returns results |
| `eqs_debug_query` | Run with full debug visualization |
| `eqs_set_run_mode` | Set SingleBestItem/RandomBestItem/AllMatching |
| `eqs_build_cover_query` | Build cover-finding query preset |
| `eqs_build_flank_query` | Build flanking position query preset |
| `eqs_build_patrol_query` | Build patrol point query preset |
| `eqs_build_retreat_query` | Build retreat/escape position query preset |
| `eqs_get_info` | Read EQS query structure |
| `eqs_list` | List all EQS assets in path |
| `eqs_delete` | Delete EQS asset |
| `eqs_duplicate` | Duplicate EQS asset |

### 🗺️ NavMesh Tools (17)

| Tool | Description |
|------|-------------|
| `nav_place_volume` | Place NavMeshBoundsVolume |
| `nav_set_agent` | Configure agent (radius, height, step height) |
| `nav_rebuild` | Trigger full navmesh rebuild |
| `nav_test_path` | Test if path exists between two points |
| `nav_get_path` | Get path points from A to B |
| `nav_create_area` | Create custom NavArea class |
| `nav_set_area_cost` | Set traversal cost on NavArea |
| `nav_place_modifier` | Place NavModifierVolume with area class |
| `nav_create_link` | Create NavLinkProxy (jump/ladder/door) |
| `nav_set_link_endpoints` | Set link start/end points and direction |
| `nav_add_smart_link` | Add SmartNavLink with custom logic |
| `nav_place_invoker` | Place NavMeshBoundsVolume with invoker |
| `nav_get_stats` | Get navmesh tile count and coverage stats |
| `nav_get_poly_at` | Get navmesh polygon at world position |
| `nav_find_nearest` | Find nearest navmesh point to location |
| `nav_diagnostics` | Full navmesh diagnostic report |
| `nav_list` | List all nav assets in path |

### 💥 Chaos Physics Tools (25)

| Tool | Description |
|------|-------------|
| `chaos_create_gc` | Create GeometryCollection from mesh |
| `chaos_fracture_voronoi` | Voronoi fracture with cell count |
| `chaos_fracture_uniform` | Uniform grid fracture |
| `chaos_fracture_radial` | Radial fracture from point |
| `chaos_fracture_cluster` | Cluster fracture (hierarchical) |
| `chaos_set_damage_threshold` | Set per-level damage threshold |
| `chaos_set_mass` | Set mass and density |
| `chaos_set_collision` | Configure collision profile |
| `chaos_add_anchor_field` | Add anchor field (static base) |
| `chaos_add_strain_field` | Add strain field (internal strength) |
| `chaos_create_cloth` | Create Chaos Cloth component |
| `chaos_set_cloth_params` | Set cloth stiffness, damping, wind |
| `chaos_set_cloth_collision` | Add cloth self-collision and world collision |
| `chaos_create_rb` | Create rigid body simulation |
| `chaos_place_radial_force` | Place RadialForceActor |
| `chaos_set_radial_params` | Set force strength, radius, falloff |
| `chaos_apply_impulse` | Apply impulse to simulated actor |
| `chaos_apply_force` | Apply continuous force |
| `chaos_create_constraint` | Create physics constraint joint |
| `chaos_set_constraint_limits` | Set angular/linear limits |
| `chaos_simulate_mesh` | Enable physics simulation on StaticMesh |
| `chaos_set_break_event` | Set on-fracture Blueprint event |
| `chaos_get_info` | Read GeometryCollection structure |
| `chaos_list` | List all Chaos assets in path |
| `chaos_diagnostics` | Chaos simulation diagnostic report |

### 🌿 PCG Tools (21)

| Tool | Description |
|------|-------------|
| `pcg_create_graph` | Create PCG Graph asset |
| `pcg_add_surface_sampler` | Add surface point sampler |
| `pcg_add_mesh_sampler` | Add mesh surface sampler |
| `pcg_add_volume_sampler` | Add volume point sampler |
| `pcg_add_static_mesh_spawner` | Add static mesh spawner node |
| `pcg_add_actor_spawner` | Add actor spawner node |
| `pcg_set_density` | Set point density |
| `pcg_set_scale` | Set min/max scale range |
| `pcg_add_filter` | Add density/tag/bounds filter |
| `pcg_add_transform` | Add transform node (offset, jitter) |
| `pcg_add_attribute_noise` | Add attribute noise to points |
| `pcg_add_slope_filter` | Filter points by slope angle |
| `pcg_add_biome_filter` | Filter by painted landscape layer |
| `pcg_connect` | Connect PCG graph nodes |
| `pcg_place_volume` | Place PCGVolume in level |
| `pcg_assign_graph` | Assign PCG graph to volume |
| `pcg_generate` | Trigger PCG generation |
| `pcg_clear` | Clear generated PCG output |
| `pcg_get_info` | Read PCG graph structure |
| `pcg_list` | List all PCG graphs in path |
| `pcg_diagnostics` | PCG generation diagnostic report |

### 🎮 Enhanced Input Tools (18)

| Tool | Description |
|------|-------------|
| `input_create_action` | Create InputAction asset |
| `input_set_action_type` | Set value type (bool/axis1D/axis2D/axis3D) |
| `input_add_trigger` | Add trigger (Pressed/Released/Hold/Tap/Pulse) |
| `input_add_modifier` | Add modifier (DeadZone/Negate/Swizzle/Scale) |
| `input_create_imc` | Create Input Mapping Context |
| `input_add_mapping` | Add key binding to IMC |
| `input_set_mapping_modifiers` | Set modifiers on specific mapping |
| `input_set_mapping_triggers` | Set triggers on specific mapping |
| `input_assign_imc` | Assign IMC to PlayerController/Character |
| `input_build_fps_preset` | Build complete FPS input preset |
| `input_build_tps_preset` | Build complete TPS input preset |
| `input_build_topdown_preset` | Build top-down input preset |
| `input_build_vehicle_preset` | Build vehicle input preset |
| `input_wire_to_bp` | Wire input actions to Blueprint events |
| `input_get_info` | Read InputAction/IMC structure |
| `input_list` | List all Input assets in path |
| `input_delete` | Delete input asset |
| `input_diagnostics` | Input binding diagnostic report |

### 🔊 MetaSound Tools (17)

| Tool | Description |
|------|-------------|
| `ms_create_source` | Create MetaSound Source asset |
| `ms_create_patch` | Create MetaSound Patch asset |
| `ms_add_input` | Add input pin (trigger/float/int/bool/wave) |
| `ms_add_output` | Add output pin |
| `ms_add_node` | Add node (oscillator/filter/envelope/delay…) |
| `ms_connect` | Connect MetaSound nodes |
| `ms_set_param` | Set parameter default value |
| `ms_add_random_select` | Add random wave selector node |
| `ms_add_pitch_shift` | Add pitch shift node |
| `ms_add_envelope` | Add ADSR envelope |
| `ms_create_attenuation` | Create SoundAttenuation asset |
| `ms_set_attenuation` | Configure attenuation shape, falloff, inner/outer radii |
| `ms_create_class` | Create SoundClass (mix bus) |
| `ms_create_mix` | Create SoundMix preset |
| `ms_assign_to_component` | Assign MetaSound to AudioComponent on actor |
| `ms_get_info` | Read MetaSound graph structure |
| `ms_list` | List all MetaSound assets in path |

### 🔌 Pipeline Tools (8)

| Tool | Description |
|------|-------------|
| `tripo_generate` | Text → 3D model via Tripo API |
| `tripo_generate_from_image` | Image → 3D model via Tripo API |
| `tripo_import` | Import generated .glb into UE |
| `huanyuan_generate` | Image → 3D via Huanyuan3D API |
| `metatailor_rig` | Auto-rig .fbx with MetaTailor |
| `metatailor_clothe` | Add clothing to rigged character |
| `ueos_status` | Full connection health check |
| `ueos_diagnose` | Raw HTTP diagnostic to UE Remote Control |

### 🔍 Diagnostic Tools (3)

| Tool | Description |
|------|-------------|
| `ueos_status` | Connection health for all services |
| `ueos_diagnose` | Raw HTTP probe to UE port 30010 |
| `ueos_run_python` | Execute arbitrary Python inside UE editor |

---

## 💬 Example Prompts

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

"Full pipeline: take this concept art URL → generate 3D with Tripo →
 rig with MetaTailor → create Character Blueprint BP_Hero at 
 /Game/Characters → compile"

"Create an AnimBlueprint ABP_Hero for /Game/Characters/SK_Hero_Skeleton.
 Add Speed(float), IsFalling(bool), IsAiming(bool) variables.
 Build a locomotion state machine with Idle/Walk/Run/Jump/Fall/Land states."

"Set up the full GAS stack for /Game/Characters/BP_Hero:
 add an AbilitySystemComponent (mixed replication),
 create AS_HeroBase AttributeSet with Health/MaxHealth/Mana/Stamina,
 create GA_FireBolt and GA_Shield abilities, create GE_FireDamage (-30 instant)
 and GE_ShieldBuff (+50 Armor for 10 seconds)."

"Create a destructible wall: convert SM_BrickWall at /Game/Meshes into a
 GeometryCollection at /Game/Chaos. Voronoi fracture with 30 cells.
 Set level-0 damage threshold to 500."

"Set up a forest biome PCG graph at /Game/PCG. Use SM_Oak and SM_Pine meshes.
 Surface sampler density 3.0, scale 0.8–1.2. Place a PCGVolume 5000×5000 at
 the world origin and generate it immediately."

"Create a complete Enhanced Input setup for a third-person character at /Game/Input.
 Generate IA_Move (axis2D), IA_Look (axis2D), IA_Jump (bool), IA_Sprint (bool).
 Create IMC_Default, bind WASD+mouse+gamepad."
```

---

## 📁 File Structure

```
ueos/
├── .env                        ← Live config (never committed)
├── .env.example                ← Template
├── .gitignore
├── requirements.txt
├── README.md
├── UEOS_SYSTEM_PROMPT.md       ← 74KB behavioral system prompt
├── UEOS.bat                    ← Daily launcher (double-click after first setup)
├── SETUP.bat                   ← First-time setup (double-click once)
├── FIX_CLAUDE_CONFIG.bat       ← Re-write claude_desktop_config.json
├── INSTALL_BRIDGE.ps1          ← PowerShell bridge installer
├── ui/
│   └── launcher.py             ← 5-tab tkinter GUI
├── mcp_server/
│   ├── server.py               ← MCP entry point (339 tools)
│   ├── ueos.log                ← Runtime log (auto-created)
│   ├── remote_control/
│   │   └── client.py           ← UE 5.4 HTTP client w/ retry
│   ├── api_clients/
│   │   ├── tripo.py
│   │   ├── huanyuan.py
│   │   └── metatailor.py
│   └── tools/
│       ├── blueprint.py        ← 17 tools
│       ├── material.py         ← 14 tools
│       ├── niagara.py          ← 20 tools
│       ├── inspection.py       ← 12 tools
│       ├── scene.py            ← 16 tools
│       ├── data.py             ← 15 tools
│       ├── animation.py        ← 22 tools  Phase 3
│       ├── umg.py              ← 20 tools  Phase 4
│       ├── sequencer.py        ← 18 tools  Phase 4
│       ├── behavior_tree.py    ← 17 tools  Phase 4
│       ├── editor_widget.py    ← 20 tools  Phase 5
│       ├── gameplay_ability.py ← 20 tools  Phase 6
│       ├── environment_query.py ← 20 tools  Phase 6
│       ├── navmesh.py          ← 17 tools  Phase 6
│       ├── chaos_physics.py    ← 25 tools  Phase 7
│       ├── pcg.py              ← 21 tools  Phase 7
│       ├── enhanced_input.py   ← 18 tools  Phase 7
│       └── metasound.py        ← 17 tools  Phase 7
├── ue_scripts/                 ← Run INSIDE UE editor
│   ├── ueos_utils.py
│   ├── animation_utils.py
│   ├── umg_utils.py
│   ├── sequencer_utils.py
│   ├── editor_widget_utils.py
│   ├── gas_utils.py
│   ├── eqs_utils.py
│   ├── navmesh_utils.py
│   ├── chaos_utils.py
│   ├── pcg_utils.py
│   ├── input_utils.py
│   └── metasound_utils.py
├── setup/
│   ├── install.py              ← pip install + wizard launcher
│   ├── configure.py            ← interactive API key wizard
│   ├── inject_claude_config.py ← auto-writes claude_desktop_config.json
│   └── inject_ue_settings.py   ← auto-patches UE project settings
└── config/
    └── claude_desktop_config.json  ← template (not your live config)
```

---

## 📈 Phase History

| Phase | Status | Tools Added | Total |
|-------|--------|-------------|-------|
| Phase 1 | ✅ | Blueprint (17), Pipeline (8+3), GUI | 28 |
| Phase 2 | ✅ | Material (14), Niagara (20), Inspection (12), Scene (16), Data (15) | 105 |
| Phase 3 | ✅ | Animation (22) | 127 |
| Phase 4 | ✅ | UMG (20), Sequencer (18), Behavior Trees (17) | 182 |
| Phase 5 | ✅ | Editor Utility Widgets (20) | 202 |
| Phase 6 | ✅ | GAS (20), EQS (20), NavMesh (17) | 259 |
| Phase 7 | ✅ | Chaos Physics (25), PCG (21), Enhanced Input (18), MetaSounds (17) | 339 |

---

*Last updated: Phase 7 complete — 339 tools*
