ANTARES User Guide
==================

.. contents:: Table of Contents
   :depth: 3
   :local:

Overview
--------

ANTARES (Advancing Neurofeedback in Tinnitus with Adaptive Ranking and
Electrophysiology-based Selection) is a closed-loop EEG neurofeedback
platform designed for clinical neurofeedback research in tinnitus patients.

The system acquires continuous EEG via a BrainAmp amplifier, records a
resting-state baseline, performs offline analysis to identify the most
reliable and clinically deviant EEG feature for each individual participant,
and then delivers personalised neurofeedback across multiple sessions.  An
adaptive selection algorithm re-evaluates the target feature at sessions 2, 4,
and 5 to ensure optimal training targets are maintained throughout the protocol.

ANTARES runs on Windows Subsystem for Linux (WSL2 / WSLg) and communicates
with native Windows hardware drivers via subprocess bridges.  The operator
GUI runs in a customtkinter window.  The participant-facing visual
(``rspv``) runs as a separate subprocess.


Hardware Requirements
---------------------

EEG Amplifier
~~~~~~~~~~~~~

- **Brain Products BrainAmp DC** or **BrainAmp MR** amplifier.
- Powered via the BrainAmp power supply connected to a PC running
  **BrainVision Recorder** (Windows).
- EEG cap: EasyCap M1 layout (64 channels).  The cap should be positioned
  on the participant's head and all electrode impedances should be reduced to
  below 10 kΩ before starting.

.. note::
   The BrainVision Recorder software must be running and streaming data via
   the **Lab Streaming Layer (LSL)** before ANTARES can connect.  Enable the
   LSL plugin in BrainVision Recorder (Workspace → Preferences → LSL Export).

TriggerBox (recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~

- **Brain Products USB TriggerBox** connected to a USB port.  Windows will
  assign it a COM port (default: **COM4**).
- The TriggerBox output cable is connected to the BrainAmp trigger input or
  to a separate recording device.
- Serial mode is the recommended trigger mode because it does not require the
  ``inpoutx64.dll`` driver.

Parallel Port / LPT (alternative)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- For legacy setups with a physical LPT port, the ``inpoutx64.dll`` driver
  must be installed on the Windows host.
- The LPT port base address (typically ``0x3FF0``) is set in the GUI.

Participant Monitor
~~~~~~~~~~~~~~~~~~~~

- A second monitor on the operator PC is used as the participant screen.
  Configure Windows display settings to extend the desktop to this monitor.
- The rspv visual application runs full-screen on the participant monitor.


Software Setup
--------------

Prerequisites
~~~~~~~~~~~~~

1. **Windows 10/11** with WSL2 enabled and WSLg installed:

   .. code-block:: bash

       wsl --install
       wsl --set-default-version 2

2. An **Ubuntu 22.04** (or later) WSL distribution.

3. **BrainVision Recorder** installed on Windows with the LSL plugin enabled.

4. A **Miniconda** or **Anaconda** Python installation under Windows (used by
   the trigger helper subprocess).  ANTARES looks for it at:

   - ``C:\Users\KARL-EXP-ANTARES\miniconda3\python.exe``
   - ``C:\ProgramData\miniconda3\python.exe``
   - (and Anaconda equivalents)

Creating the Python virtual environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

From within the WSL terminal:

.. code-block:: bash

    cd /mnt/c/antares_v2/antares
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

.. note::
   ``pcntoolkit`` (normative modelling) and ``autoreject`` are heavy
   dependencies.  If they are not needed for a session (e.g. NF-only mode),
   ANTARES will skip the corresponding pipeline stages with a warning rather
   than raising an error.

rspv participant visual
~~~~~~~~~~~~~~~~~~~~~~~~

The rspv visual has its own virtual environment inside the project:

.. code-block:: bash

    cd /mnt/c/antares_v2/antares/rspv
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    deactivate


Launching ANTARES
-----------------

Desktop shortcut
~~~~~~~~~~~~~~~~~

Double-click the **ANTARES** shortcut on the Windows desktop.  This runs
``launch_antares.bat``, which opens a WSL terminal and executes:

.. code-block:: bash

    source /mnt/c/antares_v2/antares/.venv/bin/activate
    python /mnt/c/antares_v2/antares/antares_app.py

Manual launch
~~~~~~~~~~~~~

Open an Ubuntu WSL terminal and run:

.. code-block:: bash

    cd /mnt/c/antares_v2/antares
    source .venv/bin/activate
    python antares_app.py

The operator GUI opens on the primary monitor within a few seconds.


Operator GUI Overview
---------------------

The window is divided into two panels:

Left panel — Settings sidebar
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All session parameters are set here before starting a session.  The sidebar
scrolls vertically.  Sections:

**Subject**

- *Subject ID (4 letters)*: A four-character lowercase identifier (e.g.
  ``abcd``).  Must be unique; a duplicate-visit guard raises an error if the
  log for the requested visit already exists.
- *Age*: Integer age in years (required for normative scoring).
- *Sex*: Female or Male (used as a covariate in the normative model).
- *Visit Number*: Integer starting at 1.  Each visit creates a new BIDS
  session.
- *Participant Language*: Language used on the participant screen (English,
  German, French).
- *Mock LSL (no hardware)*: Enable to replay a recorded .fif file instead of
  connecting to the BrainAmp amplifier.  Useful for offline testing.
- *Mock LSL File*: Path to the .fif file to replay (visible only when Mock
  LSL is enabled).
- *LSL Stream Name* / *LSL Source ID*: The exact stream name and source ID
  published by BrainVision Recorder (visible only when Mock LSL is disabled).
  Default values: ``BrainVision RDA`` and ``RDA 127.0.0.1:51244``.
- *Triggers (BrainVision)*: Enable or disable hardware trigger output.
- *Trigger Mode*: ``serial`` (USB TriggerBox) or ``lpt`` (parallel port).
- *Serial Port*: COM port for the TriggerBox (default: ``COM4``).
- *LPT Address*: Hexadecimal LPT base address (default: ``0x3FF0``).

**Protocol**

- *NF Protocol*: ``Z-Score (recommended)``, ``Threshold``, ``Staircase``, or
  ``Sham (control)``.
- *Z-Score Threshold*: Reward threshold for the Z-score protocol (range:
  0.1–2.0; default: 0.5).
- *Warmup Windows*: Number of 1-second windows before the z-score baseline is
  considered initialised (default: 20).
- *Threshold Value*: Fixed threshold for the Threshold protocol (visible only
  when Threshold is selected).

**Session Design**

- *Baseline Duration (s)*: Full baseline duration in seconds (used for visit
  1).  For visits 2–4, a 3-minute quick baseline is used automatically; for
  visit 5, a 5-minute baseline is used.
- *Number of Blocks*: Number of rest+NF block pairs (default: 4).
- *Rest Duration / Block (s)*: Seconds per rest phase (default: 30).
- *NF Duration / Block (s)*: Seconds per NF phase (default: 120).
- *OSC Host*: IP address of the rspv visual host (default: ``127.0.0.1``).
- *OSC Port*: UDP port for OSC communication with rspv (default: 5005).
- *Participant Visual (rspv)*: Visual preset used by the rspv application.

**Paths**

- *Subjects Dir*: Root directory for all subject data (BIDS tree).
- *Audiometry Dir*: Directory containing per-subject audiometry .mat files.
- *Models Dir*: Directory containing pre-trained normative models for
  pcntoolkit scoring.

Right panel — Content area
~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **Status label**: Shows the current pipeline stage.
- **Overall progress bar**: Advances from 0 to 100 % through the session.
- **Block progress bar**: Visible only during the NF session.  Shows the
  current block number, phase (Rest / Neurofeedback), and fraction elapsed.
- **Log**: Scrollable timestamped log of all pipeline messages.
- **Action buttons**:

  - *Start Full Protocol* — Runs the complete session (recommended).
  - *Baseline Only* — Records the resting-state baseline and exits.
  - *Analyse Only* — Runs offline analysis on an existing baseline recording.
  - *NF Session Only* — Runs only the NF session (requires a prior analysis).
  - *Participant Screen* — Launches the participant GUI on the second monitor.
  - *Abort* — Stops the running pipeline thread and terminates subprocesses.


Session Workflow Step by Step
-----------------------------

Step 1 — Prepare the participant
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Fit the EasyCap on the participant, apply conductive gel to all electrodes,
   and reduce impedances below 10 kΩ.
2. Start **BrainVision Recorder** on the Windows host and begin recording with
   the LSL plugin active.
3. In the ANTARES sidebar, enter the subject ID, age, sex, and visit number.
4. Verify the LSL stream name and source ID match BrainVision Recorder.
5. Set the trigger mode (serial/lpt) and confirm the TriggerBox LED is lit.

Step 2 — Launch the participant screen
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Click **Participant Screen**.  The rspv window opens on the second monitor
showing a welcome page.  The participant sees their first instruction and
presses **Space** to confirm they are ready.

Step 3 — Start the full protocol
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Click **Start Full Protocol**.

The pipeline proceeds automatically through the stages below:

.. code-block:: text

    Intake  →  Baseline  →  Analysis  →  NF Session  →  Done

**Intake**: Subject info is validated, a session log file is created, and
audiometry data (if present) is loaded to compute PTA4.

**Baseline**: The resting-state recording begins.  ANTARES fires trigger
``BASELINE_START (10)`` at the start and ``BASELINE_END (11)`` at the end.
The participant sees a fixation cross during this period.

**Analysis**: The baseline EEG is preprocessed (filtered, epoched,
AutoReject), features are extracted (band power and coherence), normative
deviation scores are computed, and the best neurofeedback target is selected.

The participant screen switches to an instruction page.  The participant
presses **Space** to acknowledge and begin the NF session.

**NF session**: The personalised neurofeedback session runs for
``n_blocks × (rest_duration + nf_duration)`` seconds.  Each block transition
fires a trigger (``REST_START (20)`` or ``NF_START (30)``).  A ``SESSION_END
(99)`` trigger is sent at the end.  The operator log shows the current block
and phase.

A thank-you screen is shown for 5 seconds before the GUI clears.

Step 4 — Review outputs
~~~~~~~~~~~~~~~~~~~~~~~~~

All outputs are written to the BIDS tree under ``<subjects_dir>/sub-<id>/``.
See `File Outputs and BIDS Structure`_ for details.


Session Modes
-------------

ANTARES supports four run modes accessible via the action buttons:

Full Session
~~~~~~~~~~~~~

The complete pipeline: intake → baseline → analysis → NF session.  This is
the standard clinical mode.

Baseline Only
~~~~~~~~~~~~~~

Records only the resting-state baseline EEG and saves the raw .fif file.
Use this mode if the analysis needs to be run later or on a separate machine.

Analyse Only
~~~~~~~~~~~~~

Runs offline analysis on an existing baseline .fif file (the recording must
already be present in the BIDS tree).  Produces the feature ranking report and
HTML visualisation.

NF Only
~~~~~~~~

Runs only the neurofeedback session.  Requires that a previous analysis has
already produced a ``selection_report_v<visit>.json`` for the subject and
visit.  Useful for repeating a session without re-recording the baseline.


Multi-Session Adaptive Feature Selection
-----------------------------------------

ANTARES implements a visit-by-visit adaptive protocol to maintain an optimal
neurofeedback target across the treatment course:

Visit 1 — Full analysis
~~~~~~~~~~~~~~~~~~~~~~~~~

A full-duration resting-state baseline is recorded and the complete offline
analysis pipeline is run:

1. Preprocessing (filter, re-reference, AutoReject).
2. Feature extraction (band power and coherence in source space).
3. Normative deviation scoring (pcntoolkit; covariates: age, sex, PTA4).
4. Composite ranking (30 % |z|, 25 % ICC, 20 % SNR, 15 % dynamic range,
   10 % stationarity).
5. Primary feature and three backup features are stored in
   ``selection_report_v1.json``.

Visits 2–4 — Quick SNR/z check
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A 3-minute quick baseline is recorded.  Band power for the primary feature
channel is computed and SNR, ICC, and dynamic range are re-estimated.

Decision logic:

- **SNR ≥ 1.5 and |z| ≥ 1.0**: keep the primary feature.
- Otherwise: try backup features in ranked order; select the first backup that
  passes both thresholds.
- If all backups also fail: keep the primary with a quality warning.

Visit 5 — Mid-protocol re-evaluation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A 5-minute baseline is recorded and the full analysis pipeline is re-run.
The decision tree then evaluates five rules in order:

1. Is the previous primary still in the new top 3?  → **maintain**.
2. Did the primary feature's SNR drop by more than 50 %?  → **switch to new #1**.
3. Does the new #1 share the same modality as the previous primary?  →
   **maintain** (within-modality drift is acceptable).
4. Is the new #1 a different modality and is its composite score ≥ 30 %
   higher?  → **switch**.
5. Default: **maintain**.

Visits > 5 — Locked
~~~~~~~~~~~~~~~~~~~~~

The selected feature is locked.  No further switching occurs regardless of
quality metrics.  This ensures training consistency during the late phase of
the protocol.


Trigger Setup
-------------

Serial Mode (recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use a **Brain Products USB TriggerBox** connected via USB.

1. Connect the TriggerBox USB cable to the Windows host.
2. Open Device Manager (Windows) and note the assigned COM port (usually
   ``COM4``).
3. In the ANTARES sidebar, set *Trigger Mode* to ``serial`` and enter the COM
   port name.
4. Verify the connection by checking the TriggerBox LED.

When running under WSL/Linux Python, ANTARES automatically launches a Windows
Python helper subprocess (``serial_trigger_helper.py``) that owns the serial
port.  The subprocess communicates via stdin/stdout.

LPT Mode (legacy)
~~~~~~~~~~~~~~~~~~

Use a physical parallel port with the ``inpoutx64.dll`` driver installed.

1. Install the inpoutx64 driver on Windows (see the Brain Products website).
2. Identify the LPT port base address from Device Manager (e.g. ``0x3FF0``).
3. In the ANTARES sidebar, set *Trigger Mode* to ``lpt`` and enter the
   hexadecimal address.

Trigger codes
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Code
     - Constant
     - Meaning
   * - 10
     - ``TRIG_BASELINE_START``
     - Sent at the start of the baseline recording.
   * - 11
     - ``TRIG_BASELINE_END``
     - Sent at the end of the baseline recording.
   * - 20
     - ``TRIG_REST_START``
     - Sent at the start of each rest phase.
   * - 30
     - ``TRIG_NF_START``
     - Sent at the start of each NF phase.
   * - 99
     - ``TRIG_SESSION_END``
     - Sent when the NF session recording ends.


Troubleshooting
---------------

LSL stream not found
~~~~~~~~~~~~~~~~~~~~~

**Symptom**: ANTARES hangs or raises an error when connecting to LSL.

**Fix**:

- Confirm BrainVision Recorder is running and the LSL export plugin is
  enabled (Preferences → Online Processing → LSL).
- Check that the *LSL Stream Name* and *LSL Source ID* in the sidebar match
  what BrainVision Recorder publishes.  Default: ``BrainVision RDA`` and
  ``RDA 127.0.0.1:51244``.
- In Mock LSL mode, verify the mock .fif file path is correct.

Trigger not sending
~~~~~~~~~~~~~~~~~~~~

**Symptom**: The log shows ``WARNING: Serial/LPT trigger unavailable``.

**Fix**:

- **Serial mode**: Confirm the TriggerBox is connected and the COM port
  matches.  Try unplugging and re-plugging the USB cable.  Check that
  ``pyserial`` is installed in the Windows Python environment used by the
  helper subprocess.
- **LPT mode**: Confirm the ``inpoutx64.dll`` file is present in
  ``pipeline/`` and the driver is installed.  Run the operator with
  administrator privileges if the DLL fails to load.
- Check ``trigger_debug.log`` in the ANTARES root directory for the exact
  error message.

AutoReject fails
~~~~~~~~~~~~~~~~~

**Symptom**: AutoReject raises an error during preprocessing.

**Fix**:

- Ensure there are enough epochs (at least 5).  A very short baseline
  recording (< 50 s) may not yield sufficient 10-second epochs.
- Check electrode impedances were low during recording.

pcntoolkit not available
~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptom**: Log message ``pcntoolkit not available - skipping normative
scoring``.

**Fix**:

- Install pcntoolkit in the virtual environment:

  .. code-block:: bash

      pip install pcntoolkit

- The pipeline will continue without normative scoring; feature ranking will
  fall back to reliability metrics only (composite score will not include a
  deviation component).

Participant screen not appearing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptom**: The participant screen does not launch or the rspv window is
not visible.

**Fix**:

- Confirm WSLg is running (you should see X11 windows from WSL processes).
- Check that ``antares_gui.py`` exists in the ANTARES root directory.
- Check the operator log for ``Failed to launch participant screen`` errors.
- Try clicking *Participant Screen* manually before starting the full
  protocol.

rspv visual not launching
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptom**: Log shows ``rspv not found`` or ``rspv/config.json not found``.

**Fix**:

- Ensure the ``rspv/`` subdirectory exists and contains ``src/main.py`` and
  ``config.json``.
- Create the rspv virtual environment and install dependencies (see
  `Software Setup`_).


File Outputs and BIDS Structure
--------------------------------

ANTARES writes all outputs to a BIDS-compatible directory tree rooted at the
*Subjects Dir* configured in the sidebar.

.. code-block:: text

    <subjects_dir>/
    └── sub-<id>/
        ├── subject_info.json              # demographic metadata (accumulates across visits)
        ├── logs/
        │   └── v<visit>.log               # session log file
        ├── audiometry/
        │   └── audio.csv                  # audiogram thresholds and PTA4
        ├── ses-v<visit>b/                 # baseline session
        │   ├── eeg/
        │   │   ├── sub-<id>_ses-v<visit>b_task-baseline_eeg.fif   # raw baseline
        │   │   └── sub-<id>_ses-v<visit>b_task-baseline_epo.fif   # clean epochs
        │   ├── inv/
        │   │   └── sub-<id>_ses-v<visit>b_task-baseline_inv.fif   # inverse operator
        │   └── reports/
        │       └── autoreject_v<visit>.html
        ├── ses-v<visit>m/                 # main (NF) session
        │   ├── session_metadata_v<visit>.json
        │   ├── block_log_v<visit>.csv
        │   ├── nf_signal_log_v<visit>.csv
        │   └── <bids_beh_files>/          # ANT BIDS output (annotated with phase/block)
        ├── features/
        │   ├── power_source_v<visit>.csv
        │   └── conn_source_v<visit>.csv
        ├── reliability_metrics/
        │   ├── power_source_v<visit>.csv  # ICC, SNR, DR, stationarity, deviation z
        │   └── conn_source_v<visit>.csv
        └── nf_selection/
            ├── feature_ranking_v<visit>.csv
            ├── selection_report_v<visit>.json
            ├── selection_report_v<visit>.html
            ├── selection_report_v<visit>.png
            ├── nf_config_v<visit>.yml
            └── feature_tracking_through_v<visit>.csv   # visits > 1 only

Key output files
~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - File
     - Contents
   * - ``subject_info.json``
     - Subject demographics and per-visit metadata, accumulated across all
       visits.
   * - ``selection_report_v<visit>.json``
     - Selected NF feature and up to three backups, with composite scores,
       ICC, SNR, dynamic range, stationarity, and deviation z-score.  Also
       contains the ``session_decision`` field for visits ≥ 2.
   * - ``feature_ranking_v<visit>.csv``
     - Full ranked list of all evaluated features with all metrics.
   * - ``nf_config_v<visit>.yml``
     - Personalised ANT configuration YAML generated from the selection
       report.  Passed to ``NFRealtime.record_main`` during the NF session.
   * - ``nf_signal_log_v<visit>.csv``
     - Continuous neurofeedback signal log: elapsed time, raw value, rolling
       min/max, direction-corrected value, phase, and block for every 1-second
       window.
   * - ``block_log_v<visit>.csv``
     - Block start/end timestamps and phase labels.
   * - ``autoreject_v<visit>.html``
     - MNE-Report showing the AutoReject interpolation/rejection log for
       visual quality control.
   * - ``selection_report_v<visit>.html``
     - Interactive HTML report with the top-20 bar chart, selected-feature
       metric panel, score histogram, and ICC/SNR scatter plot.
