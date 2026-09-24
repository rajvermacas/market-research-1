"""Candidate: dividend GROWTH / STREAK / CONSISTENCY — the SHAPE of a
name's annual small-jump payout series — as strictly positive cross-
sectional percentile tilts on the CURRENT champion's returned scores
(strategy_lab contract).

Setup in words: the CURRENT champion chain — strat_l20b_spread (CS-spread
tilt sp_lb 4 / sp_w -0.05 post-chain on the strat_l19a_balanced book:
floor-lift fresh-print rank + breadth-tier exposure + wobble gw_w 0.15 +
ids tilt ids_w -0.13 + regime-conditional cap cap_weak/cap_full + listing-
age tilt la_w 0.5 + outrank tilt or_w -0.1; top 15, nse_all, cost 25bps,
split 2022-01-01) — is composed VERBATIM via `from strat_l20b_spread
import score as _champ`, and this file multiplies the scores it returns
by strictly positive cross-sectional percentile tilts built from the
Loop-20 adjustment-factor channel R(t) = adj_close(t)/close(t)
(`_r_factor` imported from strat_l20a_divyield, classed events
`_classed` imported from strat_l21a_actionclass — same 1e-4 event floor,
same 0.02 SMALL/LARGE boundary, never a second copy), with the ONE new
dimension: TIME-SERIES SHAPE of the payout, not its level, count or
recency.

The SMALL class (ac_eps 1e-4 <= step < ac_thr 0.02) is used throughout —
regular cash distributions, excluding the lumpy one-off class whose
mixture made Loop-20's pooled transforms noisy. Per name, split the last
dg_ny*12 months into dg_ny consecutive 12-month blocks ending at t2 (last
bar strictly before months[t]); block y (y = 0 = most recent) covers
(t1_y, t0_y] where t0_y = last bar < months[t - 12*y]:

    A_y = sum of log(1+step) over SMALL events in block y      (annual payout)

and the three signals (per name j, holding month t; every signal NaN
unless the name has factor history AND a bar before months[t - 48] — a
full four-block lookback — else finite):

  GROWTH    gr_j(t) = A_0 - A_1                    (YoY change of the annual
                                                    small-jump magnitude;
                                                    0 for a two-year
                                                    non/zero-payer -> the
                                                    tie-averaged zero block)
  STREAK    st_j(t) = # consecutive most-recent blocks y = 0,1,2,3 with
                      A_y > 0, capped at dg_ny       (years in a row with at
                                                    least one small event)
  DISPERSION cd_j(t)= std(A_0..A_3) / mean(A_0..A_3) over names with
                      mean > 0, else NaN               (coefficient of
                                                    variation: payout SHAPE
                                                    stability; NaN = no
                                                    percentile, never a gate)

Each armed signal is tie-averaged-percentiled across the row's finite
SIGNAL population (_pct_tie — the many tied zeros in gr/st must not be
smeared across the pct axis in column order) and applied as

    tilt = 1 + w * (2 * pct - 1),  |w| < 1
    out[t] = out[t] * tilt        # finite score entries only; NaN stays NaN

arms: dg_gr_w on GROWTH (> 0 favours RISING payers, < 0 favours FALLING
payers), dg_st_w on STREAK (> 0 favours long payout streaks), dg_cd_w on
DISPERSION (< 0 favours consistent annual payouts, > 0 favours volatile
ones).

PIT argument: t0_y and t1_y are the last bars strictly before months[t -
12*y] and every event counted lies <= its block endpoint, which is <= t0_0
< months[t]; distributions after t2 sit outside all blocks and are never
read (only the LEVEL of R, which embeds them, is unused — the backward-
window argument of strat_l20a_divyield/divregular, inherited by their
loader). Rows t < 48 read no window and keep tilt exactly 1.0; names with
no factor history keep tilt 1.0 (re-ranking, never a gate); no row > t is
read. The delegate's PIT is unchanged from strat_l20b_spread.

Import chain: strat_l21a_divgrowth -> strat_l20b_spread.score (CURRENT
champion -> strat_l19a_balanced.score -> strat_l12b_gatefail.score ->
floorhighfastgate/sustaincond/tiershape + wobble -> ids tilt from
strat_l15b_insideday -> mirrored cap -> listage tilt from
strat_l17c_listage -> outrank tilt from strat_l16b_outrank -> CS-spread
tilt) AND -> strat_l21a_divyield (_r_factor, _pct_tie) AND ->
strat_l21a_actionclass (_classed event builder).

Off-switch identity: dg_gr_w = dg_st_w = dg_cd_w = 0.0 (this file's OWN
setdefaults, applied to the params copy BEFORE delegating — Loop-13/14
imported-defaults lesson) skips the whole tilt block before any signal is
built, so `out` is a bitwise copy of strat_l20b_spread's returned scores
at the PASSED keys. Champion keys (incl. sp_*) are PASSED by the caller,
never defaulted here.

Flat-base metric (off-switch must reproduce exactly): train +102.990% /
DD -15.506% / ret-DD 6.642 / H1 +100.204% / H2 +105.682% / fwd +54.057% /
fwd DD -10.381% / full +82.001% / full DD -20.728%.

Hypothesis: Loop-20 read this channel at a SINGLE moment per row (level,
count, recency) — never the multi-year SHAPE of the per-name payout
series. A name raising its dividend for 4 straight years, or paying the
same amount every year, is a different governance object from one whose
decade yield came from a single special, even if their pooled 36-month
size/ count signals are identical (that identity is exactly why the
pooled transforms plateaued at ~100). If payout trajectory/consistency is
information the momentum book lacks, one of the three shape arms moves
the capped frontier; if all three trail, the channel's shape axis closes.

Falsifier (exact): on the champion params below, if EVERY variant in SPACE
trails the flat base on train CAGR AND on calmar, and none improves the
forward window without paying for it on train/DD (Loop-17 rule), then
dividend growth/streak/consistency is closed at this base. Base to beat:
train +102.990% / DD -15.506% / calmar 6.642 / fwd +54.057% / fwd DD
-10.381%. Before ANY promotion: book-composition mechanism — count the
decision months whose picks differ from the champion's (Loop-16 lesson).

NOVELTY STATEMENT (closest registry rows -> the ONE thing that changed):
- research/tested_mechanisms.tsv line 142 strat_l20a_divyield — same
  channel, single-window SIZE level (DEAD-not-promoted 99.79/-15.72/6.35);
- line 143 strat_l20a_divregular — same channel, COUNT/RECENCY in one
  window (DEAD-not-promoted 100.00/-16.43/6.09);
- line 144 strat_l20a2_divcombo — size x count (KEEP-not-promoted
  103.62/-16.56/6.26);
- line 152 strat_l20a3_divspread, line 154 (Loop-21) strat_l21o_liqdiv —
  cross-channel compositions of the same pooled transforms.
NONE of these rows compares a name's payout against ITSELF one year
earlier, counts payout STREAKS, or measures cross-year dispersion — the
ONE thing that changed is the transform CLASS: from level/count/recency of
events to the multi-year SHAPE (growth, streak, dispersion) of annual
small-class sums. Off-channel analogs checked and distinct:
streak/persistence families strat_floorhighrankpersist and
strat_l15b_upstreak (DEAD — price streaks), strat_l17c_eqstate /
"consist" (DEAD — equity-curve state, price), strat_l15b_upstreak
(yield-MA streaks) — no registry row at any base measures growth or
consistency of a corporate-action series.

Keys consumed: this file reads dg_gr_w, dg_st_w, dg_cd_w, dg_ny, dg_thr;
everything else flows to the delegate (champion SPACE incl. sp_*) or the
harness (max_hold 3).

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, cap_full 20,
        cap_weak 11, fast_ma 5, floor_lb 19, gf_lb 12, gf_w 0.0, gw_w 0.15,
        ids_lb 3, ids_w -0.13, la_min 0, la_w 0.5, lookback 12,
        max_dist 0.055, max_hold 3, or_lb 6, or_w -0.1, regime_ma 18,
        sp_frac 0.5, sp_lb 4, sp_w -0.05, sustain_hi 2, sustain_lo 3,
        tier_lo 0.9999, tier_mid 0.9999)
        + dg_ny {4}    annual blocks in the shape window (x 12 months =
                        signals act from row t >= 48 = 2019-01 onward;
                        rows before that keep tilt 1.0 — documented, not
                        tunable in the smoke)
        + dg_thr {0.02} SMALL-class boundary (same pin as
                        strat_l21a_actionclass; regular cash class only)
        + dg_gr_w {0.0, +0.15, -0.15}  YoY growth tilt
        + dg_st_w {0.0, +0.15}         streak tilt
        + dg_cd_w {0.0, -0.15}         dispersion (consistency) tilt
        Documented smoke rows (6): V0 identity (all three 0.0);
        V1 dg_gr_w +0.15 (rising payers); V2 dg_gr_w -0.15 (falling payers
        — sign-consistent with the round-1 non-payer winners);
        V3 dg_st_w +0.15 (long streaks); V4 dg_cd_w -0.15 (consistent
        payers); V5 dg_st_w +0.15 + dg_cd_w -0.15 (the two consistency
        arms composed). Deepen-only (not smoked): dg_ny 3, half-doses.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from strat_l20a_divyield import _pct_tie, _r_factor
from strat_l21a_actionclass import _classed
from strat_l20b_spread import score as _champ

NEEDS_DAILY = True  # the champion delegate's ids/spread terms read the daily panel

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
    "sp_frac": [0.5], "sp_lb": [4], "sp_w": [-0.05],
    # this file's keys
    "dg_ny": [4],                    # annual blocks in the shape window
    "dg_thr": [0.02],                # SMALL-class boundary, pinned
    "dg_gr_w": [0.0, 0.15, -0.15],   # YoY growth tilt; 0.0 = off
    "dg_st_w": [0.0, 0.15],          # streak tilt; 0.0 = off
    "dg_cd_w": [0.0, -0.15],         # dispersion tilt; 0.0 = off
}

_EPOCH = date(1970, 1, 1)
_SHAPE_CACHE: dict = {}


def _shape_signals(months, cols, ny: int, thr: float):
    """(GROWTH, STREAK, DISP) matrices, each (len(months), len(cols)).

    All rows t < 12*ny stay NaN; a name with factor history reads finite
    GROWTH/STREAK from row 12*ny on iff it also has a bar before
    months[t - 12*ny]; DISP additionally requires mean(A_0..A_{ny-1}) > 0
    (a never-payer has no defined coefficient of variation — it keeps tilt
    1.0, it is NOT gated). Annual block y (y = 0 = most recent) covers the
    SMALL-class log-step sum A_y over bar indices in (ix_{y+1}, ix_y],
    where ix_y = last bar strictly before months[t - 12*y].
    """
    series = _r_factor(cols)
    events = _classed(cols, thr)
    T = len(months)
    yr = 12
    k = yr * ny
    grow = np.full((T, len(cols)), np.nan)
    strk = np.full((T, len(cols)), np.nan)
    disp = np.full((T, len(cols)), np.nan)
    # block-y cutoff for row t is months[t - 12y]: slice the full day array
    # at [(k - 12y):(T - 12y)] so element j is months[j + k - 12y]
    ALL = np.array([(m - _EPOCH).days for m in months], dtype=np.int64)
    for j, s in enumerate(cols):
        sr = series.get(s)
        if sr is None:
            continue
        d, _r = sr
        e, st = events[s]
        # last bar STRICTLY before each block-y cutoff, rows k..T-1
        ix = [np.searchsorted(d, ALL[k - yr * y: T - yr * y], side="left") - 1
              for y in range(ny + 1)]   # each of length T - k
        valid = np.ones(T - k, dtype=bool)
        for a in ix:
            valid &= a >= 0
        if not valid.any():
            continue
        big = st >= thr
        eS, stS = e[~big], st[~big]
        if eS.size:
            cs = np.r_[0.0, np.cumsum(np.log1p(stS))]
            n = [np.searchsorted(eS, a, side="right") for a in ix]
            A = [cs[n[y]] - cs[n[y + 1]] for y in range(ny)]
        else:
            # factor history but zero SMALL events: every annual sum is 0
            A = [np.zeros(T - k) for _ in range(ny)]
        g = A[0] - (A[1] if ny > 1 else np.zeros(T - k))
        # streak = length of the leading run of positive blocks (cumprod
        # is 1 while all blocks so far are positive, 0 after the first
        # empty one; sum = consecutive-years-with-a-small-event count)
        pos = np.vstack([(Ay > 0) for Ay in A])
        sst = np.cumprod(pos.astype(np.int64), axis=0).sum(axis=0).astype(float)
        Amat = np.vstack(A)
        mean = Amat.mean(axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            cdv = np.where(mean > 0, Amat.std(axis=0) / mean, np.nan)
        grow[k:, j] = np.where(valid, g, np.nan)
        strk[k:, j] = np.where(valid, sst, np.nan)
        disp[k:, j] = np.where(valid, cdv, np.nan)
    return grow, strk, disp


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating (Loop-13/14 imported-defaults leak):
    # this file's own keys, plus the trio strat_l19a_balanced neutralises
    # itself (belt-and-braces, same values). Champion keys are PASSED by
    # the caller, never defaulted here.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    p.setdefault("dg_ny", 4)
    p.setdefault("dg_thr", 0.02)
    p.setdefault("dg_gr_w", 0.0)
    p.setdefault("dg_st_w", 0.0)
    p.setdefault("dg_cd_w", 0.0)
    out, regime = _champ(panels, p)       # current champion chain, verbatim
    out = np.array(out, dtype=float, copy=True)

    arms_w = (float(p["dg_gr_w"]), float(p["dg_st_w"]), float(p["dg_cd_w"]))
    if all(w == 0.0 for w in arms_w):
        return out, regime                # off-switch: bitwise champion copy

    ny = int(p["dg_ny"])
    thr = float(p["dg_thr"])
    months, cols = panels["months"], panels["cols"]
    key = (tuple(cols), ny, float(thr), len(months))
    if key not in _SHAPE_CACHE:
        _SHAPE_CACHE[key] = _shape_signals(months, cols, ny, thr)
    GROW, STRK, DISP = _SHAPE_CACHE[key]
    k = 12 * ny
    for mat, w in zip((GROW, STRK, DISP), arms_w):
        if w == 0.0:
            continue
        for t in range(k, out.shape[0]):
            sig = mat[t]
            valid = np.isfinite(sig)
            if int(valid.sum()) < 5:
                continue
            pct = _pct_tie(sig[valid])
            tilt = np.ones(out.shape[1])
            tilt[valid] = 1.0 + w * (2.0 * pct - 1.0)   # strictly positive
            fin = np.isfinite(out[t])
            out[t, fin] = out[t, fin] * tilt[fin]        # NaN stays NaN
    return out, regime
