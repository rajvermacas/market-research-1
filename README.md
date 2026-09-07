# market-research-1

Daily OHLCV price history for **every NSE-listed Indian equity**, 2000 to date, stored as
year-partitioned Parquet and meant to be read with [Polars](https://pola.rs) for strategy research
and backtesting.

## What is in here

| Path | Contents |
| --- | --- |
| `data/ohlcv/daily/year=*/data.parquet` | The price panel — `symbol, date, open, high, low, close, adj_close, volume` (+ `year` from the partition path) |
| `data/ohlcv/hourly/year=*/data.parquet` | Hourly bars — `symbol, datetime` (Asia/Kolkata)`, open, high, low, close, volume`; no `adj_close` |
| `data/ohlcv/_coverage_*.csv` | Per-symbol bar count and first/last timestamp, per interval |
| `data/ohlcv/_manifest.json` | Snapshot provenance, stats and caveats — the source of truth |
| `data/universe/nse_universe.parquet` | Every NSE main-board symbol: company, series, ISIN, listing date, face value, industry + Nifty index membership flags |
| `data/universe/nse_universe.csv` | Same, as CSV for quick eyeballing |
| `scripts/download_market_data.py` | Rebuilds everything above from NSE + Yahoo Finance |
| `scripts/validate_data.py` | Structural and data-quality checks |
| `scripts/hourly_rsi_screener.py` | Hourly RSI re-ignition screen under a daily/weekly/monthly trend filter |
| `scripts/strategy_lab.py` | Daily strategy simulator: momentum, breakout, pullback families with regime overlays, point-in-time liquid universe |

### The data present

Numbers below describe the committed snapshot; `data/ohlcv/_manifest.json` is regenerated on every
refresh and always reflects what is actually on disk.

| | |
| --- | --- |
| Interval | Daily (`1d`) |
| Rows | 7,465,347 |
| Symbols with data | 2,559 of 2,559 — the entire NSE main board |
| Date range | 2000-01-03 → 2026-08-27 |
| Trading sessions | 6,657 |
| On disk | 131 MB across 27 yearly Parquet files (largest 9.6 MB) |
| Compression | zstd |

And the hourly panel, which reaches back only as far as Yahoo serves intraday bars:

| | |
| --- | --- |
| Interval | Hourly (`1h`) |
| Rows | 9,901,435 |
| Symbols with data | 2,559 of 2,559 |
| Range | 2023-09-18 09:15 → 2026-08-28 15:15 IST (5,068 hourly bars) |
| Bars per symbol | median 5,003 |
| On disk | 132 MB across 4 yearly Parquet files (largest 47 MB) |
| Columns | `symbol, datetime, open, high, low, close, volume` — **no `adj_close`** |

Two differences from the daily panel matter when you use it. There is no `adj_close`, because
Yahoo does not dividend-adjust intraday bars — the value it returns is a verbatim copy of `close`,
so shipping it would invite silently wrong total-return math. And 13.4% of hourly bars have zero
volume (against 4.0% daily), which is what a thinly traded name looks like inside the session
rather than a data fault.

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

Every Nifty index constituent is present: Nifty 50 50/50, Next 50 50/50, Nifty 100 100/100,
Nifty 200 200/200, Nifty 500 500/500, Midcap 150 150/150, Smallcap 250 250/250.

### Daily and hourly are committed; weekly and monthly are not

Hourly is in git despite its size, because it is the one panel that cannot be reconstructed later:
Yahoo serves only a rolling window of intraday bars, so history that scrolls off the end is simply
gone unless a snapshot was taken. Weekly and monthly stay out — they are a one-line resample of
daily, so committing them would buy nothing but repository size:

```bash
python scripts/download_market_data.py --interval weekly monthly   # if you really want the files
```

Weekly and monthly do not need a download at all — resample the daily panel:

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

Hourly cannot be derived from daily at all — an hourly bar is not recoverable from a daily one —
which is exactly why it is committed rather than left to be re-downloaded.

## Universe

`data/universe/nse_universe.parquet` is NSE's full main-board equity list (series `EQ` 2,288,
`BE` 243, `BZ` 28). Nifty index membership is carried as boolean columns, so narrowing to an index
is a filter rather than another download:

```python
nifty50 = universe.filter(pl.col("in_nifty50"))   # also in_niftynext50, in_nifty100, in_nifty200,
                                                   # in_nifty500, in_niftymidcap150,
                                                   # in_niftysmallcap250
```

Not included, because Yahoo Finance does not serve them: **NSE Emerge (SME)** symbols and
**BSE-exclusive** listings.

## Quickstart

```python
import polars as pl

daily = pl.scan_parquet("data/ohlcv/daily/**/*.parquet", hive_partitioning=True)
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

## Screener

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
daily, weekly and monthly. Weekly and monthly are resampled from the daily panel. Market caps are
fetched live from Yahoo, since the repository stores prices but not fundamentals; results are
written to `.cache/screener/` (gitignored).

**The last daily bar matters here.** If the snapshot was captured mid-session, the "RSI rising"
test is reading an incomplete bar and can flip by the close. The screener prints a warning when
`_manifest.json` flags the final bar as partial — refresh the daily panel after 15:30 IST for a
settled read.

## EMA support analysis

`scripts/ema_support.py` answers a different kind of question from the screener: not "what
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

## N-pattern screener

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

## Strategy lab

`scripts/strategy_lab.py` is one daily-resolution simulator for several strategy families, built
to answer "what does this strategy actually return, and what does it cost to hold it" under the
same accounting every time: `adj_close` total return, fills at the **next day's open**, 30 bps per
unit of turnover, a daily (not month-end) drawdown, and CAGR from elapsed calendar time.

```bash
python scripts/strategy_lab.py --strategy ew                                   # benchmark
python scripts/strategy_lab.py --strategy mom --lookback 252 --top 20 --regime sma200
python scripts/strategy_lab.py --strategy breakout --entry-n 100 --top 10 --rank sharpe \
    --regime sma100 --stock-sma 200 --daily-exit regime --eq-curve 50 --eq-band 0.02 --cash-rate 0.06
python scripts/strategy_lab.py --strategy breakout --entry-n 150 --top 12 --atr-mult 3 --exit-weekly \
    --rank mom2 --regime sma100 --stock-sma 100 --eq-curve 50 --eq-band 0.02 --eq-scale 0.3 \
    --dd-budget 0.22 --dd-start 0.12 --dd-floor 0.25 --cash-rate 0.06   # the hard-gate configuration
python scripts/strategy_lab.py --sweep breakout --yearly                       # parameter grid
```

The universe is rebuilt point-in-time on every day: the top N names by trailing 126-day median
turnover among those with a year of history, a price above ₹10 and **at least ₹1 crore a day of
turnover**. That floor matters more than anything in the strategy: the first version of this lab
used a plain rank and let names trading ₹10–90 lakh a day into the book, and those names supplied
most of the apparent return. Adding the floor cut the breakout system from +29% to +20% CAGR
before any other change. The panel also carried four Saturday "sessions" on which three symbols
have a bar and nothing else does; one such row blanks every 200-day rolling window for 200 days,
which is why the momentum strategy sat in cash for all of 2012 until they were dropped.

### Results, 2007-01 to 2026-08, liquid universe, 30 bps, cash at 0%

| Strategy | CAGR | Max DD | Calmar | Invested |
| --- | --- | --- | --- | --- |
| Equal-weight universe, monthly rebalance (benchmark) | +13.0% | -72.9% | 0.18 | 100% |
| Momentum 12-1, top 20, monthly, no filters | +21.5% | -84.4% | 0.26 | 100% |
| Momentum + abs-mom + own 200 SMA + index 200 SMA regime + daily exit | +19.4% | -41.8% | 0.46 | 61% |
| Momentum ranked by return/vol, top 20, same filters | +22.5% | -41.8% | 0.54 | 60% |
| RSI(2) pullback in uptrend, best of 48 settings | +7.8% | -46.6% | 0.17 | 55% |
| 100-day breakout, 4 ATR trail, top 20, index 200 SMA regime | +19.4% | -32.0% | 0.61 | 64% |
| Breakout, top 10, index 100 SMA regime | +26.4% | -30.9% | 0.85 | 62% |
| Breakout, top 10, candidates ranked by 12-1 return / vol | +26.9% | -29.2% | 0.92 | 62% |
| ... + equity-curve cut (half size below 50-day average, ±2% band) + cash at 6% | **+28.0%** | **-23.8%** | 1.18 | 55% |
| ... at 1.05x gross | +29.0% | -25.1% | 1.16 | 58% |
| ... at 1.1x gross, funded at 9% | +30.2% | -26.4% | 1.14 | 60% |

Mean reversion is dead at these costs (36–64x annual turnover), and the pure momentum rotation
carries the full crash. Trend following on breakouts is the family that works. The changes that
moved it most were concentrating to ten names (top 20 on the final settings is +22.6% at -31.9%),
a 100-day rather than 200-day index regime (+4 points of CAGR), ranking the day's breakouts by
trailing return-to-volatility instead of raw return (+1.7 points, 4 points less drawdown), and
cutting size while the strategy's own equity is falling (5 points less drawdown, once its own
switching costs are charged).

### The target, and why the loop stopped

The brief was **CAGR ≥ 30% with max drawdown ≤ 25%**, a Calmar of 1.20 over nineteen and a half
years that include 2008. Roughly 450 configurations were run across three sweeps and nine
focused batches at this stage (about 1,400 by the end of the fourth loop). The best fully-costed result is +28.0% at -23.8%; leverage trades one bound for
the other (1.05x → +29.0% / -25.1%; 1.1x → +30.2% / -26.4%) and never satisfies both. Two sleeves
(breakout 70% + momentum 30%) do no better, because their daily returns are 0.6 correlated.

The loop stopped there for a reason the LESSONS in `AGENTS.md` already record: the remaining gap
is about one point on either metric, and the neighbouring settings move the answer by more than
that. On the same entry, `top 8` is -29% drawdown and `top 12` is -26%; the equity-curve window at
100 days instead of 50 is -27%; the band at 3% instead of 2% is -27%. A setting that crosses the
line by less than the parameter sensitivity is a curve fit, not a strategy.

What the number rests on, before anyone trades it:

- **Survivorship.** Delisted names are absent from the panel entirely, and a breakout system holds
  exactly the names that later blow up. This inflates the return by an amount the data cannot
  measure. Curing it needs NSE bhavcopy (see `AGENTS.md`).
- **Capacity.** With the floor at ₹5 crore a day instead of ₹1 crore the same settings return
  +16.8% at -27.8%. The edge lives in names trading ₹1–5 crore a day, which caps the book at a few
  crore before impact eats it.
- **Cash yield.** 6% on the ~45% of the book held in cash adds 2 points of CAGR; at 0% the same
  configuration is +25.9% at -25.3%. That is a liquid-fund assumption, not a strategy property.
- **Window.** From 2010 the same configuration is +25.4% at -23.8%; from 2015, +22.5% at -23.5%.
  The 2007 and 2009 years carry a lot of the headline.
- **Circuits.** Small-cap breakouts are often locked limit-up on the day after the signal; the
  simulator fills at the open regardless.

The strategy's drawdowns are not the crashes. 2008 cost it -22% because the regime filter and
the ATR trails got it out; the deeper episodes are the grinds — 2014-16, 2018-20, 2022-23 — where
the regime flips on and off and breakouts fail one after another. That is the cost of trend
following and no filter tested here removes it; the equity-curve cut is the one that halves it.

### Second loop: 35% CAGR under a 25% drawdown

The target was then raised to **CAGR ≥ 35% with max drawdown ≤ 25%**, a Calmar of 1.40. Rather
than re-tune the same knobs, this pass added mechanisms that change the return or drawdown
structure, each measured against the +28.0% / -23.8% configuration above:

| Change | CAGR | Max DD | Calmar |
| --- | --- | --- | --- |
| (reference) | +28.0% | -23.8% | 1.18 |
| Volume surge on the breakout day (1.5x 50-day mean) | +25.4% | -29.6% | 0.86 |
| Tight base (20-day range ≤ 30% of price) | +26.0% | -30.2% | 0.86 |
| Close within 5% of the 52-week high | +26.6% | -23.1% | 1.15 |
| Rank by relative strength vs the universe | +25.0% | -29.5% | 0.85 |
| Weekly rather than daily stop evaluation | +23.1% | -22.4% | 1.03 |
| Portfolio stop: cut at 15% below own peak | +27.2% | -25.1% | 1.08 |
| Short the large-cap index against the book while cut (0.5x) | +27.1% | -28.7% | 0.95 |
| State-dependent leverage: 1.2x while own equity trends up, 0.5x otherwise | +32.6% | -28.6% | 1.14 |
| Same at 1.3x | +34.8% | -30.9% | 1.13 |
| Same at 1.5x | +39.3% | -35.6% | 1.10 |

None of the entry-quality filters helped: each removed good trades faster than bad ones. The
portfolio stop and the index hedge both cut return more than drawdown, because the strategy's
losing stretches are not reliably falling markets. Leverage of any shape moves the two numbers
together and leaves the ratio where it was.

A seeded random search over the whole breakout space (entry length, slots, trail, regime,
rank, weighting, equity-curve settings, leverage, exits; 120 draws) puts the ceiling in
numbers: best Calmar 1.22, 95th percentile 1.00, median 0.71, none at 1.40, none meeting the
target. The best draw (+27.4% at -22.4%) is a different point on the same plateau, with no
equity-curve overlay at all, which is the useful part: the ~1.2 is a property of trend following
in this market on this data, not of one tuned setting.

On rolling windows of the reference configuration, no 10-year window meets 35% / -25%; two of
sixteen 5-year windows do (those starting 2019 and 2020), four with 1.3x leverage. The target is
reachable by choosing the window, which is not a strategy.

What would change the answer is a second, uncorrelated return source rather than a better
filter: the momentum and breakout sleeves here are 0.6 correlated. This repository holds only
NSE cash equities, so that source (index futures, bonds, gold, a genuine short book) cannot be
tested from it.

### Third loop: the drawdown is a hard gate, no leverage, no derivatives

The constraints were then fixed as: **max drawdown strictly under 25%**, gross exposure never
above 100%, no futures or options, and the objective is the highest CAGR inside that. Two things
follow from a gate being hard. First, the number has to survive the assumptions it was measured
under: the +28.0% / -23.8% configuration above is -28.1% at 50 bps of cost instead of 30, -25.3%
with cash at 0% instead of 6%, and -29.5% with both, so it is not inside the gate in any sense
that matters. Second, the right tool is no longer a filter but an exposure rule that reads the
drawdown itself: `--dd-budget` keeps exposure at 100% until the book's own drawdown passes
`--dd-start`, shrinks it linearly to `--dd-floor` as the drawdown approaches the budget, and
restores it as the drawdown heals. It never borrows; it only de-risks.

A random search of 150 configurations was then scored under the **worst** assumptions (50 bps,
0% cash) rather than the base ones, every candidate inside the gate was re-run under all four
assumption sets, and the leader was checked across its parameter neighbourhood. The result:

```bash
python scripts/strategy_lab.py --strategy breakout --entry-n 150 --top 12 --atr-mult 3 --exit-weekly \
    --rank mom2 --regime sma100 --stock-sma 100 --eq-curve 50 --eq-band 0.02 --eq-scale 0.3 \
    --dd-budget 0.22 --dd-start 0.12 --dd-floor 0.25 --cash-rate 0.06
```

150-day breakouts, twelve names, a 3 ATR trail evaluated weekly, candidates ranked by a blend of
12-1 and 6-1 momentum, a 100-day index regime and a 100-day own-trend filter, exposure cut to
30% while the book's equity is under its 50-day average and scaled down between a 12% and a
22% drawdown.

| Assumptions | CAGR | Max DD |
| --- | --- | --- |
| 30 bps, cash at 6% (base) | **+27.4%** | **-21.5%** |
| 50 bps, cash at 6% | +23.6% | -21.6% |
| 30 bps, cash at 0% | +25.4% | -21.8% |
| 50 bps, cash at 0% (worst) | +22.0% | -22.0% |
| Base, from 2010 | +25.5% | -21.5% |
| Base, from 2015 | +23.6% | -21.5% |
| Base, 500-name universe | +24.9% | -22.0% |
| Worst, from 2010 | +20.3% | -22.0% |

The drawdown sits between -21.5% and -22.0% under every assumption, window and universe tested,
which is what the budget rule is for: the gate holds with three points of margin instead of one.
Of seventeen single-parameter neighbours (slots, entry length, trail, rank, filters, overlay
settings), fifteen stay inside the gate under both base and worst assumptions; the two that do
not miss it by 0.1 and 1.3 points, and only under the worst case. CAGR across the neighbourhood
runs from +17.5% to +28.6%, so the return is the soft number and the drawdown the hard one,
which is the right way round for this brief.

The cost of the gate is return: the best configuration inside it under base assumptions alone was
+28.0%, and inside it under every assumption +27.4%, against +29.8% for the same entries with no
drawdown control at all. The 35% asked for is not available inside the gate on this data by
any construction tested (three grid sweeps, sixteen focused batches, 470 random draws).

Read the CAGR with its concentration in mind. 2021 returned +205% for this configuration; with
the best calendar year set to zero the CAGR is +20.3%. That is the shape of trend following,
and the reason a 19-year number should not be read as a promise for the next five.

### Fourth loop: 35% inside the gate, without leverage

The goal was restated as **35% CAGR with max drawdown under 25%, no leverage, no derivatives**.
Three more mechanisms were built and tested; one of them worked.

**Stop orders (did not help).** `--strategy breakout_orders` is a second simulator that trades
the same signals with resting orders: a buy-stop at the breakout level filled intraday, and a
sell-stop at the trail filled intraday at the level (or at the open on a gap through), with
slippage. Against the reference book, buy-stop entries cost 7 points of CAGR (false breakouts
that pierce the level and close back below it) and intraday stop exits cost 2 more (lows that
touch the trail and recover). Pyramiding into winners (`--pyramid-units`) cost 4 points. On
daily data, entering after a confirmed close and exiting at the next open is the better model.

**Strong close (helped).** `--clv 1.0` requires the breakout bar to close at its high. It cuts
the trade count by half, drops the invested fraction from 62% to 42%, and lifts the same book
from +29.8% / -27.3% to +27.9% / -22.5% — less return, far less drawdown, so the freed drawdown
budget can be spent on concentration: eight slots instead of ten and a 75-day high instead of
100 take it to +32.0% / -23.3%, and a 100-day own-trend filter instead of 200 to +34.2%. Two
universe settings — a ₹5 price floor instead of ₹10, six months of history instead of a year,
both still behind the ₹1 crore/day turnover floor — add the rest.

```bash
# F1: the target on base assumptions
python scripts/strategy_lab.py --strategy breakout --entry-n 75 --top 8 --atr-mult 4 --clv 1.0 \
    --rank mom2 --regime sma100 --stock-sma 100 --daily-exit regime --min-price 5 --min-bars 126 \
    --cash-rate 0.06
# F2: the same with a drawdown budget, inside the gate under every assumption
python scripts/strategy_lab.py ...same... --dd-budget 0.25 --dd-start 0.15 --dd-floor 0.5
```

| | F1 | F2 (F1 + drawdown budget) |
| --- | --- | --- |
| 30 bps, cash at 6% (base) | **+35.6% / -23.3%** | **+33.3% / -22.7%** |
| 50 bps, cash at 6% | +34.4% / -23.4% | +31.4% / -23.4% |
| 30 bps, cash at 0% | +31.0% / -25.4% | +27.8% / -24.2% |
| 50 bps, cash at 0% | +29.8% / -26.3% | +26.1% / -24.8% |
| Base, from 2010 | +31.6% / -23.3% | +29.1% / -22.7% |
| Base, from 2015 | +35.3% / -23.3% | +32.3% / -21.8% |
| Base, 500-name universe | +27.2% / -36.8% | +24.1% / -28.5% |
| Invested (mean gross) | 42% | 41% |
| Annual one-way turnover | 2.3x | 2.6x |
| CAGR with the best year set to zero | +28.8% | +26.6% |

Gross exposure never exceeds 100% in either run. Costs matter little here because the book turns
over only 2.3 times a year; the cash yield matters a lot, because 58% of the book is in cash on
an average day and 6% on that is 3.5 points of CAGR. That is why F1 leaves the gate with cash at
0%: the yield cushions the equity path through the 2015-16 and 2018-20 grinds. F2 spends 2.3
points of CAGR to hold the drawdown under 25% whichever way those assumptions fall.

**Read before trading it.** This is the maximum of a search that has now run about 750
configurations on one 19.6-year history, so the headline is optimistic by an amount that cannot
be measured from the same data. The specific concerns, in order:

1. **Universe dependence.** On the 500 most liquid names the same rules lose 8 points of CAGR and
   the drawdown is -36.8%. The edge is in names ranked 500 to 1,000 by turnover — ₹1-5 crore a
   day — and it does not survive without them. Capacity is a few crore.
2. **Regime dependence.** The 100-day index regime is load-bearing: at 200 days the drawdown is
   -40%, at 125 days -30%. A rule that sensitive to its one parameter is a risk in itself.
3. **Concentration.** 2007 returned +172%; without it the CAGR is +28.8%. Eight names at a time is
   a concentrated book, and the path is the path of a handful of trades a year.
4. **Survivorship and circuits.** Delisted names are absent from the panel, and a small-cap
   breakout that closes at its high is often locked limit-up the next morning. At the time of
   this table the simulator refused only rangeless *signal* bars; the independent review below
   found it still filled entries and exits on locked bars, and the corrected numbers follow.

The honest reading of the fourth loop: the 35% is reachable on this data inside the gate at 30 bps
with idle cash in a liquid fund, and +33% is reachable with the gate held under every assumption
tested. Both rest on the strong-close filter, the small-cap tier and a single regime length, and
the next five years will pay something closer to the ex-best-year figures than the headline.

### Independent review, corrected accounting, and the Nifty 50 scorecard

A second model instance, given only the repository and the search logs and told to be
adversarial, reviewed F1 and F2. It reproduced F1 exactly and verified the indicator alignment
(`hh` excludes the signal bar), the lagged regime index, the two-leg fill arithmetic, cost on
both legs, the cash-yield compounding and the bad-tick handling against hand calculations. It
then found two accounting errors that both lean the same way, and one undercount:

- **Entries filled on upper-circuit bars.** The signal-bar guard did not cover the fill bar:
  15 of F1's 376 entries were bought at an open with no range, which no order could have got.
- **Exits filled on lower-circuit locks.** 24 of 376 exits filled on a rangeless bar, 21 of
  them -5% lower-circuit locks; the first bar that actually traded averaged 7.3% lower.
- **The search was ~1,400 breakout evaluations**, not the ~750 stated above.

Both fills are now fixed in `simulate()`: a buy is dropped on a locked bar (the strategy
re-places it if the signal persists) and a sell is carried to the first bar with range. The
breakout state also now starts at the test window, so no ghost positions from the warm-up
occupy slots on day one. On corrected accounting:

| | F1 | F2 |
| --- | --- | --- |
| 30 bps, cash at 6% (base) | **+33.1% / -24.6%** | **+30.9% / -24.0%** |
| 50 bps, cash at 6% | +31.9% / -25.3% | +28.9% / -24.5% |
| 30 bps, cash at 0% | +28.5% / -28.1% | +25.3% / -25.6% |
| 50 bps, cash at 0% (worst) | +27.4% / -28.9% | +23.9% / -26.0% |
| CAGR ex-best year / ex-top-2 years | +27.1% / +22.0% | +25.0% / +20.1% |

So on honest fills the 35% is not reached, and the 25% gate holds only on base assumptions:
the corrections cost 2.5 points of CAGR and 1.3 of drawdown, and F2 no longer holds the gate
under stress. The earlier fourth-loop table stands as the record of what was claimed before
the review.

**Plateau or overfit — the review's verdict, in its own numbers.** Mixed, leaning overfit on
the level though not on the mechanism. The edge is real: trade-level t-statistic 6.2 on 376
trades, deflated Sharpe ≈ 1.0 after 1,400 trials, every one-notch neighbour beats the
benchmark. The level is selected: the local hill-climb batches (184 rows) have CAGR mean 29.2
with SD 3.4, and the expected maximum of 184 such draws is about 38, so 35.6 is exactly what
the best of those draws looks like around a ~29% true mean. F1 is Calmar rank 1 of 16 in its
neighbourhood. CAGR is a plateau (neighbours 29-37%); the drawdown gate is not (4 of 15
neighbours breach -25%). Tuning against a truly untuned family member is worth +13 points of
CAGR, 4-6 times the neighbourhood spread, most of it from two whole-window choices: the
strong-close bar and the 100-day regime. Selecting the best neighbour on 2007-16 and running
it on 2017-26 lands at rank 9 of 19, the median. The reviewer's forward expectation, after the
fill corrections, the cash assumption and a survivorship haircut it could not measure: **CAGR
15-22% with drawdowns of -30% to -40%**, delivered as a few +50-100% years amid a third of years
flat or negative, on about 20 trades a year of which two decide the year. Its list of what it
would demand before trading — a point-in-time universe from bhavcopy, a participation-based
impact model at a stated book size, a historical cash-rate series, a true walk-forward, and a
pass/fail gate matrix over neighbourhood × cost × cash × universe — is the next piece of work.

**Against the Nifty 50.** The index history (Yahoo `^NSEI`, price only, from 2007-09-17) gives
19 measurable calendar years; 2007 is not covered, and the strategy's +149% that year beat any
index figure. On corrected accounting, over 2007-09 to 2026-08 the Nifty 50 returned 9.3% a
year (about 10.6% with dividends) with a -59.9% drawdown.

| Year | Nifty 50 | F1 | F2 |
| --- | --- | --- | --- |
| 2008 | -51.8% | -16.1% | -16.6% |
| 2009 | +75.8% | +57.6% | +55.1% |
| 2010 | +17.9% | +22.6% | +22.6% |
| 2011 | -24.6% | +2.3% | +2.3% |
| 2012 | +27.7% | -2.5% | -2.5% |
| 2013 | +6.8% | +23.0% | +23.0% |
| 2014 | +31.4% | +86.1% | +86.1% |
| 2015 | -4.1% | -2.4% | -5.0% |
| 2016 | +3.0% | +22.8% | +9.2% |
| 2017 | +28.6% | +65.4% | +55.2% |
| 2018 | +3.2% | -2.8% | -3.3% |
| 2019 | +12.0% | +14.0% | +8.8% |
| 2020 | +14.9% | +96.1% | +91.7% |
| 2021 | +24.1% | +86.8% | +86.6% |
| 2022 | +4.3% | +3.0% | +3.0% |
| 2023 | +20.0% | +120.9% | +118.8% |
| 2024 | +8.8% | +48.8% | +47.7% |
| 2025 | +10.5% | -0.2% | -0.2% |
| 2026 (to Aug) | -7.8% | +9.9% | +9.9% |

F1 beats the index in **14 of 19** years and loses in 2009, 2012, 2018, 2022 and 2025; F2 in
12 of 19. On rolling windows of the daily curves, F1 is ahead in 79% of 1-year windows, 99% of
3-year windows and 100% of 5-year windows. The losing years are the ones the regime filter
keeps the book in cash through a recovery (2009, 2012) or the ones where breakouts fail one
after another (2018, 2022, 2025).

### Fifth loop: 40% under a 30% drawdown

The goal was raised to **40% CAGR with max drawdown under 30%**, still unlevered, on the
corrected fills. The looser gate re-admits the concentrated books, so the search went there:
four to eight slots, 60-125-day highs, 4-6 ATR trails, 50-100-day own-trend filters, the
1,000- and 1,500-name universes, and the drawdown budget re-sized to the new gate (about 130
more configurations).

Concentration buys return at a fixed price in drawdown: each slot removed from eight adds
roughly two points of CAGR and three of drawdown. Four slots is the only way to a raw 40%
(+40.6% at -39.3% on 90-day highs and a 5 ATR trail), and no budget brings that inside the
gate at 40%: the best budgeted four-slot book is +38.5% at -33.0%. The frontier inside the
gate is a **five-slot book at +37.1% / -29.1%** (90-day high, 5 ATR trail, 75-day own trend,
budget cutting exposure between a 15% and a 30% drawdown):

```bash
python scripts/strategy_lab.py --strategy breakout --entry-n 90 --top 5 --atr-mult 5 --clv 1.0 \
    --rank mom2 --regime sma100 --stock-sma 75 --daily-exit regime --min-price 5 --min-bars 126 \
    --dd-budget 0.30 --dd-start 0.15 --dd-floor 0.5 --cash-rate 0.06
```

| Assumptions / window | CAGR | Max DD |
| --- | --- | --- |
| 30 bps, cash at 6% (base) | **+37.1%** | **-29.1%** |
| 50 bps, cash at 6% | +35.6% | -29.6% |
| 30 bps, cash at 0% | +32.5% | -30.0% |
| 50 bps, cash at 0% | +31.0% | -30.4% |
| Base, from 2010 / from 2015 / to 2016 | +33.0% / +37.3% / +26.4% | -29.1% / -31.3% / -29.1% |
| Base, 500-name universe | +17.4% | -31.5% |
| CAGR ex-best year / ex-top-2 years | +29.8% | +22.9% |

It beats the Nifty 50 in 13 of 19 years. It is also the most selected point in this
repository: one-notch neighbours run from +28.3% to +38.1% (a 75- or 125-day high, a 4 ATR
trail or a 50-day own trend each cost 5 to 9 points), five of ten neighbours breach 30%, every
stressed assumption breaches it by a fraction, and on the 500 most liquid names it returns
half as much. 2007 (+191%) and 2020 (+194%) are a third of its compounding.

So at that stage 40% inside a 30% drawdown looked unavailable without leverage: the frontier
on corrected fills ran from about +33% at -25% (eight slots) to +37% at -29% (five) to +40% at
-39% (four). The sixth loop below moved it with one more exit rule.

### Sixth loop: 40% under a 25% drawdown

The goal was raised again, to **40% CAGR under a 25% drawdown**, still unlevered and on
corrected fills: a return-to-drawdown ratio of 1.6 against a frontier that had never passed
1.3. Five mechanisms aimed at the years the book loses were added and tested on both the
eight-slot and five-slot books. Four hurt: late entries into breakouts that happened while
the regime was off (the 2009 and 2012 recoveries) cost 4-13 points; keeping winners with a
large cushion through a regime exit cost 1-4; a rising-turnover filter cost 5-15; and every
variant of those combined. The fifth helped, and it is the only exit rule that has: a
**channel exit**, selling at the next open when the close falls below the lowest low of the
last N sessions, alongside the ATR trail.

On the five-slot book a 40-day channel took the drawdown from -29% to -26% for one point of
CAGR. On the concentrated books it moved the whole frontier: four slots with a 40-day channel
and no budget returns **+41.4% at -28.6%**, which is the previous loop's 40%/30% target met
outright, and the ratio across the four- and five-slot books rose from about 1.3 to 1.5. Under
the 25% gate the best point is four slots, a 25-day channel and a drawdown budget cutting
exposure between an 18% and a 30% drawdown:

```bash
python scripts/strategy_lab.py --strategy breakout --entry-n 90 --top 4 --atr-mult 5 --exit-n 25 \
    --clv 1.0 --rank mom2 --regime sma100 --stock-sma 75 --daily-exit regime \
    --min-price 5 --min-bars 126 --dd-budget 0.30 --dd-start 0.18 --dd-floor 0.5 --cash-rate 0.06
```

| Assumptions / window | CAGR | Max DD |
| --- | --- | --- |
| 30 bps, cash at 6% (base) | **+38.9%** | **-24.8%** |
| 50 bps, cash at 6% | +37.0% | -25.1% |
| 30 bps, cash at 0% | +34.6% | -26.2% |
| 50 bps, cash at 0% | +32.6% | -26.4% |
| Base, from 2010 | +34.5% | -24.8% |
| Base, from 2015 | +36.9% | **-33.7%** |
| Base, 500-name universe | +20.8% | -31.5% |
| CAGR ex-best year / ex-top-2 years | +30.7% | +23.0% |

It beats the Nifty 50 in 16 of 19 years. It does not reach 40%: the fine grid around it (120
configurations of channel length and budget) tops out at +38.9% inside the gate, and the one
neighbour that crosses 40% (+40.3%) does so at -25.7%. That is the plateau under this gate:
38-39% on this path.

**On this path** is the operative phrase, and the 2015 row shows why. Started in January 2015
instead of 2007, the same rules lose -33.7% in 2015-16 (-41.8% without the budget) where the
full-window run loses -20%. The full-window book entered 2015 holding four 2014 winners with a
cushion and half in cash; the 2015-start book began flat, bought the breakouts of early 2015,
and those failed. A four-name book's drawdown in any given year is decided by which four names
it happens to hold going in, so its maximum drawdown is a property of one path, not of the
rules. The one-notch neighbourhood says the same: sixteen neighbours span +22% to +40% CAGR
and seven of them breach the gate (a 4 ATR trail is -34%, a 20-day channel -32%, three slots
-28%, five slots -29%). Concentration bought the return; it also removed the averaging that
made the eight-slot book's drawdown mean something.

What survives the loop as a finding: the channel exit is worth about 0.15 of Calmar across the
concentrated books and belongs in the family. What does not: the claim that any four- or
five-slot configuration holds a 25% drawdown with margin. The forward expectation for this
book, by the review's reasoning applied to a smaller trade count, is a CAGR in the high twenties
with drawdowns that will exceed 30% on some path.

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

## Data caveats

Worth reading before trusting a backtest:

1. **Survivorship bias.** The universe is NSE's *current* main-board listing. Companies delisted
   before the snapshot are absent entirely, which flatters long-only backtests.
2. **Uneven history.** Median symbol has ~2,400 bars, not 6,600. See the percentile table above.
3. **Adjustments.** `open/high/low/close` are split-adjusted as served by Yahoo; `adj_close` is
   additionally dividend-adjusted. Use `adj_close` for return series, raw `close` for price levels.
4. **Partial last bar.** If a snapshot is taken while the NSE session is open, the newest bar is
   incomplete. `last_bar_possibly_partial` in `_manifest.json` flags it — filter that date out
   before backtesting. It is set in the current snapshot (2026-08-27).
5. **Upstream gaps.** Yahoo occasionally drops a session for individual symbols — 2026-08-26 is
   missing for a large share of the universe. `scripts/validate_data.py` reports affected dates.
6. **Bad ticks.** 1,852 bars of 7.47M (0.025%, across 290 symbols) violate OHLC ordering upstream,
   mostly illiquid names on zero volume. Documented rather than silently patched.
7. **Zero-volume bars.** 4.0% of bars (300,926) have zero volume — thin names with no trades that session.
   Screen them out for anything execution-sensitive.
8. **Symbol availability.** In this snapshot every NSE main-board symbol resolved on Yahoo
   (`symbols_unavailable_on_yahoo` is empty). The downloader records a symbol as absent only when
   Yahoo explicitly says so, never on a transient failure — an earlier run mislabelled a whole
   failed batch of large caps as "no history", and that class of bug now fails loudly instead.

Data source: Yahoo Finance via `yfinance`; symbol lists from NSE's public archives. For personal
research use — check the respective terms before redistributing.

## Agent instructions

See [AGENTS.md](AGENTS.md).
