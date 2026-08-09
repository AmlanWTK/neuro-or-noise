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
    """Return (raw_auc, |auc|, direction). Direction matters: reporting only
    max(auc, 1-auc) hides WHICH group is higher, which is the whole point."""
    a = roc_auc_score(y, x)
    return a, max(a, 1 - a), ("MDD>HC" if a > 0.5 else "HC>MDD")


def _log_cohen_d(a, b, eps=1e-12):
    """Effect size, on a log scale when the feature is strictly positive.

    Power-like features are heavy-tailed, so a raw-scale d understates them.
    But kurtosis can be negative, so fall back to raw scale rather than
    returning NaN.
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.min() > 0 and b.min() > 0:
        la, lb = np.log10(a + eps), np.log10(b + eps)
    else:
        la, lb = a, b
    sp = np.sqrt(((len(la) - 1) * la.var(ddof=1) + (len(lb) - 1) * lb.var(ddof=1))
                 / max(1, len(la) + len(lb) - 2))
    return float((la.mean() - lb.mean()) / (sp + 1e-12))


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
    """Per-subject separation, reported honestly for heavy-tailed data.

    The previous version reported 'fraction of MDD inside the HC 5-95 band',
    which is useless when HC has a long tail: nearly everything falls inside a
    wide band even under perfect rank separation. Replaced with quartiles, a
    log-scale effect size, and an explicit direction.
    """
    from scipy.stats import mannwhitneyu
    y = np.array([r["label"] for r in rows])
    print(f"  {len(rows)} subjects  (MDD={int(y.sum())}, HC={int((1-y).sum())})")
    print(f"\n  {'feature':<20}{'dir':>8}{'AUC':>7}{'log d':>8}{'p':>10}"
          f"   MDD q1|med|q3            HC q1|med|q3")
    out = []
    for name in FEATURE_NAMES:
        x = np.array([r[name] for r in rows])
        mdd, hc = x[y == 1], x[y == 0]
        a, aabs, direction = _auc(y, x)
        d = _log_cohen_d(mdd, hc)
        try:
            pval = float(mannwhitneyu(mdd, hc, alternative="two-sided").pvalue)
        except Exception:
            pval = float("nan")
        mq = np.percentile(mdd, [25, 50, 75])
        hq = np.percentile(hc, [25, 50, 75])
        print(f"  {name:<20}{direction:>8}{aabs:>7.3f}{d:>8.2f}{pval:>10.2e}"
              f"   {mq[0]:.2e}|{mq[1]:.2e}|{mq[2]:.2e}"
              f"  {hq[0]:.2e}|{hq[1]:.2e}|{hq[2]:.2e}")
        out.append(dict(feature=name, direction=direction, subject_auc=float(aabs),
                        log_cohen_d=d, p_mannwhitney=pval,
                        mdd_q=[float(v) for v in mq], hc_q=[float(v) for v in hq]))
    print("\n  |log d| > 0.8 is a large effect. AUC is rank-based so it is robust")
    print("  to the heavy tails; the quartiles show whether the gap is a whole-")
    print("  population shift or a tail effect.")
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
    per_subject = {}
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

        d = per_subject.setdefault(rec.subject, dict(label=rec.label, raw=[], notched=[]))
        d["raw"].append(float(ratio))
        d["notched"].append(float(ratio_n))

    # Aggregate to SUBJECT level. Per-recording values are extremely heavy-tailed
    # (a single noisy channel-minute can dominate), which is why the earlier
    # per-recording AUC sat near chance despite a 6x median gap.
    subs = sorted(per_subject)
    y = np.array([per_subject[s]["label"] for s in subs])
    pr = np.array([np.median(per_subject[s]["raw"]) for s in subs])
    pn = np.array([np.median(per_subject[s]["notched"]) for s in subs])

    from scipy.stats import mannwhitneyu

    def report(tag, v):
        a, aabs, direction = _auc(y, v)
        p = float(mannwhitneyu(v[y == 1], v[y == 0], alternative="two-sided").pvalue)
        mq = np.percentile(v[y == 1], [25, 50, 75])
        hq = np.percentile(v[y == 0], [25, 50, 75])
        # "clear line peak" = 50 Hz bin at least 2x its neighbours
        fm = float((v[y == 1] >= 2).mean())
        fh = float((v[y == 0] >= 2).mean())
        print(f"  {tag}")
        print(f"    MDD  q1/med/q3 = {mq[0]:.2f} / {mq[1]:.2f} / {mq[2]:.2f}"
              f"   {fm:.0%} with a clear 50 Hz peak")
        print(f"    HC   q1/med/q3 = {hq[0]:.2f} / {hq[1]:.2f} / {hq[2]:.2f}"
              f"   {fh:.0%} with a clear 50 Hz peak")
        print(f"    AUC {aabs:.3f} ({direction})   log-d {_log_cohen_d(v[y==1], v[y==0]):+.2f}"
              f"   p={p:.2e}")
        return dict(auc=float(aabs), direction=direction, p=p,
                    mdd_median=float(mq[1]), hc_median=float(hq[1]),
                    mdd_frac_peak=fm, hc_frac_peak=fh)

    print(f"  n={len(subs)} subjects, per-subject median over recordings\n")
    raw = report("50 Hz peak-to-neighbour, RAW (no notch, no bandpass):", pr)
    print()
    notched = report("after our 50 Hz notch:", pn)
    print("\n  A high RAW AUC means the line-noise difference is a property of the")
    print("  recordings. A low RAW but high post-notch AUC would mean WE created it.")
    return dict(raw=raw, notched=notched,
                per_subject={s: dict(label=per_subject[s]["label"],
                                     raw_median=float(np.median(per_subject[s]["raw"])))
                             for s in subs})


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
