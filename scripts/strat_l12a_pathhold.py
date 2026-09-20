"""Candidate: path-conditional hold clock over the champion base (strategy_lab
contract).

Setup in words: rank, gates and exposure are imported wholesale from
strat_floorhighrankpersist (champion base). The hold machinery replaces the
harness's flat max_hold with a per-name clock folded into the score matrix
via the exact pick-rule replay (imported from strat_l12a_incbonus):

    the harness risk key max_hold must be 0/absent in these trials — this
    candidate implements the cap itself, per name, on the name's own path:

    cap_flat  months a name may be held with no profit to show; past it, the
              name is exited (rank set NaN for the decision month).
    win_arm   exemption threshold: once a name's peak gain since entry
              (month-end closes) has reached win_arm, it is a "winner" and
              is governed by cap_win instead — 0 means exempt while it keeps
              re-qualifying; a positive cap_win still retires it eventually.
              Peak-based arming: once earned, the exemption survives a
              later fade in gain, so the tail is ridden until the name's own
              gates (fresh print, fast-MA, max_dist) fail it anyway.

A name exited by its clock can re-enter later on a fresh qualification
(fresh clock), exactly as the harness's max_hold allows.

Hypothesis (corrected by smoke): in the uncapped champion book, flats never
survive to month 4 — measured: 1,335 held name-months; of the 157 at age >= 4
the median peak gain since entry is +131% (only 3% below +25%, 24% below
+75%). The natural churn of the gates rotates flats; the max_hold 4 clock's
DD repair comes almost entirely from force-retiring IN-PROFIT WINNERS
(verified: {"win_arm": 0.25, "cap_flat": 4, "cap_win": 0} is numerically
IDENTICAL to no cap at all — +79.01 / -22.06 both). So the live question is
the reverse of the naive framing: should ANY of the winners the 4-month
clock cuts be spared? win_arm is "how big a peak earns the exemption" —
the dial spans max_hold 4 (win_arm huge) to no cap (win_arm 0). If the
no-scale-out lesson holds at this margin, sparing the biggest winners
recovers CAGR faster than DD returns; if the clock's winner-cutting IS the
DD repair, every intermediate point is dominated by one of the two ends.
cap_win additionally tests a bounded ride: winners exempt for cap_win
months from entry, then retired even if still winning.
Falsified if: intermediate points trail BOTH the champion (+83.93/-19.96)
and the no-cap reference (+79.01/-22.06) on Calmar — then the two endpoints
bracket a dead zone and the flat clock should stay.

REJECTED ON THE WAY (smoke finding, Loop-12, kept here as the record):
entry-anchored month-end stops are structurally inert on this base. Entry
happens at a fresh print (at/next to the 10-month high), and the gate stack
(fast_ma 5 + max_dist 0.055 + fresh-print/sustain) applies to HELD names
too — a held name whose rank goes NaN is not re-picked. Measured on the
replayed champion book: among held name-months whose rank is still finite,
the minimum gain since entry is exactly 0.0 (738 name-months; share <= -1%
is 0.0%) — no still-eligible holding is ever under water. A stop_level of
-0.08 reproduced the no-op baseline to the basis point. The month-end stop
already exists inside the gates; the open exit dimension is the CLOCK, not
the price path below entry. (Breakeven lock-in binds only ~7-10 times in
139 months — kept out as too thin to matter.)

PIT: entry close is px[t0, j] with t0 = the month the name was picked by the
replayed book (known from picks at months < t; px[t0] is finite because the
harness only picks names with a finite px[t0]). Peak/gain tracking reads
closes px[t0..t], all ≤ t — decision at month-end t, no forward value.
px[t+1] is touched only for finiteness inside the replay's harness-exact
mask, never its value.

book_n must equal the harness --top (15 in this loop's trials).
max_hold MUST be 0/absent in the params-json of these trials (the candidate
owns the clock; a harness max_hold would double-apply it).

SPACE = champion base + variants:
  {"win_arm": 0.40, "cap_flat": 4, "cap_win": 0,  "max_hold": 0}  spare 8% of age>=4 holds
  {"win_arm": 0.75, "cap_flat": 4, "cap_win": 0,  "max_hold": 0}  only +75% winners spared
  {"win_arm": 0.25, "cap_flat": 4, "cap_win": 6,  "max_hold": 0}  winners ride to month 6
  {"win_arm": 0.25, "cap_flat": 4, "cap_win": 12, "max_hold": 0}  winners ride to month 12
(anchors, already known: win_arm huge = the max_hold 4 champion +83.93/-19.96;
 win_arm 0.25/cap_win 0 = the no-cap reference +79.01/-22.06.)
"""

from __future__ import annotations

import numpy as np

from strat_floorhighrankpersist import score as _rp_score
from strat_l12a_incbonus import replay_book

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
    "pers_lb": [6],
    "pers_w": [-0.16],
    "max_hold": [0],
    "book_n": [15],
    "win_arm": [0.0, 0.25, 0.40, 0.75],
    "cap_flat": [0, 4],
    "cap_win": [0, 6, 12],
}


def score(panels, params):
    rank, exposure = _rp_score(panels, params)
    px = panels["px"]
    book_n = int(params.get("book_n", 15))
    cap_flat = int(params.get("cap_flat", 0) or 0)
    cap_win = int(params.get("cap_win", 0) or 0)
    win_arm = float(params.get("win_arm", 0.0) or 0.0)
    cols = panels["cols"]
    col_idx = {s: j for j, s in enumerate(cols)}

    out = np.array(rank, dtype=float, copy=True)
    entry_px: dict[str, float] = {}
    peak_gain: dict[str, float] = {}

    def build_row(t, held):
        row = np.array(rank[t], dtype=float, copy=True)
        if cap_flat == 0 and cap_win == 0:
            return row  # no clock at all: exact no-op reference
        for sym in list(entry_px):
            if sym not in held:
                entry_px.pop(sym, None)
                peak_gain.pop(sym, None)
        for sym, t0 in held.items():
            j = col_idx.get(sym)
            if j is None or not np.isfinite(px[t, j]):
                continue
            if sym not in entry_px:
                # fresh pick: t0 = the month it was picked (first appears in
                # held entering t0 + 1); the harness only picks names with a
                # finite px[t0], so the reference exists
                if not np.isfinite(px[t0, j]) or px[t0, j] <= 0:
                    continue  # no valid entry reference; leave the name alone
                entry_px[sym] = float(px[t0, j])
                peak_gain[sym] = 0.0
            gain = float(px[t, j]) / entry_px[sym] - 1.0
            peak_gain[sym] = max(peak_gain.get(sym, 0.0), gain)
            cap = cap_win if peak_gain[sym] >= win_arm else cap_flat
            if cap > 0 and t - t0 >= cap:
                row[j] = np.nan  # force exit this decision month
                entry_px.pop(sym, None)
                peak_gain.pop(sym, None)
        out[t] = row
        return row

    replay_book(panels, exposure, book_n, 0, build_row)
    return out, exposure
