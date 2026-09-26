"""Candidate: breadth tiers measured over the LIQUID universe only (Loop-22 B).

Setup in words: rank and eligibility exactly as strat_floorhighfresh (imported).
The exposure regime keeps the strat_newhigh_tier breadth-tier shape (share of
names above their regime_ma-month average -> 1.0/0.7/0.4/0.0 at b_hi/b_mid/
b_lo), but breadth is counted only over names whose median daily traded value
(close*volume) over the last `liq_days` sessions is >= `liq_min` INR. Under
realistic execution most of the board is untradeable; its breadth may describe
a market the book cannot buy.

PIT: decision row t uses month-end closes through px[t] and daily bars with
date < months[t] (conservative: the month-end session itself is excluded).

Hypothesis: liquid-only breadth tracks the tradeable market's regime better,
lifting train Calmar and forward vs the whole-board regime.
Falsifier: off-switch identity holds and both variants fail to beat base
train CAGR at equal-or-better DD, or forward falls below base.

Novelty: closest registry rows are strat_floorhighbreadthlin / strat_floorhighhyst
(breadth regime shape variants, DEAD) and strat_floorhighliq / liqw
(liquidity used as a *name gate / weight*, DEAD). None restricts the breadth
*population* to liquid names; also those were legacy-exec verdicts.

Keys: liq_min (INR; 0 = off-switch -> base untouched), liq_days (default 40).
SPACE variants: liq_min 5e6/liq_days 40 (same 50 lakh floor as the harness),
liq_min 2e7/liq_days 60 (2 crore, stricter large-liquid regime).
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_floorhighfresh import score as _base

NEEDS_DAILY = True
SPACE = {"liq_min": [0, 5e6, 2e7], "liq_days": [40, 60]}


def liquid_mask(panels, liq_min: float, liq_days: int) -> np.ndarray:
    """months x stocks bool: median traded value over the last liq_days
    sessions with date < months[t] is >= liq_min."""
    months, cols = panels["months"], panels["cols"]
    d = panels["daily"]
    tv = (d.with_columns((pl.col("close") * pl.col("volume")).alias("tv"))
          .sort("symbol", "date")
          .with_columns(pl.col("tv").rolling_median(liq_days, min_samples=max(10, liq_days // 2))
                        .over("symbol").alias("mtv"))
          .select("symbol", "date", "mtv").drop_nulls())
    grid = pl.DataFrame({"mdate": list(months)}).with_columns(
        pl.col("mdate").cast(pl.Date)).with_row_index("t")
    out = np.zeros((len(months), len(cols)), dtype=bool)
    cidx = {s: j for j, s in enumerate(cols)}
    tv = tv.with_columns(pl.col("date").cast(pl.Date))
    # last row strictly before months[t]
    tv = tv.with_columns((pl.col("date") + pl.duration(days=1)).alias("key")).sort("key")
    j = grid.sort("mdate").join_asof(tv, left_on="mdate", right_on="key",
                                     by=None, strategy="backward") if False else None
    for s, g in tv.group_by("symbol"):
        s = s[0] if isinstance(s, tuple) else s
        jj = cidx.get(s)
        if jj is None:
            continue
        r = grid.join_asof(g.sort("key"), left_on="mdate", right_on="key",
                           strategy="backward")
        v = r["mtv"].to_numpy()
        with np.errstate(invalid="ignore"):
            out[r["t"].to_numpy(), jj] = np.nan_to_num(v, nan=0.0) >= liq_min
    return out


def tier(b, hi, mid, lo):
    if not np.isfinite(b):
        return 0.0
    return 1.0 if b > hi else 0.7 if b > mid else 0.4 if b > lo else 0.0


def score(panels, params):
    scores, exposure = _base(panels, params)
    liq_min = float(params.get("liq_min", 0))
    if liq_min <= 0:
        return scores, exposure
    liq = liquid_mask(panels, liq_min, int(params.get("liq_days", 40)))
    px, months = panels["px"], panels["months"]
    ma = int(params.get("regime_ma", 5))
    ma_px = np.full_like(px, np.nan)
    for t in range(ma - 1, len(months)):
        ma_px[t] = np.nanmean(px[t - ma + 1:t + 1], axis=0)
    with np.errstate(invalid="ignore"):
        alive = np.isfinite(px) & np.isfinite(ma_px) & liq
        above = alive & (px > ma_px)
    n = alive.sum(axis=1)
    out = exposure.astype(float).copy()
    for t in range(len(months)):
        if n[t] >= 20:
            out[t] = tier(above[t].sum() / n[t], float(params.get("b_hi", 0.55)),
                          float(params.get("b_mid", 0.45)), float(params.get("b_lo", 0.35)))
    return scores, out
