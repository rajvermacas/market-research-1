"""Candidate: same-calendar-month seasonal-momentum tilt on the champion
book (strategy_lab contract).

Setup in words: the CURRENT champion chain — strat_l13a_concwobble at
lookback 12 (floor-lift fresh-print rank among short-trend-passing,
print-continuity-passing names, breadth-tier exposure with tier 0.9999,
regime-conditional book cap cap_weak/cap_full) carrying the
eligibility-wobble discount gw_w 0.15 / gf_lb 12 AND the inside-day
pause-share tilt ids_lb 3 / ids_w -0.13 (strat_l15b_insideday, the live
champion) — is imported wholesale via strat_l12b_gatefail.score. Before
the regime-conditional cap step (mirrored inline, a composition step, not
an indicator), the imported lift is re-weighted by a NEW signal read from
the daily panel: the name's SEASONAL MOMENTUM — its mean return in the
same calendar month over prior years (Heston–Sadka seasonality).

Per (stock, calendar month m = 1..12), using daily closes grouped into
calendar-month buckets:

    r_{k,m}  = last close of bucket m in year k / last close of the
               PRIOR bucket  -  1          (the month's own return)
    seas_{m} = mean of r_{k,m} over the prior years k with a valid pair
               (the CURRENT year's bucket is EXCLUDED — the signal must
               never read the month being entered)

Among names with a finite seasonal mean in the row it is
percentile-ranked into pct in [0, 1]:

    tilt = 1 + seas_w * (2 * pct - 1)   # seas_w > 0 favours seasonally
    out  = (gatefail lift * ids tilt) * seas tilt   #  strong months

Hypothesis: the champion buys fresh 12-month-high printers. Month-end
closes know the calendar date but not what the calendar date MEANS for
that name: results season, advance-tax flows, dividend/record-date
clusters, budget/FY effects land in specific months per stock and repeat
year after year (Heston–Sadka find cross-sectional seasonalities in
individual-stock monthly returns that persist out-of-sample). If fresh
prints continue better in the names' own seasonally strong months,
seas_w > 0 lifts the top-15 cut's quality; if the fresh-print rank already
implicitly selects for seasonal strength (a 12-month high is itself 1/12
made of this month's history), every variant ties the champion and the
channel closes.

Falsification test: seas_w 0.0 must reproduce the champion EXACTLY
(train +96.882% / DD -17.032% / calmar 5.688, fwd +48.973% / fwd DD
-12.311% / fwd bench +14.717%). The channel falsifies if no tested
(seas_lb, seas_w) cell beats train +96.882% within the 2pp DD slack
(DD >= -19.032%). A KNOWN-CONSTRUCT secondary signature: Loop-15's
daily-tape tilts (rngcomp, ids) both traded train for forward or the
reverse — if the seasonal tilt also shows a monotone sign flip between
windows, treat it as another compression-like quality axis, not an
independent return predictor.

Import chain: strat_l16a_seasmom -> strat_l12b_gatefail.score (which
imports strat_floorhighfastgate + strat_floorhighsustaincond for the gate
layers and strat_floorhightiershape for rank/exposure, and applies the
wobble tilt) -> ids term IMPORTED as strat_l15b_insideday._monthly_inside
(the champion's own tilt helper; reuse, never reimplement) -> cap step
mirrored inline from strat_floorhightiershapeconc.score /
strat_l13a_concwobble.score / strat_l15b_insideday.score (identical loop:
cap = cap_full where exposure >= 1.0 else cap_weak; lower ranks set NaN
after a stable descending sort).

PIT argument: NEEDS_DAILY loads the daily long panel (full window —
handled as follows). Monthly returns are built from calendar-month bucket
last-closes via group_by_dynamic("1mo"); the return r_{k,m} uses the
bucket's own last close and the PRIOR bucket's last close — both strictly
before the bucket's end, never a future bar. For score row t (holding
month starting months[t]) the seasonal mean targets the calendar month of
months[t] — the month being ENTERED — and averages only PRIOR-YEAR
occurrences of that month (buckets t-12, t-24, ...), each verified by its
calendar month so a missing bucket cannot alias onto a different month;
the current year's occurrence has no bars before months[t] at decision
time, so the exclusion is physical. The newest bar read is the last close
of bucket t-12, dated inside [months[t-12], months[t-11)) — strictly
BEFORE months[t]; no bar inside the holding month is ever read.
Percentiles at row t use only seasonal means from that same backward
window. Rows with insufficient history (fewer than seas_min valid prior
years) and names with no bars keep tilt exactly 1.0 — eligibility and
rank unmodified, nothing dropped on missing data, nothing peeks. The cap
reads month-t ranks only.

Off-switch identity: seas_w = 0.0 leaves the ids tilt exactly as the
champion applies it and the mirrored cap bitwise unchanged, so the flat
base IS the champion at the champion params. NOTE imported defaults leak:
strat_l12b_gatefail's own default is gf_w = 0.05 — this file setdefaults
gf_lb = 12 / gf_w = 0.0 / gw_w = 0.0 BEFORE delegating, so the off-switch
is exact and the champion's gw_w 0.15 and ids keys (ids_lb 3 / ids_w
-0.13) must be PASSED by the caller (champion keys, not defaults here).
This file's own defaults are NEUTRAL: ids_w 0.0 / seas_w 0.0.

Level-2 off-switch (ids_w 0.0 AND seas_w 0.0 at otherwise champion keys)
reproduces the wobble-only chain at gw_w 0.15: documented Loop-15
measurement gw 0.15 alone -> train +87.00 / DD -17.34.

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

NOVELTY STATEMENT: the mechanism inventory has NO entry for seasonality —
no same-calendar-month, turn-of-month, holiday, or any calendar-anchored
per-name signal (the breadth-tier exposure reads the PANEL's advancing
share, a cross-sectional regime — not a per-name calendar effect).
Closest prior art is strat_l15b_insideday (the champion's daily-tape tilt):
both re-weight the imported lift with a per-name signal percentile-ranked
within the row. The one thing changed: the SIGNAL — the daily tape's
range geometry is replaced by the return history of the same calendar
month in prior years, an axis (per-name calendar anchoring) that no file
in the chain and no inventory family consumes. "Same signal, new shape"
it is not: nothing in the book reads the calendar month of the holding
month.

SPACE = my keys: seas_lb {3, 6} (max prior years averaged; all valid
        prior years up to seas_lb are averaged — the effective window is
        min(seas_lb, available history)) x seas_w {-0.2, 0.0, +0.2} —
        six cells; seas_w 0.0 arms are the off-switch, seas_w +0.2 is the
        Heston–Sadka direction (buy seasonally strong months), -0.2 the
        reverse control. seas_min 3 (a name needs >= 3 valid prior years
        of its calendar month or it keeps tilt 1.0 — pinned, not swept).
        Champion keys pinned (passed by the caller, docs only): b_hi 0.69,
        b_lo 0.45, b_mid 0.55, floor_lb 19, lookback 12, max_dist 0.055,
        regime_ma 18, fast_ma 5, sustain_lo 3, sustain_hi 2, tier_lo
        0.9999, tier_mid 0.9999, cap_weak 11, cap_full 20, gf_lb 12,
        gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13. max_hold 3 is a
        HARNESS key passed via params-json; this file does not consume it.

Designer smoke observations (Loop-16, pre-freeze, nse_all top 15 25bps
split 2022-01-01, isolated ledger l16_dA): off-switch reproduced the
champion EXACTLY — train +96.88 / DD -17.03 / calmar 5.688, fwd +48.97 /
-12.31. First +0.2 arm printed bitwise-identical to the off-switch: that
was a DESIGNER BUG (target month off by one — the seasonal mean targeted
the print month's calendar via cal[t-1] and checked candidates at
cal[k-1], which never matches, so every row stayed tilt 1.0 and the tilt
was silently dead). Fixed to target the month being ENTERED (cal[t],
candidates checked at cal[k]) BEFORE delivery; off-switch re-verified
exact after the fix. Live results: seas_w +0.2 / seas_lb 3 -> train
+70.16 / DD -26.52, fwd +46.05 / -15.90; seas_w -0.2 / seas_lb 3 -> train
+78.61 / DD -22.74, fwd +61.70 / -17.33. BOTH directions are 18-27pp
below the champion on train with worse DD — reordering the fresh-print
book by past same-calendar-month returns fights the rank in either
direction; the reverse arm's forward print (+61.70) carries a worse fwd DD
than the champion (-12.31). Falsifier FIRED for the train-CAGR ruler:
seasonality adds nothing on this base. Do not spend worker windows on
seas_lb 6 or |seas_w| 0.1 (intermediate weights interpolate toward the
champion, never above it — the ordering effect is sign-symmetric harm).
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_l12b_gatefail import score as _gf_score
from strat_l15b_insideday import _monthly_inside as _ids_monthly

NEEDS_DAILY = True
SPACE = {
    # this file's keys
    "seas_lb": [3, 6],
    "seas_w": [-0.2, 0.0, 0.2],
    "seas_min": [3],
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


def _monthly_last_close(daily: pl.DataFrame, months, cols) -> np.ndarray:
    """Per (calendar month bucket, stock) the LAST daily close of the
    bucket; NaN where the bucket had no bars. Bucket index i aligns with
    months[i] (the bucket STARTING at that month start)."""
    g = (daily.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("close").last())
          .sort("symbol", "date"))
    piv = g.pivot(on="symbol", index="date", values="close").sort("date")
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


def _seasonal_scores(px_m: np.ndarray, months, seas_lb: int,
                     seas_min: int) -> np.ndarray:
    """Row t: the name's mean return in the SAME calendar month as the
    month being ENTERED (months[t]) over PRIOR YEARS, computed from bucket
    last-closes. The current year's occurrence of that calendar month has
    no data at decision time (its bars lie inside the holding month), so
    only prior-year buckets are averaged — the exclusion is physical, not
    a rule. NaN where fewer than seas_min valid prior years exist.

    Bucket indexing: bucket i starts at months[i], px_m[i] is its LAST
    close; the calendar-month return of bucket k is px_m[k] / px_m[k-1]
    - 1 (last close over the PRIOR bucket's last close). Prior-year
    occurrences are found by stepping back 12 buckets from t; each
    candidate k must satisfy cal[k] == cal[t] so a missing bucket cannot
    alias the signal onto a different month.
    """
    n_rows, n_cols = px_m.shape
    out = np.full((n_rows, n_cols), np.nan)
    cal = np.array([m.month for m in months])

    def _bucket_ret(k: int) -> np.ndarray:
        with np.errstate(invalid="ignore", divide="ignore"):
            r = px_m[k] / px_m[k - 1] - 1.0
        return np.where((px_m[k - 1] > 0) & np.isfinite(px_m[k])
                        & np.isfinite(px_m[k - 1]), r, np.nan)

    for t in range(12, n_rows):
        target_cal = cal[t]  # calendar month of the month being entered
        vals = []
        k = t - 12  # most recent PRIOR-YEAR bucket of the same month
        while k >= 1 and len(vals) < seas_lb:
            if cal[k] == target_cal:
                vals.append(_bucket_ret(k))
            k -= 12
        if len(vals) < seas_min:
            continue
        mean = np.nanmean(np.vstack(vals), axis=0)
        out[t] = np.where(np.isfinite(mean), mean, np.nan)
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
    seas_w = float(params.get("seas_w", 0.0))
    out = np.array(lift, dtype=float, copy=True)

    tilts_per_row = [None, None]  # [ids, seas]

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

    if seas_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        slb = int(params.get("seas_lb", 3))
        smin = int(params.get("seas_min", 3))
        P = _monthly_last_close(daily, months, cols)
        with np.errstate(invalid="ignore"):
            SEAS = _seasonal_scores(P, months, slb, smin)
        tilts = {}
        for t in range(1, lift.shape[0]):
            row = SEAS[t]
            if not np.isfinite(row).any():
                continue
            valid = np.isfinite(row)
            n = int(valid.sum())
            tilt = np.ones(lift.shape[1])
            if n >= 5:
                sv = row[valid]
                order = np.argsort(sv, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + seas_w * (2.0 * pct - 1.0)
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
