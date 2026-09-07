# Four-slot channel-exit breakout book (NSE cash equities)

Long only. No leverage. No derivatives. Daily bars. Reproduced by:

```bash
python scripts/strategy_lab.py --strategy breakout --entry-n 90 --top 4 --atr-mult 5 --exit-n 25 \
    --clv 1.0 --rank mom2 --regime sma100 --stock-sma 75 --daily-exit regime \
    --min-price 5 --min-bars 126 --dd-budget 0.30 --dd-start 0.18 --dd-floor 0.5 --cash-rate 0.06 --yearly
```

The same book without the drawdown budget and with a 40-day channel (`--exit-n 40`, no
`--dd-*` flags) returns +41.4% at -28.6% on the same assumptions.

## Rules

**Universe, rebuilt daily.** The 1,000 NSE names with the highest trailing 126-day median
turnover among those trading at least ₹1 crore a day, priced at ₹5 or more, with 126 bars of
history. No index membership is used. Delisted names are absent from the data (see Caveats).

**Regime.** An equal-weight total-return index of the eligible names (membership lagged a day)
must be above its 100-day simple moving average. When it is not, nothing new is bought and every
position is sold at the next open.

**Entry, evaluated at the close, filled at the next open.** All of:

1. Close above the highest high of the previous 90 sessions (signal bar excluded).
2. The bar closed at its own high: (close - low) / (high - low) = 1.0. A bar with no range
   (a circuit lock) does not qualify, and a buy is dropped if the fill bar has no range.
3. Close above the stock's 75-day simple moving average.
4. Regime on.

**Selection and size.** Four slots, 25% of equity each. When more names qualify than there are
free slots, rank by a blend of 12-month and 6-month momentum (each measured to 21 days ago)
and take the best. Gross exposure never exceeds 100%; idle cash earns the cash rate.

**Exit, evaluated at the close, filled at the next open.** Any of:

1. Close more than 5 × ATR(20) below the highest close since the signal bar.
2. Close below the lowest low of the previous 25 sessions (the channel exit).
3. Close below the 75-day simple moving average.
4. Regime off (all positions).

A sell on a bar with no range is carried to the first bar that trades.

**Drawdown budget.** Exposure is 100% of normal until the book's own equity is 18% below its
peak, then shrinks linearly to 50% of normal at a 30% drawdown, and expands as it heals. Each
change is charged the transaction cost.

**Costs.** 30 bps per unit of one-way turnover (50 bps in the stress rows).

## Results, 2007-01-02 to 2026-08-27, corrected fills

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

Mean gross exposure 49%; annual one-way turnover 2.7x.

## Year by year against the Nifty 50

Nifty 50 is the price index (Yahoo `^NSEI`), which starts 2007-09-17; 2026 runs to late August.
Drawdown is the worst peak-to-trough fall inside the year, measured from the prior year-end.

| Year | Nifty 50 return / DD | Strategy return / DD |
| --- | --- | --- |
| 2007 | n/a | +227.1% / -21.1% |
| 2008 | -51.8% / -59.9% | -13.3% / -23.6% |
| 2009 | +75.8% / -17.6% | +58.7% / -13.0% |
| 2010 | +17.9% / -10.7% | +41.4% / -8.5% |
| 2011 | -24.6% / -26.2% | -1.4% / -5.4% |
| 2012 | +27.7% / -13.8% | -16.2% / -22.0% |
| 2013 | +6.8% / -14.6% | +36.4% / -10.2% |
| 2014 | +31.4% / -6.5% | +32.6% / -20.0% |
| 2015 | -4.1% / -16.0% | -2.8% / -20.3% |
| 2016 | +3.0% / -12.3% | +25.6% / -8.9% |
| 2017 | +28.6% / -4.1% | +37.3% / -20.8% |
| 2018 | +3.2% / -14.6% | +7.9% / -15.8% |
| 2019 | +12.0% / -11.4% | +26.3% / -8.3% |
| 2020 | +14.9% / -38.4% | +234.0% / -21.9% |
| 2021 | +24.1% / -10.1% | +71.8% / -23.5% |
| 2022 | +4.3% / -16.5% | +41.2% / -16.9% |
| 2023 | +20.0% / -7.1% | +72.8% / -13.2% |
| 2024 | +8.8% / -10.9% | +68.4% / -14.7% |
| 2025 | +10.5% / -8.7% | +3.0% / -16.5% |
| 2026 (to Aug) | -7.8% / -15.2% | +21.5% / -9.5% |

The strategy out-returns the index in 16 of 19 measurable years (losing 2009, 2012, 2025). On
the common window it compounds at 38.5% against the index's 9.3%, and is ahead in 77% of rolling
1-year windows, 93% of 3-year windows and 96% of 5-year windows.

## Read before trading it

1. **The drawdown is a property of the path, not the rules.** Started in 2015 the same rules
   lose 33.7% in 2015-16 (41.8% without the budget) where the 2007-start run loses 20%: the
   2007-start book entered 2015 holding cushioned 2014 winners, the 2015-start book bought the
   failing breakouts of early 2015. With four names, any year's drawdown depends on which four
   are held going in.
2. **The point is selected.** Sixteen one-notch neighbours span +22% to +40% CAGR and seven of
   them breach a 25% drawdown (a 4 ATR trail: -34%; a 20-day channel: -32%; three slots: -28%;
   five slots: -29%). About 1,700 configurations have been evaluated on this one history.
3. **Concentration.** 2007 (+227%) and 2020 (+234%) carry much of the compounding; ex-top-2
   years the CAGR is +23%. About 20 trades a year, a handful deciding each year.
4. **Survivorship and capacity.** Delisted names are absent; the edge lives in names trading
   ₹1-5 crore a day; on the 500 most liquid names the book returns +20.8% at -31.5%.
5. **Cash yield.** 6% on the ~50% idle is worth about 4 points of CAGR.

An independent review of the eight-slot predecessor put the forward expectation of this family
at a CAGR in the high teens to twenties with drawdowns of 30-40%. For the four-slot book the
return expectation is higher and the drawdown expectation is not lower. The full research trail
is in README.md and the lessons in AGENTS.md; the eight-slot book is documented in
docs/F1_STRATEGY.md on branch claude/f1-strategy-details.
