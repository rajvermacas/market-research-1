"""Candidate: shaped freshness-drought premium on the champion book
(strategy_lab contract).

Setup in words: keep the champion's rank, eligibility gates and tier exposure
untouched (strat_floorhightiershape legs via strat_floorhighrankpersist) and
replace only the freshness term. The champion carries a LINEAR drought
premium: score = rank * (1 + pers_w * share_of_recent_months_eligible) with
pers_lb 6 / pers_w -0.16 — a constant per-month discount for every eligible
month in the window, and it is the biggest single lever found (freshness >
book caps > tiers). This file generalises the SHAPE of that term to make the
discount steepen with age — two shapes over the same eligibility-share input
(share = fraction of the last `drought_lb` months the name was eligible,
imported from the champion's own rank history):

  shape "sqrt":  tilt = 1 - d_w * sqrt(share)
  shape "step":  tilt = 1 - d_w  if share >= s_hi, else 1 - d_w/2 if
                 share >= s_lo, else 1.0

Hypothesis: the linear premium worked, which proves freshness carries
information — but not that a straight line is the right functional form. The
champion's own ledger hints the marginal month is not constant: at pers_lb 12
the DD sat at -22.06% for EVERY weight (window, not weight), while pers_lb 6
produced an inside-DD plateau — the effect is concentrated, not diffuse. If
staleness bites non-linearly (a name eligible 5-of-6 months is far staler than
one eligible 2-of-6, worth much more than the linear gap), a concave or
threshold shape should extract more from the same channel. If the linear form
was already right, every shape here ties or trails and the line stands.

Falsifies if: neither shape beats the linear champion (train +83.93 / DD
-19.96) — then the freshness channel is exhausted at this base in BOTH
directions and further shape work is dead.

PIT argument: the eligibility share uses only the imported rank's own finite/
NaN pattern in rows up to and including month t — each row of which is
computed by the champion from closes through px[m] only. No forward rows are
read; no daily panel is needed.

SPACE = champion base + drought_lb {6, 12}, drought_w {0.15, 0.3},
        drought_shape {"sqrt", "step"}, s_lo {0.3}, s_hi {0.7}.
"""

from __future__ import annotations

import numpy as np

from strat_floorhightiershape import score as _ts_score

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
    "drought_lb": [6, 12],
    "drought_w": [0.15, 0.3],
    "drought_shape": ["sqrt", "step"],
    "s_lo": [0.3],
    "s_hi": [0.7],
}


def score(panels, params):
    rank, exposure = _ts_score(panels, params)
    dlb = int(params.get("drought_lb", 6))
    dw = float(params.get("drought_w", 0.15))
    shape = str(params.get("drought_shape", "sqrt"))
    s_lo = float(params.get("s_lo", 0.3))
    s_hi = float(params.get("s_hi", 0.7))
    fin = np.isfinite(rank)

    out = np.array(rank, dtype=float, copy=True)
    for t in range(rank.shape[0]):
        lo = max(0, t - dlb + 1)
        n = t - lo + 1
        share = fin[lo:t + 1].sum(axis=0) / n
        if shape == "sqrt":
            tilt = 1.0 - dw * np.sqrt(share)
        else:  # step
            tilt = np.where(share >= s_hi, 1.0 - dw,
                            np.where(share >= s_lo, 1.0 - dw / 2.0, 1.0))
        out[t] = rank[t] * tilt
    out = np.where(fin, out, np.nan)
    return out, exposure
