# src/visuals/visual_welcome.py
# pylint: disable=no-member
import threading
import py5
from visuals.visual_base import VisualBase

_C_BG    = (10, 12, 20)
_C_WHITE = (230, 230, 230)
_C_DIM   = (140, 140, 150)
_C_GREEN = (80, 220, 120)

_TEXTS = {
    "en": {
        "title":        "Welcome to ANTARES",
        "fixation_hint": "During rest blocks a fixation cross will appear — please relax and look at it.",
        "press_space":  "Press SPACE when ready",
    },
    "de": {
        "title":        "Willkommen bei ANTARES",
        "fixation_hint": "Während der Ruheblöcke erscheint ein Fixationskreuz — bitte entspannen Sie sich und schauen Sie es an.",
        "press_space":  "Leertaste drücken, wenn bereit",
    },
    "fr": {
        "title":        "Bienvenue dans ANTARES",
        "fixation_hint": "Pendant les blocs de repos, une croix de fixation apparaîtra — détendez-vous et regardez-la.",
        "press_space":  "Appuyez sur ESPACE quand vous êtes prêt",
    },
}


class VisualWelcome(VisualBase):
    """Fullscreen welcome screen. Participant presses Space to confirm readiness."""

    def __init__(self, signal_handler, config, on_ready=None):
        super().__init__(signal_handler, config)
        lang = config.get("lang", "en")
        txt = _TEXTS.get(lang, _TEXTS["en"])
        self._title         = txt["title"]
        self._fixation_hint = txt["fixation_hint"]
        self._press_space   = txt["press_space"]
        self._on_ready      = on_ready
        self._ready         = False
        self._font_title    = None
        self._font_sub      = None
        self._font_hint     = None
        self._tick          = 0.0

    def setup(self) -> None:
        super().setup()
        self._font_title = py5.create_font("DejaVu Sans Bold", 64)
        self._font_sub   = py5.create_font("DejaVu Sans", 22)
        self._font_hint  = py5.create_font("DejaVu Sans", 16)

    def draw(self) -> None:
        if self._font_title is None:
            return
        self._tick += 0.04
        W, H = py5.width, py5.height
        py5.background(*_C_BG)

        # Soft pulsing ring
        r = 140 + 12 * py5.sin(self._tick * 0.7)
        alpha = int(20 + 12 * py5.sin(self._tick * 0.7))
        py5.no_fill()
        py5.stroke(*_C_GREEN, alpha)
        py5.stroke_weight(1.5)
        py5.ellipse(W / 2, H * 0.38, r * 2, r * 2)
        py5.no_stroke()

        # Title
        py5.text_align(py5.CENTER, py5.CENTER)
        py5.fill(*_C_WHITE)
        py5.text_font(self._font_title)
        py5.text(self._title, W / 2, H * 0.38)

        # Fixation cross hint
        py5.fill(*_C_DIM)
        py5.text_font(self._font_hint)
        py5.text(self._fixation_hint, W / 2, H * 0.55)

        # "Press SPACE" prompt — pulsing
        if not self._ready:
            alpha_hint = int(140 + 100 * (0.5 + 0.5 * py5.sin(self._tick * 1.2)))
            py5.fill(*_C_DIM, alpha_hint)
            py5.text_font(self._font_sub)
            py5.text(self._press_space, W / 2, H * 0.65)

        super().draw()

    def key_pressed(self, e) -> None:
        super().key_pressed(e)
        if py5.key == ' ' and not self._ready and self._on_ready:
            self._ready = True
            threading.Thread(target=self._on_ready, daemon=True).start()
