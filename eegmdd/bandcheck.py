"""BandCheck -- a validity protocol for band-specific EEG biomarker claims.

THE CONTRIBUTION. Everything else in this repo is an application of it.

A large literature reports that some frequency band is the best discriminator for
some clinical label. Almost none of those papers check whether the claim is even
well-posed. Five cheap checks, run before any modelling, catch the failure modes
we found in a published 99.60% result:

  V1  PASSBAND SUPPORT    Is the analysis band inside the recording's real
                          passband? Reading filter settings out of the file
                          header takes milliseconds and can invalidate a band
                          outright. (Found: 29% of a nominal 30-100 Hz band lay
                          above an 80 Hz acquisition low-pass -- empty spectrum.)

  V2  PROTOCOL DELTA      How much accuracy is attributable to the split rule
                          alone? Epoch-level vs subject-level splits, one factor
                          at a time. (Found: 0.114.)

  V3  ARTIFACT CONTROL    Can five signal-quality scalars -- with no neural
                          content whatsoever -- match the model? If so, the model
                          is not demonstrating a neural biomarker.
                          (Found: 0.873 vs 0.841, p=0.63. It matched.)

  V4  SUB-BAND LOCALISATION  Split the band into sub-bands. Does one narrow
                          slice reproduce the whole result? A claim about
                          "30-100 Hz" that is really about 30-45 Hz is
                          mis-specified. (Found: exactly that, r=0.979.)

  V5  EXCISION CONTROL    Band-stop the suspected contaminant (mains, EMG peak)
                          and re-measure. If accuracy is unchanged, that
                          contaminant is not the mechanism -- a useful null that
                          stops a wrong story being told. (Found: mains costs
                          0.0004.)

Each check returns PASS / FLAG / FAIL plus the number behind it. A claim that
passes all five is not necessarily true, but a claim that fails any of them is
not yet well-posed -- and that is a much cheaper thing to establish than a
replication study.

Usage:
    from eegmdd.bandcheck import run_bandcheck
    report = run_bandcheck(recs, band="gamma", model="artifact_lr")
    print(report.render())
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np
from scipy.signal import welch

from .config import BANDS, Config
from .data import build_epochs
from .metrics import binary_metrics, bootstrap_ci, mcnemar, to_subject_level
from .train import run_cv

PASS, FLAG, FAIL, INFO = "PASS", "FLAG", "FAIL", "INFO"


@dataclass
class Check:
    id: str
    name: str
    status: str
    headline: str
    value: Any = None
    detail: dict = field(default_factory=dict)


@dataclass
class Report:
    band: str
    band_range: tuple
    model: str
    n_subjects: int
    checks: list = field(default_factory=list)

    def add(self, c: Check):
        self.checks.append(c)

    @property
    def verdict(self) -> str:
        if any(c.status == FAIL for c in self.checks):
            return "NOT WELL-POSED"
        if any(c.status == FLAG for c in self.checks):
            return "QUALIFIED"
        return "WELL-POSED"

    def render(self) -> str:
        lo, hi = self.band_range
        out = ["", "=" * 72,
               f" BandCheck report -- band '{self.band}' ({lo:g}-{hi:g} Hz), "
               f"model '{self.model}', n={self.n_subjects}",
               "=" * 72]
        for c in self.checks:
            mark = {PASS: "[ok]  ", FLAG: "[FLAG]", FAIL: "[FAIL]", INFO: "[info]"}[c.status]
            out.append(f" {mark} {c.id}  {c.name}")
            out.append(f"        {c.headline}")
        out += ["-" * 72, f" VERDICT: {self.verdict}", "=" * 72, ""]
        return "\n".join(out)

    def to_dict(self):
        return dict(band=self.band, band_range=list(self.band_range), model=self.model,
                    n_subjects=self.n_subjects, verdict=self.verdict,
                    checks=[asdict(c) for c in self.checks])


# ---------------------------------------------------------------- V1

def v1_passband_support(recs, band, fs=256, header_lp=None, header_hp=None) -> Check:
    """Fraction of the analysis band that carries no signal."""
    lo, hi = BANDS[band][:2]
    # empirical: median PSD across subjects, find where it falls to the noise floor
    psds = []
    for r in recs[: min(len(recs), 40)]:
        if r.condition not in ("EC", "EO"):
            continue
        f, p = welch(r.data, fs=fs, nperseg=min(2048, r.data.shape[-1]), axis=-1)
        psds.append(p.mean(axis=0))
    if not psds:
        return Check("V1", "Passband support", INFO, "no resting recordings found")
    m = np.median(np.array(psds), axis=0)

    # noise floor = median power above 0.45*fs (nothing real lives there)
    floor = np.median(m[f >= 0.45 * fs])
    usable = f[(m > 5 * floor)]
    emp_edge = float(usable.max()) if len(usable) else float(f[-1])

    # The HEADER is ground truth about what the amplifier passed; the empirical
    # edge is an estimate that a steep 1/f can drag down. Prefer the header when
    # available and treat the empirical value as corroboration, reporting both
    # so a reader can see if they disagree.
    # Report BOTH. The header is what the amplifier was set to; the empirical
    # edge is where signal actually stops. They can differ a lot (analogue
    # roll-off, extra anti-alias stages), and the gap is informative. We take
    # the HEADER as the headline number because it is the conservative one --
    # it always yields the smaller dead fraction -- but a reader must see both.
    edge = float(header_lp) if header_lp else emp_edge
    # 0.35 was far too loose: 56 vs 80 Hz is a 30% gap and materially changes
    # the dead fraction (0.29 -> 0.63). Tightened to 0.15.
    agree = (header_lp is None) or (abs(emp_edge - header_lp) / header_lp < 0.15)

    dead = max(0.0, hi - edge)
    frac = dead / (hi - lo)
    dead_emp = max(0.0, hi - emp_edge) / (hi - lo)
    detail = dict(band=[lo, hi], empirical_edge_hz=round(emp_edge, 1),
                  header_lp_hz=header_lp, edge_used_hz=round(edge, 1),
                  edge_sources_agree=bool(agree),
                  dead_hz=round(dead, 1), dead_fraction=round(frac, 3),
                  dead_fraction_empirical=round(dead_emp, 3))
    extra = ("" if agree else
             f"; empirically signal stops at {emp_edge:.0f} Hz, giving {dead_emp:.0%}")
    if frac >= 0.15:
        return Check("V1", "Passband support", FAIL,
                     f"{frac:.0%} of the band ({dead:.0f} Hz) lies above the usable "
                     f"edge {edge:.0f} Hz -- that portion contains no signal{extra}",
                     frac, detail)
    if frac > 0.02:
        return Check("V1", "Passband support", FLAG,
                     f"{frac:.0%} of the band lies above the usable edge {edge:.0f} Hz",
                     frac, detail)
    return Check("V1", "Passband support", PASS,
                 f"band fits inside the usable spectrum (edge {edge:.0f} Hz)", frac, detail)


# ---------------------------------------------------------------- V2

# V2, V3, V4 and V5 each need the SAME full-band subject-wise fit. Without a
# cache that is four identical CNN trainings -- roughly an hour wasted on a
# 3-hour report. Key on the config tag, which already encodes every field that
# changes the result.
_CACHE: dict = {}


def clear_cache():
    _CACHE.clear()


def _acc(recs, cfg):
    key = cfg.tag()
    if key in _CACHE:
        return _CACHE[key]
    es = build_epochs(recs, cfg)
    res = run_cv(es, cfg, verbose=False)
    ys, ps, subs = to_subject_level(es.y, res["_prob"], es.subject)
    _CACHE[key] = (res["epoch"]["accuracy"], ys, ps, subs)
    return _CACHE[key]


def v2_protocol_delta(recs, band, model, max_epochs=40, epoch_sec=15.0, n_folds=10, seed=0,
                      weight_decay=1e-4) -> Check:
    """Accuracy attributable to the split rule alone."""
    base = dict(band=band, epoch_sec=epoch_sec, overlap_sec=0.0, model=model,
                seed=seed, n_folds=n_folds, calibrate=False, max_epochs=max_epochs,
                weight_decay=weight_decay)
    a, *_ = _acc(recs, Config(split="epoch_random", norm_scope="global", **base))
    b, *_ = _acc(recs, Config(split="subject_kfold", norm_scope="train_fold", **base))
    d = a - b
    detail = dict(epoch_random=round(a, 4), subject_wise=round(b, 4), delta=round(d, 4))
    if d >= 0.10:
        return Check("V2", "Protocol delta", FAIL,
                     f"split rule alone accounts for {d:.3f} "
                     f"({a:.3f} epoch-random vs {b:.3f} subject-wise)", d, detail)
    if d >= 0.03:
        return Check("V2", "Protocol delta", FLAG,
                     f"split rule accounts for {d:.3f}", d, detail)
    return Check("V2", "Protocol delta", PASS,
                 f"split rule accounts for only {d:.3f}", d, detail)


# ---------------------------------------------------------------- V3

def v3_artifact_control(recs, band, model, max_epochs=40, epoch_sec=15.0, n_folds=10, seed=0,
                        weight_decay=1e-4) -> Check:
    """Can five signal-quality scalars match the model?"""
    if model == "artifact_lr":
        # Comparing the artifact baseline against itself is degenerate: it would
        # always report a perfect match and hence always FAIL. V3 is only
        # meaningful for a model that claims to use neural information.
        return Check("V3", "Artifact control", INFO,
                     "not applicable -- the model under test IS the artifact "
                     "baseline; rerun with the substantive model to apply V3")
    base = dict(band=band, epoch_sec=epoch_sec, overlap_sec=0.0, split="subject_kfold",
                norm_scope="train_fold", seed=seed, n_folds=n_folds, calibrate=False, max_epochs=max_epochs,
                weight_decay=weight_decay)
    _, ym, pm, sm = _acc(recs, Config(model=model, **base))
    _, ya, pa, sa = _acc(recs, Config(model="artifact_lr", **base))
    am = binary_metrics(ym, pm)["accuracy"]
    aa = binary_metrics(ya, pa)["accuracy"]
    n01, n10, p = mcnemar(ym, pm, pa)
    detail = dict(model_acc=round(am, 4), artifact_acc=round(aa, 4),
                  mcnemar_p=round(p, 4), discordant=[n01, n10],
                  model_ci=[round(v, 3) for v in bootstrap_ci(ym, pm)],
                  artifact_ci=[round(v, 3) for v in bootstrap_ci(ya, pa)])
    if p >= 0.05:
        return Check("V3", "Artifact control", FAIL,
                     f"a 5-scalar signal-quality baseline MATCHES the model "
                     f"({aa:.3f} vs {am:.3f}, McNemar p={p:.2f}) -- no evidence "
                     f"the model uses neural information", aa - am, detail)
    if aa > am:
        return Check("V3", "Artifact control", FAIL,
                     f"the artifact baseline BEATS the model ({aa:.3f} vs {am:.3f}, "
                     f"p={p:.3f})", aa - am, detail)
    return Check("V3", "Artifact control", PASS,
                 f"model exceeds the artifact baseline ({am:.3f} vs {aa:.3f}, "
                 f"p={p:.3f})", am - aa, detail)


# ---------------------------------------------------------------- V4

def v4_subband_localisation(recs, band, model, max_epochs=40, n_sub=3, epoch_sec=15.0,
                            n_folds=10, seed=0, weight_decay=1e-4) -> Check:
    """Does one narrow slice reproduce the whole band's result?"""
    lo, hi = BANDS[band][:2]
    edges = np.linspace(lo, hi, n_sub + 1)
    base = dict(epoch_sec=epoch_sec, overlap_sec=0.0, split="subject_kfold",
                norm_scope="train_fold", model=model, seed=seed,
                n_folds=n_folds, calibrate=False, max_epochs=max_epochs,
                weight_decay=weight_decay)

    full_e, yf, pf, _ = _acc(recs, Config(band=band, **base))
    full = binary_metrics(yf, pf)["accuracy"]

    subs = []
    for i in range(n_sub):
        name = f"_bc_sub{i}"
        BANDS[name] = (float(edges[i]), float(edges[i + 1]))
        try:
            _, ys, ps, _ = _acc(recs, Config(band=name, **base))
            acc = binary_metrics(ys, ps)["accuracy"]
            r = float(np.corrcoef(ps, pf)[0, 1])
            agree = float(((ps >= .5) == (pf >= .5)).mean())
            subs.append(dict(range=[round(edges[i], 1), round(edges[i + 1], 1)],
                             acc=round(acc, 4), r_with_full=round(r, 3),
                             agreement=round(agree, 3)))
        finally:
            BANDS.pop(name, None)

    best = max(subs, key=lambda s: s["acc"])
    detail = dict(full_band_acc=round(full, 4), subbands=subs, best=best)
    width_frac = (best["range"][1] - best["range"][0]) / (hi - lo)

    if best["acc"] >= full - 0.02 and width_frac <= 0.5:
        return Check("V4", "Sub-band localisation", FAIL,
                     f"{best['range'][0]:g}-{best['range'][1]:g} Hz alone reaches "
                     f"{best['acc']:.3f} vs {full:.3f} for the full band "
                     f"(r={best['r_with_full']:.2f}, {best['agreement']:.0%} agreement)"
                     f" -- the claim is mis-specified as a whole-band effect",
                     best["acc"] - full, detail)
    if best["acc"] >= full - 0.05:
        return Check("V4", "Sub-band localisation", FLAG,
                     f"{best['range'][0]:g}-{best['range'][1]:g} Hz nearly matches the "
                     f"full band ({best['acc']:.3f} vs {full:.3f})",
                     best["acc"] - full, detail)
    return Check("V4", "Sub-band localisation", PASS,
                 f"no sub-band reproduces the full band (best {best['acc']:.3f} "
                 f"vs {full:.3f})", best["acc"] - full, detail)


# ---------------------------------------------------------------- V5

def v5_excision_control(recs, band, model, max_epochs=40, stop=(45.0, 55.0), epoch_sec=15.0,
                        n_folds=10, seed=0, weight_decay=1e-4) -> Check:
    """Band-stop a suspected contaminant; does accuracy move?"""
    lo, hi = BANDS[band][:2]
    if not (lo < stop[0] and stop[1] < hi):
        return Check("V5", "Excision control", INFO,
                     f"{stop[0]:g}-{stop[1]:g} Hz lies outside the band; not applicable")
    base = dict(epoch_sec=epoch_sec, overlap_sec=0.0, split="subject_kfold",
                norm_scope="train_fold", model=model, seed=seed,
                n_folds=n_folds, calibrate=False, max_epochs=max_epochs,
                weight_decay=weight_decay)
    _, y0, p0, _ = _acc(recs, Config(band=band, **base))
    name = "_bc_excised"
    BANDS[name] = (lo, hi, tuple(stop))
    try:
        _, y1, p1, _ = _acc(recs, Config(band=name, **base))
    finally:
        BANDS.pop(name, None)
    a0 = binary_metrics(y0, p0)["accuracy"]
    a1 = binary_metrics(y1, p1)["accuracy"]
    d = a0 - a1
    detail = dict(intact=round(a0, 4), excised=round(a1, 4), delta=round(d, 4),
                  stop_hz=list(stop))
    if abs(d) < 0.02:
        return Check("V5", "Excision control", PASS,
                     f"removing {stop[0]:g}-{stop[1]:g} Hz changes accuracy by "
                     f"{d:+.4f} -- that region is NOT the mechanism", d, detail)
    return Check("V5", "Excision control", FLAG,
                 f"removing {stop[0]:g}-{stop[1]:g} Hz costs {d:+.4f} -- that region "
                 f"carries part of the result", d, detail)


# ---------------------------------------------------------------- driver

def run_bandcheck(recs, band="gamma", model="artifact_lr", epoch_sec=15.0,
                  n_folds=10, seed=0, header_lp=None, checks=("V1", "V2", "V3", "V4", "V5"),
                  n_sub=3, stop=(45.0, 55.0), max_epochs=40, weight_decay=1e-4,
                  verbose=True) -> Report:
    """max_epochs is EXPLICIT because it moves the numbers. An earlier code path
    hardcoded 25 and produced a protocol delta of 0.114 where this produces
    0.091 -- same experiment, different training budget. Whatever a paper
    reports, it must report this value alongside it."""
    clear_cache()
    n_subj = len({r.subject for r in recs if r.condition in ("EC", "EO")})
    rep = Report(band=band, band_range=BANDS[band][:2], model=model, n_subjects=n_subj)
    kw = dict(epoch_sec=epoch_sec, n_folds=n_folds, seed=seed, max_epochs=max_epochs,
              weight_decay=weight_decay)

    if "V1" in checks:
        rep.add(v1_passband_support(recs, band, header_lp=header_lp))
    if "V2" in checks:
        rep.add(v2_protocol_delta(recs, band, model, **kw))
    if "V3" in checks:
        rep.add(v3_artifact_control(recs, band, model, **kw))
    if "V4" in checks:
        rep.add(v4_subband_localisation(recs, band, model, n_sub=n_sub, **kw))
    if "V5" in checks:
        rep.add(v5_excision_control(recs, band, model, stop=stop, **kw))

    if verbose:
        print(rep.render())
    return rep
