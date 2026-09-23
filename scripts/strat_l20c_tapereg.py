"""Candidate: MARKET-WIDE TAPE-MICROSTRUCTURE exposure regime on the CURRENT
champion chain (strategy_lab contract, Loop-20 designer C).

Setup in words: this file re-implements the strat_l19a_balanced champion
chain faithfully — gatefail delegate with neutralised defaults, inside-day
(ids) tilt on the returned lift, the regime-conditional book cap (binary
switch, UNCHANGED here — the cap axis belongs to strat_l20c_capconc),
listing-age tilt, cross-sectional outrank tilt, final no-op cap pass — and
adds an EXPOSURE regime computed from MARKET-WIDE DAILY TAPE state, not
from price state: a cross-sectional aggregate of daily-bar SHAPE over the
trailing window of calendar months strictly before months[t].

Two signals (tp_sig), both pooled across the whole panel:

  "inside" (inside-day breadth): per daily date d,
      f_d = #{names: high_d < high_{d-1} AND low_d > low_{d-1}}
            / #{names with both bars}          # the ids boolean, aggregated
      per calendar-month bucket: mean of f_d over the bucket's days.
  "range" (median daily range): per daily date d,
      m_d = cross-sectional median of (high - low) / close over names
      per calendar-month bucket: mean of m_d over the bucket's days.

Level and adaptive mapping (PIT, all indices < t):

      x_t = mean of bucket values over buckets [t - tp_lb .. t - 1]   # trailing
      q_t = midrank percentile of x_t among x of rows [t - tp_rb + 1 .. t]
            (>= 5 finite required, else undefined -> no de-risk)
      band  g_t = 0 / 0.5 / 1 by thresholds (tp_t1, tp_t2) on q   [tier mode]
             g_t = q (or 1 - q when tp_flip)                      [smooth mode]
             (tier mode with tp_flip applies thresholds to 1 - q)
      mult_t = clip(1 - tp_w * g_t, 0, 1)
      E'_t   = E_t * mult_t            # multiplied INTO the champion regime

Decisions documented: the multiplier is applied ALONGSIDE the existing
regime (multiplicative into E), AFTER the cap step reads the untouched
champion E — so book composition (who is held) is bit-identical to the
champion and ONLY the exposure scale changes; this isolates the exposure
axis from the book-size axis. tp_w 0.6 in tier mode gives exactly the
1.0 / 0.7 / 0.4 ladder at thresholds (0, tp_t1, tp_t2). Cash months
(E = 0) stay cash (0 * mult = 0); mult = 1 leaves E bitwise unchanged.

Hypothesis: the champion's exposure regime keys off price-trend breadth
(where names sit vs their moving averages). The daily tape carries a
orthogonal, faster read: months in which the WHOLE PANEL's bars are
contraction-compressed (dense inside days, tight median ranges) are months
of coiled positioning, months of wide ranges / no pauses are months of
already-spent dispersion. Which DIRECTION de-risking helps is genuinely
open — the Loop-15 per-name ids term ran the OPPOSITE of its coil
hypothesis ("rewards FEWER inside days" — skill state at Loop-15 close) —
so both flips are in the SPACE and the direction is whatever the screen
says, not what the story says.

Falsifier: if every tested (tp_sig, tp_mode, tp_flip) variant trails the
flat base — train +98.682% / DD -15.506% / calmar 6.364 / H1 +95.295% /
H2 +101.966% / fwd +53.148% / fwd DD -10.403% — on BOTH train CAGR and
forward risk-adjusted numbers (a keep needs train > 98.682+0.05, DD >=
-17.506, both halves > 0), then the market-wide tape-microstructure
aggregate carries no exposure information beyond the champion's breadth
tiers, and this axis closes at this base. A caveat read into every result:
Loop-18 already found "exposure smoothing via partial tiers is strictly
WORSE" — a tier that merely dilutes exposure without timing anything will
show up as lower CAGR at similar DD, which is the expected death, not a
near-miss.

Import chain: strat_l20c_tapereg -> strat_l12b_gatefail.score (imports
strat_floorhighfastgate + strat_floorhighsustaincond +
strat_floorhightiershape for the gate layers and rank/exposure, applies
the wobble tilt; gf_w 0.05 default neutralised by setdefault BEFORE
delegating — Loop-14 lesson) -> ids tilt re-expressed from
strat_l15b_insideday.score via _monthly_inside -> mirrored binary cap
(strat_l19a_balanced position) -> listing-age tilt from
strat_l17c_listage.score -> outrank tilt from strat_l16b_outrank.score ->
final no-op cap pass -> tape multiplier into E (this file).

PIT argument: for score row t (holding month starting months[t]) the newest
daily bar read is the last bar of bucket t-1, i.e. date < months[t]
(buckets are calendar months starting at months[r] = group_by_dynamic
"1mo" truncation of the same daily dates — same mapping as
_monthly_inside). The level window [t-tp_lb .. t-1] and the rank window
[rows <= t] therefore touch only bars strictly before months[t]; rows with
insufficient history keep mult = 1.0 (no de-risk, conservative), NaN never
propagates into E. The champion chain's own PIT arguments (ids: daily bars
strictly before months[t]; age: static listing_date; outrank: px through
row t) are unchanged.

Off-switch identity: tp_w = 0.0 (neutral default set via setdefault BEFORE
delegating) skips the entire tape computation and returns the champion's
E untouched, so scores AND regime are bitwise the champion's at the same
params; champion keys are PASSED by the caller (gf_lb 12 / gf_w 0.0
neutralised here; gw_w 0.15 / ids_lb 3 / ids_w -0.13 / la_w 0.5 /
or_w -0.1 passed through).

Flat-base metric (off-switch must reproduce exactly): train +98.682% /
DD -15.506% / calmar 6.364 / H1 +95.295% / H2 +101.966% /
fwd +53.148% / fwd DD -10.403% / full +79.237% / full DD -20.728%.

NOVELTY STATEMENT (exact registry rows, research/tested_mechanisms.tsv):
the CLOSED families are cited explicitly so the delta is visible —
  - calendar: `strat_l17c_calreg.py  l17  calendar-month exposure  DEAD`
  - index/price breadth level & change: `strat_l14a_breadthdelta.py  l14
    breadth change/derivative  DEAD  - one-sided harm, grows with the
    shift`, plus the legacy breadth regime block
    (`strat_floorhighregimeswitch.py`, `strat_floorhighbreadthlin.py`,
    `strat_floorhighhyst.py`, `strat_floorhightier*` — all DEAD,
    "ramps/hysteresis/regime switches"); the LIVE breadth TIERS are the
    champion's own price-level breadth (fraction of names above trend)
  - index-DD veto (skill inventory, DEAD), vol targeting
    (`strat_concvoltarget.py` / `strat_concvolgate.py` / `strat_volfloor.py`
    / `strat_volmom.py` / `strat_volnewhigh.py` / `strat_floorhightiervol.py`
    / `strat_floorhighvoltarget.py`, all DEAD, "exposure or rank scaled by
    volatility"), equity state (`strat_l17c_eqstate.py  DEAD  83.6-90.7`),
    book-health (`strat_l12a_bookhealth.py  DEAD`, held-book returns)
  - per-name tape re-ranking: `strat_l15b_rngcomp.py  DEAD on ids base`,
    `strat_l16a_idsrng.py  DEAD  69.5-75.8  rngcomp does not stack with
    ids; ids saturates the tape axis` — Loop-16/15 closed the PER-NAME
    tape axis.
THE ONE THING THAT CHANGED: the exposure regime now reads a CROSS-SECTIONAL
TAPE-MICROSTRUCTURE aggregate — the breadth of inside days (or the
cross-sectional median daily range/close) across the whole panel — none of
the rows above uses bar-shape aggregated across names: the breadth rows
aggregate price-LEVEL/trend position (and are dead as ramps/derivatives),
the vol rows use per-name volatility, the tape rows re-rank PER NAME (and
are saturated by ids), calreg/eqstate/bookhealth read calendar, own equity
curve, or held book respectively. This signal is orthogonal to trend
breadth by construction (a panel can be 90% above its MA with either
wide-range or inside-day-dense bars), is market-wide rather than per-name,
and drives EXPOSURE (E), not rank.

SPACE = champion keys pinned (b_hi 0.69, b_lo 0.45, b_mid 0.55, floor_lb 19,
        lookback 12, max_dist 0.055, regime_ma 18, fast_ma 5, sustain_lo 3,
        sustain_hi 2, tier_lo 0.9999, tier_mid 0.9999, cap_weak 11,
        cap_full 20, gf_lb 12, gf_w 0.0, gw_w 0.15, ids_lb 3, ids_w -0.13,
        la_min 0, la_w 0.5, or_lb 6, or_w -0.1; max_hold 3 is a HARNESS key
        passed via params-json, not consumed here)
        + tp_w {0.0 (off-switch), 0.6} (de-risk amount at full band;
          0.6 -> ladder 1.0 / 0.7 / 0.4 in tier mode)
        + tp_sig {"inside", "range"} (market inside-day breadth vs
          cross-sectional median daily range/close)
        + tp_lb [2] (trailing month buckets in the level window, 1-3 briefed)
        + tp_rb [24] (trailing rows for the adaptive percentile)
        + tp_mode {"tier", "smooth"} (0/0.5/1 bands vs continuous scale)
        + tp_t1 [0.66], tp_t2 [0.85] (tier thresholds on the percentile)
        + tp_flip {0, 1} (1 = de-risk the LOW side of the metric)
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import polars as pl

from strat_l12b_gatefail import score as _gf_score
from strat_l15b_insideday import _monthly_inside

NEEDS_DAILY = True  # own tape signal AND the delegate's ids term need daily

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
    "la_min": [0],
    "la_w": [0.5],
    "or_lb": [6],
    "or_w": [-0.1],
    # this file's keys
    "tp_w": [0.0, 0.6],
    "tp_sig": ["inside", "range"],
    "tp_lb": [2],
    "tp_rb": [24],
    "tp_mode": ["tier", "smooth"],
    "tp_t1": [0.66],
    "tp_t2": [0.85],
    "tp_flip": [0, 1],
}

_UNI_CACHE: dict = {}


def _listing_dates() -> dict:
    """symbol -> listing_date from the universe snapshot (static ex-ante
    attribute; copied from strat_l19a_balanced._listing_dates)."""
    if "ld" not in _UNI_CACHE:
        root = Path(__file__).resolve().parents[1]
        u = pl.read_parquet(root / "data" / "universe" / "nse_universe.parquet")
        _UNI_CACHE["ld"] = dict(zip(u["symbol"].to_list(), u["listing_date"].to_list()))
    return _UNI_CACHE["ld"]


def _bucket_series(daily: pl.DataFrame, sig: str) -> pl.DataFrame:
    """Per calendar-month bucket the market-wide tape aggregate:
    "inside" -> mean over days of (share of names printing an inside day);
    "range"  -> mean over days of the cross-sectional median (high-low)/close.
    Returns columns [date, v] sorted by bucket date."""
    d = daily.with_columns(
        pl.col("high").shift(1).over("symbol").alias("ph"),
        pl.col("low").shift(1).over("symbol").alias("pl"))
    if sig == "inside":
        d = d.with_columns(
            pl.when(pl.col("ph").is_not_null() & pl.col("pl").is_not_null())
              .then((pl.col("high") < pl.col("ph")) & (pl.col("low") > pl.col("pl")))
              .otherwise(None)
              .cast(pl.Float64)
              .alias("v"))
        per_day = d.group_by("date").agg(pl.col("v").mean().alias("v"))
    else:
        d = d.with_columns(
            ((pl.col("high") - pl.col("low")) / pl.col("close")).alias("v"))
        per_day = d.group_by("date").agg(pl.col("v").median().alias("v"))
    return (per_day.sort("date").group_by_dynamic("date", every="1mo")
            .agg(pl.col("v").mean().alias("v")).sort("date"))


def score(panels, params):
    p = dict(params)
    # neutral defaults BEFORE delegating (gatefail's own gf_w 0.05 default
    # would leak — Loop-14 lesson); this file's own keys neutralised the
    # same way. Champion keys gw_w 0.15 / ids_w -0.13 / ids_lb 3 / la_w 0.5
    # / or_w -0.1 must be PASSED by the caller.
    p.setdefault("gf_lb", 12)
    p.setdefault("gf_w", 0.0)
    p.setdefault("gw_w", 0.0)
    p.setdefault("tp_w", 0.0)
    p.setdefault("tp_sig", "inside")
    p.setdefault("tp_lb", 2)
    p.setdefault("tp_rb", 24)
    p.setdefault("tp_mode", "tier")
    p.setdefault("tp_t1", 0.66)
    p.setdefault("tp_t2", 0.85)
    p.setdefault("tp_flip", 0)
    lift, exposure = _gf_score(panels, p)  # champion lift (wobble tilt inside)
    out = np.array(lift, dtype=float, copy=True)

    # ---- ids tilt, re-expressed from strat_l15b_insideday.score (its inline
    # loop: tilt = 1 + ids_w * (2 * pct - 1) on the trailing ids_lb monthly
    # inside-day shares, percentile-ranked among finite shares) ----
    ids_w = float(params.get("ids_w", 0.0))
    if ids_w != 0.0:
        daily, months, cols = panels["daily"], panels["months"], panels["cols"]
        ilb = int(params.get("ids_lb", 3))
        IDS = _monthly_inside(daily, months, cols)
        for t in range(1, out.shape[0]):
            lo = t - ilb
            if lo < 0:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                share = np.nanmean(IDS[lo:t], axis=0)
            valid = np.isfinite(share)
            n = int(valid.sum())
            tilt = np.ones(out.shape[1])
            if n >= 5:
                sv = share[valid]
                order = np.argsort(sv, kind="stable")
                pct = np.empty(n)
                pct[order] = np.arange(n) / (n - 1)
                tilt[valid] = 1.0 + ids_w * (2.0 * pct - 1.0)
            ok = np.isfinite(out[t])
            out[t] = np.where(ok, out[t] * tilt, np.nan)

    # cap step mirrored inline from strat_l19a_balanced.score (binary switch,
    # cap = cap_full where exposure >= 1.0 else cap_weak; lower ranks set
    # NaN after a stable descending sort) — UNCHANGED, in the same position
    # (between the ids tilt and the age/outrank tilts) so book composition
    # matches the champion end-to-end.
    cw = int(params.get("cap_weak", 11))
    cf = int(params.get("cap_full", 20))
    E = np.asarray(exposure, dtype=float)

    def _cap(scores: np.ndarray) -> np.ndarray:
        for t in range(scores.shape[0]):
            r = scores[t]
            fin = np.flatnonzero(np.isfinite(r))
            if fin.size == 0:
                continue
            cap = cf if E[t] >= 1.0 else cw
            if fin.size <= cap:
                continue
            order = fin[np.argsort(-r[fin], kind="stable")]
            scores[t, order[cap:]] = np.nan
        return scores

    out = _cap(out)

    # ---- (a) listing-age tilt, re-expressed from strat_l17c_listage.score
    # (source formula, cited in strat_l19a_balanced's docstring) ----
    la_w = float(params.get("la_w", 0.0))
    la_min = float(params.get("la_min", 0.0) or 0.0)  # retained, PINNED 0
    if la_w != 0.0 or la_min > 0.0:
        ld = _listing_dates()
        months, cols = panels["months"], panels["cols"]
        age_ref = np.full(len(cols), np.nan)
        for j, s in enumerate(cols):
            d0 = ld.get(s)
            if d0 is not None:
                age_ref[j] = max(0, (months[-1] - d0).days) / 365.25
        tilt_a = np.ones(len(cols))
        valid = np.flatnonzero(np.isfinite(age_ref))
        if valid.size >= 5:
            order = valid[np.argsort(age_ref[valid], kind="stable")]
            pct = np.empty(valid.size)
            pct[order] = np.arange(valid.size) / (valid.size - 1)
            tilt_a[valid] = 1.0 + la_w * (2.0 * pct - 1.0)
        for t in range(1, out.shape[0]):
            ok = np.isfinite(out[t])
            out[t] = np.where(ok, out[t] * tilt_a, np.nan)
            if la_min > 0.0:
                d0s = np.array([ld.get(s) for s in cols], dtype=object)
                young = np.array(
                    [d is None or (months[t] - d).days < la_min * 365.25 for d in d0s])
                out[t] = np.where(ok & ~young, out[t], np.nan)

    # final no-op cap pass (strat_l19a_balanced re-runs the cap after the
    # age tilt; fin.size <= cap on every row, so it removes nothing)

    # ---- (b) cross-sectional outrank tilt, re-expressed from
    # strat_l16b_outrank.score (source formula, cited in strat_l19a's
    # docstring: ret = px[t]/px[t-or_lb] - 1; tilt_b = 1 + or_w*(2pct-1)) ----
    or_w = float(params.get("or_w", 0.0))
    if or_w != 0.0:
        px = panels["px"]
        olb = int(params.get("or_lb", 6))
        for t in range(olb, out.shape[0]):
            with np.errstate(invalid="ignore"):
                ret = px[t] / px[t - olb] - 1.0
            valid = np.isfinite(ret)
            n = int(valid.sum())
            if n < 5:
                continue
            rv = ret[valid]
            order = np.argsort(rv, kind="stable")
            pct = np.empty(n)
            pct[order] = np.arange(n) / (n - 1)
            tilt_b = np.ones(out.shape[1])
            tilt_b[valid] = 1.0 + or_w * (2.0 * pct - 1.0)
            ok = np.isfinite(out[t])
            out[t] = np.where(ok, out[t] * tilt_b, np.nan)

    out = _cap(out)

    # ---- tape-microstructure exposure multiplier (this file; see docstring)
    tp_w = float(p.get("tp_w", 0.0))
    if tp_w == 0.0:
        return out, E  # off-switch: regime bitwise the champion's

    daily, months = panels["daily"], panels["months"]
    sig = str(p.get("tp_sig", "inside"))
    tlb = int(p.get("tp_lb", 2))
    trb = int(p.get("tp_rb", 24))
    mode = str(p.get("tp_mode", "tier"))
    t1 = float(p.get("tp_t1", 0.66))
    t2 = float(p.get("tp_t2", 0.85))
    flip = int(p.get("tp_flip", 0))

    b = _bucket_series(daily, sig)
    mind = {}
    for i, m in enumerate(months):
        mind[m if not hasattr(m, "date") else m.date()] = i
    x = np.full(len(months), np.nan)
    for row in b.iter_rows(named=True):
        i = mind.get(row["date"])
        if i is not None and row["v"] is not None:
            x[i] = float(row["v"])

    mult = np.ones(len(months))
    lvl = np.full(len(months), np.nan)
    for t in range(len(months)):
        lo = t - tlb
        if lo < 0:
            continue
        w = x[lo:t]  # buckets t-tlb .. t-1: every bar strictly < months[t]
        w = w[np.isfinite(w)]
        if w.size == 0:
            continue
        lvl[t] = float(w.mean())
    for t in range(len(months)):
        if not np.isfinite(lvl[t]):
            continue
        lo = max(0, t - trb + 1)
        w = lvl[lo:t + 1]
        w = w[np.isfinite(w)]
        if w.size < 5:
            continue
        q = ((w < lvl[t]).sum() + 0.5 * (w == lvl[t]).sum()) / w.size
        if mode == "smooth":
            g = (1.0 - q) if flip else q
        else:
            qq = (1.0 - q) if flip else q
            g = 0.0 if qq < t1 else (0.5 if qq < t2 else 1.0)
        mult[t] = float(np.clip(1.0 - tp_w * g, 0.0, 1.0))

    return out, E * mult
