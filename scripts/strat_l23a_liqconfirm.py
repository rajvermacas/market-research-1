"""Candidate: liquid-breadth tiers that must be CONFIRMED by whole-board breadth (Loop-23 A).

Setup in words: rank and eligibility exactly as strat_floorhighfresh (imported,
never copied). The exposure regime is computed twice with the same
strat_newhigh_tier shape (share of names above their regime_ma-month average ->
1.0/0.7/0.4/0.0 at b_hi/b_mid/b_lo):
  * board tier  = the champion's own exposure (whole universe);
  * liquid tier = breadth over names whose median daily traded value over the
    last lq_days sessions (date < months[t]) is >= lq_min INR
    (strat_l22b_liqbreadth.liquid_mask, imported), with thresholds shifted UP
    by lq_shift (stricter).
lq_mode picks the combination:
  "min"    -> exposure = min(board, liquid)   (both must agree: second confirmation)
  "strict" -> exposure = liquid tier only, with the stricter shifted thresholds
  "upconf" -> liquid tier may RAISE exposure above board only if liquid breadth
              clears b_hi + lq_shift; otherwise exposure = min(board, liquid)
Monthly decision row t uses closes through px[t] and daily bars date < months[t].

Hypothesis: L22-B's liquid breadth added CAGR but paid ~6pp DD via higher
exposure; requiring confirmation (or stricter liquid tiers) keeps the useful
de-risking months and drops the exposure creep, beating base on CAGR and DD.
Falsifier: every variant either loses train CAGR vs base or widens DD.

Novelty: strat_l22b_liqbreadth (PARTIAL) measured liquid breadth as a
replacement regime; strat_floorhightierdual / tieror (DEAD, legacy exec, breadth
regime variants) combined two WHOLE-board breadth measures. No row combines a
liquid-population breadth with the whole-board breadth as a confirmation, nor
shifts liquid thresholds. Changed base: realistic execution + fresh champion.

Keys: lq_min (INR; 0 = off-switch -> champion exactly), lq_days (40),
lq_shift (0.0), lq_mode ("min"); lq_shift_hi / lq_shift_lo optionally override
the shift of the top / bottom threshold only (default = lq_shift), to separate
"stricter to go full" from "cut earlier".
SPACE variants: min 5e6/40; min 2e7/60; strict 5e6/40 shift 0.05; strict 2e7/60
shift 0.05; upconf 5e6/40 shift 0.05.
"""

from __future__ import annotations

import numpy as np

from strat_floorhighfresh import score as _base
from strat_l22b_liqbreadth import liquid_mask, tier

NEEDS_DAILY = True
SPACE = {"lq_min": [0, 5e6, 2e7], "lq_days": [40, 60], "lq_shift": [0.0, 0.05, 0.1],
         "lq_mode": ["min", "strict", "upconf"]}


def liquid_breadth(panels, params):
    liq = liquid_mask(panels, float(params["lq_min"]), int(params.get("lq_days", 40)))
    px, months = panels["px"], panels["months"]
    ma = int(params.get("regime_ma", 5))
    ma_px = np.full_like(px, np.nan)
    for t in range(ma - 1, len(months)):
        ma_px[t] = np.nanmean(px[t - ma + 1:t + 1], axis=0)
    with np.errstate(invalid="ignore"):
        alive = np.isfinite(px) & np.isfinite(ma_px) & liq
        above = alive & (px > ma_px)
    n = alive.sum(axis=1)
    return np.where(n >= 20, above.sum(axis=1) / np.maximum(n, 1), np.nan)


def score(panels, params):
    scores, exposure = _base(panels, params)
    if float(params.get("lq_min", 0)) <= 0:
        return scores, exposure
    b = liquid_breadth(panels, params)
    sh = float(params.get("lq_shift", 0.0))
    hi, mid, lo = (float(params.get("b_hi", 0.55)), float(params.get("b_mid", 0.45)),
                   float(params.get("b_lo", 0.35)))
    mode = params.get("lq_mode", "min")
    sh_hi = float(params.get("lq_shift_hi", sh))  # asymmetric variants; default = lq_shift
    sh_lo = float(params.get("lq_shift_lo", sh))
    board = np.asarray(exposure, dtype=float)
    out = board.copy()
    for t in range(len(out)):
        if not np.isfinite(b[t]):
            continue
        lt = tier(b[t], hi + sh_hi, mid + sh, lo + sh_lo)
        if mode == "strict":
            out[t] = lt
        elif mode == "upconf":
            lt0 = tier(b[t], hi, mid, lo)
            out[t] = max(board[t], 1.0) if b[t] > hi + sh else min(board[t], lt0)
        else:
            out[t] = min(board[t], lt)
    return scores, out
