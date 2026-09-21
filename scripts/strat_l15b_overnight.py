"""Candidate: overnight-vs-intraday move-decomposition tilt on the champion
book (strategy_lab contract).

Setup in words: the CURRENT champion chain (strat_l13a_concwobble at
lookback 12: floor-lift fresh-print rank among short-trend-passing,
print-continuity-passing names, breadth-tier exposure with tier 0.9999,
regime-conditional book cap cap_weak/cap_full, eligibility-wobble discount
gw_w 0.13 / gf_lb 12) is imported wholesale via strat_l12b_gatefail.score.
Before the regime-conditional cap step (mirrored inline, exactly as
strat_l13a_concwobble mirrors it — a composition step, not an indicator),
the imported lift is re-weighted by a NEW daily-tape signal, the overnight
share of the name's trailing move. Each daily bar decomposes into an
overnight leg and an intraday leg:

    overnight leg d: ln(open_d / close_{d-1})
    intraday leg  d: ln(close_d / open_d)

Per calendar month these legs are summed; over the `on_lb` monthly buckets
ending at the print month (the calendar month before the holding month):

    ON = mean monthly overnight leg sum
    ID = mean monthly intraday leg sum
    s  = ON / (ON + ID)   defined only where the trailing total ON+ID > 0

s is the share of the trailing up-move that was earned overnight (gaps
between sessions) rather than during sessions. Among all names with finite
s in the row, s is cross-sectionally percentile-ranked into pct in [0, 1]:

    tilt = 1 + on_w * (2 * pct - 1)    # on_w > 0 favours overnight-carried
    out  = imported lift * tilt        # names with NaN s keep tilt 1.0

Hypothesis: the champion buys fresh 12-month highs. WHERE the move that
produced the high was earned is information a monthly close cannot carry:
a run financed by persistent overnight gaps is pre-open accumulation
(demand that cannot be day-traded away), while the same run earned
intraday is session-to-session speculation that evaporates at the bell.
Overnight/intraday return decomposition is a documented institutional-flow
and disposition proxy (Lou-Polk-Skouras, "A tug of war: Overnight versus
intraday expected returns"). If overnight-carried printers continue,
on_w > 0 lifts the top-15 cut's quality; if the monthly-print chain
already fully prices the move's character, every variant ties the base
and the channel closes.

Falsifier: if every tested (on_lb, on_w) combination trails the flat base —
train +88.139% / DD -17.339% / calmar 5.083, fwd +49.274% / fwd DD
-14.926% / fwd bench +14.717% — then the overnight/intraday decomposition
of the trailing move carries no information beyond what the champion's
monthly-close rank and gates already consume, and the family is closed at
this base. If a variant shows the documented forward-positive /
train-negative pattern instead, check stacking with the forward geometry
(rs_w 0.2 / rs_lb 6 + cap_full 15 / max_hold 6) before discarding — but
selection stays train-side either way.

Import chain: strat_l15b_overnight -> strat_l12b_gatefail.score (which
imports strat_floorhighfastgate + strat_floorhighsustaincond for the gate
layers and strat_floorhightiershape for rank/exposure, and applies the
wobble tilt) -> cap step mirrored inline from
strat_floorhightiershapeconc.score / strat_l13a_concwobble.score (identical
loop: cap = cap_full where exposure >= 1.0 else cap_weak; lower ranks set
NaN after a stable descending sort).

PIT argument: NEEDS_DAILY loads the daily long panel (full window — handled
as follows). Daily bars are grouped into calendar-month buckets with
group_by_dynamic("1mo"). For score row t (holding month starting months[t])
the newest bucket read is bucket t-1, the calendar month starting
months[t-1], whose bars all have date in [months[t-1], months[t]) — every
bar read is strictly BEFORE months[t]; buckets t and later are never
touched, so the fact that `daily` covers the full panel window is harmless.
The percentile at row t uses only s values from that same backward window.
Rows with insufficient history (t < on_lb) and names with NaN legs, NaN s,
or a non-positive trailing total keep tilt exactly 1.0 — eligibility and
rank unmodified, nothing dropped on missing data, nothing peeks.

Off-switch identity: on_w = 0.0 makes tilt == 1.0 for every name and every
row, so `out` is bitwise the gatefail lift and the mirrored cap yields
bitwise the champion's scores at the same params. NOTE imported defaults
leak: strat_l12b_gatefail's own default is gf_w = 0.05 — this file
setdefaults gf_w = 0.0 / gw_w = 0.0 / gf_lb = 12 BEFORE delegating, so the
off-switch is exact and the champion's gw_w 0.13 must be PASSED by the
caller (it is a champion key, not a default here).

Flat-base metric (off-switch must reproduce exactly): train +88.139% /
DD -17.339% / calmar 5.083 / H1 +80.14% / H2 +96.09% / invested 65.5% /
fwd +49.274% / fwd DD -14.926% / fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art in the mechanism inventory is the DEAD
close-location tilt (strat_l12b_printclose, clv) and the DEAD signed-volume
accumulation share (strat_floorhighaccum) — the two daily-tape signals ever
composed onto this chain. Both measured the SESSION: clv asked where in the
day's own range it closed; accumulation asked which days carried the
volume. The one thing changed: the signal lives in the boundary BETWEEN
sessions — the open-to-previous-close leg, using the `open` column, which
no file in the live chain reads. Overnight-vs-intraday decomposition of the
trailing move is a different variable from close location, volume
direction, volatility level (vol-rank tilt, DEAD) and persistence
(freshness/wobble, LIVE-adjacent): it is not a re-shape of any of them.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.13; max_hold 3 is a HARNESS
        key passed via params-json, this file does not consume it)
        + on_lb {3, 6} (window in monthly buckets)
        + on_w {-0.4, -0.2, +0.2, +0.4} (percentile tilt; 0.0 = off-switch).

Designer smoke observations (Loop-15, pre-freeze, nse_all top 15 25bps
split 2022-01-01): off-switch reproduced +88.14 / -17.34 / 5.08, fwd
+49.27 / -14.93 exactly. on_w +0.2 / on_lb 3 -> train +73.90 / -19.48,
fwd +41.74 / -26.84 (overnight-favouring HARMFUL both sides). on_w -0.2 /
on_lb 6 -> train +67.72 / -20.18, fwd +52.14 / -16.99 — the same
forward-positive / train-negative signature as the documented relstrength
line (PARTIAL, stacks with cap_full 15 / max_hold 6). Selection stays
train-side; if a screen reproduces that signature, test stacking with the
forward geometry before discarding the line.
"""

from __future__ import annotations

import warnings

import numpy as np
import polars as pl

from strat_l12b_gatefail import score as _gf_score

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
    # this file's keys
    "on_lb": [3, 6],
    "on_w": [-0.4, -0.2, 0.2, 0.4],
}


def _monthly_legs(daily: pl.DataFrame, months, cols) -> tuple[np.ndarray, np.ndarray]:
    """Per (calendar month, stock) sums of the overnight leg ln(open/prev
    close) and the intraday leg ln(close/open); NaN where a leg is undefined
    (missing prior close, non-positive price) or the month had no bars."""
    d = daily.with_columns(pl.col("close").shift(1).over("symbol").alias("pc"))
    d = d.with_columns(
        pl.when((pl.col("pc") > 0) & (pl.col("open") > 0))
          .then(pl.col("open").log() - pl.col("pc").log())
          .otherwise(None)
          .alias("on"),
        pl.when((pl.col("open") > 0) & (pl.col("close") > 0))
          .then(pl.col("close").log() - pl.col("open").log())
          .otherwise(None)
          .alias("idr"),
    )
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("on").sum(), pl.col("idr").sum())
          .sort("symbol", "date"))
    mind = {}
    for i, m in enumerate(months):
        mind[m if not hasattr(m, "date") else m.date()] = i
    outs = []
    for val in ("on", "idr"):
        piv = g.pivot(on="symbol", index="date", values=val).sort("date")
        arr = np.full((len(months), len(cols)), np.nan)
        cidx = {s: j for j, s in enumerate(cols)}
        for row in piv.iter_rows(named=True):
            i = mind.get(row["date"])
            if i is None:
                continue
            for s, v in row.items():
                if s == "date":
                    continue
                j = cidx.get(s)
                if j is not None and v is not None:
                    arr[i, j] = v
        outs.append(arr)
    return outs[0], outs[1]


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating: gatefail's own gf_w default (0.05)
    # would leak into the off-switch. Champion values are passed, not defaulted.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    lift, exposure = _gf_score(panels, p)

    on_w = float(params.get("on_w", 0.0))
    out = np.array(lift, dtype=float, copy=True)

    if on_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        on_lb = int(params.get("on_lb", 3))
        ON, ID = _monthly_legs(daily, months, cols)
        for t in range(1, lift.shape[0]):
            lo = t - on_lb
            if lo < 0:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                onv = np.nanmean(ON[lo:t], axis=0)
                idv = np.nanmean(ID[lo:t], axis=0)
            tot = onv + idv
            with np.errstate(invalid="ignore", divide="ignore"):
                s = np.where((tot > 0) & np.isfinite(onv) & np.isfinite(idv),
                             onv / tot, np.nan)
            valid = np.isfinite(s)
            n = int(valid.sum())
            tilt = np.ones(lift.shape[1])
            if n >= 5:
                sv = s[valid]
                order = np.argsort(sv, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + on_w * (2.0 * pct - 1.0)
            ok = np.isfinite(lift[t])
            out[t] = np.where(ok, lift[t] * tilt, np.nan)

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
