"""Hardware trigger sender via parallel port (inpoutx64.dll).

On Windows Python: calls inpoutx64.dll directly via ctypes.
On WSL/Linux Python: spawns a Windows Python helper subprocess that owns the DLL.
"""
from __future__ import annotations

import logging
import subprocess
import sys
import time
import traceback
from pathlib import Path

_DLL_PATH = Path(__file__).parent / "inpoutx64.dll"
_HELPER_PATH = Path(__file__).parent / "trigger_helper.py"

# Trigger codes
TRIG_BASELINE_START = 10
TRIG_BASELINE_END   = 11
TRIG_REST_START     = 20
TRIG_NF_START       = 30
TRIG_SESSION_END    = 99

# Known Windows Python locations (checked in order)
_WIN_PYTHON_CANDIDATES = [
    Path("/mnt/c/Users/KARL-EXP-ANTARES/miniconda3/python.exe"),
    Path("/mnt/c/Users/KARL-EXP-ANTARES/anaconda3/python.exe"),
    Path("/mnt/c/ProgramData/miniconda3/python.exe"),
    Path("/mnt/c/ProgramData/anaconda3/python.exe"),
]


def _to_win_path(p: Path) -> str:
    """Convert a WSL mount path to a Windows UNC path for subprocess calls.

    Translates paths of the form ``/mnt/<drive>/...`` to
    ``<DRIVE>:\\...`` so they can be passed to a Windows Python interpreter
    launched as a subprocess.

    Args:
        p: Absolute ``Path`` object, typically under ``/mnt/c/``.

    Returns:
        str: Windows-style path (e.g. ``C:\\foo\\bar``), or the original
        string representation if *p* does not match the WSL ``/mnt/<x>/``
        pattern.
    """
    parts = p.resolve().parts
    if len(parts) >= 3 and parts[1] == "mnt" and len(parts[2]) == 1:
        drive = parts[2].upper()
        return drive + ":\\" + "\\".join(parts[3:])
    return str(p)


def _find_win_python() -> Path | None:
    """Search known Windows Python install locations and return the first found.

    Checks the paths listed in ``_WIN_PYTHON_CANDIDATES`` in order.

    Returns:
        ``Path`` to the Windows Python executable, or ``None`` if none of the
        candidate paths exist.
    """
    for candidate in _WIN_PYTHON_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


class ParallelTrigger:
    """Sends 1-byte TTL triggers to a parallel (LPT) port via inpoutx64.dll.

    On a native Windows Python interpreter the DLL is loaded directly via
    ``ctypes.WinDLL``.  When running under WSL/Linux Python, a persistent
    Windows Python helper subprocess (``trigger_helper.py``) is spawned; it
    owns the DLL handle and accepts trigger codes on its stdin, responding
    with ``"OK\\n"`` after each send.

    The port is reset to 0 on ``__init__`` and on ``close()``.

    Args:
        port_address: Hexadecimal LPT port address (e.g. ``0x3FF0``).
    """

    def __init__(self, port_address: int) -> None:
        self._addr = port_address
        self._io   = None   # ctypes DLL handle (Windows-native path)
        self._proc = None   # subprocess handle (WSL path)

        log_path = Path(__file__).parent.parent / "trigger_debug.log"
        print(f"[Trigger] Initialising LPT trigger at 0x{port_address:04X}")
        print(f"[Trigger] Python: {sys.executable}  platform: {sys.platform}")

        if sys.platform == "win32":
            self._init_direct(port_address, log_path)
        else:
            self._init_subprocess(port_address, log_path)

    # ------------------------------------------------------------------
    def _init_direct(self, port_address: int, log_path: Path) -> None:
        """Initialise via direct ctypes DLL call (Windows Python only).

        Args:
            port_address: LPT port address integer.
            log_path: Path to write a one-line init status log.
        """
        import ctypes
        print(f"[Trigger] Mode: direct ctypes  DLL: {_DLL_PATH}  exists={_DLL_PATH.exists()}")
        try:
            self._io = ctypes.WinDLL(str(_DLL_PATH))
            self._io.Out32(port_address, 0)
            msg = f"[Trigger] Connected OK -LPT 0x{port_address:04X} (direct)"
            print(msg)
            logging.info(msg)
            log_path.write_text(msg + "\n")
        except Exception:
            tb = traceback.format_exc()
            msg = f"[Trigger] FAILED (direct):\n{tb}"
            print(msg)
            logging.warning(msg)
            log_path.write_text(msg)
            self._io = None

    # ------------------------------------------------------------------
    def _init_subprocess(self, port_address: int, log_path: Path) -> None:
        """Initialise via a Windows Python helper subprocess (WSL/Linux path).

        Locates a Windows Python executable, launches ``trigger_helper.py``
        as a subprocess with the port address as an argument, and waits for
        ``"READY\\n"`` on stdout before returning.

        Args:
            port_address: LPT port address integer.
            log_path: Path to write a one-line init status log.
        """
        win_python = _find_win_python()
        if win_python is None:
            msg = "[Trigger] FAILED: no Windows Python found in known locations."
            print(msg)
            logging.warning(msg)
            log_path.write_text(msg + "\n")
            return

        win_helper  = _to_win_path(_HELPER_PATH)
        win_address = f"0x{port_address:04X}"
        print(f"[Trigger] Mode: subprocess  WinPython: {win_python}")
        print(f"[Trigger] Helper: {win_helper}")

        try:
            self._proc = subprocess.Popen(
                [str(win_python), win_helper, win_address],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            ready = self._proc.stdout.readline().strip()
            if ready == "READY":
                msg = f"[Trigger] Connected OK -LPT 0x{port_address:04X} (subprocess)"
                print(msg)
                logging.info(msg)
                log_path.write_text(msg + "\n")
            else:
                stderr = self._proc.stderr.read()
                msg = f"[Trigger] FAILED -helper said: {ready!r}\nstderr: {stderr}"
                print(msg)
                logging.warning(msg)
                log_path.write_text(msg)
                self._proc.kill()
                self._proc = None
        except Exception:
            tb = traceback.format_exc()
            msg = f"[Trigger] FAILED (subprocess):\n{tb}"
            print(msg)
            logging.warning(msg)
            log_path.write_text(msg)
            self._proc = None

    # ------------------------------------------------------------------
    @property
    def available(self) -> bool:
        """Return ``True`` if the trigger hardware or subprocess is ready."""
        return self._io is not None or self._proc is not None

    def send(self, code: int) -> None:
        """Send a trigger byte then reset the port to 0 after 5 ms.

        The port is written with *code*, held for 5 ms, then reset to 0.
        Failures are logged as warnings but do not raise exceptions.

        Args:
            code: 1-byte trigger code (0–255).  Known codes are defined as
                module-level constants (e.g. ``TRIG_NF_START = 30``).
        """
        _NAMES = {10: "BASELINE_START", 11: "BASELINE_END",
                  20: "REST_START", 30: "NF_START", 99: "SESSION_END"}
        label = _NAMES.get(code, str(code))
        print(f"[Trigger] >> {label} ({code})", flush=True)

        if self._io is not None:
            try:
                self._io.Out32(self._addr, int(code))
                time.sleep(0.005)
                self._io.Out32(self._addr, 0)
            except Exception as exc:
                logging.warning("ParallelTrigger.send(%d) failed: %s", code, exc)

        elif self._proc is not None:
            try:
                self._proc.stdin.write(f"{code}\n")
                self._proc.stdin.flush()
                self._proc.stdout.readline()  # consume "OK\n"
            except Exception as exc:
                logging.warning("ParallelTrigger.send(%d) failed: %s", code, exc)

    def close(self) -> None:
        """Pull the LPT line low and release resources.

        Writes 0 to the port (direct path) or sends ``"0\\n"`` to the helper
        subprocess and waits for it to exit (subprocess path).  Safe to call
        multiple times.
        """
        if self._io is not None:
            try:
                self._io.Out32(self._addr, 0)
            except Exception:
                pass

        if self._proc is not None:
            try:
                self._proc.stdin.write("0\n")
                self._proc.stdin.flush()
                self._proc.stdin.close()
                self._proc.wait(timeout=2)
            except Exception:
                pass
            finally:
                self._proc = None


class SerialTrigger:
    """Sends 1-byte TTL triggers via a serial COM port (e.g. BrainProducts TriggerBox on COM4).

    On a native Windows Python interpreter the port is opened directly via
    pyserial.  When running under WSL/Linux Python, a persistent Windows
    Python helper subprocess (``serial_trigger_helper.py``) is spawned; it
    owns the serial port handle and accepts trigger codes on its stdin.

    The port is reset (byte ``0x00``) on ``__init__`` and on ``close()``.

    Args:
        port: Serial port name, e.g. ``"COM4"`` (Windows) or ``"/dev/ttyUSB0"``
            (Linux).
    """

    _SERIAL_HELPER_PATH = Path(__file__).parent / "serial_trigger_helper.py"

    def __init__(self, port: str) -> None:
        self._port = port
        self._ser  = None   # pyserial handle (Windows-native path)
        self._proc = None   # subprocess handle (WSL path)

        log_path = Path(__file__).parent.parent / "trigger_debug.log"
        print(f"[Trigger] Initialising serial trigger on {port}")
        print(f"[Trigger] Python: {sys.executable}  platform: {sys.platform}")

        if sys.platform == "win32":
            self._init_direct(port, log_path)
        else:
            self._init_subprocess(port, log_path)

    def _init_direct(self, port: str, log_path: Path) -> None:
        """Initialise via direct pyserial call (Windows Python only).

        Args:
            port: Serial port name (e.g. ``"COM4"``).
            log_path: Path to write a one-line init status log.
        """
        try:
            import serial as _serial
            self._ser = _serial.Serial(port, baudrate=19200, timeout=1)
            self._ser.write(bytes([0]))
            msg = f"[Trigger] Connected OK -{port} (serial direct)"
            print(msg); logging.info(msg); log_path.write_text(msg + "\n")
        except Exception:
            tb = traceback.format_exc()
            msg = f"[Trigger] FAILED (serial direct):\n{tb}"
            print(msg); logging.warning(msg); log_path.write_text(msg)
            self._ser = None

    def _init_subprocess(self, port: str, log_path: Path) -> None:
        """Initialise via a Windows Python helper subprocess (WSL/Linux path).

        Args:
            port: Serial port name passed as the first argument to the helper.
            log_path: Path to write a one-line init status log.
        """
        win_python = _find_win_python()
        if win_python is None:
            msg = "[Trigger] FAILED: no Windows Python found in known locations."
            print(msg); logging.warning(msg); log_path.write_text(msg + "\n"); return

        win_helper = _to_win_path(self._SERIAL_HELPER_PATH)
        print(f"[Trigger] Mode: subprocess  WinPython: {win_python}")
        print(f"[Trigger] Helper: {win_helper}  Port: {port}")

        try:
            self._proc = subprocess.Popen(
                [str(win_python), win_helper, port],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            ready = self._proc.stdout.readline().strip()
            if ready == "READY":
                msg = f"[Trigger] Connected OK -{port} (serial subprocess)"
                print(msg); logging.info(msg); log_path.write_text(msg + "\n")
            else:
                stderr = self._proc.stderr.read()
                msg = f"[Trigger] FAILED -helper said: {ready!r}\nstderr: {stderr}"
                print(msg); logging.warning(msg); log_path.write_text(msg)
                self._proc.kill(); self._proc = None
        except Exception:
            tb = traceback.format_exc()
            msg = f"[Trigger] FAILED (serial subprocess):\n{tb}"
            print(msg); logging.warning(msg); log_path.write_text(msg)
            self._proc = None

    @property
    def available(self) -> bool:
        """Return ``True`` if the serial port or helper subprocess is ready."""
        return self._ser is not None or self._proc is not None

    def send(self, code: int) -> None:
        """Send a trigger byte then reset the port to 0 after 5 ms.

        Args:
            code: 1-byte trigger code (0–255).
        """
        _NAMES = {10: "BASELINE_START", 11: "BASELINE_END",
                  20: "REST_START", 30: "NF_START", 99: "SESSION_END"}
        label = _NAMES.get(code, str(code))
        print(f"[Trigger] >> {label} ({code})", flush=True)

        if self._ser is not None:
            try:
                self._ser.write(bytes([int(code)]))
                time.sleep(0.005)
                self._ser.write(bytes([0]))
            except Exception as exc:
                logging.warning("SerialTrigger.send(%d) failed: %s", code, exc)

        elif self._proc is not None:
            try:
                self._proc.stdin.write(f"{code}\n")
                self._proc.stdin.flush()
                self._proc.stdout.readline()  # consume "OK\n"
            except Exception as exc:
                logging.warning("SerialTrigger.send(%d) failed: %s", code, exc)

    def close(self) -> None:
        """Send a zero byte, close the serial port, and release the subprocess.

        Safe to call multiple times.
        """
        if self._ser is not None:
            try:
                self._ser.write(bytes([0]))
                self._ser.close()
            except Exception:
                pass
            finally:
                self._ser = None

        if self._proc is not None:
            try:
                self._proc.stdin.write("0\n")
                self._proc.stdin.flush()
                self._proc.stdin.close()
                self._proc.wait(timeout=2)
            except Exception:
                pass
            finally:
                self._proc = None


def make_trigger(enabled: bool, port_address: int = 0,
                 serial_port: str = "", mode: str = "serial") -> SerialTrigger | ParallelTrigger | None:
    """Construct and return a trigger object, or ``None`` if triggers are disabled.

    Factory function that centralises trigger creation.  The caller is
    responsible for calling ``.close()`` when the session ends.

    Args:
        enabled: If ``False``, returns ``None`` immediately without attempting
            any hardware initialisation.
        port_address: LPT parallel-port address (e.g. ``0x3FF0``).  Only used
            when *mode* is ``"lpt"``.
        serial_port: Serial COM port name (e.g. ``"COM4"``).  Only used when
            *mode* is ``"serial"``.
        mode: ``"serial"`` (default) to use ``SerialTrigger``, or ``"lpt"``
            to use ``ParallelTrigger``.

    Returns:
        ``SerialTrigger`` or ``ParallelTrigger`` instance, or ``None``.
    """
    if not enabled:
        return None
    if mode == "serial":
        return SerialTrigger(serial_port)
    return ParallelTrigger(port_address)
