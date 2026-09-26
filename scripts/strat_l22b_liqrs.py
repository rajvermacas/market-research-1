"""Candidate: floorhighfresh with a liquid-subset relative-strength tilt (Loop-22 B).

Setup in words: eligibility, rank and exposure from strat_floorhighfresh
(imported). Additionally, a name's `rs_lb`-month return is converted to a
percentile AMONG LIQUID NAMES ONLY (liquidity mask from strat_l22b_liqbreadth:
median daily traded value over the last liq_days sessions >= liq_min).
Illiquid names are dropped (NaN) and the score becomes
base_pct + rs_w * rs_pct, both cross-sectional percentiles within the liquid
eligible set. The board-wide ranks the base uses are dominated by
untradeable small caps; this measures strength against what can be bought.

PIT: decision row t uses closes through px[t] (return px[t]/px[t-rs_lb]) and
daily bars with date < months[t] (conservative).

Hypothesis: preferring liquid RS leaders among fresh-print names raises
realised (fillable) returns and cuts blocked-tv entries.
Falsifier: variants fail to beat base train CAGR at equal-or-better DD, or
forward falls below base.

Novelty: closest registry rows are strat_floorhighliq / liqw (liquidity as a
gate/weight on board-wide ranks, DEAD, legacy exec) and the momentum-tilt
family; none computes the RS percentile within a liquid-only population.

Keys: rs_w (0 = off-switch -> base untouched), rs_lb (default 6),
liq_min (default 5e6), liq_days (default 40).
SPACE variants: rs_w 0.5/rs_lb 6/liq 5e6; rs_w 1.0/rs_lb 12/liq 2e7.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfresh import score as _base
from strat_l22b_liqbreadth import liquid_mask

NEEDS_DAILY = True
SPACE = {"rs_w": [0, 0.5, 1.0], "rs_lb": [6, 12], "liq_min": [5e6, 2e7], "liq_days": [40]}


def _pct(row: np.ndarray) -> np.ndarray:
    out = np.full_like(row, np.nan)
    m = np.isfinite(row)
    if m.sum() > 1:
        r = row[m].argsort().argsort()
        out[m] = r / (m.sum() - 1)
    elif m.sum() == 1:
        out[m] = 1.0
    return out


def score(panels, params):
    scores, exposure = _base(panels, params)
    rs_w = float(params.get("rs_w", 0))
    if rs_w == 0:
        return scores, exposure
    lb = int(params.get("rs_lb", 6))
    liq = liquid_mask(panels, float(params.get("liq_min", 5e6)),
                      int(params.get("liq_days", 40)))
    px = panels["px"]
    out = np.full_like(scores, np.nan)
    for t in range(lb, len(px)):
        with np.errstate(invalid="ignore", divide="ignore"):
            ret = px[t] / px[t - lb] - 1.0
        ret = np.where(liq[t] & np.isfinite(ret), ret, np.nan)
        rs = _pct(ret)
        base = np.where(liq[t], scores[t], np.nan)
        elig = np.isfinite(base)
        bp = _pct(base)
        out[t] = np.where(elig, bp + rs_w * np.nan_to_num(rs, nan=0.0), np.nan)
    return out, exposure
