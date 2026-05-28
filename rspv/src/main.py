# src/main.py
# pylint: disable=no-member
import threading
import time
from pathlib import Path

from visuals.visual_welcome     import VisualWelcome
from visuals.visual_waiting     import VisualWaiting
from visuals.visual_fixation    import VisualFixation
from visuals.visual_instruction import InstructionVisual
from visuals.visual_thankyou    import VisualThankYou
from visuals.visual_rorschach   import VisualRorschach
from visuals.visual_tree        import VisualTree
from visuals.visual_wire        import VisualWire
from visuals.visual_sunflower   import VisualSunflower
from visuals.visual_galaxy_spiral import VisualGalaxySpiral
from visuals.visual_rings       import VisualRings
from visuals.visual_flow_field  import VisualFlowField
from visuals.visual_ellipses    import VisualEllipses
from visuals.visual_amoeba      import VisualAmoeba
from visuals.visual_metaballs   import VisualMetaBalls
from visuals.visual_spider      import VisualSpider
from visuals.visual_complex_mataballs import VisualComplexMetaBalls

from rendering.py5_renderer     import render_visual
from visual_manager             import VisualManager
from visual_controller          import VisualController
from signal_processing.signal_manager import SignalManager
from utils.ant_utils            import load_config, parse_arguments

# ---------------------------------------------------------------------------
# Flag files — operator writes these; rspv watches and deletes after reading.
# ---------------------------------------------------------------------------
# Participant presses Space on welcome  → rspv writes this for the operator.
_WELCOME_READY_FILE    = Path("/tmp/antares_participant_ready.flag")
# Operator writes this when baseline recording should start (fixation cross).
_SHOW_BASELINE_FLAG    = Path("/tmp/antares_rspv_show_baseline.flag")
# Operator writes this when analysis is done (instruction page).
_SHOW_INSTRUCTION_FLAG = Path("/tmp/antares_rspv_show_instruction.flag")
# Participant presses Space on instruction page → rspv writes this for operator.
_RSPV_READY_FILE       = Path("/tmp/antares_rspv_ready.flag")
# Operator writes this after NF data is saved → rspv shows thank-you screen.
_SHOW_THANKYOU_FLAG    = Path("/tmp/antares_rspv_show_thankyou.flag")

VISUAL_PRESETS = {
    "VisualComplexMetaBalls": VisualComplexMetaBalls,
    "VisualRorschach":    VisualRorschach,
    "VisualEllipses":     VisualEllipses,
    "VisualWire":         VisualWire,
    "VisualSunflower":    VisualSunflower,
    "VisualGalaxySpiral": VisualGalaxySpiral,
    "VisualRings":        VisualRings,
    "VisualFlowField":    VisualFlowField,
    "VisualAmoeba":       VisualAmoeba,
    "VisualTree":         VisualTree,
    "VisualMetaBalls":    VisualMetaBalls,
    "VisualSpider":       VisualSpider,
}


def _switch(visual_controller, visual):
    """Set the current visual and schedule a setup+draw swap."""
    visual_controller.current_visual = visual
    render_visual(visual, restart=True)


def main():
    args = parse_arguments()
    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(e)
        return

    signal_manager = SignalManager(config)
    visual_preset  = config.get("visual_preset", "VisualRorschach")
    visual_manager = VisualManager(visual_preset, VISUAL_PRESETS)
    visual_controller = VisualController(
        visual_manager, signal_manager.signal_handler, config
    )
    threading.Thread(target=visual_controller.start_listeners, daemon=True).start()

    _CONNECT_WAIT = config.get("connect_wait_s", 3.0)

    # ------------------------------------------------------------------
    # Callbacks for participant Space presses
    # ------------------------------------------------------------------

    def on_welcome_ready():
        """Space on welcome page: signal operator, switch to waiting screen."""
        try:
            _WELCOME_READY_FILE.touch()
        except OSError:
            pass
        _switch(visual_controller, VisualWaiting(signal_manager.signal_handler, config))

    def on_instruction_ready():
        """Space on instruction page: signal operator, start signal processing,
        hold connecting screen, then fall back to NF if no OSC arrives."""
        try:
            _RSPV_READY_FILE.touch()
        except OSError:
            pass
        signal_manager.start_signal_processing()
        time.sleep(_CONNECT_WAIT)
        if isinstance(visual_controller.current_visual, InstructionVisual):
            visual_controller.on_phase_change("nf")

    # ------------------------------------------------------------------
    # Phase watcher — operator-driven transitions via flag files
    # ------------------------------------------------------------------

    def _phase_watcher():
        """Walk the participant through session phases.

        Waits for:
          1. _SHOW_BASELINE_FLAG    → fixation cross   (baseline + analysis)
          2. _SHOW_INSTRUCTION_FLAG → instruction page (participant presses Space)
        Both flags may already exist when this thread starts (nf-only flow).
        """
        # Step 1 — baseline / fixation cross
        while not (_SHOW_BASELINE_FLAG.exists() or _SHOW_INSTRUCTION_FLAG.exists()):
            time.sleep(0.3)

        if _SHOW_BASELINE_FLAG.exists():
            try:
                _SHOW_BASELINE_FLAG.unlink(missing_ok=True)
            except OSError:
                pass
            _switch(
                visual_controller,
                VisualFixation(signal_manager.signal_handler, config),
            )

            # Step 2 — instruction page (after analysis)
            while not _SHOW_INSTRUCTION_FLAG.exists():
                time.sleep(0.3)

        try:
            _SHOW_INSTRUCTION_FLAG.unlink(missing_ok=True)
        except OSError:
            pass
        _switch(
            visual_controller,
            InstructionVisual(
                signal_manager.signal_handler, config, on_ready=on_instruction_ready
            ),
        )

    threading.Thread(target=_phase_watcher, daemon=True).start()

    # ------------------------------------------------------------------
    # Thank-you watcher — fires once after NF data is saved
    # ------------------------------------------------------------------

    def _thankyou_watcher():
        while True:
            if _SHOW_THANKYOU_FLAG.exists():
                try:
                    _SHOW_THANKYOU_FLAG.unlink(missing_ok=True)
                except OSError:
                    pass
                _switch(visual_controller,
                        VisualThankYou(signal_manager.signal_handler, config))
                return
            time.sleep(0.3)

    threading.Thread(target=_thankyou_watcher, daemon=True).start()

    # ------------------------------------------------------------------
    # Start — welcome screen
    # ------------------------------------------------------------------
    welcome = VisualWelcome(
        signal_manager.signal_handler, config, on_ready=on_welcome_ready
    )
    visual_controller.current_visual = welcome
    render_visual(welcome, restart=False)


if __name__ == "__main__":
    main()
