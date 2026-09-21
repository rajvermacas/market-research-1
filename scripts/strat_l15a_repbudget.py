"""Candidate: monthly replacement budget on the champion book (strategy_lab
contract).

Setup in words: the champion chain (strat_l13a_concwobble: floor-lift rank
among fresh prints, short-trend + print-continuity gates, breadth-tier
exposure, regime-conditional cap cap_weak/cap_full, eligibility-wobble tilt)
is imported wholesale. On top, the harness's monthly pick is replayed
causally (exact harness rule: px masks, max_hold exclusions, stable top-N
sort, min-count rule) and a REPLACEMENT BUDGET is folded in: in full-risk
months (E >= 1.0) at most `rep_max` NEW names may enter the book per month.
When the natural top-15 pick aspires to more than rep_max entrants, the
highest-scoring rep_max challengers are admitted; the remaining pick slots
are shielded by incumbents:
    rep_fill 1: held names that fell out of the natural pick but still carry
                a finite champion score (ranks 16-20 of the capped pool) keep
                their seats, best score first, until the book is 15 again.
    rep_fill 0: the slots stay empty — the book shrinks instead of shielding
                (concentration test; distinct from the cap because it is
                churn-conditional, not breadth-conditional).
The scaled/cap_weak months are NOT touched unless rep_weak 1: there the cap
already concentrates deliberately and every finite name is picked, so the
budget would only shrink the book (rep_weak 1 variants test exactly that).
The initial book build (held book empty, e.g. the first decision month and
the month after every cash spell) is exempt — the budget governs
replacements, not population.

Hypothesis: the champion re-picks top-15 from a capped-20 pool every month
with no incumbency memory; measured on the replayed book, full-risk months
turn over ~9 of 15 names (probe: mean 9.02, p10-p90 6-12) — the 15-of-20
boundary is a knife-edge and names bouncing across it cost 25 bps/side per
swap while adding names whose only claim is a hair's rank advantage. If the
boundary churn is noise, a budget buys the same or better compounding at
lower cost and with a steadier book; the shield variant additionally asks
whether a seated name with a still-passing gate is worth more than the
marginal challenger.

Falsifier: if every (rep_max, rep_fill) variant trails the flat base on
train CAGR AND none improves forward — then the monthly re-pick discipline
IS the edge and the churn is paying for itself; the axis closes at this
base. If only rep_fill 0 works, the effect is concentration, not retention.

Import chain: strat_l15a_repbudget -> strat_l13a_concwobble.score (the whole
champion chain, imported never copied) + strat_l12a_incbonus.replay_book
(the harness pick-rule replay machinery, reused as in strat_l12a_bookhealth).
The px/max_hold/min-count/top-N rules inside this file's build_row mirror
strategy_lab.backtest_scores so the natural pick U is exact.

PIT argument: the replay is causal — incumbency entering month t comes from
picks at months < t; the row folded for t reads only base scores at t
(closes through px[m]) and the existence (not value) of px[t+1] for the
same finiteness mask the harness itself applies. No forward values, no
daily panel.

Off-switch identity: rep_max >= top (15) makes every natural pick pass the
budget untouched, so no row is ever modified and the returned matrix is
bitwise the champion's. (len(held) == 0 months are exempt by design; with
rep_max >= top the bind condition can never fire anyway.)

Flat-base metric (off-switch must reproduce exactly, top 15, cost 25bps,
nse_all, split 2022-01-01): train +88.139% / DD -17.339% / calmar 5.083 /
H1 +80.1% / H2 +96.1% / invested 65.5% / fwd +49.274% / fwd DD -14.926% /
fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art in the mechanism inventory is the DEAD
retention-bonus line (strat_l12a_incbonus `inc_b`: an additive score bonus
for incumbents — mathematically the same reordering as a per-pair
"beat-it-by-a-margin" hurdle) and the LIVE cap_weak/cap_full book-size
lever. The ONE thing that changed: the incumbency preference is a COUNT
RATION on new entrants (a budget whose bind depends on how many challengers
aspire that month), not any additive score adjustment — no per-pair margin
or bonus can express "at most k entries this month, ranked by score", and
the effect lands only in full-risk months where the 15-of-20 cut has slack
(the inc_b negatives were measured on an uncapped top-15-of-all base with
max_hold 4, superseded by the cap chain).

book_n MUST equal the harness --top (15 in this loop's trials).

SPACE = champion-chain params (pinned) + rep_max {15(off), 2, 4, 8},
        rep_fill {1, 0}, rep_weak {0, 1}. Worker variants, one literal
        params-json each (champion keys as in the flat-base config):
  {"rep_max": 2, "rep_fill": 1, "rep_weak": 0}
  {"rep_max": 4, "rep_fill": 1, "rep_weak": 0}
  {"rep_max": 8, "rep_fill": 1, "rep_weak": 0}
  {"rep_max": 2, "rep_fill": 0, "rep_weak": 0}
  {"rep_max": 4, "rep_fill": 0, "rep_weak": 0}
  {"rep_max": 4, "rep_fill": 1, "rep_weak": 1}
"""

from __future__ import annotations

import numpy as np

from strat_l13a_concwobble import score as _cw_score
from strat_l12a_incbonus import replay_book

NEEDS_DAILY = False
SPACE = {
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
    "gw_w": [0.13],
    "max_hold": [3],
    "book_n": [15],
    "rep_max": [15, 2, 4, 8],
    "rep_fill": [1, 0],
    "rep_weak": [0, 1],
}


def score(panels, params):
    p = dict(params)
    # mirror strat_l13a_concwobble's own neutral defaults BEFORE delegating so
    # the off-switch never inherits the Loop-12 discount through a leak
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    base, E = _cw_score(panels, p)

    top = int(params.get("book_n", 15))
    max_hold = int(params.get("max_hold", 0) or 0)
    rep_max = int(params.get("rep_max", top))  # off-switch: >= top
    rep_fill = int(params.get("rep_fill", 1))
    rep_weak = int(params.get("rep_weak", 0))
    px, cols = panels["px"], panels["cols"]
    col_idx = {s: j for j, s in enumerate(cols)}

    out = np.array(base, dtype=float, copy=True)
    if rep_max < top:
        def build_row(t, held):
            row = base[t]
            # ---- replicate the harness pick rule on the base row: the
            # natural pick U the champion would have taken this month ----
            s = np.array(row, dtype=float, copy=True)
            ok = np.isfinite(s) & np.isfinite(px[t]) & np.isfinite(px[t + 1])
            s[~ok] = np.nan
            if max_hold:
                for sym, t0 in held.items():
                    j = col_idx.get(sym)
                    if j is not None and t - t0 >= max_hold:
                        s[j] = np.nan
            idx = np.flatnonzero(np.isfinite(s))
            E_t = float(np.clip(E[t], 0.0, 1.0))
            if E_t <= 0 or idx.size < max(top // 2, 3) or len(held) == 0:
                return row  # cash either way, or initial book build: exempt
            order = idx[np.argsort(-s[idx], kind="stable")[:top]]
            held_js = {col_idx[sym] for sym in held if sym in col_idx}
            challengers = [int(j) for j in order if j not in held_js]
            bind = len(challengers) > rep_max and (E_t >= 1.0 or rep_weak)
            if not bind:
                return row
            admit = challengers[:rep_max]  # U is score-desc already
            survivors = [int(j) for j in order if j in held_js]
            pick = set(survivors) | set(admit)
            if rep_fill:
                slots = top - len(pick)
                if slots > 0:
                    shield = []
                    for sym, t0 in held.items():
                        j = col_idx.get(sym)
                        if j is None or j in pick:
                            continue
                        if not (np.isfinite(row[j]) and np.isfinite(px[t, j])
                                and np.isfinite(px[t + 1, j])):
                            continue
                        if max_hold and t - t0 >= max_hold:
                            continue
                        shield.append((int(j), float(row[j])))
                    shield.sort(key=lambda jc: (-jc[1], jc[0]))  # score desc, stable
                    pick |= {j for j, _ in shield[:slots]}
            # encode: every still-finite name not in the budgeted pick is
            # ineligible this month; pick members keep their champion scores
            newrow = np.array(row, dtype=float, copy=True)
            for j in np.flatnonzero(np.isfinite(row)):
                if j not in pick:
                    newrow[j] = np.nan
            out[t] = newrow
            return newrow

        replay_book(panels, E, top, max_hold, build_row)
    return out, E
