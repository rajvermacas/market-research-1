"""Candidate: liquid-core DOWN-capture vs UP-capture asymmetry (daily, vs the whole board) as an exposure cut on the L25 champion (Loop-29 A).

Setup in words: rank, eligibility, book policy and base exposure are exactly the
L25 champion strat_l23a_liqconfirm (imported, never copied). Daily equal-weight
returns (per-name daily returns clipped to +-30% against bad ticks) are
formed for the whole board and for the liquid core (names whose lq_days median
traded value is >= lq_min, membership as of the month-end row the day belongs
to, itself computed from date < that month-end). Over the last cp_w sessions
with date < months[t]:
  up_cap   = mean(core | board up day)   / mean(board | board up day)
  down_cap = mean(core | board down day) / mean(board | board down day)
  asym     = down_cap - up_cap
If asym > cp_thr (the liquid core falls MORE than the board on down days while
lagging it on up days: institutional distribution under a still-rising tail)
exposure *= (1 - cp_cut). cp_mode "rearm": if asym < -cp_thr and 0 < exposure
< 1, exposure -> 1.0 (core leading on the upside, cushioning on the downside).

Hypothesis: distribution by large holders shows up as asymmetric capture in
the liquid core before breadth tiers fall.
Falsifier: no cell beats the champion on train CAGR at no deeper DD, or the
gain rests on <= 3 firings.

Novelty: closest rows are strat_l17b_updown / strat_l17a_semi (down/up
comovement asymmetry of individual STOCKS as a rank tilt, DEAD, legacy),
strat_l27a_sizeflight (tail-minus-core RETURN level, DEAD), strat_l27o_coreslump
(core return level, DEAD). The one thing that changed: a board-state capture
ASYMMETRY of the liquid core versus the board, used on the EXPOSURE side.
Base: L25 champion.

Off-switch: cp_w = 0 -> champion exactly.
SPACE: cp_w {42,63,126}, cp_thr {.1,.2,.3}, cp_cut {.5,1.0}, cp_mode {cut,rearm}.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from strat_l23a_liqconfirm import score as _champ
from strat_l22b_liqbreadth import liquid_mask
from strat_l29a_breadthspread import report_firings

NEEDS_DAILY = True
SPACE = {"cp_w": [0, 42, 63, 126], "cp_thr": [0.1, 0.2, 0.3], "cp_cut": [0.5, 1.0],
         "cp_mode": ["cut", "rearm"]}


def capture_asym(panels, params, w):
    months = np.array(panels["months"], dtype="datetime64[D]")
    cols = list(panels["cols"])
    liq = liquid_mask(panels, float(params["lq_min"]), int(params.get("lq_days", 40)))
    d = (panels["daily"].select("symbol", "date", "close")
         .with_columns(pl.col("date").cast(pl.Date))
         .sort("symbol", "date")
         .with_columns((pl.col("close") / pl.col("close").shift(1).over("symbol") - 1.0)
                       .clip(-0.3, 0.3).alias("r"))
         .drop_nulls("r"))
    dates = d["date"].to_numpy().astype("datetime64[D]")
    # month row a day belongs to: first m with months[m] > date
    mrow = np.searchsorted(months, dates, side="right")
    cidx = {s: j for j, s in enumerate(cols)}
    sj = np.array([cidx.get(s, -1) for s in d["symbol"].to_list()])
    ok = (mrow < len(months)) & (sj >= 0)
    is_core = np.zeros(len(d), dtype=bool)
    is_core[ok] = liq[mrow[ok], sj[ok]]
    f = pl.DataFrame({"date": d["date"], "r": d["r"], "core": is_core})
    agg = (f.group_by("date").agg(pl.col("r").mean().alias("board"),
                                  pl.col("r").filter(pl.col("core")).mean().alias("corer"),
                                  pl.col("core").sum().alias("ncore"))
           .sort("date"))
    ad = agg["date"].to_numpy().astype("datetime64[D]")
    b = agg["board"].to_numpy()
    c = agg["corer"].to_numpy().astype(float)
    nc = agg["ncore"].to_numpy()
    out = np.full(len(months), np.nan)
    for t in range(len(months)):
        hi = np.searchsorted(ad, months[t], side="left")  # dates < months[t]
        lo = hi - w
        if lo < 0:
            continue
        bb, cc, nn = b[lo:hi], c[lo:hi], nc[lo:hi]
        good = np.isfinite(bb) & np.isfinite(cc) & (nn >= 20)
        if good.sum() < w * 0.8:
            continue
        bb, cc = bb[good], cc[good]
        up, dn = bb > 0, bb < 0
        if up.sum() < 5 or dn.sum() < 5:
            continue
        upc = cc[up].mean() / bb[up].mean()
        dnc = cc[dn].mean() / bb[dn].mean()
        out[t] = dnc - upc
    return out


def score(panels, params):
    res = _champ(panels, params)
    scores, exposure = res[0], res[1]
    w = int(params.get("cp_w", 0))
    if w <= 0:
        return res
    thr = float(params.get("cp_thr", 0.2))
    cut = float(params.get("cp_cut", 0.5))
    mode = params.get("cp_mode", "cut")
    a = capture_asym(panels, params, w)
    base = np.asarray(exposure, dtype=float)
    out = base.copy()
    for t in range(len(out)):
        if not np.isfinite(a[t]):
            continue
        if mode == "cut" and a[t] > thr:
            out[t] = base[t] * (1.0 - cut)
        elif mode == "rearm" and a[t] < -thr and 0.0 < base[t] < 1.0:
            out[t] = 1.0
    report_firings(panels["months"], base, out, "L29A-cp")
    return (scores, out) + tuple(res[2:])
