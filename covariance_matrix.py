import yfinance as yf
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# Fetch data
tickers = ['AAPL', 'MSFT', 'GOOGL']
data = yf.download(tickers, auto_adjust=True, start='2024-01-01', end='2025-01-01')['Close']

print("Data => ", data)

# Calculate daily returns
returns = data.pct_change().dropna()

print("Returns => " ,returns)

# Compute covariance matrix
cov_matrix = np.cov(returns, rowvar=False)

print("Cov =>", cov_matrix)

# Visualize
sns.heatmap(cov_matrix, annot=True, xticklabels=tickers, yticklabels=tickers)
plt.title('Covariance Matrix of Stock Returns')
plt.show()