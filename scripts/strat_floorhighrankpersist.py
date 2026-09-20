"""Candidate: eligibility-persistence-weighted rank at the current best's base
(strategy_lab contract).

Mutation composing a tested mechanism (imported, never copied): rank, gates
and shaped exposure from strat_floorhightiershape, with the score multiplied
by a persistence factor built from how often the name has been eligible
(finite rank) over the last `pers_lb` months:

    score = rank * (1 + pers_w * share_of_recent_months_eligible)

Rationale: the base rank already contains the eligibility gates, but it cannot
distinguish a name that keeps qualifying month after month from a one-month
wonder once both are eligible. A persistent qualifier (fresh prints and an
intact short trend for most of the last K months) is a different animal from a
single pop. If persistence carries no information, the weighted rank trails;
if it does, it should buy the same return from fewer marginal names.

PIT-safe: the eligibility share uses only rank rows up to month t.

FINDING (Loop-11, promoted to the main ledger twice): persistence is
ANTI-informative at this base. Positive weights degrade monotonically (w 0.25
→ 65.6, w 1.0 → 54.6 train vs 77.9 base). The keep is a negative weight — a
freshness premium: first `pers_lb 22 / pers_w -0.40` (+81.23 / -18.39 /
calmar 4.42 / fwd +58.53), then the converged champion
`pers_lb 6 / pers_w -0.16 / max_hold 4` (+83.93 / -19.96 / calmar 4.20 /
fwd +49.89, full-window DD -22.66% vs the -35.3% of the no-hold version).
Key shape findings: at pers_lb 12 the DD sits at -22.06% for every weight
(a window effect, not a weight effect); only pers_lb 6 yields the
inside-DD plateau; `max_hold 4` is a sharp isolated optimum that repairs the
DD while raising CAGR (max_hold 9 is inert — monthly churn resets holdings
first). Rows here are tuned on train; nifty500 discards (43.8/-20.6) and the
NSE board's survivorship bias applies.

SPACE = strat_floorhightiershape params + pers_lb {3,6,12}, pers_w {0.25,0.5,1.0}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhightiershape import score as _ts_score

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
    "pers_lb": [3, 6, 12],
    "pers_w": [0.25, 0.5, 1.0],
}


def score(panels, params):
    rank, exposure = _ts_score(panels, params)
    plb = int(params.get("pers_lb", 6))
    w = float(params.get("pers_w", 0.5))
    fin = np.isfinite(rank)

    out = np.array(rank, dtype=float, copy=True)
    for t in range(rank.shape[0]):
        lo = max(0, t - plb + 1)
        n = t - lo + 1
        share = fin[lo:t + 1].sum(axis=0) / n
        out[t] = rank[t] * (1.0 + w * share)
    out = np.where(fin, out, np.nan)
    return out, exposure
