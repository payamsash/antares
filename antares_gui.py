"""ANTARES participant screen — full-screen py5 display.

Driven entirely by /tmp/antares_session_state.json, which the operator
application (antares_app.py) updates at each phase transition.
The participant screen reads this file on every frame (only on mtime change)
and updates its visuals accordingly.

Launch:
    python antares_gui.py [--lang en|de]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import py5

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent))
from i18n import t

# ---------------------------------------------------------------------------
# State file
# ---------------------------------------------------------------------------

_STATE_FILE = Path("/tmp/antares_session_state.json")
_READY_FILE = Path("/tmp/antares_participant_ready.flag")

# Shared mutable state (module-level globals, set in setup/draw)
_state: dict = {"phase": "waiting", "block": 0, "n_blocks": 4, "lang": "en"}
_last_mtime: float = 0.0

# ---------------------------------------------------------------------------
# Animation state
# ---------------------------------------------------------------------------

_tick: float = 0.0          # global frame counter for animations
_fade: float = 0.0          # 0–1 cross-fade for phase transitions
_prev_phase: str = ""

# ---------------------------------------------------------------------------
# Design constants
# ---------------------------------------------------------------------------

_C_BG      = (10,  10,  12)        # near-black background
_C_WHITE   = (245, 245, 248)       # primary text
_C_DIM     = (120, 120, 130)       # secondary text / labels
_C_ACCENT  = (70,  140, 220)       # blue accent
_C_ACCENT2 = (100, 200, 160)       # green accent (NF active)
_C_DOT_ON  = (80,  150, 230)       # completed block dot
_C_DOT_CUR = (200, 220, 255)       # current block dot
_C_DOT_OFF = (35,  35,  40)        # future block dot


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def setup() -> None:
    global _state

    py5.full_screen(2)   # JAVA2D (default) — P2D/OpenGL is unreliable in WSLg
    py5.smooth(8)
    py5.no_cursor()
    py5.frame_rate(30)
    py5.color_mode(py5.RGB, 255)

    args = sys.argv[1:]
    lang = "en"
    if "--lang" in args:
        idx = args.index("--lang")
        lang = args[idx + 1] if idx + 1 < len(args) else "en"
    _state["lang"] = lang

    _poll_state()


# ---------------------------------------------------------------------------
# Main draw loop
# ---------------------------------------------------------------------------

def draw() -> None:
    global _tick, _fade, _prev_phase

    _poll_state()
    _tick += 0.04

    phase = _state.get("phase", "waiting")
    lang  = _state.get("lang",  "en")

    # Cross-fade on phase change
    if phase != _prev_phase:
        _fade = 0.0
        _prev_phase = phase
    _fade = min(_fade + 0.06, 1.0)

    # Background
    py5.background(*_C_BG)

    # Draw current phase
    if phase == "welcome":
        _draw_welcome(lang)
    elif phase == "waiting":
        _draw_waiting(lang)
    elif phase == "baseline":
        _draw_baseline()
    elif phase == "nf_ready":
        _draw_nf_ready(lang)
    elif phase == "rest":
        _draw_rest(lang)
    elif phase == "nf":
        _draw_nf_active(lang)
    elif phase == "end":
        _draw_end(lang)
    else:
        _draw_waiting(lang)

    # Fade-in overlay on transition
    if _fade < 1.0:
        alpha = int((1.0 - _fade) * 255)
        py5.no_stroke()
        py5.fill(*_C_BG, alpha)
        py5.rect(0, 0, py5.width, py5.height)


# ---------------------------------------------------------------------------
# Phase renderers
# ---------------------------------------------------------------------------

def _draw_welcome(lang: str) -> None:
    W, H = py5.width, py5.height

    # Soft pulsing background ring — calm, welcoming
    for i in range(4):
        offset = i * 0.6
        r = 160 + 20 * py5.sin(_tick * 0.6 + offset)
        alpha = int(18 + 10 * py5.sin(_tick * 0.6 + offset))
        py5.no_fill()
        py5.stroke(*_C_ACCENT2, alpha)
        py5.stroke_weight(1.0)
        py5.ellipse(W / 2, H / 2, r * 2, r * 2)

    py5.no_stroke()

    # Top accent bar (green instead of blue for a warm feel)
    py5.stroke(*_C_ACCENT2, 160)
    py5.stroke_weight(3)
    py5.line(W * 0.15, H * 0.06, W * 0.85, H * 0.06)
    py5.no_stroke()

    # "Welcome to ANTARES" heading
    py5.fill(*_C_ACCENT2)
    py5.text_align(py5.CENTER, py5.CENTER)
    py5.text_font(py5.create_font("DejaVu Sans Bold", 32))
    py5.text(t("welcome_title", lang), W / 2, H * 0.24)

    # ANTARES logo — very large centrepiece
    py5.fill(*_C_WHITE)
    py5.text_font(py5.create_font("DejaVu Sans Bold", 72))
    py5.text("ANTARES", W / 2, H * 0.38)

    # Subtitle
    py5.fill(*_C_DIM)
    py5.text_font(py5.create_font("DejaVu Sans", 20))
    py5.text(t("welcome_subtitle", lang), W / 2, H * 0.50)

    _divider(W, H, 0.57)

    # Greeting body
    py5.fill(*_C_DIM)
    py5.text_font(py5.create_font("DejaVu Sans", 18))
    py5.text_leading(34)
    py5.text(t("welcome_session_msg", lang), W / 2, H * 0.70)

    # "Press SPACE" prompt — pulsing alpha so it gently calls for attention
    alpha_hint = int(140 + 100 * (0.5 + 0.5 * py5.sin(_tick * 1.2)))
    py5.fill(*_C_DIM, alpha_hint)
    py5.text_font(py5.create_font("DejaVu Sans", 18))
    py5.text(t("press_space", lang), W / 2, H * 0.87)


def _draw_waiting(lang: str) -> None:
    W, H = py5.width, py5.height

    # Top accent bar
    _accent_bar(W, H)

    # Logo / title
    py5.fill(*_C_WHITE)
    py5.text_align(py5.CENTER, py5.CENTER)
    py5.text_font(py5.create_font("DejaVu Sans Bold", 52))
    py5.text("ANTARES", W / 2, H * 0.28)

    # Subtitle
    py5.fill(*_C_ACCENT)
    py5.text_font(py5.create_font("DejaVu Sans", 20))
    py5.text(t("welcome_subtitle", lang), W / 2, H * 0.37)

    # Divider
    _divider(W, H, 0.44)

    # Waiting body
    py5.fill(*_C_DIM)
    py5.text_font(py5.create_font("DejaVu Sans", 18))
    py5.text_leading(32)
    py5.text(t("waiting_body", lang), W / 2, H * 0.57)

    # Animated breathing dots
    _breathing_dots(W, H, 0.77)


def _draw_baseline() -> None:
    W, H = py5.width, py5.height

    # Subtle pulsing ring around fixation
    r = 28 + 6 * py5.sin(_tick * 1.2)
    py5.no_fill()
    py5.stroke(*_C_ACCENT, 60)
    py5.stroke_weight(1.5)
    py5.ellipse(W / 2, H / 2, r * 2, r * 2)
    py5.no_stroke()

    # Fixation cross
    arm = 32
    py5.stroke(*_C_WHITE, 220)
    py5.stroke_weight(2.5)
    py5.line(W / 2 - arm, H / 2, W / 2 + arm, H / 2)
    py5.line(W / 2, H / 2 - arm, W / 2, H / 2 + arm)
    py5.no_stroke()


def _draw_nf_ready(lang: str) -> None:
    W, H = py5.width, py5.height

    _accent_bar(W, H)

    # Title
    py5.fill(*_C_WHITE)
    py5.text_align(py5.CENTER, py5.CENTER)
    py5.text_font(py5.create_font("DejaVu Sans Bold", 38))
    py5.text(t("nf_instructions_title", lang), W / 2, H * 0.22)

    _divider(W, H, 0.30)

    # Instructions body
    py5.fill(*_C_DIM)
    py5.text_font(py5.create_font("DejaVu Sans", 19))
    py5.text_leading(36)
    py5.text(t("nf_instructions_body", lang), W / 2, H * 0.54)

    # "Session starts shortly" hint
    alpha = int(160 + 80 * py5.sin(_tick * 1.3))
    py5.fill(*_C_DIM, alpha)
    py5.text_font(py5.create_font("DejaVu Sans", 16))
    py5.text(t("waiting_body", lang), W / 2, H * 0.84)


def _draw_rest(lang: str) -> None:
    W, H = py5.width, py5.height

    block    = _state.get("block",    0)
    n_blocks = _state.get("n_blocks", 4)

    # Slow pulsing concentric rings (calm, breathing-like)
    for i in range(3):
        offset = i * 0.8
        r = 90 + 18 * py5.sin(_tick * 0.7 + offset)
        alpha = int(40 + 20 * py5.sin(_tick * 0.7 + offset))
        py5.no_fill()
        py5.stroke(*_C_ACCENT, alpha)
        py5.stroke_weight(1.2)
        py5.ellipse(W / 2, H / 2, r * 2, r * 2)

    # Soft centre dot
    dot_alpha = int(80 + 40 * py5.sin(_tick * 0.9))
    py5.no_stroke()
    py5.fill(*_C_ACCENT, dot_alpha)
    py5.ellipse(W / 2, H / 2, 10, 10)

    # Rest label
    py5.fill(*_C_DIM)
    py5.text_align(py5.CENTER, py5.CENTER)
    py5.text_font(py5.create_font("DejaVu Sans", 16))
    py5.text(t("block_rest", lang), W / 2, H * 0.80)

    # Block progress dots
    _block_dots(W, H, block, n_blocks, 0.90)


def _draw_nf_active(lang: str) -> None:
    """Blank screen during NF — rspv window handles the visual feedback."""
    W, H = py5.width, py5.height

    block    = _state.get("block",    0)
    n_blocks = _state.get("n_blocks", 4)

    # Tiny block-progress dots only — otherwise fully black
    _block_dots(W, H, block, n_blocks, 0.97)


def _draw_end(lang: str) -> None:
    W, H = py5.width, py5.height

    _accent_bar(W, H)

    # Checkmark-like decoration
    py5.stroke(*_C_ACCENT2, 180)
    py5.stroke_weight(2.5)
    py5.no_fill()
    py5.ellipse(W / 2, H * 0.33, 70, 70)
    # Simple ✓ — two lines
    py5.line(W / 2 - 14, H * 0.33, W / 2 - 3, H * 0.33 + 14)
    py5.line(W / 2 - 3,  H * 0.33 + 14, W / 2 + 18, H * 0.33 - 12)
    py5.no_stroke()

    # Title
    py5.fill(*_C_WHITE)
    py5.text_align(py5.CENTER, py5.CENTER)
    py5.text_font(py5.create_font("DejaVu Sans Bold", 42))
    py5.text(t("end_title", lang), W / 2, H * 0.53)

    # Subtitle
    py5.fill(*_C_ACCENT)
    py5.text_font(py5.create_font("DejaVu Sans", 22))
    py5.text(t("end_subtitle", lang), W / 2, H * 0.64)


# ---------------------------------------------------------------------------
# Shared drawing helpers
# ---------------------------------------------------------------------------

def _accent_bar(W: int, H: int) -> None:
    """Thin coloured line at the top of the screen."""
    py5.stroke(*_C_ACCENT, 160)
    py5.stroke_weight(3)
    py5.line(W * 0.15, H * 0.06, W * 0.85, H * 0.06)
    py5.no_stroke()


def _divider(W: int, H: int, y_frac: float) -> None:
    py5.stroke(*_C_DIM, 60)
    py5.stroke_weight(1)
    py5.line(W * 0.30, H * y_frac, W * 0.70, H * y_frac)
    py5.no_stroke()


def _breathing_dots(W: int, H: int, y_frac: float) -> None:
    """Three dots that pulse out of phase — 'session loading' cue."""
    n = 3
    spacing = 18
    total = (n - 1) * spacing
    for i in range(n):
        phase_offset = i * 1.1
        alpha = int(80 + 100 * (0.5 + 0.5 * py5.sin(_tick * 1.4 + phase_offset)))
        r = 4 + 2 * py5.sin(_tick * 1.4 + phase_offset)
        py5.no_stroke()
        py5.fill(*_C_ACCENT, alpha)
        x = W / 2 - total / 2 + i * spacing
        py5.ellipse(x, H * y_frac, r, r)


def _block_dots(W: int, H: int, block: int, n_blocks: int, y_frac: float) -> None:
    """Row of dots showing completed / current / future blocks."""
    spacing = 20
    total = max(1, n_blocks - 1) * spacing
    for i in range(n_blocks):
        x = W / 2 - total / 2 + i * spacing
        y = H * y_frac
        py5.no_stroke()
        if i < block:
            py5.fill(*_C_DOT_ON)
            py5.ellipse(x, y, 9, 9)
        elif i == block:
            # Slightly larger pulsing dot for current block
            r = 6 + 2 * py5.sin(_tick * 2.0)
            py5.fill(*_C_DOT_CUR)
            py5.ellipse(x, y, r, r)
        else:
            py5.fill(*_C_DOT_OFF)
            py5.ellipse(x, y, 7, 7)


# ---------------------------------------------------------------------------
# State polling (reads file only when mtime changes)
# ---------------------------------------------------------------------------

def _poll_state() -> None:
    global _state, _last_mtime
    if not _STATE_FILE.exists():
        return
    try:
        mtime = _STATE_FILE.stat().st_mtime
        if mtime > _last_mtime:
            with open(_STATE_FILE) as fh:
                new = json.load(fh)
            _state.update(new)
            _last_mtime = mtime
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Key handler
# ---------------------------------------------------------------------------

def key_pressed() -> None:
    if py5.key == py5.ESC:
        py5.exit_sketch()
    elif py5.key == ' ' and _state.get("phase") == "welcome":
        # Signal the operator app that the participant is ready to begin
        try:
            _READY_FILE.write_text("ready")
        except Exception:
            pass
        # Locally transition to waiting while the operator starts intake
        _state["phase"] = "waiting"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    py5.run_sketch()
