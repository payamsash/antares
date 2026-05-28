# src/rendering/py5_renderer.py
# pylint: disable=no-member
import py5
import psutil
import gc
import cProfile
import traceback

check_memory = False

# Module-level current visual — updated by render_visual() on every switch.
# The sketch's draw/key_pressed closures always read this, so swapping the
# visual never requires opening a new sketch window or calling hot_reload_draw.
_current_visual = None
_pending_setup = False   # True → call setup() on the new visual next draw frame


def get_memory_usage():
    process = psutil.Process()
    mem_info = process.memory_info()
    return mem_info.rss / (1024 * 1024)


def check_garbage():
    gc.collect()
    print(f"Unreachable objects: {len(gc.garbage)}")


def profile_drawing(visual):
    profiler = cProfile.Profile()
    profiler.enable()
    visual.draw()
    profiler.disable()
    profiler.print_stats(sort="cumulative")


def render_visual(visual, restart):
    """Register *visual* as the active visual.

    If *restart* is False this is the first call: sets up py5 lifecycle hooks
    and calls run_sketch() (blocks until the sketch exits).

    If *restart* is True the sketch is already running: just update
    _current_visual and schedule a one-shot setup() call on the next draw
    frame.  No new window is opened.
    """
    global _current_visual, _pending_setup

    if check_memory:
        print(f"Memory before loading visual: {get_memory_usage():.2f} MB")

    _current_visual = visual

    if restart:
        _pending_setup = True
        return

    # ------------------------------------------------------------------ #
    # First launch: define py5 lifecycle functions and start the sketch.  #
    # The closures reference _current_visual (the global), so they always  #
    # call the most recently registered visual — no rewiring needed when   #
    # visuals are swapped later.                                           #
    # ------------------------------------------------------------------ #

    def settings():
        if _current_visual is not None and hasattr(_current_visual, 'settings'):
            try:
                _current_visual.settings()
            except Exception as e:
                print(f"[py5] Error in visual.settings():\n{traceback.format_exc()}")

    def setup():
        global _pending_setup
        if _current_visual is not None and hasattr(_current_visual, 'setup'):
            try:
                _current_visual.setup()
            except Exception as e:
                print(f"[py5] Error in visual.setup():\n{traceback.format_exc()}")
        _pending_setup = False

    _draw_error_printed: set = set()

    def draw():
        global _pending_setup
        # One-shot setup for a newly swapped-in visual (runs in sketch thread).
        if _pending_setup:
            if _current_visual is not None and hasattr(_current_visual, 'setup'):
                try:
                    _current_visual.setup()
                except Exception as e:
                    print(f"[py5] Error in visual.setup() [swap]:\n{traceback.format_exc()}")
            _pending_setup = False
        if _current_visual is not None and hasattr(_current_visual, 'draw'):
            try:
                _current_visual.draw()
            except Exception as e:
                key = (type(_current_visual).__name__, type(e).__name__, str(e))
                if key not in _draw_error_printed:
                    _draw_error_printed.add(key)
                    print(f"[py5] Error in visual.draw():\n{traceback.format_exc()}")

    def key_pressed(e):
        if _current_visual is not None and hasattr(_current_visual, 'key_pressed'):
            try:
                _current_visual.key_pressed(e)
            except Exception as ex:
                print(f"Error in visual.key_pressed(): {ex}")

    py5.settings = lambda: settings()
    py5.setup    = lambda: setup()
    py5.draw     = lambda: draw()
    py5.key_pressed = lambda e: key_pressed(e)

    try:
        py5.run_sketch()
    except Exception as e:
        print(f"Error running py5 sketch: {e}")

    if check_memory:
        print(f"Memory after loading visual: {get_memory_usage():.2f} MB")
        check_garbage()
