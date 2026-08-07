"""Loading, filtering, epoching, normalisation.

Two data sources:
  load_husm()  -- the real Mumtaz/HUSM recordings (needs mne + the .edf files)
  make_synthetic() -- a controlled fake dataset with a KNOWN shortcut, used to
                      validate the whole pipeline before real data arrives.
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, filtfilt, iirnotch

from .config import Config


@dataclass
class Recording:
    """One continuous recording from one subject."""
    subject: str
    label: int          # 1 = MDD, 0 = HC
    condition: str      # 'EC' | 'EO'
    data: np.ndarray    # (n_channels, n_samples)


@dataclass
class EpochSet:
    X: np.ndarray        # (n_epochs, n_channels, n_samples)
    y: np.ndarray        # (n_epochs,)
    subject: np.ndarray  # (n_epochs,) subject id per epoch -- drives grouping
    condition: np.ndarray

    def __len__(self):
        return len(self.y)

    @property
    def n_subjects(self):
        return len(np.unique(self.subject))


# --- filtering ---------------------------------------------------------------

def bandpass(x: np.ndarray, lo: float, hi: float, fs: int, order: int = 4):
    nyq = fs / 2.0
    hi = min(hi, nyq * 0.99)
    b, a = butter(order, [lo / nyq, hi / nyq], btype="band")
    return filtfilt(b, a, x, axis=-1)


def notch(x: np.ndarray, f0: float, fs: int, q: float = 30.0):
    b, a = iirnotch(f0 / (fs / 2.0), q)
    return filtfilt(b, a, x, axis=-1)


# --- epoching ----------------------------------------------------------------

def epoch_recording(rec: Recording, cfg: Config):
    """Slice one recording into epochs. Overlap is in SECONDS of shared signal."""
    win = int(round(cfg.epoch_sec * cfg.fs))
    hop = int(round((cfg.epoch_sec - cfg.overlap_sec) * cfg.fs))
    if hop <= 0:
        raise ValueError("overlap_sec must be smaller than epoch_sec")
    n = rec.data.shape[-1]
    starts = range(0, max(0, n - win + 1), hop)
    return np.stack([rec.data[:, s:s + win] for s in starts]) if starts else None


def build_epochs(recs: list[Recording], cfg: Config) -> EpochSet:
    lo, hi = cfg.band_range()
    Xs, ys, subs, conds = [], [], [], []
    for rec in recs:
        if cfg.condition != "both" and rec.condition != cfg.condition:
            continue
        sig = rec.data.astype(np.float64)
        if cfg.apply_notch:
            sig = notch(sig, cfg.notch_hz, cfg.fs)
        sig = bandpass(sig, lo, hi, cfg.fs)
        chunks = epoch_recording(Recording(rec.subject, rec.label, rec.condition, sig), cfg)
        if chunks is None or len(chunks) == 0:
            continue
        Xs.append(chunks)
        ys.append(np.full(len(chunks), rec.label))
        subs.append(np.full(len(chunks), rec.subject))
        conds.append(np.full(len(chunks), rec.condition))
    return EpochSet(
        X=np.concatenate(Xs).astype(np.float32),
        y=np.concatenate(ys).astype(np.int64),
        subject=np.concatenate(subs),
        condition=np.concatenate(conds),
    )


# --- normalisation -----------------------------------------------------------

def normalise(es: EpochSet, cfg: Config, train_idx: np.ndarray | None = None):
    """z-score with an explicit, auditable scope.

    global      -- statistics over the entire dataset  (leaks test info)
    per_subject -- statistics per subject              (removes subject offset)
    train_fold  -- statistics from training epochs only (correct)
    """
    X = es.X.copy()
    if cfg.norm_scope == "global":
        mu, sd = X.mean(), X.std() + 1e-8
        X = (X - mu) / sd
    elif cfg.norm_scope == "per_subject":
        for s in np.unique(es.subject):
            m = es.subject == s
            mu = X[m].mean(axis=(0, 2), keepdims=True)
            sd = X[m].std(axis=(0, 2), keepdims=True) + 1e-8
            X[m] = (X[m] - mu) / sd
    elif cfg.norm_scope == "train_fold":
        if train_idx is None:
            raise ValueError("train_fold scope needs train_idx")
        mu = X[train_idx].mean(axis=(0, 2), keepdims=True)
        sd = X[train_idx].std(axis=(0, 2), keepdims=True) + 1e-8
        X = (X - mu) / sd
    else:
        raise ValueError(cfg.norm_scope)
    return EpochSet(X, es.y, es.subject, es.condition)


# --- real data ---------------------------------------------------------------

def load_husm(root: str, fs: int = 256) -> list[Recording]:
    """Load the Mumtaz/HUSM MDD dataset (.edf files).

    Expected filenames contain 'MDD'/'H' and 'EC'/'EO', e.g.
        MDD S12 EC.edf, H S03 EO.edf
    Adjust the parser to whatever the download actually gives you -- verify
    channel order and count (should be 19 EEG channels) before trusting it.
    """
    import mne  # lazy: only needed for real data

    recs = []
    for path in sorted(glob.glob(os.path.join(root, "*.edf"))):
        name = os.path.basename(path)
        upper = name.upper()
        label = 1 if "MDD" in upper else 0
        cond = "EC" if "EC" in upper else "EO"
        subject = f"{'MDD' if label else 'HC'}_{''.join(c for c in name if c.isdigit())}"
        raw = mne.io.read_raw_edf(path, preload=True, verbose="ERROR")
        raw.pick("eeg")
        if int(raw.info["sfreq"]) != fs:
            raw.resample(fs, verbose="ERROR")
        recs.append(Recording(subject, label, cond, raw.get_data()))
    if not recs:
        raise FileNotFoundError(f"no .edf files under {root}")
    return recs


# --- synthetic data with a planted shortcut ----------------------------------

def make_synthetic(n_mdd=34, n_hc=30, minutes=5.0, cfg: Config | None = None,
                   shortcut_strength=1.6, neural_strength=0.30, seed=0,
                   shortcut_mode="class_correlated"):
    """Fake EEG with a KNOWN structure, for validating the experimental design.

    Each subject gets:
      * pink-ish background noise
      * a WEAK genuine class effect in the alpha band (the 'real' biomarker)
      * a STRONG subject-specific narrowband component in the gamma range,
        standing in for EMG / impedance / line-noise signatures.

    shortcut_mode controls what that component encodes -- the two failure modes
    behave DIFFERENTLY and the probes must tell them apart:

      'class_correlated' -- the artifact genuinely differs by class (e.g. MDD
          patients are more tense during recording). It transfers across
          subjects, so LOSO stays high. The result is real but NOT NEURAL:
          you are measuring jaw tension, not cortex.
      'subject_only'     -- the artifact is pure subject identity, uncorrelated
          with class. Epoch-level splits memorise it and score near 1.0; LOSO
          collapses to chance. This is classic leakage.

    Real data may contain either or both. P1 detects the fingerprint, P2
    distinguishes the modes.

    The planted shortcut is constant within a subject. So:
      epoch-level random splits  -> near-perfect accuracy (memorises subjects)
      leave-one-subject-out      -> collapses toward the weak neural effect

    If your pipeline does NOT reproduce that pattern here, the pipeline is
    broken -- fix it before touching real data.
    """
    cfg = cfg or Config()
    rng = np.random.default_rng(seed)
    fs, n_ch = cfg.fs, cfg.n_channels
    n = int(minutes * 60 * fs)
    t = np.arange(n) / fs
    recs = []

    for i in range(n_mdd + n_hc):
        label = 1 if i < n_mdd else 0
        sid = f"{'MDD' if label else 'HC'}_{i:03d}"

        # subject-specific gamma signature
        cc = 1.0 if shortcut_mode == "class_correlated" else 0.0
        f0 = rng.normal(70 + 8 * label * cc, 3.0 if cc else 12.0)
        amp = rng.lognormal(np.log(shortcut_strength * (1 + 0.35 * label * cc)),
                            0.25 if cc else 0.55)
        phase = rng.uniform(0, 2 * np.pi, size=n_ch)[:, None]

        for cond in ("EC", "EO"):
            # 1/f-ish background
            white = rng.standard_normal((n_ch, n))
            spec = np.fft.rfft(white, axis=-1)
            freqs = np.fft.rfftfreq(n, 1 / fs)
            spec /= (1.0 + freqs) ** 0.6
            bg = np.fft.irfft(spec, n=n, axis=-1)
            bg /= bg.std() + 1e-9

            # weak genuine alpha effect (HC have more alpha, esp. eyes-closed)
            a_amp = neural_strength * (1.0 - 0.45 * label) * (1.3 if cond == "EC" else 1.0)
            alpha = a_amp * np.sin(2 * np.pi * 10.0 * t + rng.uniform(0, 6.28))

            # the planted shortcut: subject-stable, class-correlated gamma
            emg = amp * np.sin(2 * np.pi * f0 * t + phase)
            emg *= (1 + 0.3 * rng.standard_normal((n_ch, 1)))

            recs.append(Recording(sid, label, cond, bg + alpha + emg))
    return recs
