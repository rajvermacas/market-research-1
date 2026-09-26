"""Candidate: breadth tiers over the top-N names by traded value (rank-relative liquid population) (Loop-23 A).

Setup in words: rank and eligibility exactly as strat_floorhighfresh
(imported). The exposure regime keeps the strat_newhigh_tier breadth-tier
shape, with thresholds shifted up by lr_shift, but breadth (share above the
regime_ma-month average) is counted over the lr_n names with the highest median
daily traded value (close*volume, last lr_days sessions with date < months[t])
at each month-end. strat_l22b_liqbreadth / strat_l23a_liqconfirm use an
ABSOLUTE INR floor, whose population grows several-fold 2015->2022 as turnover
inflates, so its breadth measures a changing cohort; a fixed-count cohort is a
stable "large liquid market" (Nifty-500-like at lr_n 500).
PIT: closes through px[t]; daily bars date < months[t].

Hypothesis: a stable-size liquid cohort gives a cleaner regime than the
absolute-floor cohort, keeping liqconfirm's DD gain with more CAGR.
Falsifier: no lr_n beats base on both CAGR and DD, or all variants trail
strat_l23a_liqconfirm strict 5e6/40/0.05 (+26.59/-16.95).

Novelty: registry rows strat_l22b_liqbreadth (PARTIAL, absolute floor) and the
legacy breadth-variant family (tierdual/tieror/hyst: DEAD, whole board). No row
defines the breadth population by cross-sectional traded-value RANK.

Keys: lr_n (0 = off-switch -> champion exactly), lr_days (40), lr_shift (0.05),
lr_shift_lo (bottom-threshold shift only; default = lr_shift).
SPACE variants: lr_n 300/500/1000 at shift 0.05; lr_n 500 at shift 0.0/0.075.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_floorhighfresh import score as _base
from strat_l22b_liqbreadth import tier

NEEDS_DAILY = True
SPACE = {"lr_n": [0, 300, 500, 1000], "lr_days": [40], "lr_shift": [0.0, 0.05, 0.075]}


def traded_value_matrix(panels, days: int) -> np.ndarray:
    """months x stocks: median traded value over last `days` sessions, date < months[t]."""
    months, cols = panels["months"], panels["cols"]
    tv = (panels["daily"].with_columns((pl.col("close") * pl.col("volume")).alias("tv"),
                                       pl.col("date").cast(pl.Date))
          .sort("symbol", "date")
          .with_columns(pl.col("tv").rolling_median(days, min_samples=max(10, days // 2))
                        .over("symbol").alias("mtv"))
          .select("symbol", "date", "mtv").drop_nulls()
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
        r = grid.join_asof(g.sort("key"), left_on="mdate", right_on="key", strategy="backward")
        out[r["t"].to_numpy(), jj] = r["mtv"].cast(pl.Float64).fill_null(np.nan).to_numpy()
    return out


def score(panels, params):
    scores, exposure = _base(panels, params)
    n_top = int(params.get("lr_n", 0))
    if n_top <= 0:
        return scores, exposure
    mtv = traded_value_matrix(panels, int(params.get("lr_days", 40)))
    px, months = panels["px"], panels["months"]
    ma = int(params.get("regime_ma", 5))
    ma_px = np.full_like(px, np.nan)
    for t in range(ma - 1, len(months)):
        ma_px[t] = np.nanmean(px[t - ma + 1:t + 1], axis=0)
    sh = float(params.get("lr_shift", 0.05))
    hi, mid, lo = (float(params.get("b_hi", 0.55)), float(params.get("b_mid", 0.45)),
                   float(params.get("b_lo", 0.35)))
    sh_lo = float(params.get("lr_shift_lo", sh))  # bottom-threshold override; default = lr_shift
    out = np.asarray(exposure, dtype=float).copy()
    for t in range(len(months)):
        with np.errstate(invalid="ignore"):
            ok = np.isfinite(px[t]) & np.isfinite(ma_px[t]) & np.isfinite(mtv[t])
        idx = np.where(ok)[0]
        if len(idx) < 20:
            continue
        top = idx[np.argsort(-mtv[t, idx])[:n_top]]
        b = float(np.mean(px[t, top] > ma_px[t, top]))
        out[t] = tier(b, hi + sh, mid + sh, lo + sh_lo)
    return scores, out
