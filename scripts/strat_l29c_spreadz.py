"""Candidate: spread own-history z-score rank tilt on the L25 champion (Loop-29 C).

Setup in words: scores and exposure exactly as strat_l23a_liqconfirm (imported,
verbatim; universe nse_all, invvol top 25 via policy keys). Per name, L[t] =
trailing mean of monthly Corwin-Schultz spread buckets t-sp_lb..t-1 (every
daily bar dated < months[t]; estimator strat_l20b_spread._monthly_spread and
series builder strat_l21b_spreadz._level_series, both imported, never copied).
z[t] = (L[t] - mean(L[t-sz_lb..t-1])) / std(same), needing >= ceil(sz_frac *
sz_lb) finite prior rows and std > 0. Cross-sectional percentile pct of z among
names with finite z (>= 5); score * (1 + sz_w*(2*pct-1)). sz_w < 0 favours names
whose spread is TIGHT relative to their own past (the legacy promoted sign,
-0.05). NaN scores stay NaN; sz_w = 0 is the exact off-switch. Exposure
untouched.

Hypothesis: a name whose spread has narrowed versus its own history is gaining
liquidity/attention, which under realistic next-open fills should lower slippage
and adverse selection; the own-history normalisation removes the size/level
effect that made the CS-level tilt (l27b_spread) an illiquidity bet.
Falsifier: neither sign beats +30.09/-17.22 train at no deeper DD, or the gain
sits inside the random-tilt null (strat_l29c_randtilt: 12 rows, train CAGR
28.9-32.6, mean ~30.6).

Novelty: strat_l21b_spreadz (L21, PROMOTED on the legacy chain, sz_lb 24 / z /
-0.05: 104.45/-14.96) was fitted under the legacy execution model that bought
un-fillable limit-up names; only the spread LEVEL (l27b_spread, gated, fwd
-3.23pp) and amihud/roll/zeroret were retested on the realistic base. No
L22-L28 realistic ledger row carries sz_w. Changed base: realistic execution +
liqconfirm strict regime + invvol top 25 book.
"""
from __future__ import annotations
import numpy as np
from strat_l23a_liqconfirm import score as _base
from strat_l20b_spread import _monthly_spread
from strat_l21b_spreadz import _level_series

NEEDS_DAILY = True
SPACE = {"sz_w": [-0.1, -0.05, 0.05, 0.1], "sz_lb": [24], "sp_lb": [4],
         "sp_frac": [0.5], "sz_frac": [0.5]}


def score(panels, params):
    scores, exposure = _base(panels, params)
    w = float(params.get("sz_w", 0.0))
    if w == 0.0:
        return scores, exposure
    slb = int(params.get("sp_lb", 4))
    zlb = int(params.get("sz_lb", 24))
    need_win = max(2, int(np.ceil(float(params.get("sp_frac", 0.5)) * slb)))
    need_own = max(3, int(np.ceil(float(params.get("sz_frac", 0.5)) * zlb)))
    L = _level_series(_monthly_spread(panels["daily"], panels["months"], panels["cols"]),
                      slb, need_win)
    out = np.array(scores, dtype=float, copy=True)
    for t in range(slb + zlb, out.shape[0]):
        h = L[t - zlb:t]                      # strictly prior rows
        cnt = np.isfinite(h).sum(axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                mu = np.nanmean(h, axis=0)
                sd = np.nanstd(h, axis=0)
            z = (L[t] - mu) / sd
        z = np.where((cnt >= need_own) & (sd > 0) & np.isfinite(L[t]), z, np.nan)
        valid = np.isfinite(z)
        n = int(valid.sum())
        if n < 5:
            continue
        order = np.argsort(z[valid], kind="stable")
        pct = np.empty(n)
        pct[order] = np.arange(n) / (n - 1)
        tilt = np.ones(out.shape[1])
        tilt[valid] = 1.0 + w * (2.0 * pct - 1.0)
        out[t] = np.where(np.isfinite(out[t]), out[t] * tilt, np.nan)
    return out, exposure
