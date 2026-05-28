"""Offline EEG analysis: preprocessing, feature extraction, normative scoring, ranking."""
from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path
from typing import Callable

import matplotlib
matplotlib.use("Agg")  # headless – no display required
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.patches import Patch
from scipy.stats import spearmanr


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log(msg: str, cb: Callable[[str], None] | None = None) -> None:
    """Log *msg* via the standard logger and optionally forward it to a GUI callback.

    Args:
        msg: The message string to log.
        cb: Optional callable that accepts a single string argument.  When
            provided, the message is forwarded to it (e.g. to update a GUI
            text widget).
    """
    logging.info(msg)
    if cb:
        cb(msg)


def _baseline_fif(subjects_dir: Path, subject_id: str, visit: int) -> Path:
    """Return the BIDS-compliant path where ANT saves the baseline raw .fif.

    The path follows the pattern::

        <subjects_dir>/sub-<id>/ses-v<visit>b/eeg/sub-<id>_ses-v<visit>b_task-baseline_eeg.fif

    Args:
        subjects_dir: Root directory that contains all ``sub-*`` folders.
        subject_id: Four-letter subject identifier (e.g. ``"abcd"``).
        visit: Integer visit number.

    Returns:
        Absolute ``Path`` object for the expected .fif file.
    """
    session = f"v{visit}b"
    stem = f"sub-{subject_id}_ses-{session}"
    return (
        subjects_dir
        / f"sub-{subject_id}"
        / f"ses-{session}"
        / "eeg"
        / f"{stem}_task-baseline_eeg.fif"
    )


def _inv_fif(subjects_dir: Path, subject_id: str, visit: int) -> Path:
    """Return the BIDS-compliant path where ANT saves the inverse operator .fif.

    The path follows the pattern::

        <subjects_dir>/sub-<id>/ses-v<visit>b/inv/sub-<id>_ses-v<visit>b_task-baseline_inv.fif

    Args:
        subjects_dir: Root directory that contains all ``sub-*`` folders.
        subject_id: Four-letter subject identifier.
        visit: Integer visit number.

    Returns:
        Absolute ``Path`` object for the expected inverse operator file.
    """
    session = f"v{visit}b"
    stem = f"sub-{subject_id}_ses-{session}"
    return (
        subjects_dir
        / f"sub-{subject_id}"
        / f"ses-{session}"
        / "inv"
        / f"{stem}_task-baseline_inv.fif"
    )


# ---------------------------------------------------------------------------
# Stage 1 – preprocessing
# ---------------------------------------------------------------------------

def preprocess_baseline(
    subject_id: str,
    visit: int,
    subjects_dir: Path,
    log_callback: Callable[[str], None] | None = None,
):
    """Load, filter, re-reference, epoch, and AutoReject the baseline recording.

    Reads the raw baseline .fif file saved by ANT, applies a 0.1–40 Hz bandpass
    filter, sets an average reference, assigns the EasyCap-M1 montage, cuts the
    continuous recording into 10-second fixed-length epochs, and then runs
    AutoReject to interpolate or drop bad epochs.  An HTML AutoReject report and
    cleaned epoch file are written to the subject BIDS tree.

    Args:
        subject_id: Four-letter subject identifier.
        visit: Integer visit number.  Used to locate the correct BIDS session.
        subjects_dir: Root directory containing all ``sub-*`` folders.
        log_callback: Optional callable forwarded to ``_log()`` for GUI updates.

    Returns:
        mne.Epochs: The cleaned epoch object after AutoReject.

    Raises:
        FileNotFoundError: If the baseline .fif file does not exist.
    """
    from autoreject import AutoReject
    from mne import make_fixed_length_epochs, set_log_level, Report
    from mne.channels import make_standard_montage
    from mne.io import read_raw_fif

    set_log_level("ERROR")
    cb = log_callback

    fname = _baseline_fif(subjects_dir, subject_id, visit)
    if not fname.exists():
        raise FileNotFoundError(
            f"Baseline file not found: {fname}\n"
            "Run the baseline recording stage first."
        )

    subject_dir = subjects_dir / f"sub-{subject_id}"
    report_dir = subject_dir / f"ses-v{visit}b" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    _log(f"Loading {fname.name} ...", cb)
    raw = read_raw_fif(fname, preload=True, verbose=False)
    raw.drop_channels(['IO'], on_missing='ignore')
    raw.filter(0.1, 40, verbose=False)
    raw.set_eeg_reference("average", projection=True, verbose=False)
    raw.set_montage(
        make_standard_montage("easycap-M1"),
        match_case=False,
        on_missing="warn",
        verbose=False,
    )
    _log("Filtered (0.1–40 Hz), average-referenced, montage set.", cb)

    epochs = make_fixed_length_epochs(raw, duration=10, preload=True, verbose=False)
    _log(f"Epoched into {len(epochs)} x 10 s segments.", cb)

    _log("Running AutoReject ...", cb)
    ar = AutoReject(
        n_interpolate=np.array([1, 4, 8]),
        consensus=np.linspace(0, 1.0, 11),
        cv=5,
        n_jobs=1,
        random_state=11,
        verbose=False,
    )
    ar.fit(epochs)
    epochs, reject_log = ar.transform(epochs, return_log=True)
    _log(f"AutoReject done: {len(epochs)} clean epochs retained.", cb)

    epo_dir = subject_dir / f"ses-v{visit}b" / "eeg"
    epo_dir.mkdir(parents=True, exist_ok=True)
    epochs.save(epo_dir / f"sub-{subject_id}_ses-v{visit}b_task-baseline_epo.fif", overwrite=True)

    report = Report(title=f"{subject_id}_v{visit}", verbose=False)
    report.add_figure(reject_log.plot(show=False), title="AutoReject log", image_format="PNG")
    report.save(report_dir / f"autoreject_v{visit}.html", overwrite=True, open_browser=False)
    _log("AutoReject report saved.", cb)

    return epochs


# ---------------------------------------------------------------------------
# Stage 2 – feature extraction
# ---------------------------------------------------------------------------

def extract_features(
    epochs,
    subject_id: str,
    visit: int,
    subjects_dir: Path,
    log_callback: Callable[[str], None] | None = None,
) -> None:
    """Extract band-power and coherence features in sensor and source space.

    Computes per-epoch band-power for ten frequency bands (delta through gamma)
    and pairwise coherence using a single CWT pass.  Source-space features
    require a pre-computed inverse operator (.fif) in the subject BIDS tree; if
    it is absent, source features are skipped with a warning.

    Feature CSVs and reliability-metric CSVs are written to::

        <subjects_dir>/sub-<id>/features/
        <subjects_dir>/sub-<id>/reliability_metrics/

    Args:
        epochs: Clean ``mne.Epochs`` object (output of ``preprocess_baseline``).
        subject_id: Four-letter subject identifier.
        visit: Integer visit number.
        subjects_dir: Root directory containing all ``sub-*`` folders.
        log_callback: Optional callable for GUI log forwarding.
    """
    from mne import read_labels_from_annot, extract_label_time_course, set_log_level
    from mne.minimum_norm import read_inverse_operator, apply_inverse_epochs
    from mne.time_frequency import psd_array_multitaper
    from mne_connectivity import spectral_connectivity_time

    set_log_level("ERROR")
    cb = log_callback

    subject_dir = subjects_dir / f"sub-{subject_id}"
    features_dir = subject_dir / "features"
    features_dir.mkdir(exist_ok=True)
    reliability_dir = subject_dir / "reliability_metrics"
    reliability_dir.mkdir(exist_ok=True)

    freq_bands = {
        "delta":  [1,    6],
        "theta":  [6.5,  8.5],
        "alpha_0": [8.5, 12.5],
        "alpha_1": [8.5, 10.5],
        "alpha_2": [10.5, 12.5],
        "beta_0":  [12.5, 30],
        "beta_1":  [12.5, 18.5],
        "beta_2":  [18.5, 21],
        "beta_3":  [21,   30],
        "gamma":   [30,   40],
    }

    # -- Sensor band power --------------------------------------------------
    epochs.pick_types(eeg=True, verbose=False)
    
    '''
    epochs_ts = epochs.get_data(picks="eeg")
    ch_names = epochs.info["ch_names"]

    _log("Computing sensor-space band powers ...", cb)
    psd_chs, freqs = epochs.compute_psd(
        fmin=1, fmax=40, verbose=False
    ).get_data(return_freqs=True)

    columns, all_band_powers = [], []
    for band_name, (fmin, fmax) in freq_bands.items():
        mask = (freqs >= fmin) & (freqs <= fmax)
        bp = np.trapezoid(psd_chs[:, :, mask], freqs[mask], axis=-1)
        all_band_powers.append(bp)
        columns.extend([f"{ch}_{band_name}" for ch in ch_names])

    chs_power = np.concatenate(all_band_powers, axis=1)
    pd.DataFrame(chs_power, columns=columns).to_csv(
        features_dir / f"power_sensor_v{visit}.csv", index=False
    )
    compute_reliability_metrics(chs_power, columns, "power_sensor").to_csv(
        reliability_dir / f"power_sensor_v{visit}.csv", index=False
    )
    _log("Sensor band power done.", cb)
    '''

    # -- Source band power --------------------------------------------------
    inv_fname = _inv_fif(subjects_dir, subject_id, visit)
    if not inv_fname.exists():
        _log(f"Inverse operator not found ({inv_fname.name}); skipping source features.", cb)
    else:
        _log("Computing source-space band powers ...", cb)
        inverse_operator = read_inverse_operator(inv_fname, verbose=False)
        labels = read_labels_from_annot(
            "fsaverage", subjects_dir=None, parc="aparc", verbose=False
        )[:-1]
        stcs = apply_inverse_epochs(
            epochs,
            inverse_operator,
            lambda2=1.0,
            method="dSPM",
            pick_ori="normal",
            return_generator=True,   # generator avoids holding all ~20k-source STCs in RAM
            verbose=False,
        )
        label_ts = np.array(
            extract_label_time_course(
                stcs, labels, inverse_operator["src"],
                mode="mean_flip", return_generator=False, verbose=False,
            )
        )
        lb_names = [lb.name for lb in labels]
        n_epochs, n_labels, n_times = label_ts.shape
        psd, freqs_src = psd_array_multitaper(
            label_ts.reshape(-1, n_times),
            sfreq=epochs.info["sfreq"],
            fmin=1, fmax=40, verbose=False,
        )
        src_columns, labels_power = [], []
        for band_name, (fmin, fmax) in freq_bands.items():
            mask = (freqs_src >= fmin) & (freqs_src <= fmax)
            bp = np.trapezoid(psd[:, mask], freqs_src[mask], axis=-1)
            labels_power.append(bp.reshape(n_epochs, n_labels))
            src_columns.extend([f"{lb.name}_{band_name}" for lb in labels])
        labels_power = np.concatenate(labels_power, axis=1)
        pd.DataFrame(labels_power, columns=src_columns).to_csv(
            features_dir / f"power_source_v{visit}.csv", index=False
        )
        compute_reliability_metrics(labels_power, src_columns, "power_source").to_csv(
            reliability_dir / f"power_source_v{visit}.csv", index=False
        )
        _log("Source band power done.", cb)

    # -- Connectivity -------------------------------------------------------
    for mode in ["source"]: # ("sensor", "source")
        if mode == "source" and not inv_fname.exists():
            continue
        data_ts = epochs_ts if mode == "sensor" else label_ts
        names = ch_names if mode == "sensor" else lb_names
        n_nodes = data_ts.shape[1]
        i_lower, j_lower = np.tril_indices(n_nodes, k=-1)

        _log(f"Computing {mode} coherence ...", cb)
        # Single CWT pass over the full frequency range, averaged into bands — 10× faster
        # than calling spectral_connectivity_time once per band.
        all_fmins = [v[0] for v in freq_bands.values()]
        all_fmaxs = [v[1] for v in freq_bands.values()]
        min_f = min(all_fmins)
        max_f = max(all_fmaxs)
        all_freqs_arr = np.arange(min_f, max_f + 1, 1.0)
        # MNE wavelet length ≈ 10·n_cycles/(2π·f)·sfreq samples; cap so it fits epoch.
        _epoch_dur = data_ts.shape[-1] / epochs.info["sfreq"]
        _n_cycles = np.minimum(7.0, 0.9 * 2 * np.pi * all_freqs_arr * _epoch_dur / 10)
        con = spectral_connectivity_time(
            data_ts,
            freqs=all_freqs_arr,
            method="coh",
            average=False,
            sfreq=epochs.info["sfreq"],
            mode="cwt_morlet",
            fmin=all_fmins,
            fmax=all_fmaxs,
            faverage=True,
            n_cycles=_n_cycles,
            verbose=False,
        )
        # con.get_data shape: (n_epochs, n_nodes, n_nodes, n_bands)
        con_data = con.get_data(output="dense")
        con_columns, freq_cons = [], []
        for band_idx, key in enumerate(freq_bands):
            con_matrix = con_data[:, :, :, band_idx]  # (n_epochs, n_nodes, n_nodes)
            cons = [ep[i_lower, j_lower] for ep in con_matrix]
            freq_cons.append(np.array(cons))
            con_columns += [
                f"{names[i]}_vs_{names[j]}_{key}_coh"
                for i, j in zip(i_lower, j_lower)
            ]

        freq_cons_arr = np.concatenate(freq_cons, axis=-1)
        pd.DataFrame(freq_cons_arr, columns=con_columns).T.to_csv(
            features_dir / f"conn_{mode}_v{visit}.csv", index=False
        )
        compute_reliability_metrics(freq_cons_arr, con_columns, f"conn_{mode}").to_csv(
            reliability_dir / f"conn_{mode}_v{visit}.csv", index=False
        )
        _log(f"{mode.capitalize()} coherence done.", cb)


# ---------------------------------------------------------------------------
# Stage 3 – reliability metrics
# ---------------------------------------------------------------------------

def compute_reliability_metrics(
    epoch_features: np.ndarray,
    feature_names: list[str],
    feature_type: str = "",
) -> pd.DataFrame:
    """Compute ICC, SNR, dynamic range, and stationarity for each feature.

    For each feature column in *epoch_features* the following metrics are
    computed:

    - **ICC**: split-half intraclass correlation via the Spearman-Brown formula
      applied to the Spearman rank correlation between the first and second
      halves of the epoch array.
    - **SNR**: ratio of the absolute mean to the standard deviation.
    - **Dynamic range**: normalised inter-percentile range (P90 - P10) / ``|median|``.
    - **Stationarity**: stability of the rolling per-window variance, expressed
      as 1 / (1 + CV of rolling variances).

    Args:
        epoch_features: 2-D array of shape ``(n_epochs, n_features)``.
        feature_names: List of column names matching the second axis.
        feature_type: Descriptive tag written to the ``feature_type`` column
            (e.g. ``"power_source"``).

    Returns:
        pd.DataFrame with one row per feature and columns: ``feature_name``,
        ``feature_type``, ``icc``, ``snr``, ``dynamic_range``, ``stationarity``,
        ``mean``, ``std``, ``median``, ``p10``, ``p90``, ``n_epochs``.
    """
    n_epochs, n_features = epoch_features.shape
    half = n_epochs // 2
    first, second = epoch_features[:half], epoch_features[half : 2 * half]
    rows = []
    for idx, name in enumerate(feature_names):
        vals = epoch_features[:, idx]
        # ICC via split-half Spearman-Brown
        if len(first) > 1:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                r, _ = spearmanr(first[:, idx], second[:, idx])
            icc = float((2 * r) / (1 + r)) if np.isfinite(r) else 0.0
        else:
            icc = 0.0
        mean_val = float(np.mean(vals))
        std_val = float(np.std(vals))
        snr = abs(mean_val) / std_val if std_val > 0 else 0.0
        p10, p90 = np.percentile(vals, [10, 90])
        med = float(np.median(vals))
        dynamic_range = float((p90 - p10) / abs(med)) if med != 0 else 0.0
        # Rolling variance stationarity
        ws = max(2, n_epochs // 5)
        rvars = [np.var(vals[i : i + ws]) for i in range(0, n_epochs - ws + 1, max(1, ws // 2))]
        if len(rvars) > 1:
            stationarity = float(1 / (1 + np.std(rvars) / np.mean(rvars)))
        else:
            stationarity = 1.0
        rows.append({
            "feature_name": name,
            "feature_type": feature_type,
            "icc": icc,
            "snr": snr,
            "dynamic_range": dynamic_range,
            "stationarity": stationarity,
            "mean": mean_val,
            "std": std_val,
            "median": med,
            "p10": float(p10),
            "p90": float(p90),
            "n_epochs": n_epochs,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Stage 4 – normative deviation scores
# ---------------------------------------------------------------------------

def compute_dev_scores(
    subject_id: str,
    age: int,
    sex: str,
    visit: int,
    subjects_dir: Path,
    models_dir: Path,
    site: str = "zuerich",
    log_callback: Callable[[str], None] | None = None,
) -> None:
    """Score each feature against normative models using pcntoolkit.

    Loads the pre-trained normative models from *models_dir* and computes
    deviation Z-scores for every feature that has a corresponding reliability
    CSV.  Covariates are age, sex, and PTA4 (pure-tone average); the PTA4 is
    read from ``<subjects_dir>/sub-<id>/audiometry/audio.csv``.  If that file
    is absent or if pcntoolkit is not installed, the function logs a warning
    and returns without modifying any files.

    The Z-score column ``deviation`` is appended in-place to the matching
    reliability metric CSV files under::

        <subjects_dir>/sub-<id>/reliability_metrics/

    Args:
        subject_id: Four-letter subject identifier.
        age: Subject age in years.
        sex: ``"M"`` (male) or ``"F"`` (female).
        visit: Integer visit number.
        subjects_dir: Root directory containing all ``sub-*`` folders.
        models_dir: Directory that contains the pre-trained normative model
            hierarchy (``<models_dir>/<space>/<tag>/full_model/``).
        site: Acquisition site label used as a batch-effect covariate.
            Defaults to ``"zuerich"``.
        log_callback: Optional callable for GUI log forwarding.
    """
    try:
        from pcntoolkit.normative_model import NormativeModel
        from pcntoolkit import NormData
        import pcntoolkit.util.output
        pcntoolkit.util.output.Output.set_show_messages(False)
    except ImportError:
        _log("pcntoolkit not available - skipping normative scoring.", log_callback)
        return

    from mne import read_labels_from_annot, set_log_level
    set_log_level("ERROR")
    cb = log_callback

    sex_code = 1 if sex.upper() == "M" else 0
    subject_dir = subjects_dir / f"sub-{subject_id}"
    reliability_dir = subject_dir / "reliability_metrics"

    audio_csv = subject_dir / "audiometry" / "audio.csv"
    pta = float(pd.read_csv(audio_csv)["PTA4_mean"].values[0]) if audio_csv.exists() else np.nan
    if np.isnan(pta):
        _log("WARNING: PTA4 not available - normative scoring requires audiometry data. Skipping.", log_callback)
        return

    freq_bands = {
        "delta": [1, 6], "theta": [6.5, 8.5],
        "alpha_0": [8.5, 12.5], "alpha_1": [8.5, 10.5], "alpha_2": [10.5, 12.5],
        "beta_0": [12.5, 30], "beta_1": [12.5, 18.5], "beta_2": [18.5, 21],
        "beta_3": [21, 30], "gamma": [30, 40],
    }

    for mode in ("power", "conn"):
        for space in ["source"]: # ("sensor", "source")
            tag = "conn_coh" if mode == "conn" else mode
            model_path = models_dir / space / tag / "full_model"
            if not model_path.exists():
                _log(f"No normative model at {model_path} - skipping.", cb)
                continue

            feat_csv = subject_dir / "features" / f"{mode}_{space}_v{visit}.csv"
            rel_csv = reliability_dir / f"{mode}_{space}_v{visit}.csv"
            if not feat_csv.exists() or not rel_csv.exists():
                _log(f"Feature file missing for {mode}_{space} - skipping.", cb)
                continue

            _log(f"Scoring {mode}_{space} against normative model ...", cb)
            df_f = pd.read_csv(feat_csv)

            if mode == "conn":
                labels = read_labels_from_annot(
                    "fsaverage", subjects_dir=None, parc="aparc", verbose=False
                )[:-1]
                lb_names = [lb.name for lb in labels]
                n_nodes = len(lb_names)
                i_lower, j_lower = np.tril_indices(n_nodes, k=-1)
                col_list = [
                    f"{lb_names[i]}_vs_{lb_names[j]}_{k}_coh"
                    for k in freq_bands
                    for i, j in zip(i_lower, j_lower)
                ]
                df_f = df_f.T.copy()
                df_f.columns = col_list
            else:
                df_f = df_f.mean(axis=0).to_frame().T

            df_f["SITE"] = site
            df_f["subject_id"] = subject_id
            df_f["age"] = age
            df_f["sex"] = sex_code
            df_f["PTA4_mean"] = pta

            feat_cols = df_f.columns.tolist()[:-5]
            covar_cols = ["age", "sex", "PTA4_mean"]

            norm_data = NormData.from_dataframe(
                name="test",
                dataframe=df_f,
                covariates=covar_cols,
                batch_effects=["SITE"],
                response_vars=feat_cols,
                subject_ids="subject_id",
            )
            model = NormativeModel.load(str(model_path))
            zscores = model.compute_zscores(norm_data).Z.data[0]

            df_rel = pd.read_csv(rel_csv)
            df_z = pd.DataFrame({"feature_name": feat_cols, "deviation": zscores})
            df_rel = df_rel.merge(df_z, on="feature_name", how="left")
            df_rel.to_csv(rel_csv, index=False)
            _log(f"Normative scoring done for {mode}_{space}.", cb)


# ---------------------------------------------------------------------------
# Stage 5 – feature ranking & selection
# ---------------------------------------------------------------------------

def rank_features(
    subject_id: str,
    visit: int,
    subjects_dir: Path,
    log_callback: Callable[[str], None] | None = None,
) -> dict:
    """Rank all features by composite score and select the NF target.

    Reads all reliability metric CSVs for the given visit, computes a weighted
    composite score (30 % ``|z|``, 25 % ICC, 20 % SNR, 15 % dynamic range, 10 %
    stationarity), and selects the top-ranked feature that meets all quality
    criteria (``|z|`` >= 1.5, ICC >= 0.6, SNR >= 2.0, DR >= 0.3).  If no feature
    meets the criteria, the overall top-ranked feature is used with status
    ``"relaxed_criteria"``.

    The full ranking table is saved to::

        <subjects_dir>/sub-<id>/nf_selection/feature_ranking_v<visit>.csv

    A JSON summary (excluding the full DataFrame) is written alongside it as::

        <subjects_dir>/sub-<id>/nf_selection/selection_report_v<visit>.json

    Args:
        subject_id: Four-letter subject identifier.
        visit: Integer visit number.
        subjects_dir: Root directory containing all ``sub-*`` folders.
        log_callback: Optional callable for GUI log forwarding.

    Returns:
        dict with keys: ``subject_id``, ``visit``, ``selection_status``,
        ``selection_message``, ``selected_feature``, ``backup_features``
        (up to 3 dicts), ``n_features_evaluated``,
        ``n_features_meeting_criteria``, ``ranking_table`` (DataFrame).

    Raises:
        RuntimeError: If no reliability metric files with deviation scores are
            found (i.e. ``compute_dev_scores`` has not been run yet).
    """
    cb = log_callback
    subject_dir = subjects_dir / f"sub-{subject_id}"
    reliability_dir = subject_dir / "reliability_metrics"

    all_rankings = []
    for rel_file in reliability_dir.glob(f"*_v{visit}.csv"):
        df_r = pd.read_csv(rel_file)
        if "deviation" not in df_r.columns:
            continue
        for _, row in df_r.iterrows():
            z = row["deviation"]
            icc = row["icc"]
            snr = row["snr"]
            dr = row["dynamic_range"]
            stat = row["stationarity"]
            abs_z = abs(z)
            meets = bool(abs_z >= 1.5 and icc >= 0.6 and snr >= 2.0 and dr >= 0.3)
            score = (
                0.30 * min(abs_z / 3.0, 1.0)
                + 0.25 * min(max(icc, 0), 1.0)
                + 0.20 * min(snr / 10.0, 1.0)
                + 0.15 * min(dr / 2.0, 1.0)
                + 0.10 * min(stat, 1.0)
            )
            all_rankings.append({
                "feature_name": row["feature_name"],
                "feature_type": row["feature_type"],
                "z_score": float(z),
                "icc": float(icc),
                "snr": float(snr),
                "dynamic_range": float(dr),
                "stationarity": float(stat),
                "composite_score": float(score),
                "meets_criteria": meets,
            })

    if not all_rankings:
        raise RuntimeError("No ranked features found. Run analysis first.")

    df_ranked = pd.DataFrame(all_rankings).sort_values(
        "composite_score", ascending=False
    ).reset_index(drop=True)
    df_ranked["rank"] = range(1, len(df_ranked) + 1)

    viable = df_ranked[df_ranked["meets_criteria"]]
    if len(viable) > 0:
        selected = viable.iloc[0].to_dict()
        backups = viable.iloc[1:4].to_dict("records")
        status = "success"
        msg = f"Selected {selected['feature_name']} (score={selected['composite_score']:.3f})"
    else:
        selected = df_ranked.iloc[0].to_dict()
        backups = df_ranked.iloc[1:4].to_dict("records")
        status = "relaxed_criteria"
        msg = f"No feature met all criteria; using best available: {selected['feature_name']}"

    _log(msg, cb)

    out_dir = subject_dir / "nf_selection"
    out_dir.mkdir(exist_ok=True)
    df_ranked.to_csv(out_dir / f"feature_ranking_v{visit}.csv", index=False)

    report = {
        "subject_id": subject_id,
        "visit": visit,
        "selection_status": status,
        "selection_message": msg,
        "selected_feature": selected,
        "backup_features": backups,
        "n_features_evaluated": len(df_ranked),
        "n_features_meeting_criteria": len(viable),
        "ranking_table": df_ranked,
    }

    # persist JSON (without ranking_table)
    json_rep = {k: v for k, v in report.items() if k != "ranking_table"}
    json_rep["selected_feature"] = {
        k: float(v) if isinstance(v, (np.floating, np.integer)) else v
        for k, v in selected.items()
    }
    with open(out_dir / f"selection_report_v{visit}.json", "w") as fh:
        json.dump(json_rep, fh, indent=2)

    return report


# ---------------------------------------------------------------------------
# Stage 6 – HTML report
# ---------------------------------------------------------------------------

def generate_selection_report_html(report_dict: dict, subjects_dir: Path) -> Path:
    """Generate a PNG summary figure and a self-contained HTML report for feature selection.

    Creates four matplotlib panels (top-20 bar chart, selected-feature metric
    comparison, score histogram, and ICC vs SNR scatter) saved as a PNG, and
    wraps them in a styled HTML page with a ranked top-10 table.  Both files
    are written to::

        <subjects_dir>/sub-<id>/nf_selection/selection_report_v<visit>.{png,html}

    Args:
        report_dict: Output dict from ``rank_features()``, containing at minimum
            ``subject_id``, ``visit``, ``selected_feature``, ``backup_features``,
            and ``ranking_table``.
        subjects_dir: Root directory containing all ``sub-*`` folders.

    Returns:
        Path to the saved HTML report file.
    """
    sid = report_dict["subject_id"]
    visit = report_dict["visit"]
    out_dir = subjects_dir / f"sub-{sid}" / "nf_selection"
    out_dir.mkdir(exist_ok=True)

    selected = report_dict["selected_feature"]
    backups = report_dict["backup_features"]
    df_ranked = report_dict["ranking_table"]

    sns.set_style("whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f"Feature Selection: {sid} — Visit {visit}", fontsize=16, fontweight="bold")

    # Top-20 bar
    ax = axes[0, 0]
    top20 = df_ranked.head(20)
    colors = ["#2ecc71" if m else "#e74c3c" for m in top20["meets_criteria"]]
    ax.barh(range(len(top20)), top20["composite_score"], color=colors)
    ax.set_yticks(range(len(top20)))
    ax.set_yticklabels(top20["feature_name"], fontsize=7)
    ax.set_xlabel("Composite Score")
    ax.set_title("Top 20 Features")
    ax.invert_yaxis()
    ax.legend(handles=[
        Patch(facecolor="#2ecc71", label="Meets criteria"),
        Patch(facecolor="#e74c3c", label="Below threshold"),
    ], loc="lower right", fontsize=8)

    # Selected feature metrics
    ax = axes[0, 1]
    metrics = ["z_score", "icc", "snr", "dynamic_range", "stationarity"]
    thresholds = [1.5, 0.6, 2.0, 0.3, 0.7]
    x = np.arange(len(metrics))
    ax.bar(x, [selected[m] for m in metrics], color="#3498db", alpha=0.7)
    ax.scatter(x, thresholds, color="red", s=100, marker="_", linewidths=3, label="Threshold", zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(["Z-score", "ICC", "SNR", "Dyn. Range", "Stationarity"], rotation=45, ha="right")
    ax.set_title(f"Selected: {selected['feature_name'][:30]}")
    ax.legend()

    # Histogram
    ax = axes[1, 0]
    ax.hist(df_ranked["composite_score"], bins=30, color="#95a5a6", alpha=0.7, edgecolor="black")
    ax.axvline(selected["composite_score"], color="#2ecc71", lw=3, linestyle="--", label="Selected")
    for b in backups:
        ax.axvline(b["composite_score"], color="#f39c12", lw=2, alpha=0.6, linestyle=":")
    ax.set_xlabel("Composite Score")
    ax.set_ylabel("Count")
    ax.set_title("Distribution of Scores")
    ax.legend()

    # ICC vs SNR scatter
    ax = axes[1, 1]
    sc = ax.scatter(df_ranked["icc"], df_ranked["snr"], c=df_ranked["composite_score"],
                    cmap="viridis", s=40, alpha=0.6)
    ax.scatter(selected["icc"], selected["snr"], color="#2ecc71", s=300, marker="*",
               edgecolor="black", lw=2, label="Selected", zorder=5)
    ax.axhline(2.0, color="red", linestyle="--", alpha=0.3)
    ax.axvline(0.6, color="red", linestyle="--", alpha=0.3)
    ax.set_xlabel("ICC")
    ax.set_ylabel("SNR")
    ax.set_title("Feature Space")
    ax.legend()
    plt.colorbar(sc, ax=ax, label="Composite Score")

    plt.tight_layout()
    png_path = out_dir / f"selection_report_v{visit}.png"
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    html = _build_html_report(report_dict, visit)
    html_path = out_dir / f"selection_report_v{visit}.html"
    html_path.write_text(html)
    logging.info("Selection report saved to %s", html_path)
    return html_path


def _build_html_report(report_dict: dict, visit: int) -> str:
    sid = report_dict["subject_id"]
    selected = report_dict["selected_feature"]
    backups = report_dict["backup_features"]
    df_ranked = report_dict["ranking_table"]

    def _class(val, good_thresh, bad_thresh=None):
        if bad_thresh is not None and val < bad_thresh:
            return "bad"
        return "good" if val >= good_thresh else "warning"

    rows_html = ""
    for _, row in df_ranked.head(10).iterrows():
        rows_html += (
            f"<tr><td>{int(row['rank'])}</td>"
            f"<td><b>{row['feature_name']}</b></td>"
            f"<td>{row['feature_type']}</td>"
            f"<td>{row['composite_score']:.3f}</td>"
            f"<td>{row['z_score']:.2f}</td>"
            f"<td>{row['icc']:.3f}</td>"
            f"<td>{row['snr']:.2f}</td>"
            f"<td>{row['dynamic_range']:.2f}</td>"
            f"<td>{'✓' if row['meets_criteria'] else '✗'}</td></tr>"
        )

    backup_html = ""
    for i, b in enumerate(backups, 1):
        backup_html += (
            f"<div style='margin:10px 0;padding:10px;background:#ecf0f1;border-radius:5px;'>"
            f"<b>{i}. {b['feature_name']}</b> "
            f"(Score:{b['composite_score']:.3f} Z:{b['z_score']:.2f} ICC:{b['icc']:.3f})</div>"
        )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>NF Feature Selection — {sid}</title>
<style>
body{{font-family:Arial,sans-serif;max-width:1200px;margin:40px auto;padding:20px;background:#f5f5f5}}
.header{{background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:30px;border-radius:10px;margin-bottom:20px}}
.card{{background:white;padding:20px;border-radius:10px;margin:20px 0;box-shadow:0 2px 10px rgba(0,0,0,.1)}}
.good{{color:#2ecc71}}.warning{{color:#f39c12}}.bad{{color:#e74c3c}}
table{{width:100%;border-collapse:collapse}}
th,td{{padding:10px;text-align:left;border-bottom:1px solid #ddd}}
th{{background:#667eea;color:white}}
img{{width:100%;border-radius:10px;margin:10px 0}}
</style></head>
<body>
<div class="header"><h1>Neurofeedback Feature Selection</h1><h2>{sid} — Visit {visit}</h2></div>
<div class="card">
  <h2>Selected Feature</h2><h3>{selected['feature_name']}</h3>
  <p><em>{selected['feature_type']}</em></p>
  <span class="{_class(selected['composite_score'],0.6,0.4)}">Score: {selected['composite_score']:.3f}</span> &nbsp;
  <span class="{_class(selected['z_score'],1.5)}">Z: {selected['z_score']:.2f}</span> &nbsp;
  <span class="{_class(selected['icc'],0.6)}">ICC: {selected['icc']:.3f}</span> &nbsp;
  <span class="{_class(selected['snr'],2.0)}">SNR: {selected['snr']:.2f}</span> &nbsp;
  <span class="{_class(selected['dynamic_range'],0.3)}">DR: {selected['dynamic_range']:.2f}</span>
</div>
<div class="card"><h2>Backup Features</h2>{backup_html}</div>
<div class="card"><h2>Visualisation</h2>
  <img src="selection_report_v{visit}.png" alt="Feature selection plots"></div>
<div class="card"><h2>Top 10</h2>
<table><thead><tr><th>Rank</th><th>Feature</th><th>Type</th><th>Score</th>
<th>Z</th><th>ICC</th><th>SNR</th><th>DR</th><th>OK</th></tr></thead>
<tbody>{rows_html}</tbody></table></div>
</body></html>"""


# ---------------------------------------------------------------------------
# Stage 7 – cross-session tracking
# ---------------------------------------------------------------------------

def track_feature_across_sessions(
    subject_id: str,
    subjects_dir: Path,
    current_visit: int,
    log_callback: Callable[[str], None] | None = None,
) -> dict | None:
    """Compare the stability of the primary selected feature across visits.

    Loads all available selection report JSONs up to *current_visit* and checks
    whether the feature chosen at visit 1 remains reliable (ICC std < 0.15 or
    SNR std < 1.0) in subsequent recordings.  Based on the latest metrics it
    returns a ``MAINTAIN`` or ``SWITCH`` recommendation.

    A tracking CSV is written to::

        <subjects_dir>/sub-<id>/nf_selection/feature_tracking_through_v<visit>.csv

    Args:
        subject_id: Four-letter subject identifier.
        subjects_dir: Root directory containing all ``sub-*`` folders.
        current_visit: The visit number being evaluated.
        log_callback: Optional callable for GUI log forwarding.

    Returns:
        dict with keys ``decision`` (``"MAINTAIN"`` or ``"SWITCH"``),
        ``message``, and ``primary_feature``, or ``None`` if fewer than two
        visit reports are available.
    """
    cb = log_callback
    sel_dir = subjects_dir / f"sub-{subject_id}" / "nf_selection"

    reports = []
    for v in range(1, current_visit + 1):
        jp = sel_dir / f"selection_report_v{v}.json"
        if jp.exists():
            with open(jp) as fh:
                reports.append(json.load(fh))

    if len(reports) < 2:
        return None

    primary = reports[0]["selected_feature"]["feature_name"]
    tracking = []
    for rep in reports:
        vn = rep["visit"]
        rp = sel_dir / f"feature_ranking_v{vn}.csv"
        if not rp.exists():
            continue
        df = pd.read_csv(rp)
        row = df[df["feature_name"] == primary]
        if len(row):
            tracking.append({"visit": vn, **row.iloc[0].to_dict()})

    df_track = pd.DataFrame(tracking)
    icc_stable = df_track["icc"].std() < 0.15
    snr_stable = df_track["snr"].std() < 1.0
    cur = df_track.iloc[-1]

    if cur["meets_criteria"] and (icc_stable or snr_stable):
        decision, msg = "MAINTAIN", f"Continue training {primary} — stable and reliable."
    elif cur["snr"] < 1.5:
        decision, msg = "SWITCH", f"SNR dropped ({cur['snr']:.2f}) — consider switching target."
    else:
        decision, msg = "MAINTAIN", f"Continue with {primary} despite variability."

    _log(f"Cross-session decision: {decision} - {msg}", cb)
    df_track.to_csv(sel_dir / f"feature_tracking_through_v{current_visit}.csv", index=False)
    return {"decision": decision, "message": msg, "primary_feature": primary}


# ---------------------------------------------------------------------------
# Convenience: run the full offline analysis pipeline
# ---------------------------------------------------------------------------

def run_full_analysis(
    subject_id: str,
    age: int,
    sex: str,
    visit: int,
    subjects_dir: Path,
    models_dir: Path,
    site: str = "zuerich",
    log_callback: Callable[[str], None] | None = None,
) -> dict:
    """Run the complete offline analysis pipeline in a single call.

    Sequentially executes:
    1. ``preprocess_baseline`` — filter, re-reference, AutoReject.
    2. ``extract_features`` — band-power and coherence CSVs.
    3. ``compute_dev_scores`` — normative deviation Z-scores via pcntoolkit.
    4. ``rank_features`` — composite scoring and NF target selection.
    5. ``generate_selection_report_html`` — PNG + HTML report.
    6. ``track_feature_across_sessions`` (visits > 1 only).

    Args:
        subject_id: Four-letter subject identifier.
        age: Subject age in years.
        sex: ``"M"`` or ``"F"``.
        visit: Integer visit number.
        subjects_dir: Root directory containing all ``sub-*`` folders.
        models_dir: Directory containing pre-trained normative models.
        site: Acquisition site label for batch-effect correction.
        log_callback: Optional callable for GUI log forwarding.

    Returns:
        dict: The selection report as returned by ``rank_features()``.
    """
    cb = log_callback
    epochs = preprocess_baseline(subject_id, visit, subjects_dir, cb)
    extract_features(epochs, subject_id, visit, subjects_dir, cb)
    compute_dev_scores(subject_id, age, sex, visit, subjects_dir, models_dir, site=site, log_callback=cb)
    report = rank_features(subject_id, visit, subjects_dir, cb)
    generate_selection_report_html(report, subjects_dir)
    if visit > 1:
        track_feature_across_sessions(subject_id, subjects_dir, visit, cb)
    return report


# ---------------------------------------------------------------------------
# Quick feature metrics (used by SessionManager for sessions 2–4)
# ---------------------------------------------------------------------------

def compute_quick_feature_metrics(
    subject_id: str,
    visit: int,
    subjects_dir: Path,
    feature_name: str,
    log_callback: Callable[[str], None] | None = None,
) -> dict:
    """Compute SNR, ICC, and dynamic range for a single sensor-power feature.

    Preprocesses the quick baseline recording for *visit* via
    ``preprocess_baseline``, then computes band-power epochs for the channel
    and band encoded in *feature_name* (e.g. ``"Cz_alpha_0"``).  This is
    intended for the fast per-session quality check in sessions 2–4 where
    running the full feature extraction pipeline is too slow.

    Only sensor-space band-power features are supported.  Connectivity features
    (``"_vs_"`` in name) and source-space labels (``"-lh"``/``"-rh"`` in
    channel) raise ``ValueError``.

    Args:
        subject_id: Four-letter subject identifier.
        visit: Integer visit number of the quick baseline to analyse.
        subjects_dir: Root directory containing all ``sub-*`` folders.
        feature_name: Full feature name in ``<channel>_<band>`` format, e.g.
            ``"Cz_alpha_0"``.  The band suffix must match a key in ``BAND_MAP``.
        log_callback: Optional callable for GUI log forwarding.

    Returns:
        dict with keys ``snr`` (float), ``icc`` (float), ``dynamic_range``
        (float).

    Raises:
        ValueError: If *feature_name* cannot be parsed, or if it encodes a
            connectivity or source-space feature.
    """
    from .session import BAND_MAP
    cb = log_callback

    # Parse band from feature_name
    band_name = None
    frange = None
    for bname, fr in BAND_MAP.items():
        if feature_name.endswith(f"_{bname}"):
            band_name = bname
            frange = fr
            channel = feature_name[: -(len(bname) + 1)]
            break

    if band_name is None:
        raise ValueError(
            f"Cannot parse band from feature name '{feature_name}'. "
            "Quick metrics only support sensor-band features (e.g. 'Cz_alpha_0')."
        )

    # Connectivity and source features are not supported for quick recomputation
    if "_vs_" in feature_name or "-lh" in channel or "-rh" in channel:
        raise ValueError(
            f"Quick metrics not supported for connectivity/source feature '{feature_name}'."
        )

    _log(f"[quick_metrics] Preprocessing quick baseline (visit {visit}) ...", cb)
    epochs = preprocess_baseline(subject_id, visit, subjects_dir, log_callback)

    epochs.pick_types(eeg=True, verbose=False)
    ch_names = epochs.info["ch_names"]
    # Case-insensitive channel lookup
    ch_map = {c.upper(): c for c in ch_names}
    ch_key = channel.upper()
    if ch_key not in ch_map:
        raise ValueError(
            f"Channel '{channel}' not found in recording "
            f"(available: {ch_names[:5]} ...)."
        )
    ch_actual = ch_map[ch_key]
    ch_idx = ch_names.index(ch_actual)

    _log(f"[quick_metrics] Computing {band_name} power for {ch_actual} ...", cb)
    psd_data, freqs = epochs.compute_psd(
        fmin=frange[0], fmax=frange[1], verbose=False
    ).get_data(return_freqs=True)

    mask = (freqs >= frange[0]) & (freqs <= frange[1])
    bp = np.trapezoid(psd_data[:, ch_idx, mask], freqs[mask], axis=-1)

    mean_val = float(np.mean(bp))
    std_val  = float(np.std(bp))
    snr      = abs(mean_val) / std_val if std_val > 0 else 0.0
    p10, p90 = np.percentile(bp, [10, 90])
    med      = float(np.median(bp))
    dr       = float((p90 - p10) / abs(med)) if med != 0 else 0.0

    n = len(bp) // 2
    if n > 1:
        from scipy.stats import spearmanr
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r, _ = spearmanr(bp[:n], bp[n : 2 * n])
        icc = float((2 * r) / (1 + r)) if np.isfinite(r) else 0.0
    else:
        icc = 0.0

    _log(
        f"[quick_metrics] {ch_actual} {band_name}: "
        f"SNR={snr:.2f}  ICC={icc:.3f}  DR={dr:.2f}",
        cb,
    )
    return {"snr": snr, "icc": icc, "dynamic_range": dr}
