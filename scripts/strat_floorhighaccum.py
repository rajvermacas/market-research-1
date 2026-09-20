"""Candidate: volume-accumulation gate on the conditional-sustain book
(strategy_lab contract).

Mutation composing a tested mechanism (imported, never copied): rank and
regime from strat_floorhighsustaincond, but eligible only when the name's
recent volume has been accumulating — the signed-volume share

    acc_m = sum over daily bars d in month m of vol_d * sign(close_d - close_{d-1})
            / sum over daily bars in month m of vol_d

averaged over the `acc_lb` months ending at the print month (the calendar
month before the holding month). acc in [-1, 1]: volume transacted on up days
minus down days, as a share of all volume.

Rationale: prior volume work in this tree tested EXCLUSION (static liquidity,
which subtracted) and single-month turnover expansion at the print
(strat_floorhighvolconf, which subtracted hard). Neither measured the
DIRECTIONAL character of volume over a window. A fresh high printed while the
prior months' volume has leaned to accumulation is demand; the same print on
distribution volume is supply selling into it. The monthly closes cannot
separate those; the daily tape can.

PIT-safe: NEEDS_DAILY loads the daily long panel. For score row t the print
month is months[t-1] and the window covers acc_lb buckets ending there, all
strictly before the holding month starting months[t]. Daily `chg` is computed
within symbol after sorting by date; no forward bars are read.

SPACE = strat_floorhighsustaincond params + acc_lb {3,6}, acc_min {0.0,0.05,0.10}.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_floorhighsustaincond import score as _sc_score

NEEDS_DAILY = True
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [19],
    "lookback": [16],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [9],
    "sustain_lo": [6],
    "sustain_hi": [2],
    "acc_lb": [3, 6],
    "acc_min": [0.0, 0.05, 0.10],
}


def _monthly_accumulation(daily, months, cols):
    """Monthly signed-volume share per (month, stock); NaN where no volume."""
    d = (daily
         .with_columns(pl.col("close").diff().over("symbol").alias("chg"))
         .with_columns((pl.col("volume").cast(pl.Float64)
                        * pl.col("chg").sign()).alias("sv")))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.when(pl.col("volume").sum() > 0)
                 .then(pl.col("sv").sum() / pl.col("volume").sum())
                 .otherwise(None).alias("acc"))
          .sort("symbol", "date"))
    piv = g.pivot(on="symbol", index="date", values="acc").sort("date")
    mind = {}
    for i, m in enumerate(months):
        key = m if not hasattr(m, "date") else m.date()
        mind[key] = i

    out = np.full((len(months), len(cols)), np.nan)
    cidx = {s: j for j, s in enumerate(cols)}
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
    rank, exposure = _sc_score(panels, params)
    daily, months, cols = panels["daily"], panels["months"], panels["cols"]
    alb = int(params.get("acc_lb", 6))
    amin = float(params.get("acc_min", 0.0))

    acc = _monthly_accumulation(daily, months, cols)
    out = np.array(rank, dtype=float, copy=True)
    for t in range(1, rank.shape[0]):
        pm = t - 1  # print-month bucket
        lo = pm - alb + 1
        if lo < 0:
            out[t] = np.nan
            continue
        with np.errstate(invalid="ignore"):
            m = np.nanmean(acc[lo:pm + 1], axis=0)
        ok = np.isfinite(rank[t]) & np.isfinite(m) & (m >= amin)
        out[t] = np.where(ok, rank[t], np.nan)
    out[0] = np.nan
    return out, exposure
