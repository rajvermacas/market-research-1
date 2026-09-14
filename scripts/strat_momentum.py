"""Candidate: cross-sectional momentum (strategy_lab contract).

Signal: total return over `lookback` months, skipping the most recent month
(short-term reversal is an opposing effect). Optional absolute-momentum gate
(`abs_mom`: only positive lookback returns) and per-stock trend gate
(`stock_ma`: price above its own N-month average). Regime overlay: hold only
while the equal-weight index of the universe sits above its own `regime_ma`
month average, else cash. Ranking is relative, so without the gates the book
happily holds falling stocks in a falling market.

SPACE = lookback {3,6,9,12,15}, regime_ma {0,6,8,10,12}, stock_ma {0,6,10},
abs_mom {False,True}. Top-N is the harness's decision, not this file's.
"""

from __future__ import annotations

import numpy as np
import polars as pl

NEEDS_DAILY = False
SPACE = {
    "lookback": [3, 6, 9, 12, 15],
    "regime_ma": [0, 6, 8, 10, 12],
    "stock_ma": [0, 6, 10],
    "abs_mom": [False, True],
}


def score(panels, params):
    px, months = panels["px"], panels["months"]
    start_i = panels["start_i"]
    lb = int(params.get("lookback", 9))
    ma = int(params.get("regime_ma", 6))
    sma = int(params.get("stock_ma", 0))
    absmom = bool(params.get("abs_mom", True))

    mom = np.full_like(px, np.nan)
    mom[lb + 1:] = px[1:-lb] / px[:-lb - 1] - 1
    if absmom:
        mom[~(mom > 0)] = np.nan
    if sma:
        own = np.full_like(px, np.nan)
        for t in range(sma - 1, len(months)):
            own[t] = np.nanmean(px[t - sma + 1:t + 1], axis=0)
        mom[~(px > own)] = np.nan

    alive = ~np.isnan(px[start_i])
    idx = np.nanmean(px[:, alive] / px[start_i, alive], axis=1)
    regime = np.ones(len(months), dtype=bool)
    if ma:
        idx_ma = pl.Series(idx).rolling_mean(ma).to_numpy()
        regime = np.array([bool(idx[t] > idx_ma[t]) if not np.isnan(idx_ma[t]) else False
                           for t in range(len(months))])
    return mom, regime
