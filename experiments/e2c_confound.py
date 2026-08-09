"""E2c -- confound checks on the artifact-only result.

E2 showed that five signal-quality scalars classify MDD vs HC at ~0.88, matching
or beating the deep model, and that the strongest single feature is RESIDUAL
45-55 Hz POWER, which differs ~21x between groups.

That is an extraordinary claim (it says the published biomarker is mains hum),
so before it goes in a paper it has to survive every cheap attempt to explain it
away. This script runs those attempts.

  C1  per-subject distribution   -- is it a population shift, or a few outliers?
  C2  per-condition split        -- is it an EC/EO imbalance artifact?
  C3  single-feature, subject-level -- how far does ONE scalar get on its own?
  C4  notch ablation             -- is it our 50 Hz notch, or the raw recording?
  C5  raw line peak              -- measure 50 Hz contamination before any filtering
  C6  subject-index / batch      -- does it track recording order (a batch effect)?

Run:
  python experiments/e2c_confound.py --data "D:\\Project\\PaperPlan\\EEG"
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np
from scipy.signal import welch
from sklearn.metrics import roc_auc_score

sys.path.insert(0, ".")

from eegmdd.runlog import start_run

from eegmdd.artifact import FEATURE_NAMES, featurise
from eegmdd.config import Config
from eegmdd.data import build_epochs, load_husm, make_synthetic, notch


def _auc(y, x):
    a = roc_auc_score(y, x)
    return a, max(a, 1 - a)


# --- C1 / C3 -----------------------------------------------------------------

def per_subject_table(es, fs):
    """Mean feature vector per subject -> the honest unit of analysis."""
    F = featurise(es.X, fs)
    subs = np.unique(es.subject)
    rows = []
    for s in subs:
        m = es.subject == s
        rows.append(dict(subject=str(s), label=int(es.y[m][0]),
                         n_epochs=int(m.sum()),
                         **{n: float(F[m, i].mean()) for i, n in enumerate(FEATURE_NAMES)}))
    return rows


def c1_c3(rows):
    y = np.array([r["label"] for r in rows])
    print(f"  {len(rows)} subjects  (MDD={int(y.sum())}, HC={int((1-y).sum())})")
    print(f"\n  {'feature':<20}{'MDD med':>12}{'HC med':>12}{'ratio':>9}"
          f"{'subj AUC':>10}{'overlap':>9}")
    out = []
    for name in FEATURE_NAMES:
        x = np.array([r[name] for r in rows])
        mdd, hc = x[y == 1], x[y == 0]
        a, aabs = _auc(y, x)
        # overlap = fraction of subjects inside the other group's 5-95 range
        lo, hi = np.percentile(hc, [5, 95])
        ov = float(((mdd >= lo) & (mdd <= hi)).mean())
        ratio = (np.median(mdd) + 1e-12) / (np.median(hc) + 1e-12)
        print(f"  {name:<20}{np.median(mdd):>12.5f}{np.median(hc):>12.5f}"
              f"{ratio:>9.2f}{aabs:>10.3f}{ov:>9.2f}")
        out.append(dict(feature=name, mdd_median=float(np.median(mdd)),
                        hc_median=float(np.median(hc)), ratio=float(ratio),
                        subject_auc=float(aabs), overlap_frac=ov))
    print("\n  overlap = fraction of MDD subjects inside the HC 5-95 percentile band.")
    print("  Low overlap + high AUC = a clean population separation, not outliers.")
    return out


# --- C2 ----------------------------------------------------------------------

def c2_by_condition(recs, band, epoch_sec):
    for cond in ("EC", "EO"):
        cfg = Config(band=band, epoch_sec=epoch_sec, overlap_sec=0.0, condition=cond)
        es = build_epochs(recs, cfg)
        rows = per_subject_table(es, cfg.fs)
        y = np.array([r["label"] for r in rows])
        if len(np.unique(y)) < 2:
            print(f"  {cond}: only one class present, skipping")
            continue
        line = np.array([r["line_resid_45_55"] for r in rows])
        hf = np.array([r["hf_power_60_100"] for r in rows])
        print(f"  {cond}: n={len(rows)} subjects  "
              f"line-resid AUC={_auc(y, line)[1]:.3f}   hf-power AUC={_auc(y, hf)[1]:.3f}")


# --- C4 / C5 -----------------------------------------------------------------

def c4_c5_notch(recs, epoch_sec, fs=256):
    """Measure 50 Hz contamination in the RAW signal, before any of our filtering.

    If the group difference exists here, it is in the recordings, not in our code.
    """
    y, peak_raw, peak_notched = [], [], []
    for rec in recs:
        if rec.condition not in ("EC", "EO"):
            continue
        n = int(epoch_sec * fs)
        seg = rec.data[:, :n * max(1, rec.data.shape[1] // n)]
        f, p = welch(seg, fs=fs, nperseg=min(2048, seg.shape[-1]), axis=-1)
        band = (f >= 48) & (f <= 52)
        nbr = ((f >= 40) & (f < 48)) | ((f > 52) & (f <= 60))
        ratio = (p[..., band].mean(-1) / (p[..., nbr].mean(-1) + 1e-20)).mean()

        seg_n = notch(seg, 50.0, fs)
        f2, p2 = welch(seg_n, fs=fs, nperseg=min(2048, seg_n.shape[-1]), axis=-1)
        b2 = (f2 >= 48) & (f2 <= 52)
        n2 = ((f2 >= 40) & (f2 < 48)) | ((f2 > 52) & (f2 <= 60))
        ratio_n = (p2[..., b2].mean(-1) / (p2[..., n2].mean(-1) + 1e-20)).mean()

        y.append(rec.label)
        peak_raw.append(float(ratio))
        peak_notched.append(float(ratio_n))

    y = np.array(y)
    pr, pn = np.array(peak_raw), np.array(peak_notched)
    print(f"  50 Hz peak-to-neighbour ratio, RAW (no notch, no bandpass):")
    print(f"    MDD median {np.median(pr[y==1]):.2f}   HC median {np.median(pr[y==0]):.2f}"
          f"   AUC {_auc(y, pr)[1]:.3f}")
    print(f"  after our 50 Hz notch:")
    print(f"    MDD median {np.median(pn[y==1]):.2f}   HC median {np.median(pn[y==0]):.2f}"
          f"   AUC {_auc(y, pn)[1]:.3f}")
    print("\n  If the RAW AUC is already high, the line-noise difference is a property")
    print("  of the recordings themselves -- our preprocessing did not create it.")
    return dict(raw_auc=float(_auc(y, pr)[1]), notched_auc=float(_auc(y, pn)[1]),
                raw_mdd=float(np.median(pr[y == 1])), raw_hc=float(np.median(pr[y == 0])))


# --- C6 ----------------------------------------------------------------------

def c6_batch(rows):
    """Does the feature track subject NUMBER within each group?

    Subject ids were assigned in recording order. A monotone trend inside a group
    means equipment/setup drifted over the collection period -- i.e. a batch
    effect, which is the most likely mundane explanation for a group difference.
    """
    from scipy.stats import spearmanr
    for grp, lab in (("MDD", 1), ("HC", 0)):
        sel = [r for r in rows if r["label"] == lab]
        idx = np.array([int(r["subject"].split("_")[1]) for r in sel])
        for name in ("line_resid_45_55", "hf_power_60_100"):
            v = np.array([r[name] for r in sel])
            rho, p = spearmanr(idx, v)
            flag = "  <-- TREND" if p < 0.05 else ""
            print(f"  {grp:4s} {name:<20} rho={rho:+.3f}  p={p:.4f}{flag}")


# --- main --------------------------------------------------------------------

def _main(run):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="synthetic")
    ap.add_argument("--band", default="gamma")
    ap.add_argument("--epoch-sec", type=float, default=15.0)
    ap.add_argument("--minutes", type=float, default=1.0)
    args = ap.parse_args()

    recs = (make_synthetic(minutes=args.minutes) if args.data == "synthetic"
            else load_husm(args.data))

    cfg = Config(band=args.band, epoch_sec=args.epoch_sec, overlap_sec=0.0)
    es = build_epochs(recs, cfg)
    rows = per_subject_table(es, cfg.fs)

    print("\n[C1/C3] per-subject feature separation (subject is the unit)")
    feats = c1_c3(rows)

    print("\n[C2] does it hold within each recording condition?")
    c2_by_condition(recs, args.band, args.epoch_sec)

    print("\n[C4/C5] is the line noise in the recordings, or in our filtering?")
    notch_res = c4_c5_notch(recs, args.epoch_sec, cfg.fs)

    print("\n[C6] batch / recording-order trend within each group")
    c6_batch(rows)

    run.set_result(dict(subjects=rows, features=feats, notch=notch_res))


def main():
    with start_run("e2c") as run:
        _main(run)


if __name__ == "__main__":
    main()
