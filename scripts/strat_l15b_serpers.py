"""Candidate: serial-dependence (sign-persistence excess) tilt on the ids
champion book (strategy_lab contract).

Setup in words: the CURRENT champion — strat_l15b_insideday at ids_lb 3 /
ids_w -0.13 (the promoted best: the strat_l13a_concwobble chain at
lookback 12 — floor-lift fresh-print rank among short-trend-passing,
print-continuity-passing names, breadth-tier exposure tier 0.9999,
wobble discount gw_w 0.13 / gf_lb 12 — carrying the inside-day
compression tilt ids_w -0.13 applied pre-cap), with cap_weak/cap_full
mirrored inline as in every file of this chain. THIS FILE COMPOSES ON THE
IDS CHAMPION, not the plain concwobble chain — its promoted numbers are
the off-switch target. The composition re-applies the ids tilt exactly as
strat_l15b_insideday.score does (imported `_monthly_inside`, identical
percentile machinery and pre-cap application point), then applies ONE NEW
daily-tape tilt BEFORE the cap: the serial dependence of the name's daily
returns. Each daily bar yields a log return

    lr_d = ln(close_d / close_{d-1})

and each ADJACENT pair (lr_{d-1}, lr_d) with both non-null is a pair;
a pair is SAME-SIGN when lr_d * lr_{d-1} > 0 (both strictly up or both
strictly down; zero-return pairs are excluded from both sides). Over the
`ac_lb` monthly buckets ending at the print month:

    pairs    = count of valid adjacent pairs
    obs_same = same-sign pairs / pairs
    p_up     = up returns / valid returns   (the window's drift level)
    exp_same = p_up^2 + (1 - p_up)^2        (independence expectation
                                              at the same drift level)
    ac       = obs_same - exp_same

ac is the drift-adjusted sign-persistence excess — the binary analogue of
a lag-1 autocorrelation: > 0 means the tape TRENDS day-to-day (an up day
is likelier followed by another), < 0 means it CHOPS (up days followed by
down days). Drift adjustment matters: a name that simply goes up a lot
mechanically shows high same-sign share (p^2 + (1-p)^2 grows as p leaves
0.5); subtracting the independence expectation at the name's OWN p_up
isolates the serial dependence from the drift level. Among names with a
finite ac in the row it is percentile-ranked into pct in [0, 1]:

    tilt = 1 + ac_w * (2 * pct - 1)   # ac_w > 0 favours trending tapes
    out  = ids-champion score * tilt  # NaN ac keeps tilt 1.0

Hypothesis: the champion buys fresh 12-month-high printers; the ids tilt
already favours prints out of compressed tape. Serial dependence is the
remaining temporal character of the tape a monthly close cannot carry: a
high printed on a self-reinforcing, day-after-day trending tape is
sequential accumulation (each session's demand carries into the next),
while the same high printed on a choppy, anti-persistent tape is an
oscillation that filled nobody's trend. Time-series-momentum work
(Moskowitz-Ooi-Pedersen) ties persistence of returns to positive daily
autocorrelation; disposition-driven chop reverts. If trending-tape
printers continue, ac_w > 0 lifts the top-15 cut's quality; if the
anti-persistent chop mean-reverts into the print, ac_w < 0; if the gates
already encode it, every variant ties the base and the channel closes.

Falsifier: if every tested (ac_lb, ac_w) combination trails the flat base
— train +94.58% / DD -18.86% / calmar 5.01, fwd +54.40% / fwd DD -12.31%
— then the serial dependence of daily returns carries no information
beyond what the champion's monthly-close rank, gates and inside-day tilt
already consume, and the sign-sequence channel is closed at this base.
Given the loop's history (four of five daily-tilt families lost train to
gain forward), a forward-heavy / train-light print here would be a
documented negative, not a win.

Import chain: strat_l15b_serpers -> strat_l12b_gatefail.score (the
champion lift: strat_floorhightiershape rank/exposure + fastgate +
sustaincond gate layers + the gw_w 0.13 wobble discount, gf_w FORCED 0.0)
-> ids tilt re-applied with `strat_l15b_insideday._monthly_inside`
IMPORTED (that file is FROZEN and promoted; importing its helper neither
copies nor edits it — reuse, never reimplement — and the application
block is line-for-line its own score()) -> serial-dependence term is NEW
math (per-bar sign-pair indicators, monthly-bucket sums, drift-adjusted
excess) -> cap step mirrored inline from
strat_floorhightiershapeconc.score / strat_l13a_concwobble.score /
strat_l15b_insideday.score (identical loop: cap = cap_full where exposure
>= 1.0 else cap_weak; lower ranks set NaN after a stable descending sort).

PIT argument: NEEDS_DAILY loads the daily long panel (full window —
handled as follows). lr uses close_d and close_{d-1} of the SAME symbol
(shift within symbol over dates sorted ascending) — never a future bar;
pairs are between adjacent bars only. Daily bars are grouped into
calendar-month buckets with group_by_dynamic("1mo"); the pair indicators
are additive sums per bucket. For score row t (holding month starting
months[t]) the newest bucket read is bucket t-1, whose bars all have date
in [months[t-1], months[t]) — every bar read is strictly BEFORE
months[t]; buckets t and later are never touched, so the fact that
`daily` covers the full panel window is harmless. The percentile at row t
uses only ac values from that same backward window. Rows with
insufficient history (t < ac_lb), windows with fewer than `ac_min` valid
pairs (fixed guard 20, not searched), and names with undefined
ingredients read tilt exactly 1.0 — eligibility and rank unmodified,
nothing dropped on missing data, nothing peeks.

Off-switch identity: ac_w = 0.0 skips the serial-dependence term
entirely, leaving the ids tilt (applied identically to
strat_l15b_insideday.score) and the mirrored cap — bitwise the promoted
champion's scores at the same params. Expected flat base: train +94.58%
/ DD -18.86% / calmar 5.01 / H1 +99.32% / H2 +90.16% / invested 65.5% /
fwd +54.40% / fwd DD -12.31% / fwd bench +14.72% at the promoted params
(ids_lb 3 / ids_w -0.13, cap_full 20 / cap_weak 11, max_hold 3, lookback
12). NOTE imported defaults leak: strat_l12b_gatefail's own default is
gf_w = 0.05 — this file setdefaults gf_lb = 12 / gw_w = 0.13 and FORCES
gf_w = 0.0 BEFORE delegating (an override, not a setdefault), so the
off-switch is exact.

Flat-base metric (off-switch must reproduce exactly): train +94.58% /
DD -18.86% / calmar 5.01 / fwd +54.40% / fwd DD -12.31% / fwd bench
+14.72%.

NOVELTY STATEMENT: closest prior art — (a) the DEAD up-streak file
(strat_l15b_upstreak): it counts the TERMINAL RUN of consecutive up
closes, an order statistic of the sign sequence's last few days, and it
falsified both directions; (b) the LIVE fresh-print rank: momentum of
monthly closes; (c) strat_l15b_insideday (promoted): range CONTAINMENT
geometry between sessions. The ONE thing changed: serial dependence is a
STATISTICAL PROPERTY OF THE WHOLE RETURN SEQUENCE over the window — the
drift-adjusted rate at which signs persist across ALL adjacent pairs,
i.e. a binary lag-1 autocorrelation — not a terminal streak count, not a
return sum, not a path shape (dip depth), not range geometry, not CLV,
not volume, not volatility level. No file in the chain reads the
sign-persistence structure of daily returns; the drift adjustment
(subtracting the independence expectation at the name's own up-frequency)
is what separates it from a drift proxy — and from the up-streak's
failure mode.

SPACE = my keys only: ac_lb {3, 6} (window in monthly buckets ending at
        the print month), ac_w {0.0, +0.2, -0.2} (percentile tilt;
        0.0 = off-switch; positive = favour trending tapes, negative =
        favour choppy tapes). Fixed guard (not searched): ac_min = 20
        valid pairs. Champion keys pinned: ids_lb 3, ids_w -0.13,
        b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19, lookback 12,
        max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.13; max_hold 3 is a
        HARNESS key passed via params-json, this file does not consume
        it.

Designer smoke observations (Loop-15 round 4, pre-freeze, nse_all top 15
25bps split 2022-01-01, isolated ledger l15_dB): off-switch reproduced
the promoted champion bit-exact — train +94.58 / DD -18.86 / calmar 5.01,
fwd +54.40 / -12.31. ac_w +0.2 / ac_lb 3 (favour trending tapes) ->
train +77.93 / -17.75, fwd +45.73 / fwd DD -27.61 — harmful both sides,
fwd DD blown out to bench level. ac_w -0.2 / ac_lb 6 (favour choppy
tapes) -> train +72.65 / -24.49 (H2 collapses to +59.5), fwd +69.55 /
-16.13 (fwd-calmar 4.31) — the loop's familiar forward-heavy /
train-light signature, but from the CHOPPY side, not the trending side.
Reading: the serial-dependence channel is NOT inert and its live side,
if any, is anti-persistence (choppy tapes continue, trending tapes
revert) — but the ids champion's train is +94.58 and every tilt loses
~17-22pp of it, so the cagr ratchet will discard; treat this file as the
sign-sequence channel's falsification candidate with a documented
forward lead, and screen the remaining SPACE corners (ac_lb 3 / ac_w
-0.2; ac_lb 6 / ac_w +0.2) only if a worker window is free.
"""

from __future__ import annotations

import warnings

import numpy as np
import polars as pl

from strat_l12b_gatefail import score as _gf_score
from strat_l15b_insideday import _monthly_inside as _ids_monthly

NEEDS_DAILY = True
SPACE = {
    # my keys
    "ac_lb": [3, 6],
    "ac_w": [0.0, 0.2, -0.2],
    # fixed guard (not searched)
    "ac_min": [20],
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
    "ids_lb": [3],
    "ids_w": [-0.13],
}

AC_MIN = 20  # fixed: minimum valid adjacent pairs in the window


def _monthly_serpers(daily: pl.DataFrame, months, cols):
    """Per (calendar month, stock) additive counts: valid log returns (nv),
    up returns (nu), valid adjacent pairs (np), same-sign pairs (ns). NaN
    buckets (no bars) stay NaN."""
    d = daily.with_columns(pl.col("close").shift(1).over("symbol").alias("pc"))
    d = d.with_columns(
        pl.when((pl.col("pc") > 0) & (pl.col("close") > 0))
          .then((pl.col("close") / pl.col("pc")).log())
          .otherwise(None)
          .alias("lr"))
    d = d.with_columns(pl.col("lr").shift(1).over("symbol").alias("lrp"))
    d = d.with_columns(
        (pl.col("lr").is_not_null() & pl.col("lrp").is_not_null())
          .fill_null(False).alias("pair"),
        (pl.col("lr").is_not_null() & pl.col("lrp").is_not_null()
         & (pl.col("lr") * pl.col("lrp") > 0))
          .fill_null(False).alias("same"))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("lr").is_not_null().sum().alias("nv"),
               (pl.col("lr").fill_null(0.0) > 0).sum().alias("nu"),
               pl.col("pair").sum().alias("np"),
               pl.col("same").sum().alias("ns"))
          .sort("symbol", "date"))
    mind = {}
    for i, m in enumerate(months):
        mind[m if not hasattr(m, "date") else m.date()] = i
    cidx = {s: j for j, s in enumerate(cols)}
    outs = {}
    for key in ("nv", "nu", "np", "ns"):
        piv = g.pivot(on="symbol", index="date", values=key).sort("date")
        arr = np.full((len(months), len(cols)), np.nan)
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
        outs[key] = arr
    return outs["nv"], outs["nu"], outs["np"], outs["ns"]


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating: gatefail's own gf_w default (0.05)
    # would leak into the off-switch. gf_w is FORCED (champion keeps the
    # gate-failure leg off); gw_w/gf_lb default to the champion values.
    p.setdefault("gf_lb", 12)
    p.setdefault("gw_w", 0.13)
    p["gf_w"] = 0.0
    lift, exposure = _gf_score(panels, p)

    ids_w = float(params.get("ids_w", 0.0))
    ac_w = float(params.get("ac_w", 0.0))
    out = np.array(lift, dtype=float, copy=True)

    # ids tilt re-applied exactly as strat_l15b_insideday.score does it
    if ids_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        ilb = int(params.get("ids_lb", 3))
        IDS = _ids_monthly(daily, months, cols)
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
            ok = np.isfinite(out[t])
            out[t] = np.where(ok, out[t] * tilt, np.nan)

    # serial-dependence tilt (new math)
    if ac_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        alb = int(params.get("ac_lb", 3))
        NV, NU, NP, NS = _monthly_serpers(daily, months, cols)
        for t in range(1, lift.shape[0]):
            lo = t - alb
            if lo < 0:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                pairs = np.nansum(NP[lo:t], axis=0)
                same = np.nansum(NS[lo:t], axis=0)
                nv = np.nansum(NV[lo:t], axis=0)
                nu = np.nansum(NU[lo:t], axis=0)
            with np.errstate(invalid="ignore", divide="ignore"):
                obs = np.where(pairs >= AC_MIN, same / pairs, np.nan)
                p_up = np.where(nv > 0, nu / nv, np.nan)
                exp = p_up * p_up + (1.0 - p_up) * (1.0 - p_up)
                ac = np.where(np.isfinite(obs) & np.isfinite(exp),
                              obs - exp, np.nan)
            valid = np.isfinite(ac)
            n = int(valid.sum())
            tilt = np.ones(lift.shape[1])
            if n >= 5:
                av = ac[valid]
                order = np.argsort(av, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + ac_w * (2.0 * pct - 1.0)
            ok = np.isfinite(out[t])
            out[t] = np.where(ok, out[t] * tilt, np.nan)

    # cap step mirrored inline from strat_floorhightiershapeconc.score /
    # strat_l13a_concwobble.score / strat_l15b_insideday.score
    # (book-size composition, not an indicator)
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
