"""Immutable run records.

Every experiment writes a timestamped directory under results/runs/ that is
NEVER overwritten:

    results/runs/20260805-1432_e2/
        meta.json      command, git commit, package versions, timing
        console.log    full stdout, exactly as you saw it
        result.json    the structured result the script produced

Why this matters: in four months you will look at a number in the paper and
need to know which code produced it, on what data, with which flags. A single
results/e2.json that gets clobbered on every run cannot answer that. These
directories can.

They are small (KB), so they are COMMITTED to git -- they are the experimental
record, not build artifacts.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import platform
import subprocess
import sys
import time

RUNS_DIR = os.path.join("results", "runs")


def _git(*args) -> str:
    try:
        return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL,
                                       text=True).strip()
    except Exception:
        return "unknown"


def _versions() -> dict:
    v = {"python": sys.version.split()[0], "platform": platform.platform()}
    for mod in ("numpy", "scipy", "sklearn", "torch", "mne"):
        try:
            v[mod] = __import__(mod).__version__
        except Exception:
            v[mod] = "absent"
    return v


class _Tee:
    """Duplicate stdout to a file without hiding it from the terminal."""

    def __init__(self, stream, path):
        self.stream = stream
        self.fh = open(path, "w", encoding="utf-8")

    def write(self, data):
        self.stream.write(data)
        self.fh.write(data)
        return len(data)

    def flush(self):
        self.stream.flush()
        self.fh.flush()

    def close(self):
        try:
            self.fh.close()
        except Exception:
            pass


class Run:
    """Context manager. Use via start_run()."""

    def __init__(self, name: str, args=None, root: str = RUNS_DIR):
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.name = name
        self.dir = os.path.join(root, f"{stamp}_{name}")
        os.makedirs(self.dir, exist_ok=True)
        self.args = vars(args) if hasattr(args, "__dict__") else (args or {})
        self.t0 = time.time()
        self._tee = None
        self.result = {}

    # -- lifecycle --------------------------------------------------------
    def __enter__(self):
        self._tee = _Tee(sys.stdout, os.path.join(self.dir, "console.log"))
        sys.stdout = self._tee
        print(f"[runlog] {self.dir}")
        return self

    def __exit__(self, exc_type, exc, tb):
        meta = {
            "name": self.name,
            "started": _dt.datetime.fromtimestamp(self.t0).isoformat(timespec="seconds"),
            "duration_s": round(time.time() - self.t0, 1),
            "argv": sys.argv,
            "args": self.args,
            "git_commit": _git("rev-parse", "--short", "HEAD"),
            "git_dirty": bool(_git("status", "--porcelain")),
            "versions": _versions(),
            "status": "error" if exc_type else "ok",
        }
        if exc_type:
            meta["error"] = f"{exc_type.__name__}: {exc}"
        with open(os.path.join(self.dir, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)
        if self.result:
            self.save(self.result, "result.json")

        dirty = "  [UNCOMMITTED CHANGES]" if meta["git_dirty"] else ""
        print(f"\n[runlog] {meta['duration_s']}s  commit {meta['git_commit']}{dirty}")
        print(f"[runlog] saved -> {self.dir}")
        if meta["git_dirty"]:
            print("[runlog] WARNING: working tree is dirty, so this run is not "
                  "reproducible from a commit. Commit before the next run.")

        sys.stdout = self._tee.stream
        self._tee.close()
        return False  # never swallow exceptions

    # -- helpers ----------------------------------------------------------
    def save(self, obj, filename: str = "result.json"):
        path = os.path.join(self.dir, filename)
        with open(path, "w") as f:
            json.dump(obj, f, indent=2, default=float)
        return path

    def set_result(self, obj):
        self.result = obj


def start_run(name: str, args=None) -> Run:
    return Run(name, args)


def latest(name: str | None = None) -> str | None:
    """Path of the most recent run, optionally filtered by experiment name."""
    if not os.path.isdir(RUNS_DIR):
        return None
    cands = sorted(d for d in os.listdir(RUNS_DIR)
                   if name is None or d.endswith(f"_{name}"))
    return os.path.join(RUNS_DIR, cands[-1]) if cands else None
