"""Candidate (L29 designer B): Nifty 500 fresh-print book with exposure tiers
keyed to the book's OWN trailing monthly-return volatility (strategy_lab contract).

Setup in words: rank and breadth-tier exposure are strat_floorhighfresh's
(imported unchanged; universe nifty500, top 25). The un-overlaid base book is
replayed causally as an equal-weight top-`top` proxy (strat_l29b_bookdd.
proxy_returns, imported): r[t] = e[t] * mean next-month return of the names
picked at t. For the holding month starting months[m], the proxy's realized
volatility over the last `bv_k` completed months, std(r[m-bv_k:m]) (only r[t]
with t+1 <= m, i.e. closes through px[m]), sets the overlay:

    vol > bv_thr  ->  exposure[m] *= bv_cut      (else unchanged)

Months in cash contribute r = 0, so the book's own vol reflects what it
actually carried, not the market's.

Novelty: legacy vol-targeting rows (DEAD) scaled by index or single-name vol
on the full-board champion chain; this keys exposure to the BOOK's own
realized return vol, and the base changed (Nifty 500 universe, L25 cell).
Disclosure: the target (Nifty 500 book DD) was MOTIVATED by the revealed L25
forward DD (-25.65). Thresholds were read off the TRAIN-only (pre-2022)
distribution of the proxy vol (k3 median .028 / p75 .048 / p90 .061;
k6 median .036 / p75 .053 / p90 .066); no forward value is looked at.

Off-switch: bv_cut = 1.0 returns the base exposure exactly.
SPACE = base params + bv_k {3, 6}, bv_thr {0.05, 0.06, 0.07}, bv_cut {1.0, 0.5, 0.0}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfresh import score as _fresh_score
from strat_l29b_bookdd import proxy_returns

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65], "b_mid": [0.58], "b_lo": [0.45], "floor_lb": [24],
    "lookback": [16], "max_dist": [0.055], "regime_ma": [24],
    "bv_k": [3, 6], "bv_thr": [0.05, 0.06, 0.07], "bv_cut": [1.0, 0.5, 0.0],
}


def score(panels, params):
    scores, exposure = _fresh_score(panels, params)
    exposure = np.asarray(exposure, dtype=float)
    cut = float(params.get("bv_cut", 1.0))
    if cut == 1.0:
        return scores, exposure
    k = int(params.get("bv_k", 3))
    thr = float(params.get("bv_thr", 0.06))
    top = int(params.get("top", 25))
    r = proxy_returns(panels["px"], scores, exposure, top)
    out = exposure.copy()
    for m in range(k, len(out)):
        if np.std(r[m - k:m]) > thr:
            out[m] *= cut
    return scores, out
