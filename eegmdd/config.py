"""Central configuration. Every protocol choice from the paper is a flag here.

This is the whole point of the design: E1 (protocol decomposition) becomes a
loop over configs, not four separate rewrites of the pipeline.
"""
from dataclasses import dataclass, asdict, field
from typing import Literal, Tuple

# Band definitions exactly as in Anik et al. 2024, Section II-D.
BANDS = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 12.0),
    "beta": (12.0, 30.0),
    "gamma": (30.0, 100.0),
    "all": (0.5, 100.0),
    # Control arm: gamma with the EMG-dominant range excluded.
    "gamma_low": (30.0, 45.0),
    # Control arm: everything below the line-noise notch.
    "sub45": (0.5, 45.0),

    # --- bands added after E2d ------------------------------------------
    # The EDF headers say the recordings are low-passed at 80 Hz, so the
    # paper's nominal 30-100 Hz "gamma" includes 20 Hz of empty stopband.
    "gamma_usable": (30.0, 80.0),    # gamma, clipped to what was recorded
    # Above the mains region and below the low-pass: if a real neural gamma
    # effect exists, it has to live here.
    "gamma_noline": (55.0, 80.0),
    # The mains region on its own. If this alone matches full-gamma accuracy,
    # the "gamma biomarker" is residual 50 Hz.
    "line_only": (45.0, 55.0),
}

SplitKind = Literal["epoch_random", "subject_kfold", "loso"]
NormScope = Literal["global", "per_subject", "train_fold"]
Condition = Literal["EC", "EO", "both"]


@dataclass
class Config:
    # --- signal ---
    fs: int = 256
    band: str = "gamma"
    epoch_sec: float = 15.0
    overlap_sec: float = 1.0          # paper uses 1 s overlap; 0.0 = disjoint
    notch_hz: float = 50.0            # HUSM recorded in Malaysia -> 50 Hz mains
    apply_notch: bool = True
    apply_ica: bool = False           # paper tested ICA and discarded it
    condition: Condition = "both"

    # --- protocol (the variables under study) ---
    split: SplitKind = "subject_kfold"
    n_folds: int = 10
    norm_scope: NormScope = "train_fold"

    # --- model ---
    model: str = "ex1dcnn"            # ex1dcnn | ex1dcnn_dann | artifact_lr
    n_channels: int = 19
    n_filters: int = 5                # paper uses 5; 16 generalises far better
    lr: float = 1e-3
    # NOTE: the paper states lambda = 0.02 (eq. 8). Applied literally as Adam
    # weight_decay this COLLAPSES the 5-filter network to a constant output
    # (logit variance -> 0, accuracy -> majority class). Their lambda is
    # evidently a different formulation. Document this in the paper; use 1e-4.
    weight_decay: float = 1e-4
    batch_size: int = 25
    max_epochs: int = 40
    patience: int = 8

    # --- DANN ---
    dann_lambda: float = 0.3          # gradient-reversal strength
    dann_warmup_frac: float = 0.3     # ramp lambda in over first N% of training

    # --- eval ---
    seed: int = 0
    n_seeds: int = 5
    calibrate: bool = True            # temperature scaling on held-out split
    subject_level: bool = True        # aggregate epoch probs -> subject decision

    def band_range(self) -> Tuple[float, float]:
        return BANDS[self.band]

    def tag(self) -> str:
        return (f"{self.band}_{self.epoch_sec:g}s_ov{self.overlap_sec:g}"
                f"_{self.split}_{self.norm_scope}_{self.model}_s{self.seed}")

    def to_dict(self):
        return asdict(self)


# --- Reference configs -------------------------------------------------------

def paper_config() -> Config:
    """Anik et al. 2024 as literally described: gamma, 15 s, 1 s overlap."""
    return Config(band="gamma", epoch_sec=15.0, overlap_sec=1.0,
                  split="subject_kfold", norm_scope="global")


def optimistic_config() -> Config:
    """The same, but with an epoch-level random split -- the leaky version."""
    c = paper_config()
    c.split = "epoch_random"
    return c


def honest_config() -> Config:
    """Strict: disjoint epochs, leave-one-subject-out, train-only statistics."""
    return Config(band="gamma", epoch_sec=15.0, overlap_sec=0.0,
                  split="loso", norm_scope="train_fold")
