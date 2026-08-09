"""E1 -- protocol decomposition. The most quotable table in the paper.

Vary one protocol factor at a time and attribute accuracy points to each.
Run on synthetic data first to validate; then point it at real recordings.
"""
import argparse, json, sys, time
import numpy as np
sys.path.insert(0, ".")

from eegmdd.runlog import start_run

from eegmdd.config import Config
from eegmdd.data import make_synthetic, build_epochs, load_husm
from eegmdd.train import run_cv


def get_recordings(args):
    if args.data == "synthetic":
        return make_synthetic(minutes=args.minutes, seed=args.seed)
    return load_husm(args.data)


def _main(run):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="synthetic", help="'synthetic' or path to .edf dir")
    ap.add_argument("--minutes", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epoch-sec", type=float, default=15.0,
                    help="paper's best config is gamma @ 15 s")
    ap.add_argument("--n-folds", type=int, default=10, help="paper uses 10")
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--skip-loso", action="store_true", help="LOSO is ~10x slower; skip for smoke tests")
    args = ap.parse_args()

    recs = get_recordings(args)

    # one factor at a time, from the paper's setting toward the strict setting
    arms = [
        ("A paper-as-described", dict(split="subject_kfold", norm_scope="global",  overlap_sec=1.0)),
        ("B epoch-random split", dict(split="epoch_random",  norm_scope="global",  overlap_sec=1.0)),
        ("C + no overlap",       dict(split="epoch_random",  norm_scope="global",  overlap_sec=0.0)),
        ("D subject folds",      dict(split="subject_kfold", norm_scope="train_fold", overlap_sec=0.0)),
        ("E leave-one-subj-out", dict(split="loso",          norm_scope="train_fold", overlap_sec=0.0)),
    ]

    if args.skip_loso:
        arms = [a for a in arms if "loso" not in a[1]["split"]]

    out = []
    for name, over in arms:
        cfg = Config(band="gamma", epoch_sec=args.epoch_sec, max_epochs=args.epochs,
                     seed=args.seed, n_folds=args.n_folds, **over)
        es = build_epochs(recs, cfg)
        t0 = time.time()
        print(f"\n=== {name}  ({len(es)} epochs, {es.n_subjects} subjects)")
        res = run_cv(es, cfg, verbose=False)
        e, s = res["epoch"], res["subject"]
        print(f"    epoch acc {e['accuracy']:.4f} | subject acc {s['accuracy']:.4f} "
              f"CI[{s['ci95'][0]:.2f},{s['ci95'][1]:.2f}] | {time.time()-t0:.0f}s")
        out.append(dict(arm=name, epoch_acc=e["accuracy"], subject_acc=s["accuracy"],
                        ci=s["ci95"], n_epochs=len(es)))

    print("\n--- protocol deltas (epoch-level accuracy) ---")
    for i in range(1, len(out)):
        d = out[i]["epoch_acc"] - out[i-1]["epoch_acc"]
        print(f"  {out[i-1]['arm']:24s} -> {out[i]['arm']:24s}  {d:+.4f}")

    run.set_result(dict(arms=out, args=vars(args)))


def main():
    with start_run("e1") as run:
        _main(run)


if __name__ == "__main__":
    main()
