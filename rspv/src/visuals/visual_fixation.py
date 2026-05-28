# src/visuals/visual_fixation.py
# pylint: disable=no-member
import py5
from .visual_base import VisualBase


class VisualFixation(VisualBase):
    """Blank dark screen with a white fixation cross — shown during rest phases."""

    def draw(self) -> None:
        py5.reset_shader()
        W, H = py5.width, py5.height
        py5.background(10, 10, 10)
        cx, cy = W / 2, H / 2
        arm, thick = 30, 4
        py5.no_stroke()
        py5.fill(200, 200, 200)
        py5.rect(cx - arm, cy - thick / 2, arm * 2, thick)   # horizontal
        py5.rect(cx - thick / 2, cy - arm, thick, arm * 2)   # vertical
        super().draw()
