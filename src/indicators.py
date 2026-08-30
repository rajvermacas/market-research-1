"""Indicators used by the strategy, defined the way Connors defines them."""

import numpy as np
import pandas as pd


def wilder_rsi(close: pd.Series, period: int = 2) -> pd.Series:
    """Wilder's RSI - the definition used in 'Short Term Trading Strategies That Work'.

    Wilder smoothing is an EMA with alpha = 1/period, seeded with the simple
    average of the first `period` gains/losses.
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100.0 - 100.0 / (1.0 + rs)
    # avg_loss == 0 -> no down moves in the window -> RSI 100 (and 50 if flat)
    rsi = rsi.where(avg_loss != 0.0, np.where(avg_gain > 0.0, 100.0, 50.0))
    return rsi


def sma_rsi(close: pd.Series, period: int = 2) -> pd.Series:
    """RSI using simple moving averages of gains/losses (Cutler's RSI).

    Only used as a robustness check - some charting packages default to this.
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0).rolling(period).mean()
    loss = (-delta).clip(lower=0.0).rolling(period).mean()
    rs = gain / loss
    rsi = 100.0 - 100.0 / (1.0 + rs)
    return rsi.where(loss != 0.0, np.where(gain > 0.0, 100.0, 50.0))


def sma(close: pd.Series, period: int = 200) -> pd.Series:
    return close.rolling(period, min_periods=period).mean()
