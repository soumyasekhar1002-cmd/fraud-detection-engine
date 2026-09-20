import os
import uuid
import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import bcrypt
import joblib
import shap
import pandas as pd

# --- PASSWORD HASHING SETUP (NATIVE BCRYPT) ---
def get_password_hash(password: str) -> str:
    # Encode and enforce 72-byte limit safely
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd_bytes = plain_password.encode('utf-8')[:72]
    return bcrypt.checkpw(pwd_bytes, hashed_password.encode('utf-8'))

# --- DATABASE SETUP (NEON POSTGRESQL) ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback to local SQLite if DATABASE_URL environment variable isn't set locally
    DATABASE_URL = "sqlite:///./artifacts/institutional_fraud_audit.db"

# Handle Neon's postgres:// prefix quirk for SQLAlchemy if present
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- SQLALCHEMY MODELS ---
class UserModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    institution_name = Column(String(255), nullable=False)
    api_key = Column(String(255), unique=True, index=True, nullable=False)
    is_admin = Column(Boolean, default=False)

class AuditLogModel(Base):
    __tablename__ = "audit_logs" # Matches the Neon table created earlier
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String(100))
    cardholder_id = Column(String(100))
    amount = Column(Float)
    merchant_category = Column(String(100))
    fraud_probability = Column(Float)
    decision = Column(String(50))
    evaluated_institution = Column(String(255))
    api_key = Column(String(255))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# Create tables if they don't exist yet
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- FASTAPI APP INITIALIZATION ---
app = FastAPI(
    title="Institutional Real-Time Fraud Detection Engine",
    version="2.3.0",
    description="Multi-tenant core engine featuring Neon PostgreSQL persistence, dynamic API keys, and secure bcrypt password hashing."
)

# 1. Load Model & Initialize SHAP TreeExplainer
try:
    model = joblib.load("fraud_model.pkl")
    explainer = shap.TreeExplainer(model)
except Exception:
    model = None
    explainer = None


# --- PYDANTIC SCHEMAS ---
class SignupSchema(BaseModel):
    email: str
    password: str
    institution_name: str

class LoginSchema(BaseModel):
    email: str
    password: str

class TransactionPayload(BaseModel):
    transaction_id: str = Field(..., json_schema_extra={"example": "TXN_070038"})
    cardholder_id: str = Field(..., json_schema_extra={"example": "USER_4392"})
    amount: float = Field(..., gt=0, json_schema_extra={"example": 500000.00})
    distance_from_home: float = Field(..., ge=0, json_schema_extra={"example": 12.50})
    velocity_1h: int = Field(..., ge=0, json_schema_extra={"example": 1})
    velocity_24h: int = Field(..., ge=0, json_schema_extra={"example": 3})
    is_international: int = Field(..., ge=0, le=1, json_schema_extra={"example": 0})
    merchant_category: Optional[str] = Field("Retail", json_schema_extra={"example": "Electronics"})

class BatchTransactionPayload(BaseModel):
    transactions: List[TransactionPayload]


# --- AUTHENTICATION DEPENDENCY ---
def verify_user_by_api_key(x_api_key: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Missing institutional API key (x-api-key)."
        )
    
    user = db.query(UserModel).filter(UserModel.api_key == x_api_key).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid institutional API key."
        )
    return user


# --- AUTH ENDPOINTS ---
@app.post("/signup")
def register_user(payload: SignupSchema, db: Session = Depends(get_db)):
    existing = db.query(UserModel).filter(UserModel.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Generate a unique API key for this specific tenant/user
    unique_key = f"key_{uuid.uuid4().hex[:12]}"
    
    # Securely hash the password using bcrypt
    hashed_password = get_password_hash(payload.password)
    
    new_user = UserModel(
        email=payload.email,
        password_hash=hashed_password,
        institution_name=payload.institution_name,
        api_key=unique_key,
        is_admin=False
    )
    db.add(new_user)
    db.commit()
    
    # Return success without exposing password data
    return {
        "message": "User created successfully",
        "email": payload.email,
        "institution_name": payload.institution_name,
        "api_key": unique_key
    }

@app.post("/login")
def login_user(payload: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.email == payload.email).first()
    
    # Verify email existence and check password against stored bcrypt hash safely
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    return {
        "email": user.email,
        "institution_name": user.institution_name,
        "api_key": user.api_key,
        "is_admin": user.is_admin
    }


# --- CORE LOGIC HELPERS ---
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

def log_audit_decision(user: UserModel, txn: TransactionPayload, prob: float, decision: str, db: Session):
    try:
        audit_entry = AuditLogModel(
            transaction_id=txn.transaction_id,
            cardholder_id=txn.cardholder_id,
            amount=txn.amount,
            merchant_category=txn.merchant_category,
            fraud_probability=round(prob, 4),
            decision=decision,
            evaluated_institution=user.institution_name,
            api_key=user.api_key
        )
        db.add(audit_entry)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Audit logging failed: {e}")


# --- EVALUATION ENDPOINTS ---
@app.post("/v1/evaluate-fraud")
def evaluate_single(payload: TransactionPayload, user: UserModel = Depends(verify_user_by_api_key), db: Session = Depends(get_db)):
    prob, decision, explanation = process_risk_and_explanation(payload)
    log_audit_decision(user, payload, prob, decision, db)
    
    return {
        "transaction_id": payload.transaction_id,
        "fraud_probability": round(prob, 4),
        "risk_score": round(prob * 100, 2),
        "decision": decision,
        "shap_explanation": explanation,
        "evaluated_institution": user.institution_name
    }

@app.post("/v1/batch-evaluate")
def evaluate_batch(payload: BatchTransactionPayload, user: UserModel = Depends(verify_user_by_api_key), db: Session = Depends(get_db)):
    results = []
    
    for txn in payload.transactions:
        prob, decision, explanation = process_risk_and_explanation(txn)
        log_audit_decision(user, txn, prob, decision, db)
        results.append({
            "transaction_id": txn.transaction_id,
            "fraud_probability": round(prob, 4),
            "decision": decision,
            "shap_explanation": explanation
        })
        
    return {
        "total_processed": len(results),
        "evaluated_institution": user.institution_name,
        "evaluations": results
    }

# --- AUDIT LOGS ENDPOINT (WITH TENANT ISOLATION & ADMIN OVERRIDE) ---
@app.get("/v1/audit-logs")
def get_audit_logs(user: UserModel = Depends(verify_user_by_api_key), db: Session = Depends(get_db)):
    try:
        if user.is_admin:
            # Master Admin sees ALL logs across every tenant globally
            logs = db.query(AuditLogModel).order_by(AuditLogModel.id.desc()).limit(200).all()
        else:
            # Standard users see strictly their own institution's data
            logs = db.query(AuditLogModel).filter(
                AuditLogModel.evaluated_institution == user.institution_name
            ).order_by(AuditLogModel.id.desc()).all()
            
        # Convert SQLAlchemy objects to dictionaries for the frontend
        result_list = []
        for l in logs:
            result_list.append({
                "id": l.id,
                "transaction_id": l.transaction_id,
                "cardholder_id": l.cardholder_id,
                "amount": l.amount,
                "merchant_category": l.merchant_category,
                "fraud_probability": l.fraud_probability,
                "decision": l.decision,
                "evaluated_institution": l.evaluated_institution,
                "created_at": str(l.created_at)
            })
        return result_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve audit logs: {str(e)}")