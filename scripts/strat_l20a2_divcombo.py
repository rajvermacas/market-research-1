"""Candidate: SIZE x TIMING composition of the dividend / corporate-action
channel — both Loop-20 round-1 transforms re-expressed and multiplied onto the
CURRENT champion's returned scores (strategy_lab contract).

Setup in words: the CURRENT champion chain, strat_l19a_balanced (floor-lift
fresh-print rank + breadth-tier exposure + eligibility wobble gw_w 0.15 +
inside-day tilt ids_w -0.13 + regime-conditional cap cap_weak/cap_full +
listing-age tilt la_w 0.5 + cross-sectional outrank tilt or_w -0.1), is called
UNCHANGED through `from strat_l19a_balanced import score as _l19`, and this
file multiplies the scores it returns by one or two more strictly positive,
cross-sectionally rank-based multipliers built from the corporate-action
adjustment factor R(t) = adj_close(t)/close(t) — the round-1 channel:

  (a) SIZE / magnitude transform, source strat_l20a_divyield (Loop-20 round 1,
      md5 2fdd06525da0ea177b1f5a3b6dc228aa): the trailing dividend-factor
      change over (t - dy_lb, t],
          y_j(t) = clip( log( R(t2)/R(t1) ), 0, 0.01 * dy_lb )     [winsorised]
      with t2/t1 = last bars strictly before months[t] / months[t - dy_lb],
      tie-averaged cross-sectional percentile, tilt = 1 + dy_w*(2pct - 1).
      Winning round-1 arm: dy_lb 36 / dy_w -0.15 (FAVOUR NON-PAYERS).

  (b) TIMING transforms, source strat_l20a_divregular (Loop-20 round 1, md5
      a6e0814500ba8bb3a6742c038ff983f7), same channel, event timeline instead
      of event size (event iff a daily R-step > dv_eps 1e-4; pinned dv_eps
      1e-4 / dr_cap 60 months, windows in dv_lb months):
          count  : n_j(t) = #events in (t1, t2]      tilt = 1 + dv_w*(2pct-1)
          recency: rec_j(t) = months since last event <= t2, censored at
                   dr_cap (never-fired = dr_cap)     tilt = 1 + dr_w*(2pct-1)
      Round-1 arms: count dv_w -0.15 (FAVOUR INFREQUENT, +100.002 train) and
      recency dr_w +0.15 (FAVOUR STALE, mid-pack, ~flat at 98.653).

Both transforms are re-used NOT copied: `_trail_yield` is imported from
strat_l20a_divyield and `_signals` / `_event_idx` from strat_l20a_divregular
(exactly as strat_l19a_balanced imports `_monthly_inside` from
strat_l15b_insideday), so the windows, winsorisation, event threshold,
censoring and tie-averaged percentile (`_pct_tie`) are bit-identical to the
files that produced the parent numbers. What this file owns is only the
COMPOSITION of the tilt applications on the champion's returned scores.

Formula citations:
 - Back-adjustment identity (both round-1 files, S&P/MSCI price-vs-total-
   return convention): adj_close(t) = close(t) * Prod_{ex-dates d > t} A_d,
   so log R(t2)/R(t1) = Sum_{t1 < d <= t2} -log A_d ~= trailing dividend
   yield over the window (SIZE), and each factor A_d is one upward step of
   R (TIMING).
 - Composition forms:
     mode "prod" (default): out[t] = out[t] * tilt_a * tilt_b
         — exactly the round-1 application repeated, one tilt per source,
         each percentile over that source's OWN finite signal population,
         each applied to the finite score entries only.
     mode "avg" (documented one-parameter alternative): each source's
         percentile is ORIENTED so that high = the direction its registered
         weight favours (sign(dy_w)/sign(dv_w)/sign(dr_w), magnitude ignored),
         the oriented percentiles are AVERAGED over names where every needed
         signal is finite, and ONE weight c_w is applied:
             pct_comb = mean_i ( sign_i > 0 ? pct_i : 1 - pct_i )
             tilt     = 1 + c_w * (2 * pct_comb - 1)
         The avg form removes the multiplicative interaction term
         (w_a*w_b*(2pct_a-1)*(2pct_b-1) that prod carries) and keeps the
         tilt bounded in [1-|c_w|, 1+|c_w|] no matter how many sources
         stack — the clean way to compose N rank tilts into one parameter.

PIT argument: unchanged from the sources, which this file inherits verbatim
by calling their signal builders. The LEVEL of R is not point-in-time clean
(it embeds every future dividend); every signal here is a trailing window
ending at the last bar strictly before months[t], with the start cutoff at the
last bar strictly before months[t - k] < months[t], so only distributions
public at the decision enter. Rows t < max(window) are untouched; NaN scores
stay NaN; every multiplier is strictly positive for |weight| < 1 and |c_w| < 1.

Import chain: strat_l20a2_divcombo -> strat_l19a_balanced.score (champion:
-> strat_l12b_gatefail -> floorhighfastgate/floorhighsustaincond/
floorhightiershape + wobble -> ids tilt from strat_l15b_insideday -> mirrored
cap -> listage tilt from strat_l17c_listage -> outrank tilt from
strat_l16b_outrank -> final no-op cap) AND -> strat_l20a_divyield
(_trail_yield, _pct_tie) AND -> strat_l20a_divregular (_signals,
_event_idx).

Off-switch identity: with the neutral defaults set via setdefault BEFORE
delegating (gf_lb 12 / gf_w 0.0 / gw_w 0.0 — the values
strat_l19a_balanced sets itself, Loop-14 rule; plus c_mode "prod", c_w 0.0,
dy_w 0.0, dv_w 0.0, dr_w 0.0), NO source is armed, so the function returns
`_l19(panels, p)` untouched — bit-exact champion scores. (In mode "prod" the
file is armed iff any of dy_w/dv_w/dr_w != 0; in mode "avg" iff c_w != 0 and
at least one source weight is non-zero for orientation. All zero -> identity.)

Flat-base metric (off-switch must reproduce exactly, champion params passed
by the caller): train +98.682% / DD -15.506% / calmar 6.364 / H1 +95.295% /
H2 +101.966% / fwd +53.148% / fwd DD -10.403% / full +79.237% / -20.728%.

Pre-registered question (Loop-20 round 2, bounded composition, not a new
channel hunt): does SIZE and TIMING of the SAME channel STACK — the combo
beating BOTH parents on train while holding DD and forward — or does it
SATURATE / INTERFERE? Parents on this base:
    size   dy_lb 36 / dy_w -0.15      : train +99.789 / -15.719 / 6.348,
                                        fwd +55.012 / -10.381
    count  dv_lb 24 / dv_w -0.15      : train +100.002 / -16.429 / 6.087,
                                        fwd +54.472 / -10.381
    base (off-switch)                 : train +98.682 / -15.506 / 6.364,
                                        fwd +53.148 / -10.403
Verdict rules, fixed before the runs:
    STACK     : train > 100.002 (beats BOTH parents) AND calmar >= 6.348
                (best parent) AND fwd >= 55.012 (best parent) AND
                fwd DD >= -10.403 (no worse than base) AND
                train DD >= -16.429 (no worse than the worse parent).
    SATURATE  : train lands between base and best parent (or within +-0.3pp
                of the best parent) without the simultaneous calmar/forward
                improvement — the second transform buys nothing the first
                did not already buy (signals are the same field).
    INTERFERE : train <= base (98.682), or train below BOTH parents with
                calmar < 6.087 / DD worse than -16.429 — a negative
                interaction between two tilts of one channel.
Prior expectation, cited: Loop-15's dualshield and ids x grandfather stacks
were SUB-ADDITIVE ("one book-composition channel, not two"), so saturation is
the favoured prior; the round-1 sign consistency (both winning arms favour
non-payers) is the reason stacking is plausible at all.

Falsification test (exact): if no prod cell meets STACK and the best prod
cell sits at or below the better parent on train, the two transforms of this
channel do not stack at this base — the composition closes as a negative and
NO second file is written.

NOVELTY STATEMENT: closest prior art is my own round-1 pair —
strat_l20a_divyield (channel SIZE) and strat_l20a_divregular (channel
TIMING) — both on this same new adj_close/close channel, both bit-exact
off-switch identities, NEITHER of which measured the other's transform
present. There is still no prior art on this DATA CHANNEL anywhere else in
`research/tested_mechanisms.tsv` (zero dividend/adj/corporate/payout rows,
verified by grep in round 1); the nearest off-channel families remain the
attribute axis (strat_l17c_listage LIVE; faceval/idxflag/seriesgate DEAD) and
the recency/base-duration price families (breakrec/floortrendq/highbase/
timesince DEAD). The ONE thing that changed vs round 1: the COMPOSITION —
two distinct transforms (magnitude vs timing) of one new channel applied
together on the champion chain, answering stack-vs-saturate. This is a
pre-registered composition question from the Loop-20 round-2 brief, not a
claim of a third channel; a "same signal, new weights" re-shape is NOT what
is being claimed — the parents were never measured jointly.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13,
        la_min 0, la_w 0.5, or_lb 6, or_w -0.1; max_hold 3 is a HARNESS key)
        + c_mode {"prod", "avg"}   composition form (default "prod")
        + dy_lb {36}               SIZE window (round-1 winning window)
        + dy_w  {0.0, -0.15, -0.10} SIZE tilt weight (0 = off; negative
                                    favours NON-payers, the round-1 winner)
        + dv_lb {24}               TIMING window (round-1 window)
        + dv_w  {0.0, -0.15, -0.10} COUNT tilt weight (negative favours
                                    infrequent payers, round-1 winner)
        + dr_w  {0.0, +0.15}       RECENCY tilt weight (positive favours
                                    STALE payers, the mid-pack round-1 arm)
        + c_w   {0.0, 0.15}        single weight for mode "avg" only
        Pinned: dv_eps 1e-4, dr_cap 60 (imported behaviour). The round-1
        eligibility gates (dy_min / dv_min) are deliberately NOT carried:
        both were measured decisively destructive in round 1 (train +3.2% /
        +8.2%, invested 7% / 24%) — gates closed, not re-armed.
        Documented variant rows: identity; A = (36,-0.15) x (count,-0.15)
        prod; B = (36,-0.15) x (recency,+0.15) prod; A-avg and B-avg (mode
        "avg", c_w 0.15, parent signs for orientation); plateau pair around
        A with EACH weight scaled by 0.67 -> (-0.10, -0.10), plus the
        one-at-a-time cells (-0.10, -0.15) and (-0.15, -0.10) to see which
        axis carries the composition.
"""

from __future__ import annotations

import numpy as np

from strat_l19a_balanced import score as _l19
from strat_l20a_divregular import _signals
from strat_l20a_divyield import _pct_tie, _trail_yield

NEEDS_DAILY = True  # the champion delegate's ids term reads the daily panel

SPACE = {
    # champion keys (pinned, docs only)
    "b_hi": [0.69], "b_lo": [0.45], "b_mid": [0.55],
    "floor_lb": [19], "lookback": [12], "max_dist": [0.055],
    "regime_ma": [18], "fast_ma": [5],
    "sustain_lo": [3], "sustain_hi": [2],
    "tier_lo": [0.9999], "tier_mid": [0.9999],
    "cap_weak": [11], "cap_full": [20],
    "gf_lb": [12], "gf_w": [0.0], "gw_w": [0.15],
    "ids_lb": [3], "ids_w": [-0.13],
    "la_min": [0], "la_w": [0.5], "or_lb": [6], "or_w": [-0.1],
    # this file's keys
    "c_mode": ["prod", "avg"],        # composition form; default "prod"
    "dy_lb": [36],                    # SIZE window (round-1 winner)
    "dy_w": [0.0, -0.15, -0.10],      # SIZE tilt; negative favours non-payers
    "dv_lb": [24],                    # TIMING window (round-1 window)
    "dv_w": [0.0, -0.15, -0.10],      # COUNT tilt; negative favours infrequent
    "dr_w": [0.0, 0.15],              # RECENCY tilt; positive favours stale
    "c_w": [0.0, 0.15],               # single weight, mode "avg" only
}


def _tilt_row(sig: np.ndarray, w: float) -> np.ndarray | None:
    """Round-1 tilt row for one source: tie-averaged percentile over the
    row's finite SIGNAL population, expressed as a full-length vector that is
    1.0 outside the signal mask (sources: strat_l20a_divyield.score /
    strat_l20a_divregular.score application blocks). None if the signal
    population is too small to rank."""
    valid = np.isfinite(sig)
    if int(valid.sum()) < 5:
        return None
    pct = _pct_tie(sig[valid])
    tilt = np.ones(sig.size)
    tilt[valid] = 1.0 + w * (2.0 * pct - 1.0)   # strictly positive, |w| < 1
    return tilt


def _pct_row(sig: np.ndarray) -> np.ndarray | None:
    """Oriented-free percentile row (NaN outside the signal mask), for the
    mode-"avg" mean-percentile form."""
    valid = np.isfinite(sig)
    if int(valid.sum()) < 5:
        return None
    pct = np.full(sig.size, np.nan)
    pct[valid] = _pct_tie(sig[valid])
    return pct


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating (Loop-14 imported-defaults leak):
    # the same three strat_l19a_balanced sets itself, plus this file's keys.
    # Champion keys (gw_w 0.15, ids_w -0.13, la_w 0.5, or_w -0.1, ...) are
    # PASSED by the caller, never defaulted here.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    p.setdefault("c_mode", "prod")
    p.setdefault("c_w", 0.0)
    p.setdefault("dy_lb", 36)
    p.setdefault("dy_w", 0.0)
    p.setdefault("dv_lb", 24)
    p.setdefault("dv_w", 0.0)
    p.setdefault("dr_w", 0.0)
    out, regime = _l19(panels, p)          # champion scores, cap included
    out = np.array(out, dtype=float, copy=True)

    mode = str(p["c_mode"])
    dy_w = float(p["dy_w"])
    dv_w = float(p["dv_w"])
    dr_w = float(p["dr_w"])
    c_w = float(p["c_w"])

    # sources: (name, registered round-1 weight). In mode "prod" the weight
    # is the magnitude; in mode "avg" only its SIGN (direction) is read and
    # the single magnitude c_w is applied to the mean oriented percentile.
    sources = []
    if dy_w != 0.0:
        sources.append(("size", dy_w))
    if dv_w != 0.0:
        sources.append(("count", dv_w))
    if dr_w != 0.0:
        sources.append(("rec", dr_w))
    if mode == "avg":
        # c_w is the ONLY magnitude in avg mode; parent signs give direction
        armed = c_w != 0.0 and len(sources) > 0
    else:
        # prod mode ignores c_w (avg-only key, documented): armed by parents
        armed = len(sources) > 0
    if not armed:
        return out, regime                  # off-switch: bit-exact identity

    months, cols = panels["months"], panels["cols"]
    T = out.shape[0]

    # --- signal matrices, built only for armed sources, via the ROUND-1
    # builders (identical windows / winsorisation / eps / censoring) ---
    mats: dict = {}
    wins: dict = {}
    if any(n == "size" for n, _ in sources):
        mats["size"] = _trail_yield(months, cols, int(p["dy_lb"]))
        wins["size"] = int(p["dy_lb"])
    if any(n in ("count", "rec") for n, _ in sources):
        cnt, rec = _signals(months, cols, int(p["dv_lb"]))
        mats["count"], mats["rec"] = cnt, rec
        wins["count"] = wins["rec"] = int(p["dv_lb"])

    if mode == "prod":
        # repeat each round-1 file's own application block, in sequence
        for name, w in sources:
            k = wins[name]
            M = mats[name]
            for t in range(k, T):
                tilt = _tilt_row(M[t], w)
                if tilt is None:
                    continue
                fin = np.isfinite(out[t])
                out[t, fin] = out[t, fin] * tilt[fin]   # NaN stays NaN
        return out, regime

    # ---- mode "avg": one weight on the mean ORIENTED percentile ----
    k = max(wins[n] for n, _ in sources)
    for t in range(k, T):
        oriented, all_ok = [], np.ones(out.shape[1], dtype=bool)
        for name, w in sources:
            pct = _pct_row(mats[name][t])
            if pct is None:
                oriented = None
                break
            # orient so high = the direction this source's weight favours
            oriented.append(pct if w > 0 else 1.0 - pct)  # NaN -> NaN
            all_ok &= np.isfinite(pct)
        if oriented is None or int(all_ok.sum()) < 5:
            continue
        mean_pct = sum(oriented) / len(oriented)
        tilt = np.ones(out.shape[1])
        tilt[all_ok] = 1.0 + c_w * (2.0 * mean_pct[all_ok] - 1.0)
        fin = np.isfinite(out[t])
        out[t, fin] = out[t, fin] * tilt[fin]             # NaN stays NaN
    return out, regime
