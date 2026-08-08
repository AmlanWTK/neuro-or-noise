"""E2 -- shortcut probes. The scientific core of the paper.

Four probes, in order of how damaging they are to the gamma-biomarker claim:

  P1  subject-ID probe      -- are epochs from one subject mutually identifiable?
                               If yes, epoch-level splits are meaningless.
  P2  artifact-only baseline-- can FIVE hand-computed scalars match the CNN under
                               an epoch-level split, then collapse under LOSO?
                               This is the headline figure.
  P3  band x protocol matrix-- does gamma's advantage survive subject-wise
                               evaluation, or does the band ranking change?
  P4  channel topography    -- is the discriminative HF power concentrated at
                               temporal/lateral-frontal (muscle-prone) sites?

Run:
  python experiments/e2_shortcut.py --data synthetic --minutes 1.0
  python experiments/e2_shortcut.py --data /path/to/husm_edf --probes P1,P2,P3,P4
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, ".")

from eegmdd.artifact import FEATURE_NAMES, featurise, channel_hf_profile
from eegmdd.config import Config, BANDS
from eegmdd.data import build_epochs, load_husm, make_synthetic, normalise
from eegmdd.metrics import binary_metrics
from eegmdd.splits import make_folds
from eegmdd.train import run_cv


# --------------------------------------------------------------------------
# P1 -- subject identification probe
# --------------------------------------------------------------------------

def subject_features(X, fs):
    """Per-channel 60-100 Hz relative power (19) + 5 global artifact scalars."""
    from scipy.signal import welch
    f, p = welch(X, fs=fs, nperseg=min(512, X.shape[-1]), axis=-1)
    m = (f >= 60) & (f < 100)
    per_ch = p[..., m].sum(-1) / (p.sum(-1) + 1e-12)      # (n_epochs, n_ch)
    glob = featurise(X, fs)                                # (n_epochs, 5)
    return np.hstack([per_ch, glob])


def probe_subject_id(es, cfg, train_frac=0.7, gap=2):
    """Within-subject temporal split: train on the first 70% of each subject's
    epochs, test on the last 30%, with a small gap to defeat epoch overlap.

    Chance = 1 / n_subjects. Anything far above chance means epochs carry a
    stable subject fingerprint -- which is exactly what an epoch-level random
    split lets a classifier memorise.
    """
    F = subject_features(es.X, cfg.fs)
    subs = np.unique(es.subject)
    code = {s: i for i, s in enumerate(subs)}
    y = np.array([code[s] for s in es.subject])

    tr, te = [], []
    for s in subs:
        idx = np.where(es.subject == s)[0]
        k = int(len(idx) * train_frac)
        tr.extend(idx[:max(1, k - gap)])
        te.extend(idx[k:])
    tr, te = np.array(tr), np.array(te)

    sc = StandardScaler().fit(F[tr])
    clf = LogisticRegression(max_iter=3000)
    clf.fit(sc.transform(F[tr]), y[tr])
    acc = float((clf.predict(sc.transform(F[te])) == y[te]).mean())
    chance = 1.0 / len(subs)
    return dict(probe="subject_id", accuracy=acc, chance=chance,
                ratio=acc / chance, n_subjects=int(len(subs)),
                n_train=int(len(tr)), n_test=int(len(te)))


# --------------------------------------------------------------------------
# P2 -- artifact-only baseline
# --------------------------------------------------------------------------

def probe_artifact_only(recs, band="gamma", epoch_sec=15.0, seed=0, n_folds=10):
    """Five scalars + logistic regression, under three protocols.

    Prediction: high under epoch_random, collapsing under subject_kfold/loso.
    A five-parameter linear model has no capacity to learn a subtle neural
    biomarker -- so if it tracks the CNN, the CNN is not using one either.
    """
    out = []
    for split, norm in [("epoch_random", "global"),
                        ("subject_kfold", "train_fold"),
                        ("loso", "train_fold")]:
        cfg = Config(band=band, epoch_sec=epoch_sec, overlap_sec=0.0,
                     split=split, norm_scope=norm, model="artifact_lr",
                     seed=seed, n_folds=n_folds, calibrate=False)
        es = build_epochs(recs, cfg)
        res = run_cv(es, cfg, verbose=False)
        out.append(dict(split=split,
                        epoch_acc=res["epoch"]["accuracy"],
                        subject_acc=res["subject"]["accuracy"],
                        ci=res["subject"]["ci95"]))
        print(f"  artifact-only  {split:14s} epoch={out[-1]['epoch_acc']:.4f} "
              f"subject={out[-1]['subject_acc']:.4f}")
    return out


def feature_separation(recs, band="gamma", epoch_sec=15.0):
    """Per-feature class means + univariate AUC. Shows WHICH artifact carries it."""
    from sklearn.metrics import roc_auc_score
    cfg = Config(band=band, epoch_sec=epoch_sec, overlap_sec=0.0)
    es = build_epochs(recs, cfg)
    F = featurise(es.X, cfg.fs)
    rows = []
    for i, name in enumerate(FEATURE_NAMES):
        auc = float(roc_auc_score(es.y, F[:, i]))
        rows.append(dict(feature=name,
                         mdd_mean=float(F[es.y == 1, i].mean()),
                         hc_mean=float(F[es.y == 0, i].mean()),
                         auc=auc, auc_abs=max(auc, 1 - auc)))
    rows.sort(key=lambda r: -r["auc_abs"])
    for r in rows:
        print(f"  {r['feature']:18s} MDD={r['mdd_mean']:+.4f} HC={r['hc_mean']:+.4f} "
              f"AUC={r['auc']:.3f}")
    return rows


# --------------------------------------------------------------------------
# P3 -- band x protocol matrix
# --------------------------------------------------------------------------

def probe_band_matrix(recs, bands=None, epoch_sec=15.0, model="artifact_lr",
                      seed=0, n_folds=10, max_epochs=25):
    """The table that tests the paper's central claim.

    Anik et al. rank gamma first. If that ranking is driven by artifact, it
    should weaken or invert once subjects are held out.
    """
    bands = bands or ["delta", "theta", "alpha", "beta", "gamma", "gamma_low", "sub45"]
    rows = []
    for band in bands:
        row = {"band": band}
        for split, norm in [("epoch_random", "global"), ("subject_kfold", "train_fold")]:
            cfg = Config(band=band, epoch_sec=epoch_sec, overlap_sec=0.0,
                         split=split, norm_scope=norm, model=model, seed=seed,
                         n_folds=n_folds, max_epochs=max_epochs, calibrate=False)
            es = build_epochs(recs, cfg)
            res = run_cv(es, cfg, verbose=False)
            row[split] = res["epoch"]["accuracy"]
            row[f"{split}_subject"] = res["subject"]["accuracy"]
        row["gap"] = row["epoch_random"] - row["subject_kfold"]
        rows.append(row)
        print(f"  {band:10s} epoch-random={row['epoch_random']:.4f}  "
              f"subject-wise={row['subject_kfold']:.4f}  gap={row['gap']:+.4f}")

    print("\n  ranking under epoch-random :",
          " > ".join(r["band"] for r in sorted(rows, key=lambda r: -r["epoch_random"])))
    print("  ranking under subject-wise :",
          " > ".join(r["band"] for r in sorted(rows, key=lambda r: -r["subject_kfold"])))
    return rows


# --------------------------------------------------------------------------
# P4 -- channel topography
# --------------------------------------------------------------------------

# Channel names now come from the data itself (EpochSet.ch_names), set by
# eegmdd.data.select_scalp_channels. Never hardcode the order -- the HUSM files
# ship two different channel layouts (22ch and 20ch) and position-based
# indexing would silently compare different electrodes across files.
MUSCLE_PRONE = {"T3", "T4", "T5", "T6", "F7", "F8"}


def probe_topography(recs, band="gamma", epoch_sec=15.0, ch_names=None):
    """Per-channel HF power and per-channel discriminability.

    EMG signature = concentration at T3/T4/T5/T6/F7/F8. Cortical gamma would
    not be so lateralised toward the temporalis.
    """
    from sklearn.metrics import roc_auc_score
    cfg = Config(band=band, epoch_sec=epoch_sec, overlap_sec=0.0)
    es = build_epochs(recs, cfg)
    names = ch_names or es.ch_names or [f"ch{i}" for i in range(es.X.shape[1])]
    if len(names) != es.X.shape[1]:
        raise ValueError(f"{len(names)} channel names for {es.X.shape[1]} channels")

    from scipy.signal import welch
    f, p = welch(es.X, fs=cfg.fs, nperseg=min(512, es.X.shape[-1]), axis=-1)
    m = (f >= 60) & (f < 100)
    per_ch = p[..., m].sum(-1) / (p.sum(-1) + 1e-12)     # (n_epochs, n_ch)

    rows = []
    for i, nm in enumerate(names):
        auc = float(roc_auc_score(es.y, per_ch[:, i]))
        rows.append(dict(channel=nm, hf_power=float(per_ch[:, i].mean()),
                         auc=auc, auc_abs=max(auc, 1 - auc),
                         muscle_prone=nm in MUSCLE_PRONE))
    rows.sort(key=lambda r: -r["auc_abs"])

    top6 = rows[:6]
    n_muscle = sum(r["muscle_prone"] for r in top6)
    print("  most discriminative channels (60-100 Hz relative power):")
    for r in top6:
        flag = "  <-- muscle-prone" if r["muscle_prone"] else ""
        print(f"    {r['channel']:4s} AUC={r['auc']:.3f}{flag}")
    print(f"  {n_muscle}/6 of the top channels are muscle-prone "
          f"({len(MUSCLE_PRONE)}/{len(names)} of all channels are)")
    return dict(channels=rows, top6_muscle_prone=n_muscle,
                baseline_rate=len(MUSCLE_PRONE) / len(names))


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="synthetic")
    ap.add_argument("--minutes", type=float, default=1.0)
    ap.add_argument("--epoch-sec", type=float, default=15.0)
    ap.add_argument("--band", default="gamma")
    ap.add_argument("--probes", default="P1,P2,P3,P4")
    ap.add_argument("--n-folds", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--shortcut-mode", default="class_correlated",
                    choices=["class_correlated", "subject_only"])
    ap.add_argument("--out", default="results/e2.json")
    args = ap.parse_args()

    recs = (make_synthetic(minutes=args.minutes, seed=args.seed,
                           shortcut_mode=args.shortcut_mode)
            if args.data == "synthetic" else load_husm(args.data))
    want = set(args.probes.split(","))
    results = {"data": args.data, "band": args.band, "epoch_sec": args.epoch_sec}

    if "P1" in want:
        print("\n[P1] subject-identification probe")
        cfg = Config(band=args.band, epoch_sec=args.epoch_sec, overlap_sec=0.0)
        es = build_epochs(recs, cfg)
        r = probe_subject_id(es, cfg)
        print(f"  accuracy {r['accuracy']:.4f} vs chance {r['chance']:.4f} "
              f"({r['ratio']:.1f}x chance, {r['n_subjects']} subjects)")
        results["P1"] = r

    if "P2" in want:
        print("\n[P2] artifact-only baseline (5 scalars + logistic regression)")
        results["P2"] = probe_artifact_only(recs, args.band, args.epoch_sec,
                                            args.seed, args.n_folds)
        print("\n[P2b] per-feature separation")
        results["P2b"] = feature_separation(recs, args.band, args.epoch_sec)

    if "P3" in want:
        print("\n[P3] band x protocol matrix")
        results["P3"] = probe_band_matrix(recs, epoch_sec=args.epoch_sec,
                                          seed=args.seed, n_folds=args.n_folds)

    if "P4" in want:
        print("\n[P4] channel topography")
        results["P4"] = probe_topography(recs, args.band, args.epoch_sec)

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2, default=float)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
