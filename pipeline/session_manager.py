"""Multi-session adaptive NF target selection.

Session 1   : Full baseline (config duration) ->full analysis ->primary + 3 backups.
Sessions 2-4: Quick baseline (3 min) ->SNR + ``|z|`` check ->switch to backup if needed.
Session 5   : Mid-protocol evaluation (5 min) ->full re-ranking ->decision tree.
Sessions > 5: Quick baseline (2 min) ->locked feature, no switching.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log(msg: str, cb: Callable[[str], None] | None = None) -> None:
    """Log *msg* via the standard logger and optionally forward to a GUI callback.

    Args:
        msg: The message string to log.
        cb: Optional callable that accepts a single string argument.
    """
    logging.info(msg)
    if cb:
        cb(msg)


def _clean_json(obj):
    """Recursively convert numpy scalars to Python native types for JSON serialisation.

    Traverses dicts and lists recursively.  ``numpy.floating`` and
    ``numpy.integer`` values are converted to ``float``; all other objects are
    returned unchanged.

    Args:
        obj: Any Python object, potentially containing numpy scalars.

    Returns:
        A JSON-serialisable equivalent of *obj*.
    """
    if isinstance(obj, (np.floating, np.integer)):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _clean_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_json(i) for i in obj]
    return obj


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------

class SessionManager:
    """Manages adaptive NF target selection across multiple visits.

    Implements the four-phase adaptive logic used across a tinnitus NF
    protocol:

    - **Visit 1**: Loads the full-analysis selection report produced by
      ``run_full_analysis`` (no further action).
    - **Visits 2-4**: Runs a quick SNR/``|z|`` check on the primary feature;
      falls back to a ranked backup if quality thresholds are not met.
    - **Visit 5**: Triggers a full re-ranking baseline and applies a
      five-rule decision tree to decide whether to maintain or switch.
    - **Visits > 5**: Feature locked — no further switching regardless of
      quality metrics.

    All class-level constants serve as configurable thresholds and can be
    overridden by subclassing or monkey-patching for research experiments.

    Class Attributes:
        QUICK_BASELINE_SECS: Duration of the quick baseline for sessions 2–4
            and > 5 (180 s).
        MID_EVAL_BASELINE_SECS: Duration of the mid-protocol baseline for
            session 5 (300 s).
        MID_EVAL_SESSION: Session number that triggers full re-evaluation (5).
        LOCK_AFTER_SESSION: Session number after which switching is disabled (5).
        SNR_SWITCH_THRESHOLD: SNR floor for keeping the primary feature (1.5).
        Z_MIN_THRESHOLD: Minimum ``|z|`` for keeping a feature viable (1.0).
        SCORE_SWITCH_MARGIN: Minimum relative composite-score improvement
            required to justify a cross-modality switch (0.30 = 30 %).
    """

    QUICK_BASELINE_SECS    = 180.0   # 3 min for sessions 2–4 and > 5
    MID_EVAL_BASELINE_SECS = 300.0   # 5 min for session 5
    MID_EVAL_SESSION       = 5
    LOCK_AFTER_SESSION     = 5

    SNR_SWITCH_THRESHOLD   = 1.5
    Z_MIN_THRESHOLD        = 1.0
    SCORE_SWITCH_MARGIN    = 0.30    # 30 % better score required for cross-modality switch

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_baseline_duration(self, visit: int, full_duration: float) -> float:
        """Return the appropriate baseline recording duration for *visit*.

        Args:
            visit: Integer visit number.
            full_duration: The full baseline duration configured by the
                operator (used only for visit 1).

        Returns:
            float: Seconds to record.  Returns *full_duration* for visit 1,
            ``MID_EVAL_BASELINE_SECS`` for visit 5, and
            ``QUICK_BASELINE_SECS`` for all other visits.
        """
        if visit == 1:
            return full_duration
        if visit == self.MID_EVAL_SESSION:
            return self.MID_EVAL_BASELINE_SECS
        return self.QUICK_BASELINE_SECS

    def prepare_session(
        self,
        subject_id: str,
        visit: int,
        subjects_dir: Path,
        models_dir: Path,
        age: int,
        sex: str,
        site: str = "zuerich",
        log_callback: Callable[[str], None] | None = None,
    ) -> dict:
        """Run pre-session analysis and return the selection report for *visit*.

        For visit 1: loads and returns the report produced by run_full_analysis().
        For visits 2-4: runs a quick SNR/``|z|`` check; switches to backup if needed.
        For visit 5: runs full re-ranking + decision tree.
        For visits > 5: locks to the last confirmed feature; no switching.

        Returns
        -------
        dict
            Selection report with keys ``selected_feature``, ``backup_features``,
            ``session_decision`` (for visits >= 2), etc.

        Raises
        ------
        FileNotFoundError
            If the previous visit's selection report does not exist.
        """
        cb = log_callback

        if visit == 1:
            report = self._load_report(subject_id, visit, subjects_dir)
            if report is None:
                raise FileNotFoundError(
                    "Visit 1 selection report not found. "
                    "Run baseline recording and full analysis first."
                )
            return report

        prev_report = self._load_report(subject_id, visit - 1, subjects_dir)
        if prev_report is None:
            raise FileNotFoundError(
                f"Selection report for visit {visit - 1} not found. "
                f"Complete session {visit - 1} before starting session {visit}."
            )

        primary = prev_report["selected_feature"]
        backups = prev_report.get("backup_features", [])

        # ---- Sessions > LOCK_AFTER_SESSION ->locked -----------------------
        if visit > self.LOCK_AFTER_SESSION:
            _log(
                f"[SessionManager] Visit {visit}: feature locked -"
                f"training {primary['feature_name']} (no further switching).",
                cb,
            )
            decision = {
                "decision": "locked",
                "reason": f"No switching after session {self.LOCK_AFTER_SESSION}.",
                "feature": primary,
            }
            report = {**prev_report, "visit": visit, "session_decision": decision}
            self._save_report(subject_id, visit, subjects_dir, report)
            return report

        # ---- Session 5 ->full re-ranking + decision tree ------------------
        if visit == self.MID_EVAL_SESSION:
            _log(
                "[SessionManager] Session 5: mid-protocol evaluation -"
                "running full re-ranking ...",
                cb,
            )
            from .analysis import run_full_analysis
            run_full_analysis(
                subject_id=subject_id,
                age=age,
                sex=sex,
                visit=visit,
                subjects_dir=subjects_dir,
                models_dir=models_dir,
                site=site,
                log_callback=log_callback,
            )
            new_report = self._load_report(subject_id, visit, subjects_dir)
            decision = self._apply_decision_tree(primary, backups, new_report, cb)
            final_report = {
                **new_report,
                "selected_feature": decision["feature"],
                "session_decision": decision,
            }
            self._save_report(subject_id, visit, subjects_dir, final_report)
            return final_report

        # ---- Sessions 2–4 ->quick SNR/z check ----------------------------
        _log(
            f"[SessionManager] Visit {visit}: quick SNR/|z| check for "
            f"'{primary['feature_name']}' ...",
            cb,
        )
        metrics = self._get_quick_metrics(
            subject_id, visit, subjects_dir, primary, cb
        )
        decision = self._apply_snr_switch(primary, backups, metrics, cb)
        report = {
            **prev_report,
            "visit": visit,
            "selected_feature": decision["feature"],
            "session_decision": decision,
        }
        self._save_report(subject_id, visit, subjects_dir, report)
        return report

    # ------------------------------------------------------------------
    # Internal: report I/O
    # ------------------------------------------------------------------

    def _load_report(
        self, subject_id: str, visit: int, subjects_dir: Path
    ) -> dict | None:
        """Load a selection report JSON for *subject_id* at *visit*.

        Args:
            subject_id: Four-letter subject identifier.
            visit: Integer visit number.
            subjects_dir: Root directory containing all ``sub-*`` folders.

        Returns:
            dict parsed from the JSON file, or ``None`` if it does not exist.
        """
        path = (
            subjects_dir
            / f"sub-{subject_id}"
            / "nf_selection"
            / f"selection_report_v{visit}.json"
        )
        if not path.exists():
            return None
        with open(path) as fh:
            return json.load(fh)

    def _save_report(
        self,
        subject_id: str,
        visit: int,
        subjects_dir: Path,
        report: dict,
    ) -> None:
        """Persist *report* as a JSON file for *subject_id* at *visit*.

        Non-serialisable objects (e.g. DataFrames with a ``to_dict`` attribute)
        are excluded.  NumPy scalars are converted to Python floats via
        ``_clean_json``.

        Args:
            subject_id: Four-letter subject identifier.
            visit: Integer visit number.
            subjects_dir: Root directory containing all ``sub-*`` folders.
            report: Selection report dict, which may contain DataFrames that
                are stripped before serialisation.
        """
        out_dir = subjects_dir / f"sub-{subject_id}" / "nf_selection"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"selection_report_v{visit}.json"
        # Exclude non-serialisable fields (e.g. DataFrame)
        safe = {
            k: _clean_json(v)
            for k, v in report.items()
            if not hasattr(v, "to_dict")
        }
        with open(path, "w") as fh:
            json.dump(safe, fh, indent=2)
        logging.info("[SessionManager] Report saved ->%s", path)

    # ------------------------------------------------------------------
    # Internal: quick metrics
    # ------------------------------------------------------------------

    def _get_quick_metrics(
        self,
        subject_id: str,
        visit: int,
        subjects_dir: Path,
        primary: dict,
        log_callback=None,
    ) -> dict:
        """Return SNR / ICC / dynamic_range for *primary* from the quick baseline.

        Sensor-power features are re-computed from the raw epochs.
        Connectivity and source features fall back to stored metrics from
        the previous visit to avoid the cost of full feature extraction.
        """
        feature_name = primary["feature_name"]
        feature_type = primary.get("feature_type", "")

        if feature_type in ("power_sensor",) or (
            "_vs_" not in feature_name and "-lh" not in feature_name and "-rh" not in feature_name
        ):
            # Attempt fast recomputation
            try:
                from .analysis import compute_quick_feature_metrics
                return compute_quick_feature_metrics(
                    subject_id, visit, subjects_dir, feature_name, log_callback
                )
            except Exception as exc:
                _log(
                    f"[SessionManager] Quick metrics failed ({exc}); "
                    "using stored metrics.",
                    log_callback,
                )

        # Fallback: use stored values from the selection report
        return {
            "snr":           primary.get("snr", 0.0),
            "icc":           primary.get("icc", 0.0),
            "dynamic_range": primary.get("dynamic_range", 0.0),
        }

    # ------------------------------------------------------------------
    # Internal: switching logic -sessions 2–4
    # ------------------------------------------------------------------

    def _apply_snr_switch(
        self,
        primary: dict,
        backups: list[dict],
        metrics: dict,
        log_callback=None,
    ) -> dict:
        """Decide whether to stay on *primary* or switch to a backup (sessions 2–4).

        Evaluates the freshly computed *metrics* for the primary feature.  If
        SNR >= ``SNR_SWITCH_THRESHOLD`` and ``|z|`` >= ``Z_MIN_THRESHOLD``, the
        primary is maintained.  Otherwise backups are tested in ranked order and
        the first that passes both thresholds is selected.  If all options fail,
        the primary is kept with a ``"maintain_fallback"`` decision.

        Args:
            primary: Selected-feature dict from the previous session's report.
            backups: List of up to three backup-feature dicts from the previous
                report.
            metrics: Quick-computed metrics dict with keys ``snr``, ``icc``,
                ``dynamic_range``.
            log_callback: Optional callable for GUI log forwarding.

        Returns:
            dict with keys ``decision`` (str), ``reason`` (str), and
            ``feature`` (the maintained or newly selected feature dict).
        """
        snr = metrics.get("snr", 0.0)
        z   = abs(primary.get("z_score", 0.0))

        if snr >= self.SNR_SWITCH_THRESHOLD and z >= self.Z_MIN_THRESHOLD:
            reason = (
                f"SNR={snr:.2f} >= {self.SNR_SWITCH_THRESHOLD}, "
                f"|z|={z:.2f} >= {self.Z_MIN_THRESHOLD} -primary remains."
            )
            _log(f"[SessionManager] {reason}", log_callback)
            return {"decision": "maintain", "reason": reason, "feature": primary}

        # Try backups in ranked order
        for i, backup in enumerate(backups):
            b_snr = backup.get("snr", 0.0)
            b_z   = abs(backup.get("z_score", 0.0))
            if b_snr >= self.SNR_SWITCH_THRESHOLD and b_z >= self.Z_MIN_THRESHOLD:
                reason = (
                    f"Primary '{primary['feature_name']}': "
                    f"SNR={snr:.2f} or |z|={z:.2f} below threshold -"
                    f"switching to backup #{i + 1}: '{backup['feature_name']}'."
                )
                _log(f"[SessionManager] {reason}", log_callback)
                return {
                    "decision": f"switch_to_backup_{i + 1}",
                    "reason": reason,
                    "feature": backup,
                }

        # All backups also failed -keep primary with a warning
        reason = (
            f"Primary and all {len(backups)} backup(s) failed SNR/|z| check. "
            "Keeping primary with quality warning."
        )
        _log(f"[SessionManager] WARNING: {reason}", log_callback)
        return {"decision": "maintain_fallback", "reason": reason, "feature": primary}

    # ------------------------------------------------------------------
    # Internal: decision tree -session 5
    # ------------------------------------------------------------------

    def _apply_decision_tree(
        self,
        prev_primary: dict,
        prev_backups: list[dict],
        new_report: dict,
        log_callback=None,
    ) -> dict:
        """Apply the session-5 decision tree to decide whether to maintain or switch.

        Rules are evaluated in order and the first matching rule is applied:

        1. Previous primary is still in the new top-3 ranking -> **maintain**.
        2. Previous primary SNR dropped > 50 % -> **switch** to new #1.
        3. New #1 shares the same feature modality -> **maintain** (within-
           modality drift is acceptable).
        4. New #1 is a different modality AND its composite score is >= 30 %
           higher -> **switch**.
        Default: **maintain**.

        Args:
            prev_primary: Selected-feature dict from the previous session.
            prev_backups: Backup-feature list from the previous session.
            new_report: Full selection report dict produced by the mid-protocol
                re-ranking (visit 5 ``run_full_analysis`` output).
            log_callback: Optional callable for GUI log forwarding.

        Returns:
            dict with keys ``decision`` (str), ``reason`` (str), and
            ``feature`` (the maintained or newly selected feature dict).
        """
        prev_name  = prev_primary["feature_name"]
        prev_score = prev_primary.get("composite_score", 0.0)
        prev_snr   = prev_primary.get("snr", 0.0)

        new_primary  = new_report["selected_feature"]
        new_backups  = new_report.get("backup_features", [])
        top3         = [new_primary] + new_backups[:2]
        top3_names   = [f["feature_name"] for f in top3]

        # Rule 1 ----------------------------------------------------------------
        if prev_name in top3_names:
            reason = f"'{prev_name}' still in top 3 of new ranking ->maintain."
            _log(f"[SessionManager] Decision tree R1: {reason}", log_callback)
            return {"decision": "maintain", "reason": reason, "feature": prev_primary}

        # Rule 2 ----------------------------------------------------------------
        new_row = next(
            (f for f in [new_primary] + new_backups if f["feature_name"] == prev_name),
            None,
        )
        new_snr = new_row.get("snr", prev_snr) if new_row else prev_snr
        if prev_snr > 0 and new_snr < prev_snr * 0.5:
            reason = (
                f"'{prev_name}' SNR: {prev_snr:.2f} ->{new_snr:.2f} (>50% drop) "
                f"-> switch to '{new_primary['feature_name']}'."
            )
            _log(f"[SessionManager] Decision tree R2: {reason}", log_callback)
            return {
                "decision": "switch_snr_drop",
                "reason": reason,
                "feature": new_primary,
            }

        prev_modality = prev_primary.get("feature_type", "")
        new_modality  = new_primary.get("feature_type", "")

        # Rule 3 ----------------------------------------------------------------
        if new_modality == prev_modality:
            reason = (
                f"New #1 '{new_primary['feature_name']}' shares modality "
                f"'{prev_modality}' with '{prev_name}' ->maintain original."
            )
            _log(f"[SessionManager] Decision tree R3: {reason}", log_callback)
            return {"decision": "maintain", "reason": reason, "feature": prev_primary}

        # Rule 4 ----------------------------------------------------------------
        new_score = new_primary.get("composite_score", 0.0)
        if prev_score > 0 and new_score >= prev_score * (1.0 + self.SCORE_SWITCH_MARGIN):
            reason = (
                f"New #1 '{new_primary['feature_name']}' (modality: {new_modality}) "
                f"is {self.SCORE_SWITCH_MARGIN * 100:.0f}%+ better: "
                f"{new_score:.3f} vs {prev_score:.3f} ->switch."
            )
            _log(f"[SessionManager] Decision tree R4: {reason}", log_callback)
            return {
                "decision": "switch_score_improvement",
                "reason": reason,
                "feature": new_primary,
            }

        # Default ---------------------------------------------------------------
        reason = (
            f"New #1 is different modality but improvement "
            f"({new_score:.3f} vs {prev_score:.3f}) < "
            f"{self.SCORE_SWITCH_MARGIN * 100:.0f}% ->maintain '{prev_name}'."
        )
        _log(f"[SessionManager] Decision tree default: {reason}", log_callback)
        return {"decision": "maintain", "reason": reason, "feature": prev_primary}
