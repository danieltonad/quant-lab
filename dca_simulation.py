import yfinance as yf
import pandas as pd
from datetime import datetime

def simulate_dca(symbol, start_date, end_date, capital_per_interval, interval='1d', price: str ="Open"):
    # Download historical data
    data = yf.download(symbol, start=start_date, end=end_date, interval=interval, progress=False, auto_adjust=True)

    if data.empty:
        return "No data found for the given parameters."

    data = data.dropna(subset=[price])

    total_quantity = 0
    total_spent = 0

    for date, row in data.iterrows():
        close_price = row[price]
        if close_price == 0:
            continue
        qty = capital_per_interval / close_price
        total_quantity += qty
        total_spent += capital_per_interval

    # Final stock price to calculate current value
    final_price = data[price].iloc[-1]
    current_value = total_quantity * final_price
    pnl = current_value - total_spent
    avg_price = total_spent / total_quantity if total_quantity else 0

    return {
        'symbol': symbol,
        'average_price': round(avg_price, 2),
        'quantity_acquired': round(total_quantity, 4),
        'amount_spent': round(total_spent, 2),
        'final_price': round(final_price, 2),
        'current_value': round(current_value, 2),
        'PnL': round(pnl, 2)
    }
if __name__ == "__main__":
    # Example usage
    symbol = 'AAPL'
    start_date = '2020-01-01'
    end_date = '2023-01-01'
    capital_per_interval = 100  # Amount to invest at each interval

    result = simulate_dca(symbol, start_date, end_date, capital_per_interval)
    print(result)