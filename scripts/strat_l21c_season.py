"""Candidate: new-entry SEASONING — names in their first N months of the
book get a small rank bonus or penalty (strategy_lab contract; Loop-21
designer C, axis = book-state CHURN).

Setup in words: the CURRENT champion chain strat_l20b_spread (gatefail lift
-> ids tilt -> cap -> listing-age tilt -> outrank tilt -> Corwin-Schultz
spread tilt, top 15, nse_all, cost 25bps, split 2022-01-01, max_hold 3) is
composed VERBATIM via `from strat_l20b_spread import score as _l20`. On top of
its returned scores this file applies ONE book-state rule which depends on the
HELD BOOK, so score() replays the harness pick rule month by month inside
replay_book (imported from strat_l21c_lockout — single source, the same
line-for-line mirror of strategy_lab.backtest_scores' selection walk) and
folds the tilt in BEFORE each pick:

    at decision month t, every candidate whose COMPLETED time in the book is
    less than se_n months gets its row multiplied by (1 + se_w):

        tenure(sym, t) = t - entry_month(sym)   if held entering t
                       = 0                      otherwise (a fresh entry)
        if tenure < se_n:  row[sym] *= 1 + se_w      (|se_w| < 1)

so with se_n = 1 only fresh entrants are tilted; with se_n = 3 entrants plus
1- and 2-month incumbents are tilted and only longer-tenured names keep the
baseline weight. Counting convention: tenure is holding PERIODS completed at
the decision, so a name picked for the first time at t has tenure 0 (it is
in its first month during t -> t+1) and is tilted when se_n >= 1; a name
held since t-1 has tenure 1 at t — its first month is behind it. The tilt
multiplies the whole candidate row (challengers and young incumbents alike),
is strictly positive (|se_w| < 1), never creates or destroys eligibility (NaN
stays NaN), and — a structural property worth stating — is a UNIFORM scale in
any month where every candidate qualifies (e.g. the first invested month
after a cash month, where the whole book was wiped and everyone has tenure
0): uniform positive scaling preserves the sort order, so in such months the
mechanism provably changes nothing. It can only bite where the book carries
tenure differences across the decision boundary.

Both signs are first-class, as the brief requires:
  se_w > 0  REWARD young-book names — new blood out-ranks incumbents of equal
            score: forced churn, anti-incumbency, the fresh-signal story.
  se_w < 0  PENALISE young-book names — an entrant must prove itself before
            taking a slot from an established holder: the retention story in
            boundary form (see NOVELTY: this arm is a declared restatement
            of a DEAD family, screened here for symmetry, not claimed new).

PIT argument: the only state the tilt reads is book state produced by picks
at decision months < t (the replay is causal: month t's tenure map is fully
determined before month t's pick) plus the champion's own score rows, which
read closes through px[t] and daily bars strictly before months[t] (delegate
chain guarantee). Entry months are decision counters, not prices. The
replay's availability mask reads isfinite(px[t+1]) — the existence of next
month's close, never its value — exactly as the harness's own pick rule
does. No row > t is ever read.

Causal-replay argument: the harness re-picks top-15 every month with no
incumbency memory, so "first N months in the book" is undefined unless the
candidate reconstructs the book itself. score() runs replay_book twice: once
over the pristine champion rows (the champion book, for diagnostics) and once
over the rows it is modifying, with the tenure tilt folded in before each
pick. Induction: both walks start from an empty book; if the books entering
month t agree, both apply the same rule to the same row at t, so the picks
agree and the books entering t+1 agree — the harness's book on the RETURNED
rows therefore equals the replayed book, and the tilt the harness sees is
exactly the one computed here. The mirror is validated END-TO-END by
.cache/l21dC_replay_check.py: picks re-derived from a candidate's RETURNED
rows, fed through a copy of backtest_scores' equity step, reproduce the
harness's printed metrics for the off-switch identity (train +102.990/
-15.506/6.642) and for an active lockout cell. (trail_k is not replicated:
no trial here sets it — same stipulation as strat_l12a_incbonus.replay_book.)
Cash months (exposure 0) empty the book through the regime; that wipes
tenure, so the mechanism is inert in the following month by the uniform-scale
property above — stated, not hidden.

NOVELTY STATEMENT (closest registry rows -> the ONE thing changed):
- research/tested_mechanisms.tsv line 84 strat_l12a_incbonus (retention
  bonus / grandfather, DEAD) — the NEGATIVE arm of this file (penalise
  entrants) is that family restated at the entry boundary: a bonus to every
  incumbent equals a penalty on every challenger. Declared, not claimed as
  new; it is screened here for symmetry because the BRIEF requires both signs,
  and it must clear the same bar the original failed.
- research/tested_mechanisms.tsv line 103 strat_l15a_repbudget (replacement
  budget, DEAD), line 115 strat_l16b_hurdle (replacement hurdle,
  KEEP-not-promoted, one firing), line 99 strat_l15a_capgrand, line 100
  dualshield, line 102 pickband — the whole incumbency family PROTECTS
  stayers with a constant; none of them ever conditioned a score on how long
  a name has been in the book.
- research/tested_mechanisms.tsv line 53 strat_floorhightierhold and line 85
  strat_l12a_pathhold (hold clocks, DEAD) constrain EXIT by duration — how
  long a name may stay. Seasoning constrains ENTRY by tenure — how a name is
  WEIGHTED while young — and never removes a name: re-ordering, not a gate,
  not a clock.
- WHAT CHANGED — the ONE thing: tenure-conditioned rank weighting (a signal
  no registry row has: score x f(months already held)) in its POSITIVE
  direction — rewarding new entries, forced churn — which is the untested
  half of the incumbency axis; plus the BASE, the L20 champion chain
  strat_l20b_spread (train +102.990 / -15.506 / 6.642), which none of the
  rows above ever saw (they died on rankpersist / conc / ids chains).

Hypothesis: max_hold 3 already forces a third of the book out every quarter,
so the book is permanently young; if fresh entries deserve their slots, a
bonus to them compounds the harness's own churn, and if they are mostly
noise-driven replacements the penalty keeps challengers from edging out
holders by a hair (L12's whipsaw framing) until they have "seasoned". The
two signs test both stories on the same boundary.

Falsifier: the entry-tenure axis CLOSES on this base if every one of the six
cells trails the flat base on train CAGR with no offsetting drawdown or
forward improvement (the harness keep rule never fires on the smoke ledger),
and per the Loop-17 rule a train gain bought with wider drawdown or a forward
collapse is an ARTIFACT, not an upgrade. It closes as a MECHANISM — whatever
the numbers — if the L21C-DIAG line shows either (a) the footprint is a
handful of decision months (diff <= ~10 of 139: a gain sourced from a handful
of name-months is a sample of a handful — Loop-16), or (b) every differing
month is an already-capped weak month (diff == diff_capped, diff_full == 0,
meanbook_cand < meanbook_base and/or newempty > 0) — then the tilt only
thins the 11-name weak-month book, which is exposure withdrawal, not
seasoning. A negative-only result that echoes line 84's failure is expected
and is recorded as such, not as a fresh falsification of churn.

Flat-base metric (off-switch must reproduce bit-exactly): train +102.990% /
DD -15.506% / ret-DD 6.642 / H1 +100.204 / H2 +105.682 / fwd +54.057% /
fwd DD -10.381% / full +82.001% / full DD -20.728%.

Keys consumed: se_n (seasoning length), se_w (tilt weight, both signs),
book_n (replay book size — MUST equal the harness --top, 15 in every smoke
trial), max_hold (the replay must mirror the harness risk clock, 3, read
from params the way the harness reads it). Everything else in params-json —
the full champion key set — flows through to the delegate and is PASSED,
never defaulted here. Off-switch: se_n = 0 OR se_w = 0.0.

SPACE (6 documented variants + off-switch, all on the pinned champion keys):
    se_n 0 / se_w 0.0   off-switch identity (reproduces the flat base exactly)
    se_n {1, 2, 3} x se_w {+0.05, -0.05} = 6 cells
        (+ = bonus to young-book names / forced churn; - = penalty on them)
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
    "se_n": [0, 1, 2, 3],
    "se_w": [0.0, 0.05, -0.05],
}


def score(panels, params):
    p = dict(params)  # neutral defaults for THIS file's keys, then delegate
    p.setdefault("se_n", 0)
    p.setdefault("se_w", 0.0)
    p.setdefault("book_n", 15)
    base_scores, regime = _l20(panels, p)  # current champion chain, verbatim
    base = np.array(base_scores, dtype=float, copy=True)
    out = np.array(base, dtype=float, copy=True)
    book_n = int(p["book_n"])
    max_hold = int(p.get("max_hold", 0) or 0)
    se_n = int(p["se_n"])
    se_w = float(p["se_w"])

    # champion book (unmodified rows) — the DIAG baseline
    labels, base_picks = replay_book(panels, base, regime, book_n, max_hold)

    if se_n > 0 and se_w != 0.0:
        col_idx = {s: j for j, s in enumerate(panels["cols"])}
        n_sym = len(panels["cols"])
        scale = 1.0 + se_w

        def modify(t, row, held):
            # tenure >= se_n incumbents keep weight 1.0; everyone else
            # (fresh entrants and young incumbents) gets the tilt
            old = np.zeros(n_sym, dtype=bool)
            for sym, t0 in held.items():
                if t - t0 >= se_n:
                    j = col_idx.get(sym)
                    if j is not None:
                        old[j] = True
            row[~old] = row[~old] * scale  # NaN * scale = NaN (stays NaN)
            return row

        _, cand_picks = replay_book(panels, out, regime, book_n, max_hold,
                                    modify=modify)
    else:
        # off-switch: out stays a bitwise copy of the champion's rows
        _, cand_picks = replay_book(panels, out, regime, book_n, max_hold)

    print(format_diag("strat_l21c_season", f"se_n={se_n} se_w={se_w:+g}",
                      labels, base_picks, cand_picks, book_n), flush=True)
    return out, regime
