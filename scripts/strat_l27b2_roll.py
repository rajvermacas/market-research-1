"""Candidate: Roll (1984) serial-covariance spread-level rank tilt on the L23-A champion (Loop-27 B2).

Setup in words: scores and exposure exactly as strat_l23a_liqconfirm (imported,
verbatim). For each name at month t, rv = mean of the monthly Roll implied-
spread buckets t-rl_lb..t-1 (S = 2*sqrt(max(0,-cov(r_t, r_{t-1}))) from daily
close-to-close returns, buckets with < 10 pairs NaN; estimator imported from
strat_l21b_spreadvol._monthly_roll, not copied), every bar dated < months[t],
requiring >= ceil(rl_frac*rl_lb) finite buckets (window helper imported from
strat_l27b2_amihud). Cross-sectional percentile pct; score *= 1 + rl_w*(2*pct-1)
(strat_l27b_spread._pct_tilt). rl_w>0 favours WIDE implied spreads. rl_w=0 is
the exact off-switch. Regime/exposure untouched.

Question: is the round-1 Corwin-Schultz result the bid-ask spread itself? Roll
estimates the same spread from a genuinely different input (close-only
negative serial covariance, no high/low range). If Roll reproduces the CS
effect the spread is real; if not, the CS tilt is picking up intraday range
(volatility), not cost.
Falsifier: neither sign beats 30.09/-17.22 train.

Novelty: closest row strat_l21b_spreadvol, which used Roll only as an in-file
robustness input to spread DISPERSION (6m, -0.05) on the L19/L20 legacy chain;
Roll LEVEL has never been a rank tilt, and never on the realistic-exec L23-A
champion. One thing changed: Roll LEVEL as the rank signal on the new base.
SPACE: rl_w in {-0.2,-0.1,+0.1,+0.2}, rl_lb in {6,9,12}, rl_frac 0.5.
"""
from __future__ import annotations
import numpy as np
from strat_l23a_liqconfirm import score as _base
from strat_l21b_spreadvol import _monthly_roll
from strat_l27b_spread import _pct_tilt
from strat_l27b2_amihud import window_mean

NEEDS_DAILY = True
SPACE = {"rl_w": [-0.2, -0.1, 0.1, 0.2], "rl_lb": [6, 9, 12], "rl_frac": [0.5]}


def score(panels, params):
    scores, exposure = _base(panels, params)
    w = float(params.get("rl_w", 0.0))
    if w == 0.0:
        return scores, exposure
    lb = int(params.get("rl_lb", 9))
    need = max(2, int(np.ceil(float(params.get("rl_frac", 0.5)) * lb)))
    rs = _monthly_roll(panels["daily"], panels["months"], panels["cols"])
    return _pct_tilt(scores, window_mean(rs, lb, need), w), exposure
