from contextlib import asynccontextmanager
from datetime import datetime
import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.database import init_audit_db, log_audit_decision
from app.schemas import TransactionPayload

# Global model container
ml_artifacts = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
  init_audit_db()
  artifact_path = "artifacts/fraud_model.pkl"
  if not joblib.os.path.exists(artifact_path):
    raise RuntimeError(
        f"Model artifact not found at {artifact_path}. Run training scripts"
        " first!"
    )

  loaded_data = joblib.load(artifact_path)
  ml_artifacts["model"] = loaded_data["model"]
  ml_artifacts["feature_columns"] = loaded_data["feature_columns"]
  print("--- Production Fraud Model Loaded Successfully into Memory ---")
  yield
  ml_artifacts.clear()


app = FastAPI(
    title="Institutional Real-Time Fraud Detection Engine",
    version="1.0.0",
    description=(
        "Enterprise-grade, low-latency transaction fraud scoring API for"
        " financial institutions."
    ),
    lifespan=lifespan,
)

# API Key Security Setup
API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

VALID_API_KEYS = {
    "bank_alpha_secret_key_991": "Alpha Bank Corp",
    "fintech_beta_key_442": "Beta Financial Services",
}


def get_api_key(api_key: str = Security(api_key_header)):
  if api_key in VALID_API_KEYS:
    return VALID_API_KEYS[api_key]
  raise HTTPException(
      status_code=403, detail="Unauthorized: Invalid or missing API Key"
  )


@app.post("/v1/evaluate-fraud")
def evaluate_fraud(
    transaction: TransactionPayload, institution: str = Security(get_api_key)
):
  # 1. Construct raw input dataframe
  input_data = {
      "amount": [transaction.amount],
      "merchant_category": [transaction.merchant_category],
      "distance_from_home": [transaction.distance_from_home],
      "velocity_1h": [transaction.velocity_1h],
      "velocity_24h": [transaction.velocity_24h],
      "is_international": [transaction.is_international],
  }
  df_input = pd.DataFrame(input_data)

  # 2. One-hot encode categorical features to match training columns
  df_encoded = pd.get_dummies(df_input, columns=["merchant_category"])

  for col in ml_artifacts["feature_columns"]:
    if col not in df_encoded.columns:
      df_encoded[col] = 0
  df_encoded = df_encoded[ml_artifacts["feature_columns"]]

  # 3. Model Inference (Get Fraud Probability)
  fraud_prob = float(
      ml_artifacts["model"].predict_proba(df_encoded)[:, 1][0]
  )

  # 4. Institutional Hard-Stop Business Rules (Compliance & Risk Guardrails)
  if transaction.amount >= 50000.0 or transaction.velocity_1h >= 8:
    decision = "BLOCK"
    fraud_prob = max(fraud_prob, 0.95)  # Force high risk score for audit trail
  elif transaction.amount >= 20000.0 or transaction.velocity_1h >= 4:
    decision = "CHALLENGE_2FA"
    fraud_prob = max(fraud_prob, 0.75)
  elif fraud_prob >= 0.70:
    decision = "BLOCK"
  elif fraud_prob >= 0.35:
    decision = "CHALLENGE_2FA"
  else:
    decision = "APPROVE"

  # 5. Immutable Regulatory Audit Logging
  log_audit_decision(
      institution=institution,
      transaction_id=transaction.transaction_id,
      cardholder_id=transaction.cardholder_id,
      amount=transaction.amount,
      probability=fraud_prob,
      decision=decision,
  )

  return {
      "transaction_id": transaction.transaction_id,
      "evaluated_for_institution": institution,
      "fraud_probability": round(fraud_prob, 4),
      "action": decision,
      "timestamp": datetime.utcnow().isoformat(),
  }