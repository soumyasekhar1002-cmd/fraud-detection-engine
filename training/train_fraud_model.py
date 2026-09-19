import os
import joblib
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
import xgboost as xgb

print("Loading processed data for XGBoost Fraud Model Training...")
df = pd.read_csv("artifacts/processed_transactions.csv")

# Feature selection
feature_cols = [
    "amount",
    "merchant_category",
    "distance_from_home",
    "velocity_1h",
    "velocity_24h",
    "is_international",
]
target_col = "is_fraud"

# One-hot encode categorical features like merchant category
df_encoded = pd.get_dummies(df[feature_cols], columns=["merchant_category"])

X = df_encoded
y = df[target_col]

# Stratified Train-Test Split to maintain rare fraud class distribution
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Calculate scale_pos_weight to manage extreme class imbalance
neg_count = (y_train == 0).sum()
pos_count = (y_train == 1).sum()
scale_pos_weight_val = neg_count / pos_count

print(
    f"Training Data Shape: {X_train.shape} | Positive Class Imbalance Weight:"
    f" {scale_pos_weight_val:.2f}"
)

# Configure XGBoost for High-Imbalance Tabular Classification
model = xgb.XGBClassifier(
    n_estimators=300,
    learning_rate=0.03,
    max_depth=6,
    scale_pos_weight=scale_pos_weight_val,
    eval_metric="aucpr",  # Optimize specifically for PR-AUC
    random_state=42,
    n_jobs=-1,
)

print("Training XGBoost Classifier...")
model.fit(
    X_train,
    y_train,
    eval_set=[(X_test, y_test)],
    verbose=50,
)

# Evaluate model performance
y_pred_proba = model.predict_proba(X_test)[:, 1]
pr_auc = average_precision_score(y_test, y_pred_proba)
roc_auc = roc_auc_score(y_test, y_pred_proba)

print("\n--- Model Evaluation Metrics ---")
print(f"Precision-Recall AUC (PR-AUC): {pr_auc:.4f}")
print(f"ROC-AUC Score: {roc_auc:.4f}")

# Save serialized model artifact for the API backend
os.makedirs("artifacts", exist_ok=True)
joblib.dump(
    {"model": model, "feature_columns": list(X.columns)},
    "artifacts/fraud_model.pkl",
)
print("Successfully serialized production model to 'artifacts/fraud_model.pkl'")