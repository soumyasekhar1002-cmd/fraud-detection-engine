from datetime import datetime
import os
import sqlite3
import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, Header, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
import shap
from pydantic import BaseModel, Field

app = FastAPI(
    title='Institutional Real-Time Fraud Detection Engine',
    version='1.0.0',
    description=(
        'Secure, low-latency transaction fraud scoring API for financial'
        ' institutions.'
    ),
)

# Simulated Secure API Key Store (In production, load from secure environment variables or a DB)
API_KEY_NAME = 'x-api-key'
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)
VALID_API_KEYS = {
    'bank_alpha_secret_key_991': 'Alpha Bank Corp',
    'fintech_beta_key_442': 'Beta Financial Services',
}


def get_api_key(api_key: str = Security(api_key_header)):
  if api_key in VALID_API_KEYS:
    return VALID_API_KEYS[api_key]
  raise HTTPException(
      status_code=403, detail='Unauthorized: Invalid or missing Institutional API Key'
  )


# Initialize Institutional Audit Database
def init_audit_db():
  conn = sqlite3.connect('institutional_fraud_audit.db')
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS fraud_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            institution_name TEXT,
            transaction_id TEXT,
            cardholder_id TEXT,
            amount REAL,
            fraud_probability REAL,
            decision_tier TEXT
        )
    """)
  conn.commit()
  conn.close()


init_audit_db()

# Load Fraud Model Artifact (ensure you train and save 'fraud_model.pkl' first)
# model = joblib.load('fraud_model.pkl')


class TransactionPayload(BaseModel):
  transaction_id: str = Field(..., description='Unique transaction reference ID')
  cardholder_id: str = Field(..., description='Unique user/card identifier')
  amount: float = Field(..., gt=0, description='Transaction amount in USD')
  merchant_category: str = Field(..., description='Category code of merchant')
  distance_from_home: float = Field(
      ..., ge=0, description='Miles from primary billing address'
  )
  velocity_1h: int = Field(
      ..., ge=0, description='Transactions by user in last 1 hour'
  )
  velocity_24h: int = Field(
      ..., ge=0, description='Transactions by user in last 24 hours'
  )
  is_international: int = Field(
      ..., ge=0, le=1, description='1 if international, 0 otherwise'
  )


@app.post('/v1/evaluate-fraud')
def evaluate_fraud(
    transaction: TransactionPayload, institution: str = Security(get_api_key)
):
  # Mock scoring logic (replace with model.predict_proba once trained)
  # Dynamic risk calculation factoring velocity and amount
  risk_score = min(
      0.99,
      (transaction.amount / 5000.0) * 0.3
      + (transaction.velocity_1h * 0.15)
      + (transaction.is_international * 0.25),
  )

  if risk_score > 0.75:
    decision = 'BLOCK'
  elif risk_score > 0.40:
    decision = 'CHALLENGE_2FA'
  else:
    decision = 'APPROVE'

  # Log decision immutably to audit database
  conn = sqlite3.connect('institutional_fraud_audit.db')
  cursor = conn.cursor()
  cursor.execute(
      """
        INSERT INTO fraud_decisions (timestamp, institution_name, transaction_id, cardholder_id, amount, fraud_probability, decision_tier)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
      (
          datetime.utcnow().isoformat(),
          institution,
          transaction.transaction_id,
          transaction.cardholder_id,
          transaction.amount,
          float(risk_score),
          decision,
      ),
  )
  conn.commit()
  conn.close()

  return {
      'transaction_id': transaction.transaction_id,
      'evaluated_for_institution': institution,
      'fraud_probability': round(float(risk_score), 4),
      'action': decision,
      'timestamp': datetime.utcnow().isoformat(),
  }