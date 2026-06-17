#!/usr/bin/env python3
"""
inject_ue_settings.py
Finds all Unreal Engine projects on this machine and patches their
DefaultEngine.ini to allow UEOS Remote Control Python execution.

Required settings (two separate sections in DefaultEngine.ini):

  [/Script/RemoteControl.RemoteControlSettings]
  bRestrictServerAccess=False
  bEnablePythonExecution=True

  [/Script/PythonScriptPlugin.PythonScriptPluginSettings]
  bRemoteExecution=True

Without these, the Remote Control API blocks Python CDO access and
UEOS cannot send commands to the UE editor.

Exit codes:
  0 — patched one or more projects
  1 — no projects found / all failed
  2 — already configured (no change needed)
"""

import sys
import os
import re
from pathlib import Path


# ── Settings to inject ───────────────────────────────────────────────────────

REQUIRED_SETTINGS = {
    "/Script/RemoteControl.RemoteControlSettings": {
        "bRestrictServerAccess":  "False",
        "bEnablePythonExecution": "True",
    },
    "/Script/PythonScriptPlugin.PythonScriptPluginSettings": {
        "bRemoteExecution": "True",
    },
}


# ── Find UE projects ──────────────────────────────────────────────────────────

def _glob_limited(root: Path, max_depth: int, seen: set, found: list):
    """
    Walk root looking for .uproject files up to max_depth levels deep.
    Never uses ** glob (which scans entire drives). Uses os.scandir instead.
    """
    try:
        with os.scandir(root) as it:
            for entry in it:
                try:
                    if entry.is_file() and entry.name.endswith(".uproject"):
                        ini_path = Path(entry.path).parent / "Config" / "DefaultEngine.ini"
                        key = str(ini_path).lower()
                        if key not in seen:
                            seen.add(key)
                            found.append(ini_path)
                    elif entry.is_dir() and max_depth > 0:
                        # Skip hidden dirs, system dirs, and known time-wasters
                        skip = {"$recycle.bin", "windows", "program files",
                                "program files (x86)", "programdata", "system volume information",
                                "node_modules", ".git", "__pycache__", "appdata"}
                        if entry.name.lower() not in skip and not entry.name.startswith("."):
                            _glob_limited(Path(entry.path), max_depth - 1, seen, found)
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError):
        pass


def find_ue_projects() -> list[Path]:
    """
    Search common locations for Unreal Engine projects.
    Returns list of DefaultEngine.ini paths found.
    Never scans entire drives — only known project locations, max 4 levels deep.
    """
    home = Path.home()
    docs = home / "Documents"

    # Specific high-probability folders — checked first, shallow scan
    priority_roots = [
        docs / "Unreal Projects",
        home / "OneDrive" / "Documents" / "Unreal Projects",
        home / "Desktop",
        docs,
        home / "OneDrive" / "Documents",
    ]

    # Drive-level folders that commonly hold UE projects — 3 levels max
    drive_subfolders = ["Unreal Projects", "UE5", "UE4", "Games", "Projects", "Dev"]
    for drive in ["C:\\", "D:\\", "E:\\"]:
        dp = Path(drive)
        if dp.exists():
            for sub in drive_subfolders:
                candidate = dp / sub
                if candidate.exists():
                    priority_roots.append(candidate)

    found: list[Path] = []
    seen:  set[str]   = set()

    for root in priority_roots:
        if root.exists():
            _glob_limited(root, max_depth=4, seen=seen, found=found)

    return found


# ── INI parser / patcher ──────────────────────────────────────────────────────

def read_ini(path: Path) -> list[str]:
    """Read ini file lines, return empty list if file doesn't exist."""
    if path.exists():
        try:
            return path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return []
    return []


def patch_ini(lines: list[str], required: dict) -> tuple[list[str], bool]:
    """
    Patch ini lines to include all required settings.
    Returns (new_lines, was_changed).
    """
    changed = False

    # Parse existing sections
    # Build map: section_name -> list of (line_index, key, value)
    section_map: dict[str, list] = {}
    current_section = None
    section_start: dict[str, int] = {}

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1]
            section_map.setdefault(current_section, [])
            section_start[current_section] = i
        elif current_section and "=" in stripped and not stripped.startswith(";"):
            key, _, val = stripped.partition("=")
            section_map[current_section].append((i, key.strip(), val.strip()))

    result = list(lines)

    for section, settings in required.items():
        if section not in section_map:
            # Section doesn't exist — append it
            result.append("")
            result.append(f"[{section}]")
            for key, val in settings.items():
                result.append(f"{key}={val}")
            changed = True
        else:
            # Section exists — check each key
            existing_keys = {k: (idx, v) for idx, k, v in section_map[section]}

            for key, val in settings.items():
                if key not in existing_keys:
                    # Key missing — insert after section header
                    insert_at = section_start[section] + 1
                    result.insert(insert_at, f"{key}={val}")
                    # Update all subsequent indices
                    for s in section_map:
                        section_map[s] = [
                            (idx + 1 if idx >= insert_at else idx, k, v)
                            for idx, k, v in section_map[s]
                        ]
                    section_start = {
                        s: (si + 1 if si >= insert_at else si)
                        for s, si in section_start.items()
                    }
                    changed = True
                else:
                    line_idx, existing_val = existing_keys[key]
                    if existing_val != val:
                        # Key exists but wrong value — update it
                        result[line_idx] = f"{key}={val}"
                        changed = True

    return result, changed


def patch_project(ini_path: Path) -> tuple[bool, str]:
    """
    Patch a single project's DefaultEngine.ini.
    Returns (success, message).
    """
    try:
        lines = read_ini(ini_path)
        new_lines, changed = patch_ini(lines, REQUIRED_SETTINGS)

        if not changed:
            return True, f"already configured"

        # Ensure Config directory exists
        ini_path.parent.mkdir(parents=True, exist_ok=True)

        # Write back
        ini_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        return True, f"patched"

    except PermissionError:
        return False, f"permission denied"
    except Exception as e:
        return False, f"error: {e}"


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    print("  Scanning for Unreal Engine projects...")

    projects = find_ue_projects()

    if not projects:
        print("  ! No Unreal Engine projects found.")
        print("  ! You can patch manually — add to your project's Config/DefaultEngine.ini:")
        print()
        print("    [/Script/RemoteControl.RemoteControlSettings]")
        print("    bRestrictServerAccess=False")
        print("    bEnablePythonExecution=True")
        print()
        print("    [/Script/PythonScriptPlugin.PythonScriptPluginSettings]")
        print("    bRemoteExecution=True")
        print()
        return 1

    print(f"  Found {len(projects)} project(s):")

    patched   = 0
    already   = 0
    failed    = 0

    for ini_path in projects:
        project_name = ini_path.parent.parent.name
        ok, msg = patch_project(ini_path)
        if ok:
            if msg == "already configured":
                already += 1
                print(f"  ✓ {project_name} — already configured")
            else:
                patched += 1
                print(f"  ✓ {project_name} — patched successfully")
        else:
            failed += 1
            print(f"  ✗ {project_name} — {msg}")

    print()
    if patched > 0:
        print(f"  ✓ Patched {patched} project(s) — restart UE5 to apply changes")
    if already > 0:
        print(f"  ✓ {already} project(s) already configured")
    if failed > 0:
        print(f"  ! {failed} project(s) could not be patched (check permissions)")

    if patched == 0 and failed == 0:
        return 2  # all already configured
    if patched > 0:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
