"""Loading, filtering, epoching, normalisation.

Two data sources:
  load_husm()  -- the real Mumtaz/HUSM recordings (needs mne + the .edf files)
  make_synthetic() -- a controlled fake dataset with a KNOWN shortcut, used to
                      validate the whole pipeline before real data arrives.
"""
from __future__ import annotations

import glob
import os
import re
from collections import Counter
from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, filtfilt, iirnotch

from .config import Config


@dataclass
class Recording:
    """One continuous recording from one subject."""
    subject: str
    label: int          # 1 = MDD, 0 = HC
    condition: str      # 'EC' | 'EO' | 'TASK'
    data: np.ndarray    # (n_channels, n_samples)
    ch_names: list | None = None


@dataclass
class EpochSet:
    X: np.ndarray        # (n_epochs, n_channels, n_samples)
    y: np.ndarray        # (n_epochs,)
    subject: np.ndarray  # (n_epochs,) subject id per epoch -- drives grouping
    condition: np.ndarray
    ch_names: list | None = None

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


def bandstop(x: np.ndarray, lo: float, hi: float, fs: int, order: int = 4):
    """Excise a frequency range entirely (wider and harder than a notch)."""
    nyq = fs / 2.0
    b, a = butter(order, [lo / nyq, min(hi, nyq * 0.99) / nyq], btype="bandstop")
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
        stop = cfg.band_stop()
        if stop is not None:
            sig = bandstop(sig, stop[0], stop[1], cfg.fs)
        chunks = epoch_recording(
            Recording(rec.subject, rec.label, rec.condition, sig, rec.ch_names), cfg)
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
        ch_names=(recs[0].ch_names if recs and recs[0].ch_names else list(CANONICAL_19)),
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
    return EpochSet(X, es.y, es.subject, es.condition, es.ch_names)


# --- real data ---------------------------------------------------------------

# The 19 scalp electrodes of the 10-20 system, in the order the HUSM files
# store them. The released .edf files ALSO contain non-scalp channels that must
# NOT be fed to the model:
#   'EEG A2-A1'      -- the linked-ear reference itself
#   'EEG 23A-23R'    -- auxiliary bipolar pair
#   'EEG 24A-24R'    -- auxiliary bipolar pair
# Files carry either 22 channels (19 + A2A1 + 23A + 24A) or 20 (19 + A2A1).
# Selecting by POSITION would therefore mix different signals across files;
# selecting by NAME is the only safe option.
CANONICAL_19 = ["Fp1", "F3", "C3", "P3", "O1", "F7", "T3", "T5", "Fz",
                "Fp2", "F4", "C4", "P4", "O2", "F8", "T4", "T6", "Cz", "Pz"]

NON_SCALP_HINTS = ("A2-A1", "23A", "24A", "EOG", "ECG", "EMG", "STATUS")


def canonical_channel(raw_name: str) -> str:
    """'EEG Fp1-LE' -> 'Fp1'.  Robust to 'EEG '/'-LE'/'-REF' decoration."""
    n = raw_name.strip()
    if n.upper().startswith("EEG "):
        n = n[4:]
    for suffix in ("-LE", "-REF", "-A1", "-A2", "-AVG"):
        if n.upper().endswith(suffix):
            n = n[: -len(suffix)]
            break
    return n.strip()


def select_scalp_channels(ch_names: list[str]) -> tuple[list[int], list[str]]:
    """Return (indices, names) for the 19 scalp electrodes, in CANONICAL_19 order.

    Raises if any of the 19 is missing -- silently dropping an electrode would
    change the topography analysis without changing any accuracy number.
    """
    lookup = {}
    for i, raw in enumerate(ch_names):
        c = canonical_channel(raw)
        lookup.setdefault(c.upper(), i)

    idx, missing = [], []
    for want in CANONICAL_19:
        j = lookup.get(want.upper())
        if j is None:
            missing.append(want)
        else:
            idx.append(j)
    if missing:
        raise ValueError(f"missing scalp channels {missing} in {ch_names}")
    return idx, list(CANONICAL_19)


def parse_filename(name: str) -> dict:
    """Parse an HUSM filename into subject / label / condition.

    The released files look like:  "MDD S12 EC.edf", "H S3 EO.edf",
    and often "MDD S5 TASK.edf" as well.

    Two traps this avoids:
      * "H" appears inside "HEALTHY" but ALSO inside nothing else -- we key on
        MDD first, so anything not marked MDD is treated as control.
      * TASK files are NOT eyes-open. A naive `"EC" in name else "EO"` test
        silently mislabels every TASK recording as eyes-open, quietly polluting
        the resting-state analysis. We detect TASK explicitly.
    """
    upper = os.path.basename(name).upper()
    label = 1 if "MDD" in upper else 0

    if "TASK" in upper:
        cond = "TASK"
    elif re.search(r"\bEC\b|_EC|EC\.", upper) or " EC" in upper:
        cond = "EC"
    elif re.search(r"\bEO\b|_EO|EO\.", upper) or " EO" in upper:
        cond = "EO"
    else:
        cond = "UNKNOWN"

    m = re.search(r"S\s*(\d+)", upper)
    if m:
        subject = f"{'MDD' if label else 'HC'}_{int(m.group(1)):03d}"
    else:
        digits = re.findall(r"\d+", upper)
        subject = f"{'MDD' if label else 'HC'}_{int(digits[0]):03d}" if digits else None

    return dict(subject=subject, label=label, condition=cond)


def load_husm(root: str, fs: int = 256, include_task: bool = False,
              verbose: bool = True, require_both_conditions: bool = False,
              on_duplicate: str = "first") -> list[Recording]:
    """Load the Mumtaz/HUSM MDD dataset (.edf files).

    Run experiments/inspect_data.py FIRST to verify the parser against your
    actual download. Silently mislabelled files are the single easiest way to
    produce a confidently wrong paper.
    """
    import mne  # lazy: only needed for real data

    paths = sorted(glob.glob(os.path.join(root, "**", "*.edf"), recursive=True))
    if not paths:
        raise FileNotFoundError(f"no .edf files under {root}")

    # --- pass 1: parse names, detect duplicates -------------------------
    # The figshare release ships TWO copies of H S15 EO, prefixed with
    # different figshare ids ("6921143_H S15 EO.edf", "6921959_H S15 EO.edf").
    # Loading both would double-weight that subject's eyes-open data.
    seen: dict[tuple, str] = {}
    duplicates: list[tuple[str, str]] = []
    keep: list[tuple[str, dict]] = []
    for path in paths:
        meta = parse_filename(os.path.basename(path))
        if meta["subject"] is None or meta["condition"] == "UNKNOWN":
            continue
        key = (meta["subject"], meta["condition"])
        if key in seen:
            duplicates.append((path, seen[key]))
            if on_duplicate == "first":
                continue
            raise ValueError(f"duplicate recording for {key}: {path} vs {seen[key]}")
        seen[key] = path
        keep.append((path, meta))

    dup_paths = {p for p, _ in duplicates}

    recs, skipped = [], []
    for path in paths:
        if path in dup_paths:
            skipped.append((path, "duplicate of an earlier file"))
            continue
        meta = parse_filename(os.path.basename(path))
        if meta["subject"] is None:
            skipped.append((path, "unparsed subject id"))
            continue
        if meta["condition"] == "TASK" and not include_task:
            skipped.append((path, "TASK recording"))
            continue
        if meta["condition"] == "UNKNOWN":
            skipped.append((path, "unknown condition"))
            continue

        raw = mne.io.read_raw_edf(path, preload=True, verbose="ERROR")
        if abs(float(raw.info["sfreq"]) - fs) > 0.5:
            raw.resample(fs, verbose="ERROR")
        idx, names = select_scalp_channels(raw.ch_names)
        recs.append(Recording(meta["subject"], meta["label"],
                              meta["condition"], raw.get_data()[idx], names))

    # --- condition availability ----------------------------------------
    avail: dict[str, set] = {}
    for r in recs:
        avail.setdefault(r.subject, set()).add(r.condition)
    incomplete = {s: sorted(c) for s, c in avail.items()
                  if not {"EC", "EO"} <= c}
    if require_both_conditions and incomplete:
        recs = [r for r in recs if r.subject not in incomplete]

    if verbose:
        n_ch = {r.data.shape[0] for r in recs}
        subs = {r.subject for r in recs}
        n_mdd = len({s for s in subs if s.startswith("MDD")})
        n_hc = len(subs) - n_mdd
        print(f"[load_husm] {len(recs)} recordings, {len(subs)} subjects "
              f"(MDD={n_mdd}, HC={n_hc}), channels={sorted(n_ch)}")
        if duplicates:
            print(f"[load_husm] {len(duplicates)} duplicate file(s) dropped:")
            for d, orig in duplicates:
                print(f"    {os.path.basename(d)}  (kept {os.path.basename(orig)})")
        if incomplete:
            verb = "EXCLUDED" if require_both_conditions else "kept"
            print(f"[load_husm] {len(incomplete)} subject(s) lack both EC and EO "
                  f"({verb}): {incomplete}")
        if len(n_ch) > 1:
            raise ValueError(f"inconsistent channel counts {sorted(n_ch)} -- "
                             "run experiments/inspect_data.py and fix before proceeding")
        if skipped:
            print(f"[load_husm] skipped {len(skipped)} file(s): "
                  f"{Counter(r for _, r in skipped)}")
    if not recs:
        raise RuntimeError("every file was skipped -- check parse_filename against your data")
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

            recs.append(Recording(sid, label, cond, bg + alpha + emg,
                                  list(CANONICAL_19)[:n_ch]))
    return recs
