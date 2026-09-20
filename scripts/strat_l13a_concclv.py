"""Candidate: champion-chain book re-ranked by close-location tilt
(strategy_lab contract).

Mutation composing a tested mechanism (imported, never copied): the CURRENT
champion chain — strat_floorhightiershapeconc, i.e. the tier-shape lift of
strat_floorhightiershape (floor-lift rank among fresh prints, short-trend
gate, print-continuity gate, breadth-tier exposure) with the
regime-conditional book cap (cap_weak / cap_full) — re-weighted by the
Loop-12 close-location term from strat_l12b_printclose (its keys clv_lb,
clv_scale; the CLV helper is imported, not copied):

    clv  = mean over print-month daily bars of (close - low) / (high - low),
           averaged over clv_lb buckets ending at the print month, in [0, 1]
    score = tier-shape lift * (clv_scale + (1 - clv_scale) * clv)

Hypothesis: the champion buys fresh prints on a short trend under a
continuity gate; whether the print month CLOSED near its highs (demand
persisting to the bell) or near its lows (distribution into the breakout)
is daily-tape confirmation the monthly panel cannot see. A high print that
closes at its lows should be discounted; one that closes at its highs is
the stronger entry. Applied BEFORE the cap, the tilt changes which names
the cap keeps — necessary because the cap IS the selection in weak months
(cap_weak=11 binds there; a tilt after the cap could only re-order the
full-month 20->15 cut).

Why re-based: Loop-12 built strat_l12b_printclose on
strat_floorhighrankpersist — tier-shape PLUS the freshness premium
(pers_w=-0.16) the current champion chain does NOT carry — so its term was
screened against a superseded base. This file re-tests the tilt against the
current champion so "better than base" means better than the champion.

Falsifier: if every tested (clv_lb, clv_scale) combination trails the flat
base — train +85.23% / DD -17.49% / calmar 4.87, fwd +53.76% — then the
close location of the print month carries no marginal information at this
base and the daily-close channel is closed.

Import chain: strat_l13a_concclv -> strat_l12b_printclose._monthly_clv
(daily-tape helper only; its score() is NOT imported because it carries the
freshness premium) -> strat_floorhightiershape.score for rank/exposure. The
conc cap step is mirrored inline from strat_floorhightiershapeconc.score
(a book-size composition step, not an indicator).

Off-switch identity: clv_scale = 1.0 (the source file's own no-op
convention) makes the tilt exactly 1.0 for every name — finite CLV reads
1.0 + 0.0 * clv = 1.0, NaN CLV reads 1.0 — so the tilted lift is bitwise
the tier-shape lift and the cap yields bitwise the champion's scores. This
file's default is clv_scale = 1.0 for exactly that reason (the source
file's default 0.8 would break the off-switch).

Flat-base metric (off-switch must reproduce exactly): train +85.23% /
DD -17.49% / calmar 4.87, fwd +53.76%.

PIT argument: inherited from strat_l12b_printclose — for score row t
(holding month starting months[t]) the print month is calendar month
months[t-1]; CLV is computed ONLY from daily bars with date in
[months[lo], months[t]) — strictly before the holding month opens, never
peeks. Row 0 has no prior month: it keeps the imported lift un-tilted
(deliberately NOT the source file's out[0] = NaN, which would discard a
row the champion keeps). NaN CLV (no bars / zero range) keeps eligibility
with tilt 1.0 — never drops on missing data.

SPACE = champion-chain params + clv_lb {5, 4}, clv_scale {1.0, 0.67, 0.60,
0.65}. max_hold is a harness key (params-json).
"""

from __future__ import annotations

import numpy as np

from strat_l12b_printclose import _monthly_clv
from strat_floorhightiershape import score as _ts_score

NEEDS_DAILY = True
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
    "clv_lb": [5, 4],
    "clv_scale": [1.0, 0.67, 0.60, 0.65],
}


def score(panels, params):
    rank, exposure = _ts_score(panels, params)
    daily, months, cols = panels["daily"], panels["months"], panels["cols"]
    clb = int(params.get("clv_lb", 1))
    cscale = float(params.get("clv_scale", 1.0))  # off-switch = champion

    clv = _monthly_clv(daily, months, cols)
    out = np.array(rank, dtype=float, copy=True)
    for t in range(1, rank.shape[0]):
        pm = t - 1  # print-month bucket = calendar month before the hold month
        lo = pm - clb + 1
        if lo < 0:
            continue
        with np.errstate(invalid="ignore"):
            c = np.nanmean(clv[lo:pm + 1], axis=0)
        # tilt in (cscale, 1.0]; NaN clv -> tilt 1.0 (lift unmodified)
        tilt = np.where(np.isfinite(c), cscale + (1.0 - cscale) * c, 1.0)
        ok = np.isfinite(rank[t])
        out[t] = np.where(ok, rank[t] * tilt, np.nan)

    cw = int(params.get("cap_weak", 11))
    cf = int(params.get("cap_full", 20))
    E = np.asarray(exposure, dtype=float)
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
