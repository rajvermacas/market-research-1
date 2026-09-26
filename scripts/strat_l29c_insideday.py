"""Candidate: inside-day pause-share rank tilt on the L25 champion (Loop-29 C).

Setup in words: scores and exposure exactly as strat_l23a_liqconfirm (imported,
verbatim; universe nse_all, invvol top 25 set by the harness policy keys).
For each name at month t, share = mean of the monthly inside-day share buckets
t-ids_lb..t-1 (every daily bar dated < months[t]; a bar is "inside" when its
high < prior high and low > prior low; bucket builder imported from
strat_l15b_insideday._monthly_inside, not copied). Cross-sectional percentile
pct of share over names with a finite share (>= 5 names); the champion's score
is multiplied by 1 + ids_w*(2*pct-1). ids_w < 0 favours names that did NOT
pause (few inside days) - the legacy champion's sign. NaN scores stay NaN;
ids_w = 0 is the exact off-switch. Exposure untouched.

Hypothesis: a fresh-print name that keeps expanding its range (few inside
days) is in active price discovery; one that compresses is stalling. Under
realistic execution the stalling names are also the ones whose next-open fill
buys the top of a coil. Falsifier: neither sign beats +30.09/-17.22 train at
no deeper DD, or it gains train CAGR while hurting fold consistency.

Novelty: strat_l15b_insideday (L15, PROMOTED on the legacy chain, ids_lb 3 /
ids_w -0.13, train 96.88/-17.03 under the legacy execution model that bought
un-fillable limit-up names). Never run on the realistic harness: no l22-l28
realistic ledger row carries ids_w. Changed base: realistic execution (next-
open fills, lock/traded-value blocks, 50 bps) + liqconfirm strict regime +
invvol top 25 book.
"""
from __future__ import annotations
import warnings
import numpy as np
from strat_l23a_liqconfirm import score as _base
from strat_l15b_insideday import _monthly_inside

NEEDS_DAILY = True
SPACE = {"ids_w": [-0.2, -0.13, -0.07, 0.07, 0.13], "ids_lb": [3, 6]}

_CACHE: dict = {}


def score(panels, params):
    scores, exposure = _base(panels, params)
    w = float(params.get("ids_w", 0.0))
    if w == 0.0:
        return scores, exposure
    lb = int(params.get("ids_lb", 3))
    key = (id(panels["daily"]), len(panels["months"]), len(panels["cols"]))
    if key not in _CACHE:
        _CACHE[key] = _monthly_inside(panels["daily"], panels["months"], panels["cols"])
    ids = _CACHE[key]
    out = np.array(scores, dtype=float, copy=True)
    for t in range(lb, out.shape[0]):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            share = np.nanmean(ids[t - lb:t], axis=0)  # buckets t-lb..t-1: bars < months[t]
        valid = np.isfinite(share)
        n = int(valid.sum())
        if n < 5:
            continue
        order = np.argsort(share[valid], kind="stable")
        pct = np.empty(n)
        pct[order] = np.arange(n) / (n - 1)
        tilt = np.ones(out.shape[1])
        tilt[valid] = 1.0 + w * (2.0 * pct - 1.0)
        ok = np.isfinite(out[t])
        out[t] = np.where(ok, out[t] * tilt, np.nan)
    return out, exposure
