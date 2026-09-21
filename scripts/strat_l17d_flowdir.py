"""Candidate: signed-volume flow tilt on the champion book (strategy_lab
contract).

Setup in words: the CURRENT champion chain (strat_l12b_gatefail.score:
floor-lift fresh-print rank among short-trend-passing, print-continuity-
passing names, breadth tiers, eligibility-wobble) carrying the champion's
inside-day tilt (ids_lb 3 / ids_w -0.13, helper imported from
strat_l15b_insideday and mirrored pre-cap exactly as strat_l17b_crowd
mirrors it) is re-weighted, BEFORE the regime-conditional cap step (mirrored
inline), by a NEW statistic: the SIGNED SPLIT of the name's recent volume.
Per daily bar and symbol the change sign is

    sgn_d = +1 if close_d > close_{d-1}; -1 if close_d < close_{d-1}; 0 else

(first bar of a symbol: sgn 0 — volume counted, no direction). Per
calendar-month bucket:

    fl_m = sum(vol_d * sgn_d) / sum(vol_d)      in [-1, 1]

averaged over the fl_lb monthly buckets ending at the print month (the
calendar month before the holding month), percentile-ranked cross-
sectionally among names with a finite share, tilt = 1 + fl_w * (2*pct - 1);
NaN share keeps tilt 1.0. fl_w > 0 favours tapes where volume transacted on
UP days (accumulation); fl_w < 0 favours distribution-heavy tapes.

Hypothesis: the champion buys fresh 12-month-high printers; the monthly
closes know THAT a name printed, not WHAT KIND OF VOLUME carried it. Two
opposite stories: (a) fl_w > 0 — a high printed on net accumulation is
demand taking the offer; supply is being absorbed and continuation follows;
(b) fl_w < 0 — a high printed on net distribution is supply selling into
strength; the print is exit liquidity and fades. If the sign-split of
volume is already encoded by the chain's gates and tape terms, every
variant ties the base and the channel closes.

NOVELTY STATEMENT (closest registry rows + the one thing changed):
- strat_floorhighaccum (legacy, DEAD): the CLOSEST prior art — the SAME
  signed-share statistic (acc_m = sum vol*sign(chg) / sum vol) tested as a
  HARD ELIGIBILITY GATE (acc >= acc_min) on the pre-Loop-12 sustaincond
  chain (lookback 16, tier 1.0, no weak-month cap, no wobble, no ids tilt,
  no max_hold). Two things changed: (i) THE BASE IS GONE — the champion
  book differs on every axis a volume statistic could interact with (the
  cap changes the cut the tilt re-orders; the gate's falsification cannot
  bind a re-ranking inside a different eligible set); (ii) THE EXPRESSION —
  a continuous pre-cap ordering tilt, not exclusion: a gate can only remove
  names (this loop's history: gates subtract by cutting exposure), a tilt
  tests the ordering. This is the sanctioned changed-base retest; if the
  base change is judged insufficient the file dies at the gate — the
  statistic itself is deliberately the same, for comparability.
- strat_l16c_volpart (DEAD, 58.0-81.5, champion base): UNSIGNED self-
  relative participation (volume level vs the name's own baseline). The
  sign-split is orthogonal to it: identical total volume can be 90% buy-
  side or 90% sell-side; participation cannot see the difference.
- strat_floorhighliq / highliq / liqtrend / spons (DEAD): static liquidity
  LEVELS and share-volume gates — no direction, no sign.
The one thing changed: the signed share of volume (direction of flow) as a
pre-cap ordering tilt on the current champion base — no term in the chain
consumes a signed-volume statistic.

Import chain: strat_l17d_flowdir -> strat_l12b_gatefail.score (which
imports floorhighfastgate + floorhighsustaincond + floorhightiershape and
applies the wobble) + the ids tilt mirrored via _monthly_inside imported
from strat_l15b_insideday (champion term, pre-cap) + cap step mirrored
inline from strat_floorhightiershapeconc.score / strat_l13a_concwobble.score
/ strat_l15b_insideday.score (book-size composition, not an indicator).

PIT argument: NEEDS_DAILY loads the daily long panel (full window). sgn_d
uses close_d and close_{d-1} of the SAME symbol (shift within symbol over
dates sorted ascending) — no future bar. Buckets are calendar months via
group_by_dynamic("1mo"); for score row t (holding month starting months[t])
the newest bucket read is t-1, whose bars all have date < months[t]; the
percentile at row t uses only that backward window. Rows t < fl_lb and
names with no bars in the window keep tilt exactly 1.0 — eligibility and
rank unmodified, nothing dropped on missing data, nothing peeks. `close`
is split-adjusted, so split days do not fabricate a sign; ex-dividend days
can flip one day's sign — one bar among ~63 in a 3-bucket window.

Off-switch identity: fl_w = 0.0 (default) skips the tilt block, so `out`
is bitwise the ids-tilted gatefail lift and the mirrored cap yields
bitwise the champion's scores at the same params. Imported defaults leak:
gatefail's own gf_w default (0.05) is neutralised — this file setdefaults
gf_w = 0.0 / gw_w = 0.0 BEFORE delegating, so the off-switch is exact and
the champion's gw_w 0.15 / ids_w -0.13 must be PASSED by the caller.

Flat-base metric (off-switch must reproduce exactly): train +96.882% /
DD -17.032% / calmar 5.688 / H1 +98.302% / H2 +95.538% / fwd +48.973% /
fwd DD -12.311% / fwd bench +14.717%.

PROMOTION PRECONDITION (Loop-16 lesson): the tilt re-orders the top-15 cut
(a book-composition mechanism) — count the decision months where the
candidate's picks differ from the champion's before believing any gain.

Falsifier: if every tested (fl_lb, fl_w) combination trails the flat base —
train +96.882% / DD -17.032% / calmar 5.688 — then the signed split of
volume carries no selection information beyond the champion chain on THIS
base (the changed-base retest fails: the accum gate's DEAD verdict stands,
now with the tilt form closed too), and the flow-direction axis closes. A
train gain that coincides with forward/DD deterioration keeps the family's
known failure shape; record it, never promote it.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13;
        max_hold 3 is a HARNESS key passed via params-json, this file does
        not consume it)
        + fl_lb {3, 6} (window in monthly buckets ending at the print month)
        + fl_w {-0.2, -0.1, +0.1, +0.2} (percentile tilt; 0.0 = off-switch;
          positive = favour accumulation-heavy tapes).
"""

from __future__ import annotations

import warnings

import numpy as np
import polars as pl

from strat_l12b_gatefail import score as _gf_score
from strat_l15b_insideday import _monthly_inside

NEEDS_DAILY = True  # ids tilt (champion) and this file's signal read daily

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
    "gw_w": [0.15],
    "ids_lb": [3],
    "ids_w": [-0.13],
    # this file's keys
    "fl_lb": [3, 6],
    "fl_w": [-0.2, -0.1, 0.1, 0.2],
}


def _monthly_flow(daily: pl.DataFrame, months, cols) -> np.ndarray:
    """Per (calendar month, stock) the signed-volume share
    sum(vol * sign(close - prev close)) / sum(vol); NaN where the bucket
    had no bars or zero volume."""
    d = daily.sort("symbol", "date")
    d = d.with_columns(pl.col("close").shift(1).over("symbol").alias("pc"))
    sgn = (pl.when(pl.col("close") > pl.col("pc")).then(1.0)
             .when(pl.col("close") < pl.col("pc")).then(-1.0)
             .otherwise(0.0)).cast(pl.Float64)
    d = d.with_columns(
        (pl.col("volume").cast(pl.Float64) * sgn).alias("sv"),
        pl.col("volume").cast(pl.Float64).alias("vv"))
    g = (d.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg([pl.col("sv").sum().alias("num"),
                pl.col("vv").sum().alias("den")])
          .sort("symbol", "date"))
    g = g.with_columns(
        pl.when(pl.col("den") > 0)
          .then(pl.col("num") / pl.col("den"))
          .otherwise(None)
          .cast(pl.Float64).alias("flow"))
    piv = g.pivot(on="symbol", index="date", values="flow").sort("date")
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

    # champion's ids tilt, mirrored exactly from strat_l15b_insideday.score
    # (same loop, same percentile form, helper imported — never copied)
    ids_w = float(params.get("ids_w", 0.0))
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
            lift[t] = np.where(ok, lift[t] * tilt, np.nan)

    fl_w = float(params.get("fl_w", 0.0))
    out = np.array(lift, dtype=float, copy=True)

    if fl_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        flb = int(params.get("fl_lb", 3))
        F = _monthly_flow(daily, months, cols)
        for t in range(1, out.shape[0]):
            lo = t - flb
            if lo < 0:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                share = np.nanmean(F[lo:t], axis=0)
            valid = np.isfinite(share)
            n = int(valid.sum())
            tilt = np.ones(out.shape[1])
            if n >= 5:
                sv = share[valid]
                order = np.argsort(sv, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + fl_w * (2.0 * pct - 1.0)
            ok = np.isfinite(out[t])
            out[t] = np.where(ok, out[t] * tilt, np.nan)

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
