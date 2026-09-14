"""Candidate: volatility-scaled momentum (strategy_lab contract).

Mutation on the momentum mechanism: rank by trailing return per unit of
realized monthly volatility (a Sharpe-like cross-sectional score) instead of
raw trailing return. Rationale: raw momentum crowns the most violent
rallies — exactly the extenders that snap back. Scaling by trailing vol
prefers smooth advancers, which should cut drawdown and turnover churn
without a hard gate (invested% stays high). Absolute gate kept: only
positive lookback returns eligible. Same index-vs-MA regime overlay.

PIT-safe: score for holding month starting months[m] uses month-end closes
through px[m] only; vol is the std of the lb monthly simple returns ending
at px[m]/px[m-1] (skipping the most recent month like the return leg would
need care — here both legs use the same window ending at m for simplicity
and PIT-safety; the skip-1 refinement is a follow-up).

SPACE = lookback {6,9,12}, regime_ma {0,6,10}, vol_lb {6,9,12}.
"""

from __future__ import annotations

import numpy as np
import polars as pl

NEEDS_DAILY = False
SPACE = {
    "lookback": [6, 9, 12],
    "regime_ma": [0, 6, 10],
    "vol_lb": [6, 9, 12],
}


def score(panels, params):
    px, months = panels["px"], panels["months"]
    start_i = panels["start_i"]
    lb = int(params.get("lookback", 9))
    ma = int(params.get("regime_ma", 6))
    vlb = int(params.get("vol_lb", 9))

    mom = np.full_like(px, np.nan)
    mom[lb + 1:] = px[1:-lb] / px[:-lb - 1] - 1
    mom[~(mom > 0)] = np.nan

    # monthly simple returns, then trailing std over vol_lb months ending at t
    ret = np.full_like(px, np.nan)
    ret[1:] = px[1:] / px[:-1] - 1
    vol = np.full_like(px, np.nan)
    for t in range(vlb, len(months)):
        vol[t] = np.nanstd(ret[t - vlb + 1:t + 1], axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        scaled = mom / vol
    scaled[~np.isfinite(scaled) | (vol <= 0)] = np.nan

    alive = ~np.isnan(px[start_i])
    idx = np.nanmean(px[:, alive] / px[start_i, alive], axis=1)
    regime = np.ones(len(months), dtype=bool)
    if ma:
        idx_ma = pl.Series(idx).rolling_mean(ma).to_numpy()
        regime = np.array([bool(idx[t] > idx_ma[t]) if not np.isnan(idx_ma[t]) else False
                           for t in range(len(months))])
    return scaled, regime
