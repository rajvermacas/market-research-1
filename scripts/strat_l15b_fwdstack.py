"""Candidate: the forward-geometry book carrying BOTH measured forward tilts
(strategy_lab contract).

Setup in words: the low-train/high-forward book — the champion chain
(strat_l13a_concwobble at lookback 12: floor-lift fresh-print rank among
short-trend-passing, print-continuity-passing names, breadth-tier exposure
with tier 0.9999, eligibility-wobble discount gw_w 0.13 / gf_lb 12) placed
on the forward geometry cap_full 15 / max_hold 6 — carrying BOTH forward
tilts measured in this loop, applied in sequence BEFORE the
regime-conditional cap (mirrored inline, a composition step, not an
indicator):

    rs tilt   score *= (1 + rs_w * rsdiff)      rsdiff = k-month return
              minus the panel's own equal-weight mean at the same month
              (market-relative strength; NaN rsdiff -> tilt 1.0)
    ids tilt  score *= (1 + ids_w * (2*pct - 1))   pct = cross-sectional
              percentile of the name's inside-day share over the ids_lb
              monthly buckets ending at the print month (compression;
              NaN share -> tilt 1.0)

Both tilts re-rank the SAME imported lift; the cap then cuts
cap_weak/cap_full from the re-ranked book. Multiplicative tilts commute,
so the order of application is irrelevant to the result.

Hypothesis: the two tilts were each measured alone on this loop and each
is forward-positive at train cost — rs (rs_w 0.2 / rs_lb 6) took the
geometry book to fwd +63.18 / -14.44 at train +68.93, and the inside-day
compression tilt took the champion book to fwd +68.57 / -13.14 at train
+90.69 (ids_lb 6 / ids_w -0.4). If they measure DIFFERENT quality axes —
market-relative momentum vs within-name range compression — stacking
should push the forward print beyond either alone (fwd 65-70 at fwd DD
-12 to -14). If they are the same axis ("quality of the print" read two
ways), the stack will sit at or below the better single tilt and the two
mechanisms are substitutes — which is itself the finding, because it
would collapse two designer lines into one degree of freedom.

Falsifier: if the stacked book's forward does not exceed the better of
the two single-tilt forwards on the same geometry (rs-only fwd +63.18 /
-14.44; ids-only is not yet measured on the geometry — the SPACE's
rs_w 0.0 arms supply that control), or if the stack's train collapses
below the rs-only base without any forward compensation, then the two
tilts are substitutes and only one should be carried. As always,
selection stays train-side; this file exists to document the forward
geometry interaction, not to ratchet it.

Import chain: strat_l15b_fwdstack -> strat_l12b_gatefail.score (the
champion lift: strat_floorhightiershape rank/exposure + fastgate +
sustaincond gate layers + the gw_w 0.13 wobble discount, gf_w FORCED 0.0)
-> rs term IMPORTED as strat_l14b_relstrength._rsdiff (the rs math exists
only inline in that file's score(), which applies its own cap and cannot
be reused whole; its module-level helper is imported instead of
re-derived, so the two files cannot drift) -> ids term IMPORTED as
strat_l15b_insideday._monthly_inside (that file is FROZEN mid-screen;
importing its helper neither copies nor edits it — reuse, never
reimplement) -> cap step mirrored inline from
strat_floorhightiershapeconc.score / strat_l13a_concwobble.score /
strat_l14b_relstrength.score (identical loop: cap = cap_full where
exposure >= 1.0 else cap_weak; lower ranks set NaN after a stable
descending sort).

PIT argument: the rs tilt reads only month-end closes through px[t]
(rows t and t-rs_lb of panels["px"], both already past at decision time);
rs_mean is a same-row cross-sectional mean over the panel's own names —
no index series, nothing leaves the panel. The ids tilt reads the daily
long panel grouped into calendar-month buckets; for score row t (holding
month starting months[t]) the newest bucket read is bucket t-1, whose
bars all have date in [months[t-1], months[t]) — strictly BEFORE
months[t]; buckets t and later are never touched, so the fact that
`daily` covers the full panel window is harmless. No forward rows
anywhere; names with undefined rs or NaN inside-day share read tilt
exactly 1.0 (no tilt on thin history, no eligibility change); the
percentile at row t uses only share values from that same backward
window; the cap reads month-t ranks only.

Off-switch identity: rs_w = 0.0 AND ids_w = 0.0 make both tilts exactly
1.0 for every name (1.0 + 0.0*finite, and 1.0 where the signal is NaN),
so the score is bitwise the gatefail lift and the mirrored cap yields
bitwise the champion's book at the same params — expected train
+88.139% / DD -17.339% / calmar 5.083, fwd +49.274% / fwd DD -14.926% /
fwd bench +14.717% at the champion geometry (cap_full 20, max_hold 3).
With ONLY the ids tilt off (ids_w 0.0, rs_w 0.2 / rs_lb 6, cap_full 15 /
max_hold 6) the file must reproduce the geometry+rs base measured in
l15_wA via strat_l14b_relstrength — expected train +68.925% / DD
-19.700%, fwd +63.181% / fwd DD -14.437%. NOTE imported defaults leak:
strat_l12b_gatefail's own default is gf_w = 0.05 — this file setdefaults
gf_lb = 12 / gw_w = 0.13 and FORCES gf_w = 0.0 BEFORE delegating (an
override, not a setdefault — the gate-failure leg is dead on this base
and the champion's wobble discount passes through gw_w), so both
off-switch levels are exact.

Flat-base metric (off-switch must reproduce exactly): Level 1 — champion
at champion geometry: train +88.139% / DD -17.339% / calmar 5.083 / H1
+80.14% / H2 +96.09% / invested 65.5% / fwd +49.274% / fwd DD -14.926% /
fwd bench +14.717%. Level 2 — geometry+rs base: train +68.925% / DD
-19.700%, fwd +63.181% / fwd DD -14.437% (l15_wA row, run through
strat_l14b_relstrength at cap_full 15 / max_hold 6 / rs_lb 6 / rs_w 0.2).

NOVELTY STATEMENT: closest prior art — (a) strat_l14b_relstrength
(PARTIAL line in the inventory: market-relative strength, forward-positive
/ train-negative, stacks with the forward geometry), and (b)
strat_l15b_insideday (this loop's only train-beating signal: inside-day
compression, forward-positive at negative weights). Both are single-tilt
compositions onto the same champion lift. The ONE thing changed: the two
tilts have NEVER been combined — no ledger row anywhere carries both
rs_w > 0 and ids_w != 0 (verified against l15_wA/wB/wD tails before
writing). This file is the add-vs-substitute experiment for the two
forward tilt lines; if the evidence shows they are substitutes, that
collapses two mechanisms into one axis and is the finding, not a failure.

SPACE = my keys only: rs_lb {6}, rs_w {0.0, 0.2}, ids_lb {6},
        ids_w {0.0, -0.2, -0.4} — six (rs_w, ids_w) combinations at
        rs_lb 6 / ids_lb 6. Geometry keys pinned: cap_full 15 / max_hold 6
        (max_hold is a HARNESS key passed via params-json; this file does
        not consume it). Champion keys pinned: b_hi 0.69, b_lo 0.45,
        b_mid 0.55, floor_lb 19, lookback 12, max_dist 0.055, regime_ma 18,
        fast_ma 5, sustain_lo 3, sustain_hi 2, tier_lo 0.9999,
        tier_mid 0.9999, cap_weak 11, gf_lb 12, gf_w 0.0, gw_w 0.13.
        Note the rs_w 0.0 arms double as the missing ids-only control on
        this geometry — screen them to complete the add-vs-substitute
        table.

Designer smoke observations (Loop-15 round 3, pre-freeze, nse_all top 15
25bps split 2022-01-01, isolated ledger l15_dB): BOTH off-switch levels
reproduced bit-exact — Level 1 (rs_w 0, ids_w 0, cap_full 20 / max_hold 3):
train +88.14 / DD -17.34 / calmar 5.08, fwd +49.27 / -14.93; Level 2
(ids_w 0, rs_w 0.2 / rs_lb 6, cap_full 15 / max_hold 6): train +68.93 /
DD -19.70, fwd +63.18 / -14.44 (= the l15_wA relstrength row). Stack arms
(same geometry): rs 0.2 + ids -0.2 -> train +74.09 / DD -21.71, fwd
+68.03 / fwd DD -15.97 (fwd-calmar 4.26); rs 0.2 + ids -0.4 -> train
+70.78 / DD -21.66, fwd +67.49 / -16.98 (fwd-calmar 3.97). Reading:
versus the rs-only base the stack ADDS forward return (+4.3 to +4.9pp)
and train (+1.9 to +5.2pp) — the tilts are NOT the same axis (a pure
substitute would have left fwd at ~63) — but the ids tilt carries its
fwd-DD cost with it (-1.5 to -2.5pp), so forward-CALMAR does not improve
(4.26 / 3.97 vs rs-only 4.38). Best balanced cell: ids -0.2 (fwd +68.03
at -15.97, train +74.09). The geometry+ids-only control (rs_w 0.0,
ids_w -0.2/-0.4) is unmeasured — it is in the SPACE; screen it to
complete the table before promoting either line. All geometry arms
breach the champion's train-DD slack (floor -19.34%) — forward-geometry
documentation, not ratchet candidates.
"""

from __future__ import annotations

import warnings

import numpy as np

from strat_l12b_gatefail import score as _gf_score
from strat_l14b_relstrength import _rsdiff as _rs_diff
from strat_l15b_insideday import _monthly_inside as _ids_monthly

NEEDS_DAILY = True
SPACE = {
    # my keys
    "rs_lb": [6],
    "rs_w": [0.0, 0.2],
    "ids_lb": [6],
    "ids_w": [0.0, -0.2, -0.4],
    # geometry keys (pinned)
    "cap_full": [15],
    # max_hold 6 is a harness key via params-json (documented, not consumed here)
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
    "gf_lb": [12],
    "gf_w": [0.0],
    "gw_w": [0.13],
}


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating: gatefail's own gf_w default (0.05)
    # would leak into the off-switch. gf_w is FORCED (champion keeps the
    # gate-failure leg off); gw_w/gf_lb default to the champion values.
    p.setdefault("gf_lb", 12)
    p.setdefault("gw_w", 0.13)
    p["gf_w"] = 0.0
    lift, exposure = _gf_score(panels, p)

    rs_w = float(params.get("rs_w", 0.0))
    ids_w = float(params.get("ids_w", 0.0))

    r = _rs_diff(panels["px"], int(params.get("rs_lb", 6))) if rs_w != 0.0 else None

    ids_tilt_per_row = None
    if ids_w != 0.0:
        months, cols = panels["months"], panels["cols"]
        ilb = int(params.get("ids_lb", 6))
        IDS = _ids_monthly(panels["daily"], months, cols)
        ids_tilt_per_row = []
        for t in range(1, lift.shape[0]):
            lo = t - ilb
            if lo < 0:
                ids_tilt_per_row.append(None)
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
            ids_tilt_per_row.append(tilt)

    out = np.array(lift, dtype=float, copy=True)
    for t in range(out.shape[0]):
        row = out[t]
        if r is not None:
            tilt = 1.0 + rs_w * r[t]
            tilt = np.where(np.isfinite(r[t]), tilt, 1.0)
            o = np.isfinite(row)
            row = np.where(o, row * tilt, np.nan)
        if ids_tilt_per_row is not None and t >= 1:
            tilt = ids_tilt_per_row[t - 1]
            if tilt is not None:
                o = np.isfinite(row)
                row = np.where(o, row * tilt, np.nan)
        out[t] = row

    # cap step mirrored inline from strat_floorhightiershapeconc.score /
    # strat_l13a_concwobble.score / strat_l14b_relstrength.score
    # (book-size composition, not an indicator)
    cw = int(params.get("cap_weak", 11))
    cf = int(params.get("cap_full", 20))
    E = np.asarray(exposure, dtype=float)
    for t in range(out.shape[0]):
        r_row = out[t]
        fin = np.flatnonzero(np.isfinite(r_row))
        if fin.size == 0:
            continue
        cap = cf if E[t] >= 1.0 else cw
        if fin.size <= cap:
            continue
        order = fin[np.argsort(-r_row[fin], kind="stable")]
        out[t, order[cap:]] = np.nan
    return out, E
