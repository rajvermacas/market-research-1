"""Candidate: freshness/persistence rank tilt on the CURRENT champion chain
(strategy_lab contract).

Setup in words: entry, rank, gates, shaped exposure and the regime-
conditional concentration cap are ALL untouched — the full champion chain
strat_floorhightiershapeconc -> strat_floorhightiershape ->
strat_floorhighsustaincond (imported, never copied) produces the capped rank,
and this file multiplies it by the Loop-11 freshness premium, a LINEAR
persistence tilt over the same rank history:

    share = fraction of the last `pers_lb` months the name was eligible
            (finite in the capped rank history)
    score = rank * (1 + pers_w * share)

Hypothesis (the question this file answers): the freshness premium was found
in Loop-11 at max_hold 4 on the UNCAPPED strat_floorhightiershape base;
Loop-12 then found a drought-shaped substitute at max_hold 4 on that same
superseded base. Neither was ever screened against the CURRENT champion —
weak-month cap 11/20 at max_hold 3. The cap keeps only the top 11 ranks in
scaled-risk months, which may already BE the freshness filter (stale one-pop
names sit below the cap line). If the freshness channel still carries
information on top of the cap at max_hold 3, a negative weight (freshness
premium: fewer eligible months in the window = HIGHER score) should beat the
capped champion from the same eligibility history; if the cap absorbed it,
every weight here trails and the channel is exhausted at this base.

Falsifies if: no (pers_lb, pers_w) beats the capped champion train +85.23% /
DD -17.49% / calmar 4.87 / fwd +53.76% — then the weak-month cap and the
freshness premium are the same signal at max_hold 3.

Import chain: strat_l13b_concpers -> strat_floorhightiershapeconc ->
strat_floorhightiershape -> strat_floorhighsustaincond (chain untouched).

Flat-base metric (pers_w = 0 must reproduce EXACTLY):
    train +85.23% / DD -17.49% / calmar 4.87, fwd +53.76%
    (champion strat_floorhightiershapeconc, top 15, max_hold 3).

Consumed keys: pers_lb, pers_w — plus every champion key (b_hi, b_lo, b_mid,
floor_lb, lookback, max_dist, regime_ma, fast_ma, sustain_lo, sustain_hi,
tier_lo, tier_mid, cap_weak, cap_full, max_hold) passed straight through to
the chain.

PIT-safe: the eligibility share reads only rows of the imported capped rank up
to and including month t; no forward rows, no daily panel.

SPACE = champion base + pers_lb {4, 5, 6}, pers_w {-0.16, -0.18}.
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
    "pers_lb": [4, 5, 6],
    "pers_w": [-0.16, -0.18],
}


def score(panels, params):
    rank, exposure = _conc_score(panels, params)
    plb = int(params.get("pers_lb", 6))
    w = float(params.get("pers_w", 0.0))
    fin = np.isfinite(rank)

    out = np.array(rank, dtype=float, copy=True)
    for t in range(rank.shape[0]):
        lo = max(0, t - plb + 1)
        n = t - lo + 1
        share = fin[lo:t + 1].sum(axis=0) / n
        out[t] = rank[t] * (1.0 + w * share)
    out = np.where(fin, out, np.nan)
    return out, exposure
