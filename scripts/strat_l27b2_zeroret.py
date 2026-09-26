"""Candidate: Lesmond zero-return-day share rank tilt on the L23-A champion (Loop-27 B2).

Setup in words: scores and exposure exactly as strat_l23a_liqconfirm (imported,
verbatim). Per (calendar month, stock) bucket: zr = share of daily bars with a
previous close whose close-to-close return is exactly zero (|r| < 1e-9) AND
volume > 0 (traded, but price did not move: Lesmond-Ogden-Trzcinka 1999
transaction-cost proxy; zero-VOLUME / circuit days are excluded so this is not
the dead lockpen signal), buckets with < 10 usable bars NaN. zv[t] = mean of
buckets t-zr_lb..t-1 (every bar dated < months[t]; window helper imported from
strat_l27b2_amihud), requiring >= ceil(zr_frac*zr_lb) finite buckets. Percentile
tilt score *= 1 + zr_w*(2*pct-1) (strat_l27b_spread._pct_tilt). zr_w>0 favours
names with MORE zero-return days (costlier to trade). zr_w=0 is the exact
off-switch. Regime/exposure untouched.

Question: a THIRD illiquidity estimator from different inputs (price
discreteness / non-trading of information, no range, no volume magnitude). If
it reproduces the Amihud/CS sign, the base carries a generic illiquidity
premium; if not, the premium is specific to price-impact/range measures.
Falsifier: neither sign beats 30.09/-17.22 train.

Novelty: no registry row implements zero-return share. Closest: strat_l22a_lockpen
(DEAD: circuit-lock / zero-VOLUME share penalty) - different event (no trade vs
trade-without-move) - and strat_l20b_illiq (Amihud). One thing changed: new
signal. The bucket->matrix pivot plumbing mirrors strat_l20b_spread (not an
indicator).
SPACE: zr_w in {-0.2,-0.1,+0.1,+0.2}, zr_lb in {9,12}, zr_frac 0.5.
"""
from __future__ import annotations
import numpy as np
import polars as pl
from strat_l23a_liqconfirm import score as _base
from strat_l27b_spread import _pct_tilt
from strat_l27b2_amihud import window_mean

NEEDS_DAILY = True
SPACE = {"zr_w": [-0.2, -0.1, 0.1, 0.2], "zr_lb": [9, 12], "zr_frac": [0.5]}


def _monthly_zeroret(daily: pl.DataFrame, months, cols, min_bars: int = 10) -> np.ndarray:
    d = daily.sort("symbol", "date")
    d = d.with_columns(pl.col("close").shift(1).over("symbol").alias("pc"))
    ok = (pl.col("pc").is_not_null() & (pl.col("pc") > 0) & (pl.col("close") > 0)
          & (pl.col("volume") > 0)).fill_null(False)
    d = d.with_columns(
        pl.when(ok).then(((pl.col("close") / pl.col("pc") - 1.0).abs() < 1e-9).cast(pl.Float64))
          .otherwise(None).alias("z"))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("z").count().alias("n"), pl.col("z").mean().alias("zr"))
          .with_columns(pl.when(pl.col("n") >= min_bars).then(pl.col("zr"))
                          .otherwise(None).cast(pl.Float64).alias("zr")))
    piv = g.pivot(on="symbol", index="date", values="zr").sort("date")
    mind = {(m if not hasattr(m, "date") else m.date()): i for i, m in enumerate(months)}
    cidx = {s: j for j, s in enumerate(cols)}
    out = np.full((len(months), len(cols)), np.nan)
    for row in piv.iter_rows(named=True):
        i = mind.get(row["date"])
        if i is None:
            continue
        for s, v in row.items():
            if s == "date":
                continue
            j = cidx.get(s)
            if j is not None and v is not None:
                out[i, j] = v
    return out


def score(panels, params):
    scores, exposure = _base(panels, params)
    w = float(params.get("zr_w", 0.0))
    if w == 0.0:
        return scores, exposure
    lb = int(params.get("zr_lb", 12))
    need = max(2, int(np.ceil(float(params.get("zr_frac", 0.5)) * lb)))
    zr = _monthly_zeroret(panels["daily"], panels["months"], panels["cols"])
    return _pct_tilt(scores, window_mean(zr, lb, need), w), exposure
