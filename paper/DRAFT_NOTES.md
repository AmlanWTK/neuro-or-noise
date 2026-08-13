# Draft notes — what is done, what you must do

`icassp2027.tex` is a complete first draft. Every number in it is traceable to a
run record. Below is what still needs your hand.

## Blocking TODOs

| # | Item | Why it matters |
|---|---|---|
| 1 | **Authors + affiliation** | — |
| 2 | **Confirm ICASSP 2027 anonymity policy** | Historically ICASSP is *not* double-blind. If 2027 changes that, the framing around `\cite{anik2024}` needs no change (we cite normally either way), but the author block does. Check the author kit. |
| 3 | **3–5 more citations of EEG-MDD papers using epoch-level evaluation** | **Load-bearing.** The paper's fairness rests on "this convention is widespread, not specific to [1]". Without those citations that sentence is an assertion, and a reviewer who reads it as an attack on one group will mark the paper down. Find them before anything else. |
| 4 | **Repo URL** | Make the repo public before submission. |
| 5 | **Figures** | Currently none. Three are specified below. |

## Figures to make

**Fig. 1 — Band decomposition (the money figure).** Horizontal bars, subject-level
accuracy per sub-band, majority baseline as a vertical line. Bands: full gamma
30–100, 30–45, 45–55, 55–80, 80–100 (mark as "not recorded"), beta 12–30. Shade
the 80–100 region to show it is outside the acquisition passband. One glance
should say: *the band is wider than the signal, and the effect is in one slice.*

**Fig. 2 — Protocol delta.** Two bars, epoch-random vs subject-wise, with
bootstrap CIs. Annotate the gap.

**Fig. 3 — Sub-band agreement.** Scatter of per-subject predicted probability,
30–45 Hz model (x) vs 30–100 Hz model (y), coloured by true class, with $r=0.979$
annotated. Makes "the same predictions" visual rather than asserted.

Data for all three is already in `results/runs/*/result.json`.

## Things NOT to change without rerunning

- All numbers are `max_epochs=40`, 15 s epochs, 10 folds, seed 0, 63 subjects.
- Table 1 comes from run `20260813-083449_bandcheck`.
- The 30–45 Hz secondary result comes from `20260812-225345_e2` vs
  `20260812-215110_e2`.

## Framing decisions already baked in — keep them

1. **"Match", not "beat".** V3 is a null result (p=1.00). The paper says the
   baseline *matches* the CNN. Do not upgrade this in revision; it does not
   survive the power analysis.
2. **Protocol, not people.** The paper criticises an evaluation convention and
   treats [1] as an instance. Sec. VI says explicitly that [1] is not unusual.
   Keep that sentence.
3. **Mechanism unresolved.** Sec. III-F and the limitations both say we cannot
   identify why 30–45 Hz separates the groups. Four mechanism hypotheses were
   tested and rejected during this work; do not add a fifth at writing time.
4. **V2 reported as a number, not a verdict.** 0.091 is just under the 0.10
   threshold. The text says "nine accuracy points" and does not lean on "FAIL".

## Honest self-assessment

**Strongest parts.** V1 is unarguable — the header says 80 Hz, the band says
100 Hz, and no modelling is needed to see the problem. The rejected-hypotheses
table pre-empts most reviewer objections with numbers. The single-command
reproducibility is real and rare.

**Weakest parts, in the order a reviewer will hit them.**

1. *One dataset.* The obvious objection, and we have no answer. Limitations
   names it.
2. *Uncalibrated thresholds.* Mitigated by exposing them and reporting raw
   quantities, but a reviewer may still object that a "protocol" with arbitrary
   cut-offs is a checklist, not a method. The honest defence is that the
   quantities are the contribution and the thresholds are conveniences.
3. *Is a validity protocol a signal-processing contribution?* This is the venue
   risk. V1, V4 and V5 are spectral operations, which helps. If reviewers say no,
   the content transfers unchanged to a journal.
4. *$N=63$.* Handled explicitly in Sec. V-B, which turns a weakness into a
   methodological point.

**My estimate:** a credible ICASSP submission, better than borderline on rigour,
genuinely uncertain on venue fit. If it is rejected, it will be on scope
("interesting but not signal processing"), not on soundness — and that same
manuscript goes to EMBC 2027 or *J. Neural Eng.* with minimal change.

## Suggested order of work

1. Find the 3–5 supporting citations (item 3). Half a day. Do it first — it can
   change the framing.
2. Make Fig. 1. Half a day.
3. Read the draft end to end and mark everything you disagree with. Your name is
   on it, and I have been wrong repeatedly in this project.
4. Figs 2–3, then a full pass.
5. Send to a colleague by ~6 Sep with a 48-hour window.
6. Submit 15 Sep, not the 16th.
