"""Candidate: structural floor-lift ranked, steepening-gated (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied):
rank by strat_floorlift log-distance above the trailing floor (structural
compounders with seasoning + 12m trend gate) but only among names eligible
under strat_accel (positive 12m return, i.e. intact-year-gain; the accel
score itself is the steepening statistic). Regime is floorlift's float
index-vs-MA exposure (supports weak_exp tiers).

Rationale: floorlift holds steady climbers and fading extenders alike; the
accel gate keeps only names whose trend is intact over the full year while
the floor-distance rank orders them structurally. Tests whether steepening
vs fading separation helps the compounder book.

PIT-safe: both legs use month-end closes through px[m] only for holding
month starting months[m]; floor needs flb bars, accel needs slow bars.

SPACE = union of strat_floorlift.SPACE and strat_accel.SPACE.
"""

from __future__ import annotations

import numpy as np

from strat_accel import score as _acc_score
from strat_floorlift import score as _floor_score

NEEDS_DAILY = False
SPACE = {"note": "union of strat_floorlift.SPACE and strat_accel.SPACE"}


def score(panels, params):
    lift, regime = _floor_score(panels, params)
    gate, _ = _acc_score(panels, params)
    return np.where(np.isfinite(gate), lift, np.nan), regime
