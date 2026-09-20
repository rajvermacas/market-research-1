"""Candidate: volatility-scaled rank tilted into the champion score
(strategy_lab contract).

Mutation composing a tested mechanism (imported, never copied): the CURRENT
champion chain (strat_l13a_concwobble's composition: tier-shape lift +
regime-conditional book cap + gate-eligibility wobble gw_w 0.13) with the
composed score re-weighted by each name's realized volatility:

    vol[t,j]   = stdev(ddof=1) of name j's last v_lb monthly returns (px)
    score[t,j] = lift[t,j] / vol[t,j]**v_w   (divisor 1 where vol unknown)

v_w interpolates the rank between the champion's raw lift (v_w 0) and the
full score-over-vol rank (v_w 1); the power form keeps one score scale — an
additive blend of score and score/vol would let the vol term dominate at any
weight because the two live on different scales.

Hypothesis: the lift rank crowns the steepest multi-year climbers, and the
champion's DD months are presumably carried by the most violent names in the
top-15 (book-level DD; position stops are dead on this family). Dividing by
realized vol tilts the cut toward smooth compounders at the same floor
distance. If the champion's gates already exclude the violent tail, the
tilt only reorders near-ties and ties the base; if smoothness carries
return per unit DD, calmar rises without paying the return away.

Applied BEFORE the cap, per the L13 lesson: the cap IS the selection in weak
months (cap_weak 11 binds there); a tilt applied after it could only re-order
the full-month 20->15 cut and would be dead in every weak month. The cap
choice then reads the vol-tilted order.

Falsifier: if every tested (v_w, v_lb) trails the flat base — train +86.88% /
DD -17.34% / calmar 5.01, fwd +48.19% — realized per-name vol carries nothing
the chain's gates and lift do not already price, and the vol axis is closed
on this base.

Import chain: strat_l12b_gatefail.score (which imports
strat_floorhighfastgate + strat_floorhighsustaincond for the gate layers and
strat_floorhightiershape for rank/exposure). The conc cap step is mirrored
inline from strat_floorhightiershapeconc.score (book-size composition step,
not an indicator).

Novelty: closest prior art = strat_volfloor (score/vol, DEAD on the Loop-10
floorlift base, vol proxied by the volsqueeze 3m coil score) and the
vol-targeting / vol-exclusion lines (DEAD: exposure scaled by INDEX vol;
quantile EXCLUSION on the old tier book). Three things changed: (1) base —
the floorlift rank never carried the champion's gates, cap or wobble;
(2) vol measure — per-name realized stdev of monthly returns computed from
the panel, not a re-used indicator score; (3) form — a continuous power
exponent (score / vol**v_w) that searches the MIX, not a hard replacement,
so the falsifier reads "no mix helps", stronger than one hard variant. This
is the inventory's OPEN axis "volatility-scaled rank (score divided by
realized vol)".

Off-switch identity: v_w defaults 0.0 and the vol loop is skipped entirely
at v_w == 0.0, so scores are bitwise the tilt-layer scores and the mirrored
cap step yields bitwise the champion at the same params. setdefaults
gf_w/gw_w to 0.0 BEFORE delegating (gatefail's own gf_w default 0.05 would
leak); gf_lb 12 is the inert window guard.

Flat-base metric (off-switch must reproduce exactly): train +86.88% /
DD -17.34% / calmar 5.01, fwd +48.19% (top 15).

PIT argument: vol[t] reads px rows up to and including month t (returns
r[i] = px[i]/px[i-1]-1 for i in [t-vlb+1, t], i.e. closes px[t-vlb..t]); no
forward rows, no daily panel. Rows with fewer than two finite returns in the
window read vol NaN -> divisor 1.0 — thin-history names keep the raw rank
(conservative: no discount on unknown vol).

SPACE = champion-chain params + v_lb {6, 12}, v_w {0.0, 0.25, 0.5, 1.0}.
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
    "v_lb": [6, 12],
    "v_w": [0.0, 0.25, 0.5, 1.0],
}


def score(panels, params):
    p = dict(params)
    p.setdefault("gf_lb", 12)  # inert at zero weights; window guard
    p.setdefault("gf_w", 0.0)  # off-switch: delegate's own default 0.05 would leak
    p.setdefault("gw_w", 0.0)  # off-switch (champion runs pass 0.13 explicitly)
    lift, exposure = _gf_score(panels, p)

    px = panels["px"]
    vlb = max(int(params.get("v_lb", 6)), 1)
    vw = float(params.get("v_w", 0.0))

    ret = np.full(px.shape, np.nan, dtype=float)
    if px.shape[0] > 1:
        ret[1:] = px[1:] / px[:-1] - 1.0

    E = np.asarray(exposure, dtype=float)
    out = np.array(lift, dtype=float, copy=True)

    if vw != 0.0:
        for t in range(out.shape[0]):
            lo = max(0, t - vlb + 1)
            w = ret[lo:t + 1]
            with np.errstate(invalid="ignore"):
                vol = np.nanstd(w, axis=0, ddof=1)
            good = np.isfinite(vol) & (vol > 0.0)
            with np.errstate(invalid="ignore"):
                pw = np.power(vol, vw)
            div = np.where(good, pw, 1.0)  # unknown vol -> divisor 1 (raw rank)
            with np.errstate(invalid="ignore", divide="ignore"):
                out[t] = out[t] / div  # NaN rows stay NaN; row/1.0 is bitwise row

    cw = int(params.get("cap_weak", 11))
    cf = int(params.get("cap_full", 20))
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
