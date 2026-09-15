"""Candidate: structural floor-lift ranked, breakout-timed (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied):
rank by strat_floorlift log-distance above the trailing floor (structural
compounders with seasoning + 12m trend gate) but only among names within
`max_dist` of their trailing high per strat_newhigh (fresh breakouts/bases,
not runaway extenders or basement bounces). Regime is floorlift's float
index-vs-MA exposure (supports weak_exp tiers).

Rationale: floorlift/24 trains +36.6% with forward +17.3% but DD -29.7%
breaches the best-DD slack; newhigh timing may trim the extended tail that
drives that DD. Conversely newhigh alone overfits (train +33.8%, fwd +6.5%);
the seasoning + floor-distance rank may select the subset that holds forward.

PIT-safe: both legs use month-end closes through px[m] only for holding
month starting months[m]; floor needs flb bars, high needs lb bars.

SPACE = union of strat_floorlift.SPACE and strat_newhigh.SPACE.
"""

from __future__ import annotations

import numpy as np

from strat_floorlift import score as _floor_score
from strat_newhigh import score as _high_score

NEEDS_DAILY = False
SPACE = {"note": "union of strat_floorlift.SPACE and strat_newhigh.SPACE"}


def score(panels, params):
    lift, regime = _floor_score(panels, params)
    prox, _ = _high_score(panels, params)
    return np.where(np.isfinite(prox), lift, np.nan), regime
