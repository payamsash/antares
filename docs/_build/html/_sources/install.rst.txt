.. _install:

Installation
============

Requirements
------------

**Operating system**
   Windows 10/11 with WSL2 and WSLg enabled.
   All Python code runs inside Ubuntu on WSL2; the participant visual and
   trigger bridge use WSLg for display and Windows subprocess calls.

**Hardware**
   - BrainProducts BrainAmp EEG amplifier (connected via USB BrainAmp USB2
     Adapter / BUA)
   - BrainProducts TriggerBox Plus (USB + LPT cable)
   - A second monitor for the participant (*rspv* fullscreen visual)

**Python**
   Python 3.10 or newer inside the ANTARES virtual environment
   (``/mnt/c/antares_v2/antares/.venv``).

Setting up the virtual environment
-----------------------------------

.. code-block:: bash

   cd /mnt/c/antares_v2/antares
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt   # if present
   # or install core deps manually:
   pip install customtkinter mne autoreject mne-connectivity \
               pyserial python-osc pyyaml numpy scipy pandas \
               matplotlib seaborn

Installing the Windows trigger driver
--------------------------------------

The BrainProducts TriggerBox requires a Windows driver to expose a virtual
serial port (``COM4``).

1. Download ``SetupTriggerBoxPlusx64.msi`` from the BrainProducts website.
2. Run it on the Windows host (not inside WSL).
3. Open **Device Manager** and confirm that
   *TriggerBox VirtualSerial Port (COM4)* appears under *Ports (COM & LPT)*.

.. note::

   Without this driver the TriggerBox USB appears as an unknown device and
   no triggers will be sent.  The LPT port on a PCIe AX99100 card does **not**
   support direct I/O port access via ``inpoutx64.dll``; use the serial
   (COM4) path.

Launching ANTARES
-----------------

Double-click the **ANTARES** shortcut on the Windows desktop.  It runs:

.. code-block:: bat

   wsl.exe -d Ubuntu -- bash -c "source /mnt/c/antares_v2/antares/.venv/bin/activate && python antares_app.py"

The operator GUI appears on the primary monitor via WSLg.

Building these docs
-------------------

.. code-block:: bash

   cd /mnt/c/antares_v2/antares
   source .venv/bin/activate
   pip install sphinx pydata-sphinx-theme numpydoc sphinx-tabs
   cd docs
   make html
   # Output: docs/_build/html/index.html
