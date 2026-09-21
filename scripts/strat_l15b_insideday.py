"""Candidate: inside-day compression-count tilt on the champion book
(strategy_lab contract).

Setup in words: the CURRENT champion chain (strat_l13a_concwobble at
lookback 12: floor-lift fresh-print rank among short-trend-passing,
print-continuity-passing names, breadth-tier exposure with tier 0.9999,
regime-conditional book cap cap_weak/cap_full, eligibility-wobble discount
gw_w 0.13 / gf_lb 12) is imported wholesale via strat_l12b_gatefail.score.
Before the regime-conditional cap step (mirrored inline, exactly as
strat_l13a_concwobble mirrors it — a composition step, not an indicator),
the imported lift is re-weighted by a NEW daily-tape signal: the share of
INSIDE DAYS in the name's recent daily tape. Per daily bar and symbol:

    inside_d = (high_d < high_{d-1}) AND (low_d > low_{d-1})

An inside day is a pause: the whole session traded within the prior
session's range — neither side extended. Per calendar month bucket:

    ids_m = count(inside days in month m) / count(bars in month m)

averaged over the `ids_lb` monthly buckets ending at the print month (the
calendar month before the holding month). Among names with a finite share
in the row it is percentile-ranked into pct in [0, 1]:

    tilt = 1 + ids_w * (2 * pct - 1)   # ids_w < 0 favours compressed tape
    out  = imported lift * tilt        # NaN share keeps tilt 1.0

Hypothesis: the champion buys fresh 12-month-high printers. The tape
leading INTO the high carries structure monthly closes cannot see: a high
printed after a tape dense with inside days is a breakout from a coil of
agreed prices (volatility contraction precedes continuation in the
classic breakout literature), while a high printed on a tape with no
pause days is a grinding, extended move that has never rested. This is
the DISCRETE expression of range compression — a count of pause days —
deliberately distinct from the continuous self-normalised range-ratio
(strat_l15b_rngcomp, same loop): a tape can be quiet in magnitude yet
have no inside days (steady directional drift), and a volatile tape can
still print inside days (churn within wide bars). The two can disagree;
whether the count adds anything beyond the ratio is exactly what the
screen answers. If inside-day-dense printers continue, ids_w < 0 lifts
the top-15 cut's quality; if the short-trend/continuity gates already
encode it, every variant ties the base and the channel closes.

Falsifier: if every tested (ids_lb, ids_w) combination trails the flat
base — train +88.139% / DD -17.339% / calmar 5.083, fwd +49.274% / fwd DD
-14.926% / fwd bench +14.717% — then inside-day frequency carries no
information beyond the champion's monthly-close rank and gates (and
beyond the range-ratio signal where that survives its own screen), and
the discrete-compression family is closed at this base. Designer smoke
context (Loop-15): every daily-tape tilt so far traded train for forward
— compression-favouring carried the best forward print (rngcomp cmp_lb 6
/ cmp_w -0.4 -> fwd +60.94% / fwd DD -11.61%) — so a forward-heavy /
train-light result here would CONFIRM the family signature, not
falsify it; the falsifier is failing to reach the base on ANY tested
variant while also not improving forward risk-adjusted numbers over the
documented geometry lines.

Import chain: strat_l15b_insideday -> strat_l12b_gatefail.score (which
imports strat_floorhighfastgate + strat_floorhighsustaincond for the gate
layers and strat_floorhightiershape for rank/exposure, and applies the
wobble tilt) -> cap step mirrored inline from
strat_floorhightiershapeconc.score / strat_l13a_concwobble.score (identical
loop: cap = cap_full where exposure >= 1.0 else cap_weak; lower ranks set
NaN after a stable descending sort).

PIT argument: NEEDS_DAILY loads the daily long panel (full window — handled
as follows). inside_d uses only high/low of bar d and bar d-1 of the SAME
symbol (shift within symbol over dates sorted ascending) — no future bar.
Daily bars are grouped into calendar-month buckets with
group_by_dynamic("1mo"); the share is the bucket's own count ratio. For
score row t (holding month starting months[t]) the newest bucket read is
bucket t-1, the calendar month starting months[t-1], whose bars all have
date in [months[t-1], months[t]) — every bar read is strictly BEFORE
months[t]; buckets t and later are never touched, so the fact that
`daily` covers the full panel window is harmless. The percentile at row t
uses only share values from that same backward window. Rows with
insufficient history (t < ids_lb) and names with no bars in the window
(NaN share) keep tilt exactly 1.0 — eligibility and rank unmodified,
nothing dropped on missing data, nothing peeks.

Off-switch identity: ids_w = 0.0 makes tilt == 1.0 for every name and
every row, so `out` is bitwise the gatefail lift and the mirrored cap
yields bitwise the champion's scores at the same params. NOTE imported
defaults leak: strat_l12b_gatefail's own default is gf_w = 0.05 — this
file setdefaults gf_w = 0.0 / gw_w = 0.0 / gf_lb = 12 BEFORE delegating,
so the off-switch is exact and the champion's gw_w 0.13 must be PASSED by
the caller (it is a champion key, not a default here).

Flat-base metric (off-switch must reproduce exactly): train +88.139% /
DD -17.339% / calmar 5.083 / H1 +80.14% / H2 +96.09% / invested 65.5% /
fwd +49.274% / fwd DD -14.926% / fwd bench +14.717%.

NOVELTY STATEMENT: the mechanism inventory has NO entry for inside-day,
NR7 or any daily-range-count signal — the closest prior art is
strat_l15b_rngcomp (this loop, same designer): the continuous
self-normalised print-month range ratio. The one thing changed: this
signal counts PAUSE DAYS (sessions that failed to extend the prior
session's range in either direction) as a share of the tape, capturing
the SEQUENCE of non-extension rather than range magnitude — the two
disagree whenever drift is steady (quiet magnitude, zero inside days) or
churn is wide (large ranges, inside days present). It is not CLV (close
location within a day's own range — DEAD), not volatility level
(vol-rank tilt — DEAD), not volume (volume gates / signed accumulation —
DEAD), not streak/freshness (close-to-close order, monthly-print recency
— separate families): the boolean high/low containment relation between
consecutive sessions is a variable nothing in the chain consumes.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.13; max_hold 3 is a HARNESS
        key passed via params-json, this file does not consume it)
        + ids_lb {3, 6} (window in monthly buckets ending at the print
          month)
        + ids_w {-0.4, -0.3, -0.2, -0.1, +0.2} (percentile tilt; 0.0 =
          off-switch; negative = favour inside-day-dense, compressed tape).

Designer smoke observations (Loop-15, pre-freeze, nse_all top 15 25bps
split 2022-01-01, isolated ledger l15_dB): off-switch reproduced +88.14 /
-17.34 / 5.08, fwd +49.27 / -14.93 exactly. ids_lb 6: ids_w -0.4 -> train
+90.69 / DD -21.99 / calmar 4.12, fwd +68.57 / fwd DD -13.14; ids_w -0.3
-> train +91.71 / DD -22.92, fwd +61.98 / -13.75; ids_w -0.2 -> train
+87.27 / DD -20.37, fwd +58.89 / -13.38. Reading: the compression tilt is
the first daily-tape signal that ADDS train above the champion (+3.6pp at
-0.3) and lifts forward sharply (fwd calmar ~4.5-5.2 vs champion 3.30),
but the DD cost is monotone-ish and every screened weight breaches the
2pp DD slack (keeps need DD >= -19.34%). The untested lower weights
(-0.1, -0.15) and ids_lb 3 are where a keep could still live — screen
those first, and treat any knife-edge weight near the DD boundary with
the Loop-12 suspicion (rank-ordering artifact, do not promote without a
neighbourhood). For the forward-geometry book: ids_lb 6 / ids_w -0.4
fwd +68.57 / -13.14 (forward-calmar 5.22) is the best forward print of
the loop so far — check stacking with rs_w 0.2 / rs_lb 6 + cap_full 15 /
max_hold 6 before discarding the line.
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
    "ids_lb": [3, 6],
    "ids_w": [-0.4, -0.3, -0.2, -0.1, 0.2],
}


def _monthly_inside(daily: pl.DataFrame, months, cols) -> np.ndarray:
    """Per (calendar month, stock) the share of inside days among the
    bucket's bars; NaN where the bucket had no bars or no prior bar."""
    d = daily.with_columns(
        pl.col("high").shift(1).over("symbol").alias("ph"),
        pl.col("low").shift(1).over("symbol").alias("pl"))
    d = d.with_columns(
        pl.when(pl.col("ph").is_not_null() & pl.col("pl").is_not_null())
          .then((pl.col("high") < pl.col("ph")) & (pl.col("low") > pl.col("pl")))
          .otherwise(None)
          .alias("ins"))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("ins").cast(pl.Float64).mean())
          .sort("symbol", "date"))
    piv = g.pivot(on="symbol", index="date", values="ins").sort("date")
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
