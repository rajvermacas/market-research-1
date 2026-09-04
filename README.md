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
| `scripts/supertrend_rsi_w.py` | RSI double-bottom ("W") + SuperTrend confluence, ablated against the naive oversold buy and against random entries |
| `scripts/rsi2_mean_reversion.py` | Connors' RSI(2), R3 and IBS on the real Nifty index series and on constituents, against buy-and-hold and random entries |
| `scripts/opening_range_breakout.py` | Opening range breakout on the hourly panel, both directions, against random same-day entries |
| `scripts/turn_of_month.py` | The turn-of-the-month (Ultimo) calendar effect on the real Nifty index series, with a full window sweep |
| `docs/strategy-ledger.md` | Every published strategy tested here, with its verdict and the method they all follow |
| `scripts/bollinger_rsi_ablation.py` | RSI oversold, Bollinger band-touch, squeeze breakout and divergence, measured separately and combined |

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

## RSI "W" + SuperTrend confluence

`scripts/supertrend_rsi_w.py` tests a widely taught intraday setup, and — more usefully — the
claim it rests on. The recipe: wait for RSI to fall into the oversold zone, let it carve a **"W"**
(a first trough at the 30 line, a bounce, then a second trough at or above the first), check that
price made its own higher low, check that SuperTrend is pointing up, and enter when all of it
agrees at once. It is explicitly sold *against* the textbook oversold buy — "RSI under 30, buy" —
which the same lesson calls dangerous because it buys into falling knives.

Both halves of that are testable, so this runs an ablation rather than a backtest. Five entry
rules trade the same bars, the same universe and the same exits:

| Arm | Entry |
| --- | --- |
| `naive` | RSI crosses back up through 30 — the textbook oversold buy, and the charitable version of it: it at least waits for the turn |
| `st_flip` | SuperTrend flips up. Trend alone, no RSI |
| `w` | the RSI W completes and turns up. Oscillator alone, no trend filter |
| `w_price` | the W, plus price confirming with its own higher low |
| `full` | all of it, including SuperTrend up — the setup as drawn |

Two controls, because a return without one measures the market rather than the setup: an
equal-weight buy-and-hold of the universe, and **random entries** drawn from the same bars and
walked to an exit by identical code. The random control is deliberately oversampled to 50,000
draws — matched to an arm's trade count its own standard error is as wide as the arm's and it
stops being a yardstick.

```bash
python scripts/supertrend_rsi_w.py                          # 1:2 target, all five arms
python scripts/supertrend_rsi_w.py --exit trail             # ride the SuperTrend line
python scripts/supertrend_rsi_w.py --exit horizon --horizon 24
python scripts/supertrend_rsi_w.py --arms full --charts 8   # look at what it matched
```

### Three exits, because the answer depends on which one you use

`rr` stops at the entry candle's low and targets a multiple of that risk. `trail` rides the
SuperTrend line and leaves on the flip down — the strategy's own exit, since the sell conditions
in the lesson are the mirror of the buy ones. `horizon` holds a fixed number of bars with no stop
and no target, and it is the arbiter.

The first two both stop at a price derived from the entry bar, and **the arms do not agree about
what that price is.** An arm entering in a SuperTrend uptrend stops at the line, typically far
below; an arm with no trend filter enters mid-downtrend and stops just under its own candle. That
difference alone produced a median hold of 23 bars against 4. Any gap in mean trade between them
is then partly a gap in how much room the trade was given, not in what the entry predicted.

### What it found

Traded on the adjusted Kite 60-minute Nifty 500 panel, 2015-02-02 to 2026-08-28 — 19,993 bars,
11.57 years — at 10 bps one-way and 10 portfolio slots. Equal-weight buy-and-hold of the 307
symbols trading at the window start returns **+20.80% CAGR at -50.03% max drawdown**.

Under the trailing SuperTrend stop the ablation looks like a clean result. `sigma` is the gap
from the random control in combined standard errors:

| Arm | Signals | Win % | Mean trade | sigma vs random | Median hold | CAGR | Deployed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `naive` | 119,999 | 19.7 | -0.065% | **-3.3** | 5 | -21.88% | 97.5% |
| `st_flip` | 101,992 | 36.1 | +0.145% | **+3.7** | 24 | -16.59% | 97.1% |
| `w` | 45,900 | 19.4 | +0.005% | -0.7 | 4 | -16.38% | 85.8% |
| `w_price` | 36,216 | 18.7 | -0.042% | **-2.1** | 4 | -21.47% | 82.3% |
| `full` | 9,300 | 35.0 | +0.143% | +1.8 | 23 | -6.05% | 67.6% |
| `random` | 50,000 | 21.2 | +0.028% | — | 8 | -13.74% | 95.6% |

Read on its own that says the lesson is half right: the naive oversold buy really is worse than
random, SuperTrend really does carry an edge — and the RSI W adds nothing, since `full` earns the
same mean trade as `st_flip` from a ninth as many signals. The same ordering holds at every
reward:risk target from 1:1 to 1:5, which makes it look robust.

It is not. Hold the exit genuinely constant and it vanishes:

| Arm | 6 bars | sigma | 24 bars | sigma | 48 bars | sigma |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `naive` | -0.120% | +0.1 | +0.124% | -0.2 | +0.430% | -1.6 |
| `st_flip` | -0.129% | -0.6 | +0.134% | +0.2 | +0.397% | **-2.3** |
| `w` | -0.048% | **+4.1** | +0.192% | +2.0 | +0.428% | -1.4 |
| `w_price` | -0.096% | +1.4 | +0.094% | -1.1 | +0.370% | **-2.4** |
| `full` | -0.158% | -1.2 | +0.135% | +0.1 | +0.464% | -0.5 |
| `random` | -0.121% | — | +0.129% | — | +0.504% | — |

**The setup as drawn (`full`) is indistinguishable from a randomly chosen bar at every horizon
tested** — +0.1, -1.2 and -0.5 sigma. So is SuperTrend on its own, except at 48 bars where it is
significantly *worse* than random. The naive oversold buy is not specially dangerous as an entry
either: it is dangerous in combination with a tight stop, which is a different claim. Buying into
a decline puts the stop exactly where the volatility is, and that — not the entry — is what the
trailing-stop table was measuring.

The one detectable effect anywhere is the RSI W **alone**: +4.1 sigma at a 6-bar horizon. It is
worth almost nothing. Both figures are negative (-0.048% against the control's -0.121%), so it
is a matter of losing less over six hourly bars; the gap of 0.073% is a third of the 0.20%
round-trip cost; it has decayed to +2.0 sigma by 24 bars and reversed by 48. It is a short-horizon
bounce after a decline, which is what an oversold oscillator is supposed to find. And every step
the lesson adds on top of it makes it worse, not better — price confirmation takes it to +1.4
sigma, the SuperTrend filter to -1.2.

Nothing here is tradeable in any case. Every arm loses heavily against the +20.80% benchmark
under any portfolio simulation: hourly churn at 0.20% round trip bleeds out regardless of what
the entry rule is, and the arms with lower drawdowns have them because they sit in cash, which is
what the `deployed` column is for.

Two caveats on top of the repository's usual survivorship warning. The setup was drawn on an
intraday index chart and is tested here on NSE single-stock hourly bars, because that is the data
this repository has — the mechanism is timeframe-agnostic as taught, but the translation is not
free. And `--charts` was used before any of the above was believed: the matched signals really
are Ws, with the deep first trough, the higher second trough, the price double bottom and the
SuperTrend flip all where they should be. The setup is real and it was found correctly. It just
does not predict anything.

## RSI(2) mean reversion — the Connors rule on Nifty

`scripts/rsi2_mean_reversion.py` tests the strategy QuantifiedStrategies publishes as a
proven 56%-a-year mean-reversion edge. Unlike a video setup, this one states its rules, so
it is tested exactly as written rather than inferred:

| | |
| --- | --- |
| Entry | RSI(2) closes below 10 — bought at that close |
| Exit | the first close above the **previous** bar's high — sold at that close |
| Filter | optionally, only enter while the close is above its 200-day SMA |

Published on QQQ it returns 12.75% CAGR against 6.4% buy-and-hold, 75% winners, profit
factor 3.15, from 196 trades and 14% time in the market.

Two translations, because they answer different questions. `--mode index` trades the real
cap-weighted Nifty series pulled from Yahoo (`^NSEI` 2007-, `^CNX100` and `^CRSLDX`
2005-), which is the faithful analogue of the QQQ test and the only version here free of
this repository's survivorship bias — an index series is not a basket of today's
survivors. `--mode stocks` runs the same rule on individual constituents out of the
committed daily panel, portfolio-simulated with a slot cap.

Both are measured against buy-and-hold **and** against random entries using the identical
exit. That control is not optional here: "sell on the first close above yesterday's high"
is itself a mean-reversion bet that closes most trades within days whatever opened them,
and without the control its work is credited to RSI(2).

```bash
python scripts/rsi2_mean_reversion.py --mode index --universe nifty50 --trend-filter
python scripts/rsi2_mean_reversion.py --mode index --cost-sweep
python scripts/rsi2_mean_reversion.py --mode stocks --universe nifty500 --start 2015-01-01
```

### On the index, there is no edge

Nifty 50, 2007-09 to 2026-09 (18.96 years), RSI(2) < 10 with the 200-day filter. Buy-and-hold
returns **+9.25% CAGR at -59.86%**:

| Cost (one-way) | Mean trade | Profit factor | CAGR | Max DD | CAGR / exposure |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 bps | +0.154% | 1.22 | +0.90% | -31.63% | +5.5% |
| 0 bps — random | +0.141% | 1.25 | +0.86% | -22.74% | +6.7% |
| 10 bps | -0.047% | 0.94 | -0.70% | -35.16% | -4.3% |
| 20 bps | -0.247% | 0.70 | -2.29% | -45.18% | -14.0% |

152 trades, 16.4% of the time in the market. **Even at zero cost the rule is worth +0.90%
a year against random entries' +0.86%**, and against +9.25% for simply holding. By 10 bps
one-way — 0.20% round trip, which is optimistic for a retail participant — it is negative.
Nifty 100 and Nifty 500 are the same or worse; on Nifty 100 the random control beats
RSI(2) at every cost level tested.

The event study says the same thing without the exit confusing matters. Forward returns
after the signal against every other day the filter would have allowed:

| Days held | After RSI(2)<10 | Baseline | Edge | t |
| ---: | ---: | ---: | ---: | ---: |
| 1 | +0.045% | +0.042% | +0.003% | 0.05 |
| 3 | +0.221% | +0.126% | +0.094% | 0.87 |
| 5 | +0.410% | +0.212% | +0.198% | 1.50 |
| 10 | +0.762% | +0.423% | +0.339% | 1.75 |

Right sign, right rough magnitude, and not significant at any horizon over 19 years.

**Where the 56% comes from.** The strategy is in the market 14-16% of the time, so
dividing its return by its exposure multiplies it by six or seven. That column is reported
above as `CAGR / exposure` — on Nifty it is +5.5% at zero cost and negative at any real
one. It is arithmetic, not a return anyone receives: the capital has to sit somewhere for
the other 84% of the time, and if it sits in the index it is just holding the index.

### On single stocks, the effect is real but smaller than the spread

The same rule on Nifty 500 constituents, 2015 onward (the period the panel is solid for):

| Days held | After signal | Baseline | Edge (winsorised) | t pooled | t by date |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | +0.145% | +0.108% | +0.051% | 3.23 | 5.04 |
| 3 | +0.446% | +0.322% | +0.151% | 6.68 | 6.42 |
| 5 | +0.653% | +0.539% | +0.155% | 4.80 | 4.29 |
| 10 | +1.211% | +1.085% | +0.176% | 3.63 | 2.96 |

Two t-statistics because only the second is worth anything. RSI(2) < 10 fires on hundreds
of names at once in a market-wide selloff, so pooling symbol-days counts the same market
move over and over; the clustered column collapses each date to one observation. Here it
survives — this is a **real** short-horizon reversal effect, worth about +0.15% over three
to five days. On Nifty 50 alone it is not there at all (clustered t of 0.12 to 0.69),
which fits: short-term reversal is a liquidity effect and the largest names have it
arbitraged out.

It is still not a strategy. **The edge is +0.15% and the round trip is 0.20%** — more in a
mid-cap, where much of the measured reversal is bid-ask bounce you cannot capture. Traded
with 10 slots the rule returns **+9.67% CAGR at -41.97%** against **+19.96%** for
equal-weight buy-and-hold, and against **+12.32%** for random entries with the same exit.
The entry does beat random on mean trade by 5.8 sigma; it loses on CAGR anyway, because it
is in the market far less of the time.

### Larry Connors' R3, and IBS

`scripts/rsi2_mean_reversion.py --rules rsi2 r3 ibs` runs three entry rules through the
same machinery, so the marginal value of each extra condition is priced rather than
assumed.

| Rule | Entry |
| --- | --- |
| `rsi2` | RSI(2) < 10 — the plain Connors rule, above |
| `r3` | Connors' **R3**: RSI(2) must have fallen three days running, the first fall starting from a reading below 60, and today's reading under 10 |
| `ibs` | **Internal Bar Strength**, `(close - low) / (high - low)`, below 0.2 |

R3 differs from `rsi2` *only* in a path condition — the same destination reached in a
specified way — which makes the pair a clean measurement of what the path is worth. IBS is
carried as a family control: it is the strongest documented daily mean-reversion signal in
the literature, so if nothing in this family works on Nifty it should fail too.

Both of Connors' exits are offered (`--exit-rule up-close` for RSI(2), `rsi70` for R3)
plus `horizon`, which is the arbiter for the reason established above.

**On the index, R3 does not work.** Mean trade against its own random control, all three
Nifty indices, both exits, 10 bps:

| | Nifty 50 | Nifty 100 | Nifty 500 |
| --- | ---: | ---: | ---: |
| R3, exit on up-close | +0.143% *vs* +0.117% | +0.134% *vs* **+0.213%** | -0.372% *vs* **+0.092%** |
| R3, 5-bar horizon | +0.167% *vs* **+0.303%** | +0.451% *vs* **+0.704%** | +0.102% *vs* **+0.240%** |

**R3 loses to randomly chosen entries in five of the six cells.** Its CAGR across every
index and exit runs -1.69% to +1.73% against buy-and-hold's +9.25% to +11.84%. The one
encouraging number anywhere — a forward-return edge of +0.559% at five days on the Nifty
50, t = 3.17 — is a single cell out of the fifteen the event study prints, and the trades
behind it split +0.480% in the first half of the window against -0.124% in the second.

IBS fails harder: negative on every index under the Connors exit (-0.142%, -0.137%,
-0.177% mean trade) and behind its control in most cells.

**On constituents the story reverses, exactly as it did for `rsi2`.** Nifty 500 names,
2015 onward, forward returns clustered by calendar date:

| Rule | Edge at 3 days | t (by date) | Mean trade | sigma vs random | CAGR | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `r3` | +0.219% | 6.39 | +0.523% | **+5.92** | +10.55% | -44.10% |
| `rsi2` | +0.151% | 6.42 | +0.445% | **+5.80** | +9.67% | -41.97% |
| `ibs` | -0.031% | 1.97 | +0.274% | +3.29 | +11.27% | -34.40% |

R3's path condition is worth something after all — +0.219% against `rsi2`'s +0.151% at the
same horizon, from half as many signals. It is the first edge in this series to sit
*above* a 0.20% round trip rather than under it, which makes it the only candidate here
worth a second look.

It is still not a strategy as it stands. Against **+19.96%** equal-weight buy-and-hold,
R3 returns **+10.55%** — the edge per trade is real and the book still trails the market,
because the rule is in cash most of the time. And the constituent panel is today's index
membership walked backwards, so the figure is optimistic by an unmeasured amount while
the index test, which has no such bias, says there is nothing there. When those two
disagree the index is the one to believe about the market and the constituent test is the
one to believe about single stocks; they are different claims, and only the second is
positive.

## RSI + Bollinger components, ablated

`scripts/bollinger_rsi_ablation.py`. The source here is a five-minute video whose only
machine-readable content is its chapter list — "RSI Signals / Bollinger Bands / Breakout
Strategy / Divergence / Trading Strategies" — so **nothing in this section reproduces its
rules**, which are not recoverable. What is testable is the canonical reading of those four
components, which are standard individually, measured separately and together so each
one's contribution is visible whatever recipe combines them.

| Arm | Entry |
| --- | --- |
| `rsi_os` | RSI(14) crosses back up through 30 |
| `bb_lower` | close returns above the lower Bollinger Band (20, 2) after closing below it |
| `squeeze` | bandwidth in its own trailing bottom quintile, then a close above the upper band |
| `divergence` | price makes a lower low while RSI makes a higher low, both pivots confirmed |
| `combo` | `rsi_os` today with `bb_lower` and `divergence` inside the last 5 bars |

Nifty 500 daily, 2015-01 to 2026-08 (11.65 years, 457 symbols), 10 bps one-way, held
exactly 10 bars with no stop and no target. Equal-weight buy-and-hold returns **+19.48%
CAGR at -41.52%**:

| Arm | Signals | Mean trade | sigma vs random | CAGR | Max DD | Deployed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `squeeze` | 12,582 | +1.164% | **+4.97** | +23.92% | -38.47% | 81.4% |
| `divergence` | 12,367 | +0.984% | +2.73 | +10.52% | -55.99% | 83.4% |
| `combo` | 168 | +1.767% | +1.36 | +0.87% | -17.75% | 5.1% |
| `rsi_os` | 11,787 | +0.778% | +0.22 | +10.59% | -46.17% | 72.7% |
| `bb_lower` | 26,044 | +0.309% | **-6.84** | +14.61% | -45.44% | 85.7% |
| `random` | 50,000 | +0.757% | — | +14.53% | -49.82% | 91.3% |

Repeating it with a completely different exit — sell on the first close above the previous
high — keeps the ordering, which is what makes it worth reporting: `squeeze` +2.88 sigma,
`rsi_os` +0.66, `divergence` -0.15, `bb_lower` **-6.13**.

Three things survive both exits:

**The squeeze breakout is the only component that works.** +4.97 and +2.88 sigma, stable
across both halves of the window (+0.98% then +1.26% mean trade, against the control's
+0.40% and +1.01%), and the only arm to beat buy-and-hold on CAGR while running a smaller
drawdown. It is also the only component of the four that is not a mean-reversion idea.

**Buying the lower band is significantly worse than random** — -6.84 and -6.13 sigma, the
largest effect in the table and pointing the wrong way. The textbook "price is at the lower
band, it is oversold, buy" is a losing entry on Nifty equity, and it was worst in the first
half (-0.649% mean trade against the control's +0.395%).

**The oversold buy adds nothing** (+0.22 sigma), and the divergence is not robust — +2.73
sigma on one exit, -0.15 on the other. The full confluence fires 168 times in 11.65 years
across 457 names, roughly once a month for the whole market, which is too rare to be a
strategy whatever its mean.

Read alongside the RSI(2) result above, the two studies agree: on Indian equity the
mean-reversion entries — RSI(2) < 10, RSI(14) < 30, the lower Bollinger Band — range from
worthless to actively harmful, and the one thing in either study with a robust edge is a
volatility-contraction breakout, which is a momentum idea.

## Opening range breakout

`scripts/opening_range_breakout.py`. The source states both its rules and its conclusion,
which makes it unusually testable: buy when price breaks above the high of the session's
first *N* hours, sell at that day's close, never hold overnight; the flip buys the break
*below* the range low. Its finding on the S&P 500 was that the best average gain per trade
was **0.04%**, the win rate was low, the downside flip was worse, and opening range
breakouts "don't work very well anymore".

Traded on the adjusted Kite 60-minute Nifty 500 panel, 2015-02 to 2026-08 (2,867 sessions,
11.57 years). The hourly granularity is a real limit and is stated rather than hidden: the
range can only be drawn in whole hours, and a breakout is detected by a later bar's high
clearing the level rather than tick by tick. Fills are taken at the level, or at the bar's
open when it gapped through — the worse of the two.

### Gross of costs, the upside breakout is one of the strongest signals tested here

Against random entries drawn from the same day and held to the same close:

| Range | Trades | Win % | Mean trade | sigma vs random | Quiet days | Heavy days | h1 / h2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 hour | 511,627 | 45.4 | +0.0457% | +26.8 | -0.315% | +0.428% | +0.015 / +0.072 |
| 2 hours | 400,912 | 46.5 | +0.0867% | +36.5 | -0.235% | +0.408% | +0.071 / +0.100 |
| 3 hours | 325,020 | 47.0 | +0.1082% | +39.6 | -0.177% | +0.342% | +0.100 / +0.115 |
| 4 hours | 259,376 | 47.3 | **+0.1190%** | **+40.1** | -0.126% | +0.304% | +0.124 / +0.115 |

The edge rises monotonically with the length of the range, is stable across both halves of
the window, and the `quiet`/`heavy` columns say where it comes from: **the breakout pays on
days when many names break out together and bleeds on days when few do.** That is the
honest shape of a breakout — it is paid for participating in the few broad trend days and
charged for the rest.

**And it still does not survive costs.** At 10 bps one way the same arm averages -0.081%
and the book returns -34.55% CAGR. The source's conclusion holds on Nifty: the effect is
real, roughly three times the size they measured on the S&P, and still smaller than the
round trip needed to capture it.

The downside flip is worse than random at every range length — **-13.9 to -17.4 sigma** —
which also matches what they found.

### The trap in the drawdown column

Gross, the `down 4h` arm reports **+15.01% CAGR at -6.61% max drawdown**, a return/drawdown
of **2.27** — far the best ratio in this repository. It is not real, and the mechanism is
worth naming because any day-trading backtest can produce it.

A book that equal-weights each day's signals gives every session one vote no matter how
many opportunities it held. Its compounded curve is therefore a **day-weighted** mean,
while the average trade is a **trade-weighted** one. For `down 4h` those are +0.057% and
**-0.046%** respectively, and the split shows why:

| Day type | Days | Signals that day | Mean signal return |
| --- | ---: | ---: | ---: |
| Quiet | 1,442 | 82 | **+0.197%** |
| Normal | 1,147 | 161 | -0.018% |
| Heavy | 291 | 276 | **-0.343%** |

Buying breakdowns makes money on the 1,442 quiet days and loses it on the 291 days when
the whole market is breaking down — it works except when it matters. Equal-weighting by
day lets the quiet days outvote the heavy ones five to one, and a 2.27 return/drawdown
falls out. The trade-weighted mean, which weights each session by the opportunity it
actually offered, is negative. Both numbers are printed side by side for exactly this
reason.

## Turn of the month (the Ultimo effect)

`scripts/turn_of_month.py`. Buy at the close of the **fifth-last** trading day of the
month, sell at the close of the **third** trading day of the new month, sit in cash the
rest of the time — about a third invested. The source's claim is explicitly about risk
rather than return: on the S&P 500 since 1960, 7% CAGR against buy-and-hold's 7.5%, at a
27% drawdown against 56%.

This is the first strategy tested here whose signal is not a price. There is no indicator
to warm up, no lookahead to guard, and no parameter fitted to the data — the rule is a
calendar. Run on the real cap-weighted Nifty series from Yahoo, so it also carries no
survivorship bias: an index is not a basket of today's survivors.

### The effect is visible before any window is chosen

Average session return by position in the month, `^CRSLDX` (Nifty 500), 20.93 years —
against an all-session average of **+0.0538%**:

| | −1 | −2 | −3 | −4 | −5 | +1 | +2 | +3 | +4 | +5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Nifty 500 | **+0.281%** | +0.101% | +0.072% | +0.125% | −0.017% | **+0.278%** | **+0.202%** | +0.034% | −0.056% | +0.014% |
| Nifty 100 | **+0.240%** | +0.111% | +0.066% | +0.123% | −0.008% | **+0.235%** | **+0.174%** | +0.010% | −0.060% | +0.021% |
| Nifty 50 | **+0.208%** | +0.130% | +0.047% | +0.082% | −0.005% | **+0.210%** | +0.137% | +0.025% | −0.058% | +0.064% |

The last two sessions of the month and the first two of the next run four to five times
the average session, on all three indices independently, and the effect dies by +4. Nobody
picked a window to produce that.

### It reproduces the source's claim

10 bps one way — and note this is the first strategy tested here where costs barely matter,
because it trades twelve times a year rather than hundreds:

| Index | Run | CAGR | Max DD | **ret/DD** | In market | sigma vs random | h1 / h2 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Nifty 50 | turn-of-month | +7.01% | −35.35% | **0.20** | 34.2% | **+2.61** | +0.58 / +0.64 |
| | random windows | −2.99% | −69.05% | 0.04 | 34.2% | — | −0.63 / +0.20 |
| | buy-and-hold | +9.25% | −59.86% | 0.15 | 100% | — | — |
| Nifty 100 | turn-of-month | +8.85% | −35.60% | **0.25** | 34.0% | **+2.02** | +0.79 / +0.73 |
| | buy-and-hold | +11.55% | −61.51% | 0.19 | 100% | — | — |
| Nifty 500 | turn-of-month | +10.54% | −35.57% | **0.30** | 34.0% | **+2.22** | +0.94 / +0.84 |
| | random windows | +2.05% | −53.49% | 0.04 | 34.0% | — | +0.17 / +0.28 |
| | buy-and-hold | +11.84% | −64.26% | 0.18 | 100% | — | — |

It gives up one to two points of CAGR and takes **little more than half the drawdown**,
which is what the source claimed and what the previous five strategies all failed to do.
Against random windows of the same count and the same lengths — the control that matters,
since a part-time book has a small drawdown for free — it wins by 2.0 to 2.6 sigma, and
it is stable across both halves of every window.

### The window is not fitted

Every entry offset from −1 to −7 against every exit from +1 to +5, on the Nifty 500:

**All 35 windows have a positive mean trade.** Return per drawdown runs 0.05 to 0.44, and
**24 of 35 beat buy-and-hold's 0.18**. The published (−5,+3) scores 0.30 and is not the
best — the best is (−4,+2) at **0.44** (+8.79% CAGR, −19.78% drawdown, 24.4% invested),
with (−3,+2) at 0.39 and (−5,+2) at 0.37 alongside it. Sitting mid-plateau rather than on
a peak is what a real effect looks like; a fitted one is a spike with nothing around it.

### What is not settled

The honest reservations, in order of how much they should bother you:

* **The sample is ~250 monthly trades per index**, and 2.0–2.6 sigma is respectable, not
  overwhelming. The case rests on the consistency — three indices, 35 windows, both halves,
  and the raw day profile — rather than on any single test clearing a threshold.
* **The tight windows have decayed.** (−2,+2) fell from +0.902% in the first half to
  +0.236% in the second, (−3,+2) from +1.022% to +0.328%. The wider ones did not: (−5,+3)
  went +0.940% to +0.838%, (−5,+1) +0.651% to +0.654%. Something concentrated at the very
  turn looks arbitraged while a broader end-of-month drift persists.
* **It is a lower-return strategy in absolute terms.** The entire case is risk-adjusted,
  which is only useful to someone who can act on it — by levering it, or by holding
  something else with the two thirds of the time it sits in cash.
* The usual structural story — monthly salary flows, SIP inflows and fund rebalancing all
  landing at the turn — is plausible in India and would explain why it survives, but this
  test does not establish the mechanism, only the pattern.

This is the first entry in the ledger to reach a verdict of **yes**.

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
