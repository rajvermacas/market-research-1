"""Candidate: W50-K30B momentum-thirty port (strategy_lab contract).

Faithful port of the certified book in
/workspaces/stock-database/.claude/skills/w50-k30b-evening/SKILL.md, as far as
this monthly harness allows:
    ranking  R(126d skipping last 10d) / 63d-vol, top 30 at month-end
             reconstitution (their COMPACT_RECONSTITUTE cadence)
    breadth  share of names above their 200-session EMA, smoothed 15
             sessions; invest only when share >= 0.65 (their top tier).
             Their 0.4/0.7 partial-exposure tiers cannot be expressed in an
             invest-or-cash harness, so weak breadth reads as cash here.
NOT ported (harness has no such machinery — read results accordingly):
    20% per-name trailing stop + tombstones, rank/time/crash exits, T+2
    funding, AMO open fills, whole-share granularity, LIQUIDCASE parking.
Costs stay at the harness 25bps so the number compares with other trials.

SPACE = vol_floor {0.0}, breadth_hi {0.65}. Ranking params are certified
dials, not tunables — do not sweep them.
"""

from __future__ import annotations

import numpy as np
import polars as pl

NEEDS_DAILY = True
SPACE = {"note": "certified dials R126/skip10/vol63, breadth 200EMA/15s/0.65"}


def score(panels, params):
    daily, months, cols = panels["daily"], panels["months"], panels["cols"]
    start_i = panels["start_i"]
    hi = float(params.get("breadth_hi", 0.65))

    d = daily.sort("symbol", "date").with_columns(
        pl.int_range(pl.len()).over("symbol").alias("_n"),
        pl.col("close").shift(10).over("symbol").alias("_c10"),
        pl.col("close").shift(126).over("symbol").alias("_c126"),
        pl.col("close").log().diff().over("symbol").alias("_lr"),
    )
    d = d.with_columns(
        (pl.col("_c10") / pl.col("_c126") - 1).alias("_ret"),
        (pl.col("_lr").rolling_std(63) * np.sqrt(252)).over("symbol").alias("_vol"),
        (pl.col("close") > pl.col("close").rolling_mean(200).over("symbol")).alias("_abv"),
    )
    d = d.with_columns(
        pl.when((pl.col("_vol") > 0) & (pl.col("_n") >= 200))
        .then(pl.col("_ret") / pl.col("_vol")).otherwise(None).alias("_score"))

    share = (d.group_by("date").agg(pl.col("_abv").mean().alias("_sh"))
             .sort("date").with_columns(pl.col("_sh").rolling_mean(15).alias("_sh15")))

    cuts = months[start_i:len(months) - 1]
    grid = (pl.DataFrame({"date": cuts})
            .join(pl.DataFrame({"symbol": cols}), how="cross").sort("date"))
    g = grid.join_asof(d.select("symbol", "date", "_score").sort("date"),
                       on="date", by="symbol", strategy="backward")
    g = g.join_asof(share.select("date", "_sh15").sort("date"),
                    on="date", strategy="backward")
    g = g.with_columns((pl.col("_sh15") >= hi).fill_null(False).alias("_on"))

    col_idx = {s: j for j, s in enumerate(cols)}
    mind = {m: i for i, m in enumerate(months)}
    scores = np.full_like(panels["px"], np.nan, dtype=float)
    regime = np.zeros(len(months), dtype=bool)
    for row in g.select("symbol", "date", "_score", "_on").iter_rows():
        s, cut, sc, on = row
        if s in col_idx:
            if sc is not None and np.isfinite(sc):
                scores[mind[cut], col_idx[s]] = sc
            regime[mind[cut]] = bool(on)
    return scores, regime
