"""Candidate: breakout-magnitude tilt on the L23-A champion (Loop-26 B).

Setup in words: scores and exposure exactly as strat_l23a_liqconfirm (imported).
bm = px[t] / max(px[t-bm_lb .. t-1]) - 1: how far the current month-end close
sits above the prior bm_lb-month base high (closes through px[t] only).
Cross-sectional percentile pct among names with a finite score; score is
multiplied by 1 + bm_w*(2*pct-1). NaN stays NaN; bm_w=0 is the exact off-switch.
Regime untouched.

Hypothesis: a decisive clearance of the prior base (bm_w>0) marks demand, or
alternatively a marginal clearance (bm_w<0) leaves room to run; one sign lifts
train CAGR at no DD cost.
Falsifier: neither sign beats +30.09/-17.22 train.

Novelty: the registry's breakout rows (strat_breakrec / strat_floorbreak /
strat_highbase, legacy DEAD) scored breakout RECENCY and base DURATION, not the
magnitude above the base; the closed less-extended axis (strat_l23b_ddquality,
strat_l17d_reldd) measures distance below a high, not clearance above a prior
base. New signal on the realistic L23-A base.
"""
from __future__ import annotations
import numpy as np
from strat_l23a_liqconfirm import score as _base
from strat_l26b_upmonths import _pct_tilt

NEEDS_DAILY = True
SPACE = {"bm_w": [-0.2, 0.2], "bm_lb": [12]}


def score(panels, params):
    scores, exposure = _base(panels, params)
    w = float(params.get("bm_w", 0.0))
    if w == 0.0:
        return scores, exposure
    lb = int(params.get("bm_lb", 12))
    px = panels["px"]
    sig = np.full_like(px, np.nan, dtype=float)
    for t in range(lb, px.shape[0]):
        win = px[t - lb:t]
        n = np.isfinite(win).sum(axis=0)
        with np.errstate(invalid="ignore", divide="ignore"), np.testing.suppress_warnings() as sw:
            sw.filter(RuntimeWarning)
            hi = np.nanmax(np.where(n >= lb // 2, win, np.nan), axis=0)
            sig[t] = px[t] / hi - 1
    return _pct_tilt(scores, sig, w), exposure
