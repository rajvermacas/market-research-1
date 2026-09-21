"""Candidate: cross-sectional outrank percentile tilt on the champion book
(strategy_lab contract).

Setup in words: the CURRENT champion chain — strat_l15b_insideday at its
champion params (the strat_l13a_concwobble floor-lift fresh-print rank +
gates + breadth tiers + regime-conditional cap + eligibility-wobble tilt,
carrying the inside-day pause-share tilt ids_w -0.13 / ids_lb 3 and
gw_w 0.15) — is imported wholesale, POST-cap. On top, the finite entries of
each row are re-weighted by a NEW cross-sectional structure signal: the
name's standing in the panel's own trailing return distribution. For month t
and window or_lb months:

    ret_j(t) = px[t, j] / px[t - or_lb, j] - 1
    share_beaten_j(t) = share of panel names k with ret_k(t) > ret_j(t)
    pct_j(t) = cross-sectional percentile of ret_j(t) among names with a
               finite ret (equivalent ordering: share_beaten is a monotone
               transform of ret, so the percentile of ret IS the percentile
               of share_beaten)

    tilt = 1 + or_w * (2 * pct - 1)   # applied to finite champion entries
    out  = champion_scores * tilt     # NaN share keeps tilt 1.0

or_w > 0 favours names the whole panel failed to beat over the window
(the strongest 12m movers); or_w < 0 favours names still in the lower half
of the panel's trailing distribution. The tilt lands AFTER the cap, so it
re-orders the capped pool (20 in full months / 11 in weak months) and moves
the harness top-15 cut across the 15-of-20 boundary — the same selection
surface the eligibility-wobble and inside-day terms act on, from a signal
none of them read.

Hypothesis: the champion buys fresh 12-month-high printers, i.e. names near
their own highs — but "near its own high" says nothing about where the name
sits AMONG all panel names over the trailing year. A printer that is also a
top-decile 12m performer is a crowded, extended leader whose continuation
the panel has already paid for; a printer sitting mid-distribution on the
trailing window is a fresh break out of a base the market has not chased.
This is the ORDINAL, cross-sectional expression of trailing strength —
distinct from the PARTIAL market-relative-strength line (strat_l14b_relstrength:
rs_w subtracts a CARDINAL offset vs the panel MEAN, which changes every
name's tilt when the mean moves and was forward-positive/train-negative);
here only the rank order of the panel's trailing returns enters, no mean,
no level. If trailing panel-rank carries information the own-high proximity
and gates do not, some sign of or_w lifts the top-15 cut's quality; if the
floor-lift (distance from the 12m high) already encodes trailing standing
for the eligible pool, every variant ties the base and the channel closes.

Falsifier: if every tested (or_lb, or_w) combination trails the flat base —
train +96.882% / DD -17.032% / calmar 5.688, fwd +48.973% / fwd DD -12.311%
/ fwd bench +14.717% — on BOTH windows (no variant improving forward
risk-adjusted numbers either), then cross-sectional trailing-rank carries no
information beyond the champion chain and the family closes at this base.

Import chain: strat_l16b_outrank -> strat_l15b_insideday.score (the whole
champion chain including the cap, imported never copied, champion params
passed by the caller). No indicator math is copied.

PIT argument: ret at row t reads px[t] and px[t-or_lb] only — both are
month-end closes at or before the decision month's own month-end px[m];
no row > t is touched. The percentile at row t uses only that same row's
cross-section. Rows with t < or_lb and names with NaN in either endpoint
keep tilt exactly 1.0 — eligibility and rank unmodified, nothing dropped on
missing data, nothing peeks. (NEEDS_DAILY is True only because the imported
insideday chain consumes the daily panel; this file itself reads px alone.)

Off-switch identity: or_w = 0.0 makes tilt == 1.0 for every name and row,
so `out` is bitwise the imported champion scores at the same params.

Flat-base metric (off-switch must reproduce exactly, top 15, 25 bps,
nse_all, split 2022-01-01): train +96.882% / DD -17.032% / calmar 5.688 /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art in the mechanism inventory is the
PARTIAL market-relative-strength line (strat_l14b_relstrength, rs_w/rs_lb:
forward-positive, train-negative, never promoted) and the DEAD rank
smoothing/blending family (re-weighting the champion's OWN rank history).
The ONE thing changed: a NEW signal — the name's ordinal position in the
PANEL's trailing-return distribution (a rank-of-rank: the share of panel
names that beat this name over the window) — which no prior file computes;
rs is a cardinal offset from the panel mean (level-dependent, and tested as
an additive term on an older base), rank smoothing blends the champion's own
scores across months (no new variable). Here the input is the cross-section
of trailing returns itself, applied post-cap on the current champion chain —
a base neither prior line was ever measured on.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, cap_weak 11,
        cap_full 20, floor_lb 19, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3,
        ids_w -0.13, lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5,
        sustain_lo 3, sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999;
        max_hold 3 is a HARNESS key via params-json, not consumed here)
        + or_lb {6, 12} (trailing window in months)
        + or_w {-0.3, -0.15, +0.15, +0.3} (percentile tilt; 0.0 = off-switch;
          positive = favour panel-leading 12m, negative = favour laggards).
"""

from __future__ import annotations

import numpy as np

from strat_l15b_insideday import score as _ids_score

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
    "or_lb": [6, 12],
    "or_w": [-0.3, -0.15, 0.15, 0.3],
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

    or_w = float(params.get("or_w", 0.0))
    out = np.array(base, dtype=float, copy=True)
    if or_w == 0.0:
        return out, exposure

    px = panels["px"]
    lb = int(params.get("or_lb", 12))
    for t in range(lb, out.shape[0]):
        with np.errstate(invalid="ignore"):
            ret = px[t] / px[t - lb] - 1.0
        valid = np.isfinite(ret)
        n = int(valid.sum())
        if n < 5:
            continue
        rv = ret[valid]
        order = np.argsort(rv, kind="stable")
        pct = np.empty(n)
        pct[order] = np.arange(n) / (n - 1)
        tilt = np.ones(out.shape[1])
        tilt[valid] = 1.0 + or_w * (2.0 * pct - 1.0)
        ok = np.isfinite(out[t])
        out[t] = np.where(ok, out[t] * tilt, np.nan)
    return out, exposure
