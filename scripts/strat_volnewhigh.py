"""Candidate: volatility-scaled new-high proximity (strategy_lab contract).

Composition of the loop's two best ideas: strat_newhigh's ranking
(proximity to the trailing 12M high, fresh breakouts) scaled by trailing
monthly volatility (strat_volmom's smoother-is-better tilt). Rationale: a
name grinding into its high on low vol is a base breakout; a name spiking
into its high on huge vol is a blowoff. Raw proximity cannot tell them
apart — dividing by realized vol can. Absolute gate kept (within max_dist
of high only). Same index-vs-MA regime overlay.

PIT-safe: all inputs are month-end closes through px[m]; vol is the std of
monthly simple returns over vol_lb months ending at m.

SPACE = lookback {9,12}, max_dist {0.07,0.10,0.15}, vol_lb {6,9},
regime_ma {0,6,10}.
"""

from __future__ import annotations

import numpy as np
import polars as pl

NEEDS_DAILY = False
SPACE = {
    "lookback": [9, 12],
    "max_dist": [0.07, 0.10, 0.15],
    "vol_lb": [6, 9],
    "regime_ma": [0, 6, 10],
}


def score(panels, params):
    px, months = panels["px"], panels["months"]
    start_i = panels["start_i"]
    lb = int(params.get("lookback", 12))
    md = float(params.get("max_dist", 0.10))
    vlb = int(params.get("vol_lb", 9))
    ma = int(params.get("regime_ma", 6))

    hi = np.full_like(px, np.nan)
    for t in range(lb - 1, len(months)):
        hi[t] = np.nanmax(px[t - lb + 1:t + 1], axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        prox = px / hi - 1
    prox[~(prox >= -md)] = np.nan

    ret = np.full_like(px, np.nan)
    ret[1:] = px[1:] / px[:-1] - 1
    vol = np.full_like(px, np.nan)
    for t in range(vlb, len(months)):
        vol[t] = np.nanstd(ret[t - vlb + 1:t + 1], axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = (1 + prox) / vol  # nearer-high AND smoother = higher
    out[~np.isfinite(prox) | ~np.isfinite(vol) | (vol <= 0)] = np.nan

    alive = ~np.isnan(px[start_i])
    idx = np.nanmean(px[:, alive] / px[start_i, alive], axis=1)
    regime = np.ones(len(months), dtype=bool)
    if ma:
        idx_ma = pl.Series(idx).rolling_mean(ma).to_numpy()
        regime = np.array([bool(idx[t] > idx_ma[t]) if not np.isnan(idx_ma[t]) else False
                           for t in range(len(months))])
    return out, regime
