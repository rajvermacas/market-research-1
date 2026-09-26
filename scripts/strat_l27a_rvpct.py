"""Candidate: board realized-vol PERCENTILE exposure cut on the champion (Loop-27 A).

Setup in words: rank, eligibility and breadth-tier exposure are exactly
strat_l23a_liqconfirm (imported, never copied). On top, an exposure cut from
the equal-weight board's own realized volatility, read as a percentile of its
own history rather than as a vol target:
  * daily equal-weight return = mean over names of close/prev_close - 1
    (|r| >= 0.25 dropped as bad prints / unadjusted actions);
  * rv = rolling std of that series over rv_win sessions (min rv_win sessions);
  * month t reads rv on the last session with date < months[t] (PIT);
  * pct = share of month-values rv[0..t-1] (strictly earlier months, at least
    rv_warm of them, else no action) below rv[t];
  * if pct > rv_thr, exposure *= (1 - rv_cut). rv_mode "weak" applies the cut
    only when the champion's own exposure is already < 1 (vol confirms a
    weakening breadth tier); "all" applies it regardless.

Hypothesis: the champion's DD legs (2018 small-cap unwind, forward -20.5%)
start while breadth is still middling; a vol spike relative to the board's own
history flags the unwind a month earlier than breadth tiers step down.
Falsifier: DD does not improve by >= 1pp at any cell, or CAGR loss exceeds it.

Novelty: the vol-targeting family (strat_floorhighvoltarget, concvoltarget,
floorhightiervol, volfloor; DEAD, legacy exec) scaled exposure to a fixed vol
TARGET on the legacy base. Changed here: (1) base = realistic execution + L25
liqconfirm champion (changed base, declared), (2) signal is a self-history
percentile trigger on the BOARD's daily realized vol, not a continuous
target on book vol, with an optional breadth-confirmation mode.
strat_l26a_corrspike (DEAD) read comovement, not vol level.

Off-switch: rv_cut = 0 -> champion exactly.
SPACE: rv_win {21,63}, rv_thr {0.8,0.9}, rv_cut {0,0.5,1.0}, rv_mode {all,weak}, rv_warm 24.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_l23a_liqconfirm import score as _base

NEEDS_DAILY = True
SPACE = {"rv_win": [21, 63], "rv_thr": [0.8, 0.9], "rv_cut": [0.0, 0.5, 1.0],
         "rv_mode": ["all", "weak"], "rv_warm": [24]}


def board_rv(panels, win):
    d = panels["daily"]
    r = (d.select("symbol", "date", "close").sort("symbol", "date")
         .with_columns((pl.col("close") / pl.col("close").shift(1).over("symbol") - 1.0).alias("r"))
         .filter(pl.col("r").is_finite() & (pl.col("r").abs() < 0.25))
         .group_by("date").agg(pl.col("r").mean().alias("ew"), pl.len().alias("n"))
         .filter(pl.col("n") >= 50).sort("date")
         .with_columns(pl.col("ew").rolling_std(win, min_samples=win).alias("rv"))
         .drop_nulls("rv")
         .with_columns(pl.col("date").cast(pl.Date))
         .with_columns((pl.col("date") + pl.duration(days=1)).alias("key")).sort("key"))
    grid = pl.DataFrame({"mdate": list(panels["months"])}).with_columns(
        pl.col("mdate").cast(pl.Date)).with_row_index("t").sort("mdate")
    j = grid.join_asof(r.select("key", "rv"), left_on="mdate", right_on="key",
                       strategy="backward").sort("t")
    return j["rv"].to_numpy().astype(float)


def score(panels, params):
    scores, exposure = _base(panels, params)
    cut = float(params.get("rv_cut", 0.0))
    if cut <= 0:
        return scores, exposure
    win = int(params.get("rv_win", 21))
    thr = float(params.get("rv_thr", 0.9))
    mode = params.get("rv_mode", "all")
    warm = int(params.get("rv_warm", 24))
    rv = board_rv(panels, win)
    base = np.asarray(exposure, dtype=float)
    out = base.copy()
    for t in range(len(out)):
        if not np.isfinite(rv[t]):
            continue
        hist = rv[:t]
        hist = hist[np.isfinite(hist)]
        if hist.size < warm:
            continue
        if (hist < rv[t]).mean() > thr and (mode == "all" or base[t] < 1.0):
            out[t] = base[t] * (1.0 - cut)
    return scores, out
