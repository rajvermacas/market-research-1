"""Candidate: low-volatility gate on the concentrated-shape book
(strategy_lab contract).

Mutation composing a tested mechanism (imported, never copied): rank and
shaped exposure from strat_floorhightiershapeconc, but eligible only when the
name's trailing monthly-return volatility is at or below the cross-sectional
`vol_q` quantile of the eligible names at month t.

Rationale: the concentration finding showed the binding constraint is
drawdown, not signal — the loop has repeatedly bought CAGR with exposure and
paid for it in DD. This tests the complementary lever: keep the same
exposure and roughly the same eligible set, but drop the most volatile
fresh prints from the book (they dominate the left tail). If high-vol
breakouts are where the tail winners live, this trails; if vol is mostly a
risk tax on this setup, it trims DD for little CAGR.

PIT-safe: vol_t is std of monthly returns over the `vol_lb` months ending at
month t; the quantile is cross-sectional at t. No forward bars.

SPACE = strat_floorhightiershapeconc params + vol_lb {6,12}, vol_q {0.5,0.75}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhightiershapeconc import score as _base_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [19],
    "lookback": [16],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [9],
    "sustain_lo": [4],
    "sustain_hi": [2],
    "tier_lo": [0.55],
    "tier_mid": [1.0],
    "cap_weak": [12],
    "cap_full": [20],
    "vol_lb": [6, 12],
    "vol_q": [0.5, 0.75],
}


def score(panels, params):
    rank, exposure = _base_score(panels, params)
    px, months = panels["px"], panels["months"]
    vlb = int(params.get("vol_lb", 6))
    q = float(params.get("vol_q", 0.5))

    ret = np.full_like(px, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        ret[1:] = px[1:] / px[:-1] - 1

    out = np.array(rank, dtype=float, copy=True)
    for t in range(vlb, rank.shape[0]):
        w = ret[t - vlb + 1:t + 1]
        with np.errstate(invalid="ignore"):
            vol = np.nanstd(w, axis=0, ddof=1)
        elig = np.isfinite(rank[t]) & np.isfinite(vol)
        if elig.any():
            thr = float(np.quantile(vol[elig], q))
            keep = elig & (vol <= thr)
        else:
            keep = np.zeros(rank.shape[1], bool)
        out[t] = np.where(keep, rank[t], np.nan)
    out[:vlb] = np.nan
    return out, exposure
