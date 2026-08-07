# neuro-or-noise

**Is gamma-band EEG measuring depression, or measuring muscle?**

Code for the ICASSP 2027 paper re-examining:

> I. A. Anik, A. H. M. Kamal, M. A. Kabir, S. Uddin, M. A. Moni,
> "A Robust Deep-Learning Model to Detect Major Depressive Disorder Utilizing EEG Signals,"
> *IEEE Transactions on Artificial Intelligence*, vol. 5, no. 10, pp. 4938–4947, Oct. 2024.
> DOI: 10.1109/TAI.2024.3394792

**Thesis:** the reported gamma-band superiority (99.60%) is substantially attributable to
evaluation protocol and non-neural high-frequency signal, not cortical gamma.

---

## Install

```bash
pip install numpy scipy scikit-learn pandas matplotlib torch mne
```

CPU is fine. No GPU required.

## Validate the pipeline before touching real data

```bash
python experiments/e1_protocol.py --data synthetic --minutes 0.8 --epochs 25 --skip-loso
```

`make_synthetic()` plants a **known** shortcut: a subject-stable, class-correlated
narrowband component in the gamma range, standing in for EMG / impedance / line-noise
signatures. It also plants a *weak genuine* alpha-band class effect.

Expected output — and this is the acceptance test for the whole codebase:

| Arm | Epoch acc |
|---|---|
| B epoch-random split | ~1.00 |
| C + no overlap | ~1.00 |
| D subject-wise folds | ~0.50 |

If subject-wise does **not** collapse relative to epoch-random, the pipeline is broken.
Fix it before spending a single fold on real recordings.

## Then point it at the real data

```bash
python experiments/e1_protocol.py --data /path/to/husm_edf_dir --epochs 40
```

`load_husm()` expects `.edf` files with `MDD`/`H` and `EC`/`EO` in the filename.
**Verify the channel count is 19 and the order is consistent before trusting anything.**

---

## Two findings already, from the reimplementation alone

### 1. The paper's stated λ = 0.02 collapses the network

Equation (8) of the paper gives λ = 0.02 as a regularisation parameter. Applied
literally as Adam `weight_decay` on the 5-filter architecture, the model degenerates
to a constant output — logit variance 0.000, accuracy pinned to the majority class,
at every learning rate and epoch budget tested.

| weight_decay | train acc | test acc | logit std |
|---|---|---|---|
| 0.02 (as stated) | 0.529 | 0.538 | **0.000** |
| 0.0 | 1.000 | 0.462 | 14.3 |
| 1e-4 (ours) | — | see below | — |

Their λ is evidently a different formulation than decoupled weight decay. This belongs
in the paper as a neutral reproducibility note — not as a criticism, but because anyone
reimplementing from the published description will hit it.

### 2. The 5-filter bottleneck memorises subjects

On synthetic data with a subject-wise split:

| n_filters | subject-wise acc |
|---|---|
| 5 (paper) | 0.462 |
| 16 | 0.756 |

The paper's narrow trunk generalises *worse* across subjects than a wider one — consistent
with it latching onto per-subject signatures rather than a transferable class boundary.
Run this ablation on real data; if it holds, it is a genuine architectural finding and
strengthens the shortcut argument considerably.

---

## Layout

```
eegmdd/
  config.py    every protocol choice as a flag -- E1 is a loop, not a rewrite
  data.py      loading, filterbank, epoching, normalisation, synthetic generator
  splits.py    epoch_random / subject_kfold / loso + a leak assertion
  models.py    Ex1DCNN (faithful to Table I) + Ex1DCNN_DANN (gradient reversal)
  artifact.py  the 5 scalar artifact features -- the headline experiment
  metrics.py   subject-level aggregation, bootstrap CIs, ECE, temperature, McNemar
  train.py     shared CV loop
experiments/
  e1_protocol.py   protocol decomposition table
```

---

## E2 — the shortcut probes (written, validated)

```bash
python experiments/e2_shortcut.py --data synthetic --minutes 1.2 --epoch-sec 5 --n-folds 5
python experiments/e2_shortcut.py --data /path/to/husm_edf --probes P1,P2,P3,P4
```

| Probe | Question | Why it matters |
|---|---|---|
| **P1** subject-ID | can 24 scalars identify *which person* an epoch came from? | if yes, epoch-level splits are meaningless |
| **P2** artifact-only | can 5 scalars + logistic regression match the CNN? | 5 parameters cannot learn a subtle biomarker |
| **P3** band × protocol | does gamma stay top-ranked under subject-wise CV? | tests the paper's central claim directly |
| **P4** topography | is HF discriminability at T3/T4/T5/T6/F7/F8? | temporalis muscle signature |

### The two failure modes are different — and the probes separate them

`make_synthetic(shortcut_mode=...)` plants either one:

| Mode | What it means | epoch-random | LOSO |
|---|---|---|---|
| `class_correlated` | artifact genuinely differs by class (MDD patients more tense during recording) | 0.968 | **0.954** |
| `subject_only` | artifact is pure subject identity, uncorrelated with class | 0.590 | **0.518** |

This distinction is the intellectual core of the paper, so be precise about it:

- **`subject_only` is leakage.** The result evaporates under LOSO. The model learned nothing.
- **`class_correlated` is worse in a way, and more interesting.** The result *survives* LOSO — it
  generalises to new subjects, it would replicate — and it is still not a brain measurement.
  You are classifying jaw tension, not cortex. No amount of stricter cross-validation catches
  this; only P2 and P4 do.

Validated on synthetic data (64 subjects): P1 reaches 62× chance in `class_correlated` mode and
50× chance in `subject_only` mode. **Epochs carry a strong subject fingerprint under both.**

If the real data turns out to be `class_correlated`, do **not** write "their result is wrong."
Write: the effect is real and reproducible, and it is not neural. That is a stronger, more
defensible, and more interesting paper.

## Still to write

- `e0_reproduce.py` — reproduce γ @ 15 s under the paper's protocol as described
- `e3_method.py` — DANN + artifact suppression + calibration, with ablations
- `e4_external.py` — train HUSM → test PRED+CT

## Guardrails baked in

- `assert_no_subject_leak` runs on every non-epoch-random fold. It will raise rather than
  silently produce an inflated number.
- `run_cv` asserts every epoch appeared in exactly one test fold.
- Bootstrap CIs resample **subjects**, not epochs.
- Subject-level metrics are reported alongside epoch-level ones everywhere.
