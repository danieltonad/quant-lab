import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt

# --- Parameters ---
symbol = 'AAPL'  # Any stock symbol
period = '1y'
num_paths = 100  # Number of simulated paths
T = 1.0          # Years to simulate
dt = 1/252       # Daily step
N = int(T / dt)  # Number of steps

# --- Get real data ---
df = yf.download(symbol, period=period)
df['Return'] = df['Close'].pct_change()
df.dropna(inplace=True)

# --- Estimate drift and volatility ---
mean_daily = df['Return'].mean()
std_daily = df['Return'].std()
mu = mean_daily * 252
sigma = std_daily * np.sqrt(252)

# --- Initial price ---
S0 = df['Close'].iloc[-1]

# --- Monte Carlo Simulation ---
simulations = np.zeros((num_paths, N))
for i in range(num_paths):
    S = np.zeros(N)
    S[0] = S0
    Z = np.random.normal(0, 1, N)
    for t in range(1, N):
        S[t] = S[t-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z[t])
    simulations[i] = S

# --- Plot Simulations ---
plt.figure(figsize=(14, 6))
for i in range(num_paths):
    plt.plot(simulations[i], alpha=0.3)

plt.title(f"{symbol} - Simulated Price Paths ({num_paths} paths)")
plt.xlabel("Day")
plt.ylabel("Price")
plt.grid(True)
plt.show()

# --- Risk Metrics at Final Day ---
final_prices = simulations[:, -1]
mean_price = np.mean(final_prices)
VaR_5 = np.percentile(final_prices, 5)
VaR_1 = np.percentile(final_prices, 1)
max_loss = S0 - np.min(final_prices)
max_gain = np.max(final_prices) - S0

print(f"\n--- {symbol} 1-Year Risk Summary ---")
print(f"Initial Price: ${S0:.2f}")
print(f"Expected Price (Mean): ${mean_price:.2f}")
print(f"5% Value at Risk (VaR): ${S0 - VaR_5:.2f}")
print(f"1% Value at Risk (VaR): ${S0 - VaR_1:.2f}")
print(f"Max Simulated Loss: ${max_loss:.2f}")
print(f"Max Simulated Gain: ${max_gain:.2f}")
