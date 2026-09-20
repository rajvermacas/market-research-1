"""Candidate: industry-neutral rank on the concentrated-shape book
(strategy_lab contract).

Mutation composing a tested mechanism (imported, never copied): eligibility,
rank and shaped exposure from strat_floorhightiershapeconc, but the score is
made industry-neutral — each eligible name's rank is replaced by its
deviation from its own industry's mean rank among the eligible names at
month t. The harness then picks the top names by "how much better than its
industry peers this name is".

Rationale: the raw lift rank is industry-agnostic, so a hot sector can fill
the book with its 25 names and the strategy inherits one sector's drawdown
(seen in the ledger: strat_floorhighdiverse was built for exactly that
symptom). Strat_floorhighsector gated on sector momentum and subtracted;
this is a different question — not which sectors are strong, but which names
lead WITHIN their sector, keeping cross-sector diversification for free. If
intra-industry leadership carries information, this beats the level rank; if
lift level was the signal, it trails.

Caveats: industry labels are NSE's current classification applied
historically (static reference data; mild reclassification lookahead). PIT-safe
otherwise: month-t cross-section only.

DATA CAVEAT (2026-09-20): `industry` is null for ~80% of the universe, so the
neutralisation subtracted one giant "UNKNOWN" group's mean — an order-preserving
constant shift, i.e. a no-op (confirmed: metrics identical to the unmodified
composition). Its "no effect" result is vacuous, NOT evidence against
industry-neutral ranking. Re-run only with a populated industry field.

SPACE = strat_floorhightiershapeconc params (no extra keys).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

from strat_floorhightiershapeconc import score as _base_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [19],
    "lookback": [16],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [9],
    "sustain_lo": [4],
    "sustain_hi": [2],
    "tier_lo": [0.55],
    "tier_mid": [1.0],
    "cap_weak": [12],
    "cap_full": [20],
}

_REPO = Path(__file__).resolve().parents[1]
_ind_cache: dict | None = None


def _industries(cols):
    global _ind_cache
    if _ind_cache is None:
        u = pl.read_parquet(_REPO / "data" / "universe" / "nse_universe.parquet")
        _ind_cache = dict(zip(u["symbol"].to_list(), u["industry"].to_list()))
    return np.array([(_ind_cache.get(s) or "UNKNOWN") for s in cols])


def score(panels, params):
    rank, exposure = _base_score(panels, params)
    ind = _industries(panels["cols"])
    uniq, gidx = np.unique(ind, return_inverse=True)
    out = np.array(rank, dtype=float, copy=True)
    for t in range(rank.shape[0]):
        r = rank[t]
        fin = np.isfinite(r)
        if not fin.any():
            continue
        s = np.bincount(gidx[fin], weights=r[fin], minlength=len(uniq))
        c = np.bincount(gidx[fin], minlength=len(uniq))
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = np.where(c > 0, s / np.maximum(c, 1), np.nan)
        v = mean[gidx]
        out[t] = np.where(fin & np.isfinite(v), r - v, np.nan)
    return out, exposure
