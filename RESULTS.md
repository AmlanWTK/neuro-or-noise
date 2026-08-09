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
