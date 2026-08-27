#!/usr/bin/env python3
"""Find the "N" continuation pattern riding a rising 10 EMA.

The shape, read left to right on a daily chart:

        B          D          A  swing low the impulse starts from
       /\         /           B  impulse high
      /  \       /            C  pullback low - a HIGHER low than A, resting on the 10 EMA
     /    \     /             D  today: price turning back up off C
    A      C___/

Three legs. An impulse up (A to B), a partial pullback that holds the rising 10 EMA (B to C),
and a resumption (C to D). The pullback making a higher low is what separates an N from a V
or a failed breakout, and the 10 EMA is what the pullback is expected to lean on.

Each leg is located by swing decomposition inside the last --window bars: B is the highest
high (leaving --min-tail bars of room after it), A is the lowest low before B, C is the
lowest low after B. Conditions are then applied to the geometry:

    impulse     (B - A) / A >= --min-impulse
    pullback    retracement (B - C) / (B - A) within --min/--max-retrace
                C > A, and C's low came within --ema-touch of the 10 EMA
                without closing more than --ema-break below it
    resumption  C was 1..--max-bars-since-c bars ago, price is now >= --min-resume above C
                and not more than --max-extension above B
    trend       10 EMA rising over the last --slope-bars, price above it now

Usage:
    python scripts/n_pattern.py
    python scripts/n_pattern.py --universe nifty500 --min-impulse 0.10
    python scripts/n_pattern.py --window 50 --max-retrace 0.5 --no-market-cap
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from screener import CRORE, fetch_market_caps  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_GLOB = str(REPO_ROOT / "data" / "ohlcv" / "daily" / "**" / "*.parquet")
UNIVERSE = REPO_ROOT / "data" / "universe" / "nse_universe.parquet"
CACHE = REPO_ROOT / ".cache" / "screener"


def build_windows(daily: pl.DataFrame, span: int, window: int) -> pl.DataFrame:
    """Per symbol: the last `window` bars as list columns, plus liquidity context."""
    bars = daily.sort("symbol", "date").with_columns(
        pl.col("close").ewm_mean(span=span, adjust=False).over("symbol").alias("ema")
    )
    return (
        bars.group_by("symbol")
        .agg(
            pl.len().alias("bars"),
            pl.col("date").last().alias("date"),
            pl.col("close").last().alias("close"),
            pl.col("ema").last().alias("ema_now"),
            pl.col("high").tail(window).alias("h"),
            pl.col("low").tail(window).alias("l"),
            pl.col("close").tail(window).alias("c"),
            pl.col("ema").tail(window).alias("e"),
            ((pl.col("close") * pl.col("volume")).tail(20).mean() / CRORE).alias("turnover_cr"),
        )
        .filter((pl.col("bars") > window + 60) & (pl.col("h").list.len() == window))
    )


def decompose(frame: pl.DataFrame, window: int, min_tail: int) -> pl.DataFrame:
    """Locate A (swing low), B (impulse high) and C (pullback low) inside each window."""
    head = pl.col("h").list.slice(0, window - min_tail)  # B must leave room for C and D

    frame = frame.with_columns(bi=head.list.arg_max())
    frame = frame.with_columns(
        b_high=pl.col("h").list.get(pl.col("bi")),
        pre=pl.col("l").list.slice(0, pl.col("bi")),          # strictly before B
        post=pl.col("l").list.slice(pl.col("bi") + 1),        # strictly after B
    )
    # An empty `pre` means the window opens on its own high: no impulse to measure.
    frame = frame.filter(pl.col("pre").list.len() > 0, pl.col("post").list.len() > 0)

    return frame.with_columns(
        a_low=pl.col("pre").list.min(),
        ai=pl.col("pre").list.arg_min(),
        c_low=pl.col("post").list.min(),
        ci=pl.col("bi") + 1 + pl.col("post").list.arg_min(),
    ).with_columns(
        leg1_bars=pl.col("bi") - pl.col("ai"),
        pullback_bars=pl.col("ci") - pl.col("bi"),
        bars_since_c=(window - 1) - pl.col("ci"),
        ema_at_c=pl.col("e").list.get(pl.col("ci")),
        close_at_c=pl.col("c").list.get(pl.col("ci")),
        ema_slope=(pl.col("e").list.last() / pl.col("e").list.get(-1 - pl.col("slope_bars")) - 1),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--universe", default="nse_all")
    parser.add_argument("--ema-span", type=int, default=10, help="the yellow average (default 10)")
    parser.add_argument("--window", type=int, default=40, help="bars searched for the N")
    parser.add_argument("--min-tail", type=int, default=3, help="bars that must follow B")
    parser.add_argument("--min-impulse", type=float, default=0.07, help="leg A->B, default 7%%")
    parser.add_argument("--max-leg1-bars", type=int, default=15,
                        help="A->B must be a recent thrust, not the whole window (default 15)")
    parser.add_argument("--min-pullback-bars", type=int, default=2,
                        help="B->C must be a real dip, not a single-day wick (default 2)")
    parser.add_argument("--max-pullback-bars", type=int, default=12)
    parser.add_argument("--min-retrace", type=float, default=0.15)
    parser.add_argument("--max-retrace", type=float, default=0.70)
    parser.add_argument("--ema-touch", type=float, default=0.03,
                        help="C's low must come within this of the EMA (default 3%%)")
    parser.add_argument("--ema-break", type=float, default=0.03,
                        help="C must not close more than this below the EMA (default 3%%)")
    parser.add_argument("--max-bars-since-c", type=int, default=6)
    parser.add_argument("--min-resume", type=float, default=0.01,
                        help="price must be this far above C (default 1%%)")
    parser.add_argument("--max-extension", type=float, default=0.05,
                        help="and no more than this above B (default 5%%)")
    parser.add_argument("--slope-bars", type=int, default=5, help="EMA slope measured over N bars")
    parser.add_argument("--turnover-min", type=float, default=5.0, help="rupees crore")
    parser.add_argument("--market-cap-min", type=float, default=1000.0, help="rupees crore")
    parser.add_argument("--no-market-cap", action="store_true")
    parser.add_argument("--charts", type=int, default=0,
                        help="render this many top hits to a PNG for visual verification")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    universe = pl.read_parquet(UNIVERSE)
    if args.universe != "nse_all":
        universe = universe.filter(pl.col(f"in_{args.universe}"))

    daily = (
        pl.scan_parquet(DAILY_GLOB, hive_partitioning=True)
        .select("symbol", "date", "open", "high", "low", "close", "volume")
        .filter(pl.col("symbol").is_in(universe["symbol"].to_list()))
        .collect()
    )
    as_of = daily["date"].max()
    print(f"Universe {args.universe}: {universe.height} symbols | panel through {as_of}\n")

    frame = build_windows(daily, args.ema_span, args.window)
    frame = frame.filter(pl.col("turnover_cr") > args.turnover_min)
    print(f"1. Liquid enough (turnover > {args.turnover_min:g} cr): {frame.height} symbols")

    frame = frame.with_columns(pl.lit(args.slope_bars).alias("slope_bars"))
    frame = decompose(frame, args.window, args.min_tail)
    print(f"2. Windows with a usable A-B-C decomposition: {frame.height} symbols")

    frame = frame.with_columns(
        impulse=(pl.col("b_high") / pl.col("a_low") - 1),
        retrace=((pl.col("b_high") - pl.col("c_low")) / (pl.col("b_high") - pl.col("a_low"))),
        resume=(pl.col("close") / pl.col("c_low") - 1),
        vs_b=(pl.col("close") / pl.col("b_high") - 1),
        c_to_ema=(pl.col("c_low") / pl.col("ema_at_c") - 1),
        c_close_vs_ema=(pl.col("close_at_c") / pl.col("ema_at_c") - 1),
    )

    stages = [
        (f"impulse >= {args.min_impulse:.0%}", pl.col("impulse") >= args.min_impulse),
        (f"A->B within {args.max_leg1_bars} bars", pl.col("leg1_bars") <= args.max_leg1_bars),
        (f"pullback {args.min_pullback_bars}-{args.max_pullback_bars} bars",
         pl.col("pullback_bars").is_between(args.min_pullback_bars, args.max_pullback_bars)),
        ("higher low (C > A)", pl.col("c_low") > pl.col("a_low")),
        (f"retrace {args.min_retrace:.0%}-{args.max_retrace:.0%}",
         pl.col("retrace").is_between(args.min_retrace, args.max_retrace)),
        (f"C rested on the {args.ema_span} EMA",
         (pl.col("c_to_ema") <= args.ema_touch) & (pl.col("c_close_vs_ema") >= -args.ema_break)),
        (f"C was 1-{args.max_bars_since_c} bars ago",
         pl.col("bars_since_c").is_between(1, args.max_bars_since_c)),
        (f"resumed >= {args.min_resume:.0%} off C", pl.col("resume") >= args.min_resume),
        (f"not > {args.max_extension:.0%} above B", pl.col("vs_b") <= args.max_extension),
        (f"{args.ema_span} EMA rising", pl.col("ema_slope") > 0),
        ("price above the EMA", pl.col("close") > pl.col("ema_now")),
    ]
    print("\n3. N-pattern geometry")
    for label, condition in stages:
        frame = frame.filter(condition)
        print(f"   after {label:<32} {frame.height:>5} symbols")

    if not args.no_market_cap and frame.height:
        print(f"\n4. Market cap > {args.market_cap_min:,.0f} crore")
        caps = fetch_market_caps(frame["symbol"].to_list())
        frame = frame.join(caps, on="symbol", how="inner").filter(
            pl.col("market_cap_cr") > args.market_cap_min
        )
        print(f"   after market cap                   {frame.height:>5} symbols")
    else:
        frame = frame.with_columns(pl.lit(None, dtype=pl.Float64).alias("market_cap_cr"))

    result = (
        frame.join(universe.select("symbol", "company_name"), on="symbol", how="left")
        .sort("impulse", descending=True)
        .select(
            "symbol", "company_name", "market_cap_cr", "close",
            pl.col("a_low").alias("A"), pl.col("b_high").alias("B"), pl.col("c_low").alias("C"),
            (pl.col("impulse") * 100).alias("impulse_pct"),
            (pl.col("retrace") * 100).alias("retrace_pct"),
            (pl.col("resume") * 100).alias("off_C_pct"),
            (pl.col("vs_b") * 100).alias("vs_B_pct"),
            (pl.col("c_to_ema") * 100).alias("C_vs_ema_pct"),
            (pl.col("ema_slope") * 100).alias("ema_slope_pct"),
            "leg1_bars", "pullback_bars", "bars_since_c", "turnover_cr",
        )
    )

    print(f"\n{'=' * 78}\n{result.height} symbols show the N pattern on a rising "
          f"{args.ema_span} EMA (as of {as_of})\n{'=' * 78}")
    if result.height:
        with pl.Config(tbl_rows=60, tbl_width_chars=215, fmt_str_lengths=24):
            print(result.with_columns(pl.col(pl.Float64).round(1)))
        print("\nA/B/C are the swing prices. impulse_pct is leg A->B, retrace_pct how much of it "
              "gave back,\noff_C_pct the bounce so far, vs_B_pct where price sits against the "
              "impulse high (negative = still under it).")
    out = Path(args.out) if args.out else CACHE / f"n_pattern_{dt.date.today()}.csv"
    result.write_csv(out)
    print(f"\nWrote {out}")

    if args.charts and result.height:
        chart_path = out.with_suffix(".png")
        render_charts(result, daily, args.ema_span, args.window, args.charts, chart_path)
        print(f"Wrote {chart_path}")
    return 0


# --------------------------------------------------------------------------- charting


def render_charts(result: pl.DataFrame, daily: pl.DataFrame, span: int, window: int,
                  count: int, path: Path) -> None:
    """Candlestick grid of the top hits, so the geometry can be eyeballed, not trusted."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    symbols = result["symbol"].to_list()[:count]
    cols = 3
    rows = (len(symbols) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(6.2 * cols, 3.6 * rows), facecolor="#0e1117")
    axes = axes.flatten() if len(symbols) > 1 else [axes]

    for ax, symbol in zip(axes, symbols):
        bars = (
            daily.filter(pl.col("symbol") == symbol).sort("date")
            .with_columns(pl.col("close").ewm_mean(span=span, adjust=False).alias("ema"))
            .tail(window + 20)
        )
        row = result.filter(pl.col("symbol") == symbol).row(0, named=True)
        o, h, l, c = (bars[k].to_numpy() for k in ("open", "high", "low", "close"))
        x = range(len(bars))

        ax.set_facecolor("#0e1117")
        for i in x:
            up = c[i] >= o[i]
            colour = "#26a69a" if up else "#ef5350"
            ax.plot([i, i], [l[i], h[i]], color=colour, linewidth=0.8, zorder=2)
            ax.add_patch(plt.Rectangle((i - 0.32, min(o[i], c[i])), 0.64,
                                       max(abs(c[i] - o[i]), 1e-9), color=colour, zorder=3))
        ax.plot(x, bars["ema"].to_numpy(), color="#ffd54f", linewidth=1.4, zorder=4)

        for level, label, colour in ((row["A"], "A", "#4fc3f7"), (row["B"], "B", "#ff8a65"),
                                     (row["C"], "C", "#ba68c8")):
            ax.axhline(level, color=colour, linewidth=0.8, linestyle="--", alpha=0.75, zorder=1)
            ax.text(len(bars) + 0.4, level, label, color=colour, fontsize=9, va="center")

        ax.set_title(f"{symbol}   impulse {row['impulse_pct']:.0f}% in {row['leg1_bars']}d  "
                     f"retrace {row['retrace_pct']:.0f}% over {row['pullback_bars']}d  "
                     f"off C {row['off_C_pct']:.1f}%  C {row['bars_since_c']}d ago",
                     color="#e0e0e0", fontsize=9.5, pad=6)
        ax.tick_params(colors="#666", labelsize=7)
        for spine in ax.spines.values():
            spine.set_color("#333")
        ax.grid(color="#1e242e", linewidth=0.6, zorder=0)
        ax.set_xlim(-1, len(bars) + 3)

    for ax in axes[len(symbols):]:
        ax.set_visible(False)
    fig.suptitle(f"N pattern on a rising {span} EMA — yellow line is the EMA, "
                 "dashed levels are the A/B/C swings",
                 color="#e0e0e0", fontsize=12, y=0.995)
    fig.tight_layout()
    fig.savefig(path, dpi=115, facecolor="#0e1117")
    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
