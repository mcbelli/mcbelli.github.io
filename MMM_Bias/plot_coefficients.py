"""
plot_coefficients.py
--------------------
Reads mmm_data.csv, fits models, and produces a focused coefficient
comparison chart: true DGP vs Model 2 (OLS) vs Model 3 (ARIMAX),
with 95% confidence intervals shown as error bars.
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import statsmodels.api as sm
from statsmodels.tsa.statespace.sarimax import SARIMAX

# ------------------------------------------------------------------
# 1. Load data and fit models
# ------------------------------------------------------------------
df       = pd.read_csv("mmm_data.csv")
leads    = df["leads"].values
dm_billed= df["dm_spend_billed"].values
digital  = df["digital_spend"].values

# 4-week rolling average of billed DM -- the same regressor used elsewhere
dm_roll = pd.Series(dm_billed).rolling(window=4, min_periods=1).mean().values

# Model 2: OLS, spend only (rolling DM + digital)
X2 = sm.add_constant(np.column_stack([dm_roll, digital]))
m2 = sm.OLS(leads, X2).fit()
m2_ci = m2.conf_int()   # shape (3, 2): rows = const, dm, digital

# Model 3: ARIMAX(2,0,0) on rolling DM + digital
exog3 = pd.DataFrame({"dm_roll": dm_roll, "digital_spend": digital})
m3    = SARIMAX(leads, exog=exog3, order=(2, 0, 0), trend="c").fit(disp=False, method="lbfgs", maxiter=500)
m3_ci = m3.conf_int()

# ------------------------------------------------------------------
# 2. Collect values and CIs for each channel x model
# ------------------------------------------------------------------
TRUE = {"dm": 30.0, "digital": 25.0}

data = {
    "Direct mail": {
        "true":  TRUE["dm"],
        "m2":    m2.params[1],
        "m2_lo": m2_ci[1][0],
        "m2_hi": m2_ci[1][1],
        "m3":    float(m3.params["dm_roll"]),
        "m3_lo": float(m3_ci.loc["dm_roll", 0]),
        "m3_hi": float(m3_ci.loc["dm_roll", 1]),
    },
    "Digital": {
        "true":  TRUE["digital"],
        "m2":    m2.params[2],
        "m2_lo": m2_ci[2][0],
        "m2_hi": m2_ci[2][1],
        "m3":    float(m3.params["digital_spend"]),
        "m3_lo": float(m3_ci.loc["digital_spend", 0]),
        "m3_hi": float(m3_ci.loc["digital_spend", 1]),
    },
}

# ------------------------------------------------------------------
# 3. Plot
# ------------------------------------------------------------------
COLORS = {
    "true": "#0F6E56",
    "m2":   "#888780",
    "m3":   "#D85A30",
    "zero": "#cccccc",
}

plt.rcParams.update({
    "font.family":      "sans-serif",
    "font.size":        11,
    "axes.spines.top":  False,
    "axes.spines.right":False,
    "axes.grid":        True,
    "grid.color":       "#E0E0D8",
    "grid.linewidth":   0.6,
    "axes.facecolor":   "#FFFFFF",
    "figure.facecolor": "#F8F8F6",
})

fig, axes = plt.subplots(1, 2, figsize=(11, 6), sharey=False)
fig.suptitle(
    "Estimated vs. true channel coefficients\n(leads per $1K spent)",
    fontsize=13, fontweight="bold", y=1.01, color="#1a1a1a"
)
fig.text(
    0.5, 0.97,
    "Same total spend. Same true impact. Billing lag alone flips the model's verdict.",
    ha="center", fontsize=10, color="#555550"
)

channels = ["Direct mail", "Digital"]
x        = np.array([0])   # single group per panel
w        = 0.18

for ax, channel in zip(axes, channels):
    d = data[channel]

    # True value -- horizontal reference line
    ax.axhline(d["true"], color=COLORS["true"], linewidth=2.0,
               linestyle="--", zorder=1, label=f'True DGP ({d["true"]})')

    # Model 2 bar + CI
    m2_err = [[d["m2"] - d["m2_lo"]], [d["m2_hi"] - d["m2"]]]
    ax.bar(x - w, d["m2"], w * 1.6, color=COLORS["m2"], alpha=0.85,
           zorder=2, label="Model 2 – OLS")
    ax.errorbar(x - w, d["m2"], yerr=m2_err, fmt="none",
                color="#444", capsize=6, capthick=1.5, linewidth=1.5, zorder=3)

    # Model 3 bar + CI
    m3_err = [[d["m3"] - d["m3_lo"]], [d["m3_hi"] - d["m3"]]]
    ax.bar(x + w, d["m3"], w * 1.6, color=COLORS["m3"], alpha=0.85,
           zorder=2, label='Model 3 – ARIMAX ("best fit")')
    ax.errorbar(x + w, d["m3"], yerr=m3_err, fmt="none",
                color="#444", capsize=6, capthick=1.5, linewidth=1.5, zorder=3)

    # Zero line
    ax.axhline(0, color=COLORS["zero"], linewidth=0.8, zorder=0)

    # Annotations
    ax.annotate(f'True: {d["true"]}', xy=(0.97, d["true"]),
                xycoords=("axes fraction", "data"),
                ha="right", va="bottom", fontsize=9,
                color=COLORS["true"], fontweight="bold")
    ax.annotate(f'{d["m2"]:+.2f}', xy=(x[0] - w, d["m2"]),
                ha="center", va="bottom" if d["m2"] >= 0 else "top",
                fontsize=9, color="#444",
                xytext=(0, 4 if d["m2"] >= 0 else -4), textcoords="offset points")
    ax.annotate(f'{d["m3"]:+.2f}', xy=(x[0] + w, d["m3"]),
                ha="center", va="bottom" if d["m3"] >= 0 else "top",
                fontsize=9, color="#444",
                xytext=(0, 4 if d["m3"] >= 0 else -4), textcoords="offset points")

    ax.set_title(channel, fontsize=12, fontweight="500", pad=10)
    ax.set_xticks([])
    ax.set_ylabel("Leads per $1K spent")
    ax.legend(fontsize=8.5, frameon=False, loc="upper right")

# Shade the "wrong sign" region on DM panel
dm_ax = axes[0]
ymin, ymax = dm_ax.get_ylim()
dm_ax.axhspan(ymin, 0, color="#FAECE7", alpha=0.4, zorder=0)
dm_ax.text(0.5, 0.08, "← wrong sign territory",
           transform=dm_ax.transAxes, ha="center",
           fontsize=8.5, color="#993C1D", style="italic")

fig.tight_layout(pad=1.5)

out = "mmm_coefficients.png"
fig.savefig(out, dpi=150, bbox_inches="tight")
print(f"Saved {out}")
plt.close()
