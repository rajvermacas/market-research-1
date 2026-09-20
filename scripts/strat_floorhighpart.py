"""Candidate: floor-high rank gated on stock-level trend participation
(strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank by
strat_floorhigh (floor-lift distance among names within max_dist of their
trailing high) and regime by strat_newhigh_tier breadth tiers, but a name is
eligible only if it *participated* in the trend itself — fraction of the
past `part_lb` month-ends printing above its own `regime_ma`-month average
at least `p_min`.

Rationale: market breadth gates the book's exposure, but a qualifying name
can still be a lone drifter below its own trend while breadth is carried by
others. This is the two-tier rank cut: floor-distance x stock-level
breadth-participation. It should cut the left tail (names that rank on a
high floor but have already rolled over) at the cost of some eligible count.

PIT-safe: participation for holding month starting months[m] uses closes
through px[m] only; NaN MA rows (warm-up) count as below-MA, conservative,
never peeks. Requires a full part_lb window of finite closes (seasoning).

SPACE = strat_floorhightier params + part_lb {6, 12}, p_min {0.5, 0.67}.
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
    "floor_lb": [18],
    "lookback": [15],
    "max_dist": [0.05],
    "regime_ma": [18],
    "part_lb": [6, 12],
    "p_min": [0.5, 0.67],
}


def score(panels, params):
    rank, _ = _fh_score(panels, params)
    _, exposure = _tier_score(panels, params)
    px, months = panels["px"], panels["months"]
    ma = int(params.get("regime_ma", 18))
    plb = int(params.get("part_lb", 6))
    p_min = float(params.get("p_min", 0.5))

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
        ok = np.isfinite(rank[t]) & np.isfinite(part) & (part >= p_min)
        out[t] = np.where(ok, rank[t], np.nan)
    return out, exposure
