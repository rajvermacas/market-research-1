"""Candidate: champion-chain book re-weighted by gate-eligibility wobble
(strategy_lab contract).

Mutation composing a tested mechanism (imported, never copied): the CURRENT
champion chain — strat_floorhightiershapeconc, i.e. the tier-shape lift of
strat_floorhightiershape (floor-lift rank among fresh prints, short-trend
gate, print-continuity gate, breadth-tier exposure) with the
regime-conditional book cap (cap_weak in scaled-risk months, cap_full in
full-risk months) — re-weighted by the Loop-12 gate-eligibility term from
strat_l12b_gatefail (its keys gf_lb, gf_w, gw_w; imported wholesale, not
copied):

    fail   = share of last gf_lb months the name FAILED a gate
             (short-trend/print, or continuity after passing the base)
    wobble = share of last gf_lb months the champion's own ELIGIBILITY
             FLIPPED (eligible where it was not the month before, or vice)
    score  = tier-shape lift * (1 - gf_w * fail - gw_w * wobble)

Hypothesis: the champion's edge is a gate-intersection book, and a name that
keeps failing or flickering across gates is a marginal qualifier whose pass
is boundary jitter, not sponsorship. Discounting such names BEFORE the cap
lets the wobble term change which names the cap keeps — necessary because
the cap IS the selection in weak months (cap_weak=11 binds there; a tilt
applied after the cap could only re-order the full-month 20->15 cut and
would be dead in every weak month).

Why re-based: Loop-12 built strat_l12b_gatefail on the OLD
strat_floorhightiershape base (no cap, no max_hold), so its surviving terms
were screened against a superseded base. This file re-tests the term against
the current champion chain so "better than base" means better than the
champion, not better than a file the champion superseded.

Falsifier: if every tested (gw_w, gf_w) combination trails the flat base —
train +85.23% / DD -17.49% / calmar 4.87, fwd +53.76% — then gate-failure
and wobble carry no information beyond what the champion chain already
consumes, and the term is closed at this base.

Import chain: strat_l13a_concwobble -> strat_l12b_gatefail.score (which
imports strat_floorhighfastgate + strat_floorhighsustaincond for the gate
layers and strat_floorhightiershape for rank/exposure). The conc cap step is
mirrored inline from strat_floorhightiershapeconc.score (a book-size
composition step, not an indicator).

Off-switch identity: defaults gf_w = 0.0 and gw_w = 0.0 make the tilt
exactly 1.0 for every name, so the tilted lift is bitwise the tier-shape
lift and the cap (mirrored exactly) yields bitwise the champion's scores at
the same params. NOTE: the delegate's own default is gf_w = 0.05 — this file
setdefaults gf_w/gw_w to 0.0 BEFORE delegating, otherwise the off-switch
would silently carry the Loop-12 discount.

Flat-base metric (off-switch must reproduce exactly): train +85.23% /
DD -17.49% / calmar 4.87, fwd +53.76%.

PIT argument: inherited unchanged from strat_l12b_gatefail — fail/wobble
read only the finite/NaN pattern of the imported layer scores in rows up to
and including month t, each itself computed from closes through px[m]; no
daily panel, no forward rows; rows before the window read 0 (no discount on
thin history). The cap reads month-t ranks only.

SPACE = champion-chain params + gf_lb {12}, gf_w {0.0, 0.05},
        gw_w {0.0, 0.09, 0.12}. max_hold is a harness key (params-json).
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
    "gf_w": [0.0, 0.05],
    "gw_w": [0.0, 0.09, 0.12],
}


def score(panels, params):
    p = dict(params)
    p.setdefault("gf_lb", 6)   # inert at weights 0; window guard from the source term
    p.setdefault("gf_w", 0.0)  # off-switch: delegate's own default 0.05 would break it
    p.setdefault("gw_w", 0.0)  # off-switch
    tilted, exposure = _gf_score(panels, p)

    cw = int(params.get("cap_weak", 11))
    cf = int(params.get("cap_full", 20))
    E = np.asarray(exposure, dtype=float)
    out = np.array(tilted, dtype=float, copy=True)
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
