"""Candidate: blended lift-x-proximity rank under breadth tiers
(strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): the rank
is a cross-sectional blend of strat_floorlift's structural lift (log distance
above the trailing floor, seasoners with 12m trend) and strat_newhigh's
breakout proximity (closeness to the trailing high), z-scored per month and
summed as z_lift + w * z_prox, eligible only among names within max_dist of
their high. Regime is strat_newhigh_tier breadth-tier exposure.

Rationale: strat_floorhigh ranks purely on lift and uses proximity only as a
hard mask — a name 5.4% off its high ranks the same as one printing it, and
a marginal-lift fresh breakout never outranks a stale compounder. If both
dimensions carry signal, the blend should beat either leg alone; if lift
dominates, small w trails gracefully. Weight w is the trial param.

PIT-safe: both legs use closes through px[m] only; z-scoring is purely
cross-sectional within month t, no forward information.

SPACE = strat_floorhightier params + blend_w {0.5, 1.0, 2.0}.
"""

from __future__ import annotations

import numpy as np

from strat_floorlift import score as _lift_score
from strat_newhigh import score as _high_score
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
    "blend_w": [0.5, 1.0, 2.0],
}


def score(panels, params):
    lift, _ = _lift_score(panels, params)
    prox, _ = _high_score(panels, params)
    _, exposure = _tier_score(panels, params)
    w = float(params.get("blend_w", 1.0))
    out = np.full_like(lift, np.nan)
    for t in range(lift.shape[0]):
        ok = np.isfinite(lift[t]) & np.isfinite(prox[t])
        if ok.sum() < 2:
            continue
        lz, pz = lift[t], prox[t]
        lz = (lz - np.nanmean(lz[ok])) / (np.nanstd(lz[ok]) or 1.0)
        pz = (pz - np.nanmean(pz[ok])) / (np.nanstd(pz[ok]) or 1.0)
        out[t] = np.where(ok, lz + w * pz, np.nan)
    return out, exposure
