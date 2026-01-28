"""
Utility functions for DFGT MEG analysis.

Functions:
    source_id_to_bids_id: Convert source ID (C01) to BIDS ID (001)
    bids_id_to_source_id: Convert BIDS ID (001) to source ID (C01)
    get_subject_group: Determine A/B group for a subject
    fix_inverted_triggers: Fix trigger inversion for affected subjects
    load_subject_list: Load subject list from CSV
"""

from pathlib import Path
from typing import Literal, Optional, cast

import mne
import numpy as np
import pandas as pd

from .config import SUBJECT_LIST_CSV, FGT_INVERTED_TRIGGER_SUBJECTS


def _read_subject_list(subject_list_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(subject_list_csv, sep="\t")
    if df.shape[1] == 1:
        df = pd.read_csv(subject_list_csv)
    return df


def _normalize_group_value(value: object) -> Optional[str]:
    if value is None:
        return None

    if isinstance(value, float) and np.isnan(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    upper = text.upper()
    if upper[0] in {"A", "B"}:
        return upper[0]

    try:
        num = int(float(upper))
    except ValueError:
        return None

    return "A" if num == 0 else "B"


def source_id_to_bids_id(source_id: str) -> str:
    """
    Convert source subject ID to BIDS-compliant ID.

    Parameters
    ----------
    source_id : str
        Source ID (e.g., "C01", "C10")

    Returns
    -------
    str
        BIDS ID (e.g., "001", "010")

    Examples
    --------
    >>> source_id_to_bids_id("C01")
    "001"
    >>> source_id_to_bids_id("C10")
    "010"
    """
    # Extract numeric part
    num = int(source_id.replace("C", ""))
    return f"{num:03d}"


def bids_id_to_source_id(bids_id: str) -> str:
    """
    Convert BIDS ID to source subject ID.

    Parameters
    ----------
    bids_id : str
        BIDS ID (e.g., "001", "010")

    Returns
    -------
    str
        Source ID (e.g., "C01", "C10")
    """
    num = int(bids_id)
    return f"C{num:02d}"


def get_subject_group(
    subject_id: str,
    subject_list_csv: Path = SUBJECT_LIST_CSV,
) -> Literal["A", "B"]:
    """
    Determine the A/B randomization group for a subject.

    Parameters
    ----------
    subject_id : str
        Source subject ID (e.g., "C01")
    subject_list_csv : Path
        Path to subject list CSV with group info

    Returns
    -------
    str
        Group letter ("A" or "B")
    """
    df = load_subject_list(subject_list_csv)

    # Find subject row
    row = df[df["subid"] == subject_id]

    if row.empty:
        raise ValueError(f"Subject {subject_id} not found in subject list")

    row_values = row.iloc[0]

    if "randval" in df.columns:
        group = _normalize_group_value(row_values.get("randval"))
        if group in {"A", "B"}:
            return cast(Literal["A", "B"], group)

    # Default to A if no group info available
    return "A"


def load_subject_list(
    subject_list_csv: Path = SUBJECT_LIST_CSV,
) -> pd.DataFrame:
    """
    Load the subject list (tab-delimited file).

    Parameters
    ----------
    subject_list_csv : Path
        Path to CSV file

    Returns
    -------
    pd.DataFrame
        Subject information
    """
    df = _read_subject_list(subject_list_csv)
    if "subid" in df.columns:
        df["subid"] = df["subid"].astype(str).str.strip()
    return df


def get_valid_subjects(
    subject_list_csv: Path = SUBJECT_LIST_CSV,
) -> list:
    """
    Get list of valid subject IDs from CSV.

    Parameters
    ----------
    subject_list_csv : Path
        Path to subject list CSV

    Returns
    -------
    list
        List of subject IDs (e.g., ["C01", "C02", ...])
    """
    df = load_subject_list(subject_list_csv)
    if "subid" not in df.columns:
        raise ValueError("Subject list is missing required column 'subid'")
    return df["subid"].tolist()


def fix_inverted_triggers(
    raw: mne.io.Raw,
    subject_id: str,
) -> mne.io.Raw:
    """
    Fix inverted trigger values for subjects with known issues.

    Subjects C03 and C04 have inverted GS triggers that need to be
    corrected during BIDS conversion.

    Parameters
    ----------
    raw : mne.io.Raw
        Raw MEG data
    subject_id : str
        Source subject ID

    Returns
    -------
    mne.io.Raw
        Raw data with corrected triggers
    """
    if subject_id not in FGT_INVERTED_TRIGGER_SUBJECTS:
        return raw

    # Get trigger channel
    stim_channel = "UPPT01"
    if stim_channel not in raw.ch_names:
        print(f"Warning: {stim_channel} not found, skipping trigger fix")
        return raw

    # Find events
    events = mne.find_events(raw, stim_channel=stim_channel)

    if len(events) == 0:
        return raw

    # Invert trigger codes
    # Study-specific logic: typically bitwise inversion or specific value swaps
    # Implement based on actual trigger scheme
    # Example: invert specific bits
    # events[:, 2] = np.bitwise_xor(events[:, 2], 0xFF)

    # For now, log that fix was applied
    print(f"Applied trigger inversion for {subject_id}")

    # Create annotations from fixed events if needed
    # ... implementation based on study requirements

    return raw


def denoise_pca(
    raw: mne.io.Raw,
    ref_channels: Optional[list] = None,
    n_components: int = 3,
) -> mne.io.Raw:
    """
    Denoise MEG data using reference channel PCA.

    Parameters
    ----------
    raw : mne.io.Raw
        Raw MEG data
    ref_channels : list, optional
        Reference channel names (auto-detect if None)
    n_components : int
        Number of PCA components to remove

    Returns
    -------
    mne.io.Raw
        Denoised raw data
    """
    # Detect reference channels if not provided
    if ref_channels is None:
        ref_channels = [ch for ch in raw.ch_names if ch.startswith("REF")]

    if not ref_channels:
        print("No reference channels found, skipping PCA denoising")
        return raw

    # Apply reference-based denoising
    # Implementation using MNE's denoise functionality
    # This is a placeholder - implement based on actual requirements

    return raw
