"""
shift_analysis.py
-----------------
Grounds the budget-shift test in concrete levels for a specific 10-week window.

Scenario: move $20K out of direct mail and into digital over a 10-week window
(~$2K/week, against a ~$5K/week baseline in each channel).

For that window we report, in LEVELS (not just deltas):
  * average weekly spend per channel, before and after the shift
  * total leads that actually occurred (no shift)
  * total leads the MODEL predicts the shift would produce
  * total leads the shift would TRULY produce (from the DGP)

Counterfactuals are exact:
  * True side: the DGP is leads[t] = det[t] + 0.35*leads[t-1] + noise[t].
    Changing spend changes det[t]; the noise cancels in the difference, so the
    counterfactual delta d[t] = ddet[t] + 0.35*d[t-1] is exact. True level =
    actual leads + d[t].
  * Model side: cutting actual DM is re-billed using the stored per-week lag,
    re-smoothed (4-wk rolling avg), and pushed through the fitted model's
    coefficients and AR(2) structure. Predicted level = actual leads + model d[t].
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.statespace.sarimax import SARIMAX

# ---- scenario settings -------------------------------------------------
WIN_START, WIN_LEN = 51, 10          # weeks 51..60 (1-indexed)
SHIFT_TOTAL        = 20.0            # $20K moved DM -> digital
ROLL               = 4

TRUE = {"intercept": 400.0, "dm": 30.0, "digital": 25.0, "ar1": 0.35, "decay": 0.5}

# ---- load --------------------------------------------------------------
df        = pd.read_csv("mmm_data.csv")
leads     = df["leads"].values
dm_actual = df["dm_spend_actual"].values
dm_billed = df["dm_spend_billed"].values
digital   = df["digital_spend"].values
lag       = df["dm_billing_lag"].values.astype(int)
N         = len(df)

w0 = WIN_START - 1
w1 = w0 + WIN_LEN
win = slice(w0, w1)

# ---- build the shifted spend ------------------------------------------
# Digital: add evenly across the window (+$2K/week).
digital_shift = digital.copy()
digital_shift[win] += SHIFT_TOTAL / WIN_LEN

# DM: cut $20K from the active weeks inside the window, proportionally.
dm_actual_shift = dm_actual.copy()
active_in_win = np.where(dm_actual[win] > 5)[0] + w0
dm_in_win = dm_actual[active_in_win].sum()
scale = (dm_in_win - SHIFT_TOTAL) / dm_in_win      # proportional reduction
dm_actual_shift[active_in_win] = dm_actual[active_in_win] * scale

# ---- spend summary -----------------------------------------------------
def avg_wk(arr):  return arr[win].mean()
def tot(arr):     return arr[win].sum()

print("=" * 66)
print(f"SHIFT WINDOW: weeks {WIN_START}-{WIN_START+WIN_LEN-1}  |  move ${SHIFT_TOTAL:.0f}K  DM -> digital")
print("=" * 66)
print(f"  DM active weeks in window: {[a+1 for a in active_in_win]}  (total ${dm_in_win:.1f}K)")
print()
print(f"  {'':12s}{'avg $/wk BEFORE':>18}{'avg $/wk AFTER':>18}")
print(f"  {'Direct mail':12s}{avg_wk(dm_actual):>18.2f}{avg_wk(dm_actual_shift):>18.2f}")
print(f"  {'Digital':12s}{avg_wk(digital):>18.2f}{avg_wk(digital_shift):>18.2f}")
print()
print(f"  {'':12s}{'total $ BEFORE':>18}{'total $ AFTER':>18}")
print(f"  {'Direct mail':12s}{tot(dm_actual):>18.1f}{tot(dm_actual_shift):>18.1f}")
print(f"  {'Digital':12s}{tot(digital):>18.1f}{tot(digital_shift):>18.1f}")
print(f"  {'Combined':12s}{tot(dm_actual)+tot(digital):>18.1f}{tot(dm_actual_shift)+tot(digital_shift):>18.1f}")

# ---- TRUE counterfactual (exact) --------------------------------------
def adstock(x, d):
    out = np.zeros_like(x, float)
    for t in range(len(x)):
        out[t] = x[t] + (d * out[t-1] if t > 0 else 0.0)
    return out * (1 - d)

dm_ad_base  = adstock(dm_actual,       TRUE["decay"])
dm_ad_shift = adstock(dm_actual_shift, TRUE["decay"])

ddet = TRUE["dm"] * (dm_ad_shift - dm_ad_base) + TRUE["digital"] * (digital_shift - digital)
d_true = np.zeros(N)
for t in range(N):
    d_true[t] = ddet[t] + (TRUE["ar1"] * d_true[t-1] if t > 0 else 0.0)

true_leads_shift = leads + d_true

# ---- MODEL counterfactual (Model 3: ARIMAX(2) on rolling DM + digital) -
dm_roll_base = pd.Series(dm_billed).rolling(ROLL, min_periods=1).mean().values
exog = pd.DataFrame({"dm_roll": dm_roll_base, "digital": digital})
m3 = SARIMAX(leads, exog=exog, order=(2,0,0), trend="c").fit(disp=False, method="lbfgs", maxiter=500)
dm_c, dig_c = float(m3.params["dm_roll"]), float(m3.params["digital"])
ar1_c, ar2_c = float(m3.params["ar.L1"]), float(m3.params["ar.L2"])

# Re-bill the shifted DM using the stored per-week lag, then re-smooth.
dm_billed_shift = np.zeros(N)
for t in range(N):
    b = t + lag[t]
    if b < N:
        dm_billed_shift[b] += dm_actual_shift[t]
dm_roll_shift = pd.Series(dm_billed_shift).rolling(ROLL, min_periods=1).mean().values

mdet = dm_c * (dm_roll_shift - dm_roll_base) + dig_c * (digital_shift - digital)
d_mod = np.zeros(N)
for t in range(N):
    ar = (ar1_c * d_mod[t-1] if t >= 1 else 0.0) + (ar2_c * d_mod[t-2] if t >= 2 else 0.0)
    d_mod[t] = mdet[t] + ar

model_leads_shift = leads + d_mod

# ---- results: levels for the window -----------------------------------
A = leads[win].sum()
T = true_leads_shift[win].sum()
P = model_leads_shift[win].sum()

print()
print("=" * 66)
print(f"LEADS over the {WIN_LEN}-week window (levels)")
print("=" * 66)
print(f"  Actual leads, no shift (reality)        : {A:8.0f}")
print(f"  Model predicts the shift would yield    : {P:8.0f}   ({P-A:+.0f} vs actual)")
print(f"  TRUE outcome of the shift (DGP)         : {T:8.0f}   ({T-A:+.0f} vs actual)")
print()
print(f"  Model's promised gain                   : {P-A:+8.0f} leads")
print(f"  Actual result of taking the model's advice: {T-A:+6.0f} leads")
print(f"  Model overstates the shift by           : {P-T:8.0f} leads")
print()
print(f"  Model coefficients (per $1K, 10x scale): DM={dm_c:.1f}  digital={dig_c:.1f}  (true: DM=30, digital=25)")
