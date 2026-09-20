"""Candidate: trend-consistency rank on the floor-seasoned near-high universe.

Fresh rank statistic (fourth cut) on a proven universe: eligibility is the
strat_floorhigh mask (seasoned floor + positive 12m trend + within
max_dist of the trailing high — imported, never copied), but the rank is
trend QUALITY, not lift depth: the fraction of positive monthly returns
over the trailing `trend_lb` months (higher = smoother, steadier
advancer). Regime is the breadth-tier exposure from strat_newhigh_tier.

Rationale: lift depth crowns the names furthest above their floor, which
skews toward the most violent multi-year rallies; among already-seasoned
near-high names, the smoothest climbers (most up-months) should carry
less book-level drawdown than the deepest ones. Prior cuts on this
universe (depth, freshness, duration, vol-scale, coil/sponsorship gates)
all left train DD as the binding problem or subtracted forward; up-month
consistency is untested here.

PIT-safe: eligibility, rank and breadth all use month-end closes through
px[m] only for the holding month starting months[m].

SPACE = union of strat_floorhigh / strat_newhigh_tier params + trend_lb {12}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhigh import score as _fh_score
from strat_newhigh_tier import score as _tier_score

NEEDS_DAILY = False
SPACE = {"note": "union of strat_floorhigh/strat_newhigh_tier params + trend_lb"}


def score(panels, params):
    px, months = panels["px"], panels["months"]
    elig, _ = _fh_score(panels, params)
    _, exposure = _tier_score(panels, params)
    tlb = int(params.get("trend_lb", 12))

    ret = np.full_like(px, np.nan)
    ret[1:] = px[1:] / px[:-1] - 1
    out = np.full_like(px, np.nan)
    for t in range(tlb, len(months)):
        w = ret[t - tlb + 1:t + 1]
        cnt = np.isfinite(w).sum(axis=0)
        with np.errstate(invalid="ignore"):
            frac = np.nansum(w > 0, axis=0) / cnt
        frac[cnt < tlb] = np.nan
        out[t] = frac
    out[~np.isfinite(elig)] = np.nan  # floor-seasoned near-high universe only
    return out, exposure
