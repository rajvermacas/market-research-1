"""Candidate: drought-shape tilt on the CURRENT champion chain
(strategy_lab contract).

Setup in words: entry, rank, gates, shaped exposure and the regime-conditional
concentration cap are ALL untouched — the full champion chain
strat_floorhightiershapeconc -> strat_floorhightiershape ->
strat_floorhighsustaincond (imported, never copied) produces the capped rank,
and this file multiplies it by a shaped freshness-drought tilt:

    share = fraction of the last `drought_lb` months the name was eligible
            (finite in the capped rank history)
    shape "sqrt":  tilt = 1 - drought_w * sqrt(share)
    shape "step":  tilt = 1 - drought_w      if share >= s_hi
                   tilt = 1 - drought_w / 2  if share >= s_lo
                   tilt = 1.0                otherwise

Hypothesis: Loop-12 found the drought term works on the OLD
strat_floorhightiershape base (no weak-month cap, max_hold 4) — but that base
is superseded. Loop-11 proved freshness carries information (the anti-
persistence premium) and Loop-12 proved the marginal month is not constant in
age; if the freshness channel still carries information ON TOP of the weak-
month cap at max_hold 3, a staleness-tilted score should beat the capped
champion from the same eligibility history. If the cap already absorbed the
freshness signal (weak-month capping keeps only the top 11 ranks, which may
itself be the freshness filter), every tilt here trails and the channel is
exhausted at this base.

Falsifies if: no (drought_lb, drought_w, shape) beats the capped champion
train +85.23% / DD -17.49% / calmar 4.87 / fwd +53.76% — then the cap and the
drought premium are the same signal, and shape work on this base is dead.

Import chain: strat_l13b_concdrought -> strat_floorhightiershapeconc ->
strat_floorhightiershape -> strat_floorhighsustaincond (chain untouched).

Flat-base metric (drought_w = 0 must reproduce EXACTLY):
    train +85.23% / DD -17.49% / calmar 4.87, fwd +53.76%
    (champion strat_floorhightiershapeconc, top 15, max_hold 3).

Consumed keys: drought_lb, drought_w, drought_shape, s_lo, s_hi — plus every
champion key (b_hi, b_lo, b_mid, floor_lb, lookback, max_dist, regime_ma,
fast_ma, sustain_lo, sustain_hi, tier_lo, tier_mid, cap_weak, cap_full,
max_hold) passed straight through to the chain.

PIT-safe: the eligibility share reads only rows of the imported capped rank up
to and including month t; no forward rows, no daily panel.

SPACE = champion base + drought_lb {3, 6}, drought_w {0.15, 0.25, 0.28},
        drought_shape {"sqrt"}, s_lo {0.3}, s_hi {0.7}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhightiershapeconc import score as _conc_score

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
    "tier_lo": [0.9999],
    "tier_mid": [0.9999],
    "cap_weak": [11],
    "cap_full": [20],
    "max_hold": [3],
    "drought_lb": [3, 6],
    "drought_w": [0.15, 0.25, 0.28],
    "drought_shape": ["sqrt"],
    "s_lo": [0.3],
    "s_hi": [0.7],
}


def score(panels, params):
    rank, exposure = _conc_score(panels, params)
    dlb = int(params.get("drought_lb", 6))
    dw = float(params.get("drought_w", 0.0))
    shape = str(params.get("drought_shape", "sqrt"))
    s_lo = float(params.get("s_lo", 0.3))
    s_hi = float(params.get("s_hi", 0.7))
    fin = np.isfinite(rank)

    out = np.array(rank, dtype=float, copy=True)
    for t in range(rank.shape[0]):
        lo = max(0, t - dlb + 1)
        n = t - lo + 1
        share = fin[lo:t + 1].sum(axis=0) / n
        if shape == "sqrt":
            tilt = 1.0 - dw * np.sqrt(share)
        else:  # step
            tilt = np.where(share >= s_hi, 1.0 - dw,
                            np.where(share >= s_lo, 1.0 - dw / 2.0, 1.0))
        out[t] = rank[t] * tilt
    out = np.where(fin, out, np.nan)
    return out, exposure
