"""Training / evaluation loop shared by every experiment."""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from .artifact import featurise
from .config import Config
from .data import EpochSet, normalise
from .metrics import (binary_metrics, bootstrap_ci, expected_calibration_error,
                      fit_temperature, to_subject_level)
from .models import build_model
from .splits import make_folds, assert_no_subject_leak


def _device():
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _loaders(X, y, subj_codes, cfg, shuffle=True):
    ds = torch.utils.data.TensorDataset(
        torch.from_numpy(X), torch.from_numpy(y).float(),
        torch.from_numpy(subj_codes).long())
    return torch.utils.data.DataLoader(ds, batch_size=cfg.batch_size,
                                       shuffle=shuffle, drop_last=False)


def train_one_fold(es: EpochSet, tr, te, cfg: Config, subject_codes=None):
    """Train on tr, return probabilities and logits on te."""
    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)

    es_n = normalise(es, cfg, train_idx=tr)
    dev = _device()

    if cfg.model == "artifact_lr":
        F = featurise(es_n.X, cfg.fs)
        sc = StandardScaler().fit(F[tr])
        clf = LogisticRegression(max_iter=2000, C=1.0)
        clf.fit(sc.transform(F[tr]), es_n.y[tr])
        prob = clf.predict_proba(sc.transform(F[te]))[:, 1]
        logit = np.log(np.clip(prob, 1e-7, 1 - 1e-7) /
                       np.clip(1 - prob, 1e-7, 1 - 1e-7))
        return prob, logit

    n_subj = len(np.unique(subject_codes)) if subject_codes is not None else 64
    model = build_model(cfg, n_subjects=n_subj).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr,
                           weight_decay=cfg.weight_decay,
                           betas=(0.9, 0.999), eps=1e-7)
    bce = nn.BCEWithLogitsLoss()
    ce = nn.CrossEntropyLoss()

    codes = subject_codes if subject_codes is not None else np.zeros(len(es_n), dtype=np.int64)
    dl = _loaders(es_n.X[tr], es_n.y[tr], codes[tr], cfg, shuffle=True)

    is_dann = cfg.model.endswith("dann")
    best_loss, bad, best_state = np.inf, 0, None

    for ep in range(cfg.max_epochs):
        model.train()
        frac = ep / max(1, cfg.max_epochs - 1)
        lambd = cfg.dann_lambda * min(1.0, frac / max(1e-6, cfg.dann_warmup_frac))
        tot = 0.0
        for xb, yb, sb in dl:
            xb, yb, sb = xb.to(dev), yb.to(dev), sb.to(dev)
            opt.zero_grad()
            if is_dann:
                logit, slog = model(xb, lambd)
                loss = bce(logit, yb) + ce(slog, sb)
            else:
                loss = bce(model(xb), yb)
            loss.backward()
            opt.step()
            tot += loss.item() * len(xb)
        tot /= max(1, len(tr))
        if tot < best_loss - 1e-4:
            best_loss, bad = tot, 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= cfg.patience:
                break
    if best_state is not None:
        model.load_state_dict(best_state)

    model.eval()
    with torch.no_grad():
        xb = torch.from_numpy(es_n.X[te]).to(dev)
        out = model(xb, 0.0) if is_dann else model(xb)
        logit = (out[0] if is_dann else out).cpu().numpy()
    prob = 1.0 / (1.0 + np.exp(-logit))
    return prob, logit


def run_cv(es: EpochSet, cfg: Config, verbose=True) -> dict:
    """Full cross-validation. Returns epoch- and subject-level results."""
    subs = np.unique(es.subject)
    code_of = {s: i for i, s in enumerate(subs)}
    codes = np.array([code_of[s] for s in es.subject], dtype=np.int64)

    all_prob = np.zeros(len(es))
    all_logit = np.zeros(len(es))
    seen = np.zeros(len(es), dtype=bool)

    for k, (tr, te) in enumerate(make_folds(es, cfg)):
        if cfg.split != "epoch_random":
            assert assert_no_subject_leak(es, tr, te), f"subject leak in fold {k}"
        p, l = train_one_fold(es, tr, te, cfg, subject_codes=codes)
        all_prob[te], all_logit[te], seen[te] = p, l, True
        if verbose:
            m = binary_metrics(es.y[te], p)
            print(f"  fold {k:2d}  n_te={len(te):5d}  acc={m['accuracy']:.4f}")

    assert seen.all(), "some epochs never appeared in a test fold"

    res = {"config": cfg.to_dict()}
    res["epoch"] = binary_metrics(es.y, all_prob)
    res["epoch"]["ece"] = expected_calibration_error(es.y, all_prob)

    ys, ps, _ = to_subject_level(es.y, all_prob, es.subject)
    sm = binary_metrics(ys, ps)
    lo, hi = bootstrap_ci(ys, ps, seed=cfg.seed)
    sm["ci95"] = (lo, hi)
    sm["n_subjects"] = int(len(ys))
    res["subject"] = sm

    if cfg.calibrate:
        T = fit_temperature(all_logit, es.y)
        pc = 1.0 / (1.0 + np.exp(-all_logit / T))
        res["temperature"] = T
        res["epoch_calibrated_ece"] = expected_calibration_error(es.y, pc)

    res["_prob"] = all_prob
    return res
