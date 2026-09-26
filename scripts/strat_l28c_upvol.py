"""Candidate: board UP-VALUE share as an exposure cut / re-arm (Loop-28 C).

Setup in words: rank, eligibility, liquid-breadth tier exposure and book are
exactly strat_l23a_liqconfirm (imported, never copied). On every session, over
nse_all names with volume > 0 and a prior close, traded value v = close*volume
(value, not share volume, so penny stocks do not dominate). The up-value share
over a window is UVS = sum(v on names with close > prior close) / sum(v) over
the last uv_days sessions with date < months[t] (point-in-time; a month is
null until uv_days sessions exist, >=50 names per session).
  cut:   if UVS < uv_lo -> exposure *= uv_cut      (uv_cut = 1 -> no cut)
  rearm: if UVS > uv_hi and exposure < 1 -> exposure = max(exposure, uv_to)
         (uv_to = 0 -> no re-arm)
Thresholds are set from the pre-2022 distribution of monthly UVS (percentiles).

Hypothesis: where money flows (value-weighted up/down participation, the
Arms/TRIN family idea) leads price breadth: distribution under a still-positive
share-above-MA breadth shows up first as sub-50% up-value, and accumulation in
a washed-out tape shows up as >55% up-value before the 18-month breadth tier
re-arms. Falsifier: no cell beats 30.09 CAGR at DD no deeper than -17.22, or
the gain comes from one episode.

Novelty: breadth rows (ramps/hysteresis/derivative/new-high/new-low share,
l28a thrust) all count NAMES; l28a turnover surge reads total value LEVEL, not
its up/down split; legacy liquidity/volume/sponsorship rows (floorhighvolconf,
floorhighpart...) are per-stock volume gates on the rank, not a market-level
exposure input. No registry row uses the value-weighted up/down split of board
turnover. (Own-book equity-curve governors were skipped: l12a_bookhealth and
l17c_eqstate are both DEAD.)

Off-switch: uv_cut = 1 and uv_to = 0 -> champion exactly.
SPACE: uv_days {21,63}, uv_lo {p10,p20 of pre-2022}, uv_cut {1,0.5,0},
uv_hi {p80,p90}, uv_to {0,0.7,1.0}.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_l23a_liqconfirm import score as _base

NEEDS_DAILY = True
SPACE = {"uv_days": [21, 63], "uv_lo": [0.45, 0.48], "uv_cut": [1.0, 0.5, 0.0],
         "uv_hi": [0.55, 0.58], "uv_to": [0.0, 0.7, 1.0]}


def upvalue_daily(daily):
    d = (daily.filter(pl.col("volume") > 0)
         .with_columns(pl.col("date").cast(pl.Date))
         .sort("symbol", "date")
         .with_columns(pl.col("close").shift(1).over("symbol").alias("pc"))
         .drop_nulls("pc")
         .with_columns((pl.col("close") * pl.col("volume")).cast(pl.Float64).alias("v"))
         .group_by("date").agg(pl.col("v").filter(pl.col("close") > pl.col("pc")).sum().alias("up"),
                               pl.col("v").sum().alias("tot"), pl.len().alias("n"))
         .filter(pl.col("n") >= 50).sort("date"))
    dord = np.array([x.toordinal() for x in d["date"].to_list()])
    return dord, d["up"].to_numpy().astype(float), d["tot"].to_numpy().astype(float)


def monthly_uvs(panels, days: int):
    dord, up, tot = upvalue_daily(panels["daily"])
    cu, ct = np.concatenate([[0], np.cumsum(up)]), np.concatenate([[0], np.cumsum(tot)])
    out = np.full(len(panels["months"]), np.nan)
    for t, m in enumerate(panels["months"]):
        i = int(np.searchsorted(dord, m.toordinal(), "left"))  # sessions date < months[t]
        if i >= days:
            den = ct[i] - ct[i - days]
            if den > 0:
                out[t] = (cu[i] - cu[i - days]) / den
    return out


def score(panels, params):
    scores, exposure = _base(panels, params)
    cut, to = float(params.get("uv_cut", 1.0)), float(params.get("uv_to", 0.0))
    if cut >= 1.0 and to <= 0:
        return scores, exposure
    u = monthly_uvs(panels, int(params.get("uv_days", 21)))
    lo, hi = float(params.get("uv_lo", 0.45)), float(params.get("uv_hi", 0.55))
    out = np.asarray(exposure, dtype=float).copy()
    for t in range(len(out)):
        if not np.isfinite(u[t]):
            continue
        if cut < 1.0 and u[t] < lo:
            out[t] = out[t] * cut
        elif to > 0 and u[t] > hi and out[t] < 1.0:
            out[t] = max(out[t], to)
    return scores, out
