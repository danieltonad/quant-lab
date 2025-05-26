import numpy as np
import matplotlib.pyplot as plt

# Parameters
mean_return = 0.001
volatility = 0.02
num_days = 1000

# Simulate returns
returns = np.random.normal(mean_return, volatility, num_days)
print(returns)

# Plot histogram
plt.hist(returns, bins=50, density=True, alpha=0.7)
plt.title('Simulated Daily Returns (Normal Distribution)')
plt.xlabel('Return')
plt.ylabel('Density')
plt.show()