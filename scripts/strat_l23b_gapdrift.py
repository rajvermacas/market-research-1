"""Candidate: held high-volume gap-up bonus — post-event drift proxy (strategy_lab
contract; Loop-23 designer B, axis = NEW RANKING/SELECTION CHANNEL).

Setup in words: rank exactly as strat_floorhighfresh (composed via
`from strat_floorhighfresh import score as _base`, breadth-tier regime kept),
then multiply each eligible score by (1 + w) when the name had a "held event"
in the {lb} calendar months strictly BEFORE the decision month. A held event is
a session whose open gapped >= {gap} above the prior close on volume >= {vm} x
the name's trailing 20-session median volume (shifted, so the event bar is not
in its own baseline), AND whose month's last close stayed at or above that
session's open (the gap was not filled by month end). Names without an event
keep their base score; NaN stays NaN; exposure untouched.

PIT: only daily bars with date < months[t] (whole months strictly before month
t, stale by one month) — same conservative convention as strat_l22a_gappen.

Hypothesis: a high-volume gap that holds is an information event (results,
orders) the market is still digesting — post-earnings-announcement drift without
an earnings calendar. Among fresh-high names, the ones carrying such an event
should drift further and fail less.
Falsifier: if no variant beats the off-switch on the robust ruler by more than
noise without widening DD, the drift proxy adds nothing on this base.

NOVELTY: closest registry rows — strat_l22a_gappen (overnight-gap SIZE as a
PENALTY, mean |gap| over months, DEAD) and the legacy liquidity/volume/
sponsorship + strat_l16c_volpart / strat_l17d_flowdir volume families (DEAD).
This file is different in kind: a discrete signed EVENT (gap UP x volume
shock x not-filled) rewarded as a bonus, not a continuous gap-size or volume-
level tilt. No registry row conditions on an event holding its gain.

Keys consumed: gd_w (default 0.0 = off-switch identity), gd_lb, gd_gap, gd_vm,
gd_held (default true; false = ablation that drops the "held its gain" test, to
check the hold condition carries the effect rather than the gap alone),
gd_placebo (default absent; an int seed gives the same NUMBER of bonuses per
month to random eligible names — a same-dose random control).
All base keys pass through to strat_floorhighfresh.
SPACE (documented variants + off-switch):
    gd_w 0.0                                   off-switch
    gd_w 0.15, gd_lb 2, gd_gap 0.03, gd_vm 2.0
    gd_w 0.30, gd_lb 2, gd_gap 0.03, gd_vm 2.0
    gd_w 0.15, gd_lb 3, gd_gap 0.05, gd_vm 3.0
    gd_w 0.15, gd_lb 1, gd_gap 0.03, gd_vm 2.0
    gd_w 0.15, gd_lb 3, gd_gap 0.03, gd_vm 2.0, gd_held false   (ablation)
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_floorhighfresh import score as _base

NEEDS_DAILY = True
SPACE = {"gd_w": [0.0, 0.15, 0.3], "gd_lb": [1, 2, 3], "gd_gap": [0.03, 0.05], "gd_vm": [2.0, 3.0]}


def _monthly_event(daily: pl.DataFrame, gap: float, vm: float, held: bool = True) -> pl.DataFrame:
    d = daily.sort(["symbol", "date"]).with_columns(
        pl.col("close").shift(1).over("symbol").alias("pc"),
        pl.col("volume").cast(pl.Float64).shift(1).rolling_median(20).over("symbol").alias("mv"),
        pl.col("date").dt.truncate("1mo").cast(pl.Date).alias("mon"),
    ).with_columns(
        pl.col("close").last().over(["symbol", "mon"]).alias("mclose"),
    )
    ev = ((pl.col("open") / pl.col("pc") - 1.0 >= gap)
          & (pl.col("volume").cast(pl.Float64) >= vm * pl.col("mv"))
          & (pl.col("mv") > 0)
          & ((pl.col("mclose") >= pl.col("open")) | (not held)))
    return d.group_by(["symbol", "mon"]).agg(ev.fill_null(False).any().cast(pl.Float64).alias("f"))


def score(panels, params):
    s, regime = _base(panels, params)
    w = float(params.get("gd_w", 0.0))
    if w == 0.0:
        return s, regime
    lb = int(params.get("gd_lb", 2))
    gap = float(params.get("gd_gap", 0.03))
    vm = float(params.get("gd_vm", 2.0))
    seed = params.get("gd_placebo")
    rng = np.random.default_rng(int(seed)) if seed is not None else None
    months = pl.Series(list(panels["months"])).cast(pl.Date).to_list()
    cols = list(panels["cols"])
    held = bool(params.get("gd_held", True))
    feat = _monthly_event(panels["daily"], gap, vm, held)
    wide = (feat.filter(pl.col("symbol").is_in(cols))
            .pivot(on="symbol", index="mon", values="f").sort("mon"))
    idx = {m: i for i, m in enumerate(months)}
    ci = {c: j for j, c in enumerate(cols)}
    F = np.zeros((len(months), len(cols)))
    mons = wide["mon"].to_list()
    for c in wide.columns[1:]:
        j = ci.get(c)
        if j is None:
            continue
        v = np.nan_to_num(wide[c].to_numpy().astype(float))
        for m, x in zip(mons, v):
            i = idx.get(m)
            if i is not None:
                F[i, j] = x
    out = s.copy()
    for t in range(len(months)):
        if t - lb < 0:
            continue
        flag = F[t - lb:t].max(axis=0) > 0  # months strictly before month t
        ok = np.isfinite(s[t]) & flag
        if rng is not None:  # placebo: same number of bonuses, random names
            fin = np.where(np.isfinite(s[t]))[0]
            k = int(ok.sum())
            ok = np.zeros(len(cols), dtype=bool)
            if k:
                ok[rng.choice(fin, size=k, replace=False)] = True
        out[t, ok] = s[t, ok] * (1.0 + w)
    return out, regime
