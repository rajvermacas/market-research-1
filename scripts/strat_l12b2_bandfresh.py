"""Candidate: band-conditional freshness premium on the champion rank
(strategy_lab contract).

Setup in words: keep the champion's base rank, gates and tier exposure
(strat_floorhightiershape legs — the rank BEFORE the persistence weighting)
and re-express the freshness premium per risk band instead of as one scalar:

    share = fraction of the last `pers_lb` months the name was eligible
    score = rank * (1 + w_band * share)
    w_band = pers_w_full if this month's exposure >= 1.0, else pers_w_weak

Negative w = freshness premium (names that keep qualifying month after month
are discounted; first-time qualifiers rank up), matching the champion's
pers_lb 6 / pers_w -0.16.

Live evidence (Loop-12): the freshness premium is the champion's biggest
single lever, but every attempt to re-shape it GLOBALLY died this round
(droughtshape sqrt/step: train 78-82 < champion 83.93; gatefail: 76.07;
trail_k 0.2: 59.5). What survived is band-conditional: concentration cuts in
SCALED months (cap_weak 11) lifted calmar and forward while full months stayed
wide — the tail damage is located in scaled months. So condition the one
proven lever on the same band: discount stale names harder in scaled months
(pers_w_weak more negative) where the tail lives, leave full months alone.

Hypothesis: the freshness premium's marginal value differs by regime band. If
stale qualifiers are the scaled-month tail, (w_full -0.16, w_weak -0.30) beats
the champion on train CAGR or DD; if the premium is one scalar, every pairing
ties or trails and band-conditional freshness is dead.

Falsifies if: no (w_full, w_weak) pairing beats champion train +83.93 / DD
-19.96 / calmar 4.20 — then the freshness channel is a single scalar at this
base and further conditioning work (band, window, shape) should stop.

PIT argument: the share uses only the imported rank's own finite/NaN pattern
in rows up to and including month t (each computed from closes through month
t); the band uses the same month-t tier exposure. No forward rows, no daily
panel (NEEDS_DAILY False). max_hold stays at the champion's 4 (the isolated
optimum) — this file varies weights only.

NOTE for runners: pass tier_lo 0.999 / tier_mid 0.999 so scaled months read
0.999 < 1.0 and the band split is visible (with 1.0/1.0 every in-market month
is "full" and the file reduces to the uniform premium).

SPACE = champion base + tier_lo {0.999}, tier_mid {0.999},
        pers_lb {6}, pers_w_full {-0.16, -0.08}, pers_w_weak {-0.30, -0.08},
        max_hold {4}.
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
    "tier_lo": [0.999],
    "tier_mid": [0.999],
    "pers_lb": [6],
    "pers_w_full": [-0.16, -0.08],
    "pers_w_weak": [-0.30, -0.08],
    "max_hold": [4],
}


def score(panels, params):
    rank, exposure = _ts_score(panels, params)
    plb = int(params.get("pers_lb", 6))
    w_full = float(params.get("pers_w_full", -0.16))
    w_weak = float(params.get("pers_w_weak", -0.30))
    E = np.asarray(exposure, dtype=float)
    fin = np.isfinite(rank)

    out = np.array(rank, dtype=float, copy=True)
    for t in range(rank.shape[0]):
        lo = max(0, t - plb + 1)
        n = t - lo + 1
        share = fin[lo:t + 1].sum(axis=0) / n
        w = w_full if E[t] >= 1.0 else w_weak
        out[t] = rank[t] * (1.0 + w * share)
    out = np.where(fin, out, np.nan)

    # sizes: any in-market month trades at full size (band split is for
    # weighting only; the champion sizes every in-market month at 1.0)
    sizes = np.where(E > 0, 1.0, 0.0)
    return out, sizes
