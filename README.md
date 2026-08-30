# Backtest: the RSI(2) "Dip Buy" on ES and NQ

Independent replication and stress-test of the strategy posted by
[@MrMilkTrading](https://x.com/MrMilkTrading/status/2093923934823403813) on 2026-08-30.

## The rules under test

1. RSI(2) on daily closes
2. Buy the close when RSI(2) < 10 and price > 200 day SMA
3. Sell the close when RSI(2) > 70, or after 10 sessions, whichever comes first
4. Long only. ES and NQ, 1 contract each. No stop.

Originally from Larry Connors & Cesar Alvarez, *Short Term Trading Strategies That Work*.

## Headline: the claims replicate

Claims were made for 2009–Aug 2026, 1 ES + 1 NQ, "$4 RT + slippage baked in".

| Claim | Claimed | Replicated (raw series) | Replicated (roll-adjusted) |
|---|---|---|---|
| Win rate since 2022 | 83% | 82.1% | 83.1% |
| Profit factor since 2022 | 2.53 | 2.74 | 2.54 |
| 2026 YTD, 1+1 contracts | $76K | $77.7K | $77.9K |
| Green years | 14/18 | 14/18 | 14/18 |
| Cumulative net since 2009 | $335K | $342K | $315K |

Nothing was cherry-picked or misreported. The numbers are close enough that the
methodology is clearly the same. The edge is also statistically real: mean return
per trade is **+0.435% of notional, t = 5.00, p < 1e-6** (n = 298), and it beats
randomised entries above the 200 SMA with matched exposure and holding periods at
the **99.9th percentile (ES)** and **98.3rd percentile (NQ)** over 2,000 simulations.

So this is not a bad backtest. What follows is what the presentation leaves out.

## Finding 1 — the hockey stick is index price levels, not a growing edge

The equity curve bends upward hard after 2021. That is *not* the strategy getting
better. It is 1 contract of NQ being a far bigger bet at 24,000 than at 1,800.

| | 2009–2017 | 2018–2026 |
|---|---|---|
| Net P&L | $79,619 | $235,171 |
| Mean return per trade | **0.427%** | **0.443%** |
| Mean notional per trade | $126,603 | $315,074 |
| Win rate | 79.9% | 76.3% |

Regressing yearly results on time:

* **Dollar P&L**: +$2,769/year, p = 0.027, R² = 0.27 — looks like improvement.
* **Percent return**: +0.28%/year, p = 0.495, R² = 0.03 — **no trend at all.**

Sizing 1 contract on an index that quadrupled turns a flat edge into an exponential
chart. 60% of all P&L since 2009 lands in 2024–2026; 25% lands in 2026 YTD alone.

## Finding 2 — it captures 38% of simply holding the same two contracts

Buy and hold 1 ES + 1 NQ from 2009 to Aug 2026: **$818,063**.
The strategy: **$314,790**, or 38.5% of that, while in the market 15.0% of days.

Per unit of exposure the strategy is far more efficient, and it sidesteps
2022 almost entirely (4 trades, the 200 SMA filter did its job). But in the
dollars-per-contract terms the post uses, doing nothing beat it by 2.6x.

## Finding 3 — an 83% win rate on a payoff that loses more than it wins

| | |
|---|---|
| Average win | $2,352 |
| Average loss | **$3,588** (1.53x the average win) |
| Worst single trade | **−$29,004** (NQ, entered 2025-02-21) |
| Worst intra-trade excursion | **−13.3%** of notional |
| Trades that went 5%+ underwater | 6.7% |

The 284 RSI-target exits made $438,428. The 14 time-stop exits — the trades where
the dip kept dipping and the 10-session clock ran out — lost $123,638. That is the
whole shape of the strategy: it wins small and often, and pays for it in rare,
large, un-stopped chunks. With no stop, "no stop" is the risk model.

## Finding 4 — the drawdown you have to fund

Marked to market daily (not on closed trades, which hides open-trade pain):

* **Max drawdown: −$47,531**, 2025-02-04 to 2025-05-23, not recovered until 2025-10-13.
* **251 days underwater.**

Estimated initial margin for 1 ES + 1 NQ at current levels is ~$58.6K. Plus that
drawdown, a sane account is **~$106K**, on which $314,790 over 17.7 years is
**~16.8% a year simple**. A real return, and a very different headline from "$335K".

## Finding 5 — ~8% of the raw P&L is a data artifact

Yahoo's `ES=F` / `NQ=F` are front-month series stitched at expiry **without**
back-adjustment, so each quarterly roll injects a price jump of roughly +0.5% to
+1.5% in contango that no position ever earned. A long-only backtest harvests
them as free profit. `src/roll_adjust.py` removes them with a Panama adjustment
(gap sized as the part of the roll-day move the cash index does not explain):

**$342,275 raw → $314,790 adjusted. $27,485, or 8.0%, was phantom.**

## Finding 6 — "buy the close" is not quite executable

The signal is RSI(2) computed *on* the close you are supposedly filled at. Taking
the next open instead — the honest, executable version:

| | Net P&L | Profit factor | Max DD |
|---|---|---|---|
| Entry at the signal close (as stated) | $314,790 | 2.35 | −$41,683 |
| Entry at the next open | $280,145 | 2.11 | **−$66,003** |

11% of the profit and a 58% larger drawdown live in that one assumption. In
practice you would submit an MOC order on an estimated close, landing somewhere
between these two.

## Robustness

Parameters are not knife-edge, which is a genuine point in the strategy's favour:

| Variant | Trades | Win rate | PF | Net | Max DD |
|---|---|---|---|---|---|
| As stated | 298 | 78.2% | 2.35 | $314,790 | −$41,683 |
| Next-open entry | 296 | 77.0% | 2.11 | $280,145 | −$66,003 |
| Cutler's RSI instead of Wilder's | 764 | 72.4% | **1.62** | $361,352 | −$59,374 |
| RSI entry < 5 | 167 | 77.2% | 2.30 | $209,840 | −$48,033 |
| RSI entry < 15 | 419 | 75.4% | 2.21 | $383,864 | −$41,683 |
| RSI exit > 60 | 303 | 70.6% | 2.23 | $253,070 | −$25,378 |
| RSI exit > 80 | 283 | 75.6% | 1.93 | $305,093 | −$78,605 |
| Max hold 5 | 313 | 69.3% | 1.83 | $242,875 | −$47,414 |
| Max hold 20 | 294 | 78.2% | 2.38 | $312,907 | −$54,430 |
| 100-day SMA filter | 254 | 78.3% | 2.38 | $247,309 | −$30,033 |
| 50-day SMA filter | 195 | 78.5% | 2.68 | $189,525 | −$18,763 |

The one sensitivity that matters: **which RSI you use**. Wilder's smoothing gives
PF 2.35; the simple-average (Cutler) variant many charting packages default to
gives PF 1.62 on 2.5x the trades. Costs barely matter — going from 0 to 4 ticks of
slippage per side only moves the total from $319,930 to $299,370.

## Out of sample: 2001–2008

The published curve starts in 2009. Running the same rules on 2001–2008 (all the
futures history Yahoo has): 91 trades, 75.8% win rate, PF 2.23, **net $21,881**.

The edge holds up — the win rate and profit factor survive the dot-com bust and the
GFC. But the dollars are trivial next to the later years, for the same reason as
Finding 1: the index was a quarter of its current level, and the 200 SMA filter kept
the strategy out of most of both bear markets.


## Does it work in India?

The strategy was published for ES and NQ. The hardest available out-of-sample test
is a different market, so the identical rules were run on the two most-traded NSE
index contracts over 2008–Aug 2026.

**It does not travel.** The effect is present in raw Indian prices and too weak to
trade after what it costs to trade it there.

| | US · ES + NQ | India · Nifty + Nifty Bank |
|---|---|---|
| Trades | 300 | 287 |
| Win rate | 78.0% | **62.7%** |
| Profit factor | 2.31 | **1.18** |
| Mean gross return per trade | +0.423% | +0.341% |
| Significance | t = 4.85 | **t = 2.45** |
| Beats random entry at | 99.9th pct | **80th / 60th pct** |
| Costs as a share of the edge | 3.3% | **46.5%** |
| Green years | 14 / 18 | **11 / 18** |
| Cumulative, net of costs | **+122.6%** | +52.4% |

Three things break it:

**1. The gross edge is smaller and barely significant.** Across four Indian indices,
only the Nifty 50 clears conventional significance, and only just:

| Index | Trades | Win rate | Mean gross return | t | p |
|---|---|---|---|---|---|
| Nifty 50 | 146 | 68.5% | +0.349% | 2.04 | 0.043 |
| Nifty Bank | 141 | 64.5% | +0.333% | 1.50 | 0.136 |
| Nifty IT | 108 | 74.1% | +0.297% | 1.11 | 0.268 |
| Sensex | 144 | 68.1% | +0.242% | 1.35 | 0.179 |

**2. The RSI timing adds almost nothing.** The random-entry test is more damning
than the p-values. In the US the signal beats randomly chosen entry days above the
200 SMA at the 99.9th percentile. In India the same test puts Nifty at the **80th
percentile** and Nifty Bank at the **60th**. At the 60th percentile there is no
timing edge — only a long position in an index that rose.

**3. Indian costs eat almost half of what is left.** STT is 0.02% of the sell side,
and — the piece most backtests miss — a long futures position gives up the basis as
it converges. At a ~6.5% repo rate against a ~1.3% dividend yield, the strategy's
average 4.8-session hold costs 0.10% of notional before anything else:

| Mean return per trade | India | US |
|---|---|---|
| Gross price move | +0.341% | +0.423% |
| After fees and slippage | +0.293% | — |
| After cost of carry | **+0.193%** | **+0.409%** |

Total costs take **46.5%** of the Indian edge and **3.3%** of the US one.

The risk is also worse in every dimension: max drawdown ₹2.67 lakh against ₹3.28
lakh of profit across eighteen years (82%), a −29.3% worst excursion on Nifty Bank
in Feb–Mar 2020, and 2026 the worst year on record so far at −₹1.51 lakh.

**Verdict for Indian traders:** the published edge is a US phenomenon at these
parameters. On the Nifty it survives as a marginal gross effect that the STT-and-carry
stack consumes almost half of; on the Nifty Bank it does not survive at all. Expect a
profit factor near 1.2 and a drawdown roughly the size of your lifetime profit — not
83% winners.

### Indian method notes

No usable continuous NSE futures series exists, so the Indian runs use the Nifty 50,
Nifty Bank, Nifty IT and Sensex **cash indices** as futures proxies and charge the
long-futures cost of carry explicitly at 5.2%/yr over each holding period. Transaction
costs model the full statutory stack — STT at 0.02% of the sell side, exchange and
SEBI charges, stamp duty and GST, about 0.0257% of notional per round turn — plus ₹47
of brokerage and one index point of slippage per side (three on Nifty Bank). Rupee
figures use current NSE lot sizes (75 Nifty, 30 Nifty Bank); percentage figures are
lot-independent and are the primary unit for any cross-market comparison.


## NSE cash equities

Index futures are one thing; NSE cash equities are where most Indian retail traders
would actually run this. The same four rules were applied to every liquid Nifty 500
constituent — 340 stocks clearing ₹5 crore of median daily turnover — at a fixed
₹1 lakh per position, 2008–Aug 2026.

The headline looks emphatic: **27,892 trades, 67.2% winners, +0.545% per trade before
costs, t = 18.0**. A t-statistic of 18 is not a fluke. But it measures the wrong thing.

### The edge is 0.075%, the cost is 0.32%

Buying *random* days in the same 340 stocks above their 200-day SMA, holding for the
same distribution of days, returns **+0.470% per trade**. The RSI(2) signal adds
**0.075%** on top — 13.8% of the gross figure. The rest is the well-known fact that
stocks in uptrends drift up.

| Mean return per trade | % of position |
|---|---|
| Available from random entry in the same universe | +0.470% |
| Added by the RSI(2) signal | **+0.075%** |
| Gross, as reported | +0.545% |
| Stock-futures round-trip cost | −0.126% (1.7× the edge) |
| Delivery-equity round-trip cost | **−0.323% (4.3× the edge)** |
| Net after delivery costs | +0.222% |

The strategy still finishes positive after costs. So would randomly buying uptrending
stocks, at +0.147%. You pay 0.32% in tax and spread to harvest 0.075% of signal on top
of a drift anyone can have for free.

The random-entry benchmark also settles the survivorship question. Today's Nifty 500 is
a list of companies that made it, so a long-only backtest on it is flattered — but the
benchmark trades that same survivor list, so the bias inflates both numbers equally.
Only the 0.075% gap is survivorship-neutral.

Cost sensitivity is the whole story:

| Round-trip cost | Mean net per trade | Win rate |
|---|---|---|
| 0% | +0.545% | 67.2% |
| 0.1% | +0.445% | 66.3% |
| 0.2% | +0.345% | 65.6% |
| 0.323% (delivery) | +0.222% | 64.6% |
| 0.5% | **+0.045%** | 62.8% |

At 0.5% round trip — ordinary for a mid-cap with a real spread — the edge is gone.

### You cannot take the trades anyway

RSI(2) < 10 is a market-wide condition: when India sells off, hundreds of stocks trip it
at once. The uncapped book holds a **median of 24 positions**, 71 at the 90th percentile,
and peaked at **219 open positions on 26 October 2023** — ₹2.19 crore deployed.

Cap it at something a person can run:

| Max positions | Capital | Trades taken | Skipped | Return/yr | Max drawdown |
|---|---|---|---|---|---|
| 5 | ₹5 L | 3,899 | 23,993 | 7.0% | −51.6% |
| 10 | ₹10 L | 7,139 | 20,753 | **3.8%** | **−49.8%** |
| 20 | ₹20 L | 12,288 | 15,604 | 2.7% | −40.5% |

A ten-position book earns 3.8% a year and draws down 50% over 18.7 years — a
fixed-deposit return carrying equity-crash risk. The capping is not a modelling artifact;
it is the constraint any real account faces, and it bites hardest exactly when signals
are most abundant, because that is when the market is falling.

### The single-stock tail

Average loss −4.61% against an average win of +2.88%. 11.3% of trades went more than 10%
underwater, 1.6% past 20%, with no stop. The worst was ADANIENT in January 2023: entered
on the dip, **−70.6% at its low**, closed by the 10-session clock at −54.5%. The 3,267
time-stop exits (11.7% of trades) lost ₹2.78 crore between them while the 24,625 target
exits made ₹3.40 crore.

Ten green years out of nineteen — a coin flip. 2008 averaged −3.56% a trade across 537
trades: the 200-day SMA filter let stocks in early that year and the market then fell
through it. 2025 and 2026 are both negative.

**Verdict for NSE equities:** the effect is statistically real and economically
negligible. It is 0.075% a trade of genuine signal sitting under 0.32% of cost, in a
strategy that wants 24 simultaneous positions and hands you a 50% drawdown for a 3.8%
annual return when you size it like a human. A single-stock dip buy with no stop also
carries −70% excursions that no index version ever will.

### NSE equity method notes

All Nifty 500 constituents whose Yahoo history is available and whose median daily
turnover since 2008 clears ₹5 crore — 340 of 485 downloaded names. Prices split and bonus
adjusted. Positions are a fixed ₹1 lakh, so no result depends on share price level.
Delivery friction is 0.323% per round trip: STT 0.1% each side, exchange charge 0.00297%
a side, stamp duty 0.015% on the buy, SEBI and GST, plus 0.05% slippage per side. The
stock-futures column swaps STT for the 0.02% sell-side rate. Capped-portfolio results
break ties on a signal date by lowest entry RSI, known at the signal, so no look-ahead.

## Verdict

The strategy is real, the post's numbers are honest, and the edge survives
randomisation, a proper out-of-sample window, and parameter perturbation. It is a
genuine short-term mean-reversion effect in index futures.

What the chart oversells:

1. The exponential shape is notional growth, not edge growth. The percentage edge
   has been flat for 18 years.
2. Dollars per contract on a risen index is the most flattering possible unit.
3. It captures 38% of buy and hold on the same two contracts.
4. An 83% win rate hides average losses 1.5x average wins, a −$29K worst trade and
   a −13.3% worst excursion, with no stop by design.
5. You need ~$106K to trade it through its own drawdown, making it ~16.8%/yr simple.

6. It is a US effect at these parameters. On the Nifty it is marginal and mostly
   eaten by costs; on the Nifty Bank it does not survive at all. On NSE single
   stocks the genuine timing edge is 0.075% a trade against 0.32% of cost.

The honest framing: a well-behaved mean-reversion overlay worth roughly 0.44% of
notional per trade, ~17 trades a year, in the market 15% of the time — not a
$335K machine, and not a strategy that ports to NSE futures as published.

## Reproducing

```bash
pip install pandas numpy scipy requests
python src/fetch_data.py       # ES=F, NQ=F, ^GSPC, ^NDX daily from Yahoo -> data/
python src/run_analysis.py     # reproduction, robustness, costs -> output/results.json
python src/deep_dive.py        # MTM drawdown, concentration, significance -> output/deep_dive.json
python src/export_charts.py    # series for the report -> output/chart_data.json
python src/india.py            # same rules on NSE indices -> output/india.json
python src/fetch_nse.py        # Nifty 500 daily history -> data/nse/  (~180MB, not in git)
python src/nse_equities.py     # same rules on 340 NSE stocks -> output/nse_equities.json
```

| File | Purpose |
|---|---|
| `src/fetch_data.py` | Yahoo chart API downloader (yfinance's transport fails behind a TLS-terminating proxy) |
| `src/indicators.py` | Wilder's RSI, Cutler's RSI, SMA |
| `src/roll_adjust.py` | Panama back-adjustment of the stitched continuous futures series |
| `src/backtest.py` | Strategy engine, contract specs, trade metrics |
| `src/run_analysis.py` | Claim reproduction, robustness grid, cost and random-entry tests |
| `src/deep_dive.py` | Mark-to-market drawdown, concentration, edge significance, capital needed |
| `src/india.py` | The same rules on Nifty 50, Nifty Bank, Nifty IT and Sensex, with the Indian cost stack |
| `src/fetch_nse.py` | Nifty 500 daily history downloader, split/bonus adjusted |
| `src/nse_equities.py` | The same rules on 340 liquid NSE stocks: cost decomposition, survivorship-neutral benchmark, capacity caps |
| `src/export_charts.py` | Chart series for the published report |

## Caveats

* Yahoo daily futures data is a front-month series; even back-adjusted it is not a
  tick-accurate settlement series. Treat P&L as accurate to a few percent.
* Entry and exit both occur at the daily close; real MOC fills will differ.
* No stop is modelled because the rules specify none. Position sizing is fixed at
  1 contract throughout, as stated.
* Not financial advice.
