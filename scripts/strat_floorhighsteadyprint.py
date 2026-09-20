"""Candidate: steady-print rank among confirmed breakouts (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied):
eligibility and regime from strat_floorhighfastgate, but eligible only when
the print month's intra-month dip was shallow — month low within `dip_mult`
x the month's own close-to-close range... simplified: (close - low)/close
over the print month <= `max_dip` — and the RANK stays lift level.

Rationale: volume confirmation subtracted (thin prints win) and smoothness
trailed, both pointing the same way — but neither tested the print month
itself. A breakout that never dipped intra-month is pure sponsorship; a
print made after a deep shakeout is a round-trip. If steadiness at the
moment of confirmation matters even though trailing smoothness doesn't,
this beats the base; if any steadiness filter is anti-edge here, it joins
the pile and the conclusion (this book wants its breakouts wild) is
triangulated from three sides.

PIT-safe: NEEDS_DAILY loads the daily long panel; dip uses bars with date
in [months[t-1], months[t]) only — strictly before the holding month. No
forward information.

SPACE = strat_floorhighfastgate params + max_dip {0.05, 0.10}.
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
    "max_dip": [0.05, 0.10],
}


def _monthly_dip(daily, months, cols):
    df = daily.with_columns((pl.col("low") / pl.col("close") - 1.0).alias("dip"))
    g = (df.group_by_dynamic("date", every="1mo", group_by="symbol")
           .agg(pl.col("dip").min()).sort("symbol", "date"))
    piv = g.pivot(on="symbol", index="date", values="dip").sort("date")
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
    return out  # out[i] = worst (low/close-1) of calendar month starting months[i]


def score(panels, params):
    rank, exposure = _fg_score(panels, params)
    daily, months = panels["daily"], panels["months"]
    cols = panels["cols"]
    md = float(params.get("max_dip", 0.05))
    dip = _monthly_dip(daily, months, cols)
    out = np.array(rank, dtype=float, copy=True)
    for t in range(1, rank.shape[0]):
        d = dip[t - 1]
        ok = np.isfinite(rank[t]) & np.isfinite(d) & (d >= -md)
        out[t] = np.where(ok, rank[t], np.nan)
    out[0] = np.nan
    return out, exposure
