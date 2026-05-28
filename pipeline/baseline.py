"""Resting-state baseline recording via ANT."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

from .triggers import ParallelTrigger, TRIG_BASELINE_START, TRIG_BASELINE_END


def run_baseline(
    subject_id: str,
    visit: int,
    subjects_dir: Path,
    baseline_duration: float,
    mock_lsl: bool = False,
    mock_fname: str | None = None,
    stream_name: str | None = None,
    stream_source_id: str | None = None,
    on_connected: Callable[[], None] | None = None,
    log_callback: Callable[[str], None] | None = None,
    trigger: ParallelTrigger | None = None,
) -> None:
    """Record a resting-state baseline using ANT's NFRealtime.

    Initialises an ``ANT.NFRealtime`` recorder for the BIDS session
    ``v<visit>b``, connects to the LSL stream (real or mock), waits 4 seconds
    for the stream to stabilise, optionally fires a hardware trigger, then
    records the continuous EEG for *baseline_duration* seconds.  The raw
    recording is saved to the BIDS tree by ANT automatically.

    Args:
        subject_id: Four-letter subject identifier (e.g. ``"abcd"``).
        visit: Integer visit number.  Determines the BIDS session label
            (``v1b``, ``v2b``, ...).
        subjects_dir: Root directory that contains all ``sub-*`` folders.
        baseline_duration: Duration of the resting-state recording in seconds.
        mock_lsl: If ``True``, replays *mock_fname* via a simulated LSL stream
            instead of connecting to real EEG hardware.
        mock_fname: Path to a MNE-readable file (e.g. ``.fif``) used as the
            source for mock streaming.  Required when *mock_lsl* is ``True``.
        stream_name: LSL stream name to connect to (e.g. ``"BrainVision RDA"``).
            Passed directly to ``NFRealtime.connect_to_lsl()``.
        stream_source_id: LSL source identifier string.  Passed directly to
            ``NFRealtime.connect_to_lsl()``.
        on_connected: Optional zero-argument callable invoked immediately after
            the LSL connection is established.  Used by the GUI to signal rspv
            to show the fixation cross.
        log_callback: Optional callable that accepts a string, used to forward
            log messages to the operator GUI.
        trigger: Optional ``ParallelTrigger`` or ``SerialTrigger`` instance.
            When provided, sends ``TRIG_BASELINE_START`` (10) at recording
            start and ``TRIG_BASELINE_END`` (11) at recording end.
    """
    from ant import NFRealtime

    def _log(msg: str) -> None:
        logging.info(msg)
        if log_callback:
            log_callback(msg)

    session = f"v{visit}b"  # BIDS session label: v1b, v2b, ...

    _log(f"Initialising ANT baseline recorder (session={session}) ...")
    nf = NFRealtime(
        subject_id=subject_id,
        session=session,
        subjects_dir=str(subjects_dir),
        montage="easycap-M1",
        mri=False,
        artifact_correction=False,
        verbose=False,
    )

    _log("Connecting to LSL stream ...")
    nf.connect_to_lsl(
        mock_lsl=mock_lsl, fname=mock_fname,
        stream_name=stream_name, stream_source_id=stream_source_id,
    )
    if on_connected:
        on_connected()
    _log("Connected. Waiting 4 s for stream to stabilise ...")
    time.sleep(4)

    _log(f"Recording baseline ({baseline_duration} s) ...")
    if trigger:
        _log("Trigger: BASELINE_START (10)")
        trigger.send(TRIG_BASELINE_START)
    nf.record_baseline(baseline_duration=baseline_duration)
    if trigger:
        _log("Trigger: BASELINE_END (11)")
        trigger.send(TRIG_BASELINE_END)
    _log("Baseline recording finished.")
