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

## The three parts

| | |
| --- | --- |
| `data/` | The substrate. Strategy code reads it and never writes to it; only the downloaders rebuild it. |
| `scripts/` | The playground. Screeners, backtests and parameter labs — one file each, each with a `--help`. |
| `autoresearch/` | The search. One editable strategy file behind an immutable scoring harness, for running an agent in a keep-or-revert loop. |

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

## The autoresearch loop

`autoresearch/` runs a different kind of experiment. Instead of a human writing one strategy and
measuring it, an agent proposes a change, the harness scores it, and git keeps it or throws it
away — the [autoresearch pattern](https://github.com/karpathy/autoresearch), on this panel.

The discipline is the whole point, so it is enforced rather than trusted:

| File | |
| --- | --- |
| `strategy.py` | **The only file the loop may edit.** Returns a bars x symbols matrix of target weights |
| `program.md` | The instructions the agent reads — goal, rules, ideas, when to stop. The file a *human* iterates on |
| `prepare.py` | Builds the panel: total-return prices, a causally-computed tradability mask, forward-filled marks |
| `evaluate.py` | The simulation, the costs, the benchmark, the score, the look-ahead probe |
| `toolkit.py` | Causal, warm-up-guarded indicators over the matrix, so no iteration writes a second RSI |
| `backtest.py` | The command an iteration runs. Prints the report, appends `results.tsv` |
| `test_harness.py` | Synthetic panels whose right answers are known by construction |
| `harness.lock` | Hashes of the four harness files. A run whose measurement has moved refuses to score |

```
python autoresearch/backtest.py --note "what this iteration changed"
```

The score is `min(train Sharpe, validation Sharpe)` over two disjoint windows — 2008-2015 and
2016-2021 — net of a 25 bps round trip, and zero for a book that opens fewer than 100 positions
or averages under 20% invested. A minimum, because the loop will otherwise converge on whatever
fits one window; the guards, because both of those failure modes post a flattering Sharpe while
being unrunnable. The 2022-onward window is neither printed nor written to `results.tsv`, and is
worth something only for as long as it stays unseen.

Three things the harness checks that a human reviewer reliably does not:

- **Causality.** The strategy is re-run on truncated history, and the run fails if the book
  changes when the future is removed. A threshold fitted on the full panel gives itself away.
- **Reachability.** Weights on names that were not liquid enough on that bar are zeroed before
  scoring, so nothing is earned in a stock nobody could have bought.
- **Its own arithmetic.** `test_harness.py` pins the one-bar shift, the cost of a round trip,
  drift between rebalances, the benchmark as a mean rather than a median, and annualisation read
  off the timestamps. Four arithmetic errors once survived repeated self-review in this
  repository; these are the tests that catch that class.

Every run appends to `autoresearch/results.tsv`, including the reverted ones.

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
| Autoresearch baseline (`autoresearch/strategy.py`) | 2008-15 / 2016-21, Nifty 500 | Sharpe 0.77 / 1.57; +16.6% CAGR vs benchmark +10.8%, then +39.4% vs +19.7% | The floor the loop starts from. On the Nifty 200 the same rules score 0.66 and *lose* to the benchmark on the first window — the edge lives in the smaller half of the 500 |
| — momentum skipping the last month | same | Score 0.77 → 0.68 | **Reverted.** The standard reversal skip costs 2.7 points of CAGR on the first window here |
| EMA support (`ema_support.py`) | 3 yrs rolling | Cohort median hold rate ~37% on the 20 EMA, ~41% on the 50 | A ranking tool, not a strategy — read a name against the cohort, not against 50% |

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
