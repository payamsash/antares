# src/visuals/visual_thankyou.py
# pylint: disable=no-member
import py5
from visuals.visual_base import VisualBase

_C_BG    = (10, 12, 20)
_C_WHITE = (230, 230, 230)
_C_DIM   = (140, 140, 150)
_C_GREEN = (80, 220, 120)

_TEXTS = {
    "en": {
        "title": "Thank You",
        "body":  "The session data has been saved.",
        "sub":   "You may now remove the EEG headset.",
    },
    "de": {
        "title": "Vielen Dank",
        "body":  "Die Sitzungsdaten wurden gespeichert.",
        "sub":   "Sie können das EEG-Headset nun abnehmen.",
    },
    "fr": {
        "title": "Merci",
        "body":  "Les données de la séance ont été enregistrées.",
        "sub":   "Vous pouvez maintenant retirer le casque EEG.",
    },
}


class VisualThankYou(VisualBase):
    """Fullscreen thank-you screen shown for ~5 s after the NF session saves."""

    def __init__(self, signal_handler, config):
        super().__init__(signal_handler, config)
        lang = config.get("lang", "en")
        txt = _TEXTS.get(lang, _TEXTS["en"])
        self._title      = txt["title"]
        self._body       = txt["body"]
        self._sub        = txt["sub"]
        self._font_title = None
        self._font_body  = None
        self._tick       = 0.0

    def setup(self) -> None:
        super().setup()
        self._font_title = py5.create_font("DejaVu Sans Bold", 56)
        self._font_body  = py5.create_font("DejaVu Sans", 22)

    def draw(self) -> None:
        if self._font_title is None:
            return
        self._tick += 0.04
        W, H = py5.width, py5.height
        py5.background(*_C_BG)

        # Soft pulsing ring
        r = 120 + 8 * py5.sin(self._tick * 0.5)
        alpha = int(25 + 15 * py5.sin(self._tick * 0.5))
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

        # Body lines
        py5.fill(*_C_DIM)
        py5.text_font(self._font_body)
        py5.text(self._body, W / 2, H * 0.58)
        py5.text(self._sub,  W / 2, H * 0.64)

        super().draw()
