"""Candidate: total-return (dividend-adjusted) momentum tilt (strategy_lab
contract; Loop-23 designer B, axis = NEW RANKING/SELECTION CHANNEL).

Setup in words: rank exactly as strat_floorhighfresh (composed via
`from strat_floorhighfresh import score as _base`, breadth-tier regime kept),
then multiply each eligible score by 1 + w*(2*pct-1), where pct is the
cross-sectional percentile (among the base's finite names) of the name's
TOTAL-RETURN momentum: last adj_close of month t-1 over last adj_close of
month t-1-lb, minus 1. adj_close (dividend + split adjusted) is read by this
file from data/ohlcv/daily/**/*.parquet because panels['daily'] carries no
adj_close. w > 0 rewards total-return leaders.

PIT: only daily bars with date < months[t] (whole months strictly before
month t). Caveat stated: Yahoo's adj_close is back-adjusted at snapshot time,
so a dividend paid AFTER month t rescales earlier adj_close values by a
constant factor per name — ratios within the window are unaffected unless the
dividend falls inside it, and then only by the dividend, which is information
the window did contain.

Hypothesis: the base ranks on price structure only; total return adds the
cash yield, favouring compounders whose holders are paid to wait.
Falsifier: no variant beats the off-switch beyond noise, or gains widen DD.

NOVELTY: closest rows are strat_l20a_divyield / divregular / l20a2_divcombo /
l21a_divgrowth (the adj_close/close dividend FACTOR as a size/timing signal on
the L20 legacy chain). Changed base (strat_floorhighfresh, --exec realistic)
and a different transform: total-return MOMENTUM level, not the dividend
factor itself. Stated as a changed-base neighbour of the dividend channel.

Keys consumed: tr_w (default 0.0 = off-switch identity), tr_lb, tr_price_only
(default false; true reads split-adjusted close instead of adj_close — the
ablation that isolates what the dividend adjustment itself contributes).
SPACE:
    tr_w 0.0            off-switch
    tr_w 0.15, tr_lb 6
    tr_w 0.15, tr_lb 12
    tr_w -0.15, tr_lb 6
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

from strat_floorhighfresh import score as _base

NEEDS_DAILY = True
SPACE = {"tr_w": [0.0, 0.15, -0.15], "tr_lb": [6, 12]}
_ROOT = Path(__file__).resolve().parents[1]


def _monthly_adj(cols, field: str = "adj_close") -> pl.DataFrame:
    return (pl.scan_parquet(str(_ROOT / "data" / "ohlcv" / "daily" / "**" / "*.parquet"),
                            hive_partitioning=True)
            .filter(pl.col("symbol").is_in(list(cols)))
            .select("symbol", "date", pl.col(field).alias("adj_close"))
            .with_columns(pl.col("date").dt.truncate("1mo").cast(pl.Date).alias("mon"))
            .sort("symbol", "date")
            .group_by(["symbol", "mon"]).agg(pl.col("adj_close").drop_nulls().last().alias("f"))
            .collect())


def score(panels, params):
    s, regime = _base(panels, params)
    w = float(params.get("tr_w", 0.0))
    if w == 0.0:
        return s, regime
    lb = int(params.get("tr_lb", 6))
    months = pl.Series(list(panels["months"])).cast(pl.Date).to_list()
    cols = list(panels["cols"])
    field = "close" if params.get("tr_price_only") else "adj_close"
    wide = _monthly_adj(cols, field).pivot(on="symbol", index="mon", values="f").sort("mon")
    idx = {m: i for i, m in enumerate(months)}
    ci = {c: j for j, c in enumerate(cols)}
    A = np.full((len(months), len(cols)), np.nan)
    mons = wide["mon"].to_list()
    for c in wide.columns[1:]:
        j = ci.get(c)
        if j is None:
            continue
        v = wide[c].to_numpy().astype(float)
        for m, x in zip(mons, v):
            i = idx.get(m)
            if i is not None:
                A[i, j] = x
    out = s.copy()
    for t in range(len(months)):
        if t - 1 - lb < 0:
            continue
        with np.errstate(all="ignore"):
            x = A[t - 1] / A[t - 1 - lb] - 1.0  # months strictly before month t
        x[~np.isfinite(x)] = np.nan
        ok = np.isfinite(s[t]) & np.isfinite(x)
        n = ok.sum()
        if n < 2:
            continue
        r = np.empty(n)
        r[np.argsort(x[ok], kind="stable")] = np.arange(n)
        pct = r / (n - 1)
        out[t, ok] = s[t, ok] * (1.0 + w * (2.0 * pct - 1.0))
    return out, regime
