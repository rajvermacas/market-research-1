"""Candidate: liquidity-weighted structural rank among sustained breakouts
(strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied):
eligibility and regime from strat_floorhighsustaincond (regime-conditional
print continuity, fast gate, breadth tiers), but the RANK blends lift level
with cross-sectional liquidity standing — score = z_lift + w * z_liq, where
z_liq is the z-score of log trailing-median rupee turnover. Prior volume
work tested EXCLUSION (subtracted) and print-month CONFIRMATION
(subtracted); rank-WEIGHTING was never tested — the question is whether
liquidity helps choose AMONG qualified breakouts even though it fails as a
filter.

Rationale: among confirmed sustained breakouts, the deeper-liquidity name
absorbs the book's own flow and suffers less impact; weighting rank toward
liquidity should cut slippage-unseen-here and fragile-microcap blowups. If
the edge concentrates in thin names (volconf suggested thin prints win),
the weight subtracts and the liquidity question closes on all three
margins: filter, confirmation, weight.

PIT-safe: NEEDS_DAILY loads the daily long panel; trailing median turnover
uses bars with date < months[t] only (strictly before the holding month).
z-scores purely cross-sectional within month t. No forward information.

SPACE = strat_floorhighsustaincond params + liq_lb {6}, liq_w {0.5, 1.0}.
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
    "liq_lb": [6],
    "liq_w": [0.5, 1.0],
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
    return out


def score(panels, params):
    rank, exposure = _sc_score(panels, params)
    daily, months = panels["daily"], panels["months"]
    cols = panels["cols"]
    llb = int(params.get("liq_lb", 6))
    w = float(params.get("liq_w", 0.5))
    turn = _monthly_turnover(daily, months, cols)
    out = np.full_like(rank, np.nan)
    for t in range(llb, rank.shape[0]):
        base = turn[t - llb:t]
        with np.errstate(invalid="ignore"):
            med = np.nanmedian(base, axis=0)
            lz = np.log(np.where(med > 0, med, np.nan))
        ok = np.isfinite(rank[t]) & np.isfinite(lz)
        if ok.sum() < 2:
            continue
        r = rank[t].copy()
        r[ok] = (r[ok] - r[ok].mean()) / (r[ok].std() or 1.0)
        lz[ok] = (lz[ok] - lz[ok].mean()) / (lz[ok].std() or 1.0)
        out[t] = np.where(ok, r + w * lz, np.nan)
    return out, exposure
