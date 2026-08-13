# Is the Band the Biomarker? — readable draft

*This is the paper as prose, so you can judge the writing and argument without
compiling LaTeX. It mirrors `icassp2027.tex` exactly. Numbers are traceable to
run records; unresolved items are marked **[TODO]**.*

---

## Title
**Is the Band the Biomarker? A Validity Protocol for Band-Specific EEG Classification Claims**

## Abstract

Resting-state EEG studies routinely report that one frequency band is the
strongest discriminator for a clinical label. Such claims are seldom checked for
well-posedness before modelling begins. We propose **BandCheck**: five
inexpensive tests that ask whether a band-specific claim can be true at all —
passband support, the accuracy attributable to the cross-validation split alone,
whether a five-parameter signal-quality baseline matches the model, whether a
narrow sub-band reproduces the whole result, and whether excising a suspected
contaminant changes anything. Applied to a published result reporting 99.60%
accuracy for major depressive disorder on the 30–100 Hz band, four of five checks
fail: the nominal band extends 20 Hz beyond the recordings' 80 Hz acquisition
low-pass; the split rule alone accounts for 0.106±0.013 accuracy over three
seeds; a five-scalar baseline with no neural content matches an eleven-layer CNN
(0.873 vs 0.847±0.009, McNemar p≥0.625); and a single uniform third of the band
reproduces the full-band predictions (r=0.98±0.01, 92–98% agreement). We
reproduce 0.847±0.009 subject-level accuracy, not 0.9960. The protocol is
released as a tool.

## 1. Introduction

A recurring result form in clinical EEG: *model M on band B classifies condition
C with accuracy a, and B is the most effective band.* It appears to localise a
biomarker in frequency. It is also fragile in ways cheap to test and rarely
tested.

Three failure modes recur: (1) the nominal band may exceed what the acquisition
filters actually recorded; (2) accuracy may come from the cross-validation split
rather than the signal — not hypothetical and not new: Saeb et al. (2017) found
median error 5.60% record-wise vs 13.00% subject-wise across 62 clinical studies,
and reproducing published EEG architectures under a subject-wise split drops
Alzheimer's classification from 99.8% to 53.0% (Brookshire et al. 2024); it is
one instance of leakage now documented in 294 papers across 17 fields (Kapoor &
Narayanan 2023); (3) the discriminative information may be non-neural.
None needs a replication study to detect — each is a short computation runnable
before modelling. We package them as **BandCheck** and demonstrate on a recent
high-profile result.

**Contributions:** (i) a five-check well-posedness protocol with released code;
(ii) an application in which four of five checks fail on a published 99.60%
result; (iii) a record of six alternative explanations tested and rejected.

The protocol tests *well-posedness, not truth*. Passing all five does not make a
claim correct; failing one means it is not yet meaningful enough to be either.

## 2. The BandCheck protocol

- **V1 Passband support.** Estimate the usable spectral edge from the file
  header's filter settings and from where the median PSD hits the noise floor.
  Dead fraction φ = portion of the band above that edge. Flag φ>0.02, fail φ≥0.15.
- **V2 Protocol delta.** Fit M twice, changing only the split (epoch-random vs
  subject-wise). The difference Δₚ is accuracy from the protocol. Flag ≥0.03,
  fail ≥0.10.
- **V3 Artifact control.** Logistic regression on five signal-quality scalars
  (relative 60–100 Hz power, relative 45–55 Hz power, kurtosis, zero-crossing
  rate, RMS). If it matches M under identical subject-independent evaluation
  (McNemar on paired subject decisions), there is no evidence M uses neural
  information.
- **V4 Sub-band localisation.** Partition B into k=3 uniform sub-bands; fit each.
  A narrow sub-band that reproduces the full-band predictions means the claim is
  mis-specified in width. Uniform partition is deliberate — not tuned to the answer.
- **V5 Excision control.** Band-stop a suspected contaminant and refit. Unchanged
  accuracy means that contaminant is not the mechanism. Usually returns a null;
  that is its value.

## 3. Case study

**Target.** Anik et al. [1] report 99.60% for MDD vs HC using an 11-layer 1-D CNN
on 30–100 Hz, 15 s epochs, tenfold CV, concluding gamma is the most effective
band. Data: public HUSM recordings [2], 19 electrodes, 256 Hz, eyes-closed/open.

**Data decisions (reported because they change the denominator):** a duplicated
recording; one MDD subject with only task data; seven subjects missing a
condition. We use the 63 resting subjects (33 MDD, 30 HC; 119 recordings) vs the
34/30 stated in [1].

**Reproducibility note:** applied literally as decoupled weight decay, the
stated λ=0.02 reduces our reimplementation to near chance — epoch-level 0.514
epoch-random and 0.548 subject-wise, against 0.947 and 0.856 at λ=1e-4, with
Δₚ=−0.034, **a value that would pass V2**. We use 1e-4 throughout and report
this neutrally: the published λ is evidently a different formulation, not an
error. (V2's definition now carries the corollary: Δₚ must be read alongside the
absolute accuracies, because a model that learned nothing has no protocol delta
either.)

**Report (Table 1):** V1 FAIL (29% of band above the 80 Hz edge) ·
V2 FAIL (0.106±0.013, 2/3 seeds exceed threshold) ·
V3 FAIL (0.873 vs 0.847±0.009, McNemar p≥0.625) ·
V4 FAIL (30–53.3 Hz alone in 4/4 runs, r=0.976–0.986, 92–98%) ·
V5 PASS† (−0.005±0.033, sign flips across seeds).
**Verdict: not well-posed, in all four runs.**

**V1.** Headers report `HP:0.5Hz LP:80Hz`, identical across groups. 70–100 Hz
gives mean per-bin AUC 0.537, 100–127 Hz gives 0.550 — chance, as expected of
empty spectrum. The median PSD in fact hits its noise floor near 56 Hz, below
the nominal low-pass, so the empirical dead fraction is 0.63; we report the
header-based 0.29 as the conservative figure.

**V3.** Baseline 0.873 vs CNN 0.847±0.009 (McNemar p≥0.625 in every run; CIs
[0.778,0.952] and [0.746,0.921] at seed 0). Stated as a *match*, not a win — with N=63 the smallest
detectable difference is ~0.095 and the gap is 0.016. The same five scalars reach
0.81–0.88 in *every* band (spread 0.070, majority 0.524).

**V4.** Best uniform third is 30–53.3 Hz in all four runs: 0.873±0.016 vs
0.847±0.009 full band, r=0.980±0.005, 92–98% decision agreement. The upper two
thirds are not: 53.3–76.7 Hz gives 0.714±0.028, and 76.7–100 Hz gives
0.540±0.000 against a 0.524 majority baseline, correlating with the full-band
predictions at r=0.15±0.14. A hand-specified 30–45 Hz band (secondary, post-hoc,
25-epoch budget) gives identical subject-level accuracy (0.8413 both, p=1.00,
r=0.979, 93.7%). Everything above 45 Hz is inert.

**What the signal is.** Aperiodic exponent differs (MDD 2.15, HC 1.32; AUC 0.776)
as does offset (AUC 0.859); two numbers give 0.794±0.084 CV. But removing the
aperiodic component does not remove the difference (0.858→0.841), so a periodic
component contributes too. We do not claim to identify the mechanism — only that
the effect is not a 30–100 Hz phenomenon, not mains-driven, and matched by a
signal-quality baseline.

## 4. Alternative explanations tested and rejected (Table 2)

Subject leakage (Δₚ only 0.106; subject-ID probe 13.4× chance) · temporalis EMG
(topography posterior, >55 Hz at chance) · controls have more mains (raw 50 Hz
AUC 0.568, p=0.36) · different filters (headers identical) · mains drives gamma
(excision costs −0.016) · aperiodic explains all (flattening −0.017).

## 5. Sensitivity and power

**Seeds and budget (real runs, four of them).** Three seeds at 40 epochs plus
one at 25. The verdict is *not well-posed* in all four, and V1/V3/V4 are
identical in all four. Two checks have seed-dependent *labels*: V2 is
0.106±0.013, straddling the 0.10 threshold (2 fail, 1 flags), and V5 is
−0.005±0.033 with its sign flipping. Budget variation is smaller than seed
variation — the 25-epoch V2 delta (0.114) sits inside the 40-epoch range
[0.091, 0.116]. This is the strongest argument for the paper's own
recommendation: **report the quantity, not the verdict**.

**Power.** At N=63, McNemar needs ≥6 net subjects to reach p<0.05 (~0.095
accuracy). We avoid model-vs-model claims, report CIs throughout, rest on
epoch-level contrasts and structural findings.

**Thresholds** are reasoned defaults, exposed as parameters. Report the quantity,
not the verdict.

## 6. Discussion

Cheap by design: V1 reads a header, V3/V5 are minutes, V4 is k model fits. We
make no claim about the biology of depression and do not claim [1] is unusual —
**it is not**. Brookshire et al. (2024) surveyed 63 deep-learning EEG papers
published since 2018, depression among the conditions: 61.9% split train/test at
the segment level, 6.3% did not say, and only 27.0% split by subject. That
epoch-level evaluation is the field's default is exactly why a mechanical check
is worth having — a reviewer cannot single out one paper for what most papers
do, but a protocol applies to all of them.

**The unit of evaluation matters independently of the split rule.** Ke et al.
(2021) report 99±0.08% on this same dataset, from counts consistent with a
subject-disjoint partition — but that is an *epoch-level* accuracy over 3,728
four-second segments from a single, non-rotated holdout of 13 subjects, with no
per-subject aggregation. A fixed 13-subject test set cannot express
between-subject variability whatever the ±0.08% ranges over, so the number is
not comparable to a subject-level accuracy over 63 subjects. Their stated reason
for windowing — "overfitting would occur when performing classification based on
subjects" — is candid, and representative of why the convention persists: at
N≈60 the subject is a scarce unit. Reporting Δₚ and subject-level accuracy does
not solve that scarcity; it makes it visible.

**Limitations.** Single dataset; N=63; the 30–45 Hz mechanism is unresolved
(residual EMG, aperiodic difference, genuine low-gamma all consistent);
thresholds uncalibrated; reimplementation may differ from the original in
unstated details (code + run records released).

## 7. Conclusion

Band-specific EEG classification claims can be checked for well-posedness before
being believed. On a published 99.60% result, four of five checks fail: more
than a quarter of the nominal band was never recorded, the split rule accounts
for eleven accuracy points, a five-parameter signal-quality baseline matches an
eleven-layer network, and a single uniform third of the band reproduces the
full-band predictions. We reproduce 0.847±0.009. Protocol and run records
released.

---

## Figures — all three built, all generated from run records

| | File | Built by | Placed in |
|---|---|---|---|
| **Fig. 1** | `figs/fig1_band_decomposition.pdf` | `make_fig1.py` | §V1 |
| **Fig. 2** | `figs/fig2_protocol_and_baseline.pdf` | `make_fig2.py` | §V3 |
| **Fig. 3** | `figs/fig3_subband_agreement.pdf` | `make_fig3.py` | §V4 |

Fig. 3 is two panels: (a) the V4 uniform-third result across three 40-epoch
seeds — accuracy and per-subject decision agreement for each third, with r
printed above each pair; (b) the per-subject scatter for the hand-specified
30–45 Hz band at the 25-epoch budget, 63 points, shaded disagreement quadrants,
the four disagreeing subjects ringed.

Every script reads `results/runs/*/result.json` and prints the numbers it drew,
so no value in a figure is typed by hand. Run them from the repo root:

```bash
python paper/make_fig3.py results/runs
```

## References
[1] Anik et al., IEEE TAI 5(10):4938–4947, 2024. [2] Mumtaz et al., Biomed Sig
Proc Control 31:108–115, 2017. [3] Whitham et al. 2007 (EMG >20 Hz). [4]
Muthukumaraswamy 2013. [5] Geirhos et al. 2020 (shortcut learning). [6] Donoghue
et al. 2020 (aperiodic). [7] Brookshire et al., *Front. Neurosci.* 18:1373515,
2024 (EEG leakage audit). [8] Saeb et al., *GigaScience* 6(5):gix019, 2017
(record- vs subject-wise CV). [9] Kapoor & Narayanan, *Patterns* 4(9):100804,
2023 (leakage across fields). [9] Ke et al., *Front. Comput. Neurosci.*
15:773147, 2021 (99% epoch-level on this dataset).
