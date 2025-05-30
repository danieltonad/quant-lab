import time
import sys

data = {"AAPL": 150.25, "MSFT": 320.10, "GOOGL": 2805.50}
keys = list(data.keys())

def print_data(d):
    for k, v in d.items():
        print(f"{k}: {v:.2f}        ")

# Initial print
print_data(data)

for i in range(10):
    time.sleep(1)

    # Simulate update
    for k in data:
        data[k] += 0.1 * i

    # Move cursor up N lines
    sys.stdout.write(f"\033[{len(data)}A")  # ANSI escape: move cursor up N lines

    # Print updated data
    print_data(data)
    data["BALL"] = 90
