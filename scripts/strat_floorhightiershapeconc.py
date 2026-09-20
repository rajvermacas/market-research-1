"""Candidate: tier-shape book with regime-conditional concentration
(strategy_lab contract).

Mutation composing a tested mechanism (imported, never copied): rank and
shaped exposure from strat_floorhightiershape, but the book size is
regime-conditional — in full-risk months (shaped exposure 1.0) the harness
may take its full `cap_full` names; in scaled-risk months only the top
`cap_weak` ranks survive (lower ranks set NaN, so the harness backfills
nothing).

Rationale: the shape search showed the strategy wants MORE capital deployed
in scaled-breadth months. A second, orthogonal question is breadth of the
book: when the regime is only partly on, the lower-ranked names in the top-20
are the marginal ideas — concentrating on the best `cap_weak` of them may
raise per-name quality (and cut the weakest-month left tail) while letting
full-risk months keep diversification. If the marginal names are as good as
the leaders, this trails and says so.

PIT-safe: capping reads month-t ranks only; exposure is tier-shape's.

SPACE = strat_floorhightiershape params + cap_weak {8,12,15}, cap_full {20}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhightiershape import score as _ts_score

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
    "cap_weak": [8, 12, 15],
    "cap_full": [20],
}


def score(panels, params):
    rank, exposure = _ts_score(panels, params)
    cw = int(params.get("cap_weak", 12))
    cf = int(params.get("cap_full", 20))
    E = np.asarray(exposure, dtype=float)
    out = np.array(rank, dtype=float, copy=True)
    for t in range(out.shape[0]):
        r = out[t]
        fin = np.flatnonzero(np.isfinite(r))
        if fin.size == 0:
            continue
        cap = cf if E[t] >= 1.0 else cw
        if fin.size <= cap:
            continue
        order = fin[np.argsort(-r[fin], kind="stable")]
        out[t, order[cap:]] = np.nan
    return out, E
