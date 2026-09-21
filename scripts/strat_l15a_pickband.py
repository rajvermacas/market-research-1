"""Candidate: rank-space replacement band on the champion pick line
(strategy_lab contract).

Setup in words: the champion chain (strat_l13a_concwobble: floor-lift rank
among fresh prints, short-trend + print-continuity gates, breadth-tier
exposure, cap_weak/cap_full, eligibility-wobble tilt) is imported wholesale.
The harness pick rule is replayed causally (exact harness rule: px masks,
max_hold exclusions, stable sort, min-count), and a BUFFER is folded into
the pick: an incumbent keeps its seat while its cross-sectional rank
POSITION within the month's capped-eligible pool is inside the band —
position < book_n + band. A challenger therefore takes an incumbent's seat
only by outranking it by MORE than `band` positions; an incumbent that
falls further than band ranks below the cut line is out as usual (no
grandfathering of deep falls, gates and max_hold untouched). Remaining
seats are filled by the best-ranked challengers; book size stays
min(book_n, pool) — identical to the champion's pick size, so the test is
pure composition at the jitter zone. The initial book build (held empty) is
exempt. In scaled months the pool is cap_weak-bounded (11 < 15), every
finite name is picked and the band is vacuous there by construction — the
band acts in full-risk months where the 15-of-20 cut has slack.

Hypothesis: measured on the replayed book, full-risk months turn over ~9 of
15 names; much of that is the 15-of-20 knife-edge, where a name that slips
one rank is swapped for one that gains one — 25 bps/side to trade
near-identical exposure. A 1-3 rank buffer keeps such jitters seated while
leaving genuine rank moves (beyond the band) to churn freely: cheaper book,
same information. This is the mildest dial on the replacement axis —
strat_l15a_repbudget rations the COUNT of entries (harsh: rep_max 2 costs
-11pp train), this file rations only the MARGIN at the line.

Falsifier: if every band {1, 2, 3} trails the flat base on train CAGR and
none improves forward, then even boundary-jitter churn pays for itself and
the pick line should stay a pure score cut; combined with the repbudget
result the whole replacement-hurdle axis closes at this base. If band helps
while rep_max 2 hurt, the churn that matters is localized at the line, not
gross turnover.

Import chain: strat_l15a_pickband -> strat_l13a_concwobble.score (the whole
champion chain, imported never copied) + strat_l12a_incbonus.replay_book
(harness pick-rule replay machinery). The px/max_hold/min-count/top-N rules
in build_row mirror strategy_lab.backtest_scores.

PIT argument: causal replay — incumbency entering month t comes from picks
at months < t; the row folded for t reads only champion scores at t (closes
through px[m]) and the existence (not value) of px[t+1] in the same
finiteness mask the harness applies. No forward rows, no daily panel.

Off-switch identity: band = 0 keeps incumbents only within the top-15 (the
champion pick), the fill reproduces the champion pick exactly, and the
mechanism never modifies a row — the file returns the champion matrix
bitwise (the replay is not even run).

Flat-base metric (off-switch must reproduce exactly, top 15, cost 25bps,
nse_all, split 2022-01-01): train +88.139% / DD -17.339% / calmar 5.083 /
H1 +80.1% / H2 +96.1% / invested 65.5% / fwd +49.274% / fwd DD -14.926% /
fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art is the DEAD retention-bonus line
(strat_l12a_incbonus inc_b — an unbounded additive score bonus on every
incumbent, tested on the superseded uncapped rankpersist base with
max_hold 4) and this loop's strat_l15a_repbudget (count ration). The ONE
thing that changed: the incumbency preference is denominated in
CROSS-SECTIONAL RANK POSITIONS and is BOUNDED — protection exists only in
the band immediately below the pick line, so deep falls still exit and the
pro strength is scale-free (independent of the arbitrary log-lift score
units that made inc_b's magnitude uninterpretable). No prior file
conditioned the pick line itself on book state.

book_n MUST equal the harness --top (15 in this loop's trials).

SPACE = champion-chain params (pinned) + band {0, 1, 2, 3}. Worker
variants, one literal params-json each (champion keys as in the flat
config):
  {"band": 1}
  {"band": 2}
  {"band": 3}
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
    "band": [0, 1, 2, 3],
}


def score(panels, params):
    p = dict(params)
    # mirror strat_l13a_concwobble's own neutral defaults BEFORE delegating
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    base, E = _cw_score(panels, p)

    top = int(params.get("book_n", 15))
    max_hold = int(params.get("max_hold", 0) or 0)
    band = int(params.get("band", 0))  # off-switch: 0
    px, cols = panels["px"], panels["cols"]
    col_idx = {s: j for j, s in enumerate(cols)}

    out = np.array(base, dtype=float, copy=True)
    if band > 0:
        def build_row(t, held):
            row = base[t]
            # replicate the harness pick rule on the base row
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
            pool = [int(j) for j in idx[np.argsort(-s[idx], kind="stable")]]
            held_js = {col_idx[sym] for sym in held if sym in col_idx}
            line = top + band
            kept_inc = {j for j in pool[:line] if j in held_js}
            pick = set(kept_inc)
            for j in pool:
                if len(pick) >= top:
                    break
                if j in held_js and j not in kept_inc:
                    continue  # fell beyond the band: an exit, however ranked
                pick.add(j)
            newrow = np.array(row, dtype=float, copy=True)
            for j in np.flatnonzero(np.isfinite(row)):
                if j not in pick:
                    newrow[j] = np.nan
            out[t] = newrow
            return newrow

        replay_book(panels, E, top, max_hold, build_row)
    return out, E
