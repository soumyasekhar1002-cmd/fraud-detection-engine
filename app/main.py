import joblib
import shap
import pandas as pd
from fastapi import FastAPI, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional

app = FastAPI(
    title="Institutional Real-Time Fraud Detection Engine",
    version="2.1.0",
    description="Core engine featuring real-time evaluation, batch processing, and SHAP explainability."
)

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
        # Map feature names to their respective SHAP impact values
        explanation = dict(zip(df.columns, shap_vals[0].tolist()))
    else:
        # Fallback sandbox behavior if .pkl is absent
        prob = 0.95 if txn.amount > 100000 or txn.velocity_1h > 3 else 0.05
        explanation = {"amount_impact": 0.45, "velocity_impact": 0.30}

    # Thresholding rules
    if prob > 0.80:
        decision = "BLOCK"
    elif prob >= 0.20:
        decision = "REVIEW"
    else:
        decision = "APPROVE"
        
    return prob, decision, explanation

# 4. Endpoints
@app.post("/v1/evaluate-fraud")
def evaluate_single(payload: TransactionPayload, institution: str = Depends(verify_api_key)):
    prob, decision, explanation = process_risk_and_explanation(payload)
    
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