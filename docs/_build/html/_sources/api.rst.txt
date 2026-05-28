.. _api:

API Reference
=============

This page documents the public Python API of ANTARES.
Source code links are provided via the :guilabel:`[source]` buttons on each
entry.

Pipeline — public API
---------------------

These are the functions and classes exported by the ``pipeline`` package and
used directly by the operator GUI.

.. autosummary::
   :toctree: generated/
   :nosignatures:

   pipeline.get_user_info
   pipeline.compute_pta
   pipeline.run_baseline
   pipeline.run_full_analysis
   pipeline.compute_quick_feature_metrics
   pipeline.run_nf_session
   pipeline.SessionManager

Analysis
--------

Offline preprocessing, feature extraction, normative scoring, and ranking.

.. autosummary::
   :toctree: generated/
   :nosignatures:

   pipeline.analysis.preprocess_baseline
   pipeline.analysis.extract_features
   pipeline.analysis.compute_reliability_metrics
   pipeline.analysis.compute_dev_scores
   pipeline.analysis.rank_features
   pipeline.analysis.generate_selection_report_html
   pipeline.analysis.track_feature_across_sessions
   pipeline.analysis.run_full_analysis
   pipeline.analysis.compute_quick_feature_metrics

Session
-------

NF session runner, block scheduler, and OSC bridge.

.. autosummary::
   :toctree: generated/
   :nosignatures:

   pipeline.session.BlockScheduler
   pipeline.session.RspvOSCSender
   pipeline.session.BlockAwareOSCSender
   pipeline.session.create_protocol
   pipeline.session.parse_feature_name
   pipeline.session.create_nf_yaml
   pipeline.session.save_session_metadata
   pipeline.session.run_nf_session

Adaptive selection
------------------

Multi-session adaptive NF target selection.

.. autosummary::
   :toctree: generated/
   :nosignatures:

   pipeline.session_manager.SessionManager

Triggers
--------

Hardware trigger output via serial (TriggerBox) or parallel port (LPT).

.. autosummary::
   :toctree: generated/
   :nosignatures:

   pipeline.triggers.SerialTrigger
   pipeline.triggers.ParallelTrigger
   pipeline.triggers.make_trigger

Intake
------

.. autosummary::
   :toctree: generated/
   :nosignatures:

   pipeline.intake.get_user_info
   pipeline.intake.compute_pta

Baseline recording
------------------

.. autosummary::
   :toctree: generated/
   :nosignatures:

   pipeline.baseline.run_baseline

Operator GUI
------------

.. autosummary::
   :toctree: generated/
   :nosignatures:

   antares_app.AntaresApp
