"""Candidate: minimum print-strength gate on sustained breakouts
(strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied):
eligibility and regime from strat_floorhighsustainprint, plus a STRENGTH
floor — the print month's own return must exceed `h_min`.

Rationale: hotprint ranked on 1-month heat and collapsed (heat mean-reverts,
so ranking on it is backwards), but a FLOOR is the opposite bet: not "hottest
first" but "no weak prints". Marginal +0.1% nominal prints are data quirks
and tiny bases, not sponsorship; requiring a real thrust (5-10% print month)
may cut exactly the entries that dilute the book. If heat is pure noise in
both directions, this trails like hotprint did.

PIT-safe: print-month return uses closes at t-1 and t only, both known at
the entry decision; NaNs propagate as ineligible, never peek.

SPACE = strat_floorhighsustainprint params + h_min {0.05, 0.10}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighsustainprint import score as _sustain_score

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
    "sustain_lb": [6],
    "h_min": [0.05, 0.10],
}


def score(panels, params):
    rank, exposure = _sustain_score(panels, params)
    px = panels["px"]
    hm = float(params.get("h_min", 0.05))
    out = np.array(rank, dtype=float, copy=True)
    for t in range(1, rank.shape[0]):
        with np.errstate(invalid="ignore"):
            heat = px[t] / px[t - 1] - 1
        ok = np.isfinite(rank[t]) & np.isfinite(heat) & (heat >= hm)
        out[t] = np.where(ok, rank[t], np.nan)
    out[0] = np.nan
    return out, exposure
