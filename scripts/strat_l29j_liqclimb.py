"""Candidate: liquidity-rank CLIMB tilt on the champion (Loop-29 J).

Setup in words: scores and exposure exactly as strat_l23a_liqconfirm (imported).
At each decision month m, every name's trailing 60-session median traded value
(close*volume, daily bars with date < months[m] only; strat_l29g_liqcore.median_tv,
imported) is percentile-ranked across the board. The climb is that percentile
now minus the same percentile lc_lb months earlier -- a point-in-time proxy for
"on its way into the index". Among finite-score names the climb is ranked to a
percentile p in [0,1] (names without a lagged rank get p = 0.5, neutral) and the
score is tilted multiplicatively: score * (1 + lc_w * (2p - 1)), the same form as
the null-band strat_l29c_randtilt. Novelty vs l17b volmom / l22a advtilt / l22b
liqrs: those use the LEVEL of liquidity or volume; this uses the CHANGE in the
cross-sectional liquidity rank.

Off-switch: lc_w = 0 (default) returns the imported scores untouched.
"""

from __future__ import annotations

import numpy as np

from strat_l23a_liqconfirm import score as _base
from strat_l29g_liqcore import median_tv

NEEDS_DAILY = True
SPACE = {"lc_w": [0.0, 0.1, 0.2, -0.1], "lc_lb": [6, 12], "lc_days": [60]}


def _pct_rows(M: np.ndarray) -> np.ndarray:
    out = np.full(M.shape, np.nan)
    for t in range(M.shape[0]):
        v = M[t]
        ok = np.isfinite(v) & (v > 0)
        n = int(ok.sum())
        if n < 5:
            continue
        o = np.argsort(v[ok], kind="stable")
        p = np.empty(n)
        p[o] = np.arange(n) / (n - 1)
        out[t, ok] = p
    return out


def score(panels, params):
    scores, exposure = _base(panels, params)
    w = float(params.get("lc_w", 0.0) or 0.0)
    if w == 0.0:
        return scores, exposure
    lb = int(params.get("lc_lb", 6))
    rk = _pct_rows(median_tv(panels, int(params.get("lc_days", 60))))
    climb = np.full(rk.shape, np.nan)
    climb[lb:] = rk[lb:] - rk[:-lb]
    out = np.array(scores, dtype=float, copy=True)
    for t in range(out.shape[0]):
        valid = np.isfinite(out[t])
        c = climb[t]
        has = valid & np.isfinite(c)
        n = int(has.sum())
        if n < 5:
            continue
        pct = np.full(out.shape[1], 0.5)
        o = np.argsort(c[has], kind="stable")
        p = np.empty(n)
        p[o] = np.arange(n) / (n - 1)
        pct[has] = p
        out[t, valid] = out[t, valid] * (1.0 + w * (2.0 * pct[valid] - 1.0))
    return out, exposure
