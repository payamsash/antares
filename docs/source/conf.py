import os
import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Path setup — let autodoc find the ANTARES package from any working dir
# ---------------------------------------------------------------------------
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_here, "..", ".."))   # project root

# ---------------------------------------------------------------------------
# Mock GUI / hardware / optional-heavy deps so autodoc works without them.
# All of these are installed into sys.modules BEFORE autodoc's import phase.
# ---------------------------------------------------------------------------
_MOCK_MODULES = [
    # GUI toolkit (top-level import in antares_app.py)
    "customtkinter",
    # ANT neurofeedback toolbox (lazy-imported inside pipeline functions, but
    # mock preemptively so any accidental top-level usage doesn't break the build)
    "ant",
    "ant.NFRealtime",
    "ant.protocols",
    "ant.protocols.ZScoreProtocol",
    "ant.protocols.ThresholdProtocol",
    "ant.protocols.UpDownStaircaseProtocol",
    "ant.protocols.ShamProtocol",
    "ant.osc",
    "ant.osc.OSCSender",
    # Optional heavy analysis deps (imported lazily inside function bodies)
    "autoreject",
    "mne_connectivity",
    "pcntoolkit",
    "pcntoolkit.normative_model",
    "pcntoolkit.util",
    "pcntoolkit.util.output",
    # Participant visual
    "py5",
    # OSC
    "pythonosc",
    "pythonosc.udp_client",
    "pythonosc.dispatcher",
    "pythonosc.osc_server",
]
for _mod in _MOCK_MODULES:
    sys.modules.setdefault(_mod, MagicMock())

# AntaresApp inherits from customtkinter.CTk (which is now a MagicMock).
# Replace it with a plain Python class so autodoc can render the class
# hierarchy and docstrings properly instead of showing "alias of MagicMock".
class _MockCTk:
    """Placeholder used during Sphinx docs build for customtkinter.CTk."""
    def __init__(self, *args, **kwargs): pass

sys.modules["customtkinter"].CTk = _MockCTk

autodoc_mock_imports = _MOCK_MODULES

# ---------------------------------------------------------------------------
# Project information
# ---------------------------------------------------------------------------
project   = "ANTARES"
copyright = "2025, Payam S. Shabestari"
author    = "Payam S. Shabestari"
release   = "1.0.0"

# ---------------------------------------------------------------------------
# Extensions
# ---------------------------------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",       # Google-style docstrings
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "numpydoc",
    "sphinx_tabs.tabs",
]

templates_path   = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

suppress_warnings = [
    "ref.python",
    "app.add_node",
    "autosummary",
]

# ---------------------------------------------------------------------------
# autodoc / autosummary
# ---------------------------------------------------------------------------
autosummary_generate           = True
autosummary_generate_overwrite = False   # keep hand-written RSTs intact

autodoc_default_options = {
    "members":          True,
    "undoc-members":    False,
    "show-inheritance": True,
}
autodoc_member_order = "bysource"

# Napoleon (Google-style → RST conversion)
napoleon_google_docstring  = True
napoleon_numpy_docstring   = False
napoleon_include_init_with_doc = True
napoleon_use_param         = True
napoleon_use_rtype         = True

# numpydoc (used for extra rendering polish even with napoleon)
numpydoc_show_class_members    = False
numpydoc_class_members_toctree = False

# ---------------------------------------------------------------------------
# HTML output — pydata_sphinx_theme (same as ANT / MNE)
# ---------------------------------------------------------------------------
html_theme      = "pydata_sphinx_theme"
html_title      = "ANTARES"
html_static_path = ["_static"]
html_css_files   = ["custom.css"]

html_theme_options = {
    "navbar_end":              ["navbar-icon-links"],
    "secondary_sidebar_items": ["page-toc"],
    "show_toc_level":          2,
    "navigation_depth":        3,
    "show_nav_level":          1,
}

html_sidebars = {
    "index": [],
    "**":    ["sidebar-nav-bs"],
}

# ---------------------------------------------------------------------------
# Intersphinx — clickable cross-references into NumPy, SciPy, MNE docs
# ---------------------------------------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "numpy":  ("https://numpy.org/doc/stable/", None),
    "scipy":  ("https://docs.scipy.org/doc/scipy/", None),
    "mne":    ("https://mne.tools/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
}
