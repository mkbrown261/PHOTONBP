# UEOS — Unreal Engine Operating System
### AI-Driven Unreal Engine 5.4 Development via MCP

---

## What This Is

UEOS connects Claude (or any MCP-compatible AI) directly to Unreal Engine 5.4.
No C++. No screenshots. Structured API calls only.

The AI reads, creates, edits, compiles, and validates every major UE asset type
through Python Editor Scripting and the Remote Control API.

---

## Architecture

```
Claude Desktop
      ↓ MCP protocol
UEOS MCP Server (Python, local)
      ↓ HTTP port 30010
Unreal Remote Control API (built-in UE plugin)
      ↓ executes
Python Editor Scripts (run inside UE 5.4)
      ↓
All Unreal Engine asset APIs
```

---

## Quick Setup

### Step 1 — Clone / place this folder
```
C:\UEOS\
```

### Step 2 — Run setup
```bash
python setup/install.py
```

### Step 3 — Fill in .env
```
TRIPO_API_KEY=your_key_here
```

### Step 4 — Enable UE Plugins
In Unreal Engine 5.4: Edit → Plugins, enable:
- ✅ Python Editor Script Plugin
- ✅ Remote Control API
- ✅ Remote Control Logic
- ✅ Editor Scripting Utilities
- ✅ Niagara

Then: Edit → Project Settings → Plugins → Remote Control → Allow remote = ON

### Step 5 — Add to Claude Desktop config
See `config/claude_desktop_config.json`

### Step 6 — Verify
```bash
python setup/verify.py
```

### Step 7 — Test in Claude
```
ueos_status
```

---

## Available Tools (Phase 1)

### Connection
| Tool | Description |
|------|-------------|
| `ueos_status` | Check all service connections |

### Blueprint Engineering
| Tool | Description |
|------|-------------|
| `blueprint_create` | Create any Blueprint type |
| `blueprint_add_variable` | Add typed variables |
| `blueprint_add_function` | Add functions with params |
| `blueprint_add_event` | Add custom events |
| `blueprint_add_node` | Add nodes to graphs |
| `blueprint_connect_pins` | Wire nodes together |
| `blueprint_add_component` | Add components |
| `blueprint_add_interface` | Implement interfaces |
| `blueprint_add_dispatcher` | Add event dispatchers |
| `blueprint_set_construction_script` | Build construction script (auto Leader Pose) |
| `blueprint_add_timeline` | Add timeline with tracks |
| `blueprint_compile` | Compile + get errors |
| `blueprint_save` | Save to disk |
| `blueprint_read` | Read as JSON |
| `blueprint_validate` | Validate without compile |
| `blueprint_delete` | Delete asset |
| `blueprint_reparent` | Change parent class |

### Asset Generation (Tripo)
| Tool | Description |
|------|-------------|
| `tripo_generate_from_text` | Text → 3D model |
| `tripo_generate_from_image` | Concept art → 3D model |
| `tripo_get_task_status` | Poll generation status |
| `tripo_import_to_unreal` | Import model into UE |

### Asset Generation (Huanyuan)
| Tool | Description |
|------|-------------|
| `huanyuan_generate_from_image` | Image → 3D model |

### Character Pipeline
| Tool | Description |
|------|-------------|
| `metatailor_rig_character` | Auto-rig character mesh |
| `pipeline_concept_to_character` | Full pipeline: art → UE character |

---

## Phase Roadmap

- ✅ **Phase 1**: Blueprint engine + Tripo/Huanyuan/MetaTailor integration
- ⏳ **Phase 2**: Material graph editing, Niagara particle systems
- ⏳ **Phase 3**: Animation Blueprints, state machines, montages
- ⏳ **Phase 4**: UMG widgets, Sequencer, Behavior Trees
- ⏳ **Phase 5**: Editor Utility Widget panel (native UE UI)

---

## Example Usage in Claude

```
Create a Character Blueprint called BP_SwordsmanCharacter in /Game/Characters
with Health (float, exposed), MaxHealth (float), IsAlive (bool) variables,
a TakeDamage function with float DamageAmount input,
add SkeletalMeshComponent and CapsuleComponent,
compile and save.
```

```
Generate a 3D character model from this concept art [image],
import it into /Game/Characters/Swordsman,
create a Character Blueprint with it,
set up Leader Pose Component in the construction script.
```

---

## File Structure

```
ueos/
├── mcp_server/
│   ├── server.py              ← MCP server entry point
│   ├── tools/
│   │   ├── blueprint.py       ← Blueprint tools (Phase 1)
│   │   ├── material.py        ← (Phase 2)
│   │   ├── niagara.py         ← (Phase 2)
│   │   ├── animation.py       ← (Phase 3)
│   │   ├── data.py            ← (Phase 3)
│   │   ├── umg.py             ← (Phase 4)
│   │   ├── sequencer.py       ← (Phase 4)
│   │   ├── inspection.py      ← (Phase 2)
│   │   └── scene.py           ← (Phase 2)
│   ├── remote_control/
│   │   └── client.py          ← UE HTTP client
│   └── api_clients/
│       ├── tripo.py           ← Tripo 3D API
│       ├── huanyuan.py        ← Huanyuan3D API
│       └── metatailor.py      ← MetaTailor API
├── setup/
│   ├── install.py             ← One-command setup
│   └── verify.py              ← Connection verification
├── config/
│   └── claude_desktop_config.json
├── .env                       ← Your API keys (never commit)
├── .env.example               ← Template
├── requirements.txt
└── README.md
```
