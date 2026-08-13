# Second dataset — revised plan

*13 Aug 2026. This supersedes the "do not start Tier 3" line in
`ROAD_TO_ACCEPTANCE.md`, which was too absolute. Reasoning below.*

---

## I was wrong to rule it out flatly

My argument was time risk. Two things I under-weighted:

1. **The draft is finished.** The critical path to submission is now one 10-minute
   run, fifteen minutes of author details, your read-through, and a colleague.
   None of that is blocked by dataset work, so a second dataset is a *parallel*
   track, not a competing one.
2. **The cheapest version of this is very cheap.** I was costing out "replicate
   the whole protocol on a second cohort." But **V1 needs no labels and no model
   training at all** — it reads acquisition metadata and computes a median PSD.
   That is hours, not weeks, and it happens to answer the single strongest
   objection to the paper.

What stands from the original warning: **the submission must never wait on this.**
That is handled by a drop-dead date, not by refusing to start.

## Why this is worth doing — the actual argument

The paper's weakest point right now is that **BandCheck has only ever been shown
failing.** A reviewer can reasonably ask whether the protocol is tuned to fail on
the one case it was built from. We have no answer to that today.

TDBRAIN was acquired with a **100 Hz hardware low-pass**, against HUSM's 80 Hz. A
nominal 30–100 Hz band is therefore *supported* by that acquisition chain. Running
V1 there turns it from a foregone conclusion into a real test with a real chance
of passing.

To be precise about what we can and cannot promise: the header-based dead
fraction on TDBRAIN should be ~0, but HUSM taught us the empirical noise floor
can sit well below the nominal low-pass (56 Hz against a stated 80 Hz). So V1
might still flag empirically. **Either outcome is publishable in one sentence,
and either one is better than silence** — a PASS shows the protocol
discriminates; a FLAG shows the empirical edge check catches something headers
alone miss, on two independent cohorts.

---

## The three candidates, as verified 13 Aug

| | **TDBRAIN** | **MODMA** | **PRED+CT** |
|---|---|---|---|
| Subjects | 1,274 total; **426 MDD** | 53 (24 MDD / 29 HC), 128-ch resting | not verified |
| Healthy controls | **None identified as distributed** | Yes, 29 | Believed yes, unverified |
| Resting protocol | 2 min EO + 2 min EC | resting | not verified |
| Channels / rate | 26 (10–10) / 500 Hz | 128 / not stated | not verified |
| **Acquisition low-pass** | **100 Hz, stated** | not stated | not verified |
| Raw or preprocessed | Raw `.eeg`/`.vhdr`, BIDS; derivatives separate | not stated | not verified |
| Access | ORCID login + sign DUA on Synapse — **self-serve** | Org email + printed/signed/scanned EULA + admin approval, *"could take a couple of days"* | Public Domain Dedication v1.0; mechanism not verified |
| Catch | 30% of labels blinded → usable MDD ≈ 298 | small; no bigger than HUSM | unverified throughout |

### Recommendation: TDBRAIN, for V1 first

- **Fastest access.** Sign a DUA and download; no committee, no approval wait.
- **It is the one that makes V1 interesting** — the 100 Hz low-pass is the whole
  point.
- Its fatal-looking weakness — no healthy controls — **does not bite for V1**,
  which never touches a diagnostic label.

MODMA is the right choice only if you want the same MDD-vs-HC contrast, and at
53 subjects it adds no statistical power over HUSM's 63. Start the MODMA EULA
anyway, in parallel, because it costs ten minutes and the approval clock runs
while you work on TDBRAIN.

---

## MODMA — direct download links (verified 13 Aug)

The Lanzhou server needs an EULA and has been throwing 500s. **Use the UK Data
Service copy instead** — deposited by Bin Hu (Lanzhou) himself, **CC BY 4.0**,
and the EEG archives need no registration:
*"The Data Collection is available to any user without the requirement for
registration for download/access."*

Record page: <https://reshare.ukdataservice.ac.uk/854301/>

| File | Size | Access | Link |
|---|---|---|---|
| **`854301_Methodology.docx`** — read this first | 16 kB | open | `/854301/8/854301_Methodology.docx` |
| **`854301_EEG_128Channels_Resting_Lanzhou_2015.zip`** — the one we want | 2 GB | open | `/854301/4/854301_EEG_128Channels_Resting_Lanzhou_2015.zip` |
| `854301_EEG_128Channels_ERP_Lanzhou_2015.zip` | 5 GB | open | `/854301/3/854301_EEG_128Channels_ERP_Lanzhou_2015.zip` |
| `854301_EEG_3Channels_Resting_Lanzhou_2015.zip` | 147 MB | open | `/854301/2/854301_EEG_3Channels_Resting_Lanzhou_2015.zip` |
| `ReadMe.pdf` | 441 kB | open | `/854301/37/ReadMe.pdf` |
| `854301_Audio_Lanzhou_2015.zip` | 2 GB | **restricted** | not needed |
| `Behavioral_Data.zip` | 1 MB | **restricted** | not needed |

Prefix each with `https://reshare.ukdataservice.ac.uk`.

There is also a BIDS-format version split across `MODMA_EEG_BIDS_format.zip` plus
`.z01`–`.z10`, roughly 10 GB total. Skip it unless BIDS tooling is wanted — the
2 GB native archive is the cheaper path, and every part of a split archive must
sit in one folder before 7-Zip will extract it. Take those part URLs off the
record page rather than from this table; I did not read them reliably.

### One observation that shortens Stage 1 considerably

The source paper says the 128-channel data went `.mff` → `.mat` → **`.EDF`** for
BIDS compliance. **If the distributed files are EDF, our existing header parser
already reads them** — `load_husm()` pulls the acquisition filter settings out of
EDF headers today. That could turn the "budget a full day for the loader" estimate
into an afternoon: mostly channel mapping (E1–E128 to 10-20 positions) and the
250 Hz sampling rate.

Confirm the format by looking inside the zip before writing any code.

### Still unknown, and it decides whether MODMA is worth it

The source paper does **not** state acquisition filter settings for the
128-channel resting data — only for the 3-electrode set, and there only as
processing (1 Hz HP, 45 Hz LP FIR), not acquisition. `854301_Methodology.docx`
is the likely place this is recorded; it is 16 kB and I could not read it
remotely because it is binary. **Open it first.** If no acquisition filter is
documented anywhere, V1's header arm cannot run on MODMA and we are left with
the empirical noise-floor estimate alone — which weakens the case for using
MODMA at all, and argues for TDBRAIN, where the 100 Hz low-pass *is* documented.

## Staged plan — stop wherever the calendar stops you

Each stage stands alone and is worth a sentence in the paper.

**Stage 1 — V1 only. No labels, no training. Target: 3 days.**
Download TDBRAIN, write the BrainVision loader, read the hardware filter settings
from the `.vhdr` headers, compute the median PSD and the empirical edge.
*Deliverable:* one row in Table 1 and one sentence in §V1. This is the stage that
actually answers the reviewer objection — if you do nothing else, do this.

**Stage 2 — V2 and V3, on MDD vs ADHD. Target: +1 week.**
TDBRAIN has no healthy controls, so the contrast has to change. MDD (≈298
labelled) vs ADHD (≈190) is a legitimate psychiatric classification task, and at
that N the protocol delta gets **real statistical power** — which directly
retires our biggest stated limitation. Be explicit in the text that the contrast
differs; do not let it read as an MDD-vs-HC replication.

**Stage 3 — V4 and V5. Only if Stages 1–2 are done and verified by 25 Aug.**

**Drop-dead: 1 September.** Anything not verified and written by then is cut, and
the paper submits as it stands today. Write that date down now, while it is still
cheap to honour.

---

## What will actually take the time

Not the protocol — that is config-driven, which is why it was built that way. The
work is the loader and the montage:

- **Channel naming.** TDBRAIN is 10–10; HUSM is 10–20. `CANONICAL_19` uses
  T3/T4/T5/T6, which are T7/T8/P7/P8 in 10–10. `canonical_channel()` needs that
  mapping or it will silently drop four electrodes — the same class of bug as the
  select-by-position error we already fixed once.
- **Sampling rate.** 500 Hz against 256 Hz. Either resample or make `fs` genuinely
  a config parameter throughout. Check nothing assumes 256.
- **Format.** BrainVision `.eeg`/`.vhdr`, not EDF. New reader, and the filter
  metadata lives in a different header field — which V1 depends on.
- **Use the raw files, not the `derivatives/` folder.** Preprocessed data would
  destroy V1's premise.

Budget a full day for the loader alone, and expect the same two or three rounds
of correction every other stage of this project has needed.

---

## Ground rules, unchanged

- Every claim from the new dataset gets a run record, or it is a hypothesis.
- If BandCheck returns a different verdict on TDBRAIN, **that is a finding, not a
  problem** — a protocol that flags one cohort and passes another is far more
  credible than one that has only ever failed. Report it as it lands.
- The primary submission does not wait. Ever.
