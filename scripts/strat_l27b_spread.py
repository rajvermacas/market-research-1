"""Candidate: Corwin-Schultz spread-level rank tilt on the L23-A champion (Loop-27 B).

Setup in words: scores and exposure exactly as strat_l23a_liqconfirm
(imported, verbatim). For each name at month t, sv = mean of the monthly
Corwin-Schultz two-day spread buckets t-sp_lb..t-1 (all daily bars dated
< months[t]; spread estimator imported from strat_l20b_spread._monthly_spread,
not copied), requiring >= ceil(sp_frac*sp_lb) finite buckets. Cross-sectional
percentile pct of sv among names with a finite score; score multiplied by
1 + sp_w*(2*pct-1). sp_w<0 favours tight-spread names. NaN scores stay NaN;
sp_w=0 is the exact off-switch (returns the champion's arrays untouched).
Regime/exposure untouched.

Hypothesis: under realistic execution (next-open fills, 50 bps cost, lock
blocks) the realised cost of a fresh-print name scales with its spread, so a
tight-spread tilt should persist for an economic reason (lower slippage and
fewer adverse fills), unlike pure train-fit tilts.
Falsifier: neither sign beats +30.09/-17.22 train.

Novelty: closest rows strat_l20b_spread (L20, promoted then superseded, on
the L19 legacy-exec chain) and strat_l21b_spreadz/spreadchg/spreadnorm/
spreadvol (L21, same legacy chain). Declared changed-base retest: the one
thing that changed is the base - L23-A liquid-confirmed champion under the
realistic harness. Distinct from the dead L22+ fillability tilts (advtilt =
traded value, lockpen = circuit locks, gappen = gaps, liqrs = liquid-subset
RS): none of those measures the high-low bid-ask spread.
"""
from __future__ import annotations
import warnings
import numpy as np
from strat_l23a_liqconfirm import score as _base
from strat_l20b_spread import _monthly_spread

NEEDS_DAILY = True
SPACE = {"sp_w": [-0.1, -0.05, 0.05, 0.1], "sp_lb": [6], "sp_frac": [0.5]}


def _pct_tilt(scores, sig, w):
    out = np.array(scores, dtype=float, copy=True)
    for t in range(out.shape[0]):
        m = np.isfinite(out[t]) & np.isfinite(sig[t])
        if m.sum() < 2:
            continue
        v = sig[t, m]
        r = v.argsort().argsort().astype(float)
        pct = r / (len(v) - 1)
        out[t, m] = out[t, m] * (1.0 + w * (2 * pct - 1))
    return out


def score(panels, params):
    scores, exposure = _base(panels, params)
    w = float(params.get("sp_w", 0.0))
    if w == 0.0:
        return scores, exposure
    lb = int(params.get("sp_lb", 6))
    need = max(2, int(np.ceil(float(params.get("sp_frac", 0.5)) * lb)))
    spr = _monthly_spread(panels["daily"], panels["months"], panels["cols"])
    sig = np.full(spr.shape, np.nan)
    for t in range(lb, spr.shape[0]):
        win = spr[t - lb:t]  # buckets t-lb..t-1: every bar dated < months[t]
        cnt = np.isfinite(win).sum(axis=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            val = np.nanmean(win, axis=0)
        sig[t] = np.where(cnt >= need, val, np.nan)
    return _pct_tilt(scores, sig, w), exposure
