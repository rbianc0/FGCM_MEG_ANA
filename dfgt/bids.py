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
from datetime import datetime, timedelta, timezone
from typing import Optional
import json

import mne
from mne._fiff.constants import FIFF
from mne_bids import write_raw_bids, BIDSPath, make_dataset_description
from mne_bids import write as mne_bids_write
import pandas as pd

from .config import (
    BIDS_ROOT,
    FGCM_CHANNEL_MAP,
    FGCM_CHANNEL_PREFIX_MAP,
    FGCM_TRIGGER_LABELS,
    FGCM_TRIGGER_LABELS_BY_TASK,
    FGCM_AUTHORS,
    ANONYMIZE_DAYS_BACK,
    POWER_LINE_FREQ,
    SUBJECT_LIST_CSV,
)
from .io import load_raw_ctf, get_bids_path
from .utils import source_id_to_bids_id, fix_inverted_triggers, load_subject_list

_MNE_BIDS_CH_MAPPING_PATCHED = False


def _patch_mne_bids_channel_mapping() -> None:
    """Patch mne-bids mapping for CTF axial grads and refs."""
    global _MNE_BIDS_CH_MAPPING_PATCHED
    if _MNE_BIDS_CH_MAPPING_PATCHED:
        return

    original = mne_bids_write._get_ch_type_mapping

    def _get_ch_type_mapping_fgcm(fro="mne", to="bids"):
        mapping = original(fro=fro, to=to)
        mapping["mag"] = "MEGGRADAXIAL"
        mapping["ref_meg"] = "MEGREFGRADAXIAL"
        return mapping

    mne_bids_write._get_ch_type_mapping = _get_ch_type_mapping_fgcm
    _MNE_BIDS_CH_MAPPING_PATCHED = True


def update_channel_types(
    raw: mne.io.Raw,
    channel_map: dict = FGCM_CHANNEL_MAP,
    channel_prefix_map: dict = FGCM_CHANNEL_PREFIX_MAP,
) -> mne.io.Raw:
    """
    Update channel types based on study-specific mapping.

    Parameters
    ----------
    raw : mne.io.Raw
        Raw MEG data
    channel_map : dict
        Mapping of channel names to BIDS channel types
    channel_prefix_map : dict
        Mapping of channel name prefixes to BIDS channel types

    Returns
    -------
    mne.io.Raw
        Raw data with updated channel types
    """
    # Build mapping for channels that exist in this recording
    existing_channels = {
        name: ch_type for name, ch_type in channel_map.items() if name in raw.ch_names
    }

    for ch_name in raw.ch_names:
        if ch_name in existing_channels:
            continue
        for prefix, ch_type in channel_prefix_map.items():
            if ch_name.startswith(prefix):
                existing_channels[ch_name] = ch_type
                break

    if existing_channels:
        raw.set_channel_types(existing_channels)

        for ch_name, ch_type in existing_channels.items():
            if ch_type not in {"eyegaze", "pupil"}:
                continue
            ch_idx = raw.ch_names.index(ch_name)
            if ch_type == "eyegaze":
                raw.info["chs"][ch_idx]["coil_type"] = FIFF.FIFFV_COIL_EYETRACK_POS
            else:
                raw.info["chs"][ch_idx]["coil_type"] = FIFF.FIFFV_COIL_EYETRACK_PUPIL

    return raw


def check_trigger_consistency(
    raw: mne.io.Raw,
    subject_id: str,
    task: str,
    expected_labels: Optional[list] = None,
) -> None:
    """
    Report trigger label consistency using annotations.

    Parameters
    ----------
    raw : mne.io.Raw
        Raw MEG data with annotations loaded
    subject_id : str
        Source subject ID
    task : str
        Task name
    expected_labels : list, optional
        Expected annotation labels
    """
    if raw.annotations is None or len(raw.annotations) == 0:
        print(f"[TRIGGERS] {subject_id} {task}: no annotations found")
        return

    expected = set(expected_labels or [])
    present = list(raw.annotations.description)
    present_set = set(present)
    missing = sorted(expected - present_set) if expected else []
    unexpected = sorted(present_set - expected) if expected else []

    counts = pd.Series(present).value_counts().to_dict()
    print(f"[TRIGGERS] {subject_id} {task}: {len(present)} annotations")
    print(f"[TRIGGERS] {subject_id} {task}: counts {counts}")
    if missing:
        print(f"[TRIGGERS] {subject_id} {task}: missing {missing}")
    if unexpected:
        print(f"[TRIGGERS] {subject_id} {task}: unexpected {unexpected}")


def convert_to_bids(
    subject_id: str,
    task: str,
    bids_root: Path = BIDS_ROOT,
    channel_map: dict = FGCM_CHANNEL_MAP,
    channel_prefix_map: dict = FGCM_CHANNEL_PREFIX_MAP,
    anonymize: bool = True,
    overwrite: bool = False,
    check_triggers: bool = True,
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
    raw = load_raw_ctf(subject_id, task, preload=False)

    # Update channel types
    raw = update_channel_types(raw, channel_map, channel_prefix_map)

    # Fix inverted triggers if needed
    raw = fix_inverted_triggers(raw, subject_id)

    if check_triggers:
        expected_labels = FGCM_TRIGGER_LABELS_BY_TASK.get(task)
        check_trigger_consistency(
            raw, subject_id, task, expected_labels=expected_labels
        )

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

    participants_tsv = bids_root / "participants.tsv"
    if not overwrite and participants_tsv.exists():
        try:
            df_part = pd.read_csv(participants_tsv, sep="\t")
            subject_tag = f"sub-{bids_subject_id}"
            if (
                "participant_id" in df_part.columns
                and subject_tag in df_part["participant_id"].astype(str).tolist()
            ):
                overwrite = True
                print(
                    f"Info: {subject_tag} already in participants.tsv, using overwrite"
                )
        except Exception:
            overwrite = True
            print("Info: participants.tsv exists; using overwrite")

    # Anonymization settings
    anonymize_dict = None
    if anonymize:
        daysback = ANONYMIZE_DAYS_BACK
        meas_date = raw.info.get("meas_date")
        if meas_date is not None:
            if not isinstance(meas_date, datetime):
                meas_date = mne.utils._stamp_to_dt(meas_date)
            if meas_date.tzinfo is None:
                meas_date = meas_date.replace(tzinfo=timezone.utc)
            int32_min = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
                seconds=-(2**31)
            )
            max_daysback = max(0, (meas_date - int32_min).days)
            if daysback > max_daysback:
                print(
                    f"Warning: daysback {daysback} too large for {subject_id}; "
                    f"using {max_daysback} instead"
                )
                daysback = max_daysback

        anonymize_dict = {"daysback": daysback}

    _patch_mne_bids_channel_mapping()

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
    name: str = "FearGenCrossMod (FGCM)",
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
        authors=authors or FGCM_AUTHORS,
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
    df = load_subject_list(subject_list_csv)

    if "megid" not in df.columns:
        raise ValueError("Subject list is missing required column 'megid'")

    # Create participants dataframe
    participants = pd.DataFrame(
        {
            "participant_id": [
                f"sub-{source_id_to_bids_id(sid)}" for sid in df["megid"]
            ],
            "source_id": df["megid"],
        }
    )

    # Add additional columns if available in source
    for col in ["age", "sex"]:
        if col in df.columns:
            participants[col] = df[col]

    # Write TSV
    participants.to_csv(bids_root / "participants.tsv", sep="\t", index=False)

    participants_json_path = bids_root / "participants.json"
    if participants_json_path.exists():
        with participants_json_path.open("r", encoding="utf-8") as f:
            participants_json = json.load(f)
    else:
        participants_json = {}

    participants_json.setdefault(
        "source_id",
        {
            "Description": "Original MEG subject identifier (e.g., C01)",
        },
    )

    with participants_json_path.open("w", encoding="utf-8") as f:
        json.dump(participants_json, f, indent=4)


def batch_convert(
    subject_list: list,
    task_list: list,
    bids_root: Path = BIDS_ROOT,
    channel_map: dict = FGCM_CHANNEL_MAP,
    channel_prefix_map: dict = FGCM_CHANNEL_PREFIX_MAP,
    check_triggers: bool = True,
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
                    channel_prefix_map=channel_prefix_map,
                    check_triggers=check_triggers,
                )
                results["success"].append((subject, task))
                print(f"OK: {subject} - {task}")
            except Exception as e:
                results["failed"].append((subject, task, str(e)))
                print(f"FAIL: {subject} - {task}: {e}")

    return results
