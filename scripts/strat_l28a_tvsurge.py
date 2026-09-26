"""Candidate: board traded-value SURGE (volume climax) exposure cut (Loop-28 A).

Setup in words: rank, eligibility, breadth-tier exposure and book are exactly
strat_l23a_liqconfirm (imported, never copied). A board-level turnover gauge
is added: TV_d = sum over every nse_all symbol of close*volume on session d.
For month t, using only sessions with date < months[t]:
recent = mean TV over the last 21*tv_k sessions, base = mean TV over the
21*tv_base sessions before those. ratio_t = recent / base. If ratio_t > tv_thr
exposure *= (1 - tv_cut) for that month.

Hypothesis (theory, fixed before looking at any result): speculative peaks
are volume climaxes -- retail participation and turnover surge well above
their trend in the final leg (Jan-2008, Jan-2018 small-cap top); a turnover
surge is a participation-froth signal that the price-level breadth tier does
not see until prices roll over.
Falsifier: no cell improves train DD without costing CAGR, or only one
knife-edge cell does.

Novelty: l27a_froth (illiquid-minus-liquid RETURN spread), l27a_rvpct
(realized VOL percentile), legacy liquidity/volume rows (strat_floorhigh*
part/volconf/accum/spons: per-stock volume GATES or tilts), l22a_advtilt
(per-stock traded-value tilt). None uses the AGGREGATE board turnover's
surge versus its own trend as a market-level exposure signal.

Off-switch: tv_cut = 0 -> champion exactly.
SPACE: tv_k {1,2,3}, tv_base {6,12}, tv_thr {1.4,1.6,1.8,2.0}, tv_cut {0,0.5,1.0}.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_l23a_liqconfirm import score as _base

NEEDS_DAILY = True
SPACE = {"tv_k": [1, 2, 3], "tv_base": [6, 12], "tv_thr": [1.4, 1.6, 1.8, 2.0],
         "tv_cut": [0.0, 0.5, 1.0]}


def board_tv(daily):
    agg = (daily.filter(pl.col("volume") > 0)
           .with_columns(pl.col("date").cast(pl.Date))
           .group_by("date").agg((pl.col("close") * pl.col("volume")).sum().alias("tv"))
           .sort("date"))
    return (np.array([d.toordinal() for d in agg["date"].to_list()]),
            agg["tv"].to_numpy().astype(float))


def tv_ratio(panels, k: int, base: int) -> np.ndarray:
    dord, tv = board_tv(panels["daily"])
    months = panels["months"]
    out = np.full(len(months), np.nan)
    nk, nb = 21 * k, 21 * base
    for t, m in enumerate(months):
        i = int(np.searchsorted(dord, m.toordinal(), "left"))  # sessions < months[t]
        if i - nk - nb < 0:
            continue
        b = tv[i - nk - nb:i - nk].mean()
        if b > 0:
            out[t] = tv[i - nk:i].mean() / b
    return out


def score(panels, params):
    scores, exposure = _base(panels, params)
    cut = float(params.get("tv_cut", 0.0))
    if cut <= 0:
        return scores, exposure
    r = tv_ratio(panels, int(params.get("tv_k", 2)), int(params.get("tv_base", 12)))
    thr = float(params.get("tv_thr", 1.6))
    out = np.asarray(exposure, dtype=float).copy()
    for t in range(len(out)):
        if np.isfinite(r[t]) and r[t] > thr:
            out[t] = out[t] * (1.0 - cut)
    return scores, out
