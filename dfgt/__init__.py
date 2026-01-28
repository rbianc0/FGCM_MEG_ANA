"""
DFGT MEG Analysis Package
=========================

A modular Python package for MEG data analysis in the DFGT/FGCM studies.

Modules:
    io: Data loading utilities (CTF, BIDS, preprocessed)
    bids: BIDS conversion functions
    preproc: MEG preprocessing pipeline
    utils: Shared utilities (triggers, subject mapping)
    config: Project configuration and paths
"""

__version__ = "0.1.0"

from . import io
from . import bids
from . import preproc
from . import utils
from . import config

__all__ = ["io", "bids", "preproc", "utils", "config"]
