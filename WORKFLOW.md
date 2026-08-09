# Run & commit workflow

One rule: **every experiment run produces a commit, and every commit message states
the finding.** In January, when a reviewer questions a number, `git log --oneline`
should read like a lab notebook.

---

## The loop

```bash
# 1. commit any code changes FIRST, so the run is tied to a clean tree
git add -A && git commit -m "fix(data): select 19 scalp channels by name, not position"

# 2. run
python experiments/e2_shortcut.py --data "D:\Project\PaperPlan\EEG" --probes P1,P2,P4

# 3. commit the run record with the finding in the subject line
git add -A && git commit -m "exp(e2): artifact-only 0.884 beats CNN 0.835; line-noise AUC 0.893"
```

If you run with uncommitted changes, the runner prints
`WARNING: working tree is dirty`. That run cannot be reproduced from a commit —
still usable for exploration, never quotable in the paper.

## What gets saved

Every run writes an immutable directory, never overwritten:

```
results/runs/20260809-041620_e2c/
    meta.json     command, git commit, dirty flag, package versions, duration
    console.log   full stdout exactly as printed
    result.json   structured results
```

These are committed to git. They are kilobytes, and they are the only thing that
ties a number in the paper to the code that produced it.

Loose files directly in `results/` are scratch and stay gitignored.

## Commit message format

```
<type>(<scope>): <finding or change, imperative, one line>
```

**Types**

| Type | Use for |
|---|---|
| `exp` | an experiment run — **subject line states the RESULT, not the action** |
| `feat` | new capability (a new probe, a new model) |
| `fix` | a bug, especially one that would have corrupted results |
| `data` | loader / dataset handling |
| `docs` | markdown, notes, plan updates |
| `refactor` | no behaviour change |

**Scope** is the experiment or module: `e0` `e1` `e2` `e2c` `e3` `e4` `data` `models` `metrics`.

### `exp` commits state findings, not actions

The subject line is what you will scan in six weeks. Make it carry the number.

Good:

```
exp(e2): artifact-only 0.884 beats CNN 0.835; line-noise AUC 0.893
exp(e1): protocol gap 0.12 (epoch-random 0.955 vs subject-wise 0.835)
exp(e2c): 50Hz group difference present in RAW signal, AUC 0.91 pre-notch
exp(e1): overlap contributes -0.005 at 5s epochs; negative result
```

Useless:

```
exp(e2): ran e2                     <- what happened?
exp: update results                 <- which experiment? what did it show?
wip                                 <- no
```

Add a body when the finding needs a caveat:

```
exp(e1): protocol gap 0.12 (epoch-random 0.955 vs subject-wise 0.835)

Ran at epoch_sec=5.0, n_folds=5 -- NOT the paper's 15s/10-fold config.
Directionally valid, must be re-measured at 15s before publication.
Run: results/runs/20260809-0332_e1
```

## Commit messages for the runs already done

Backfill these in order so the history is complete:

```bash
git add -A && git commit -m "feat: scaffold protocol-configurable EEG-MDD pipeline with artifact probes"
git add -A && git commit -m "fix(data): parse TASK files explicitly; dedupe H S15 EO; regex subject ids"
git add -A && git commit -m "fix(data): select 19 scalp channels by name, dropping A2-A1 and aux pairs"
git add -A && git commit -m "exp(gate0): synthetic acceptance passes, epoch-random 1.00 vs subject-wise 0.50"
git add -A && git commit -m "data: HUSM verified -- 63 resting subjects (MDD=33), 1 dup, 7 missing a condition"
git add -A && git commit -m "exp(e1): protocol gap 0.12; 99.60% not reproduced (best 0.960, subject-wise 0.835)"
git add -A && git commit -m "exp(e2): artifact-only 0.884 beats CNN 0.835; line-noise AUC 0.893, posterior topography"
git add -A && git commit -m "feat(runlog): immutable timestamped run records with git commit and versions"
```

## Tagging the decision points

The plan has gates. Tag them so you can diff against them later:

```bash
git tag -a gate0 -m "synthetic pipeline validated"
git tag -a gate1 -m "protocol gap 0.12 -- artifact story leads the paper"
```

## Before the ICASSP submission

```bash
git log --oneline > results/provenance.txt
```

Paste that into the reproducibility appendix. Reviewers rarely check. The ones
who do will remember that you made it possible.
