"""Candidate: book-health-conditioned exposure over the champion base
(strategy_lab contract).

Setup in words: rank, gates and tier exposure are imported wholesale from
strat_floorhighrankpersist (champion base, whose shaped exposure is binary
0/1 because tier_lo = tier_mid = 1.0). The regime is then scaled by the
health of the book itself, measured with the exact pick-rule replay
(imported from strat_l12a_incbonus):

    share[t] = fraction of names held ENTERING month t whose imported rank
               is still finite at t (still passing the fresh-print, fast-MA
               and print-drought gates)
    E[t]     = base_E[t] * max(share_floor, share[t])

so when most of the book is quietly failing its own entry gates, exposure
drops toward share_floor even if market breadth has not yet crossed the tier
lines; when the book is intact, exposure is unchanged.

Hypothesis: the tier regime measures the MARKET, but the book is a selected
subset — its own gate attrition is a faster, finer-grained read on the same
crack-up. Breadth fell before every drawdown, but the held names' gates fail
BEFORE breadth crosses b_lo. If attrition leads, scaling on it cuts the
worst months' exposure and improves Calmar without giving up much CAGR.
Falsified if: attrition is either simultaneous with (or lagged behind) the
breadth tiers — then scaling on it only dilutes exposure in already-weak
months (CAGR falls, DD unchanged) or adds churn around the tier edges.

Exactness argument: the replay uses the UNMODIFIED imported rank and base
exposure. This candidate only scales exposure, and share_floor > 0 keeps
E[t] > 0 exactly when base_E[t] > 0, so the harness's pick sets are
identical to the replayed ones (pick depends on E only through E > 0) —
held_mat is exact, not a proxy. This is why share_floor never takes 0 here.

PIT: share[t] uses incumbency from picks at months < t (replay is causal)
and rank rows ≤ t, i.e. closes through px[t]. px[t+1] is touched only for
finiteness inside the replay's harness-exact mask, never its value.

book_n must equal the harness --top (15 in this loop's trials).
max_hold mirrors the harness risk key so the replay matches the live book.

SPACE = champion base + variants:
  {"share_floor": 0.5, "max_hold": 4}
  {"share_floor": 0.3, "max_hold": 4}
  {"share_floor": 0.5, "max_hold": 0}   (no cap; pure exposure scaling)
"""

from __future__ import annotations

import numpy as np

from strat_floorhighrankpersist import score as _rp_score
from strat_l12a_incbonus import replay_book

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.69],
    "b_lo": [0.45],
    "b_mid": [0.55],
    "floor_lb": [19],
    "lookback": [10],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [5],
    "sustain_lo": [3],
    "sustain_hi": [2],
    "tier_lo": [1.0],
    "tier_mid": [1.0],
    "pers_lb": [6],
    "pers_w": [-0.16],
    "max_hold": [0, 4],
    "book_n": [15],
    "share_floor": [0.3, 0.5],
}


def score(panels, params):
    rank, base_exposure = _rp_score(panels, params)
    book_n = int(params.get("book_n", 15))
    max_hold = int(params.get("max_hold", 0) or 0)
    floor = float(params.get("share_floor", 0.5))
    col_idx = {s: j for j, s in enumerate(panels["cols"])}

    held_mat, _ = replay_book(panels, base_exposure, book_n, max_hold,
                              lambda t, held: rank[t])

    E = np.array(base_exposure, dtype=float, copy=True)
    for t in range(rank.shape[0]):
        if E[t] <= 0:
            continue
        held_idx = np.flatnonzero(held_mat[t])
        if held_idx.size == 0:
            continue  # book empty: no attrition signal, leave exposure alone
        alive = np.isfinite(rank[t][held_idx])
        share = float(alive.sum()) / held_idx.size
        E[t] = E[t] * max(floor, share)
    return rank, np.clip(E, 0.0, 1.0)
