"""Candidate: self-relative participation-expansion tilt on the champion book
(strategy_lab contract).

Setup in words: the CURRENT champion chain is composed exactly as
strat_l15b_insideday composes it — strat_l12b_gatefail.score (floor-lift
fresh-print rank, gates, breadth-tier exposure, wobble tilt with neutral
gf/gw defaults set here) → the inside-day percentile tilt (ids_lb/ids_w,
verbatim behaviour, reusing the imported `_monthly_inside` daily helper) —
and then a NEW volume tilt is applied to the same lift, BEFORE the
regime-conditional cap step, which is mirrored inline (identical loop to
strat_l13a_concwobble / strat_l15b_insideday).

The new signal, per daily bar and symbol — share VOLUME only:

    per calendar-month bucket m:   mv_m = mean(daily volume in bucket m)
                                   (NaN when the bucket had < vmin bars —
                                   partial months at panel edges excluded)
    baseline_m = nanmean(mv over the `vbase` monthly buckets before m)
    vr_m = mv_m / baseline_m       (self-relative participation ratio)

For score row t (holding month starting months[t]) the newest bucket read is
bucket t-1; `vlb` bucket ratios ending there are averaged:

    share_t = nanmean(vr_{t-vlb .. t-1})

cross-sectionally percentile-ranked among finite values (n >= 5 guard):

    tilt = 1 + vw * (2 * pct - 1)
    out  = (gatefail lift * ids tilt) * tilt     # NaN share keeps tilt 1.0

Hypothesis: the champion buys fresh 12-month-high printers and re-weights
them by tape COMPRESSION (inside-day share, ids_w < 0). Nothing in the chain
reads volume. A high printed on participation that is EXPANDING against the
name's own trailing baseline is confirmed demand — the classic volume-
confirms-breakout argument — while a high printed on contracting volume is a
thin move that fewer hands validate. Because the ratio is SELF-relative
(name's own baseline), it is scale-free across rupee-volume classes and
orthogonal to the cross-sectional liquidity-level weight (strat_floorhighliqw,
DEAD) and to all volume GATES (binary exclusion at a quantile/multiplier).
vw > 0 favours expansion into the print; vw < 0 favours quiet prints. The
screen decides the sign; if both directions trail the champion, the
participation axis is closed on this base.

Closest prior art and the one thing changed: the volume-confirmation family —
strat_floorhighvolconf (single-month rupee-turnover > mult x trailing baseline
as an EXCLUSION GATE on the floorhighfastgate base), strat_liqtrend
(near-vs-baseline volume ratio as a STANDALONE score basis), strat_floorhighspons
(same ratio replacing lift depth), strat_floorhighaccum (signed-volume share
gate), strat_floorhighliqw (continuous z-score of trailing-median turnover
LEVEL), strat_floorhightiervol (cross-sectional volume quantile gate). The one
thing changed: the trailing-baseline participation ratio is applied as a
CONTINUOUS percentile tilt (multiplicative, pre-cap) on the CURRENT champion
chain, averaged over `vlb` monthly buckets rather than a single print month —
a signal form (windowed self-relative ratio as tilt) and a base (the ids
champion) it was never tested on. It is not a gate, not a liquidity level,
not signed accumulation, and not tape geometry (the ids term reads high/low
containment; this reads volume).

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13;
        max_hold 3 is a HARNESS key, not consumed here)
        + vlb {3, 6}   (bucket window ending at the print month)
        + vbase {6, 12} (trailing baseline buckets, excluded from the window)
        + vw {+0.30, -0.30, +0.15, -0.15} (percentile tilt; 0.0 = off-switch;
          positive = favour participation expansion into the print)

Falsification test: if every tested (vlb, vbase, vw) combination ties or
trails the flat champion — train +96.882% / DD -17.032% / calmar 5.688,
fwd +48.973% / fwd DD -12.311% — with no forward or DD improvement on any
variant, then self-relative participation carries no information beyond the
monthly-close rank, gates, wobble and inside-day tilt, and the volume-tilt
channel is closed at this base. A variant that gains train only by breaching
the DD discipline is a rank-ordering artefact, not a keep.

PIT argument: NEEDS_DAILY loads the daily long panel (full window). mv and
the baseline use only volume of bars within each bucket and of EARLIER
buckets (shifted window on the compact bucket grid); for row t the newest
bucket read is t-1, whose bars all have date < months[t]; buckets t and
later are never touched. Rows t < vlb and names with no bucket values keep
tilt exactly 1.0 — nothing dropped on missing data, nothing peeks.

Off-switch identity: vw = 0.0 skips the volume tilt entirely, so `out` is
bitwise strat_l15b_insideday's scores at the same params and the mirrored
cap yields bitwise the champion. NOTE imported defaults leak:
strat_l12b_gatefail's gf_w default (0.05) is neutralised here with
setdefault gf_lb 12 / gf_w 0.0 / gw_w 0.0 BEFORE delegating — champion values
(gw_w 0.15, ids_w -0.13) are PASSED by the caller, not defaulted.

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688, fwd +48.973% / fwd DD -12.311%.
"""

from __future__ import annotations

import warnings

import numpy as np
import polars as pl

from strat_l12b_gatefail import score as _gf_score
from strat_l15b_insideday import _monthly_inside

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
    "gw_w": [0.15],
    "ids_lb": [3],
    "ids_w": [-0.13],
    # this file's keys
    "vlb": [3, 6],
    "vbase": [6, 12],
    "vw": [0.3, -0.3, 0.15, -0.15],
}

_VMIN = 10  # min daily bars in a bucket for its mean volume to count


def _monthly_vratio(daily: pl.DataFrame, months, cols, vbase: int) -> np.ndarray:
    """Per (panel month, stock) the self-relative participation ratio
    mv_m / baseline_m; NaN where the bucket or its baseline is missing."""
    g = (daily.group_by_dynamic("date", every="1mo", group_by="symbol")
              .agg(pl.col("volume").cast(pl.Float64).mean().alias("mv"),
                   pl.len().alias("nb"))
              .sort("symbol", "date"))
    g = g.with_columns(
        pl.when(pl.col("nb") >= _VMIN).then(pl.col("mv")).otherwise(None).alias("mv"))
    piv = g.pivot(on="symbol", index="date", values="mv").sort("date")
    dates = piv["date"].to_list()
    V = np.full((len(dates), len(cols)), np.nan)
    cidx = {s: j for j, s in enumerate(cols)}
    for k, row in enumerate(piv.iter_rows(named=True)):
        for s, v in row.items():
            if s == "date":
                continue
            j = cidx.get(s)
            if j is not None and v is not None:
                V[k, j] = v
    R = np.full_like(V, np.nan)
    for i in range(V.shape[0]):
        lo = i - vbase
        if lo < 0:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            R[i] = np.nanmean(V[lo:i], axis=0)
    VR = np.full_like(V, np.nan)
    ok = np.isfinite(V) & np.isfinite(R) & (R > 0)
    np.divide(V, R, out=VR, where=ok)
    mind = {}
    for i, m in enumerate(months):
        mind[m if not hasattr(m, "date") else m.date()] = i
    out = np.full((len(months), len(cols)), np.nan)
    for k, dt in enumerate(dates):
        i = mind.get(dt if not hasattr(dt, "date") else dt.date())
        if i is None:
            continue
        out[i] = VR[k]
    return out


def _apply_pct_tilt(out, base, X, lb, w):
    """Verbatim structure of strat_l15b_insideday's ids block: per row t,
    nanmean of X over the lb buckets ending at t-1, percentile-ranked among
    finite values (n >= 5), multiplicative tilt on `base`."""
    for t in range(1, base.shape[0]):
        lo = t - lb
        if lo < 0:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            share = np.nanmean(X[lo:t], axis=0)
        valid = np.isfinite(share)
        n = int(valid.sum())
        tilt = np.ones(base.shape[1])
        if n >= 5:
            sv = share[valid]
            order = np.argsort(sv, kind="stable")
            pct = np.empty(n)
            pct[order] = np.arange(n) / (n - 1)
            tilt[valid] = 1.0 + w * (2.0 * pct - 1.0)
        ok = np.isfinite(base[t])
        out[t] = np.where(ok, base[t] * tilt, np.nan)


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating: gatefail's own gf_w default (0.05)
    # would leak into the off-switch. Champion values are passed, not defaulted.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    lift, exposure = _gf_score(panels, p)

    out = np.array(lift, dtype=float, copy=True)
    ids_w = float(params.get("ids_w", 0.0))
    if ids_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        IDS = _monthly_inside(daily, months, cols)
        _apply_pct_tilt(out, lift, IDS, int(params.get("ids_lb", 3)), ids_w)

    vw = float(params.get("vw", 0.0))
    if vw != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        VR = _monthly_vratio(daily, months, cols, int(params.get("vbase", 6)))
        _apply_pct_tilt(out, out, VR, int(params.get("vlb", 3)), vw)

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
