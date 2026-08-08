"""Inspect the downloaded HUSM .edf files BEFORE running any experiment.

Run this first. It answers the questions that decide whether every later number
is trustworthy:

  * how many files, and does the filename parser assign the right label?
  * how many subjects, and is the MDD/HC count 34/30 as the paper says?
  * how many channels, and are the names and order identical across files?
  * what is the sampling rate, and does it match the 256 Hz the paper assumes?
  * how long is each recording, and are any suspiciously short?
  * are there TASK files mixed in with the eyes-open/eyes-closed ones?

Usage:
  python experiments/inspect_data.py --data data/husm
  python experiments/inspect_data.py --data data/husm --json results/data_report.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter

sys.path.insert(0, ".")

from eegmdd.data import parse_filename


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="directory containing .edf files")
    ap.add_argument("--json", default=None, help="optional path to write a report")
    ap.add_argument("--expect-fs", type=int, default=256)
    ap.add_argument("--expect-channels", type=int, default=19)
    args = ap.parse_args()

    try:
        import mne
    except ImportError:
        sys.exit("mne is not installed.  pip install mne")

    paths = sorted(glob.glob(os.path.join(args.data, "**", "*.edf"), recursive=True))
    if not paths:
        sys.exit(f"no .edf files found under {args.data}")

    print(f"found {len(paths)} .edf files under {args.data}\n")

    rows, problems = [], []
    ch_signatures = Counter()
    subjects = {}

    for p in paths:
        name = os.path.basename(p)
        meta = parse_filename(name)
        try:
            raw = mne.io.read_raw_edf(p, preload=False, verbose="ERROR")
        except Exception as e:
            problems.append(f"UNREADABLE  {name}: {e}")
            continue

        picks = mne.pick_types(raw.info, eeg=True, exclude=[])
        ch = [raw.ch_names[i] for i in picks]
        fs = float(raw.info["sfreq"])
        dur = raw.n_times / fs

        ch_signatures["|".join(ch)] += 1
        if meta["subject"]:
            subjects.setdefault(meta["subject"], set()).add(meta["condition"])

        rows.append(dict(file=name, subject=meta["subject"], label=meta["label"],
                         condition=meta["condition"], n_channels=len(ch),
                         fs=fs, duration_s=round(dur, 1)))

        if meta["subject"] is None:
            problems.append(f"UNPARSED    {name}  -> parser could not find a subject id")
        if meta["condition"] == "UNKNOWN":
            problems.append(f"UNKNOWN COND {name}  -> not EC / EO / TASK")
        if abs(fs - args.expect_fs) > 0.5:
            problems.append(f"SAMPLE RATE {name}  -> {fs} Hz, expected {args.expect_fs}")
        if len(ch) != args.expect_channels:
            problems.append(f"CHANNELS    {name}  -> {len(ch)}, expected {args.expect_channels}")
        if dur < 60:
            problems.append(f"SHORT       {name}  -> only {dur:.0f}s")

    # ---- per-file table -------------------------------------------------
    print(f"{'file':<34}{'subject':<12}{'lab':<5}{'cond':<7}{'ch':<5}{'fs':<7}{'dur(s)'}")
    print("-" * 82)
    for r in rows[:40]:
        lab = "MDD" if r["label"] == 1 else ("HC" if r["label"] == 0 else "?")
        print(f"{r['file'][:33]:<34}{str(r['subject']):<12}{lab:<5}"
              f"{r['condition']:<7}{r['n_channels']:<5}{r['fs']:<7.0f}{r['duration_s']}")
    if len(rows) > 40:
        print(f"... and {len(rows) - 40} more")

    # ---- summary --------------------------------------------------------
    mdd = {s for s, _ in ((r["subject"], r) for r in rows if r["label"] == 1) if s}
    hc = {s for s, _ in ((r["subject"], r) for r in rows if r["label"] == 0) if s}
    conds = Counter(r["condition"] for r in rows)

    print(f"\nsubjects : {len(mdd) + len(hc)}   MDD={len(mdd)}  HC={len(hc)}"
          f"   (paper says MDD=34, HC=30)")
    print(f"conditions: {dict(conds)}")
    print(f"channel layouts seen: {len(ch_signatures)}")
    if len(ch_signatures) == 1:
        names = list(ch_signatures)[0].split("|")
        print(f"  consistent across all files, {len(names)} channels:")
        print(f"  {names}")
    else:
        print("  *** INCONSISTENT CHANNEL SETS -- this must be resolved before any run ***")
        for sig, n in ch_signatures.most_common():
            print(f"    [{n} files] {sig.split('|')}")

    if conds.get("TASK"):
        print(f"\nNOTE: {conds['TASK']} TASK files present. The paper uses only the "
              f"resting EC/EO recordings; TASK files are excluded by default "
              f"(condition='both' means EC+EO, not TASK).")

    # ---- problems -------------------------------------------------------
    if problems:
        print(f"\n{len(problems)} PROBLEM(S):")
        for p in problems[:30]:
            print("  " + p)
        if len(problems) > 30:
            print(f"  ... and {len(problems) - 30} more")
    else:
        print("\nno problems detected.")

    print("\nPaste this output back before running experiments on real data.")

    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w") as f:
            json.dump(dict(files=rows, problems=problems,
                           n_mdd=len(mdd), n_hc=len(hc),
                           conditions=dict(conds),
                           channel_layouts=len(ch_signatures)), f, indent=2)
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
