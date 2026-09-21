"""Candidate: replacement hurdle for incumbents on the champion book
(strategy_lab contract).

Setup in words: the CURRENT champion chain — strat_l15b_insideday at its
champion params (floor-lift fresh-print rank + gates + breadth tiers +
regime-conditional cap + eligibility-wobble gw_w 0.15 + inside-day tilt
ids_w -0.13 / ids_lb 3), imported wholesale, POST-cap — is replayed through
the exact harness pick rule month by month (strat_l12a_incbonus.replay_book)
and a REPLACEMENT HURDLE is folded in BEFORE each pick, in the decision
month t itself:

  1. mask and sort exactly like the harness: finite champion score,
     finite px[t] AND px[t+1] (existence only), names past max_hold
     excluded; stable descending sort -> natural top-15 pick U.
  2. every INCUMBENT (held entering t) whose masked score fell out of U is
     a challenger V (sorted descending by score). The weakest member of U
     that is NOT an incumbent is the defended slot.
  3. the incumbent keeps its slot only if the challenger's score advantage
     clears the hurdle: swap the weakest non-incumbent out for the best
     challenger v while
         s[v] >= s[defended] * (1 - hur_m)
     i.e. the challenger must beat the defended slot by a RELATIVE margin
     of hur_m to take it. hur_n caps how many swaps one month may make.
     If the best remaining challenger fails the hurdle, weaker ones fail
     too (V is descending) and the loop stops.
  4. the returned row keeps U's original scores and NaNs every other
     masked-eligible name, so the harness's own re-sort reproduces U
     exactly (the strat_l15a_capgrand row-writing convention).

Full-risk and scaled months are treated identically: the hurdle acts at the
harness top-15 cut, which exists in every month the book is populated.

Hypothesis: the champion re-picks top-15 every month with no incumbency
memory; the eligibility-wobble result (gw_w 0.15 is part of the champion)
proved that marginal qualifiers flicker across gates and that their churn
costs real money. The DEAD retention-bonus line (inc_b) and the DEAD
replacement budget (rep_max/rep_fill) attacked this as a book-wide bonus or
a monthly ration; both lost train. The hurdle is LOCAL: only boundary
incumbents — those who actually fell below the cut this month — get a
voice, and only against the weakest seat, and only within a small margin.
If the 15-of-20 boundary jitter is noise, a small hurdle buys the same
compounding at lower cost; if the monthly re-pick discipline IS the edge,
every hur_m > 0 trails the base and the axis closes for good (the third
and sharpest test of this family: a bonus that applies to every incumbent
every month, and a ration on all entrants, have both been falsified — the
one shape never tested is the local, boundary-conditional margin).

Falsifier: if every (hur_m, hur_n) combination trails the flat base on
train CAGR and none improves forward risk-adjusted numbers — then the
top-15 cut is already the right selection at every margin and the
incumbency-protection family closes at this base (bonus: dead, budget:
dead, hurdle: dead => the mechanism itself, not its shape, is wrong).

Import chain: strat_l16b_hurdle -> strat_l15b_insideday.score (the whole
champion chain including the cap, imported never copied) +
strat_l12a_incbonus.replay_book (harness pick-rule replay machinery). The
mask/sort/min-count/top-N rules inside build_row mirror
strategy_lab.backtest_scores so the natural pick is exact.

PIT argument: the replay is causal — incumbency entering month t comes from
picks at months < t; the row folded for t reads only champion scores at t
(closes through px[m]) and the existence (not value) of px[t+1] in the same
finiteness mask the harness itself applies. No forward values, no daily
panel read here.

Off-switch identity: hur_m = 0 (or <= 0) returns the champion row untouched
in every month — no swap, no NaN rewrite — so `out` is bitwise the
imported champion scores at the same params. (The swap condition at
hur_m = 0 would be s[v] >= s[defended], which the sort order can satisfy on
ties; the guard short-circuits BEFORE any row modification, so the identity
is exact regardless.)

Flat-base metric (off-switch must reproduce exactly, top 15, 25 bps,
nse_all, split 2022-01-01): train +96.882% / DD -17.032% / calmar 5.688 /
H1 +98.3% / H2 +95.5% / fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art is the DEAD retention-bonus line
(strat_l12a_incbonus inc_b — an ADDITIVE score bonus for EVERY incumbent
EVERY month, i.e. a per-pair margin that reorders the whole book) and the
DEAD replacement-budget line (strat_l15a_repbudget rep_max/rep_fill — a
COUNT ration on new entrants with shield/empty variants, dominated on this
base's predecessor). The ONE thing that changed — mechanism, not shape:
protection is now CONDITIONAL ON THE BOUNDARY. A retention bonus pays every
incumbent every month (and was falsified because stale names kept seats
they had not earned); a budget caps entrants by count regardless of how
close the contest was. The hurdle pays nothing unless an incumbent is
actually below the cut THIS month, and even then only lets it keep a seat
it already holds against the weakest challenger slot within a small score
margin — no bonus enters the score, no entrant ration exists, and a
challenger that beats the incumbent by more than hur_m replaces it exactly
as the champion would. Neither prior mechanism collapses to this under any
parameter value (inc_b 0 is the off-switch of the bonus, not a conditional
hurdle; rep_max >= top disables the budget entirely). Base is additionally
new to the family: both dead lines were measured on the L12/L13
pre-insideday chains; this is the first incumbency mechanism on the
current champion base.

book_n MUST equal the harness --top (15 in this loop's trials).

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, cap_weak 11,
        cap_full 20, floor_lb 19, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3,
        ids_w -0.13, lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5,
        sustain_lo 3, sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999;
        max_hold 3 is a HARNESS key via params-json, mirrored in the replay)
        + hur_m {0.0 = off-switch, 0.01, 0.03, 0.06} (relative margin a
          challenger must clear to displace a cut incumbent)
        + hur_n {1, 2} (max swaps per month).
"""

from __future__ import annotations

import numpy as np

from strat_l15b_insideday import score as _ids_score
from strat_l12a_incbonus import replay_book

NEEDS_DAILY = True
SPACE = {
    # champion keys (pinned, docs only)
    "b_hi": [0.69],
    "b_lo": [0.45],
    "b_mid": [0.55],
    "cap_weak": [11],
    "cap_full": [20],
    "floor_lb": [19],
    "gf_lb": [12],
    "gf_w": [0.0],
    "gw_w": [0.15],
    "ids_lb": [3],
    "ids_w": [-0.13],
    "lookback": [12],
    "max_dist": [0.055],
    "regime_ma": [18],
    "fast_ma": [5],
    "sustain_lo": [3],
    "sustain_hi": [2],
    "tier_lo": [0.9999],
    "tier_mid": [0.9999],
    # this file's keys
    "book_n": [15],
    "hur_m": [0.0, 0.01, 0.03, 0.06],
    "hur_n": [1, 2],
}


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating (gatefail's gf_w 0.05 default would
    # leak); the champion's gw_w/ids values must be PASSED by the caller.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    p.setdefault("ids_w", 0.0)
    base, exposure = _ids_score(panels, p)  # champion scores, post-cap

    hur_m = float(params.get("hur_m", 0.0))
    hur_n = int(params.get("hur_n", 1))
    top = int(params.get("book_n", 15))
    max_hold = int(params.get("max_hold", 0) or 0)
    px, cols = panels["px"], panels["cols"]
    col_idx = {s: j for j, s in enumerate(cols)}

    out = np.array(base, dtype=float, copy=True)

    def build_row(t, held):
        row = base[t]
        if hur_m <= 0.0:
            return row  # off-switch: bitwise champion row, no rewrite
        E = float(np.clip(exposure[t] if t < len(exposure) else 1.0, 0.0, 1.0))
        # harness mask: finite score, finite px[t] and px[t+1] (existence only)
        s = np.array(row, dtype=float, copy=True)
        ok = np.isfinite(s)
        ok &= np.isfinite(px[t]) & np.isfinite(px[t + 1])
        inc_js = {}
        for sym, t0 in held.items():
            j = col_idx.get(sym)
            if j is None:
                continue
            if max_hold and t - t0 >= max_hold:
                ok[j] = False  # harness excludes past-max_hold names
            elif ok[j]:
                inc_js[j] = t0
        idx = np.flatnonzero(ok)
        if E <= 0 or idx.size < max(top // 2, 3):
            return row  # harness picks nothing; leave the row as champion's
        order = idx[np.argsort(-s[idx], kind="stable")]
        if idx.size <= top:
            return row  # no cut, nothing to defend
        U = [int(j) for j in order[:top]]
        Uset = set(U)
        # challengers: incumbents below the cut, best score first
        V = sorted((j for j in inc_js if j not in Uset),
                   key=lambda j: (-s[j], j))
        if not V:
            return row
        inc_set = set(inc_js)
        swaps = 0
        for v in V:
            defenders = [j for j in U if j not in inc_set]
            if not defenders:
                break
            m = min(defenders, key=lambda j: (s[j], j))
            if s[v] >= s[m] * (1.0 - hur_m):
                U.remove(m)
                U.append(v)
                inc_set.add(v)
                swaps += 1
                if swaps >= hur_n:
                    break
            else:
                break  # V is descending: weaker challengers fail too
        newrow = np.array(row, dtype=float, copy=True)
        for j in idx:
            if j not in set(U):
                newrow[j] = np.nan
        out[t] = newrow
        return newrow

    replay_book(panels, exposure, top, max_hold, build_row)
    return out, exposure
