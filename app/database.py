from datetime import datetime
import sqlite3

DB_PATH = "artifacts/institutional_fraud_audit.db"


def init_audit_db():
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


def log_audit_decision(
    institution: str,
    transaction_id: str,
    cardholder_id: str,
    amount: float,
    probability: float,
    decision: str,
):
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute(
      """
        INSERT INTO fraud_decisions (timestamp, institution_name, transaction_id, cardholder_id, amount, fraud_probability, decision_tier)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
      (
          datetime.utcnow().isoformat(),
          institution,
          transaction_id,
          cardholder_id,
          amount,
          float(probability),
          decision,
      ),
  )
  conn.commit()
  conn.close()