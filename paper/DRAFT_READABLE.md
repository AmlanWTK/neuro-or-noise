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
low-pass; the split rule alone accounts for 0.091 accuracy; a five-scalar
baseline with no neural content matches an eleven-layer CNN (0.873 vs 0.857,
McNemar p=1.00); and a single uniform third of the band reproduces the full-band
predictions (r=0.99, 98% agreement). We reproduce 0.857 subject-level accuracy,
not 0.9960. The protocol is released as a tool.

## 1. Introduction

A recurring result form in clinical EEG: *model M on band B classifies condition
C with accuracy a, and B is the most effective band.* It appears to localise a
biomarker in frequency. It is also fragile in ways cheap to test and rarely
tested.

Three failure modes recur: (1) the nominal band may exceed what the acquisition
filters actually recorded; (2) accuracy may come from the cross-validation split
rather than the signal; (3) the discriminative information may be non-neural.
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

**Reproducibility note:** the stated λ=0.02 collapses our reimplementation to a
constant output as decoupled weight decay; we use 1e-4. Reported neutrally.

**Report (Table 1):** V1 FAIL (29% of band above 80 Hz edge) · V2 FLAG (0.091) ·
V3 FAIL (0.873 vs 0.857, p=1.00) · V4 FAIL (30–53.3 Hz alone, r=0.99, 98%) ·
V5 PASS (−0.016). **Verdict: not well-posed.**

**V1.** Headers report `HP:0.5Hz LP:80Hz`, identical across groups. 70–100 Hz
gives mean per-bin AUC 0.537, 100–127 Hz gives 0.550 — chance, as expected of
empty spectrum.

**V3.** Baseline 0.873 vs CNN 0.857 (McNemar p=1.00; CIs [0.778,0.952] and
[0.746,0.921]). Stated as a *match*, not a win — with N=63 the smallest
detectable difference is ~0.095 and the gap is 0.016. The same five scalars reach
0.81–0.88 in *every* band (spread 0.070, majority 0.524).

**V4.** Best uniform third 30–53.3 Hz reaches 0.873 vs 0.857, r=0.99, 98%
agreement. A hand-specified 30–45 Hz band (secondary, post-hoc, 25-epoch budget)
gives identical subject-level accuracy (0.8413 both, p=1.00, r=0.979, 93.7%).
Everything above 45 Hz is inert.

**What the signal is.** Aperiodic exponent differs (MDD 2.15, HC 1.32; AUC 0.776)
as does offset (AUC 0.859); two numbers give 0.794±0.084 CV. But removing the
aperiodic component does not remove the difference (0.858→0.841), so a periodic
component contributes too. We do not claim to identify the mechanism — only that
the effect is not a 30–100 Hz phenomenon, not mains-driven, and matched by a
signal-quality baseline.

## 4. Alternative explanations tested and rejected (Table 2)

Subject leakage (Δₚ only 0.091; subject-ID probe 13.4× chance) · temporalis EMG
(topography posterior, >55 Hz at chance) · controls have more mains (raw 50 Hz
AUC 0.568, p=0.36) · different filters (headers identical) · mains drives gamma
(excision costs −0.016) · aperiodic explains all (flattening −0.017).

## 5. Sensitivity and power

**Training budget.** 40→25 epochs leaves overall verdict and V1/V3 unchanged;
V2 rises 0.091→0.114 (crosses threshold — why we report the quantity, not the
label). V4/V5 not rerun at 25 epochs. **[TODO: replace with real 25-epoch run.]**

**Power.** At N=63, McNemar needs ≥6 net subjects to reach p<0.05 (~0.095
accuracy). We avoid model-vs-model claims, report CIs throughout, rest on
epoch-level contrasts and structural findings.

**Thresholds** are reasoned defaults, exposed as parameters. Report the quantity,
not the verdict.

## 6. Discussion

Cheap by design: V1 reads a header, V3/V5 are minutes, V4 is k model fits. We
make no claim about the biology of depression and do not claim [1] is unusual —
the convention it follows is widespread, which is why a mechanical check is worth
having. **[TODO: cite 3–5 papers using epoch-level evaluation.]**

**Limitations.** Single dataset; N=63; the 30–45 Hz mechanism is unresolved
(residual EMG, aperiodic difference, genuine low-gamma all consistent);
thresholds uncalibrated; reimplementation may differ from the original in
unstated details (code + run records released).

## 7. Conclusion

Band-specific EEG classification claims can be checked for well-posedness before
being believed. On a published 99.60% result, four of five checks fail. We
reproduce 0.857. Protocol and run records released.

---

## Figures (specified, not yet built)

- **Fig. 1** — band decomposition bar chart; 80–100 Hz shaded "not recorded". *The money figure.*
- **Fig. 2** — protocol delta, two bars with CIs.
- **Fig. 3** — sub-band agreement scatter, 30–45 vs 30–100 Hz, r annotated.

## References
[1] Anik et al., IEEE TAI 5(10):4938–4947, 2024. [2] Mumtaz et al., Biomed Sig
Proc Control 31:108–115, 2017. [3] Whitham et al. 2007 (EMG >20 Hz). [4]
Muthukumaraswamy 2013. [5] Geirhos et al. 2020 (shortcut learning). [6] Donoghue
et al. 2020 (aperiodic). **[TODO: +3–5 epoch-level-evaluation EEG-MDD papers.]**
