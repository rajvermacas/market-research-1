"""Candidate: fresh-print rank under participation gate (strategy_lab contract).

Composition of the two surviving cuts (imported, never copied): rank by
strat_floorhighfresh (lift among names printing a trailing-high close, under
breadth-tier regime) but eligible only where strat_floorhighpart also scores
finite (stock-level trend participation above p_min over part_lb months).

Rationale: the fresh print selects market confirmation; the participation
gate selects names whose own trend carried them there rather than one
spike. Each cut helped or held (fresh kept, part gate trailed by ~1.5pp but
kept the DD line); their intersection should keep the confirmed breakouts
while dropping lone-spike prints. If the two filters overlap fully, this
ties the fresh leg and says so.

PIT-safe: inherits both legs' discipline; intersection of two PIT-safe
eligibility sets is PIT-safe.

SPACE = strat_floorhightier params + part_lb {6}, p_min {0.5}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfresh import score as _fresh_score
from strat_floorhighpart import score as _part_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [19],
    "lookback": [16],
    "max_dist": [0.055],
    "regime_ma": [18],
    "part_lb": [6],
    "p_min": [0.5],
}


def score(panels, params):
    rank, exposure = _fresh_score(panels, params)
    gate, _ = _part_score(panels, params)
    return np.where(np.isfinite(gate), rank, np.nan), exposure
