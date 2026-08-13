"""Print a saved run record in full -- every stored number, not just the render.

The console render is deliberately terse (it shows the delta, not the two
accuracies it came from). When a result is surprising, the delta alone is not
enough to interpret it: a protocol delta near zero means one thing if both
accuracies are 0.95 and something completely different if both are 0.53.

  python experiments/show_run.py                      # most recent run
  python experiments/show_run.py 20260813-220728_bandcheck
"""
from __future__ import annotations
import json, sys
from pathlib import Path

RUNS = Path("results/runs")


def main():
    if len(sys.argv) > 1:
        run = RUNS / sys.argv[1]
    else:
        run = max((d for d in RUNS.iterdir() if d.is_dir()), key=lambda d: d.name)
    print(f"=== {run.name} ===")

    meta = run / "meta.json"
    if meta.exists():
        m = json.loads(meta.read_text())
        for k in ("argv", "commit", "dirty", "seconds", "started"):
            if k in m:
                print(f"  {k}: {m[k]}")

    res = json.loads((run / "result.json").read_text())
    for k, v in res.items():
        if k == "checks":
            continue
        print(f"  {k}: {v}")

    for c in res.get("checks", []):
        print(f"\n  [{c['id']}] {c.get('name','')}  ->  {c.get('status','')}")
        print(f"      {c.get('message','')}")
        for dk, dv in c.get("detail", {}).items():
            if isinstance(dv, list) and dv and isinstance(dv[0], dict):
                for row in dv:
                    print(f"      {dk}: {row}")
            else:
                print(f"      {dk} = {dv}")


if __name__ == "__main__":
    main()
