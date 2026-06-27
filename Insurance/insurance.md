---
---
# Insurance Marketing Analytics Decision Engine

[← Back to Home](../index.md)

---

This is a self-directed demonstration project. It walks an end-to-end analytics workflow for a B2C insurance company — from exploratory analysis through predictive modeling to budget optimization and business-impact measurement — to show *how I approach the work*.

> **Note on the data:** Everything here runs on a synthetic dataset I generated to mirror realistic insurance-marketing dynamics. The figures throughout are outputs of that simulation, included to illustrate the methodology end to end — not results from a client engagement.

**[View Repository →](https://github.com/mcbelli/insurance-marketing-analytics-decision-engine)**

---

## The Business Problem

In insurance, growth without risk discipline destroys value. Marketing teams optimize for lead volume and cost-per-lead, but cheap leads often become unprofitable policies. This project works through three questions:

1. Which marketing channels drive *profitable* growth—not just volume?
2. How do we model the diminishing returns of marketing spend?
3. Where should we reallocate budget to maximize lifetime value?

---

## 1. Exploratory Data Analysis

<table>
<tr>
<td width="55%" valign="top" markdown="1">

Eight exploratory analyses reveal the key dynamics of insurance marketing:

- **Credit score** strongly predicts both conversion and claims risk
- **Channel quality varies**: cheaper leads have higher loss ratios
- **Cross-sell customers** have 2x higher lifetime value
- **Geographic variation** requires state-level pricing adjustments

The EDA surfaces the core insight: **email has the highest ROI despite the lowest lead quality**, because its acquisition cost ($8/lead) is dramatically lower than paid search ($45/lead).

**[View Full EDA →](EDA/insurance_exploratory-analysis)**

</td>
<td width="45%" valign="top">


<a href="EDA/insurance_exploratory-analysis">
  <img src="EDA/EDA_cross_sell.png" width="100%">
</a>
<em>Click for details</em>

</td>
</tr>
</table>

---

## 2. Marketing Mix Model

<table>
<tr>
<td width="55%" valign="top" markdown="1">

The Marketing Mix Model (MMM) quantifies the relationship between spend and conversions using **Hill saturation curves**:

- **Response curves** capture diminishing returns at higher spend levels
- **Unit economics** (avg profit per conversion) vary by channel
- **ROI-saturation constraint** ensures high-ROI channels aren't mistakenly labeled as "saturated"

The model reveals that email is operating at just 8% of its half-saturation point—significant room to scale—while search and social are both near 70%.

**[View Full Model Documentation →](MMM/insurance_marketing-mix-model)**

</td>
<td width="45%" valign="top">

<a href="MMM/insurance_marketing-mix-model">
  <img src="MMM/MMM_homepage.png" width="100%">
</a>
<em>Click for details</em>

</td>
</tr>
</table>

---

## 3. Budget Optimization

<table>
<tr>
<td width="55%" valign="top" markdown="1">

Using the fitted response curves, we simulate two scenarios:

- **Period 1 (Current)**: Historical budget allocation
- **Period 2 (Optimal)**: Budget reallocated to equalize marginal ROI across channels

With the **same total marketing spend**, the optimal allocation shifts ~$4,800/month out of search and social into under-saturated email, yielding:

- **+12.8% more conversions**
- **+5.9% higher profit**
- **11% lower customer acquisition cost**

**[View Optimization Details →](Optimization/insurance_optimization)**

</td>
<td width="45%" valign="top">

<a href="Optimization/insurance_optimization">
  <img src="Optimization/Optimization_homepage.png" width="100%">
</a>
<em>Click to enlarge</em>

</td>
</tr>
</table>

---

## 4. Business Impact

<a href="Business_Impact/Business_Impact_homepage.png">
  <img src="Business_Impact/Business_Impact_homepage.png" width="70%">
</a>

**Within the simulation**, reallocating the same modeled $308K annual marketing budget produces:

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| New Customers | 957 | 1,079 | **+12.8%** |
| Lifetime Revenue | $18.4M | $20.8M | **+$2.4M** |
| Policy Profit | $3.49M | $3.69M | **+$205K** |
| CAC | $322 | $286 | **-11%** |

*(Profit rises far less than conversions because the reallocation leans into email — high ROI on acquisition cost, but lower-margin policies. Surfacing that trade-off is exactly the point of the model.)*

---

## Technical Implementation

**Data Generation:** Python script creating synthetic but realistic insurance marketing data with:
- 3 years of lead data across 3 products (Health, Life, Property/Casualty)
- 3 marketing channels with quality/cost trade-offs, where daily spend varies widely (budget regimes and experiments) and leads follow a saturating response to spend
- Full sales funnel with claims simulation, plus cross-sell dynamics (bundled customers convert better and retain longer)

**Modeling:** Hill saturation functions with an ROI-based constraint, fit on monthly-aggregated data using nonlinear least squares.

**Optimization:** Profit-maximizing budget allocation using scipy.optimize.

---

[← Back to Home](../index.md)
