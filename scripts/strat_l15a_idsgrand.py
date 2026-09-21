"""Candidate: inside-day compression tilt + cap-boundary grandfather, combined
on the champion chain (strategy_lab contract).

Setup in words: the champion chain's pre-cap scores are strat_l12b_gatefail's
tilted lift (floor-lift fresh-print rank among short-trend- and
print-continuity-passing names, breadth-tier exposure, eligibility-wobble
discount — imported wholesale). Two independent book-composition stages are
then folded in, in order:

  stage 1 (signal): the inside-day compression tilt, arithmetic mirrored
    exactly from the FROZEN strat_l15b_insideday.score (this file IMPORTS
    its `_monthly_inside` helper; the loop below is composition glue, not
    signal math). Per daily bar: inside_d = high < prior high AND low >
    prior low; per calendar-month bucket the share of inside days; averaged
    over the `ids_lb` monthly buckets ending at the print month (rows
    t-ilb..t-1, all strictly before months[t]); percentile-ranked among
    finite shares (needs >= 5 valid); tilt = 1 + ids_w * (2*pct - 1);
    out[t] = lift[t] * tilt where lift is finite, NaN kept NaN. Applied
    PRE-CAP, exactly where insideday applies it.
  stage 2 (book): the regime-conditional cap with the weak-month
    incumbency grandfather from this designer's strat_l15a_capgrand
    (mirrored): in scaled months (E < 1.0) the cap still keeps exactly
    cap_weak finite names, but the first `grand_n` slots are reserved for
    held names with a finite tilted score, passing the px masks, not past
    max_hold, ranked by score + grand_tnb * min(months_held, grand_tcap);
    unfilled grandfather slots are backfilled by the next-best name by
    score. Full months keep the plain top-cap_full cut.

Hypothesis: the promoted insideday champion (ids_lb 3 / ids_w -0.15) buys
train (+5.3pp over concwobble) at a small DD cost; the capgrand grandfather
buys DD (-1.3pp) at a small train cost. If the two are independent
composition effects — one reweights WHO ranks near the cut, the other
changes WHO may be cut — the combo could hold the train gain AND the DD
gain, the ledger's best risk-adjusted line. CAVEAT STATED UP FRONT: the two
effects were measured on DIFFERENT books (capgrand on the concwobble book,
insideday on its own ids-tilted book); they are NOT known to be additive.
The grandfather shields the incumbents the ids book happens to have, and
the ids tilt changes which names sit at the cap boundary — the shield's
population is different under the tilt, so the DD gain may shrink, vanish,
or (if the ids book churns more at the boundary) grow.

Falsifier: if every (grand_n, ids_w) cell of the SPACE trails BOTH parents
on the relevant axis — i.e. no cell reaches insideday's train 93.425 while
also reaching capgrand's DD -16.05 — then the tilt and the shield interact
destructively (the tilt's rank changes are exactly what the shield then
freezes in) and the combination is closed; the parents stay as separate
lines.

Import chain: strat_l15a_idsgrand -> _monthly_inside IMPORTED from the
frozen strat_l15b_insideday (md5 3e36eb12944e92efc8c57cbfa307fc5f, not
edited, not copied) + strat_l12b_gatefail.score (pre-cap tilted lift)
+ strat_l13a_concwobble.score (bitwise off-switch fast path)
+ strat_l12a_incbonus.replay_book (harness pick-rule replay machinery).
The cap step is mirrored inline exactly as
strat_floorhightiershapeconc / strat_l13a_concwobble / strat_l15b_insideday
mirror it; the grandfather stage mirrors this designer's own FROZEN
strat_l15a_capgrand build_row (book-composition step, not indicator math).

PIT argument: stage 1 reads only daily buckets with bars strictly before
months[t] — bucket t-1 spans [months[t-1], months[t]) — and percentiles
within the same backward window; rows t < ids_lb keep the raw lift (tilt
untouched), matching the frozen file. Stage 2's replay is causal:
incumbency and tenure entering month t come from picks at months < t; the
row folded for t reads only tilted scores at t (closes through px[m]) and
the existence (not value) of px[t+1] in the same finiteness mask the
harness applies. No forward rows anywhere.

Off-switch identities (each with its expected number; the first is a fast
path that returns strat_l13a_concwobble.score bitwise):
  1. ids_w 0.0 AND grand_n 0 -> the concwobble champion bit-exact:
     train +88.139% / DD -17.339% / calmar 5.083, fwd +49.274% / -14.926%
     (top 15, 25bps, nse_all, split 2022-01-01).
  2. grand_n 0 with ids on (ids_lb 3 / ids_w -0.15) -> the promoted
     insideday champion: train +93.425% / DD -17.032% / calmar 5.49,
     fwd +52.906% / -12.311%.
  3. ids_w 0.0 with grandfather on (grand_n 4) -> this designer's capgrand:
     train +86.111% / DD -16.048% / calmar 5.366, fwd +52.757% / -14.926%.
Identity 2 requires the tilt loop above to be arithmetically identical to
the frozen file's (it is: same buckets, same percentile, same guards) and
the cap mirror to be identical (it is). Identity 3 is capgrand's own
verified number. Flat-base metric = identity 1.

NOVELTY STATEMENT: closest prior art is this designer's strat_l15a_capgrand
(Loop-15, weak-month cap grandfather) and this loop's promoted
strat_l15b_insideday (inside-day compression tilt); the ONE thing changed
is the COMBINATION — the ids tilt applied pre-cap AND the incumbency
grandfather applied at the cap, in one replayed candidate. Neither parent
expresses the other's stage, and no inventory entry combines a daily-tape
tilt with book-state shielding. Explicit non-additivity caveat: the parents
were measured on different books, so the cells below are the first test of
whether the train gain and the DD gain coexist.

NEEDS_DAILY = True: `_monthly_inside` consumes the daily long panel the
harness loads for this module (high/low only, via the imported helper).

book_n MUST equal the harness --top (15 in this loop's trials).
NOTE imported defaults leak: gatefail's own gf_w default (0.05) would leak
into every path — this file setdefaults gf_w 0.0 / gw_w 0.0 / gf_lb 12
BEFORE delegating, exactly as its parents do.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.13; max_hold 3 is a HARNESS
        key passed via params-json) + this file's cells, grand_tnb 0.0 /
        grand_tcap 6 / ids_lb 3 / book_n 15 throughout unless stated:
  {"grand_n": 0, "ids_w": 0.0}      identity 1 (champion)
  {"grand_n": 0, "ids_w": -0.15}    identity 2 (insideday champion)
  {"grand_n": 4, "ids_w": 0.0}      identity 3 (capgrand)
  {"grand_n": 2, "ids_w": -0.15}    combo, mild grandfather
  {"grand_n": 4, "ids_w": -0.15}    combo, full grandfather (headline cell)
  {"grand_n": 2, "grand_tnb": 0.25, "ids_w": -0.15}   tenure-tilted combo
"""

from __future__ import annotations

import warnings

import numpy as np

from strat_l12b_gatefail import score as _gf_score
from strat_l13a_concwobble import score as _cw_score
from strat_l12a_incbonus import replay_book
from strat_l15b_insideday import _monthly_inside  # imported from the FROZEN file

NEEDS_DAILY = True
SPACE = {
    # champion keys (pinned, docs only)
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
    # this file's keys
    "book_n": [15],
    "grand_n": [0, 2, 4],
    "grand_tnb": [0.0, 0.25],
    "grand_tcap": [6],
    "ids_lb": [3],
    "ids_w": [0.0, -0.15],
}


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating: gatefail's own gf_w default (0.05)
    # would leak into every path. Champion values are passed, not defaulted.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)

    ids_w = float(params.get("ids_w", 0.0))
    grand_n = int(params.get("grand_n", 0))
    if ids_w == 0.0 and grand_n <= 0:
        return _cw_score(panels, p)  # identity 1: bitwise champion fast path

    lift, exposure = _gf_score(panels, p)  # PRE-cap tilted champion scores
    out = np.array(lift, dtype=float, copy=True)

    # ---- stage 1: inside-day compression tilt (mirror of the FROZEN
    # strat_l15b_insideday.score loop; `_monthly_inside` is imported) ----
    if ids_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        ilb = int(params.get("ids_lb", 3))
        IDS = _monthly_inside(daily, months, cols)
        for t in range(1, lift.shape[0]):
            lo = t - ilb
            if lo < 0:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                share = np.nanmean(IDS[lo:t], axis=0)
            valid = np.isfinite(share)
            n = int(valid.sum())
            tilt = np.ones(lift.shape[1])
            if n >= 5:
                sv = share[valid]
                order = np.argsort(sv, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + ids_w * (2.0 * pct - 1.0)
            ok = np.isfinite(lift[t])
            out[t] = np.where(ok, lift[t] * tilt, np.nan)

    # ---- stage 2: cap with the weak-month incumbency grandfather (mirror
    # of this designer's strat_l15a_capgrand build_row), replayed causally ----
    cw = int(params.get("cap_weak", 11))
    cf = int(params.get("cap_full", 20))
    top = int(params.get("book_n", 15))
    max_hold = int(params.get("max_hold", 0) or 0)
    grand_tnb = float(params.get("grand_tnb", 0.0))
    grand_tcap = int(params.get("grand_tcap", 6))
    px, cols = panels["px"], panels["cols"]
    col_idx = {s: j for j, s in enumerate(cols)}
    E = np.asarray(exposure, dtype=float)

    def build_row(t, held):
        row = out[t]  # tilted lift (pre-cap)
        fin = np.flatnonzero(np.isfinite(row))
        if fin.size == 0:
            return row
        E_t = float(np.clip(E[t], 0.0, 1.0))
        cap = cf if E_t >= 1.0 else cw
        if fin.size <= cap:
            return row  # the mirrored cap skips too: bitwise identical
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
        newrow = np.array(row, dtype=float, copy=True)
        for j in fin:
            if int(j) not in kept:
                newrow[j] = np.nan
        out[t] = newrow
        return newrow

    replay_book(panels, E, top, max_hold, build_row)
    return out, E
