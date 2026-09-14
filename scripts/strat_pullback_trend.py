"""Candidate: pullback-in-uptrend ranked by trend strength (strategy_lab contract).

Second mutation of the pullback mechanism (plain pullback: train +12.63 /
fwd +12.44 — consistent but sub-bench). Diagnosis: it scores by trough
recovery, so the deepest snap-backs top the rank regardless of how strong
the enclosing uptrend is. This variant multiplies recovery by monthly
RSI(14) strength: same eligibility gate as strat_rsi_pullback (pullback +
turn + not-late + seasoned + weekly/monthly RSI > htf_min), but the score
is rec * (rsi_m - htf_min + 1) — a snap-back inside a screaming trend
outranks the same snap-back inside a marginal one.

Reuses screener.rsi only — no second copy of any indicator. PIT-safe: all
reads use daily bars with date < the month boundary via backward asof.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from screener import rsi

NEEDS_DAILY = True
SPACE = {
    "pullback_max": [40, 45, 50],
    "rising_bars": [1, 2],
    "min_recovery": [2.0, 3.0, 5.0],
    "htf_min": [55.0, 60.0, 65.0],
}
PERIOD = 14
SEASON_DAYS = int(42 * 30.44)


def _close_rsi(frame: pl.DataFrame, label: str) -> pl.DataFrame:
    return frame.sort("symbol", "date").with_columns(
        rsi("close", PERIOD).over("symbol").alias(label),
        pl.int_range(pl.len()).over("symbol").alias("_n"),
    )


def score(panels, params):
    px, months, cols = panels["px"], panels["months"], panels["cols"]
    daily, start_i = panels["daily"], panels["start_i"]
    pbmax = float(params.get("pullback_max", 45))
    rbars = int(params.get("rising_bars", 2))
    minrec = float(params.get("min_recovery", 3.0))
    htf = float(params.get("htf_min", 60))

    d = daily.sort("symbol", "date").with_columns(
        rsi("close", PERIOD).over("symbol").alias("rsi_d"),
        pl.int_range(pl.len()).over("symbol").alias("_n"),
    )
    d = d.with_columns(
        pl.col("rsi_d").rolling_min(15).over("symbol").alias("_trough15"),
        pl.col("rsi_d").shift(1).over("symbol").alias("_p1"),
        pl.col("rsi_d").shift(2).over("symbol").alias("_p2"),
    )
    rising = pl.col("rsi_d") > pl.col("_p1")
    if rbars >= 2:
        rising = rising & (pl.col("_p1") > pl.col("_p2"))
    d = d.with_columns(
        (pl.col("rsi_d") - pl.col("_trough15")).alias("_rec"),
        (rising
         & (pl.col("_trough15") <= pbmax)
         & (pl.col("rsi_d") - pl.col("_trough15") >= minrec)
         & (pl.col("rsi_d") < 65)
         & (pl.col("_n") >= PERIOD * 3)).fill_null(False).alias("_elig"),
    )
    first = daily.group_by("symbol").agg(pl.col("date").min().alias("_first"))

    wk = (daily.sort("symbol", "date")
          .group_by_dynamic("date", every="1w", group_by="symbol")
          .agg(pl.col("close").last()).sort("symbol", "date"))
    wk = _close_rsi(wk, "_rsi_w").select("symbol", "date", "_rsi_w")
    mo = (daily.sort("symbol", "date")
          .group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("close").last()).sort("symbol", "date"))
    mo = _close_rsi(mo, "_rsi_m").select("symbol", "date", "_rsi_m")

    cuts = months[start_i:len(months) - 1]
    grid = (pl.DataFrame({"date": cuts})
            .join(pl.DataFrame({"symbol": cols}), how="cross")
            .join(first, on="symbol", how="left")
            .sort("date"))
    dsmall = d.select("symbol", "date", "_elig", "_rec").sort("date")
    g = grid.join_asof(dsmall, on="date", by="symbol", strategy="backward")
    g = g.join_asof(wk.sort("date"), on="date", by="symbol", strategy="backward")
    g = g.join_asof(mo.sort("date"), on="date", by="symbol", strategy="backward")
    g = g.with_columns(
        ((pl.col("date") - pl.col("_first")).dt.total_days() >= SEASON_DAYS)
        .fill_null(False).alias("_seasoned"))
    g = g.with_columns(
        (pl.col("_elig").fill_null(False)
         & pl.col("_seasoned")
         & (pl.col("_rsi_w") > htf).fill_null(False)
         & (pl.col("_rsi_m") > htf).fill_null(False)).alias("_ok"))
    # trend-weighted score: recovery scaled by how far monthly RSI clears the bar
    g = g.with_columns(
        pl.when(pl.col("_ok"))
        .then(pl.col("_rec") * (pl.col("_rsi_m") - htf + 1))
        .otherwise(None).alias("_score"))

    col_idx = {s: j for j, s in enumerate(cols)}
    mind = {m: i for i, m in enumerate(months)}
    scores = np.full_like(px, np.nan, dtype=float)
    ok = g.filter(pl.col("_ok"))
    for row in ok.select("symbol", "date", "_score").iter_rows():
        s, cut, sc = row
        if s in col_idx and sc is not None and np.isfinite(sc):
            scores[mind[cut], col_idx[s]] = sc
    return scores, np.ones(len(months), dtype=bool)
