import yfinance as yf
import pandas as pd

# === CONFIGURATION ===
TICKER_FILE = "tickers.txt"   # Text file with one ticker per line
OUTPUT_CSV = "hve_analysis.csv"
INTERVAL = "1d"  # or '1wk' for weekly

# === FUNCTION TO PROCESS ONE TICKER ===
def analyze_stock(ticker, interval="1d"):
    try:
        data = yf.Ticker(ticker)
        data = data.history(interval=interval, period="max")
        if data.empty or 'Volume' not in data.columns:
            print(f"[!] No data for {ticker}")
            return None
        
        data.dropna(subset=["Open", "Close", "Volume"], inplace=True)
        
        # Find Highest Volume Ever (HVE)
        hve_row = data[data["Volume"] == data["Volume"].max()]
        if hve_row.empty:
            return None
        
        hve_date = hve_row.index[0]
        hve_close = hve_row["Close"].values[0]
        
        # Get data after HVE day
        post_hve_data = data[data.index > hve_date]
        if post_hve_data.empty:
            return None
        
        highest_close_after = post_hve_data["Close"].max()
        
        return {
            "Stock": ticker,
            "HVE_Date": hve_date.strftime("%Y-%m-%d"),
            "Close_on_HVE": round(hve_close, 2),
            "Highest_Close_After_HVE": round(highest_close_after, 2)
        }
        
    except Exception as e:
        print(f"Error processing {ticker}: {e}")
        return None

# === MAIN SCRIPT ===
def main():
    # Load tickers
    with open(TICKER_FILE, "r") as f:
        tickers = {line.strip().upper() for line in f if line.strip()}
    
    results = []
    for ticker in tickers:
        print(f"Processing {ticker}...")
        result = analyze_stock(ticker, interval=INTERVAL)
        if result:
            results.append(result)
    
    # Export to CSV
    if results:
        df_out = pd.DataFrame(results)
        df_out.to_csv(OUTPUT_CSV, index=False)
        print(f"\n {len(results)} stocks exported to {OUTPUT_CSV}")
    else:
        print("No valid stocks found.")

if __name__ == "__main__":
    main()
