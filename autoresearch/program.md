# program.md — the autoresearch loop

You are running a search over trading strategies. One file changes; nothing else does.

This is the file a human edits between runs. If a rule below turns out to be the thing holding
the search back, that is a finding — say so at the end of the run rather than working around it.

## The goal

Maximise `SCORE`, printed by `python autoresearch/backtest.py`.

`SCORE` is `min(Sharpe on train, Sharpe on validation)`, net of costs, on the Nifty 500 daily
panel. The minimum of the two, so a configuration that wins one window by losing the other
gains nothing. It is zero for a book that opens fewer than 100 positions or holds less than 20%
of its capital on average — those are not strategies, they are artefacts.

A higher `SCORE` is better. Nothing else in the printed report decides keep or revert, but read
the rest of it anyway: CAGR against the benchmark, drawdown, exposure and turnover are how you
tell a real improvement from a lucky one, and they are what you write down.

## The rules

1. **Edit `autoresearch/strategy.py`. Nothing else.** `prepare.py`, `evaluate.py`, `toolkit.py`
   and `backtest.py` are the measurement. They are hashed into `harness.lock` and a run whose
   hashes disagree refuses to score. Do not run `--update-lock`; that is a human's decision.
   If a metric or a cost assumption seems wrong, write that down as a finding — do not fix it
   and keep the resulting number.

2. **One idea per iteration.** Change the entry rule, or the exit rule, or the sizing — not
   three at once. A run that moves four things and improves teaches you nothing about which of
   the four did it, and the odds are that three were noise.

3. **Run it, then decide.**

   ```
   python autoresearch/backtest.py --note "what you changed, in one line"
   ```

   Every run appends a row to `results.tsv` whether it wins or loses, including the ones you
   revert. The record of what did not work is the point.

4. **Keep or revert on `SCORE`, with git.**

   ```
   git add -A && git commit -m "<what changed>: SCORE 0.83 (was 0.77)"   # improved
   git checkout -- autoresearch/strategy.py                              # did not
   ```

   Improved means strictly higher than the best score standing. Equal is not improved. Keep
   `results.tsv` even when you revert the strategy — commit it with the next win, or on its own.

5. **Never read forward.** Row `t` of the weight matrix is what you want to own having seen bar
   `t` and nothing after it. The harness re-runs your strategy on truncated history and prints
   `LOOK-AHEAD` if the answer moves. That check is the floor, not the ceiling: it samples four
   cut points and will not catch everything, so do not lean on it. In particular, anything
   fitted on the whole panel — a threshold, a mean, a normalisation, a list of symbols that did
   well — is look-ahead even when the probe stays quiet.

6. **Use the toolkit; do not write a second indicator.** `toolkit.py` has the moving averages,
   RSI, ATR, ranks, top-N and the rebalance helper, all causal and all warm-up guarded. A
   second copy of an indicator drifts from the first, and then two runs disagree and the wrong
   one produces the number.

7. **The panel is what it is.** `panel.close` carries NaN where a symbol had no bar; that is a
   real missing session, not something to fill. `panel.tradable` is the liquidity and listing
   filter, already causal — respect it rather than reconstructing your own from the full sample.

## What is available

`generate_weights(panel)` returns a `(bars x symbols)` float matrix. Row `t` is the book held
from the close of session `t` to the close of `t + 1`; the harness applies that shift. Weights
are fractions of capital: they may sum to less than 1, and whatever is left earns nothing.
Negative weights and anything above the gross cap are removed before scoring, so there is no
short side and no leverage to find.

The panel gives you, all shaped `(bars x symbols)`:

| | |
| --- | --- |
| `close`, `open_`, `high`, `low` | total-return adjusted prices, NaN on a missing session |
| `mark` | the forward-filled close — what open positions are marked on |
| `volume`, `rupee_volume` | shares and `close * volume` |
| `tradable` | boolean: liquid enough and listed long enough, on trailing data only |
| `dates`, `symbols` | the axes |

## Ideas worth trying, roughly in order of how much they usually matter

Exits and risk before entries. Almost every strategy in this repository was improved more by
what it did after the entry than by what triggered it.

- **Exit rules.** A trailing stop on ATR, a time stop, an exit when the trend filter breaks.
- **Position sizing.** Inverse volatility instead of equal weight; a cap on any one name.
- **Rebalance cadence.** Turnover is charged; 21 sessions is a guess, not a result.
- **The trend filter itself.** Different spans, a different indicator, a slope condition.
- **The ranking.** Trailing return over a different horizon; skipping the most recent month,
  which carries short-term reversal; risk-adjusted rather than raw return.
- **A regime overlay.** Sit in cash when the market itself is below its own average. Read the
  lesson about regime filters below before believing one.
- **Breadth of the book.** More slots is more diversification and more turnover.

## Anti-overfitting rules, all of them paid for in this repository

- **A parameter that dominates on a short window may do nothing over a full cycle.** Slot count
  swung CAGR by 39 points across 2.9 years and by under two across 11.6. Sweep on the longest
  window you have, and distrust anything that only works on one.
- **A regime filter tuned on one universe is not a regime filter.** One breadth rule lifted
  Nifty 500 by nine points of CAGR and cost the full NSE board forty. If a rule is real, it
  survives `--universe nifty200` and `--universe nse_all`. Check before believing.
- **Warm-up truncation is a silent window filter.** It once flattered a strategy by nine points
  of CAGR by deleting the worst regime in the data. If a change moves the number of bars the
  book is live for, find out what it removed.
- **Do not scale out of a strategy whose edge is in the tail.** Banking half a position early
  cost one setup twelve points of CAGR, because the far winners funded all the losers.
- **Exposure is not free.** A book that is 30% invested and draws down less than the market has
  not beaten it on risk; it has just been smaller. The report prints `invested` for this.
- **The benchmark is the mean of normalised prices, never the median.** Already handled in the
  harness — quoted here so nobody re-introduces it in a strategy's own reporting.

## Stopping

Stop after 20 iterations, or when eight consecutive attempts fail to improve the score,
whichever comes first. Then write a summary: the best score and what produced it, the three
ideas that helped most, the ideas that plainly did not work and what you think that says about
the market, and anything you wanted to try but could not within these rules.

Do not run `--reveal-holdout`. The 2022-onward window is not part of this loop. A human spends
it, once, on the strategy the loop finally settles on — and it is only worth anything for as
long as it stays unseen.
