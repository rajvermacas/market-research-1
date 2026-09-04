# Strategy ledger

Every published strategy tested in this repository, so a later pass can tell at a glance
what has already been settled and what the answer was. Newest first. Full method and
numbers live in the README section named in each row.

The bar for "works" is deliberately high and is the same for every entry: it must beat
**random entries walked to the same exit by the same code**, not merely make money.
Anything can make money in a market that rose 20% a year over the test window.

| # | Source | Strategy | Universe / window | Verdict |
| --- | --- | --- | --- | --- |
| 6 | [@QuantifiedStrat, 8 Aug 2024](https://x.com/QuantifiedStrat/status/1821481550078529677) | **Turn of the month (Ultimo)** — long from the close of the 5th-last session of the month to the close of the 3rd session of the next | Nifty 50/100/500 index 2005-2026 | **YES — the first one that works.** Beats buy-and-hold on return-per-drawdown on all three indices (0.20/0.25/0.30 vs 0.15/0.19/0.18) at a third of the exposure, beats random windows by 2.0-2.6 sigma, stable across halves, and all 35 window variants are positive. |
| 5 | [@QuantifiedStrat, 16 Jul 2024](https://x.com/QuantifiedStrat/status/1813181432749301961) | **Opening range breakout** — buy the break of the first N hours' high, exit at the close; flip buys the break of the low | Nifty 500 hourly 2015-2026 | **Confirms the source.** Real gross edge of +0.119% per trade at +40 sigma, rising with range length and stable across halves — and still under the 0.20% round trip, so net it loses. Downside flip is -14 sigma, worse than random. |
| 4 | [@QuantifiedStrat, 24 Aug 2026](https://x.com/QuantifiedStrat/status/2091873162208145497) | **Larry Connors' R3** — RSI(2) falls three days running from below 60, closes under 10, above the 200-day SMA; exit on RSI(2) > 70 | Nifty 50/100/500 index 2005-2026; constituents 2015-2026 | **No.** Loses to its own random control in 5 of 6 index tests. The path condition adds nothing over the plain level. |
| 3 | Same test | **IBS** (internal bar strength < 0.2), carried as a family control | as above | **No.** Negative on every index under the Connors exit and behind random. |
| 2 | [@QuantifiedStrat, 18 Aug 2026](https://x.com/QuantifiedStrat/status/2089698829180301601) | **RSI(2) mean reversion** — buy under 10, sell on the first close above the previous high | as above | **No** on the index (ties random, loses 8-12 points to buy-and-hold). Real but untradeable on constituents: +0.15% over 3 days against a 0.20% round trip. |
| 1b | [@SoulzBTC, 22 Jun 2026](https://x.com/SoulzBTC/status/2069025398189355128) | **RSI + Bollinger components** (rules not recoverable from the video; canonical reading ablated) | Nifty 500 daily 2015-2026 | **Mixed.** Squeeze breakout +4.97 sigma and the only arm beating buy-and-hold. Buying the lower band is -6.84 sigma, i.e. worse than random. |
| 1a | Annotated chart (Japanese) | **RSI "W" double bottom + SuperTrend** | Nifty 500 hourly 2015-2026 | **No.** Indistinguishable from random at every horizon once the exit is held constant. |

## Method that every row above follows

Established in the first two studies and applied since:

1. **Random-entry control, always.** Same bars, same exit, same code, oversampled so the
   control's own standard error is the small one. Report the gap in combined sigmas.
2. **Hold the exit genuinely constant.** A price-based stop derived from the entry bar
   gives different arms different stop distances and invents rankings that do not exist —
   this is how the first study's apparent result evaporated. A fixed horizon is the
   arbiter.
3. **Cluster by date before believing a cross-sectional t-statistic.** Oversold rules fire
   on hundreds of names inside one selloff; pooling symbol-days counts the same market
   move over and over.
4. **Sweep the free parameter and read the shape, not the peak.** A real effect is a
   plateau; a fitted one is a spike with nothing around it.
5. **Report time in market next to any return.** A headline several times a strategy's
   CAGR is usually the CAGR divided by exposure.
6. **Validate indicators against a textbook loop**, and render pattern hits before
   believing them.
7. **Costs are a parameter, not a footnote.** Anything holding a few days and trading
   often is decided by the cost assumption; sweep it.

## Standing caveat

Every constituent-level result carries survivorship bias — the universe is today's index
membership walked backwards. Index-level results (`--mode index`, real Yahoo series) do
not, which is why they are the ones quoted when the two disagree.
