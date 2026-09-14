"""Candidate: volatility-compression coil (strategy_lab contract).

Fresh mechanism — not a momentum or high-proximity rank. Thesis: the calm
before the expansion. Rank by trailing 3-month realized monthly volatility
ASCENDING (tightest coil first); eligibility needs an intact uptrend
(6-month return > 0) so the book buys coiling advancers, never dead flat
lines or coiling decliners. No reference to any trailing high anywhere.

PIT-safe: score for holding month starting months[m] uses month-end closes
through px[m] only (returns ending at m, std over the 3 returns ending at m).

SPACE = vol_lb {3}, trend_lb {6}, regime_ma {0,6}, weak_exp {0.0,0.4}.
`weak_exp` is the exposure used when the index regime is OFF, so
float-regime tiers are searchable per trial via params-json.
"""

from __future__ import annotations

import numpy as np
import polars as pl

NEEDS_DAILY = False
SPACE = {
    "vol_lb": [3],
    "trend_lb": [6],
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
    vlb = int(params.get("vol_lb", 3))
    tlb = int(params.get("trend_lb", 6))
    ma = int(params.get("regime_ma", 6))
    weak_exp = float(params.get("weak_exp", 0.0))

    ret = np.full_like(px, np.nan)
    ret[1:] = px[1:] / px[:-1] - 1
    vol = np.full_like(px, np.nan)
    for t in range(vlb, len(months)):
        vol[t] = np.nanstd(ret[t - vlb + 1:t + 1], axis=0)

    trend = np.full_like(px, np.nan)
    trend[tlb:] = px[tlb:] / px[:-tlb] - 1

    out = -vol  # tightest coil ranks first
    out[~(trend > 0)] = np.nan  # uptrend-only eligibility
    out[~(vol > 0)] = np.nan  # need real dispersion history
    return out, _regime(px, months, start_i, ma, weak_exp)
