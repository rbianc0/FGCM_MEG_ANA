"""
MEG preprocessing module.

Functions for preprocessing MEG data including filtering, artifact rejection,
ICA, and epoching.

Functions:
    preprocess: Main preprocessing pipeline
    apply_gradient_compensation: CTF gradient compensation
    filter_raw: Bandpass and notch filtering
    run_ica: ICA decomposition and artifact removal
    create_epochs: Epoch data around events
    reject_artifacts: Automatic artifact rejection
"""

from pathlib import Path
from typing import Optional, Literal

import mne
from mne.preprocessing import ICA
import numpy as np

from .config import (
    DERIVATIVES_ROOT,
    ICA_N_COMPONENTS,
    ICA_METHOD,
    POWER_LINE_FREQ,
)
from .io import load_raw_bids, get_bids_path
from .utils import source_id_to_bids_id


def apply_gradient_compensation(
    raw: mne.io.Raw,
    grade: int = 3,
) -> mne.io.Raw:
    """
    Apply CTF gradient compensation.

    Parameters
    ----------
    raw : mne.io.Raw
        Raw CTF MEG data
    grade : int
        Compensation grade (0-3)

    Returns
    -------
    mne.io.Raw
        Compensated raw data
    """
    raw.apply_gradient_compensation(grade)
    return raw


def filter_raw(
    raw: mne.io.Raw,
    l_freq: float = 0.1,
    h_freq: float = 100.0,
    notch_freq: Optional[float] = None,
) -> mne.io.Raw:
    """
    Apply bandpass and notch filtering.

    Parameters
    ----------
    raw : mne.io.Raw
        Raw MEG data
    l_freq : float
        Low cutoff frequency (Hz)
    h_freq : float
        High cutoff frequency (Hz)
    notch_freq : float, optional
        Power line frequency for notch filter (Hz)

    Returns
    -------
    mne.io.Raw
        Filtered raw data
    """
    # Bandpass filter
    raw.filter(l_freq=l_freq, h_freq=h_freq)

    # Notch filter for power line
    if notch_freq is None:
        notch_freq = POWER_LINE_FREQ

    raw.notch_filter(freqs=np.arange(notch_freq, h_freq, notch_freq))

    return raw


def run_ica(
    raw: mne.io.Raw,
    n_components: int = ICA_N_COMPONENTS,
    method: str = ICA_METHOD,
    random_state: int = 42,
    ecg_channel: Optional[str] = "ECG",
) -> tuple[mne.io.Raw, ICA]:
    """
    Run ICA for artifact removal.

    Parameters
    ----------
    raw : mne.io.Raw
        Raw MEG data (filtered)
    n_components : int
        Number of ICA components
    method : str
        ICA method ("picard", "fastica", "infomax")
    random_state : int
        Random seed for reproducibility
    ecg_channel : str, optional
        ECG channel name for heartbeat detection

    Returns
    -------
    tuple
        (cleaned raw data, fitted ICA object)
    """
    # Fit ICA
    ica = ICA(
        n_components=n_components,
        method=method,
        random_state=random_state,
    )

    # Fit on high-pass filtered data for better component separation
    raw_copy = raw.copy().filter(l_freq=1.0, h_freq=None)
    ica.fit(raw_copy)

    # Find ECG artifacts
    ecg_indices = []
    if ecg_channel and ecg_channel in raw.ch_names:
        ecg_indices, ecg_scores = ica.find_bads_ecg(raw, ch_name=ecg_channel)

    # Exclude bad components
    ica.exclude = ecg_indices

    # Apply ICA
    raw = ica.apply(raw)

    return raw, ica


def create_epochs(
    raw: mne.io.Raw,
    events: np.ndarray,
    event_id: dict,
    tmin: float = -0.2,
    tmax: float = 0.8,
    baseline: tuple = (-0.2, 0),
    reject: Optional[dict] = None,
) -> mne.Epochs:
    """
    Create epochs from continuous data.

    Parameters
    ----------
    raw : mne.io.Raw
        Raw MEG data
    events : np.ndarray
        Events array (n_events, 3)
    event_id : dict
        Event name to code mapping
    tmin : float
        Epoch start time (seconds)
    tmax : float
        Epoch end time (seconds)
    baseline : tuple
        Baseline correction window
    reject : dict, optional
        Rejection thresholds by channel type

    Returns
    -------
    mne.Epochs
        Epoched data
    """
    epochs = mne.Epochs(
        raw,
        events,
        event_id,
        tmin=tmin,
        tmax=tmax,
        baseline=baseline,
        reject=reject,
        preload=True,
    )

    return epochs


def reject_artifacts_autoreject(
    epochs: mne.Epochs,
) -> mne.Epochs:
    """
    Apply autoreject for automatic artifact rejection.

    Parameters
    ----------
    epochs : mne.Epochs
        Epoched data

    Returns
    -------
    mne.Epochs
        Cleaned epochs
    """
    try:
        from autoreject import AutoReject

        ar = AutoReject(random_state=42)
        epochs_clean = ar.fit_transform(epochs)
        return epochs_clean
    except ImportError:
        print("autoreject not installed, skipping automatic rejection")
        return epochs


def reject_artifacts_kurtosis(
    epochs: mne.Epochs,
    threshold: float = 4.0,
) -> mne.Epochs:
    """
    Reject epochs based on kurtosis.

    Parameters
    ----------
    epochs : mne.Epochs
        Epoched data
    threshold : float
        Kurtosis threshold for rejection

    Returns
    -------
    mne.Epochs
        Cleaned epochs
    """
    from scipy.stats import kurtosis

    data = epochs.get_data()
    kurt = np.abs(kurtosis(data, axis=2)).max(axis=1)
    good_epochs = kurt < threshold

    return epochs[good_epochs]


def preprocess(
    subject_id: str,
    task: str,
    events: np.ndarray,
    event_id: dict,
    tmin: float = -0.2,
    tmax: float = 0.8,
    l_freq: float = 0.1,
    h_freq: float = 100.0,
    run_ica_flag: bool = True,
    save: bool = True,
    derivatives_root: Path = DERIVATIVES_ROOT,
) -> mne.Epochs:
    """
    Run complete preprocessing pipeline.

    Parameters
    ----------
    subject_id : str
        Source or BIDS subject ID
    task : str
        Task name
    events : np.ndarray
        Events array
    event_id : dict
        Event ID mapping
    tmin, tmax : float
        Epoch time window
    l_freq, h_freq : float
        Filter frequencies
    run_ica_flag : bool
        Whether to run ICA
    save : bool
        Whether to save processed epochs
    derivatives_root : Path
        Output directory

    Returns
    -------
    mne.Epochs
        Preprocessed epochs
    """
    # Load raw data from BIDS
    raw = load_raw_bids(subject_id, task)

    # Apply gradient compensation
    raw = apply_gradient_compensation(raw)

    # Filter
    raw = filter_raw(raw, l_freq=l_freq, h_freq=h_freq)

    # ICA
    if run_ica_flag:
        raw, ica = run_ica(raw)

    # Create epochs
    epochs = create_epochs(raw, events, event_id, tmin=tmin, tmax=tmax)

    # Artifact rejection
    epochs = reject_artifacts_autoreject(epochs)

    # Save if requested
    if save:
        if subject_id.startswith("C"):
            subject_id = source_id_to_bids_id(subject_id)

        task_bids = task.replace("_", "")
        output_dir = derivatives_root / "preprocessing" / f"sub-{subject_id}" / "meg"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"sub-{subject_id}_task-{task_bids}_epo.fif"
        epochs.save(output_path, overwrite=True)

    return epochs
