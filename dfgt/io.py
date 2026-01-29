"""
I/O module for loading MEG data from various sources.

Functions:
    load_raw_ctf: Load raw CTF MEG data (.ds directories)
    load_raw_bids: Load raw data from BIDS format
    load_epochs: Load preprocessed epochs
    load_behavioral: Load behavioral data files
    get_raw_path: Construct path to raw CTF data
    get_bids_path: Construct BIDS path for a subject/task
"""

from pathlib import Path
import re
from typing import Optional, Literal

import mne
from mne_bids import BIDSPath, read_raw_bids

from .config import (
    MEG_RAW_ROOT,
    BIDS_ROOT,
    DERIVATIVES_ROOT,
    BEH_ROOT,
    FGCM_TASK_MAPPING_A,
    FGCM_TASK_MAPPING_B,
)
from .utils import get_subject_group, source_id_to_bids_id


def get_raw_path(
    subject_id: str,
    task: str,
    raw_root: Path = MEG_RAW_ROOT,
) -> Path:
    """
    Construct path to raw CTF MEG data.

    Parameters
    ----------
    subject_id : str
        Source subject ID (e.g., "C01")
    task : str
        Task name (e.g., "audio_base")
    raw_root : Path
        Root directory of raw MEG data

    Returns
    -------
    Path
        Path to the .ds directory

    Raises
    ------
    FileNotFoundError
        If the .ds directory is not found
    """
    # Determine run number based on subject group
    group = get_subject_group(subject_id)
    task_mapping = FGCM_TASK_MAPPING_A if group == "A" else FGCM_TASK_MAPPING_B

    # Find run number for this task
    run_number = None
    for run, task_name in task_mapping.items():
        if task_name == task:
            run_number = run
            break

    if run_number is None:
        raise ValueError(f"Task '{task}' not found in task mapping")

    # Construct path: MEG_RAW_ROOT/C01/C01-1/*.ds
    subject_dir = raw_root / subject_id / f"{subject_id}-1"

    if not subject_dir.exists():
        raise FileNotFoundError(f"Subject directory not found: {subject_dir}")

    try:
        target_run = int(run_number)
    except ValueError as exc:
        raise ValueError(
            f"Invalid run number '{run_number}' for task '{task}'"
        ) from exc

    ds_files = sorted(subject_dir.glob("*.ds"))
    if not ds_files:
        raise FileNotFoundError(f"No .ds directories found in {subject_dir}")

    run_pattern = re.compile(r"_(\d+)\.ds$")
    run_map: dict[int, list[Path]] = {}
    for ds_path in ds_files:
        match = run_pattern.search(ds_path.name)
        if not match:
            continue
        run_int = int(match.group(1))
        run_map.setdefault(run_int, []).append(ds_path)

    candidates = run_map.get(target_run, [])
    if not candidates:
        available_files = ", ".join(path.name for path in ds_files)
        raise FileNotFoundError(
            f"No .ds file found for run {run_number} in {subject_dir}. "
            f"Available files: {available_files}"
        )
    if len(candidates) > 1:
        matches = ", ".join(path.name for path in candidates)
        raise FileExistsError(
            f"Multiple .ds files found for run {run_number} in {subject_dir}: {matches}"
        )

    return candidates[0]


def load_raw_ctf(
    subject_id: str,
    task: str,
    raw_root: Path = MEG_RAW_ROOT,
    preload: bool = True,
) -> mne.io.Raw:
    """
    Load raw CTF MEG data.

    Parameters
    ----------
    subject_id : str
        Source subject ID (e.g., "C01")
    task : str
        Task name (e.g., "audio_base")
    raw_root : Path
        Root directory of raw MEG data
    preload : bool
        Whether to preload data into memory

    Returns
    -------
    mne.io.Raw
        Raw MEG data
    """
    ds_path = get_raw_path(subject_id, task, raw_root)
    raw = mne.io.read_raw_ctf(ds_path, preload=preload)
    return raw


def get_bids_path(
    subject_id: str,
    task: str,
    bids_root: Path = BIDS_ROOT,
    datatype: str = "meg",
) -> BIDSPath:
    """
    Construct a BIDSPath for a subject/task.

    Parameters
    ----------
    subject_id : str
        BIDS subject ID (e.g., "001") or source ID (e.g., "C01")
    task : str
        Task name (e.g., "audio_base")
    bids_root : Path
        Root of BIDS dataset
    datatype : str
        Data type (default: "meg")

    Returns
    -------
    BIDSPath
        BIDS path object
    """
    # Convert source ID to BIDS ID if needed
    if subject_id.startswith("C"):
        subject_id = source_id_to_bids_id(subject_id)

    # Remove underscore from task name for BIDS
    task_bids = task.replace("_", "")

    return BIDSPath(
        subject=subject_id,
        task=task_bids,
        datatype=datatype,
        root=bids_root,
    )


def load_raw_bids(
    subject_id: str,
    task: str,
    bids_root: Path = BIDS_ROOT,
) -> mne.io.Raw:
    """
    Load raw MEG data from BIDS format.

    Parameters
    ----------
    subject_id : str
        BIDS subject ID (e.g., "001") or source ID (e.g., "C01")
    task : str
        Task name (e.g., "audio_base")
    bids_root : Path
        Root of BIDS dataset

    Returns
    -------
    mne.io.Raw
        Raw MEG data
    """
    bids_path = get_bids_path(subject_id, task, bids_root)
    raw = read_raw_bids(bids_path)
    return raw


def load_epochs(
    subject_id: str,
    task: str,
    derivatives_root: Path = DERIVATIVES_ROOT,
    pipeline: str = "preprocessing",
) -> mne.Epochs:
    """
    Load preprocessed epochs.

    Parameters
    ----------
    subject_id : str
        BIDS subject ID or source ID
    task : str
        Task name
    derivatives_root : Path
        Root of derivatives directory
    pipeline : str
        Name of processing pipeline subdirectory

    Returns
    -------
    mne.Epochs
        Preprocessed epochs
    """
    if subject_id.startswith("C"):
        subject_id = source_id_to_bids_id(subject_id)

    task_bids = task.replace("_", "")
    epochs_path = (
        derivatives_root
        / pipeline
        / f"sub-{subject_id}"
        / "meg"
        / f"sub-{subject_id}_task-{task_bids}_epo.fif"
    )

    if not epochs_path.exists():
        raise FileNotFoundError(f"Epochs file not found: {epochs_path}")

    return mne.read_epochs(epochs_path)


def load_behavioral(
    subject_id: str,
    task: str,
    beh_root: Path = BEH_ROOT,
) -> Optional[Path]:
    """
    Get path to behavioral data file.

    Parameters
    ----------
    subject_id : str
        Source subject ID (e.g., "C01")
    task : str
        Task name
    beh_root : Path
        Root of behavioral data directory

    Returns
    -------
    Path or None
        Path to behavioral file if found
    """
    # Implementation depends on behavioral file naming convention
    # Placeholder - implement based on actual file structure
    beh_dir = beh_root / subject_id

    if not beh_dir.exists():
        return None

    # Search for task-matching file
    for pattern in [f"*{task}*.csv", f"*{task}*.mat", f"*{task}*.tsv"]:
        files = list(beh_dir.glob(pattern))
        if files:
            return files[0]

    return None
