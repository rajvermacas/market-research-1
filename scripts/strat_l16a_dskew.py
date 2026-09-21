"""Candidate: daily-return skewness tilt on the champion book (strategy_lab
contract).

Setup in words: the CURRENT champion chain — strat_l13a_concwobble at
lookback 12 (floor-lift fresh-print rank among short-trend-passing,
print-continuity-passing names, breadth-tier exposure with tier 0.9999,
regime-conditional book cap cap_weak/cap_full) carrying the
eligibility-wobble discount gw_w 0.15 / gf_lb 12 AND the inside-day
pause-share tilt ids_lb 3 / ids_w -0.13 (strat_l15b_insideday, the live
champion) — is imported wholesale via strat_l12b_gatefail.score. Before
the regime-conditional cap step (mirrored inline, a composition step, not
an indicator), the imported lift is re-weighted by a NEW daily-tape
signal: the SKEWNESS of the name's daily returns over the recent tape.

Per daily bar and symbol:

    ret_d = close_d / close_{d-1} - 1

Per calendar-month bucket:

    skew_m = sample skewness of ret_d over the bucket's bars
             (third standardised moment; NaN where fewer than 3 bars)

averaged over the `sk_lb` monthly buckets ending at the print month (the
calendar month before the holding month). Among names with a finite mean
skew in the row it is percentile-ranked into pct in [0, 1]:

    tilt = 1 + sk_w * (2 * pct - 1)   # sk_w > 0 favours lottery-like
    out  = (gatefail lift * ids tilt) * skew tilt   #  positive-skew tape

Hypothesis: the champion's one LIVE daily-tape term rewards the EXPANDING
side of the tape (ids_w < 0 favours FEWER inside days — directional
extension). Skewness is the third-moment expression of the same physics
the inside-day count sees only as containment: a tape printing a few
large up-moves among many small sessions is a directional, expanding tape
(positive skew), while a tape with big moves in both directions is
churn (near-zero skew) and one with large down-moves among small up ones
is distribution (negative skew). If lottery-like positive-skew tapes
continue better after a fresh 12-month high, sk_w > 0 adds train; the
lottery-demand literature points the other way (high-skew names attract
attention-driven overpricing that then mean-reverts), so BOTH signs are
swept. If the fresh-print rank, gates and the ids term already price the
tape's asymmetry, every variant ties the champion and the channel closes.

Falsification test: sk_w 0.0 must reproduce the champion EXACTLY
(train +96.882% / DD -17.032% / calmar 5.688, fwd +48.973% / fwd DD
-12.311% / fwd bench +14.717%). The channel falsifies if no tested
(sk_lb, sk_w) cell beats train +96.882% within the 2pp DD slack
(DD >= -19.032%). Loop-16 designer context: every per-name
tape/return-history tilt re-based onto this champion this loop
(rngcomp continuous compression, same-calendar-month seasonality,
within-month path shape) was train-destructive in BOTH directions by
18-34pp — the prior here is that the ids term has soaked up the
tape-quality axis; a live skew result must beat that prior, not just tie.

Import chain: strat_l16a_dskew -> strat_l12b_gatefail.score (which
imports strat_floorhighfastgate + strat_floorhighsustaincond for the gate
layers and strat_floorhightiershape for rank/exposure, and applies the
wobble tilt) -> ids tilt is the champion's own term, its helper IMPORTED
as strat_l15b_insideday._monthly_inside (frozen file; reuse, never
reimplement) -> cap step mirrored inline from
strat_floorhightiershapeconc.score / strat_l13a_concwobble.score /
strat_l15b_insideday.score (identical loop: cap = cap_full where exposure
>= 1.0 else cap_weak; lower ranks set NaN after a stable descending sort).

PIT argument: NEEDS_DAILY loads the daily long panel (full window —
handled as follows). ret_d uses close_{d-1} from the SAME symbol's prior
bar (shift within symbol over dates sorted ascending) — no future bar.
Buckets are calendar months via group_by_dynamic("1mo"); for score row t
(holding month starting months[t]) the newest bucket read is bucket t-1,
whose bars all have date in [months[t-1], months[t]) — strictly BEFORE
months[t]; the window mean covers buckets [t-sk_lb, t-1], never bucket t
or later, so the fact that `daily` covers the full panel window is
harmless. The percentile at row t uses only skew values from that same
backward window. Rows with insufficient history (t < sk_lb) and names
with too few bars in a bucket (skew NaN -> bucket ignored by nanmean) or
no finite window mean keep tilt exactly 1.0 — eligibility and rank
unmodified, nothing dropped on missing data, nothing peeks. The cap reads
month-t ranks only.

Off-switch identity: sk_w = 0.0 leaves the ids tilt exactly as the
champion applies it and the mirrored cap bitwise unchanged, so the flat
base IS the champion at the champion params. NOTE imported defaults leak:
strat_l12b_gatefail's own default is gf_w = 0.05 — this file setdefaults
gf_lb = 12 / gf_w = 0.0 / gw_w = 0.0 BEFORE delegating, so the off-switch
is exact and the champion's gw_w 0.15 and ids keys (ids_lb 3 / ids_w
-0.13) must be PASSED by the caller (champion keys, not defaults here).
This file's own defaults are NEUTRAL: ids_w 0.0 / sk_w 0.0.

Level-2 off-switch (ids_w 0.0 AND sk_w 0.0 at otherwise champion keys)
reproduces the wobble-only chain at gw_w 0.15: documented Loop-15
measurement gw 0.15 alone -> train +87.00 / DD -17.34.

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art — strat_l15b_rngcomp (daily true
RANGE over close: second moment, level) and strat_l15b_insideday
(inside-day COUNT: inter-session range containment, live in the
champion). The one thing changed: the SIGNAL MOMENT. Skewness is the
standardised THIRD moment of the daily return distribution — signed
asymmetry of move sizes, which neither a range magnitude (unsigned,
symmetric in up/down) nor a containment count (unsigned boolean per
session) can express: a tape with one +9% day among flat sessions and a
tape with one -9% day among flat sessions have identical range statistics
and identical inside-day counts but opposite skews. No inventory family
and no file in the chain reads any higher moment of the daily return
distribution; "same signal, new shape" does not apply.

SPACE = my keys: sk_lb {3} (buckets averaged, ending at the print month;
        pinned — the recency horizon that works for ids) x sk_w {-0.2,
        0.0, +0.2} (percentile tilt; 0.0 = off-switch; positive = favour
        positive-skew / lottery-like tape). Champion keys pinned (passed
        by the caller, docs only): b_hi 0.69, b_lo 0.45, b_mid 0.55,
        floor_lb 19, lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5,
        sustain_lo 3, sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999,
        cap_weak 11, cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3,
        ids_w -0.13. max_hold 3 is a HARNESS key passed via params-json;
        this file does not consume it.

Designer smoke observations (Loop-16, pre-freeze, nse_all top 15 25bps
split 2022-01-01, isolated ledger l16_dA): off-switch reproduced the
champion EXACTLY — train +96.88 / DD -17.03 / calmar 5.688, fwd +48.97 /
-12.31. Live results: sk_w +0.2 / sk_lb 3 -> train +74.44 / DD -23.08,
fwd +57.66 / fwd DD -11.90 (fwd-calmar 4.85 — above the champion's 3.98);
sk_w -0.2 -> train +78.01 / DD -21.05, fwd +47.38 / -21.56. Both
directions are 18-22pp below the champion on train — falsifier FIRED for
the train-CAGR ruler, consistent with every other per-name
tape/return-history tilt re-based this loop. The +0.2 arm is the one
notable forward print of the batch (fwd +57.66 at fwd DD -11.90, the best
fwd-calmar of my four files) — a documented forward-alternative, NOT a
ratchet candidate (selection stays train-side; it cannot pass the cagr
ratchet 22pp below best). Do not spend worker windows on sk_lb 6 or
|sk_w| 0.1: the ordering effect is sign-symmetric harm and intermediate
weights interpolate toward the champion, never above it.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_l12b_gatefail import score as _gf_score
from strat_l15b_insideday import _monthly_inside as _ids_monthly

NEEDS_DAILY = True
SPACE = {
    # this file's keys
    "sk_lb": [3],
    "sk_w": [-0.2, 0.0, 0.2],
    # ids keys (champion-pinned, passed by the caller)
    "ids_lb": [3],
    "ids_w": [-0.13],
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
}


def _monthly_skew(daily: pl.DataFrame, months, cols) -> np.ndarray:
    """Per (calendar month bucket, stock) the sample skewness of that
    bucket's daily close-to-close returns; NaN where fewer than 3 valid
    returns."""
    d = daily.with_columns(
        pl.col("close").shift(1).over("symbol").alias("pc"))
    d = d.with_columns(
        pl.when((pl.col("pc") > 0) & (pl.col("close") > 0))
          .then(pl.col("close") / pl.col("pc") - 1.0)
          .otherwise(None)
          .alias("ret"))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("ret").skew())
          .sort("symbol", "date"))
    piv = g.pivot(on="symbol", index="date", values="ret").sort("date")
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
    import warnings

    p = dict(params)
    # neutral defaults BEFORE delegating: gatefail's own gf_w default (0.05)
    # would leak into the off-switch. Champion values (gw_w 0.15, ids keys)
    # are passed by the caller, not defaulted here.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    lift, exposure = _gf_score(panels, p)

    ids_w = float(params.get("ids_w", 0.0))
    sk_w = float(params.get("sk_w", 0.0))
    out = np.array(lift, dtype=float, copy=True)

    tilts_per_row = [None, None]  # [ids, skew]

    if ids_w != 0.0:
        months, cols = panels["months"], panels["cols"]
        ilb = int(params.get("ids_lb", 3))
        IDS = _ids_monthly(panels["daily"], months, cols)
        tilts = {}
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
            tilts[t] = tilt
        tilts_per_row[0] = tilts

    if sk_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        slb = int(params.get("sk_lb", 3))
        SK = _monthly_skew(daily, months, cols)
        tilts = {}
        for t in range(1, lift.shape[0]):
            lo = t - slb
            if lo < 0:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                ms = np.nanmean(SK[lo:t], axis=0)
            valid = np.isfinite(ms)
            n = int(valid.sum())
            if n < 5:
                continue
            sv = ms[valid]
            order = np.argsort(sv, kind="stable")
            pct = np.empty(n)
            pct[order] = np.arange(n) / (n - 1)
            tilt = np.ones(lift.shape[1])
            tilt[valid] = 1.0 + sk_w * (2.0 * pct - 1.0)
            tilts[t] = tilt
        tilts_per_row[1] = tilts

    for t in range(out.shape[0]):
        row = out[t]
        for tilts in tilts_per_row:
            if tilts is not None and t in tilts:
                tilt = tilts[t]
                o = np.isfinite(row)
                row = np.where(o, row * tilt, np.nan)
        out[t] = row

    # cap step mirrored inline from strat_floorhightiershapeconc.score /
    # strat_l13a_concwobble.score / strat_l15b_insideday.score (book-size
    # composition, not an indicator)
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
