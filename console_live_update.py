import time

data = {"AAPL": 150.25, "MSFT": 320.10, "GOOGL": 2805.50}

for i in range(10):
    # Simulate updates
    for k in data:
        data[k] += 0.1 * i

    # Clear line and print in place
    print(f"\r{data}", end="", flush=True)
    time.sleep(1)
