"""ANTARES operator control panel — customtkinter GUI.

This module is the single entry point for the ANTARES clinical operator.  It
provides a full-screen customtkinter window split into a scrollable settings
sidebar and a main content panel with a real-time log.

Architecture overview
---------------------
- **Sidebar**: collects all session parameters (subject info, NF protocol,
  session design, trigger settings, directory paths) via customtkinter widgets
  backed by ``ctk.StringVar`` / ``ctk.BooleanVar`` / ``ctk.DoubleVar``.
- **Content panel**: displays a status label, overall progress bar, per-block
  progress bar (shown only during NF), a scrollable monospace log, and action
  buttons.
- **Pipeline threads**: each action button (Start Full Protocol, Baseline Only,
  Analyse Only, NF Session Only) launches a daemon thread that calls the
  appropriate pipeline function(s) from the ``pipeline`` package.  The GUI
  remains responsive throughout.
- **rspv subprocess**: the participant-facing neurofeedback visual (``rspv``)
  is launched as a separate subprocess.  The operator panel drives its state
  (waiting / fixation / instruction / thankyou) by writing flag files under
  ``/tmp/`` and waits for the participant to press Space before advancing.
- **Trigger support**: hardware TTL triggers are sent via ``SerialTrigger``
  (USB TriggerBox) or ``ParallelTrigger`` (LPT), selected by a sidebar toggle.

Operator UI is always in English.
Participant-screen language (English / German / French) is a separate sidebar
setting.

Flag files (``/tmp/antares_*``)
---------------------------------
- ``antares_participant_ready.flag``: written by the participant GUI when the
  participant presses Space on the welcome screen.
- ``antares_rspv_ready.flag``: written by rspv when the participant confirms
  on the instruction page.
- ``antares_rspv_show_baseline.flag``: written by the operator to switch rspv
  from the waiting screen to the fixation cross.
- ``antares_rspv_show_instruction.flag``: written by the operator to switch
  rspv from the fixation cross to the NF instruction page.
- ``antares_rspv_show_thankyou.flag``: written by the operator at session end.

Usage
-----
Run directly::

    python antares_app.py

or via the ``ANTARES`` desktop shortcut, which starts this module inside the
project virtual environment.
"""
from __future__ import annotations

import json
import logging
import platform
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import yaml

from pipeline import get_user_info, compute_pta, run_baseline, run_full_analysis, run_nf_session
from pipeline.session_manager import SessionManager
from pipeline.triggers import make_trigger, SerialTrigger, ParallelTrigger

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

_HERE = Path(__file__).parent
_CONFIG_FILE = _HERE / "config_master.yml"
_RSPV_MAIN   = _HERE / "rspv" / "src" / "main.py"
_RSPV_CFG    = _HERE / "rspv" / "config.json"
_GUI_SCRIPT  = _HERE / "antares_gui.py"
_GUI_STATE   = Path("/tmp/antares_session_state.json")

_PROTO_LABELS    = ["Z-Score (recommended)", "Threshold", "Staircase", "Sham (control)"]
_PROTO_INTERNAL  = ["zscore", "threshold", "staircase", "sham"]

_RSPV_VISUALS = [
    "VisualComplexMetaBalls",
    "VisualTree", "VisualRorschach", "VisualEllipses", "VisualWire",
    "VisualSunflower", "VisualGalaxySpiral", "VisualRings",
    "VisualFlowField", "VisualAmoeba", "VisualMetaBalls", "VisualSpider",
]

# Suppress informational "not installed" messages from arviz optional packages.
logging.getLogger("arviz").setLevel(logging.WARNING)

_PARTICIPANT_LANGS = {
    "English":          "en",
    "German (Deutsch)": "de",
    "French (Français)": "fr",
}

_DEFAULT_MOCK_FNAME = "/mnt/c/ANTARES/ANT/data/simulated/pericalcarine-lh_10_2-raw.fif"

# Font families — DejaVu Sans/Mono are installed by default on Ubuntu and
# are available to Tk via Xft/fontconfig even when tkfont.families() only
# returns core-X11 fonts (which is the case in WSLg).
_FONT_UI   = "DejaVu Sans"
_FONT_MONO = "DejaVu Sans Mono"

# Participant-ready flag: participant screen writes this when space is pressed.
_READY_FILE = Path("/tmp/antares_participant_ready.flag")
# rspv-ready flag: rspv writes this when participant presses Space on the
# instruction page — signals the operator that the block scheduler may start.
_RSPV_READY_FILE = Path("/tmp/antares_rspv_ready.flag")
# Operator writes these to drive rspv phase transitions.
_RSPV_BASELINE_FLAG    = Path("/tmp/antares_rspv_show_baseline.flag")
_RSPV_INSTRUCTION_FLAG = Path("/tmp/antares_rspv_show_instruction.flag")
_RSPV_THANKYOU_FLAG    = Path("/tmp/antares_rspv_show_thankyou.flag")


# ---------------------------------------------------------------------------
# Helper: log handler forwarding to a callback
# ---------------------------------------------------------------------------

class _CallbackHandler(logging.Handler):
    def __init__(self, callback):
        super().__init__()
        self._cb = callback

    def emit(self, record):
        self._cb(self.format(record))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class AntaresApp(ctk.CTk):
    """Main ANTARES operator control panel window.

    Inherits from ``customtkinter.CTk`` (the root window).  On construction
    it loads the master YAML config, builds the full UI, and applies any
    saved defaults from the config file.

    The window title is set to
    ``"ANTARES - Advancing Neurofeedback in Tinnitus"`` and the minimum size
    is 1484 × 720 pixels.  On WSLg, widget scaling is bumped to 1.25× for
    readability on high-DPI monitors.
    """

    def __init__(self) -> None:
        super().__init__()

        self._cfg = self._load_config()
        self._stop_event = threading.Event()
        self._n_blocks_total = 0
        self._rspv_proc: subprocess.Popen | None = None
        self._gui_proc:  subprocess.Popen | None = None
        self._session_mgr = SessionManager()

        self.title("ANTARES - Advancing Neurofeedback in Tinnitus")
        self.geometry("1792x820")
        self.minsize(1484, 720)

        self._build_ui()
        self._apply_config_defaults()
        # No root-logger handler — pipeline functions call log_callback directly,
        # adding a root handler would duplicate every message.

    # -----------------------------------------------------------------------
    # Config
    # -----------------------------------------------------------------------

    def _load_config(self) -> dict:
        """Load and return the master YAML config, or an empty dict if missing.

        Returns:
            dict: Parsed YAML contents of ``config_master.yml``, or ``{}``
            if the file does not exist or is empty.
        """
        if _CONFIG_FILE.exists():
            with open(_CONFIG_FILE) as fh:
                return yaml.safe_load(fh) or {}
        return {}

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the top bar, sidebar, and content panel widgets."""
        self._build_topbar()
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True)
        self._build_sidebar(outer)
        self._build_content(outer)

    def _build_topbar(self) -> None:
        """Build the fixed-height top bar with the application title label."""
        bar = ctk.CTkFrame(self, height=52, corner_radius=0,
                           fg_color=("gray80", "gray20"))
        bar.pack(side="top", fill="x")
        bar.pack_propagate(False)
        
        ui_font = ctk.CTkFont(family=_FONT_UI, size=16, weight="bold")

        ctk.CTkLabel(
            bar,
            text="ANTARES - Advancing Neurofeedback in Tinnitus",
            font=ui_font,
        ).pack(side="left", padx=16, pady=12)

    def _build_sidebar(self, parent: ctk.CTkFrame) -> None:
        """Build the scrollable settings sidebar and all its sub-sections."""
        self._sidebar = ctk.CTkScrollableFrame(
            parent, width=320, corner_radius=0,
            fg_color=("gray88", "gray18"),
        )
        self._sidebar.pack(side="left", fill="y")
        self._build_subject_section()
        self._build_protocol_section()
        self._build_session_section()
        self._build_paths_section()

    # --- Subject -------------------------------------------------------------

    def _build_subject_section(self) -> None:
        """Build the Subject sidebar section (ID, age, sex, visit, LSL, triggers)."""
        sb = self._sidebar
        self._sec("Subject")

        self._lbl(sb, "Subject ID (4 letters)")
        self._id_var = ctk.StringVar()
        self._id_entry = ctk.CTkEntry(
            sb, textvariable=self._id_var, width=280,
            placeholder_text="e.g. abcd",
        )
        self._id_entry.pack(padx=16, pady=(0, 8))

        self._lbl(sb, "Age")
        self._age_var = ctk.StringVar()
        ctk.CTkEntry(sb, textvariable=self._age_var, width=280).pack(padx=16, pady=(0, 8))

        self._lbl(sb, "Sex")
        self._sex_var = ctk.StringVar(value="Female")
        self._sex_menu = ctk.CTkOptionMenu(
            sb, variable=self._sex_var,
            values=["Female", "Male"], width=280,
        )
        self._sex_menu.pack(padx=16, pady=(0, 8))

        self._lbl(sb, "Visit Number")
        self._visit_var = ctk.StringVar(value="1")
        ctk.CTkEntry(sb, textvariable=self._visit_var, width=280).pack(padx=16, pady=(0, 8))

        # Participant language (for py5 screen)
        self._lbl(sb, "Participant Language")
        self._participant_lang_var = ctk.StringVar(value="English")
        ctk.CTkOptionMenu(
            sb, variable=self._participant_lang_var,
            values=list(_PARTICIPANT_LANGS.keys()), width=280,
        ).pack(padx=16, pady=(0, 8))

        self._lbl(sb, "Mock LSL (no hardware)")
        self._mock_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(
            sb, variable=self._mock_var, text="",
            command=self._on_mock_toggle,
        ).pack(padx=16, pady=(0, 4), anchor="w")

        # Container keeps the mock/real rows at their correct sidebar position.
        # pack_forget/pack within it won't displace them to the bottom of the sidebar.
        self._lsl_container = ctk.CTkFrame(sb, fg_color="transparent")
        self._lsl_container.pack(fill="x")

        # Mock file row — inside container, visible only when mock is ON
        self._mockfile_row = ctk.CTkFrame(self._lsl_container, fg_color="transparent")
        ctk.CTkLabel(self._mockfile_row, text="Mock LSL File", anchor="w").pack(
            padx=16, pady=(0, 2), anchor="w",
        )
        fr = ctk.CTkFrame(self._mockfile_row, fg_color="transparent")
        fr.pack(padx=16, pady=(0, 8), fill="x")
        self._mockfile_var = ctk.StringVar(value=_DEFAULT_MOCK_FNAME)
        ctk.CTkEntry(fr, textvariable=self._mockfile_var, width=220).pack(side="left")
        ctk.CTkButton(fr, text="...", width=40, command=self._browse_mockfile).pack(
            side="left", padx=4,
        )

        # Real LSL connection rows — inside container, visible when mock is OFF (default)
        self._lsl_real_rows = ctk.CTkFrame(self._lsl_container, fg_color="transparent")
        self._lbl(self._lsl_real_rows, "LSL Stream Name")
        self._stream_name_var = ctk.StringVar(value="BrainVision RDA")
        ctk.CTkEntry(
            self._lsl_real_rows, textvariable=self._stream_name_var, width=280,
        ).pack(padx=16, pady=(0, 8))
        self._lbl(self._lsl_real_rows, "LSL Source ID")
        self._stream_source_id_var = ctk.StringVar(value="RDA 127.0.0.1:51244")
        ctk.CTkEntry(
            self._lsl_real_rows, textvariable=self._stream_source_id_var, width=280,
        ).pack(padx=16, pady=(0, 8))
        self._lsl_real_rows.pack(fill="x", pady=(0, 4))

        # Trigger section
        self._lbl(sb, "Triggers (BrainVision)")
        self._trigger_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(
            sb, variable=self._trigger_var, text="Enable triggers",
        ).pack(padx=16, pady=(0, 4), anchor="w")
        self._lbl(sb, "Trigger Mode")
        self._trigger_mode_var = ctk.StringVar(value="serial")
        ctk.CTkSegmentedButton(
            sb, values=["serial", "lpt"],
            variable=self._trigger_mode_var,
            width=280,
        ).pack(padx=16, pady=(0, 4))
        self._lbl(sb, "Serial Port  (serial mode)")
        self._trigger_port_var = ctk.StringVar(value="COM4")
        ctk.CTkEntry(
            sb, textvariable=self._trigger_port_var, width=280,
        ).pack(padx=16, pady=(0, 4))
        self._lbl(sb, "LPT Address  (lpt mode, hex)")
        self._trigger_addr_var = ctk.StringVar(value="0x3FF0")
        ctk.CTkEntry(
            sb, textvariable=self._trigger_addr_var, width=280,
        ).pack(padx=16, pady=(0, 8))

    # --- Protocol ------------------------------------------------------------

    def _build_protocol_section(self) -> None:
        """Build the Protocol sidebar section (NF protocol, z-score threshold, warmup)."""
        sb = self._sidebar
        self._sec("Protocol")

        self._lbl(sb, "NF Protocol")
        self._proto_var = ctk.StringVar(value=_PROTO_LABELS[0])
        ctk.CTkOptionMenu(
            sb, variable=self._proto_var,
            values=_PROTO_LABELS, width=280,
            command=self._on_protocol_change,
        ).pack(padx=16, pady=(0, 8))

        self._lbl(sb, "Z-Score Threshold")
        self._zthr_var = ctk.DoubleVar(value=0.5)
        ctk.CTkSlider(
            sb, from_=0.1, to=2.0, variable=self._zthr_var, width=240,
            command=lambda v: self._zthr_val_lbl.configure(text=f"{float(v):.2f}"),
        ).pack(padx=16, pady=(0, 2))
        self._zthr_val_lbl = ctk.CTkLabel(sb, text="0.50", anchor="w")
        self._zthr_val_lbl.pack(padx=16, pady=(0, 8), anchor="w")

        self._lbl(sb, "Warmup Windows")
        self._warmup_var = ctk.StringVar(value="20")
        ctk.CTkEntry(sb, textvariable=self._warmup_var, width=280).pack(padx=16, pady=(0, 8))

        # Threshold value row — shown only for Threshold protocol
        self._thr_val_row = ctk.CTkFrame(sb, fg_color="transparent")
        ctk.CTkLabel(self._thr_val_row, text="Threshold Value", anchor="w").pack(
            padx=16, pady=(0, 2), anchor="w",
        )
        self._thr_val_var = ctk.StringVar(value="0.0")
        ctk.CTkEntry(self._thr_val_row, textvariable=self._thr_val_var, width=280).pack(
            padx=16, pady=(0, 8),
        )

    # --- Session Design ------------------------------------------------------

    def _build_session_section(self) -> None:
        """Build the Session Design sidebar section (durations, blocks, OSC, visual)."""
        sb = self._sidebar
        self._sec("Session Design")

        fields = [
            ("Baseline Duration (s)", "baseline_dur_var", "90"),
            ("Number of Blocks",      "nblocks_var",      "4"),
            ("Rest Duration / Block (s)", "rest_dur_var", "30"),
            ("NF Duration / Block (s)",   "nf_dur_var",   "120"),
            ("OSC Host (rspv)",        "osc_host_var",    "127.0.0.1"),
            ("OSC Port (rspv)",        "osc_port_var",    "5005"),
        ]
        for label, attr, default in fields:
            self._lbl(sb, label)
            var = ctk.StringVar(value=default)
            setattr(self, f"_{attr}", var)
            ctk.CTkEntry(sb, textvariable=var, width=280).pack(padx=16, pady=(0, 8))

        # Visual preset for rspv
        self._lbl(sb, "Participant Visual (rspv)")
        self._visual_var = ctk.StringVar(value=_RSPV_VISUALS[0])
        ctk.CTkOptionMenu(
            sb, variable=self._visual_var,
            values=_RSPV_VISUALS, width=280,
        ).pack(padx=16, pady=(0, 8))

    # --- Paths ---------------------------------------------------------------

    def _build_paths_section(self) -> None:
        """Build the Paths sidebar section (subjects dir, audiometry dir, models dir)."""
        sb = self._sidebar
        self._sec("Paths")
        cfg = self._cfg
        paths = [
            ("Subjects Dir",   "subjects_dir_var",  cfg.get("subjects_dir", ""),   self._browse_subjects_dir),
            ("Audiometry Dir", "audio_dir_var",      cfg.get("audiometry_dir", ""), self._browse_audio_dir),
            ("Models Dir",     "models_dir_var",     cfg.get("models_dir", ""),     self._browse_models_dir),
        ]
        for label, attr, default, cmd in paths:
            ctk.CTkLabel(sb, text=label, anchor="w").pack(padx=16, pady=(0, 2), anchor="w")
            var = ctk.StringVar(value=str(default))
            setattr(self, f"_{attr}", var)
            row = ctk.CTkFrame(sb, fg_color="transparent")
            row.pack(padx=16, pady=(0, 8), fill="x")
            ctk.CTkEntry(row, textvariable=var, width=220).pack(side="left")
            ctk.CTkButton(row, text="...", width=40, command=cmd).pack(side="left", padx=4)

    # --- Content (right panel) -----------------------------------------------

    def _build_content(self, parent: ctk.CTkFrame) -> None:
        """Build the main content panel (status, progress bars, log, action buttons)."""
        self._content = ctk.CTkFrame(parent, corner_radius=0, fg_color="transparent")
        self._content.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        # Status row
        self._status_frame = ctk.CTkFrame(self._content, corner_radius=8)
        self._status_frame.pack(fill="x", pady=(0, 8))
        self._status_lbl = ctk.CTkLabel(
            self._status_frame, text="Ready",
            font=ctk.CTkFont(family=_FONT_UI, size=15, weight="bold"), anchor="w",
        )
        self._status_lbl.pack(side="left", padx=16, pady=10)
        self._phase_lbl = ctk.CTkLabel(
            self._status_frame, text="-",
            font=ctk.CTkFont(family=_FONT_UI, size=13),
            text_color=("gray45", "gray55"), anchor="e",
        )
        self._phase_lbl.pack(side="right", padx=16, pady=10)

        # Overall progress
        self._prog_frame = ctk.CTkFrame(self._content, corner_radius=8)
        self._prog_frame.pack(fill="x", pady=(0, 8))
        self._prog_frame.columnconfigure(1, weight=1)
        ctk.CTkLabel(self._prog_frame, text="Overall", width=70, anchor="w").grid(
            row=0, column=0, padx=(16, 8), pady=10,
        )
        self._prog_bar = ctk.CTkProgressBar(self._prog_frame)
        self._prog_bar.set(0)
        self._prog_bar.grid(row=0, column=1, sticky="ew", padx=8, pady=10)
        self._prog_pct = ctk.CTkLabel(self._prog_frame, text="0%", width=42)
        self._prog_pct.grid(row=0, column=2, padx=(0, 16), pady=10)

        # Block progress (inserted dynamically after prog_frame during NF)
        self._block_frame = ctk.CTkFrame(self._content, corner_radius=8)
        self._block_frame.columnconfigure(1, weight=1)
        self._block_lbl = ctk.CTkLabel(
            self._block_frame, text="Block 1/4 - Rest", width=180, anchor="w",
        )
        self._block_lbl.grid(row=0, column=0, padx=(16, 8), pady=10)
        self._block_bar = ctk.CTkProgressBar(self._block_frame)
        self._block_bar.set(0)
        self._block_bar.grid(row=0, column=1, sticky="ew", padx=8, pady=10)
        self._block_pct = ctk.CTkLabel(self._block_frame, text="0%", width=42)
        self._block_pct.grid(row=0, column=2, padx=(0, 16), pady=10)
        self._block_visible = False

        # Log panel
        log_frame = ctk.CTkFrame(self._content, corner_radius=8)
        log_frame.pack(fill="both", expand=True, pady=(0, 8))
        
        lbl_font = ctk.CTkFont(family=_FONT_UI, size=13, weight="bold")
        ctk.CTkLabel(log_frame, text="Log", font=lbl_font, anchor="w").pack(
            anchor="w", padx=16, pady=(8, 0),
        )

        mono_font = ctk.CTkFont(family=_FONT_MONO, size=12)
        
        self._log_box = ctk.CTkTextbox(
            log_frame, font=mono_font,
            state="disabled", wrap="word",
        )
        self._log_box.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        # Action buttons
        self._btn_frame = ctk.CTkFrame(self._content, corner_radius=8)
        self._btn_frame.pack(fill="x")

        self._btn_start = ctk.CTkButton(
            self._btn_frame, text="Start Full Protocol",
            font=ctk.CTkFont(family=_FONT_UI, size=14, weight="bold"),
            fg_color="#2a7a2a", hover_color="#1e5c1e",
            width=200, height=40, command=self._on_start_full,
        )
        self._btn_start.pack(side="left", padx=(16, 8), pady=12)

        for text, cmd in [
            ("Baseline Only",   self._on_baseline_only),
            ("Analyse Only",    self._on_analyse_only),
            ("NF Session Only", self._on_nf_only),
        ]:
            ctk.CTkButton(
                self._btn_frame, text=text, width=130, height=40, command=cmd,
            ).pack(side="left", padx=(0, 8), pady=12)

        ctk.CTkButton(
            self._btn_frame, text="Participant Screen",
            width=150, height=40,
            command=self._on_launch_gui,
        ).pack(side="left", padx=(0, 8), pady=12)

        self._btn_abort = ctk.CTkButton(
            self._btn_frame, text="Abort",
            fg_color="#8b1010", hover_color="#6b0d0d",
            width=100, height=40, state="disabled",
            command=self._on_abort,
        )
        self._btn_abort.pack(side="right", padx=(0, 16), pady=12)

    # -----------------------------------------------------------------------
    # Sidebar helpers
    # -----------------------------------------------------------------------

    def _sec(self, title: str) -> None:
        """Add a section heading label and separator line to the sidebar.

        Args:
            title: Section title text (rendered in uppercase).
        """
        sec_font = ctk.CTkFont(family=_FONT_UI, size=12, weight="bold")
        ctk.CTkLabel(
            self._sidebar, text=title.upper(),
            font=sec_font,
            text_color=("gray45", "gray55"), anchor="w",
        ).pack(padx=16, pady=(14, 2), anchor="w")
        ctk.CTkFrame(
            self._sidebar, height=1, corner_radius=0,
            fg_color=("gray75", "gray35"),
        ).pack(fill="x", padx=16, pady=(0, 6))

    def _lbl(self, parent, text: str) -> ctk.CTkLabel:
        """Add a left-aligned label widget to *parent* and return it.

        Args:
            parent: The parent widget to pack the label into.
            text: Label text.

        Returns:
            ctk.CTkLabel: The created label widget.
        """
        lbl = ctk.CTkLabel(parent, text=text, anchor="w")
        lbl.pack(padx=16, pady=(0, 2), anchor="w")
        return lbl

    # -----------------------------------------------------------------------
    # Config → widget defaults
    # -----------------------------------------------------------------------

    def _apply_config_defaults(self) -> None:
        """Apply values from the loaded YAML config to the sidebar widgets."""
        cfg = self._cfg
        mapping = [
            ("baseline_duration", "_baseline_dur_var"),
            ("n_blocks",          "_nblocks_var"),
            ("rest_duration",     "_rest_dur_var"),
            ("nf_duration",       "_nf_dur_var"),
            ("osc_host",          "_osc_host_var"),
            ("osc_port",          "_osc_port_var"),
            ("warmup_windows",    "_warmup_var"),
        ]
        for cfg_key, attr in mapping:
            if cfg_key in cfg:
                getattr(self, attr).set(str(cfg[cfg_key]))
        if "zscore_threshold" in cfg:
            v = float(cfg["zscore_threshold"])
            self._zthr_var.set(v)
            self._zthr_val_lbl.configure(text=f"{v:.2f}")
        if "visual_preset" in cfg:
            if cfg["visual_preset"] in _RSPV_VISUALS:
                self._visual_var.set(cfg["visual_preset"])

    # -----------------------------------------------------------------------
    # UI event handlers
    # -----------------------------------------------------------------------

    def _on_mock_toggle(self) -> None:
        """Toggle the LSL connection rows between mock-file and real-stream mode."""
        if self._mock_var.get():
            self._lsl_real_rows.pack_forget()
            self._mockfile_row.pack(fill="x", pady=(0, 4))
        else:
            self._mockfile_row.pack_forget()
            self._lsl_real_rows.pack(fill="x", pady=(0, 4))

    def _on_protocol_change(self, value: str) -> None:
        """Show or hide the Threshold Value row based on the selected protocol.

        Args:
            value: The display label of the newly selected protocol.
        """
        is_threshold = _PROTO_INTERNAL[_PROTO_LABELS.index(value)] == "threshold"
        if is_threshold:
            self._thr_val_row.pack(fill="x", pady=(0, 4))
        else:
            self._thr_val_row.pack_forget()

    def _browse_mockfile(self) -> None:
        """Open a file chooser and update the mock LSL file path variable."""
        p = filedialog.askopenfilename()
        if p:
            self._mockfile_var.set(p)

    def _browse_subjects_dir(self) -> None:
        """Open a directory chooser and update the subjects directory variable."""
        p = filedialog.askdirectory()
        if p:
            self._subjects_dir_var.set(p)

    def _browse_audio_dir(self) -> None:
        """Open a directory chooser and update the audiometry directory variable."""
        p = filedialog.askdirectory()
        if p:
            self._audio_dir_var.set(p)

    def _browse_models_dir(self) -> None:
        """Open a directory chooser and update the normative models directory variable."""
        p = filedialog.askdirectory()
        if p:
            self._models_dir_var.set(p)

    # -----------------------------------------------------------------------
    # Input validation
    # -----------------------------------------------------------------------

    def _collect_params(self) -> tuple[dict, str | None]:
        """Read and validate all sidebar widget values.

        Returns:
            tuple: ``(params_dict, error_message)``.  On success,
            *params_dict* contains all validated session parameters and
            *error_message* is ``None``.  On validation failure,
            *params_dict* is ``{}`` and *error_message* is a human-readable
            description of the problem.
        """
        sid = self._id_var.get().strip().lower()
        if not sid.isalpha() or len(sid) != 4:
            return {}, "Subject ID must be exactly 4 letters."

        try:
            age = int(self._age_var.get().strip())
        except ValueError:
            return {}, "Please enter a valid age (integer)."

        try:
            visit = int(self._visit_var.get().strip())
        except ValueError:
            return {}, "Please enter a valid visit number (integer)."

        sex = "F" if self._sex_var.get() == "Female" else "M"
        subjects_dir = Path(self._subjects_dir_var.get().strip())

        try:
            n_blocks      = int(self._nblocks_var.get())
            rest_duration = float(self._rest_dur_var.get())
            nf_duration   = float(self._nf_dur_var.get())
            osc_port      = int(self._osc_port_var.get())
            baseline_dur  = float(self._baseline_dur_var.get())
            warmup        = int(self._warmup_var.get())
            zthr          = float(self._zthr_var.get())
            thr_val       = float(self._thr_val_var.get())
        except ValueError as exc:
            return {}, f"Invalid numeric input: {exc}"

        proto_idx = _PROTO_LABELS.index(self._proto_var.get())

        return {
            "subject_id":       sid,
            "age":              age,
            "sex":              sex,
            "visit":            visit,
            "subjects_dir":     subjects_dir,
            "audiometry_dir":   Path(self._audio_dir_var.get().strip() or "."),
            "models_dir":       Path(self._models_dir_var.get().strip() or "."),
            "mock_lsl":         self._mock_var.get(),
            "mock_fname":       self._mockfile_var.get().strip() or None,
            "stream_name":      self._stream_name_var.get().strip() or None,
            "stream_source_id": self._stream_source_id_var.get().strip() or None,
            "participant_lang": _PARTICIPANT_LANGS[self._participant_lang_var.get()],
            "protocol_name":    _PROTO_INTERNAL[proto_idx],
            "zscore_threshold": zthr,
            "warmup_windows":   warmup,
            "threshold_value":  thr_val,
            "baseline_duration":baseline_dur,
            "n_blocks":         n_blocks,
            "rest_duration":    rest_duration,
            "nf_duration":      nf_duration,
            "osc_host":         self._osc_host_var.get().strip(),
            "osc_port":         osc_port,
            "visual_preset":    self._visual_var.get(),
            "trigger_enabled":  self._trigger_var.get(),
            "trigger_mode":     self._trigger_mode_var.get(),
            "trigger_port":     self._trigger_port_var.get().strip(),
            "trigger_address":  self._trigger_addr_var.get().strip(),
        }, None

    # -----------------------------------------------------------------------
    # UI state helpers
    # -----------------------------------------------------------------------

    def _set_running(self, running: bool) -> None:
        """Enable or disable action buttons and the Abort button.

        Args:
            running: If ``True``, all action buttons are disabled and the
                Abort button is enabled.  If ``False``, the reverse.
        """
        state = "disabled" if running else "normal"
        for w in self._btn_frame.winfo_children():
            if isinstance(w, ctk.CTkButton) and w is not self._btn_abort:
                w.configure(state=state)
        self._btn_abort.configure(state="normal" if running else "disabled")

    def _set_progress(self, value: float) -> None:
        """Update the overall progress bar and percentage label (thread-safe).

        Args:
            value: Progress fraction in [0.0, 1.0].
        """
        self.after(0, lambda: self._prog_bar.set(value))
        self.after(0, lambda: self._prog_pct.configure(text=f"{int(value * 100)}%"))

    def _set_status(self, text: str) -> None:
        """Update the status label text (thread-safe).

        Args:
            text: New status string to display.
        """
        self.after(0, lambda: self._status_lbl.configure(text=text))

    def _set_phase(self, text: str) -> None:
        """Update the right-aligned phase label text (thread-safe).

        Args:
            text: Phase label text (e.g. ``"Baseline"``, ``"Analysis"``).
        """
        self.after(0, lambda: self._phase_lbl.configure(text=text))

    def _append_log(self, msg: str) -> None:
        """Append a timestamped message to the operator log text box (thread-safe).

        Args:
            msg: Log message string.  A ``[HH:MM:SS]`` timestamp is prepended
                automatically.
        """
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        def _write():
            self._log_box.configure(state="normal")
            self._log_box.insert("end", line)
            self._log_box.see("end")
            self._log_box.configure(state="disabled")
        self.after(0, _write)

    def _show_block_bar(self, show: bool) -> None:
        """Show or hide the per-block progress bar below the overall bar (thread-safe).

        Args:
            show: If ``True``, insert the block bar frame below the overall
                progress frame.  If ``False``, remove it.
        """
        def _do():
            if show and not self._block_visible:
                self._block_frame.pack(fill="x", pady=(0, 8), after=self._prog_frame)
                self._block_visible = True
            elif not show and self._block_visible:
                self._block_frame.pack_forget()
                self._block_visible = False
        self.after(0, _do)

    def _update_block(self, block_idx: int, phase: str) -> None:
        """Update the per-block progress bar and label on a block transition.

        Called by ``BlockScheduler.on_block_change`` from the session thread.
        Also writes the current phase and block to the participant GUI state
        file so the participant screen can update its display.

        Args:
            block_idx: Zero-based block index.
            phase: ``"rest"`` or ``"nf"``.
        """
        n = self._n_blocks_total or 1
        frac = (block_idx + (0.5 if phase == "nf" else 0.0)) / n
        phase_text = "Rest - please relax" if phase == "rest" else "Neurofeedback - focus"
        label = f"Block {block_idx + 1}/{n} - {phase_text}"
        def _do():
            self._block_lbl.configure(text=label)
            self._block_bar.set(frac)
            self._block_pct.configure(text=f"{int(frac * 100)}%")
        self.after(0, _do)
        self._append_log(label)
        # Propagate to participant screen
        self._write_gui_state(phase=phase, block=block_idx, n_blocks=n)

    def _finish(self, success: bool = True) -> None:
        """Finalise the session: update status, re-enable buttons, stop subprocesses.

        Args:
            success: If ``True``, sets the status to ``"Session complete."``;
                otherwise to ``"Error - see log."``.
        """
        text = "Session complete." if success else "Error - see log."
        self.after(0, lambda: self._set_status(text))
        self.after(0, lambda: self._set_phase("-"))
        self.after(0, lambda: self._set_running(False))
        self._show_block_bar(False)
        self._stop_rspv()
        self._stop_participant_gui()

    def _make_trigger(self, p: dict):
        """Create a trigger object from params, or return None if disabled."""
        if not p.get("trigger_enabled"):
            return None
        mode = p.get("trigger_mode", "serial")
        if mode == "serial":
            port = p.get("trigger_port", "COM4")
            trig = make_trigger(True, serial_port=port, mode="serial")
            if trig.available:
                self._append_log(f"Serial trigger ready on {port}.")
            else:
                self._append_log(f"WARNING: Serial trigger unavailable on {port} - check TriggerBox USB connection.")
        else:
            try:
                addr = int(p.get("trigger_address", "0x3FF0"), 16)
            except (ValueError, TypeError):
                self._append_log("WARNING: Invalid LPT trigger address - triggers disabled.")
                return None
            trig = make_trigger(True, port_address=addr, mode="lpt")
            if trig.available:
                self._append_log(f"LPT trigger ready at 0x{addr:04X}.")
            else:
                self._append_log(f"WARNING: LPT trigger unavailable at 0x{addr:04X} - check driver.")
        return trig

    # -----------------------------------------------------------------------
    # rspv subprocess management
    # -----------------------------------------------------------------------

    def _launch_rspv(self, p: dict) -> None:
        """Write a runtime config and launch rspv in a subprocess."""
        if not _RSPV_MAIN.exists():
            self._append_log("rspv not found - participant visual not launched.")
            return

        if not _RSPV_CFG.exists():
            self._append_log("rspv/config.json not found - skipping visual launch.")
            return

        with open(_RSPV_CFG) as fh:
            rspv_cfg = json.load(fh)

        # Override visual, language, and OSC source pointing at ANT's OSC port
        rspv_cfg["visual_preset"] = p["visual_preset"]
        rspv_cfg["lang"] = p["participant_lang"]
        rspv_cfg["signal_source"] = {
            "osc": {
                "osc_ip":      p["osc_host"],
                "osc_port":    p["osc_port"],
                "osc_address": "/rspv",
            }
        }

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="antares_rspv_",
        )
        json.dump(rspv_cfg, tmp)
        tmp.close()

        # Use rspv's own venv if present, else fall back to our venv
        rspv_python = _HERE / "rspv" / "venv" / "bin" / "python"
        if not rspv_python.exists():
            rspv_python = Path(sys.executable)

        try:
            self._rspv_proc = subprocess.Popen(
                [str(rspv_python), str(_RSPV_MAIN), tmp.name],
                cwd=str(_RSPV_MAIN.parent),
            )
            self._append_log(
                f"rspv launched (PID {self._rspv_proc.pid}) "
                f"- visual: {p['visual_preset']}"
            )
        except Exception as exc:
            self._append_log(f"Failed to launch rspv: {exc}")

    def _stop_rspv(self) -> None:
        """Terminate the rspv participant-visual subprocess if it is running."""
        if self._rspv_proc and self._rspv_proc.poll() is None:
            self._rspv_proc.terminate()
            self._append_log(f"rspv (PID {self._rspv_proc.pid}) terminated.")
            self._rspv_proc = None

    # -----------------------------------------------------------------------
    # Participant GUI management
    # -----------------------------------------------------------------------

    def _write_gui_state(self, **kwargs) -> None:
        """Write /tmp/antares_session_state.json so the participant screen updates."""
        try:
            current: dict = {}
            if _GUI_STATE.exists():
                with open(_GUI_STATE) as fh:
                    current = json.load(fh)
            current.update(kwargs)
            with open(_GUI_STATE, "w") as fh:
                json.dump(current, fh)
        except Exception as exc:
            self._append_log(f"[gui_state] Write failed: {exc}")

    def _launch_participant_gui(self, lang: str = "en") -> None:
        """Launch antares_gui.py on the participant screen (display 2)."""
        if not _GUI_SCRIPT.exists():
            self._append_log("antares_gui.py not found - participant screen not launched.")
            return
        if self._gui_proc and self._gui_proc.poll() is None:
            self._append_log("Participant screen already running.")
            return

        self._write_gui_state(phase="welcome", lang=lang, block=0, n_blocks=4)

        try:
            self._gui_proc = subprocess.Popen(
                [sys.executable, str(_GUI_SCRIPT), "--lang", lang],
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
            self._append_log(
                f"Participant screen launched (PID {self._gui_proc.pid}, lang={lang})"
            )
            threading.Thread(target=self._pipe_gui_log, daemon=True).start()
        except Exception as exc:
            self._append_log(f"Failed to launch participant screen: {exc}")

    def _stop_participant_gui(self) -> None:
        """Terminate the antares_gui.py participant screen subprocess if running."""
        if self._gui_proc and self._gui_proc.poll() is None:
            self._gui_proc.terminate()
            self._append_log(f"Participant screen (PID {self._gui_proc.pid}) terminated.")
            self._gui_proc = None

    def _pipe_gui_log(self) -> None:
        """Forward participant screen stderr to the operator log.

        Runs in a daemon thread.  Reads stderr line-by-line from the
        ``antares_gui.py`` subprocess and prepends ``[participant]`` to each
        line before appending it to the operator log box.  Exits silently when
        the subprocess closes.
        """
        try:
            for raw in self._gui_proc.stderr:
                line = raw.decode(errors="replace").rstrip()
                if line:
                    self._append_log(f"[participant] {line}")
        except Exception:
            pass

    def _wait_for_participant(self, timeout: float = 600.0) -> bool:
        """Block until participant presses Space on the welcome screen (or abort/timeout).

        Returns True when the flag file appears, False on abort or timeout.
        """
        _READY_FILE.unlink(missing_ok=True)   # clear any stale flag from a previous run
        self._set_status("Waiting for participant to press Space ...")
        self._set_phase("Participant ready?")
        self._append_log("Waiting for participant to confirm on their screen (Space bar).")

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._stop_event.is_set():
                return False
            if _READY_FILE.exists():
                _READY_FILE.unlink(missing_ok=True)
                self._append_log("Participant confirmed - starting session.")
                return True
            time.sleep(0.2)

        self._append_log("Timeout: participant did not confirm within the allowed time.")
        return False

    def _wait_for_rspv_ready(self, timeout: float = 600.0) -> bool:
        """Block until participant presses Space on the rspv instruction page.

        rspv writes _RSPV_READY_FILE when Space is pressed.  We poll for it
        here so the block scheduler never fires before the instruction page
        has been acknowledged.

        Returns True when the flag appears, False on abort or timeout.
        """
        _RSPV_READY_FILE.unlink(missing_ok=True)
        self._set_status("Waiting for participant to confirm on rspv screen ...")
        self._append_log("Waiting for participant to press Space on the instruction page.")

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._stop_event.is_set():
                return False
            if _RSPV_READY_FILE.exists():
                _RSPV_READY_FILE.unlink(missing_ok=True)
                self._append_log("Participant confirmed on rspv screen - starting block scheduler.")
                return True
            time.sleep(0.2)

        self._append_log("Timeout: rspv instruction page was not confirmed within the allowed time.")
        return False

    # -----------------------------------------------------------------------
    # Button handlers
    # -----------------------------------------------------------------------

    def _on_launch_gui(self) -> None:
        """Launch the participant screen at the language set in the sidebar."""
        params, err = self._collect_params()
        lang = params.get("participant_lang", "en") if not err else "en"
        self._launch_participant_gui(lang)

    def _on_abort(self) -> None:
        """Signal all running pipeline threads to stop and terminate subprocesses."""
        self._stop_event.set()
        self._stop_rspv()
        self._write_gui_state(phase="waiting")
        self._append_log("Abort requested ...")

    def _on_start_full(self) -> None:
        """Validate inputs and start the full protocol thread (intake + baseline + analysis + NF)."""
        params, err = self._collect_params()
        if err:
            messagebox.showerror("Validation Error", err)
            return
        self._stop_event.clear()
        self._set_running(True)
        threading.Thread(target=self._thread_full, args=(params,), daemon=True).start()

    def _on_baseline_only(self) -> None:
        """Validate inputs and start the baseline-only recording thread."""
        params, err = self._collect_params()
        if err:
            messagebox.showerror("Validation Error", err)
            return
        self._stop_event.clear()
        self._set_running(True)
        threading.Thread(target=self._thread_baseline_only, args=(params,), daemon=True).start()

    def _on_analyse_only(self) -> None:
        """Validate inputs and start the analysis-only thread (uses existing baseline .fif)."""
        params, err = self._collect_params()
        if err:
            messagebox.showerror("Validation Error", err)
            return
        self._stop_event.clear()
        self._set_running(True)
        threading.Thread(target=self._thread_analyse_only, args=(params,), daemon=True).start()

    def _on_nf_only(self) -> None:
        """Validate inputs and start the NF-session-only thread (skips intake and baseline)."""
        params, err = self._collect_params()
        if err:
            messagebox.showerror("Validation Error", err)
            return
        self._stop_event.clear()
        self._set_running(True)
        threading.Thread(target=self._thread_nf_only, args=(params,), daemon=True).start()

    # -----------------------------------------------------------------------
    # Pipeline threads
    # -----------------------------------------------------------------------

    def _thread_full(self, p: dict) -> None:
        """Run the full session pipeline in a background thread.

        Sequence: launch rspv -> wait for participant Space -> intake ->
        baseline recording -> analysis / adaptive selection -> show NF
        instructions -> wait for rspv ready -> NF session -> save -> finish.
        Any exception is caught, logged, and reported via ``_finish(False)``.

        Args:
            p: Validated parameter dict from ``_collect_params()``.
        """
        visit = p["visit"]
        try:
            # rspv is the participant's single window throughout.
            # It starts on the welcome screen; participant presses Space to proceed.
            self._launch_rspv(p)

            # Wait for participant Space on the welcome screen.
            if not self._wait_for_participant():
                self._finish(False); return

            # -- Intake -------------------------------------------------------
            # rspv is now showing the waiting screen.
            # In mock mode, add a delay so the waiting screen is visible.
            self._set_status("Collecting subject information ...")
            self._set_phase("Intake")
            self._append_log("Starting subject intake ...")
            get_user_info(p["subject_id"], p["age"], p["sex"], visit, p["subjects_dir"])
            compute_pta(p["subject_id"], p["subjects_dir"], p["audiometry_dir"])
            self._set_progress(0.05)
            if self._stop_event.is_set():
                self._finish(False); return

            # -- Baseline recording -------------------------------------------
            # rspv stays on the waiting screen until LSL connects; the
            # on_connected callback fires inside run_baseline() right after
            # connect_to_lsl() succeeds, writing _RSPV_BASELINE_FLAG so rspv
            # transitions to the fixation cross just as recording starts.
            baseline_dur = self._session_mgr.get_baseline_duration(
                visit, p["baseline_duration"]
            )
            self._set_status(
                f"Recording {'full' if visit == 1 else 'quick'} baseline "
                f"({int(baseline_dur)}s) ..."
            )
            self._set_phase("Baseline")

            def _on_lsl_connected():
                try:
                    _RSPV_BASELINE_FLAG.touch()
                except OSError:
                    pass

            _trigger = self._make_trigger(p)
            run_baseline(
                subject_id=p["subject_id"], visit=visit,
                subjects_dir=p["subjects_dir"],
                baseline_duration=baseline_dur,
                mock_lsl=p["mock_lsl"], mock_fname=p["mock_fname"],
                stream_name=p["stream_name"], stream_source_id=p["stream_source_id"],
                on_connected=_on_lsl_connected,
                log_callback=self._append_log,
                trigger=_trigger,
            )
            self._set_progress(0.30)
            if self._stop_event.is_set():
                self._finish(False); return

            # -- Analysis / adaptive selection --------------------------------
            self._set_phase("Analysis")
            if visit == 1:
                self._set_status("Analysing EEG & selecting NF target ...")
                run_full_analysis(
                    subject_id=p["subject_id"], age=p["age"], sex=p["sex"],
                    visit=visit, subjects_dir=p["subjects_dir"],
                    models_dir=p["models_dir"],
                    site=self._cfg.get("site", "zuerich"),
                    log_callback=self._append_log,
                )
            else:
                self._set_status(
                    "Adaptive selection: checking feature quality ..."
                    if visit < 5 else
                    "Mid-protocol evaluation: re-ranking features ..."
                )
                report = self._session_mgr.prepare_session(
                    subject_id=p["subject_id"],
                    visit=visit,
                    subjects_dir=p["subjects_dir"],
                    models_dir=p["models_dir"],
                    age=p["age"], sex=p["sex"],
                    site=self._cfg.get("site", "zuerich"),
                    log_callback=self._append_log,
                )
                decision = report.get("session_decision", {})
                self._append_log(
                    f"[SessionManager] Decision: {decision.get('decision','?')} - "
                    f"{decision.get('reason','')}"
                )

            self._set_progress(0.65)
            if self._stop_event.is_set():
                self._finish(False); return

            # Analysis done — tell rspv to switch from fixation cross to instruction page.
            self._set_status("Showing NF instructions to participant ...")
            try:
                _RSPV_INSTRUCTION_FLAG.touch()
            except OSError:
                pass

            # Wait for participant to press Space on the instruction page.
            self._set_phase("NF Session")
            self._n_blocks_total = p["n_blocks"]
            self._show_block_bar(True)
            if not self._wait_for_rspv_ready():
                self._finish(False); return

            run_nf_session(
                subject_id=p["subject_id"], visit=visit,
                subjects_dir=p["subjects_dir"],
                template_yaml_path=_CONFIG_FILE,
                protocol_name=p["protocol_name"],
                zscore_threshold=p["zscore_threshold"],
                warmup_windows=p["warmup_windows"],
                threshold_value=p["threshold_value"],
                n_blocks=p["n_blocks"],
                rest_duration=p["rest_duration"],
                nf_duration=p["nf_duration"],
                osc_host=p["osc_host"], osc_port=p["osc_port"],
                mock_lsl=p["mock_lsl"], mock_fname=p["mock_fname"],
                stream_name=p["stream_name"], stream_source_id=p["stream_source_id"],
                on_block_change=self._update_block,
                log_callback=self._append_log,
                trigger=_trigger,
            )
            if _trigger:
                _trigger.close()
            self._set_progress(1.0)
            # Show thank-you screen on rspv for 5 s, then clean up.
            try:
                _RSPV_THANKYOU_FLAG.touch()
            except OSError:
                pass
            time.sleep(5.0)
            self._finish(True)

        except Exception as exc:
            self._append_log(f"ERROR: {exc}")
            for line in traceback.format_exc().splitlines():
                self._append_log(f"  {line}")
            self._finish(False)

    def _thread_baseline_only(self, p: dict) -> None:
        """Run only the baseline recording in a background thread.

        Args:
            p: Validated parameter dict from ``_collect_params()``.
        """
        try:
            self._set_status("Recording resting-state baseline ...")
            self._set_phase("Baseline")
            self._set_progress(0.0)
            _trigger = self._make_trigger(p)
            run_baseline(
                subject_id=p["subject_id"], visit=p["visit"],
                subjects_dir=p["subjects_dir"],
                baseline_duration=p["baseline_duration"],
                mock_lsl=p["mock_lsl"], mock_fname=p["mock_fname"],
                stream_name=p["stream_name"], stream_source_id=p["stream_source_id"],
                log_callback=self._append_log,
                trigger=_trigger,
            )
            if _trigger:
                _trigger.close()
            self._set_progress(1.0)
            self._finish(True)
        except Exception as exc:
            self._append_log(f"ERROR: {exc}")
            for line in traceback.format_exc().splitlines():
                self._append_log(f"  {line}")
            self._finish(False)

    def _thread_analyse_only(self, p: dict) -> None:
        """Run only the offline analysis pipeline in a background thread.

        Requires that a baseline .fif file already exists for the given visit.

        Args:
            p: Validated parameter dict from ``_collect_params()``.
        """
        try:
            self._set_status("Analysing EEG & selecting NF target ...")
            self._set_phase("Analysis")
            self._set_progress(0.0)
            run_full_analysis(
                subject_id=p["subject_id"], age=p["age"], sex=p["sex"],
                visit=p["visit"], subjects_dir=p["subjects_dir"],
                models_dir=p["models_dir"], log_callback=self._append_log,
            )
            self._set_progress(1.0)
            self._finish(True)
        except Exception as exc:
            self._append_log(f"ERROR: {exc}")
            for line in traceback.format_exc().splitlines():
                self._append_log(f"  {line}")
            self._finish(False)

    def _thread_nf_only(self, p: dict) -> None:
        """Run only the NF session in a background thread (skips intake and baseline).

        Launches rspv, waits for participant confirmation, then runs
        ``run_nf_session`` directly using the selection report from a previous
        analysis run.

        Args:
            p: Validated parameter dict from ``_collect_params()``.
        """
        try:
            self._set_status("Running neurofeedback session ...")
            self._set_phase("NF Session")
            self._set_progress(0.0)
            self._n_blocks_total = p["n_blocks"]
            self._show_block_bar(True)
            self._launch_rspv(p)

            # Wait for participant Space on the welcome screen.
            if not self._wait_for_participant():
                self._finish(False); return

            # rspv is now on the waiting screen.
            if p.get("mock_lsl"):
                time.sleep(5.0)

            # No baseline in this flow — go straight to instruction page.
            try:
                _RSPV_INSTRUCTION_FLAG.touch()
            except OSError:
                pass

            # Wait for participant Space on the instruction page.
            if not self._wait_for_rspv_ready():
                self._finish(False); return

            _trigger = self._make_trigger(p)
            run_nf_session(
                subject_id=p["subject_id"], visit=p["visit"],
                subjects_dir=p["subjects_dir"],
                template_yaml_path=_CONFIG_FILE,
                protocol_name=p["protocol_name"],
                zscore_threshold=p["zscore_threshold"],
                warmup_windows=p["warmup_windows"],
                threshold_value=p["threshold_value"],
                n_blocks=p["n_blocks"],
                rest_duration=p["rest_duration"],
                nf_duration=p["nf_duration"],
                osc_host=p["osc_host"], osc_port=p["osc_port"],
                mock_lsl=p["mock_lsl"], mock_fname=p["mock_fname"],
                stream_name=p["stream_name"], stream_source_id=p["stream_source_id"],
                on_block_change=self._update_block,
                log_callback=self._append_log,
                trigger=_trigger,
            )
            if _trigger:
                _trigger.close()
            self._set_progress(1.0)
            # Show thank-you screen on rspv for 5 s, then clean up.
            try:
                _RSPV_THANKYOU_FLAG.touch()
            except OSError:
                pass
            time.sleep(5.0)
            self._finish(True)
        except Exception as exc:
            self._append_log(f"ERROR: {exc}")
            for line in traceback.format_exc().splitlines():
                self._append_log(f"  {line}")
            self._finish(False)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Application entry point.

    Configures customtkinter scaling for WSLg, creates the ``AntaresApp``
    window, applies Tk DPI scaling based on the actual screen resolution, and
    enters the Tk main loop.
    """
    # WSLg has no HiDPI support and reports 96 DPI regardless of monitor.
    # Bumping widget scaling makes fonts larger and more readable.
    if "microsoft" in platform.uname().release.lower():
        ctk.set_widget_scaling(1.25)
    app = AntaresApp()
    # Apply Tk DPI scaling based on the actual screen resolution reported
    # by the display server (improves font sharpness on high-DPI monitors).
    try:
        dpi = app.winfo_fpixels("1i")
        if dpi and dpi > 96:
            app.tk.call("tk", "scaling", dpi / 72.0)
    except Exception:
        pass
    app.mainloop()


if __name__ == "__main__":
    main()
