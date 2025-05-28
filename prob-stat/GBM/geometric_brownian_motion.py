import numpy as np
import matplotlib.pyplot as plt

# Parameters
S0 = 100  # Initial price
mu = 0.05  # Drift
sigma = 0.2  # Volatility
T = 1.0  # Time (1 year)
dt = 1/252  # Time step (1 trading day)
N = int(T / dt)  # Number of steps

# Simulate GBM
np.random.seed(42)
Z = np.random.normal(0, 1, N)
S = np.zeros(N)
S[0] = S0
for t in range(1, N):
    S[t] = S[t-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z[t])

# Plot
plt.plot(S)
plt.title('Geometric Brownian Motion: Stock Price Path')
plt.xlabel('Day')
plt.ylabel('Price')
plt.show()