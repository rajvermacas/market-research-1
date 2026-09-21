"""Candidate: calendar-month exposure regime on the champion book
(strategy_lab contract).

Setup in words: the CURRENT champion chain — strat_l15b_insideday (floor-lift
fresh-print rank among short-trend-passing, print-continuity-passing names,
breadth-tier exposure with tier 0.9999, regime-conditional cap cap_weak/
cap_full, eligibility-wobble gw_w 0.15, inside-day tilt ids_w -0.13 / lb 3) —
is imported wholesale via strat_l15b_insideday.score; its scores are capped
inline exactly as the champion caps them (composition step, not an
indicator), and are NOT re-ranked by this mechanism. What changes is the
EXPOSURE the harness deploys, scaled by a NEW regime signal: the panel's
historical same-CALENDAR-MONTH returns, computed point-in-time from prior
years only.

Timeline convention (harness-exact): the decision at row t is made on the
close of calendar month months[t]; the return it scales, r_t =
mean(px[t+1]/px[t]) - 1, accrues over calendar month months[t+1]. Exposure
for the holding month is therefore conditioned on the HOLDING month's
calendar identity:

    hold_cal[m] = months[m+1].month, hold_year[m] = months[m+1].year
    hist[t]     = {m' < t : hold_cal[m'] == hold_cal[t] AND
                   hold_year[m'] < hold_year[t]}   (expanding, prior YEARS
                   only — the current year's same month is never read)
    RH[m]       = equal-weight mean over names of (px[m+1]/px[m] - 1)
    z[t]        = (mean RH over hist[t] - mean RH[:t]) / std RH[:t]
    E_state[t]  = clip(1 + cr_w * z[t], cr_floor, 1.0)   if len(hist) >= cr_min
                = 1.0                                    otherwise
    E[t]        = clip(E_breadth[t] * E_state[t], 0.0, 1.0)

With cr_w > 0, holding months whose same-calendar-month panel history has
been WEAK (z < 0) carry scaled-down exposure; strong-history months stay at
the champion's own exposure (E can never exceed 1, so a positive tilt is a
no-op by construction). cr_w < 0 expresses the contrarian reading
(de-risking historically STRONG months). The cap step is mirrored with
E_breadth exactly as the champion caps, so the calendar mechanism acts ONLY
through the capital-deployment channel — one channel per mechanism, clean
attribution.

Hypothesis: NSE monthly returns carry calendar seasonality (budget-day /
results-season / futures-expiry effects are stable institutions, not
data-mined patterns), and the champion's breadth tiers are blind to WHICH
month is being held. If the same-calendar-month history of the panel
predicts the holding month's return, de-risking the historically weak
calendar months should cut drawdown without giving up the strong months'
compounding; if the seasonality lives in individual names (the Loop-16
finding) or is too thin at ~3-11 observations per calendar month, every
variant ties or trails and the calendar-exposure axis closes.

NOVELTY STATEMENT: closest prior art is Loop-16's DEAD seasonal momentum —
the per-name same-calendar-month momentum applied as a RANK tilt on the ids
chain (66.4-86.5 train, every active direction destructive). The one thing
changed: (1) the input is the PANEL-LEVEL aggregate same-month return
history (one number per month, expanding over prior years), not a per-name
rank; (2) the channel is EXPOSURE in [0,1], not the score — the book
composition is champion-identical, only the deployed fraction moves;
(3) the window is strictly prior-year (expanding), never the current year.
This is a different signal on a different channel, not a re-shape. It is
also NOT vol targeting (DEAD — keys on realized-vol LEVEL, not on the
calendar identity) and NOT the index-DD veto (DEAD — keys on the index's
drawdown/MA state, not on the calendar).

Import chain: strat_l17c_calreg -> strat_l15b_insideday.score -> cap step
mirrored inline from strat_floorhightiershapeconc.score /
strat_l13a_concwobble.score. NEEDS_DAILY=True so the delegate's ids term
can read the daily panel exactly as the champion does.

PIT argument: RH[m] for history reads uses px[m+1] with m' < t and holding
years strictly before the holding year of t — every such px[m+1] is at or
before px[t] (the decision close), so nothing peeks. The current year's
same month is excluded by construction. Rows with fewer than cr_min prior
same-month observations keep E_state = 1.0 (no early-sample drift).

Off-switch identity: cr_w = 0.0 (default) leaves E_state = 1.0 for every
row, so E = E_breadth bitwise and `out` is bitwise the champion's scores at
the same params. Champion keys are PASSED by the caller, not defaulted
here.

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

Diagnostics note: this mechanism changes exposure, not the pick sets, so
the Loop-16 firing-event concern does not apply to book composition — but
`invested` will drop below the champion's wherever E_state fires; any
"lower DD" reading must be checked against the deployed capital it gave
up (the LESSONS rule: exposure cuts can buy DD by simply sitting out).

Falsifier: if every tested (cr_w, cr_wl, cr_floor, cr_min) combination
trails the flat base — train +96.882% / DD -17.032% / calmar 5.688 — then
calendar-month history carries no exposure-relevant information beyond the
champion's breadth tiers, and the calendar-regime axis closes at this base.
Sample-size honesty: the history per calendar month grows from 0 to ~11
observations across the window — a mechanism that only "works" late in the
sample (when its history exists) must be read as such, and the falsifier
above already covers it because the off-switch rows are not window-matched.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13;
        max_hold 3 is a HARNESS key passed via params-json, not consumed
        here)
        + cr_w {+0.25, +0.5, -0.25} (exposure sensitivity to the z of
          same-month history; 0.0 = off-switch)
        + cr_min {3} (minimum prior same-month observations before firing)
        + cr_floor {0.5} (minimum E_state once it fires)
        + cr_wl {0, 8} (0 = expanding window over all prior years;
          8 = only the last 8 prior-year observations of that month).
"""

from __future__ import annotations

import warnings

import numpy as np

from strat_l15b_insideday import score as _ids_score

NEEDS_DAILY = True  # the delegate's ids term reads the daily panel (ids_w -0.13)

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
    "gw_w": [0.15],
    "ids_lb": [3],
    "ids_w": [-0.13],
    # this file's keys
    "cr_w": [0.25, 0.5, -0.25],
    "cr_min": [3],
    "cr_floor": [0.5],
    "cr_wl": [0, 8],
}


def score(panels, params):
    lift, exposure = _ids_score(panels, params)

    # cap step mirrored inline from strat_floorhightiershapeconc.score /
    # strat_l13a_concwobble.score — on the UNMODIFIED lift, keyed on the
    # champion's own exposure (book composition champion-identical)
    out = np.array(lift, dtype=float, copy=True)
    E_b = np.asarray(exposure, dtype=float)
    cw = int(params.get("cap_weak", 11))
    cf = int(params.get("cap_full", 20))
    for t in range(out.shape[0]):
        r = out[t]
        fin = np.flatnonzero(np.isfinite(r))
        if fin.size == 0:
            continue
        cap = cf if E_b[t] >= 1.0 else cw
        if fin.size <= cap:
            continue
        order = fin[np.argsort(-r[fin], kind="stable")]
        out[t, order[cap:]] = np.nan

    E = E_b.copy()
    cr_w = float(params.get("cr_w", 0.0))
    if cr_w != 0.0:
        px, months = panels["px"], panels["months"]
        cmin = int(params.get("cr_min", 3) or 3)
        floor = float(params.get("cr_floor", 0.5))
        wl = int(params.get("cr_wl", 0) or 0)
        T = len(months)
        # holding-period panel return per decision row m (uses px[m+1]; read
        # only for history rows whose holding month is strictly in the past)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            RH = np.nanmean(px[1:T] / px[0:T - 1] - 1.0, axis=1)
        hold_cal = np.array([months[m + 1].month for m in range(T - 1)])
        hold_year = np.array([months[m + 1].year for m in range(T - 1)])
        for t in range(panels["start_i"], T - 1):
            c, y = hold_cal[t], hold_year[t]
            hist = [m for m in range(0, t) if hold_year[m] < y and hold_cal[m] == c]
            if wl > 0:
                hist = hist[-wl:]
            if len(hist) < cmin:
                continue  # E_state stays 1.0
            prior = RH[:t]
            mu = float(np.nanmean(prior))
            sd = float(np.nanstd(prior))
            if not np.isfinite(sd) or sd <= 0.0:
                continue
            z = (float(np.nanmean(RH[hist])) - mu) / sd
            if not np.isfinite(z):
                continue
            E_state = min(1.0, max(floor, 1.0 + cr_w * z))
            E[t] = min(E_b[t] * E_state, 1.0)
    return out, np.clip(E, 0.0, 1.0)
