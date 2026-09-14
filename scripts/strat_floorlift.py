"""Candidate: distance above multi-year floor (strategy_lab contract).

Fresh mechanism — not a momentum or trailing-high rank. Thesis: structural
compounders, not recent runners. Rank by log distance above the trailing
36-month low (higher = further the name has carried above its floor);
eligibility needs 36 months of history (seasoning guard) plus a positive
12-month return so the book holds proven climbers, not names bouncing along
the bottom. Nothing here measures proximity to a high or a fixed-lookback
return sprint.

PIT-safe: score for holding month starting months[m] uses closes through
px[m] only (floor over px[m-35..m], current px[m]).

SPACE = floor_lb {24,36}, trend_lb {12}, regime_ma {0,6}, weak_exp {0.0,0.4}.
`weak_exp` is the exposure used when the index regime is OFF, so
float-regime tiers are searchable per trial via params-json.
"""

from __future__ import annotations

import numpy as np
import polars as pl

NEEDS_DAILY = False
SPACE = {
    "floor_lb": [24, 36],
    "trend_lb": [12],
    "regime_ma": [0, 6],
    "weak_exp": [0.0, 0.4],
}


def _regime(px, months, start_i, ma, weak_exp):
    reg = np.ones(len(months))
    if ma:
        alive = ~np.isnan(px[start_i])
        idx = np.nanmean(px[:, alive] / px[start_i, alive], axis=1)
        idx_ma = pl.Series(idx).rolling_mean(ma).to_numpy()
        for t in range(len(months)):
            if np.isnan(idx_ma[t]) or not (idx[t] > idx_ma[t]):
                reg[t] = weak_exp
    return reg


def score(panels, params):
    px, months = panels["px"], panels["months"]
    start_i = panels["start_i"]
    flb = int(params.get("floor_lb", 36))
    tlb = int(params.get("trend_lb", 12))
    ma = int(params.get("regime_ma", 6))
    weak_exp = float(params.get("weak_exp", 0.0))

    out = np.full_like(px, np.nan)
    for t in range(flb - 1, len(months)):
        w = px[t - flb + 1:t + 1]
        cnt = np.isfinite(w).sum(axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            lo = np.nanmin(w, axis=0)
            lift = np.log(px[t] / lo)
        lift[cnt < flb] = np.nan  # seasoning: need the full floor window
        out[t] = lift

    trend = np.full_like(px, np.nan)
    trend[tlb:] = px[tlb:] / px[:-tlb] - 1
    out[~(trend > 0)] = np.nan
    out[~np.isfinite(out) | (out <= 0)] = np.nan
    return out, _regime(px, months, start_i, ma, weak_exp)
