"""Personalized NF session: protocol setup, block scheduling, ANT integration."""
from __future__ import annotations

import csv
import json
import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import yaml

from .triggers import ParallelTrigger, TRIG_REST_START, TRIG_NF_START, TRIG_SESSION_END


# ---------------------------------------------------------------------------
# Band map used across antares
# ---------------------------------------------------------------------------

BAND_MAP: dict[str, list[float]] = {
    "delta":   [1,    6],
    "theta":   [6.5,  8.5],
    "alpha_0": [8.5,  12.5],
    "alpha_1": [8.5,  10.5],
    "alpha_2": [10.5, 12.5],
    "beta_0":  [12.5, 30],
    "beta_1":  [12.5, 18.5],
    "beta_2":  [18.5, 21],
    "beta_3":  [21,   30],
    "gamma":   [30,   40],
}


# ---------------------------------------------------------------------------
# Block scheduler
# ---------------------------------------------------------------------------

class BlockScheduler:
    """Drives a rest / NF block sequence in a background daemon thread.

    Each call to ``start()`` launches a thread that alternates between a
    rest phase and an NF phase for *n_blocks* iterations.  The order of the
    two phases within each block pair is controlled by *first_phase*.

    A thread-safe ``threading.Event`` (``_is_nf``) is set during NF phases so
    that downstream consumers (e.g. ``RspvOSCSender``) can gate OSC output
    without polling.  A timestamp log of every completed phase interval is
    accumulated in ``_block_log`` and accessible via ``get_block_log()``.

    Args:
        n_blocks: Number of block pairs (rest + NF) to run.
        rest_duration: Duration of each rest phase in seconds.
        nf_duration: Duration of each NF phase in seconds.
        on_block_change: Optional callback ``(block_index: int, phase: str) ->
            None`` invoked at the start of every phase transition.  *phase* is
            ``"rest"`` or ``"nf"``.
        first_phase: Which phase starts each block pair.  Use ``"nf"``
            (default) for threshold/staircase protocols, or ``"rest"`` for
            z-score protocols so the EEG can return to a neutral state before
            the first reward window.
    """

    def __init__(
        self,
        n_blocks: int,
        rest_duration: float,
        nf_duration: float,
        on_block_change: Callable[[int, str], None] | None = None,
        first_phase: str = "nf",
    ) -> None:
        self.n_blocks = n_blocks
        self.rest_duration = rest_duration
        self.nf_duration = nf_duration
        self.on_block_change = on_block_change or (lambda *_: None)
        self._first_phase = first_phase if first_phase in ("nf", "rest") else "nf"
        self._is_nf = threading.Event()
        self._stop = threading.Event()
        # Block timestamp log: list of {"block", "phase", "t_start", "t_end"}
        self._block_log: list[dict] = []
        self._block_start: float = 0.0

    def start(self) -> None:
        """Start the block schedule in a daemon thread."""
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self) -> None:
        """Signal the scheduler to stop after the current phase and unblock any waiter."""
        self._stop.set()
        self._is_nf.set()  # unblock any waiter

    @property
    def is_nf_active(self) -> bool:
        """Return ``True`` when the scheduler is currently in an NF phase."""
        return self._is_nf.is_set()

    def get_block_log(self) -> list[dict]:
        """Return a copy of the block timestamp log (populated after run completes).

        Returns:
            list[dict]: Each entry has keys ``block`` (int), ``phase`` (str),
            ``t_start`` (float, ``time.time()`` epoch), ``t_end`` (float),
            and ``duration_s`` (float).
        """
        return list(self._block_log)

    def _run(self) -> None:
        """Internal: iterate over blocks and delegate each phase to ``_run_phase``."""
        second_phase = "rest" if self._first_phase == "nf" else "nf"
        for block in range(self.n_blocks):
            if self._stop.is_set():
                break
            self._run_phase(block, self._first_phase)
            if self._stop.is_set():
                break
            self._run_phase(block, second_phase)

    def _run_phase(self, block: int, phase: str) -> None:
        """Internal: run a single phase, update the NF event flag, and record timing."""
        duration = self.nf_duration if phase == "nf" else self.rest_duration
        if phase == "nf":
            self._is_nf.set()
        else:
            self._is_nf.clear()
        self.on_block_change(block, phase)
        self._block_start = time.time()
        self._interruptible_sleep(duration)
        self._block_log.append({
            "block": block, "phase": phase,
            "t_start": self._block_start,
            "t_end":   time.time(),
            "duration_s": duration,
        })

    def _interruptible_sleep(self, secs: float) -> None:
        """Internal: sleep for *secs* seconds but wake early if ``_stop`` is set."""
        deadline = time.monotonic() + secs
        while not self._stop.is_set() and time.monotonic() < deadline:
            time.sleep(0.1)


# ---------------------------------------------------------------------------
# Block-aware OSC wrapper
# ---------------------------------------------------------------------------

class BlockAwareOSCSender:
    """Wraps an OSCSender and silences it during rest blocks.

    All ``send*`` calls are forwarded to the underlying *osc_sender* only while
    ``scheduler.is_nf_active`` is ``True``.  Calls during rest phases are
    silently discarded.

    Args:
        osc_sender: An ANT ``OSCSender`` instance (or compatible object).
        scheduler: The active ``BlockScheduler`` whose ``is_nf_active``
            property gates all outgoing OSC messages.
    """

    def __init__(self, osc_sender, scheduler: BlockScheduler) -> None:
        self._sender = osc_sender
        self._scheduler = scheduler

    def send(self, modality: str, value: float) -> None:
        """Forward a single-value OSC message if the NF phase is active."""
        if self._scheduler.is_nf_active:
            self._sender.send(modality, value)

    def send_all(self, modalities, values) -> None:
        """Forward a multi-value OSC message if the NF phase is active."""
        if self._scheduler.is_nf_active:
            self._sender.send_all(modalities, values)

    def send_raw(self, address: str, *args) -> None:
        """Forward a raw-address OSC message if the NF phase is active."""
        if self._scheduler.is_nf_active:
            self._sender.send_raw(address, *args)


# ---------------------------------------------------------------------------
# rspv OSC bridge
# ---------------------------------------------------------------------------

class RspvOSCSender:
    """Bridges ANT's OSC output to rspv's /rspv address format.

    ANT calls ``send_all(mods, vals)`` with raw EEG feature values.
    rspv's SignalHandler expects OSC messages at ``/rspv`` with the layout::

        /rspv  float  float  float
               min    max    value

    *value* is direction-corrected before sending:
    - direction="down" (decrease feature): value sent as-is.
    - direction="up"   (increase feature): value is mirrored about the
      rolling midpoint so that higher raw feature -> higher reward score.

    Every incoming window is logged (both rest and NF phases) so that the
    CSV provides a continuous record.  OSC output to rspv is still gated to
    NF blocks only.  Each CSV row carries a ``phase`` and ``block`` column
    that are updated via ``update_phase()`` on every block transition.
    """

    def __init__(
        self,
        osc_sender,
        scheduler: BlockScheduler,
        direction: str = "down",
        history_len: int = 60,
        log_path: Path | None = None,
    ) -> None:
        """Initialise the rspv OSC bridge.

        Args:
            osc_sender: Underlying ANT ``OSCSender`` that owns the UDP socket.
            scheduler: ``BlockScheduler`` whose ``is_nf_active`` flag gates
                OSC output to rspv.
            direction: ``"down"`` to reward decreasing the feature (value sent
                as-is); ``"up"`` to reward increasing it (value mirrored about
                the rolling midpoint before sending).
            history_len: Rolling window length (in samples) used to compute
                the adaptive min/max sent alongside each value.
            log_path: If provided, a CSV is opened at this path and every
                incoming window is appended with columns ``elapsed_s``,
                ``raw_value``, ``rolling_min``, ``rolling_max``,
                ``direction_corrected``, ``direction``, ``phase``, ``block``.
        """
        self._sender      = osc_sender
        self._scheduler   = scheduler
        self._direction   = direction.lower()
        self._history: list[float] = []
        self._history_len = history_len
        self._min = 0.0
        self._max = 1.0
        self._t0  = time.time()
        self._phase = "rest"
        self._block = 0

        self._log_file   = None
        self._csv_writer = None
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file   = open(log_path, "w", newline="")
            self._csv_writer = csv.writer(self._log_file)
            self._csv_writer.writerow(
                ["elapsed_s", "raw_value", "rolling_min", "rolling_max",
                 "direction_corrected", "direction", "phase", "block"]
            )

    # Public interface mirrors ANT's OSCSender ---------------------------------

    def update_phase(self, phase: str, block: int) -> None:
        """Called on each block transition so the CSV reflects the current phase."""
        self._phase = phase
        self._block = block

    def send(self, modality: str, value: float) -> None:
        """Process a single feature value from ANT and forward to rspv.

        Args:
            modality: ANT modality label (unused; present for API compatibility).
            value: Raw EEG feature value for the current window.
        """
        self._process(float(value))

    def send_all(self, modalities, values) -> None:
        """Process the first feature value in *values* from ANT.

        Args:
            modalities: Sequence of modality labels (unused).
            values: Sequence of raw feature values; only the first is used.
        """
        if values:
            self._process(float(values[0]))

    def send_raw(self, address: str, *args) -> None:
        """Forward a raw OSC message to rspv, gated to NF phases only.

        Args:
            address: OSC address string.
            *args: OSC payload arguments forwarded verbatim.
        """
        if self._scheduler.is_nf_active:
            self._sender.send_raw(address, *args)

    def send_phase(self, phase: str) -> None:
        """Notify rspv of a phase transition (always sent, bypasses NF gate)."""
        flag = 1 if phase == "nf" else 0
        self._sender.send_raw("/rspv_ctrl", flag)

    def close(self) -> None:
        """Flush and close the signal log CSV."""
        if self._log_file is not None:
            self._log_file.flush()
            self._log_file.close()
            self._log_file = None

    # Internal -----------------------------------------------------------------

    def _process(self, value: float) -> None:
        """Update rolling stats, log the window, and (during NF only) send OSC."""
        self._history.append(value)
        if len(self._history) > self._history_len:
            self._history.pop(0)
        if len(self._history) >= 5:
            self._min = min(self._history)
            self._max = max(self._history)
            if self._max <= self._min:
                self._max = self._min + 1.0

        if self._direction == "up":
            corrected = self._min + (self._max - value)
        else:
            corrected = value

        if self._csv_writer is not None:
            elapsed = time.time() - self._t0
            self._csv_writer.writerow(
                [f"{elapsed:.3f}", f"{value:.6f}",
                 f"{self._min:.6f}", f"{self._max:.6f}",
                 f"{corrected:.6f}", self._direction,
                 self._phase, self._block]
            )

        if self._scheduler.is_nf_active:
            self._sender.send_raw("/rspv", self._min, self._max, corrected)


# ---------------------------------------------------------------------------
# Protocol factory
# ---------------------------------------------------------------------------

def create_protocol(
    protocol_name: str,
    direction: str,
    zscore_threshold: float = 0.5,
    warmup_windows: int = 20,
    threshold_value: float = 0.0,
):
    """Instantiate an ANT feedback protocol object from a name string.

    Args:
        protocol_name: One of ``"zscore"``, ``"threshold"``, ``"staircase"``,
            or ``"sham"``.
        direction: ``"up"`` (reward increasing the feature) or ``"down"``
            (reward decreasing it).  Derived from the sign of the normative
            Z-score.
        zscore_threshold: Reward threshold for the Z-score protocol.
        warmup_windows: Number of windows used to estimate the rolling baseline
            before the Z-score protocol starts emitting feedback.
        threshold_value: Fixed threshold value used by the ``"threshold"``
            protocol only.

    Returns:
        An ANT protocol instance (``ZScoreProtocol``, ``ThresholdProtocol``,
        ``UpDownStaircaseProtocol``, or ``ShamProtocol``).

    Raises:
        ValueError: If *protocol_name* is not one of the recognised strings.
    """
    from ant.protocols import (
        ZScoreProtocol,
        ThresholdProtocol,
        UpDownStaircaseProtocol,
        ShamProtocol,
    )

    name = protocol_name.lower()
    if name == "zscore":
        return ZScoreProtocol(
            direction=direction,
            warmup_windows=warmup_windows,
            zscore_threshold=zscore_threshold,
        )
    elif name == "threshold":
        return ThresholdProtocol(threshold=threshold_value, direction=direction)
    elif name == "staircase":
        inner = ZScoreProtocol(direction=direction, warmup_windows=warmup_windows)
        return UpDownStaircaseProtocol(inner_protocol=inner)
    elif name == "sham":
        inner = ZScoreProtocol(direction=direction, warmup_windows=warmup_windows)
        return ShamProtocol(inner_protocol=inner)
    else:
        raise ValueError(f"Unknown protocol: {protocol_name!r}")


# ---------------------------------------------------------------------------
# Feature-name → ANT modality parser
# ---------------------------------------------------------------------------

def parse_feature_name(feature_name: str, feature_type: str) -> dict:
    """Extract ANT modality parameters from a ranked-feature name string.

    Parses the *feature_name* and *feature_type* produced by ``rank_features``
    and returns a parameter dict suitable for building the ``NF_modality``
    section of the ANT YAML config.

    Args:
        feature_name: Full feature name, e.g. ``"Cz_alpha_0"``,
            ``"pericalcarine-lh_alpha_0"``, or
            ``"Ch1_vs_Ch2_alpha_0_coh"``.
        feature_type: One of ``"power_sensor"``, ``"power_source"``,
            ``"conn_sensor"``, or ``"conn_source"``.

    Returns:
        dict containing a subset of: ``band`` (str), ``frange`` (list[float]),
        ``channel`` (str), ``brain_label`` (str), ``channel_1`` (str),
        ``channel_2`` (str), ``brain_label_1`` (str), ``brain_label_2`` (str),
        ``method`` (str), ``modality`` (str).
    """
    params: dict = {}

    for band_name, frange in BAND_MAP.items():
        if band_name in feature_name:
            params["band"] = band_name
            params["frange"] = frange
            break

    if feature_type == "power_sensor":
        params["channel"] = feature_name.split("_")[0]
        params["modality"] = "sensor_power"

    elif feature_type == "power_source":
        params["brain_label"] = feature_name.split("_")[0]
        params["modality"] = "source_power"

    elif feature_type == "conn_sensor":
        m = re.match(r"(.+?)_vs_(.+?)_(.+?)_(.+)", feature_name)
        if m:
            params.update(
                channel_1=m.group(1),
                channel_2=m.group(2),
                method=m.group(4),
                modality="sensor_connectivity",
            )

    elif feature_type == "conn_source":
        m = re.match(r"(.+?)_vs_(.+?)_(.+?)_(.+)", feature_name)
        if m:
            params.update(
                brain_label_1=m.group(1),
                brain_label_2=m.group(2),
                method=m.group(4),
                modality="source_connectivity",
            )

    return params


# ---------------------------------------------------------------------------
# YAML config generator
# ---------------------------------------------------------------------------

def create_nf_yaml(
    subject_id: str,
    visit: int,
    subjects_dir: Path,
    template_yaml_path: Path,
) -> Path:
    """Generate a personalised ANT config YAML from the selection report JSON.

    Reads the ``selection_report_v<visit>.json`` written by ``rank_features``,
    calls ``parse_feature_name`` to convert the selected feature into ANT
    ``NF_modality`` parameters, merges them into the template YAML (preserving
    all ANT-specific hardware and filter settings), and writes the result to::

        <subjects_dir>/sub-<id>/nf_selection/nf_config_v<visit>.yml

    List values are serialised in YAML flow style (inline) to match ANT's
    expected format.

    Args:
        subject_id: Four-letter subject identifier.
        visit: Integer visit number.
        subjects_dir: Root directory containing all ``sub-*`` folders.
        template_yaml_path: Path to the master ``config_master.yml`` that
            provides all ANT hardware and signal-processing defaults.

    Returns:
        Path to the generated YAML config file.

    Raises:
        FileNotFoundError: If the selection report JSON for *visit* does not exist.
    """
    json_path = subjects_dir / f"sub-{subject_id}" / "nf_selection" / f"selection_report_v{visit}.json"
    if not json_path.exists():
        raise FileNotFoundError(f"Selection report not found: {json_path}")

    with open(json_path) as fh:
        report = json.load(fh)

    feature_name = report["selected_feature"]["feature_name"]
    feature_type = report["selected_feature"]["feature_type"]
    params = parse_feature_name(feature_name, feature_type)

    with open(template_yaml_path) as fh:
        base = yaml.safe_load(fh) or {}

    modality = params.get("modality", "sensor_power")

    # Build only the NF_modality section, then merge into base so all
    # ANT-specific fields (filters, amplifier, reference, ...) are preserved.
    if modality == "sensor_power":
        nf_modality = {"sensor_power": {
            "frange": params.get("frange", [8, 13]),
            "method": "welch",
            "relative": False,
            "selected_channel": params.get("channel"),
            "selected_feature": feature_name,
        }}
    elif modality == "source_power":
        nf_modality = {"source_power": {
            "frange": params.get("frange", [8, 13]),
            "brain_label": params.get("brain_label", "pericalcarine-lh"),
            "atlas": "aparc",
            "method": "dSPM",
            "selected_feature": feature_name,
        }}
    elif modality == "sensor_connectivity":
        nf_modality = {"sensor_connectivity": {
            "frange": params.get("frange", [8, 13]),
            "channels": [[params.get("channel_1"), params.get("channel_2")]],
            "method": params.get("method", "coh"),
            "mode": "cwt_morlet",
            "selected_feature": feature_name,
        }}
    elif modality == "source_connectivity":
        nf_modality = {"source_connectivity": {
            "frange": params.get("frange", [8, 13]),
            "brain_label_1": params.get("brain_label_1", "transversetemporal-lh"),
            "brain_label_2": params.get("brain_label_2", "transversetemporal-rh"),
            "atlas": "aparc",
            "method": params.get("method", "coh"),
            "mode": "cwt_morlet",
            "selected_feature": feature_name,
        }}
    else:
        nf_modality = {}

    # Merge: base provides all ANT settings; NF_modality is overwritten.
    nf_config = {**base, "NF_modality": nf_modality}

    out_path = subjects_dir / f"sub-{subject_id}" / "nf_selection" / f"nf_config_v{visit}.yml"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    class _FlowList(list):
        pass

    def _rep(dumper, data):
        return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)

    yaml.add_representer(_FlowList, _rep)

    def _to_flow(obj):
        if isinstance(obj, dict):
            return {k: _to_flow(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return _FlowList(_to_flow(i) for i in obj)
        return obj

    with open(out_path, "w") as fh:
        yaml.dump(_to_flow(nf_config), fh, default_flow_style=False, sort_keys=False)

    logging.info("NF config written to %s", out_path)
    return out_path


# ---------------------------------------------------------------------------
# Session metadata
# ---------------------------------------------------------------------------

def save_session_metadata(
    subject_id: str,
    visit: int,
    subjects_dir: Path,
    **params,
) -> Path:
    """Save session parameters and an ISO timestamp to a JSON metadata file.

    Writes all *params* keyword arguments plus ``subject_id``, ``visit``, and
    ``timestamp`` to::

        <subjects_dir>/sub-<id>/ses-v<visit>m/session_metadata_v<visit>.json

    Args:
        subject_id: Four-letter subject identifier.
        visit: Integer visit number.
        subjects_dir: Root directory containing all ``sub-*`` folders.
        **params: Arbitrary keyword arguments serialised into the metadata
            dict (e.g. ``modality``, ``protocol``, ``n_blocks``, etc.).

    Returns:
        Path to the saved JSON metadata file.
    """
    out_dir = subjects_dir / f"sub-{subject_id}" / f"ses-v{visit}m"
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "subject_id": subject_id,
        "visit": visit,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        **params,
    }
    path = out_dir / f"session_metadata_v{visit}.json"
    with open(path, "w") as fh:
        json.dump(meta, fh, indent=2, default=str)
    logging.info("Session metadata saved → %s", path)
    return path


# ---------------------------------------------------------------------------
# Post-session beh annotation
# ---------------------------------------------------------------------------

def _annotate_beh_data(
    session_dir: Path,
    block_log: list[dict],
    t_session_start: float,
    log: "Callable[[str], None]",
) -> None:
    """Add ``phase`` and ``block`` columns to ANT's ``_beh`` output files.

    ANT records feature values continuously throughout the session.  This
    function uses the ``BlockScheduler`` timestamp log to retroactively label
    every data row as either ``"rest"`` or ``"nf"`` and to assign the
    corresponding block index.  Both JSON list format (``*_beh.json``) and
    BIDS TSV format (``*_beh.tsv``) are supported; files without an ``onset``
    column are skipped.

    Args:
        session_dir: BIDS session directory (e.g.
            ``<subjects_dir>/sub-<id>/ses-v<visit>m/``).  Searched
            recursively for ``*_beh.json`` and ``*_beh.tsv`` files.
        block_log: List of block timing dicts as returned by
            ``BlockScheduler.get_block_log()``.  Each entry must have
            ``t_start``, ``t_end``, ``phase``, and ``block`` keys.
        t_session_start: Absolute ``time.time()`` value recorded at the
            moment ``nf.record_main`` was called, used to convert relative
            ``onset`` values to absolute epoch times for block lookup.
        log: Callable that accepts a string; used to forward status messages
            to the operator GUI.
    """

    def _lookup(onset_rel: float) -> tuple[str, int]:
        abs_t = t_session_start + float(onset_rel)
        for entry in block_log:
            if entry["t_start"] <= abs_t <= entry["t_end"]:
                return entry["phase"], int(entry["block"])
        return "unknown", -1

    # JSON list format — each element is a dict with an "onset" key
    for beh_path in sorted(session_dir.glob("**/*_beh.json")):
        try:
            with open(beh_path) as fh:
                data = json.load(fh)
            if not isinstance(data, list) or not data or "onset" not in data[0]:
                continue
            for row in data:
                row["phase"], row["block"] = _lookup(row["onset"])
            with open(beh_path, "w") as fh:
                json.dump(data, fh, indent=2)
            log(f"[beh] Annotated {beh_path.name} with phase/block labels.")
        except Exception as exc:
            log(f"[beh] Could not annotate {beh_path.name}: {exc}")

    # TSV format (BIDS *_beh.tsv)
    try:
        import pandas as pd
        for tsv_path in sorted(session_dir.glob("**/*_beh.tsv")):
            try:
                df = pd.read_csv(tsv_path, sep="\t")
                if "onset" not in df.columns:
                    continue
                results = [_lookup(t) for t in df["onset"]]
                df["phase"] = [r[0] for r in results]
                df["block"] = [r[1] for r in results]
                df.to_csv(tsv_path, sep="\t", index=False)
                log(f"[beh] Annotated {tsv_path.name} with phase/block labels.")
            except Exception as exc:
                log(f"[beh] Could not annotate {tsv_path.name}: {exc}")
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Main NF session runner
# ---------------------------------------------------------------------------

def run_nf_session(
    subject_id: str,
    visit: int,
    subjects_dir: Path,
    template_yaml_path: Path,
    protocol_name: str = "zscore",
    zscore_threshold: float = 0.5,
    warmup_windows: int = 20,
    threshold_value: float = 0.0,
    n_blocks: int = 4,
    rest_duration: float = 30.0,
    nf_duration: float = 120.0,
    osc_host: str = "127.0.0.1",
    osc_port: int = 5005,
    mock_lsl: bool = False,
    mock_fname: str | None = None,
    stream_name: str | None = None,
    stream_source_id: str | None = None,
    on_block_change: Callable[[int, str], None] | None = None,
    log_callback: Callable[[str], None] | None = None,
    first_phase: str | None = None,
    trigger: ParallelTrigger | None = None,
) -> None:
    """Run the personalised closed-loop neurofeedback session with rest/NF blocks.

    Builds a personalised ANT YAML config from the selection report, determines
    the NF training direction from the normative Z-score sign, creates the ANT
    feedback protocol, connects to the LSL stream, launches a
    ``BlockScheduler`` daemon thread, and calls ``nf.record_main`` for the
    total session duration.  After the session, the block timestamp log is
    saved as a CSV, a hardware trigger is sent if provided, ANT's BIDS output
    is saved, and the behavioural data files are annotated with phase/block
    labels.

    Args:
        subject_id: Four-letter subject identifier.
        visit: Integer visit number.
        subjects_dir: Root directory containing all ``sub-*`` folders.
        template_yaml_path: Path to the master YAML config used as a template
            for personalised YAML generation.
        protocol_name: One of ``"zscore"`` (default), ``"threshold"``,
            ``"staircase"``, or ``"sham"``.
        zscore_threshold: Reward threshold for the Z-score protocol.
        warmup_windows: Number of windows before the Z-score baseline is
            considered initialised.
        threshold_value: Fixed threshold for the ``"threshold"`` protocol.
        n_blocks: Number of rest+NF block pairs.
        rest_duration: Seconds per rest phase.
        nf_duration: Seconds per NF phase.
        osc_host: OSC target hostname or IP (rspv).
        osc_port: OSC target port.
        mock_lsl: If ``True``, replay *mock_fname* instead of connecting to
            real hardware.
        mock_fname: Path to a .fif file for mock LSL streaming.
        stream_name: LSL stream name to connect to.
        stream_source_id: LSL source identifier string.
        on_block_change: Optional ``(block_index: int, phase: str) -> None``
            callback invoked at every block transition.  Used by the GUI to
            update the operator block label.
        log_callback: Optional callable for GUI log forwarding.
        first_phase: Override which phase starts each block: ``"nf"`` or
            ``"rest"``.  If ``None`` (default), auto-selected: z-score uses
            ``"rest"`` so the EEG can return to a neutral baseline before the
            first reward window; all other protocols use ``"nf"``.
        trigger: Optional ``ParallelTrigger`` or ``SerialTrigger`` instance.
            When provided, sends coded TTL pulses at rest/NF transitions and
            session end.

    Raises:
        RuntimeError: If the LSL stream reports ``sfreq <= 0`` after connection,
            indicating the EEG stream is not running correctly.
    """
    from ant import NFRealtime
    from ant.osc import OSCSender

    def _log(msg: str) -> None:
        logging.info(msg)
        if log_callback:
            log_callback(msg)

    # -- Build personalised YAML -----------------------------------------
    _log("Building personalised NF config ...")
    yaml_path = create_nf_yaml(subject_id, visit, subjects_dir, template_yaml_path)

    with open(yaml_path) as fh:
        yaml_data = yaml.safe_load(fh)

    modality = list(yaml_data["NF_modality"].keys())[0]
    feature_name = yaml_data["NF_modality"][modality].get("selected_feature", "")
    _log(f"NF modality: {modality} | feature: {feature_name}")

    # -- Determine NF direction from z-score sign --------------------------
    ranking_csv = subjects_dir / f"sub-{subject_id}" / "nf_selection" / f"feature_ranking_v{visit}.csv"
    import pandas as pd
    if feature_name and ranking_csv.exists():
        df_ranks = pd.read_csv(ranking_csv)
        rows = df_ranks[df_ranks["feature_name"] == feature_name]["z_score"]
        z = float(rows.values[0]) if len(rows) else 0.0
    else:
        z = 0.0

    direction = "down" if z > 0 else "up"
    _log(f"Normative z-score = {z:.2f} -> training direction: {direction}")

    # -- Build protocol ---------------------------------------------------
    protocol = create_protocol(
        protocol_name,
        direction=direction,
        zscore_threshold=zscore_threshold,
        warmup_windows=warmup_windows,
        threshold_value=threshold_value,
    )

    # Auto-select first phase when caller didn't specify.
    # Z-score: start with REST so the EEG settles before the first reward window.
    # All other protocols: start with NF (fixed threshold / sham don't depend on
    # EEG state at block onset, so jumping straight into feedback is fine).
    _first_phase: str = first_phase if first_phase is not None else (
        "rest" if protocol_name.lower() == "zscore" else "nf"
    )
    _log(f"Protocol: {protocol_name} ({direction}) | first phase: {_first_phase}")

    # -- ANT setup --------------------------------------------------------
    session = f"v{visit}m"
    _log(f"Initialising ANT main recorder (session={session}) ...")
    nf = NFRealtime(
        subject_id=subject_id,
        session=session,
        subjects_dir=str(subjects_dir),
        montage="easycap-M1",
        mri=False,
        artifact_correction=False,
        config_file=str(yaml_path),
        verbose=False,
    )

    _log("Connecting to LSL ...")
    nf.connect_to_lsl(
        mock_lsl=mock_lsl, fname=mock_fname,
        stream_name=stream_name, stream_source_id=stream_source_id,
    )
    time.sleep(2)
    sfreq = nf.rec_info["sfreq"]
    if sfreq <= 0:
        raise RuntimeError(
            f"LSL stream reported sfreq={sfreq} Hz. "
            "Check that the correct EEG stream is running and try again."
        )
    _log(f"Connected - stream sfreq: {sfreq:.0f} Hz.")

    # -- Session metadata -------------------------------------------------
    save_session_metadata(
        subject_id=subject_id,
        visit=visit,
        subjects_dir=subjects_dir,
        modality=modality,
        feature_name=feature_name,
        protocol=protocol_name,
        direction=direction,
        n_blocks=n_blocks,
        rest_duration=rest_duration,
        nf_duration=nf_duration,
        zscore_threshold=zscore_threshold,
        warmup_windows=warmup_windows,
        osc_host=osc_host,
        osc_port=osc_port,
    )

    # -- OSC sender: bridges ANT output → rspv /rspv format ---------------
    osc_sender_raw = OSCSender(host=osc_host, port=osc_port)
    total_duration = n_blocks * (rest_duration + nf_duration)

    nf_log_path = (
        subjects_dir
        / f"sub-{subject_id}"
        / f"ses-v{visit}m"
        / f"nf_signal_log_v{visit}.csv"
    )

    scheduler = BlockScheduler(
        n_blocks=n_blocks,
        rest_duration=rest_duration,
        nf_duration=nf_duration,
        on_block_change=on_block_change,
        first_phase=_first_phase,
    )
    block_osc = RspvOSCSender(
        osc_sender_raw,
        scheduler,
        direction=direction,
        log_path=nf_log_path,
    )

    # Wrap on_block_change so every phase transition also sends a control
    # message to rspv and keeps the CSV phase/block columns up to date.
    _gui_callback = scheduler.on_block_change
    def _on_block_change(block_idx: int, phase: str) -> None:
        block_osc.send_phase(phase)
        block_osc.update_phase(phase, block_idx)
        if trigger:
            code = TRIG_NF_START if phase == "nf" else TRIG_REST_START
            _log(f"Trigger: {'NF_START (30)' if phase == 'nf' else 'REST_START (20)'} block {block_idx}")
            trigger.send(code)
        _gui_callback(block_idx, phase)
    scheduler.on_block_change = _on_block_change

    # -- Launch block scheduler just before record_main -------------------
    _log(
        f"Starting {n_blocks} blocks "
        f"({rest_duration}s rest + {nf_duration}s NF each, "
        f"total {total_duration}s) - direction: {direction} ..."
    )
    t_session_start = time.time()
    scheduler.start()

    try:
        nf.record_main(
            duration=total_duration,
            modality=modality,
            winsize=1.0,
            estimate_delays=False,
            show_raw_signal=False,
            show_nf_signal=False,
            show_topo=False,
            show_brain_activation=False,
            osc_sender=block_osc,
            protocol=protocol,
            signal_smoothing=0.25,
            display_smoothing=0.3,
            verbose=False,
        )
    finally:
        scheduler.stop()
        block_osc.close()

    # -- Save block timestamp log -----------------------------------------
    block_log = scheduler.get_block_log()
    if block_log:
        import pandas as pd
        block_log_path = (
            subjects_dir
            / f"sub-{subject_id}"
            / f"ses-v{visit}m"
            / f"block_log_v{visit}.csv"
        )
        pd.DataFrame(block_log).to_csv(block_log_path, index=False)
        _log(f"Block log saved: {block_log_path.name}")

    if trigger:
        trigger.send(TRIG_SESSION_END)
    nf.save(bids_tsv=True)
    _log(f"Session saved. NF signal log: {nf_log_path.name}")

    # Annotate ANT's _beh output with phase/block labels from the block log.
    session_dir = subjects_dir / f"sub-{subject_id}" / f"ses-v{visit}m"
    _annotate_beh_data(session_dir, block_log, t_session_start, _log)
