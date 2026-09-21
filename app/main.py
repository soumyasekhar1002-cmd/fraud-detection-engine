import os
import uuid
import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import bcrypt
import joblib
import shap
import pandas as pd
import httpx

# --- PASSWORD HASHING SETUP (NATIVE BCRYPT) ---
def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    pwd_bytes = plain_password.encode('utf-8')[:72]
    return bcrypt.checkpw(pwd_bytes, hashed_password.encode('utf-8'))

# --- DATABASE SETUP (NEON POSTGRESQL / SQLITE) ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./artifacts/institutional_fraud_audit.db"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- UPDATED SQLALCHEMY MODELS ---
class UserModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=True) # Nullable for OAuth users
    institution_name = Column(String(255), nullable=False)
    api_key = Column(String(255), unique=True, index=True, nullable=False)
    is_admin = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    status = Column(String(50), default="ACTIVE") # ACTIVE, DEACTIVATED, SUSPENDED_TEMPORARY, PENDING
    suspension_until = Column(DateTime, nullable=True)
    role = Column(String(50), default="analyst") # admin, analyst, auditor
    verification_token = Column(String(255), nullable=True)
    reset_token = Column(String(255), nullable=True)

class AuditLogModel(Base):
    __tablename__ = "audit_logs"
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
    version="2.5.0",
    description="Multi-tenant core engine featuring advanced user lifecycle management."
)

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

class BulkUserActionRequest(BaseModel):
    emails: List[EmailStr]
    action: str  # "activate", "deactivate", "suspend"
    suspension_hours: Optional[int] = 24

class UserUpdateRoleRequest(BaseModel):
    email: EmailStr
    new_role: str  # "admin", "analyst", "auditor"

class TransactionPayload(BaseModel):
    transaction_id: str
    cardholder_id: str
    amount: float
    distance_from_home: float
    velocity_1h: int
    velocity_24h: int
    is_international: int
    merchant_category: Optional[str] = "Retail"

class BatchTransactionPayload(BaseModel):
    transactions: List[TransactionPayload]

# --- AUTHENTICATION DEPENDENCY ---
def verify_user_by_api_key(x_api_key: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing institutional API key (x-api-key).")
    user = db.query(UserModel).filter(UserModel.api_key == x_api_key).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid institutional API key.")
    
    # Check suspension expiry
    if user.status == "SUSPENDED_TEMPORARY" and user.suspension_until:
        if datetime.datetime.utcnow() < user.suspension_until:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is temporarily suspended.")
        else:
            user.status = "ACTIVE"
            user.suspension_until = None
            db.commit()
            
    if user.status == "DEACTIVATED":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account has been deactivated by an administrator.")
        
    return user

def verify_master_admin(x_api_key: Optional[str] = Header(None), db: Session = Depends(get_db)):
    user = verify_user_by_api_key(x_api_key, db)
    if not user.is_admin and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Master Admin privileges required.")
    return user

# --- AUTH & ACCOUNT ENDPOINTS ---
@app.post("/signup")
def register_user(payload: SignupSchema, db: Session = Depends(get_db)):
    existing = db.query(UserModel).filter(UserModel.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    unique_key = f"key_{uuid.uuid4().hex[:12]}"
    ver_token = uuid.uuid4().hex
    hashed_password = get_password_hash(payload.password)
    
    new_user = UserModel(
        email=payload.email,
        password_hash=hashed_password,
        institution_name=payload.institution_name,
        api_key=unique_key,
        is_admin=False,
        is_verified=False,
        status="PENDING",
        role="analyst",
        verification_token=ver_token
    )
    db.add(new_user)
    db.commit()
    
    return {
        "message": "Account created successfully! Please verify your email.",
        "email": payload.email,
        "api_key": unique_key,
        "verification_token_demo": ver_token
    }

@app.post("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.verification_token == token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token.")
    
    user.is_verified = True
    user.status = "ACTIVE"
    user.verification_token = None
    db.commit()
    return {"message": "Email successfully verified! You can now sign in."}

@app.post("/login")
def login_user(payload: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if user.status == "DEACTIVATED":
        raise HTTPException(status_code=403, detail="Account is deactivated.")
    if user.status == "SUSPENDED_TEMPORARY" and user.suspension_until and datetime.datetime.utcnow() < user.suspension_until:
        raise HTTPException(status_code=403, detail=f"Account temporarily suspended until {user.suspension_until}.")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email not verified.")
    
    return {
        "email": user.email,
        "institution_name": user.institution_name,
        "api_key": user.api_key,
        "is_admin": user.is_admin or user.role == "admin"
    }

# --- MASTER ADMIN USER MANAGEMENT ENDPOINTS ---
@app.get("/admin/users-detailed")
def get_all_users_detailed(admin_user: UserModel = Depends(verify_master_admin), db: Session = Depends(get_db)):
    users = db.query(UserModel).all()
    results = []
    for u in users:
        results.append({
            "id": u.id,
            "email": u.email,
            "institution_name": u.institution_name,
            "role": u.role,
            "is_verified": u.is_verified,
            "status": u.status,
            "suspension_until": str(u.suspension_until) if u.suspension_until else None,
            "is_admin": u.is_admin
        })
    return results

@app.post("/admin/user-lifecycle")
def modify_user_lifecycle(payload: BulkUserActionRequest, admin_user: UserModel = Depends(verify_master_admin), db: Session = Depends(get_db)):
    results = []
    for email in payload.emails:
        user = db.query(UserModel).filter(UserModel.email == email).first()
        if not user:
            continue
        
        if payload.action == "activate":
            user.is_verified = True
            user.status = "ACTIVE"
            user.suspension_until = None
            results.append({"email": email, "status": "ACTIVATED"})
        elif payload.action == "deactivate":
            user.status = "DEACTIVATED"
            results.append({"email": email, "status": "DEACTIVATED"})
        elif payload.action == "suspend":
            expiry = datetime.datetime.utcnow() + datetime.timedelta(hours=payload.suspension_hours)
            user.status = "SUSPENDED_TEMPORARY"
            user.suspension_until = expiry
            results.append({"email": email, "status": "SUSPENDED_TEMPORARY", "until": str(expiry)})
            
    db.commit()
    return {"message": "Lifecycle action processed successfully", "results": results}

@app.post("/admin/update-role")
def update_user_role(payload: UserUpdateRoleRequest, admin_user: UserModel = Depends(verify_master_admin), db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.role = payload.new_role
    if payload.new_role == "admin":
        user.is_admin = True
    db.commit()
    return {"message": f"Successfully updated role for {payload.email} to {payload.new_role}"}

# --- CORE EVALUATION & AUDIT LOGIC ---
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

@app.get("/v1/audit-logs")
def get_audit_logs(user: UserModel = Depends(verify_user_by_api_key), db: Session = Depends(get_db)):
    try:
        if user.is_admin or user.role == "admin":
            logs = db.query(AuditLogModel).order_by(AuditLogModel.id.desc()).all()
        else:
            logs = db.query(AuditLogModel).filter(AuditLogModel.evaluated_institution == user.institution_name).order_by(AuditLogModel.id.desc()).all()
            
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