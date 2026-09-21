"""Candidate: print-month range-compression tilt on the champion book
(strategy_lab contract).

Setup in words: the CURRENT champion chain (strat_l13a_concwobble at
lookback 12: floor-lift fresh-print rank among short-trend-passing,
print-continuity-passing names, breadth-tier exposure with tier 0.9999,
regime-conditional book cap cap_weak/cap_full, eligibility-wobble discount
gw_w 0.13 / gf_lb 12) is imported wholesale via strat_l12b_gatefail.score.
Before the regime-conditional cap step (mirrored inline, exactly as
strat_l13a_concwobble mirrors it — a composition step, not an indicator),
the imported lift is re-weighted by a NEW daily-tape signal: how COMPRESSED
the name's daily range was going into the fresh print. Per calendar month
and stock, compute the mean daily true range relative to that month's mean
close:

    tr_d    = max(high_d - low_d, |high_d - close_{d-1}|, |low_d - close_{d-1}|)
    mtr_m   = mean over month m of tr_d / close_d          (unitless)

Over the `cmp_lb` monthly buckets ending at the print month (the calendar
month before the holding month):

    base_m  = mean of mtr over the cmp_lb buckets ending at month m-1
              EXCLUDING the print month itself (the trailing baseline)
    ratio_m = mtr_{m-1} / base_m   (print-month range vs its own baseline)

ratio is self-normalised: it asks whether the print month traded TIGHTER or
WIDER than the same name's own recent regime, independent of price level
and independent of the book's cross-sectional volatility ranking. Among
names with a finite ratio in the row, ratio is percentile-ranked into pct
in [0, 1]:

    tilt = 1 + cmp_w * (2 * pct - 1)   # cmp_w < 0 favours COMPRESSED prints
    out  = imported lift * tilt        # NaN ratio keeps tilt 1.0

Hypothesis: the champion buys fresh 12-month-high printers. A breakout out
of a tight coil (print-month range well below its own trailing baseline —
an NR7-like state) is supply exhaustion before release; the same fresh
high after weeks of already-expanding daily ranges is a late, extended
entry where the move is spent. Classic breakout work treats compression as
the precondition, and the champion's monthly closes cannot see it. If
compressed prints continue better, cmp_w < 0 lifts the top-15 cut's
quality; if the print-continuity and short-trend gates already fully
encode it, every variant ties the base and the channel closes.

Falsifier: if every tested (cmp_lb, cmp_w) combination trails the flat base —
train +88.139% / DD -17.339% / calmar 5.083, fwd +49.274% / fwd DD
-14.926% / fwd bench +14.717% — then print-month range compression carries
no information beyond what the champion's monthly-close rank and gates
already consume, and the family is closed at this base. If a variant shows
the documented forward-positive / train-negative pattern instead, check
stacking with the forward geometry (rs_w 0.2 / rs_lb 6 + cap_full 15 /
max_hold 6) before discarding — but selection stays train-side either way.

Import chain: strat_l15b_rngcomp -> strat_l12b_gatefail.score (which
imports strat_floorhighfastgate + strat_floorhighsustaincond for the gate
layers and strat_floorhightiershape for rank/exposure, and applies the
wobble tilt) -> cap step mirrored inline from
strat_floorhightiershapeconc.score / strat_l13a_concwobble.score (identical
loop: cap = cap_full where exposure >= 1.0 else cap_weak; lower ranks set
NaN after a stable descending sort).

PIT argument: NEEDS_DAILY loads the daily long panel (full window — handled
as follows). Daily bars are grouped into calendar-month buckets with
group_by_dynamic("1mo"); tr_d uses close_{d-1} from the SAME symbol's prior
bar (shift within symbol over sorted dates), never a future bar. For score
row t (holding month starting months[t]) the newest bucket read is bucket
t-1, the calendar month starting months[t-1], whose bars all have date in
[months[t-1], months[t]) — every bar read is strictly BEFORE months[t];
buckets t and later are never touched, so the fact that `daily` covers the
full panel window is harmless. The percentile at row t uses only ratio
values from that same backward window. Rows with insufficient history
(t < cmp_lb + 1) and names with NaN mtr, NaN ratio, or a non-positive
baseline keep tilt exactly 1.0 — eligibility and rank unmodified, nothing
dropped on missing data, nothing peeks.

Off-switch identity: cmp_w = 0.0 makes tilt == 1.0 for every name and every
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
volatility-scaled rank / vol-rank tilt (Loop-14: positive side harmful,
negative tilt does not stack with the forward geometry). The one thing
changed: the dead family ranked the book on a trailing volatility LEVEL —
a cross-sectional, price-scale-dependent quantity. This signal is a name's
print-month range DIVIDED BY ITS OWN trailing baseline — a within-name
expansion state, scale-free, measured only at the print month. It is also
not CLV (where in the day's range the close landed — DEAD), not volume
(volume gates, signed accumulation — DEAD), and not persistence/freshness
(LIVE-adjacent): high/low geometry as a compression precondition is a
variable no file in the chain consumes.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.13; max_hold 3 is a HARNESS
        key passed via params-json, this file does not consume it)
        + cmp_lb {3, 6} (baseline window in monthly buckets, excluding the
          print month)
        + cmp_w {-0.4, -0.2, +0.2} (percentile tilt; 0.0 = off-switch;
          negative = favour compressed prints).

Designer smoke observations (Loop-15, pre-freeze, nse_all top 15 25bps
split 2022-01-01): off-switch reproduced +88.14 / -17.34 / 5.08, fwd
+49.27 / -14.93 exactly. cmp_w -0.2 / cmp_lb 3 -> train +73.07 / -23.72,
fwd +56.62 / -16.19. cmp_w -0.4 / cmp_lb 6 -> train +75.39 / -18.47
(calmar 4.08), fwd +60.94 / fwd DD -11.61 — forward-calmar ~5.25, ABOVE
the relstrength stack's 4.38, on the same forward-positive /
train-negative signature. Compression-favouring is the live side; the
deeper negative weight and longer baseline carried it. Selection stays
train-side (this cannot pass the cagr ratchet at 75.4), but this is the
strongest forward-risk-adjusted print of any designer smoke in Loop-15:
if the screen confirms, test stacking with the forward geometry
(rs_w 0.2 / rs_lb 6 + cap_full 15 / max_hold 6) before discarding.
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
    "cmp_lb": [3, 6],
    "cmp_w": [-0.4, -0.2, 0.2],
}


def _monthly_mtr(daily: pl.DataFrame, months, cols) -> np.ndarray:
    """Per (calendar month, stock) mean of daily true range over close;
    NaN where the month had no bars or no valid prior close."""
    d = daily.with_columns(pl.col("close").shift(1).over("symbol").alias("pc"))
    d = d.with_columns(
        pl.when(pl.col("pc") > 0)
          .then(pl.max_horizontal(
              pl.col("high") - pl.col("low"),
              (pl.col("high") - pl.col("pc")).abs(),
              (pl.col("low") - pl.col("pc")).abs()))
          .otherwise(pl.col("high") - pl.col("low"))
          .alias("tr"))
    d = d.with_columns(
        pl.when((pl.col("close") > 0) & (pl.col("tr") >= 0))
          .then(pl.col("tr") / pl.col("close"))
          .otherwise(None)
          .alias("mtr"))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("mtr").mean())
          .sort("symbol", "date"))
    piv = g.pivot(on="symbol", index="date", values="mtr").sort("date")
    mind = {}
    for i, m in enumerate(months):
        mind[m if not hasattr(m, "date") else m.date()] = i
    out = np.full((len(months), len(cols)), np.nan)
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
                out[i, j] = v
    return out


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating: gatefail's own gf_w default (0.05)
    # would leak into the off-switch. Champion values are passed, not defaulted.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    lift, exposure = _gf_score(panels, p)

    cmp_w = float(params.get("cmp_w", 0.0))
    out = np.array(lift, dtype=float, copy=True)

    if cmp_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        clb = int(params.get("cmp_lb", 3))
        M = _monthly_mtr(daily, months, cols)
        for t in range(1, lift.shape[0]):
            pm = t - 1  # print-month bucket
            lo = pm - clb  # baseline buckets: [lo, pm), print month excluded
            if lo < 0:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                base = np.nanmean(M[lo:pm], axis=0)
            with np.errstate(invalid="ignore", divide="ignore"):
                ratio = np.where((base > 0) & np.isfinite(M[pm]) & np.isfinite(base),
                                 M[pm] / base, np.nan)
            valid = np.isfinite(ratio)
            n = int(valid.sum())
            tilt = np.ones(lift.shape[1])
            if n >= 5:
                rv = ratio[valid]
                order = np.argsort(rv, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + cmp_w * (2.0 * pct - 1.0)
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
