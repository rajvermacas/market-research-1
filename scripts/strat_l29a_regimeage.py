"""Candidate: REGIME AGE (months since the exposure tier last changed) as a clock on the L25 champion (Loop-29 A).

Setup in words: rank, eligibility, book policy and base exposure are exactly the
L25 champion strat_l23a_liqconfirm (imported, never copied). age[t] = number of
consecutive month-ends, ending at t, on which the champion's exposure equals
exposure[t] (1 = the tier just changed). It depends only on exposure[0..t],
which is itself point-in-time (closes through px[t], daily bars date <
months[t]).
ra_mode:
  "fullcap" -> if exposure[t] == 1.0 and age[t] >= ra_age: exposure = 1 - ra_cut
               (a late-bull de-risking clock: a full regime that has run
               ra_age months is trimmed)
  "partrearm" -> if 0 < exposure[t] < 1 and age[t] >= ra_age: exposure = 1.0
               (a partial tier that has persisted ra_age months without
               deteriorating to cash is treated as a base, not a top)

Hypothesis: the champion's train DD comes after long full-exposure stretches
(late 2017 -> 2018); a clock trims them without needing a price trigger.
Falsifier: fullcap loses train CAGR for any DD gain (bull markets are long),
or gains rest on <= 3 firings.

Novelty: closest rows are the calendar-regime and hold-clock families
(strat_floorhightierhold, strat_l12a_pathhold: holding-duration clocks on
NAMES; calendar regimes: fixed months) and the re-arm family (l27o_corerearm,
l28o_upvolnz: price/breadth triggers). The one thing that changed: the trigger
is the AGE of the book-level exposure regime itself - no price, breadth or
calendar input. Base: L25 champion.

Off-switch: ra_age = 0 -> champion exactly.
SPACE: ra_age {6,9,12,18,24}, ra_cut {.3,.6}, ra_mode {fullcap, partrearm}.
Diagnostic: prints TRAIN-window (2015-01..2021-12) firing months to stderr.
"""

from __future__ import annotations

import numpy as np

from strat_l23a_liqconfirm import score as _champ
from strat_l29a_breadthspread import report_firings

NEEDS_DAILY = True
SPACE = {"ra_age": [0, 6, 9, 12, 18, 24], "ra_cut": [0.3, 0.6],
         "ra_mode": ["fullcap", "partrearm"]}


def score(panels, params):
    res = _champ(panels, params)
    scores, exposure = res[0], res[1]
    A = int(params.get("ra_age", 0))
    if A <= 0:
        return res
    cut = float(params.get("ra_cut", 0.3))
    mode = params.get("ra_mode", "fullcap")
    base = np.asarray(exposure, dtype=float)
    out = base.copy()
    age = 0
    for t in range(len(base)):
        age = age + 1 if t > 0 and abs(base[t] - base[t - 1]) < 1e-12 else 1
        if mode == "fullcap" and base[t] >= 1.0 and age >= A:
            out[t] = 1.0 - cut
        elif mode == "partrearm" and 0.0 < base[t] < 1.0 and age >= A:
            out[t] = 1.0
    report_firings(panels["months"], base, out, "L29A-ra")
    return (scores, out) + tuple(res[2:])
