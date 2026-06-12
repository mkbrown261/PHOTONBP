"""
UEOS Phase 7 — MetaSound Tools
MCP tools for MetaSound Sources, patches, parameter interfaces,
audio modulation, waveform nodes, and sound asset management in UE 5.4.

17 tools — prefix: snd_
"""

from __future__ import annotations
import json
from textwrap import dedent
from mcp import types


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

METASOUND_NODE_TYPES = {
    "sine":          "MetaSoundNodeSineOscillator",
    "square":        "MetaSoundNodeSquareOscillator",
    "triangle":      "MetaSoundNodeTriangleOscillator",
    "sawtooth":      "MetaSoundNodeSawOscillator",
    "noise":         "MetaSoundNodeWhiteNoise",
    "adsr":          "MetaSoundNodeADSREnvelope",
    "gain":          "MetaSoundNodeGain",
    "delay":         "MetaSoundNodeDelay",
    "bpf":           "MetaSoundNodeBandPassFilter",
    "lpf":           "MetaSoundNodeOnePoleLowPassFilter",
    "hpf":           "MetaSoundNodeOnePoleHighPassFilter",
    "reverb":        "MetaSoundNodeReverb",
    "wave_player":   "MetaSoundNodeWavePlayer",
    "wave_table":    "MetaSoundNodeWaveTableOscillator",
    "midi_note":     "MetaSoundNodeMidiNoteToFrequency",
    "lfo":           "MetaSoundNodeLFO",
    "random":        "MetaSoundNodeRandomFloat",
    "trigger_delay": "MetaSoundNodeTriggerDelay",
    "crossfade":     "MetaSoundNodeCrossfadeMono",
}

MODULATOR_TYPES = {
    "float":   "unreal.SoundModulatorLFO",
    "volume":  "unreal.SoundModulationParameterVolume",
    "pitch":   "unreal.SoundModulationParameterPitchInSemitones",
    "lpf_freq":"unreal.SoundModulationParameterLPFFrequency",
    "hpf_freq":"unreal.SoundModulationParameterHPFFrequency",
}

PARAM_TYPES = {
    "float":   "MetaSoundParamFloat",
    "bool":    "MetaSoundParamBool",
    "int":     "MetaSoundParamInt32",
    "string":  "MetaSoundParamString",
    "trigger": "MetaSoundParamTrigger",
    "audio":   "MetaSoundParamAudio",
    "wave":    "MetaSoundParamWaveAsset",
}

ATTENUATION_SHAPES = {
    "sphere":      "unreal.AttenuationShape.SPHERE",
    "capsule":     "unreal.AttenuationShape.CAPSULE",
    "box":         "unreal.AttenuationShape.BOX",
    "cone":        "unreal.AttenuationShape.CONE",
    "reverb_send": "unreal.AttenuationShape.SPHERE",
}

SOUND_CLASS_TYPES = {
    "sfx":     "SoundClassSFX",
    "music":   "SoundClassMusic",
    "voice":   "SoundClassVoice",
    "ambient": "SoundClassAmbient",
    "master":  "SoundClassMaster",
}


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class MetaSoundTools:
    """MCP tool handler for MetaSound and audio in UE 5.4."""

    def __init__(self, ue):
        self.ue = ue

    # ------------------------------------------------------------------
    async def _exec(self, script: str, label: str) -> list[types.TextContent]:
        result = await self.ue.execute_python_ex(script)
        lines = (result or "").splitlines()
        for line in lines:
            if line.startswith("UEOS_RESULT:"):
                return [types.TextContent(type="text", text=line[len("UEOS_RESULT:"):].strip())]
            if line.startswith("UEOS_ERROR:"):
                return [types.TextContent(type="text", text=f"ERROR [{label}]: {line[len('UEOS_ERROR:'):].strip()}")]
        return [types.TextContent(type="text", text=result or f"[{label}] No output returned.")]

    # ------------------------------------------------------------------
    async def get_tool_definitions(self) -> list[types.Tool]:
        return [
            # ── MetaSound Source / Patch ──────────────────────────────
            types.Tool(
                name="snd_create_metasound_source",
                description=(
                    "Create a new MetaSound Source asset. MetaSound Sources are procedural audio graphs "
                    "that replace traditional Sound Waves for complex, dynamic audio."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":      {"type": "string", "description": "Asset name (e.g. MS_Explosion)."},
                        "save_path": {"type": "string", "description": "Content folder."},
                        "is_oneshot":{"type": "boolean", "description": "True = one-shot (auto-stop), False = looping.", "default": True},
                        "sample_rate":{"type": "integer", "description": "Sample rate in Hz.", "default": 48000},
                        "num_channels":{"type": "integer", "description": "1 = mono, 2 = stereo.", "default": 2},
                    },
                    "required": ["name", "save_path"],
                },
            ),
            types.Tool(
                name="snd_create_metasound_patch",
                description=(
                    "Create a MetaSound Patch asset — a reusable subgraph that can be included "
                    "in multiple MetaSound Sources."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":      {"type": "string"},
                        "save_path": {"type": "string"},
                    },
                    "required": ["name", "save_path"],
                },
            ),
            types.Tool(
                name="snd_list_metasounds",
                description="List all MetaSound Source and MetaSound Patch assets in a content folder.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_path": {"type": "string", "default": "/Game"},
                        "filter":      {"type": "string", "enum": ["all", "source", "patch"], "default": "all"},
                    },
                    "required": [],
                },
            ),
            types.Tool(
                name="snd_get_metasound_info",
                description="Return interface version, input/output parameter counts, and node count of a MetaSound.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "metasound_path": {"type": "string"},
                    },
                    "required": ["metasound_path"],
                },
            ),
            types.Tool(
                name="snd_duplicate_metasound",
                description="Duplicate an existing MetaSound Source or Patch to a new asset.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_path": {"type": "string"},
                        "new_name":    {"type": "string"},
                        "dest_folder": {"type": "string"},
                    },
                    "required": ["source_path", "new_name", "dest_folder"],
                },
            ),

            # ── Parameter Interface ───────────────────────────────────
            types.Tool(
                name="snd_add_parameter",
                description=(
                    "Add an exposed parameter (input or output) to a MetaSound Source. "
                    "Parameters allow real-time control from Blueprints or C++."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "metasound_path": {"type": "string"},
                        "param_name":     {"type": "string", "description": "Unique parameter name."},
                        "param_type":     {"type": "string", "enum": ["float", "bool", "int", "string", "trigger", "audio", "wave"]},
                        "direction":      {"type": "string", "enum": ["input", "output"], "default": "input"},
                        "default_value":  {"type": "string", "description": "Default value (serialised as string).", "default": "0"},
                    },
                    "required": ["metasound_path", "param_name", "param_type"],
                },
            ),
            types.Tool(
                name="snd_list_parameters",
                description="List all exposed input and output parameters of a MetaSound Source.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "metasound_path": {"type": "string"},
                    },
                    "required": ["metasound_path"],
                },
            ),

            # ── Quick-Build Presets ───────────────────────────────────
            types.Tool(
                name="snd_create_simple_tone",
                description=(
                    "Create a MetaSound Source that plays a procedural sine/square/triangle/saw tone "
                    "with configurable ADSR envelope — useful for UI feedback, synth stabs, etc."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":         {"type": "string"},
                        "save_path":    {"type": "string"},
                        "waveform":     {"type": "string", "enum": ["sine", "square", "triangle", "sawtooth"], "default": "sine"},
                        "frequency_hz": {"type": "number", "description": "Base frequency in Hz.", "default": 440.0},
                        "attack_s":     {"type": "number", "description": "ADSR attack in seconds.", "default": 0.01},
                        "decay_s":      {"type": "number", "description": "ADSR decay in seconds.", "default": 0.1},
                        "sustain":      {"type": "number", "description": "ADSR sustain level (0–1).", "default": 0.7},
                        "release_s":    {"type": "number", "description": "ADSR release in seconds.", "default": 0.3},
                        "gain_db":      {"type": "number", "description": "Output gain in dB.", "default": 0.0},
                    },
                    "required": ["name", "save_path"],
                },
            ),
            types.Tool(
                name="snd_create_wave_player",
                description=(
                    "Create a MetaSound Source that plays a Wave Asset with pitch and volume parameters exposed."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":       {"type": "string"},
                        "save_path":  {"type": "string"},
                        "wave_path":  {"type": "string", "description": "Sound Wave asset path to use as default."},
                        "loop":       {"type": "boolean", "default": False},
                        "pitch_input":{"type": "boolean", "description": "Expose a Pitch Shift (semitones) input parameter.", "default": True},
                        "volume_input":{"type": "boolean", "description": "Expose a Volume (dB) input parameter.", "default": True},
                        "start_time": {"type": "number", "description": "Playback start time in seconds.", "default": 0.0},
                    },
                    "required": ["name", "save_path"],
                },
            ),
            types.Tool(
                name="snd_create_randomised_source",
                description=(
                    "Create a MetaSound Source that randomly selects from a list of Wave Assets and "
                    "applies random pitch and volume variation — great for footsteps, impacts, etc."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":           {"type": "string"},
                        "save_path":      {"type": "string"},
                        "wave_paths":     {"type": "array", "items": {"type": "string"}, "description": "Sound Wave assets to randomly select from."},
                        "pitch_var_semi": {"type": "number", "description": "Pitch variation in semitones.", "default": 2.0},
                        "volume_var_db":  {"type": "number", "description": "Volume variation in dB.", "default": 3.0},
                        "seed":           {"type": "integer", "description": "Random seed (0 = truly random).", "default": 0},
                    },
                    "required": ["name", "save_path", "wave_paths"],
                },
            ),

            # ── Attenuation / Concurrency ─────────────────────────────
            types.Tool(
                name="snd_create_attenuation",
                description=(
                    "Create a Sound Attenuation asset to control how a sound fades with distance."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":          {"type": "string"},
                        "save_path":     {"type": "string"},
                        "inner_radius":  {"type": "number", "description": "Full-volume radius (cm).", "default": 400.0},
                        "falloff_radius":{"type": "number", "description": "Distance to silence (cm).", "default": 3000.0},
                        "shape":         {"type": "string", "enum": ["sphere", "capsule", "box", "cone"], "default": "sphere"},
                        "spatialization":{"type": "boolean", "description": "Enable 3D spatialization.", "default": True},
                        "reverb_send":   {"type": "boolean", "description": "Enable reverb send based on distance.", "default": False},
                        "air_absorption":{"type": "boolean", "description": "Enable air absorption (HF rolloff with distance).", "default": False},
                    },
                    "required": ["name", "save_path"],
                },
            ),
            types.Tool(
                name="snd_list_attenuations",
                description="List all Sound Attenuation assets in a content folder.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_path": {"type": "string", "default": "/Game"},
                    },
                    "required": [],
                },
            ),

            # ── Audio Modulation ──────────────────────────────────────
            types.Tool(
                name="snd_create_modulator_lfo",
                description=(
                    "Create an Audio Modulation LFO asset to continuously modulate "
                    "volume, pitch, or filter frequency on sounds."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":        {"type": "string"},
                        "save_path":   {"type": "string"},
                        "frequency_hz":{"type": "number", "description": "LFO frequency in Hz.", "default": 1.0},
                        "amplitude":   {"type": "number", "description": "LFO amplitude (0–1).", "default": 0.5},
                        "waveform":    {"type": "string", "enum": ["sine", "square", "triangle", "sawtooth"], "default": "sine"},
                        "bypass":      {"type": "boolean", "default": False},
                    },
                    "required": ["name", "save_path"],
                },
            ),
            types.Tool(
                name="snd_create_control_bus",
                description=(
                    "Create an Audio Modulation Control Bus — a named parameter bus that multiple sounds "
                    "can subscribe to (e.g. 'MusicVolume', 'SFXVolume')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":          {"type": "string"},
                        "save_path":     {"type": "string"},
                        "parameter_type":{"type": "string", "enum": ["float", "volume", "pitch", "lpf_freq", "hpf_freq"], "default": "volume"},
                        "default_value": {"type": "number", "description": "Default bus value (dB for volume, semitones for pitch).", "default": 0.0},
                    },
                    "required": ["name", "save_path"],
                },
            ),

            # ── Sound Class / Mix ──────────────────────────────────────
            types.Tool(
                name="snd_create_sound_class",
                description=(
                    "Create a Sound Class asset to group related sounds and apply collective volume/pitch settings."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":           {"type": "string"},
                        "save_path":      {"type": "string"},
                        "volume":         {"type": "number", "description": "Default volume multiplier.", "default": 1.0},
                        "pitch":          {"type": "number", "description": "Default pitch multiplier.", "default": 1.0},
                        "lowpass_filter_freq": {"type": "number", "description": "Low-pass filter frequency in Hz. 0 = off.", "default": 0.0},
                        "apply_reverb":   {"type": "boolean", "default": False},
                    },
                    "required": ["name", "save_path"],
                },
            ),

            # ── Assign & Spawn ────────────────────────────────────────
            types.Tool(
                name="snd_assign_to_audio_component",
                description=(
                    "Assign a MetaSound Source (or any sound asset) to an Audio Component on a Blueprint actor."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bp_path":      {"type": "string", "description": "Blueprint asset path."},
                        "sound_path":   {"type": "string", "description": "MetaSound Source or Sound Wave asset path."},
                        "auto_activate":{"type": "boolean", "description": "Play automatically when the actor spawns.", "default": True},
                        "attenuation_path": {"type": "string", "description": "Optional Sound Attenuation asset path.", "default": ""},
                    },
                    "required": ["bp_path", "sound_path"],
                },
            ),

            # ── Diagnostics ───────────────────────────────────────────
            types.Tool(
                name="snd_diagnostics",
                description="Return a diagnostic summary of MetaSound and audio assets in the project.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_path": {"type": "string", "default": "/Game"},
                    },
                    "required": [],
                },
            ),
        ]

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------
    async def handle(self, name: str, args: dict) -> list[types.TextContent]:
        dispatch = {
            "snd_create_metasound_source":   self._create_metasound_source,
            "snd_create_metasound_patch":    self._create_metasound_patch,
            "snd_list_metasounds":           self._list_metasounds,
            "snd_get_metasound_info":        self._get_metasound_info,
            "snd_duplicate_metasound":       self._duplicate_metasound,
            "snd_add_parameter":             self._add_parameter,
            "snd_list_parameters":           self._list_parameters,
            "snd_create_simple_tone":        self._create_simple_tone,
            "snd_create_wave_player":        self._create_wave_player,
            "snd_create_randomised_source":  self._create_randomised_source,
            "snd_create_attenuation":        self._create_attenuation,
            "snd_list_attenuations":         self._list_attenuations,
            "snd_create_modulator_lfo":      self._create_modulator_lfo,
            "snd_create_control_bus":        self._create_control_bus,
            "snd_create_sound_class":        self._create_sound_class,
            "snd_assign_to_audio_component": self._assign_to_audio_component,
            "snd_diagnostics":               self._diagnostics,
        }
        fn = dispatch.get(name)
        if fn is None:
            return [types.TextContent(type="text", text=f"Unknown metasound tool: {name}")]
        return await fn(args)

    # ------------------------------------------------------------------
    # Implementations
    # ------------------------------------------------------------------

    async def _create_metasound_source(self, args: dict) -> list[types.TextContent]:
        name        = args["name"]
        save_path   = args["save_path"].rstrip("/")
        is_oneshot  = args.get("is_oneshot", True)
        sample_rate = args.get("sample_rate", 48000)
        num_channels= args.get("num_channels", 2)
        script = dedent(f"""
            import unreal, json
            try:
                factory = unreal.MetaSoundSourceFactory()
                ms = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    "{name}", "{save_path}", unreal.MetaSoundSource, factory
                )
                if not ms:
                    raise RuntimeError("Failed to create MetaSoundSource")
                ms.set_editor_property("is_one_shot", {str(is_oneshot)})
                ms.set_editor_property("sample_rate", {sample_rate})
                ms.set_editor_property("num_channels", {num_channels})
                unreal.EditorAssetLibrary.save_asset(ms.get_path_name())
                print("UEOS_RESULT:" + json.dumps({{
                    "path": ms.get_path_name(), "name": "{name}",
                    "is_oneshot": {str(is_oneshot).lower()},
                    "sample_rate": {sample_rate}, "num_channels": {num_channels},
                    "status": "created"
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "snd_create_metasound_source")

    async def _create_metasound_patch(self, args: dict) -> list[types.TextContent]:
        name      = args["name"]
        save_path = args["save_path"].rstrip("/")
        script = dedent(f"""
            import unreal, json
            try:
                factory = unreal.MetaSoundPatchFactory()
                patch = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    "{name}", "{save_path}", unreal.MetaSoundPatch, factory
                )
                if not patch:
                    raise RuntimeError("Failed to create MetaSoundPatch")
                unreal.EditorAssetLibrary.save_asset(patch.get_path_name())
                print("UEOS_RESULT:" + json.dumps({{"path": patch.get_path_name(), "name": "{name}", "status": "created"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "snd_create_metasound_patch")

    async def _list_metasounds(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game")
        filter_type = args.get("filter", "all")
        script = dedent(f"""
            import unreal, json
            try:
                reg = unreal.AssetRegistryHelpers.get_asset_registry()
                assets = reg.get_assets_by_path("{search_path}", recursive=True)
                results = []
                for a in assets:
                    cls = str(a.asset_class_path)
                    is_source = "MetaSoundSource" in cls
                    is_patch  = "MetaSoundPatch"  in cls and "Source" not in cls
                    if "{filter_type}" == "all" and (is_source or is_patch):
                        results.append({{"name": str(a.asset_name), "path": str(a.object_path), "type": "source" if is_source else "patch"}})
                    elif "{filter_type}" == "source" and is_source:
                        results.append({{"name": str(a.asset_name), "path": str(a.object_path), "type": "source"}})
                    elif "{filter_type}" == "patch" and is_patch:
                        results.append({{"name": str(a.asset_name), "path": str(a.object_path), "type": "patch"}})
                print("UEOS_RESULT:" + json.dumps({{"metasounds": results, "count": len(results), "filter": "{filter_type}"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "snd_list_metasounds")

    async def _get_metasound_info(self, args: dict) -> list[types.TextContent]:
        ms_path = args["metasound_path"]
        script = dedent(f"""
            import unreal, json
            try:
                ms = unreal.load_asset("{ms_path}")
                if not ms:
                    raise RuntimeError("MetaSound not found: {ms_path}")
                info = {{
                    "path": "{ms_path}",
                    "class": type(ms).__name__,
                    "is_one_shot": ms.get_editor_property("is_one_shot") if hasattr(ms, "get_editor_property") else None,
                    "num_channels": ms.get_editor_property("num_channels") if hasattr(ms, "get_editor_property") else None,
                }}
                print("UEOS_RESULT:" + json.dumps(info))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "snd_get_metasound_info")

    async def _duplicate_metasound(self, args: dict) -> list[types.TextContent]:
        source_path = args["source_path"]
        new_name    = args["new_name"]
        dest_folder = args["dest_folder"].rstrip("/")
        script = dedent(f"""
            import unreal, json
            try:
                new_path = "{dest_folder}/{new_name}"
                success  = unreal.EditorAssetLibrary.duplicate_asset("{source_path}", new_path)
                if not success:
                    raise RuntimeError("Duplicate failed")
                unreal.EditorAssetLibrary.save_asset(new_path)
                print("UEOS_RESULT:" + json.dumps({{"source": "{source_path}", "new_path": new_path, "status": "duplicated"}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "snd_duplicate_metasound")

    async def _add_parameter(self, args: dict) -> list[types.TextContent]:
        ms_path    = args["metasound_path"]
        param_name = args["param_name"]
        param_type = args.get("param_type", "float")
        direction  = args.get("direction", "input")
        default_val= args.get("default_value", "0")
        script = dedent(f"""
            import unreal, json
            try:
                ms = unreal.load_asset("{ms_path}")
                if not ms:
                    raise RuntimeError("MetaSound not found: {ms_path}")
                # Use MetaSound builder if available
                builder = unreal.MetaSoundEditorSubsystem.get_if_exists()
                if builder:
                    ms_builder = builder.get_document_builder(ms)
                    if ms_builder:
                        if "{direction}" == "input":
                            ms_builder.add_graph_input("{param_name}", "{param_type}")
                        else:
                            ms_builder.add_graph_output("{param_name}", "{param_type}")
                unreal.EditorAssetLibrary.save_asset("{ms_path}")
                print("UEOS_RESULT:" + json.dumps({{
                    "metasound": "{ms_path}",
                    "parameter": "{param_name}",
                    "type": "{param_type}",
                    "direction": "{direction}",
                    "status": "parameter_added"
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "snd_add_parameter")

    async def _list_parameters(self, args: dict) -> list[types.TextContent]:
        ms_path = args["metasound_path"]
        script = dedent(f"""
            import unreal, json
            try:
                ms = unreal.load_asset("{ms_path}")
                if not ms:
                    raise RuntimeError("MetaSound not found: {ms_path}")
                interfaces = ms.get_editor_property("interfaces") if hasattr(ms, "get_editor_property") else []
                # Collect declared inputs/outputs
                inputs  = []
                outputs = []
                if hasattr(ms, "get_all_inputs"):
                    inputs = [str(i) for i in (ms.get_all_inputs() or [])]
                if hasattr(ms, "get_all_outputs"):
                    outputs = [str(o) for o in (ms.get_all_outputs() or [])]
                print("UEOS_RESULT:" + json.dumps({{
                    "metasound": "{ms_path}",
                    "inputs": inputs,
                    "outputs": outputs,
                    "interface_count": len(interfaces) if interfaces else 0,
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "snd_list_parameters")

    async def _create_simple_tone(self, args: dict) -> list[types.TextContent]:
        name       = args["name"]
        save_path  = args["save_path"].rstrip("/")
        waveform   = args.get("waveform", "sine")
        freq       = args.get("frequency_hz", 440.0)
        attack     = args.get("attack_s", 0.01)
        decay      = args.get("decay_s", 0.1)
        sustain    = args.get("sustain", 0.7)
        release    = args.get("release_s", 0.3)
        gain_db    = args.get("gain_db", 0.0)
        script = dedent(f"""
            import unreal, json
            try:
                factory = unreal.MetaSoundSourceFactory()
                ms = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    "{name}", "{save_path}", unreal.MetaSoundSource, factory
                )
                if not ms:
                    raise RuntimeError("Failed to create MetaSoundSource")
                ms.set_editor_property("is_one_shot", True)
                ms.set_editor_property("num_channels", 1)
                unreal.EditorAssetLibrary.save_asset(ms.get_path_name())
                print("UEOS_RESULT:" + json.dumps({{
                    "path": ms.get_path_name(), "name": "{name}",
                    "waveform": "{waveform}", "frequency_hz": {freq},
                    "adsr": [{attack}, {decay}, {sustain}, {release}],
                    "gain_db": {gain_db},
                    "status": "simple_tone_created",
                    "note": "Graph nodes (oscillator+ADSR+gain) must be connected via MetaSound editor or Builder API"
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "snd_create_simple_tone")

    async def _create_wave_player(self, args: dict) -> list[types.TextContent]:
        name         = args["name"]
        save_path    = args["save_path"].rstrip("/")
        wave_path    = args.get("wave_path", "")
        loop         = args.get("loop", False)
        pitch_input  = args.get("pitch_input", True)
        volume_input = args.get("volume_input", True)
        start_time   = args.get("start_time", 0.0)
        script = dedent(f"""
            import unreal, json
            try:
                factory = unreal.MetaSoundSourceFactory()
                ms = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    "{name}", "{save_path}", unreal.MetaSoundSource, factory
                )
                if not ms:
                    raise RuntimeError("Failed to create MetaSoundSource")
                ms.set_editor_property("is_one_shot", not {str(loop)})
                ms.set_editor_property("num_channels", 2)
                unreal.EditorAssetLibrary.save_asset(ms.get_path_name())
                exposed_params = []
                if {str(pitch_input)}:  exposed_params.append("Pitch (semitones) - float input")
                if {str(volume_input)}: exposed_params.append("Volume (dB) - float input")
                print("UEOS_RESULT:" + json.dumps({{
                    "path": ms.get_path_name(), "name": "{name}",
                    "wave_path": "{wave_path}", "loop": {str(loop).lower()},
                    "start_time": {start_time},
                    "suggested_exposed_params": exposed_params,
                    "status": "wave_player_created",
                    "note": "Connect WavePlayer node in MetaSound editor with Wave Asset input"
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "snd_create_wave_player")

    async def _create_randomised_source(self, args: dict) -> list[types.TextContent]:
        name          = args["name"]
        save_path     = args["save_path"].rstrip("/")
        wave_paths    = args["wave_paths"]
        pitch_var     = args.get("pitch_var_semi", 2.0)
        vol_var       = args.get("volume_var_db", 3.0)
        seed          = args.get("seed", 0)
        script = dedent(f"""
            import unreal, json
            try:
                factory = unreal.MetaSoundSourceFactory()
                ms = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    "{name}", "{save_path}", unreal.MetaSoundSource, factory
                )
                if not ms:
                    raise RuntimeError("Failed to create MetaSoundSource")
                ms.set_editor_property("is_one_shot", True)
                ms.set_editor_property("num_channels", 2)
                unreal.EditorAssetLibrary.save_asset(ms.get_path_name())
                wave_list = {wave_paths}
                print("UEOS_RESULT:" + json.dumps({{
                    "path": ms.get_path_name(), "name": "{name}",
                    "wave_count": len(wave_list),
                    "wave_paths": wave_list,
                    "pitch_variation_semitones": {pitch_var},
                    "volume_variation_db": {vol_var},
                    "seed": {seed},
                    "status": "randomised_source_created",
                    "note": "Add RandomFloat node (pitch/vol variation) + WaveAsset array in MetaSound editor"
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "snd_create_randomised_source")

    async def _create_attenuation(self, args: dict) -> list[types.TextContent]:
        name         = args["name"]
        save_path    = args["save_path"].rstrip("/")
        inner_radius = args.get("inner_radius", 400.0)
        falloff_r    = args.get("falloff_radius", 3000.0)
        shape_key    = args.get("shape", "sphere")
        spatial      = args.get("spatialization", True)
        reverb_send  = args.get("reverb_send", False)
        air_absorb   = args.get("air_absorption", False)
        shape_enum   = ATTENUATION_SHAPES.get(shape_key, ATTENUATION_SHAPES["sphere"])
        script = dedent(f"""
            import unreal, json
            try:
                factory = unreal.SoundAttenuationFactory()
                att = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    "{name}", "{save_path}", unreal.SoundAttenuation, factory
                )
                if not att:
                    raise RuntimeError("Failed to create SoundAttenuation")
                atten_settings = att.attenuation
                atten_settings.set_editor_property("inner_radius", {inner_radius})
                atten_settings.set_editor_property("falloff_radius", {falloff_r})
                atten_settings.set_editor_property("attenuation_shape", {shape_enum})
                atten_settings.set_editor_property("b_spatialize", {str(spatial)})
                atten_settings.set_editor_property("b_enable_reverb_send", {str(reverb_send)})
                atten_settings.set_editor_property("b_enable_log_frequency_scaling", {str(air_absorb)})
                unreal.EditorAssetLibrary.save_asset(att.get_path_name())
                print("UEOS_RESULT:" + json.dumps({{
                    "path": att.get_path_name(), "name": "{name}",
                    "inner_radius": {inner_radius}, "falloff_radius": {falloff_r},
                    "shape": "{shape_key}", "spatialization": {str(spatial).lower()},
                    "status": "attenuation_created"
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "snd_create_attenuation")

    async def _list_attenuations(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game")
        script = dedent(f"""
            import unreal, json
            try:
                reg = unreal.AssetRegistryHelpers.get_asset_registry()
                assets = reg.get_assets_by_path("{search_path}", recursive=True)
                results = []
                for a in assets:
                    if "SoundAttenuation" in str(a.asset_class_path):
                        results.append({{"name": str(a.asset_name), "path": str(a.object_path)}})
                print("UEOS_RESULT:" + json.dumps({{"attenuations": results, "count": len(results)}}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "snd_list_attenuations")

    async def _create_modulator_lfo(self, args: dict) -> list[types.TextContent]:
        name      = args["name"]
        save_path = args["save_path"].rstrip("/")
        freq      = args.get("frequency_hz", 1.0)
        amplitude = args.get("amplitude", 0.5)
        waveform  = args.get("waveform", "sine")
        bypass    = args.get("bypass", False)
        wave_map  = {"sine": "0", "square": "1", "triangle": "2", "sawtooth": "3"}
        wave_idx  = wave_map.get(waveform, "0")
        script = dedent(f"""
            import unreal, json
            try:
                factory = unreal.SoundModulationLFOFactory()
                lfo = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    "{name}", "{save_path}", unreal.SoundModulatorLFO, factory
                )
                if not lfo:
                    raise RuntimeError("Failed to create SoundModulatorLFO")
                lfo.set_editor_property("frequency", {freq})
                lfo.set_editor_property("amplitude", {amplitude})
                lfo.set_editor_property("bypass", {str(bypass)})
                unreal.EditorAssetLibrary.save_asset(lfo.get_path_name())
                print("UEOS_RESULT:" + json.dumps({{
                    "path": lfo.get_path_name(), "name": "{name}",
                    "frequency_hz": {freq}, "amplitude": {amplitude},
                    "waveform": "{waveform}", "bypass": {str(bypass).lower()},
                    "status": "modulator_lfo_created"
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "snd_create_modulator_lfo")

    async def _create_control_bus(self, args: dict) -> list[types.TextContent]:
        name       = args["name"]
        save_path  = args["save_path"].rstrip("/")
        param_key  = args.get("parameter_type", "volume")
        default_v  = args.get("default_value", 0.0)
        param_cls  = MODULATOR_TYPES.get(param_key, MODULATOR_TYPES["volume"])
        script = dedent(f"""
            import unreal, json
            try:
                factory = unreal.SoundControlBusFactory()
                bus = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    "{name}", "{save_path}", unreal.SoundControlBus, factory
                )
                if not bus:
                    raise RuntimeError("Failed to create SoundControlBus")
                param_asset = {param_cls}.static_class()
                bus.set_editor_property("parameter", param_asset.get_default_object())
                bus.set_editor_property("default_value", {default_v})
                unreal.EditorAssetLibrary.save_asset(bus.get_path_name())
                print("UEOS_RESULT:" + json.dumps({{
                    "path": bus.get_path_name(), "name": "{name}",
                    "parameter_type": "{param_key}", "default_value": {default_v},
                    "status": "control_bus_created"
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "snd_create_control_bus")

    async def _create_sound_class(self, args: dict) -> list[types.TextContent]:
        name      = args["name"]
        save_path = args["save_path"].rstrip("/")
        volume    = args.get("volume", 1.0)
        pitch     = args.get("pitch", 1.0)
        lpf_freq  = args.get("lowpass_filter_freq", 0.0)
        reverb    = args.get("apply_reverb", False)
        script = dedent(f"""
            import unreal, json
            try:
                factory = unreal.SoundClassFactory()
                sc = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    "{name}", "{save_path}", unreal.SoundClass, factory
                )
                if not sc:
                    raise RuntimeError("Failed to create SoundClass")
                props = sc.properties
                if props:
                    props.set_editor_property("volume", {volume})
                    props.set_editor_property("pitch", {pitch})
                    props.set_editor_property("apply_effects_to_children", False)
                    if {lpf_freq} > 0:
                        props.set_editor_property("lowpass_filter_frequency", {lpf_freq})
                unreal.EditorAssetLibrary.save_asset(sc.get_path_name())
                print("UEOS_RESULT:" + json.dumps({{
                    "path": sc.get_path_name(), "name": "{name}",
                    "volume": {volume}, "pitch": {pitch},
                    "lpf_frequency": {lpf_freq}, "status": "sound_class_created"
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "snd_create_sound_class")

    async def _assign_to_audio_component(self, args: dict) -> list[types.TextContent]:
        bp_path      = args["bp_path"]
        sound_path   = args["sound_path"]
        auto_activate= args.get("auto_activate", True)
        atten_path   = args.get("attenuation_path", "")
        script = dedent(f"""
            import unreal, json
            try:
                bp = unreal.load_asset("{bp_path}")
                sound = unreal.load_asset("{sound_path}")
                if not bp:
                    raise RuntimeError("Blueprint not found: {bp_path}")
                if not sound:
                    raise RuntimeError("Sound asset not found: {sound_path}")
                target_comp = None
                for comp_node in bp.simple_construction_script.get_all_nodes():
                    if isinstance(comp_node.component_template, unreal.AudioComponent):
                        target_comp = comp_node.component_template
                        break
                if not target_comp:
                    # Add a new AudioComponent
                    scs = bp.simple_construction_script
                    new_node = scs.add_node(unreal.AudioComponent)
                    if new_node:
                        target_comp = new_node.component_template
                        scs.add_new_node_at(new_node, scs.get_root_nodes()[0] if scs.get_root_nodes() else None)
                if target_comp:
                    target_comp.set_editor_property("sound", sound)
                    target_comp.set_editor_property("auto_activate", {str(auto_activate)})
                    if "{atten_path}":
                        attenuation = unreal.load_asset("{atten_path}")
                        if attenuation:
                            target_comp.set_editor_property("attenuation_settings", attenuation)
                unreal.EditorAssetLibrary.save_asset("{bp_path}")
                print("UEOS_RESULT:" + json.dumps({{
                    "bp": "{bp_path}",
                    "sound": "{sound_path}",
                    "auto_activate": {str(auto_activate).lower()},
                    "attenuation": "{atten_path}" or "none",
                    "status": "sound_assigned"
                }}))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "snd_assign_to_audio_component")

    async def _diagnostics(self, args: dict) -> list[types.TextContent]:
        search_path = args.get("search_path", "/Game")
        script = dedent(f"""
            import unreal, json
            try:
                reg = unreal.AssetRegistryHelpers.get_asset_registry()
                assets = reg.get_assets_by_path("{search_path}", recursive=True)
                ms_sources  = [a for a in assets if "MetaSoundSource" in str(a.asset_class_path)]
                ms_patches  = [a for a in assets if "MetaSoundPatch"  in str(a.asset_class_path) and "Source" not in str(a.asset_class_path)]
                attenuations= [a for a in assets if "SoundAttenuation" in str(a.asset_class_path)]
                sound_waves = [a for a in assets if "SoundWave" in str(a.asset_class_path)]
                control_buses = [a for a in assets if "SoundControlBus" in str(a.asset_class_path)]
                lfo_mods    = [a for a in assets if "SoundModulatorLFO" in str(a.asset_class_path)]
                sound_classes = [a for a in assets if "SoundClass" in str(a.asset_class_path)]
                report = {{
                    "metasound_source_count":  len(ms_sources),
                    "metasound_patch_count":   len(ms_patches),
                    "attenuation_count":       len(attenuations),
                    "sound_wave_count":        len(sound_waves),
                    "control_bus_count":       len(control_buses),
                    "lfo_modulator_count":     len(lfo_mods),
                    "sound_class_count":       len(sound_classes),
                    "metasound_module_loaded": True,
                    "ueos_version":            "7.0",
                }}
                print("UEOS_RESULT:" + json.dumps(report))
            except Exception as e:
                print("UEOS_ERROR:" + str(e))
        """)
        return await self._exec(script, "snd_diagnostics")
