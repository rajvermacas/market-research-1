"""Candidate: breadth-momentum-gated tier exposure (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank by
strat_floorhigh, exposure level from strat_newhigh_tier breadth tiers — but
entry is gated on breadth DIRECTION: the book may hold risk in month t only
if tier exposure did not just step down (tier_exp[t] >= tier_exp[t-1]);
after a step-down month the book sits out that month even if the level is
still mid-tier, re-entering when the level stops falling.

Rationale: tier levels are slow-moving and exit late — the book rides
exposure 0.7/0.4 through months of deteriorating participation. If breadth
deterioration leads drawdowns, a directional exit (fast out on the step
down, Entries only on stable/rising breadth) cuts the left tail with at most
one month of whipsaw cost. If levels already time it well, this trails.

PIT-safe: the gate compares imported exposure values at t and t-1 only,
both known when ranking for the holding month starting months[m]; month 0
defaults to allowed (no history = no evidence of deterioration).

SPACE = strat_floorhightier params (no new knobs; the gate is structural).
"""

from __future__ import annotations

import numpy as np

from strat_floorhigh import score as _fh_score
from strat_newhigh_tier import score as _tier_score

NEEDS_DAILY = False
SPACE = {"note": "strat_floorhightier params; directional gate is structural"}


def score(panels, params):
    rank, _ = _fh_score(panels, params)
    _, tier_exp = _tier_score(panels, params)
    tier_exp = np.asarray(tier_exp, dtype=float)
    gate = np.ones_like(tier_exp)
    gate[1:] = (tier_exp[1:] >= tier_exp[:-1]).astype(float)
    return rank, tier_exp * gate
