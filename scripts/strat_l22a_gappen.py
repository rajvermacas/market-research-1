"""Candidate: overnight-gap penalty (strategy_lab contract; Loop-22 designer A, axis =
EXECUTION AWARENESS).

Setup in words: rank exactly as strat_floorhighfresh (composed via
`from strat_floorhighfresh import score as _base`, breadth-tier regime kept),
then multiply each eligible score by 1 + w*(2*pct-1), where pct is the
cross-sectional percentile (among the base's finite names) of
the monthly mean |open/prior close - 1| (overnight gap size), averaged (sign flipped so smaller gaps = higher pct)
over the {lb} calendar months BEFORE the decision month.

PIT: conservative choice — only daily bars with date < months[t] (i.e. whole
months strictly before month t; stale by one month). Never reads month t's
daily bars nor any later bar.

Hypothesis: next-open fills pay the overnight gap; names that habitually gap large carry execution slippage vs the signal close, so demoting them improves realised returns.
Falsifier: if neither variant beats the off-switch on train CAGR without a
wider DD or worse forward, the tilt is dead on this base under realistic exec.

NOVELTY: closest rows in research/tested_mechanisms.tsv are the legacy
liquidity/volume/sponsorship family (strat_floorhighliq, strat_floorliq,
strat_highliq, strat_liqtrend — gates, DEAD under the LEGACY fill) and
strat_l20b_illiq / strat_l20b_spread (Amihud / Corwin-Schultz level tilts on
the L20 chain). What changed: the open-vs-prior-close channel (no registry row uses the open print), and it is measured for the first time
under --exec realistic (next-open fill, lock/zero-volume refusal, 50 lakh
ADV floor), where fillability is priced by the harness.

Keys consumed: gp_w, gp_lb (w default 0.0 = off-switch identity; NaN stays NaN).
All base keys pass through to strat_floorhighfresh.
SPACE (2 documented variants + off-switch):
    gp_w 0.0  off-switch
    gp_w 0.2, gp_lb 2
    gp_w 0.4, gp_lb 3
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_floorhighfresh import score as _base

NEEDS_DAILY = True
SPACE = {"gp_w": [0.0, 0.2, 0.4], "gp_lb": [2, 3]}


def _monthly_feature(daily: pl.DataFrame) -> pl.DataFrame:
    d = daily.sort(["symbol", "date"]).with_columns(
        pl.col("close").shift(1).over("symbol").alias("pc"),
        pl.col("date").dt.truncate("1mo").cast(pl.Date).alias("mon"),
    )
    return d.group_by(["symbol", "mon"]).agg(((pl.col("open") / pl.col("pc")) - 1.0).abs().mean().alias("f"))


def score(panels, params):
    s, regime = _base(panels, params)
    w = float(params.get("gp_w", 0.0))
    if w == 0.0:
        return s, regime
    lb = int(params.get("gp_lb", 2))
    months = pl.Series(list(panels["months"])).cast(pl.Date).to_list()
    cols = list(panels["cols"])
    feat = _monthly_feature(panels["daily"])
    wide = (feat.filter(pl.col("symbol").is_in(cols))
            .pivot(on="symbol", index="mon", values="f").sort("mon"))
    idx = {m: i for i, m in enumerate(months)}
    F = np.full((len(months), len(cols)), np.nan)
    ci = {c: j for j, c in enumerate(cols)}
    mons = wide["mon"].to_list()
    for c in wide.columns[1:]:
        if c not in ci:
            continue
        v = wide[c].to_numpy().astype(float)
        for m, x in zip(mons, v):
            i = idx.get(m)
            if i is not None:
                F[i, ci[c]] = x
    out = s.copy()
    for t in range(len(months)):
        if t - lb < 0:
            continue
        with np.errstate(all="ignore"):
            win = F[t - lb:t]  # months strictly before month t
            x = np.nanmean(win, axis=0) if np.isfinite(win).any() else np.full(len(cols), np.nan)
        x = -x
        ok = np.isfinite(s[t]) & np.isfinite(x)
        n = ok.sum()
        if n < 2:
            continue
        r = np.empty(n)
        r[np.argsort(x[ok], kind="stable")] = np.arange(n)
        pct = r / (n - 1)
        out[t, ok] = s[t, ok] * (1.0 + w * (2.0 * pct - 1.0))
    return out, regime
