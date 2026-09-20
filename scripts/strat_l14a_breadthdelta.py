"""Candidate: breadth-DELTA-shifted regime boundaries on the champion chain
(strategy_lab contract).

Mutation composing a tested mechanism (imported, never copied): the CURRENT
champion chain — strat_l13a_concwobble's composition, i.e. the tier-shape
lift (floor-lift rank among fresh prints, short-trend gate, print-continuity
gate, breadth-tier exposure) + regime-conditional book cap + gate-eligibility
wobble (gw_w 0.13 / gf_lb 12) — with the EXPOSURE leg re-timed by the
derivative of breadth instead of only its level:

    d[t]     = breadth[t] - breadth[t - bd_lb]      (0 where undefined)
    b_eff[t] = breadth[t] + bd_w * d[t]
    E[t]     = tier ladder rebuilt from b_eff (same thresholds/values)

The ladder itself is unchanged; only WHICH months fall in which band moves.

Hypothesis: participation inflections lead participation levels. A breadth
rising 0.50 -> 0.62 is a market handing risk out before the level crosses
b_hi (early full-risk entry), and a breadth falling 0.78 -> 0.66 is one
taking it back before the level breaks b_lo (early exit). The level ladder
dates every state change to the cross; the delta dates it to the move. If
the level ladder already times the book optimally, every bd_w trails the
flat base and the derivative is closed.

Why a boundary shift and not a continuous exposure scale: the champion's
tier values collapse the mid/lo bands to 0.9999, so a multiplicative
delta-scale would manufacture arbitrary exposure levels (0.7, 0.85, ...) —
the ramp flavour already falsified (strat_floorhighbreadthlin), just with a
new signal. Shifting the boundary keeps the exposure vocabulary the champion
was fitted with and tests exactly one thing: the TIMING of its states.

Falsifier: if every tested (bd_w, bd_lb) trails the flat base on train —
train +86.88% / DD -17.34% / calmar 5.01, fwd +48.19% — breadth momentum
adds nothing to breadth level on this chain.

Import chain: strat_l12b_gatefail.score (which imports
strat_floorhighfastgate + strat_floorhighsustaincond for the gate layers and
strat_floorhightiershape for rank/exposure). The conc cap step is mirrored
inline from strat_floorhightiershapeconc.score (a book-size composition
step, not an indicator) — the cap choice reads the ADJUSTED exposure so a
delta-promoted month earns cap_full and a delta-demoted one cap_weak.

Novelty: closest prior art = breadth ramps (DEAD, strat_floorhighbreadthlin)
and the level ladder itself (strat_newhigh_tier). The prior signal was the
LEVEL (a smoothed/continuous read of the same breadth); here the signal is
the DERIVATIVE (k-month change) shifting the SAME ladder's boundaries — the
inventory's OPEN axis "breadth change rather than level". The base also
changed: ramps were falsified on the Loop-10 tiershape base, this retests
the derivative on the champion chain (tier_lo/mid 0.9999 + cap_weak 11 +
wobble 0.13), where the exposure/cap boundary is the binding edge.

Off-switch identity: bd_w defaults 0.0 -> b_eff bitwise equals breadth, the
rebuilt ladder bitwise equals the imported exposure (same construction,
thresholds and strict comparisons), and the tilt layer is neutralised by
setdefaults gf_w/gw_w 0.0 BEFORE delegating (gatefail's own gf_w default
0.05 would leak) -> bitwise the champion's scores and cap at the same
params. NOTE: breadth is recomputed from px with the identical construction
strat_newhigh_tier uses — the series is not exported by any module; the
off-switch smoke IS the bitwise check of that recomputation against the
imported ladder.

Flat-base metric (off-switch must reproduce exactly): train +86.88% /
DD -17.34% / calmar 5.01, fwd +48.19% (top 15).

PIT argument: breadth reads month-end closes through px[t] only; the delta
reads b[t - bd_lb], an older row of the same series; the cap reads month-t
ranks. No forward rows, no daily panel.

SPACE = champion-chain params + bd_lb {3, 6}, bd_w {0.0, 0.5, 1.0, 2.0}.
max_hold is a harness key (params-json), not consumed here.
"""

from __future__ import annotations

import numpy as np

from strat_l12b_gatefail import score as _gf_score

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
    "gf_lb": [12],
    "gf_w": [0.0],
    "gw_w": [0.0, 0.13],
    "bd_lb": [3, 6],
    "bd_w": [0.0, 0.5, 1.0, 2.0],
}


def _breadth(px, months, ma):
    """Fraction of live names above their own ma-month average — the
    identical construction strat_newhigh_tier uses (regime_ma window)."""
    ma_px = np.full_like(px, np.nan)
    for t in range(ma - 1, len(months)):
        ma_px[t] = np.nanmean(px[t - ma + 1:t + 1], axis=0)
    with np.errstate(invalid="ignore"):
        above = (px > ma_px) & np.isfinite(px) & np.isfinite(ma_px)
        alive = np.isfinite(px)
    return np.where(alive.sum(axis=1) > 0,
                    above.sum(axis=1) / np.maximum(alive.sum(axis=1), 1),
                    np.nan)


def score(panels, params):
    p = dict(params)
    p.setdefault("gf_lb", 12)  # inert at zero weights; window guard
    p.setdefault("gf_w", 0.0)  # off-switch: delegate's own default 0.05 would leak
    p.setdefault("gw_w", 0.0)  # off-switch (champion runs pass 0.13 explicitly)
    lift, exposure = _gf_score(panels, p)

    px, months = panels["px"], panels["months"]
    ma = int(params.get("regime_ma", 18))
    b_hi = float(params.get("b_hi", 0.69))
    b_mid = float(params.get("b_mid", 0.55))
    b_lo = float(params.get("b_lo", 0.45))
    tier_mid = float(params.get("tier_mid", 0.9999))
    tier_lo = float(params.get("tier_lo", 0.9999))
    tier_floor = float(params.get("tier_floor", 0.0))
    bd_lb = max(int(params.get("bd_lb", 3)), 1)
    bd_w = float(params.get("bd_w", 0.0))

    b = _breadth(px, months, ma)
    d = np.zeros(len(months))
    for t in range(len(months)):
        prev = b[t - bd_lb] if t >= bd_lb else np.nan
        d[t] = b[t] - prev if (np.isfinite(b[t]) and np.isfinite(prev)) else 0.0

    # guard: undefined deltas read 0 so bd_w 0.0 keeps b_eff bitwise b
    b_eff = b + bd_w * d
    # same raw ladder as strat_newhigh_tier, same strict comparisons
    raw = np.where(b_eff > b_hi, 1.0,
                   np.where(b_eff > b_mid, 0.7,
                            np.where(b_eff > b_lo, 0.4, 0.0)))
    # same re-valuation as strat_floorhightiershape
    with np.errstate(invalid="ignore"):
        E = np.where(raw >= 1.0, np.minimum(raw, 1.0),
                     np.where(raw >= 0.7, tier_mid,
                              np.where(raw >= 0.4, tier_lo,
                                       np.where(raw > 0.0, tier_lo, tier_floor))))
    E = np.clip(np.asarray(E, dtype=float), 0.0, 1.0)

    cw = int(params.get("cap_weak", 11))
    cf = int(params.get("cap_full", 20))
    out = np.array(lift, dtype=float, copy=True)
    for t in range(out.shape[0]):  # cap step mirrored from strat_floorhightiershapeconc.score
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
