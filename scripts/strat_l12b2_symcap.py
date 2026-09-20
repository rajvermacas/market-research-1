"""Candidate: concentration in BOTH risk bands over the freshness rank
(strategy_lab contract).

Setup in words: keep the champion's freshness-weighted rank and gates intact
(strat_floorhighrankpersist legs: rank * (1 + pers_w * share_eligible),
pers_lb 6 / pers_w -0.16) and extend the one live Loop-12 mechanism —
weak-month concentration — to full months too. Per month:

    band = exposure >= 1.0 (full risk) else (0 < exposure < 1.0, scaled risk)
    kept = top `cap_full` of the band's finite ranks, or top `cap_weak`
           in scaled months; the rest set NaN so the harness backfills nothing.
    sizes: any month with exposure > 0 trades at full size (1.0).

Live evidence (Loop-12, wB ledger): tier_lo/tier_mid 0.999 + cap_weak 11
took calmar from the champion's 4.20 to 4.40-4.47 at train 80.9-81.4, with
forward 54-57% CAGR at -12 to -14.4% DD vs the champion's 49.9 / -16.4; and
the single cap_full 18 row (max_hold 6) printed the best forward of the whole
file (60.0 / -12.3). Every weak-cap row bound at one of a few identical DDs,
so the count cap is the binding lever — but cap_full itself was almost never
moved from 20. This file moves it.

Hypothesis: the marginal names that hurt the tail are the lower-ranked names
in full-risk months too, not only in scaled months. If true, cap_full 16-18
with cap_weak 11 should keep train near the champion while lifting calmar and
forward as the weak-cap alone did. If the full-month tail is already clean,
tightening cap_full costs CAGR and the file dies.

Falsifies if: no (cap_full, cap_weak, max_hold) variant beats champion
train +83.93 / DD -19.96 / calmar 4.20 on the same selection rule — then
concentration is exhausted as a channel at this base.

PIT argument: caps read month-t ranks only, which the imported legs compute
from closes through month t; exposure bands come from the same month-t rank's
tier exposure. No forward rows, no daily panel (NEEDS_DAILY False).

NOTE for runners: pass tier_lo 0.999 / tier_mid 0.999 (as in the wB keep) so
scaled months read 0.999 < 1.0 and the band split is visible; with the
champion's 1.0/1.0 every in-market month maps to 1.0 and only cap_full bites.

SPACE = champion base + tier_lo {0.999}, tier_mid {0.999},
        cap_full {18, 16}, cap_weak {11}, max_hold {6, 8}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighrankpersist import score as _rp_score

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
    "tier_lo": [0.999],
    "tier_mid": [0.999],
    "pers_lb": [6],
    "pers_w": [-0.16],
    "cap_full": [18, 16],
    "cap_weak": [11],
    "max_hold": [6, 8],
}


def score(panels, params):
    rank, exposure = _rp_score(panels, params)
    cf = int(params.get("cap_full", 18))
    cw = int(params.get("cap_weak", 11))
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

    # sizes: any in-market month (exposure > 0) trades at full size
    sizes = np.where(E > 0, 1.0, 0.0)
    return out, sizes
