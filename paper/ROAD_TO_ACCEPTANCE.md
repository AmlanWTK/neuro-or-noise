# Road to acceptance — the single plan

This supersedes the scattered "Next" lists. One prioritised roadmap, tiered by
how much each item moves the odds. 34 days to the 16 Sep deadline; freeze results
~6 Sep. Honest framing throughout: nothing here *guarantees* acceptance — these
are the levers that actually move it, in order.

---

## Where we stand

A complete first draft exists, every number traceable to a run record. The
science is done and it is sound. The paper's fate turns on two things: **venue
fit** (is a validity protocol a signal-processing contribution?) and **not
overclaiming** (the discipline that has already caught 5 of my errors).

Realistic read: solid on rigour, genuinely uncertain on ICASSP venue fit. If
rejected, it will be on scope, not soundness — and the same manuscript transfers
to EMBC 2027 or *J. Neural Eng.* with little change.

---

## TIER 1 — must do, or the paper is not submittable

These close known holes. All are cheap.

1. **Real 25-epoch sensitivity run** (~1.5 h, unattended). Replaces the
   retracted "all verdicts unchanged" claim with a true apples-to-apples table.
   `bandcheck_run.py ... --max-epochs 25`
2. **Seed stability, seeds 1 and 2** (~2.4 h each, overnight). If V2 moves ±0.03
   across seeds the FLAG/FAIL line is noise — a reviewer *will* ask. Must know.
   `bandcheck_run.py ... --seed 1` / `--seed 2`
3. **3–5 citations of EEG-MDD papers using epoch-level evaluation.** Load-bearing
   for the "convention is widespread, not specific to [1]" framing. Without them
   the fairness argument is an assertion. Half a day of literature search.
4. **Authors, affiliation, public repo URL.**
5. **Confirm ICASSP 2027 anonymity policy** from the author kit.

## TIER 2 — strongly moves the odds

6. **The three figures.** Fig. 1 (band decomposition, 80–100 Hz shaded
   "not recorded") is the single most persuasive object in the paper — a reviewer
   should grasp the whole thesis from it in five seconds. Data already in the run
   JSONs; I can build all three.
7. **Log the λ=0.02 finding on your machine** (~10 min) so it has a run record,
   not just a claim.
8. **A colleague read by ~6 Sep**, 48-hour window. An outside reader catches what
   we cannot.

## TIER 3 — raises quality if time allows

9. **Second dataset (MODMA/TDBRAIN).** Converts "one dataset's quirk" into a claim
   about the field — the strongest possible upgrade. *Cut for time-risk earlier;*
   revisit only if Tiers 1–2 finish before 1 Sep. Needs MODMA access applied for
   immediately if pursued.
10. **Finer V4 sweep** (`--n-sub 5`) as a secondary localisation result.
11. **Calibrate one threshold** empirically instead of by reason, to blunt the
    "arbitrary cut-offs" objection.

## What NOT to do

- Do not add more seeds beyond 3, more ablations at N=63, or chase significance
  the sample size cannot support.
- Do not upgrade "match" to "beat" (V3 is p=1.00 — it does not survive).
- Do not add a mechanism claim for the 30–45 Hz effect (4 hypotheses already
  died; a 5th at writing time is how papers get retracted).
- Do not soften the "protocol, not people" framing.

---

## Suggested sequence

| When | Do |
|---|---|
| Tonight | kick off the 3 Tier-1 runs (25-epoch + 2 seeds), overnight |
| Day 1–2 | literature search for the 5 citations; I build Fig. 1 |
| Day 3 | fold real sensitivity + seed tables into the draft; Figs 2–3 |
| Day 4–5 | your full read-through, mark every disagreement |
| ~6 Sep | send to a colleague |
| 7–14 Sep | revise |
| **15 Sep** | submit (a day early — portals congest on deadline day) |

---

## The one recurring instruction

Treat any claim without a run ID behind it as a hypothesis. That rule has caught
five of my errors in this project. It is the reason the paper is trustworthy, and
it is what will get it through review.
