"""
BIDS conversion module.

Functions for converting CTF MEG data to BIDS format and managing
post-conversion metadata.

Functions:
    convert_to_bids: Convert a single subject/task to BIDS
    update_channel_types: Apply study-specific channel type mappings
    create_dataset_description: Generate dataset_description.json
    create_participants_tsv: Generate participants.tsv
    add_headshape_files: Attach Polhemus headshape files to BIDS
"""

from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional
import json
import shutil
import statistics

import mne
from mne._fiff.constants import FIFF
from mne_bids import write_raw_bids, BIDSPath, make_dataset_description
from mne_bids import write as mne_bids_write
import pandas as pd

from .config import (
    BIDS_ROOT,
    POS_ROOT,
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
from .utils import (
    source_id_to_bids_id,
    bids_id_to_source_id,
    fix_inverted_triggers,
    load_subject_list,
)

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


def _normalize_source_id(subject_id: str) -> str:
    """
    Normalize a subject identifier to the source (megid) format.

    Parameters
    ----------
    subject_id : str
        Subject ID that may be in source (C01), BIDS (001), or
        BIDS-tagged (sub-001) form.

    Returns
    -------
    str
        Source-style subject ID (e.g., "C01").
    """
    source_id = subject_id.strip()
    if source_id.startswith("sub-"):
        source_id = source_id.replace("sub-", "", 1)
    if source_id.isdigit():
        source_id = bids_id_to_source_id(source_id)
    return source_id


def _select_pos_file(
    ibbid: str,
    pos_root: Path,
    prefer_non_face: bool = True,
) -> Optional[Path]:
    """
    Select a Polhemus .pos file based on ibbid.

    Parameters
    ----------
    ibbid : str
        Identifier used to match files (e.g., "A3122").
    pos_root : Path
        Directory containing .pos files.
    prefer_non_face : bool
        Prefer filenames that do not include "Face" if available.

    Returns
    -------
    Path or None
        Selected .pos file or None if no matches are found.
    """
    if not ibbid:
        return None

    candidates = sorted(pos_root.glob(f"{ibbid}*.pos"))
    if not candidates:
        return None

    if prefer_non_face:
        non_face = [p for p in candidates if "face" not in p.name.lower()]
        if non_face:
            candidates = non_face

    return max(candidates, key=lambda path: path.stat().st_mtime)


def _parse_pos_points(pos_path: Path) -> list[tuple[float, float, float]]:
    """
    Parse xyz points from a Polhemus .pos file.

    Parameters
    ----------
    pos_path : Path
        Path to the .pos file.

    Returns
    -------
    list of tuple
        List of (x, y, z) points parsed from the file.
    """
    points: list[tuple[float, float, float]] = []
    with pos_path.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            tokens = stripped.split()
            numbers: list[float] = []
            for token in tokens:
                try:
                    numbers.append(float(token))
                except ValueError:
                    continue
            if len(numbers) < 3:
                continue
            points.append((numbers[-3], numbers[-2], numbers[-1]))
    return points


def _infer_pos_units(points: list[tuple[float, float, float]]) -> str:
    """
    Infer whether Polhemus points are in centimeters or millimeters.

    Parameters
    ----------
    points : list of tuple
        Parsed xyz points from a .pos file.

    Returns
    -------
    str
        "cm" or "mm", based on the median absolute coordinate magnitude.
    """
    if not points:
        raise ValueError("No coordinate points found in .pos file")

    magnitudes = [abs(value) for point in points for value in point]
    median_value = statistics.median(magnitudes)
    return "cm" if median_value <= 30 else "mm"


def _collect_meg_dirs(bids_root: Path, bids_subject_id: str) -> list[Path]:
    """
    Collect all MEG directories for a BIDS subject.

    Parameters
    ----------
    bids_root : Path
        BIDS dataset root directory.
    bids_subject_id : str
        BIDS subject ID without the "sub-" prefix.

    Returns
    -------
    list of Path
        All MEG directories for the subject.
    """
    subject_dir = bids_root / f"sub-{bids_subject_id}"
    if not subject_dir.exists():
        return []

    session_dirs = [
        path
        for path in subject_dir.iterdir()
        if path.is_dir() and path.name.startswith("ses-")
    ]
    if session_dirs:
        return [path / "meg" for path in session_dirs if (path / "meg").exists()]

    meg_dir = subject_dir / "meg"
    return [meg_dir] if meg_dir.exists() else []


def _get_session_label(meg_dir: Path) -> Optional[str]:
    """
    Extract the session label from a MEG directory path, if present.

    Parameters
    ----------
    meg_dir : Path
        Path to the MEG directory.

    Returns
    -------
    str or None
        Session label without the "ses-" prefix, or None if not sessioned.
    """
    parent_name = meg_dir.parent.name
    if parent_name.startswith("ses-"):
        return parent_name.replace("ses-", "", 1)
    return None


def _build_headshape_filename(
    bids_subject_id: str,
    session: Optional[str] = None,
    acquisition: str = "HEAD",
) -> str:
    """
    Build a BIDS-compliant headshape filename for a subject/session.

    Parameters
    ----------
    bids_subject_id : str
        BIDS subject ID without the "sub-" prefix.
    session : str, optional
        Session label without the "ses-" prefix.
    acquisition : str
        Acquisition label to use for the headshape file.

    Returns
    -------
    str
        Filename for the headshape sidecar (e.g.,
        "sub-001_ses-01_acq-HEAD_headshape.pos").
    """
    parts = [f"sub-{bids_subject_id}"]
    if session:
        parts.append(f"ses-{session}")
    parts.append(f"acq-{acquisition}")
    return "_".join(parts) + "_headshape.pos"


def _update_coordsystem_json(
    coordsystem_path: Path,
    headshape_relpath: str,
    units: str,
    coordinate_system: str = "CTF",
) -> None:
    """
    Update a BIDS coordsystem JSON with headshape metadata.

    Parameters
    ----------
    coordsystem_path : Path
        Path to the *_coordsystem.json file.
    headshape_relpath : str
        Relative path to the headshape file, usually the filename.
    units : str
        Coordinate units for the headshape points ("cm" or "mm").
    coordinate_system : str
        Coordinate system name, typically "CTF" for CTF MEG.
    """
    with coordsystem_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    data["DigitizedHeadPoints"] = headshape_relpath
    data["DigitizedHeadPointsCoordinateSystem"] = coordinate_system
    data["DigitizedHeadPointsCoordinateUnits"] = units

    with coordsystem_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def _update_meg_json(meg_json_path: Path, has_headshape: bool) -> None:
    """
    Update *_meg.json to reflect headshape availability.

    Parameters
    ----------
    meg_json_path : Path
        Path to the *_meg.json file.
    has_headshape : bool
        Whether digitized head points are available.
    """
    with meg_json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    data["DigitizedHeadPoints"] = bool(has_headshape)

    with meg_json_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def add_headshape_files(
    subject_list: list,
    bids_root: Path = BIDS_ROOT,
    pos_root: Path = POS_ROOT,
    subject_list_csv: Path = SUBJECT_LIST_CSV,
    dry_run: bool = False,
    prefer_non_face: bool = True,
) -> dict:
    """
    Attach Polhemus headshape files to an existing BIDS dataset.

    Parameters
    ----------
    subject_list : list
        List of subject IDs (source IDs like "C01" or BIDS IDs like "001").
    bids_root : Path
        Root directory of the BIDS dataset to update.
    pos_root : Path
        Directory containing Polhemus .pos files.
    subject_list_csv : Path
        Subject list CSV for mapping megid to ibbid.
    dry_run : bool
        If True, only report intended changes without writing files.
    prefer_non_face : bool
        Prefer .pos files without "Face" in the filename when available.

    Returns
    -------
    dict
        Result summary with "success", "failed", and "skipped" lists.
    """
    results = {"success": [], "failed": [], "skipped": []}

    if not pos_root.exists():
        raise FileNotFoundError(f"Polhemus directory not found: {pos_root}")

    df = load_subject_list(subject_list_csv)
    if "megid" not in df.columns or "ibbid" not in df.columns:
        raise ValueError("Subject list is missing required columns: megid, ibbid")

    for subject_id in subject_list:
        try:
            source_id = _normalize_source_id(subject_id)
            row = df[df["megid"] == source_id]
            if row.empty:
                results["failed"].append((subject_id, "subject not in list"))
                continue

            ibbid = str(row.iloc[0]["ibbid"]).strip()
            if not ibbid or ibbid.lower() == "nan":
                results["failed"].append((subject_id, "missing ibbid"))
                continue

            pos_path = _select_pos_file(
                ibbid, pos_root, prefer_non_face=prefer_non_face
            )
            if pos_path is None:
                results["failed"].append((subject_id, f"no .pos file for {ibbid}"))
                continue

            points = _parse_pos_points(pos_path)
            units = _infer_pos_units(points)

            bids_subject_id = source_id_to_bids_id(source_id)
            meg_dirs = _collect_meg_dirs(bids_root, bids_subject_id)
            if not meg_dirs:
                results["failed"].append((subject_id, "no MEG directory found"))
                continue

            for meg_dir in meg_dirs:
                session_label = _get_session_label(meg_dir)
                headshape_name = _build_headshape_filename(
                    bids_subject_id=bids_subject_id,
                    session=session_label,
                )
                dest_path = meg_dir / headshape_name

                if dry_run:
                    print(
                        f"[HEADSHAPE] {source_id}: would copy {pos_path.name} -> {dest_path}"
                    )
                else:
                    shutil.copy2(pos_path, dest_path)

                coordsystem_paths = sorted(meg_dir.glob("*_coordsystem.json"))
                if not coordsystem_paths:
                    results["skipped"].append((subject_id, "no coordsystem JSON found"))
                for coordsystem_path in coordsystem_paths:
                    if dry_run:
                        print(
                            f"[HEADSHAPE] {source_id}: would update {coordsystem_path.name}"
                        )
                    else:
                        _update_coordsystem_json(
                            coordsystem_path,
                            headshape_relpath=headshape_name,
                            units=units,
                        )

                meg_json_paths = sorted(meg_dir.glob("*_meg.json"))
                for meg_json_path in meg_json_paths:
                    if dry_run:
                        print(
                            f"[HEADSHAPE] {source_id}: would update {meg_json_path.name}"
                        )
                    else:
                        _update_meg_json(meg_json_path, has_headshape=True)

            results["success"].append((subject_id, pos_path.name, units))
        except Exception as exc:
            results["failed"].append((subject_id, str(exc)))

    return results


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
