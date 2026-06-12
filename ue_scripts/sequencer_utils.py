"""
UEOS Sequencer Utilities — ue_scripts/sequencer_utils.py
UE-side helper functions for Level Sequence / Sequencer operations.

Usage inside Unreal Editor Python (via Remote Control execute_python):
    import sys, importlib
    sys.path.insert(0, r"C:/path/to/ueos/ue_scripts")
    import sequencer_utils; importlib.reload(sequencer_utils)
    sequencer_utils.ueos_build_cutscene("CS_Intro", "/Game/Cinematics", duration_seconds=10.0)

All functions prefix output with UEOS_RESULT: (JSON) or UEOS_ERROR: (message).
"""

import json
import unreal


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _result(data: dict) -> None:
    print("UEOS_RESULT:" + json.dumps(data))


def _error(msg: str) -> None:
    print("UEOS_ERROR:" + msg)


def _get_sequence(asset_path: str):
    """Load an existing LevelSequence asset."""
    seq = unreal.load_asset(asset_path)
    if seq is None:
        raise RuntimeError(f"LevelSequence not found: {asset_path}")
    return seq


def _seconds_to_frame(sequence, seconds: float) -> int:
    """Convert time in seconds to frame number for a given sequence."""
    fps = sequence.get_display_rate()
    return int(seconds * fps.numerator / fps.denominator)


def _find_binding_for_actor(sequence, actor_path: str):
    """Find a binding in the sequence that matches the given actor path."""
    world = unreal.EditorLevelLibrary.get_editor_world()
    actor = unreal.EditorLevelLibrary.get_actor_reference(actor_path)
    if actor is None:
        raise RuntimeError(f"Actor not found: {actor_path}")

    bindings = sequence.get_bindings()
    for binding in bindings:
        for bound_obj in unreal.SequencerTools.get_bound_objects(
            world, sequence, [binding],
            unreal.SequencerScriptingRange(
                has_start_value=True, has_end_value=True,
                inclusive_start=sequence.get_playback_start(),
                exclusive_end=sequence.get_playback_end()
            )
        ):
            for obj in bound_obj.bound_objects:
                if obj == actor:
                    return binding
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Sequence Creation
# ─────────────────────────────────────────────────────────────────────────────

def ueos_create_level_sequence(
    name: str,
    save_path: str,
    duration_seconds: float = 10.0,
    fps: int = 30,
) -> dict:
    """
    Create a new LevelSequence asset.

    Args:
        name:             Asset name (e.g. 'LS_Intro')
        save_path:        Content path (e.g. '/Game/Cinematics')
        duration_seconds: Total sequence duration in seconds
        fps:              Frames per second (default 30)

    Returns:
        dict with 'asset_path' on success.
    """
    try:
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        factory = unreal.LevelSequenceFactoryNew()
        seq = asset_tools.create_asset(name, save_path, unreal.LevelSequence, factory)

        if seq is None:
            raise RuntimeError("Failed to create LevelSequence")

        # Set frame rate
        display_rate = unreal.FrameRate(numerator=fps, denominator=1)
        seq.set_display_rate(display_rate)

        # Set playback range
        total_frames = int(duration_seconds * fps)
        seq.set_playback_start(0)
        seq.set_playback_end(total_frames)

        full_path = f"{save_path}/{name}"
        unreal.EditorAssetLibrary.save_asset(full_path, only_if_is_dirty=False)

        _result({
            "asset_path": full_path,
            "duration_seconds": duration_seconds,
            "fps": fps,
            "total_frames": total_frames,
        })
        return {"asset_path": full_path, "fps": fps, "total_frames": total_frames}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Actor Track Management
# ─────────────────────────────────────────────────────────────────────────────

def ueos_add_actor_to_sequence(asset_path: str, actor_path: str) -> dict:
    """
    Add a world actor as a binding in a LevelSequence.

    Args:
        asset_path:  Full content path to LevelSequence
        actor_path:  Actor path in the level (e.g. 'BP_Hero_C_0')

    Returns:
        dict with 'binding_id' (GUID string).
    """
    try:
        seq = _get_sequence(asset_path)
        world = unreal.EditorLevelLibrary.get_editor_world()

        actor = unreal.EditorLevelLibrary.get_actor_reference(actor_path)
        if actor is None:
            raise RuntimeError(f"Actor not found: {actor_path}")

        binding = seq.add_possessable(actor)
        binding_id = str(binding.get_binding_id())

        unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
        _result({"asset_path": asset_path, "actor_path": actor_path, "binding_id": binding_id})
        return {"binding_id": binding_id}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_add_transform_track(
    asset_path: str,
    actor_path: str,
    keyframes: list,
) -> dict:
    """
    Add a 3D transform track to an actor binding and set keyframes.

    Args:
        asset_path:  Full content path to LevelSequence
        actor_path:  Actor path in the level
        keyframes:   List of dicts: [{
            'time': float (seconds),
            'location': [x, y, z],
            'rotation': [pitch, yaw, roll],
            'scale':    [x, y, z],
        }]

    Returns:
        dict with 'keys_set' count.
    """
    try:
        seq = _get_sequence(asset_path)
        fps = seq.get_display_rate()
        fps_value = fps.numerator / fps.denominator

        actor = unreal.EditorLevelLibrary.get_actor_reference(actor_path)
        if actor is None:
            raise RuntimeError(f"Actor not found: {actor_path}")

        binding = seq.add_possessable(actor)

        # Add 3D transform track
        transform_track = binding.add_track(unreal.MovieScene3DTransformTrack)
        section = transform_track.add_section()

        # Extend section to cover all keyframe times
        max_frame = 0
        for kf in keyframes:
            f = int(kf["time"] * fps_value)
            if f > max_frame:
                max_frame = f

        section.set_start_frame_bounded(0)
        section.set_end_frame_bounded(max_frame + 1)

        # Set keyframes on each channel
        channels = section.get_channels()
        # channels order: TX TY TZ RX RY RZ SX SY SZ

        keys_set = 0
        for kf in keyframes:
            frame = unreal.FrameNumber(int(kf["time"] * fps_value))
            loc = kf.get("location", [0, 0, 0])
            rot = kf.get("rotation", [0, 0, 0])
            scl = kf.get("scale", [1, 1, 1])

            vals = [
                loc[0], loc[1], loc[2],
                rot[0], rot[1], rot[2],
                scl[0], scl[1], scl[2],
            ]
            for i, (ch, val) in enumerate(zip(channels, vals)):
                ch.add_key(frame, val)
                keys_set += 1

        unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
        _result({
            "asset_path": asset_path,
            "actor_path": actor_path,
            "keyframes_count": len(keyframes),
            "keys_set": keys_set,
        })
        return {"keys_set": keys_set}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Camera Cut Track
# ─────────────────────────────────────────────────────────────────────────────

def ueos_add_camera_cut_section(
    asset_path: str,
    camera_actor_path: str,
    start_time: float = 0.0,
    end_time: float = 5.0,
) -> dict:
    """
    Add a camera cut section to a LevelSequence.

    Args:
        asset_path:         Full content path to LevelSequence
        camera_actor_path:  Actor path for the CameraActor/CineCameraActor
        start_time:         Start time in seconds
        end_time:           End time in seconds

    Returns:
        dict with 'section_added'.
    """
    try:
        seq = _get_sequence(asset_path)
        fps = seq.get_display_rate()
        fps_value = fps.numerator / fps.denominator

        camera_actor = unreal.EditorLevelLibrary.get_actor_reference(camera_actor_path)
        if camera_actor is None:
            raise RuntimeError(f"Camera actor not found: {camera_actor_path}")

        # Bind camera
        cam_binding = seq.add_possessable(camera_actor)

        # Add or find camera cut track
        root_tracks = seq.get_tracks()
        cut_track = None
        for t in root_tracks:
            if isinstance(t, unreal.MovieSceneCameraCutTrack):
                cut_track = t
                break
        if cut_track is None:
            cut_track = seq.add_track(unreal.MovieSceneCameraCutTrack)

        # Add section
        start_frame = int(start_time * fps_value)
        end_frame   = int(end_time   * fps_value)
        section = cut_track.add_section()
        section.set_start_frame(start_frame)
        section.set_end_frame(end_frame)
        section.set_camera_binding_id(cam_binding.get_binding_id())

        unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
        _result({
            "asset_path": asset_path,
            "camera": camera_actor_path,
            "start_time": start_time,
            "end_time": end_time,
            "section_added": True,
        })
        return {"section_added": True}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Fade Track
# ─────────────────────────────────────────────────────────────────────────────

def ueos_add_fade_track(
    asset_path: str,
    fade_in_end: float = 1.0,
    fade_out_start: float = 9.0,
    sequence_end: float = 10.0,
    fade_color_hex: str = "#000000",
) -> dict:
    """
    Add a fade track (black screen in/out) to a LevelSequence.

    Args:
        asset_path:      Full content path to LevelSequence
        fade_in_end:     Time (seconds) when fade-in completes (alpha → 0)
        fade_out_start:  Time (seconds) when fade-out begins (alpha → 1)
        sequence_end:    Total sequence duration in seconds
        fade_color_hex:  Fade color as hex (default black '#000000')

    Returns:
        dict with 'fade_track_added'.
    """
    try:
        seq = _get_sequence(asset_path)
        fps = seq.get_display_rate()
        fps_value = fps.numerator / fps.denominator

        # Find or create fade track
        root_tracks = seq.get_tracks()
        fade_track = None
        for t in root_tracks:
            if isinstance(t, unreal.MovieSceneFadeTrack):
                fade_track = t
                break
        if fade_track is None:
            fade_track = seq.add_track(unreal.MovieSceneFadeTrack)

        section = fade_track.add_section()
        section.set_start_frame(0)
        section.set_end_frame(int(sequence_end * fps_value))

        # Parse fade color
        h = fade_color_hex.lstrip("#")
        if len(h) >= 6:
            r = int(h[0:2], 16) / 255.0
            g = int(h[2:4], 16) / 255.0
            b = int(h[4:6], 16) / 255.0
        else:
            r, g, b = 0.0, 0.0, 0.0
        section.set_editor_property("fade_color", unreal.LinearColor(r=r, g=g, b=b, a=1.0))

        # Get fade channel and set keyframes: 1.0 at 0s → 0.0 at fade_in_end → 0.0 at fade_out_start → 1.0 at end
        channels = section.get_channels()
        if channels:
            ch = channels[0]
            ch.add_key(unreal.FrameNumber(0),                             1.0)
            ch.add_key(unreal.FrameNumber(int(fade_in_end * fps_value)),   0.0)
            ch.add_key(unreal.FrameNumber(int(fade_out_start * fps_value)), 0.0)
            ch.add_key(unreal.FrameNumber(int(sequence_end * fps_value)),  1.0)

        unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
        _result({
            "asset_path": asset_path,
            "fade_in_end": fade_in_end,
            "fade_out_start": fade_out_start,
            "sequence_end": sequence_end,
            "fade_track_added": True,
        })
        return {"fade_track_added": True}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Audio Track
# ─────────────────────────────────────────────────────────────────────────────

def ueos_add_audio_section(
    asset_path: str,
    sound_asset_path: str,
    start_time: float = 0.0,
    volume: float = 1.0,
    pitch: float = 1.0,
) -> dict:
    """
    Add an audio section to a LevelSequence.

    Args:
        asset_path:        Full content path to LevelSequence
        sound_asset_path:  Content path to SoundBase/SoundWave asset
        start_time:        Time (seconds) to place the audio section
        volume:            Volume multiplier (default 1.0)
        pitch:             Pitch multiplier (default 1.0)

    Returns:
        dict with 'audio_section_added'.
    """
    try:
        seq = _get_sequence(asset_path)
        fps = seq.get_display_rate()
        fps_value = fps.numerator / fps.denominator

        sound = unreal.load_asset(sound_asset_path)
        if sound is None:
            raise RuntimeError(f"Sound asset not found: {sound_asset_path}")

        # Find or add audio track
        root_tracks = seq.get_tracks()
        audio_track = None
        for t in root_tracks:
            if isinstance(t, unreal.MovieSceneAudioTrack):
                audio_track = t
                break
        if audio_track is None:
            audio_track = seq.add_track(unreal.MovieSceneAudioTrack)

        start_frame = int(start_time * fps_value)
        section = audio_track.add_section()
        section.set_start_frame(start_frame)
        section.set_editor_property("sound", sound)
        section.set_editor_property("sound_volume_multiplier", volume)
        section.set_editor_property("sound_pitch_multiplier", pitch)

        unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
        _result({
            "asset_path": asset_path,
            "sound": sound_asset_path,
            "start_time": start_time,
            "volume": volume,
            "audio_section_added": True,
        })
        return {"audio_section_added": True}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Sub-Sequences
# ─────────────────────────────────────────────────────────────────────────────

def ueos_add_sub_sequence(
    parent_path: str,
    child_path: str,
    start_time: float = 0.0,
) -> dict:
    """
    Add a child LevelSequence as a sub-sequence track in a parent LevelSequence.

    Args:
        parent_path:  Content path to parent LevelSequence
        child_path:   Content path to child LevelSequence
        start_time:   Time offset (seconds) to place child in parent

    Returns:
        dict with 'sub_sequence_added'.
    """
    try:
        parent = _get_sequence(parent_path)
        child  = _get_sequence(child_path)

        fps = parent.get_display_rate()
        fps_value = fps.numerator / fps.denominator

        sub_track = parent.add_track(unreal.MovieSceneSubTrack)
        start_frame = int(start_time * fps_value)

        # Get child duration
        child_end   = child.get_playback_end()
        end_frame   = start_frame + child_end

        section = sub_track.add_sequence(child, start_frame, end_frame)

        unreal.EditorAssetLibrary.save_asset(parent_path, only_if_is_dirty=False)
        _result({
            "parent_path":      parent_path,
            "child_path":       child_path,
            "start_time":       start_time,
            "sub_sequence_added": True,
        })
        return {"sub_sequence_added": True}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Full Cutscene Builder
# ─────────────────────────────────────────────────────────────────────────────

def ueos_build_cutscene(
    name: str,
    save_path: str,
    duration_seconds: float = 10.0,
    fps: int = 30,
    camera_actor_path: str = "",
    actor_paths: list = None,
    audio_path: str = "",
    fade_in: float = 1.0,
    fade_out: float = 1.0,
) -> dict:
    """
    Build a complete cutscene LevelSequence in one call:
      1. Create LevelSequence with given duration/fps
      2. Add camera cut track (if camera_actor_path provided)
      3. Add transform bindings for all actor_paths
      4. Add audio section (if audio_path provided)
      5. Add fade in/out track

    Args:
        name:              Sequence asset name (e.g. 'LS_Intro')
        save_path:         Content path (e.g. '/Game/Cinematics')
        duration_seconds:  Total duration in seconds
        fps:               Frames per second
        camera_actor_path: Level actor path for main camera (optional)
        actor_paths:       List of actor paths to bind (optional)
        audio_path:        Sound asset path (optional)
        fade_in:           Fade-in duration in seconds (0 = no fade in)
        fade_out:          Fade-out duration in seconds (0 = no fade out)

    Returns:
        dict with 'asset_path' and summary of added elements.
    """
    try:
        if actor_paths is None:
            actor_paths = []

        added = []

        # 1 — Create sequence
        result = ueos_create_level_sequence(name, save_path, duration_seconds, fps)
        if not result:
            return {}
        asset_path = result["asset_path"]
        added.append("LevelSequence created")

        # 2 — Camera cut
        if camera_actor_path:
            ueos_add_camera_cut_section(asset_path, camera_actor_path, 0.0, duration_seconds)
            added.append(f"Camera cut track → {camera_actor_path}")

        # 3 — Actor bindings (empty transform tracks)
        for ap in actor_paths:
            ueos_add_actor_to_sequence(asset_path, ap)
            added.append(f"Actor binding → {ap}")

        # 4 — Audio
        if audio_path:
            ueos_add_audio_section(asset_path, audio_path, 0.0)
            added.append(f"Audio → {audio_path}")

        # 5 — Fade
        if fade_in > 0 or fade_out > 0:
            fi_end = fade_in if fade_in > 0 else 0.0
            fo_start = duration_seconds - fade_out if fade_out > 0 else duration_seconds
            ueos_add_fade_track(asset_path, fi_end, fo_start, duration_seconds)
            added.append(f"Fade: in={fade_in}s out={fade_out}s")

        _result({
            "asset_path": asset_path,
            "duration_seconds": duration_seconds,
            "fps": fps,
            "added": added,
        })
        return {"asset_path": asset_path, "added": added}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Camera Rig Helpers
# ─────────────────────────────────────────────────────────────────────────────

def ueos_spawn_cine_camera(
    name: str = "CineCamera",
    location: list = None,
    rotation: list = None,
    focal_length: float = 35.0,
    aperture: float = 2.8,
) -> dict:
    """
    Spawn a CineCameraActor in the current level.

    Args:
        name:          Actor label
        location:      [x, y, z] in cm
        rotation:      [pitch, yaw, roll] in degrees
        focal_length:  Focal length in mm (default 35)
        aperture:      Aperture f-stop (default 2.8)

    Returns:
        dict with actor path.
    """
    try:
        if location is None:
            location = [0, 0, 200]
        if rotation is None:
            rotation = [0, 0, 0]

        loc = unreal.Vector(location[0], location[1], location[2])
        rot = unreal.Rotator(rotation[0], rotation[1], rotation[2])

        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.CineCameraActor, loc, rot
        )
        if actor is None:
            raise RuntimeError("Failed to spawn CineCameraActor")

        actor.set_actor_label(name)

        cam_comp = actor.get_cine_camera_component()
        if cam_comp:
            cam_comp.set_editor_property("current_focal_length", focal_length)
            cam_comp.set_editor_property("current_aperture", aperture)

        actor_path = str(actor.get_path_name())
        _result({
            "actor_path": actor_path,
            "name": name,
            "location": location,
            "rotation": rotation,
            "focal_length": focal_length,
            "aperture": aperture,
        })
        return {"actor_path": actor_path}
    except Exception as e:
        _error(str(e))
        return {}


def ueos_add_dolly_path(
    asset_path: str,
    camera_actor_path: str,
    waypoints: list,
) -> dict:
    """
    Animate a camera along a dolly path in a LevelSequence.

    Args:
        asset_path:         LevelSequence content path
        camera_actor_path:  Camera actor path in level
        waypoints:          List of {time, location, rotation} dicts

    Returns:
        dict with keys set count.
    """
    return ueos_add_transform_track(asset_path, camera_actor_path, waypoints)


# ─────────────────────────────────────────────────────────────────────────────
# Playback Control
# ─────────────────────────────────────────────────────────────────────────────

def ueos_play_sequence_in_editor(asset_path: str) -> dict:
    """
    Open and play a LevelSequence in the editor viewport.

    Args:
        asset_path:  Full content path to LevelSequence

    Returns:
        dict with 'playing' status.
    """
    try:
        seq = _get_sequence(asset_path)

        # Focus content browser on the asset
        unreal.EditorAssetLibrary.sync_browser_to_objects([asset_path])

        # Open sequence in Sequencer editor
        unreal.AssetEditorSubsystem().open_editor_for_assets([seq])

        _result({"asset_path": asset_path, "playing": True, "note": "Sequence opened in editor"})
        return {"playing": True}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Sequence Inspection
# ─────────────────────────────────────────────────────────────────────────────

def ueos_get_sequence_info(asset_path: str) -> dict:
    """
    Return detailed info about a LevelSequence:
      - Duration, fps, frame range
      - All tracks (type, name)
      - All bindings (actor name, track types)
    """
    try:
        seq = _get_sequence(asset_path)
        fps = seq.get_display_rate()
        fps_value = fps.numerator / fps.denominator

        start  = seq.get_playback_start()
        end    = seq.get_playback_end()
        dur_s  = (end - start) / fps_value

        tracks = []
        for t in seq.get_tracks():
            tracks.append({"type": t.get_class().get_name(), "name": t.get_display_name()})

        bindings = []
        for b in seq.get_bindings():
            b_tracks = [{"type": t.get_class().get_name()} for t in b.get_tracks()]
            bindings.append({
                "name":   b.get_name(),
                "tracks": b_tracks,
            })

        info = {
            "asset_path":       asset_path,
            "fps":              fps_value,
            "start_frame":      start,
            "end_frame":        end,
            "duration_seconds": dur_s,
            "track_count":      len(tracks),
            "tracks":           tracks,
            "binding_count":    len(bindings),
            "bindings":         bindings,
        }
        _result(info)
        return info
    except Exception as e:
        _error(str(e))
        return {}


def ueos_list_sequences(search_path: str = "/Game") -> dict:
    """
    Find all LevelSequence assets under a content path.

    Returns:
        dict with 'sequences' list of content paths.
    """
    try:
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        filter_ = unreal.ARFilter(
            class_names=["LevelSequence"],
            package_paths=[search_path],
            recursive_paths=True,
        )
        assets = registry.get_assets(filter_)
        paths = [str(a.package_name) for a in assets]
        _result({"search_path": search_path, "count": len(paths), "sequences": paths})
        return {"sequences": paths}
    except Exception as e:
        _error(str(e))
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Diagnostics
# ─────────────────────────────────────────────────────────────────────────────

def ueos_sequencer_diagnostics(asset_path: str = "") -> dict:
    """
    Run sequencer diagnostics.
    If asset_path provided: inspect that LevelSequence.
    Otherwise: return general environment info.
    """
    try:
        info = {
            "sequencer_utils_version": "4.0.0",
            "unreal_version": str(unreal.SystemLibrary.get_engine_version()),
        }

        if asset_path:
            seq_info = ueos_get_sequence_info(asset_path)
            info.update(seq_info)

        _result(info)
        return info
    except Exception as e:
        _error(str(e))
        return {}
