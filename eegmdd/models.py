"""Ex-1DCNN reimplemented from Anik et al. 2024, Table I, plus the DANN variant.

Layer table from the paper (15 s epoch @ 256 Hz -> 3840 samples in):
   1  Conv1d   k=3 s=1  LeakyReLU   -> 3838 x 5
   2  MaxPool  p=2 s=2              -> 1919 x 5
   3  Conv1d   k=3 s=1  LeakyReLU   -> 1917 x 5
   4  MaxPool  p=2 s=2, dropout 0.5 ->  958 x 5
   5  Conv1d   k=3 s=1  LeakyReLU   ->  956 x 5
   6  AvgPool  p=2 s=2, dropout 0.5 ->  478 x 5
   7  Conv1d   k=3 s=1  LeakyReLU   ->  476 x 5
   8  AvgPool  p=2 s=2              ->  238 x 5
   9  Conv1d   k=3 s=1  LeakyReLU   ->  236 x 5
  10  GlobalAvgPool                 ->    5
  11  Linear -> 1, sigmoid

Note the output shapes confirm 5 filters throughout and no padding.
"""
from __future__ import annotations

import torch
import torch.nn as nn
from torch.autograd import Function


class Ex1DCNN(nn.Module):
    def __init__(self, n_channels: int = 19, n_filters: int = 5, p_drop: float = 0.5):
        super().__init__()
        f = n_filters
        act = lambda: nn.LeakyReLU()
        self.features = nn.Sequential(
            nn.Conv1d(n_channels, f, 3, stride=1), act(),   # 1
            nn.MaxPool1d(2, 2),                             # 2
            nn.Conv1d(f, f, 3, stride=1), act(),            # 3
            nn.MaxPool1d(2, 2), nn.Dropout(p_drop),         # 4
            nn.Conv1d(f, f, 3, stride=1), act(),            # 5
            nn.AvgPool1d(2, 2), nn.Dropout(p_drop),         # 6
            nn.Conv1d(f, f, 3, stride=1), act(),            # 7
            nn.AvgPool1d(2, 2),                             # 8
            nn.Conv1d(f, f, 3, stride=1), act(),            # 9
            nn.AdaptiveAvgPool1d(1),                        # 10
        )
        self.classifier = nn.Linear(f, 1)                   # 11

    def embed(self, x):
        return self.features(x).squeeze(-1)                 # (B, f)

    def forward(self, x):
        return self.classifier(self.embed(x)).squeeze(-1)   # logits


# --- domain-adversarial variant ---------------------------------------------

class GradReverse(Function):
    @staticmethod
    def forward(ctx, x, lambd):
        ctx.lambd = lambd
        return x.view_as(x)

    @staticmethod
    def backward(ctx, grad):
        return -ctx.lambd * grad, None


def grad_reverse(x, lambd: float):
    return GradReverse.apply(x, lambd)


class Ex1DCNN_DANN(nn.Module):
    """Ex-1DCNN trunk + a subject-identity discriminator behind a gradient
    reversal layer. The trunk is pushed to produce representations from which
    subject identity is NOT recoverable -- i.e. subject-invariant features.

    Wider trunk (n_filters) is usually needed: 5 filters is a very small
    bottleneck to ask invariance from. Report both.
    """

    def __init__(self, n_channels=19, n_filters=5, n_subjects=64, p_drop=0.5,
                 disc_hidden=32):
        super().__init__()
        self.backbone = Ex1DCNN(n_channels, n_filters, p_drop)
        self.discriminator = nn.Sequential(
            nn.Linear(n_filters, disc_hidden), nn.ReLU(),
            nn.Linear(disc_hidden, n_subjects),
        )

    def forward(self, x, lambd: float = 0.0):
        z = self.backbone.embed(x)
        logit = self.backbone.classifier(z).squeeze(-1)
        subj_logits = self.discriminator(grad_reverse(z, lambd))
        return logit, subj_logits


def build_model(cfg, n_subjects: int = 64):
    nf = getattr(cfg, "n_filters", 5)
    if cfg.model == "ex1dcnn":
        return Ex1DCNN(cfg.n_channels, nf)
    if cfg.model == "ex1dcnn_dann":
        return Ex1DCNN_DANN(cfg.n_channels, nf, n_subjects=n_subjects)
    raise ValueError(cfg.model)
