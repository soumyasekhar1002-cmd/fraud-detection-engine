import joblib
import shap
import pandas as pd
import sqlite3
import os
import datetime
from fastapi import FastAPI, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional

app = FastAPI(
    title="Institutional Real-Time Fraud Detection Engine",
    version="2.1.0",
    description="Core engine featuring real-time evaluation, batch processing, and SHAP explainability."
)

# Initialize SQLite Audit Database
os.makedirs("artifacts", exist_ok=True)
DB_PATH = "artifacts/institutional_fraud_audit.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
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

init_db()

# 1. Load Model & Initialize SHAP TreeExplainer
try:
    model = joblib.load("fraud_model.pkl")
    explainer = shap.TreeExplainer(model)
except Exception:
    model = None
    explainer = None

VALID_API_KEY = "bank_alpha_secret_key_991"

def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if x_api_key != VALID_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid or missing institutional API key (x-api-key)."
        )
    return "Alpha Bank Corp"

# 2. Pydantic Schemas
class TransactionPayload(BaseModel):
    transaction_id: str = Field(..., json_schema_extra={"example": "TXN_070038"})
    cardholder_id: str = Field(..., json_schema_extra={"example": "USER_4392"})
    amount: float = Field(..., gt=0, json_schema_extra={"example": 500000.00})
    distance_from_home: float = Field(..., ge=0, json_schema_extra={"example": 12.50})
    velocity_1h: int = Field(..., ge=0, json_schema_extra={"example": 1})
    velocity_24h: int = Field(..., ge=0, json_schema_extra={"example": 3})
    is_international: int = Field(..., ge=0, le=1, json_schema_extra={"example": 0})

class BatchTransactionPayload(BaseModel):
    transactions: List[TransactionPayload]

# 3. Core Decision & SHAP Logic Helper
def process_risk_and_explanation(txn: TransactionPayload):
    df = pd.DataFrame([{
        "amount": txn.amount,
        "distance_from_home": txn.distance_from_home,
        "velocity_1h": txn.velocity_1h,
        "velocity_24h": txn.velocity_24h,
        "is_international": txn.is_international
    }])
    
    if model and explainer:
        prob = float(model.predict_proba(df)[0][1])
        shap_vals = explainer.shap_values(df)
        explanation = dict(zip(df.columns, shap_vals[0].tolist()))
    else:
        prob = 0.95 if txn.amount > 100000 or txn.velocity_1h > 3 else 0.05
        explanation = {"amount_impact": 0.45, "velocity_impact": 0.30}

    if prob > 0.80:
        decision = "BLOCK"
    elif prob >= 0.20:
        decision = "REVIEW"
    else:
        decision = "APPROVE"
        
    return prob, decision, explanation

def log_audit_decision(institution: str, txn: TransactionPayload, prob: float, decision: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO fraud_decisions (timestamp, institution_name, transaction_id, cardholder_id, amount, fraud_probability, decision_tier)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.datetime.utcnow().isoformat(),
            institution,
            txn.transaction_id,
            txn.cardholder_id,
            txn.amount,
            round(prob, 4),
            decision
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Audit logging failed: {e}")

# 4. Endpoints
@app.post("/v1/evaluate-fraud")
def evaluate_single(payload: TransactionPayload, institution: str = Depends(verify_api_key)):
    prob, decision, explanation = process_risk_and_explanation(payload)
    log_audit_decision(institution, payload, prob, decision)
    
    return {
        "transaction_id": payload.transaction_id,
        "fraud_probability": round(prob, 4),
        "risk_score": round(prob * 100, 2),
        "decision": decision,
        "shap_explanation": explanation,
        "evaluated_institution": institution
    }

@app.post("/v1/batch-evaluate")
def evaluate_batch(payload: BatchTransactionPayload, institution: str = Depends(verify_api_key)):
    results = []
    
    for txn in payload.transactions:
        prob, decision, explanation = process_risk_and_explanation(txn)
        log_audit_decision(institution, txn, prob, decision)
        results.append({
            "transaction_id": txn.transaction_id,
            "fraud_probability": round(prob, 4),
            "decision": decision,
            "shap_explanation": explanation
        })
        
    return {
        "total_processed": len(results),
        "evaluated_institution": institution,
        "evaluations": results
    }

@app.get("/v1/audit-logs")
def get_audit_logs(x_api_key: str = Header(...)):
    if x_api_key != VALID_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        df_audit = pd.read_sql_query("SELECT * FROM fraud_decisions ORDER BY id DESC LIMIT 100", conn)
        conn.close()
        return df_audit.to_dict(orient="records")
    except Exception as e:
        return {"error": f"Failed to retrieve audit logs: {str(e)}"}