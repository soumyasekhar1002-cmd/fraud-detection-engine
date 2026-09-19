import os
import numpy as np
import pandas as pd

print("Initializing Fraud Data Preprocessing & Velocity Engineering...")

np.random.seed(42)
n_samples = 50000

data = {
    "transaction_id": [f"TXN_{i:06d}" for i in range(n_samples)],
    "cardholder_id": [
        f"USER_{np.random.randint(1, 5000):04d}" for i in range(n_samples)
    ],
    "amount": np.random.exponential(scale=75.0, size=n_samples) + 5.0,
    "merchant_category": np.random.choice(
        ["retail", "electronics", "travel", "grocery", "digital_goods"],
        size=n_samples,
    ),
    "distance_from_home": np.abs(
        np.random.normal(loc=5.0, scale=15.0, size=n_samples)
    ),
    "velocity_1h": np.random.poisson(lam=0.3, size=n_samples),
    "velocity_24h": np.random.poisson(lam=2.5, size=n_samples),
    "is_international": np.random.choice(
        [0, 1], size=n_samples, p=[0.80, 0.20]
    ),
}

df = pd.DataFrame(data)

# Robust Fraud Injection: target transactions with high velocity spikes,
# high amounts, or unusual international behavior to form ~1.5% fraud rate.
fraud_score = (
    (df["velocity_1h"] >= 2) * 0.4
    + (df["amount"] > 200.0) * 0.3
    + (df["is_international"] == 1) * 0.2
    + (df["distance_from_home"] > 25.0) * 0.3
    + np.random.normal(0, 0.1, size=n_samples)  # random noise
)

# Top 1.5% highest risk scores are labeled as fraud
threshold = np.percentile(fraud_score, 98.5)
df["is_fraud"] = (fraud_score >= threshold).astype(int)

# Ensure artifacts directory exists
os.makedirs("artifacts", exist_ok=True)
df.to_csv("artifacts/processed_transactions.csv", index=False)

print(
    f"--- Preprocessing Complete --- Total Records: {len(df):,} | Fraud"
    f" Cases: {df['is_fraud'].sum():,} ({df['is_fraud'].mean()*100:.2f}%)"
)