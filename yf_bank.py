import yfinance as yf


yf.Ticker("BAC").history(period="1y").to_csv("bank_of_america.csv")
