"""Candidate: lift-x-participation multiplicative rank (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank is
the PRODUCT of strat_floorhigh lift level and the stock-level trend
participation fraction (share of the past `part_lb` month-ends above its own
`regime_ma`-month average), among floorhigh-eligible names; regime is
breadth tiers.

Rationale: strat_floorhighpart used participation as a HARD gate (trailed
base by ~1.5pp) and strat_floorhighpartrank ranked on participation alone
(collapsed to ~20%). Both may be too coarse: the gate discards high-lift
names on a single miss, the rank discards lift entirely. The product keeps
both dimensions continuous — a name compensates middling participation with
exceptional structure and vice versa. If any participation interaction
helps, this is the softest form; if participation is pure noise here, this
trails the gate version too and the dimension is closed.

PIT-safe: participation uses closes through px[m] only with a full-window
finite requirement; NaN MA rows count as below-MA, conservative, never
peeks.

SPACE = strat_floorhightier params + part_lb {6}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhigh import score as _fh_score
from strat_newhigh_tier import score as _tier_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [19],
    "lookback": [16],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [6],
    "part_lb": [6],
}


def score(panels, params):
    rank, _ = _fh_score(panels, params)
    _, exposure = _tier_score(panels, params)
    px, months = panels["px"], panels["months"]
    ma = int(params.get("regime_ma", 18))
    plb = int(params.get("part_lb", 6))

    ma_px = np.full_like(px, np.nan)
    for t in range(ma - 1, len(months)):
        ma_px[t] = np.nanmean(px[t - ma + 1:t + 1], axis=0)
    with np.errstate(invalid="ignore"):
        above = (px > ma_px) & np.isfinite(px) & np.isfinite(ma_px)
        alive = np.isfinite(px)

    out = np.full_like(rank, np.nan)
    for t in range(plb - 1, len(months)):
        w_above = above[t - plb + 1:t + 1]
        w_alive = alive[t - plb + 1:t + 1]
        with np.errstate(invalid="ignore"):
            part = np.where(w_alive.sum(axis=0) == plb,
                            w_above.sum(axis=0) / plb, np.nan)
        ok = np.isfinite(rank[t]) & np.isfinite(part)
        out[t] = np.where(ok, rank[t] * part, np.nan)
    return out, exposure
