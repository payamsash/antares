"""Standalone trigger test — sends S11 via Serial (COM3) and/or Parallel (LPT3).

Serial method  : matches gpias-play.py — serial.Serial + ser.write(bytes([code]))
Parallel method: inpoutx64.dll via ctypes

Usage:
    python test_trigger.py            # tries both
    python test_trigger.py serial     # serial only
    python test_trigger.py parallel   # parallel only
    python test_trigger.py loopback   # loopback test (short DB9 pin2-pin3 first!)
    python test_trigger.py train      # repeated S11 every 500 ms, 20 ms pulse, Ctrl+C to stop

When run from WSL/Linux Python this script automatically re-launches itself via
the Windows Python interpreter so that ctypes.WinDLL and COM ports work correctly.
"""
import subprocess
import sys
import time
import ctypes
from pathlib import Path

# ── WSL auto-relaunch ─────────────────────────────────────────────────────────
_WIN_PYTHON_CANDIDATES = [
    Path("/mnt/c/Users/KARL-EXP-ANTARES/miniconda3/python.exe"),
    Path("/mnt/c/Users/KARL-EXP-ANTARES/anaconda3/python.exe"),
    Path("/mnt/c/ProgramData/miniconda3/python.exe"),
    Path("/mnt/c/ProgramData/anaconda3/python.exe"),
]

def _to_win_path(p: Path) -> str:
    parts = p.resolve().parts
    if len(parts) >= 3 and parts[1] == "mnt" and len(parts[2]) == 1:
        drive = parts[2].upper()
        return drive + ":\\" + "\\".join(parts[3:])
    return str(p)

if sys.platform != "win32":
    win_python = next((c for c in _WIN_PYTHON_CANDIDATES if c.exists()), None)
    if win_python is None:
        print("ERROR: running under WSL but no Windows Python found in known locations.")
        print("Expected one of:")
        for c in _WIN_PYTHON_CANDIDATES:
            print(f"  {c}")
        sys.exit(1)
    win_script = _to_win_path(Path(__file__))
    print(f"[WSL] Relaunching via Windows Python: {win_python}")
    result = subprocess.run([str(win_python), win_script] + sys.argv[1:])
    sys.exit(result.returncode)

# ── Configuration ────────────────────────────────────────────────────────────
SERIAL_PORT  = "COM4"    # change if needed
BAUDRATE     = 19200
LPT_ADDRESS  = 0x3FF0    # LPT3 on this machine (AX99100); verified via Device Manager > Resources
TRIGGER_CODE = 11        # S11
PULSE_MS     = 0.001     # 1 ms pulse (matches gpias-play.py)
TRAIN_PULSE_MS   = 0.020 # 20 ms pulse for train mode
TRAIN_INTERVAL_S = 0.500 # 500 ms between trigger onsets
# ─────────────────────────────────────────────────────────────────────────────

DLL_PATH = Path(__file__).parent / "pipeline" / "inpoutx64.dll"

SEP = "-" * 52


# ── Serial loopback ───────────────────────────────────────────────────────────
def test_loopback():
    """Verifies the serial port hardware works independently of any cable/BrainAmp.

    BEFORE RUNNING: short DB9 Pin 2 (RX) to Pin 3 (TX) with a wire or paperclip.
    The port will send bytes and read them back — if they match, the port is good.
    If loopback FAILS → faulty port or driver issue (not a cable problem).
    If loopback PASSES but BrainVision gets nothing → cable or BrainAmp side issue.
    """
    print(SEP)
    print("SERIAL LOOPBACK TEST")
    print(f"  Port    : {SERIAL_PORT}")
    print(f"  IMPORTANT: short DB9  Pin 2 (RX) <-> Pin 3 (TX)  before continuing.")
    print()

    try:
        import serial
    except ImportError:
        print("  ERROR: pyserial not installed — run:  pip install pyserial")
        return False

    try:
        ser = serial.Serial(SERIAL_PORT, baudrate=BAUDRATE, timeout=1)
    except serial.SerialException as e:
        print(f"  ERROR: {e}")
        return False

    test_bytes = bytes([0x55, 0xAA, 11, 0, 255, 1])
    ser.reset_input_buffer()
    ser.write(test_bytes)
    time.sleep(0.1)
    received = ser.read(len(test_bytes))
    ser.close()

    if received == test_bytes:
        print(f"  PASS — sent {list(test_bytes)}, received {list(received)}")
        print("  Serial port hardware is working correctly.")
        return True
    elif len(received) == 0:
        print("  FAIL — nothing received. Either:")
        print("         • Pin 2/3 are not shorted (check your wire)")
        print("         • Port is not actually transmitting (driver issue)")
        return False
    else:
        print(f"  FAIL — sent {list(test_bytes)}, received {list(received)}")
        print("  Partial/corrupted loopback — possible baud rate or framing issue.")
        return False


# ── Serial ────────────────────────────────────────────────────────────────────
def test_serial():
    print(SEP)
    print("SERIAL TEST")
    print(f"  Port     : {SERIAL_PORT}")
    print(f"  Baudrate : {BAUDRATE}")
    print(f"  Trigger  : S{TRIGGER_CODE}")

    try:
        import serial
        import serial.tools.list_ports
    except ImportError:
        print("  ERROR: pyserial not installed — run:  pip install pyserial")
        return False

    print("\n  Available COM ports:")
    for p in serial.tools.list_ports.comports():
        marker = " <--" if p.device == SERIAL_PORT else ""
        print(f"    {p.device:8s}  {p.description}{marker}")
    print()

    try:
        ser = serial.Serial(SERIAL_PORT, baudrate=BAUDRATE, timeout=1)
    except serial.SerialException as e:
        print(f"  ERROR: {e}")
        return False

    ser.write(bytes([TRIGGER_CODE]))
    time.sleep(PULSE_MS)
    ser.write(bytes([0]))
    ser.close()
    print(f"  OK — S{TRIGGER_CODE} sent on {SERIAL_PORT}")
    return True


# ── Parallel ──────────────────────────────────────────────────────────────────
def test_parallel():
    print(SEP)
    print("PARALLEL TEST")
    print(f"  LPT address : 0x{LPT_ADDRESS:04X}  (LPT3)")
    print(f"  DLL         : {DLL_PATH}")
    print(f"  DLL exists  : {DLL_PATH.exists()}")
    print(f"  Trigger     : S{TRIGGER_CODE}")
    print()

    if not DLL_PATH.exists():
        print("  ERROR: inpoutx64.dll not found.")
        print("         Download: https://highrez.co.uk/downloads/inpout32.htm")
        print(f"         Place inpoutx64.dll in:  {DLL_PATH.parent}")
        return False

    try:
        io = ctypes.WinDLL(str(DLL_PATH))
    except OSError as e:
        print(f"  ERROR: could not load DLL: {e}")
        return False

    io.Out32(LPT_ADDRESS, 0)          # reset before pulse
    time.sleep(0.01)
    io.Out32(LPT_ADDRESS, TRIGGER_CODE)
    time.sleep(PULSE_MS)
    io.Out32(LPT_ADDRESS, 0)          # reset after pulse
    print(f"  OK — S{TRIGGER_CODE} sent on LPT3 (0x{LPT_ADDRESS:04X})")
    return True


# ── LPT port self-test ───────────────────────────────────────────────────────
def test_lpt_readback():
    """Write known values to the LPT data register and read them back.
    Also dumps all registers around 0x3FF0 to diagnose port state.
    Does NOT require a cable — purely tests the PC-side port hardware.
    """
    print(SEP)
    print("LPT READBACK TEST")
    print(f"  Address : 0x{LPT_TRAIN_ADDRESS:04X}")
    print()

    if not DLL_PATH.exists():
        print(f"  ERROR: inpoutx64.dll not found at {DLL_PATH}")
        return False

    try:
        io = ctypes.WinDLL(str(DLL_PATH))
    except OSError as e:
        print(f"  ERROR: could not load DLL: {e}")
        return False

    # Dump all registers around base address
    print("  Register dump (base=0x3FF0):")
    names = {0: "DATA", 1: "STATUS", 2: "CONTROL", 8: "ECR(+8)"}
    for offset in [0, 1, 2, 3, 4, 5, 6, 7, 8]:
        v = io.Inp32(LPT_TRAIN_ADDRESS + offset) & 0xFF
        label_str = names.get(offset, "")
        print(f"    0x{LPT_TRAIN_ADDRESS+offset:04X} (+{offset}) = 0x{v:02X}  {v:08b}  {label_str}")
    print()

    def _do_readback(label):
        patterns = [0x00, 0xFF, 0x55, 0xAA, 0x0F, 0xF0]
        passed = True
        for val in patterns:
            io.Out32(LPT_TRAIN_ADDRESS, val)
            time.sleep(0.001)
            readback = io.Inp32(LPT_TRAIN_ADDRESS) & 0xFF
            match = "OK" if readback == val else "MISMATCH"
            print(f"  [{label}]  wrote 0x{val:02X} ({val:08b})  read 0x{readback:02X} ({readback:08b})  {match}")
            if readback != val:
                passed = False
        return passed

    # First attempt
    ok = _do_readback("before fix")

    if not ok:
        print()
        print("  Readback failed — attempting to set data direction to OUTPUT ...")

        # Clear bit 5 of control register (0=output mode, 1=input/bidirectional mode)
        ctrl = io.Inp32(LPT_TRAIN_ADDRESS + 2) & 0xFF
        print(f"  Control register (0x{LPT_TRAIN_ADDRESS+2:04X}) before: 0x{ctrl:02X} ({ctrl:08b})")
        ctrl_out = ctrl & ~0x20   # clear direction bit
        io.Out32(LPT_TRAIN_ADDRESS + 2, ctrl_out)
        print(f"  Control register (0x{LPT_TRAIN_ADDRESS+2:04X}) after : 0x{ctrl_out:02X} ({ctrl_out:08b})")

        # Also try setting ECR to SPP mode (bits 7:5 = 000) if ECP port
        ecr_addr = LPT_TRAIN_ADDRESS + 0x08
        ecr = io.Inp32(ecr_addr) & 0xFF
        if ecr != 0xFF:
            print(f"  ECR (0x{ecr_addr:04X}) before: 0x{ecr:02X} — setting SPP mode (bits 7:5 → 000)")
            io.Out32(ecr_addr, ecr & 0x1F)
        print()

        ok = _do_readback("after fix")

    io.Out32(LPT_TRAIN_ADDRESS, 0)

    print()
    if ok:
        print("  PASS — data register responds correctly. Port is alive and in output mode.")
    else:
        print("  FAIL — read-back still does not match after attempting fix.")
        print("         Try changing parallel port mode to SPP in BIOS/UEFI settings.")
    return ok


# ── Train ───────────────────────────────────────────────────────────────────
# Bit 2 is permanently high in the amplifier — only bits 0 and 1 are used.
# Valid stimulus codes: 1 (bit0), 2 (bit1), 3 (bit0+bit1)
TRAIN_CODES = [1, 2, 3]   # cycles through all bit0/bit1 combinations

def test_train():
    """Cycle through codes 1→2→3 (bits 0 and 1 only), 20 ms pulse every 500 ms.
    Bit 2 is always high on the amplifier side — ignored here.
    Press Ctrl+C to stop.
    """
    print(SEP)
    print("TRIGGER TRAIN  (Ctrl+C to stop)")
    print(f"  Port     : {SERIAL_PORT}")
    print(f"  Codes    : {TRAIN_CODES}  (bit0=1, bit1=2, both=3)")
    print(f"  Pulse    : {int(TRAIN_PULSE_MS*1000)} ms")
    print(f"  Interval : {int(TRAIN_INTERVAL_S*1000)} ms")
    print()

    try:
        import serial
    except ImportError:
        print("  ERROR: pyserial not installed — run:  pip install pyserial")
        return False

    try:
        ser = serial.Serial(SERIAL_PORT, baudrate=BAUDRATE, timeout=1)
    except serial.SerialException as e:
        print(f"  ERROR: {e}")
        return False

    count = 0
    try:
        while True:
            code = TRAIN_CODES[count % len(TRAIN_CODES)]
            ser.write(bytes([code]))
            time.sleep(TRAIN_PULSE_MS)
            ser.write(bytes([0]))
            count += 1
            bvcode = code | 0b00000100   # bit2 always high on amplifier → offset +4
            print(
                f"  [{count:4d}]"
                f"  sent=0x{code:02X} ({code:3d})  binary={code:08b}"
                f"  → BrainVision expects  S {bvcode}",
                flush=True
            )
            time.sleep(TRAIN_INTERVAL_S - TRAIN_PULSE_MS)
    except KeyboardInterrupt:
        ser.write(bytes([0]))  # ensure reset on exit
        ser.close()
        print(f"\n  Stopped after {count} triggers.")
        return True


# ── LPT train ────────────────────────────────────────────────────────────────
LPT_TRAIN_ADDRESS = 0x3FF0   # LPT2 — the active AX99100 port

def test_lpt_train():
    """Repeated LPT pulses via inpoutx64.dll at 0x3FF0, 20 ms pulse every 500 ms.
    Watch trigger box LED and BrainVision TRIG channel.  Ctrl+C to stop.
    """
    print(SEP)
    print("LPT TRAIN  (Ctrl+C to stop)")
    print(f"  LPT address : 0x{LPT_TRAIN_ADDRESS:04X}")
    print(f"  Codes       : {TRAIN_CODES}  (bit0=1, bit1=2, both=3)")
    print(f"  Pulse       : {int(TRAIN_PULSE_MS*1000)} ms")
    print(f"  Interval    : {int(TRAIN_INTERVAL_S*1000)} ms")
    print(f"  DLL         : {DLL_PATH}")
    print()

    if not DLL_PATH.exists():
        print(f"  ERROR: inpoutx64.dll not found at {DLL_PATH}")
        return False

    try:
        io = ctypes.WinDLL(str(DLL_PATH))
    except OSError as e:
        print(f"  ERROR: could not load DLL: {e}")
        return False

    io.Out32(LPT_TRAIN_ADDRESS, 0)
    count = 0
    try:
        while True:
            code = TRAIN_CODES[count % len(TRAIN_CODES)]
            io.Out32(LPT_TRAIN_ADDRESS, code)
            time.sleep(TRAIN_PULSE_MS)
            io.Out32(LPT_TRAIN_ADDRESS, 0)
            count += 1
            bvcode = code | 0b00000100
            print(
                f"  [{count:4d}]"
                f"  sent=0x{code:02X} ({code:3d})  binary={code:08b}"
                f"  → BrainVision expects  S {bvcode}",
                flush=True,
            )
            time.sleep(TRAIN_INTERVAL_S - TRAIN_PULSE_MS)
    except KeyboardInterrupt:
        io.Out32(LPT_TRAIN_ADDRESS, 0)
        print(f"\n  Stopped after {count} triggers.")
        return True


# ── LPT via Windows driver API ───────────────────────────────────────────────
def test_lpt_winapi():
    """Write trigger bytes to LPT3 via Windows CreateFile/WriteFile.
    This uses the AX99100 driver instead of direct I/O port access,
    bypassing the inpoutx64 limitation with PCIe parallel ports.
    """
    print(SEP)
    print("LPT WINDOWS API TEST")
    print("  Device  : \\\\.\\LPT3")
    print(f"  Trigger : S{TRIGGER_CODE}")
    print()

    import ctypes
    from ctypes import windll, byref, c_ulong, c_void_p, create_string_buffer

    class OVERLAPPED(ctypes.Structure):
        class _U(ctypes.Union):
            class _S(ctypes.Structure):
                _fields_ = [("Offset", c_ulong), ("OffsetHigh", c_ulong)]
            _fields_ = [("s", _S), ("Pointer", c_void_p)]
        _fields_ = [
            ("Internal",     c_void_p),
            ("InternalHigh", c_void_p),
            ("u",            _U),
            ("hEvent",       c_void_p),
        ]

    GENERIC_WRITE        = 0x40000000
    OPEN_EXISTING        = 3
    FILE_FLAG_OVERLAPPED = 0x40000000  # same numeric value, different parameter slot
    WAIT_TIMEOUT_CODE    = 0x102
    ACK_WAIT_MS          = 50

    h = windll.kernel32.CreateFileW(
        r'\\.\LPT3',
        GENERIC_WRITE,
        0, None,
        OPEN_EXISTING,
        FILE_FLAG_OVERLAPPED,
        None,
    )

    if ctypes.c_void_p(h).value == ctypes.c_void_p(-1).value or h == 0:
        err = windll.kernel32.GetLastError()
        print(f"  ERROR: Cannot open \\\\.\\LPT3  (GetLastError={err})")
        print("         Error 2 = port not found, Error 5 = access denied")
        return False

    print(f"  Opened handle={h}  (overlapped mode)")

    hEvent = windll.kernel32.CreateEventW(None, True, False, None)

    def _send(value: int) -> None:
        buf = create_string_buffer(bytes([value]))
        ov  = OVERLAPPED()
        ov.hEvent = hEvent
        windll.kernel32.ResetEvent(hEvent)
        windll.kernel32.WriteFile(h, buf, 1, None, byref(ov))
        result = windll.kernel32.WaitForSingleObject(hEvent, ACK_WAIT_MS)
        if result == WAIT_TIMEOUT_CODE:
            windll.kernel32.CancelIo(h)   # cancel pending ACK wait
        print(f"  byte 0x{value:02X} fired  ({'ACK received' if result == 0 else 'no ACK — cancelled, trigger still sent'})")

    _send(TRIGGER_CODE)
    time.sleep(0.005)
    _send(0)

    windll.kernel32.CloseHandle(hEvent)
    windll.kernel32.CloseHandle(h)
    print()
    print("  Check BrainVision Recorder for S 11 or S 15.")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "both"

    print(SEP)
    print("ANTARES TRIGGER TEST")
    print(SEP)

    results = {}

    if mode == "loopback":
        results["loopback"] = test_loopback()
    elif mode == "train":
        results["train"] = test_train()
    elif mode == "lpt_train":
        results["lpt_train"] = test_lpt_train()
    elif mode == "lpt_readback":
        results["lpt_readback"] = test_lpt_readback()
    elif mode == "lpt_winapi":
        results["lpt_winapi"] = test_lpt_winapi()
    else:
        if mode in ("serial", "both"):
            results["serial"] = test_serial()

        if mode in ("parallel", "both"):
            print()
            results["parallel"] = test_parallel()

    print()
    print(SEP)
    print("SUMMARY")
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  {name:10s}: {status}")
    print(SEP)
    print()
    if any(results.values()):
        print("Check BrainVision Recorder — you should see marker  S 11  in the stream.")


if __name__ == "__main__":
    main()