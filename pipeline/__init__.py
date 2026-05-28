"""ANTARES pipeline package.

Provides the full neurofeedback pipeline for the ANTARES project, including
subject intake, resting-state baseline recording, offline EEG analysis and
normative feature ranking, personalised neurofeedback session execution, and
multi-session adaptive target selection.

Typical usage::

    from pipeline import (
        get_user_info, compute_pta,
        run_baseline,
        run_full_analysis,
        run_nf_session,
        SessionManager,
    )

Public API
----------
get_user_info : Validate intake inputs and persist subject_info.json.
compute_pta : Load audiometry .mat files and compute PTA4.
run_baseline : Record a resting-state baseline via ANT NFRealtime.
run_full_analysis : Preprocessing -> feature extraction -> normative scoring -> ranking.
compute_quick_feature_metrics : Fast SNR/ICC/DR check for a single sensor-power feature.
run_nf_session : Run the personalised closed-loop NF session.
SessionManager : Adaptive multi-session NF target selection manager.
"""
from .intake import get_user_info, compute_pta
from .baseline import run_baseline
from .analysis import run_full_analysis, compute_quick_feature_metrics
from .session import run_nf_session
from .session_manager import SessionManager

__all__ = [
    "get_user_info",
    "compute_pta",
    "run_baseline",
    "run_full_analysis",
    "compute_quick_feature_metrics",
    "run_nf_session",
    "SessionManager",
]
