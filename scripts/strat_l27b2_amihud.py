"""Candidate: Amihud illiquidity-level rank tilt on the L23-A champion (Loop-27 B2).

Setup in words: scores and exposure exactly as strat_l23a_liqconfirm (imported,
verbatim). For each name at month t, iv = mean of the monthly Amihud buckets
t-am_lb..t-1 (bucket = mean daily |close/prev_close-1| / (close*volume);
estimator imported from strat_l20b_illiq._monthly_illiq, not copied), every bar
dated < months[t], requiring >= ceil(am_frac*am_lb) finite buckets. Cross-
sectional percentile pct of iv among names with a finite score; score *=
1 + am_w*(2*pct-1) (imported strat_l27b_spread._pct_tilt). am_w>0 favours
ILLIQUID names (Amihud premium); am_w<0 favours liquid names. NaN stays NaN.
am_w=0 is the exact off-switch (champion arrays returned untouched).
Regime/exposure untouched (designer A's axis).

Question: round 1 found a wide Corwin-Schultz spread tilt (+0.2, lb 9) lifts
the champion to 35.19/-15.84. Is that the SPREAD (high-low bounce) or
illiquidity generally? Amihud measures price impact per rupee traded, a
different estimator from different inputs (close + volume, no high/low).
Falsifier: neither sign beats 30.09/-17.22 train -> the round-1 effect is
spread-specific, not a generic illiquidity premium.

Novelty: closest rows strat_l20b_illiq (KEEP-not-promoted, L19 legacy chain,
legacy exec) and strat_l20b2_liqcombo / strat_l21o_liqdiv (legacy compositions).
Declared changed-base retest: the one thing changed is the BASE - the L23-A
liquid-confirmed champion under the realistic harness (next-open fills, 50 bps,
locks, min_tv). Distinct from dead L22 advtilt (traded-value LEVEL, no return).
SPACE: am_w in {-0.2,-0.1,+0.1,+0.2}, am_lb in {6,9,12}, am_frac 0.5.
"""
from __future__ import annotations
import warnings
import numpy as np
from strat_l23a_liqconfirm import score as _base
from strat_l20b_illiq import _monthly_illiq
from strat_l27b_spread import _pct_tilt

NEEDS_DAILY = True
SPACE = {"am_w": [-0.2, -0.1, 0.1, 0.2], "am_lb": [6, 9, 12], "am_frac": [0.5]}


def window_mean(buckets, lb, need):
    sig = np.full(buckets.shape, np.nan)
    for t in range(lb, buckets.shape[0]):
        win = buckets[t - lb:t]  # buckets t-lb..t-1: every bar dated < months[t]
        cnt = np.isfinite(win).sum(axis=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            val = np.nanmean(win, axis=0)
        sig[t] = np.where(cnt >= need, val, np.nan)
    return sig


def amihud_signal(panels, params):
    lb = int(params.get("am_lb", 9))
    need = max(2, int(np.ceil(float(params.get("am_frac", 0.5)) * lb)))
    ill = _monthly_illiq(panels["daily"], panels["months"], panels["cols"])
    return window_mean(ill, lb, need)


def score(panels, params):
    scores, exposure = _base(panels, params)
    w = float(params.get("am_w", 0.0))
    if w == 0.0:
        return scores, exposure
    return _pct_tilt(scores, amihud_signal(panels, params), w), exposure
