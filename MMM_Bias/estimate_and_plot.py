"""
estimate_and_plot.py
--------------------
Reads mmm_data.csv, fits four models, and compares predicted vs actual leads
and recovered channel impact against the known true DGP.

Models
------
  Model 1 -- ARIMA(2,0,0), leads only (no spend). Momentum-only baseline.
  Model 2 -- OLS on 4-week rolling-avg billed DM + digital. Spend only.
  Model 3 -- ARIMAX(2,0,0): AR(2) + rolling-avg DM + digital.
  Model 4 -- FULL "state of the art" MMM stack (Robyn / LightweightMMM style):
               * geometric adstock on each channel, decay tuned by CV
               * Hill saturation (diminishing returns) on each channel
               * Fourier seasonality (annual) + linear trend
               * ridge regression
             This is the model a skeptic can't dismiss for "not even doing X."
             It still gets DM wrong, because none of these techniques fix a
             timing problem that lives in the DATA, not the model.

True DGP:
  Intercept = 40, DM = 3.0/$1K (adstocked), Digital = 2.5/$1K, AR(1) = 0.35

Channel impact is compared on a common "effective leads per $1K" basis:
for the nonlinear Model 4 we measure the model-predicted change in total leads
from adding a fixed increment of spend to a channel, divided by that increment.

Outputs:
  mmm_fit_comparison.png   -- predicted vs actual, one panel per model
  mmm_model4_impact.png    -- effective leads-per-$1K: true vs each model
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.api as sm
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

TRUE = {"dm": 30.0, "digital": 25.0, "ar1": 0.35, "intercept": 400.0}
ROLL = 4

# ------------------------------------------------------------------
# Load data
# ------------------------------------------------------------------
df        = pd.read_csv("mmm_data.csv")
leads     = df["leads"].values
dm_billed = df["dm_spend_billed"].values
digital   = df["digital_spend"].values
weeks     = df["week"].values
N         = len(df)

dm_roll = pd.Series(dm_billed).rolling(window=ROLL, min_periods=1).mean().values

# ==================================================================
# Models 1-3 (as before)
# ==================================================================
m1    = SARIMAX(leads, order=(2, 0, 0), trend="c").fit(disp=False, method="lbfgs", maxiter=500)
pred1 = m1.fittedvalues

X2    = sm.add_constant(np.column_stack([dm_roll, digital]))
m2    = sm.OLS(leads, X2).fit()
pred2 = m2.fittedvalues
dm_m2, dig_m2 = m2.params[1], m2.params[2]

exog3 = pd.DataFrame({"dm_roll": dm_roll, "digital": digital})
m3    = SARIMAX(leads, exog=exog3, order=(2, 0, 0), trend="c").fit(disp=False, method="lbfgs", maxiter=500)
pred3 = m3.fittedvalues
dm_m3  = float(m3.params["dm_roll"])
dig_m3 = float(m3.params["digital"])

# ==================================================================
# Model 4: full MMM transform stack
# ==================================================================
def geometric_adstock(x, decay):
    """Geometric adstock, normalized so total impact == sum(x)."""
    out = np.zeros_like(x, dtype=float)
    for t in range(len(x)):
        out[t] = x[t] + (decay * out[t - 1] if t > 0 else 0.0)
    return out * (1 - decay)

def hill_saturation(x, half):
    """Hill saturation with slope 1: x / (half + x). Diminishing returns."""
    return x / (half + x + 1e-9)

def fourier_terms(n, period, K):
    """K sin/cos pairs at the given period."""
    t = np.arange(n)
    cols = []
    for k in range(1, K + 1):
        cols.append(np.sin(2 * np.pi * k * t / period))
        cols.append(np.cos(2 * np.pi * k * t / period))
    return np.column_stack(cols)

def build_design(decay_dm, decay_dig):
    """Apply adstock + saturation to each channel, add trend + Fourier."""
    dm_ad  = geometric_adstock(dm_billed, decay_dm)
    dig_ad = geometric_adstock(digital,   decay_dig)
    dm_sat  = hill_saturation(dm_ad,  half=np.median(dm_ad[dm_ad > 0]) if np.any(dm_ad > 0) else 1.0)
    dig_sat = hill_saturation(dig_ad, half=np.median(dig_ad))
    trend = np.linspace(0, 1, N)
    fourier = fourier_terms(N, period=52, K=2)   # annual seasonality over 2 yrs
    design = np.column_stack([dm_sat, dig_sat, trend, fourier])
    return design, dm_sat, dig_sat

def cv_r2(design, y, n_folds=5, alpha=1.0):
    """Mean out-of-sample R^2 across contiguous time folds."""
    bounds = np.linspace(0, N, n_folds + 1).astype(int)
    scores = []
    for k in range(n_folds):
        lo, hi = bounds[k], bounds[k + 1]
        te = np.zeros(N, dtype=bool); te[lo:hi] = True
        tr = ~te
        sc = StandardScaler().fit(design[tr])
        ridge = Ridge(alpha=alpha).fit(sc.transform(design[tr]), y[tr])
        pred = ridge.predict(sc.transform(design[te]))
        ss_res = np.sum((y[te] - pred) ** 2)
        ss_tot = np.sum((y[te] - y[te].mean()) ** 2)
        scores.append(1 - ss_res / ss_tot)
    return np.mean(scores)

# --- Tune adstock decays by cross-validation (grid search) ---
decay_grid = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
best = (-np.inf, None, None)
for d_dm in decay_grid:
    for d_dig in decay_grid:
        design, _, _ = build_design(d_dm, d_dig)
        score = cv_r2(design, leads)
        if score > best[0]:
            best = (score, d_dm, d_dig)
best_cv_r2, best_decay_dm, best_decay_dig = best

# --- Refit on full data with tuned decays ---
design, dm_sat, dig_sat = build_design(best_decay_dm, best_decay_dig)
scaler  = StandardScaler().fit(design)
Xs      = scaler.transform(design)
ridge4  = Ridge(alpha=1.0).fit(Xs, leads)
pred4   = ridge4.predict(Xs)

# --- Effective leads per $1K (numerical marginal effect) ---
# Add a fixed increment of spend to a channel, measure predicted lead change.
def effective_per_1k(channel):
    bump = 50.0  # add $50K total to the channel, spread over its active weeks
    dm_b, dig_b = dm_billed.copy(), digital.copy()
    if channel == "dm":
        active = dm_billed > 1.0
        dm_b[active] += bump / active.sum()
    else:
        active = digital > 0
        dig_b[active] += bump / active.sum()
    dm_ad  = geometric_adstock(dm_b,  best_decay_dm)
    dig_ad = geometric_adstock(dig_b, best_decay_dig)
    dm_s  = hill_saturation(dm_ad,  half=np.median(dm_ad[dm_ad > 0]) if np.any(dm_ad > 0) else 1.0)
    dig_s = hill_saturation(dig_ad, half=np.median(dig_ad))
    trend = np.linspace(0, 1, N)
    fourier = fourier_terms(N, 52, 2)
    design_b = np.column_stack([dm_s, dig_s, trend, fourier])
    pred_b   = ridge4.predict(scaler.transform(design_b))
    return (pred_b.sum() - pred4.sum()) / bump

dm_m4  = effective_per_1k("dm")
dig_m4 = effective_per_1k("digital")

# ------------------------------------------------------------------
# Fit statistics
# ------------------------------------------------------------------
def r2(a, f):
    return 1 - np.sum((a - f) ** 2) / np.sum((a - a.mean()) ** 2)
def mape(a, f):
    return np.mean(np.abs((a - f) / a)) * 100

models = [
    ("Model 1 — ARIMA only (2 lags)",            pred1),
    ("Model 2 — OLS (rolling DM + digital)",      pred2),
    ("Model 3 — ARIMAX (2 lags + spend)",         pred3),
    ("Model 4 — Full MMM (adstock+saturation+seasonality, CV)", pred4),
]

print("=" * 70)
print("FIT: predicted vs actual")
print("=" * 70)
for name, pred in models:
    print(f"  {name:56s}  R²={r2(leads, pred):.3f}  MAPE={mape(leads, pred):.1f}%")

print(f"\nModel 4 tuned adstock decays (via CV): DM={best_decay_dm}, digital={best_decay_dig}")
print(f"Model 4 mean CV R²: {best_cv_r2:.3f}")

print("\nEffective leads per $1K  (true vs each model):")
print(f"  {'':10s}{'DM':>10}{'Digital':>10}")
print(f"  {'True':10s}{TRUE['dm']:>10.2f}{TRUE['digital']:>10.2f}")
print(f"  {'Model 2':10s}{dm_m2:>10.2f}{dig_m2:>10.2f}")
print(f"  {'Model 3':10s}{dm_m3:>10.2f}{dig_m3:>10.2f}")
print(f"  {'Model 4':10s}{dm_m4:>10.2f}{dig_m4:>10.2f}")

# ------------------------------------------------------------------
# Plot 1: predicted vs actual, 4 panels
# ------------------------------------------------------------------
COLORS = {"actual": "#378ADD", "pred": "#D85A30", "bg": "#F8F8F6"}
plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#E0E0D8", "grid.linewidth": 0.5,
    "axes.facecolor": "#FFFFFF", "figure.facecolor": COLORS["bg"],
})

fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True, sharey=True)
fig.suptitle("Predicted vs. actual leads — true impact: DM = 3.0/$1K, digital = 2.5/$1K",
             fontsize=12.5, fontweight="bold", y=0.98, color="#1a1a1a")
for ax, (name, pred) in zip(axes.flat, models):
    ax.plot(weeks, leads, color=COLORS["actual"], lw=1.8, label="Actual", zorder=3)
    ax.plot(weeks, pred,  color=COLORS["pred"], lw=1.4, linestyle="--", label="Predicted", zorder=2)
    short = name.split("—")[0].strip() + " — " + name.split("—")[1].strip()[:42]
    ax.set_title(f"{short}\nR²={r2(leads, pred):.2f}  ·  MAPE={mape(leads, pred):.1f}%",
                 fontsize=9, loc="left", pad=6, color="#333")
    ax.legend(fontsize=8.5, frameon=False, loc="upper left")
for ax in axes[-1]:
    ax.set_xlabel("Week")
for ax in axes[:, 0]:
    ax.set_ylabel("Leads")
fig.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig("mmm_fit_comparison.png", dpi=150, bbox_inches="tight")
print("\nSaved mmm_fit_comparison.png")
plt.close()

# ------------------------------------------------------------------
# Plot 2: effective leads per $1K -- true vs all models
# ------------------------------------------------------------------
fig2, ax = plt.subplots(figsize=(10, 5.5))
channels = ["Direct mail", "Digital"]
x = np.arange(2)
w = 0.2
series = [
    ("True DGP",  [TRUE["dm"], TRUE["digital"]], "#0F6E56"),
    ("Model 2",   [dm_m2, dig_m2],               "#B8B7AE"),
    ("Model 3",   [dm_m3, dig_m3],               "#888780"),
    ("Model 4 (full MMM)", [dm_m4, dig_m4],      "#D85A30"),
]
for i, (label, vals, color) in enumerate(series):
    ax.bar(x + (i - 1.5) * w, vals, w, label=label, color=color,
           alpha=0.9 if label.startswith("True") else 0.85)

ax.axhline(0, color="#cccccc", lw=0.8)
ax.set_xticks(x); ax.set_xticklabels(channels, fontsize=11)
ax.set_ylabel("Effective leads per $1K spent")
ax.set_title("Even the full state-of-the-art MMM gets direct mail backwards\n"
             "Adstock + saturation + seasonality + cross-validation — and DM still looks like the weaker channel",
             fontsize=11.5, fontweight="bold", loc="left", pad=10, color="#1a1a1a")
ax.legend(fontsize=9, frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.08))

# shade wrong-sign region
ymin, ymax = ax.get_ylim()
if ymin < 0:
    ax.axhspan(ymin, 0, color="#FAECE7", alpha=0.45, zorder=0)
    ax.text(0.0, ymin * 0.5, "wrong-sign territory", fontsize=8.5,
            color="#993C1D", style="italic", ha="center")

# annotate true vs model4 for DM
ax.annotate(f"True: {TRUE['dm']:.1f}", xy=(x[0] - 1.5*w, TRUE['dm']),
            xytext=(x[0]-1.5*w, TRUE['dm']+0.25), ha="center", fontsize=8.5,
            color="#0F6E56", fontweight="bold")
ax.annotate(f"Model 4: {dm_m4:+.2f}", xy=(x[0]+1.5*w, dm_m4),
            xytext=(x[0]+1.5*w, 0.3), ha="center", fontsize=8.5,
            color="#993C1D", fontweight="bold")

fig2.tight_layout()
fig2.savefig("mmm_model4_impact.png", dpi=150, bbox_inches="tight")
print("Saved mmm_model4_impact.png")
plt.close()
