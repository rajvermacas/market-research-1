"""Back-adjust Yahoo's stitched front-month futures series.

Yahoo's ES=F / NQ=F daily series switches to the next contract at expiry without
adjusting history, so each quarterly roll injects a price jump (typically +0.5%
to +1.5% in contango) that never happened to anyone holding a position. A
long-only strategy backtested on the raw series harvests those jumps as free
profit. This module removes them with a Panama (additive) back-adjustment.

The size of a roll gap is estimated as the part of the roll day's futures move
that the matching cash index does *not* explain.
"""

import numpy as np
import pandas as pd

ROLL_MONTHS = (3, 6, 9, 12)
# Expiry is the 3rd Friday; Yahoo's switch shows up in that week.
ROLL_WINDOW_DAYS = (13, 23)
MIN_GAP_PCT = 0.0025  # ignore ordinary futures/cash basis noise below 25 bps


def detect_rolls(fut_close: pd.Series, cash_close: pd.Series) -> pd.Series:
    """Return a Series of roll-day -> gap in price points."""
    joined = pd.DataFrame({"f": fut_close, "c": cash_close}).dropna()
    fut_ret = joined["f"].pct_change()
    cash_ret = joined["c"].pct_change()
    residual = fut_ret - cash_ret

    gaps = {}
    for (year, month), chunk in residual.groupby([residual.index.year, residual.index.month]):
        if month not in ROLL_MONTHS:
            continue
        window = chunk[
            (chunk.index.day >= ROLL_WINDOW_DAYS[0]) & (chunk.index.day <= ROLL_WINDOW_DAYS[1])
        ].dropna()
        if window.empty:
            continue
        day = window.abs().idxmax()
        if abs(window[day]) < MIN_GAP_PCT:
            continue
        prev_close = joined["f"].shift(1)[day]
        # points of the move not explained by the cash index = the contract switch
        gaps[day] = prev_close * window[day]
    return pd.Series(gaps, dtype=float).sort_index()


def back_adjust(df: pd.DataFrame, cash_close: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    """Panama back-adjustment: shift history so recent prices stay real.

    Returns the adjusted OHLC frame and the detected roll gaps.
    """
    gaps = detect_rolls(df["close"], cash_close)
    # cumulative adjustment applied to every bar strictly before each roll day
    offset = pd.Series(0.0, index=df.index)
    for day, gap in gaps.items():
        offset.loc[offset.index < day] += gap

    adjusted = df.copy()
    for col in ("open", "high", "low", "close"):
        if col in adjusted:
            adjusted[col] = adjusted[col] + offset
    return adjusted, gaps
