"""Candidate: breakout proximity ranked, sponsorship-gated (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied):
rank by strat_newhigh proximity to the trailing high (fresh breakouts and
bases within max_dist) but only among names eligible under strat_liqtrend
(expanding volume sponsorship + 6m price confirmation). Regime is the
float index-vs-MA exposure (supports weak_exp tiers).

Rationale: newhigh timing alone overfits (train +33.8%, fwd +6.5%);
breakouts that hold tend to carry sponsorship, so the liqtrend gate may
select the subset with real accumulation behind the high. Untested combo.

PIT-safe: rank uses month-end closes through px[m]; liqtrend uses daily
bars with date < months[m] plus closes through px[m] for its price gate.

SPACE = union of strat_newhigh.SPACE and strat_liqtrend.SPACE.
"""

from __future__ import annotations

import numpy as np

from strat_liqtrend import score as _liq_score
from strat_newhigh import score as _high_score

NEEDS_DAILY = True
SPACE = {"note": "union of strat_newhigh.SPACE and strat_liqtrend.SPACE"}


def score(panels, params):
    prox, _ = _high_score(panels, params)
    gate, regime = _liq_score(panels, params)
    out = np.where(np.isfinite(gate), prox, np.nan)
    return out, regime
