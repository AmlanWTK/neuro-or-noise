"""Five scalar artifact features per epoch.

This is the headline experiment. A logistic regression on these five numbers
has no capacity to learn a subtle neural biomarker. If it reaches ~90% under an
epoch-level split and collapses under leave-one-subject-out, the discriminative
signal is non-neural and subject-stable -- which is the paper's central claim.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import welch
from scipy.stats import kurtosis


FEATURE_NAMES = [
    "hf_power_60_100",   # EMG-dominant band
    "line_resid_45_55",  # residual mains / notch signature
    "kurtosis",          # spikiness -> movement & muscle bursts
    "zero_cross_rate",   # crude dominant-frequency proxy
    "rms",               # amplitude / impedance signature
]


def epoch_features(x: np.ndarray, fs: int) -> np.ndarray:
    """x: (n_channels, n_samples) -> (5,) channel-averaged features."""
    f, p = welch(x, fs=fs, nperseg=min(512, x.shape[-1]), axis=-1)

    def band_power(lo, hi):
        m = (f >= lo) & (f < hi)
        return p[..., m].sum(axis=-1)

    total = p.sum(axis=-1) + 1e-12
    hf = (band_power(60, 100) / total).mean()
    line = (band_power(45, 55) / total).mean()
    kur = kurtosis(x, axis=-1).mean()
    zcr = (np.diff(np.signbit(x), axis=-1).sum(axis=-1) / x.shape[-1]).mean()
    rms = np.sqrt((x ** 2).mean(axis=-1)).mean()
    return np.array([hf, line, kur, zcr, rms], dtype=np.float64)


def featurise(X: np.ndarray, fs: int) -> np.ndarray:
    """X: (n_epochs, n_channels, n_samples) -> (n_epochs, 5)"""
    return np.stack([epoch_features(x, fs) for x in X])


def channel_hf_profile(X: np.ndarray, fs: int) -> np.ndarray:
    """Per-channel 60-100 Hz relative power, averaged over epochs.

    Use for the topography figure. Concentration at temporal (T3/T4) and
    lateral-frontal (F7/F8) sites is the classic EMG signature.
    """
    f, p = welch(X, fs=fs, nperseg=min(512, X.shape[-1]), axis=-1)
    m = (f >= 60) & (f < 100)
    return (p[..., m].sum(-1) / (p.sum(-1) + 1e-12)).mean(axis=0)
