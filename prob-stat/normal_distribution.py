import numpy as np
import matplotlib.pyplot as plt

data = np.random.normal(0.001, 0.02, 1000)

plt.hist(data, bins=150)
plt.show()


# data = [1, 2, 23, 4, 52, 18, -12, 69, 45]
# mean = np.mean(data)
# std = np.std(data)


# print("Mean:", mean)
# print("Standard Deviation:", std)