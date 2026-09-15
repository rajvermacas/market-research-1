"""Candidate: volatility-scaled floor-lift (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied):
rank by strat_floorlift log-distance above the trailing floor divided by
trailing 3m realized monthly vol (vol recovered as -1 * strat_volsqueeze
score, which ranks tightest coil first). Eligibility needs both legs
finite (full floor window + 12m trend + 6m uptrend + real dispersion).
Regime is floorlift's float index-vs-MA exposure (supports weak_exp tiers).

Rationale: raw lift crowns the most violent multi-year rallies; scaling by
vol prefers smooth compounders grinding above their floor, which should cut
the DD that breaches slack on every floor variant so far.

PIT-safe: both legs use month-end closes through px[m] only for holding
month starting months[m].

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
    sq, _ = _sq_score(panels, params)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = lift / (-sq)
    out[~np.isfinite(lift) | ~np.isfinite(sq) | ((-sq) <= 0)] = np.nan
    return out, regime
