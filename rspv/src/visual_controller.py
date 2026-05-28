# src/visual_controller.py
# pylint: disable=no-member

import threading
import time
from rendering.py5_renderer import render_visual
from visuals.visual_fixation import VisualFixation

class VisualController:
    """
    VisualController manages switching between visual presets.

    It listens for keyboard events or external signal triggers (via the signal_handler)
    and uses a VisualManager to cycle through available visual presets. When a switch
    is triggered, it cleans up the previous visual and starts the new one.
    """
    def __init__(self, visual_manager, signal_handler, config):
        """
        Initializes the VisualController.

        Args:
            visual_manager (VisualManager): An instance managing available visual presets.
            signal_handler: The signal handler used for receiving external triggers.
            config (dict): The configuration dictionary.
        """
        self.visual_manager = visual_manager
        self.signal_handler = signal_handler
        self.config = config
        self.current_visual = None
        self.previous_trigger_state = 0
        self._nf_preset = visual_manager.get_current_preset()
        self.signal_handler.add_visual_trigger_listener(self._on_visual_trigger)
        self.signal_handler.add_phase_listener(self.on_phase_change)

    def start_listeners(self):
        threading.Thread(target=self._listen_for_key_presses, daemon=True).start()

    def _listen_for_key_presses(self):
        # keyboard-based switching is not available in WSL; visual switching
        # happens via OSC trigger (_on_visual_trigger) during the NF session.
        while True:
            time.sleep(3600)

    def _on_visual_trigger(self, trigger_value):
        """Called when visual trigger changes."""
        if trigger_value == 1:
            self.visual_manager.switch_preset()
            new_preset = self.visual_manager.get_current_preset()
            self.on_preset_change(new_preset, restart=True)

    def on_phase_change(self, phase: str) -> None:
        """Switch between fixation cross (rest) and NF visual (nf)."""
        print(f"[VisualController] phase → {phase}")
        if phase == "rest":
            new_visual = VisualFixation(self.signal_handler, self.config)
        else:
            new_visual = self.visual_manager.available_presets[self._nf_preset](
                self.signal_handler, self.config
            )
        self.current_visual = new_visual
        render_visual(new_visual, restart=True)

    def on_preset_change(self, new_preset, restart):
        """
        Handles the visual preset change event.

        This method cleans up the previous visual, instantiates the new visual using the
        VisualManager's preset mapping, and calls render_visual() to update the display.

        Args:
            new_preset (str): The identifier of the new visual preset.
            restart (bool): Whether to restart the sketch (hot reload) or not.
        """
        print(f"Switched to: {new_preset}")
        self.current_visual = self.visual_manager.available_presets[new_preset](self.signal_handler, self.config)
        render_visual(self.current_visual, restart)
