"""Candidate: Zweig-style daily breadth THRUST re-arm (Loop-28 A).

Setup in words: rank, eligibility, breadth-tier exposure and book are exactly
strat_l23a_liqconfirm (imported, never copied). On every session the board
advance share a_d = (#symbols with close > prior close) / (#symbols with a
prior close), over nse_all names with volume > 0. A_d = th_span-session EMA
of a_d (warm-up guard: first 3*th_span sessions null). A THRUST fires on
session d when A_d > th_hi and min(A over the previous 10 sessions) < th_lo
(breadth went from oversold to overbought inside ten sessions, Zweig 1986:
0.40 -> 0.615). For month t, if a thrust fired in the last th_win sessions
before months[t] (date < months[t]) and the tier exposure is below 1,
exposure = max(exposure, th_to).

Hypothesis (theory -- Zweig's published thresholds, not fitted): breadth
thrusts mark the start of new advances after washouts; the level/18-month
breadth tier re-arms late, so a thrust re-arm captures the first leg of the
recovery. Falsifier: no cell lifts train CAGR at DD <= -17.22, or the gain
comes from a single episode (the l27o_corerearm failure mode: 5 of 7 firings
in 2020).

Novelty: l27o_corerearm (PARTIAL) re-arms on the liquid core's trailing
k-month RETURN; breadth ramps/hysteresis/derivative rows (DEAD) read share-
above-MA levels/slopes monthly. No row uses the daily advance/decline
thrust (speed of a breadth swing from oversold to overbought).

Off-switch: th_to = 0 -> champion exactly.
SPACE: th_span {10}, th_lo {0.40,0.45}, th_hi {0.60,0.615,0.65}, th_win {21,42},
th_to {0,0.7,1.0}.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_l23a_liqconfirm import score as _base

NEEDS_DAILY = True
SPACE = {"th_span": [10], "th_lo": [0.40, 0.45], "th_hi": [0.60, 0.615, 0.65],
         "th_win": [21, 42], "th_to": [0.0, 0.7, 1.0]}


def adv_share(daily, span: int):
    d = (daily.filter(pl.col("volume") > 0)
         .with_columns(pl.col("date").cast(pl.Date))
         .sort("symbol", "date")
         .with_columns(pl.col("close").shift(1).over("symbol").alias("pc"))
         .drop_nulls("pc")
         .group_by("date").agg((pl.col("close") > pl.col("pc")).mean().alias("a"),
                               pl.len().alias("n"))
         .filter(pl.col("n") >= 50).sort("date"))
    a = d["a"].to_numpy().astype(float)
    ema = np.full(len(a), np.nan)
    al = 2.0 / (span + 1.0)
    e = a[0] if len(a) else np.nan
    for i in range(len(a)):
        e = a[i] if i == 0 else al * a[i] + (1 - al) * e
        if i >= 3 * span:
            ema[i] = e
    return np.array([x.toordinal() for x in d["date"].to_list()]), ema


def thrust_days(daily, span, lo, hi):
    dord, A = adv_share(daily, span)
    fire = np.zeros(len(A), dtype=bool)
    for i in range(10, len(A)):
        prev = A[i - 10:i]
        if np.isfinite(A[i]) and np.all(np.isfinite(prev)) and A[i] > hi and prev.min() < lo:
            fire[i] = True
    return dord, fire


def score(panels, params):
    scores, exposure = _base(panels, params)
    to = float(params.get("th_to", 0.0))
    if to <= 0:
        return scores, exposure
    dord, fire = thrust_days(panels["daily"], int(params.get("th_span", 10)),
                             float(params.get("th_lo", 0.40)), float(params.get("th_hi", 0.615)))
    win = int(params.get("th_win", 21))
    out = np.asarray(exposure, dtype=float).copy()
    for t, m in enumerate(panels["months"]):
        if out[t] >= 1.0:
            continue
        i = int(np.searchsorted(dord, m.toordinal(), "left"))
        if i > 0 and fire[max(0, i - win):i].any():
            out[t] = max(out[t], to)
    return scores, out
