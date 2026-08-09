"""E2e -- is it the aperiodic (1/f) slope?

P3 showed the same five scalars reach 0.81-0.88 in EVERY band -- delta, beta,
gamma, the mains region, and gamma with the mains region removed. A signal that
appears everywhere is not a band effect. It is a property of the whole spectrum.

The obvious candidate is the APERIODIC component: the broadband 1/f^x background
that every EEG spectrum sits on. If MDD spectra are steeper (larger exponent),
then mechanically:

  * relative low-frequency power rises in every band  -> zero-crossing rate falls
    in every band (observed: ZCR HC>MDD, AUC 0.918)
  * absolute delta / theta / beta power rises         (observed: +0.44 / +0.32 / +0.41)
  * relative high-frequency content falls
  * a five-scalar spectral-shape probe separates the groups in ANY band

One number would then explain the entire pattern -- including the "gamma
biomarker".

  A1  fit the aperiodic exponent per subject and test it directly
  A2  does the exponent explain the five artifact features?
  A3  FLATTEN each subject's spectrum by its own fit -- does ANY band-specific
      group difference survive?

A3 is the real test. If nothing survives flattening, there is no band-specific
biomarker in this dataset at all, and the paper's band ranking is an artifact of
a single broadband parameter.

Run:
  python experiments/e2e_aperiodic.py --data "D:\\Project\\PaperPlan\\EEG"
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
from scipy.signal import welch
from scipy.stats import mannwhitneyu, spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

sys.path.insert(0, ".")

from eegmdd.runlog import start_run
from eegmdd.data import load_husm, make_synthetic

# Fit range: above the high-pass, below the low-pass, skipping the mains region.
FIT_LO, FIT_HI = 2.0, 45.0
LINE_LO, LINE_HI = 45.0, 55.0


def _auc(y, x):
    a = roc_auc_score(y, x)
    return max(a, 1 - a), ("MDD>HC" if a > 0.5 else "HC>MDD")


def subject_spectra(recs, fs=256, nperseg=2048):
    acc = {}
    for rec in recs:
        if rec.condition not in ("EC", "EO"):
            continue
        f, p = welch(rec.data, fs=fs, nperseg=min(nperseg, rec.data.shape[-1]), axis=-1)
        d = acc.setdefault(rec.subject, dict(label=rec.label, psd=[], f=f))
        d["psd"].append(p.mean(axis=0))
    for s in acc:
        acc[s]["psd"] = np.mean(acc[s]["psd"], axis=0)
    return acc


def fit_aperiodic(f, p, lo=FIT_LO, hi=FIT_HI):
    """log10 P = offset - exponent * log10 f, fitted outside the mains band."""
    m = (f >= lo) & (f <= hi) & ~((f >= LINE_LO) & (f <= LINE_HI)) & (p > 0)
    if m.sum() < 10:
        return np.nan, np.nan, np.nan
    x, yv = np.log10(f[m]), np.log10(p[m])
    slope, offset = np.polyfit(x, yv, 1)
    resid = yv - (slope * x + offset)
    r2 = 1 - resid.var() / (yv.var() + 1e-30)
    return float(-slope), float(offset), float(r2)


def a1_exponent(acc):
    y, expo, off, r2s = [], [], [], []
    for v in acc.values():
        e, o, r2 = fit_aperiodic(v["f"], v["psd"])
        y.append(v["label"]); expo.append(e); off.append(o); r2s.append(r2)
    y, expo, off = np.array(y), np.array(expo), np.array(off)

    print(f"  fitted {FIT_LO:.0f}-{FIT_HI:.0f} Hz (mains excluded), "
          f"median R2 = {np.median(r2s):.3f}\n")
    out = {}
    for name, v in (("aperiodic exponent", expo), ("offset (broadband power)", off)):
        a, d = _auc(y, v)
        p = float(mannwhitneyu(v[y == 1], v[y == 0]).pvalue)
        print(f"  {name:<26} MDD {np.median(v[y==1]):+.3f}   HC {np.median(v[y==0]):+.3f}"
              f"   AUC {a:.3f} ({d})  p={p:.2e}")
        out[name] = dict(auc=float(a), direction=d, p=p,
                         mdd=float(np.median(v[y == 1])), hc=float(np.median(v[y == 0])))

    # how far do these two numbers alone get, cross-validated?
    X = np.c_[expo, off]
    ok = np.isfinite(X).all(1)
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    cv = StratifiedKFold(5, shuffle=True, random_state=0)
    sc = cross_val_score(clf, X[ok], y[ok], cv=cv, scoring="accuracy")
    print(f"\n  exponent + offset only, 5-fold subject-level CV: "
          f"{sc.mean():.4f} +/- {sc.std():.4f}")
    print(f"  (majority class = {max(y.mean(), 1-y.mean()):.4f})")
    out["two_param_cv"] = dict(mean=float(sc.mean()), std=float(sc.std()))
    return out, expo, off, y


def a2_explains_features(acc, expo, y):
    """Correlate the aperiodic exponent with the five artifact scalars."""
    from eegmdd.artifact import FEATURE_NAMES, epoch_features
    fs = 256
    feats = []
    for v in acc.values():
        # features on the broadband subject-average spectrum are not directly
        # comparable, so recompute the two spectral-shape ones from the PSD
        f, p = v["f"], v["psd"]
        tot = p.sum() + 1e-30
        hf = p[(f >= 60) & (f < 100)].sum() / tot
        line = p[(f >= 45) & (f < 55)].sum() / tot
        feats.append([hf, line])
    feats = np.array(feats)
    print("  Spearman correlation with the aperiodic exponent:")
    for i, n in enumerate(["hf_power_60_100", "line_resid_45_55"]):
        rho, p = spearmanr(expo, feats[:, i])
        print(f"    {n:<20} rho={rho:+.3f}  p={p:.2e}")
    print("\n  Strong correlation means these 'artifact' features are largely")
    print("  re-measurements of one broadband parameter.")


def a3_flatten(acc):
    """Remove each subject's own 1/f fit, then look for band differences again."""
    bands = [("delta", 1, 4), ("theta", 4, 8), ("alpha", 8, 12), ("beta", 12, 30),
             ("gamma_low", 30, 45), ("line", 45, 55), ("gamma_hi", 55, 80)]
    y = np.array([v["label"] for v in acc.values()])

    raw_rows, flat_rows = [], []
    for v in acc.values():
        f, p = v["f"], v["psd"]
        e, o, _ = fit_aperiodic(f, p)
        model = 10 ** (o - e * np.log10(np.maximum(f, 1e-9)))
        flat = p / (model + 1e-30)          # residual: periodic component only
        raw_rows.append([p[(f >= lo) & (f < hi)].mean() for _, lo, hi in bands])
        flat_rows.append([flat[(f >= lo) & (f < hi)].mean() for _, lo, hi in bands])
    R, F = np.array(raw_rows), np.array(flat_rows)

    print(f"  {'band':<12}{'raw AUC':>10}{'flattened AUC':>16}{'change':>10}")
    out = []
    for i, (n, lo, hi) in enumerate(bands):
        ar, _ = _auc(y, R[:, i])
        af, d = _auc(y, F[:, i])
        print(f"  {n:<12}{ar:>10.3f}{af:>16.3f}{af-ar:>+10.3f}")
        out.append(dict(band=n, raw_auc=float(ar), flat_auc=float(af)))

    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    cv = StratifiedKFold(5, shuffle=True, random_state=0)
    for tag, M in (("raw band powers", R), ("flattened band powers", F)):
        sc = cross_val_score(clf, np.log10(M + 1e-30), y, cv=cv, scoring="accuracy")
        print(f"\n  all 7 {tag:<22} 5-fold CV: {sc.mean():.4f} +/- {sc.std():.4f}")

    print("\n  If flattened AUCs drop to ~0.5, every band difference in this dataset")
    print("  is a consequence of the aperiodic slope, and no band-specific")
    print("  biomarker claim -- gamma or otherwise -- is supportable.")
    return out


def _main(run):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="synthetic")
    ap.add_argument("--minutes", type=float, default=1.0)
    args = ap.parse_args()

    recs = (make_synthetic(minutes=args.minutes) if args.data == "synthetic"
            else load_husm(args.data))
    acc = subject_spectra(recs)
    print(f"\n{len(acc)} subjects\n")

    print("[A1] aperiodic exponent and offset")
    out, expo, off, y = a1_exponent(acc)

    print("\n[A2] does the exponent explain the artifact features?")
    a2_explains_features(acc, expo, y)

    print("\n[A3] flatten each spectrum by its own 1/f fit")
    out["flatten"] = a3_flatten(acc)

    run.set_result(out)


def main():
    with start_run("e2e") as run:
        _main(run)


if __name__ == "__main__":
    main()
