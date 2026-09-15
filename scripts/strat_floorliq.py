"""Candidate: structural floor-lift ranked, sponsorship-gated (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied):
rank by strat_floorlift log-distance above the trailing floor (structural
compounders with seasoning + 12m trend gate) but only among names eligible
under strat_liqtrend (expanding volume sponsorship + 6m price confirmation).
Regime is floorlift's float index-vs-MA exposure (supports weak_exp tiers).

Rationale: floor rank crowns multi-year compounders but cannot tell
sponsored accumulation from a thin drift above an old floor; the liqtrend
gate keeps only names whose advance arrives on expanding share volume.
Untested combo — no liqtrend composition has run in the lab yet.

PIT-safe: rank uses month-end closes through px[m]; liqtrend uses daily
bars with date < months[m] plus closes through px[m] for its price gate.

SPACE = union of strat_floorlift.SPACE and strat_liqtrend.SPACE.
"""

from __future__ import annotations

import numpy as np

from strat_floorlift import score as _floor_score
from strat_liqtrend import score as _liq_score

NEEDS_DAILY = True
SPACE = {"note": "union of strat_floorlift.SPACE and strat_liqtrend.SPACE"}


def score(panels, params):
    lift, regime = _floor_score(panels, params)
    gate, _ = _liq_score(panels, params)
    return np.where(np.isfinite(gate), lift, np.nan), regime
