"""Candidate: up-streak-into-the-print tilt/gate on the champion book
(strategy_lab contract).

Setup in words: the CURRENT champion chain (strat_l13a_concwobble at
lookback 12: floor-lift fresh-print rank among short-trend-passing,
print-continuity-passing names, breadth-tier exposure with tier 0.9999,
regime-conditional book cap cap_weak/cap_full, eligibility-wobble discount
gw_w 0.13 / gf_lb 12) is imported wholesale via strat_l12b_gatefail.score.
Before the regime-conditional cap step (mirrored inline, exactly as
strat_l13a_concwobble mirrors it — a composition step, not an indicator),
the imported lift is re-weighted by a NEW daily-tape signal: the length of
the name's consecutive-up-close streak at the last daily bar before the
decision month. Per daily bar and symbol:

    up_d    = close_d > close_{d-1}
    streak_d= number of consecutive up closes ending at d (0 on a down day)

Per calendar month bucket the streak at the bucket's LAST bar is taken;
for score row t the value read is bucket t-1 — the streak as of the last
trading day of the calendar month before the holding month. Among names
with a finite streak in the row, it is percentile-ranked into pct in [0,1]:

    tilt = 1 + stk_w * (2 * pct - 1)   # stk_w < 0 penalises long streaks
    out  = imported lift * tilt        # NaN streak keeps tilt 1.0

An optional hard gate `stk_cap` (> 0) sets the score NaN for names whose
streak reaches that many days — dropping overheated entries from the book
entirely regardless of rank (0 = off). Tilt and gate are independent keys.

Hypothesis: the champion buys fresh 12-month-high printers, and a fresh
high reached on a long run of consecutive up closes is a different object
from one reached after a flat finish. Long up-streaks into a high are the
classic disposition/extension state — retail profit-taking pressure and
short-term reversal are documented after streak extremes — while a high
printed on a short or paused streak leaves the coil unspent. The monthly
closes carry none of this path. If extended entries mean-revert over the
next month, stk_w < 0 (and/or a stk_cap gate) lifts the top-15 cut's
quality; if the short-trend and print-continuity gates already fully
encode it, every variant ties the base and the channel closes.

Falsifier: if every tested (stk_w, stk_cap) combination trails the flat
base — train +88.139% / DD -17.339% / calmar 5.083, fwd +49.274% / fwd DD
-14.926% / fwd bench +14.717% — then the up-streak structure at the print
carries no information beyond what the champion's monthly-close rank and
gates already consume, and the family is closed at this base. If a variant
shows the documented forward-positive / train-negative pattern instead
(Loop-15 designer smokes: every daily-tape tilt so far lost train and
gained forward), check stacking with the forward geometry (rs_w 0.2 /
rs_lb 6 + cap_full 15 / max_hold 6) before discarding — selection stays
train-side either way.

Import chain: strat_l15b_upstreak -> strat_l12b_gatefail.score (which
imports strat_floorhighfastgate + strat_floorhighsustaincond for the gate
layers and strat_floorhightiershape for rank/exposure, and applies the
wobble tilt) -> cap step mirrored inline from
strat_floorhightiershapeconc.score / strat_l13a_concwobble.score (identical
loop: cap = cap_full where exposure >= 1.0 else cap_weak; lower ranks set
NaN after a stable descending sort).

PIT argument: NEEDS_DAILY loads the daily long panel (full window — handled
as follows). The daily streak is computed within symbol over dates sorted
ascending, from close-to-close changes only — it never references a bar
after the one it labels. Daily bars are grouped into calendar-month
buckets with group_by_dynamic("1mo"); the value kept is the bucket's LAST
bar's streak. For score row t the newest bucket read is bucket t-1, whose
bars all have date in [months[t-1], months[t]) — every bar read is
strictly BEFORE months[t]; buckets t and later are never touched, so the
fact that `daily` covers the full panel window is harmless. Known cost of
this frozen convention (mirrors strat_l12b_printclose and
strat_floorhighaccum exactly): the streak is read one bucket stale
relative to the entry close px[t] — the month-t bucket's own bars are
never read even though their closes precede px[t]. The percentile/gate at
row t uses only streak values from that same backward window. Rows with
insufficient history (t < 1) and names with no bars in the bucket (NaN)
keep tilt exactly 1.0 — eligibility and rank unmodified by missing data;
only the explicit stk_cap gate ever drops a name, and then by rule, not
by accident.

Off-switch identity: stk_w = 0.0 and stk_cap = 0 make tilt == 1.0 for
every name and every row and apply no gate, so `out` is bitwise the
gatefail lift and the mirrored cap yields bitwise the champion's scores at
the same params. NOTE imported defaults leak: strat_l12b_gatefail's own
default is gf_w = 0.05 — this file setdefaults gf_w = 0.0 / gw_w = 0.0 /
gf_lb = 12 BEFORE delegating, so the off-switch is exact and the
champion's gw_w 0.13 must be PASSED by the caller (it is a champion key,
not a default here).

Flat-base metric (off-switch must reproduce exactly): train +88.139% /
DD -17.339% / calmar 5.083 / H1 +80.14% / H2 +96.09% / invested 65.5% /
fwd +49.274% / fwd DD -14.926% / fwd bench +14.717%.

NOVELTY STATEMENT: closest prior art in the mechanism inventory is the
PARTIAL negative-persistence premium (monthly rank-persistence weight,
live on the rankpersist line, dead on the conc chain) and the DEAD
drought/freshness re-bases — all of which measure recency/persistence of
MONTHLY rank events from month-end closes. The one thing changed: the
signal is the daily close-to-close STREAK DIRECTION into the print —
within-month path structure from consecutive daily up closes, a variable
no file in the chain consumes. It is not a re-shape of monthly freshness
(month-end proximity), not CLV (where in a day's own range the close
landed — DEAD), not steadyprint (depth of the intra-month dip), not
volume, and not volatility level: it uses only the ORDER of daily closes,
which nothing in the live chain reads.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.13; max_hold 3 is a HARNESS
        key passed via params-json, this file does not consume it)
        + stk_w {-0.3, -0.15, +0.15, +0.3} (percentile tilt on streak
          length; 0.0 = off; negative = penalise extended entries)
        + stk_cap {0, 5} (hard gate: NaN the score when streak >= cap;
          0 = off).

Designer smoke observations (Loop-15, pre-freeze, nse_all top 15 25bps
split 2022-01-01): off-switch reproduced +88.14 / -17.34 / 5.08, fwd
+49.27 / -14.93 exactly. stk_w -0.3 -> train +52.65 / -17.03, fwd
+37.98 / -24.99 (harmful both sides). stk_cap 5 -> train +68.37 / -18.94
(H2 collapses to +52.4), fwd +32.17 / -18.36. BOTH directions of the
streak signal subtract: the champion's short-trend + print-continuity
gates already encode everything the daily up-streak carries. Expect the
full SPACE to confirm the negative; this file is delivered as a
falsification candidate, not a live line.
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
    "stk_w": [-0.3, -0.15, 0.15, 0.3],
    "stk_cap": [0, 5],
}


def _monthly_streak(daily: pl.DataFrame, months, cols) -> np.ndarray:
    """Per (calendar month, stock) the consecutive-up-close streak at the
    month bucket's LAST bar; NaN where the bucket had no bars. Streak is 0
    on a down close, k after k consecutive up closes."""
    d = daily.with_columns(pl.col("close").shift(1).over("symbol").alias("pc"))
    d = d.with_columns(
        pl.when((pl.col("pc") > 0) & (pl.col("close") > 0))
          .then(pl.col("close") > pl.col("pc"))
          .otherwise(None)
          .alias("up"))
    # run resets wherever up is not True; within a run, position index = streak
    d = d.with_columns(
        (~pl.col("up")).fill_null(True).cum_sum().over("symbol").alias("run"))
    d = d.with_columns(
        pl.int_range(pl.len()).over("symbol", "run").alias("pos"))
    d = d.with_columns(
        pl.when(pl.col("up") == True)  # noqa: E712 - explicit null-safe test
          .then(pl.col("pos") + 1)
          .otherwise(0)
          .alias("streak"))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("streak").last())
          .sort("symbol", "date"))
    piv = g.pivot(on="symbol", index="date", values="streak").sort("date")
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

    stk_w = float(params.get("stk_w", 0.0))
    stk_cap = int(params.get("stk_cap", 0))
    out = np.array(lift, dtype=float, copy=True)

    if stk_w != 0.0 or stk_cap > 0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        S = _monthly_streak(daily, months, cols)
        for t in range(1, lift.shape[0]):
            s = S[t - 1]  # bucket t-1: bars strictly before months[t]
            ok = np.isfinite(lift[t])
            if stk_cap > 0:
                with np.errstate(invalid="ignore"):
                    out[t] = np.where(ok & np.isfinite(s) & (s < stk_cap),
                                      lift[t], np.nan)
            else:
                out[t] = np.where(ok, lift[t], np.nan)
            if stk_w != 0.0:
                valid = np.isfinite(s) & np.isfinite(out[t])
                n = int(valid.sum())
                if n >= 5:
                    sv = s[valid]
                    order = np.argsort(sv, kind="stable")
                    pct = np.empty(n)
                    pct[order] = np.arange(n) / (n - 1)
                    tilt = 1.0 + stk_w * (2.0 * pct - 1.0)
                    cur = out[t, valid]
                    out[t, valid] = np.where(np.isfinite(cur), cur * tilt, np.nan)

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
