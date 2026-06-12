"""
metasound_utils.py — UEOS UE-side MetaSound utility library (Phase 7)
Run directly from the UE Python console or import as a module.

Quick install:
    import sys, importlib
    sys.path.insert(0, r"C:/UEOS/ue_scripts")
    import metasound_utils as ms; importlib.reload(ms)

    # Create a full audio setup (sources + attenuation + SFX class):
    ms.ueos_audio_quick_setup("/Game/Audio")

    # Create a randomised footstep source:
    ms.ueos_create_footstep_source(
        wave_paths=["/Game/Audio/Footstep_01", "/Game/Audio/Footstep_02"],
        save_path="/Game/Audio"
    )
"""

from __future__ import annotations
import json


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ok(data: dict) -> dict:
    data.setdefault("status", "ok")
    return data

def _err(msg: str) -> dict:
    return {"status": "error", "message": str(msg)}

def _log(data: dict) -> None:
    print(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ueos_audio_quick_setup(save_path: str = "/Game/Audio") -> dict:
    """
    One-call audio project setup:
      - MS_UIClick, MS_Footstep, MS_Explosion (MetaSound Sources)
      - SA_Character, SA_Explosion (Attenuation assets)
      - SC_SFX, SC_Music, SC_Voice (Sound Classes)
      - LFO_Tremolo (modulator LFO)

    Returns: dict with paths of all created assets.
    """
    import unreal
    try:
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        created = []

        def make_ms_source(name, oneshot=True, channels=2):
            factory = unreal.MetaSoundSourceFactory()
            ms = tools.create_asset(name, save_path, unreal.MetaSoundSource, factory)
            if ms:
                ms.set_editor_property("is_one_shot", oneshot)
                ms.set_editor_property("num_channels", channels)
                unreal.EditorAssetLibrary.save_asset(ms.get_path_name())
                created.append(ms.get_path_name())
            return ms

        def make_attenuation(name, inner, falloff):
            factory = unreal.SoundAttenuationFactory()
            att = tools.create_asset(name, save_path, unreal.SoundAttenuation, factory)
            if att:
                s = att.attenuation
                s.set_editor_property("inner_radius", inner)
                s.set_editor_property("falloff_radius", falloff)
                s.set_editor_property("b_spatialize", True)
                unreal.EditorAssetLibrary.save_asset(att.get_path_name())
                created.append(att.get_path_name())
            return att

        def make_sound_class(name, vol=1.0, pitch=1.0):
            factory = unreal.SoundClassFactory()
            sc = tools.create_asset(name, save_path, unreal.SoundClass, factory)
            if sc:
                props = sc.properties
                if props:
                    props.set_editor_property("volume", vol)
                    props.set_editor_property("pitch", pitch)
                unreal.EditorAssetLibrary.save_asset(sc.get_path_name())
                created.append(sc.get_path_name())
            return sc

        # MetaSound Sources
        make_ms_source("MS_UIClick",    oneshot=True,  channels=1)
        make_ms_source("MS_Footstep",   oneshot=True,  channels=2)
        make_ms_source("MS_Explosion",  oneshot=True,  channels=2)

        # Attenuations
        make_attenuation("SA_Character",  200.0,  2000.0)
        make_attenuation("SA_Explosion",  800.0,  6000.0)

        # Sound Classes
        make_sound_class("SC_SFX",   1.0, 1.0)
        make_sound_class("SC_Music", 0.8, 1.0)
        make_sound_class("SC_Voice", 1.0, 1.0)

        # LFO Modulator (tremolo effect)
        lfo_factory = unreal.SoundModulationLFOFactory()
        lfo = tools.create_asset("LFO_Tremolo", save_path, unreal.SoundModulatorLFO, lfo_factory)
        if lfo:
            lfo.set_editor_property("frequency", 4.0)
            lfo.set_editor_property("amplitude", 0.3)
            unreal.EditorAssetLibrary.save_asset(lfo.get_path_name())
            created.append(lfo.get_path_name())

        result = _ok({"assets_created": created, "count": len(created)})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_create_metasound_source(
    name: str,
    save_path: str,
    is_oneshot: bool = True,
    sample_rate: int = 48000,
    num_channels: int = 2,
) -> dict:
    """Create a MetaSound Source asset."""
    import unreal
    try:
        factory = unreal.MetaSoundSourceFactory()
        ms = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, save_path, unreal.MetaSoundSource, factory
        )
        if not ms:
            return _err(f"Failed to create MetaSoundSource: {name}")
        ms.set_editor_property("is_one_shot", is_oneshot)
        ms.set_editor_property("sample_rate", sample_rate)
        ms.set_editor_property("num_channels", num_channels)
        unreal.EditorAssetLibrary.save_asset(ms.get_path_name())
        result = _ok({
            "path": ms.get_path_name(),
            "name": name,
            "is_oneshot": is_oneshot,
            "sample_rate": sample_rate,
            "num_channels": num_channels,
        })
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_create_footstep_source(
    wave_paths: list,
    save_path: str,
    name: str = "MS_Footstep",
    pitch_var: float = 2.0,
    volume_var: float = 3.0,
) -> dict:
    """
    Create a randomised footstep MetaSound Source.
    The asset is created with metadata noting the wave list and variation.
    Connect waves + RandomFloat nodes in the MetaSound editor.
    """
    import unreal
    try:
        factory = unreal.MetaSoundSourceFactory()
        ms = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, save_path, unreal.MetaSoundSource, factory
        )
        if not ms:
            return _err(f"Failed to create MetaSoundSource: {name}")
        ms.set_editor_property("is_one_shot", True)
        ms.set_editor_property("num_channels", 2)
        unreal.EditorAssetLibrary.save_asset(ms.get_path_name())
        result = _ok({
            "path": ms.get_path_name(),
            "wave_paths": wave_paths,
            "wave_count": len(wave_paths),
            "pitch_variation_semitones": pitch_var,
            "volume_variation_db": volume_var,
            "note": "Connect WaveAsset array + RandomSelect + RandomFloat (pitch/vol) nodes in MetaSound editor",
        })
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_create_music_source(
    name: str,
    save_path: str,
    wave_path: str = "",
    loop: bool = True,
    expose_volume: bool = True,
    expose_pitch: bool = False,
) -> dict:
    """Create a looping music MetaSound Source."""
    import unreal
    try:
        factory = unreal.MetaSoundSourceFactory()
        ms = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, save_path, unreal.MetaSoundSource, factory
        )
        if not ms:
            return _err(f"Failed to create MetaSoundSource: {name}")
        ms.set_editor_property("is_one_shot", not loop)
        ms.set_editor_property("num_channels", 2)
        unreal.EditorAssetLibrary.save_asset(ms.get_path_name())
        result = _ok({
            "path": ms.get_path_name(),
            "name": name,
            "wave_path": wave_path,
            "loop": loop,
            "suggested_inputs": (["Volume_dB: float"] if expose_volume else []) + (["Pitch_semitones: float"] if expose_pitch else []),
        })
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_create_attenuation(
    name: str,
    save_path: str,
    inner_radius: float = 400.0,
    falloff_radius: float = 3000.0,
    spatialise: bool = True,
    reverb_send: bool = False,
) -> dict:
    """Create a Sound Attenuation asset."""
    import unreal
    try:
        factory = unreal.SoundAttenuationFactory()
        att = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, save_path, unreal.SoundAttenuation, factory
        )
        if not att:
            return _err(f"Failed to create SoundAttenuation: {name}")
        s = att.attenuation
        s.set_editor_property("inner_radius", inner_radius)
        s.set_editor_property("falloff_radius", falloff_radius)
        s.set_editor_property("b_spatialize", spatialise)
        s.set_editor_property("b_enable_reverb_send", reverb_send)
        unreal.EditorAssetLibrary.save_asset(att.get_path_name())
        result = _ok({
            "path": att.get_path_name(),
            "name": name,
            "inner_radius": inner_radius,
            "falloff_radius": falloff_radius,
            "spatialization": spatialise,
        })
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_create_sound_class(
    name: str,
    save_path: str,
    volume: float = 1.0,
    pitch: float = 1.0,
) -> dict:
    """Create a Sound Class asset."""
    import unreal
    try:
        factory = unreal.SoundClassFactory()
        sc = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, save_path, unreal.SoundClass, factory
        )
        if not sc:
            return _err(f"Failed to create SoundClass: {name}")
        props = sc.properties
        if props:
            props.set_editor_property("volume", volume)
            props.set_editor_property("pitch", pitch)
        unreal.EditorAssetLibrary.save_asset(sc.get_path_name())
        result = _ok({"path": sc.get_path_name(), "name": name, "volume": volume, "pitch": pitch})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_create_modulator_lfo(
    name: str,
    save_path: str,
    frequency: float = 1.0,
    amplitude: float = 0.5,
) -> dict:
    """Create an Audio Modulation LFO asset."""
    import unreal
    try:
        factory = unreal.SoundModulationLFOFactory()
        lfo = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, save_path, unreal.SoundModulatorLFO, factory
        )
        if not lfo:
            return _err(f"Failed to create SoundModulatorLFO: {name}")
        lfo.set_editor_property("frequency", frequency)
        lfo.set_editor_property("amplitude", amplitude)
        unreal.EditorAssetLibrary.save_asset(lfo.get_path_name())
        result = _ok({"path": lfo.get_path_name(), "name": name, "frequency": frequency, "amplitude": amplitude})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_list_audio_assets(search_path: str = "/Game") -> dict:
    """List MetaSound, SoundWave, Attenuation, and SoundClass assets."""
    import unreal
    try:
        reg = unreal.AssetRegistryHelpers.get_asset_registry()
        assets = reg.get_assets_by_path(search_path, recursive=True)
        ms_sources  = [{"name": str(a.asset_name), "path": str(a.object_path)} for a in assets if "MetaSoundSource" in str(a.asset_class_path)]
        ms_patches  = [{"name": str(a.asset_name), "path": str(a.object_path)} for a in assets if "MetaSoundPatch"  in str(a.asset_class_path) and "Source" not in str(a.asset_class_path)]
        sound_waves = [{"name": str(a.asset_name), "path": str(a.object_path)} for a in assets if "SoundWave" in str(a.asset_class_path)]
        attenuations= [{"name": str(a.asset_name), "path": str(a.object_path)} for a in assets if "SoundAttenuation" in str(a.asset_class_path)]
        sound_classes=[{"name": str(a.asset_name), "path": str(a.object_path)} for a in assets if "SoundClass" in str(a.asset_class_path)]
        result = _ok({
            "metasound_sources": ms_sources,
            "metasound_patches": ms_patches,
            "sound_waves":       sound_waves,
            "attenuations":      attenuations,
            "sound_classes":     sound_classes,
        })
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_duplicate_metasound(source_path: str, new_name: str, dest_folder: str) -> dict:
    """Duplicate a MetaSound asset."""
    import unreal
    try:
        new_path = f"{dest_folder.rstrip('/')}/{new_name}"
        ok = unreal.EditorAssetLibrary.duplicate_asset(source_path, new_path)
        if not ok:
            return _err(f"Duplicate failed: {source_path} → {new_path}")
        unreal.EditorAssetLibrary.save_asset(new_path)
        result = _ok({"source": source_path, "new_path": new_path})
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))


def ueos_audio_diagnostics(search_path: str = "/Game") -> dict:
    """Print full audio/MetaSound diagnostics."""
    import unreal
    try:
        reg = unreal.AssetRegistryHelpers.get_asset_registry()
        all_assets = reg.get_assets_by_path(search_path, recursive=True)
        result = _ok({
            "metasound_source_count": sum(1 for a in all_assets if "MetaSoundSource" in str(a.asset_class_path)),
            "metasound_patch_count":  sum(1 for a in all_assets if "MetaSoundPatch"  in str(a.asset_class_path) and "Source" not in str(a.asset_class_path)),
            "sound_wave_count":       sum(1 for a in all_assets if "SoundWave"        in str(a.asset_class_path)),
            "attenuation_count":      sum(1 for a in all_assets if "SoundAttenuation" in str(a.asset_class_path)),
            "sound_class_count":      sum(1 for a in all_assets if "SoundClass"       in str(a.asset_class_path)),
            "lfo_modulator_count":    sum(1 for a in all_assets if "SoundModulatorLFO" in str(a.asset_class_path)),
            "control_bus_count":      sum(1 for a in all_assets if "SoundControlBus"  in str(a.asset_class_path)),
        })
        _log(result)
        return result
    except Exception as e:
        return _err(str(e))
