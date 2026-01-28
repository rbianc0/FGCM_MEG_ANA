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
MEG_RAW_ROOT = DATA_ROOT / "FGCM_MEG_RAW"

# Behavioral data
BEH_ROOT = DATA_ROOT / "FGCM_BEH"

# BIDS output
BIDS_ROOT = DATA_ROOT / "FGCM_BIDS"

# Derivatives (preprocessed data)
DERIVATIVES_ROOT = BIDS_ROOT / "derivatives"

# Project directory
PROJECT_ROOT = Path(__file__).parent.parent

# Figures output
FIGURES_DIR = PROJECT_ROOT / "figures"

# Subject list (tab-delimited, local-only)
SUBJECT_LIST_CSV = PROJECT_ROOT / "FGCM_Demographics.csv"

# =============================================================================
# FGCM Channel Configuration
# =============================================================================

FGCM_CHANNEL_MAP = {
    "ECG": "ecg",
    "UPPT001": "stim",
    "UPPT002": "stim",
    # Note: EOGvert, EOGhor, UADC001 (Respiration) NOT present in FGCM
}

FGCM_CHANNEL_PREFIX_MAP = {
    "UADC005": "eyegaze",  # x position
    "UADC006": "eyegaze",  # y position
    "UADC007": "pupil",  # pupil
}

# =============================================================================
# FGCM Task Mapping (A/B Randomization)
# =============================================================================

# Task order depends on subject group (A or B)
FGCM_TASKS = [
    "audio_base",
    "audio_cond",
    "audio_test",
    "visual_base",
    "visual_cond",
    "visual_test",
]

# Run number -> Task mapping for each group
FGCM_TASK_MAPPING_A = {
    "01": "audio_base",
    "02": "audio_cond",
    "03": "audio_test",
    "04": "visual_base",
    "05": "visual_cond",
    "06": "visual_test",
}

FGCM_TASK_MAPPING_B = {
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
FGCM_INVERTED_TRIGGER_SUBJECTS = ["C03", "C04"]

# Expected marker labels by task (used for consistency checks)
FGCM_TRIGGER_LABELS_BY_TASK = {
    "audio_base": [
        "startACQ",
        "CSminus",
        "CSplusUnpaired",
        "Gen1",
        "Gen2",
        "Gen3",
        "Gen4",
        "Gen5",
        "Gen6",
        "Gen7",
        "USface",
        "WarningTrial",
        "acTrgBeep",
        "acTrgScream",
    ],
    "audio_cond": [
        "startACQ",
        "CSminus",
        "CSplusUnpaired",
        "CSplusPaired",
        "USface",
        "acTrgBeep",
        "acTrgScream",
    ],
    "audio_test": [
        "startACQ",
        "CSminus",
        "CSplusUnpaired",
        "CSplusPaired",
        "Gen1",
        "Gen2",
        "Gen3",
        "Gen4",
        "Gen5",
        "Gen6",
        "Gen7",
        "USface",
        "acTrgBeep",
        "acTrgScream",
    ],
    "visual_base": [
        "startACQ",
        "CSminus",
        "CSplusUnpaired",
        "Gen1",
        "Gen2",
        "Gen3",
        "Gen4",
        "Gen5",
        "Gen6",
        "Gen7",
        "USface",
        "WarningTrial",
        "acTrgScream",
    ],
    "visual_cond": [
        "startACQ",
        "CSminus",
        "CSplusUnpaired",
        "CSplusPaired",
        "USface",
        "acTrgScream",
    ],
    "visual_test": [
        "startACQ",
        "CSminus",
        "CSplusUnpaired",
        "CSplusPaired",
        "Gen1",
        "Gen2",
        "Gen3",
        "Gen4",
        "Gen5",
        "Gen6",
        "Gen7",
        "USface",
        "acTrgScream",
    ],
}

# Full trigger label union across tasks
FGCM_TRIGGER_LABELS = [
    "startACQ",
    "CSminus",
    "CSplusUnpaired",
    "CSplusPaired",
    "Gen1",
    "Gen2",
    "Gen3",
    "Gen4",
    "Gen5",
    "Gen6",
    "Gen7",
    "USface",
    "WarningTrial",
    "acTrgBeep",
    "acTrgScream",
]

# Dataset authors for dataset_description.json
FGCM_AUTHORS = [
    "Riccardo Bianco",
    "Alejandro Espino",
    "Markus junghoefer",
]

# =============================================================================
# Backward Compatibility Aliases
# =============================================================================

FGT_CHANNEL_MAP = FGCM_CHANNEL_MAP
FGT_CHANNEL_PREFIX_MAP = FGCM_CHANNEL_PREFIX_MAP
FGT_TASKS = FGCM_TASKS
FGT_TASK_MAPPING_A = FGCM_TASK_MAPPING_A
FGT_TASK_MAPPING_B = FGCM_TASK_MAPPING_B
FGT_INVERTED_TRIGGER_SUBJECTS = FGCM_INVERTED_TRIGGER_SUBJECTS

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
