"""Candidate: EXIT MEMORY — names whose exit from the book happened last
month get a small rank bonus or penalty (strategy_lab contract; Loop-21
designer C, axis = book-state CHURN; round-2 file).

Setup in words: the CURRENT champion chain strat_l20b_spread (gatefail lift
-> ids tilt -> cap -> listing-age tilt -> outrank tilt -> Corwin-Schultz
spread tilt, top 15, nse_all, cost 25bps, split 2022-01-01, max_hold 3) is
composed VERBATIM via `from strat_l20b_spread import score as _l20`. On top of
its returned scores this file applies ONE book-state rule which depends on
the HELD BOOK's recent past, so score() replays the harness pick rule month
by month inside replay_book (imported from strat_l21c_lockout — single
source, the same line-for-line mirror of strategy_lab.backtest_scores'
selection walk) with an on_exit hook that records every name-level exit, and
folds the tilt in BEFORE each pick:

    an EXIT is any departure from the book at a decision month where a
    selection actually happened (exposure > 0 and a non-empty pick): being
    out-scored past the cut, the cap truncating it, a gate failure, or the
    max_hold 3 clock forcing it out. Cash months select nothing and record no
    name-level exits (they empty the book by regime, not by selection — the
    same stipulation strat_l21c_lockout makes).
    at decision month t, every symbol whose most recent exit t0 satisfies
    1 <= t - t0 <= em_lb gets its row multiplied by (1 + em_w):

        row[sym] *= 1 + em_w        (|em_w| < 1, NaN stays NaN)

    em_lb 1 = "exited last month" exactly as the brief specifies: the tilt
    fires once, on the very next decision, then the memory lapses. A name
    that re-enters and later exits again is re-remembered from its newest
    exit. Tilted names are never barred — this is a WEIGHT, not a gate: an
    exited name can still win its slot on score alone.

Both signs are first-class, as the brief requires:
  em_w > 0  REWARD last month's exits — second chance: the exit was rank
            noise, buy the name straight back (anti-churn, mean-reversion
            at the entry boundary; raises turnover and costs deliberately).
  em_w < 0  PENALISE last month's exits — confirm the exit: the name must
            out-rank the field by the penalty to return at once (a SOFT,
            one-month, magnitude-scaled cousin of strat_l21c_lockout's hard
            re-entry bar: a bar forbids, a penalty re-ranks — the exit name
            can still win on score).

PIT argument: the only state the tilt reads is book state produced by picks
at decision months < t (the replay is causal: month t's exit memory is fully
determined before month t's pick) plus the champion's own score rows, which
read closes through px[t] and daily bars strictly before months[t] (delegate
chain guarantee). Exit months are decision counters, not prices. The
replay's availability mask reads isfinite(px[t+1]) — the existence of next
month's close, never its value — exactly as the harness's own pick rule
does. No row > t is ever read.

Causal-replay argument: "exited last month" is undefined without
reconstructing the held book, so score() runs replay_book twice: once over
the pristine champion rows (the champion book, for diagnostics) and once over
the rows it is modifying, with exits recorded and the tilt folded in before
each pick. Induction: both walks start from an empty book; if the books
entering month t agree, both apply the same rule to the same row at t, so
the picks agree, the exits recorded at t agree, and the books entering t+1
agree — the harness's book on the RETURNED rows therefore equals the
replayed book, and the tilt the harness sees is exactly the one computed
here. The mirror is validated END-TO-END by .cache/l21dC_replay_check.py:
picks re-derived from a candidate's RETURNED rows, fed through a copy of
backtest_scores' equity step, reproduce the harness's printed metrics for
the off-switch identity (train +102.990 / -15.506 / 6.642) and for an
active lockout cell. (trail_k is not replicated: no trial here sets it —
same stipulation as strat_l12a_incbonus.replay_book.)

NOVELTY STATEMENT (closest registry rows -> the ONE thing changed):
- research/tested_mechanisms.tsv line 84 strat_l12a_incbonus (retention
  bonus / grandfathered exit, DEAD): its grandfather memory stored a name's
  last rank WHILE STILL HELD, to soften an exit from inside the book; this
  file keeps memory AFTER the exit, on names that are OUT, and tilts their
  re-entry — the mirror side of that mechanism.
- research/tested_mechanisms.tsv line 102 strat_l15a_pickband (rank-space
  replacement band, DEAD) and line 115 strat_l16b_hurdle (replacement
  hurdle, KEEP-not-promoted, one firing), line 103 strat_l15a_repbudget
  (replacement budget, DEAD): all three condition WHO may replace a leaver,
  from outside the leaver's own history. Exit memory conditions the leaver's
  own next chance on the fact and recency of its leaving.
- WHAT CHANGED — the ONE thing: a rank weight conditioned on recent-EXIT
  status (post-exit memory at the entry boundary), both signs, a signal no
  registry row contains; plus the BASE, the L20 champion chain
  strat_l20b_spread (train +102.990 / -15.506 / 6.642), which none of the
  rows above ever saw (they died on rankpersist / conc / ids chains). The
  negative arm is related to strat_l21c_lockout (same churn axis, soft
  one-month penalty vs hard K-month bar — declared as one family's two
  dosages, not two independent discoveries).

Hypothesis: the memoryless harness re-picks every month, so a name's exit
carries information the next decision cannot see — either the exit was
over-reaction to one month of rank wiggle (reward it back in: fewer missed
winners, at the price of a round trip's costs), or it was the market telling
us something (confirm it: keep the field's newest rejects out for a month,
which is churn reduction without the lockout's hard floor).

Falsifier: the exit-memory axis CLOSES on this base if all four cells trail
the flat base on train CAGR with no offsetting drawdown or forward
improvement (the harness keep rule never fires on the smoke ledger), and per
the Loop-17 rule a train gain bought with wider drawdown or a forward
collapse is an ARTIFACT, not an upgrade. It closes as a MECHANISM — whatever
the numbers — if the L21C-DIAG line shows the footprint is a handful of
decision months (diff <= ~10 of 139: a gain sourced from a handful of
name-months is a sample of a handful — Loop-16), or every differing month is
an already-capped weak month (diff == diff_capped, diff_full == 0,
meanbook_cand < meanbook_base and/or newempty > 0) — a rule that only thins
the 11-name weak-month book is exposure withdrawal, not memory. If the
negative arm merely reproduces strat_l21c_lockout's verdict, that is one
family's dosage curve, recorded as such.

Flat-base metric (off-switch must reproduce bit-exactly): train +102.990% /
DD -15.506% / ret-DD 6.642 / H1 +100.204 / H2 +105.682 / fwd +54.057% /
fwd DD -10.381% / full +82.001% / full DD -20.728%.

Keys consumed: em_w (tilt weight, both signs), em_lb (memory window in
decisions, pinned 1 = "exited last month"), book_n (replay book size — MUST
equal the harness --top, 15 in every smoke trial), max_hold (the replay must
mirror the harness risk clock, 3, read from params the way the harness reads
it). Everything else in params-json — the full champion key set — flows
through to the delegate and is PASSED, never defaulted here. Off-switch:
em_w = 0.0. A wider memory (em_lb > 1) is deliberately OUT of this round's
SPACE: the brief's mechanism is one month.

SPACE (4 documented variants + off-switch, all on the pinned champion keys):
    em_w 0.0    off-switch identity (reproduces the flat base exactly)
    em_lb 1 x em_w {+0.05, -0.05, +0.1, -0.1} = 4 cells
        (+ = reward last month's exits / buy back; - = penalise them /
         confirm the exit; dose doubled in the outer pair)
book_n pinned 15 (= --top).
"""

from __future__ import annotations

import numpy as np

from strat_l20b_spread import score as _l20
from strat_l21c_lockout import replay_book, format_diag

NEEDS_DAILY = True  # the delegate chain's ids/spread terms read the daily panel

SPACE = {
    # champion keys (pinned, docs only; all PASSED through to the delegate)
    "b_hi": [0.69],
    "b_lo": [0.45],
    "b_mid": [0.55],
    "floor_lb": [19],
    "lookback": [12],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [5],
    "sustain_lo": [3],
    "sustain_hi": [2],
    "tier_lo": [0.9999],
    "tier_mid": [0.9999],
    "cap_weak": [11],
    "cap_full": [20],
    "gf_lb": [12],
    "gf_w": [0.0],
    "gw_w": [0.15],
    "ids_lb": [3],
    "ids_w": [-0.13],
    "la_min": [0],
    "la_w": [0.5],
    "or_lb": [6],
    "or_w": [-0.1],
    "sp_lb": [4],
    "sp_w": [-0.05],
    "sp_frac": [0.5],
    "max_hold": [3],
    # this file's keys
    "book_n": [15],
    "em_lb": [1],
    "em_w": [0.0, 0.05, -0.05, 0.1, -0.1],
}


def score(panels, params):
    p = dict(params)  # neutral defaults for THIS file's keys, then delegate
    p.setdefault("em_w", 0.0)
    p.setdefault("em_lb", 1)
    p.setdefault("book_n", 15)
    base_scores, regime = _l20(panels, p)  # current champion chain, verbatim
    base = np.array(base_scores, dtype=float, copy=True)
    out = np.array(base, dtype=float, copy=True)
    book_n = int(p["book_n"])
    max_hold = int(p.get("max_hold", 0) or 0)
    em_w = float(p["em_w"])
    em_lb = int(p["em_lb"])

    # champion book (unmodified rows) — the DIAG baseline
    labels, base_picks = replay_book(panels, base, regime, book_n, max_hold)

    if em_w != 0.0 and em_lb >= 1:
        col_idx = {s: j for j, s in enumerate(panels["cols"])}
        exit_m: dict[str, int] = {}  # sym -> decision month of latest exit
        scale = 1.0 + em_w

        def modify(t, row, held):
            for sym, t0 in exit_m.items():
                if 1 <= t - t0 <= em_lb:
                    j = col_idx.get(sym)
                    if j is not None:
                        row[j] = row[j] * scale  # NaN * scale = NaN
            return row

        def on_exit(sym, t):
            exit_m[sym] = t  # latest exit resets the memory window

        _, cand_picks = replay_book(panels, out, regime, book_n, max_hold,
                                    modify=modify, on_exit=on_exit)
    else:
        # off-switch: out stays a bitwise copy of the champion's rows
        _, cand_picks = replay_book(panels, out, regime, book_n, max_hold)

    print(format_diag("strat_l21c_exitmem", f"em_lb={em_lb} em_w={em_w:+g}",
                      labels, base_picks, cand_picks, book_n), flush=True)
    return out, regime
