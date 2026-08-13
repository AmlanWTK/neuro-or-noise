"""Figure 3 -- the band is mis-specified in width.

(a) V4 as the protocol actually prescribes it: split 30-100 Hz into three
    uniform thirds and refit each. The lowest third alone matches the full
    band on both accuracy and per-subject decisions; the upper two thirds
    carry nothing. 3 seeds, 40-epoch budget.
(b) The same result at the level of individual subjects, using a
    hand-specified 30-45 Hz band (secondary, post-hoc, 25-epoch budget):
    every subject's predicted probability under the narrow model against
    the same subject under the full band.

Design rules carried over from Figs 1-2: one hue; texture rather than a
second hue for the contrasting series; identity encoded by shape AND fill
so it survives greyscale and CVD; reference lines recessive; every number
read from a run record, none typed by hand.
"""
import json, sys
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUNS = sys.argv[1] if len(sys.argv) > 1 else "results/runs"

# (a) BandCheck V4, three seeds, 40 epochs -- the primary protocol result.
SEEDS = ["20260813-083449_bandcheck", "20260813-165955_bandcheck",
         "20260813-182919_bandcheck"]
# (b) the two 25-epoch E2 runs whose per-subject predictions we compare.
RUN_LOW, RUN_FULL = "20260812-225345_e2", "20260812-215110_e2"

INK, MUTED, GRID = "#1b1f24", "#5b6470", "#d7dce2"
HUE = "#2f6f9f"
WASH = "#eef2f6"          # disagreement quadrants; must not compete with the data
MAJORITY = 33 / 63

# --- load (a) ---------------------------------------------------------------
acc, agree, rs, full = [], [], [], []
for run in SEEDS:
    d = json.load(open(f"{RUNS}/{run}/result.json"))
    v4 = [c for c in d["checks"] if c["id"] == "V4"][0]["detail"]
    full.append(v4["full_band_acc"])
    acc.append([sb["acc"] for sb in v4["subbands"]])
    agree.append([sb["agreement"] for sb in v4["subbands"]])
    rs.append([sb["r_with_full"] for sb in v4["subbands"]])
    ranges = [sb["range"] for sb in v4["subbands"]]
acc, agree, rs, full = map(np.array, (acc, agree, rs, full))

# --- load (b) ---------------------------------------------------------------
lo = json.load(open(f"{RUNS}/{RUN_LOW}/result.json"))["P3"][0]["subject_kfold_pred"]
hi = json.load(open(f"{RUNS}/{RUN_FULL}/result.json"))["P3"][0]["subject_kfold_pred"]
assert lo["subjects"] == hi["subjects"] and lo["y"] == hi["y"], "subject order differs"
x = np.array(lo["prob"]); y = np.array(hi["prob"]); ytrue = np.array(lo["y"])
r_sub = stats.pearsonr(x, y)[0]
dx, dy = (x >= .5).astype(int), (y >= .5).astype(int)
agreement = (dx == dy).mean()
disagree = dx != dy
b = int(((dx == ytrue) & (dy != ytrue)).sum()); c = int(((dx != ytrue) & (dy == ytrue)).sum())
p_mcn = stats.binomtest(b, b + c, 0.5).pvalue

# Regions the annotations sit in must actually be empty -- assert rather than
# trust the eye, because the point cloud moves if a run is regenerated.
def occupied(xlo, xhi, ylo, yhi):
    return int(((x >= xlo) & (x <= xhi) & (y >= ylo) & (y <= yhi)).sum())
assert occupied(0, .36, .84, 1) == 0, "legend corner is not empty"
assert occupied(0, .40, .60, .82) == 0, "callout region is not empty"
assert occupied(.58, 1, 0, .36) == 0, "stats-box corner is not empty"

# Height is deliberately tight: at column width this figure competes directly
# with body text for the ICASSP page limit, and panel (b)'s equal aspect makes
# it the tallest object in the paper.
fig, (axa, axb) = plt.subplots(2, 1, figsize=(3.5, 3.95),
                               gridspec_kw=dict(height_ratios=[0.78, 2.0], hspace=0.42))

# ---------------- (a) uniform-third localisation ----------------------------
xs = np.arange(3)
w = 0.34
for i, (vals, off, hatch, fc) in enumerate(
        [(acc, -w / 2, None, HUE), (agree, w / 2, "///", "white")]):
    m, s = vals.mean(0), vals.std(0, ddof=1)
    axa.bar(xs + off, m, width=w, color=fc, edgecolor=HUE if fc == "white" else "white",
            hatch=hatch, linewidth=0.8, zorder=2)
    axa.errorbar(xs + off, m, yerr=s, fmt="none", ecolor=INK, elinewidth=0.9,
                 capsize=2, capthick=0.9, zorder=4)
    axa.scatter(np.repeat(xs + off, len(vals)) + np.tile(np.linspace(-.07, .07, len(vals)), 3),
                vals.T.ravel(), s=4.5, color="white", edgecolor=INK,
                linewidth=0.45, zorder=5)

# Reference lines are labelled in a reserved right margin rather than over the
# plot: at 0.52 the majority line runs straight through the 77-100 Hz bars, and
# any in-panel label collided with them.
axa.axhline(full.mean(), color=MUTED, lw=0.9, ls=(0, (4, 2)), zorder=1)
axa.text(2.62, full.mean(), "full\nband", fontsize=5.8, color=MUTED,
         ha="left", va="center", linespacing=1.2)
axa.axhline(MAJORITY, color=MUTED, lw=0.8, ls=(0, (2, 2)), zorder=1)
axa.text(2.62, MAJORITY, "majority\nclass", fontsize=5.8, color=MUTED,
         ha="left", va="center", linespacing=1.2)

# r with the full band printed above each pair -- the third quantity, as text
# rather than a third bar, because it is a correlation not a subject fraction
for i in range(3):
    axa.text(i, 1.045, f"r={rs.mean(0)[i]:.2f}", fontsize=5.8, color=INK,
             ha="center", va="bottom")

axa.set_xticks(xs)
axa.set_xticklabels([f"{a:.0f}–{b_:.0f}" for a, b_ in ranges], fontsize=6.5)
axa.set_xlabel("uniform sub-band of 30–100 Hz  (Hz)", fontsize=6.8, labelpad=1.5)
axa.set_ylabel("fraction of subjects", fontsize=6.8)
axa.set_ylim(0.35, 1.10)
axa.set_yticks([0.4, 0.6, 0.8, 1.0])
axa.set_xlim(-0.58, 3.10)   # right margin reserved for the reference-line labels
axa.spines["bottom"].set_bounds(-0.58, 2.58)

leg = [plt.Rectangle((0, 0), 1, 1, fc=HUE, ec="white", lw=0.8),
       plt.Rectangle((0, 0), 1, 1, fc="white", ec=HUE, lw=0.8, hatch="///")]
axa.legend(leg, ["accuracy", "agreement with full band"], fontsize=5.9,
           frameon=False, loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=2,
           handlelength=1.1, handleheight=0.85, borderaxespad=0,
           columnspacing=1.0, handletextpad=0.4)
axa.set_title("(a)  a uniform third reproduces the whole band",
              fontsize=7.2, color=INK, pad=17, loc="left")

# ---------------- (b) per-subject agreement scatter -------------------------
# the two quadrants where the models return different decisions
axb.add_patch(plt.Rectangle((0, .5), .5, .5, fc=WASH, ec="none", zorder=0))
axb.add_patch(plt.Rectangle((.5, 0), .5, .5, fc=WASH, ec="none", zorder=0))
axb.plot([0, 1], [0, 1], color=MUTED, lw=0.8, zorder=1)
axb.axvline(.5, color=GRID, lw=0.8, zorder=1)
axb.axhline(.5, color=GRID, lw=0.8, zorder=1)

for lab, mask, mk, fc in [("MDD", ytrue == 1, "o", HUE),
                          ("control", ytrue == 0, "s", "white")]:
    axb.scatter(x[mask], y[mask], marker=mk, s=17, facecolor=fc,
                edgecolor=HUE if fc == "white" else "white", linewidth=0.7,
                zorder=4, label=lab)
# ring the subjects the two models decide differently
axb.scatter(x[disagree], y[disagree], marker="o", s=62, facecolor="none",
            edgecolor=INK, linewidth=0.7, zorder=5)

axb.set_xlim(-0.03, 1.03); axb.set_ylim(-0.03, 1.03)
axb.set_aspect("equal")
axb.set_xticks([0, .5, 1]); axb.set_yticks([0, .5, 1])
axb.set_xlabel("P(MDD),  30–45 Hz model", fontsize=6.8, labelpad=1.5)
axb.set_ylabel("P(MDD),  30–100 Hz model", fontsize=6.8)
axb.legend(fontsize=6, frameon=False, loc="upper left", handletextpad=0.15,
           borderaxespad=0.25, labelspacing=0.25, scatterpoints=1)
# n is stated here rather than as corner counts: 31 of the 63 points overlap in
# the two saturated corners, so a reader tallying markers would come up short.
n_lo = int(((x < .05) & (y < .05)).sum()); n_hi = int(((x > .95) & (y > .95)).sum())
axb.text(.99, .015,
         f"n = {len(x)} subjects\nr = {r_sub:.3f}\n{agreement*100:.1f}% agreement"
         f"\nMcNemar p = {p_mcn:.2f}",
         fontsize=6.2, color=INK, ha="right", va="bottom", linespacing=1.45)
axb.annotate(f"{int(disagree.sum())} subjects decided\ndifferently",
             xy=(x[disagree].min() - 0.025, y[disagree].max() + 0.02),
             xytext=(0.03, 0.80), fontsize=6, color=INK, ha="left", va="top",
             arrowprops=dict(arrowstyle="-", lw=0.6, color=MUTED,
                             shrinkA=2, shrinkB=2))
axb.set_title("(b)  the same subjects, the same decisions",
              fontsize=7.2, color=INK, pad=5, loc="left")

for ax in (axa, axb):
    ax.tick_params(labelsize=6.3, length=2.5, width=0.7, colors=MUTED, pad=1.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_linewidth(0.7); ax.spines[sp].set_color(GRID)
    for t in ax.get_xticklabels() + ax.get_yticklabels():
        t.set_color(INK)

fig.savefig("paper/figs/fig3_subband_agreement.pdf", bbox_inches="tight")
fig.savefig("paper/figs/fig3_subband_agreement.png", dpi=300, bbox_inches="tight")

print("(a) V4 uniform thirds, 3 seeds, 40 epochs")
print(f"    full band  {full.mean():.4f} +/- {full.std(ddof=1):.4f}")
for i, (a_, b_) in enumerate(ranges):
    print(f"    {a_:5.1f}-{b_:5.1f}  acc {acc.mean(0)[i]:.4f}+/-{acc.std(0,ddof=1)[i]:.4f}"
          f"   agree {agree.mean(0)[i]:.4f}+/-{agree.std(0,ddof=1)[i]:.4f}"
          f"   r {rs.mean(0)[i]:.3f}+/-{rs.std(0,ddof=1)[i]:.3f}")
print("(b) hand-specified 30-45 Hz vs 30-100 Hz, seed 0, 25 epochs")
print(f"    subject-level acc  30-45 {(dx==ytrue).mean():.4f}   30-100 {(dy==ytrue).mean():.4f}")
print(f"    r {r_sub:.4f}   agreement {agreement:.4f}   discordant b={b} c={c}   McNemar p={p_mcn:.4f}")
print(f"    corner counts: both<0.05 {n_lo}, both>0.95 {n_hi}")
