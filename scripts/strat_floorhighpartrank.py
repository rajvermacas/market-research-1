"""Candidate: participation-ranked floorhigh under breadth tiers
(strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied):
eligibility from strat_floorhigh (within max_dist of the trailing high AND
above the trailing floor with a positive 12m trend) and regime from
strat_newhigh_tier breadth tiers — but the RANK is stock-level trend
participation (fraction of the past `part_lb` month-ends above its own
`regime_ma`-month average), not floor-lift distance.

Rationale: strat_floorhighpart gates on participation and ranks on lift; if
the participation leg carries the signal, ranking on it directly should beat
the gate version, and if lift carries it, this trails — a clean A/B on which
leg does the work. Higher participation = stronger sustained trend.

PIT-safe: participation for holding month starting months[m] uses closes
through px[m] only; NaN MA rows count as below-MA, conservative, never
peeks; full-window finitecloses required.

SPACE = strat_floorhightier params + part_lb {6, 12}.
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
    "lookback": [15],
    "max_dist": [0.05],
    "regime_ma": [18],
    "part_lb": [6, 12],
}


def score(panels, params):
    elig, _ = _fh_score(panels, params)
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

    out = np.full_like(elig, np.nan)
    for t in range(plb - 1, len(months)):
        w_above = above[t - plb + 1:t + 1]
        w_alive = alive[t - plb + 1:t + 1]
        with np.errstate(invalid="ignore"):
            part = np.where(w_alive.sum(axis=0) == plb,
                            w_above.sum(axis=0) / plb, np.nan)
        ok = np.isfinite(elig[t]) & np.isfinite(part)
        out[t] = np.where(ok, part, np.nan)
    return out, exposure
