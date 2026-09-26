# Research loop state — READ THIS FIRST in a new session

This file is the handoff between research loops. A fresh session resumes from it
and from the committed ledgers below; it never restarts from scratch. The
orchestrator rewrites the "Current state" and "Lead queue" sections at every loop
close-out and commits them with the ledgers.

**Workstream branch: `claude-routine`** — every loop (interactive or the scheduled night/morning
routines) checks it out, commits to it and pushes to it; never to another branch.

## Goal

Find an un-researched mechanism that beats the standing champion on **both CAGR
and max drawdown** (train AND forward), under realistic execution, and crown it
through `scripts/promote_gate.py`. Nothing else crowns a champion.

## Protocol (the loop, in one screen)

1. `TZ=Asia/Kolkata date` — set ONE wall-clock stop for the loop.
2. Read `.cache/strategy_lab/champion_real.json` (the champion, its params and
   its revealed forward numbers) and the tail of `.cache/strategy_lab/results_real.tsv`.
3. Pick an idea from the lead queue or design a new one — **never repeat a tested
   strategy** (the skill's MANDATORY no-repeat section): grep
   `research/tested_mechanisms.tsv` by signal/family words (a tested family is only
   retested on a changed base), grep `.cache/strategy_lab/*results*.tsv` for the exact
   candidate + params before every trial, and check `research/promotions/` before any
   gate. New file = `scripts/strat_l<loop><designer>_<idea>.py`, composing
   the champion by import, with an off-switch that reproduces it exactly.
4. Screen on the blind realistic ledger (defaults — never override the profile
   inside the main ledger; isolated `--results/--best-json` per parallel worker):
   `python scripts/strategy_lab.py --candidate <file> --params-json '<full json>' --universe nse_all --top <champion top>`
   Trials print train, folds and noise only; forward stays blind. ~4 s per trial
   for a light candidate (panels are cached under `.cache/strategy_lab/panels/`).
5. A KEEP (robust ruler beats the ledger best by more than the trial's own noise,
   train CAGR above bench, DD within slack, both halves positive) is a
   *candidate*. Gate it:
   `python scripts/promote_gate.py --candidate <file> --params-json '<json>' --top <n>`
   The gate reveals forward once (logged in `.cache/strategy_lab/reveals.tsv`).
   If it prints ALL CHECKS PASS: `python scripts/promote_gate.py --crown research/promotions/<report>.json`.
6. Close-out: append every mechanism to `research/tested_mechanisms.tsv`, add a
   README results-ledger row, rewrite the two sections below, `git add -f` the
   ledgers, commit, push.

## Current state (Loop-29 close, 2026-09-27 02:37 IST — champion unchanged since L25)

- **Champion** (`.cache/strategy_lab/champion_real.json`, crowned L25): `strat_l23a_liqconfirm`,
  full board (`nse_all`), `--top 25`, params
  `{"b_hi": 0.65, "b_lo": 0.45, "b_mid": 0.55, "floor_lb": 19, "lookback": 16, "max_dist": 0.055, "regime_ma": 18, "lq_min": 5e6, "lq_days": 40, "lq_shift": 0.05, "lq_shift_hi": 0.05, "lq_shift_lo": 0.075, "lq_mode": "strict", "top": 25, "weighting": "invvol"}`.
  Train +30.09% / DD −17.22% (calmar 1.75, robust 2.121, noise sd ~0.16) vs bench +19.84%;
  forward +21.58% / DD −20.47% (calmar 1.05) vs bench +14.53% / −27.88%. Nifty 500 transfer
  +28.4% / −12.1% vs bench +21.1%. Gate report:
  `research/promotions/2026-09-26T101152Z_strat_l23a_liqconfirm.json`.
- **Previous champion**: `strat_floorhighfresh` top 25 equal (train 24.13/−18.98, fwd 20.63/−21.65).
- **To dethrone it** (gate check 9 `tradeoff`, user rule), on train AND forward separately:
  dominate (CAGR higher, DD no deeper), or gain ≥ +2pp CAGR with DD at most
  min(0.5 × gain, 5pp) deeper. Train: > 30.09% / −17.22%. Forward: > 21.58% / −20.47%
  (or ≥ 23.58% with a bounded dent). Plus checks 1–8 (forward DD must also beat the bench's).
- **Universe is open**: full board or Nifty 500 (`--universe nifty500`, own ledger; gate with
  `--universe nifty500`).
- **Harness**: realistic execution + robust fold ruler + noise margin + blind forward;
  policy keys searchable (`top`, `weighting`, `max_weight`, `min_hold`, `max_hold`, `sl_pct`,
  `ts_pct`, `stop_cool`). Pass `--top 25` on the CLI; set the book size with the `top` key.
- **Reveals used**: 16 (L29 spent #16 on strat_l29j_liqclimb; L28 #14 corrdiv, #15 upvolnz; L27 #12 spread, #13 froth). **Trials under the current scoring**: ~840 across realistic ledgers (the gate's N=841).
- **Loop counter**: last loop = 29. Next loop = 30.

## Lead queue (highest first)

0000. **Loop-29 outcome (no promotion; NULL CONTROLS are now part of the protocol).** 21 files (15 mechanisms + 6 random
   controls), 238 trial rows, 1 gate:
   - **Random nulls on the L25 base** (use these bands before believing any train gain): random rank tilt
     (`strat_l29c_randtilt`, w .07/.15): train CAGR 30.46 ± 1.29 (max 32.63), robust max 2.959 — 9/16 beat the champion,
     4/16 dominate it on train; at w .2 (8 seeds, orch ledger) 26.7–31.8. Random re-arm of the 16 partial-tier train months
     (`strat_l29d_randrearm`, 8 months): 34.18 ± 2.14 — ANY re-arm adds ~+4pp train. Random partial cut (`strat_l29f_randcut`):
     26.8–29.2. Random fixed-500 slot reservation (`strat_l29h_randres`): 29.33 ± 2.65. Nifty 500 book
     (`strat_l29i_n500null`): tilt 32.29 ± 1.41 (robust max 3.558), cut robust max 3.708.
   - **Gated: `strat_l29j_liqclimb`** (lc_w −0.2 / lc_lb 6 / lc_days 60 — favour names FALLING in cross-sectional traded-value
     rank): train 36.32/−15.21 robust 2.961, above all 24 random-tilt draws (~4 sd), neighbours 29/32 → fwd **17.28/−19.54**
     vs champion 21.58/−20.47: FAILS (−4.30pp fwd CAGR; margin 0.840 < 0.898). The sixth selection-side train gain that
     dies forward — clearing a random null does NOT rescue a rank tilt. Treat rank/selection tilts on this base as closed
     for forward CAGR unless a new data source changes the base.
   - Not gated (null-level): `agerearmup` (36.38/−17.22, 83–88th pct of the re-arm null; the guard is a 2018 veto),
     `insideday` +0.07 (33.23/−16.62, robust inside the null). Contaminated: `coresat` (today's Nifty 500 membership as a
     slot reservation, 36.02/−16.20) is look-ahead — above all 10 random-reservation draws while the point-in-time
     liquidity-core version (`liqcore`) loses CAGR. Dead: breadth-spread, regime-age cut, signal-hit, capture, fall-cut
     (below its own null), Nifty 500 bookdd / midbeta; bookvol is inside the Nifty 500 cut null.
   - Data backlog promoted: point-in-time index membership would turn coresat into a testable idea.
   - Harness note (audited): the train YEARS line's "2022" bucket is the Jan-2022 holding month decided on the Dec-2021 close
     (labels are closing month-ends) — a split convention shared by every recorded number, not a forward leak.
   - Loop errors: designer B ran one batch with output discarded (4 rows), designer A piped one batch (8 rows), designers E
     and F each launched two trials in one tool block; all rows logged correctly.

000. **Loop-28 outcome (no promotion).** Two gates, both fail the forward trade-off:
   - `strat_l28b_corrdiv` (correlation-diversified selection, cd_c .3 / 60d / mean / buf 15, + weighting rank):
     train 33.16/−17.63 → fwd 18.09/−18.50 (−3.50pp CAGR). The fifth selection-side train gain that loses
     forward CAGR (after ddquality, breakmag, CS spread, top-22). Selection/rank channels look closed for forward CAGR.
   - `strat_l28o_upvolnz` (board up-value share over 42 sessions > .52 → re-arm a PARTIAL tier to full; never re-arms
     full cash): train 38.46/−17.76 (plateau .48–.55, 14 train firings) → fwd 26.79/−26.49: +5.21pp CAGR but DD 6.01pp
     deeper (allowed 2.60). Re-arming adds forward return AND forward drawdown. Its forward is now revealed — do not
     re-shape it against that number (e.g. a DD guard tuned to 2022-26 is contaminated). A re-arm variant may only be
     retested with a DD guard justified on train data alone, and gated as a new candidate with disclosure.
   - Re-arm family status: corerearm (L27), thrust (L28a, 3 firings), upvol/upvolnz — all gain on train by re-arming
     partial tiers after washouts; the one gated shows the forward cost is drawdown.
   - Ungated train leads: `strat_l28a_thrust` lo .45 / hi .60 / w21 (32.46/−17.22, 3 firings — fails footprint);
     `strat_l28d_runupdemote` 4d / .15 (32.45/−17.89, passes train trade-off, but 29.38/−18.52 at 100 bps — cost-sensitive).
   - Clean-room audit (L28): champion, both gated rows, the upvolnz off-switch and a tvsurge no-fire control all
     reproduce to printed precision; the up-value share is point-in-time (sessions strictly before months[t]).
     Caveat it raised: the gated uv_hi .52 cell lies OUTSIDE upvolnz's documented SPACE {.56,.57} (count as extra trials).
   - Harness fact (designer D): refused entries (up-lock, low traded value) are NaN'd before the pick, so the slot goes to
     the next rank — there is no cash to convert by demoting fill-risk names.

00. **Loop-27 outcome — a crown was REVOKED.** `strat_l27a_froth` (illiquid-tail minus liquid-core
   2-month return > .06 -> exposure x 0.6) passed all 9 gate checks (train 30.21/−14.09, fwd
   23.44/−14.44) and was crowned, then the audit found the designer chose the sign after a
   diagnostic that printed the Jan-2022 rel spike — a FORWARD-window value — and the 2022-01 /
   2024-01 firings carry the forward DD gain. The L25 champion was restored by hand from git
   (commit 21b710a); the gate report stays in `research/promotions/`. If the owner judges the
   contamination tolerable, re-crown with
   `python scripts/promote_gate.py --crown research/promotions/2026-09-26T173406Z_strat_l27a_froth.json`.
   Otherwise froth can only be confirmed on forward data after 2026-09. Its train DD gain is the
   2016-10/11 firings alone (demonetisation); the 2020-21 firings cost 2.6pp train CAGR.
01. **Illiquidity rank premium is train-side.** CS spread (wide sign) gated: train 35.19/−15.84 but
   fwd 18.35/−17.24 (−3.23pp CAGR) — the third rank tilt (after ddquality, breakmag) that buys train
   CAGR and loses forward CAGR. Amihud (35.11/−16.22) is the same axis; do not gate it on this
   evidence. Rank tilts on the 25-name book look exhausted for forward CAGR; exposure-side work
   (with strictly pre-2022 diagnostics) is where the forward DD improvements have come from.
02. **Liquid-core rebound re-arm** (`strat_l27o_corerearm`, k3 / thr .12 / to 1.0): train 39.18 / −17.22
   (+9.1pp at the same DD), a CAGR plateau over k 2–4, thr .12–.15, to .7–1.0, but the DD breaks
   at thr ≤ .11 (−21.05) and the gain rests on 7 train firings, five of them the 2020-06..10
   post-COVID V. The gate's footprint check (8% < 10%) would fail as is. Forward is unseen. Next
   Attribution (train, scratch `.cache/l27_rearm_attr.py`): the 2020 firings alone give 36.89 (+6.8pp);
   the two 2016 firings alone give 32.27/−17.22. **Blindness caveat:** that scratch run printed the
   harness's `full_cagr`/`full_dd` (train+forward): 32.01/−23.03 vs the base's 26.69/−23.03. The
   orchestrator has seen a full-window aggregate, so a gate of corerearm is NOT a clean forward
   test. Treat it like froth: it needs post-2026-09 data, or an owner decision.

0. **Loop-26 outcome** (no promotion): breakout magnitude (`strat_l26b_breakmag`, bm_w .2 /
   bm_lb 9) is the best forward-DD line found — fwd 18.25/−14.32, calmar 1.27 vs the champion's
   1.05 — but −3.3pp forward CAGR fails the CAGR-first rule. If the user ever weights DD more,
   it is the ready alternative. Nifty 500 DD controls (corrspike, xuniconfirm) are dead; the
   Nifty 500 book's forward DD gap (−25.7 vs −20.5) is still open.
1. **Nifty 500 with a drawdown control**: the Nifty 500 regime_ma-24 cell has the forward
   CAGR (22.8%) but a −25.7% forward DD (worse than its bench). A regime or exposure rule that
   cuts that DD could make it pass the trade-off. Its ledger: `.cache/strategy_lab/l25_dA_results.tsv`.
2. **Book size is CLOSED at 25 names**: 20–24 is a train plateau (32–33%) but the gated
   top-22 cell read fwd 20.65/−18.74 (−0.94pp CAGR vs the champion) — the fourth gate where
   a more concentrated book lost forward CAGR.
3. Rank channels that are NOT the V-recovery axis (ddquality/trmom lost forward; gapdrift on
   the new champion lowers train CAGR).
4. Stops are dead on the fresh-print book; concentration below 20 names is a train artifact.
5. Data backlog: NSE bhavcopy (survivorship) — every result here is inflated by it.

## Loop log

- L29 (2026-09-27 01:51:46–02:37:55 IST by `date`, scheduled NIGHT routine; close-out began 02:36:58, 45 elapsed min): 10 designer
  rounds (A exposure, B Nifty 500 DD, C changed-base legacy tilts, D/F/H/I random nulls, E core-satellite, G PIT liquid core,
  J liquidity-rank climb) + audit + orchestrator neighbour/null runs; 21 files, 238 trial rows; 1 gated (liqclimb, fwd −4.30pp);
  champion unchanged.
- L28 (2026-09-27 00:02–00:52 IST by `date`, routine manual test fire; close-out began at 00:47:33, 45 elapsed min): 4 designers in 2 rounds
  (exposure A/C, book construction B, entry quality D) + 1 orchestrator file, 11 mechanism files, 146 trial rows; 2 gated:
  corrdiv (fwd −3.50pp CAGR) and upvolnz (fwd DD 6.01pp deeper); champion unchanged.
- L27 (2026-09-26 22:43–23:43 IST, 60 min, routine test fire): 3 designers + 1 short round + 3 orchestrator files, 15 mechanism files,
  ~150 trials; 2 gated: CS spread (fails fwd CAGR −3.23pp) and froth (passes all checks — crown REVOKED
  for forward contamination, see lead 00); champion unchanged.

- L22 (2026-09-26, 10 min): first realistic loop; 5 execution-aware tilts, none kept.
- L23 (2026-09-26, 40 min): harness v2 (blind/robust/noise/gate); 8 mechanisms,
  126 trials; 4 candidates gated (ddquality, liqconfirm, liqdq, liqramp), all failed
  forward dominance; champion unchanged. Gate fixes: deflation counts every ledger;
  footprint counts exposure changes.
- L24 (2026-09-26, 30 min): risk policy moved into training (book size, weights,
  holds, daily-path stops); 33 trials; 2 gated (top-15 inverse-vol on the champion and on
  liqconfirm), both lost forward CAGR; stops dead; champion unchanged.
- L25 (2026-09-26, 30 min): **NEW CHAMPION** liqconfirm + top 25 inverse-vol (fwd
  21.58/−20.47 vs 20.63/−21.65; train 30.09/−17.22); Nifty 500 searched (84 trials; best cell
  gated, fwd 22.82/−25.65 fails the trade-off); gap-drift dead on the new base; top-22 book
  gated, fwd 20.65/−18.74 fails; 4 gates, 1 pass.
- L26 (2026-09-26, 30 min): 4 mechanisms (2 Nifty 500 DD controls, 2 rank tilts), 43 trials,
  1 gated (breakout magnitude: fwd 18.25/−14.32, −3.3pp CAGR, fails); champion unchanged.
