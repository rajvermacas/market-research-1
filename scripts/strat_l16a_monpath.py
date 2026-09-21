"""Candidate: intramonth path-shape tilt on the champion book (strategy_lab
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
signal: WHERE the print month's return happened. Per calendar-month bucket
and stock, the month's daily bars are split at the calendar mid-month
(day-of-month <= 15 vs > 15) and

    r1    = close at the END of the first half / first close of the
            month  -  1                    (front half's own return)
    r2    = last close of the month / close at the END of the first
            half  -  1                      (back half's own return)
    shape = r2 - r1

shape > 0 = BACK-LOADED strength (the month accelerated into its close),
shape < 0 = FRONT-LOADED (the move was made early, the tape faded or
consolidated into month-end). Among names with a finite shape in the row
it is percentile-ranked into pct in [0, 1]:

    tilt = 1 + mp_w * (2 * pct - 1)   # mp_w > 0 favours back-loaded
    out  = (gatefail lift * ids tilt) * shape tilt   #  prints

Hypothesis: the champion buys fresh 12-month-high printers, and its one
LIVE daily-tape term rewards the EXPANDING side of the tape (ids_w < 0
favours FEWER inside days — directional extension, not the coil story the
file's original docstring told). Path shape is the natural next axis on
the same theme: month-end closes know THAT a high was printed but not
WHEN inside the month. A high printed on late-month acceleration is a
move still being paid for at the entry point; a high printed early and
consolidated since may be tired. If back-loaded prints continue better,
mp_w > 0 adds train; if the fresh-print rank already implicitly selects
for acceleration (a late-month surge is one way to reach a 12-month high),
every variant ties the champion and the channel closes. BOTH signs are
swept because the consolidation story points the other way.

Falsification test: mp_w 0.0 must reproduce the champion EXACTLY
(train +96.882% / DD -17.032% / calmar 5.688, fwd +48.973% / fwd DD
-12.311% / fwd bench +14.717%). The channel falsifies if no tested
mp_w cell beats train +96.882% within the 2pp DD slack (DD >= -19.032%).
Known-construct warning carried from Loop-15/16 experience: daily-tape
tilts on this book have so far been train-destructive in both directions
(rngcomp on the ids base, seasonality) — a result showing BOTH signs
harming train closes the channel as a double-count of tape quality the
ids term already prices.

Import chain: strat_l16a_monpath -> strat_l12b_gatefail.score (which
imports strat_floorhighfastgate + strat_floorhighsustaincond for the gate
layers and strat_floorhightiershape for rank/exposure, and applies the
wobble tilt) -> ids tilt is the champion's own term, its helper IMPORTED
as strat_l15b_insideday._monthly_inside (frozen file; reuse, never
reimplement) -> cap step mirrored inline from
strat_floorhightiershapeconc.score / strat_l13a_concwobble.score /
strat_l15b_insideday.score (identical loop: cap = cap_full where exposure
>= 1.0 else cap_weak; lower ranks set NaN after a stable descending sort).

PIT argument: NEEDS_DAILY loads the daily long panel (full window —
handled as follows). The shape is computed per calendar-month bucket from
that bucket's OWN daily bars (first close, last close with day-of-month
<= 15, last close); for score row t (holding month starting months[t]) the
newest bucket read is bucket t-1, whose bars all have date in
[months[t-1], months[t]) — strictly BEFORE months[t]; buckets t and later
are never touched, so the fact that `daily` covers the full panel window
is harmless. The percentile at row t uses only shape values from that
same backward window (bucket t-1 itself). Names with no bars in the
bucket, no first-half bar (fresh listing mid-month), or non-positive
closes keep tilt exactly 1.0 — eligibility and rank unmodified, nothing
dropped on missing data, nothing peeks. The cap reads month-t ranks only.

Off-switch identity: mp_w = 0.0 leaves the ids tilt exactly as the
champion applies it and the mirrored cap bitwise unchanged, so the flat
base IS the champion at the champion params. NOTE imported defaults leak:
strat_l12b_gatefail's own default is gf_w = 0.05 — this file setdefaults
gf_lb = 12 / gf_w = 0.0 / gw_w = 0.0 BEFORE delegating, so the off-switch
is exact and the champion's gw_w 0.15 and ids keys (ids_lb 3 / ids_w
-0.13) must be PASSED by the caller (champion keys, not defaults here).
This file's own defaults are NEUTRAL: ids_w 0.0 / mp_w 0.0.

Level-2 off-switch (ids_w 0.0 AND mp_w 0.0 at otherwise champion keys)
reproduces the wobble-only chain at gw_w 0.15: documented Loop-15
measurement gw 0.15 alone -> train +87.00 / DD -17.34.

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art — strat_l15b_insideday (the
champion's live daily-tape tilt) and the DEAD close-location (CLV) family.
The one thing changed: the SIGNAL TIMESCALE AND CONTENT. CLV reads where
each day's close sat WITHIN that day's own range (intra-day geometry) and
is dead; ids counts how many SESSIONS failed to extend the prior range
(inter-session range containment); path shape reads WHERE WITHIN THE
MONTH the return accrued — a timing/sequence variable across ~21 sessions
that no file in the chain and no inventory family consumes (monthly
closes cannot see it; range magnitude and pause counts do not measure
ordering). It is also not persistence/freshness (close-to-close order,
print recency — separate families) and not momentum level (the rank
already owns that): "half vs half" return attribution is a new variable.

SPACE = my keys: mp_w {-0.3, -0.15, 0.0, 0.15, 0.3} (percentile tilt on
        the print month's shape; 0.0 = off-switch; positive = back-loaded
        acceleration favoured). mp_lb is fixed at 1 (the print month
        itself) — the sequence-within-month is the signal; averaging it
        over months would dilute exactly the recency the hypothesis
        needs. Champion keys pinned (passed by the caller, docs only):
        b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19, lookback 12,
        max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w
        -0.13. max_hold 3 is a HARNESS key passed via params-json; this
        file does not consume it.

Designer smoke observations (Loop-16, pre-freeze, nse_all top 15 25bps
split 2022-01-01, isolated ledger l16_dA): off-switch reproduced the
champion EXACTLY — train +96.88 / DD -17.03 / calmar 5.688, fwd +48.97 /
-12.31. Live results: mp_w +0.3 -> train +69.75 / DD -27.57, fwd +62.04 /
-16.31; mp_w -0.3 -> train +62.75 / DD -18.03, fwd +32.49 / -18.48. BOTH
signs are 27-34pp below the champion on train — the acceleration story
AND the consolidation story both lose; the fresh-print rank plus the ids
term already order the cut better than within-month timing does. The
reverse arm is worst on forward too (+32.49). Falsifier FIRED: path shape
is closed on this base; do not spend worker windows on |mp_w| 0.15
(intermediate weights interpolate toward the champion, never above it —
the ordering effect is sign-symmetric harm).
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_l12b_gatefail import score as _gf_score
from strat_l15b_insideday import _monthly_inside as _ids_monthly

NEEDS_DAILY = True
SPACE = {
    # this file's keys
    "mp_w": [-0.3, -0.15, 0.0, 0.15, 0.3],
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


def _monthly_shape(daily: pl.DataFrame, months, cols) -> np.ndarray:
    """Per (calendar month bucket, stock): (r2 - r1) where the month's bars
    are split at day-of-month <= 15; NaN where the bucket lacks any needed
    anchor close."""
    d = daily.with_columns(pl.col("date").dt.day().alias("dom"))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("close").first().alias("c0"),
               pl.col("close").filter(pl.col("dom") <= 15).last().alias("c1"),
               pl.col("close").last().alias("c2"))
          .sort("symbol", "date"))
    piv = g.pivot(on="symbol", index="date", values=["c0", "c1", "c2"]).sort("date")
    mind = {}
    for i, m in enumerate(months):
        mind[m if not hasattr(m, "date") else m.date()] = i
    out = np.full((len(months), len(cols)), np.nan)
    cidx = {s: j for j, s in enumerate(cols)}
    for row in piv.iter_rows(named=True):
        i = mind.get(row["date"])
        if i is None:
            continue
        for s in cols:
            j = cidx.get(s)
            if j is None:
                continue
            c0, c1, c2 = row.get(f"c0_{s}"), row.get(f"c1_{s}"), row.get(f"c2_{s}")
            if c0 is None or c1 is None or c2 is None:
                continue
            if c0 <= 0 or c1 <= 0 or c2 <= 0:
                continue
            out[i, j] = (c2 / c1 - 1.0) - (c1 / c0 - 1.0)
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
    mp_w = float(params.get("mp_w", 0.0))
    out = np.array(lift, dtype=float, copy=True)

    tilts_per_row = [None, None]  # [ids, shape]

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

    if mp_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        SH = _monthly_shape(daily, months, cols)
        tilts = {}
        for t in range(1, lift.shape[0]):
            row = SH[t - 1]  # the print month's shape
            valid = np.isfinite(row)
            n = int(valid.sum())
            if n < 5:
                continue
            sv = row[valid]
            order = np.argsort(sv, kind="stable")
            pct = np.empty(n)
            pct[order] = np.arange(n) / (n - 1)
            tilt = np.ones(lift.shape[1])
            tilt[valid] = 1.0 + mp_w * (2.0 * pct - 1.0)
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
