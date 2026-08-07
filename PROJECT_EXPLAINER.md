# neuro-or-noise — The Project, Explained

*What the original paper claims, why that claim is doubtful, and what we are doing about it.*

Read this before running anything. It is written to be understood on its own, without the code.

---

## 1. The one-paragraph version

A 2024 paper in *IEEE Transactions on Artificial Intelligence* reports that a deep network can
diagnose major depressive disorder from EEG with **99.60% accuracy**, and that the **gamma band
(30–100 Hz)** is the single most effective brainwave for the job. We think a large part of that
performance does not come from the brain. Gamma-band scalp EEG is heavily contaminated by muscle
activity from the head and neck, and the paper's own experiments show that when they applied
artifact removal, accuracy went *down* — so they removed the artifact removal. Our paper tests
whether the model is detecting depression or detecting jaw tension, electrode impedance, and
mains-hum signatures. We then build a version that is honest about it.

---

## 2. The original paper

> I. A. Anik, A. H. M. Kamal, M. A. Kabir, S. Uddin, M. A. Moni,
> "A Robust Deep-Learning Model to Detect Major Depressive Disorder Utilizing EEG Signals,"
> *IEEE Transactions on Artificial Intelligence*, vol. 5, no. 10, pp. 4938–4947, Oct. 2024.
> DOI: 10.1109/TAI.2024.3394792

### What they did

They used a public EEG dataset from Hospital Universiti Sains Malaysia (originally released by
Mumtaz et al.): **34 people with MDD, 30 healthy controls**, 19 electrodes placed by the standard
10–20 system, sampled at 256 Hz, five minutes with eyes closed and five minutes with eyes open.

Their pipeline:

1. **Notch filter at 50 Hz** to remove mains electrical hum.
2. **Split the signal into the five classical frequency bands** — delta (0.5–4 Hz), theta (4–8),
   alpha (8–12), beta (12–30), gamma (30–100).
3. **Cut each band into short windows** ("epochs") of 5, 6, 10, 15 or 20 seconds, with a
   **1-second overlap** between consecutive windows.
4. **z-score standardisation** of the values.
5. **Train "Ex-1DCNN"** — an 11-layer 1-D convolutional network, 5 convolution layers with only
   5 filters each, mixing max-pooling and average-pooling, ending in a single sigmoid output.
6. **Tenfold cross-validation.**

### What they found

| Band | Best epoch length | Accuracy |
|---|---|---|
| Delta | 15 s | 91.27% |
| Theta | 10 s | 98.92% |
| Alpha | 15 s | 95.29% |
| Beta | 5 s | 88.53% |
| **Gamma** | **15 s** | **99.60%** |
| All combined | 5 s | 98.73% |

Their headline conclusion: gamma is the best biomarker for MDD, and their model can diagnose
depression with essentially perfect accuracy.

They also report one negative result that turns out to matter enormously: **Independent Component
Analysis (ICA) preprocessing made performance worse**, so they dropped it and used no biological
artifact removal at all.

---

## 3. Why the gamma result is suspicious

This is the heart of the project, so it is worth being slow and clear.

### 3.1 What "gamma" contains besides brain

The gamma band is 30–100 Hz. Three non-brain things live in exactly that range:

**Muscle activity (EMG).** Every time you clench your jaw, furrow your brow, swallow, or hold your
head up, the temporalis, frontalis and neck muscles produce electrical activity. At the scalp this
EMG signal spans roughly 20–200 Hz and **peaks around 70–80 Hz — dead centre in the gamma band.**
It is also *much larger* in amplitude than genuine cortical gamma, which is a small, deep signal
that barely reaches the scalp electrodes.

**Mains hum residue.** The recordings were made in Malaysia, so the electrical supply is 50 Hz —
inside the gamma band. The paper applies a notch filter, but notch filters never remove
everything, and *what is left over is different for every recording session* because it depends on
electrode impedance, cable position, and how well each electrode was gelled that day.

**Eye-movement spikes.** Tiny involuntary eye movements produce a sharp electrical transient that
smears energy across high frequencies and is a well-documented contaminant of measured "gamma."

### 3.2 The tell: removing artifacts made it worse

The paper reports that ICA — a standard technique for isolating and removing artifact components —
**reduced accuracy at every epoch duration tested.** They interpret this as ICA underperforming on
a small dataset, and cite a paper about ICA's limitations to support that.

That interpretation is possible. But there is a second interpretation that fits equally well:
**ICA was working correctly, and it was removing the exact signal the classifier depended on.**

If the model's discriminative power came from muscle artifact, then stripping out muscle artifact
would necessarily hurt accuracy. The observation is the same; the conclusion is opposite. Nothing
in the paper distinguishes the two — and that is the gap we walk through.

### 3.3 Why 99.60% is itself a warning sign

Depression is diagnosed by clinicians using structured interviews, and even expert clinicians
disagree with each other a fair amount. Resting EEG is a noisy, indirect measure of brain activity.
A model that separates depressed from healthy people with 99.60% accuracy — better than the
diagnostic process that produced the labels — is claiming something extraordinary.

In practice, when a biomedical classifier reports near-perfect accuracy on a small dataset, the
overwhelmingly common explanation is that something in the recording setup, rather than the
biology, is doing the work.

---

## 4. What exactly is lacking

Six specific gaps, in descending order of importance.

### Gap 1 — No test of whether the signal is neural

This is the big one. Nothing in the paper distinguishes "the network found a brain difference"
from "the network found a muscle difference." No EMG control, no artifact-only baseline, no
topographic analysis, no comparison of gamma against a sub-45 Hz control band.

### Gap 2 — The evaluation protocol is ambiguous, and the details matter enormously

The paper says the ten folds each contain "around three MDD patients and three healthy subjects,"
which describes **subject-wise** splitting — the correct approach, where a person appears in
either the training set or the test set but never both.

But the reported accuracy is far higher than subject-independent EEG results typically achieve,
which is the pattern you would expect from **epoch-wise** splitting, where random windows from the
same person land on both sides of the split and the model can simply memorise individuals.

Combined with the **1-second overlap** between consecutive epochs — meaning two adjacent 15-second
windows share 14 seconds of identical signal — an epoch-level split would put near-duplicate data
in training and test. **We have to determine empirically which protocol was actually used.** That
is the first gate in the plan.

### Gap 3 — Accuracy is reported per-epoch, not per-patient

The clinical unit of decision is a person, not a 15-second window. With 64 subjects, a
subject-level accuracy figure carries a confidence interval roughly ±10 percentage points wide.
Reporting 99.60% with no interval implies a precision the sample size cannot support.

### Gap 4 — One dataset, one hospital, one protocol

The authors acknowledge this. Everything comes from a single site with a single recording setup.
Any site-specific quirk — one brand of amplifier, one technician's electrode technique — is
indistinguishable from a biological finding.

### Gap 5 — No calibration or uncertainty

The model outputs a decision but no trustworthy confidence. For clinical triage, a model that is
confidently wrong is worse than one that says "I am not sure, refer this to a clinician."

### Gap 6 — Single run, no statistical testing

No seed variation, no confidence intervals, no significance tests between conditions. The claim
that gamma beats theta (99.60% vs 98.92%) rests on a difference that may well be noise.

---

## 5. The distinction that shapes everything

There are **two different ways** a model can succeed without measuring the brain, and they demand
different conclusions. Getting this right is what separates a good paper from a sloppy one.

### Mode A — Leakage (subject memorisation)

The model learns to recognise *individuals*, not the disease. Because EEG is effectively a
biometric — you can identify a person from their recording — a model given random windows from
each person can memorise "this is patient 12, and patient 12 is depressed."

- **Signature:** near-perfect under epoch-level splits, **collapses to chance** under
  leave-one-subject-out.
- **Verdict:** the result is an artifact of evaluation design. The model learned nothing
  transferable.

### Mode B — A real but non-neural difference

Suppose people with depression are, on average, more tense during the recording — more jaw
clenching, more muscle tone. Then the EMG contamination **genuinely differs between the groups**.

- **Signature:** high accuracy that **survives** leave-one-subject-out and would replicate in
  another lab.
- **Verdict:** the result is real, reproducible, and still not a brain measurement. You have built
  a very good jaw-tension detector and called it a depression biomarker.

**Mode B is the more interesting finding and the harder one to catch.** Stricter cross-validation
does not touch it. Only an artifact-targeted analysis reveals it. This is why our experiments
include an artifact-only baseline and a topographic analysis rather than just fixing the splits.

We have already confirmed on simulated data that our probes separate these two modes cleanly.

---

## 6. What we are building

### Three contributions

**C1 — Diagnosis.** Quantify how much of the reported performance comes from evaluation protocol
and from non-neural high-frequency signal.

**C2 — Method.** An artifact-suppressed, subject-invariant model that holds up under strict
evaluation and reports calibrated, per-patient confidence.

**C3 — Protocol.** A released benchmark and evaluation recipe that future EEG-MDD work can be
measured against.

C1 alone would be a negative-results paper, and conferences are lukewarm on those. C2 is what
makes it a signal-processing contribution. We lead with C2 and motivate it with C1.

### The experiments

| ID | What it does | Why |
|---|---|---|
| **E0** | Faithfully reimplement Ex-1DCNN and reproduce γ @ 15 s | establishes we can hit their number before we question it |
| **E1** | Vary one protocol factor at a time — split type, overlap, normalisation scope, eyes-open/closed | attributes accuracy points to each design choice |
| **E2** | Four shortcut probes (below) | the scientific core |
| **E3** | The improved method — artifact suppression, subject-adversarial training, calibration | the contribution reviewers reward |
| **E4** | Train on HUSM, test on a second public dataset | external validity |

### The four probes in E2

| Probe | Question it asks | What a positive result means |
|---|---|---|
| **P1** subject-ID | Can a simple model identify *which person* a window came from? | Epochs carry a personal fingerprint, so epoch-level splits are meaningless |
| **P2** artifact-only | Can **five hand-computed numbers** + logistic regression match the deep network? | Five parameters cannot learn a subtle biomarker. If they match the CNN, the CNN isn't using one either |
| **P3** band × protocol | Does gamma stay top-ranked once subjects are held out? | Tests the paper's central claim directly |
| **P4** topography | Is the discriminative power concentrated at T3/T4/T5/T6/F7/F8? | Those sit over the temporalis muscle. Cortical gamma would not be so lateralised |

The five numbers in P2 are: power in 60–100 Hz (muscle), leftover power around 50 Hz (mains),
kurtosis (spikiness), zero-crossing rate, and RMS amplitude. None of them describes anything
neurologically meaningful about depression.

---

## 7. What we have found already

Two results, from reimplementing the architecture alone — before touching the real recordings.

**The paper's stated λ = 0.02 does not train.** Applied literally as weight decay on their
5-filter network, the model collapses to a constant output at every learning rate and epoch budget
we tried. Their λ must mean something different from standard weight decay. This goes in the paper
as a neutral reproducibility note, not a criticism — but anyone reimplementing from the published
description will hit it, and saying so is useful to the field.

**The 5-filter bottleneck memorises subjects.** On simulated data with subject-wise splits, their
5-filter width scores 0.462 while a 16-filter version scores 0.756. The narrow architecture
generalises *worse* across people — consistent with it latching onto per-subject signatures rather
than a transferable class boundary. If this reproduces on real data it is a genuine architectural
finding.

---

## 8. What happens next, and what each outcome means

Everything hinges on one measurement: **the gap between epoch-level and subject-level evaluation
on the real data.**

| If we observe | It means | The paper becomes |
|---|---|---|
| Large gap, artifact baseline collapses under LOSO | Mode A — leakage | "Reported performance is an artifact of epoch-level evaluation" |
| Small gap, artifact baseline stays high | Mode B — real but non-neural | "The effect is real and reproducible, and it is not neural" — the stronger paper |
| Small gap, artifact baseline collapses, gamma still wins | The original result largely holds | We pivot to cross-dataset generalisation and report the reproduction honestly |

**All three are publishable.** The third is the least exciting but the most important to be honest
about: if the finding survives our scrutiny, we say so plainly. A careful independent
reproduction of a headline result is a real contribution, and a project that can only "succeed" by
finding fault is not science.

---

## 9. How to talk about this work

We are outside the original authors' group, so the framing rule is simple: **critique the
protocol, never the people.**

Anik et al. did nothing improper. They followed a convention that a large share of the EEG
machine-learning literature follows. Say that explicitly, cite several other papers using the same
approach, and treat theirs as the strongest recent example rather than the target. This is both
fairer and more useful — a paper that corrects a field-wide practice gets cited by the field.

Use "consistent with," not "proves." Avoid "flawed," "invalid," "misleading," "fails to." The
numbers will carry the argument without adjectives.

On the ICA point specifically, the honest and powerful construction is: *we reproduce their
observation and interpret it differently.* That is an ordinary scientific disagreement, cleanly
stated.

---

## 10. Glossary

| Term | Meaning |
|---|---|
| **Epoch** | A short window of EEG, here 5–20 seconds. The unit fed to the model |
| **Subject-wise / leave-one-subject-out (LOSO)** | Splitting so each person is entirely in training or entirely in test — never both |
| **Epoch-wise split** | Splitting individual windows at random, so one person's data can appear on both sides. Usually inflates accuracy |
| **Leakage** | Information from the test set reaching the model during training, in any form |
| **Shortcut learning** | A model solving a task by a spurious cue that happens to correlate with the label |
| **EMG** | Electromyography — muscle electrical activity. The main contaminant of scalp gamma |
| **ICA** | Independent Component Analysis. Separates a signal into components so artifacts can be removed |
| **Calibration** | Whether a model's stated confidence matches its actual accuracy |
| **DANN** | Domain-Adversarial Neural Network. Trains features from which a nuisance variable — here subject identity — cannot be recovered |
| **Notch filter** | A narrow filter removing one frequency, typically 50/60 Hz mains hum |

---

## 11. Background reading

Not required, but each of these underpins a claim above:

- **Whitham et al. (2007)**, *Clinical Neurophysiology* — scalp EEG above ~20 Hz is heavily
  contaminated by muscle; demonstrated with neuromuscular blockade.
- **Muthukumaraswamy (2013)**, *Frontiers in Human Neuroscience* — review of EMG artifacts in
  gamma-band EEG/MEG research.
- **Yuval-Greenberg et al. (2008)**, *Neuron* — miniature eye movements masquerading as induced
  gamma.
- **Geirhos et al. (2020)**, *Nature Machine Intelligence* — shortcut learning in deep networks,
  the general framing.
- **Ganin & Lempitsky (2015)**, *ICML* — domain-adversarial training, the basis of our method.
- **Mumtaz et al. (2017)**, *Biomedical Signal Processing and Control* — the original dataset
  release.

---

*Target venue: IEEE ICASSP 2027. Submission deadline 16 September 2026.*
