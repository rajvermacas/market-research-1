# F1: concentrated small-cap breakout trend following on NSE cash equities

Long only. No leverage. No derivatives. Daily bars. Reproduced by:

```bash
python scripts/strategy_lab.py --strategy breakout --entry-n 75 --top 8 --atr-mult 4 --clv 1.0 \
    --rank mom2 --regime sma100 --stock-sma 100 --daily-exit regime \
    --min-price 5 --min-bars 126 --cash-rate 0.06 --yearly
```

F2 is the same book plus `--dd-budget 0.25 --dd-start 0.15 --dd-floor 0.5`: exposure is cut
linearly from 100% at a 15% drawdown to 50% at a 25% drawdown, and restored as it heals.

## Rules

**Universe, rebuilt every day.** The 1,000 NSE names with the highest trailing 126-day median
turnover among those with at least ₹1 crore a day of turnover, a price of at least ₹5, and
126 bars of history. No index membership is used, so there is no membership lookahead.
Delisted names are absent from the data (see "Caveats").

**Regime.** An equal-weight total-return index of the eligible names, membership lagged one
day, must be above its own 100-day simple moving average. When it is not, no new positions
are opened and every open position is sold at the next open.

**Entry signal, evaluated at the close.** All of:

1. The close is above the highest high of the previous 75 sessions (the signal bar itself
   excluded).
2. The bar closed at its own high: close-location value (close - low) / (high - low) = 1.0.
   A bar with no range (a circuit lock) does not qualify.
3. The close is above the stock's own 100-day simple moving average.
4. The regime is on.

**Selection.** Eight slots. When more names qualify than there are free slots, rank by a
blend of 12-month and 6-month momentum (each measured to 21 days ago, so the last month is
skipped) and take the best.

**Sizing.** Equal weight, 12.5% of equity per position, bought at the next day's open.
Gross exposure never exceeds 100%. Idle cash earns the `--cash-rate` (6% in the headline,
0% in the stress rows below).

**Exit, evaluated at the close, executed at the next open.** Any of:

1. The close is more than 4 × ATR(20) below the highest close since the signal bar
   (Chandelier trail).
2. The close is below the stock's 100-day simple moving average.
3. The regime turned off (all positions).

A freed slot can be refilled from the same close. A buy on a bar with no range (limit-up
lock) is dropped; a sell on such a bar is carried to the first bar that trades.

**Costs.** 30 bps per unit of one-way turnover on every fill (50 bps in the stress rows).

## Results, 2007-01-02 to 2026-08-27, corrected fills

| Assumptions | CAGR | Max DD |
| --- | --- | --- |
| 30 bps, cash at 6% (base) | +33.1% | -24.6% |
| 50 bps, cash at 6% | +31.9% | -25.3% |
| 30 bps, cash at 0% | +28.5% | -28.1% |
| 50 bps, cash at 0% | +27.4% | -28.9% |

Mean gross exposure 41%; annual one-way turnover 2.2x; about 20 trades a year, 376 over the
window, 52% winners, median trade +1.3%, mean +15%. CAGR with the best year removed +27.1%;
with the best two years removed +22.0%. Ten trades supply a third of the total log return.

## Year by year against the Nifty 50

Nifty 50 is the price index (Yahoo `^NSEI`), which starts 2007-09-17; 2026 runs to late
August. Drawdown is the worst peak-to-trough fall inside the year, from the prior year-end.

| Year | Nifty 50 return | Nifty 50 DD | F1 return | F1 DD |
| --- | --- | --- | --- | --- |
| 2007 | n/a | n/a | +148.8% | -13.4% |
| 2008 | -51.8% | -59.9% | -16.1% | -22.6% |
| 2009 | +75.8% | -17.6% | +57.6% | -13.6% |
| 2010 | +17.9% | -10.7% | +22.6% | -9.0% |
| 2011 | -24.6% | -26.2% | +2.3% | -2.1% |
| 2012 | +27.7% | -13.8% | -2.5% | -10.4% |
| 2013 | +6.8% | -14.6% | +23.0% | -4.9% |
| 2014 | +31.4% | -6.5% | +86.1% | -13.1% |
| 2015 | -4.1% | -16.0% | -2.4% | -21.5% |
| 2016 | +3.0% | -12.3% | +22.8% | -9.6% |
| 2017 | +28.6% | -4.1% | +65.4% | -21.7% |
| 2018 | +3.2% | -14.6% | -2.8% | -24.6% |
| 2019 | +12.0% | -11.4% | +14.0% | -5.7% |
| 2020 | +14.9% | -38.4% | +96.1% | -17.0% |
| 2021 | +24.1% | -10.1% | +86.8% | -10.5% |
| 2022 | +4.3% | -16.5% | +3.0% | -15.3% |
| 2023 | +20.0% | -7.1% | +120.9% | -9.7% |
| 2024 | +8.8% | -10.9% | +48.8% | -17.8% |
| 2025 | +10.5% | -8.7% | -0.2% | -13.4% |
| 2026 (to Aug) | -7.8% | -15.2% | +9.9% | -12.4% |

F1 returns more than the index in 14 of 19 measurable years (losing 2009, 2012, 2018, 2022,
2025) and has the shallower within-year drawdown in 11 of 19. Over the common window the
index compounded at 9.3% a year with a -59.9% drawdown. F1 is ahead in 79% of rolling
1-year windows, 99% of 3-year windows and 100% of 5-year windows.

## What an independent review found

A second model instance reviewed the code and the search logs adversarially. It reproduced
the result, verified indicator alignment, regime lag, fill arithmetic, costs and cash yield by
hand, and found two fill errors (entries on limit-up opens, exits into lower-circuit locks)
that are now fixed and cost 2.5 points of CAGR. Its verdict: the mechanism's edge is real
(trade-level t-statistic 6.2, deflated Sharpe about 1.0 after ~1,400 trials), but the level
is the best of a local search whose mean is about 29%; CAGR is a plateau across one-notch
neighbours (29-37%) while the drawdown is not (4 of 15 neighbours exceed 25%). Its forward
expectation: **CAGR 15-22%, drawdowns of 30-40%**, a few +50-100% years amid a third of years
flat or negative.

## Caveats

1. **Survivorship.** Delisted names are absent from the panel entirely. The ₹1-2 crore/day
   tier supplies 43% of the return and is where delistings concentrate. Curing this needs
   NSE bhavcopy (see AGENTS.md).
2. **Capacity.** At a ₹5 crore/day floor the family returns about half as much. A ₹2 crore
   book is 8-20% of daily volume in the bottom tier; 30 bps does not cover that impact.
3. **Universe and regime sensitivity.** On the 500 most liquid names the drawdown is -37%;
   with a 200-day index regime it is -45%.
4. **Cash yield.** 6% on the ~60% of the book that is idle is worth about 4.6 points of CAGR.
5. **Selection.** About 1,400 configurations were evaluated on this one history.

The full research trail, the earlier loops and the lessons are in README.md and AGENTS.md.
