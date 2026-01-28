"""
Configuration module for DFGT MEG Analysis.

Contains paths, channel mappings, task definitions, and study-specific parameters.
"""

from pathlib import Path

# =============================================================================
# Data Paths
# =============================================================================

# External drive root
DATA_ROOT = Path("/media/bianco/LaCie/DATA/DFGT")

# Source MEG data (CTF format)
MEG_RAW_ROOT = DATA_ROOT / "FGT_MEG_RAW"

# Behavioral data
BEH_ROOT = DATA_ROOT / "FGT_BEH"

# BIDS output
BIDS_ROOT = DATA_ROOT / "DFGT_BIDS"

# Derivatives (preprocessed data)
DERIVATIVES_ROOT = BIDS_ROOT / "derivatives"

# Project directory
PROJECT_ROOT = Path(__file__).parent.parent

# Figures output
FIGURES_DIR = PROJECT_ROOT / "figures"

# Subject list (tab-delimited, local-only)
SUBJECT_LIST_CSV = PROJECT_ROOT / "FGT_Demographics.csv"

# =============================================================================
# FGT Channel Configuration
# =============================================================================

FGT_CHANNEL_MAP = {
    "ECG": "ecg",
    "UADC005": "eyetrack",  # x position
    "UADC006": "eyetrack",  # y position
    "UADC007": "eyetrack",  # pupil
    "UPPT01": "stim",
    # Note: EOGvert, EOGhor, UADC001 (Respiration) NOT present in FGT
}

# =============================================================================
# FGT Task Mapping (A/B Randomization)
# =============================================================================

# Task order depends on subject group (A or B)
FGT_TASKS = [
    "audio_base",
    "audio_cond",
    "audio_test",
    "visual_base",
    "visual_cond",
    "visual_test",
]

# Run number -> Task mapping for each group
FGT_TASK_MAPPING_A = {
    "01": "audio_base",
    "02": "audio_cond",
    "03": "audio_test",
    "04": "visual_base",
    "05": "visual_cond",
    "06": "visual_test",
}

FGT_TASK_MAPPING_B = {
    "01": "visual_base",
    "02": "visual_cond",
    "03": "visual_test",
    "04": "audio_base",
    "05": "audio_cond",
    "06": "audio_test",
}

# =============================================================================
# Subjects with Known Issues
# =============================================================================

# Subjects requiring trigger inversion during conversion
FGT_INVERTED_TRIGGER_SUBJECTS = ["C03", "C04"]

# Subjects with split recordings (convert as-is, ignore #MERGE)
FGT_SPLIT_RECORDING_SUBJECTS = ["C21", "C22", "C25", "C26", "C27", "C28", "C32", "C33"]

# =============================================================================
# Processing Parameters
# =============================================================================

# Power line frequency (Europe)
POWER_LINE_FREQ = 50  # Hz

# ICA parameters
ICA_N_COMPONENTS = 40
ICA_METHOD = "picard"

# Anonymization
ANONYMIZE_DAYS_BACK = 365 * 10  # Shift dates back ~10 years

# =============================================================================
# DFGT Configuration (for future use)
# =============================================================================

# DFGT_CHANNEL_MAP = { ... }
# DFGT_TASKS = [ ... ]
