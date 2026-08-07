"""Metrics, subject-level aggregation, calibration, bootstrap CIs.

The paper reports epoch-level accuracy with no interval. Reviewers will want
subject-level numbers with confidence intervals -- with 64 subjects the CI is
roughly +-10 points, which is itself worth saying out loud.
"""
from __future__ import annotations

import numpy as np


def binary_metrics(y: np.ndarray, prob: np.ndarray, thr: float = 0.5) -> dict:
    pred = (prob >= thr).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    acc = (tp + tn) / max(1, len(y))
    prec = tp / max(1, tp + fp)
    rec = tp / max(1, tp + fn)
    spec = tn / max(1, tn + fp)
    f1 = 2 * prec * rec / max(1e-12, prec + rec)
    return dict(accuracy=acc, precision=prec, recall=rec,
                specificity=spec, f1=f1, tp=tp, tn=tn, fp=fp, fn=fn)


def to_subject_level(y, prob, subject):
    """Mean predicted probability per subject -> one decision per person."""
    subs = np.unique(subject)
    ys, ps = [], []
    for s in subs:
        m = subject == s
        ys.append(int(y[m][0]))
        ps.append(float(prob[m].mean()))
    return np.array(ys), np.array(ps), subs


def bootstrap_ci(y, prob, n_boot=2000, thr=0.5, seed=0, alpha=0.05):
    """Percentile CI on accuracy, resampling SUBJECTS (not epochs)."""
    rng = np.random.default_rng(seed)
    n = len(y)
    accs = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        accs.append(binary_metrics(y[idx], prob[idx], thr)["accuracy"])
    lo, hi = np.percentile(accs, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def expected_calibration_error(y, prob, n_bins=10):
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        m = (prob >= bins[i]) & (prob < bins[i + 1] if i < n_bins - 1 else prob <= 1.0)
        if m.sum() == 0:
            continue
        conf = prob[m].mean()
        acc = ((prob[m] >= 0.5).astype(int) == y[m]).mean()
        ece += (m.sum() / len(y)) * abs(acc - conf)
    return float(ece)


def fit_temperature(logits: np.ndarray, y: np.ndarray, grid=None) -> float:
    """1-D temperature search on held-out logits. Cheap and robust."""
    grid = grid if grid is not None else np.linspace(0.25, 5.0, 96)
    best, best_nll = 1.0, np.inf
    for T in grid:
        p = 1.0 / (1.0 + np.exp(-logits / T))
        p = np.clip(p, 1e-7, 1 - 1e-7)
        nll = -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()
        if nll < best_nll:
            best, best_nll = float(T), nll
    return best


def mcnemar(y, prob_a, prob_b, thr=0.5):
    """Paired test between two models on the same samples. Returns (b, c, p)."""
    from scipy.stats import binomtest
    a = (prob_a >= thr).astype(int) == y
    b_ = (prob_b >= thr).astype(int) == y
    n01 = int((a & ~b_).sum())
    n10 = int((~a & b_).sum())
    if n01 + n10 == 0:
        return n01, n10, 1.0
    p = binomtest(n01, n01 + n10, 0.5).pvalue
    return n01, n10, float(p)
