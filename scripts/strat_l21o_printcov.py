"""Candidate: trading-continuity (print-coverage) percentile tilt on the
CURRENT champion chain (strategy_lab contract).

Setup in words: the CURRENT champion chain strat_l20b_spread (the L19
balanced chain + the promoted Corwin-Schultz spread tilt) is called EXACTLY
ONCE (`from strat_l20b_spread import score as _champ`), and its returned
scores are re-weighted POST-chain by ONE strictly positive cross-sectional
percentile tilt on the name's trading-continuity ratio:

    cov[month k, name] = (daily bars printed by the name in month k)
                         / (distinct trading dates in the panel in month k)

averaged over the trailing pc_lb-month buckets t-pc_lb .. t-1 (buckets whose
bars all have date < months[t]), percentile-ranked cross-sectionally among
names with >= ceil(pc_frac * pc_lb) finite buckets (coverage guard), and
applied as tilt = 1 + pc_w*(2*pct - 1) to the finite entries of the
champion's returned scores. NaN stays NaN; names failing the guard keep tilt
exactly 1.0 (never NaN-ed — re-ranking, not a gate). Both signs are
first-class: pc_w > 0 favours names that print EVERY session (continuous,
executable, no suspension holes), pc_w < 0 favours names with missing
sessions (the neglected/illiquid premium — the same direction the champion's
illiquidity cousins reward).

Hypothesis: the champion's book is small/non-index names, where a missing
session is a real risk (suspension, circuit limits, data blackouts). This is
a THIRD distinct liquidity functional, after Amihud impact
(strat_l20b_illiq, KEEP) and Corwin-Schultz cost (strat_l20b_spread,
PROMOTED): availability. No chain term reads it; la reads age, ids reads
inside-day geometry, or reads lagged return. If it is just another
illiquidity proxy it will interfere with the spread term like the other
liquidity tilts did (strat_l20b2_liqcombo DEAD); if it carries new
information it may add where they did not.

DATA CAVEAT (must be reported if the tilt fires): the daily panel has
documented upstream session drops (`_manifest.json`), so a low coverage
ratio can be a Yahoo artefact rather than a real suspension. Any promotion
must say which names/months drive the effect and whether they look like data
holes (isolated single-session gaps) or real trading stops.

Falsifier: if all documented variants trail the flat champion on train CAGR
with no offsetting drawdown improvement (train +102.990% / DD -15.506% /
calmar 6.642), the axis closes on this base.

NOVELTY STATEMENT (closest registry rows -> the ONE thing changed):
- research/tested_mechanisms.tsv strat_l17d_timesince (DEAD 74.6-86.2) —
  "time since last bar" recency on the ids champion: a per-name STALENESS
  clock. This file measures a WINDOW SHARE (sessions printed / sessions
  available) — a rate, not a recency, and never before screened.
- The legacy liquidity/volume family (strat_floorhighliq, strat_floorliq,
  strat_highliq, strat_liqtrend, ...) ALL DEAD — hard eligibility GATES on
  the OLD floorhigh chain. This file is a strictly-positive post-chain
  MULTIPLIER on the CURRENT champion, and it measures availability rather
  than volume/turnover.
- strat_l20b_illiq / strat_l20b_spread are the accepted changed-base
  liquidity retests (KEEP / PROMOTED); this is the third functional of that
  family, never tested.
WHAT CHANGED: (a) the functional — availability rate instead of impact,
cost, volume or recency; (b) the base — the L20 champion chain, which no
member of this family has ever seen.

Import chain: strat_l21o_printcov -> strat_l20b_spread.score (current
champion) -> strat_l19a_balanced.score -> strat_l12b_gatefail.score ->
floorhighfastgate + sustaincond + tiershape. The coverage estimator is the
only new computation.

PIT argument: bucket k contains only bars whose date falls inside month k;
the window read at row t is buckets [t-pc_lb, t-1], whose bars all have
date < months[t] — the same bucket-t-1-and-older convention as the champion's
spread tilt. The market-day denominator of month k is a panel-wide property
of that same month. The percentile at row t uses only that row's backward
cross-section; no row > t is read anywhere.

Off-switch identity: pc_w = 0.0 (this file's OWN setdefault, applied BEFORE
delegating) skips the tilt block entirely and returns the champion's scores
bitwise. Champion keys (sp_w -0.05, gw_w 0.15, ids_w -0.13, la_w 0.5,
or_w -0.1, ...) are always PASSED by the caller, never defaulted here.

Flat-base metric (off-switch must reproduce exactly): train +102.990% /
DD -15.506% / calmar 6.642 / H1 +100.204 / H2 +105.682 / fwd +54.057% /
fwd DD -10.381% / full +82.001% / full DD -20.728%.

Keys consumed: pc_w, pc_lb, pc_frac; everything else flows through to the
delegate.

SPACE = champion keys pinned + pc_lb {6, 12} + pc_w {+0.1, -0.1} x {6, 12}
        = 4 documented variants (0.0 = off-switch).
"""

from __future__ import annotations

import warnings

import numpy as np
import polars as pl

from strat_l20b_spread import score as _champ

NEEDS_DAILY = True  # the delegate reads daily; the coverage estimator does too

SPACE = {
    # champion keys (pinned, docs only)
    "b_hi": [0.69],
    "b_lo": [0.45],
    "b_mid": [0.55],
    "cap_full": [20],
    "cap_weak": [11],
    "fast_ma": [5],
    "floor_lb": [19],
    "gf_lb": [12],
    "gf_w": [0.0],
    "gw_w": [0.15],
    "ids_lb": [3],
    "ids_w": [-0.13],
    "la_min": [0],
    "la_w": [0.5],
    "lookback": [12],
    "max_dist": [0.055],
    "or_lb": [6],
    "or_w": [-0.1],
    "regime_ma": [18],
    "sp_frac": [0.5],
    "sp_lb": [4],
    "sp_w": [-0.05],
    "sustain_hi": [2],
    "sustain_lo": [3],
    "tier_lo": [0.9999],
    "tier_mid": [0.9999],
    # this file's keys
    "pc_lb": [6, 12],
    "pc_w": [0.1, -0.1],
    "pc_frac": [0.5],
}


def _monthly_coverage(daily: pl.DataFrame, months, cols) -> np.ndarray:
    """Per (calendar month, stock) the share of the panel's distinct trading
    dates that the stock printed a bar on; NaN where the month has no bars
    for that stock (unlisted), 0.0 where it traded but printed nothing."""
    md = (daily.select("date").unique().sort("date")
          .group_by_dynamic("date", every="1mo")
          .agg(pl.col("date").len().alias("mkt")))
    mkt = {r["date"]: r["mkt"] for r in md.iter_rows(named=True)}
    g = (daily.group_by_dynamic("date", every="1mo", group_by="symbol")
          .agg(pl.col("date").len().alias("n")).sort("symbol", "date"))
    piv = g.pivot(on="symbol", index="date", values="n").sort("date")
    mind = {}
    for i, m in enumerate(months):
        mind[m if not hasattr(m, "date") else m.date()] = i
    out = np.full((len(months), len(cols)), np.nan)
    cidx = {s: j for j, s in enumerate(cols)}
    for row in piv.iter_rows(named=True):
        i = mind.get(row["date"])
        if i is None:
            continue
        k = mkt.get(row["date"], 0)
        if not k:
            continue
        for s, v in row.items():
            if s == "date" or v is None:
                continue
            j = cidx.get(s)
            if j is not None:
                out[i, j] = float(v) / float(k)
    return out


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating (Loop-13/14 imported-defaults leak):
    # this file's own keys default to the off-switch / pinned values whatever
    # the caller passes; the delegate neutralises ITS leakable defaults.
    p.setdefault("pc_w", 0.0)
    p.setdefault("pc_lb", 6)
    p.setdefault("pc_frac", 0.5)
    scores, regime = _champ(panels, p)  # current champion chain, verbatim
    out = np.array(scores, dtype=float, copy=True)

    pc_w = float(p["pc_w"])
    if pc_w == 0.0:
        return out, regime  # off-switch: bitwise copy of the champion

    daily, months, cols = panels["daily"], panels["months"], panels["cols"]
    plb = int(p["pc_lb"])
    need = max(2, int(np.ceil(float(p["pc_frac"]) * plb)))
    COV = _monthly_coverage(daily, months, cols)
    for t in range(plb, out.shape[0]):
        win = COV[t - plb : t]  # buckets t-plb..t-1: all date < months[t]
        cnt = np.isfinite(win).sum(axis=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            val = np.nanmean(win, axis=0)
        valid = np.isfinite(val) & (cnt >= need)  # coverage guard
        n = int(valid.sum())
        tilt = np.ones(out.shape[1])
        if n >= 5:
            sv = val[valid]
            order = np.argsort(sv, kind="stable")
            pct = np.empty(n)
            pct[order] = np.arange(n) / (n - 1)
            tilt[valid] = 1.0 + pc_w * (2.0 * pct - 1.0)
        ok = np.isfinite(out[t])
        out[t] = np.where(ok, out[t] * tilt, np.nan)
    return out, regime
