"""Candidate: print-count rank among sustained breakouts (strategy_lab contract).

Mutation composing two tested mechanisms (imported, never copied):
eligibility and regime from strat_floorhighsustainprint (printing now +
printed within the prior sustain window, above short trend, under breadth
tiers), but the RANK is the COUNT of trailing-high prints over the lookback
window, with lift/10 breaking ties (lift rarely exceeds ~3, so one extra
print month always outranks any lift gap).

Rationale: sustainprint gates on print continuity; if print persistence is
the signal rather than structure, ranking on it directly should beat
gating on it — the most-persistent printers first, one-hit names last even
when eligible. If structure still dominates (all evidence so far), this
trails and the rank question closes for good: lift level, gated on print
timing, is the terminal form.

PIT-safe: print count uses imported proximity history through px[m] only;
the lift tiebreak is the imported level. No forward information.

SPACE = strat_floorhighsustainprint params (count rank is structural).
"""

from __future__ import annotations

import numpy as np

from strat_floorhigh import score as _fh_score
from strat_floorhighsustainprint import score as _sustain_score
from strat_newhigh import score as _high_score

NEEDS_DAILY = False
SPACE = {
    "b_hi": [0.65],
    "b_mid": [0.55],
    "b_lo": [0.45],
    "floor_lb": [19],
    "lookback": [16],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [6],
    "sustain_lb": [6],
}


def score(panels, params):
    elig, exposure = _sustain_score(panels, params)
    lift, _ = _fh_score(panels, params)
    prox, _ = _high_score(panels, params)
    lb = int(params.get("lookback", 16))
    out = np.full_like(elig, np.nan)
    with np.errstate(invalid="ignore"):
        printed = np.isfinite(prox) & (prox >= -0.001)
    for t in range(elig.shape[0]):
        lo = max(0, t - lb + 1)
        cnt = printed[lo:t + 1].sum(axis=0).astype(float)
        ok = np.isfinite(elig[t]) & np.isfinite(lift[t])
        out[t] = np.where(ok, cnt + lift[t] / 10.0, np.nan)
    return out, exposure
