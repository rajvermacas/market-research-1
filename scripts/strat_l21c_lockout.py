"""Candidate: re-entry LOCKOUT — a name that exits the book is barred from
re-entering for K months (strategy_lab contract; Loop-21 designer C, axis =
book-state CHURN).

Setup in words: the CURRENT champion chain strat_l20b_spread (gatefail lift
-> ids tilt -> cap -> listing-age tilt -> outrank tilt -> Corwin-Schultz
spread tilt, top 15, nse_all, cost 25bps, split 2022-01-01, max_hold 3) is
composed VERBATIM via `from strat_l20b_spread import score as _l20`. On top of
its returned scores this file applies ONE book-state rule, and because the
rule depends on the HELD BOOK it replays the harness pick rule month by month
inside score() (see replay_book) and folds the rule in BEFORE each pick:

    at decision month t, every symbol whose most recent EXIT from the book
    happened at decision month t0 with 1 <= t - t0 <= lock_k has its row at t
    set to NaN (hard bar); lock_k = 0 disables the rule entirely.

Counting (explicit, because "K months" is ambiguous): the exit decision month
t0 itself already excludes the name (it was not picked there), so lock_k
counts ADDITIONAL decision months barred after the exit — first eligible
re-entry is decision t0 + lock_k + 1. lock_k 1 = the name must sit out the
exit month's holding period plus one more; lock_k 6 = seven holding periods
out of the book. An "exit" is any departure from the book at a decision where
a selection actually happened: being out-scored past the cut, the cap
truncating it, a gate failure (row NaN), or the max_hold 3 clock forcing it
out. Exits are NOT recorded in cash months (exposure 0 empties the whole book
by regime, not by selection — recording those would turn this into a
post-breadth-collapse rotation rule, a different mechanism, and would make
the bar bite exactly in the months the falsifier below flags). A held name is
never barred: re-entry requires t - t0 > lock_k, so from its entry onward
t - t0 only grows — the bar filters CHALLENGERS at the entry boundary, which
is where the incumbency family (bonus/budget/hurdle, all protecting STAYERS)
never looked.

PIT argument: the only state this rule reads is (a) book state produced by
picks at decision months < t — the replay is causal, month t's bar set is
fully determined before month t's pick — and (b) the champion's own score
rows, which read closes through px[t] and daily bars strictly before
months[t] (delegate chain guarantee). The replay's availability mask reads
isfinite(px[t+1]) — the EXISTENCE of next month's close, never its value —
exactly as the harness's own pick rule does; the exit-month index is a
decision counter, not a price. No row > t is ever read.

Causal-replay argument: the harness re-picks top-15 every month with no
incumbency memory, so a bar that depends on the held book must be folded in
BEFORE each pick, inside score(). replay_book() is a line-for-line mirror of
strategy_lab.backtest_scores' selection walk (mask on finite row / px[t] /
px[t+1]; held-book exclusions for non-finite px and max_hold; empty pick
unless exposure > 0 and the surviving pool >= max(top//2, 3); top-book_n by
np.argsort(-s, kind="stable")). score() runs it TWICE: once over the
pristine champion rows (the champion book, for diagnostics) and once over the
rows it is modifying (this candidate's book, with the bar folded in before
each pick). Induction: both walks start from an empty book; if the books
entering month t agree, both apply the same rule to the same row at t, so the
picks agree and the books entering t+1 agree — therefore the harness's book
on the RETURNED rows equals the replayed book, and the modification the
harness sees is exactly the one this file computed. The mirror was validated
END-TO-END by .cache/l21dC_replay_check.py: picks re-derived from a
candidate's RETURNED rows, fed through a copy of backtest_scores' equity
step, reproduce the harness's printed metrics for the off-switch identity
(train +102.990/-15.506/6.642) AND for an active cell — if either missed to
the printed precision the replay would be wrong and this file undeliverable.
(trail_k is not replicated: no trial here sets it, same stipulation as
strat_l12a_incbonus.replay_book.)

NOVELTY STATEMENT (closest registry rows -> the ONE thing changed):
- research/tested_mechanisms.tsv line 84 strat_l12a_incbonus (retention
  bonus / grandfathered exit, DEAD), line 103 strat_l15a_repbudget (monthly
  replacement budget, DEAD), line 100 strat_l15a_dualshield (dual incumbency
  shield, DEAD), line 102 strat_l15a_pickband (rank-space replacement band,
  DEAD), line 115 strat_l16b_hurdle (replacement hurdle, KEEP-not-promoted
  and traced to ONE firing), line 99 strat_l15a_capgrand (weak-month cap
  grandfather, KEEP-not-promoted) — that is the incumbency-protection
  family, complete and DEAD as of Loop-16, and EVERY row in it protects
  names that are already in the book (bonus to stayers, budget for drops,
  hurdle against replacements, grandfather against exits).
- WHAT CHANGED — the mirror direction on a changed base: this file bars
  RE-ENTRY after an exit (a cost on leavers' return, not a bonus on stayers)
  and no registry row has ever screened a re-entry bar: forced churn was the
  untested half of the family. (b) the BASE: none of those rows ever saw the
  L20 champion chain strat_l20b_spread (train +102.990 / -15.506 / 6.642);
  they died on the rankpersist / conc / ids chains. Related but distinct:
  line 53 strat_floorhightierhold and line 85 strat_l12a_pathhold cap EXIT
  by holding duration (how long a name may stay); a lockout constrains
  RE-ENTRY (how soon a name may come back) and never touches a held name.
- Also distinct from line 130 strat_l17c_eqstate, which replayed the book to
  read an equity state off it (its replay boundary bug is noted there); the
  replay here feeds a selection rule, not a regime.

Hypothesis: the harness's monthly re-pick is memoryless, so a name can win
its slot back the month after losing it — whipsawing the book and paying 25
bps/side on the round trip (L12's framing: marginal fresh names nose ahead of
out a hair). If those immediate returns are noise, barring them for K months
holds the replacement name longer, cuts turnover, and keeps the winners; the
rival story is that immediate re-entry IS the edge — the memoryless re-pick
discipline keeps the book tracking fresh signals, so any bar buys cost savings
with stale names.

Falsifier: the lockout family CLOSES on this base if every K in {1,2,3,6}
trails the flat base on train CAGR with no offsetting drawdown or forward
improvement (the harness keep rule never fires on the smoke ledger), and it
closes as a MECHANISM — whatever the numbers — if the L21C-DIAG line shows
the bar only thins already-capped weak months: diff == diff_capped with
diff_full == 0, meanbook_cand < meanbook_base and/or newempty > 0. A rule
that only shrinks the 11-name weak-month book (or pushes it under the
max(top//2,3)=8 floor into cash) is exposure withdrawal, not churn, and is
the brief's named falsifier. Per the Loop-17 rule a train gain bought with
wider drawdown or a forward collapse is an ARTIFACT, not an upgrade; before
ANY promotion the decision-month pick-diff footprint must be counted (Loop-16:
a gain sourced from a handful of name-months is a sample of a handful).

Flat-base metric (off-switch must reproduce bit-exactly): train +102.990% /
DD -15.506% / ret-DD 6.642 / H1 +100.204 / H2 +105.682 / fwd +54.057% /
fwd DD -10.381% / full +82.001% / full DD -20.728%.

Keys consumed: lock_k (this file's rule), book_n (replay book size — MUST
equal the harness --top, 15 in every smoke trial), max_hold (the replay must
mirror the harness risk clock, 3, read from params the way the harness's
params-override merge reads it). Everything else in params-json — the full
champion key set — flows through to the delegate and is PASSED, never
defaulted here. trail_k is not replicated (no trial sets it).

SPACE (4 documented variants + off-switch, all on the pinned champion keys):
    lock_k 0   off-switch identity (must reproduce the flat base exactly)
    lock_k 1   bar the next decision after any exit
    lock_k 2   bar two decisions after any exit
    lock_k 3   bar three decisions after any exit
    lock_k 6   bar six decisions after any exit (a full max_hold cycle x2)
book_n pinned 15 (= --top).
"""

from __future__ import annotations

import numpy as np

from strat_l20b_spread import score as _l20

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
    "lock_k": [0, 1, 2, 3, 6],
}


def replay_book(panels, out, regime, book_n, max_hold, modify=None,
                on_exit=None):
    """Mirror of strategy_lab.backtest_scores' SELECTION walk (equity/cost
    bookkeeping omitted — it cannot affect picks). Shared by the three
    Loop-21c churn files; single source, imported, never re-copied.

    Walks decision months t = start_i .. len(months)-2 over `out` (the score
    rows the harness will read). If `modify` is given it is called
    modify(t, row, held) BEFORE the pick and its returned row is written back
    into out[t] — that is the causal fold-in: the bar at month t sees only
    the book held entering t (picks at months < t). If `on_exit` is given it
    is called on_exit(sym, t) for every symbol in the entering book that the
    pick at t did not keep, at every decision where a selection happened
    (exposure > 0 and a non-empty pick; cash months select nothing and are
    not name-level exits).

    Selection, line-for-line from backtest_scores:
      E = clip(regime[t], 0, 1); s = out[t].copy(); NaN where NOT
      (isfinite(s) & isfinite(px[t]) & isfinite(px[t+1])); held names with
      non-finite px[t] or t - entry >= max_hold are NaN'd; pick = top book_n
      of the survivors by np.argsort(-s, kind="stable") iff E > 0 and the
      survivor count >= max(book_n // 2, 3), else the pick is EMPTY; held
      advances (picked names keep their entry month, else enter at t).

    Returns (labels, picks) with picks[i] a frozenset for labels[i] =
    months[start_i + i]. trail_k is NOT replicated (no Loop-21c trial sets
    it), the same stipulation strat_l12a_incbonus.replay_book records.
    """
    px, months, cols = panels["px"], panels["months"], panels["cols"]
    start_i = panels["start_i"]
    col_idx = {s: j for j, s in enumerate(cols)}
    n_stocks = px.shape[1]
    held: dict[str, int] = {}
    labels, picks = [], []
    for t in range(start_i, len(months) - 1):
        if modify is not None and t < out.shape[0]:
            out[t] = modify(t, np.array(out[t], dtype=float, copy=True), held)
        E = float(np.clip(regime[t] if t < len(regime) else 1.0, 0.0, 1.0))
        s = out[t].copy() if t < out.shape[0] else np.full(n_stocks, np.nan)
        ok = np.isfinite(s) & np.isfinite(px[t]) & np.isfinite(px[t + 1])
        s[~ok] = np.nan
        excl = set()
        for sym, t0 in held.items():
            j = col_idx.get(sym)
            if j is None or not np.isfinite(px[t, j]):
                excl.add(sym)
                continue
            if max_hold and t - t0 >= max_hold:
                excl.add(sym)
        for sym in excl:
            j = col_idx.get(sym)
            if j is not None:
                s[j] = np.nan
        idx = np.flatnonzero(np.isfinite(s))
        pick = set()
        if E > 0 and len(idx) >= max(book_n // 2, 3):
            order = idx[np.argsort(-s[idx], kind="stable")[:book_n]]
            pick = {cols[i] for i in order}
        labels.append(months[t])
        picks.append(frozenset(pick))
        if on_exit is not None and pick:  # a selection happened (not cash)
            for sym in held:
                if sym not in pick:
                    on_exit(sym, t)
        held = {sym: held.get(sym, t) for sym in pick}
    return labels, picks


def _turnover(picks):
    """Harness-style mean turnover: at each decision with a non-empty pick,
    len(pick - entering_book) / len(pick); cash months skip (harness charges
    no cost then) and empty the entering book, exactly as backtest_scores."""
    vals, repl, prev = [], [], set()
    for pk in picks:
        if pk:
            out_n = len(pk - prev)
            vals.append(out_n / max(len(pk), 1))
            repl.append(out_n)
            prev = set(pk)
        else:
            prev = set()
    m = float(np.mean(vals)) if vals else float("nan")
    r = float(np.mean(repl)) if repl else float("nan")
    return m, r


def format_diag(cand, key, labels, base_picks, cand_picks, book_n):
    """One greppable line with the Loop-16 diagnostics: how many decision
    months the picks differ from the champion's, how many of those change the
    BOOK SIZE, how many sit in already-capped months (champ book below
    book_n = the weak/capped months), how many push a full book to cash, plus
    book-size and turnover shifts for both books."""
    n = len(labels)
    diff = [i for i in range(n) if base_picks[i] != cand_picks[i]]
    bookdiff = sum(1 for i in range(n)
                   if len(base_picks[i]) != len(cand_picks[i]))
    capped = sum(1 for i in diff if len(base_picks[i]) < book_n)
    newempty = sum(1 for i in diff
                   if len(cand_picks[i]) == 0 and len(base_picks[i]) > 0)
    to_b, r_b = _turnover(base_picks)
    to_c, r_c = _turnover(cand_picks)
    nm_b = sum(len(x) for x in base_picks)
    nm_c = sum(len(x) for x in cand_picks)
    return (f"L21C-DIAG cand={cand} {key} months={n} diff={len(diff)} "
            f"bookdiff={bookdiff} diff_capped={capped} "
            f"diff_full={len(diff) - capped} newempty={newempty} "
            f"meanbook_base={nm_b / max(n, 1):.2f} "
            f"meanbook_cand={nm_c / max(n, 1):.2f} nmm_base={nm_b} "
            f"nmm_cand={nm_c} to_base={to_b:.4f} to_cand={to_c:.4f} "
            f"repl_base={r_b:.2f} repl_cand={r_c:.2f}")


def score(panels, params):
    p = dict(params)  # neutral defaults for THIS file's keys, then delegate
    p.setdefault("lock_k", 0)
    p.setdefault("book_n", 15)
    base_scores, regime = _l20(panels, p)  # current champion chain, verbatim
    base = np.array(base_scores, dtype=float, copy=True)
    out = np.array(base, dtype=float, copy=True)
    book_n = int(p["book_n"])
    max_hold = int(p.get("max_hold", 0) or 0)
    lock_k = int(p["lock_k"])

    # champion book (unmodified rows) — the DIAG baseline
    labels, base_picks = replay_book(panels, base, regime, book_n, max_hold)

    if lock_k > 0:
        col_idx = {s: j for j, s in enumerate(panels["cols"])}
        exit_m: dict[str, int] = {}  # sym -> decision month of latest exit

        def modify(t, row, held):
            for sym, t0 in exit_m.items():
                if 1 <= t - t0 <= lock_k:
                    j = col_idx.get(sym)
                    if j is not None:
                        row[j] = np.nan  # barred: cannot re-enter yet
            return row

        def on_exit(sym, t):
            exit_m[sym] = t  # latest exit resets the bar window

        _, cand_picks = replay_book(panels, out, regime, book_n, max_hold,
                                    modify=modify, on_exit=on_exit)
    else:
        # off-switch: out stays a bitwise copy of the champion's rows
        _, cand_picks = replay_book(panels, out, regime, book_n, max_hold)

    print(format_diag("strat_l21c_lockout", f"lock_k={lock_k}", labels,
                      base_picks, cand_picks, book_n), flush=True)
    return out, regime
