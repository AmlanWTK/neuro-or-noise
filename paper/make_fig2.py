"""Figure 2 -- what the reported accuracy is actually made of.

(a) the split rule alone costs ~0.11, and neither protocol reaches the
    published 99.60%
(b) a five-parameter signal-quality baseline matches the eleven-layer CNN

Same design rules as Fig 1: one hue, texture not colour for the special case,
individual seed points shown rather than summary statistics alone, recessive
reference lines.
"""
import json, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUNS = sys.argv[1] if len(sys.argv) > 1 else "results/runs"
SEEDS = ["20260813-083449_bandcheck", "20260813-165955_bandcheck", "20260813-182919_bandcheck"]
INK, MUTED, GRID = "#1b1f24", "#5b6470", "#d7dce2"
HUE = "#2f6f9f"
REPORTED, MAJORITY = 0.9960, 33 / 63

v2, v3m, v3a = [], [], []
for r in SEEDS:
    d = json.load(open(f"{RUNS}/{r}/result.json"))
    g = lambda cid: [c for c in d["checks"] if c["id"] == cid][0]["detail"]
    a = g("V2"); v2.append((a["epoch_random"], a["subject_wise"]))
    b = g("V3"); v3m.append(b["model_acc"]); v3a.append(b["artifact_acc"])
v2 = np.array(v2); v3m = np.array(v3m); v3a = np.array(v3a)
delta = v2[:, 0] - v2[:, 1]

fig, (axa, axb) = plt.subplots(1, 2, figsize=(3.5, 2.5),
                               gridspec_kw=dict(wspace=0.55))

def bars(ax, vals, labels, ylim):
    x = np.arange(len(vals))
    for xi, v in zip(x, vals):
        ax.bar(xi, v.mean(), width=0.55, color=HUE, edgecolor="white",
               linewidth=0.8, zorder=2)
        ax.errorbar(xi, v.mean(), yerr=v.std(ddof=1), fmt="none", ecolor=INK,
                    elinewidth=0.9, capsize=2, capthick=0.9, zorder=4)
        ax.scatter(np.full(len(v), xi) + np.linspace(-.10, .10, len(v)), v,
                   s=5, color="white", edgecolor=INK, linewidth=0.5, zorder=5)
        ax.text(xi, v.mean() - 0.035, f"{v.mean():.3f}", ha="center", va="top",
                fontsize=6.2, color="white", zorder=6)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=6.5)
    ax.set_ylim(*ylim)
    ax.axhline(MAJORITY, color=MUTED, lw=0.8, ls=(0, (2, 2)), zorder=1)

# ---- (a) protocol ----
bars(axa, [v2[:, 0], v2[:, 1]], ["epoch-\nrandom", "subject-\nwise"], (0.4, 1.06))
axa.axhline(REPORTED, color=INK, lw=0.9, ls=(0, (4, 2)))
axa.text(1.45, REPORTED, "reported 0.996", fontsize=6, color=INK,
         ha="right", va="bottom")
top = v2[:, 0].mean()
axa.annotate("", xy=(0.32, top), xytext=(0.32, v2[:, 1].mean()),
             arrowprops=dict(arrowstyle="<->", lw=0.8, color=INK))
axa.text(0.38, (top + v2[:, 1].mean()) / 2, f"Δ={delta.mean():.3f}\n±{delta.std(ddof=1):.3f}",
         fontsize=6.2, color=INK, va="center")
# right-aligned inside the axes; at the left edge it collided with the 0.5 tick
axa.text(1.45, MAJORITY + 0.012, "majority", fontsize=5.8, color=MUTED,
         ha="right", va="bottom")
axa.set_ylabel("Epoch-level accuracy", fontsize=7)
axa.set_title("(a) the split rule", fontsize=7.5, color=INK, loc="left", pad=4)

# ---- (b) model vs baseline ----
bars(axb, [v3m, v3a], ["Ex-1DCNN\n(11 layers)", "5 scalars\n(logistic)"], (0.4, 1.06))
axb.annotate("", xy=(0, 0.95), xytext=(1, 0.95),
             arrowprops=dict(arrowstyle="-", lw=0.7, color=MUTED))
axb.text(0.5, 0.965, "McNemar $p\\geq$0.625 (n.s.)", ha="center", fontsize=6,
         color=MUTED)
axb.text(1.45, MAJORITY + 0.012, "majority", fontsize=5.8, color=MUTED,
         ha="right", va="bottom")
axb.set_ylabel("Subject-level accuracy", fontsize=7)
axb.set_title("(b) the model", fontsize=7.5, color=INK, loc="left", pad=4)

for ax in (axa, axb):
    ax.tick_params(labelsize=6.5, colors=MUTED, length=2)
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"): ax.spines[sp].set_color(GRID)
    ax.grid(axis="y", color=GRID, lw=0.5, zorder=0); ax.set_axisbelow(True)
    ax.yaxis.label.set_color(INK)

fig.savefig("paper/figs/fig2_protocol_and_baseline.pdf", bbox_inches="tight")
fig.savefig("paper/figs/fig2_protocol_and_baseline.png", dpi=300, bbox_inches="tight")
print("wrote paper/figs/fig2_protocol_and_baseline.{pdf,png}")
print(f"  epoch-random  {v2[:,0].mean():.4f} +/- {v2[:,0].std(ddof=1):.4f}")
print(f"  subject-wise  {v2[:,1].mean():.4f} +/- {v2[:,1].std(ddof=1):.4f}")
print(f"  delta         {delta.mean():.4f} +/- {delta.std(ddof=1):.4f}")
print(f"  CNN           {v3m.mean():.4f} +/- {v3m.std(ddof=1):.4f}")
print(f"  5 scalars     {v3a.mean():.4f} +/- {v3a.std(ddof=1):.4f}")
