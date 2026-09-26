"""Candidate: pullback-shallowness quality tilt (strategy_lab contract; Loop-23
designer B, axis = NEW RANKING/SELECTION CHANNEL on a CHANGED BASE).

Setup in words: rank exactly as strat_floorhighfresh (composed via
`from strat_floorhighfresh import score as _base`, breadth-tier regime kept),
then multiply each eligible score by 1 + w*(2*pct-1), where pct is the
cross-sectional percentile (among the base's finite names) of the NEGATED
deepest drawdown from the running peak of daily closes over the {lb} calendar
months strictly BEFORE the decision month. w > 0 favours names whose uptrend
pullbacks were shallow (clean grinders); w < 0 favours V-recoveries.

PIT: only daily bars with date < months[t] (whole months strictly before
month t) — same conservative convention as strat_l22a_gappen. The running
peak is taken over the loaded daily history up to each bar only.

Hypothesis: among names printing a fresh high, the ones that got there with
shallow pullbacks have steadier holder bases, so the book should take smaller
drawdowns without giving up CAGR.
Falsifier: no variant beats the off-switch by more than noise on the robust
ruler, or the gain comes with a wider DD.

NOVELTY / DEAD-family retest: strat_l17d_reldd (panel-relative max drawdown,
DEAD on the L17 legacy-exec chain) is the closest row. What changed: the base
(strat_floorhighfresh, a different, simpler rank chain) and the execution model
(--exec realistic: next-open fill, lock refusal, 50 lakh ADV floor), and the
form (plain window max-dd percentile, post-base multiplicative, no pre-cap
mirroring). Stated as a changed-base retest, not a new family.

Keys consumed: dq_w (default 0.0 = off-switch identity), dq_lb, dq_placebo
(default absent; an int seed permutes the percentiles among eligible names each
month — a same-dose random-tilt control for the tilt's effect).
SPACE (documented variants + off-switch):
    dq_w 0.0            off-switch
    dq_w 0.15, dq_lb 6
    dq_w 0.15, dq_lb 12
    dq_w -0.15, dq_lb 6
    dq_w 0.3, dq_lb 6
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_floorhighfresh import score as _base

NEEDS_DAILY = True
SPACE = {"dq_w": [0.0, 0.15, -0.15, 0.3], "dq_lb": [6, 12]}


def _monthly_feature(daily: pl.DataFrame) -> pl.DataFrame:
    d = daily.sort(["symbol", "date"]).with_columns(
        (1.0 - pl.col("close") / pl.col("close").cum_max().over("symbol")).alias("dd"),
        pl.col("date").dt.truncate("1mo").cast(pl.Date).alias("mon"),
    )
    return d.group_by(["symbol", "mon"]).agg(pl.col("dd").max().alias("f"))


def score(panels, params):
    s, regime = _base(panels, params)
    w = float(params.get("dq_w", 0.0))
    if w == 0.0:
        return s, regime
    lb = int(params.get("dq_lb", 6))
    seed = params.get("dq_placebo")
    rng = np.random.default_rng(int(seed)) if seed is not None else None
    months = pl.Series(list(panels["months"])).cast(pl.Date).to_list()
    cols = list(panels["cols"])
    feat = _monthly_feature(panels["daily"])
    wide = (feat.filter(pl.col("symbol").is_in(cols))
            .pivot(on="symbol", index="mon", values="f").sort("mon"))
    idx = {m: i for i, m in enumerate(months)}
    ci = {c: j for j, c in enumerate(cols)}
    F = np.full((len(months), len(cols)), np.nan)
    mons = wide["mon"].to_list()
    for c in wide.columns[1:]:
        j = ci.get(c)
        if j is None:
            continue
        v = wide[c].to_numpy().astype(float)
        for m, x in zip(mons, v):
            i = idx.get(m)
            if i is not None:
                F[i, j] = x
    out = s.copy()
    for t in range(len(months)):
        if t - lb < 0:
            continue
        win = F[t - lb:t]  # months strictly before month t
        with np.errstate(all="ignore"):
            x = -np.nanmax(np.where(np.isfinite(win), win, -np.inf), axis=0)
        x[~np.isfinite(x)] = np.nan
        ok = np.isfinite(s[t]) & np.isfinite(x)
        n = ok.sum()
        if n < 2:
            continue
        r = np.empty(n)
        r[np.argsort(x[ok], kind="stable")] = np.arange(n)
        if rng is not None:
            r = rng.permutation(r)  # placebo: same dose, signal destroyed
        pct = r / (n - 1)
        out[t, ok] = s[t, ok] * (1.0 + w * (2.0 * pct - 1.0))
    return out, regime
