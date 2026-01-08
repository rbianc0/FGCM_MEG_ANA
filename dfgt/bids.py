"""
BIDS conversion module.

Functions for converting CTF MEG data to BIDS format.

Functions:
    convert_to_bids: Convert a single subject/task to BIDS
    update_channel_types: Apply study-specific channel type mappings
    create_dataset_description: Generate dataset_description.json
    create_participants_tsv: Generate participants.tsv
"""

from pathlib import Path
from datetime import timedelta
from typing import Optional

import mne
from mne_bids import write_raw_bids, BIDSPath, make_dataset_description
import pandas as pd

from .config import (
    BIDS_ROOT,
    FGT_CHANNEL_MAP,
    FGT_INVERTED_TRIGGER_SUBJECTS,
    ANONYMIZE_DAYS_BACK,
    POWER_LINE_FREQ,
    SUBJECT_LIST_CSV,
)
from .io import load_raw_ctf, get_bids_path
from .utils import source_id_to_bids_id, fix_inverted_triggers


def update_channel_types(
    raw: mne.io.Raw,
    channel_map: dict = FGT_CHANNEL_MAP,
) -> mne.io.Raw:
    """
    Update channel types based on study-specific mapping.

    Parameters
    ----------
    raw : mne.io.Raw
        Raw MEG data
    channel_map : dict
        Mapping of channel names to BIDS channel types

    Returns
    -------
    mne.io.Raw
        Raw data with updated channel types
    """
    # Build mapping for channels that exist in this recording
    existing_channels = {
        name: ch_type for name, ch_type in channel_map.items() if name in raw.ch_names
    }

    if existing_channels:
        raw.set_channel_types(existing_channels)

    return raw


def convert_to_bids(
    subject_id: str,
    task: str,
    bids_root: Path = BIDS_ROOT,
    channel_map: dict = FGT_CHANNEL_MAP,
    anonymize: bool = True,
    overwrite: bool = False,
) -> BIDSPath:
    """
    Convert a single subject/task from CTF to BIDS format.

    Parameters
    ----------
    subject_id : str
        Source subject ID (e.g., "C01")
    task : str
        Task name (e.g., "audio_base")
    bids_root : Path
        Root directory for BIDS output
    channel_map : dict
        Channel name to type mapping
    anonymize : bool
        Whether to anonymize dates
    overwrite : bool
        Whether to overwrite existing files

    Returns
    -------
    BIDSPath
        Path to the written BIDS data
    """
    # Load raw data
    raw = load_raw_ctf(subject_id, task)

    # Update channel types
    raw = update_channel_types(raw, channel_map)

    # Fix inverted triggers if needed
    if subject_id in FGT_INVERTED_TRIGGER_SUBJECTS:
        raw = fix_inverted_triggers(raw, subject_id)

    # Set power line frequency
    raw.info["line_freq"] = POWER_LINE_FREQ

    # Create BIDS path
    bids_subject_id = source_id_to_bids_id(subject_id)
    task_bids = task.replace("_", "")

    bids_path = BIDSPath(
        subject=bids_subject_id,
        task=task_bids,
        datatype="meg",
        root=bids_root,
    )

    # Anonymization settings
    anonymize_dict = None
    if anonymize:
        anonymize_dict = {"daysback": ANONYMIZE_DAYS_BACK}

    # Write to BIDS
    write_raw_bids(
        raw,
        bids_path,
        anonymize=anonymize_dict,
        overwrite=overwrite,
    )

    return bids_path


def create_dataset_description(
    bids_root: Path = BIDS_ROOT,
    name: str = "FearGenTinn",
    authors: Optional[list] = None,
    license: str = "CC-BY-4.0",
    acknowledgements: str = "",
    funding: Optional[list] = None,
) -> None:
    """
    Generate dataset_description.json for the BIDS dataset.

    Parameters
    ----------
    bids_root : Path
        Root of BIDS dataset
    name : str
        Dataset name
    authors : list, optional
        List of author names
    license : str
        Data license
    acknowledgements : str
        Acknowledgements text
    funding : list, optional
        Funding sources
    """
    make_dataset_description(
        path=bids_root,
        name=name,
        authors=authors or [],
        data_license=license,
        acknowledgements=acknowledgements,
        funding=funding or [],
        overwrite=True,
    )


def create_participants_tsv(
    bids_root: Path = BIDS_ROOT,
    subject_list_csv: Path = SUBJECT_LIST_CSV,
) -> None:
    """
    Generate participants.tsv for the BIDS dataset.

    Parameters
    ----------
    bids_root : Path
        Root of BIDS dataset
    subject_list_csv : Path
        Path to CSV with subject information
    """
    # Load subject list
    df = pd.read_csv(subject_list_csv)

    # Create participants dataframe
    participants = pd.DataFrame(
        {
            "participant_id": [
                f"sub-{source_id_to_bids_id(sid)}" for sid in df["subid"]
            ],
            "source_id": df["subid"],
        }
    )

    # Add additional columns if available in source
    for col in ["age", "sex", "group"]:
        if col in df.columns:
            participants[col] = df[col]

    # Write TSV
    participants.to_csv(bids_root / "participants.tsv", sep="\t", index=False)


def batch_convert(
    subject_list: list,
    task_list: list,
    bids_root: Path = BIDS_ROOT,
    channel_map: dict = FGT_CHANNEL_MAP,
) -> dict:
    """
    Batch convert multiple subjects and tasks to BIDS.

    Parameters
    ----------
    subject_list : list
        List of source subject IDs
    task_list : list
        List of task names
    bids_root : Path
        Root directory for BIDS output
    channel_map : dict
        Channel name to type mapping

    Returns
    -------
    dict
        Results with 'success' and 'failed' lists
    """
    results = {"success": [], "failed": []}

    for subject in subject_list:
        for task in task_list:
            try:
                convert_to_bids(
                    subject,
                    task,
                    bids_root=bids_root,
                    channel_map=channel_map,
                )
                results["success"].append((subject, task))
                print(f"OK: {subject} - {task}")
            except Exception as e:
                results["failed"].append((subject, task, str(e)))
                print(f"FAIL: {subject} - {task}: {e}")

    return results
