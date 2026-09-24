"""Candidate: spread relative to the name's OWN history (z-score / own-trailing
percentile) percentile tilt, champion level term kept underneath (contract).

Setup in words: the CURRENT champion chain — strat_l20b_spread (strat_l19a_balanced
gatefail lift -> ids tilt -> cap -> age tilt -> outrank tilt -> cap, then the
Corwin-Schultz spread-LEVEL cross-sectional percentile tilt at sp_lb 4 /
sp_w -0.05 / sp_frac 0.5) is composed VERBATIM via
`from strat_l20b_spread import score as _l20` with the champion's sp keys
PINNED underneath (setdefault to 4 / -0.05 / 0.5; a caller PASSING sp_w 0.0 —
the control cell — wins, setdefault never overrides). On top of the champion's
returned scores this file applies ONE new term: a cross-sectional percentile
tilt on how the name's CURRENT spread level sits relative to THAT NAME'S OWN
past — "abnormally tight for this name" / "abnormally wide for this name".

Level series (same estimator and window as the champion's level term):

    SPR[t, j] = _monthly_spread (strat_l20b_spread) monthly CS spread buckets
    L[t, j]   = nanmean(SPR[t-sp_lb : t, j]) over buckets with count >=
                ceil(sp_frac * sp_lb)          # the champion's level series

Own-history normalisation at decision row t (history is STRICTLY prior rows):

    hist = { L[k, j] : k in [t - sz_lb, t - 1], finite }
    mode "z":      score[t,j] = (L[t,j] - mean(hist)) / std(hist)
                   # requires >= max(3, ceil(sz_frac * sz_lb)) finite history
                   # points AND std(hist) > 0 (a flat own history earns no z)
    mode "ownpct": score[t,j] = (#hist < L[t] + 0.5 * #hist == L[t]) / n
                   # own-trailing percentile in [0,1]; ties averaged;
                   # requires >= max(3, ceil(sz_frac * sz_lb)) points

score is then percentile-ranked CROSS-SECTIONALLY among names with a finite
score (n >= 5), and applied as:

    tilt[t] = 1 + sz_w * (2 * pct - 1)     # pct in [0,1], |sz_w| < 1
    out[t]  = out[t] * tilt                # finite entries only, NaN stays NaN

Rows t < sp_lb + sz_lb are untouched (no own history yet); names failing the
coverage guard or with a zero-variance history keep tilt exactly 1.0 (a thin
history earns no score, it does not lose eligibility — re-ranking, never a
gate); NaN stays NaN; |sz_w| < 1 keeps the multiplier strictly positive.
Both signs are first-class: sz_w < 0 favours names whose spread is tight
relative to THEIR OWN norm (abnormally tight NOW — improving execution),
sz_w > 0 favours names abnormally wide relative to themselves (deteriorating
execution / premium story).

Hypothesis: the champion's level tilt is a CROSS-SECTIONAL statement — a
structurally wide-spread small-cap always ranks badly against a large-cap.
This file's score is WITHIN-name: it asks whether a name is tighter or wider
than its own norm, which is invariant to its standing level. A wide name that
has genuinely tightened (new sponsor base, better float) scores high here while
still ranking low on the champion's level — so the two can disagree by
construction, and the BOTH-terms-active cells (sp_w -0.05 + sz_w != 0) are the
direct test of "does the dynamic add anything BEYOND the level". The sp_w 0.0
control cell shows the own-history term alone. If every active cell trails the
flat base, own-history normalisation adds nothing beyond the level and the
axis closes.

Falsifier: if ALL four SPACE variants trail the flat base — train +102.990% /
DD -15.506% / ret-DD 6.642 / fwd +54.057% / fwd DD -10.381% — on train CAGR
with no offsetting improvement in drawdown or forward (operationally: the
harness keep rule never fires on the smoke ledger; per the Loop-17 rule a train
gain bought with wider DD or a forward collapse is an ARTIFACT), then the
spread-own-history axis closes on the champion base. Before ANY promotion:
this tilt re-orders the capped pool (a book-composition mechanism) — count the
decision months where its picks differ from the champion's (Loop-16 lesson;
the champion level term's footprint was 23/139).

NOVELTY STATEMENT (closest registry rows -> the ONE thing that changed):
- research/tested_mechanisms.tsv line 146 strat_l20b_spread — the CLOSEST
  prior art and this file's own base: Corwin-Schultz spread LEVEL, a
  CROSS-SECTIONAL percentile (where the name sits vs the panel), PROMOTED
  champion. ONE THING CHANGED: cross-sectional LEVEL -> OWN-HISTORY
  normalisation (z-score / own trailing percentile of the same level series
  against the name's own past). Same estimator, same tilt machinery, a
  different reference frame — the resulting cross-sectional order differs
  whenever standing levels and own-relative moves disagree.
- research/tested_mechanisms.tsv line 107 strat_l15b_rngcomp (self-normalised
  range COMPRESSION vs own history, DEAD on the ids base 69.5-75.8) and line
  112 strat_l16a_idsrng (its ids-base retest, DEAD 69.5-75.8) — the nearest
  own-history-normalisation precedent in the registry: same FORM class,
  different SIGNAL (intraday range, a volatility proxy the vol-level family
  lines 6/96 also falsified) and a base (ids champion) that predates the
  spread channel entirely. Spread is a microstructure COST, not symmetric
  risk; no registry row has ever normalised a spread against a name's own
  history.
- research/tested_mechanisms.tsv line 70 strat_liqtrend (legacy liquidity
  trend, DEAD): volume/turnover liquidity, hard gate, old chain — not a
  spread estimator, not a normalisation, not this base.

Import chain: strat_l21b_spreadz -> strat_l20b_spread.score (the CURRENT
champion: CS level tilt on the l19 chain) -> strat_l19a_balanced ->
strat_l12b_gatefail + strat_l15b_insideday. This file adds only the
post-chain own-history tilt; the CS estimator is imported from
strat_l20b_spread (`_monthly_spread`), never copied.

PIT argument: bucket k of _monthly_spread contains only pairs whose CARRYING
(second) bar falls in [months[k], months[k+1]); L[t] reads buckets
[t-sp_lb, t-1] (all date < months[t]) and the own history reads rows
[t - sz_lb, t - 1] — strictly PRIOR decision rows, each of which only used
buckets before its own month. The score at row t therefore combines the
current level (knowable at t) with own history entirely before t; the
percentile at row t uses only that row's cross-section; rows
t < sp_lb + sz_lb are untouched; no row > t is read anywhere. The delegate's
PIT is unchanged from strat_l20b_spread (ids: daily bars strictly before
months[t]; age: static listing_date; outrank: px[t-or_lb]..px[t]; cap: month-t
ranks; level: buckets t-4..t-1).

Off-switch identity: sz_w = 0.0 (this file's OWN setdefault, applied to the
params copy BEFORE delegating — Loop-13/14 imported-default lesson) skips the
own-history block entirely and returns the delegate's scores untouched, so
`out` is bitwise strat_l20b_spread's returned scores at the PASSED keys —
with the sp keys pinned to the champion dose above, that is the champion
bit-exactly. Champion keys are ALWAYS PASSED by the caller, never defaulted
here: the delegate's parents read la_w/or_w/gw_w/ids_w via .get with 0.0
defaults, so a missing key would silently de-tune the base.

Flat-base metric (off-switch must reproduce exactly): train +102.990% /
DD -15.506% / ret-DD 6.642 / H1 +100.204% / H2 +105.682% / fwd +54.057% /
fwd DD -10.381% / full +82.001% / full DD -20.728%.

Keys consumed: this file reads sz_w, sz_lb, sz_frac, sz_mode, and (for the
level series it normalises) sp_lb, sp_frac — the sp keys pinned to the
champion dose via setdefault. Everything else in params-json flows through to
the delegate (all SPACE champion keys incl. sp_w, which the control cell sets
to 0.0) or is read by the harness (max_hold 3).

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13,
        la_min 0, la_w 0.5, or_lb 6, or_w -0.1, sp_lb 4, sp_w -0.05,
        sp_frac 0.5; max_hold 3 is a HARNESS key passed via params-json)
        + FIVE documented cells, one literal trial each (smoke = all five):
          1. OFF-SWITCH identity: canonical champion JSON (sz_w absent ->
             0.0) — must reproduce the flat-base metric bit-exactly
          2. BOTH terms active:  sz_lb 24, sz_mode "z", sz_w -0.05
             (two years of own history; abnormally-tight-for-this-name)
          3. BOTH terms active:  sz_lb 24, sz_mode "z", sz_w +0.05 (other
             sign: abnormally-wide-for-this-name)
          4. BOTH terms active:  sz_lb 24, sz_mode "ownpct", sz_w -0.05
             (the alternate normaliser: current level as a percentile of
             its own past — robust to the heavy right tail of spread
             histories that inflates a mean/std z)
          5. CONTROL (own-history alone): sz_lb 24, sz_mode "z",
             sz_w -0.05, sp_w 0.0 — the champion level term OFF
        + sz_mode is "z" (default) or "ownpct" (both shown above); sz_lb is
          pinned at 24 in the smoke (two years of own history) — a 60-month
          depth axis is documented for a follow-up pass
        + sz_frac [0.5] pinned (a name needs >= ceil(0.5 * sz_lb) finite
          own-history points to earn a score; otherwise tilt stays 1.0).
"""

from __future__ import annotations

import warnings

import numpy as np

from strat_l20b_spread import _monthly_spread, score as _l20

NEEDS_DAILY = True  # the champion chain (ids term + CS spread) reads daily

SPACE = {
    # champion keys (pinned, docs only)
    "b_hi": [0.69], "b_lo": [0.45], "b_mid": [0.55], "floor_lb": [19],
    "lookback": [12], "max_dist": [0.055], "regime_ma": [18], "fast_ma": [5],
    "sustain_lo": [3], "sustain_hi": [2], "tier_lo": [0.9999],
    "tier_mid": [0.9999], "cap_weak": [11], "cap_full": [20], "gf_lb": [12],
    "gf_w": [0.0], "gw_w": [0.15], "ids_lb": [3], "ids_w": [-0.13],
    "la_min": [0], "la_w": [0.5], "or_lb": [6], "or_w": [-0.1],
    "sp_lb": [4], "sp_w": [-0.05, 0.0],  # 0.0 = the control cell only
    "sp_frac": [0.5],
    # this file's keys
    "sz_lb": [24, 60],
    "sz_mode": ["z", "ownpct"],
    "sz_w": [0.05, -0.05],
    "sz_frac": [0.5],
}


def _level_series(SPR: np.ndarray, slb: int, need: int) -> np.ndarray:
    """L[t] = nanmean(SPR[t-slb:t]) over buckets with >= need finite entries —
    the SAME trailing-mean level series the champion's level term ranks on
    (strat_l20b_spread score(), re-expressed here as a series so it can be
    normalised against its own history; NaN where the window is thin)."""
    L = np.full(SPR.shape, np.nan)
    for t in range(slb, SPR.shape[0]):
        win = SPR[t - slb : t]
        cnt = np.isfinite(win).sum(axis=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            m = np.nanmean(win, axis=0)
        L[t] = np.where(cnt >= need, m, np.nan)
    return L


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating (Loop-13/14 imported-default lesson):
    # this file's own keys default to the off-switch / pinned values; the
    # champion's sp keys are pinned to their champion dose so the composed
    # base IS the champion even if the caller omits them (a PASSED key —
    # e.g. the control cell's sp_w 0.0 — always wins over setdefault).
    p.setdefault("sz_w", 0.0)
    p.setdefault("sz_lb", 24)
    p.setdefault("sz_frac", 0.5)
    p.setdefault("sz_mode", "z")
    p.setdefault("sp_lb", 4)
    p.setdefault("sp_w", -0.05)
    p.setdefault("sp_frac", 0.5)
    out, regime = _l20(panels, p)  # current champion chain + level, verbatim
    out = np.array(out, dtype=float, copy=True)

    sz_w = float(p["sz_w"])
    if sz_w == 0.0:
        return out, regime  # off-switch: bitwise copy of the champion

    daily, months, cols = panels["daily"], panels["months"], panels["cols"]
    slb = int(p["sp_lb"])
    zlb = int(p["sz_lb"])
    mode = str(p["sz_mode"])
    if mode not in ("z", "ownpct"):
        raise ValueError(f"sz_mode must be 'z' or 'ownpct', got {mode!r}")
    need_win = max(2, int(np.ceil(float(p["sp_frac"]) * slb)))
    need_own = max(3, int(np.ceil(float(p["sz_frac"]) * zlb)))
    SPR = _monthly_spread(daily, months, cols)  # imported estimator
    L = _level_series(SPR, slb, need_win)
    for t in range(slb + zlb, out.shape[0]):
        hist_all = L[t - zlb : t]        # strictly PRIOR decision rows
        cur = L[t]                       # current level, buckets < months[t]
        score_x = np.full(out.shape[1], np.nan)
        for j in range(out.shape[1]):
            cj = cur[j]
            if not np.isfinite(cj):
                continue
            h = hist_all[:, j]
            h = h[np.isfinite(h)]
            if h.size < need_own:
                continue                 # thin own history: no score, tilt 1.0
            if mode == "z":
                sd = float(h.std())      # ddof 0; > 0 required
                if sd <= 0.0:
                    continue             # flat own history earns no z
                score_x[j] = (cj - float(h.mean())) / sd
            else:  # ownpct: percentile of the current level within own past
                lt = int(np.count_nonzero(h < cj))
                eq = int(np.count_nonzero(h == cj))
                score_x[j] = (lt + 0.5 * eq) / h.size
        valid = np.isfinite(score_x)
        n = int(valid.sum())
        tilt = np.ones(out.shape[1])
        if n >= 5:
            sv = score_x[valid]
            order = np.argsort(sv, kind="stable")
            pct = np.empty(n)
            pct[order] = np.arange(n) / (n - 1)
            tilt[valid] = 1.0 + sz_w * (2.0 * pct - 1.0)
        ok = np.isfinite(out[t])
        out[t] = np.where(ok, out[t] * tilt, np.nan)
    return out, regime
