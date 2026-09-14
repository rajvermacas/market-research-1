"""Candidate: momentum timing-gated by RSI pullback (strategy_lab contract).

Mutation combining the two mechanisms tested so far: rank by trailing
momentum (the return driver) but only among names currently showing a
pullback-turn inside an intact uptrend (the timing gate). Momentum alone
holds winners that are already extended; pullback alone earns less than the
bench. The question is whether timing the winners buys back return without
re-importing momentum's drawdown.

Implementation reuses both candidates verbatim — no second copy of either
signal: strat_momentum supplies ranked returns + regime, strat_rsi_pullback
supplies the eligibility gate (finite score = eligible). Params are the union
of both SPACEs; unset keys fall back to each file's own defaults.
"""

from __future__ import annotations

import numpy as np

from strat_momentum import score as _mom_score
from strat_rsi_pullback import score as _pb_score

NEEDS_DAILY = True
SPACE = {"note": "union of strat_momentum.SPACE and strat_rsi_pullback.SPACE"}


def score(panels, params):
    mom, regime = _mom_score(panels, params)
    gate, _ = _pb_score(panels, params)
    return np.where(np.isfinite(gate), mom, np.nan), regime
