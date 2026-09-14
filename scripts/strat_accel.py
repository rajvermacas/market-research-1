"""Candidate: trend acceleration, 2nd derivative (strategy_lab contract).

Fresh mechanism — not a level-of-momentum rank. Thesis: momentum holds
steady climbers and fading extenders alike; the second derivative separates
them. Rank by recent-leg return MINUS full-window return (3m sprint vs 12m
march, both ending at the decision month): highest acceleration first, i.e.
names whose trend is STEEPENING. Eligibility needs a positive 12m return so
a violent dead-cat bounce off a collapsed base cannot qualify.

PIT-safe: score for holding month starting months[m] uses closes through
px[m] only.

SPACE = fast {3}, slow {12}, regime_ma {0,6}, weak_exp {0.0,0.4}.
`weak_exp` is the exposure used when the index regime is OFF, so
float-regime tiers are searchable per trial via params-json.
"""

from __future__ import annotations

import numpy as np
import polars as pl

NEEDS_DAILY = False
SPACE = {
    "fast": [3],
    "slow": [12],
    "regime_ma": [0, 6],
    "weak_exp": [0.0, 0.4],
}


def _regime(px, months, start_i, ma, weak_exp):
    reg = np.ones(len(months))
    if ma:
        alive = ~np.isnan(px[start_i])
        idx = np.nanmean(px[:, alive] / px[start_i, alive], axis=1)
        idx_ma = pl.Series(idx).rolling_mean(ma).to_numpy()
        for t in range(len(months)):
            if np.isnan(idx_ma[t]) or not (idx[t] > idx_ma[t]):
                reg[t] = weak_exp
    return reg


def score(panels, params):
    px, months = panels["px"], panels["months"]
    start_i = panels["start_i"]
    fast = int(params.get("fast", 3))
    slow = int(params.get("slow", 12))
    ma = int(params.get("regime_ma", 6))
    weak_exp = float(params.get("weak_exp", 0.0))

    r_fast = np.full_like(px, np.nan)
    r_fast[fast:] = px[fast:] / px[:-fast] - 1
    r_slow = np.full_like(px, np.nan)
    r_slow[slow:] = px[slow:] / px[:-slow] - 1
    out = r_fast - r_slow  # steepening trend ranks first
    out[~(r_slow > 0)] = np.nan  # intact-year-gain eligibility
    return out, _regime(px, months, start_i, ma, weak_exp)
