"""Figure 1 -- the band decomposition. Built from run records, not hand-entered.

Design notes (print figure, IEEE single column):
  * ONE hue. This is a single series, so no legend box is needed for the bars
    and no categorical palette is involved -- there is no adjacent-pair CVD
    risk to validate. Identity is carried by the axis labels.
  * The never-recorded region is marked with TEXTURE, not a second colour, so
    the figure survives greyscale printing and colour-vision deficiency.
  * Direct value labels on all four bars (only four -- selective labelling is
    for dense charts).
  * Majority-class baseline as a recessive dashed reference, not a series.
"""
import json, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

RUNS = sys.argv[1] if len(sys.argv) > 1 else "results/runs"
SEEDS = ["20260813-083449_bandcheck", "20260813-165955_bandcheck", "20260813-182919_bandcheck"]
E2D = "20260809-104431_e2d"

INK, MUTED, GRID = "#1b1f24", "#5b6470", "#d7dce2"
HUE, HUE_DEAD = "#2f6f9f", "#9fb8cc"     # one hue, light step for the dead band
LOWPASS, EMP_EDGE, MAJORITY = 80.0, 56.0, 33 / 63

# ---- data, straight from the run records --------------------------------
sub, full = {}, []
for r in SEEDS:
    d = json.load(open(f"{RUNS}/{r}/result.json"))
    v4 = [c for c in d["checks"] if c["id"] == "V4"][0]["detail"]
    full.append(v4["full_band_acc"])
    for b in v4["subbands"]:
        sub.setdefault(tuple(b["range"]), []).append(b["acc"])
rows = [(f"{lo:.0f}–{hi:.0f}", np.mean(v), np.std(v, ddof=1), lo, hi)
        for (lo, hi), v in sorted(sub.items())]
full_m, full_s = np.mean(full), np.std(full, ddof=1)

psd = json.load(open(f"{RUNS}/{E2D}/result.json"))["psd"]
f = np.array(psd["freqs"]); mdd = np.array(psd["mdd_median"]); hc = np.array(psd["hc_median"])

fig, (axa, axb) = plt.subplots(
    2, 1, figsize=(3.5, 4.3), gridspec_kw=dict(height_ratios=[1, 1.15], hspace=0.55))

# ---- (a) spectrum, with the nominal band and the acquisition edge --------
m = (f >= 1) & (f <= 110)
axa.semilogy(f[m], mdd[m], color=HUE, lw=1.2, label="MDD")
axa.semilogy(f[m], hc[m], color=MUTED, lw=1.2, ls=(0, (3, 1.5)), label="HC")
axa.axvspan(LOWPASS, 100, facecolor="none", edgecolor=HUE_DEAD, hatch="////", lw=0.0, zorder=0)
axa.axvline(LOWPASS, color=INK, lw=0.9)
# NB: keep x in DATA coords. An earlier version used axes-fraction for x with a
# value of 62, which placed the text 62 axis-widths off-canvas and expanded the
# tight bbox to ~50,000 px.
axa.text(LOWPASS - 3, 0.30, "80 Hz\nlow-pass\n(header)", transform=axa.get_xaxis_transform(),
         fontsize=6, color=INK, ha="right", va="center", linespacing=1.2)
axa.axvline(EMP_EDGE, color=MUTED, lw=0.8, ls=(0, (1, 2)))
axa.text(EMP_EDGE - 2, 0.72, "56 Hz\nnoise floor", transform=axa.get_xaxis_transform(),
         fontsize=6, color=MUTED, ha="right", va="center", linespacing=1.2)
axa.annotate("", xy=(30, 1.02), xytext=(100, 1.02), xycoords=("data", "axes fraction"),
             textcoords=("data", "axes fraction"),
             arrowprops=dict(arrowstyle="|-|,widthA=0.3,widthB=0.3", lw=0.8, color=INK))
axa.text(65, 1.06, "nominal “gamma” band", transform=axa.get_xaxis_transform(),
         ha="center", fontsize=6.5, color=INK)
axa.set_xlabel("Frequency (Hz)", fontsize=7)
axa.set_ylabel("PSD (median)", fontsize=7)
axa.set_xlim(1, 110)
axa.legend(fontsize=6, frameon=False, loc="lower left", handlelength=1.6)
axa.set_title("(a) The band runs to 100 Hz; signal ends at 56 Hz",
              fontsize=7.5, color=INK, pad=14, loc="left")

# ---- (b) sub-band accuracy ----------------------------------------------
y = np.arange(len(rows) + 1)[::-1]
labels = [r[0] for r in rows] + ["30–100\n(full)"]
means = [r[1] for r in rows] + [full_m]
sds = [r[2] for r in rows] + [full_s]
# the top third is 86% above the acquisition edge -> texture it
dead = [r[3] >= LOWPASS - 5 for r in rows] + [False]

for yi, mu, sd, dd in zip(y, means, sds, dead):
    axb.barh(yi, mu, height=0.62, color=(HUE_DEAD if dd else HUE),
             hatch=("////" if dd else None), edgecolor="white", linewidth=0.8, zorder=2)
    axb.errorbar(mu, yi, xerr=sd, fmt="none", ecolor=INK, elinewidth=0.9,
                 capsize=2, capthick=0.9, zorder=3)
    axb.text(mu + sd + 0.015, yi, f"{mu:.3f}", va="center", fontsize=6.5, color=INK)

axb.axvline(MAJORITY, color=MUTED, lw=0.9, ls=(0, (2, 2)), zorder=1)
# place inside the axes, right of the line -- above the axes collides with the title
axb.text(MAJORITY + 0.012, 0.02, "majority", transform=axb.get_xaxis_transform(),
         fontsize=6, color=MUTED, ha="left", va="bottom")
axb.set_yticks(y); axb.set_yticklabels(labels, fontsize=6.8)
axb.set_ylim(y[-1] - 0.95, y[0] + 0.5)
axb.set_xlabel("Subject-level accuracy (mean ± s.d., 3 seeds)", fontsize=7)
axb.set_xlim(0, 1.05)
axb.set_title("(b) 30–53 Hz alone exceeds the full band",
              fontsize=7.5, color=INK, pad=6, loc="left")
axb.legend(handles=[Patch(facecolor=HUE_DEAD, hatch="////", edgecolor="white",
                          label="86% above the 80 Hz edge")],
           fontsize=6, frameon=False, loc="upper center",
           bbox_to_anchor=(0.5, -0.30))

for ax in (axa, axb):
    ax.tick_params(labelsize=6.5, colors=MUTED, length=2)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(GRID)
axb.grid(axis="x", color=GRID, lw=0.5, zorder=0)
axb.set_axisbelow(True)

fig.savefig("paper/figs/fig1_band_decomposition.pdf", bbox_inches="tight")
fig.savefig("paper/figs/fig1_band_decomposition.png", dpi=300, bbox_inches="tight")
print("wrote paper/figs/fig1_band_decomposition.{pdf,png}")
for lab, mu, sd in zip(labels, means, sds):
    print(f"  {lab.replace(chr(10),' '):<14} {mu:.4f} +/- {sd:.4f}")
