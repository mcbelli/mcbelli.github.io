"""
generate_data.py
----------------
Simulates 104 weeks of leads data from a known data generating process (DGP).

True model:
  Leads(t) = 40
            + 3.8 * DM_spend(t)        [direct mail is the stronger channel]
            + 1.6 * digital_spend(t)
            + 0.35 * Leads(t-1)        [organic carry-over / word-of-mouth]
            + noise

Key complication:
  Direct mail is billed 3-5 weeks AFTER the mail drops. The CSV records the
  billing date (dm_spend_billed), not the drop date (dm_spend_actual). This
  timing mismatch makes it hard for any model reading the CSV to recover the
  true DM coefficient, even with distributed lags or smoothing.

  Digital spend is recorded in the same week the activity occurs, so its
  timing is clean and any model can recover its coefficient easily.

  Total spend is approximately equal across channels (~520 units), so any
  difference in model performance is due to timing/observability, not budget size.

Outputs:
  mmm_data.csv  -- one row per week with columns:
      week, leads, dm_spend_billed, digital_spend, dm_spend_actual (truth only,
      for validation purposes -- a real analyst would NOT have this column)
"""

import numpy as np
import pandas as pd

RNG = np.random.default_rng(seed=42)
N = 104  # two years of weekly data
DM_ACTIVE_WEEKS = 21   # exactly 1 in 5 weeks; fixes total spend regardless of seed


def generate():
    # ------------------------------------------------------------------
    # Spend schedules
    # ------------------------------------------------------------------

    # Digital: always-on channel with seasonal wave + week-to-week noise
    # create 1D array of N (104) evenly spaced values for use in creating a seasonal wave
    # include the endpoints, set spacing between values at (stop - start) / (N - 1)
    # set start at 0 and stop at 4*pi (two full annual cycles over two years)
    spaced_104 = np.linspace(0, 4 * np.pi, N)
    digital_spend = (
        5.0
        + 2.5 * np.sin(spaced_104)   # seasonal wave: oscillates +/-2.5 around baseline
        + RNG.normal(0, 1.2, N)      # week-to-week noise
    ).clip(1.5, 12.0)

    # Direct mail: zero most weeks, spend in exactly 1-in-5 weeks
    # randomly choose DM_ACTIVE_WEEKS indices without replacement -- this fixes
    # the number of active weeks precisely so total spend is always matched to
    # digital regardless of seed (using a probability would let active week
    # count vary too much across seeds)
    #
    # target total: digital ~520; 21 active weeks * mean(uniform(20,30))=25 = 525
    active_idx = RNG.choice(N, size=DM_ACTIVE_WEEKS, replace=False)
    dm_actual = RNG.normal(0, 0.1, N).clip(0, None)   # near-zero noise floor
    dm_actual[active_idx] = RNG.uniform(20.0, 30.0, DM_ACTIVE_WEEKS)

    # Billing lag: each week's DM spend is billed 3-5 weeks later
    lag_weeks = RNG.integers(3, 6, size=N)   # lag drawn per week
    dm_billed = np.zeros(N)
    for t in range(N):
        billed_at = t + lag_weeks[t]
        if billed_at < N:
            dm_billed[billed_at] += dm_actual[t]
        # spend past week 103 is simply not recorded in this dataset

    # ------------------------------------------------------------------
    # Direct-mail adstock (true behavioral response lag)
    # ------------------------------------------------------------------
    # Real direct mail doesn't generate all its leads the week it drops --
    # recipients sit on the postcard and respond over the following weeks.
    # We model this as geometric adstock: each drop's effect decays by
    # DM_DECAY per week. We normalize by (1 - DM_DECAY) so the TOTAL leads
    # generated per $1K is unchanged -- the effect is SPREAD over time, not
    # amplified. This keeps DM and digital comparable in total impact.
    #
    # Note this is a SPREAD (the effect is distributed over several weeks
    # starting at the drop). It is distinct from the billing SHIFT applied
    # above (which moves the recorded spend later in time). The post's point
    # hinges on the difference: a rolling average can address spread, but
    # cannot undo a shift.
    DM_DECAY = 0.5   # 50% carry-over per week -> effect spread over ~3-4 weeks
    dm_adstock = np.zeros(N)
    for t in range(N):
        prior = dm_adstock[t - 1] if t > 0 else 0.0
        dm_adstock[t] = dm_actual[t] + DM_DECAY * prior
    dm_adstock *= (1 - DM_DECAY)   # normalize so total impact == sum(dm_actual)

    # ------------------------------------------------------------------
    # True leads (DGP)
    # ------------------------------------------------------------------
    TRUE_INTERCEPT = 400.0
    TRUE_DM_COEF   = 30.0  # leads per $1K of DM spend (spread via adstock)
    TRUE_DIG_COEF  = 25.0  # leads per $1K of digital spend
    TRUE_AR1       = 0.35  # organic carry-over

    leads = np.zeros(N)
    for t in range(N):
        carry = TRUE_AR1 * leads[t - 1] if t > 0 else 0.0
        leads[t] = (
            TRUE_INTERCEPT
            + TRUE_DM_COEF  * dm_adstock[t]      # adstocked DM: spread over weeks
            + TRUE_DIG_COEF * digital_spend[t]
            + carry
            + RNG.normal(0, 30.0)
        )
    leads = leads.clip(0).round(1)

    # ------------------------------------------------------------------
    # Assemble CSV
    # ------------------------------------------------------------------
    df = pd.DataFrame({
        "week":             np.arange(1, N + 1),
        "leads":            leads,
        "dm_spend_billed":  dm_billed.round(2),   # what the analyst sees
        "digital_spend":    digital_spend.round(2),
        "dm_spend_actual":  dm_actual.round(2),    # ground truth (hidden in real life)
        "dm_adstock":       dm_adstock.round(2),   # true spread effect (hidden in real life)
        "dm_billing_lag":   lag_weeks,             # per-week billing lag (hidden; for counterfactuals)
    })

    out_path = "mmm_data.csv"
    df.to_csv(out_path, index=False)

    print(f"Saved {len(df)} rows to {out_path}")
    print(f"\nSpend totals (should be roughly equal):")
    print(f"  Digital total   : {digital_spend.sum():.1f}")
    print(f"  DM actual total : {dm_actual.sum():.1f}  ({DM_ACTIVE_WEEKS} active weeks)")
    print(f"\nTrue DGP coefficients:")
    print(f"  Intercept  : {TRUE_INTERCEPT}")
    print(f"  Direct mail: {TRUE_DM_COEF}  leads per $1K (spread via adstock, decay={DM_DECAY})")
    print(f"  Digital    : {TRUE_DIG_COEF}  leads per $1K")
    print(f"  AR(1)      : {TRUE_AR1}  (organic carry-over)")
    print("\nNote: dm_spend_actual is included for validation only.")
    print("A real analyst would only see dm_spend_billed.")
    return df


if __name__ == "__main__":
    generate()
