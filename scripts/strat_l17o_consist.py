"""Candidate: monthly return-consistency tilt on the ids champion chain
(strategy_lab contract).

Setup in words: the CURRENT champion chain — strat_l13a_concwobble at
lookback 12 (floor-lift fresh-print rank among short-trend-passing,
print-continuity-passing names, breadth-tier exposure with tier 0.9999,
regime-conditional book cap cap_weak/cap_full) carrying the
eligibility-wobble discount gw_w 0.15 / gf_lb 12 AND the inside-day
pause-share tilt ids_lb 3 / ids_w -0.13 (strat_l15b_insideday, the live
champion) — is imported wholesale via strat_l12b_gatefail.score. Before the
regime-conditional cap step (mirrored inline, a composition step, not an
indicator), the imported lift is re-weighted by a NEW signal: the name's
MONTHLY RETURN CONSISTENCY — the share of its last `cs_lb` monthly returns
that were positive.

    ret_m   = px[m] / px[m-1] - 1                        (monthly simple return)
    cons_t  = mean( ret_m > 0 ) over m in (t-cs_lb, t]   (non-finite months
              skipped; NaN when fewer than 5 finite months in the window)

Among names with a finite consistency in the row it is percentile-ranked
into pct in [0, 1]:

    tilt = 1 + cs_w * (2 * pct - 1)   # cs_w > 0 favours steady grinders
    out  = (gatefail lift * ids tilt) * cons tilt

Hypothesis: the champion buys fresh 12-month-high printers. Two names can
arrive at the same high with very different paths: one that printed most
months positive (broad, time-diversified demand) and one whose entire
advance came in a single month (event-driven, thin). Classic momentum
argues the steady path continues; the supply-overhead argument says a
one-jump name carries less accumulated overhead. Both directions are tested
via the cs_w sign.

Novelty statement (required): closest prior art in the inventory is the
PARTIAL market-relative-strength line (rs), which reads the trailing return
LEVEL, and the DEAD serpers line, which read the autocorrelation of monthly
return SIGNS; neither reads the hit rate. This is not rank
smoothing/blending (the input is a different statistic, not a transform of
the rank), not persistence weighting (no month weighting), and not a
freshness/drought re-shape. The base is the current ids champion.

Falsification test: every non-zero cs_w ties or trails the off-switch
identity (train +96.882 / DD -17.032) with no DD or forward case; then the
signal is dead on this base.
"""

from __future__ import annotations

import warnings

import numpy as np

from strat_l12b_gatefail import score as _gf_score
from strat_l15b_insideday import _monthly_inside

NEEDS_DAILY = True
SPACE = {
    # this file's keys
    "cs_lb": [6, 12],
    "cs_w": [-0.3, -0.15, 0.15, 0.3],
    # champion keys (pinned, passed by the caller; docs only)
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
}


def _consistency(px: np.ndarray, lb: int) -> np.ndarray:
    """Row t: share of the last lb monthly returns (ending at the print
    month t) that were positive. Non-finite months are skipped; NaN where
    fewer than 5 finite months are in the window."""
    ret = np.full(px.shape, np.nan)
    ret[1:] = px[1:] / px[:-1] - 1.0
    out = np.full(px.shape, np.nan)
    for t in range(1, px.shape[0]):
        lo = t - lb + 1
        if lo < 1:
            continue
        win = ret[lo:t + 1]
        pos = np.where(np.isfinite(win), win > 0, np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cnt = np.sum(np.isfinite(pos), axis=0)
            share = np.nanmean(pos, axis=0)
        out[t] = np.where(cnt >= 5, share, np.nan)
    return out


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating: gatefail's own gf_w default (0.05)
    # would leak into the off-switch. Champion values are passed, not defaulted.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    lift, exposure = _gf_score(panels, p)

    ids_w = float(params.get("ids_w", 0.0))
    out = np.array(lift, dtype=float, copy=True)

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

    cs_w = float(params.get("cs_w", 0.0))
    if cs_w != 0.0:
        px = panels["px"]
        clb = int(params.get("cs_lb", 12))
        cons = _consistency(px, clb)
        for t in range(1, out.shape[0]):
            s = cons[t]
            valid = np.isfinite(s)
            n = int(valid.sum())
            if n < 5:
                continue
            sv = s[valid]
            order = np.argsort(sv, kind="stable")
            pct = np.empty(n)
            pct[order] = np.arange(n) / (n - 1)
            tilt = np.ones(out.shape[1])
            tilt[valid] = 1.0 + cs_w * (2.0 * pct - 1.0)
            ok = np.isfinite(out[t])
            out[t] = np.where(ok, out[t] * tilt, np.nan)

    # cap step mirrored inline from strat_floorhightiershapeconc.score /
    # strat_l13a_concwobble.score (book-size composition, not an indicator)
    cw = int(params.get("cap_weak", 11))
    cf = int(params.get("cap_full", 20))
    E = np.asarray(exposure, dtype=float)
    for t in range(out.shape[0]):
        r = out[t]
        fin = np.flatnonzero(np.isfinite(r))
        if fin.size == 0:
            continue
        cap = cf if E[t] >= 1.0 else cw
        if fin.size <= cap:
            continue
        order = fin[np.argsort(-r[fin], kind="stable")]
        out[t, order[cap:]] = np.nan
    return out, E
