"""E2d -- what ACTUALLY differs between the groups' spectra?

E2c killed the clean version of the line-noise story: the raw 50 Hz
peak-to-neighbour ratio does NOT differ between groups (AUC 0.568, p=0.36).
Yet `line_resid_45_55` -- relative power in 45-55 Hz within the gamma band --
separates them at AUC 0.876 with log-d -2.24, and `zero_cross_rate` at 0.918.

Both of those are measures of SPECTRAL SHAPE, not of absolute line noise. So the
question is no longer "who has more mains hum" but:

    where in the spectrum do the two groups diverge, and is that divergence
    physiological or instrumental?

Three tests, cheapest and most decisive first:

  S1  EDF header audit   -- read the recorded filter settings straight out of
                            the file headers. If MDD and HC were acquired with
                            different high-pass / low-pass / notch settings,
                            everything downstream is an instrumentation
                            difference and the question is answered outright.
  S2  group-average PSD  -- 0 to Nyquist, log power, MDD vs HC, plus the ratio.
                            Shows exactly which frequencies carry the gap.
  S3  spectral edge      -- per-subject frequency below which 95% of power
                            lies. A hard group difference here means different
                            anti-alias / low-pass cutoffs.

Run:
  python experiments/e2d_spectrum.py --data "D:\\Project\\PaperPlan\\EEG"
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
from collections import Counter, defaultdict

import numpy as np
from scipy.signal import welch
from sklearn.metrics import roc_auc_score

sys.path.insert(0, ".")

from eegmdd.runlog import start_run
from eegmdd.data import load_husm, make_synthetic, parse_filename


# --- S1: EDF header audit ----------------------------------------------------

def read_edf_prefilter(path: str):
    """Parse the EDF header's per-signal prefiltering field.

    EDF layout: 256-byte fixed header, then for ns signals:
        label 16 | transducer 80 | phys dim 8 | phys min 8 | phys max 8
        | dig min 8 | dig max 8 | prefiltering 80 | n samples 8 | reserved 32
    The prefiltering strings are what the acquisition software recorded, e.g.
    "HP:0.1Hz LP:70Hz N:50Hz". They are the ground truth about filter settings.
    """
    with open(path, "rb") as f:
        head = f.read(256)
        ns = int(head[252:256].decode("ascii", "ignore").strip() or 0)
        if ns <= 0:
            return None, 0
        block = f.read(ns * 256)
    off = ns * (16 + 80 + 8 + 8 + 8 + 8 + 8)
    pre = [block[off + i * 80: off + (i + 1) * 80].decode("ascii", "ignore").strip()
           for i in range(ns)]
    return pre, ns


def s1_headers(root: str):
    paths = sorted(glob.glob(os.path.join(root, "**", "*.edf"), recursive=True))
    by_group = defaultdict(Counter)
    n_bad = 0
    for p in paths:
        meta = parse_filename(os.path.basename(p))
        if meta["subject"] is None or meta["condition"] not in ("EC", "EO"):
            continue
        try:
            pre, ns = read_edf_prefilter(p)
        except Exception:
            n_bad += 1
            continue
        if not pre:
            n_bad += 1
            continue
        grp = "MDD" if meta["label"] == 1 else "HC"
        # the EEG channels normally share one setting; record the distinct set
        by_group[grp][" | ".join(sorted(set(pre[:19])))] += 1

    print(f"  prefiltering strings recorded in the EDF headers"
          f"{f'  ({n_bad} unreadable)' if n_bad else ''}:")
    for grp in ("MDD", "HC"):
        print(f"\n    {grp}:")
        if not by_group[grp]:
            print("      (none)")
        for s, n in by_group[grp].most_common():
            print(f"      [{n:3d} files] {s[:110] if s else '(empty)'}")

    sets = {g: set(by_group[g]) for g in by_group}
    if len(sets) == 2:
        only_mdd = sets.get("MDD", set()) - sets.get("HC", set())
        only_hc = sets.get("HC", set()) - sets.get("MDD", set())
        if only_mdd or only_hc:
            print("\n  *** GROUPS DIFFER IN RECORDED FILTER SETTINGS ***")
            print("  This is an instrumentation difference, not a neural one.")
        else:
            print("\n  header filter settings are identical across groups")
    return {g: dict(c) for g, c in by_group.items()}


# --- S2 / S3: spectra --------------------------------------------------------

def subject_psd(recs, fs=256, nperseg=2048):
    """Average PSD per subject, across channels and recordings."""
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


def s2_group_psd(acc, top_n=12):
    f = next(iter(acc.values()))["f"]
    mdd = np.array([v["psd"] for v in acc.values() if v["label"] == 1])
    hc = np.array([v["psd"] for v in acc.values() if v["label"] == 0])
    gm, gh = np.median(mdd, axis=0), np.median(hc, axis=0)
    ratio = np.log10((gm + 1e-30) / (gh + 1e-30))

    y = np.array([v["label"] for v in acc.values()])
    P = np.array([v["psd"] for v in acc.values()])
    aucs = np.array([max(a, 1 - a) for a in
                     (roc_auc_score(y, P[:, i]) for i in range(P.shape[1]))])

    print(f"  {len(mdd)} MDD / {len(hc)} HC subjects, {len(f)} frequency bins "
          f"(resolution {f[1]-f[0]:.3f} Hz)\n")
    print("  frequencies where the groups separate most (per-bin subject AUC):")
    print(f"    {'Hz':>8}{'AUC':>8}{'dir':>9}{'log10 MDD/HC':>15}")
    for i in np.argsort(-aucs)[:top_n]:
        d = "MDD>HC" if gm[i] > gh[i] else "HC>MDD"
        print(f"    {f[i]:>8.2f}{aucs[i]:>8.3f}{d:>9}{ratio[i]:>15.2f}")

    print("\n  coarse band summary (median power, log10 MDD/HC):")
    for lo, hi in [(1, 4), (4, 8), (8, 12), (12, 30), (30, 45),
                   (45, 55), (55, 70), (70, 100), (100, 127)]:
        m = (f >= lo) & (f < hi)
        if not m.any():
            continue
        r = np.log10((gm[m].mean() + 1e-30) / (gh[m].mean() + 1e-30))
        print(f"    {lo:>3}-{hi:<3} Hz   log10 ratio {r:+6.2f}   "
              f"mean AUC {aucs[m].mean():.3f}")
    return dict(freqs=f.tolist(), auc=aucs.tolist(),
                log_ratio=ratio.tolist(),
                mdd_median=gm.tolist(), hc_median=gh.tolist())


def s3_spectral_edge(acc, frac=0.95):
    """Frequency below which `frac` of total power lies, per subject."""
    f = next(iter(acc.values()))["f"]
    y, edge = [], []
    for v in acc.values():
        c = np.cumsum(v["psd"])
        c = c / c[-1]
        edge.append(float(f[np.searchsorted(c, frac)]))
        y.append(v["label"])
    y, edge = np.array(y), np.array(edge)
    a = roc_auc_score(y, edge)
    from scipy.stats import mannwhitneyu
    p = float(mannwhitneyu(edge[y == 1], edge[y == 0]).pvalue)
    print(f"  {int(frac*100)}% spectral edge frequency:")
    print(f"    MDD  q1/med/q3 = " +
          " / ".join(f"{v:.1f}" for v in np.percentile(edge[y == 1], [25, 50, 75])) + " Hz")
    print(f"    HC   q1/med/q3 = " +
          " / ".join(f"{v:.1f}" for v in np.percentile(edge[y == 0], [25, 50, 75])) + " Hz")
    print(f"    AUC {max(a, 1-a):.3f} ({'MDD>HC' if a > 0.5 else 'HC>MDD'})  p={p:.2e}")
    print("\n  A hard group difference here means different low-pass / anti-alias")
    print("  cutoffs -- an acquisition setting, not physiology.")
    return dict(auc=float(max(a, 1 - a)), p=p,
                mdd_median=float(np.median(edge[y == 1])),
                hc_median=float(np.median(edge[y == 0])))


def _main(run):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="synthetic")
    ap.add_argument("--minutes", type=float, default=1.0)
    args = ap.parse_args()

    out = {}
    if args.data != "synthetic":
        print("\n[S1] EDF header filter-setting audit")
        out["headers"] = s1_headers(args.data)

    recs = (make_synthetic(minutes=args.minutes) if args.data == "synthetic"
            else load_husm(args.data))
    acc = subject_psd(recs)

    print("\n[S2] group-average power spectrum")
    out["psd"] = s2_group_psd(acc)

    print("\n[S3] spectral edge frequency")
    out["edge"] = s3_spectral_edge(acc)

    run.set_result(out)


def main():
    with start_run("e2d") as run:
        _main(run)


if __name__ == "__main__":
    main()
