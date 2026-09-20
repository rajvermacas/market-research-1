"""Candidate: sustained-print breakouts under fast gate (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank and
regime from strat_floorhighfastgate, but eligible only if the name ALSO
printed a trailing high within the prior `sustain_lb` months — the logical
complement of strat_floorhighfirstprint (debut prints collapsed to +13-30%,
so this tests the other side: sustained printers).

Rationale: firstprint's failure says debut breakouts underperform; if
repeated printing is the actual signal (sponsorship confirmation month after
month), requiring print continuity should match or beat the base while
cutting one-off spikes. If instead any print filter beyond "printing now"
is overfitting the timing, this trails the fresh leg and the print-timing
question closes with "now is all that matters".

PIT-safe: prior-print status uses imported proximity history through px[m]
only; the current-month print is required too (fresh leg), never peeks.

SPACE = strat_floorhighfastgate params + sustain_lb {3, 6}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfastgate import score as _fg_score
from strat_newhigh import score as _high_score

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
    "sustain_lb": [3, 6],
}


def score(panels, params):
    rank, exposure = _fg_score(panels, params)
    prox, _ = _high_score(panels, params)
    slb = int(params.get("sustain_lb", 3))
    out = np.array(rank, dtype=float, copy=True)
    with np.errstate(invalid="ignore"):
        printed = np.isfinite(prox) & (prox >= -0.001)
    for t in range(rank.shape[0]):
        lo = max(0, t - slb)
        prior = printed[lo:t].any(axis=0) if t > lo else np.zeros(rank.shape[1], bool)
        out[t] = np.where(np.isfinite(rank[t]) & prior, rank[t], np.nan)
    return out, exposure
