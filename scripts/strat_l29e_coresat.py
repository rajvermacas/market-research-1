"""Candidate: core-satellite book composition on the champion (Loop-29 E).

Setup in words: scores and exposure exactly as strat_l23a_liqconfirm (imported,
never copied). Then, on each decision row t, the cs_k highest-scoring ELIGIBLE
(finite-score) names that carry the Nifty 500 flag in the universe snapshot
receive a large additive bonus, so they occupy cs_k of the harness's top-N slots
(the "core"); the remaining top - cs_k slots fill from the full board by the
champion's own score (the "satellite", which may also contain further Nifty 500
names). Relative order inside each group is unchanged; weighting, exposure,
entry/exit and universe are the champion's.

Hypothesis: a reserved core of index names (liquid, widely owned) steadies the
book and trims drawdown without surrendering the small-cap satellite's return.
Falsifier: every cs_k either loses train CAGR beyond the null band (~1.3pp sd of
random rank tilts) or fails to improve DD / robust.

Novelty: strat_l17c_idxflag used membership as a multiplicative tilt (inert,
94.5-96.5) or an eligibility GATE (collapsed the book), on the legacy base.
This file is a slot RESERVATION (core-satellite) on the realistic-execution
L23a champion base — a different composition mechanism on a changed base.

POINT-IN-TIME CAVEAT: in_nifty500 is TODAY's membership, not membership at the
decision date. It is look-ahead/survivorship contaminated (today's members were
partly selected by the returns being measured); any train gain is suspect and
carries weak evidential weight.

Off-switch: cs_k = 0 (default) returns the imported scores untouched -> the
champion exactly.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

from strat_l23a_liqconfirm import score as _base

NEEDS_DAILY = True
SPACE = {"cs_k": [0, 5, 8, 12, 15]}
BONUS = 1e6

_U: dict = {}


def _members() -> set:
    if "m" not in _U:
        root = Path(__file__).resolve().parents[1]
        u = pl.read_parquet(root / "data" / "universe" / "nse_universe.parquet")
        _U["m"] = set(u.filter(pl.col("in_nifty500"))["symbol"].to_list())
    return _U["m"]


def score(panels, params):
    scores, exposure = _base(panels, params)
    k = int(params.get("cs_k", 0) or 0)
    if k <= 0:
        return scores, exposure
    mem = _members()
    is_m = np.array([c in mem for c in panels["cols"]])
    out = np.array(scores, dtype=float, copy=True)
    for t in range(out.shape[0]):
        r = out[t]
        idx = np.flatnonzero(np.isfinite(r) & is_m)
        if idx.size == 0:
            continue
        core = idx[np.argsort(-r[idx], kind="stable")[:k]]
        out[t, core] = r[core] + BONUS
    return out, exposure
