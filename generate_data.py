import pandas as pd
import numpy as np

# Set seed for reproducibility
np.random.seed(42)
n_records = 400

# Generate realistic synthetic distribution for transaction features
data = {
    "transaction_id": [f"TXN_{str(i).zfill(5)}" for i in range(1, n_records + 1)],
    "cardholder_id": [f"USER_{np.random.randint(1000, 9999)}" for _ in range(n_records)],
    "amount": np.random.exponential(scale=350.0, size=n_records) + 15.0,
    "distance_from_home": np.random.gamma(shape=2.0, scale=8.0, size=n_records),
    "velocity_1h": np.random.poisson(lam=1.0, size=n_records),
    "velocity_24h": np.random.poisson(lam=3.0, size=n_records),
    "is_international": np.random.choice([0, 1], size=n_records, p=[0.85, 0.15])
}

df = pd.DataFrame(data)

# Inject high-risk anomalous fraud profiles in the first 20 rows
df.loc[0:20, 'amount'] = np.random.uniform(75000.0, 600000.0, 21)
df.loc[0:20, 'velocity_1h'] = np.random.randint(4, 12, 21)
df.loc[0:20, 'is_international'] = 1

# Save to CSV
output_filename = "test_transactions_500.csv"
df.to_csv(output_filename, index=False)
print(f"Successfully generated {output_filename} with {len(df)} records!")