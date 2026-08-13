# Claims audit — every assertion in the draft, mapped to evidence

Rule: no claim ships without a run record behind it. This table is the check.

Status key — **VERIFIED**: measured, run record exists. **PARTIAL**: measured,
but not under the exact conditions claimed. **UNTESTED**: asserted, no
measurement. **WRONG**: measurement contradicts the text.

---

## Abstract & headline claims

| # | Claim in draft | Evidence | Run | Status |
|---|---|---|---|---|
| A1 | 29% of band above 80 Hz low-pass | EDF headers `LP:80Hz`, 120 files; 70–100 Hz AUC 0.537 | `...083449_bandcheck`, `...104431_e2d` | **VERIFIED** |
| A2 | Split rule accounts for 0.091 | V2 | `...083449_bandcheck` | **VERIFIED** |
| A3 | 5 scalars match CNN, 0.873 vs 0.857, p=1.00 | V3 | `...083449_bandcheck` | **VERIFIED** |
| A4 | Uniform third reproduces full band, r=0.99, 98% | V4 | `...083449_bandcheck` | **VERIFIED** |
| A5 | We reproduce 0.857, not 0.9960 | V3 model arm | `...083449_bandcheck` | **VERIFIED** |
| A6 | "checks can be run in minutes" | artifact_lr path ~5 min; **CNN path took 8644 s** | `...083449_bandcheck` | **WRONG** — overclaim |

## Section III — case study

| # | Claim | Evidence | Status |
|---|---|---|---|
| B1 | 63 subjects (33 MDD, 30 HC), 119 recordings | loader output, every run | **VERIFIED** |
| B2 | Duplicate file; one MDD subject task-only; 7 missing a condition | `inspect_data` + loader | **VERIFIED** |
| B3 | λ=0.02 collapses the network to constant output | weight-decay sweep, logit std 0.000 | **VERIFIED** (container run, no run record) → *rerun on their machine to log it* |
| B4 | Headers identical across groups | `...104431_e2d` S1 | **VERIFIED** |
| B5 | Hand-picked 30–45 Hz: 0.8413 both, p=1.00, r=0.979, 93.7% | compare_runs | `...225345_e2` vs `...215110_e2` | **VERIFIED** but at **max_epochs=25**, not 40 → *label it as such* |
| B6 | 5 scalars reach 0.81–0.88 in every band, spread 0.070 | P3 artifact_lr, 7 bands | `...110230_e2` | **VERIFIED** |
| B7 | Aperiodic exponent 2.15 vs 1.32, AUC 0.776; offset AUC 0.859; two params 0.794±0.084 | `...115241_e2e` | **VERIFIED** |
| B8 | Flattening changes CV by −0.017 | `...115241_e2e` A3 | **VERIFIED** |

## Section IV — rejected hypotheses

| # | Claim | Run | Status |
|---|---|---|---|
| C1 | Subject-ID probe 13.4× chance | `...110136_e2`/E2 P1 | **VERIFIED** |
| C2 | Topography posterior, not temporal | E2 P4 | **VERIFIED** |
| C3 | Raw 50 Hz AUC 0.568, p=0.36 | `...103927_e2c` | **VERIFIED** |
| C4 | Headers identical | `...104431_e2d` | **VERIFIED** |
| C5 | Excising 45–55 Hz costs −0.016 | V5 | **VERIFIED** |
| C6 | Aperiodic doesn't explain it | `...115241_e2e` | **VERIFIED** |

## Section V — sensitivity and power

| # | Claim | Status |
|---|---|---|
| D1 | **"All five verdicts are unchanged" at 25 vs 40 epochs** | **WRONG** |
| D2 | Smallest detectable difference ≈ 0.095 at N=63 | **VERIFIED** (analytic) |
| D3 | Thresholds are uncalibrated defaults | **VERIFIED** (stated honestly) |

### D1 in detail — the error

| Check | 40 epochs | 25 epochs | |
|---|---|---|---|
| V1 | FAIL | FAIL | same (budget-independent) |
| V2 | FLAG (0.091) | **FAIL (0.114)** | **flips** |
| V3 | FAIL (p=1.00) | FAIL (p=0.625) | same |
| V4 | FAIL | **?** | no comparable run — the 25-epoch number used a *hand-picked* 30–45 Hz band, not the uniform-third protocol |
| V5 | PASS | **?** | no comparable run — P3 reported epoch-level accuracy, V5 uses subject-level |

**What is true:** the overall verdict (NOT WELL-POSED) is unchanged, and V1/V3
are unchanged. **What is not true:** that all five verdicts are unchanged.

**Fix, two options.**

1. *Cheap and honest (no compute).* Rewrite as: "Reducing the budget to 25
   epochs leaves the overall verdict and the V1/V3 outcomes unchanged; the V2
   quantity rises from 0.091 to 0.114, crossing our nominal threshold, which
   illustrates why we recommend reporting the quantity rather than the label.
   V4 and V5 were not rerun at the reduced budget."
2. *Better (~1.5 h).* Actually run BandCheck at `--max-epochs 25` and report a
   real, apples-to-apples sensitivity table.

Option 2 is worth it. It is one unattended run and it turns a caveat into a
table — and a genuine sensitivity analysis is exactly the kind of thing that
distinguishes a protocol paper from a checklist.

## Untested but assumed

| # | Assumption | Risk | Test |
|---|---|---|---|
| E1 | **Seed stability.** Every number is seed 0. | A reviewer will ask. If seeds move V2 by ±0.03 the FLAG/FAIL boundary is meaningless. | 2 more BandCheck runs, `--seed 1`, `--seed 2` |
| E2 | **"The convention is widespread."** | Load-bearing for fairness of framing. | Literature search, 3–5 citations |
| E3 | **Our reimplementation is faithful.** | Cannot be fully closed without the original code. | Already stated in limitations; consider emailing the authors |

---

## Required before submission

```bash
# 1. real sensitivity analysis (~1.5 h)  -- replaces the WRONG claim D1
python experiments/bandcheck_run.py --data "D:\Project\PaperPlan\EEG" \
    --band gamma --model ex1dcnn --header-lp 80 --max-epochs 25

# 2. seed stability (~2 x 2.4 h, run overnight) -- closes E1
python experiments/bandcheck_run.py --data "D:\Project\PaperPlan\EEG" \
    --band gamma --model ex1dcnn --header-lp 80 --seed 1
python experiments/bandcheck_run.py --data "D:\Project\PaperPlan\EEG" \
    --band gamma --model ex1dcnn --header-lp 80 --seed 2

# 3. log the lambda finding on your machine (~10 min) -- closes B3
```

Then: fix A6 ("minutes" → state both paths), fix D1, label B5 as 25-epoch.
