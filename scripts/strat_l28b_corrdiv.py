"""Candidate: correlation-aware diversified book on the L25 champion (Loop-28 designer B).

Setup in words: rank, eligibility and exposure regime are exactly the champion's
(strat_l23a_liqconfirm, imported, never copied; strict liquid-cohort breadth tiers,
top 25 inverse-vol weights). Only WHICH 25 names fill the book changes. Each month t
the eligible names are walked down the champion rank (best first). A name is
ACCEPTED unless its trailing daily-return correlation with the names already
accepted exceeds cd_c (cd_agg "max": its highest pairwise correlation; "mean": its
average correlation with the accepted set). The walk stops once top + cd_buf names
are accepted (the buffer absorbs the harness's execution masks: next-month price,
circuit lock, traded value). Accepted names are lifted above every rejected name
with their champion order preserved; rejected names keep their champion order below,
as fallbacks. No name is removed and no alpha signal is added: the ordering inside
each group is the champion's rank, so this is a book-construction rule, not a tilt.
Correlations use cd_lb daily log returns of `close` with date < months[t] (point in
time); a name with fewer than cd_lb // 2 returns in the window is always accepted.

Hypothesis: the fresh-print momentum book is crowded - in a sector run it holds
many near-duplicates (same theme, same factor), so its drawdowns are a single bet.
Skipping redundant names for the next-best uncorrelated one should cut DD more
than CAGR. Falsifier: every cd_c either lowers train CAGR by more than the noise
(~0.16 robust) with no DD gain, or leaves the book essentially unchanged.
Thresholds chosen from theory (pairwise daily-return correlation of Indian
small/mid caps is typically 0.2-0.4; 0.5-0.7 flags genuine duplicates), not from
any 2022+ data.

Novelty: registry has no selection-time diversification rule. Closest rows:
strat_l17b_crowd / strat_l17b_corrtrend (DEAD - correlation as a RANK signal, legacy
base), strat_l26a_corrspike (DEAD - correlation spike as an EXPOSURE cut, Nifty 500),
strat_floorhighdiverse / strat_concsectorneutral (DEAD - industry-key diversity,
degraded by the 80%-null industry column; this rule needs no reference column).

Off-switch: cd_c >= 1.0 (default) returns the champion's scores untouched.
Keys: cd_c (corr ceiling), cd_lb (sessions, 60), cd_agg ("max"|"mean"), cd_buf (10).
SPACE: cd_c {0.5, 0.6, 0.7}, cd_lb {60, 120}, cd_agg {max, mean}.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_l23a_liqconfirm import score as _champ

NEEDS_DAILY = True
SPACE = {"cd_c": [1.0, 0.5, 0.6, 0.7], "cd_lb": [60, 120], "cd_agg": ["max", "mean"],
         "cd_buf": [10]}


def daily_returns(panels):
    """dates (np datetime64[D]) and a dates x cols matrix of daily log returns."""
    cols = list(panels["cols"])
    d = (panels["daily"].select("symbol", "date", "close")
         .filter(pl.col("symbol").is_in(cols) & (pl.col("close") > 0))
         .sort("symbol", "date")
         .with_columns(pl.col("close").log().diff().over("symbol").alias("r"))
         .drop_nulls("r"))
    dates = np.unique(d["date"].to_numpy().astype("datetime64[D]"))
    di = np.searchsorted(dates, d["date"].to_numpy().astype("datetime64[D]"))
    cidx = {s: j for j, s in enumerate(cols)}
    cj = np.array([cidx[s] for s in d["symbol"].to_list()])
    R = np.full((len(dates), len(cols)), np.nan)
    R[di, cj] = d["r"].to_numpy()
    return dates, R


def diversify(scores, exposure, panels, params):
    top = int(params.get("top", 25))
    c = float(params.get("cd_c", 1.0))
    lb = int(params.get("cd_lb", 60))
    agg = params.get("cd_agg", "max")
    buf = int(params.get("cd_buf", 10))
    dates, R = daily_returns(panels)
    months = np.asarray(panels["months"]).astype("datetime64[D]")
    out = scores.copy()
    for t in range(len(months)):
        s = scores[t]
        idx = np.flatnonzero(np.isfinite(s))
        if idx.size == 0 or not (np.asarray(exposure)[t] > 0):
            continue
        order = idx[np.argsort(-s[idx], kind="stable")]
        k = int(np.searchsorted(dates, months[t]))  # rows with date < months[t]
        W = R[max(0, k - lb):k][:, order]
        ok = np.isfinite(W).sum(axis=0) >= lb // 2
        Z = np.where(np.isfinite(W), W, 0.0)
        mu = Z.sum(axis=0) / np.maximum(np.isfinite(W).sum(axis=0), 1)
        Z = np.where(np.isfinite(W), W - mu, 0.0)
        nrm = np.sqrt((Z * Z).sum(axis=0))
        nrm[nrm == 0] = np.nan
        U = Z / nrm
        acc, acc_ok = [], []
        for p in range(len(order)):
            if len(acc) >= top + buf:
                break
            if ok[p] and acc_ok:
                cr = U[:, acc_ok].T @ U[:, p]
                cr = cr[np.isfinite(cr)]
                if cr.size:
                    v = cr.max() if agg == "max" else cr.mean()
                    if v > c:
                        continue
            acc.append(p)
            if ok[p]:
                acc_ok.append(p)
        a = order[acc]
        lift = np.nanmax(s[idx]) - np.nanmin(s[idx]) + 1.0
        out[t, a] = s[a] + lift
    return out


def score(panels, params):
    scores, exposure = _champ(panels, params)[:2]
    if float(params.get("cd_c", 1.0)) >= 1.0:
        return scores, exposure
    return diversify(np.asarray(scores, dtype=float), exposure, panels, params), exposure
