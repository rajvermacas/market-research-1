"""Candidate: 52-week-high proximity ranking (strategy_lab contract).

Fresh mechanism, not a momentum variant: rank by closeness to the trailing
`lookback`-month high (George-Hwang style). Rationale: trailing-return
momentum holds extended winners that then mean-revert; proximity-to-high
prefers names pressing against resistance — fresh breakouts and bases —
while excluding both runaway extenders that fell back and basement
bounce candidates. Absolute gate (`abs_mom`-like): only names within
`max_dist` of their high are eligible, so a falling market yields cash via
the harness minimum-count rule. Regime overlay: same equal-weight
index-vs-MA gate as strat_momentum.

PIT-safe: score for holding month starting months[m] uses closes through
px[m] only (high over px[m-lookback+1..m], current px[m]).

SPACE = lookback {6,9,12}, regime_ma {0,6,10}, max_dist {0.10,0.15,0.25}.
"""

from __future__ import annotations

import numpy as np
import polars as pl

NEEDS_DAILY = False
SPACE = {
    "lookback": [6, 9, 12],
    "regime_ma": [0, 6, 10],
    "max_dist": [0.10, 0.15, 0.25],
}


def score(panels, params):
    px, months = panels["px"], panels["months"]
    start_i = panels["start_i"]
    lb = int(params.get("lookback", 9))
    ma = int(params.get("regime_ma", 6))
    md = float(params.get("max_dist", 0.15))

    # rolling max of closes ending at t (inclusive), needs lb bars
    hi = np.full_like(px, np.nan)
    for t in range(lb - 1, len(months)):
        hi[t] = np.nanmax(px[t - lb + 1:t + 1], axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        prox = px / hi - 1  # <= 0, closer to 0 = nearer the high
    prox[~(prox >= -md)] = np.nan  # eligible only within max_dist of high

    alive = ~np.isnan(px[start_i])
    idx = np.nanmean(px[:, alive] / px[start_i, alive], axis=1)
    regime = np.ones(len(months), dtype=bool)
    if ma:
        idx_ma = pl.Series(idx).rolling_mean(ma).to_numpy()
        regime = np.array([bool(idx[t] > idx_ma[t]) if not np.isnan(idx_ma[t]) else False
                           for t in range(len(months))])
    return prox, regime
