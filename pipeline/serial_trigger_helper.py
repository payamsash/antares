"""Windows Python helper: reads trigger codes from stdin, sends via serial port.

Launched as a subprocess by triggers.py when running under WSL/Linux Python.
Protocol:
  stdin:  integer trigger code, one per line (e.g. "30\n")
  stdout: "READY\n" on startup success, "OK\n" after each send, "ERR: ...\n" on failure
"""
import sys
import time
import serial


def main() -> None:
    """Entry point: open the serial port and serve trigger codes from stdin.

    Usage::

        python serial_trigger_helper.py <port>

    where *port* is a serial port name such as ``COM4``.

    Protocol:

    - On successful port open: writes ``"READY\\n"`` to stdout.
    - On failure: writes ``"ERR: <message>\\n"`` to stdout and exits with
      code 1.
    - For each trigger code received on stdin: sends the byte via the serial
      port, waits 5 ms, resets to 0, then writes ``"OK\\n"`` (or
      ``"ERR: <msg>\\n"`` on failure).
    - The loop exits when stdin is closed (parent process terminated).
    """
    if len(sys.argv) < 2:
        sys.stdout.write("ERR: usage: serial_trigger_helper.py <port>\n")
        sys.stdout.flush()
        sys.exit(1)

    port = sys.argv[1]

    try:
        ser = serial.Serial(port, baudrate=19200, timeout=1)
        ser.write(bytes([0]))
    except Exception as exc:
        sys.stdout.write(f"ERR: Serial init failed: {exc}\n")
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
            ser.write(bytes([code]))
            time.sleep(0.005)
            ser.write(bytes([0]))
            sys.stdout.write("OK\n")
            sys.stdout.flush()
        except Exception as exc:
            sys.stdout.write(f"ERR: {exc}\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
