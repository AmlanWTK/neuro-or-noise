# Results log

Append every real-data run here, with the exact command. This file becomes the
paper's results section and its reproducibility appendix.

---

## GATE 1 — E1 protocol decomposition (real HUSM data)

```
python experiments/e1_protocol.py --data "D:\Project\PaperPlan\EEG" --epochs 40 --skip-loso
```

Data as loaded: **119 recordings, 63 subjects (MDD=33, HC=30)**, 19 scalp channels,
1 duplicate dropped, 61 TASK files excluded, 7 subjects missing one condition.

> ⚠ **Config caveat:** this run used `epoch_sec=5.0`, `n_folds=5` — those were hardcoded
> defaults in the script at the time, *not* the paper's configuration. The paper's headline
> is gamma @ **15 s** with **10** folds. Defaults are now fixed; the 15 s / 10-fold rerun is
> the number that belongs in the paper. Everything below is directionally valid but must be
> re-measured at 15 s before publication.

| Arm | Split | Norm | Overlap | Epoch acc | Subject acc | 95% CI |
|---|---|---|---|---|---|---|
| A paper-as-described | subject-wise | global | 1 s | 0.8470 | 0.8095 | [0.71, 0.90] |
| B epoch-random | epoch-random | global | 1 s | **0.9604** | 0.9841 | [0.95, 1.00] |
| C + no overlap | epoch-random | global | none | 0.9551 | 0.9841 | [0.95, 1.00] |
| D subject folds | subject-wise | train-fold | none | **0.8354** | 0.8254 | [0.73, 0.92] |

**Protocol deltas (epoch-level):**

| Transition | Δ |
|---|---|
| A → B (subject-wise → epoch-random) | **+0.1135** |
| B → C (drop the 1 s overlap) | −0.0053 |
| C → D (epoch-random → subject-wise) | **−0.1197** |

### Reading

**1. The split protocol is worth ~12 accuracy points.** C → D is a clean single-factor
contrast: same epochs, same normalisation, only the split changes. 0.9551 → 0.8354.

**2. Epoch overlap contributes almost nothing** (−0.005). This is a genuine negative result
and worth reporting — the intuition that 1 s overlap creates near-duplicate leakage is
*not* borne out here, because at 5 s epochs the overlap is only 20% of the window. Re-test
at 15 s, where 1 s overlap means 93% shared signal between neighbours.

**3. We do not reproduce 99.60%.** Best case under the most generous protocol is 0.9604.
Under subject-wise evaluation, 0.8354. The paper describes subject-wise folds and reports
0.9960 — a ~16-point discrepancy against our closest equivalent (arm A: 0.8470).

**4. Subject-wise accuracy is still far above chance.** Majority class is 33/63 = 0.524;
we get 0.8354. So *something real generalises across subjects.* This is the crux: the
remaining ~84% is either a neural biomarker or a class-correlated artifact, and E1 cannot
tell the difference. **Only E2 can.**

### Gate 1 verdict

Gap = **0.12** → the 5–15 point band. **Proceed, with the artifact evidence (E2) carrying
the paper rather than the leakage story.** The leakage angle alone is too weak to headline:
12 points is real and worth a table, but it does not explain away the result.

The paper's spine is now: *protocol explains ~12 points; of the rest, how much is brain?*

---

## Next

- [ ] **E2 on real data** — decisive. P1/P2/P4 are cheap (no CNN).
- [ ] **E1 rerun at the paper's true config** — `--epoch-sec 15 --n-folds 10`
- [ ] LOSO arm (drop `--skip-loso`) — ~10× slower, run overnight
- [ ] Multi-seed repeats for the arms that reach the paper

---

## E2 — shortcut probes (real data, gamma @ 15 s)

```
python experiments/e2_shortcut.py --data "D:\Project\PaperPlan\EEG" --probes P1,P2,P4
```

| Model | Epoch acc | Subject acc |
|---|---|---|
| Ex-1DCNN, subject-wise (E1 arm D) | 0.8354 | 0.8254 |
| **5 artifact scalars + logistic regression** | **0.8837** | **0.8730** |

Artifact-only accuracy is **invariant to protocol** — 0.8841 epoch-random, 0.8837
subject-wise, 0.8837 LOSO. It does not care whether subjects are held out.

**P1 subject-ID:** 0.2135 vs 0.0159 chance = 13.4x. A real fingerprint, but far
weaker than the synthetic sanity case predicted (60x). Consistent with E1's modest
12-point protocol gap. *The leakage story keeps shrinking.*

**P4 topography:** O1, O2, T5, P3, Pz, P4 — posterior-dominant. Only 1/6 in the
temporalis set. This is a **neck-muscle** distribution (splenius/trapezius), not a
jaw one. Muscle groups are now labelled separately in the code.

---

## E2c — confound checks (2 runs; the second corrected the first)

The first run aggregated per RECORDING and reported `max(auc, 1-auc)`, which hid
direction and was destroyed by heavy tails. Corrected to per-SUBJECT medians with
explicit direction, log-scale effect size and Mann-Whitney p.

### Per-subject feature separation (63 subjects)

| Feature | Direction | AUC | log d | p |
|---|---|---|---|---|
| `zero_cross_rate` | HC>MDD | **0.918** | −2.25 | 1.3e−08 |
| `line_resid_45_55` | HC>MDD | **0.876** | −2.24 | 3.2e−07 |
| `kurtosis` | MDD>HC | 0.773 | +0.69 | 2.1e−04 |
| `hf_power_60_100` | MDD>HC | 0.762 | +0.80 | 3.7e−04 |
| `rms` | HC>MDD | 0.667 | −0.57 | 2.4e−02 |

- **C2 — not a condition effect.** line-resid AUC 0.887 (EC) and 0.889 (EO).
- **C6 — not recording-order drift.** No significant Spearman trend in either group.

### ⚠ C4/C5 — the raw line-noise claim FAILED

| Measure | MDD | HC | AUC | p |
|---|---|---|---|---|
| RAW 50 Hz peak-to-neighbour (subject median) | 1.50 | 7.23 | 0.568 | **0.36** |
| % subjects with a clear 50 Hz peak | 48% | 60% | — | — |

**There is no significant group difference in raw mains contamination.** The
hypothesis that "HC recordings simply have more line noise" is not supported and
must not be written. The medians differ but the distributions interleave; both
groups contain heavily contaminated and clean recordings.

---

## E2d — spectral forensics

```
python experiments/e2d_spectrum.py --data "D:\Project\PaperPlan\EEG"
```

### S1 — EDF headers are IDENTICAL

```
MDD: [62 files] HP:0.5Hz LP:80Hz
HC:  [58 files] HP:0.5Hz LP:80Hz
```

Same acquisition filter settings in both groups. The simplest instrumentation
explanation is ruled out. **But note the LP: 80 Hz.**

### The structural finding: the paper's gamma band is 20 Hz too wide

The recordings are low-passed at **80 Hz**. The paper's gamma band is **30–100 Hz**.
So **29% of the nominal band is filter stopband containing no signal** — confirmed
empirically: 70–100 Hz gives log-ratio −0.01 and mean AUC 0.537, and 100–127 Hz
AUC 0.550. Chance, as expected for empty spectrum.

### S2 — where the groups actually differ

| Band | log10 MDD/HC | mean AUC |
|---|---|---|
| 1–4 Hz | **+0.44** | **0.787** |
| 4–8 Hz | +0.32 | 0.710 |
| 8–12 Hz | +0.09 | 0.597 |
| 12–30 Hz | **+0.41** | **0.776** |
| 30–45 Hz | +0.05 | 0.659 |
| **45–55 Hz** | **−1.46** | 0.669 |
| 55–70 Hz | +0.01 | 0.565 |
| 70–100 Hz | −0.01 | 0.537 |
| 100–127 Hz | −0.01 | 0.550 |

Top individual bins: **2.1–3.8 Hz** and **12.75–13.9 Hz**, AUC 0.82–0.84, MDD>HC.

Two things follow, and both are paper-worthy:

1. **The best-separating frequencies are delta and low-beta, not gamma.** This
   contradicts the paper's band ranking, in which gamma (99.60%) beat delta (91.27%)
   and beta (88.53%).
2. **Inside the gamma band, separation is concentrated at 45–55 Hz** (log-ratio −1.46,
   ~29× more power in HC) — the mains region. Above 55 Hz, AUC is 0.54–0.57, i.e.
   chance. *There is no evidence of a neural gamma effect anywhere above the mains
   band.*

### S3 — spectral edge

MDD median 26.9 Hz, HC 35.2 Hz, AUC 0.611, **p=0.13** — not significant, though HC's
upper quartile (50.1 Hz) reflects the subgroup with strong mains contamination.

---

## Where the paper stands

Supported by evidence in hand:

1. 99.60% is not reproducible: 0.960 epoch-random, 0.835 subject-wise.
2. Split protocol accounts for ~12 points.
3. A 5-feature signal-quality baseline with no neural content **beats** the CNN
   (0.884 vs 0.835), and is protocol-invariant.
4. The nominal gamma band exceeds the recordings' 80 Hz low-pass by 20 Hz.
5. Within gamma, discrimination sits at the mains band; above 55 Hz it is chance.
6. Delta and low-beta separate the groups better than gamma does.
7. Acquisition filter settings are identical across groups (headers), so this is
   not a trivial instrumentation artifact.

Explicitly NOT supported — do not write these:

- "HC recordings have more line noise" (raw peak test: p=0.36)
- "Gamma superiority is muscle artifact" (no temporalis topography; above-55 Hz
  discrimination is at chance)
- Leakage as the primary explanation (only 12 points; subject-ID probe just 13x chance)

## Next

- [ ] **E2 P3 band ablation** with the new bands — the decisive test
- [ ] E1 rerun at the paper's config (`--epoch-sec 15 --n-folds 10`)
- [ ] LOSO arm overnight
- [ ] Multi-seed repeats
