"""Candidate: lift-velocity rank among fresh breakouts (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied):
eligibility and regime from strat_floorhighfresh (names printing a trailing
high under breadth tiers), but the RANK is lift VELOCITY — the change in
strat_floorlift log-distance-above-floor over the past `mom_lb` months —
instead of the lift level.

Rationale: the level rank holds the most-extended compounders; velocity
holds names whose structure is IMPROVING fastest right now (fresh legs
leaving the floor, not decade-long 10-baggers resting on old gains). The
edge-lives-in-the-tail lesson cuts both ways: if the far winners keep
extending, level wins; if breakouts burst then stall, velocity rotates into
the next burst earlier. mom_lb sets the measurement window.

PIT-safe: velocity at month t uses imported lift values at t and t-mom_lb
only, both known from closes through px[m]; lift NaNs (unseasoned names)
propagate as ineligible, never peek.

SPACE = strat_floorhightier params + mom_lb {6, 12}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfresh import score as _fresh_score
from strat_floorlift import score as _lift_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [19],
    "lookback": [16],
    "max_dist": [0.055],
    "regime_ma": [18],
    "mom_lb": [6, 12],
}


def score(panels, params):
    elig, exposure = _fresh_score(panels, params)
    lift, _ = _lift_score(panels, params)
    mlb = int(params.get("mom_lb", 12))
    out = np.full_like(elig, np.nan)
    for t in range(mlb, elig.shape[0]):
        with np.errstate(invalid="ignore"):
            vel = lift[t] - lift[t - mlb]
        ok = np.isfinite(elig[t]) & np.isfinite(vel)
        out[t] = np.where(ok, vel, np.nan)
    return out, exposure
