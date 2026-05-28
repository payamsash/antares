# ANTARES

**Advancing Neurofeedback in Tinnitus via Adaptive Real-time EEG**

ANTARES is a closed-loop EEG neurofeedback system designed for tinnitus research. It runs an adaptive multi-session protocol: automatically selecting the best EEG feature to train per subject, monitoring feature quality across sessions, and adjusting the training target when necessary.

---

## Overview

```
Session 1          →  Full 80 s baseline + complete feature analysis → target selected
Sessions 2–4       →  3 min quick baseline + SNR re-validation only
Session 5          →  5 min mid-protocol evaluation + full re-ranking + decision tree
Sessions 6+        →  3 min baseline + locked target (no further switching)
```

The operator controls everything from a single GUI (`antares_app.py`).  
A separate full-screen display (`antares_gui.py`) runs on the participant's monitor.  
The real-time visualisation engine (`rspv/`) renders the neurofeedback animation.

---

## Project Structure

```
antares/
├── antares_app.py          # Operator control panel (customtkinter)
├── antares_gui.py          # Participant-facing full-screen display (py5)
├── config_master.yml       # Master configuration (paths, durations, protocol)
├── i18n.py                 # Localisation strings (English / German)
│
├── pipeline/
│   ├── intake.py           # Subject demographics + PTA audiometry
│   ├── baseline.py         # Resting-state EEG recording via LSL
│   ├── analysis.py         # Feature extraction, ranking, NF target selection
│   ├── session.py          # NF session: block scheduler + OSC reward sender
│   └── session_manager.py  # Adaptive multi-session logic + decision tree
│
├── rspv/                   # Real-time signal-driven particle visualisation engine
│   ├── src/
│   │   ├── main.py
│   │   ├── visuals/        # Visual presets (VisualTree, VisualRings, …)
│   │   └── signal_processing/
│   └── config.json
│
└── docs/
    ├── design.html         # Code design & methodology reference
    └── operator_guide.html # Operator working instructions
```

---

## Quick Start

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install rspv dependencies separately (it uses py5 which requires Java):

```bash
cd rspv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure paths

Edit `config_master.yml`:

```yaml
subjects_dir:   /path/to/antares_subjects
audiometry_dir: /path/to/audiometry_files
models_dir:     /path/to/normative_models
site:           zuerich   # or: basel
```

### 3. Run

```bash
python antares_app.py
```

See `docs/operator_guide.html` for full session-by-session operating instructions.

---

## EEG Feature Types

ANTARES ranks three classes of features per subject:

| Class | Examples | Training direction |
|---|---|---|
| Sensor-band power | alpha at Cz, theta at Fz | ↓ suppress or ↑ restore |
| Functional connectivity | alpha coherence Cz–Pz | ↓ suppress |
| Source-level power | alpha in auditory cortex | ↓ suppress |

Feature selection is based on a composite score of SNR, inter-session ICC, and dynamic range.

---

## NF Protocols

| Protocol | Description |
|---|---|
| `zscore` | Reward when feature deviates from rolling baseline by > z threshold |
| `threshold` | Reward when feature crosses a fixed absolute threshold |
| `staircase` | Adaptive threshold that tracks ~70% success rate |
| `sham` | Control condition — reward signal is randomised |

---

## Output Files

Per-subject data is saved under `<subjects_dir>/sub-<id>/`:

| File | Contents |
|---|---|
| `subject_info.json` | Demographics + visit history |
| `audiometry/audio.csv` | PTA thresholds at 9 frequencies |
| `ses-v{N}b/baseline_raw_v{N}.fif` | Raw baseline EEG |
| `models/analysis_report_v{N}.json` | Feature ranking + selected NF target |
| `ses-v{N}m/session_metadata_v{N}.json` | Protocol parameters for this NF session |
| `ses-v{N}m/nf_signal_log_v{N}.csv` | Per-window reward signal time series |
| `ses-v{N}m/block_log_v{N}.csv` | Wall-clock block timestamps |

---

## License

Academic / research use. Contact the authors before any clinical or commercial application.
