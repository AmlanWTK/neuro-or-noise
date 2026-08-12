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

---

## E2 P3 — band × protocol ablation (artifact_lr, subject-wise)

| Band | Epoch-random | Subject-wise |
|---|---|---|
| gamma 30–100 | 0.8841 | 0.8837 |
| gamma_usable 30–80 | 0.8850 | 0.8837 |
| line_only 45–55 | 0.8709 | 0.8632 |
| **gamma_noline 55–80** | 0.8551 | **0.8512** |
| delta 0.5–4 | 0.8427 | 0.8422 |
| sub45 0.5–45 | 0.8585 | 0.8341 |
| beta 12–30 | 0.8487 | 0.8140 |

Spread across seven bands: **0.070**. Majority baseline 0.524. Removing the mains
region costs only **0.033**.

**The mains hypothesis is dead.** The five scalars work everywhere, so the signal is
not localised to any band. (Note: this ran `artifact_lr`, not the CNN.)

---

## E2e — aperiodic decomposition ⭐ **THE DECISIVE RESULT**

```
python experiments/e2e_aperiodic.py --data "D:\Project\PaperPlan\EEG"
```

### A1 — the aperiodic background differs strongly

| Parameter | MDD | HC | AUC | p |
|---|---|---|---|---|
| aperiodic exponent (2–45 Hz) | +2.152 | +1.315 | 0.776 | 1.8e−04 |
| offset (broadband power) | −9.221 | −10.236 | **0.859** | 1.1e−06 |

**Two numbers**, cross-validated at subject level: **0.794 ± 0.084** (baseline 0.524).
MDD spectra are markedly steeper and higher-powered.

### A2 — partial

`line_resid_45_55` is largely a re-measurement of the exponent (rho = −0.688,
p = 5e−10). `hf_power_60_100` is **not** (rho = −0.117, p = 0.36).

### A3 — flattening does NOT remove the difference

| Band | Raw AUC | Flattened AUC | Change |
|---|---|---|---|
| delta | 0.769 | 0.743 | −0.025 |
| theta | 0.542 | 0.824 | +0.282 |
| alpha | 0.553 | 0.748 | +0.196 |
| **beta 12–30** | 0.790 | **0.919** | +0.129 |
| gamma_low 30–45 | 0.516 | 0.622 | +0.106 |
| line 45–55 | 0.717 | 0.747 | +0.030 |
| **gamma_hi 55–80** | 0.593 | **0.529** | −0.064 |

All 7 bands, 5-fold subject CV: raw 0.858 ± 0.094 → flattened 0.841 ± 0.085.

### What this means — the hypothesis was wrong, and the refutation is the finding

The aperiodic slope does **not** explain the group difference: removing it leaves
accuracy essentially unchanged, and *sharpens* several bands. So there is a genuine
**periodic (oscillatory)** difference underneath.

And it has a clear location:

- **Beta (12–30 Hz) is the strongest periodic discriminator, AUC 0.919 after
  flattening.** Theta 0.824, alpha 0.748, delta 0.743.
- **Gamma above the mains region (55–80 Hz) is at chance after flattening: 0.529.**
- Gamma 30–45 Hz is weak: 0.622.

**There is no gamma biomarker in this dataset.** What separates the groups is
(a) a broadband aperiodic difference — steeper, higher-powered spectra in MDD — and
(b) genuine periodic differences concentrated in **beta**, with theta and alpha
contributing. The paper's gamma band picks this up only indirectly, via broadband
properties any band can capture, plus residual mains at 45–55 Hz.

---

## THE PAPER (evidence-backed, as of E2e)

**Claim:** the reported gamma-band MDD biomarker does not survive scrutiny. The
separable signal is broadband-aperiodic plus beta-band periodic; gamma above the
mains region carries no group information.

Supporting results, all in hand:

1. **99.60% is not reproducible.** 0.960 epoch-random, 0.835 subject-wise.
2. **Protocol accounts for ~12 points** (0.955 → 0.835, single-factor contrast).
3. **A 5-scalar signal-quality baseline beats the CNN** (0.884 vs 0.835),
   protocol-invariant, and reaches 0.81–0.88 in *every* band.
4. **The nominal gamma band exceeds the recordings' 80 Hz low-pass by 20 Hz** —
   29% of it is empty stopband (EDF headers: `HP:0.5Hz LP:80Hz`, identical in both
   groups).
5. **Gamma 55–80 Hz is at chance** once the aperiodic background is removed (0.529).
6. **Beta is the real periodic marker** (0.919), not gamma — inverting the paper's
   band ranking.
7. **Two aperiodic parameters alone reach 0.794** subject-level CV.

Hypotheses tested and REJECTED (each stated, tested, and killed by the data —
report these, they are part of the contribution):

| Hypothesis | Killed by |
|---|---|
| Subject leakage explains it | only 12 pts; subject-ID probe 13.4× chance |
| Muscle (temporalis) artifact | posterior topography; >55 Hz at chance |
| HC recordings have more mains | raw 50 Hz peak test: AUC 0.568, **p=0.36** |
| Different acquisition settings | EDF headers identical |
| Mains region drives gamma | removing 45–55 Hz costs only 0.033 |
| Aperiodic slope explains all | flattening changes CV by −0.017 |

## Next

- [ ] **CNN on `gamma_noline`** — does the paper's own model collapse at 55–80 Hz?
      `--probes P3 --p3-model ex1dcnn --bands gamma,gamma_noline,beta` (slow, overnight)
- [ ] E1 rerun at the paper's config (`--epoch-sec 15 --n-folds 10`)
- [ ] Multi-seed repeats for every headline number
- [ ] LOSO arm

---

## E2 P3 — Ex-1DCNN (the paper's own model), by band

Three separate runs, each its own run dir. `--probes P3 --p3-model ex1dcnn`.

| Band | Epoch-random | Subject-wise | Run | Time |
|---|---|---|---|---|
| gamma 30–100 | 0.9436 | **0.8294** | `20260809-125155_e2` | 2407 s |
| gamma_noline 55–80 | 0.7366 | **0.6845** | `20260809-120153_e2` | 1269 s |
| beta 12–30 | — | — | **`20260809-122725_e2` DIED** | — |

### The headline comparison

| Model | gamma 30–100 | 55–80 Hz | Drop |
|---|---|---|---|
| **Ex-1DCNN (paper's)** | 0.8294 | **0.6845** | **−0.145** |
| 5 artifact scalars | 0.8837 | 0.8512 | −0.033 |

Majority baseline 0.524.

Restricted to 55–80 Hz, the paper's own architecture falls from 0.829 to **0.685** —
it loses **4.5× more** than the linear probe does. The deep model's gamma performance
depends heavily on the lower part of the band; the linear probe, which reads
broadband spectral shape, barely notices.

This lines up exactly with E2e A3: at 55–80 Hz the *periodic* signal is at chance
(flattened AUC 0.529), so all that remains there is broadband amplitude — enough for
0.685, nowhere near 0.829.

The gamma epoch-random vs subject-wise gap (0.9436 → 0.8294 = **0.114**) independently
reproduces E1's 0.12 protocol effect at the paper's own 15 s / 10-fold setting.

### ⚠ Caveat that must be fixed before publication

`gamma_noline` is 55–80 Hz, so it removes the mains region **and** 30–45 Hz. The
0.145 drop therefore cannot be attributed to mains alone. Added `gamma_bs`
(30–100 with 45–55 excised via band-stop) and `gamma_usable_bs` (30–80 likewise) as
the clean controls.

### ⚠ One run died

`20260809-122725_e2` (beta, CNN) has a 0-byte console.log and no meta.json, so the
process was hard-killed — sleep, closed terminal, or OOM — rather than raising. The
runlog cannot record what it never saw. **Beta with the CNN is still missing**, and
it is the band E2e says matters most (flattened AUC 0.919).

## Next

- [ ] **beta with the CNN** — rerun the one that died
- [ ] **`gamma_bs`** — clean mains-only ablation, keeps 30–45 Hz
- [ ] E1 at the paper's config (`--epoch-sec 15 --n-folds 10`)
- [ ] Multi-seed repeats for every headline number

---

## E2 P3 — Ex-1DCNN, complete band table

| Band | Epoch-random | Subject-wise | Run |
|---|---|---|---|
| gamma 30–100 | 0.9436 | **0.8294** | `20260809-125155_e2` |
| **gamma_bs** (30–100, 45–55 excised) | 0.9423 | **0.8290** | `20260812-183921_e2` |
| gamma_noline 55–80 | 0.7366 | 0.6845 | `20260809-120153_e2` |
| beta 12–30 | 0.7828 | 0.6776 | `20260812-152905_e2` |

### The mains region contributes NOTHING to the CNN

`gamma_bs` keeps 30–45 and 55–100 and excises only 45–55. Subject-wise:
**0.8290 vs 0.8294 — a difference of 0.0004.**

So the earlier 0.145 drop for `gamma_noline` was **entirely** the loss of 30–45 Hz,
not the mains region. With the clean control in hand, the mains explanation is
dead for the CNN exactly as it was for the linear probe. Report it as a clean
negative result: *the 50 Hz region carries none of the model's gamma performance.*

### Beta underperforms gamma in the CNN — and this needs care

CNN beta 0.6776 vs CNN gamma 0.8294. That appears to contradict E2e, where
flattened beta had the highest AUC (0.919).

**It does not, because those numbers are not comparable.** E2e's 0.919 is a
descriptive AUC computed on subject-averaged flattened band power across all 63
subjects with no cross-validation — optimistically biased. The CNN's 0.6776 is
cross-validated subject-wise accuracy on raw time series. Comparing them directly
is a category error, and the paper must not do it.

Corrected reading: beta shows the strongest *spectral* group difference; it does
not follow that a time-series CNN restricted to beta will classify better.

### ⚠ Is "the linear probe beats the CNN" actually significant?

artifact_lr 0.8837 vs CNN 0.8294 on gamma = **0.0543 = 3.4 subjects** out of 63.
That may well be noise. **This claim cannot be made until a paired test is run.**

P3 now persists subject-level predictions, and `experiments/compare_runs.py` runs
McNemar plus bootstrap CIs on any two runs. The runs completed so far predate this,
so the gamma cells need one rerun each to produce comparable predictions.

## Where the paper stands now

Robustly supported:

1. **99.60% does not reproduce.** 0.8294 subject-wise at the paper's own config
   (gamma, 15 s, 10 folds).
2. **Protocol accounts for 0.114** (0.9436 → 0.8294), measured at the paper's config.
3. **Band choice barely matters.** The same five scalars reach 0.81–0.88 across seven
   bands (spread 0.070) — undercutting "gamma is the best band" directly.
4. **The nominal gamma band is 20 Hz wider than the recorded signal** (LP 80 Hz).
5. **The mains region contributes nothing** — CNN 0.8290 vs 0.8294 with 45–55 excised.
6. Two aperiodic parameters alone reach 0.794 subject-level CV.

Now requiring a paired test before it can be stated:

- "A five-parameter linear model beats the CNN" (0.884 vs 0.829, n=63)

## Next

- [ ] **rerun gamma for both models** with prediction saving, then `compare_runs.py`
- [ ] **`gamma_low` 30–45 with the CNN** — locate where the gamma result actually lives
- [ ] multi-seed repeats for every headline number
- [ ] E1 at the paper's config
