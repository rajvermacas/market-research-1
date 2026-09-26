"""Candidate: high-BETA count cap on the L25 champion's book (Loop-28 designer B).

Setup in words: identical to strat_l28b_volcap (champion strat_l23a_liqconfirm
imported; top 25 inverse-vol; only WHICH names fill the book changes), but the
capped group is defined by trailing MARKET BETA instead of total volatility. Beta
= cov(r_i, r_m) / var(r_m) over the last bc_lb daily log returns with date <
months[t], where r_m is the equal-weight mean daily log return of all names in the
panel that day (point in time). "High-beta" = beta above the bc_q quantile of that
month's eligible names. Walking down the champion rank, at most bc_k high-beta
names are accepted; the rest are demoted below every accepted name (champion order
kept within each group). Walk stops at top + bc_buf accepted names.

Hypothesis: strat_l28b_volcap showed that capping high-vol names trades CAGR for
DD. If the DD gain is the SYSTEMATIC part (names that gap with the market), a beta
cap should keep more of the CAGR (idiosyncratic high-vol winners stay in) for a
similar DD gain. Falsifier: beta cap cuts DD less than, or costs more CAGR than,
the vol cap at matched (q, k).
Thresholds mirror volcap's theory-chosen grid; no 2022+ data consulted.

Novelty: strat_l17b_beta (DEAD) used rolling beta as a RANK signal on the legacy
base; strat_l28b_volcap caps total vol. No row caps the COUNT of high-beta names.

Off-switch: bc_k >= top (default 99) returns the champion's scores untouched.
Keys: bc_k, bc_q, bc_lb (60), bc_buf (10).
SPACE: bc_q {0.5, 0.67}, bc_k {5, 8, 12}.
"""

from __future__ import annotations

import numpy as np

from strat_l23a_liqconfirm import score as _champ
from strat_l28b_corrdiv import daily_returns

NEEDS_DAILY = True
SPACE = {"bc_q": [0.5, 0.67], "bc_k": [5, 8, 12, 99], "bc_lb": [60], "bc_buf": [10]}


def cap(scores, exposure, panels, params):
    top = int(params.get("top", 25))
    k_max = int(params.get("bc_k", 99))
    q = float(params.get("bc_q", 0.5))
    lb = int(params.get("bc_lb", 60))
    buf = int(params.get("bc_buf", 10))
    dates, R = daily_returns(panels)
    with np.errstate(invalid="ignore"):
        rm = np.nanmean(R, axis=1)
    months = np.asarray(panels["months"]).astype("datetime64[D]")
    out = scores.copy()
    for t in range(len(months)):
        s = scores[t]
        idx = np.flatnonzero(np.isfinite(s))
        if idx.size == 0 or not (np.asarray(exposure)[t] > 0):
            continue
        k = int(np.searchsorted(dates, months[t]))
        W = R[max(0, k - lb):k][:, idx]
        m = rm[max(0, k - lb):k]
        fin = np.isfinite(W) & np.isfinite(m)[:, None]
        n = fin.sum(axis=0)
        Wz = np.where(fin, W, 0.0)
        Mz = np.where(fin, m[:, None], 0.0)
        nn = np.maximum(n, 1)
        mw, mm = Wz.sum(0) / nn, Mz.sum(0) / nn
        cov = (np.where(fin, (W - mw) * (m[:, None] - mm), 0.0)).sum(0) / nn
        var = (np.where(fin, (m[:, None] - mm) ** 2, 0.0)).sum(0) / nn
        with np.errstate(invalid="ignore", divide="ignore"):
            beta = np.where((n >= lb // 2) & (var > 0), cov / var, np.nan)
        if not np.isfinite(beta).any():
            continue
        thr = np.nanquantile(beta, q)
        hb = np.isfinite(beta) & (beta > thr)
        pos = np.argsort(-s[idx], kind="stable")
        acc, nh = [], 0
        for p in pos:
            if len(acc) >= top + buf:
                break
            if hb[p]:
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
    if int(params.get("bc_k", 99)) >= int(params.get("top", 25)):
        return scores, exposure
    return cap(np.asarray(scores, dtype=float), exposure, panels, params), exposure
