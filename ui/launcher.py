#!/usr/bin/env python3
"""
UEOS Launcher — GUI Control Panel
Native Windows/macOS desktop app using tkinter (built into Python, no install needed).

Tabs (first-run):
  Setup Wizard — numbered checklist: Python / UE Plugins / Claude / API Keys / Test
Tabs (normal):
  Dashboard   — health bar + live connection status, Start/Stop server
  API Keys    — Tripo / Huanyuan / MetaTailor key entry with show/hide + live validate
  Settings    — UE host/port, temp dir, log level
  Claude      — auto-detect claude_desktop_config.json, one-click inject MCP config
  Log         — live tail of ueos.log

Run:
  python ui/launcher.py
  python ui/launcher.py --minimized   (start minimized to tray area)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import subprocess
import sys
import os
import json
import shutil
import urllib.request
import urllib.error
import time
import webbrowser
from pathlib import Path
import platform

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

ROOT          = Path(__file__).parent.parent
ENV_FILE      = ROOT / ".env"
EXAMPLE       = ROOT / ".env.example"
SERVER_PY     = ROOT / "mcp_server" / "server.py"
LOG_FILE      = ROOT / "mcp_server" / "ueos.log"
SETUP_MARKER  = ROOT / ".setup_complete"

def setup_is_complete() -> bool:
    return SETUP_MARKER.exists()

def mark_setup_complete():
    SETUP_MARKER.write_text("1", encoding="utf-8")

# Claude Desktop config locations
CLAUDE_CONFIGS = [
    Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json",   # Windows
    Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",  # macOS
    Path.home() / ".config" / "Claude" / "claude_desktop_config.json",               # Linux
]

# ─────────────────────────────────────────────────────────────────────────────
# Color palette — dark theme
# ─────────────────────────────────────────────────────────────────────────────

BG        = "#1a1a2e"   # deep navy background
BG2       = "#16213e"   # slightly darker panels
ACCENT    = "#0f3460"   # accent panels
BLUE      = "#e94560"   # primary highlight (pinkish-red)
BLUE2     = "#533483"   # secondary (purple)
GREEN     = "#00b894"   # success
YELLOW    = "#fdcb6e"   # warning
RED       = "#d63031"   # error
TEXT      = "#dfe6e9"   # main text
TEXT_DIM  = "#636e72"   # dimmed text
WHITE     = "#ffffff"
BTN_BG    = "#0f3460"
BTN_FG    = "#ffffff"
ENTRY_BG  = "#2d3436"
ENTRY_FG  = TEXT

FONT_H1   = ("Segoe UI", 18, "bold")
FONT_H2   = ("Segoe UI", 12, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_MONO = ("Consolas", 9)
FONT_SMALL= ("Segoe UI", 9)

# ─────────────────────────────────────────────────────────────────────────────
# .env helpers
# ─────────────────────────────────────────────────────────────────────────────

def read_env() -> dict:
    values = {}
    if not ENV_FILE.exists():
        return values
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            values[k.strip()] = v.strip()
    return values

def write_env(values: dict):
    template = EXAMPLE.read_text(encoding="utf-8") if EXAMPLE.exists() else ""
    lines    = []
    written  = set()
    for line in template.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            lines.append(line)
        elif "=" in stripped:
            k = stripped.split("=")[0].strip()
            written.add(k)
            lines.append(f"{k}={values.get(k, '')}")
        else:
            lines.append(line)
    for k, v in values.items():
        if k not in written:
            lines.append(f"{k}={v}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

# ─────────────────────────────────────────────────────────────────────────────
# API validators (run in threads)
# ─────────────────────────────────────────────────────────────────────────────

def validate_tripo(key: str) -> tuple[bool, str]:
    if not key or not key.strip():
        return False, "No key entered"
    if not key.startswith("tsk_"):
        return False, "Tripo keys start with tsk_"
    try:
        req = urllib.request.Request(
            "https://api.tripo3d.ai/v2/openapi/user/balance",
            headers={"Authorization": f"Bearer {key}"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
            bal  = data.get("data", {}).get("balance", "?")
            return True, f"Valid  •  Balance: {bal} credits"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Invalid key (401 Unauthorized)"
        return False, f"API error {e.code}"
    except Exception as e:
        return False, f"Cannot reach Tripo: {e}"

def check_ue(host: str, port: str) -> tuple[bool, str]:
    try:
        payload = json.dumps({
            "objectPath": "/Script/PythonScriptPlugin.Default__PythonScriptLibrary",
            "functionName": "ExecutePythonScript",
            "parameters": {"PythonScript": "print('UEOS:OK')"}
        }).encode()
        req = urllib.request.Request(
            f"http://{host}:{port}/remote/object/call",
            data=payload, headers={"Content-Type": "application/json"}, method="PUT"
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            return True, f"Connected  •  {host}:{port}"
    except Exception:
        return False, f"Not reachable  •  Start UE 5.4 first"

# ─────────────────────────────────────────────────────────────────────────────
# Main App
# ─────────────────────────────────────────────────────────────────────────────

class UEOSLauncher(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("UEOS — Unreal Engine Operating System")
        self.geometry("860x640")
        self.minsize(760, 580)
        self.configure(bg=BG)
        self.resizable(True, True)

        # State
        self.env_values       = read_env()
        self.server_proc      = None
        self._log_after       = None
        self._status_after    = None
        self._wizard_tab_index = 0   # set in _build_tabs if wizard exists

        # Style
        self._apply_style()

        # Build UI
        self._build_header()
        self._build_health_bar()
        self._build_tabs()

        # Initial status poll
        self.after(500, self._poll_status)

        # Ensure .env exists
        if not ENV_FILE.exists() and EXAMPLE.exists():
            shutil.copy(EXAMPLE, ENV_FILE)

    # ──────────────────────────────────────────────────────────────────────
    # Styling
    # ──────────────────────────────────────────────────────────────────────

    def _apply_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TNotebook",
            background=BG, borderwidth=0, tabmargins=[0,0,0,0])
        style.configure("TNotebook.Tab",
            background=ACCENT, foreground=TEXT_DIM,
            padding=[18, 8], font=FONT_BODY, borderwidth=0)
        style.map("TNotebook.Tab",
            background=[("selected", BG2), ("active", BLUE2)],
            foreground=[("selected", WHITE), ("active", WHITE)])

        style.configure("TFrame", background=BG2)
        style.configure("Inner.TFrame", background=BG2)

        style.configure("TLabel",
            background=BG2, foreground=TEXT, font=FONT_BODY)
        style.configure("Dim.TLabel",
            background=BG2, foreground=TEXT_DIM, font=FONT_SMALL)
        style.configure("H2.TLabel",
            background=BG2, foreground=WHITE, font=FONT_H2)
        style.configure("Green.TLabel",
            background=BG2, foreground=GREEN, font=FONT_BODY)
        style.configure("Red.TLabel",
            background=BG2, foreground=RED, font=FONT_BODY)
        style.configure("Yellow.TLabel",
            background=BG2, foreground=YELLOW, font=FONT_BODY)

        style.configure("TEntry",
            fieldbackground=ENTRY_BG, foreground=ENTRY_FG,
            insertcolor=WHITE, borderwidth=1, relief="flat",
            padding=6)

        style.configure("Accent.TButton",
            background=BLUE, foreground=WHITE,
            font=("Segoe UI", 10, "bold"),
            borderwidth=0, relief="flat", padding=[14, 8])
        style.map("Accent.TButton",
            background=[("active", "#c0392b"), ("pressed", "#922b21")])

        style.configure("Secondary.TButton",
            background=ACCENT, foreground=TEXT,
            font=FONT_BODY, borderwidth=0, relief="flat", padding=[12, 6])
        style.map("Secondary.TButton",
            background=[("active", BLUE2)])

        style.configure("Green.TButton",
            background=GREEN, foreground=BG,
            font=("Segoe UI", 10, "bold"),
            borderwidth=0, relief="flat", padding=[14, 8])
        style.map("Green.TButton",
            background=[("active", "#00a381")])

        style.configure("TProgressbar",
            troughcolor=ACCENT, background=BLUE, borderwidth=0)

        style.configure("TSeparator", background=ACCENT)

    # ──────────────────────────────────────────────────────────────────────
    # Header
    # ──────────────────────────────────────────────────────────────────────

    def _build_header(self):
        header = tk.Frame(self, bg=BG, height=64)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(header, text="UEOS", font=("Segoe UI", 22, "bold"),
                 bg=BG, fg=BLUE).pack(side="left", padx=(20, 6), pady=14)
        tk.Label(header, text="Unreal Engine Operating System",
                 font=("Segoe UI", 11), bg=BG, fg=TEXT_DIM).pack(side="left", pady=14)

        # Server status pill
        self.header_status_var = tk.StringVar(value="● Server Stopped")
        self.header_status_lbl = tk.Label(header,
            textvariable=self.header_status_var,
            font=("Segoe UI", 10, "bold"),
            bg=BG, fg=RED)
        self.header_status_lbl.pack(side="right", padx=20)

    # ──────────────────────────────────────────────────────────────────────
    # Health Bar  (persistent strip below header)
    # ──────────────────────────────────────────────────────────────────────

    def _build_health_bar(self):
        """Persistent coloured strip showing UE / Claude MCP / Python status."""
        self._hbar = tk.Frame(self, bg=ACCENT, height=32)
        self._hbar.pack(fill="x", side="top")
        self._hbar.pack_propagate(False)

        # Three pill indicators: Python | UE | Claude MCP
        self._hbar_pills = {}
        pill_defs = [
            ("python",  "🐍 Python"),
            ("ue",      "🎮 UE 5.4"),
            ("claude",  "🤖 Claude MCP"),
        ]
        left = tk.Frame(self._hbar, bg=ACCENT)
        left.pack(side="left", padx=(12, 0), fill="y")

        for key, label in pill_defs:
            pill = tk.Frame(left, bg=ACCENT)
            pill.pack(side="left", padx=(0, 4), pady=5)

            dot = tk.Label(pill, text="●", font=("Segoe UI", 9),
                           bg=ACCENT, fg=TEXT_DIM)
            dot.pack(side="left", padx=(4, 2))

            lbl = tk.Label(pill, text=label, font=("Segoe UI", 9),
                           bg=ACCENT, fg=TEXT_DIM)
            lbl.pack(side="left", padx=(0, 6))

            self._hbar_pills[key] = {"dot": dot, "lbl": lbl}

        # Right side: fix button (hidden unless something is wrong)
        self._hbar_fix_btn = ttk.Button(
            self._hbar, text="⚡ Fix Issues",
            style="Secondary.TButton",
            command=self._show_wizard_tab)
        self._hbar_fix_btn.pack(side="right", padx=12, pady=4)
        self._hbar_fix_btn.pack_forget()  # hidden by default

        # Schedule first health check
        self.after(600, self._refresh_health_bar)

    def _set_pill(self, key: str, ok: bool, msg: str = ""):
        pill = self._hbar_pills.get(key)
        if not pill:
            return
        color = GREEN if ok else RED
        pill["dot"].configure(fg=color)
        pill["lbl"].configure(fg=WHITE if ok else RED)
        if msg:
            pill["lbl"].configure(text=msg)

    def _refresh_health_bar(self):
        """Re-check all three health indicators in background threads."""
        def _check_python():
            v = sys.version_info
            ok = v.major >= 3 and v.minor >= 10
            label = f"🐍 Python {v.major}.{v.minor}"
            self.after(0, lambda: self._set_pill("python", ok, label))

        def _check_ue():
            env = read_env()
            host = env.get("UE_REMOTE_CONTROL_HOST", "127.0.0.1")
            port = int(env.get("UE_REMOTE_CONTROL_PORT", 30010))
            ok, _ = check_ue(host, port)
            label = "🎮 UE 5.4 ✓" if ok else "🎮 UE 5.4 ✗"
            self.after(0, lambda: self._set_pill("ue", ok, label))

        def _check_claude():
            try:
                setup_dir = str(ROOT / "setup")
                if setup_dir not in sys.path:
                    sys.path.insert(0, setup_dir)
                from inject_claude_config import find_claude_config
                p = find_claude_config()
                if p and p.exists():
                    data = json.loads(p.read_text(encoding="utf-8"))
                    configured = "ueos" in data.get("mcpServers", {})
                else:
                    configured = False
            except Exception:
                configured = False
            label = "🤖 Claude MCP ✓" if configured else "🤖 Claude MCP ✗"
            self.after(0, lambda: self._set_pill("claude", configured, label))
            # Show fix button if anything is wrong
            self.after(0, self._update_fix_button)

        threading.Thread(target=_check_python, daemon=True).start()
        threading.Thread(target=_check_ue,     daemon=True).start()
        threading.Thread(target=_check_claude, daemon=True).start()

        # Re-check every 60 seconds
        self.after(60000, self._refresh_health_bar)

    def _update_fix_button(self):
        """Show the Fix Issues button if any pill is red."""
        any_red = any(
            p["dot"].cget("fg") == RED
            for p in self._hbar_pills.values()
        )
        if any_red:
            self._hbar_fix_btn.pack(side="right", padx=12, pady=4)
        else:
            self._hbar_fix_btn.pack_forget()

    def _show_wizard_tab(self):
        """Switch to the Setup Wizard tab."""
        try:
            self.notebook.select(self._wizard_tab_index)
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────────
    # Tabs
    # ──────────────────────────────────────────────────────────────────────

    def _build_tabs(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=0, pady=0)

        # Prepend wizard tab on first run (before setup_complete marker exists)
        if not setup_is_complete():
            self._build_wizard_tab()
            self._wizard_tab_index = 0

        self._build_dashboard_tab()
        self._build_apikeys_tab()
        self._build_settings_tab()
        self._build_claude_tab()
        self._build_log_tab()

    # ──────────────────────────────────────────────────────────────────────
    # Tab 0 — Setup Wizard  (first-run only)
    # ──────────────────────────────────────────────────────────────────────

    def _build_wizard_tab(self):
        frame = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(frame, text="  ⚡ Setup  ")

        # Scrollable canvas
        canvas = tk.Canvas(frame, bg=BG2, highlightthickness=0)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        inner  = tk.Frame(canvas, bg=BG2)
        inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Title
        tk.Label(inner, text="Welcome to UEOS!",
                 font=("Segoe UI", 16, "bold"), bg=BG2, fg=WHITE
                 ).pack(anchor="w", padx=24, pady=(20, 2))
        tk.Label(inner,
                 text="Complete these steps once and you're ready to control Unreal Engine with Claude.",
                 font=FONT_SMALL, bg=BG2, fg=TEXT_DIM
                 ).pack(anchor="w", padx=24, pady=(0, 16))

        # Step state storage
        self._wiz_steps = {}   # key → {status_var, status_lbl, row_frame}

        # ── Step definitions ────────────────────────────────────────────
        steps = [
            {
                "key":   "python",
                "num":   "1",
                "title": "Python 3.10+",
                "desc":  "The runtime UEOS needs. Already installed if you're seeing this.",
                "auto":  True,
                "check": self._wiz_check_python,
                "fix":   None,   # nothing to fix — Python is running
            },
            {
                "key":   "deps",
                "num":   "2",
                "title": "Python Dependencies",
                "desc":  "mcp, aiohttp, python-dotenv — installed automatically.",
                "auto":  True,
                "check": self._wiz_check_deps,
                "fix":   self._wiz_fix_deps,
            },
            {
                "key":   "ue_plugins",
                "num":   "3",
                "title": "Unreal Engine Plugins",
                "desc":  'In UE: Edit → Plugins → enable "Remote Control API" + "Python Editor Script Plugin" → restart UE.',
                "auto":  False,
                "check": self._wiz_check_ue,
                "fix":   self._wiz_open_ue_plugin_guide,
            },
            {
                "key":   "claude",
                "num":   "4",
                "title": "Claude Desktop Config",
                "desc":  "Injects the UEOS server entry into claude_desktop_config.json automatically.",
                "auto":  True,
                "check": self._wiz_check_claude,
                "fix":   self._wiz_fix_claude,
            },
            {
                "key":   "test",
                "num":   "5",
                "title": "Test Connection",
                "desc":  'Ask Claude: "run ueos_status" — you should get a live report back.',
                "auto":  False,
                "check": self._wiz_check_ue,   # same UE ping
                "fix":   None,
            },
        ]

        for step in steps:
            self._build_wizard_step(inner, step)

        # ── Done button ─────────────────────────────────────────────────
        done_row = tk.Frame(inner, bg=BG2)
        done_row.pack(fill="x", padx=24, pady=(20, 24))
        ttk.Button(done_row,
                   text="✅  I'm all set — go to Dashboard",
                   style="Green.TButton",
                   command=self._wizard_complete).pack(side="left")
        ttk.Button(done_row,
                   text="🔄  Re-check All Steps",
                   style="Secondary.TButton",
                   command=self._wizard_recheck_all).pack(side="left", padx=(12, 0))

        # Auto-run checks
        self.after(400, self._wizard_recheck_all)

    def _build_wizard_step(self, parent, step: dict):
        """Build one wizard step row."""
        key = step["key"]

        row = tk.Frame(parent, bg=ACCENT, pady=14, padx=18)
        row.pack(fill="x", padx=20, pady=(0, 8))

        # Number badge
        badge = tk.Label(row, text=step["num"],
                         font=("Segoe UI", 13, "bold"),
                         bg=BLUE2, fg=WHITE,
                         width=3, anchor="center")
        badge.grid(row=0, column=0, rowspan=2, padx=(0, 14), sticky="ns")

        # Title + description
        tk.Label(row, text=step["title"],
                 font=FONT_H2, bg=ACCENT, fg=WHITE
                 ).grid(row=0, column=1, sticky="w")
        tk.Label(row, text=step["desc"],
                 font=FONT_SMALL, bg=ACCENT, fg=TEXT_DIM,
                 wraplength=480, justify="left"
                 ).grid(row=1, column=1, sticky="w", pady=(2, 0))

        row.columnconfigure(1, weight=1)

        # Status label
        status_var = tk.StringVar(value="⏳ Checking…")
        status_lbl = tk.Label(row, textvariable=status_var,
                              font=("Segoe UI", 10, "bold"),
                              bg=ACCENT, fg=YELLOW)
        status_lbl.grid(row=0, column=2, rowspan=2, padx=(14, 0), sticky="e")

        # Fix / Action button
        if step["fix"]:
            fix_label = "Install" if step["key"] == "deps" else (
                        "Show me how" if step["key"] == "ue_plugins" else
                        "Auto-fix")
            fix_btn = ttk.Button(row, text=fix_label,
                                 style="Secondary.TButton",
                                 command=step["fix"])
            fix_btn.grid(row=0, column=3, rowspan=2, padx=(10, 0))
        elif not step["auto"] and step["key"] == "test":
            ttk.Button(row, text="Open Claude",
                       style="Secondary.TButton",
                       command=lambda: webbrowser.open("https://claude.ai")
                       ).grid(row=0, column=3, rowspan=2, padx=(10, 0))

        self._wiz_steps[key] = {
            "status_var": status_var,
            "status_lbl": status_lbl,
            "badge":      badge,
        }

    def _wiz_set_status(self, key: str, ok: bool, msg: str):
        s = self._wiz_steps.get(key)
        if not s:
            return
        s["status_var"].set(msg)
        color = GREEN if ok else (YELLOW if "…" in msg else RED)
        s["status_lbl"].configure(fg=color)
        s["badge"].configure(bg=GREEN if ok else (BLUE2 if "…" in msg else RED))

    # ── Wizard checks ────────────────────────────────────────────────────

    def _wiz_check_python(self):
        v = sys.version_info
        ok = v.major >= 3 and v.minor >= 10
        msg = f"✓  Python {v.major}.{v.minor}.{v.micro}" if ok else f"✗  Python {v.major}.{v.minor} (need 3.10+)"
        self.after(0, lambda: self._wiz_set_status("python", ok, msg))

    def _wiz_check_deps(self):
        try:
            import mcp, aiohttp, dotenv
            self.after(0, lambda: self._wiz_set_status("deps", True, "✓  All installed"))
        except ImportError as e:
            self.after(0, lambda: self._wiz_set_status("deps", False, f"✗  Missing: {e.name}"))

    def _wiz_check_ue(self):
        env = read_env()
        host = env.get("UE_REMOTE_CONTROL_HOST", "127.0.0.1")
        port = int(env.get("UE_REMOTE_CONTROL_PORT", 30010))
        ok, _ = check_ue(host, port)
        msg = "✓  UE connected on port 30010" if ok else "✗  UE not detected — follow step instructions"
        key = "ue_plugins"
        self.after(0, lambda: self._wiz_set_status(key, ok, msg))
        # Also update the test step with same result
        test_msg = "✓  Ready — try it in Claude!" if ok else "⏳ Waiting for UE connection"
        self.after(0, lambda: self._wiz_set_status("test", ok, test_msg))

    def _wiz_check_claude(self):
        try:
            sys.path.insert(0, str(ROOT / "setup"))
            from inject_claude_config import find_claude_config
            p = find_claude_config()
            if p and p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                ok = "ueos" in data.get("mcpServers", {})
            else:
                ok = False
        except Exception:
            ok = False
        msg = "✓  Config written — restart Claude" if ok else "✗  Not configured yet — click Auto-fix"
        self.after(0, lambda: self._wiz_set_status("claude", ok, msg))

    # ── Wizard fixes ─────────────────────────────────────────────────────

    def _wiz_fix_deps(self):
        self._wiz_set_status("deps", False, "⏳ Installing…")
        def _run():
            req_file = ROOT / "requirements.txt"
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                self.after(0, lambda: self._wiz_set_status("deps", True, "✓  Installed"))
            else:
                self.after(0, lambda: self._wiz_set_status("deps", False, "✗  Install failed — see Log tab"))
                self.after(0, lambda: self._append_log(result.stdout + result.stderr))
        threading.Thread(target=_run, daemon=True).start()

    def _wiz_open_ue_plugin_guide(self):
        """Open a simple instructions popup + UE docs link."""
        win = tk.Toplevel(self)
        win.title("Enable UE Plugins")
        win.configure(bg=BG2)
        win.geometry("520x320")
        win.resizable(False, False)

        tk.Label(win, text="Enable these two UE plugins",
                 font=FONT_H2, bg=BG2, fg=WHITE).pack(anchor="w", padx=24, pady=(20, 6))

        steps_text = (
            "1.  Open Unreal Engine 5.4\n\n"
            "2.  Go to:  Edit  →  Plugins\n\n"
            '3.  Search  "Remote Control API"  →  Enable  ✓\n\n'
            '4.  Search  "Python Editor Script Plugin"  →  Enable  ✓\n\n'
            "5.  Click  Restart Now\n\n"
            "6.  That's it — port 30010 opens automatically on every launch."
        )
        txt = tk.Text(win, font=FONT_BODY, bg=ACCENT, fg=TEXT,
                      relief="flat", wrap="word", height=10,
                      padx=16, pady=12, state="normal")
        txt.insert("1.0", steps_text)
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        btn_row = tk.Frame(win, bg=BG2)
        btn_row.pack(fill="x", padx=20, pady=(0, 16))
        ttk.Button(btn_row, text="Open UE Plugin Docs",
                   style="Secondary.TButton",
                   command=lambda: webbrowser.open(
                       "https://docs.unrealengine.com/5.4/en-US/remote-control-api-for-unreal-engine/"
                   )).pack(side="left")
        ttk.Button(btn_row, text="Done",
                   style="Accent.TButton",
                   command=win.destroy).pack(side="right")

    def _wiz_fix_claude(self):
        """Auto-inject UEOS into Claude Desktop config."""
        self._wiz_set_status("claude", False, "⏳ Writing config…")
        def _run():
            sys.path.insert(0, str(ROOT / "setup"))
            try:
                from inject_claude_config import main as inject_main
                code = inject_main()
                if code == 0:
                    self.after(0, lambda: self._wiz_set_status(
                        "claude", True, "✓  Done — restart Claude Desktop"))
                    self.after(0, lambda: messagebox.showinfo(
                        "Done",
                        "✅  UEOS added to Claude Desktop!\n\nRestart Claude Desktop to activate.",
                        parent=self))
                elif code == 2:
                    self.after(0, lambda: self._wiz_set_status(
                        "claude", True, "✓  Already configured"))
                else:
                    self.after(0, lambda: self._wiz_set_status(
                        "claude", False, "✗  Claude Desktop not installed"))
                    self.after(0, lambda: webbrowser.open("https://claude.ai/download"))
            except Exception as e:
                self.after(0, lambda: self._wiz_set_status(
                    "claude", False, f"✗  Error: {e}"))
        threading.Thread(target=_run, daemon=True).start()

    # ── Wizard recheck / complete ────────────────────────────────────────

    def _wizard_recheck_all(self):
        # Reset all to checking
        for key in self._wiz_steps:
            self._wiz_set_status(key, False, "⏳ Checking…")
        threading.Thread(target=self._wiz_check_python, daemon=True).start()
        threading.Thread(target=self._wiz_check_deps,   daemon=True).start()
        threading.Thread(target=self._wiz_check_ue,     daemon=True).start()
        threading.Thread(target=self._wiz_check_claude, daemon=True).start()

    def _wizard_complete(self):
        mark_setup_complete()
        # Remove wizard tab and switch to Dashboard
        try:
            self.notebook.forget(self._wizard_tab_index)
        except Exception:
            pass
        self.notebook.select(0)
        # Hide fix button if all green
        self._hbar_fix_btn.pack_forget()

    # ──────────────────────────────────────────────────────────────────────
    # Tab 1 — Dashboard
    # ──────────────────────────────────────────────────────────────────────

    def _build_dashboard_tab(self):
        frame = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(frame, text="  Dashboard  ")

        # ── Server control ──────────────────────────────────────────────
        ctrl = tk.Frame(frame, bg=ACCENT, pady=16)
        ctrl.pack(fill="x", padx=20, pady=(20, 10))

        tk.Label(ctrl, text="MCP Server", font=FONT_H2,
                 bg=ACCENT, fg=WHITE).pack(side="left", padx=20)

        self.server_status_lbl = tk.Label(ctrl, text="● Stopped",
            font=("Segoe UI", 10, "bold"), bg=ACCENT, fg=RED)
        self.server_status_lbl.pack(side="left", padx=(0, 20))

        self.stop_btn = ttk.Button(ctrl, text="Stop",
            style="Secondary.TButton", command=self._stop_server, state="disabled")
        self.stop_btn.pack(side="right", padx=(0, 8))

        self.start_btn = ttk.Button(ctrl, text="▶  Start Server",
            style="Green.TButton", command=self._start_server)
        self.start_btn.pack(side="right", padx=(0, 8))

        # ── Service status cards ─────────────────────────────────────────
        tk.Label(frame, text="Service Status",
                 font=FONT_H2, bg=BG2, fg=WHITE).pack(anchor="w", padx=24, pady=(10, 6))

        cards_frame = tk.Frame(frame, bg=BG2)
        cards_frame.pack(fill="x", padx=20)

        self.status_indicators = {}
        services = [
            ("unreal",     "Unreal Engine 5.4",  "Remote Control API"),
            ("tripo",      "Tripo API",           "3D Generation"),
            ("huanyuan",   "Huanyuan3D",          "3D Generation (optional)"),
            ("metatailor", "MetaTailor",          "Auto-Rigging (optional)"),
        ]

        for i, (key, name, desc) in enumerate(services):
            col = i % 2
            row = i // 2
            card = tk.Frame(cards_frame, bg=ACCENT, pady=14, padx=16,
                            highlightthickness=1, highlightbackground=BG)
            card.grid(row=row, column=col, padx=6, pady=6, sticky="ew")
            cards_frame.columnconfigure(col, weight=1)

            dot_var = tk.StringVar(value="●")
            dot_lbl = tk.Label(card, textvariable=dot_var,
                               font=("Segoe UI", 18), bg=ACCENT, fg=TEXT_DIM)
            dot_lbl.grid(row=0, column=0, rowspan=2, padx=(0, 12))

            tk.Label(card, text=name, font=FONT_H2,
                     bg=ACCENT, fg=WHITE).grid(row=0, column=1, sticky="w")
            msg_var = tk.StringVar(value="Not checked")
            tk.Label(card, textvariable=msg_var, font=FONT_SMALL,
                     bg=ACCENT, fg=TEXT_DIM).grid(row=1, column=1, sticky="w")

            self.status_indicators[key] = {
                "dot": dot_var, "dot_lbl": dot_lbl,
                "msg": msg_var, "card": card
            }

        # ── Quick actions ────────────────────────────────────────────────
        tk.Label(frame, text="Quick Actions",
                 font=FONT_H2, bg=BG2, fg=WHITE).pack(anchor="w", padx=24, pady=(18, 6))

        actions = tk.Frame(frame, bg=BG2)
        actions.pack(fill="x", padx=20)

        btns = [
            ("🔄  Check All Status",    self._poll_status_now),
            ("📂  Open .env File",      self._open_env_file),
            ("📋  Copy Claude Config",  self._copy_claude_config),
            ("🌐  Tripo Dashboard",     lambda: webbrowser.open("https://platform.tripo3d.ai")),
        ]
        for i, (label, cmd) in enumerate(btns):
            ttk.Button(actions, text=label, style="Secondary.TButton",
                       command=cmd).grid(row=0, column=i, padx=6, pady=4, sticky="ew")
            actions.columnconfigure(i, weight=1)

        # ── Tool count ───────────────────────────────────────────────────
        info_frame = tk.Frame(frame, bg=BG2)
        info_frame.pack(fill="x", padx=24, pady=(16, 0))
        tk.Label(info_frame,
            text="339 MCP Tools  •  Blueprint(17)  •  Material(14)  •  Niagara(20)  •  Animation(22)  •  UMG(20)  •  Sequencer(18)"
                 "  •  BehaviorTree(17)  •  EUW(20)  •  GAS(20)  •  EQS(20)  •  NavMesh(17)"
                 "  •  ChaosPhysics(25)  •  PCG(21)  •  EnhancedInput(18)  •  MetaSound(17)",
            font=FONT_SMALL, bg=BG2, fg=TEXT_DIM).pack(anchor="w")

    # ──────────────────────────────────────────────────────────────────────
    # Tab 2 — API Keys
    # ──────────────────────────────────────────────────────────────────────

    def _build_apikeys_tab(self):
        frame = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(frame, text="  API Keys  ")

        canvas = tk.Canvas(frame, bg=BG2, highlightthickness=0)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        inner  = tk.Frame(canvas, bg=BG2)
        inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.key_vars   = {}
        self.key_status = {}

        sections = [
            {
                "service": "tripo",
                "label":   "Tripo API Key",
                "desc":    "Required for text→3D and image→3D generation",
                "link":    "https://platform.tripo3d.ai",
                "link_text": "Get key at platform.tripo3d.ai",
                "env_key": "TRIPO_API_KEY",
                "validate": validate_tripo,
                "placeholder": "tsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            },
            {
                "service": "huanyuan",
                "label":   "Huanyuan3D API Key",
                "desc":    "Optional — alternative 3D generation service",
                "link":    "https://hunyuan.cloud.tencent.com",
                "link_text": "Get key at hunyuan.cloud.tencent.com",
                "env_key": "HUANYUAN_API_KEY",
                "validate": None,
                "placeholder": "Optional",
            },
            {
                "service": "metatailor",
                "label":   "MetaTailor API Key",
                "desc":    "Optional — auto-rigging and clothing simulation",
                "link":    "https://metatailor.io",
                "link_text": "Get key at metatailor.io",
                "env_key": "METATAILOR_API_KEY",
                "validate": None,
                "placeholder": "Optional",
            },
        ]

        for sec in sections:
            self._build_key_section(inner, sec)

        # Save all button
        save_row = tk.Frame(inner, bg=BG2)
        save_row.pack(fill="x", padx=24, pady=(10, 24))
        ttk.Button(save_row, text="💾  Save All Keys",
                   style="Accent.TButton",
                   command=self._save_all_keys).pack(side="right")

    def _build_key_section(self, parent, sec):
        box = tk.Frame(parent, bg=ACCENT, pady=16, padx=20)
        box.pack(fill="x", padx=20, pady=(16, 0))

        # Header row
        hdr = tk.Frame(box, bg=ACCENT)
        hdr.pack(fill="x")
        tk.Label(hdr, text=sec["label"], font=FONT_H2,
                 bg=ACCENT, fg=WHITE).pack(side="left")
        tk.Label(hdr, text=sec["desc"], font=FONT_SMALL,
                 bg=ACCENT, fg=TEXT_DIM).pack(side="left", padx=(12, 0))
        tk.Label(hdr, text=sec["link_text"], font=FONT_SMALL,
                 bg=ACCENT, fg="#74b9ff", cursor="hand2").pack(side="right")
        # make link clickable
        link_lbl = hdr.winfo_children()[-1]
        link_lbl.bind("<Button-1>", lambda e, url=sec["link"]: webbrowser.open(url))

        # Entry row
        entry_row = tk.Frame(box, bg=ACCENT)
        entry_row.pack(fill="x", pady=(10, 0))

        var = tk.StringVar(value=self.env_values.get(sec["env_key"], ""))
        entry = ttk.Entry(entry_row, textvariable=var, show="•", font=FONT_MONO,
                          width=52)
        entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.key_vars[sec["env_key"]] = var

        # Show/hide toggle
        show_var = tk.BooleanVar(value=False)
        def toggle_show(e=entry, sv=show_var):
            sv.set(not sv.get())
            e.configure(show="" if sv.get() else "•")
        ttk.Button(entry_row, text="👁", style="Secondary.TButton",
                   command=toggle_show, width=3).pack(side="left", padx=(6, 0))

        # Validate button (only if validator exists)
        status_var = tk.StringVar(value="")
        status_lbl = tk.Label(box, textvariable=status_var,
                              font=FONT_SMALL, bg=ACCENT, fg=TEXT_DIM)
        status_lbl.pack(anchor="w", pady=(6, 0))
        self.key_status[sec["env_key"]] = (status_var, status_lbl)

        if sec["validate"]:
            def do_validate(v=var, sv=status_var, sl=status_lbl, fn=sec["validate"]):
                key = v.get().strip()
                sv.set("Validating…")
                sl.configure(fg=YELLOW)
                def _run():
                    ok, msg = fn(key)
                    self.after(0, lambda: sv.set(("✓  " if ok else "✗  ") + msg))
                    self.after(0, lambda: sl.configure(fg=GREEN if ok else RED))
                threading.Thread(target=_run, daemon=True).start()

            ttk.Button(entry_row, text="Validate",
                       style="Secondary.TButton",
                       command=do_validate).pack(side="left", padx=(6, 0))

    def _save_all_keys(self):
        values = read_env()
        for env_key, var in self.key_vars.items():
            values[env_key] = var.get().strip()
        write_env(values)
        self.env_values = values
        messagebox.showinfo("Saved", "API keys saved to .env\n\nRestart the MCP server if it's running.", parent=self)

    # ──────────────────────────────────────────────────────────────────────
    # Tab 3 — Settings
    # ──────────────────────────────────────────────────────────────────────

    def _build_settings_tab(self):
        frame = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(frame, text="  Settings  ")

        def section_label(text):
            tk.Label(frame, text=text, font=FONT_H2,
                     bg=BG2, fg=WHITE).pack(anchor="w", padx=24, pady=(20, 6))

        def field_row(parent, label, env_key, default="", browse=False):
            row = tk.Frame(parent, bg=ACCENT, pady=12, padx=16)
            row.pack(fill="x", padx=20, pady=3)

            tk.Label(row, text=label, font=FONT_BODY,
                     bg=ACCENT, fg=TEXT, width=26, anchor="w").pack(side="left")

            var = tk.StringVar(value=self.env_values.get(env_key, default))
            self.settings_vars[env_key] = var

            entry = ttk.Entry(row, textvariable=var, font=FONT_BODY, width=36)
            entry.pack(side="left", padx=(0, 8), ipady=4)

            if browse:
                def pick_dir(v=var):
                    d = filedialog.askdirectory(title="Select folder")
                    if d:
                        v.set(d)
                ttk.Button(row, text="Browse…", style="Secondary.TButton",
                           command=pick_dir).pack(side="left")
            return var

        self.settings_vars = {}

        # ── UE Remote Control ───────────────────────────────────────────
        section_label("Unreal Engine 5.4")

        ue_box = tk.Frame(frame, bg=ACCENT, pady=12, padx=16)
        ue_box.pack(fill="x", padx=20, pady=3)
        tk.Label(ue_box, text="Remote Control Host", font=FONT_BODY,
                 bg=ACCENT, fg=TEXT, width=26, anchor="w").pack(side="left")
        host_var = tk.StringVar(value=self.env_values.get("UE_REMOTE_CONTROL_HOST", "127.0.0.1"))
        self.settings_vars["UE_REMOTE_CONTROL_HOST"] = host_var
        ttk.Entry(ue_box, textvariable=host_var, font=FONT_BODY, width=20).pack(side="left", padx=(0,8), ipady=4)

        tk.Label(ue_box, text="Port", font=FONT_BODY,
                 bg=ACCENT, fg=TEXT).pack(side="left", padx=(12,4))
        port_var = tk.StringVar(value=self.env_values.get("UE_REMOTE_CONTROL_PORT", "30010"))
        self.settings_vars["UE_REMOTE_CONTROL_PORT"] = port_var
        ttk.Entry(ue_box, textvariable=port_var, font=FONT_BODY, width=8).pack(side="left", padx=(0,8), ipady=4)

        ue_status_var = tk.StringVar(value="")
        ue_status_lbl = tk.Label(ue_box, textvariable=ue_status_var,
                                  font=FONT_SMALL, bg=ACCENT, fg=TEXT_DIM)
        ue_status_lbl.pack(side="left", padx=8)

        def test_ue():
            ue_status_var.set("Testing…")
            ue_status_lbl.configure(fg=YELLOW)
            def _run():
                ok, msg = check_ue(host_var.get(), port_var.get())
                self.after(0, lambda: ue_status_var.set(("✓  " if ok else "✗  ") + msg))
                self.after(0, lambda: ue_status_lbl.configure(fg=GREEN if ok else RED))
            threading.Thread(target=_run, daemon=True).start()

        ttk.Button(ue_box, text="Test Connection",
                   style="Secondary.TButton", command=test_ue).pack(side="left")

        # ── Asset Storage ───────────────────────────────────────────────
        section_label("Asset Storage")
        field_row(frame, "Temp Download Directory",
                  "UEOS_ASSET_TEMP_DIR", "C:/UEOS/temp", browse=True)

        # ── Logging ─────────────────────────────────────────────────────
        section_label("Logging")
        log_box = tk.Frame(frame, bg=ACCENT, pady=12, padx=16)
        log_box.pack(fill="x", padx=20, pady=3)
        tk.Label(log_box, text="Log Level", font=FONT_BODY,
                 bg=ACCENT, fg=TEXT, width=26, anchor="w").pack(side="left")
        log_var = tk.StringVar(value=self.env_values.get("UEOS_LOG_LEVEL", "INFO"))
        self.settings_vars["UEOS_LOG_LEVEL"] = log_var
        ttk.Combobox(log_box, textvariable=log_var, font=FONT_BODY,
                     values=["DEBUG", "INFO", "WARNING", "ERROR"],
                     state="readonly", width=12).pack(side="left", ipady=4)

        # ── Save ─────────────────────────────────────────────────────────
        save_row = tk.Frame(frame, bg=BG2)
        save_row.pack(fill="x", padx=24, pady=20)
        ttk.Button(save_row, text="💾  Save Settings",
                   style="Accent.TButton",
                   command=self._save_settings).pack(side="right")

    def _save_settings(self):
        values = read_env()
        for k, var in self.settings_vars.items():
            values[k] = var.get().strip()
        write_env(values)
        self.env_values = values

        # Create temp dir if needed
        temp = values.get("UEOS_ASSET_TEMP_DIR", "")
        if temp:
            try:
                Path(temp).mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        messagebox.showinfo("Saved", "Settings saved to .env", parent=self)

    # ──────────────────────────────────────────────────────────────────────
    # Tab 4 — Claude Config
    # ──────────────────────────────────────────────────────────────────────

    def _build_claude_tab(self):
        frame = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(frame, text="  Claude Setup  ")

        tk.Label(frame, text="Claude Desktop Configuration",
                 font=FONT_H2, bg=BG2, fg=WHITE).pack(anchor="w", padx=24, pady=(20, 4))
        tk.Label(frame,
            text="UEOS runs as an MCP server inside Claude Desktop.\nThis tab detects your config file and writes the server entry automatically.",
            font=FONT_SMALL, bg=BG2, fg=TEXT_DIM, justify="left").pack(anchor="w", padx=24)

        # Config file location
        loc_box = tk.Frame(frame, bg=ACCENT, pady=14, padx=16)
        loc_box.pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(loc_box, text="Config file location",
                 font=FONT_BODY, bg=ACCENT, fg=TEXT, width=22, anchor="w").pack(side="left")

        detected = self._detect_claude_config()
        self.claude_path_var = tk.StringVar(value=str(detected) if detected else "")
        path_entry = ttk.Entry(loc_box, textvariable=self.claude_path_var,
                               font=FONT_MONO, width=50)
        path_entry.pack(side="left", padx=(0,8), ipady=4)

        def browse_claude():
            f = filedialog.askopenfilename(
                title="Select claude_desktop_config.json",
                filetypes=[("JSON", "*.json"), ("All files", "*.*")]
            )
            if f:
                self.claude_path_var.set(f)
        ttk.Button(loc_box, text="Browse…",
                   style="Secondary.TButton", command=browse_claude).pack(side="left")

        # Status
        self.claude_status_var = tk.StringVar(value="")
        tk.Label(frame, textvariable=self.claude_status_var,
                 font=FONT_SMALL, bg=BG2, fg=TEXT_DIM).pack(anchor="w", padx=24, pady=(6,0))
        self._check_claude_config()

        # Preview
        tk.Label(frame, text="Config block that will be written:",
                 font=FONT_H2, bg=BG2, fg=WHITE).pack(anchor="w", padx=24, pady=(16, 4))

        preview_frame = tk.Frame(frame, bg=BG, padx=16, pady=12)
        preview_frame.pack(fill="x", padx=20)
        self.claude_preview = tk.Text(preview_frame, font=FONT_MONO,
                                      bg="#0d0d1a", fg="#00cec9",
                                      height=10, relief="flat",
                                      wrap="none", state="disabled",
                                      insertbackground=WHITE)
        self.claude_preview.pack(fill="x")
        self._refresh_claude_preview()

        # Buttons
        btn_row = tk.Frame(frame, bg=BG2)
        btn_row.pack(fill="x", padx=20, pady=16)

        ttk.Button(btn_row, text="✅  Write Config Automatically",
                   style="Green.TButton",
                   command=self._write_claude_config).pack(side="left", padx=(0,8))
        ttk.Button(btn_row, text="📋  Copy to Clipboard",
                   style="Secondary.TButton",
                   command=self._copy_claude_config).pack(side="left", padx=(0,8))
        ttk.Button(btn_row, text="📂  Open Config File",
                   style="Secondary.TButton",
                   command=self._open_claude_config).pack(side="left")

        # Instructions
        tk.Label(frame,
            text="After writing the config, restart Claude Desktop completely for changes to take effect.",
            font=FONT_SMALL, bg=BG2, fg=YELLOW).pack(anchor="w", padx=24, pady=(4, 0))

    def _detect_claude_config(self) -> Path | None:
        for p in CLAUDE_CONFIGS:
            if p.exists():
                return p
        # Return the platform default even if it doesn't exist yet
        if sys.platform == "win32":
            return CLAUDE_CONFIGS[0]
        elif sys.platform == "darwin":
            return CLAUDE_CONFIGS[1]
        return CLAUDE_CONFIGS[2]

    def _get_mcp_block(self) -> dict:
        server_path = str(SERVER_PY).replace("\\", "\\\\")
        cwd_path    = str(SERVER_PY.parent).replace("\\", "\\\\")
        return {
            "command": sys.executable,
            "args":    [str(SERVER_PY)],
            "cwd":     str(SERVER_PY.parent)
        }

    def _refresh_claude_preview(self):
        block   = {"mcpServers": {"ueos": self._get_mcp_block()}}
        preview = json.dumps(block, indent=2)
        self.claude_preview.configure(state="normal")
        self.claude_preview.delete("1.0", "end")
        self.claude_preview.insert("1.0", preview)
        self.claude_preview.configure(state="disabled")

    def _check_claude_config(self):
        p = self.claude_path_var.get()
        if not p:
            self.claude_status_var.set("⚠  Config file not found — will create it")
            return
        path = Path(p)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if "ueos" in data.get("mcpServers", {}):
                    self.claude_status_var.set("✓  UEOS already configured in this file")
                else:
                    self.claude_status_var.set("ℹ  Claude config found — UEOS not yet added")
            except Exception:
                self.claude_status_var.set("⚠  Config file found but couldn't parse JSON")
        else:
            self.claude_status_var.set("ℹ  Config file doesn't exist yet — will create it")

    def _write_claude_config(self):
        p = self.claude_path_var.get().strip()
        if not p:
            messagebox.showerror("Error", "No config file path set.", parent=self)
            return
        path = Path(p)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
            else:
                data = {}
            if "mcpServers" not in data:
                data["mcpServers"] = {}
            data["mcpServers"]["ueos"] = self._get_mcp_block()
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self._check_claude_config()
            messagebox.showinfo("Done",
                "✅ UEOS added to Claude Desktop config!\n\nRestart Claude Desktop to activate.",
                parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Could not write config:\n{e}", parent=self)

    def _copy_claude_config(self):
        block   = {"mcpServers": {"ueos": self._get_mcp_block()}}
        preview = json.dumps(block, indent=2)
        self.clipboard_clear()
        self.clipboard_append(preview)
        messagebox.showinfo("Copied", "Config block copied to clipboard.", parent=self)

    def _open_claude_config(self):
        p = self.claude_path_var.get()
        if p and Path(p).exists():
            if sys.platform == "win32":
                os.startfile(p)
            elif sys.platform == "darwin":
                subprocess.run(["open", p])
            else:
                subprocess.run(["xdg-open", p])
        else:
            messagebox.showinfo("Not found", "Config file doesn't exist yet.\nClick 'Write Config' to create it.", parent=self)

    # ──────────────────────────────────────────────────────────────────────
    # Tab 5 — Log
    # ──────────────────────────────────────────────────────────────────────

    def _build_log_tab(self):
        frame = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(frame, text="  Log  ")

        top = tk.Frame(frame, bg=BG2)
        top.pack(fill="x", padx=16, pady=(10, 4))
        tk.Label(top, text="Server Log", font=FONT_H2,
                 bg=BG2, fg=WHITE).pack(side="left")
        ttk.Button(top, text="Clear", style="Secondary.TButton",
                   command=self._clear_log).pack(side="right")
        ttk.Button(top, text="📂 Open log file", style="Secondary.TButton",
                   command=self._open_log_file).pack(side="right", padx=(0, 6))

        self.log_text = tk.Text(frame, font=FONT_MONO, bg="#0a0a16", fg="#a8d8ea",
                                relief="flat", wrap="none", state="disabled",
                                insertbackground=WHITE)
        scroll_y = ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
        scroll_x = ttk.Scrollbar(frame, orient="horizontal", command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        self.log_text.pack(fill="both", expand=True, padx=0)

        # Tag colors for log levels
        self.log_text.tag_configure("ERROR",   foreground=RED)
        self.log_text.tag_configure("WARNING", foreground=YELLOW)
        self.log_text.tag_configure("INFO",    foreground="#a8d8ea")
        self.log_text.tag_configure("DEBUG",   foreground=TEXT_DIM)

        self._log_pos = 0
        self._tail_log()

    def _append_log(self, text: str):
        self.log_text.configure(state="normal")
        for line in text.splitlines(keepends=True):
            tag = "INFO"
            if "ERROR" in line:    tag = "ERROR"
            elif "WARNING" in line: tag = "WARNING"
            elif "DEBUG" in line:  tag = "DEBUG"
            self.log_text.insert("end", line, tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _tail_log(self):
        if LOG_FILE.exists():
            try:
                with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(self._log_pos)
                    new_text = f.read()
                    self._log_pos = f.tell()
                if new_text:
                    self._append_log(new_text)
            except Exception:
                pass
        self._log_after = self.after(1000, self._tail_log)

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self._log_pos = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0

    def _open_log_file(self):
        if LOG_FILE.exists():
            if sys.platform == "win32":
                os.startfile(LOG_FILE)
            elif sys.platform == "darwin":
                subprocess.run(["open", LOG_FILE])
            else:
                subprocess.run(["xdg-open", LOG_FILE])

    # ──────────────────────────────────────────────────────────────────────
    # Server start / stop
    # ──────────────────────────────────────────────────────────────────────

    def _start_server(self):
        if self.server_proc and self.server_proc.poll() is None:
            return  # already running
        try:
            self.server_proc = subprocess.Popen(
                [sys.executable, str(SERVER_PY)],
                cwd=str(SERVER_PY.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            self._update_server_ui(running=True)
            self._append_log(f"[UEOS] Server started (PID {self.server_proc.pid})\n")
        except Exception as e:
            messagebox.showerror("Error", f"Could not start server:\n{e}", parent=self)

    def _stop_server(self):
        if self.server_proc:
            self.server_proc.terminate()
            self.server_proc = None
        self._update_server_ui(running=False)
        self._append_log("[UEOS] Server stopped\n")

    def _update_server_ui(self, running: bool):
        if running:
            self.server_status_lbl.configure(text="● Running", fg=GREEN)
            self.header_status_var.set("● Server Running")
            self.header_status_lbl.configure(fg=GREEN)
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
        else:
            self.server_status_lbl.configure(text="● Stopped", fg=RED)
            self.header_status_var.set("● Server Stopped")
            self.header_status_lbl.configure(fg=RED)
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")

    # ──────────────────────────────────────────────────────────────────────
    # Status polling
    # ──────────────────────────────────────────────────────────────────────

    def _set_indicator(self, key: str, ok: bool, msg: str):
        ind = self.status_indicators.get(key)
        if not ind:
            return
        ind["dot"].set("●")
        ind["dot_lbl"].configure(fg=GREEN if ok else (TEXT_DIM if "optional" in msg.lower() else RED))
        ind["msg"].set(msg)

    def _poll_status(self):
        env = read_env()

        def _check_tripo():
            key = env.get("TRIPO_API_KEY", "")
            if not key:
                self.after(0, lambda: self._set_indicator("tripo", False, "API key not set — add in API Keys tab"))
                return
            ok, msg = validate_tripo(key)
            self.after(0, lambda: self._set_indicator("tripo", ok, msg))

        def _check_ue():
            host = env.get("UE_REMOTE_CONTROL_HOST", "127.0.0.1")
            port = env.get("UE_REMOTE_CONTROL_PORT", "30010")
            ok, msg = check_ue(host, port)
            self.after(0, lambda: self._set_indicator("unreal", ok, msg))

        def _check_optional(key_name, svc_key, svc_name):
            key = env.get(key_name, "")
            if not key:
                self.after(0, lambda: self._set_indicator(svc_key, False, f"Not configured (optional)"))
            else:
                self.after(0, lambda: self._set_indicator(svc_key, True, "Key configured"))

        # Set to "checking" state
        for key in self.status_indicators:
            self._set_indicator(key, False, "Checking…")

        threading.Thread(target=_check_ue,    daemon=True).start()
        threading.Thread(target=_check_tripo, daemon=True).start()
        threading.Thread(target=lambda: _check_optional("HUANYUAN_API_KEY",   "huanyuan",   "Huanyuan3D"), daemon=True).start()
        threading.Thread(target=lambda: _check_optional("METATAILOR_API_KEY", "metatailor", "MetaTailor"), daemon=True).start()

        # Check if server process is still alive
        if self.server_proc and self.server_proc.poll() is not None:
            self.server_proc = None
            self._update_server_ui(running=False)
            self._append_log("[UEOS] Server process exited\n")

        # Schedule next poll (every 30s)
        self._status_after = self.after(30000, self._poll_status)

    def _poll_status_now(self):
        """Immediate status check from quick action button."""
        if self._status_after:
            self.after_cancel(self._status_after)
        self._poll_status()

    # ──────────────────────────────────────────────────────────────────────
    # Misc
    # ──────────────────────────────────────────────────────────────────────

    def _open_env_file(self):
        if not ENV_FILE.exists() and EXAMPLE.exists():
            shutil.copy(EXAMPLE, ENV_FILE)
        if sys.platform == "win32":
            os.startfile(ENV_FILE)
        elif sys.platform == "darwin":
            subprocess.run(["open", ENV_FILE])
        else:
            subprocess.run(["xdg-open", ENV_FILE])

    def destroy(self):
        if self._log_after:
            self.after_cancel(self._log_after)
        if self._status_after:
            self.after_cancel(self._status_after)
        if self.server_proc:
            self.server_proc.terminate()
        super().destroy()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if sys.platform == "win32":
        import ctypes
        # Enable DPI awareness for sharp rendering on Windows
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        # Enable ANSI in any attached console
        os.system("")

    app = UEOSLauncher()
    app.mainloop()
