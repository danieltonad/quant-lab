import yfinance as yf
import pandas as pd
import os

# === CONFIGURATION ===
TICKER_FILE = "tickers.txt"   # Text file with one ticker per line
OUTPUT_CSV = "hve_analysis.csv"
INTERVAL = "1wk"  # or '1wk' for weekly


def format_ticker(asset: str):
    ticker = asset.split(":")[-1]
    if ticker.endswith("USD"):
        return f"{ticker[:-3]}-{ticker[-3:]}"
    elif ticker.endswith("USDT") or ticker.endswith("USDC"):
        return f"{ticker[:-4]}-{ticker[-4:-1]}"
    # stocks
    ticker = ticker.replace(".3S", "")
    ticker = ticker.replace(".3L", "")
    ticker = ticker.replace("/", "-")
    ticker = ticker.replace(".", "-")
    return ticker.strip().upper()

import pandas as pd

def pull_tickers(ticker_txt="tickers.txt", result_csv="hve_analysis.csv"):
    try:
        # Load already processed tickers from the CSV
        processed_df = pd.read_csv(result_csv)
        processed_tickers = set(processed_df["Stock"].str.upper())

        # Load original tickers from txt
        with open(ticker_txt, "r") as f:
            all_tickers = {format_ticker(line) for line in f if line.strip()}

        # Filter out already processed tickers
        remaining_tickers = [t for t in all_tickers if t not in processed_tickers]

        print(f"Processing {len(remaining_tickers)}...")
        return remaining_tickers
    except Exception as e:
        print(f"Error cleaning ticker list: {e}")


# === FUNCTION TO PROCESS ONE TICKER ===
def analyze_stock(ticker, interval="1d"):
    try:
        data = yf.Ticker(ticker).history(interval=interval, period="max")
        if data.empty or 'Volume' not in data.columns:
            print(f"[!] No data for {ticker}")
            return None

        data.dropna(subset=["Open", "Close", "Volume"], inplace=True)

        # Step 1: Get the max volume value
        max_volume = data["Volume"].max()

        # Step 2: Filter rows where volume == max_volume
        hve_candidates = data[data["Volume"] == max_volume]

        # Step 3: Keep only positive HVE candidates (Close > Open)
        positive_hves = hve_candidates[hve_candidates["Close"] > hve_candidates["Open"]]
        if positive_hves.empty:
            return None  # No positive HVE found

        # Step 4: Get the most recent positive HVE
        last_positive_hve = positive_hves.iloc[-1]
        hve_date = last_positive_hve.name
        hve_close = last_positive_hve["Close"]

        # Step 5: Get data after HVE
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
    # Load tickers to process (excluding those already in CSV)
    tickers = pull_tickers(TICKER_FILE, OUTPUT_CSV)

    total = len(tickers)

    # Check if output CSV exists and load it
    if os.path.exists(OUTPUT_CSV):
        existing_df = pd.read_csv(OUTPUT_CSV)
        processed_tickers = set(existing_df["Stock"].str.upper())
    else:
        existing_df = pd.DataFrame(columns=["Stock", "Close_on_HVE", "Highest_Close_After_HVE"])
        processed_tickers = set()

    for i, ticker in enumerate(tickers, start=1):
        if ticker in processed_tickers:
            continue

        result = analyze_stock(ticker, interval=INTERVAL)
        if result:
            # Append result to CSV immediately
            new_df = pd.DataFrame([result])
            new_df.to_csv(OUTPUT_CSV, mode='a', header=not os.path.exists(OUTPUT_CSV), index=False)

            # Optional: update the in-memory set to avoid reprocessing
            processed_tickers.add(ticker)

        if i % 11 == 0 or i == total:
            print(f"⏳ Processing {i:,} of {total:,}: {ticker}", end="\r")


if __name__ == "__main__":
    main()
