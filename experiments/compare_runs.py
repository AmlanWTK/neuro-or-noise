"""Compare two saved runs statistically.

A 0.05 accuracy gap on 63 subjects is about three people. Eyeballing two numbers
cannot tell you whether that is a real difference. This does the paired test.

  python experiments/compare_runs.py results/runs/<runA> results/runs/<runB> \
      --band-a gamma --band-b gamma --split subject_kfold
"""
from __future__ import annotations

import argparse, json, os, sys
import numpy as np

sys.path.insert(0, ".")
from eegmdd.metrics import binary_metrics, bootstrap_ci, mcnemar


def load_pred(run_dir, band, split):
    with open(os.path.join(run_dir, "result.json")) as f:
        res = json.load(f)
    rows = res.get("P3") or []
    for r in rows:
        if r.get("band") == band:
            key = f"{split}_pred"
            if key not in r:
                sys.exit(f"{run_dir}: no saved predictions for {band}/{split}.\n"
                         "That run predates prediction saving -- rerun it.")
            p = r[key]
            return (np.array(p["y"]), np.array(p["prob"]),
                    [str(s) for s in p["subjects"]])
    sys.exit(f"{run_dir}: band '{band}' not found. Present: "
             f"{[r.get('band') for r in rows]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_a"); ap.add_argument("run_b")
    ap.add_argument("--band-a", default="gamma"); ap.add_argument("--band-b", default="gamma")
    ap.add_argument("--split", default="subject_kfold")
    a = ap.parse_args()

    ya, pa, sa = load_pred(a.run_a, a.band_a, a.split)
    yb, pb, sb = load_pred(a.run_b, a.band_b, a.split)
    if sa != sb:
        common = sorted(set(sa) & set(sb))
        ia = [sa.index(s) for s in common]; ib = [sb.index(s) for s in common]
        ya, pa, yb, pb = ya[ia], pa[ia], yb[ib], pb[ib]
        print(f"  aligned on {len(common)} shared subjects")
    assert (ya == yb).all(), "label mismatch between runs"

    ma, mb = binary_metrics(ya, pa), binary_metrics(yb, pb)
    ca, cb = bootstrap_ci(ya, pa), bootstrap_ci(yb, pb)
    n01, n10, p = mcnemar(ya, pa, pb)

    print(f"\n  A  {a.band_a:<16} acc {ma['accuracy']:.4f}  CI[{ca[0]:.3f},{ca[1]:.3f}]")
    print(f"  B  {a.band_b:<16} acc {mb['accuracy']:.4f}  CI[{cb[0]:.3f},{cb[1]:.3f}]")
    print(f"\n  difference: {ma['accuracy']-mb['accuracy']:+.4f} "
          f"({(ma['accuracy']-mb['accuracy'])*len(ya):+.1f} subjects)")
    print(f"  McNemar: A-only correct = {n01}, B-only correct = {n10}, p = {p:.4f}")
    print("\n  " + ("DIFFERENCE IS SIGNIFICANT (p<0.05)" if p < 0.05 else
                    "NOT SIGNIFICANT -- report both, claim no winner"))


if __name__ == "__main__":
    main()
