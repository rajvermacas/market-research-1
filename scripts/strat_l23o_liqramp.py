"""Candidate: continuous exposure ramp on liquid-cohort breadth.

Setup in words: the champion `strat_floorhighfresh` (fresh-print rank; its
scores are untouched). Exposure is no longer the board-wide breadth tier
(1.0/0.7/0.4/0). It is a linear ramp on LIQUID-cohort breadth: the share of
names with median traded value >= lr_min over lr_days sessions (daily bars
before months[t]) whose close px[t] is above their regime_ma-month average.
The ramp is 0 at breadth <= rp_lo, 1 at >= rp_hi, and linear between, with
exposure below rp_floor rounded down to cash. Liquid breadth is computed by
`strat_l23a_liqconfirm.liquid_breadth`, imported.

Hypothesis: `strat_l23a_liqconfirm` bought its drawdown gain by moving to cash
sooner in the lowest breadth tier, but it changed exposure in only 9 of 94
months. A ramp acts in every month where breadth moves, so the same protection
should rest on a broad footprint rather than two cash months.
Falsifier: no ramp cell beats the champion's robust score by more than its
noise margin, or the gains come with a train DD worse than the champion's
(−18.98%).

PIT: inherited from liqconfirm (closes through px[t], daily bars dated before
months[t]).
Off-switch: rp_on 0 (default) returns the champion exactly.
Keys: champion keys + rp_on, rp_lo, rp_hi, rp_floor, lq_min, lq_days.
Novelty: the registry's breadth "ramps" (legacy, DEAD) ramped whole-board
breadth on the legacy harness; this ramps LIQUID-cohort breadth on the
realistic base (lead #1 of research/loop_state.md after Loop-23).
SPACE: rp_lo {0.45, 0.5, 0.55}, rp_hi {0.65, 0.7, 0.75}, rp_floor {0, 0.3}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfresh import score as _base
from strat_l23a_liqconfirm import liquid_breadth

NEEDS_DAILY = True


def score(panels, params):
    scores, exposure = _base(panels, params)
    if not params.get("rp_on", 0):
        return scores, exposure
    p = {**params, "lq_min": params.get("lq_min", 5e6), "lq_days": params.get("lq_days", 40)}
    b = liquid_breadth(panels, p)
    lo, hi = float(params.get("rp_lo", 0.5)), float(params.get("rp_hi", 0.7))
    floor = float(params.get("rp_floor", 0.0))
    out = np.asarray(exposure, dtype=float).copy()
    for t in range(len(out)):
        if not np.isfinite(b[t]):
            continue
        e = float(np.clip((b[t] - lo) / (hi - lo), 0.0, 1.0))
        out[t] = 0.0 if e < floor else e
    return scores, out
