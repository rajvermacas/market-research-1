"""Candidate: industry-momentum gate on the conditional-sustain book
(strategy_lab contract).

Mutation composing a tested mechanism (imported, never copied): rank and
regime from strat_floorhighsustaincond, but eligible only when the name's own
industry is a leader — the equal-weight mean `sect_lb`-month return of all
industry members with a finite close at month end t must clear `ind_q` as a
quantile of the industry-mean cross-section (ind_q 0.0 = any positive sector
momentum, 0.5 = the stronger half of industries).

Rationale: the floor-lift rank is industry-agnostic; when a sector bases,
the screen fills the book with its 25 best names, and the strategy inherits
one sector's drawdown. Strat_floorhighdiverse capped names per industry and
asked whether concentration is the edge; this gate asks the orthogonal
question — is the name's sector itself in demand? A stock climbing while its
industry lags is idiosyncratic; a stock climbing inside a leading industry is
rotation. If sector context is noise, the gate trails and says so.

Caveats: industry labels are NSE's current classification applied
historically (static reference data; mild reclassification lookahead, same
as strat_floorhighdiverse). PIT-safe otherwise: sector momentum for holding
month t uses closes through px[t] only, and only names with finite ret.

DATA CAVEAT (2026-09-20): the universe snapshot's `industry` column is null
for 2,059 of 2,558 symbols (~80%), so this file could NOT test a sector
hypothesis — most names collapse into one "UNKNOWN" group and the gate
degenerates into a market-momentum veto. Its ledger rows are NOT sector
evidence. Re-run only after a populated industry field exists.

SPACE = strat_floorhighsustaincond params + sect_lb {6,12}, ind_q {0.0,0.5}.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

from strat_floorhighsustaincond import score as _sc_score

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
    "sustain_lo": [6],
    "sustain_hi": [2],
    "sect_lb": [6, 12],
    "ind_q": [0.0, 0.5],
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
    rank, exposure = _sc_score(panels, params)
    px, months = panels["px"], panels["months"]
    cols = panels["cols"]
    lb = int(params.get("sect_lb", 6))
    q = float(params.get("ind_q", 0.0))

    ind = _industries(cols)
    uniq, gidx = np.unique(ind, return_inverse=True)
    n_g = len(uniq)

    ret = np.full_like(px, np.nan)
    if lb < px.shape[0]:
        with np.errstate(invalid="ignore", divide="ignore"):
            ret[lb:] = px[lb:] / px[:-lb] - 1

    out = np.array(rank, dtype=float, copy=True)
    for t in range(lb, rank.shape[0]):
        r = ret[t]
        fin = np.isfinite(r)
        if not fin.any():
            out[t] = np.nan
            continue
        s = np.bincount(gidx[fin], weights=r[fin], minlength=n_g)
        c = np.bincount(gidx[fin], minlength=n_g)
        with np.errstate(invalid="ignore", divide="ignore"):
            mom = np.where(c > 0, s / np.maximum(c, 1), np.nan)
        fg = np.isfinite(mom)
        thresh = float(np.quantile(mom[fg], q)) if q > 0 else 0.0
        keep = np.zeros(n_g, bool)
        keep[fg] = mom[fg] > thresh
        ok = np.isfinite(rank[t]) & keep[gidx]
        out[t] = np.where(ok, rank[t], np.nan)
    return out, exposure
