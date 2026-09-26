"""Candidate: demote likely-bad-fill names to fallback on the L25 champion (Loop-28 designer D).

Setup in words: rank, eligibility, exposure regime and weights are exactly the
champion's (strat_l23a_liqconfirm, imported, never copied; top 25 inverse-vol).
Each month t, a ranked name is flagged FILL-RISK if in the last ld_days sessions
before the decision date (daily date < months[t]) it had a session that closed
at its high (close >= high * (1 - 0.001)) with a close-to-close gain of at least
ld_r - i.e. it closed at / near an upper circuit, so the next-open fill is either
refused (harness up-lock) or taken at a gapped-up price. Flagged names are
DEMOTED below every unflagged name, champion order preserved inside each group.
No name is removed, nothing is added to the score: it is a lift/demote scheme
(as in strat_l28b_corrdiv), not a tilt.

Harness fact (scripts/strategy_lab.py simulate): a refused entry (up-locked or
tv20 < 50 lakh) is NOT cash - the slot already goes to the next rank. So this
rule cannot convert cash into fills; its only possible value is avoiding names
that DO fill but at a bad (gapped-up) open. Hypothesis: names closing at an
upper circuit then fill at an elevated open and mean-revert over the month, so
swapping them for the next fillable names raises CAGR/lowers DD. Falsifier:
blocked-lock falls but CAGR falls beyond noise (as in l22a_lockpen: up-lockers
are the momentum winners) or nothing moves.

Novelty: closest DEAD rows strat_l22a_lockpen / strat_l22a_gappen (ADDITIVE
penalties on share of locked / gap days, OLD floorhighfresh base) and
strat_l22b_liqrs (liquid pre-filter, old base). Here: base = L25 champion,
mechanism = demote-to-fallback (never drops a name, keeps champion order),
predictor = a last-few-sessions closed-at-high big-gain event.

Off-switch: ld_r >= 1.0 (default) returns the champion untouched.
Keys: ld_r (min close-to-close gain of the event day), ld_days (sessions looked back).
SPACE: ld_r {0.09, 0.15, 0.19}, ld_days {1, 3}.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_l23a_liqconfirm import score as _champ

NEEDS_DAILY = True
SPACE = {"ld_r": [1.0, 0.09, 0.15, 0.19], "ld_days": [1, 3]}


def event_matrix(panels, r_min):
    cols = list(panels["cols"])
    d = (panels["daily"].select("symbol", "date", "high", "close")
         .filter(pl.col("symbol").is_in(cols) & (pl.col("close") > 0))
         .sort("symbol", "date")
         .with_columns((pl.col("close") / pl.col("close").shift(1).over("symbol") - 1).alias("r"))
         .with_columns(((pl.col("r") >= r_min) & (pl.col("close") >= pl.col("high") * 0.999))
                       .fill_null(False).alias("ev")))
    dates = np.unique(d["date"].to_numpy().astype("datetime64[D]"))
    di = np.searchsorted(dates, d["date"].to_numpy().astype("datetime64[D]"))
    cidx = {s: j for j, s in enumerate(cols)}
    cj = np.array([cidx[s] for s in d["symbol"].to_list()])
    # per-symbol sessions: store the event on the symbol's own session index
    ev = d["ev"].to_numpy()
    return dates, di, cj, ev


def score(panels, params):
    scores, exposure = _champ(panels, params)[:2]
    r_min = float(params.get("ld_r", 1.0))
    if r_min >= 1.0:
        return scores, exposure
    nd = int(params.get("ld_days", 1))
    s0 = np.asarray(scores, dtype=float)
    out = s0.copy()
    dates, di, cj, ev = event_matrix(panels, r_min)
    months = np.asarray(panels["months"]).astype("datetime64[D]")
    ncol = s0.shape[1]
    # per-symbol ordered session dates and events
    per = [[] for _ in range(ncol)]
    for a, j, e in zip(di, cj, ev):
        per[j].append((a, e))
    sd = [np.array([x[0] for x in p], dtype=np.int64) for p in per]
    se = [np.array([x[1] for x in p], dtype=bool) for p in per]
    for t in range(min(len(months), s0.shape[0])):
        s = s0[t]
        idx = np.flatnonzero(np.isfinite(s))
        if idx.size == 0:
            continue
        k = int(np.searchsorted(dates, months[t]))  # date index < months[t]
        lift = np.nanmax(s[idx]) - np.nanmin(s[idx]) + 1.0
        for j in idx:
            q = int(np.searchsorted(sd[j], k))  # this symbol's sessions before months[t]
            if q == 0 or not se[j][max(0, q - nd):q].any():
                out[t, j] = s[j] + lift
    return out, exposure
