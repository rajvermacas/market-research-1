"""Candidate: incumbency-aware weak-month cap (cap-boundary grandfather) over
the champion chain (strategy_lab contract).

Setup in words: the champion's scores are strat_l12b_gatefail's tilted lift
(the full floor-lift + gates + breadth-tier + eligibility-wobble chain,
imported wholesale, PRE-cap), and the regime-conditional cap step of
strat_floorhightiershapeconc / strat_l13a_concwobble is re-implemented here
as a mirrored composition step (imported chain, cap mirrored inline exactly
as concwobble does) with ONE modification in scaled-risk months (E < 1.0):
the cap still keeps exactly `cap_weak` finite names, but the first
`grand_n` of its slots are reserved for INCUMBENTS — held names that still
carry a finite pre-cap score, pass the same px masks, are not past max_hold,
and sit below the score cut. Grandfather candidates are ranked by
pre-cap score + grand_tnb * min(months_held, grand_tcap) (grand_tnb 0 =
pure score order among the cut incumbents, i.e. the boundary-jitter cases;
a positive tilt ranks longer-held names first). Any grandfather slot left
unfilled is backfilled by the next-best non-kept name by score, so the
book keeps exactly cap_weak names — the cut's COUNT is untouched, only its
composition near the line changes. Full-risk months keep the champion's
plain top-cap_full cut.

Hypothesis: in scaled months the cap (cap_weak 11 < book 15) IS the
selection, and its score-order cut has no incumbency memory — a seated name
whose gate still passes but whose tilted score slipped one slot is cut and
re-admitted next month when it re-qualifies, paying 25 bps/side for
boundary jitter, exactly where breadth is weakest and ranks are noisiest
(the eligibility-wobble result says these flickers are common enough to
tilt the whole book). Reserving a couple of cap slots for the best cut
incumbents keeps vetted names through weak stretches; the count stays
cap_weak, so concentration is preserved and the test is pure composition.

Falsifier: if every (grand_n, grand_tnb) variant trails the flat base on
train CAGR and none improves forward — then the cap's score-order cut is
already the right weak-month selection and incumbency carries no
information at the cap boundary; the axis closes at this base.

Import chain: strat_l15a_capgrand -> strat_l12b_gatefail.score (pre-cap
tilted lift of the champion chain, imported never copied) +
strat_l12a_incbonus.replay_book (harness pick-rule replay machinery).
The cap step is MIRRORED inline from strat_floorhightiershapeconc.score /
strat_l13a_concwobble.score (a book-size composition step, not indicator
math) and, at grand_n 0, is bitwise the champion's cap.

PIT argument: the replay is causal — incumbency and tenure entering month t
come from picks at months < t; the row folded for t reads only pre-cap
scores at t (closes through px[m]) and the existence (not value) of
px[t+1] in the same finiteness mask the harness applies. No forward rows,
no daily panel.

Off-switch identity: grand_n = 0 reserves nothing, the mirrored cap is
bitwise strat_l13a_concwobble's (same sort, same NaN pattern, same
exposure), so the returned matrix is bitwise the champion's.

Flat-base metric (off-switch must reproduce exactly, top 15, cost 25bps,
nse_all, split 2022-01-01): train +88.139% / DD -17.339% / calmar 5.083 /
H1 +80.1% / H2 +96.1% / invested 65.5% / fwd +49.274% / fwd DD -14.926% /
fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art is the LIVE cap_weak/cap_full lever
(PARTIAL in the inventory: the values are sharp peaks but "changing their
mechanism is not" closed) and the DEAD retention-bonus line
(strat_l12a_incbonus inc_b). The ONE thing that changed: the cap's CUT
ORDER becomes book-state-aware — the weak-month cap now sees incumbency
(reserved grandfather slots, optional tenure tilt) where it previously cut
by current score alone; no prior file fed book state into the cap, and the
inc_b negative was a pick-side score bonus on an uncapped base, not a
cap-composition change.

book_n MUST equal the harness --top (15 in this loop's trials).
NOTE: gatefail's own defaults would leak (gf_w 0.05, gf_lb 6) — this file
forces the champion-neutral defaults (gf_w 0.0, gw_w 0.0, gf_lb 12) BEFORE
delegating, exactly the Loop-13 lesson.

SPACE = champion-chain params (pinned) + grand_n {0, 2, 4},
        grand_tnb {0.0, 0.25, 0.5}, grand_tcap {4, 6}. Worker variants,
        one literal params-json each (champion keys as in the flat config):
  {"grand_n": 2, "grand_tnb": 0.0, "grand_tcap": 6}
  {"grand_n": 4, "grand_tnb": 0.0, "grand_tcap": 6}
  {"grand_n": 4, "grand_tnb": 0.25, "grand_tcap": 6}
  {"grand_n": 2, "grand_tnb": 0.5, "grand_tcap": 4}
"""

from __future__ import annotations

import numpy as np

from strat_l12b_gatefail import score as _gf_score
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
    "grand_n": [0, 2, 4],
    "grand_tnb": [0.0, 0.25, 0.5],
    "grand_tcap": [4, 6],
}


def score(panels, params):
    p = dict(params)
    # champion-neutral defaults BEFORE delegating (gatefail's own gf_w 0.05
    # default would silently break the off-switch)
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    lift, E = _gf_score(panels, p)  # PRE-cap tilted champion scores

    cw = int(params.get("cap_weak", 11))
    cf = int(params.get("cap_full", 20))
    top = int(params.get("book_n", 15))
    max_hold = int(params.get("max_hold", 0) or 0)
    grand_n = int(params.get("grand_n", 0))  # off-switch: 0
    grand_tnb = float(params.get("grand_tnb", 0.0))
    grand_tcap = int(params.get("grand_tcap", 6))
    px, cols = panels["px"], panels["cols"]
    col_idx = {s: j for j, s in enumerate(cols)}

    out = np.array(lift, dtype=float, copy=True)

    def build_row(t, held):
        row = lift[t]
        fin = np.flatnonzero(np.isfinite(row))
        if fin.size == 0:
            return row
        E_t = float(np.clip(E[t], 0.0, 1.0))
        if E_t >= 1.0:
            cap = cf
        else:
            cap = cw
        if fin.size <= cap:
            return row  # champion's cap skips too: bitwise identical
        order = fin[np.argsort(-row[fin], kind="stable")]
        if E_t >= 1.0 or grand_n <= 0:
            newrow = np.array(row, dtype=float, copy=True)
            newrow[order[cap:]] = np.nan
            out[t] = newrow
            return newrow
        # scaled month with a grandfather reserve: cap_weak slots, the first
        # (cap_weak - grand_n) by score, the rest reserved for incumbents
        n_base = cw - grand_n
        kept = {int(j) for j in order[:n_base]}
        cands = []
        for sym, t0 in held.items():
            j = col_idx.get(sym)
            if j is None or j in kept:
                continue
            if not (np.isfinite(row[j]) and np.isfinite(px[t, j])
                    and np.isfinite(px[t + 1, j])):
                continue
            if max_hold and t - t0 >= max_hold:
                continue
            tenure = t - t0
            key = float(row[j]) + grand_tnb * min(tenure, grand_tcap)
            cands.append((-key, int(j)))
        cands.sort()
        grand = {j for _, j in cands[:grand_n]}
        kept |= grand
        slots = cw - len(kept)
        if slots > 0:
            for j in order:  # champion-style backfill by score
                if slots <= 0:
                    break
                jj = int(j)
                if jj not in kept:
                    kept.add(jj)
                    slots -= 1
        newrow = np.array(row, dtype=float, copy=True)
        for j in fin:
            if int(j) not in kept:
                newrow[j] = np.nan
        out[t] = newrow
        return newrow

    replay_book(panels, E, top, max_hold, build_row)
    return out, E
