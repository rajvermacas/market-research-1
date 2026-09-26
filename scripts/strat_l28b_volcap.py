"""Candidate: high-volatility COUNT cap on the L25 champion's book (Loop-28 designer B).

Setup in words: rank, eligibility and the exposure regime are exactly the champion's
(strat_l23a_liqconfirm, imported; top 25 inverse-vol weights). Only WHICH 25 names
fill the book changes. Each month t, trailing volatility is the std of the last
vc_lb daily log returns with date < months[t] (point in time; daily_returns imported
from strat_l28b_corrdiv). A name is "high-vol" if its vol is above the vc_q quantile
of the vols of that month's eligible (finite-score) names. Walking down the champion
rank, high-vol names are accepted until vc_k of them are in; further high-vol names
are demoted below every accepted name (champion order preserved within each group),
so the next-ranked calmer names take their places. The walk stops once top + vc_buf
names are accepted (buffer for the harness's execution masks). Names without enough
history (< vc_lb // 2 returns) count as not high-vol.

Hypothesis: inverse-vol weights already shrink the wild names' weight, but they
still occupy slots; in drawdowns the high-vol cluster gaps together. Capping how
many of them the book holds (a composition constraint, not a score tilt: order
inside each group is unchanged) cuts DD more than CAGR. Falsifier: every cell
loses train CAGR beyond noise with DD no better than -17.22.
Thresholds from theory (tercile / half / quintile splits; k spans a fifth to
half the book), not from any 2022+ data.

Novelty: the legacy vol rows (strat_concvolgate, strat_volfloor, strat_floorhighvoltarget,
..., DEAD) scale EXPOSURE or RANK by vol on legacy execution; policy weighting=invvol
(L24/L25) sets WEIGHTS. None constrains the COUNT of high-vol names in the book.

Off-switch: vc_k >= top (default 99) returns the champion's scores untouched.
Keys: vc_k (max high-vol names), vc_q (quantile), vc_lb (60 sessions), vc_buf (10).
SPACE: vc_q {0.5, 0.67, 0.8}, vc_k {3, 5, 8, 12}.
"""

from __future__ import annotations

import numpy as np

from strat_l23a_liqconfirm import score as _champ
from strat_l28b_corrdiv import daily_returns

NEEDS_DAILY = True
SPACE = {"vc_q": [0.5, 0.67, 0.8], "vc_k": [3, 5, 8, 12, 99], "vc_lb": [60], "vc_buf": [10]}


def cap(scores, exposure, panels, params):
    top = int(params.get("top", 25))
    k_max = int(params.get("vc_k", 99))
    q = float(params.get("vc_q", 0.67))
    lb = int(params.get("vc_lb", 60))
    buf = int(params.get("vc_buf", 10))
    dates, R = daily_returns(panels)
    months = np.asarray(panels["months"]).astype("datetime64[D]")
    out = scores.copy()
    for t in range(len(months)):
        s = scores[t]
        idx = np.flatnonzero(np.isfinite(s))
        if idx.size == 0 or not (np.asarray(exposure)[t] > 0):
            continue
        k = int(np.searchsorted(dates, months[t]))
        W = R[max(0, k - lb):k][:, idx]
        n = np.isfinite(W).sum(axis=0)
        with np.errstate(invalid="ignore"):
            v = np.where(n >= lb // 2, np.nanstd(np.where(n >= 2, W, np.nan), axis=0), np.nan)
        if not np.isfinite(v).any():
            continue
        thr = np.nanquantile(v, q)
        hv = np.isfinite(v) & (v > thr)
        pos = np.argsort(-s[idx], kind="stable")
        acc, nh = [], 0
        for p in pos:
            if len(acc) >= top + buf:
                break
            if hv[p]:
                if nh >= k_max:
                    continue
                nh += 1
            acc.append(idx[p])
        a = np.asarray(acc, dtype=int)
        lift = np.nanmax(s[idx]) - np.nanmin(s[idx]) + 1.0
        out[t, a] = s[a] + lift
    return out


def score(panels, params):
    scores, exposure = _champ(panels, params)[:2]
    if int(params.get("vc_k", 99)) >= int(params.get("top", 25)):
        return scores, exposure
    return cap(np.asarray(scores, dtype=float), exposure, panels, params), exposure
