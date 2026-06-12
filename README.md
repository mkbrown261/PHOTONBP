# UEOS — Unreal Engine Operating System

**Version 4.0.0 — Phase 4 Complete: UMG + Sequencer + Behavior Trees**

AI-driven Unreal Engine 5.4 development system. Claude controls the UE editor
through **182 MCP tools** via the Remote Control API. Zero C++. Pure Python.

---

## 🖥️ GUI Launcher (Recommended)

Double-click **`UEOS.bat`** on Windows — that's it.

The GUI launcher opens a full desktop application with 5 tabs:

| Tab | What it does |
|-----|-------------|
| **Dashboard** | Live status of UE, Tripo, Huanyuan, MetaTailor. Start/Stop MCP server. |
| **API Keys** | Enter & validate Tripo / Huanyuan / MetaTailor keys. Masked by default. |
| **Settings** | UE Remote Control host/port, temp directory, log level. |
| **Claude Setup** | Auto-detects your Claude Desktop config and writes the UEOS entry for you. |
| **Log** | Live color-coded tail of `ueos.log`. |

> **First launch:** the API Keys tab opens automatically so you can enter your Tripo key and validate it before starting the server.

```
UEOS/
└── UEOS.bat   ← double-click this
```

---

## Quick Start (Command Line)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run setup wizard (configures API keys interactively)
python setup/install.py

# 3. (Optional) Verify all connections
python setup/verify.py

# 4. Launch the GUI
python ui/launcher.py

# — OR start the MCP server directly —
python mcp_server/server.py
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
mcp_server/server.py          ← 202 tools registered
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
     └── tools/editor_widget.py  ← 20 tools: EUW panels, menus, UEOS panel    ← NEW Phase 5
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

### 🗄️ Data Tools (15)

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

### 🎬 Animation Tools (22)

| Tool | Description |
|------|-------------|
| `anim_create_anim_blueprint` | Create AnimBlueprint for a skeleton |
| `anim_set_anim_graph_variable` | Add/update variable in AnimBP (Speed, IsFalling, etc.) |
| `anim_create_state_machine` | Add State Machine node to AnimBP Anim Graph |
| `anim_add_state` | Add state to State Machine (Idle, Walk, Run, Jump…) |
| `anim_add_transition` | Add transition rule between two states |
| `anim_set_state_animation` | Bind AnimSequence or BlendSpace to a state |
| `anim_add_blend_tree` | Insert weighted blend tree inside a state |
| `anim_create_blend_space` | Create 2D BlendSpace (Speed × Direction) |
| `anim_create_blend_space_1d` | Create 1D BlendSpace (single axis) |
| `anim_add_blend_space_sample` | Add animation sample to BlendSpace |
| `anim_create_montage` | Create AnimMontage from AnimSequence |
| `anim_add_montage_section` | Add named section to montage (WindUp, HitFrame…) |
| `anim_add_montage_notify` | Add AnimNotify to montage track |
| `anim_set_montage_slot` | Set slot (DefaultSlot, UpperBody, FullBody) |
| `anim_get_montage_info` | Inspect montage sections, notifies, slots |
| `anim_list_sequences` | List all AnimSequences for a skeleton |
| `anim_get_sequence_info` | Get length/rate/notifies for a sequence |
| `anim_add_notify_to_sequence` | Add AnimNotify to raw AnimSequence |
| `anim_retarget_pose` | Set retarget pose on skeleton |
| `anim_create_ik_rig` | Create IKRig Definition asset |
| `anim_set_ik_goal` | Add IK goal to IKRig (LeftFoot, RightHand…) |
| `anim_compile_anim_blueprint` | Force compile AnimBP, return errors/warnings |

**Blend Space axis presets:** `speed` `direction` `yaw` `lean` `aim_pitch` `aim_yaw`

---

### 🖼️ UMG Widget Tools (20) — NEW Phase 4

| Tool | Description |
|------|-------------|
| `umg_create_widget` | Create a new WidgetBlueprint asset |
| `umg_add_text` | Add TextBlock widget to canvas panel |
| `umg_add_button` | Add Button widget with child label text |
| `umg_add_image` | Add Image widget, optionally bind Texture2D |
| `umg_add_progress_bar` | Add ProgressBar with fill color and percent |
| `umg_add_slider` | Add Slider widget with min/max/value |
| `umg_add_input_field` | Add EditableTextBox input widget |
| `umg_add_checkbox` | Add CheckBox widget with label |
| `umg_add_combobox` | Add ComboBoxString with option list |
| `umg_add_scroll_box` | Add ScrollBox container widget |
| `umg_add_canvas_panel` | Add nested CanvasPanel |
| `umg_add_horizontal_box` | Add HorizontalBox layout container |
| `umg_add_vertical_box` | Add VerticalBox layout container |
| `umg_add_overlay` | Add Overlay container widget |
| `umg_add_named_slot` | Add NamedSlot for child widget injection |
| `umg_bind_variable` | Add Blueprint variable for data binding |
| `umg_add_widget_animation` | Add named UMG animation track |
| `umg_set_widget_style` | Update style properties (font, color, size) |
| `umg_create_hud` | Build complete HUD from preset template |
| `umg_compile_widget` | Compile and save WidgetBlueprint |

**HUD presets:** `fps` · `rpg` · `main_menu` · `pause_menu` · `inventory`

**Anchor presets:** `top_left` · `top_center` · `top_right` · `center_left` · `center` · `center_right` · `bottom_left` · `bottom_center` · `bottom_right` · `full_stretch`

---

### 🎥 Sequencer Tools (18) — NEW Phase 4

| Tool | Description |
|------|-------------|
| `seq_create_sequence` | Create new LevelSequence asset with fps/duration |
| `seq_set_playback_range` | Set start/end frames on a sequence |
| `seq_add_camera_cut_track` | Add CameraCutTrack to sequence |
| `seq_add_camera_cut` | Add camera cut section (start→end, camera binding) |
| `seq_add_actor_track` | Bind a world actor to the sequence |
| `seq_add_transform_key` | Set location/rotation/scale keyframe on actor binding |
| `seq_add_property_track` | Add bool/float/color property track on actor component |
| `seq_add_property_key` | Set property value keyframe on property track |
| `seq_add_audio_track` | Add audio track to sequence |
| `seq_add_audio_section` | Place SoundBase at time offset with volume/pitch |
| `seq_add_fade_track` | Add MovieSceneFadeTrack (black screen in/out) |
| `seq_add_fade_key` | Set fade alpha value at frame |
| `seq_add_sub_sequence` | Embed child LevelSequence as sub-sequence track |
| `seq_add_event_track` | Add event track for Blueprint event triggers |
| `seq_add_event_key` | Add event key at frame to fire Blueprint event |
| `seq_list_tracks` | List all tracks in a sequence (type, sections) |
| `seq_get_info` | Full sequence info: fps, range, bindings, tracks |
| `seq_play_in_editor` | Open sequence in Sequencer and play in editor |

---

### 🌲 Behavior Tree Tools (17) — NEW Phase 4

| Tool | Description |
|------|-------------|
| `bt_create_blackboard` | Create BlackboardData asset |
| `bt_add_blackboard_key` | Add typed key to Blackboard (object/vector/bool/float/int/string/name) |
| `bt_get_blackboard_keys` | Read all keys from a Blackboard |
| `bt_create_behavior_tree` | Create BehaviorTree asset, optionally bind Blackboard |
| `bt_add_selector` | Add Selector composite node (tries children until one succeeds) |
| `bt_add_sequence` | Add Sequence composite node (runs children in order) |
| `bt_add_parallel` | Add SimpleParallel composite node |
| `bt_add_task` | Add built-in task node (MoveTo, Wait, RotateTo, etc.) |
| `bt_add_decorator` | Add decorator to composite (Blackboard check, Loop, Timer, etc.) |
| `bt_add_service` | Add service to composite (run on tick while active) |
| `bt_create_custom_task` | Create new BTTask_BlueprintBase asset with custom logic |
| `bt_create_custom_decorator` | Create new BTDecorator_BlueprintBase asset |
| `bt_create_custom_service` | Create new BTService_BlueprintBase asset |
| `bt_set_ai_controller` | Configure AIController on a Character Blueprint |
| `bt_get_tree_info` | Inspect BT structure: composites, tasks, decorators |
| `bt_create_ai_character` | Create full AI character: BP + Controller + BT + BB |
| `bt_create_patrol_tree` | Build complete patrol Behavior Tree in one call |

**Built-in tasks:** `move_to` · `wait` · `rotate_to` · `run_eqs` · `play_anim` · `play_sound` · `clear_bb_value` · `make_noise` · `move_directly_toward` · `set_bb_value` · `finish_with_result`

**Built-in decorators:** `blackboard` · `loop` · `timer` · `cone_check` · `force_success` · `does_path_exist` · `is_at_location` · `cooldown` · `gameplay_tag` · `compare_bb_entries` · `time_limit`

**Built-in services:** `default_focus` · `run_eqs` · `update_cooldown` · `gameplay_tag_condition`

**Blackboard key types:** `object` · `vector` · `bool` · `float` · `int` · `string` · `name` · `enum` · `rotator` · `class`

---

### 🪩 Editor Utility Widget Tools (20) — NEW Phase 5

| Tool | Description |
|------|-------------|
| `ew_create_utility_widget` | Create EditorUtilityWidget Blueprint asset |
| `ew_open_panel` | Open EUW as docked tab in the UE editor |
| `ew_close_panel` | Close a registered EUW tab |
| `ew_list_panels` | List all EUW panels in a content path |
| `ew_add_text_to_panel` | Add TextBlock widget to EUW canvas |
| `ew_add_button_to_panel` | Add Button with optional on-click Python script |
| `ew_add_progress_bar_to_panel` | Add ProgressBar (loading/import indicators) |
| `ew_add_list_view` | Add scrollable item list (ScrollBox + VerticalBox) |
| `ew_add_tab_widget` | Add WidgetSwitcher tabbed container |
| `ew_set_panel_title` | Rename the docked tab label |
| `ew_compile_panel` | Compile and save EUW Blueprint |
| `ew_add_tool_menu_entry` | Add entry to UE menus (Tools / Window / Help) |
| `ew_remove_tool_menu_entry` | Remove a custom menu entry |
| `ew_post_status_bar_message` | Post text + progress to UE status bar |
| `ew_create_ueos_panel` | **Build the full 5-tab UEOS control panel** in one call |
| `ew_refresh_ueos_status` | Force-refresh UEOS status indicators in the panel |
| `ew_add_property_inspector` | Add Details View (property inspector) to an EUW |
| `ew_add_output_log_widget` | Add scrollable read-only log text widget |
| `ew_register_on_tick` | Bind Blueprint function to Editor tick event |
| `ew_unregister_on_tick` | Remove Editor tick binding |

**UEOS Panel — 5 tabs:**

| Tab | Contents |
|-----|----------|
| **Status** | Live connection dots (UE/Tripo/Huanyuan/MetaTailor) · phase summary · Refresh button |
| **Tools** | Category grid (12 categories · 202 tools) · search box |
| **Log** | Scrollable operation log · Clear/Copy buttons |
| **Settings** | UE host/port · API key inputs · log level picker · Save/Reset |
| **Pipeline** | Concept → character one-click launcher · service picker · progress bar |

**Install the panel from UE Python console (no MCP needed):**
```python
import sys, importlib
sys.path.insert(0, r"C:\UEOS\ue_scripts")
import editor_widget_utils as ewu; importlib.reload(ewu)
ewu.ueos_install_panel()          # creates + opens panel + adds Tools menu entry
```

**Or via Claude Desktop:**
```
"Create the UEOS control panel"
→ calls ew_create_ueos_panel() → 5-tab dockable panel opens in UE immediately
```

---

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

| Script | Public Functions | Purpose |
|--------|-----------------|---------|
| `ueos_utils.py` | 40+ | General helpers: assets, BPs, materials, actors, data |
| `animation_utils.py` | 16 | Locomotion SM, attack pipeline, footsteps, IK |
| `umg_utils.py` | 18 | Widget builders, HUD presets, style helpers |
| `sequencer_utils.py` | 14 | Cutscene builder, camera dolly, fade/audio tracks |
| `editor_widget_utils.py` | 17 | EUW builder, UEOS panel, menus, status bar ← NEW |
| `bulk_compile_blueprints.py` | — | Compile all BPs under path |
| `import_fbx_batch.py` | — | Batch FBX import with full options |
| `setup_character_bp.py` | — | Complete Character BP with mesh/anim/clothing |
| `material_instance_factory.py` | — | Batch Material Instance creation |
| `datatable_batch_ops.py` | — | Merge/export/import/search DataTables |
| `scene_snapshot.py` | — | Full level JSON snapshot |

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

| Phase | Status | Scope | Tools |
|-------|--------|-------|-------|
| Phase 1 | ✅ Complete | Blueprint (17), Pipeline (8+3), GUI Launcher | 28 |
| Phase 2 | ✅ Complete | Material (14), Niagara (20), Inspection (12), Scene (16), Data (15) | 77 |
| Phase 3 | ✅ Complete | Animation (22): AnimBP, State Machines, BlendSpaces, Montages, IK | 22 |
| Phase 4 | ✅ Complete | UMG (20), Sequencer (18), Behavior Trees (17) | 55 |
| **Total** | | | **182** |
| Phase 5 | ✅ Complete | Editor Utility Widgets (20): dockable UEOS panel, menus, status bar | 20 |
| **Total** | | | **202** |
| Phase 6 | ⏳ Planned | Enhanced Gameplay: GAS (Ability System), EQS (Environment Queries), NavMesh | TBD |

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

"Create an AnimBlueprint ABP_Hero for /Game/Characters/SK_Hero_Skeleton.
 Add Speed(float), IsFalling(bool), IsAiming(bool) variables.
 Build a locomotion state machine with Idle/Walk/Run/Jump/Fall/Land states."

"Create BlendSpace1D BS1D_Speed for SK_Mannequin_Skeleton.
 Speed axis 0→600. Samples: AS_Idle at 0, AS_Walk at 200, AS_Run at 450."

"Create attack montage AM_SwordSlash_01 from AS_SwordSlash_01.
 Slot: UpperBody. Add sections WindUp(0.1s), HitFrame(0.35s), Recovery(0.7s).
 Add hit-window notify state 0.35→0.55s."

"Create IKRig IK_Mannequin for SK_Mannequin_Skeleton.
 Add foot IK goals: LeftFoot on foot_l, RightFoot on foot_r."

"Build an FPS HUD WBP_PlayerHUD at /Game/UI with health bar, 
 stamina bar, ammo counter, crosshair, and minimap slot."

"Create a Main Menu WBP_MainMenu at /Game/UI/Menus with 
 Play, Settings, and Quit buttons. Use the main_menu preset."

"Create a Level Sequence LS_BossIntro at /Game/Cinematics, 10 seconds, 
 30fps. Add camera cut track for CineCameraActor_0. Add fade in (1s) 
 and fade out (1s). Add background music from /Game/Audio/Boss_Theme."

"Create a complete AI character: BP_Guard with AIController, 
 Blackboard with TargetActor/PatrolTarget/bIsAlerted keys, 
 and a patrol BehaviorTree at /Game/AI."

"Build a patrol Behavior Tree BT_Guard at /Game/AI.
 Blackboard: /Game/AI/BB_Guard.
 Patrol waypoints with random wait, alert on sight with MoveTo chase."

"Create the UEOS control panel"

"Add a custom Tools menu entry 'Compile All BPs' that compiles
 every Blueprint under /Game."

"Create a custom editor tool EUW_LightPlacer at /Game/EditorTools with
 three buttons: Add Point Light, Add Spot Light, Add Directional Light.
 Each button runs the matching scene_ tool on click."

"Build an editor progress panel EUW_ImportStatus at /Game/EditorTools.
 Add a progress bar ImportProgress, a TextBlock StatusLabel,
 and a Cancel button. Open it as a docked tab."

"Post a status bar message: 'UEOS: Importing 42 assets… 67%'
 with progress 0.67."
```

---

## File Structure

```
ueos/
├── .env                        ← Live config (never committed)
├── .env.example                ← Template
├── .gitignore
├── requirements.txt
├── README.md
├── UEOS.bat                    ← Windows double-click launcher
├── ui/
│   ├── __init__.py
│   └── launcher.py             ← 5-tab tkinter GUI (993 lines)
├── mcp_server/
│   ├── server.py               ← MCP entry point (202 tools)
│   ├── remote_control/
│   │   └── client.py           ← UE 5.4 HTTP client w/ retry
│   ├── api_clients/
│   │   ├── tripo.py
│   │   ├── huanyuan.py
│   │   └── metatailor.py
│   └── tools/
│       ├── blueprint.py        ← 17 tools ✅
│       ├── material.py         ← 14 tools ✅
│       ├── niagara.py          ← 20 tools ✅
│       ├── inspection.py       ← 12 tools ✅
│       ├── scene.py            ← 16 tools ✅
│       ├── data.py             ← 15 tools ✅
│       ├── animation.py        ← 22 tools ✅ Phase 3
│       ├── umg.py              ← 20 tools ✅ Phase 4
│       ├── sequencer.py        ← 18 tools ✅ Phase 4
│       ├── behavior_tree.py    ← 17 tools ✅ Phase 4
│       └── editor_widget.py    ← 20 tools ✅ Phase 5
├── ue_scripts/                 ← Run INSIDE UE editor
│   ├── ueos_utils.py           ← 40+ helper functions
│   ├── animation_utils.py      ← 16 animation helpers ✅ Phase 3
│   ├── umg_utils.py            ← 18 UMG helpers          ✅ Phase 4
│   ├── sequencer_utils.py      ← 14 sequencer helpers    ✅ Phase 4
│   ├── editor_widget_utils.py  ← 17 EUW helpers + panel  ✅ Phase 5
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

*Last updated: Phase 5 complete — 202 tools*
