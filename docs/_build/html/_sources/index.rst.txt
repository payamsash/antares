ANTARES
=======

**ANTARES** *(Advancing Neurofeedback in Tinnitus with Adaptive Ranking and
Electrophysiology-based Selection)* is a closed-loop EEG neurofeedback
platform for tinnitus research.  It acquires continuous EEG via a BrainAmp
amplifier, records a resting-state baseline, and uses offline analysis to
identify the most reliable and clinically deviant EEG feature for each
participant.  Personalised neurofeedback is then delivered across multiple
sessions, with an adaptive selection algorithm re-evaluating the target feature
at sessions 2, 4, and 5.

ANTARES runs on Windows Subsystem for Linux (WSL2 / WSLg) and communicates
with Windows hardware drivers through subprocess bridges.  The operator GUI
is built on `customtkinter`; the participant visual (*rspv*) runs as a separate
subprocess.

.. raw:: html

    <div style="height:12px;"></div>

Pipeline overview
-----------------

.. raw:: html

   <div style="overflow-x:auto; margin:16px 0;">
   <table style="border-collapse:separate; border-spacing:0; width:100%;
                 font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                 font-size:13px;">
   <thead>
     <tr>
       <th style="background:#1e40af;color:white;padding:8px 14px;
                  border-radius:8px 0 0 0;white-space:nowrap;">Stage</th>
       <th style="background:#1e40af;color:white;padding:8px 14px;">
           Module / class</th>
       <th style="background:#1e40af;color:white;padding:8px 14px;
                  border-radius:0 8px 0 0;">Notes</th>
     </tr>
   </thead>
   <tbody>
     <tr style="background:#eff6ff;">
       <td style="padding:7px 14px;border-bottom:1px solid #dbeafe;
                  font-weight:600;white-space:nowrap;">1 &nbsp;Intake</td>
       <td style="padding:7px 14px;border-bottom:1px solid #dbeafe;">
           <code>get_user_info</code> &nbsp; <code>compute_pta</code></td>
       <td style="padding:7px 14px;border-bottom:1px solid #dbeafe;">
           Validates subject info, creates BIDS log, loads audiometry PTA4</td>
     </tr>
     <tr style="background:#f0fdf4;">
       <td style="padding:7px 14px;border-bottom:1px solid #dcfce7;
                  font-weight:600;white-space:nowrap;">2 &nbsp;Baseline</td>
       <td style="padding:7px 14px;border-bottom:1px solid #dcfce7;">
           <code>run_baseline</code></td>
       <td style="padding:7px 14px;border-bottom:1px solid #dcfce7;">
           Resting-state recording via ANT NFRealtime; writes BIDS .fif</td>
     </tr>
     <tr style="background:#eff6ff;">
       <td style="padding:7px 14px;border-bottom:1px solid #dbeafe;
                  font-weight:600;white-space:nowrap;">3 &nbsp;Analysis</td>
       <td style="padding:7px 14px;border-bottom:1px solid #dbeafe;">
           <code>run_full_analysis</code></td>
       <td style="padding:7px 14px;border-bottom:1px solid #dbeafe;">
           AutoReject &rarr; source band power &rarr; coherence &rarr;
           normative scoring &rarr; feature ranking</td>
     </tr>
     <tr style="background:#f0fdf4;">
       <td style="padding:7px 14px;border-bottom:1px solid #dcfce7;
                  font-weight:600;white-space:nowrap;">4 &nbsp;NF session</td>
       <td style="padding:7px 14px;border-bottom:1px solid #dcfce7;">
           <code>run_nf_session</code></td>
       <td style="padding:7px 14px;border-bottom:1px solid #dcfce7;">
           Block scheduler, OSC bridge to rspv, trigger output, BIDS save</td>
     </tr>
     <tr style="background:#eff6ff;">
       <td style="padding:7px 14px;font-weight:600;white-space:nowrap;">
           5 &nbsp;Adaptive selection</td>
       <td style="padding:7px 14px;"><code>SessionManager</code></td>
       <td style="padding:7px 14px;">
           Visits 2-4: quick SNR/z check; visit 5: full re-ranking +
           decision tree; visits 6+: locked</td>
     </tr>
   </tbody>
   </table>
   </div>

.. toctree::
   :hidden:
   :caption: Getting started

   install
   user_guide

.. toctree::
   :hidden:
   :caption: API Reference

   api

.. raw:: html

    <div style="height:20px;"></div>
