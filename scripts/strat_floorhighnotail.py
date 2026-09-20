"""Candidate: fresh-print rank with extended-tail trim (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied): rank and
breadth-tier regime from strat_floorhighfresh, but names above the monthly
`tail_q` quantile of lift are excluded — the book holds confirmed breakouts
without the most-extended outliers.

Rationale: the no-scale-out lesson says the edge lives in the tail, but
that was about EXITS (holding winners), not entries — chasing the single
most-extended name each month may still be overpaying for lottery tickets
while the meat sits at the 80-95th percentile of lift. Trimming the very
top tests entry-tail vs exit-tail asymmetry directly: if entries want the
tail too, this trails; if entries pay for extremes, the trim keeps the
compounding while cutting the blow-ups.

PIT-safe: the quantile is purely cross-sectional within month t on the
imported rank; eligibility otherwise inherits the fresh leg. No forward
information.

SPACE = strat_floorhighfresh params + tail_q {0.95, 0.99} (upper trim only).
"""

from __future__ import annotations

import numpy as np

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
    "tail_q": [0.95, 0.99],
}


def score(panels, params):
    rank, exposure = _fresh_score(panels, params)
    q = float(params.get("tail_q", 0.95))
    out = np.array(rank, dtype=float, copy=True)
    for t in range(rank.shape[0]):
        s = rank[t]
        ok = np.isfinite(s)
        if ok.sum() < 5:
            continue
        cap = np.nanquantile(s[ok], q)
        out[t] = np.where(ok & (s <= cap), s, np.nan)
    return out, exposure
