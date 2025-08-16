import yfinance as yf
import pandas as pd

# Parameters
ticker = "BTC-USD"
interval = "1m"  # "1m", "5m", "15m"
lookback_days = 2
ema_fast = 9
ema_slow = 21
capital = 1_000  # starting capital in USD
tp_usd = 50     # Take profit in USD
sl_usd = 100       # Stop loss in USD

# Fetch intraday data
df = yf.Ticker(ticker).history(period=f"{lookback_days}d", interval=interval)
df.dropna(inplace=True)

# Calculate EMAs
df["EMA9"] = df["Close"].ewm(span=ema_fast, adjust=False).mean()
df["EMA21"] = df["Close"].ewm(span=ema_slow, adjust=False).mean()

# Calculate VWAP
df["CumVol"] = df["Volume"].cumsum()
df["CumPV"] = (df["Close"] * df["Volume"]).cumsum()
df["VWAP"] = df["CumPV"] / df["CumVol"]

# Generate EMA crossover signals
df["Signal"] = 0
df.loc[df["EMA9"] > df["EMA21"], "Signal"] = 1   # Long bias
df.loc[df["EMA9"] < df["EMA21"], "Signal"] = -1  # Short bias

trades = []
position = None
entry_price = 0
entry_time = None
units = 0

for i in range(len(df)):
    row = df.iloc[i]
    current_time = df.index[i]
    signal = row["Signal"]

    if position is None:
        # Apply VWAP filter
        if signal == 1 and row["Close"] > row["VWAP"]:
            position = "long"
            entry_price = row["Close"]
            entry_time = current_time
            units = capital / entry_price
        elif signal == -1 and row["Close"] < row["VWAP"]:
            position = "short"
            entry_price = row["Close"]
            entry_time = current_time
            units = capital / entry_price

    else:
        # Calculate unrealized PnL
        if position == "long":
            pnl_usd = (row["Close"] - entry_price) * units
        else:
            pnl_usd = (entry_price - row["Close"]) * units

        # Exit criteria
        hit_tp = pnl_usd >= tp_usd
        hit_sl = pnl_usd <= -sl_usd
        ema_flip = (position == "long" and signal == -1) or (position == "short" and signal == 1)

        if hit_tp or hit_sl or ema_flip:
            trades.append({
                "Entry Time": entry_time,
                "Exit Time": current_time,
                "Direction": position,
                "Entry Price": entry_price,
                "Exit Price": row["Close"],
                "Exit Reason": "TP" if hit_tp else "SL" if hit_sl else "EMA Flip",
                "PnL_USD": pnl_usd
            })
            position = None

# Convert to DataFrame
trades_df = pd.DataFrame(trades)
total_pnl = trades_df["PnL_USD"].sum()

import yfinance as yf
import pandas as pd

# Parameters
ticker = "BTC-USD"
interval = "1m"  # "1m", "5m", "15m"
lookback_days = 2
ema_fast = 9
ema_slow = 21
capital = 10000  # starting capital in USD
tp_usd = 100      # Take profit in USD
sl_usd = 50       # Stop loss in USD

# Fetch intraday data
df = yf.Ticker(ticker).history(period=f"{lookback_days}d", interval=interval)
df.dropna(inplace=True)

# Calculate EMAs
df["EMA9"] = df["Close"].ewm(span=ema_fast, adjust=False).mean()
df["EMA21"] = df["Close"].ewm(span=ema_slow, adjust=False).mean()

# Calculate VWAP
df["CumVol"] = df["Volume"].cumsum()
df["CumPV"] = (df["Close"] * df["Volume"]).cumsum()
df["VWAP"] = df["CumPV"] / df["CumVol"]

# Generate EMA crossover signals
df["Signal"] = 0
df.loc[df["EMA9"] > df["EMA21"], "Signal"] = 1   # Long bias
df.loc[df["EMA9"] < df["EMA21"], "Signal"] = -1  # Short bias

trades = []
position = None
entry_price = 0
entry_time = None
units = 0

for i in range(len(df)):
    row = df.iloc[i]
    current_time = df.index[i]
    signal = row["Signal"]

    if position is None:
        # Apply VWAP filter
        if signal == 1 and row["Close"] > row["VWAP"]:
            position = "long"
            entry_price = row["Close"]
            entry_time = current_time
            units = capital / entry_price
        elif signal == -1 and row["Close"] < row["VWAP"]:
            position = "short"
            entry_price = row["Close"]
            entry_time = current_time
            units = capital / entry_price

    else:
        # Calculate unrealized PnL
        if position == "long":
            pnl_usd = (row["Close"] - entry_price) * units
        else:
            pnl_usd = (entry_price - row["Close"]) * units

        # Exit criteria
        hit_tp = pnl_usd >= tp_usd
        hit_sl = pnl_usd <= -sl_usd
        ema_flip = (position == "long" and signal == -1) or (position == "short" and signal == 1)

        if hit_tp or hit_sl or ema_flip:
            trades.append({
                "Entry Time": entry_time,
                "Exit Time": current_time,
                "Direction": position,
                "Entry Price": entry_price,
                "Exit Price": row["Close"],
                "Exit Reason": "TP" if hit_tp else "SL" if hit_sl else "EMA Flip",
                "PnL_USD": pnl_usd
            })
            position = None

# Convert to DataFrame
trades_df = pd.DataFrame(trades)
total_pnl = trades_df["PnL_USD"].sum()

trades_df.to_csv("trades.csv", index=False)
print(f"Total PnL: ${total_pnl:,.2f}")
