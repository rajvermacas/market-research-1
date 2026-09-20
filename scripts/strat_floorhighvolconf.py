"""Candidate: volume-confirmed fresh prints under breadth tiers
(strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank and
regime from strat_floorhighfastgate, but eligible only when the print
month's share turnover exceeds `vol_mult` x its trailing `vol_lb`-month
median — the breakout must arrive with expanding participation, not on thin
ticks.

Rationale: price prints without volume are the classic failed breakout;
prior volume work in this tree only tested EXCLUSION (dropping illiquid
names, which subtracted) — never CONFIRMATION (requiring the breakout
itself to print volume). Turnover = volume / shares... shares outstanding
is unavailable, so turnover here is rupee volume (close x volume) summed
over the print month vs its trailing median — a per-name relative measure,
immune to cross-sectional size bias.

PIT-safe: NEEDS_DAILY loads the daily long panel; the print month for score
row t is daily bars with date in [months[t-1], months[t]) (months are
calendar month-starts), strictly before the holding month. Median uses the
vol_lb months before that. No forward information.

SPACE = strat_floorhighfastgate params + vol_lb {6}, vol_mult {1.0, 1.5}.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_floorhighfastgate import score as _fg_score

NEEDS_DAILY = True
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [19],
    "lookback": [16],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [6],
    "vol_lb": [6],
    "vol_mult": [1.0, 1.5],
}


def _monthly_turnover(daily, months, cols):
    df = daily.with_columns((pl.col("close") * pl.col("volume")).alias("rp"))
    g = (df.group_by_dynamic("date", every="1mo", group_by="symbol")
           .agg(pl.col("rp").sum()).sort("symbol", "date"))
    piv = g.pivot(on="symbol", index="date", values="rp").sort("date")
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
    # out[i] = turnover of calendar month starting months[i];
    # print month for score row t is months[t-1] -> shift by one.
    return out


def score(panels, params):
    rank, exposure = _fg_score(panels, params)
    daily, months = panels["daily"], panels["months"]
    cols = panels["cols"]
    vlb = int(params.get("vol_lb", 6))
    mult = float(params.get("vol_mult", 1.0))
    turn = _monthly_turnover(daily, months, cols)
    out = np.array(rank, dtype=float, copy=True)
    for t in range(1, rank.shape[0]):
        pm = t - 1  # print-month bucket
        lo = pm - vlb
        if lo < 0:
            out[t] = np.nan
            continue
        base = turn[pm]
        with np.errstate(invalid="ignore"):
            med = np.nanmedian(turn[lo:pm], axis=0)
        ok = np.isfinite(rank[t]) & np.isfinite(base) & np.isfinite(med) & (med > 0) \
            & (base >= mult * med)
        out[t] = np.where(ok, rank[t], np.nan)
    out[0] = np.nan
    return out, exposure
