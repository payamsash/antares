# src/signal_processing/signal_handler.py
# pylint: disable=no-member
from pythonosc import dispatcher, osc_server
import threading


class SignalHandler:
    """
    Receives and processes neurofeedback signals via OSC.

    The incoming /rspv message carries (min_power, max_power, value).
    The value is normalised to [0, 1] using the rolling min/max sent by
    ANTARES, then scaled to [min_range_viz, max_range_viz].

    Thread safety: the latest signal value is stored under a lock so that
    get_signal() always returns the most recent value without competing
    with any background thread.
    """

    def __init__(self, min_power, max_power, min_range_viz, max_range_viz):
        self.min_power      = min_power
        self.max_power      = max_power
        self.min_range_viz  = min_range_viz
        self.max_range_viz  = max_range_viz
        self.print_signal   = False
        self.visual_trigger = 0
        self.trigger_listeners = []

        # Latest-value store (replaces FIFO queue — we always want the newest)
        self._latest_signal = 0.0
        self._lock          = threading.Lock()

        self._phase = "rest"
        self._phase_listeners: list = []

    # ------------------------------------------------------------------
    # Trigger / phase listeners
    # ------------------------------------------------------------------

    def add_visual_trigger_listener(self, callback):
        """Register a callback invoked when the visual trigger changes."""
        self.trigger_listeners.append(callback)

    def add_phase_listener(self, callback):
        """Register a callback invoked when /rspv_ctrl changes phase."""
        self._phase_listeners.append(callback)

    # ------------------------------------------------------------------
    # OSC handler
    # ------------------------------------------------------------------

    def osc_handler(self, addr, *args):
        """
        Handle incoming /rspv OSC message.

        Expected layout:
            args[0]  rolling min power  (float)
            args[1]  rolling max power  (float)
            args[2]  participant performance / raw feature value  (float)
            args[5]  (optional) visual trigger flag  (int)
        """
        try:
            participant_performance = float(args[2])

            if args[0] is not None:
                self.min_power = float(args[0])
            if args[1] is not None:
                self.max_power = float(args[1])

            scaled = self.scale_signal(participant_performance)

            if self.print_signal:
                print(
                    f"perf={participant_performance:.4f}  "
                    f"range=[{self.min_power:.4f},{self.max_power:.4f}]  "
                    f"scaled={scaled:.4f}"
                )

            with self._lock:
                self._latest_signal = scaled

            if len(args) > 5:
                new_trigger = int(args[5])
                if new_trigger != self.visual_trigger:
                    self.visual_trigger = new_trigger
                    for cb in self.trigger_listeners:
                        cb(self.visual_trigger)

        except (ValueError, TypeError, IndexError) as exc:
            print(f"[SignalHandler] OSC parse error: {exc}")

    # ------------------------------------------------------------------
    # Scaling
    # ------------------------------------------------------------------

    def scale_signal(self, participant_performance: float) -> float:
        """Normalise *participant_performance* to [0, 1] then scale to viz range."""
        rng = self.max_power - self.min_power
        # Guard: if range is zero (very start of session), treat as midpoint
        if rng == 0.0:
            normalised = 0.5
        else:
            normalised = (participant_performance - self.min_power) / rng
        normalised = max(0.0, min(normalised, 1.0))
        return normalised * (self.max_range_viz - self.min_range_viz) + self.min_range_viz

    # ------------------------------------------------------------------
    # Signal access
    # ------------------------------------------------------------------

    def get_signal(self) -> float:
        """Return the latest scaled signal value (thread-safe)."""
        with self._lock:
            return self._latest_signal

    def get_visual_trigger(self) -> int:
        """Return the current visual trigger state (0 or 1)."""
        return self.visual_trigger

    def update_signal(self, participant_performance: float, print_signal: bool = False) -> None:
        """Programmatically inject a signal value (used by file / LSL sources)."""
        self.print_signal = print_signal
        scaled = self.scale_signal(participant_performance)
        if self.print_signal:
            print(f"[SignalHandler] perf={participant_performance:.4f}  scaled={scaled:.4f}")
        with self._lock:
            self._latest_signal = scaled

    # ------------------------------------------------------------------
    # OSC server
    # ------------------------------------------------------------------

    def phase_handler(self, addr, *args) -> None:
        """Handle /rspv_ctrl messages (0 = rest, 1 = nf)."""
        try:
            phase = "nf" if int(args[0]) == 1 else "rest"
            if phase != self._phase:
                self._phase = phase
                for cb in self._phase_listeners:
                    cb(phase)
        except (ValueError, TypeError, IndexError) as exc:
            print(f"[SignalHandler] phase parse error: {exc}")

    def start_receiving(
        self,
        ip: str = "127.0.0.1",
        port: int = 5005,
        address: str = "/rspv",
        print_signal: bool = False,
    ) -> None:
        """Start a blocking OSC UDP server (call from a daemon thread)."""
        self.print_signal = print_signal
        disp = dispatcher.Dispatcher()
        disp.map(address, self.osc_handler)
        disp.map("/rspv_ctrl", self.phase_handler)
        server = osc_server.BlockingOSCUDPServer((ip, port), disp)
        print(f"[SignalHandler] OSC server listening on {ip}:{port}  address='{address}'")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("[SignalHandler] OSC server stopped.")

    def stop(self) -> None:
        """No-op kept for API compatibility."""
        pass
