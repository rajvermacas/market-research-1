"""Candidate: index-drawdown veto over the conditional-sustain book
(strategy_lab contract).

Mutation composing a tested mechanism (imported, never copied): rank and
breadth tiers from strat_floorhighsustaincond, with the tier exposure
multiplied by a trend-risk veto on the equal-weight index (names alive at
test start, same construction as strat_floorlift's regime):

    dd_t   = 1 - idx[t] / max(idx[t-dd_lb+1 .. t])     (running drawdown)
    veto_t = 0.0 if dd_t > dd_stop else 1.0, floored at dd_exp

Rationale: breadth tiers cut exposure when participation thins, but the
market's own drawdown is a different, slower state variable — deep bear
phases keep breadth low for months and the tier ladder can still hold 0.4
into continued decline. An index-drawdown veto switches the book off once
the market has lost more than dd_stop from its recent peak and back on after
recovery; dd_exp > 0 tests a partial rather than full stand-down. If the
tiers already express this state, the veto ties or trails.

PIT-safe: dd_t uses the index path through month t only; the harness applies
E[t] to the return t -> t+1.

SPACE = strat_floorhighsustaincond params + dd_lb {12,24}, dd_stop {0.08,0.12,0.16},
        dd_exp {0.0,0.4}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighsustaincond import score as _sc_score

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
    "sustain_lo": [6],
    "sustain_hi": [2],
    "dd_lb": [12, 24],
    "dd_stop": [0.08, 0.12, 0.16],
    "dd_exp": [0.0, 0.4],
}


def score(panels, params):
    rank, exposure = _sc_score(panels, params)
    px, months = panels["px"], panels["months"]
    start_i = panels["start_i"]
    ddlb = int(params.get("dd_lb", 12))
    stop = float(params.get("dd_stop", 0.12))
    dexp = float(params.get("dd_exp", 0.0))

    alive = ~np.isnan(px[start_i])
    idx = np.nanmean(px[:, alive] / px[start_i, alive], axis=1)

    E = np.asarray(exposure, dtype=float).copy()
    for t in range(ddlb, len(months)):
        peak = np.nanmax(idx[t - ddlb + 1:t + 1])
        if np.isfinite(peak) and peak > 0:
            dd = 1.0 - idx[t] / peak
            if dd > stop:
                E[t] = dexp
    return rank, np.clip(E, 0.0, 1.0)
