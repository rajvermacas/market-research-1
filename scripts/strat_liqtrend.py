"""Candidate: liquidity-expansion sponsorship (strategy_lab contract).

Fresh mechanism — no price-pattern rank at all. Thesis: durable advances
arrive on expanding sponsorship. Rank by the ratio of recent average daily
share volume (~1 trading month) to baseline average daily volume (~6 trading
months): highest expansion first. Eligibility needs a positive 6-month price
return so volume spikes in collapsing names (panic liquidation) cannot
qualify. Reuses no price indicator; volume means are plain rolling averages.

PIT-safe: holding month starting at months[m] uses daily bars with
date < months[m] only (cuts shifted one day back before the backward asof),
plus month-end closes through px[m] for the 6m price gate.

SPACE = near {21}, base {126}, trend_lb {6}, regime_ma {0,6},
weak_exp {0.0,0.4}. `weak_exp` is the exposure used when the index regime
is OFF, so float-regime tiers are searchable per trial via params-json.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

NEEDS_DAILY = True
SPACE = {
    "near": [21],
    "base": [126],
    "trend_lb": [6],
    "regime_ma": [0, 6],
    "weak_exp": [0.0, 0.4],
}


def _regime(px, months, start_i, ma, weak_exp):
    reg = np.ones(len(months))
    if ma:
        alive = ~np.isnan(px[start_i])
        idx = np.nanmean(px[:, alive] / px[start_i, alive], axis=1)
        idx_ma = pl.Series(idx).rolling_mean(ma).to_numpy()
        for t in range(len(months)):
            if np.isnan(idx_ma[t]) or not (idx[t] > idx_ma[t]):
                reg[t] = weak_exp
    return reg


def score(panels, params):
    px, months, cols = panels["px"], panels["months"], panels["cols"]
    daily = panels["daily"]
    start_i = panels["start_i"]
    near = int(params.get("near", 21))
    base = int(params.get("base", 126))
    tlb = int(params.get("trend_lb", 6))
    ma = int(params.get("regime_ma", 6))
    weak_exp = float(params.get("weak_exp", 0.0))

    d = daily.sort("symbol", "date").with_columns([
        pl.col("volume").cast(pl.Float64).rolling_mean(near, min_samples=near)
        .over("symbol").alias("_vn"),
        pl.col("volume").cast(pl.Float64).rolling_mean(base, min_samples=base)
        .over("symbol").alias("_vb"),
    ])
    cuts = [(m - timedelta(days=1)) for m in months]
    syms = daily["symbol"].unique().sort()
    grid = (pl.DataFrame({"symbol": syms}).join(
        pl.DataFrame({"date": cuts, "_m": list(range(len(months)))}),
        how="cross").sort("date"))
    g = grid.join_asof(
        d.select("symbol", "date", "_vn", "_vb").sort("date"),
        on="date", by="symbol", strategy="backward")
    with np.errstate(invalid="ignore", divide="ignore"):
        piv_n = g.pivot(on="symbol", index="_m", values="_vn").sort("_m")
        piv_b = g.pivot(on="symbol", index="_m", values="_vb").sort("_m")

    out = np.full_like(px, np.nan)
    mind = {m: i for i, m in enumerate(piv_n["_m"].to_list())}
    colset = set(cols)
    for row_n, row_b in zip(piv_n.iter_rows(named=True), piv_b.iter_rows(named=True)):
        t = mind.get(row_n["_m"])
        if t is None or t >= len(months):
            continue
        for j, s in enumerate(cols):
            if s not in colset:
                continue
            vn, vb = row_n.get(s), row_b.get(s)
            if vn is not None and vb is not None and vb > 0:
                out[t, j] = vn / vb

    trend = np.full_like(px, np.nan)
    trend[tlb:] = px[tlb:] / px[:-tlb] - 1
    out[~(trend > 0)] = np.nan  # price must confirm the sponsorship
    return out, _regime(px, months, start_i, ma, weak_exp)
