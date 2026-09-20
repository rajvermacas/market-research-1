"""Candidate: close-location-value rank on the champion book (strategy_lab contract).

Setup in words: keep the champion's eligibility and exposure untouched —
rank, gates and shaped tiers come from strat_floorhighrankpersist, which
composes strat_floorhightiershape (floor-lift rank among fresh prints, short
trend gate, print-continuity gate, breadth-tier exposure) with a freshness
premium and the harness's max_hold. Among the ELIGIBLE names only, the RANK
is re-cut by print quality measured on the daily tape of the print month:

    clv = mean over print-month daily bars of ((close - low) / (high - low))

averaged over `clv_lb` buckets ending at the print month, in [0, 1] — did the
month CLOSE near its highs (buyers in control into the bell) or near its lows
(fade into the close)? Final score = lift * (clv_scale + (1 - clv_scale) * clv),
a multiplicative tilt that preserves lift ordering within equal CLV and CLV
ordering within equal lift, with `clv_scale` interpolating between no tilt
(1.0) and full replacement (0.0).

Hypothesis: the freshness premium finding says the book's edge lives in names
the market is confirming RIGHT NOW. Where the print month closed within its
own range is the daily-tape version of that confirmation: a high print that
closes at its lows is distribution into the breakout; one that closes at its
highs is demand persisting to the bell. Monthly closes cannot see this; the
daily tape can. Note the neighbouring daily-path evidence cuts BOTH ways —
steadyprint (shallow intra-month dip) subtracted, but that measured the path
TO the high, not the CLOSE at the high — so this is a genuine open question,
not a re-run.

Falsifies if: the clv tilt trails the flat base (clv_scale 1.0 ≈ +83.9 train)
across all variants — then the close location of the print month carries no
marginal information at this base and the daily-path channel is closed for
the close, whatever the dip said.

PIT argument: NEEDS_DAILY loads the daily long panel. For score row t (holding
month starting months[t]) the print month is calendar month months[t-1]; CLV
is computed ONLY from daily bars with date in [months[t-1], months[t]) —
strictly before the holding month opens. Bars in the holding month itself are
never read. `clv_lb` buckets end at the print month and extend back, all
before months[t]. NaN CLV (no bars / zero range) keeps eligibility but leaves
the imported lift unmodified (tilt 1.0) — never peeks, never drops on missing
data.

SPACE = champion base + clv_lb {1, 3}, clv_scale {0.5, 0.8}.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_floorhighrankpersist import score as _rp_score

NEEDS_DAILY = True
SPACE = {
    "b_hi": [0.69],
    "b_lo": [0.45],
    "b_mid": [0.55],
    "floor_lb": [19],
    "lookback": [10],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [5],
    "sustain_lo": [3],
    "sustain_hi": [2],
    "tier_lo": [1.0],
    "tier_mid": [1.0],
    "pers_lb": [6],
    "pers_w": [-0.16],
    "clv_lb": [1, 3],
    "clv_scale": [0.5, 0.8],
}


def _monthly_clv(daily: pl.DataFrame, months, cols) -> np.ndarray:
    """Mean daily close-location value per (calendar month, stock); NaN where
    the month had no bars or every bar had high == low."""
    d = daily.with_columns(
        pl.when(pl.col("high") > pl.col("low"))
          .then((pl.col("close") - pl.col("low")) / (pl.col("high") - pl.col("low")))
          .otherwise(None)
          .alias("clv"))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("clv").mean()).sort("symbol", "date"))
    piv = g.pivot(on="symbol", index="date", values="clv").sort("date")
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
    return out  # out[i] = mean CLV of calendar month starting months[i]


def score(panels, params):
    rank, exposure = _rp_score(panels, params)
    daily, months, cols = panels["daily"], panels["months"], panels["cols"]
    clb = int(params.get("clv_lb", 1))
    cscale = float(params.get("clv_scale", 0.8))

    clv = _monthly_clv(daily, months, cols)
    out = np.array(rank, dtype=float, copy=True)
    for t in range(1, rank.shape[0]):
        pm = t - 1  # print-month bucket = calendar month before the hold month
        lo = pm - clb + 1
        if lo < 0:
            continue
        with np.errstate(invalid="ignore"):
            c = np.nanmean(clv[lo:pm + 1], axis=0)
        # tilt in (cscale, 1.0]; NaN clv -> tilt 1.0 (lift unmodified)
        tilt = np.where(np.isfinite(c), cscale + (1.0 - cscale) * c, 1.0)
        ok = np.isfinite(rank[t])
        out[t] = np.where(ok, rank[t] * tilt, np.nan)
    out[0] = np.nan
    return out, exposure
