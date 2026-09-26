"""Candidate: point-in-time liquidity core-satellite on the champion (Loop-29 G).

Setup in words: scores and exposure exactly as strat_l23a_liqconfirm (imported,
never copied). At each decision month m the "core" is the pc_n names with the
highest trailing pc_days-session median daily traded value (close * volume, the
same measure strat_l22b_liqbreadth.liquid_mask uses), read from daily bars with
date < months[m] only. The pc_k highest-scoring ELIGIBLE (finite-score) core
names receive a +1e6 bonus so they occupy pc_k of the top-N slots; the rest fill
from the full board by the champion's score. Order within groups, weighting,
exposure, entry/exit and universe are the champion's.

This is the point-in-time replacement for strat_l29e_coresat, whose core was
TODAY's Nifty 500 flag (look-ahead). Novelty: l22a advtilt (traded-value tilt),
l22b liqrs / l23a liqrank / l23a liqconfirm (liquidity filters / breadth) --
this is a slot RESERVATION keyed on PIT liquidity rank, not a tilt or filter.

Off-switch: pc_k = 0 (default) returns the imported scores untouched.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_l23a_liqconfirm import score as _base

NEEDS_DAILY = True
SPACE = {"pc_k": [0, 8, 15, 17], "pc_n": [300, 500, 800], "pc_days": [60, 120]}
BONUS = 1e6
_C: dict = {}


def median_tv(panels, days: int) -> np.ndarray:
    """months x stocks: median close*volume over the last `days` sessions with
    date < months[t] (NaN where unavailable). Mirrors liquid_mask's PIT join."""
    key = (id(panels["daily"]), len(panels["months"]), days)
    if key in _C:
        return _C[key]
    months, cols = panels["months"], panels["cols"]
    tv = (panels["daily"].with_columns((pl.col("close") * pl.col("volume")).alias("tv"))
          .sort("symbol", "date")
          .with_columns(pl.col("tv").rolling_median(days, min_samples=max(10, days // 2))
                        .over("symbol").alias("mtv"))
          .select("symbol", "date", "mtv").drop_nulls()
          .with_columns(pl.col("date").cast(pl.Date))
          .with_columns((pl.col("date") + pl.duration(days=1)).alias("key")))
    grid = pl.DataFrame({"mdate": list(months)}).with_columns(
        pl.col("mdate").cast(pl.Date)).with_row_index("t")
    out = np.full((len(months), len(cols)), np.nan)
    cidx = {s: j for j, s in enumerate(cols)}
    for s, g in tv.group_by("symbol"):
        s = s[0] if isinstance(s, tuple) else s
        jj = cidx.get(s)
        if jj is None:
            continue
        r = grid.join_asof(g.sort("key"), left_on="mdate", right_on="key",
                           strategy="backward")
        out[r["t"].to_numpy(), jj] = r["mtv"].fill_null(np.nan).to_numpy()
    _C[key] = out
    return out


def score(panels, params):
    scores, exposure = _base(panels, params)
    k = int(params.get("pc_k", 0) or 0)
    if k <= 0:
        return scores, exposure
    n = int(params.get("pc_n", 500))
    mtv = median_tv(panels, int(params.get("pc_days", 120)))
    out = np.array(scores, dtype=float, copy=True)
    for t in range(out.shape[0]):
        v = mtv[t]
        fin = np.flatnonzero(np.isfinite(v) & (v > 0))
        if fin.size == 0:
            continue
        core = np.zeros(out.shape[1], dtype=bool)
        core[fin[np.argsort(-v[fin], kind="stable")[:n]]] = True
        r = out[t]
        idx = np.flatnonzero(np.isfinite(r) & core)
        if idx.size == 0:
            continue
        pick = idx[np.argsort(-r[idx], kind="stable")[:k]]
        out[t, pick] = r[pick] + BONUS
    return out, exposure
