"""Candidate: champion book tilted by market-relative strength (strategy_lab
contract).

Mutation composing a tested mechanism (imported, never copied): the CURRENT
champion chain — strat_l13a_concwobble, i.e. the tier-shape lift discounted by
the eligibility wobble (gw_w 0.13 over the gf_lb 12 flip share) — with each
name's score multiplied by a market-relative strength tilt applied BEFORE the
regime-conditional cap:

    rs[t,j]    = px[t,j] / px[t-rs_lb,j] - 1          (k-month month-end return)
    rs_mean[t] = equal-weight mean of rs over every panel name with a finite
                 k-month return at month t   (the panel's OWN mean — no index
                 series is fetched or constructed, nothing leaves the panel)
    rsdiff     = rs - rs_mean                          (NaN where rs undefined)
    score      = champion_score * (1 + rs_w * rsdiff)  (tilt 1.0 where rs
                 undefined — no tilt on thin history)

Hypothesis: the champion ranks on a purely self-referential breakout (own
fresh high, own trend gates). A name can pass all of those while badly
LAGGING the panel mean — a laggard breakout the whole tape is leaving behind.
Subtracting the panel's own equal-weight k-month mean at the same PIT moment
re-expresses each candidate's momentum in market-relative units; a positive
tilt (rs_w > 0) then pushes names OUTPERFORMING the average cohort up the
rank and laggards down, while the existing gates keep deciding eligibility.
If market-relative strength carries information the self-referential rank
does not, the tilt improves which names the weak-month cap keeps (the cap IS
the selection there); if the gates already price relative strength, every
variant ties or trails and the axis closes.

Falsifier: if every tested (rs_w, rs_lb) combination trails the flat base —
train +86.88% / DD -17.34% / calmar 5.01, fwd +48.19% — then market-relative
strength carries no information beyond what the champion chain already
consumes, and this OPEN axis is closed at this base.

Import chain: strat_l14b_relstrength -> strat_l12b_gatefail.score (which
imports strat_floorhighfastgate + strat_floorhighsustaincond for the gate
layers and strat_floorhightiershape for rank/exposure, and applies the
champion's own wobble discount — gf_w set to 0.0 by THIS file because its
default 0.05 would leak, gw_w passed through at the champion value). The
relative-strength term is new math; the cap step is mirrored inline from
strat_floorhightiershapeconc.score (a book-size composition step, not an
indicator), exactly as strat_l13a_concwobble does.

Off-switch identity: rs_w = 0.0 makes the tilt exactly 1.0 for every name
(1.0 + 0.0 * finite, and 1.0 where rsdiff is NaN), so the tilted score is
bitwise the delegate's champion score and the mirrored cap yields bitwise the
champion's book at the same params. NOTE the delegate is called with
gw_w defaulting to 0.13 (champion value, passes through when params carry it)
and gf_w FORCED to 0.0 (an override, not a setdefault — the delegate's own
default 0.05 would leak; the gate-failure leg is dead on this base).

Flat-base metric (off-switch must reproduce exactly): train +86.88% /
DD -17.34% / calmar 5.01, fwd +48.19%.

PIT argument: rs reads only month-end closes through px[t] (rows t and
t-rs_lb, both already past at decision time); rs_mean is a same-row
cross-sectional mean. No daily panel, no forward rows; names with undefined
rs read tilt 1.0 (conservative: no tilt on thin history). The cap reads
month-t ranks only.

NOVELTY STATEMENT: closest prior art in the inventory — (a) the LIVE
fresh-print rank (proximity to own high): a TIME-SERIES breakout, purely
self-referential; (b) the DEAD sector/industry-neutrality line: it grouped
this same cross-section by an attribute and died on 80%-null `industry`
coverage, not on the concept of market-relative comparison; (c)
strat_momentum: ranks on RAW cross-sectional k-month return as a standalone
book. The one thing changed: the signal is each name's return MINUS the
equal-weight panel mean at the same PIT moment (market-relative, no index
series, no industry attribute needed), applied as a multiplicative tilt
inside the champion book rather than a standalone rank. This is the OPEN
axis "relative strength vs the panel's own mean" from the inventory — the
DEAD freshness/eligibility family consumes a name's own print/drought
history, a different signal entirely.

SPACE = champion-chain params (pinned) + rs_lb {6, 12}, rs_w {0.0, 0.2, 0.5}.
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
    "gw_w": [0.13],
    "rs_lb": [6, 12],
    "rs_w": [0.0, 0.2, 0.5],
}


def _rsdiff(px: np.ndarray, lb: int) -> np.ndarray:
    """Row t: each name's k-month return minus the panel's own equal-weight
    mean k-month return at t. NaN where the return is undefined; an empty
    cross-section reads NaN (tilt 1.0 downstream)."""
    out = np.full(px.shape, np.nan)
    for t in range(px.shape[0]):
        if t < lb:
            continue
        base, cur = px[t - lb], px[t]
        ok = np.isfinite(base) & np.isfinite(cur) & (base > 0)
        rs = np.full(px.shape[1], np.nan)
        with np.errstate(invalid="ignore", divide="ignore"):
            rs[ok] = cur[ok] / base[ok] - 1.0
        vals = rs[np.isfinite(rs)]
        if vals.size == 0:
            continue
        out[t] = rs - vals.mean()
    return out


def score(panels, params):
    p = dict(params)
    p.setdefault("gf_lb", 12)   # champion window (delegate default 6 would drift)
    p.setdefault("gw_w", 0.13)  # champion wobble discount (delegate default 0.0)
    p["gf_w"] = 0.0             # FORCED, not setdefault: delegate's own default 0.05
                                # would leak, and this base keeps the gate-failure
                                # leg off (dead on this base, Loop-13). The
                                # champion's wobble discount passes through gw_w.
    tilted, exposure = _gf_score(panels, p)

    px = panels["px"]
    rs_lb = int(params.get("rs_lb", 6))
    rs_w = float(params.get("rs_w", 0.0))

    r = _rsdiff(px, rs_lb) if rs_w != 0.0 else None

    out = np.array(tilted, dtype=float, copy=True)
    for t in range(out.shape[0]):  # cap step mirrored from strat_floorhightiershapeconc.score
        if r is not None:
            tilt = 1.0 + rs_w * r[t]
            tilt = np.where(np.isfinite(r[t]), tilt, 1.0)
            o = np.isfinite(out[t])
            out[t] = np.where(o, out[t] * tilt, np.nan)
        E = float(np.asarray(exposure, dtype=float)[t])
        fin = np.flatnonzero(np.isfinite(out[t]))
        if fin.size == 0:
            continue
        cap = int(params.get("cap_full", 20)) if E >= 1.0 else int(params.get("cap_weak", 11))
        if fin.size <= cap:
            continue
        order = fin[np.argsort(-out[t][fin], kind="stable")]
        out[t, order[cap:]] = np.nan
    return out, exposure
