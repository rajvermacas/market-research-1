# market-research-1

A **backtesting playground for the Indian equity market (NSE)**. The price history is already
here and committed — daily bars for every main-board listing back to 2000, hourly bars, and a
corporate-action-adjusted Kite intraday panel reaching 2015 — so a new strategy starts at the
research, not at a download.

This is not one strategy's repository. `scripts/` is where strategies live: one file per
strategy or per experiment, each runnable from the command line, all reading the same panels
under `data/`. Ideas that were tested and found not to work stay in the tree with their
results written down, because the next idea is worth more when the last one's failure is on
record.

## The two halves

| | |
| --- | --- |
| `data/` | The substrate. Strategy code reads it and never writes to it; only the downloaders rebuild it. |
| `scripts/` | The playground. Screeners, backtests and parameter labs — one file each, each with a `--help`. |

## What is in `scripts/`

### Strategies and screeners

| Script | Setup | Timeframe |
| --- | --- | --- |
| `screener.py` | Pullback in an uptrend: higher timeframes strong, daily RSI dipped and just turning back up | daily |
| `hourly_rsi_screener.py` | Hourly RSI re-ignition — hourly RSI crosses 60 while daily/weekly/monthly RSI stay > 60 | hourly |
| `n_pattern.py` | Impulse, partial pullback onto a rising 10 EMA, resumption — the three-leg "N" | daily |
| `ema_support.py` | Which momentum names historically bounce off their daily 20/50 EMA, measured against a control | daily |
| `rsi_backtest.py` | Full backtest of the hourly RSI re-ignition setup, and the shared engine every other backtest imports | hourly |
| `momentum_rotation.py` | Cross-sectional momentum: hold the top *N* by trailing return, rebalance monthly, optional regime overlay | monthly, from daily |

### Research labs

Each of these takes one question about a strategy already in the tree and answers it on the data,
rather than on intuition.

| Script | Question |
| --- | --- |
| `rsi_filter_lab.py` | Which candidate entry filters raise the edge, measured on each half of the window separately? |
| `rsi_stop_lab.py` | Do the winning filters stack, or are they all one effect — and is the stop itself the problem? |
| `rsi_combo_search.py` | Every subset of the optional filters, scored, and reported only if it earns in both halves |
| `rsi_slots_sweep.py` | Portfolio slot count vs return, drawdown, and how much capital is actually deployed |

### Data pipeline

| Script | What it does |
| --- | --- |
| `download_market_data.py` | Rebuilds the universe and the Yahoo daily/hourly panels from scratch |
| `kite_download.py` | Deep intraday history from Kite Connect (back to ~2015, vs Yahoo's rolling ~730 trading days) |
| `clean_kite_panel.py` | Repairs the Kite panel: token reuse, non-positive prints, adjustment breaks |
| `validate_data.py` | Structural, quality and cross-interval checks — run after anything touches `data/` |

### The shared toolkit

Import these instead of writing a second copy that can drift from the first:

| From | Name | What it gives you |
| --- | --- | --- |
| `screener` | `rsi(column, period)` | Wilder's RSI as a Polars expression, validated to < 1e-9 against a textbook loop |
| `screener` | `resample(daily, every)` | Daily bars → weekly (`"1w"`) or monthly (`"1mo"`) OHLCV |
| `screener` | `fetch_market_caps(symbols)` | Market caps from Yahoo, cached under `.cache/screener/` |
| `hourly_rsi_screener` | `ema(column, span)` | EMA as a Polars expression |
| `rsi_backtest` | `prior_bar_rsi`, `attach_htf` | Higher-timeframe RSI joined onto intraday bars, shifted so it is knowable at the bar — with the warm-up guard |
| `rsi_backtest` | `attach_market_cap` | Today's cap walked back through the price series |
| `rsi_backtest` | `find_trades(frame, cost, reward_risk, ...)` | Forward walk from each signal to whichever of stop or target it reaches first |
| `rsi_backtest` | `simulate(trades, prices, slots, cost, ...)` | Equal-weight portfolio with a slot limit, marked bar by bar |
| `rsi_backtest` | `elapsed_years(grid)`, `performance(equity, years)` | CAGR and max drawdown, with elapsed time read off the timestamps |

## Quickstart

```python
import polars as pl

daily = pl.scan_parquet("data/ohlcv/daily/**/*.parquet", hive_partitioning=True)
hourly = pl.scan_parquet("data/ohlcv/60minute_kite_clean/**/*.parquet", hive_partitioning=True)
universe = pl.scan_parquet("data/universe/nse_universe.parquet")

# Nifty 50 members only, last 5 years
nifty50 = (
    daily.join(universe.filter(pl.col("in_nifty50")).select("symbol"), on="symbol")
    .filter(pl.col("date") >= pl.date(2021, 1, 1))
    .collect()
)

# 20/50-day moving-average crossover signal per symbol
signals = (
    daily.sort("symbol", "date")
    .with_columns(
        pl.col("adj_close").rolling_mean(20).over("symbol").alias("ma20"),
        pl.col("adj_close").rolling_mean(50).over("symbol").alias("ma50"),
    )
    .with_columns((pl.col("ma20") > pl.col("ma50")).alias("long"))
    .collect()
)

# Tradeable subset: enough history and real liquidity
liquid = (
    daily.filter(pl.col("date") >= pl.date(2024, 1, 1))
    .group_by("symbol")
    .agg(
        pl.len().alias("bars"),
        (pl.col("close") * pl.col("volume")).median().alias("median_turnover"),
    )
    .filter((pl.col("bars") > 400) & (pl.col("median_turnover") > 1e7))
    .collect()
)

# The `year` column comes from the partition path — filtering on it skips whole files
recent = daily.filter(pl.col("year") >= 2024).collect()
```

## Adding a strategy

A new strategy is a new file in `scripts/`. Name it for the mechanism (`momentum_rotation.py`,
`n_pattern.py`), not for the author or the attempt number.

```python
#!/usr/bin/env python3
"""One paragraph stating the setup in words: entry, stop, exit, universe, rebalance.

Then the caveats that apply to *this* test — what the data cannot tell you here.

Usage:
    python scripts/my_strategy.py --universe nifty500
"""
import argparse
from pathlib import Path

import polars as pl

from screener import rsi, resample                 # don't reimplement the indicators
from rsi_backtest import find_trades, simulate, elapsed_years, performance

REPO_ROOT = Path(__file__).resolve().parents[1]
```

The house rules, each of them the residue of something that went wrong here (the full list is
in [AGENTS.md](AGENTS.md#lessons)):

1. **State the setup in words first, then check the filters select for it.** "Daily RSI > 60"
   picks names that have already run; a pullback entry wants the RSI *low and turning up*.
2. **Point-in-time or it is not a backtest.** Higher-timeframe values read the last *completed*
   bar (`shift(1)`); anything fetched live today (market cap) is walked back, and said so.
3. **Guard indicator warm-up.** Wilder's RSI seeded at zero reads exactly 100.0 on bar one and
   passes any "RSI > 60" filter for free. `prior_bar_rsi` gates on `period * 3` bars — match it.
4. **Seed indicators from the longest history available**, not from the panel being traded.
   Warming the monthly RSI off the intraday panel once deleted 3.5 years — and the worst regime
   in the data — from a backtest without anyone deciding to.
5. **Always report a control.** Equal-weight buy-and-hold of the same universe over the same
   window, as the **mean** of normalised prices (never the median — that is not tradeable and is
   always lower). A return without a control measures the market.
6. **Report deployment alongside return.** A book that sits 20% invested has a smaller drawdown
   than the index because it is mostly in cash, not because it is safer.
7. **Charge costs, and score both halves of the window separately.** A result that only exists
   in one half is noise.
8. **Sweep every free parameter on the longest data you have.** Slot count swung CAGR by 39
   points across 2.9 years of bull market and by under two points across 11.6 years.
9. **Render the hits before believing a chart-pattern screen.** Geometric conditions are easy to
   satisfy in ways that look nothing like the intended shape.
10. **Write the result down — especially a negative one.** Commit message, and a row in the
    ledger below.

Scratch output belongs in `.cache/` (gitignored). After anything touches `data/`, run
`python scripts/validate_data.py`.

## Results so far

Numbers are from the run recorded in git history for each line; re-run the command to confirm
them, since a data refresh moves the window. Both survivorship bias and the thin early years
apply throughout — see [Data caveats](#data-caveats).

| Strategy | Window / panel | Result | Verdict |
| --- | --- | --- | --- |
| Hourly RSI re-ignition (`rsi_backtest.py`) | 11.5 yrs, Kite Nifty 500 | +18.1% CAGR at best vs equal-weight market +20.5%; return/drawdown 0.64 | **No tradeable edge.** What survives is a −24% drawdown against the market's −49% — a different ride, not a better return |
| — scaled exits (`find_trades_scaled`) | same | +14.8% vs +27.1% for the single far target | **Worse.** The edge is in the tail; banking half at 1:2 gives away what funds the losers |
| — breadth regime filter | Nifty 500, then full NSE | +17.7% → +27.1% on one universe; +44.2% → +3.8% on the other | **Fitted to one universe.** A real regime effect cannot do that |
| — slot count (`rsi_slots_sweep.py`) | 11.6 yrs, Nifty 500 | +4.4% to +6.2% across a 13-fold range of slots, vs benchmark +25.0% | **Not the free parameter it looked like** on the short window |
| Cross-sectional momentum (`momentum_rotation.py`) | 2015→, Nifty 500 | +29.7% CAGR at −15.5% drawdown unlevered (ratio 1.92); +35.7% at −19.8% at 1.25x, funded at 9% | **Most promising so far, and unsettled.** Survivorship is severe on today's index members, and it has not been tested on any universe but the one it was built on |
| EMA support (`ema_support.py`) | 3 yrs rolling | Cohort median hold rate ~37% on the 20 EMA, ~41% on the 50 | A ranking tool, not a strategy — read a name against the cohort, not against 50% |
| Inside-day pause-share tilt + retuned wobble on the floor-lift fresh-print book (`strat_l15b_insideday`, gw_w 0.15 / ids_lb 3 / ids_w −0.13, on the L13 concwobble chain) | 2015→2026, monthly, full NSE board, top 15 | Train **+96.9%** CAGR at −17.0% DD (calmar 5.69) vs equal-weight +19.8%/−62.7%; forward +49.0% (fwd DD −12.3% vs bench −27.9%); full-window DD −27.1% | **New best train line; beats the L13 chain on CAGR (+8.7pp), drawdown (0.3pp) and calmar (5.69 vs 5.08).** Signal = each name's share of inside days (a session whose high/low stay inside the prior session's range) over the 3 months before the monthly print; the tested direction rewards names whose tape had FEWER pause days — note the file's stated coil hypothesis is inverted vs the code. Both axes are plateaus: ids_w −0.10..−0.18 → 91.7–94.6 at gw 0.13; gw_w 0.10..0.20 → 94.3–96.9 at ids −0.13 (0.15/0.16 tie the peak). Documented frontier siblings: balanced gw 0.13/ids −0.13 (94.6/−18.9, calmar 5.01, fwd +54.4/−12.3), risk-lean ids −0.15/gw 0.13 (93.4/−17.0, calmar 5.49, fwd +52.9), forward-lean gw 0.00/ids −0.25 (89.3/−18.6, fwd **+62.2/−13.9**). Costs on the promoted point: 50bps → 94.6/calmar 5.52 (fwd +47.2), 100bps → 90.0/5.00 (fwd +43.6). Diagnostics: inside-day coverage ~100% of priced names, turnover unchanged vs the base (5.0 replacements/month), so the edge is a re-ranking effect, not churn or coverage. Independent audit (L15): clean-room re-run exact, PIT-clean, independent inside-day recomputation matches to 0.0; the whole +9.9pp train lift is the ids term (gw 0.15 alone = 87.0/−17.3) and it is train-side only (fwd 48.97 vs 49.29 untilted); ids_lb 3 is load-bearing (lb 6 → 86.4/−21.8). Caveats: the train-DD edge over the L13 chain flips at other train/forward splits (2020/2021: +10.5–10.7pp train but DD 1.5pp worse) and nothing transfers to Nifty 500 (+35.9/−25.1; fwd DD −29.0 worse than bench). Ledger: `.cache/strategy_lab/best.json` |
| Floor-lift fresh-print book + weak-month book cap + 3-month hold + eligibility-wobble tilt (`strat_l13a_concwobble`, cap_weak 11 / max_hold 3 / tier 0.9999 / gw_w 0.13 / gf_lb 12 / lookback 12) | 2015→2026, monthly, full NSE board, top 15 | Train +88.1% CAGR at −17.3% DD (calmar 5.08) vs equal-weight +19.8%/−62.7%; forward +49.3% (fwd DD −14.9% vs bench −27.9%); full-window DD −26.3% | **Superseded on the train ratchet by the inside-day tilt (L15, three promotions: +96.9%/−17.0%/calmar 5.69); remains the reference chain for the loop's incremental tests.** The wobble tilt (with `lookback 12`) buys +2.9pp of train for ~4.5pp of forward versus the un-tilted conc champion (85.2%/−17.5%, fwd +53.8%), which remains the forward-preserving alternative (the relstrength stack `rs_w 0.2/lb6 + cap_full 15/max_hold 6` pushes that line further to fwd +63.2%/−14.4%, forward-calmar 4.38 vs the champion's 3.30, at train 68.9 — documented in `strat_l14b_relstrength`, not ledger-eligible); the promoted point is a plateau in `gw_w` (0.10–0.13), a soft ridge in `gf_lb` (11–12), and `lookback` 11–12 tie on train with 12 better forward. Cost slopes: 50bps → 85.9%/calmar 4.87; 100bps → 81.6%/4.48. Doesn't transfer to index universes (Nifty 500 +39.2%/−26.7%, fwd DD worse than bench); full board carries survivorship bias — a lead, not a validated strategy. Lineage: tiershape (L10) → weak-month cap + short hold (L12) → eligibility-wobble tilt (L13) → lookback 12 (L14). Ledger: `.cache/strategy_lab/results.tsv` |
| Forward-geometry tilts on the low-train book (`strat_l15b_rngcomp` / `strat_l14b_relstrength` / `strat_l15b_fwdstack` / `strat_l15b_insideday`, all at cap_full 15 / max_hold 6) | 2015→2026, monthly, full NSE board, top 15 | Range-compression (cmp_lb 6 / cmp_w −0.4): train +74.0% at −19.7% DD, forward **+63.7%** (fwd DD −11.6%, fwd-calmar 5.49) vs bench +14.7%/−27.9%; market-relative strength (rs_w 0.2 / rs_lb 6): +68.9%/−19.7%, fwd +63.2%/−14.4%; rs+ids stack: fwd +68.0%/−16.0%; serpers choppy arm on the champion book: fwd +69.6%/−16.1% at train +72.7%; ids-on-geometry (gw 0.13/ids −0.13): train +84.5%/−18.9%, fwd +59.5%/−12.3% (fwd-calmar 4.84) | **The loop's forward frontier — the best forward risk-adjusted numbers in the ledger, none ratchet-eligible (train far below the champion).** The forward tilts are largely substitutes for one another (the rs+ids stack adds ~+1.2pp forward over ids-only but worsens fwd DD by ~1.2pp); the low-drawdown property does not survive the un-fitted universe (Nifty 500: fwd +28.9%/−32.0% — DD worse than the index bench), so these are documented alternatives, not promoted lines. The range-compression crown was chosen on the forward window itself (designer smoke read forward prints and stacked to improve them) — an in-sample forward pick, not a clean holdout; both the champion and the crown passed independent clean-room/PIT audits (L15). |
| Loop-16 mechanism screens on the champion book (`strat_l16a_idsrng` / `strat_l16a_seasmom` / `strat_l16a_monpath` / `strat_l16a_dskew` / `strat_l16b_outrank` / `strat_l16b_hurdle` / `strat_l16c_volpart`) | 2015→2026, monthly, full NSE board, top 15, 25 bps | Every active variant trailed the champion (+96.9%/−17.0%, calmar 5.69) by 3–34pp, each after a bit-exact off-switch identity: range compression re-based on the ids chain 69.5–75.8; seasonal momentum 66.4–86.5; intramonth path shape 62.8–76.3; daily skewness 74.4–78.0; cross-sectional outrank 84.8–94.4; volume participation 58.0–81.5; replacement hurdle 96.1–97.5. The one KEEP (`strat_l16b_hurdle`, hur_m 0.01 / hur_n 2) reads train +97.5%/−17.0%/calmar 5.72 (h1 +99.5, h2 +95.5, fwd identical) but is a knife-edge: 0.005 → 96.88 (no fire), 0.0075 → 97.28, 0.010 → 97.48, 0.015 → 96.24, 0.02 → 96.24, 0.03–0.06 → 96.4–96.9, with the gain resting on ONE hurdle firing (2017-07, reinstating AVANTIFEED over STARPAPER) that propagates through the path-dependent held set into 3 differing decision months, all in H1 (independent audit replay, harness-validated to 1e-9), and zero forward/DD effect | **No promotion — the champion stands.** The per-name daily-tape axis is saturated by the ids term (four tape signals plus volume participation, all losing in both directions), and the incumbency-protection family closes completely (bonus dead L13, budget dead L15, boundary hurdle = in-sample knife-edge L16). Next loop needs a new channel, not another tape re-ranking. |
| Loop-17 mechanism screens on the champion book (22 files: `strat_l17a_*` path structure, `strat_l17b_*` panel structure, `strat_l17c_*` attributes/regimes, `strat_l17d_*` round-2 tape signals, `strat_l17o_consist`) | 2015→2026, monthly, full NSE board, top 15, 25 bps | All 22 passed a bit-exact off-switch identity (+96.88%/−17.03%/5.69) and every active direction trailed the champion: panel structure 58.1–91.2; path structure 57.4–95.5; attributes 75.6–96.5 (index-membership gate −0.32); regimes 68.6–94.9. One mechanical keep, `strat_l17c_pxlevel` (pxfv +0.3), reads +97.46% train but DD −18.67 (calmar 5.22 vs 5.69) and fwd +38.0/−20.8 vs +49.0/−12.3 — a train artifact, not promoted. Structural: the champion book is essentially non-index members (a membership gate collapses it) and its BE/BZ-series tail is load-bearing (EQ-only costs 21pp). | **No promotion — the champion stands.** The panel/path/attribute/regime axes are all saturated at this base; forward-heavy arms (fwd +58.8–69.9 at train 57–87) remain documented alternatives only. |
| **Tight-spread liquidity tilt** `strat_l20b_spread` (Corwin–Schultz two-day high-low spread proxy, 4-month trailing mean, cross-sectional percentile tilt `sp_w −0.05`) | 2015→2026, monthly, full NSE board, top 15, 25 bps | Train **+103.0%** CAGR at **−15.5%** DD (calmar **6.64**) vs equal-weight +19.8%/−62.7%; forward **+54.1%** at **−10.4%** DD (fwd calmar 5.21); full decade +82.0%/−20.7% (calmar 3.96); worst complete year −15.0%; yearly stdev 172 | **New champion (Loop-20)** — promoted on the main CAGR ratchet. Signal: the Corwin–Schultz (2012) two-day high-low spread estimator (negative estimates floored at 0), averaged over 4 months, ranked cross-sectionally; the tested direction favours **tight-spread** names, i.e. names with real depth. The promoted cell is the risk-clean HALF DOSE: it improves all four headline dimensions vs the L19 line (train +4.3pp, DD equal, calmar +0.28, fwd +0.9pp, fwd DD equal). Dose-response caveat: the full dose (`−0.1`) reads train +103.8%/−15.0%/calmar 6.92 — mechanically the higher keep — but pays **2.68pp of forward DD** (−13.1% vs −10.4%); the break trips already at −0.075, so promotion took the risk-clean dose and declined the mechanical higher keep. Robustness: the lb neighbourhood is a flat hump (3:103.1, 4:103.8, 5:103.5, 6:103.3, 8:101.2, all DD −15.0); book footprint 23/139 decision months — independently re-derived by the clean-room audit (harness-faithful replay; the tool agrees name-for-name), so the book change is broad, not a handful of name-months. Costs on the promoted point: 50bps → 100.59%/calmar 6.30 (fwd +52.18/−10.52), 100bps → 95.87%/5.63 (fwd +48.48/−10.78). Split behaviour: from 2018-01 train 84.6%/−12.4% (H1 −6.7% — the weak half), from 2020-01 264.0%/−11.8%; forward identical at 54.06/−10.38 in every split run. Audit note: the promoted cell lies outside the file's documented SPACE (sp_lb {6,12}, sp_w ±0.1) — it comes from the close-out dose sweep; and choosing the dose partly on the forward window spends holdout, so the forward numbers are the family's upper edge — read them accordingly. Post-commit robustness: the lb-4 dose curve is monotone from −0.025 (102.05) to −0.1 (103.83) with no cliff below the promoted point, so −0.05 is exactly the highest risk-clean dose; the coverage guard is inert at 0.3/0.5/0.7; and the illiq × half-dose-spread stack still interferes (best 102.61, fwd DD break), confirming composition must be across channels. Companion findings from the same loop: Amihud illiquidity `il_lb 12 / +0.1` (102.4/−16.0/6.41, fwd +54.4, fwd DD equal, independently reproduced, declined only because the promoted cell dominates it); illiq × spread **interfere** (best combo 102.1, below both parents; avg form below base); the first use of `adj_close/close` in the tree (dividend-factor size × timing) is sign-consistent but calmar-negative (best combo 103.6/−16.6/6.26, fwd +55.7, a confirmed weight spike); the champion's **cap-before-tilt order is load-bearing** (`strat_l20o_tiltorder`: pre-cap placement 74.9–97.2); the sector axis remains untestable — a company-name keyword sector key covers only 56% of the panel (agreement 77.6% vs 15.5% chance), so the family needs an external sector map, not a new mechanism. Nifty 500 transfer fails as always (+36.6/−23.9 train, fwd +18.0/−31.4). Ledger: `.cache/strategy_lab/best.json` |
| **Balanced composition** `strat_l19a_balanced` (listing-age × cross-sectional outrank on the ids champion chain; la_w 0.5 / or_w −0.1) | 2015→2026, monthly, full NSE board, top 15, 25 bps | Train **+98.7%** CAGR at **−15.5%** DD (calmar **6.36**) vs equal-weight +19.8%/−62.7%; forward **+53.2%** at −10.4% DD (fwd calmar 5.11 vs bench 0.53); full decade +79.2%/−20.7% (calmar 3.82); worst complete year −14.9%; yearly stdev 159 | **Superseded by the Loop-20 spread tilt** (train +103.0%/−15.5%/calmar 6.64, fwd +54.1). Promoted in Loop-19 on the main CAGR ratchet: beat the L15 line on CAGR (+1.8pp), DD (1.5pp) and calmar (6.36 vs 5.69). Composes two Loop-17 tilts (listage la_w 0.5 + outrank or_w −0.1), each bit-exact vs its source; balanced-calmar alternatives were calreg cr_w 0.70 (6.21, but −6pp CAGR) and listage alone (6.18). Caveats: Nifty 500 transfer failed (+39.0/−23.9 train, fwd +21.7/−31.4), 2021 (+461%) dominated the decade (best-year share 44%), yearly dispersion marginally higher than the L15 line's (159 vs 150). Its key neighbourhood was re-measured in Loop-20: la_w 0.6 (99.3) and or_lb 8 (99.1) are interior optima, both below the new champion. |

## The data

| Path | Contents |
| --- | --- |
| `data/ohlcv/daily/year=*/data.parquet` | The daily panel — `symbol, date, open, high, low, close, adj_close, volume` (+ `year` from the partition path) |
| `data/ohlcv/hourly/year=*/data.parquet` | Yahoo hourly bars — `symbol, datetime` (Asia/Kolkata), `open, high, low, close, volume`; no `adj_close` |
| `data/ohlcv/60minute_kite/year=*/data.parquet` | Kite hourly bars for the Nifty 500, back to 2015-02, corporate-action adjusted |
| `data/ohlcv/60minute_kite_clean/year=*/data.parquet` | The same after `clean_kite_panel.py` — **this is the one to trade** |
| `data/ohlcv/_coverage_*.csv` | Per-symbol bar count and first/last timestamp, per interval |
| `data/ohlcv/_manifest.json` | Snapshot provenance, stats and caveats for the Yahoo panels — the source of truth |
| `data/universe/nse_universe.parquet` | Every NSE main-board symbol: company, series, ISIN, listing date, face value, industry + Nifty index membership flags |
| `data/universe/nse_universe.csv` | Same, as CSV for quick eyeballing |

Numbers below describe the committed snapshot; `data/ohlcv/_manifest.json` is regenerated on
every refresh and always reflects what is actually on disk.

### Daily — the deep panel

| | |
| --- | --- |
| Interval | Daily (`1d`) |
| Rows | 7,465,347 |
| Symbols with data | 2,559 of 2,559 — the entire NSE main board |
| Date range | 2000-01-03 → 2026-08-27 |
| Trading sessions | 6,657 |
| On disk | 131 MB across 27 yearly Parquet files (largest 9.6 MB) |

History per symbol is very uneven — this is a full-market panel, not an index panel:

| Percentile | Bars available |
| --- | --- |
| 5th | 7 |
| 25th | 682 |
| 50th | 2,389 |
| 75th | 5,108 |
| 95th | 6,003 |

403 symbols have under a year of history, and only 81 reach all the way back to
January 2000. **Filter on bar count before any cross-sectional ranking** or recent listings will
distort the results.

#### The early years are thin — read this before backtesting pre-2005

The date range says 2000, but coverage in the early years is a small fraction of the market that
actually traded. Measured against NSE's own daily bhavcopy (the official end-of-day record of every
symbol that traded):

| Date | Symbols that traded on NSE | In this panel | Coverage |
| --- | --- | --- | --- |
| 2000-06-12 | 917 | 86 | **9%** |
| 2004-06-10 | 752 | 570 | 76% |
| 2008-06-10 | 1,225 | 898 | 73% |
| 2012-06-11 | 1,514 | 1,089 | 72% |
| 2016-06-10 | 1,532 | 1,226 | 80% |
| 2020-06-10 | 1,683 | 1,577 | 94% |
| 2024-06-10 | 2,208 | 1,975 | 89% |

Two effects stack. Delisted and merged companies are absent entirely (survivorship bias), and
Yahoo's Indian history is shallow even for companies that still trade — ABB, ACC and AARTIIND are
all currently listed and still have no year-2000 data there.

Practical reading: treat this panel as solid from roughly 2015, usable with care 2005–2015, and
**not representative of the market before about 2004**. A cross-sectional backtest run on 2000-2003
is ranking 9% of the universe, pre-selected for having survived to 2026.

Curing this requires a different source — NSE bhavcopy, stacked per trading day, which records the
universe as it was on each date. See `AGENTS.md` for the approach.

### Hourly — two panels, and which to use

| | Yahoo `hourly` | Kite `60minute_kite_clean` |
| --- | --- | --- |
| Symbols | 2,559 — the whole main board | 500 — the Nifty 500 |
| Range | 2023-09-18 → 2026-08-28 | 2015-02-02 → 2026-08-28 |
| Rows | 9,901,435 | 7,864,122 |
| Corporate actions | **not adjusted** | back-adjusted by Kite |
| On disk | 132 MB | 100 MB |

**Anything spanning 2018 or 2020 has to use the Kite panel**, and the `_clean` one specifically:
Kite reuses instrument tokens, so the raw panel gives a 2019 listing the 2015 prices of whatever
security held its token before — AFFLE reads as a 469x return and poisons any equal-weight
benchmark built from it. `clean_kite_panel.py` adjudicates each case against the independently
sourced Yahoo daily panel and drops 14,858 such bars plus 1,677 non-positive prints. The Kite
panels are not described by `_manifest.json`, which covers the Yahoo download only.

The Yahoo hourly panel covers the whole market but only one rising market. Two further
differences from the daily panel matter: there is no `adj_close`, because Yahoo does not
dividend-adjust intraday bars and the value it returns is a verbatim copy of `close`; and 13.4%
of its bars have zero volume (against 4.0% daily), which is what a thinly traded name looks like
inside the session rather than a data fault.

Mixing the two adjustment conventions in one test puts a demerger into one timeframe and not the
other — `rsi_backtest.py --daily-from-hourly` exists so a Kite-panel run can derive its daily
bars from the same source it trades.

### Weekly and monthly are not committed

They are a one-line resample of daily, so committing them would buy nothing but repository size:

```python
weekly = (
    daily.sort("date")
    .group_by_dynamic("date", every="1w", group_by="symbol")
    .agg(
        pl.col("open").first(), pl.col("high").max(), pl.col("low").min(),
        pl.col("close").last(), pl.col("adj_close").last(), pl.col("volume").sum(),
    )
)
```

`scripts/screener.py` exposes this as `resample(daily, "1w" | "1mo")`. If you really want the
files, `python scripts/download_market_data.py --interval weekly monthly` writes them.

Hourly, by contrast, cannot be derived from daily at all, and Yahoo serves only a rolling window
of it — which is why the intraday panels are committed rather than left to be re-downloaded.

### Universe

`data/universe/nse_universe.parquet` is NSE's full main-board equity list (series `EQ` 2,288,
`BE` 243, `BZ` 28). Nifty index membership is carried as boolean columns, so narrowing to an index
is a filter rather than another download:

```python
nifty50 = universe.filter(pl.col("in_nifty50"))   # also in_niftynext50, in_nifty100, in_nifty200,
                                                   # in_nifty500, in_niftymidcap150,
                                                   # in_niftysmallcap250
```

Every Nifty index constituent is present: Nifty 50 50/50, Next 50 50/50, Nifty 100 100/100,
Nifty 200 200/200, Nifty 500 500/500, Midcap 150 150/150, Smallcap 250 250/250.

Not included, because Yahoo Finance does not serve them: **NSE Emerge (SME)** symbols and
**BSE-exclusive** listings.

## The strategy scripts in detail

### Pullback screener

`scripts/screener.py` implements a **pullback-in-uptrend** screen: higher timeframes strongly
trending, daily RSI dipped, daily RSI just turning back up — so the entry lands as strength
resumes rather than after the move has run.

```bash
python scripts/screener.py                      # full NSE universe
python scripts/screener.py --universe nifty500
python scripts/screener.py --pullback-max 50 --rising-bars 1   # looser
python scripts/screener.py --mode trend         # plain "daily+weekly+monthly RSI > 60"
```

Default conditions, each a flag:

| Stage | Condition |
| --- | --- |
| Structure | monthly RSI(14) > 60, weekly RSI(14) > 60, close above 200-day SMA |
| Pullback | daily RSI dipped to <= 45 within the last 15 bars |
| Turn | daily RSI rising 2 consecutive bars, >= 3 points off its trough, trough <= 7 bars ago |
| Not late | daily RSI still below 65 |
| Tradable | market cap > 5,000 crore, 20-day average turnover > 5 crore |

`--mode trend` is the opposite selection — it finds names already extended, which is what a
"daily RSI > 60" condition gives you.

RSI is Wilder's, validated to machine precision (< 1e-9) against a reference implementation on
daily, weekly and monthly. Market caps are fetched live from Yahoo, since the repository stores
prices but not fundamentals; results are written to `.cache/screener/` (gitignored).

**The last daily bar matters here.** If the snapshot was captured mid-session, the "RSI rising"
test is reading an incomplete bar and can flip by the close. The screener prints a warning when
`_manifest.json` flags the final bar as partial — refresh the daily panel after 15:30 IST for a
settled read.

### Hourly RSI re-ignition — screener and backtest

`scripts/hourly_rsi_screener.py` finds the live signals; `scripts/rsi_backtest.py` is the test
of the same setup and the engine the rest of the backtests import.

```bash
python scripts/hourly_rsi_screener.py --universe nifty500
python scripts/hourly_rsi_screener.py --explain          # per-condition funnel

python scripts/rsi_backtest.py --hourly-dir 60minute_kite_clean --daily-from-hourly \
    --reward-risk 5 10 15 --slots 10
```

The setup: a stock trending on every higher timeframe whose hourly momentum cooled off and is
only now turning back up through 60. Entry at that candle's close, stop at the candle's low,
target a multiple of that risk. When one candle spans both stop and target the stop is assumed to
fill first — the hourly bar does not say which came first, and the alternative books the win
every time.

The backtest's flags cover the questions worth asking of it: `--hourly-dir` picks the panel,
`--daily-from-hourly` keeps one adjustment convention throughout, `--slots` and `--per-symbol`
shape the portfolio, `--shared-stop` and `--fixed-notional` change how positions are managed, and
`--cost-bps` charges the round trip. The verdict on the strategy is in the ledger above.

### Momentum rotation

`scripts/momentum_rotation.py` tests a different mechanism rather than another setting of the
same one: rank the universe by trailing return, hold the leaders, rebalance monthly.

```bash
python scripts/momentum_rotation.py --lookback 12 --top 25 --regime-ma 10 --stock-ma 10 --abs-mom
python scripts/momentum_rotation.py --leverage 1.0 1.25 1.5 --funding-rate 0.09
```

The lookback skips the most recent month, where short-term reversal runs against momentum.
`--stock-ma` and `--abs-mom` ask whether a name is trending at all — ranking is relative, so in a
falling market it happily keeps ranking falling stocks highly. `--regime-ma` sits the book in cash
while an equal-weight index of the universe is below its own N-month average.

### EMA support analysis

`scripts/ema_support.py` answers a different kind of question from the screeners: not "what
qualifies today" but "which momentum names *historically* bounce off their daily 20/50 EMA".

```bash
python scripts/ema_support.py                     # monthly RSI > 60 universe, 3-year window
python scripts/ema_support.py --years 5 --min-touches 12
python scripts/ema_support.py --horizon 20 --break-tol 0.03
```

A touch is counted when the previous close sat comfortably above the EMA (`--separation`,
default 1.5%) and the bar's low came down to it (`--touch-tol`, 0.5%) — requiring the prior bar to
be clearly above is what stops a week of chopping along the average counting as five touches. It
held if no close over the next `--horizon` bars fell more than `--break-tol` below the EMA and the
close at the horizon is back above it.

Two numbers matter, and the second is the honest one:

- **hold rate** — share of touches that held. Cohort median is ~37% on the 20 EMA and ~41% on the
  50 EMA, so read a name against that, not against 50%. The tool ranks rather than gates for this
  reason (`--min-hold` defaults to 0).
- **edge** — median return after a touch minus the same stock's median return from a random bar in
  the window. A stock in a relentless uptrend posts a high hold rate because *any* entry worked.
  Positive edge is what says the average itself carried information.

### N-pattern screener

`scripts/n_pattern.py` finds the three-leg continuation shape — impulse up, partial pullback that
leans on a rising 10 EMA, then resumption — by decomposing the recent swings:

```
      B          D        A  swing low the impulse starts from
     /\         /         B  impulse high
    /  \       /          C  pullback low: a HIGHER low than A, resting on the 10 EMA
   /    \     /           D  today, turning back up off C
  A      C___/
```

```bash
python scripts/n_pattern.py                            # full NSE universe
python scripts/n_pattern.py --universe nifty500 --charts 9
python scripts/n_pattern.py --min-impulse 0.10 --max-retrace 0.5
```

B is the highest high in the last `--window` bars, A the lowest low before it, C the lowest low
after it. Conditions then cover the geometry: impulse size, retracement depth, `C > A`, C touching
the 10 EMA without closing far below it, how recently C formed, how far price has resumed, and the
EMA rising with price above it.

**Leg duration matters as much as leg size.** Without `--max-leg1-bars` and `--min-pullback-bars`,
a stock in one long uninterrupted trend matches: A pins to the left edge of the window, the
"impulse" measures the entire run, and the "pullback" is a one-day wick near the highs. Those
constraints are what keep the pattern local and shaped like an N.

`--charts N` renders the top hits as candlesticks with the EMA and the A/B/C levels marked. Use it
— geometric conditions are easy to satisfy in ways that look nothing like the intended shape, and
the picture is the only quick way to catch that.

## Refreshing the data

```bash
pip install -r requirements.txt

python scripts/download_market_data.py --interval daily       # rebuild the committed panel
python scripts/download_market_data.py --universe nifty50     # smaller run
python scripts/download_market_data.py --start 2015-01-01 --end 2025-12-31

python scripts/validate_data.py                               # verify the result
```

The universe is re-fetched from NSE's public archives on every run, so a refresh also picks up new
listings and index reshuffles. Each batch is checkpointed under `.cache/` (gitignored): an
interrupted run resumes rather than re-fetching thousands of symbols. Pass `--fresh` to ignore
checkpoints.

Yahoo throttles somewhere past ~1,500 consecutive symbol requests, so a full run is paced and takes
roughly 20–30 minutes. The downloader detects throttling explicitly and **aborts with a resume hint
rather than writing a panel with silent holes**.

The Kite panel is a separate, deliberate run — its access token expires daily and refreshing it
needs an interactive login, so it is not something to schedule:

```bash
export KITE_API_KEY=...   KITE_API_SECRET=...          # never as CLI arguments
python scripts/kite_download.py --login                # then open the URL it prints
echo "<request_token>" | python scripts/kite_download.py --exchange
python scripts/kite_download.py --interval 60minute --universe nifty500
python scripts/clean_kite_panel.py --in 60minute_kite --out 60minute_kite_clean
```

## Data caveats

Worth reading before trusting a backtest:

1. **Survivorship bias.** The universe is NSE's *current* main-board listing. Companies delisted
   before the snapshot are absent entirely, which flatters long-only backtests — and momentum
   strategies most of all, since the names that fell out of an index are exactly the ones such a
   book would have been holding on the way down.
2. **Uneven history.** Median symbol has ~2,400 bars, not 6,600. See the percentile table above.
3. **Adjustments.** In the daily panel `open/high/low/close` are split-adjusted as served by
   Yahoo and `adj_close` is additionally dividend-adjusted; use `adj_close` for return series and
   raw `close` for price levels. The Yahoo hourly panel is *not* corporate-action adjusted; the
   Kite panels are. Do not mix conventions inside one test.
4. **Partial last bar.** If a snapshot is taken while the NSE session is open, the newest bar is
   incomplete. `last_bar_possibly_partial` in `_manifest.json` flags it — filter that date out
   before backtesting. It is set in the current snapshot (2026-08-27).
5. **Upstream gaps.** Yahoo occasionally drops a session for individual symbols — 2026-08-26 is
   missing for a large share of the universe. `scripts/validate_data.py` reports affected dates.
6. **Bad ticks.** 1,852 bars of 7.47M (0.025%, across 290 symbols) violate OHLC ordering upstream,
   mostly illiquid names on zero volume. Documented rather than silently patched.
7. **Zero-volume bars.** 4.0% of daily bars (300,926) have zero volume — thin names with no trades
   that session. Screen them out for anything execution-sensitive.
8. **Kite adjustment breaks.** 28 symbols whose Kite total return disagrees with Yahoo's by more
   than a quarter are reported by `clean_kite_panel.py` rather than patched.
9. **Symbol availability.** In this snapshot every NSE main-board symbol resolved on Yahoo
   (`symbols_unavailable_on_yahoo` is empty). The downloader records a symbol as absent only when
   Yahoo explicitly says so, never on a transient failure — an earlier run mislabelled a whole
   failed batch of large caps as "no history", and that class of bug now fails loudly instead.

Data sources: Yahoo Finance via `yfinance` and Kite Connect; symbol lists from NSE's public
archives. For personal research use — check the respective terms before redistributing.

## Agent instructions

See [AGENTS.md](AGENTS.md).
