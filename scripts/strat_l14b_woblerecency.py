"""Candidate: recency-weighted eligibility wobble on the champion chain
(strategy_lab contract).

Mutation composing a tested mechanism (imported, never copied): the CURRENT
champion chain — strat_l13a_concwobble — with the SHAPE of its LIVE wobble
term changed. The champion discounts each name by the flat flip share:

    wobble = share of the last gf_lb months the name's champion ELIGIBILITY
             FLIPPED (equal weight on every month in the window)
    score  = lift * (1 - gw_w * wobble)     [gf_w leg stays 0 — dead on this base]

This file blends that flat share with an exponentially decayed share:

    wob_decayed[t] = sum_k 0.5^(k/rec_hl) * flip[t-k] / sum_k 0.5^(k/rec_hl)
                     (k = 0..available window; normalized by the weight mass
                     of the AVAILABLE rows, mirroring the flat share's
                     available-rows denominator)
    wob_eff  = (1 - rec_w) * wobble_flat + rec_w * wob_decayed
    score    = lift * (1 - gw_w * wob_eff)

so a flip LAST month counts more than a flip a year ago; a name whose
eligibility stopped flickering is forgiven faster than the flat share
allows, and a name that STARTED flickering is discounted sooner.

Hypothesis: the wobble term's gain came from discounting marginal
qualifiers, but a flat window treats a flicker that ENDED 11 months ago like
one that happened last month. If boundary jitter is informative only while
it is recent, recency-shaping sharpens the discount without touching its
weight (gw_w stays 0.13); if the flat share's long memory was part of the
edge, every blend trails the flat base and the shape family closes.

Falsifier: if every tested (rec_w, rec_hl) combination trails the flat base —
train +86.88% / DD -17.34% / calmar 5.01, fwd +48.19% — then recency-shaping
the flip share carries no information beyond the flat share, and the
wobble term's shape family is closed at this base.

Import chain: strat_l14b_woblerecency -> strat_l12b_gatefail (score for the
tier-shape lift + exposure, with gf_w/gw_w set to 0.0 by THIS file so the
delegate applies NO discount — its own defaults gf_w 0.05 / gw_w 0.0 would
leak or mis-shape; and _share, the flat flip-share helper, imported not
copied, for the flat leg). The delegate is the imported wobble term's home;
the flip definition (ok = isfinite(lift), flip at row boundaries) is the
delegate's own, read off the delegate's returned lift. The cap step is
mirrored inline from strat_floorhightiershapeconc.score (a book-size
composition step, not an indicator), exactly as strat_l13a_concwobble does.

Off-switch identity: rec_w = 0.0 short-circuits to wob_eff = wobble_flat
(the delegate's own _share on the same flip pattern — no blend arithmetic at
all), tilt = 1 - gw_w * wobble_flat is bitwise the champion's tilt (the
dropped gf_w leg is exactly 0.0 * fail = 0.0 in the champion's arithmetic),
and the mirrored cap yields bitwise the champion's book at the same params.
NOTE the delegate is called with gw_w FORCED to 0.0 (an override, not a
setdefault — the harness passes the champion's gw_w 0.13 through params, and
a setdefault would let the delegate apply it on top of the tilt built here,
double-discounting); gw_w is read back from params for THIS file's tilt.

Flat-base metric (off-switch must reproduce exactly): train +86.88% /
DD -17.34% / calmar 5.01, fwd +48.19%.

PIT argument: inherited unchanged — flip/wobble read only the finite/NaN
pattern of the delegate's returned lift in rows up to and including month t,
each itself computed from closes through px[m]; the decay weights depend only
on LAG, not on any future row; rows before the window read the weighted share
of available history (conservative, no forward peek). No daily panel. The cap
reads month-t ranks only.

NOVELTY STATEMENT: closest prior art in the inventory — the LIVE
eligibility-wobble discount (gw_w 0.13 / gf_lb 12, strat_l13a_concwobble):
same signal (the champion's own eligibility flip pattern over gf_lb months),
and this file explicitly changes the TERM'S SHAPE, which the PARTIAL note
allows ("changing their mechanism is not [closed]") — only gw_w's local
plateau is closed to tuning, and gw_w is pinned at 0.13 here. This is NOT the
DEAD gate-failure share (gf_w): that consumed how often GATES REJECTED the
name; this file consumes no gate-rejection history at all — only the
champion's own eligibility FLIP pattern, re-weighted in time, on the live
leg. A new filename/weight on the same signal would be a replay; a time
re-weighting of the live share's shape is the change being tested.

SPACE = champion-chain params (pinned) + rec_hl {3, 6, 12},
        rec_w {0.0, 0.25, 0.5}. gf_w is fixed at 0 (dead on this base,
        Loop-13) and is NOT consumed by this file.
"""

from __future__ import annotations

import numpy as np

from strat_l12b_gatefail import score as _gf_score
from strat_l12b_gatefail import _share

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
    "gw_w": [0.13],
    "rec_hl": [3, 6, 12],
    "rec_w": [0.0, 0.25, 0.5],
}


def _share_decay(fin: np.ndarray, lb: int, hl: int) -> np.ndarray:
    """Row t: exponentially decayed share of `fin` over the last lb rows,
    half-life hl months (weight 0.5^(lag/hl)), normalized by the weight mass
    of the AVAILABLE rows. Rows before the window read the weighted share of
    available history; always finite (never NaN)."""
    out = np.zeros(fin.shape)
    for t in range(fin.shape[0]):
        lo = max(0, t - lb + 1)
        n = t - lo + 1
        w = 0.5 ** (np.arange(n - 1, -1, -1, dtype=float) / float(hl))
        out[t] = (fin[lo:t + 1] * w[:, None]).sum(axis=0) / w.sum()
    return out


def score(panels, params):
    p = dict(params)
    p.setdefault("gf_lb", 12)  # champion window (delegate default 6 would drift)
    p["gf_w"] = 0.0            # FORCED, not setdefault: params carry the champion's
    p["gw_w"] = 0.0            # gw_w 0.13, and setdefault would let the delegate
                               # apply it — double-discounting on top of the tilt
                               # built here. The delegate must return the RAW
                               # tier-shape lift; the wobble discount is rebuilt.
    lift, exposure = _gf_score(panels, p)

    glb = int(params.get("gf_lb", 12))
    gww = float(params.get("gw_w", 0.13))
    rec_w = float(params.get("rec_w", 0.0))
    rec_hl = max(1, int(params.get("rec_hl", 6)))

    # wobble: eligibility flips in the champion's own book (either direction),
    # read off the delegate's lift — same definition as strat_l12b_gatefail
    ok = np.isfinite(lift)
    flip = np.zeros_like(ok, dtype=float)
    flip[1:] = ok[1:] != ok[:-1]
    wob_flat = _share(flip.astype(bool), glb)
    if rec_w == 0.0:
        wob_eff = wob_flat  # off-switch: the delegate's own computation, bitwise
    else:
        wob_dec = _share_decay(flip.astype(bool), glb, rec_hl)
        wob_eff = (1.0 - rec_w) * wob_flat + rec_w * wob_dec

    out = np.array(lift, dtype=float, copy=True)
    E = np.asarray(exposure, dtype=float)
    for t in range(lift.shape[0]):
        tilt = 1.0 - gww * wob_eff[t]
        out[t] = np.where(ok[t], lift[t] * tilt, np.nan)
        fin = np.flatnonzero(np.isfinite(out[t]))  # cap step mirrored from
        if fin.size == 0:                          # strat_floorhightiershapeconc.score
            continue
        cap = int(params.get("cap_full", 20)) if E[t] >= 1.0 else int(params.get("cap_weak", 11))
        if fin.size <= cap:
            continue
        order = fin[np.argsort(-out[t][fin], kind="stable")]
        out[t, order[cap:]] = np.nan
    return out, E
