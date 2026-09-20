"""Candidate: re-shaped exposure tiers over the conditional-sustain book
(strategy_lab contract).

Mutation composing a tested mechanism (imported, never copied): rank and gate
from strat_floorhighsustaincond — importantly its print-continuity condition
still keys off the ORIGINAL tier exposure — with the book's exposure layers
re-valued: the 0.4 and 0.7 tiers and the cash state are replaced by
searchable values

    tier_floor (was 0.0)  tier_lo (was 0.4)  tier_mid (was 0.7)

so a trial can run fully invested in deep-weak months (tier_floor 1.0), carry
the mid tier heavier, etc.

Rationale: the best book is invested only 55% of the time and its cash sits
idle; the 0.4/0.7/0.0 ladder was inherited, never searched. If the
conditional-sustain entries work in weak months too, an exposure floor buys
compounding at the price of drawdown; if the tiers were already right, the
shape search ties and says so. This is risk-setting search expressed as
mechanism (the skill's "exposure in [0,1] is trial params" clause).

PIT-safe: tier values are constants per trial; breadth and gate read closes
through month t only.

SPACE = strat_floorhighsustaincond params + tier_floor {0.0}, tier_lo {0.4,0.55},
        tier_mid {0.7,0.85}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighsustaincond import score as _sc_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [19],
    "lookback": [16],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [9],
    "sustain_lo": [6],
    "sustain_hi": [2],
    "tier_floor": [0.0],
    "tier_lo": [0.4, 0.55],
    "tier_mid": [0.7, 0.85],
}


def score(panels, params):
    rank, exposure = _sc_score(panels, params)
    tfloor = float(params.get("tier_floor", 0.0))
    tlo = float(params.get("tier_lo", 0.4))
    tmid = float(params.get("tier_mid", 0.7))
    E = np.asarray(exposure, dtype=float)
    with np.errstate(invalid="ignore"):
        out = np.where(E >= 1.0, np.minimum(E, 1.0),
                       np.where(E >= 0.7, tmid,
                                np.where(E >= 0.4, tlo,
                                         np.where(E > 0.0, tlo, tfloor))))
    return rank, np.clip(out, 0.0, 1.0)
