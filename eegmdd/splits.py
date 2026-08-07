"""Cross-validation splitters. The single most important file in the project.

The difference between `epoch_random` and `subject_kfold` is the difference
between 99.6% and whatever the truth turns out to be.
"""
from __future__ import annotations

import numpy as np
from sklearn.model_selection import KFold, StratifiedKFold

from .config import Config
from .data import EpochSet


def _subject_table(es: EpochSet):
    subs = np.unique(es.subject)
    labels = np.array([es.y[es.subject == s][0] for s in subs])
    return subs, labels


def make_folds(es: EpochSet, cfg: Config):
    """Yield (train_idx, test_idx) over EPOCH indices."""
    idx = np.arange(len(es))

    if cfg.split == "epoch_random":
        # The optimistic protocol: epochs shuffled without regard to subject.
        # Overlapping epochs from one recording land on both sides of the split.
        kf = KFold(n_splits=cfg.n_folds, shuffle=True, random_state=cfg.seed)
        yield from kf.split(idx)

    elif cfg.split == "subject_kfold":
        # Folds are built over SUBJECTS, stratified by class.
        subs, labels = _subject_table(es)
        skf = StratifiedKFold(n_splits=cfg.n_folds, shuffle=True, random_state=cfg.seed)
        for tr_s, te_s in skf.split(subs, labels):
            test_subs = set(subs[te_s])
            te = np.array([i for i in idx if es.subject[i] in test_subs])
            tr = np.array([i for i in idx if es.subject[i] not in test_subs])
            yield tr, te

    elif cfg.split == "loso":
        subs, _ = _subject_table(es)
        for s in subs:
            te = np.where(es.subject == s)[0]
            tr = np.where(es.subject != s)[0]
            yield tr, te

    else:
        raise ValueError(cfg.split)


def n_folds_for(es: EpochSet, cfg: Config) -> int:
    return es.n_subjects if cfg.split == "loso" else cfg.n_folds


def assert_no_subject_leak(es: EpochSet, tr: np.ndarray, te: np.ndarray) -> bool:
    """True if no subject appears on both sides. Call this in tests."""
    return not (set(es.subject[tr]) & set(es.subject[te]))
