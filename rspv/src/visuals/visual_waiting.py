# src/visuals/visual_waiting.py
# pylint: disable=no-member
import py5
from visuals.visual_base import VisualBase

_C_BG    = (10, 12, 20)
_C_WHITE = (230, 230, 230)
_C_DIM   = (140, 140, 150)
_C_GREEN = (80, 220, 120)

_TEXTS = {
    "en": "Please wait ...",
    "de": "Bitte warten ...",
    "fr": "Veuillez patienter ...",
}


class VisualWaiting(VisualBase):
    """Fullscreen waiting screen shown while the operator prepares the session."""

    def __init__(self, signal_handler, config):
        super().__init__(signal_handler, config)
        lang = config.get("lang", "en")
        self._label     = _TEXTS.get(lang, _TEXTS["en"])
        self._font_text = None
        self._tick      = 0.0

    def setup(self) -> None:
        super().setup()
        self._font_text = py5.create_font("DejaVu Sans", 26)

    def draw(self) -> None:
        if self._font_text is None:
            return
        self._tick += 0.04
        W, H = py5.width, py5.height
        py5.background(*_C_BG)

        # Label
        py5.text_align(py5.CENTER, py5.CENTER)
        py5.fill(*_C_DIM)
        py5.text_font(self._font_text)
        py5.text(self._label, W / 2, H * 0.45)

        # Pulsing dots
        n, spacing = 3, 18
        total = (n - 1) * spacing
        for i in range(n):
            phase_offset = i * 1.1
            a = int(80 + 100 * (0.5 + 0.5 * py5.sin(self._tick * 1.4 + phase_offset)))
            dot_r = 4 + 2 * py5.sin(self._tick * 1.4 + phase_offset)
            py5.no_stroke()
            py5.fill(*_C_GREEN, a)
            py5.ellipse(W / 2 - total / 2 + i * spacing, H * 0.56, dot_r, dot_r)

        super().draw()
