"""The Connors RSI(2) 'dip buy', implemented exactly as the tweet states it.

Rules under test (@MrMilkTrading, 2026-08-30):
  1. RSI(2) on daily closes
  2. Buy the close when RSI(2) < 10 and price > 200 day SMA
  3. Sell the close when RSI(2) > 70, or after 10 sessions, whichever comes first
  4. Long only. ES and NQ, 1 contract each. No stop.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from indicators import sma, sma_rsi, wilder_rsi


@dataclass(frozen=True)
class Contract:
    """One futures contract, with a cost model rich enough for two markets.

    US index futures are dominated by flat commission plus tick slippage. Indian
    index futures are dominated by *percentage* costs - STT alone is 0.02% of the
    sell side - so both a flat and a proportional term are needed.
    """

    name: str
    point_value: float            # currency per index point (US$ or INR)
    slippage_points: float = 0.25  # points given up on each side of the trade
    commission_rt: float = 4.0     # flat cost per round turn
    pct_cost_rt: float = 0.0       # taxes and fees as a fraction of notional, round turn
    carry_pct_yr: float = 0.0      # long-futures cost of carry (r - q), annualised
    currency: str = "USD"
    label: str = ""

    @property
    def cost_per_trade(self) -> float:
        """Fixed component only - the flat part of a round turn."""
        return self.commission_rt + 2 * self.slippage_points * self.point_value

    def cost(self, notional: float, bars_held: int = 0) -> float:
        """Total round-turn cost, including proportional taxes and carry.

        `carry_pct_yr` is only non-zero when the backtest runs on a *cash* index
        as a stand-in for futures: a long futures position gives up the basis as
        it converges, which a cash index series does not show.
        """
        carry = self.carry_pct_yr * (bars_held / 252.0) * notional
        return self.cost_per_trade + self.pct_cost_rt * notional + carry


# --- US: costs as claimed in the source post ($4 round turn, 1 tick a side) ---
ES = Contract("ES", point_value=50.0, slippage_points=0.25, label="E-mini S&P 500")
NQ = Contract("NQ", point_value=20.0, slippage_points=0.25, label="E-mini Nasdaq 100")

# --- India: NSE lot sizes and the statutory cost stack ---
# STT 0.02% (sell side) + exchange charge 0.00173%/side + SEBI fee + stamp duty
# ~= 0.0257% of notional per round turn, plus about Rs 47 of brokerage and GST.
# Backtested on the cash index, so the long-futures cost of carry is charged
# explicitly: repo ~6.5% less a ~1.3% dividend yield.
INDIA_PCT_COST = 0.000257
INDIA_CARRY = 0.052

NIFTY = Contract("NIFTY", point_value=75.0, slippage_points=1.0, commission_rt=47.0,
                 pct_cost_rt=INDIA_PCT_COST, carry_pct_yr=INDIA_CARRY,
                 currency="INR", label="Nifty 50 futures (lot 75)")
BANKNIFTY = Contract("BANKNIFTY", point_value=30.0, slippage_points=3.0, commission_rt=47.0,
                     pct_cost_rt=INDIA_PCT_COST, carry_pct_yr=INDIA_CARRY,
                     currency="INR", label="Nifty Bank futures (lot 30)")


@dataclass
class Params:
    rsi_period: int = 2
    rsi_entry: float = 10.0     # buy when RSI(2) < 10
    rsi_exit: float = 70.0      # sell when RSI(2) > 70
    sma_period: int = 200       # price must be above the 200 day SMA
    max_hold: int = 10          # ...or after 10 sessions, whichever comes first
    entry_on: str = "close"     # "close" (as stated) or "next_open" (executable variant)
    rsi_kind: str = "wilder"    # "wilder" or "sma"
    stop_pct: float | None = None  # the rules say no stop; used for sensitivity tests


def compute_signals(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    out = df.copy()
    rsi_fn = wilder_rsi if p.rsi_kind == "wilder" else sma_rsi
    out["rsi"] = rsi_fn(out["close"], p.rsi_period)
    out["sma"] = sma(out["close"], p.sma_period)
    out["long_ok"] = out["close"] > out["sma"]
    out["entry_signal"] = (out["rsi"] < p.rsi_entry) & out["long_ok"]
    out["exit_signal"] = out["rsi"] > p.rsi_exit
    return out


def run(df: pd.DataFrame, contract: Contract, p: Params | None = None) -> pd.DataFrame:
    """Return one row per closed trade."""
    p = p or Params()
    d = compute_signals(df, p).reset_index(drop=True)

    trades = []
    in_pos = False
    entry_i = entry_px = None

    for i in range(len(d)):
        row = d.loc[i]
        if np.isnan(row["sma"]) or np.isnan(row["rsi"]):
            continue

        if in_pos:
            bars_held = i - entry_i
            reason = None
            if row["exit_signal"]:
                reason = "rsi_target"
            elif bars_held >= p.max_hold:
                reason = "time_stop"
            if reason:
                exit_px = row["close"]
                gross_pts = exit_px - entry_px
                hold = d.loc[entry_i + 1 : i]
                notional = entry_px * contract.point_value
                cost = contract.cost(notional, bars_held)
                trades.append(
                    {
                        "entry_date": d.loc[entry_i, "date"],
                        "exit_date": row["date"],
                        "entry_px": entry_px,
                        "exit_px": exit_px,
                        "bars_held": bars_held,
                        "exit_reason": reason,
                        "gross_pts": gross_pts,
                        "gross_usd": gross_pts * contract.point_value,
                        "cost_usd": cost,
                        "net_usd": gross_pts * contract.point_value - cost,
                        "entry_rsi": d.loc[entry_i, "rsi"],
                        # notional-normalised return: the only way to compare a
                        # 1-contract P&L across an index that has 10x'd
                        "ret_pct": gross_pts / entry_px,
                        "notional_usd": notional,
                        # how far underwater the trade went - matters a lot with no stop
                        "mae_pct": (hold["low"].min() - entry_px) / entry_px if len(hold) else 0.0,
                        "mfe_pct": (hold["high"].max() - entry_px) / entry_px if len(hold) else 0.0,
                    }
                )
                in_pos = False
                entry_i = entry_px = None

        if not in_pos and row["entry_signal"]:
            # one contract at a time: a fresh signal while flat opens the trade
            if p.entry_on == "close":
                in_pos, entry_i, entry_px = True, i, row["close"]
            elif i + 1 < len(d):
                in_pos, entry_i, entry_px = True, i + 1, d.loc[i + 1, "open"]

    tr = pd.DataFrame(trades)
    if not tr.empty:
        tr["symbol"] = contract.name
        tr["year"] = pd.to_datetime(tr["exit_date"]).dt.year
    return tr


def metrics(trades: pd.DataFrame, label: str = "") -> dict:
    if trades.empty:
        return {"label": label, "trades": 0}
    net = trades["net_usd"]
    wins, losses = net[net > 0], net[net <= 0]
    gross_win, gross_loss = wins.sum(), -losses.sum()
    equity = net.cumsum()
    drawdown = equity - equity.cummax()

    return {
        "label": label,
        "trades": len(trades),
        "win_rate": len(wins) / len(net),
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else np.inf,
        "net_usd": net.sum(),
        "avg_trade": net.mean(),
        "avg_win": wins.mean() if len(wins) else 0.0,
        "avg_loss": losses.mean() if len(losses) else 0.0,
        "best": net.max(),
        "worst": net.min(),
        "max_dd_usd": drawdown.min(),
        "avg_bars": trades["bars_held"].mean(),
        "first": pd.to_datetime(trades["entry_date"]).min().date(),
        "last": pd.to_datetime(trades["exit_date"]).max().date(),
    }


def combine(trade_frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Merge per-instrument trades into one portfolio, ordered by exit date."""
    frames = [t for t in trade_frames if not t.empty]
    if not frames:
        return pd.DataFrame()
    allt = pd.concat(frames, ignore_index=True)
    return allt.sort_values(["exit_date", "symbol"]).reset_index(drop=True)
