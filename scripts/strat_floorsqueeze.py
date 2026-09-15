"""Candidate: structural floor-lift ranked, coil-gated (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied):
rank by strat_floorlift log-distance above the trailing floor (structural
compounders with seasoning + 12m trend gate) but only among names eligible
under strat_volsqueeze (6m uptrend + real dispersion history, i.e. coiling
advancers, never dead flats or coiling decliners). Regime is floorlift's
float index-vs-MA exposure (supports weak_exp tiers).

Rationale: floorlift/24 trains +36.6% with forward +17.3% but DD -29.7%
breaches slack; the squeeze gate may trim extended, high-vol names that
drive that DD while keeping the compounder rank. Conversely squeeze alone
is weak; the floor rank may select the coiling subset that actually holds.

PIT-safe: both legs use month-end closes through px[m] only for holding
month starting months[m]; floor needs flb bars, squeeze needs vlb+trend bars.

SPACE = union of strat_floorlift.SPACE and strat_volsqueeze.SPACE.
"""

from __future__ import annotations

import numpy as np

from strat_floorlift import score as _floor_score
from strat_volsqueeze import score as _sq_score

NEEDS_DAILY = False
SPACE = {"note": "union of strat_floorlift.SPACE and strat_volsqueeze.SPACE"}


def score(panels, params):
    lift, regime = _floor_score(panels, params)
    gate, _ = _sq_score(panels, params)
    return np.where(np.isfinite(gate), lift, np.nan), regime
