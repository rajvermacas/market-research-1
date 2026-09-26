"""Candidate: demote extreme last-week run-ups to fallback on the L25 champion (Loop-28 designer D).

Setup in words: rank, eligibility, exposure regime and inverse-vol weights are
exactly the champion's (strat_l23a_liqconfirm, imported, never copied). Each month
t, a ranked name whose close-to-close return over its last ru_days sessions before
the decision date (daily date < months[t]) is at least ru_r is flagged as a
BAD-FILL risk (gap-up open, near-circuit, likely refused or filled at a stretched
price). Flagged names are DEMOTED below all unflagged names; champion order is kept
inside each group, nothing is removed, nothing is added to the score (lift/demote
as in strat_l28b_corrdiv, not a tilt).

Harness fact: a refused entry already passes its slot to the next rank (not cash),
so the only value available is avoiding names that fill at a stretched open and
then give back the spike. Hypothesis: a >= ru_r run-up in the final week before
rebalance is exhaustion, not momentum, at the monthly horizon. Falsifier: CAGR falls
beyond noise (~0.16 robust) with blocked-lock unchanged or down (the stretched
names were the winners, as in l22a_lockpen), or nothing moves.

Novelty: closest DEAD rows strat_l22a_gappen / strat_l22a_lockpen (additive
penalties, old floorhighfresh base), strat_l28d_lockdemote (single closed-at-high
event; barely touched the book). Here predictor = short-window run-up magnitude,
base = L25 champion, mechanism = demote-to-fallback.

Off-switch: ru_r >= 5.0 (default) returns the champion untouched.
Keys: ru_r (min run-up), ru_days (sessions).
SPACE: ru_r {0.15, 0.25, 0.35}, ru_days {5, 10}.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_l23a_liqconfirm import score as _champ

NEEDS_DAILY = True
SPACE = {"ru_r": [5.0, 0.15, 0.25, 0.35], "ru_days": [5, 10]}


def score(panels, params):
    scores, exposure = _champ(panels, params)[:2]
    r_min = float(params.get("ru_r", 5.0))
    if r_min >= 5.0:
        return scores, exposure
    nd = int(params.get("ru_days", 5))
    cols = list(panels["cols"])
    cidx = {s: j for j, s in enumerate(cols)}
    d = (panels["daily"].select("symbol", "date", "close")
         .filter(pl.col("symbol").is_in(cols) & (pl.col("close") > 0))
         .sort("symbol", "date"))
    sd, sc = {}, {}
    for (sym,), g in d.group_by(["symbol"], maintain_order=True):
        sd[cidx[sym]] = g["date"].to_numpy().astype("datetime64[D]")
        sc[cidx[sym]] = g["close"].to_numpy()
    s0 = np.asarray(scores, dtype=float)
    out = s0.copy()
    months = np.asarray(panels["months"]).astype("datetime64[D]")
    for t in range(min(len(months), s0.shape[0])):
        s = s0[t]
        idx = np.flatnonzero(np.isfinite(s))
        if idx.size == 0:
            continue
        lift = np.nanmax(s[idx]) - np.nanmin(s[idx]) + 1.0
        for j in idx:
            flag = False
            if j in sd:
                q = int(np.searchsorted(sd[j], months[t]))  # sessions with date < months[t]
                if q > nd:
                    flag = sc[j][q - 1] / sc[j][q - 1 - nd] - 1 >= r_min
            if not flag:
                out[t, j] = s[j] + lift
    return out, exposure
