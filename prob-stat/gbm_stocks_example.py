import yfinance as yf
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# --- Fetch stock data ---
symbol = 'AAPL'
df = yf.download(symbol, period='5y', progress=False, auto_adjust=True)  # Last 1 year of data

# --- Calculate daily returns ---
df['Return'] = df['Close'].pct_change()
df.dropna(inplace=True)

# --- Estimate drift (mu) and volatility (sigma) from real data ---
mean_daily_return = df['Return'].mean()
std_daily_return = df['Return'].std()

mu = mean_daily_return * 252        # Annualized drift
sigma = std_daily_return * np.sqrt(252)  # Annualized volatility

print(f"Estimated mu (drift): {mu:.4f}")
print(f"Estimated sigma (volatility): {sigma:.4f}")

# --- Simulate GBM ---
T = 1.0  # 1 year
dt = 1/252
N = int(T / dt)
S0 = df['Close'].iloc[0]

np.random.seed(252) # simulated price action determined bt the seed, lol
Z = np.random.normal(0, 1, N)

S_sim = np.zeros(N)
S_sim[0] = S0
for t in range(1, N):
    S_sim[t] = S_sim[t-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z[t])

# --- Plot real vs simulated ---
plt.figure(figsize=(12, 6))
plt.plot(df['Close'].values, label='Real Price')
plt.plot(S_sim, label='Simulated GBM Path', linestyle='--')
plt.title(f'{symbol}: Real vs Simulated Price (GBM)')
plt.xlabel('Day')
plt.ylabel('Price')
plt.legend()
plt.grid(True)
plt.show()
