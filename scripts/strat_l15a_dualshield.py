"""Candidate: dual incumbency shield — cap-boundary grandfather (weak months)
plus pick-line band (full months) on the champion chain (strategy_lab
contract).

Setup in words: the champion's pre-cap scores are strat_l12b_gatefail's
tilted lift (imported wholesale). The harness pick rule is replayed
causally, and the book is shielded at BOTH cut lines, which act on disjoint
month types:

  weak/scaled months (E < 1.0): the cap keeps exactly cap_weak finite names,
    but the first `grand_n` of its slots are reserved for INCUMBENTS — held
    names with a finite pre-cap score, passing the px masks, not past
    max_hold, sitting below the score cut, ranked by score +
    grand_tnb * min(months_held, grand_tcap). Unfilled grandfather slots are
    backfilled by the next-best name by score, so the count stays cap_weak.
    (Mirrors strat_l15a_capgrand.)
  full-risk months (E >= 1.0): plain top-cap_full cut, then a rank-space
    BAND on the pick line: an incumbent keeps its seat while its position in
    the capped pool is < book_n + band; a challenger takes the seat only by
    outranking it by more than `band` positions; incumbents beyond the band
    exit as usual; seats fill with the best-ranked challengers, so the book
    size stays min(book_n, pool). (Mirrors strat_l15a_pickband.)

The two stages never interact: the band is vacuous in weak months (pool <=
cap_weak 11 < book_n 15, every finite name is picked) and the grandfather
is inert in full months (plain cap). This file exists to test the STACK in
one candidate — the incumbency-aware book — rather than asking the worker
to infer it from two separate screens.

Hypothesis: each shield alone traded a little train CAGR for drawdown and
held or improved forward (capgrand grand_n 4: 86.11/-16.05/calmar 5.37,
fwd +52.76; pickband band 2: 87.08/-16.42/calmar 5.30, fwd +48.60 — vs
champion 88.14/-17.34/5.08, fwd +49.27). If the jitter churn the shields
remove is the same phenomenon at both lines, the stack should compound the
DD reduction while keeping forward; if weak-month and full-month churn are
different phenomena, the stack inherits only the better half's gain.

Falsifier: if the stack's DD/calmar is no better than the better single
shield, the two effects are one effect measured twice and only the better
single file deserves the worker window; if the stack trails BOTH singles on
calmar, boundary incumbency carries no robust information and the whole
shield family closes at this base.

Import chain: strat_l15a_dualshield -> strat_l12b_gatefail.score (pre-cap
tilted lift, imported never copied) + strat_l13a_concwobble.score (bitwise
off-switch fast path) + strat_l12a_incbonus.replay_book (harness pick-rule
replay machinery). The cap step is MIRRORED inline exactly as
strat_floorhightiershapeconc/strat_l13a_concwobble do; the grandfather and
band stages mirror this designer's own strat_l15a_capgrand /
strat_l15a_pickband build_row logic (book-composition steps, not indicator
math; those files are FROZEN and reused here only as the spec).

PIT argument: causal replay — incumbency and tenure entering month t come
from picks at months < t; the row folded for t reads only pre-cap scores at
t (closes through px[m]) and the existence (not value) of px[t+1] in the
same finiteness mask the harness applies. No forward rows, no daily panel.

Off-switch identity: grand_n = 0 and band = 0 delegate directly to
strat_l13a_concwobble.score — bitwise the champion matrix.

Flat-base metric (off-switch must reproduce exactly, top 15, cost 25bps,
nse_all, split 2022-01-01): train +88.139% / DD -17.339% / calmar 5.083 /
H1 +80.1% / H2 +96.1% / invested 65.5% / fwd +49.274% / fwd DD -14.926% /
fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art is this loop's own strat_l15a_capgrand
and strat_l15a_pickband (both unscreened at delivery) — the ONE thing that
changed is the STACK: incumbency-aware composition applied at both cut
lines of the book in one replayed candidate, which neither single file
expresses (capgrand cannot shield the full-month pick line; pickband
cannot shield the weak-month cap line), and which no inventory entry covers
(the DEAD retention bonus was an unbounded score-space subsidy on a
superseded uncapped base, not a bounded composition change at the two live
cut lines).

book_n MUST equal the harness --top (15 in this loop's trials).

SPACE = champion-chain params (pinned) + grand_n {0, 2, 4},
        grand_tnb {0.0, 0.25}, grand_tcap {6}, band {0, 2, 3}. Worker
        variants, one literal params-json each (champion keys as in the
        flat config):
  {"grand_n": 2, "grand_tnb": 0.0, "grand_tcap": 6, "band": 2}
  {"grand_n": 4, "grand_tnb": 0.0, "grand_tcap": 6, "band": 2}
  {"grand_n": 4, "grand_tnb": 0.25, "grand_tcap": 6, "band": 3}
  {"grand_n": 0, "grand_tnb": 0.0, "grand_tcap": 6, "band": 2}
  {"grand_n": 2, "grand_tnb": 0.0, "grand_tcap": 6, "band": 0}
"""

from __future__ import annotations

import numpy as np

from strat_l12b_gatefail import score as _gf_score
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
    "grand_n": [0, 2, 4],
    "grand_tnb": [0.0, 0.25],
    "grand_tcap": [6],
    "band": [0, 2, 3],
}


def score(panels, params):
    p = dict(params)
    # champion-neutral defaults BEFORE delegating (gatefail's own gf_w 0.05
    # default would silently break the off-switch)
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)

    grand_n = int(params.get("grand_n", 0))
    band = int(params.get("band", 0))
    if grand_n <= 0 and band <= 0:
        return _cw_score(panels, p)  # bitwise champion fast path

    lift, E = _gf_score(panels, p)  # PRE-cap tilted champion scores
    cw = int(params.get("cap_weak", 11))
    cf = int(params.get("cap_full", 20))
    top = int(params.get("book_n", 15))
    max_hold = int(params.get("max_hold", 0) or 0)
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
        cap = cf if E_t >= 1.0 else cw
        # ---- stage 1: the cap, incumbency-aware in scaled months ----
        if fin.size <= cap:
            capped = np.array(row, dtype=float, copy=True)  # champion skips too
        elif E_t >= 1.0 or grand_n <= 0:
            capped = np.array(row, dtype=float, copy=True)
            order = fin[np.argsort(-row[fin], kind="stable")]
            capped[order[cap:]] = np.nan
        else:
            order = fin[np.argsort(-row[fin], kind="stable")]
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
                key = float(row[j]) + grand_tnb * min(t - t0, grand_tcap)
                cands.append((-key, int(j)))
            cands.sort()
            kept |= {j for _, j in cands[:grand_n]}
            slots = cw - len(kept)
            if slots > 0:
                for j in order:  # champion-style backfill by score
                    if slots <= 0:
                        break
                    jj = int(j)
                    if jj not in kept:
                        kept.add(jj)
                        slots -= 1
            capped = np.array(row, dtype=float, copy=True)
            for j in fin:
                if int(j) not in kept:
                    capped[j] = np.nan
        # ---- stage 2: the pick-line band (vacuous when pool < book_n) ----
        if band <= 0:
            out[t] = capped
            return capped
        s = np.array(capped, dtype=float, copy=True)
        ok = np.isfinite(s) & np.isfinite(px[t]) & np.isfinite(px[t + 1])
        s[~ok] = np.nan
        if max_hold:
            for sym, t0 in held.items():
                j = col_idx.get(sym)
                if j is not None and t - t0 >= max_hold:
                    s[j] = np.nan
        idx = np.flatnonzero(np.isfinite(s))
        if E_t <= 0 or idx.size < max(top // 2, 3) or len(held) == 0:
            out[t] = capped
            return capped
        pool = [int(j) for j in idx[np.argsort(-s[idx], kind="stable")]]
        held_js = {col_idx[sym] for sym in held if sym in col_idx}
        kept_inc = {j for j in pool[:top + band] if j in held_js}
        pick = set(kept_inc)
        for j in pool:
            if len(pick) >= top:
                break
            if j in held_js and j not in kept_inc:
                continue  # beyond the band: an exit, however ranked
            pick.add(j)
        for j in np.flatnonzero(np.isfinite(capped)):
            if j not in pick:
                capped[j] = np.nan
        out[t] = capped
        return capped

    replay_book(panels, E, top, max_hold, build_row)
    return out, E
