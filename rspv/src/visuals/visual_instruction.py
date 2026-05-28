# src/visuals/visual_instruction.py
# pylint: disable=no-member
import threading
import py5
from visuals.visual_base import VisualBase

_C_BG    = (10, 12, 20)
_C_GREEN = (80, 220, 120)
_C_WHITE = (230, 230, 230)
_C_DIM   = (140, 140, 150)

_TEXTS = {
    "en": {
        "title": "Neurofeedback Session",
        "lines": [
            "You will see a visual that responds to your brain activity.",
            "Try to stay calm and focused throughout the session.",
            "",
            "The session runs in alternating blocks:",
            "Rest block (fixation cross) — relax and breathe normally.",
            "Feedback block (visual) — follow your therapist's guidance.",
        ],
        "press_space": "Press SPACE to begin",
        "connecting":  "Connecting — please wait ...",
    },
    "de": {
        "title": "Neurofeedback-Sitzung",
        "lines": [
            "Sie sehen eine Visualisierung, die auf Ihre Hirnaktivität reagiert.",
            "Versuchen Sie, während der gesamten Sitzung ruhig und konzentriert zu bleiben.",
            "",
            "Die Sitzung verläuft in abwechselnden Blöcken:",
            "Ruheblock (Fixationskreuz) — entspannen Sie sich und atmen Sie normal.",
            "Feedback-Block (Visualisierung) — folgen Sie den Anweisungen Ihres Therapeuten.",
        ],
        "press_space": "Leertaste drücken, um zu beginnen",
        "connecting":  "Verbindung wird hergestellt — bitte warten ...",
    },
    "fr": {
        "title": "Séance de neurofeedback",
        "lines": [
            "Vous verrez un affichage visuel qui réagit à votre activité cérébrale.",
            "Essayez de rester calme et concentré tout au long de la séance.",
            "",
            "La séance se déroule en blocs alternés :",
            "Bloc de repos (croix de fixation) — détendez-vous et respirez normalement.",
            "Bloc de feedback (visuel) — suivez les conseils de votre thérapeute.",
        ],
        "press_space": "Appuyez sur ESPACE pour commencer",
        "connecting":  "Connexion en cours — veuillez patienter ...",
    },
}


class InstructionVisual(VisualBase):
    """
    Fullscreen instruction screen shown before the NF session begins.
    Waits for the participant to press Space, then calls on_ready() in a
    background thread (which starts the OSC stream and swaps to the real visual).
    """

    def __init__(self, signal_handler, config, on_ready=None):
        super().__init__(signal_handler, config)
        self._on_ready = on_ready
        self._accepted = False
        self._tick = 0
        self._font_title = None
        self._font_body  = None
        self._font_hint  = None
        lang = config.get("lang", "en")
        self._txt = _TEXTS.get(lang, _TEXTS["en"])

    def setup(self):
        super().setup()
        self._font_title = py5.create_font("DejaVu Sans Bold", 30)
        self._font_body  = py5.create_font("DejaVu Sans", 16)
        self._font_hint  = py5.create_font("DejaVu Sans", 18)

    def draw(self):
        W, H = py5.width, py5.height
        py5.background(*_C_BG)
        py5.no_stroke()
        py5.text_align(py5.CENTER, py5.CENTER)

        # top accent bar
        py5.fill(*_C_GREEN)
        py5.rect(0, 0, W, 4)

        # heading
        py5.fill(*_C_WHITE)
        py5.text_font(self._font_title)
        py5.text(self._txt["title"], W / 2, H * 0.22)

        # instruction lines
        py5.text_font(self._font_body)
        y = H * 0.38
        for line in self._txt["lines"]:
            if line:
                py5.fill(*_C_DIM)
                py5.text(line, W / 2, y)
            y += 34

        # pulsing space hint
        self._tick += 1
        if not self._accepted:
            alpha = int(140 + 100 * (0.5 + 0.5 * py5.sin(self._tick * 0.06)))
            py5.fill(*_C_GREEN, alpha)
            py5.text_font(self._font_hint)
            py5.text(self._txt["press_space"], W / 2, H * 0.82)
        else:
            py5.fill(*_C_GREEN)
            py5.text_font(self._font_hint)
            py5.text(self._txt["connecting"], W / 2, H * 0.82)

        super().draw()  # debug overlays (Ctrl+F / Ctrl+V etc.)

    def key_pressed(self, e):
        super().key_pressed(e)
        if py5.key == ' ' and not self._accepted:
            self._accepted = True
            if self._on_ready:
                threading.Thread(target=self._on_ready, daemon=True).start()
