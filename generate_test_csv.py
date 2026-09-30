"""
Utility script to generate realistic synthetic test speed data (my_speed.csv).
Simulates 12 timesteps (1 hour) for 207 METR-LA sensors with realistic congestion patterns.
"""

import numpy as np
import pandas as pd

np.random.seed(42)
num_timesteps = 12
num_sensors = 207

# Create realistic baseline speeds per sensor region
speeds = np.zeros((num_timesteps, num_sensors), dtype=np.float32)

# Region 1 (Sensors 0-30): Heavy bottleneck congestion (8 - 22 mph)
speeds[:, 0:31] = np.random.uniform(8.0, 22.0, size=(num_timesteps, 31))

# Region 2 (Sensors 31-150): Clear highway flow (50 - 68 mph)
speeds[:, 31:151] = np.random.uniform(50.0, 68.0, size=(num_timesteps, 120))

# Region 3 (Sensors 151-180): Moderate congestion / slowdown (22 - 38 mph)
speeds[:, 151:181] = np.random.uniform(22.0, 38.0, size=(num_timesteps, 30))

# Region 4 (Sensors 181-206): Fast arterial road (55 - 72 mph)
speeds[:, 181:207] = np.random.uniform(55.0, 72.0, size=(num_timesteps, 26))

# Save to CSV without index header
df = pd.DataFrame(speeds, columns=[f"sensor_{i}" for i in range(num_sensors)])
df.to_csv("my_speed.csv", index=False)

print(f"Generated 'my_speed.csv' with shape {df.shape} successfully!")
