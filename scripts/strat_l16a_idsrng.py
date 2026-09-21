"""Candidate: continuous range-compression tilt RE-BASED onto the ids
champion chain (strategy_lab contract).

Setup in words: the CURRENT champion chain — strat_l13a_concwobble at
lookback 12 (floor-lift fresh-print rank among short-trend-passing,
print-continuity-passing names, breadth-tier exposure with tier 0.9999,
regime-conditional book cap cap_weak/cap_full) carrying the
eligibility-wobble discount gw_w 0.15 / gf_lb 12 AND the inside-day
pause-share tilt ids_lb 3 / ids_w -0.13 (strat_l15b_insideday, the live
champion) — is imported wholesale via strat_l12b_gatefail.score. Before
the regime-conditional cap step (mirrored inline, a composition step, not
an indicator), the imported lift is re-weighted by a SECOND daily-tape
tilt imported from strat_l15b_rngcomp: the name's print-month mean true
range DIVIDED BY ITS OWN trailing baseline —

    tr_d    = max(high_d - low_d, |high_d - close_{d-1}|, |low_d - close_{d-1}|)
    mtr_m   = mean over month m of tr_d / close_d          (unitless)
    base_m  = mean of mtr over the cmp_lb buckets ending BEFORE the print
              month (print month excluded)
    ratio_m = mtr_{print} / base_m

Among names with a finite ratio in the row, ratio is percentile-ranked
into pct in [0, 1] and

    tilt = 1 + cmp_w * (2 * pct - 1)   # cmp_w < 0 favours COMPRESSED prints
    out  = (gatefail lift * ids tilt) * cmp tilt

The ids tilt (percentile of inside-day share over ids_lb buckets ending
at the print month, ids_w < 0 favouring pause-dense tape) is applied
exactly as the champion applies it. Multiplicative tilts commute, so the
application order is irrelevant. The cap then cuts cap_weak/cap_full from
the re-ranked book.

Why re-base (novelty duty): the rngcomp tilt has ONLY ever been tested on
the PRE-ids chain — its Loop-15 smoke ran on the l13 concwobble base
(flat base train +88.139% / DD -17.339%) where it read train-negative /
forward-positive (cmp_w -0.4 / cmp_lb 6 -> train +75.39 / fwd +60.94 /
fwd DD -11.61). The champion has since moved: the ids term (+9.9pp train
at gw 0.15) is now part of the base, and it measures a DISCRETE
compression proxy (count of pause days) while rngcomp measures the
CONTINUOUS one (range magnitude vs the name's own regime). Whether the
continuous signal still carries information once the discrete one is
already priced into the book — or whether the two are the same axis read
twice — is exactly what this screen answers. A same-axis verdict collapses
two designer lines into one degree of freedom; a both-stack verdict is a
new champion candidate.

Hypothesis: the champion buys fresh 12-month-high printers whose recent
tape was NOT pause-dense is already discounted; the remaining question is
whether the print month itself traded tighter or wider than the name's own
recent regime. A breakout out of a tight coil (ratio << 1) is supply
exhaustion before release; the same fresh high after already-expanding
ranges is a late, extended entry. If compression still ranks quality
WITHIN the ids book, cmp_w < 0 adds train above +96.882 within DD slack;
if the ids term already encodes it, every variant ties the champion and
the continuous channel closes as a substitute for the discrete one.

Falsification test: cmp_w 0.0 must reproduce the champion EXACTLY
(train +96.882% / DD -17.032% / calmar 5.688, fwd +48.973% / fwd DD
-12.311% / fwd bench +14.717%). The channel falsifies if no tested
(cmp_lb, cmp_w) cell beats train +96.882% within the 2pp DD slack
(DD >= -19.032%) AND none improves forward risk-adjusted numbers over the
champion (fwd-calmar 3.98). A forward-positive / train-negative result on
this base would mirror the pre-ids signature and close the line as
selection-incompatible (document it; check stacking with the forward
geometry rs_w 0.2 / rs_lb 6 + cap_full 15 / max_hold 6 before discarding,
per the Loop-15 convention).

Import chain: strat_l16a_idsrng -> strat_l12b_gatefail.score (which
imports strat_floorhighfastgate + strat_floorhighsustaincond for the gate
layers and strat_floorhightiershape for rank/exposure, and applies the
wobble tilt) -> ids term IMPORTED as strat_l15b_insideday._monthly_inside
and cmp term IMPORTED as strat_l15b_rngcomp._monthly_mtr (both files are
FROZEN; importing their helpers neither copies nor edits them — reuse,
never reimplement) -> cap step mirrored inline from
strat_floorhightiershapeconc.score / strat_l13a_concwobble.score /
strat_l15b_insideday.score (identical loop: cap = cap_full where exposure
>= 1.0 else cap_weak; lower ranks set NaN after a stable descending sort).

PIT argument: the ids tilt reads the daily long panel grouped into
calendar-month buckets; for score row t (holding month starting months[t])
the newest bucket read is bucket t-1, whose bars all have date in
[months[t-1], months[t]) — strictly BEFORE months[t]; buckets t and later
are never touched, so the fact that `daily` covers the full panel window
is harmless. The cmp tilt reads the same bucket discipline: ratio at row t
uses mtr of bucket t-1 divided by a mean over buckets [t-1-cmp_lb, t-1),
all strictly before months[t]. tr_d uses close_{d-1} from the SAME
symbol's prior bar (shift within symbol over sorted dates), never a future
bar. Both percentiles at row t use only signal values from that same
backward window. Rows with insufficient history and names with NaN signal
keep tilt exactly 1.0 — eligibility and rank unmodified, nothing dropped
on missing data, nothing peeks. The cap reads month-t ranks only.

Off-switch identity: cmp_w = 0.0 leaves the ids tilt as the champion
applies it and the mirrored cap bitwise unchanged, so the flat base IS the
champion at the champion params. NOTE imported defaults leak:
strat_l12b_gatefail's own default is gf_w = 0.05 — this file setdefaults
gf_lb = 12 / gf_w = 0.0 / gw_w = 0.0 BEFORE delegating, so the off-switch
is exact and the champion's gw_w 0.15 and ids keys (ids_lb 3 / ids_w
-0.13) must be PASSED by the caller (champion keys, not defaults here).
This file's own defaults are NEUTRAL: ids_w 0.0 / cmp_w 0.0.

Level-2 off-switch (ids_w 0.0 AND cmp_w 0.0 at otherwise champion keys)
reproduces the wobble-only chain at gw_w 0.15: documented Loop-15
measurement gw 0.15 alone -> train +87.00 / DD -17.34.

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / invested 65.5% /
fwd +48.973% / fwd DD -12.311% / fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art — (a) strat_l15b_rngcomp, whose
continuous compression tilt this file re-bases, and (b)
strat_l15b_insideday, the live champion whose discrete pause-count tilt is
already IN the base. The one thing changed: the BASE. The rngcomp tilt has
never been measured on a book that already prices the inside-day term —
every prior row of it sits on the pre-ids l13 chain. This is the
add-vs-substitute experiment between the continuous and discrete
compression proxies on the live champion; "same signal, new shape" it is
not — the signal is unchanged, the book it is measured on is the one that
changed.

SPACE = my keys: cmp_lb {3, 6} x cmp_w {0.0, -0.2, -0.4} — six cells,
        each also runnable at ids_w 0.0 as the ids-off control.
        Champion keys pinned (passed by the caller, docs only): b_hi 0.69,
        b_lo 0.45, b_mid 0.55, floor_lb 19, lookback 12, max_dist 0.055,
        regime_ma 18, fast_ma 5, sustain_lo 3, sustain_hi 2, tier_lo
        0.9999, tier_mid 0.9999, cap_weak 11, cap_full 20, gf_lb 12,
        gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13. max_hold 3 is a
        HARNESS key passed via params-json; this file does not consume it.

Designer smoke observations (Loop-16, pre-freeze, nse_all top 15 25bps
split 2022-01-01, isolated ledger l16_dA): off-switch reproduced the
champion EXACTLY — train +96.88 / DD -17.03 / calmar 5.688, fwd +48.97 /
-12.31. The continuous tilt is DEAD on the ids base: cmp_w -0.2 / cmp_lb 3
-> train +69.48 / DD -22.13, fwd +58.38 / -17.87; cmp_w -0.4 / cmp_lb 6 ->
train +73.59 / DD -23.52, fwd +60.64 / -13.67; cmp_w -0.2 / cmp_lb 6 ->
train +75.77 / DD -21.30, fwd +51.29 / -13.54. Every cell is 21-27pp below
the champion on train with a worse DD — far more destructive than the same
tilt ever was on the pre-ids chain (-12 to -13pp there). Reading: the ids
book has already spent the "quiet tape" premium; adding the continuous
ratio double-counts compression and drags the book toward slow movers.
The falsifier fired: the continuous and discrete compression proxies are
NOT additive on this base — treat rngcomp as a substitute that lost to
ids, and do not spend a worker window on the remaining cmp_w cells (sign
is unambiguous at three cells spanning both windows and both weights).
"""

from __future__ import annotations

import warnings

import numpy as np

from strat_l12b_gatefail import score as _gf_score
from strat_l15b_insideday import _monthly_inside as _ids_monthly
from strat_l15b_rngcomp import _monthly_mtr as _rng_monthly

NEEDS_DAILY = True
SPACE = {
    # this file's keys
    "cmp_lb": [3, 6],
    "cmp_w": [0.0, -0.2, -0.4],
    # ids keys (champion-pinned, passed by the caller; ids_w 0.0 arms are
    # the ids-off controls)
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


def _pct_tilt(signal_row: np.ndarray, weight: float) -> np.ndarray:
    """Percentile tilt for one row: 1 + w*(2*pct - 1) among finite entries,
    exactly 1.0 elsewhere. Identical math to the frozen tilt files."""
    tilt = np.ones(signal_row.shape[0])
    valid = np.isfinite(signal_row)
    n = int(valid.sum())
    if n >= 5:
        sv = signal_row[valid]
        order = np.argsort(sv, kind="stable")
        pct = np.empty(n)
        pct[order] = np.arange(n) / (n - 1)
        tilt[valid] = 1.0 + weight * (2.0 * pct - 1.0)
    return tilt


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating: gatefail's own gf_w default (0.05)
    # would leak into the off-switch. Champion values (gw_w 0.15, ids keys)
    # are passed by the caller, not defaulted here.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    lift, exposure = _gf_score(panels, p)

    ids_w = float(params.get("ids_w", 0.0))
    cmp_w = float(params.get("cmp_w", 0.0))
    out = np.array(lift, dtype=float, copy=True)

    tilts_per_row = [None, None]  # [ids, cmp], applied only where computed

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
            tilts[t] = _pct_tilt(share, ids_w)
        tilts_per_row[0] = tilts

    if cmp_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        clb = int(params.get("cmp_lb", 3))
        M = _rng_monthly(daily, months, cols)
        tilts = {}
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
            tilts[t] = _pct_tilt(ratio, cmp_w)
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
