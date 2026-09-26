"""Candidate: limit-DOWN lock PANIC detector as an exposure cut (Loop-27 designer C).

Setup in words: rank, eligibility and tiered exposure come unchanged from the
champion strat_l23a_liqconfirm (imported, never copied). On top, a board-wide
panic gauge: for every trading day, the share of names that traded that day
whose bar was LOCKED LIMIT-DOWN — high == low with close below the prior
close (the same lower-circuit test as strategy_lab.exec_panels' lock_dn,
minus its zero-volume clause, since an untraded name is illiquid, not
panicking). The monthly reading P[m] is the mean of that daily share over the
last pk_k sessions with date < months[m] (strictly before the month label —
conservative PIT, no bar of month m is read). P[m] is ranked as a percentile
against its own trailing history P[0..m-1] (at least 24 prior months, else no
signal). If that percentile >= pk_pct, exposure *= (1 - pk_cut).

PRE-REGISTERED SIGN (fixed before any trial): CUT exposure when panic is
HIGH. Hypothesis: clustered lower-circuit locks mark forced selling /
liquidity cascades (small-cap sell-offs) that the slow breadth-above-MA tiers
lag; trimming then shortens drawdown legs. Falsifier: no cell improves train
calmar over the off-switch, or the overlay is inert (identical rows).

Novelty (research/tested_mechanisms.tsv grep lock|panic|circuit):
strat_l22a_lockpen (DEAD) used up-lock/zero-volume share as a per-NAME rank
penalty; strat_l21c_lockout (DEAD) is a book re-entry lockout, unrelated;
strat_l23a_newlows (DEAD) used new-low share as an exposure cap. None uses
the board-level DOWN-lock share, self-normalised by its own trailing
percentile, as a regime/exposure signal.

Keys: pk_cut (0.0 = off-switch -> champion exactly), pk_k (sessions, 10),
pk_pct (0.9), pk_warm (24). All champion keys pass through.
SPACE: off-switch; k 10/20 x pct 0.8/0.9 x cut 0.5/1.0 (screened subset).
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_l23a_liqconfirm import score as _base

NEEDS_DAILY = True
SPACE = {"pk_cut": [0.0, 0.5, 1.0], "pk_k": [10, 20], "pk_pct": [0.8, 0.9], "pk_warm": [24]}


def daily_lock_share(daily: pl.DataFrame) -> pl.DataFrame:
    d = (daily.sort("symbol", "date")
         .with_columns(pl.col("close").shift(1).over("symbol").alias("pc"))
         .filter(pl.col("volume") > 0)
         .with_columns(((pl.col("high") == pl.col("low")) & (pl.col("close") < pl.col("pc")))
                       .fill_null(False).cast(pl.Float64).alias("dn")))
    return (d.group_by("date").agg(pl.col("dn").mean().alias("sh"), pl.len().alias("n"))
            .filter(pl.col("n") >= 50).sort("date"))


def panic_series(daily: pl.DataFrame, months, k: int) -> np.ndarray:
    sh = daily_lock_share(daily)
    dates = np.array(sh["date"].cast(pl.Date).to_list(), dtype="datetime64[D]")
    vals = sh["sh"].to_numpy()
    out = np.full(len(months), np.nan)
    for m, mo in enumerate(months):
        cut = np.searchsorted(dates, np.datetime64(mo, "D"), side="left")  # dates < months[m]
        if cut >= k:
            out[m] = float(np.mean(vals[cut - k:cut]))
    return out


def score(panels, params):
    scores, exposure = _base(panels, params)
    cutf = float(params.get("pk_cut", 0.0))
    if cutf == 0.0:
        return scores, exposure
    k = int(params.get("pk_k", 10))
    thr = float(params.get("pk_pct", 0.9))
    warm = int(params.get("pk_warm", 24))
    months = pl.Series(list(panels["months"])).cast(pl.Date).to_list()
    P = panic_series(panels["daily"], months, k)
    out = np.asarray(exposure, dtype=float).copy()
    for m in range(len(months)):
        if not np.isfinite(P[m]):
            continue
        hist = P[:m][np.isfinite(P[:m])]
        if len(hist) < warm:
            continue
        pct = float(np.mean(hist <= P[m]))
        if pct >= thr:
            out[m] = out[m] * (1.0 - cutf)
    return scores, out
