"""Candidate: breakout proximity ranked, coil-gated, float regime (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied):
rank by strat_newhigh proximity to the trailing high (fresh breakouts/bases)
but only among names eligible under strat_volsqueeze (6m uptrend + real
dispersion, i.e. coiling advancers). Regime is volsqueeze's float
index-vs-MA exposure (supports weak_exp tiers: 0.0 cash vs 0.4 stay-in).

Rationale: newhigh alone overfits (train +33.8%, fwd +6.5%); the coil gate
may select the subset pressing into highs on compression rather than
blowoff spikes. Float regime (weak_exp=0.4) is the loop's best forward
mechanism (floorlift weak fwd +20.2%), so this file supports it per trial.

PIT-safe: both legs use month-end closes through px[m] only for holding
month starting months[m]; high needs lb bars, squeeze needs vlb+trend bars.

SPACE = union of strat_newhigh.SPACE and strat_volsqueeze.SPACE.
"""

from __future__ import annotations

import numpy as np

from strat_newhigh import score as _high_score
from strat_volsqueeze import score as _sq_score

NEEDS_DAILY = False
SPACE = {"note": "union of strat_newhigh.SPACE and strat_volsqueeze.SPACE"}


def score(panels, params):
    prox, _ = _high_score(panels, params)
    gate, regime = _sq_score(panels, params)
    return np.where(np.isfinite(gate), prox, np.nan), regime
