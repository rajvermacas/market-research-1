"""Candidate: breakout recency — fewest bars since trailing high (strategy_lab contract).

Sibling of strat_newhigh testing a different cut of the same intuition:
newhigh ranks by HOW FAR below the high (depth); this ranks by HOW LONG
AGO the high printed (freshness). A base that touched its high yesterday
outranks one grinding 2% below for six months. Score = -(bars since high),
so most-recent breakout ranks first. Same absolute gate (within max_dist
of the high) and same index-vs-MA regime overlay, so the only difference
vs strat_newhigh is the ranking statistic — a clean ablation of depth vs
freshness.

PIT-safe: bars-since-high counted on closes through px[m] only.

SPACE = lookback {9,12}, max_dist {0.10,0.15}, regime_ma {6}.
"""

from __future__ import annotations

import numpy as np
import polars as pl

NEEDS_DAILY = False
SPACE = {
    "lookback": [9, 12],
    "max_dist": [0.10, 0.15],
    "regime_ma": [6],
}


def score(panels, params):
    px, months = panels["px"], panels["months"]
    start_i = panels["start_i"]
    lb = int(params.get("lookback", 12))
    md = float(params.get("max_dist", 0.10))
    ma = int(params.get("regime_ma", 6))

    hi = np.full_like(px, np.nan)
    for t in range(lb - 1, len(months)):
        hi[t] = np.nanmax(px[t - lb + 1:t + 1], axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        prox = px / hi - 1

    # bars since the window high: argmax over the trailing window
    age = np.full_like(px, np.nan)
    for t in range(lb - 1, len(months)):
        w = px[t - lb + 1:t + 1]
        finite = np.isfinite(w)
        has = finite.any(axis=0)
        wf = np.where(finite, w, -np.inf)
        with np.errstate(invalid="ignore"):
            am = np.argmax(wf, axis=0).astype(float)
        am[~has] = np.nan
        age[t] = (lb - 1) - am
    out = -age
    out[~(prox >= -md)] = np.nan  # same absolute gate as newhigh

    alive = ~np.isnan(px[start_i])
    idx = np.nanmean(px[:, alive] / px[start_i, alive], axis=1)
    regime = np.ones(len(months), dtype=bool)
    if ma:
        idx_ma = pl.Series(idx).rolling_mean(ma).to_numpy()
        regime = np.array([bool(idx[t] > idx_ma[t]) if not np.isnan(idx_ma[t]) else False
                           for t in range(len(months))])
    return out, regime
