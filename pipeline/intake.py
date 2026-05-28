"""Subject intake: collect demographic info and compute audiometric PTA."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat


def get_user_info(
    subject_id: str,
    age: int,
    sex: str,
    visit: int,
    subjects_dir: Path,
) -> None:
    """Validate intake inputs, create the visit log file, and update subject_info.json.

    Creates the subject directory tree if necessary, configures a
    ``logging.basicConfig`` handler writing to
    ``<subjects_dir>/sub-<id>/logs/v<visit>.log``, and maintains a structured
    ``subject_info.json`` that accumulates demographic metadata across visits.
    The arviz logger is silenced to prevent spurious INFO messages from
    optional sub-packages.

    Args:
        subject_id: Four-letter subject identifier (e.g. ``"abcd"``).
        age: Subject age in years.
        sex: ``"M"`` (male) or ``"F"`` (female).
        visit: Integer visit number.  Used to name the log file and to key
            the per-visit entry in ``subject_info.json``.
        subjects_dir: Root directory that contains all ``sub-*`` folders.

    Raises:
        ValueError: If the log file for *visit* already exists, which guards
            against accidentally running intake twice for the same session.
    """
    from datetime import datetime

    subject_dir = subjects_dir / f"sub-{subject_id}"
    log_dir = subject_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"v{visit}.log"
    if log_file.exists():
        raise ValueError(
            f"Log file for visit {visit} already exists: {log_file}"
        )

    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    # arviz logs INFO "not installed" messages for its optional sub-packages;
    # suppress them so they don't clutter the session log.
    logging.getLogger("arviz").setLevel(logging.WARNING)
    logging.info(
        "Subject intake: subject_id=%s age=%s sex=%s visit=%s",
        subject_id, age, sex, visit,
    )

    # Maintain a structured subject_info.json that accumulates across visits
    info_path = subject_dir / "subject_info.json"
    if info_path.exists():
        with open(info_path) as fh:
            info = json.load(fh)
    else:
        info = {
            "subject_id": subject_id,
            "age":        age,
            "sex":        sex,
            "created":    datetime.now().isoformat(timespec="seconds"),
            "visits":     {},
        }

    info["visits"][str(visit)] = {
        "visit":     visit,
        "date":      datetime.now().isoformat(timespec="seconds"),
        "age":       age,
        "sex":       sex,
    }
    info["last_visit"] = visit
    info["n_visits"]   = len(info["visits"])

    with open(info_path, "w") as fh:
        json.dump(info, fh, indent=2)
    logging.info("subject_info.json updated → %s", info_path)


def compute_pta(subject_id: str, subjects_dir: Path, audiometry_dir: Path) -> float:
    """Load audiometry .mat files and return the PTA4 mean across both ears.

    Searches ``<audiometry_dir>/<subject_id>/`` for left- and right-ear MATLAB
    files whose filenames begin with ``<subject_id> L`` and ``<subject_id> R``
    (case-insensitive).  Extracts audiometric thresholds at the standard
    frequencies [125, 250, 500, 1000, 2000, 4000, 6000, 8000, 12000] Hz,
    computes the four-frequency Pure Tone Average (PTA4) at 0.5, 1, 2, and
    4 kHz for each ear, and averages the two ears.

    The full audiogram DataFrame is saved to::

        <subjects_dir>/sub-<id>/audiometry/audio.csv

    Args:
        subject_id: Four-letter subject identifier.
        subjects_dir: Root directory containing all ``sub-*`` folders.  Used
            both to locate the subject directory and to write the output CSV.
        audiometry_dir: Directory that contains per-subject audiometry
            sub-directories named by subject ID.

    Returns:
        float: PTA4 mean across left and right ears in dB HL.  Returns
        ``numpy.nan`` if no audiometry directory is found for the subject.
    """
    log_dir = subjects_dir / f"sub-{subject_id}" / "logs"
    log_file = log_dir / "antares.log"
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logging.getLogger("arviz").setLevel(logging.WARNING)

    target_freqs = [125, 250, 500, 1000, 2000, 4000, 6000, 8000, 12000]
    freq_cols = [f"A{h}E_{f}" for h in ("L", "R") for f in target_freqs]
    row: dict = {"subject": subject_id, **{c: np.nan for c in freq_cols}}

    subject_audio_dir = audiometry_dir / subject_id
    if not subject_audio_dir.exists():
        logging.warning("No audiometry directory found for %s — PTA set to NaN.", subject_id)
        pta = np.nan
    else:
        for fname in subject_audio_dir.iterdir():
            for hemi in ("L", "R"):
                if fname.name.lower().startswith(f"{subject_id.lower()} {hemi.lower()}"):
                    logging.info("Audiometry data found for %s ear.", hemi)
                    data = loadmat(fname)
                    freqs = data["betweenRuns"]["var1Sequence"][0][0][0]
                    thrs = data["betweenRuns"]["thresholds"][0][0][0]
                    for f, thr in zip(freqs[np.argsort(freqs)], thrs[np.argsort(freqs)]):
                        col = f"A{hemi}E_{int(f)}"
                        if col in row:
                            row[col] = thr

        df = pd.DataFrame([row])
        pta_freqs = [500, 1000, 2000, 4000]
        df["PTA4_L"] = df[[f"ALE_{f}" for f in pta_freqs]].mean(axis=1)
        df["PTA4_R"] = df[[f"ARE_{f}" for f in pta_freqs]].mean(axis=1)
        df["PTA4_mean"] = df[["PTA4_L", "PTA4_R"]].mean(axis=1)
        pta = float(df["PTA4_mean"].values[0])

        audio_dir = subjects_dir / f"sub-{subject_id}" / "audiometry"
        audio_dir.mkdir(exist_ok=True)
        df.to_csv(audio_dir / "audio.csv", index=False)
        logging.info("PTA4 = %.1f dB. Audiometry saved.", pta)

    return pta
