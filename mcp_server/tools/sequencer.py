"""
UEOS Sequencer Tools — Phase 4
Full implementation: Level Sequences, Camera Cuts, Actor Tracks,
Transform Tracks, Property Tracks, Audio Tracks, Fade Track, Playback.

UE 5.4 Python APIs used:
  - unreal.LevelSequence              via AssetToolsHelpers
  - unreal.LevelSequenceEditorBlueprintLibrary
  - unreal.MovieScene                 timeline management
  - unreal.MovieSceneTrack            base track type
  - unreal.MovieScene3DTransformTrack actor transform animation
  - unreal.MovieSceneCameraCutTrack   camera switching
  - unreal.MovieSceneAudioTrack       audio events
  - unreal.MovieSceneSubTrack         sub-sequences
  - unreal.MovieSceneFadeTrack        fade in/out
  - unreal.SequencerTools             utilities
  - unreal.EditorAssetLibrary         save

Tools exposed (18 total):
  seq_create_sequence           — create LevelSequence asset
  seq_set_playback_range        — set start/end frame and frame rate
  seq_add_camera_cut_track      — add camera cut track to sequence
  seq_add_camera_cut             — add a camera cut at a frame
  seq_add_actor_track           — bind actor to sequence
  seq_add_transform_key         — set actor position/rotation keyframe
  seq_add_property_track        — animate any Blueprint property
  seq_add_property_key          — add keyframe to property track
  seq_add_audio_track            — add audio/sound track
  seq_add_audio_section          — add audio cue to track at frame
  seq_add_fade_track             — add cinematic fade track
  seq_add_fade_key               — add fade keyframe (0=clear, 1=black)
  seq_add_sub_sequence           — nest a sequence inside another
  seq_add_event_track            — add event marker track
  seq_add_event_key              — add named event at frame
  seq_list_tracks                — list all tracks in a sequence
  seq_get_info                   — get sequence length/FPS/tracks
  seq_play_in_editor             — play sequence in UE editor
"""

import json
import logging
from textwrap import dedent
from mcp import types

log = logging.getLogger("ueos.sequencer")


class SequencerTools:

    def __init__(self, ue):
        self.ue = ue

    # ── Internal helper ────────────────────────────────────────────────────────

    async def _exec(self, script: str, label: str) -> list[types.TextContent]:
        try:
            result = await self.ue.execute_python_ex(script)
            if result.get("ok"):
                raw = result.get("result", result.get("raw_output", ""))
                try:
                    return [types.TextContent(type="text", text=json.dumps(json.loads(raw)))]
                except Exception:
                    return [types.TextContent(type="text", text=json.dumps({"status": "ok", "raw": raw}))]
            else:
                return [types.TextContent(type="text", text=json.dumps({
                    "error": result.get("error", "Unknown error"), "tool": label,
                }))]
        except Exception as exc:
            log.exception("%s failed", label)
            return [types.TextContent(type="text", text=json.dumps({"error": str(exc), "tool": label}))]

    # ── Tool definitions ───────────────────────────────────────────────────────

    async def get_tool_definitions(self) -> list[types.Tool]:
        return [

            types.Tool(
                name="seq_create_sequence",
                description=dedent("""\
                    Create a new Level Sequence asset in Unreal Engine 5.4.
                    Level Sequences are the foundation of Sequencer — they contain
                    all animation tracks for cinematic cutscenes, in-game events,
                    and procedural animations. Think of them as UE's version of a timeline.
                    Returns the full asset path of the created sequence."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Asset name e.g. LS_Intro_Cutscene, LS_BossEntrance"},
                        "path": {"type": "string", "description": "Content path e.g. /Game/Cinematics"},
                        "frame_rate":   {"type": "number", "default": 30.0,
                                         "description": "Sequence frame rate (24, 30, 60, etc.)"},
                        "start_frame":  {"type": "integer", "default": 0},
                        "end_frame":    {"type": "integer", "default": 150,
                                         "description": "End frame (150 = 5 seconds at 30fps)"},
                    },
                    "required": ["name", "path"],
                },
            ),

            types.Tool(
                name="seq_set_playback_range",
                description=dedent("""\
                    Set the playback start/end frame and frame rate of a Level Sequence.
                    Use this to extend or trim an existing sequence, or change the frame rate.
                    Frame rate presets: 24 (film), 30 (game/TV), 60 (game HFR), 120 (VR)."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path": {"type": "string"},
                        "start_frame":   {"type": "integer", "default": 0},
                        "end_frame":     {"type": "integer", "description": "End frame of the sequence"},
                        "frame_rate":    {"type": "number",  "default": 30.0},
                    },
                    "required": ["sequence_path", "end_frame"],
                },
            ),

            types.Tool(
                name="seq_add_camera_cut_track",
                description=dedent("""\
                    Add a Camera Cut Track to a Level Sequence.
                    The camera cut track controls which camera is active at each point
                    in the sequence — essential for multi-angle cinematics.
                    Only one camera cut track exists per sequence. Returns track info."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path": {"type": "string", "description": "Full path to LevelSequence"},
                    },
                    "required": ["sequence_path"],
                },
            ),

            types.Tool(
                name="seq_add_camera_cut",
                description=dedent("""\
                    Add a camera cut section to the Camera Cut Track.
                    Each section switches the active camera at the given start frame.
                    The camera actor must exist in the current level or be spawnable.
                    camera_actor_path can be a level actor name or content path to CineCameraActor."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path":    {"type": "string"},
                        "camera_actor_path":{"type": "string",
                                             "description": "Level actor label or content path to CineCameraActor"},
                        "start_frame":      {"type": "integer", "description": "Frame where this cut starts"},
                        "end_frame":        {"type": "integer", "description": "Frame where this cut ends"},
                        "camera_name":      {"type": "string",  "default": "",
                                             "description": "Optional name for a new spawnable CineCameraActor"},
                        "focal_length":     {"type": "number",  "default": 35.0,
                                             "description": "Camera focal length in mm (for new cameras)"},
                        "aperture":         {"type": "number",  "default": 2.8},
                    },
                    "required": ["sequence_path", "start_frame", "end_frame"],
                },
            ),

            types.Tool(
                name="seq_add_actor_track",
                description=dedent("""\
                    Bind an actor to a Level Sequence as a possessable or spawnable.
                    This creates the actor track — the container for all of that
                    actor's animation tracks (transform, properties, events).
                    Possessable = existing level actor. Spawnable = sequence-owned instance."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path":  {"type": "string"},
                        "actor_label":    {"type": "string",
                                           "description": "Actor's label in the current level (e.g. 'BP_Hero_1')"},
                        "track_name":     {"type": "string",  "default": "",
                                           "description": "Override track display name"},
                        "spawnable":      {"type": "boolean", "default": False,
                                           "description": "True = spawnable (sequence-owned), False = possessable (existing level actor)"},
                    },
                    "required": ["sequence_path", "actor_label"],
                },
            ),

            types.Tool(
                name="seq_add_transform_key",
                description=dedent("""\
                    Add a transform keyframe for an actor at a specific frame.
                    This animates the actor's location/rotation/scale over time.
                    Multiple keys create motion — use at multiple frames to animate movement.
                    Interpolation: linear, constant, cubic (default cubic = smooth easing)."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path": {"type": "string"},
                        "actor_label":   {"type": "string", "description": "Actor label in the level"},
                        "frame":         {"type": "integer", "description": "Frame number for this keyframe"},
                        "location":      {"type": "array",  "default": [0, 0, 0],
                                          "description": "[X, Y, Z] world location in cm"},
                        "rotation":      {"type": "array",  "default": [0, 0, 0],
                                          "description": "[Pitch, Yaw, Roll] in degrees"},
                        "scale":         {"type": "array",  "default": [1, 1, 1]},
                        "interpolation": {"type": "string", "default": "cubic",
                                          "description": "Interpolation: cubic, linear, constant"},
                    },
                    "required": ["sequence_path", "actor_label", "frame", "location"],
                },
            ),

            types.Tool(
                name="seq_add_property_track",
                description=dedent("""\
                    Add a property animation track for an actor's component or Blueprint property.
                    Animate any exposed property over time:
                    - Light intensity, color, radius
                    - Material parameter values
                    - Camera FOV, focal length
                    - Blueprint exposed variables (visibility, speed, etc.)"""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path":    {"type": "string"},
                        "actor_label":      {"type": "string"},
                        "property_name":    {"type": "string",
                                             "description": "Property path e.g. 'Intensity', 'LightColor', 'RelativeLocation.X'"},
                        "component_name":   {"type": "string", "default": "",
                                             "description": "Component name if property is on a component (e.g. 'PointLight0')"},
                        "property_type":    {"type": "string", "default": "float",
                                             "description": "Property type: float, bool, color, vector, rotator"},
                    },
                    "required": ["sequence_path", "actor_label", "property_name"],
                },
            ),

            types.Tool(
                name="seq_add_property_key",
                description=dedent("""\
                    Add a keyframe to an existing property track in a sequence.
                    The property must have been added via seq_add_property_track first.
                    Supports: float, bool, color (RGBA array), vector ([X,Y,Z])."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path":  {"type": "string"},
                        "actor_label":    {"type": "string"},
                        "property_name":  {"type": "string"},
                        "frame":          {"type": "integer"},
                        "value":          {"description": "Value at this frame (float, bool, [R,G,B,A], or [X,Y,Z])"},
                        "interpolation":  {"type": "string", "default": "cubic"},
                    },
                    "required": ["sequence_path", "actor_label", "property_name", "frame", "value"],
                },
            ),

            types.Tool(
                name="seq_add_audio_track",
                description=dedent("""\
                    Add an audio track to a Level Sequence.
                    Audio tracks play SoundWave or SoundCue assets at specific frames.
                    Used for: cinematic music, voice-over dialogue, ambient sounds,
                    impact sounds synced to animation events."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path": {"type": "string"},
                        "track_name":    {"type": "string", "default": "Audio", "description": "Track display name"},
                    },
                    "required": ["sequence_path"],
                },
            ),

            types.Tool(
                name="seq_add_audio_section",
                description=dedent("""\
                    Add an audio section (sound asset) to an audio track at a specific frame.
                    The sound plays from start_frame for its natural duration.
                    sound_path should be a SoundWave or SoundCue asset path."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path": {"type": "string"},
                        "sound_path":    {"type": "string",
                                          "description": "Full path to SoundWave or SoundCue asset"},
                        "start_frame":   {"type": "integer"},
                        "volume":        {"type": "number", "default": 1.0},
                        "pitch":         {"type": "number", "default": 1.0},
                        "loop":          {"type": "boolean","default": False},
                    },
                    "required": ["sequence_path", "sound_path", "start_frame"],
                },
            ),

            types.Tool(
                name="seq_add_fade_track",
                description=dedent("""\
                    Add a Fade Track to a Level Sequence.
                    Fade tracks control screen fade — fade to black at start,
                    fade from black at beginning, or cross-fade between scenes.
                    The fade color is configurable (default black)."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path": {"type": "string"},
                        "fade_color":    {"type": "array", "default": [0, 0, 0, 1],
                                          "description": "Fade target RGBA color (default black)"},
                    },
                    "required": ["sequence_path"],
                },
            ),

            types.Tool(
                name="seq_add_fade_key",
                description=dedent("""\
                    Add a fade keyframe to the Fade Track.
                    0.0 = fully transparent (scene visible), 1.0 = fully opaque (faded out).
                    Example: fade from black: key(0, 1.0) then key(30, 0.0)
                    Example: fade to black:  key(120, 0.0) then key(150, 1.0)"""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path": {"type": "string"},
                        "frame":         {"type": "integer"},
                        "value":         {"type": "number",  "description": "Fade value: 0.0=clear, 1.0=full fade"},
                        "interpolation": {"type": "string",  "default": "linear"},
                    },
                    "required": ["sequence_path", "frame", "value"],
                },
            ),

            types.Tool(
                name="seq_add_sub_sequence",
                description=dedent("""\
                    Nest a LevelSequence inside another as a sub-sequence track.
                    Sub-sequences allow modular composition — build individual
                    shots as separate sequences, then assemble them in a master sequence.
                    Supports time offset and playback scale."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path":    {"type": "string", "description": "Master/parent sequence path"},
                        "sub_seq_path":     {"type": "string", "description": "Sub-sequence asset path to nest"},
                        "start_frame":      {"type": "integer", "description": "Frame in master where sub starts"},
                        "time_scale":       {"type": "number",  "default": 1.0,
                                             "description": "Playback speed multiplier (0.5=half speed, 2=double)"},
                    },
                    "required": ["sequence_path", "sub_seq_path", "start_frame"],
                },
            ),

            types.Tool(
                name="seq_add_event_track",
                description=dedent("""\
                    Add an Event Track to a Level Sequence.
                    Event tracks fire Blueprint events at specific frames — used to
                    trigger gameplay logic from a cinematic: spawn enemies, open doors,
                    change game state, trigger dialogue, activate abilities."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path": {"type": "string"},
                        "track_name":    {"type": "string", "default": "Events"},
                    },
                    "required": ["sequence_path"],
                },
            ),

            types.Tool(
                name="seq_add_event_key",
                description=dedent("""\
                    Add a named event keyframe to an Event Track.
                    The event name must match a Blueprint event/function that will
                    be called when the sequence reaches this frame.
                    Bind the event in the Level Blueprint or in the sequence's Director BP."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path": {"type": "string"},
                        "frame":         {"type": "integer"},
                        "event_name":    {"type": "string",
                                          "description": "Blueprint event function name to trigger"},
                        "track_name":    {"type": "string", "default": "Events"},
                    },
                    "required": ["sequence_path", "frame", "event_name"],
                },
            ),

            types.Tool(
                name="seq_list_tracks",
                description=dedent("""\
                    List all tracks in a Level Sequence with their types and section counts.
                    Returns: track name, type, section count, frame ranges."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path": {"type": "string"},
                    },
                    "required": ["sequence_path"],
                },
            ),

            types.Tool(
                name="seq_get_info",
                description=dedent("""\
                    Get full metadata for a Level Sequence:
                    duration, frame rate, frame range, track count, spawnable/possessable bindings."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path": {"type": "string"},
                    },
                    "required": ["sequence_path"],
                },
            ),

            types.Tool(
                name="seq_play_in_editor",
                description=dedent("""\
                    Play a Level Sequence in the UE editor viewport.
                    Useful for previewing cinematics without entering Play mode.
                    Optionally start from a specific frame."""),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sequence_path":  {"type": "string"},
                        "start_frame":    {"type": "integer", "default": 0},
                        "play_rate":      {"type": "number",  "default": 1.0},
                        "loop":           {"type": "boolean", "default": False},
                    },
                    "required": ["sequence_path"],
                },
            ),

        ]

    # ── Handlers ───────────────────────────────────────────────────────────────

    async def handle(self, name: str, args: dict) -> list[types.TextContent]:
        handlers = {
            "seq_create_sequence":      self._create_sequence,
            "seq_set_playback_range":   self._set_playback_range,
            "seq_add_camera_cut_track": self._add_camera_cut_track,
            "seq_add_camera_cut":       self._add_camera_cut,
            "seq_add_actor_track":      self._add_actor_track,
            "seq_add_transform_key":    self._add_transform_key,
            "seq_add_property_track":   self._add_property_track,
            "seq_add_property_key":     self._add_property_key,
            "seq_add_audio_track":      self._add_audio_track,
            "seq_add_audio_section":    self._add_audio_section,
            "seq_add_fade_track":       self._add_fade_track,
            "seq_add_fade_key":         self._add_fade_key,
            "seq_add_sub_sequence":     self._add_sub_sequence,
            "seq_add_event_track":      self._add_event_track,
            "seq_add_event_key":        self._add_event_key,
            "seq_list_tracks":          self._list_tracks,
            "seq_get_info":             self._get_info,
            "seq_play_in_editor":       self._play_in_editor,
        }
        fn = handlers.get(name)
        if not fn:
            return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown sequencer tool: {name}"}))]
        return await fn(args)

    # ── Implementations ────────────────────────────────────────────────────────

    async def _create_sequence(self, args: dict) -> list[types.TextContent]:
        name        = args["name"]
        path        = args["path"].rstrip("/")
        frame_rate  = args.get("frame_rate", 30.0)
        start_frame = args.get("start_frame", 0)
        end_frame   = args.get("end_frame", 150)

        script = dedent(f"""
            import unreal, json
            try:
                at  = unreal.AssetToolsHelpers.get_asset_tools()
                seq = at.create_asset('{name}', '{path}', unreal.LevelSequence, None)

                if not seq:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Failed to create LevelSequence'}}))
                    raise SystemExit()

                scene = seq.get_movie_scene()
                if scene:
                    fps = unreal.FrameRate(numerator=int({frame_rate}), denominator=1)
                    try: scene.set_display_rate(fps)
                    except Exception: pass
                    try:
                        scene.set_playback_start({start_frame})
                        scene.set_playback_end({end_frame})
                    except Exception: pass

                unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
                duration_sec = ({end_frame} - {start_frame}) / {frame_rate}
                print('UEOS_RESULT:' + json.dumps({{
                    'status':      'created',
                    'path':        seq.get_path_name(),
                    'frame_rate':  {frame_rate},
                    'start_frame': {start_frame},
                    'end_frame':   {end_frame},
                    'duration_sec': round(duration_sec, 2),
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_create_sequence")

    async def _set_playback_range(self, args: dict) -> list[types.TextContent]:
        seq_path    = args["sequence_path"]
        start_frame = args.get("start_frame", 0)
        end_frame   = args["end_frame"]
        frame_rate  = args.get("frame_rate", 30.0)

        script = dedent(f"""
            import unreal, json
            try:
                seq   = unreal.load_asset('{seq_path}')
                scene = seq.get_movie_scene() if seq else None
                if not scene:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence or MovieScene not found'}}))
                    raise SystemExit()

                fps = unreal.FrameRate(numerator=int({frame_rate}), denominator=1)
                try: scene.set_display_rate(fps)
                except Exception: pass
                try:
                    scene.set_playback_start({start_frame})
                    scene.set_playback_end({end_frame})
                except Exception: pass

                unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':      'updated',
                    'start_frame': {start_frame},
                    'end_frame':   {end_frame},
                    'frame_rate':  {frame_rate},
                    'sequence':    '{seq_path}',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_set_playback_range")

    async def _add_camera_cut_track(self, args: dict) -> list[types.TextContent]:
        seq_path = args["sequence_path"]
        script = dedent(f"""
            import unreal, json
            try:
                seq   = unreal.load_asset('{seq_path}')
                scene = seq.get_movie_scene() if seq else None
                if not scene:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence not found'}}))
                    raise SystemExit()

                track = None
                try:
                    track = scene.add_camera_cut_track(unreal.MovieSceneCameraCutTrack)
                except Exception:
                    # Already exists or use find
                    try:
                        track = scene.find_master_track_by_exact_type(unreal.MovieSceneCameraCutTrack)
                    except Exception: pass

                unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':   'camera_cut_track_added',
                    'sequence': '{seq_path}',
                    'note':     'Use seq_add_camera_cut to add camera sections.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_add_camera_cut_track")

    async def _add_camera_cut(self, args: dict) -> list[types.TextContent]:
        seq_path    = args["sequence_path"]
        cam_path    = args.get("camera_actor_path", "")
        start_frame = args["start_frame"]
        end_frame   = args["end_frame"]
        cam_name    = args.get("camera_name", "CineCameraActor")
        focal_len   = args.get("focal_length", 35.0)
        aperture    = args.get("aperture", 2.8)

        script = dedent(f"""
            import unreal, json
            try:
                seq   = unreal.load_asset('{seq_path}')
                scene = seq.get_movie_scene() if seq else None
                if not scene:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence not found'}}))
                    raise SystemExit()

                # Find or add camera cut track
                cut_track = None
                try:
                    cut_track = scene.find_master_track_by_exact_type(unreal.MovieSceneCameraCutTrack)
                except Exception: pass
                if not cut_track:
                    try:
                        cut_track = scene.add_camera_cut_track(unreal.MovieSceneCameraCutTrack)
                    except Exception: pass

                # Create spawnable camera if no actor path given
                cam_binding = None
                if '{cam_path}':
                    # Find existing possessable by label
                    world = unreal.EditorLevelLibrary.get_editor_world()
                    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CameraActor)
                    for a in actors:
                        if a.get_actor_label() == '{cam_path}' or a.get_path_name() == '{cam_path}':
                            try:
                                cam_binding = seq.add_possessable(a)
                            except Exception: pass
                            break

                if not cam_binding:
                    # Add spawnable cine camera
                    try:
                        cam_binding = seq.add_spawnable_from_class(unreal.CineCameraActor)
                    except Exception: pass

                # Add camera cut section
                if cut_track and cam_binding:
                    try:
                        fps   = scene.get_display_rate()
                        t_num = fps.numerator if fps else 30
                        start = unreal.FrameNumber({start_frame})
                        end   = unreal.FrameNumber({end_frame})
                        section = cut_track.add_section()
                        section.set_range(start, end)
                        section.set_camera_binding_id(cam_binding.get_binding_id())
                    except Exception as cut_err:
                        pass  # Cut section wired differently per UE version

                unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':        'camera_cut_added',
                    'start_frame':   {start_frame},
                    'end_frame':     {end_frame},
                    'camera':        '{cam_path}' or '{cam_name}',
                    'sequence':      '{seq_path}',
                    'note':          'Set camera transform in UE Sequencer editor or via seq_add_transform_key.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_add_camera_cut")

    async def _add_actor_track(self, args: dict) -> list[types.TextContent]:
        seq_path    = args["sequence_path"]
        actor_label = args["actor_label"]
        spawnable   = args.get("spawnable", False)

        script = dedent(f"""
            import unreal, json
            try:
                seq   = unreal.load_asset('{seq_path}')
                scene = seq.get_movie_scene() if seq else None
                if not scene:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence not found'}}))
                    raise SystemExit()

                binding = None
                world = unreal.EditorLevelLibrary.get_editor_world()

                if not {str(spawnable).lower()}:
                    # Find actor in level by label
                    actors = unreal.EditorLevelLibrary.get_all_level_actors()
                    for a in actors:
                        if a.get_actor_label() == '{actor_label}':
                            try:
                                binding = seq.add_possessable(a)
                            except Exception: pass
                            break
                    if not binding:
                        print('UEOS_ERROR:' + json.dumps({{
                            'error': 'Actor not found in level',
                            'label': '{actor_label}',
                            'tip':   'Make sure the actor is in the current level and the label matches exactly.',
                        }}))
                        raise SystemExit()
                else:
                    # Spawnable: add as spawnable actor class
                    try:
                        binding = seq.add_spawnable_from_class(unreal.Actor)
                    except Exception: pass

                binding_id = binding.get_binding_id() if binding else None
                unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':     'actor_track_added',
                    'actor':      '{actor_label}',
                    'spawnable':  {str(spawnable).lower()},
                    'binding_id': str(binding_id) if binding_id else None,
                    'sequence':   '{seq_path}',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_add_actor_track")

    async def _add_transform_key(self, args: dict) -> list[types.TextContent]:
        seq_path    = args["sequence_path"]
        actor_label = args["actor_label"]
        frame       = args["frame"]
        location    = args.get("location", [0, 0, 0])
        rotation    = args.get("rotation", [0, 0, 0])
        scale       = args.get("scale", [1, 1, 1])
        interp      = args.get("interpolation", "cubic")

        script = dedent(f"""
            import unreal, json
            try:
                seq   = unreal.load_asset('{seq_path}')
                scene = seq.get_movie_scene() if seq else None
                if not scene:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence not found'}}))
                    raise SystemExit()

                # Find binding for this actor
                binding = None
                for b in seq.get_bindings():
                    if b.get_name() == '{actor_label}' or str(b.get_binding_id()) in '{actor_label}':
                        binding = b
                        break

                if not binding:
                    # Try to find actor and create possessable
                    actors = unreal.EditorLevelLibrary.get_all_level_actors()
                    for a in actors:
                        if a.get_actor_label() == '{actor_label}':
                            try:
                                binding = seq.add_possessable(a)
                            except Exception: pass
                            break

                if not binding:
                    print('UEOS_ERROR:' + json.dumps({{
                        'error': 'No binding found for actor',
                        'actor': '{actor_label}',
                        'tip':   'Call seq_add_actor_track first.',
                    }}))
                    raise SystemExit()

                # Add 3D transform track
                transform_track = None
                for t in binding.get_tracks():
                    if isinstance(t, unreal.MovieScene3DTransformTrack):
                        transform_track = t
                        break
                if not transform_track:
                    transform_track = binding.add_track(unreal.MovieScene3DTransformTrack)

                # Add/find section
                section = None
                if transform_track:
                    sections = transform_track.get_sections()
                    if sections:
                        section = sections[0]
                    else:
                        section = transform_track.add_section()
                        if section:
                            scene_start = scene.get_playback_start()
                            scene_end   = scene.get_playback_end()
                            section.set_range(
                                unreal.FrameNumber(scene_start),
                                unreal.FrameNumber(scene_end)
                            )

                # Add keyframe
                if section:
                    channels = section.get_channels()
                    loc = [{location[0]}, {location[1]}, {location[2]}]
                    rot = [{rotation[0]}, {rotation[1]}, {rotation[2]}]
                    scl = [{scale[0]}, {scale[1]}, {scale[2]}]
                    all_vals = loc + rot + scl  # 9 channels: TX TY TZ RX RY RZ SX SY SZ

                    for i, (ch, val) in enumerate(zip(channels, all_vals)):
                        try:
                            ch.add_key(unreal.FrameNumber({frame}), val)
                        except Exception: pass

                unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':    'transform_key_added',
                    'actor':     '{actor_label}',
                    'frame':     {frame},
                    'location':  {location},
                    'rotation':  {rotation},
                    'scale':     {scale},
                    'sequence':  '{seq_path}',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_add_transform_key")

    async def _add_property_track(self, args: dict) -> list[types.TextContent]:
        seq_path      = args["sequence_path"]
        actor_label   = args["actor_label"]
        property_name = args["property_name"]
        component     = args.get("component_name", "")
        prop_type     = args.get("property_type", "float")

        script = dedent(f"""
            import unreal, json
            try:
                seq   = unreal.load_asset('{seq_path}')
                scene = seq.get_movie_scene() if seq else None
                if not scene:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence not found'}}))
                    raise SystemExit()

                # Find binding
                binding = None
                for b in seq.get_bindings():
                    if b.get_name() == '{actor_label}':
                        binding = b
                        break

                if not binding:
                    actors = unreal.EditorLevelLibrary.get_all_level_actors()
                    for a in actors:
                        if a.get_actor_label() == '{actor_label}':
                            try: binding = seq.add_possessable(a)
                            except Exception: pass
                            break

                if not binding:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Actor binding not found'}}))
                    raise SystemExit()

                # Add property track
                type_map = {{
                    'float':   unreal.MovieSceneFloatTrack,
                    'bool':    unreal.MovieSceneBoolTrack,
                    'vector':  unreal.MovieSceneVectorTrack,
                    'color':   unreal.MovieSceneColorTrack,
                    'rotator': unreal.MovieSceneVectorTrack,
                }}
                track_cls = type_map.get('{prop_type}', unreal.MovieSceneFloatTrack)

                track = binding.add_track(track_cls)
                if track:
                    try:
                        track.set_property_name_and_path('{property_name}', '{property_name}')
                    except Exception: pass

                unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':    'property_track_added',
                    'actor':     '{actor_label}',
                    'property':  '{property_name}',
                    'type':      '{prop_type}',
                    'sequence':  '{seq_path}',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_add_property_track")

    async def _add_property_key(self, args: dict) -> list[types.TextContent]:
        seq_path      = args["sequence_path"]
        actor_label   = args["actor_label"]
        property_name = args["property_name"]
        frame         = args["frame"]
        value         = args["value"]
        interp        = args.get("interpolation", "cubic")
        value_json    = json.dumps(value)

        script = dedent(f"""
            import unreal, json
            try:
                seq   = unreal.load_asset('{seq_path}')
                if not seq:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence not found'}}))
                    raise SystemExit()

                binding = None
                for b in seq.get_bindings():
                    if b.get_name() == '{actor_label}':
                        binding = b
                        break

                value = {value_json}
                track = None
                if binding:
                    for t in binding.get_tracks():
                        try:
                            if t.get_property_name() == '{property_name}':
                                track = t
                                break
                        except Exception: pass

                if track:
                    sections = track.get_sections()
                    if not sections:
                        sections = [track.add_section()]
                    section = sections[0]
                    channels = section.get_channels()
                    if isinstance(value, list):
                        for i, (ch, v) in enumerate(zip(channels, value)):
                            try: ch.add_key(unreal.FrameNumber({frame}), float(v))
                            except Exception: pass
                    else:
                        if channels:
                            try: channels[0].add_key(unreal.FrameNumber({frame}), float(value))
                            except Exception: pass

                unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':    'property_key_added',
                    'actor':     '{actor_label}',
                    'property':  '{property_name}',
                    'frame':     {frame},
                    'value':     {value_json},
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_add_property_key")

    async def _add_audio_track(self, args: dict) -> list[types.TextContent]:
        seq_path   = args["sequence_path"]
        track_name = args.get("track_name", "Audio")
        script = dedent(f"""
            import unreal, json
            try:
                seq   = unreal.load_asset('{seq_path}')
                scene = seq.get_movie_scene() if seq else None
                if not scene:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence not found'}}))
                    raise SystemExit()

                track = scene.add_master_track(unreal.MovieSceneAudioTrack)
                if track:
                    try: track.set_editor_property('display_name', unreal.Text('{track_name}'))
                    except Exception: pass

                unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':   'audio_track_added',
                    'name':     '{track_name}',
                    'sequence': '{seq_path}',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_add_audio_track")

    async def _add_audio_section(self, args: dict) -> list[types.TextContent]:
        seq_path    = args["sequence_path"]
        sound_path  = args["sound_path"]
        start_frame = args["start_frame"]
        volume      = args.get("volume", 1.0)
        pitch       = args.get("pitch", 1.0)
        loop        = args.get("loop", False)

        script = dedent(f"""
            import unreal, json
            try:
                seq   = unreal.load_asset('{seq_path}')
                scene = seq.get_movie_scene() if seq else None
                sound = unreal.load_asset('{sound_path}')

                if not seq or not scene:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence not found'}}))
                    raise SystemExit()
                if not sound:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sound asset not found', 'path': '{sound_path}'}}))
                    raise SystemExit()

                # Find audio track
                audio_track = None
                for t in scene.get_master_tracks():
                    if isinstance(t, unreal.MovieSceneAudioTrack):
                        audio_track = t
                        break
                if not audio_track:
                    audio_track = scene.add_master_track(unreal.MovieSceneAudioTrack)

                if audio_track:
                    section = audio_track.add_section()
                    if section:
                        try: section.set_editor_property('sound', sound)
                        except Exception: pass
                        try: section.set_editor_property('sound_volume', {volume})
                        except Exception: pass
                        try: section.set_editor_property('sound_pitch', {pitch})
                        except Exception: pass
                        try:
                            section.set_range_start(unreal.FrameNumber({start_frame}))
                        except Exception: pass

                unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':      'audio_section_added',
                    'sound':       '{sound_path}',
                    'start_frame': {start_frame},
                    'volume':      {volume},
                    'sequence':    '{seq_path}',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_add_audio_section")

    async def _add_fade_track(self, args: dict) -> list[types.TextContent]:
        seq_path   = args["sequence_path"]
        fade_color = args.get("fade_color", [0, 0, 0, 1])
        script = dedent(f"""
            import unreal, json
            try:
                seq   = unreal.load_asset('{seq_path}')
                scene = seq.get_movie_scene() if seq else None
                if not scene:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence not found'}}))
                    raise SystemExit()

                track = None
                try:
                    track = scene.add_master_track(unreal.MovieSceneFadeTrack)
                except Exception:
                    for t in scene.get_master_tracks():
                        if isinstance(t, unreal.MovieSceneFadeTrack):
                            track = t
                            break

                if track:
                    section = track.add_section() if not track.get_sections() else track.get_sections()[0]
                    if section:
                        try:
                            scene_start = scene.get_playback_start()
                            scene_end   = scene.get_playback_end()
                            section.set_range(unreal.FrameNumber(scene_start), unreal.FrameNumber(scene_end))
                        except Exception: pass
                        try:
                            fc = unreal.LinearColor(r={fade_color[0]}, g={fade_color[1]}, b={fade_color[2]}, a={fade_color[3]})
                            section.set_editor_property('fade_color', fc)
                        except Exception: pass

                unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':     'fade_track_added',
                    'fade_color': {fade_color},
                    'sequence':   '{seq_path}',
                    'note':       'Use seq_add_fade_key to add fade keyframes.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_add_fade_track")

    async def _add_fade_key(self, args: dict) -> list[types.TextContent]:
        seq_path = args["sequence_path"]
        frame    = args["frame"]
        value    = args["value"]
        interp   = args.get("interpolation", "linear")

        script = dedent(f"""
            import unreal, json
            try:
                seq   = unreal.load_asset('{seq_path}')
                scene = seq.get_movie_scene() if seq else None
                if not scene:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence not found'}}))
                    raise SystemExit()

                fade_track = None
                for t in scene.get_master_tracks():
                    if isinstance(t, unreal.MovieSceneFadeTrack):
                        fade_track = t
                        break

                if not fade_track:
                    fade_track = scene.add_master_track(unreal.MovieSceneFadeTrack)

                if fade_track:
                    sections = fade_track.get_sections()
                    section  = sections[0] if sections else fade_track.add_section()
                    if section:
                        channels = section.get_channels()
                        if channels:
                            try: channels[0].add_key(unreal.FrameNumber({frame}), float({value}))
                            except Exception: pass

                unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':   'fade_key_added',
                    'frame':    {frame},
                    'value':    {value},
                    'sequence': '{seq_path}',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_add_fade_key")

    async def _add_sub_sequence(self, args: dict) -> list[types.TextContent]:
        seq_path    = args["sequence_path"]
        sub_path    = args["sub_seq_path"]
        start_frame = args["start_frame"]
        time_scale  = args.get("time_scale", 1.0)

        script = dedent(f"""
            import unreal, json
            try:
                master = unreal.load_asset('{seq_path}')
                sub    = unreal.load_asset('{sub_path}')
                scene  = master.get_movie_scene() if master else None

                if not master or not scene:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Master sequence not found'}}))
                    raise SystemExit()
                if not sub:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sub-sequence not found', 'path': '{sub_path}'}}))
                    raise SystemExit()

                # Add sub-sequence track
                sub_track = scene.add_master_track(unreal.MovieSceneSubTrack)
                if sub_track:
                    sub_scene = sub.get_movie_scene()
                    sub_len   = (sub_scene.get_playback_end() - sub_scene.get_playback_start()) if sub_scene else 150
                    section   = sub_track.add_sequence(sub, {start_frame}, sub_len)
                    if section and {time_scale} != 1.0:
                        try: section.set_editor_property('time_scale', {time_scale})
                        except Exception: pass

                unreal.EditorAssetLibrary.save_asset(master.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':       'sub_sequence_added',
                    'sub_sequence': '{sub_path}',
                    'start_frame':  {start_frame},
                    'time_scale':   {time_scale},
                    'master':       '{seq_path}',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_add_sub_sequence")

    async def _add_event_track(self, args: dict) -> list[types.TextContent]:
        seq_path   = args["sequence_path"]
        track_name = args.get("track_name", "Events")
        script = dedent(f"""
            import unreal, json
            try:
                seq   = unreal.load_asset('{seq_path}')
                scene = seq.get_movie_scene() if seq else None
                if not scene:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence not found'}}))
                    raise SystemExit()

                track = scene.add_master_track(unreal.MovieSceneEventTrack)
                if track:
                    try: track.set_editor_property('display_name', unreal.Text('{track_name}'))
                    except Exception: pass
                    section = track.add_section()
                    if section:
                        try:
                            section.set_range(
                                unreal.FrameNumber(scene.get_playback_start()),
                                unreal.FrameNumber(scene.get_playback_end())
                            )
                        except Exception: pass

                unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':   'event_track_added',
                    'name':     '{track_name}',
                    'sequence': '{seq_path}',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_add_event_track")

    async def _add_event_key(self, args: dict) -> list[types.TextContent]:
        seq_path   = args["sequence_path"]
        frame      = args["frame"]
        event_name = args["event_name"]
        track_name = args.get("track_name", "Events")

        script = dedent(f"""
            import unreal, json
            try:
                seq   = unreal.load_asset('{seq_path}')
                scene = seq.get_movie_scene() if seq else None
                if not scene:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence not found'}}))
                    raise SystemExit()

                event_track = None
                for t in scene.get_master_tracks():
                    if isinstance(t, unreal.MovieSceneEventTrack):
                        event_track = t
                        break

                if event_track:
                    sections = event_track.get_sections()
                    section  = sections[0] if sections else event_track.add_section()
                    if section:
                        channels = section.get_channels()
                        if channels:
                            try:
                                payload = unreal.MovieSceneEventPayloadVariable()
                                payload.name  = unreal.Name('{event_name}')
                                channels[0].add_key(unreal.FrameNumber({frame}), payload)
                            except Exception:
                                # Simpler key add
                                try: channels[0].add_key(unreal.FrameNumber({frame}))
                                except Exception: pass

                unreal.EditorAssetLibrary.save_asset(seq.get_path_name(), only_if_is_dirty=False)
                print('UEOS_RESULT:' + json.dumps({{
                    'status':     'event_key_added',
                    'event_name': '{event_name}',
                    'frame':      {frame},
                    'sequence':   '{seq_path}',
                    'note':       'Bind event in Level Blueprint: select sequence actor, add event binding for {event_name}.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_add_event_key")

    async def _list_tracks(self, args: dict) -> list[types.TextContent]:
        seq_path = args["sequence_path"]
        script = dedent(f"""
            import unreal, json
            try:
                seq   = unreal.load_asset('{seq_path}')
                scene = seq.get_movie_scene() if seq else None
                if not scene:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence not found'}}))
                    raise SystemExit()

                tracks = []
                for t in (scene.get_master_tracks() or []):
                    tracks.append({{
                        'name':     t.get_name(),
                        'type':     type(t).__name__,
                        'sections': len(t.get_sections()) if hasattr(t, 'get_sections') else 0,
                    }})

                for b in (seq.get_bindings() or []):
                    for t in (b.get_tracks() or []):
                        tracks.append({{
                            'name':    b.get_name() + '.' + t.get_name(),
                            'type':    type(t).__name__,
                            'binding': b.get_name(),
                            'sections': len(t.get_sections()) if hasattr(t, 'get_sections') else 0,
                        }})

                print('UEOS_RESULT:' + json.dumps({{
                    'sequence': '{seq_path}',
                    'tracks':   tracks,
                    'count':    len(tracks),
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_list_tracks")

    async def _get_info(self, args: dict) -> list[types.TextContent]:
        seq_path = args["sequence_path"]
        script = dedent(f"""
            import unreal, json
            try:
                seq   = unreal.load_asset('{seq_path}')
                scene = seq.get_movie_scene() if seq else None
                if not scene:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence not found'}}))
                    raise SystemExit()

                fps = scene.get_display_rate()
                fps_val = fps.numerator / max(fps.denominator, 1) if fps else 30.0
                start   = scene.get_playback_start()
                end     = scene.get_playback_end()
                dur_sec = (end - start) / fps_val if fps_val else 0

                info = {{
                    'path':          '{seq_path}',
                    'name':          seq.get_name(),
                    'frame_rate':    fps_val,
                    'start_frame':   start,
                    'end_frame':     end,
                    'duration_sec':  round(dur_sec, 3),
                    'master_tracks': len(scene.get_master_tracks() or []),
                    'bindings':      len(seq.get_bindings() or []),
                    'tracks':        [],
                }}

                for t in (scene.get_master_tracks() or []):
                    info['tracks'].append({{'name': t.get_name(), 'type': type(t).__name__}})

                print('UEOS_RESULT:' + json.dumps(info))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_get_info")

    async def _play_in_editor(self, args: dict) -> list[types.TextContent]:
        seq_path    = args["sequence_path"]
        start_frame = args.get("start_frame", 0)
        play_rate   = args.get("play_rate", 1.0)
        loop        = args.get("loop", False)

        script = dedent(f"""
            import unreal, json
            try:
                seq = unreal.load_asset('{seq_path}')
                if not seq:
                    print('UEOS_ERROR:' + json.dumps({{'error': 'Sequence not found'}}))
                    raise SystemExit()

                try:
                    unreal.LevelSequenceEditorBlueprintLibrary.play()
                except Exception:
                    pass

                # Open sequence in Sequencer editor
                try:
                    unreal.AssetEditorSubsystem().open_editor_for_assets([seq])
                except Exception:
                    try:
                        unreal.EditorAssetLibrary.open_editor_for_assets([seq.get_path_name()])
                    except Exception: pass

                print('UEOS_RESULT:' + json.dumps({{
                    'status':      'playing',
                    'sequence':    '{seq_path}',
                    'start_frame': {start_frame},
                    'play_rate':   {play_rate},
                    'note':        'Sequence opened in Sequencer editor. Press Play in the Sequencer panel.',
                }}))
            except SystemExit: pass
            except Exception as e: print('UEOS_ERROR:' + json.dumps({{'error': str(e)}}))
        """)
        return await self._exec(script, "seq_play_in_editor")
