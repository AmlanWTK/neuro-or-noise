"""Run the BandCheck validity protocol on a dataset + band claim.

  python experiments/bandcheck_run.py --data "D:\\Project\\PaperPlan\\EEG" --band gamma
  python experiments/bandcheck_run.py --data "D:\\..." --band gamma --model ex1dcnn   # slow
"""
from __future__ import annotations
import argparse, sys
sys.path.insert(0, ".")

from eegmdd.runlog import start_run
from eegmdd.bandcheck import run_bandcheck
from eegmdd.data import load_husm, make_synthetic


def _main(run):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="synthetic")
    ap.add_argument("--band", default="gamma")
    ap.add_argument("--model", default="artifact_lr", choices=["artifact_lr", "ex1dcnn"])
    ap.add_argument("--epoch-sec", type=float, default=15.0)
    ap.add_argument("--n-folds", type=int, default=10)
    ap.add_argument("--n-sub", type=int, default=3, help="sub-bands for V4")
    ap.add_argument("--stop", default="45,55", help="V5 excision range, Hz")
    ap.add_argument("--header-lp", type=float, default=None,
                    help="low-pass from the EDF header, e.g. 80")
    ap.add_argument("--checks", default="V1,V2,V3,V4,V5")
    ap.add_argument("--minutes", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-epochs", type=int, default=40,
                    help="training budget; MOVES THE NUMBERS -- always report it")
    args = ap.parse_args()

    recs = (make_synthetic(minutes=args.minutes) if args.data == "synthetic"
            else load_husm(args.data))
    lo, hi = (float(v) for v in args.stop.split(","))
    rep = run_bandcheck(recs, band=args.band, model=args.model,
                        epoch_sec=args.epoch_sec, n_folds=args.n_folds,
                        seed=args.seed, header_lp=args.header_lp,
                        checks=tuple(args.checks.split(",")),
                        n_sub=args.n_sub, stop=(lo, hi),
                        max_epochs=args.max_epochs)
    run.set_result(rep.to_dict())


def main():
    with start_run("bandcheck") as run:
        _main(run)


if __name__ == "__main__":
    main()
