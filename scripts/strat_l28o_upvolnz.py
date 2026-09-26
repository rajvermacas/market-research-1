"""Candidate: up-value-share re-arm from a NONZERO base only (Loop-28 orchestrator).

Setup in words: rank, eligibility and breadth-tier exposure are exactly
strat_l23a_liqconfirm; the up-value share UVS (value-weighted share of board
turnover on advancing names over the last uv_days sessions before months[t])
is strat_l28c_upvol.monthly_uvs (imported, never copied). Re-arm as in
strat_l28c_upvol (UVS > uv_hi and tier exposure < 1 -> exposure = max(exposure,
uv_to)), EXCEPT that a month whose tier exposure is 0 (full cash) is never
re-armed: the rule may only top up a partially invested book.

Purpose (pre-registered falsification, written before any trial of this file):
l28c_upvol's best cell (63d / .57 / 1.0: 34.56/-17.19) fires in 2016-09
(base 0.7), 2020-07 (base 0.0), 2020-08 and 2020-09 (base 0.4). If the gain is
a genuine breadth-of-buying confirmation it should mostly survive without the
cash-month re-arm; if it collapses toward 30.09 the upvol lead is the
post-COVID V (the same episode as l27o_corerearm / l28a_thrust) and is closed.
Falsifier: train CAGR within 1pp of the champion at every tested cell.

Novelty: a scoped variant of l28c_upvol (same signal) run only as a
falsification test of that lead, not a new mechanism; it is not counted as one.
Off-switch: uv_to = 0 -> champion exactly.
SPACE: uv_days {42, 63, 84}, uv_hi {.56, .57}, uv_to {1.0}.
"""

from __future__ import annotations

import numpy as np

from strat_l23a_liqconfirm import score as _base
from strat_l28c_upvol import monthly_uvs

NEEDS_DAILY = True
SPACE = {"uv_days": [42, 63, 84], "uv_hi": [0.56, 0.57], "uv_to": [1.0]}


def score(panels, params):
    scores, exposure = _base(panels, params)
    to = float(params.get("uv_to", 0.0))
    if to <= 0:
        return scores, exposure
    u = monthly_uvs(panels, int(params.get("uv_days", 63)))
    hi = float(params.get("uv_hi", 0.57))
    out = np.asarray(exposure, dtype=float).copy()
    for t in range(len(out)):
        if np.isfinite(u[t]) and u[t] > hi and 0.0 < out[t] < 1.0:
            out[t] = max(out[t], to)
    return scores, out
