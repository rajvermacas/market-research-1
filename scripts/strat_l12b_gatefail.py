"""Candidate: gate-failure-forecast score on the champion book (strategy_lab
contract).

Setup in words: the champion's eligibility is the INTERSECTION of three
imported layers — fresh print (proximity == 0), short trend (close above its
fast_ma average), print continuity (a prior print within the regime-conditioned
sustain window), all under breadth tiers. A name can be eligible today while
sitting ON the edge of any gate. This file measures, per name, how often each
gate REJECTED it over the trailing `gf_lb` months (the imported layers' own
finite/NaN history — no new signal math), and re-weights the book accordingly:

    fail  = share of last gf_lb months the name FAILED one of the gates
    wobble= share of last gf_lb months the name's ELIGIBILITY FLIPPED
            (eligible where it was not the month before, or vice versa)
    score = lift * (1 - gf_w * fail - gw_w * wobble)

Hypothesis: the champion's freshness premium (negative persistence weight)
proved that eligibility HISTORY carries information the level rank cannot see.
This is the second, untested half of the same channel: a name that has spent
the window failing a gate is a marginal qualifier whose pass may be noise, and
a name whose eligibility flickers on/off month to month sits on a threshold —
its passes are not sponsorship but boundary jitter, and the harness pays full
turnover to trade them. Persistent clean passers should compound; wobbly
marginal ones should be discounted out of the top-15 cut. If gate history is
fully captured by the existing eligibility-share premium, this ties the base
and closes the channel.

Falsifies if: both weights at any tested combination trail the flat base
(train +83.93 / DD -19.96) — then gate-failure and wobble carry no information
beyond the existing persistence term. (Smoke at gf_w 0.15 / gw_w 0 cost ~11pp
train — the discount is heavy at the face value; the SPACE starts at 0.05.)

PIT argument: both features read ONLY the finite/NaN pattern of the imported
rank and layer scores in rows up to and including month t; each such row is
itself computed from closes through px[m] by the imported legs. No daily
panel, no forward rows. Rows before the window read as fail/wobble 0
(conservative: no discount on thin history).

SPACE = champion base + gf_lb {6, 12}, gf_w {0.05, 0.15}, gw_w {0.0, 0.05}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhightiershape import score as _ts_score
from strat_floorhighfastgate import score as _fg_score
from strat_floorhighsustaincond import score as _scond_score

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
    "tier_lo": [1.0],
    "tier_mid": [1.0],
    "gf_lb": [6, 12],
    "gf_w": [0.05, 0.15],
    "gw_w": [0.0, 0.05],
}


def _share(fin: np.ndarray, lb: int) -> np.ndarray:
    """Row t: fraction of the last lb rows (ending t) that were finite.
    Rows before the window read as share 0."""
    out = np.zeros(fin.shape)
    for t in range(fin.shape[0]):
        lo = max(0, t - lb + 1)
        out[t] = fin[lo:t + 1].sum(axis=0) / (t - lo + 1)
    return out


def score(panels, params):
    lift, exposure = _ts_score(panels, params)
    fg, _ = _fg_score(panels, params)     # fresh print + short trend layers
    sc, _ = _scond_score(panels, params)  # + continuity gate on top
    glb = int(params.get("gf_lb", 6))
    gfw = float(params.get("gf_w", 0.05))
    gww = float(params.get("gw_w", 0.0))

    # layer memberships: eligible under the short-trend/print layer, and
    # additionally under the continuity gate
    base_ok = np.isfinite(fg)
    full_ok = np.isfinite(sc)
    fail = _share(~base_ok, glb)          # failed short-trend or print gate
    cont_fail = _share(base_ok & ~full_ok, glb)  # passed base, failed continuity
    fail = np.clip(fail + cont_fail, 0.0, 1.0)

    # wobble: eligibility flips in the champion's own book (either direction)
    ok = np.isfinite(lift)
    flip = np.zeros_like(ok, dtype=float)
    flip[1:] = ok[1:] != ok[:-1]
    wobble = _share(flip.astype(bool), glb)

    out = np.array(lift, dtype=float, copy=True)
    for t in range(lift.shape[0]):
        tilt = 1.0 - gfw * fail[t] - gww * wobble[t]
        out[t] = np.where(ok[t], lift[t] * tilt, np.nan)
    return out, exposure
