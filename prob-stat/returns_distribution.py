import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt

# Download historical prices for Apple
ticker = 'BTC-USD'
data = yf.download(ticker, period="6mo", progress=False, interval='1d', auto_adjust=True)


data['Daily Return'] = data['Close'].pct_change()
returns_real = data['Daily Return'].dropna()


plt.hist(returns_real, bins=50, density=True, alpha=0.6, label='Real Returns')
plt.xlabel('Daily Return')
plt.ylabel('Density')
plt.title(f'{ticker} Daily Returns')


mean_real = returns_real.mean()
std_real = returns_real.std()

# Simulate returns using the same mean and std
simulated_returns = np.random.normal(mean_real, std_real, len(returns_real))

plt.hist(simulated_returns, bins=50, density=True, alpha=0.6, label='Simulated Normal')
plt.legend()
plt.show()
