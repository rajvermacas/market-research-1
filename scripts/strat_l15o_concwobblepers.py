"""Candidate: freshness-premium rank tilt re-based onto the CURRENT champion
chain (strategy_lab contract).

Setup in words: entry, rank, gates, shaped exposure, the regime-conditional
concentration cap AND the eligibility-wobble discount are ALL untouched — the
full current champion chain (strat_l13a_concwobble at lookback 12, imported
wholesale) produces the capped, wobble-discounted rank, and this file
multiplies it by the Loop-11/13 freshness premium, a LINEAR persistence tilt
over the champion's own eligibility history:

    share = fraction of the last `pers_lb` months the name was eligible
            (finite in the imported champion rank history, rows t-pers_lb+1..t)
    score = champion_score * (1 + pers_w * share)

Why re-based: strat_l13b_concpers tested this term against the Loop-12
champion (capped chain, lookback 10, NO wobble tilt) and closed the channel at
that base — but the base has since changed twice: lookback 10 -> 12 (Loop-14)
and the eligibility-wobble discount gw_w 0.13 arrived (Loop-13), which is a
SECOND consumer of the same eligibility history. The open question is whether
the level-premium (pers_w < 0: fewer eligible months in the window = higher
score) is a substitute for the flip-share discount (already in the base) or
whether the crown's documented drawdown edge
(strat_floorhighrankpersist, pers_lb 4 / pers_w -0.18 / max_hold 2 / top 13:
train +80.88% / DD -15.05% / calmar 5.37 / fwd +54.11%) survives stacking onto
the current champion — which would give the ledger its first line with BOTH
the champion's train CAGR class and the crown's drawdown.

Hypothesis: the wobble term discounts names whose eligibility FLICKERS;
the persistence term discounts names that were mostly INELIGIBLE. A name can
have a clean flip history while being absent for most of the window (a single
recent print), and vice versa. If the two histories are not proportional, the
level term still carries information on top of the champion and a negative
weight should buy the same return from fewer marginal names; if the wobble
discount already prices the level, every variant trails.

Falsifies if: no (pers_lb, pers_w) with pers_w < 0 beats the flat base —
train +88.139% / DD -17.339% / calmar 5.083 / fwd +49.274% — then the
persistence-level channel is exhausted at the current champion base, and the
crown's edge is specific to its own (uncapped, max_hold 2, top 13) geometry.

Import chain: strat_l15o_concwobblepers -> strat_l13a_concwobble.score (which
imports strat_l12b_gatefail.score for the gate layers and wobble tilt and
mirrors the cap step from strat_floorhightiershapeconc.score). The persistence
tilt is the same linear form as strat_l13b_concpers, computed over THIS
base's own finite pattern — the base is the only thing changed.

Flat-base metric (pers_w = 0.0 must reproduce EXACTLY, including the wobble
tilt): train +88.139% / DD -17.339% / calmar 5.083 / H1 +80.14% / H2 +96.09% /
invested 65.5% / fwd +49.274% / fwd DD -14.926% / fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art is strat_l13b_concpers (the same linear
persistence term on the Loop-12 chain: capped, lookback 10, no wobble) and
strat_l13a_concwobble (the wobble discount = the SECOND eligibility-history
consumer). The one thing changed: the base. The prior falsification was
measured before lookback 12 and before the wobble discount existed; this file
asks whether a level-premium over the champion's own wobble-discounted
eligibility pattern still adds after that second consumer is in place. This is
a re-base of a surviving term, not a new shape of an old signal.

PIT argument: `share` reads only rows of the imported champion score up to and
including month t; each such row is computed from closes through px[m] by the
chain's own PIT guarantees. No daily panel, no forward rows. Names not finite
at t read NaN after the multiply (the tilt cannot resurrect an ineligible
name). Rows before the window read share over available rows only (divisor
t - lo + 1), matching the source term's convention.

SPACE = champion keys pinned (lookback 12, cap_weak 11, cap_full 20, gw_w
        0.13, gf_lb 12, gf_w 0.0, tier_lo/tier_mid 0.9999; max_hold 3 is a
        HARNESS key passed via params-json, this file does not consume it)
        + pers_lb {4, 6, 8}
        + pers_w {-0.20, -0.18, -0.16} (0.0 = off-switch).
"""

from __future__ import annotations

import numpy as np

from strat_l13a_concwobble import score as _cw_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.69],
    "b_lo": [0.45],
    "b_mid": [0.55],
    "floor_lb": [19],
    "lookback": [12],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [5],
    "sustain_lo": [3],
    "sustain_hi": [2],
    "tier_lo": [0.9999],
    "tier_mid": [0.9999],
    "cap_weak": [11],
    "cap_full": [20],
    "gf_lb": [12],
    "gf_w": [0.0],
    "gw_w": [0.13],
    "pers_lb": [4, 6, 8],
    "pers_w": [-0.20, -0.18, -0.16],
}


def score(panels, params):
    rank, exposure = _cw_score(panels, params)
    plb = int(params.get("pers_lb", 4))
    w = float(params.get("pers_w", 0.0))
    fin = np.isfinite(rank)

    out = np.array(rank, dtype=float, copy=True)
    if w != 0.0:
        for t in range(rank.shape[0]):
            lo = max(0, t - plb + 1)
            n = t - lo + 1
            share = fin[lo:t + 1].sum(axis=0) / n
            out[t] = rank[t] * (1.0 + w * share)
        out = np.where(fin, out, np.nan)
    return out, exposure
