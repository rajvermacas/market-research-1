"""Candidate: fresh-print rank with per-industry concentration cap
(strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank and
breadth-tier regime from strat_floorhighfresh, plus a diversification
constraint — within each month, eligible names are taken in lift order but
at most `max_per_ind` per NSE industry survive (lower-ranked same-industry
names are set NaN, so the harness backfills from other sectors).

Rationale: floor-lift screens herd into whatever sector is basing — the book
can print 25 names from two industries and the "strategy DD" is really one
sector's drawdown. If concentration drives the left tail, the cap cuts DD
cheaper than any timing tweak; if the herding IS the edge (sector momentum),
the cap trails and says so. Industry is a static attribute (no PIT issue);
ordering within sector reuses the imported rank, never a new signal.

PIT-safe: cap applies to the month-t cross-section only; industry mapping is
static reference data.

DATA CAVEAT (2026-09-20): `industry` is null for ~80% of the universe, so the
cap mostly applied to a single "UNKNOWN" mega-group rather than to sectors —
this file's ledger rows (max_per_ind 3/5 trailing the base) are NOT evidence
about sector concentration or diversification. Re-run only with a populated
industry field.

SPACE = strat_floorhighfresh params + max_per_ind {3, 5}.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

from strat_floorhighfresh import score as _fresh_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [19],
    "lookback": [16],
    "max_dist": [0.055],
    "regime_ma": [18],
    "max_per_ind": [3, 5],
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
    rank, exposure = _fresh_score(panels, params)
    k = int(params.get("max_per_ind", 3))
    cols = panels["cols"]
    ind = _industries(cols)
    out = np.array(rank, dtype=float, copy=True)
    for t in range(rank.shape[0]):
        s = rank[t]
        ok = np.isfinite(s)
        if ok.sum() <= k:
            continue
        order = np.flatnonzero(ok)[np.argsort(-s[ok], kind="stable")]
        seen: dict = {}
        for j in order:
            g = ind[j]
            seen[g] = seen.get(g, 0) + 1
            if seen[g] > k:
                out[t, j] = np.nan
    return out, exposure
