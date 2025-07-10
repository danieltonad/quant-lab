import yfinance as yf
import pandas as pd
from datetime import datetime


def simulate_dca(symbol, start_date, end_date, capital_per_interval, interval='1d'):
    ticker = yf.Ticker(symbol)
    data = ticker.history(start=start_date, end=end_date, interval=interval)

    if data.empty:
        return f"No data available for {symbol} in the given range or interval."

    if 'Open' not in data.columns or 'Close' not in data.columns:
        return "'Open' or 'Close' price missing from data."

    # Drop rows with missing Open/Close prices
    data = data.dropna(subset=['Open', 'Close'])

    total_quantity = 0
    total_spent = 0

    for _, row in data.iterrows():
        open_price = row['Open']
        if open_price <= 0:
            continue
        qty = capital_per_interval / open_price
        total_quantity += qty
        total_spent += capital_per_interval

    final_price = data['Close'].iloc[-1]
    last_open_price = data['Open'].iloc[-1]
    current_value = total_quantity * final_price
    pnl = current_value - total_spent
    avg_price = total_spent / total_quantity if total_quantity else 0

    return {
        'symbol': symbol,
        'interval': interval,
        'average_price': round(avg_price, 2),
        'quantity_acquired': round(total_quantity, 4),
        'amount_spent': round(total_spent, 2),
        'final_price': round(final_price, 2),
        'last_open_price': round(last_open_price, 2),
        'current_value': round(current_value, 2),
        'capital_per_interval': capital_per_interval,
        'start_date': start_date,
        'end_date': end_date,
        'PnL': round(pnl, 2)
    }


def simulate_dca_buy_only(symbol, start_date, end_date, daily_capital, interval='1d'):
    # Fetch daily historical prices
    ticker = yf.Ticker(symbol)
    data = ticker.history(start=start_date, end=end_date, interval=interval)

    if data.empty:
        return f"No data available for {symbol} in the given range."

    # Ensure required columns are present and valid
    data = data.dropna(subset=['Open', 'Close'])
    data = data[data['Open'] > 0]

    total_quantity = 0
    total_spent = 0

    # Simulate daily DCA buying
    for _, row in data.iterrows():
        qty = daily_capital / row['Open']
        total_quantity += qty
        total_spent += daily_capital

    # Final stats
    final_price = data['Close'].iloc[-1]
    current_value = total_quantity * final_price
    pnl = current_value - total_spent
    avg_price = total_spent / total_quantity if total_quantity else 0

    return {
        'symbol': symbol,
        'days_invested': len(data),
        'average_price': round(avg_price, 2),
        'quantity_acquired': round(total_quantity, 4),
        'amount_spent': round(total_spent, 2),
        'final_price': round(final_price, 2),
        'current_value': round(current_value, 2),
        'PnL': round(pnl, 2),
        'return_pct': round((pnl / total_spent) * 100, 2) if total_spent else 0,
        'start_date': start_date,
        'end_date': end_date
    }

    
def save_dict_to_text_file(data, filename):
    with open(filename, 'w') as file:
        for key, value in data.items():
            if isinstance(value, float):
                value = f"{value:,.2f}"
            file.write(f"{key}: {value}\n")    
    

if __name__ == "__main__":
    # Example usage
    symbol = 'MAG'
    start_date = '2020-07-09'
    end_date = '2025-07-09'
    capital_per_interval = 50  # Amount to invest at each interval

    result = simulate_dca_buy_only(symbol, start_date, end_date, capital_per_interval)
    # print(result)
    save_dict_to_text_file(result, f"./data/{symbol}_dca_simulation.txt")