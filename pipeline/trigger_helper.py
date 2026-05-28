"""Windows Python helper: reads trigger codes from stdin, sends via inpoutx64.dll.

Launched as a subprocess by triggers.py when running under WSL/Linux Python.
Communicates via stdin/stdout lines. Protocol:
  stdin:  integer trigger code, one per line (e.g. "30\n")
  stdout: "READY\n" on startup success, "OK\n" after each send, "ERR: ...\n" on failure
"""
import sys
import ctypes
import time
from pathlib import Path

def main() -> None:
    """Entry point: initialise inpoutx64.dll and serve trigger codes from stdin.

    Usage::

        python trigger_helper.py <hex_address>

    where *hex_address* is the LPT port address in hexadecimal (e.g.
    ``0x3FF0``).

    Protocol:

    - On successful DLL load and port initialisation: writes ``"READY\\n"``
      to stdout.
    - On DLL failure: writes ``"ERR: DLL init failed: <msg>\\n"`` to stdout
      and exits with code 1.
    - For each trigger code received on stdin: writes *code* to the parallel
      port data register, waits 5 ms, resets to 0, then writes ``"OK\\n"``
      (or ``"ERR: <msg>\\n"`` on failure).
    - The loop exits when stdin is closed (parent process terminated).
    """
    if len(sys.argv) < 2:
        sys.stdout.write("ERR: usage: trigger_helper.py <hex_address>\n")
        sys.stdout.flush()
        sys.exit(1)

    port_address = int(sys.argv[1], 16)
    dll_path = Path(__file__).parent / "inpoutx64.dll"

    try:
        io = ctypes.WinDLL(str(dll_path))
        # Set data direction to output: clear bit 5 of control register
        ctrl = io.Inp32(port_address + 2) & 0xFF
        io.Out32(port_address + 2, ctrl & ~0x20)
        # Set SPP mode via ECR if present
        ecr = io.Inp32(port_address + 8) & 0xFF
        if ecr != 0xFF:
            io.Out32(port_address + 8, ecr & 0x1F)
        io.Out32(port_address, 0)  # reset line at startup
    except Exception as exc:
        sys.stdout.write(f"ERR: DLL init failed: {exc}\n")
        sys.stdout.flush()
        sys.exit(1)

    sys.stdout.write("READY\n")
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            code = int(line)
            io.Out32(port_address, code)
            time.sleep(0.005)
            io.Out32(port_address, 0)
            sys.stdout.write("OK\n")
            sys.stdout.flush()
        except Exception as exc:
            sys.stdout.write(f"ERR: {exc}\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
