"""
plot_explainer.py
-----------------
Two explanatory visuals for a non-technical audience:

  Figure 1 (mmm_timing.png):
      A timeline showing how a direct-mail drop in one week is not recorded
      until the invoice is billed 3-5 weeks later, while digital is recorded
      the same week. Illustrates WHY the model struggles with DM.

  Figure 2 (mmm_smearing.png):
      Three series over the 104 weeks --
        (a) actual DM activity (drop weeks),
        (b) DM as billed (shifted later),
        (c) billed DM smoothed with a 4-week rolling average.
      Shows how the practitioner's rolling-average fix spreads the spikes out.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

df        = pd.read_csv("mmm_data.csv")
weeks     = df["week"].values
dm_actual = df["dm_spend_actual"].values
dm_billed = df["dm_spend_billed"].values
dm_roll   = pd.Series(dm_billed).rolling(window=4, min_periods=1).mean().values

COLORS = {
    "actual":  "#0F6E56",   # green  -- the truth (when mail dropped)
    "billed":  "#D85A30",   # orange -- when it was recorded
    "roll":    "#185FA5",   # blue   -- the rolling-average fix
    "digital": "#888780",
    "bg":      "#F8F8F6",
}

plt.rcParams.update({
    "font.family":       "sans-serif",
    "font.size":         11,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "grid.color":        "#E0E0D8",
    "grid.linewidth":    0.5,
    "axes.facecolor":    "#FFFFFF",
    "figure.facecolor":  COLORS["bg"],
})

# ==================================================================
# FIGURE 1 -- Timing concept
# ==================================================================
fig1, ax = plt.subplots(figsize=(11, 4.8))
ax.set_title("Why direct mail confuses the model: it's recorded weeks after it works",
             fontsize=13, fontweight="bold", pad=14, color="#1a1a1a", loc="left")

# Two lanes: digital (top), direct mail (bottom)
y_dig, y_dm = 2.0, 1.0
ax.set_xlim(0, 13)
ax.set_ylim(0.3, 2.7)

# Week gridlines
for wk in range(1, 13):
    ax.axvline(wk, color="#E8E8E0", linewidth=0.8, zorder=0)
ax.set_xticks(range(1, 13))
ax.set_xticklabels([f"Wk {w}" for w in range(1, 13)], fontsize=9)
ax.set_yticks([y_dm, y_dig])
ax.set_yticklabels(["Direct\nmail", "Digital"], fontsize=11, fontweight="500")

# Digital: spend and effect both in week 4 and week 8
for wk in [4, 8]:
    ax.scatter(wk, y_dig, s=320, color=COLORS["digital"], zorder=3, edgecolor="white", linewidth=1.5)
    ax.annotate("spent &\nrecorded", (wk, y_dig), ha="center", va="center",
                fontsize=7.5, color="white", fontweight="bold", zorder=4)
ax.annotate("Digital: spend is recorded the same week it happens  →  model sees it correctly",
            (0.5, y_dig + 0.42), fontsize=9, color=COLORS["digital"], fontweight="500")

# Direct mail: drop in week 3, billed week 8 (lag 5); drop week 7, billed week 10 (lag 3)
drops  = [(3, 8), (7, 10)]
for drop_wk, bill_wk in drops:
    # drop marker (green, when it actually drives leads)
    ax.scatter(drop_wk, y_dm, s=320, color=COLORS["actual"], zorder=3, edgecolor="white", linewidth=1.5)
    ax.annotate("mail\ndrops", (drop_wk, y_dm), ha="center", va="center",
                fontsize=7.5, color="white", fontweight="bold", zorder=4)
    # billed marker (orange, when it's recorded)
    ax.scatter(bill_wk, y_dm, s=320, color=COLORS["billed"], zorder=3, edgecolor="white", linewidth=1.5)
    ax.annotate("billed", (bill_wk, y_dm), ha="center", va="center",
                fontsize=7.5, color="white", fontweight="bold", zorder=4)
    # arrow from drop to billed
    arr = FancyArrowPatch((drop_wk + 0.18, y_dm), (bill_wk - 0.18, y_dm),
                          arrowstyle="-|>", mutation_scale=14,
                          color="#B0651F", linewidth=1.6, linestyle=(0, (4, 2)),
                          zorder=2)
    ax.add_patch(arr)
    ax.annotate(f"{bill_wk - drop_wk}-week billing lag",
                ((drop_wk + bill_wk) / 2, y_dm - 0.26), ha="center",
                fontsize=8, color="#B0651F", style="italic")

ax.annotate("Direct mail: leads are driven when the mail DROPS (green),\n"
            "but the spend isn't recorded until it's BILLED weeks later (orange)",
            (0.5, y_dm + 0.40), fontsize=9, color=COLORS["actual"], fontweight="500")

ax.text(0.5, 0.42,
        "The model is handed the orange dates. It tries to match leads to spend that, on paper, happened weeks after the leads did.",
        fontsize=9, color="#993C1D", style="italic")

fig1.tight_layout()
fig1.savefig("mmm_timing.png", dpi=150, bbox_inches="tight")
print("Saved mmm_timing.png")
plt.close()

# ==================================================================
# FIGURE 2 -- Smearing: actual vs billed vs rolling average
# ==================================================================
fig2, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True, sharey=True)
fig2.suptitle("What the rolling-average 'fix' actually does to the direct-mail signal",
              fontsize=13, fontweight="bold", y=0.98, color="#1a1a1a")

series = [
    (axes[0], dm_actual, COLORS["actual"],
     "1. Actual direct-mail activity — sharp spikes in the weeks mail really dropped (the truth)"),
    (axes[1], dm_billed, COLORS["billed"],
     "2. Direct mail as billed — same spikes, but shifted 3–5 weeks later (what the model is given)"),
    (axes[2], dm_roll, COLORS["roll"],
     "3. Billed spend, 4-week rolling average — the practitioner's fix: spikes flattened and spread out"),
]

for ax, data, color, title in series:
    ax.fill_between(weeks, data, color=color, alpha=0.22, zorder=1)
    ax.plot(weeks, data, color=color, lw=1.6, zorder=2)
    ax.set_title(title, fontsize=9.5, loc="left", pad=5, color="#333")
    ax.set_ylabel("DM spend\n($K)", fontsize=9)

axes[-1].set_xlabel("Week")
fig2.text(0.5, 0.005,
          "The rolling average smooths the billed spikes — but it's smoothing data that's already in the wrong place. "
          "It spreads a mis-timed signal across even more weeks.",
          ha="center", fontsize=9, color="#993C1D", style="italic")

fig2.tight_layout(rect=[0, 0.03, 1, 0.96])
fig2.savefig("mmm_smearing.png", dpi=150, bbox_inches="tight")
print("Saved mmm_smearing.png")
plt.close()
