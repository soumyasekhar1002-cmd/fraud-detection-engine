import pandas as pd
import requests
import streamlit as st
import sqlite3

st.set_page_config(
    page_title="Institutional Fraud Intelligence Portal",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ Institutional Real-Time Fraud Detection Portal")
st.markdown(
    "Enterprise-grade transaction risk scoring and regulatory audit viewer."
)

# Sidebar for Institutional Authentication
st.sidebar.header("🔐 Institutional Access")
institution_api_key = st.sidebar.text_input(
    "API Key (`x-api-key`)",
    value="bank_alpha_secret_key_991",
    type="password",
)
api_endpoint = st.sidebar.text_input(
    "FastAPI Gateway URL", value="https://fraud-detection-engine-v5wj.onrender.com/v1/evaluate-fraud"
)

tab1, tab2 = st.tabs(
    ["🚀 Live Transaction Scoring", "📊 Regulatory Audit Logs"]
)

with tab1:
  st.subheader("Transaction Risk Evaluation Form")

  col1, col2 = st.columns(2)
  with col1:
    transaction_id = st.text_input(
        "Transaction ID", value=f"TXN_{pd.Timestamp.now().strftime('%H%M%S')}"
    )
    cardholder_id = st.text_input("Cardholder ID", value="USER_4392")
    amount = st.number_input("Transaction Amount ($)", min_value=1.0, value=250.0)
    merchant_category = st.selectbox(
        "Merchant Category",
        ["retail", "electronics", "travel", "grocery", "digital_goods"],
    )

  with col2:
    distance_from_home = st.number_input(
        "Distance From Home (miles)", min_value=0.0, value=12.5
    )
    velocity_1h = st.slider(
        "Velocity (Transactions in last 1 hour)", 0, 20, 1
    )
    velocity_24h = st.slider(
        "Velocity (Transactions in last 24 hours)", 0, 50, 3
    )
    is_international = st.selectbox(
        "Is International Transaction?", [0, 1], format_func=lambda x: "Yes" if x == 1 else "No"
    )

  if st.button("Evaluate Transaction Risk", type="primary"):
    payload = {
        "transaction_id": transaction_id,
        "cardholder_id": cardholder_id,
        "amount": amount,
        "merchant_category": merchant_category,
        "distance_from_home": distance_from_home,
        "velocity_1h": velocity_1h,
        "velocity_24h": velocity_24h,
        "is_international": is_international,
    }
    headers = {"x-api-key": institution_api_key, "Content-Type": "application/json"}

    try:
      response = requests.post(api_endpoint, json=payload, headers=headers)
      if response.status_code == 200:
        res_data = response.json()
        prob = res_data["fraud_probability"]
        action = res_data["action"]

        st.markdown("---")
        st.subheader("Evaluation Results")
        mcol1, mcol2, mcol3 = st.columns(3)
        mcol1.metric("Fraud Probability", f"{prob * 100:.2f}%")
        mcol2.metric("Evaluated Institution", res_data["evaluated_for_institution"])

        if action == "BLOCK":
          mcol3.error(f"Decision: {action}")
        elif action == "CHALLENGE_2FA":
          mcol3.warning(f"Decision: {action}")
        else:
          mcol3.success(f"Decision: {action}")

      else:
        st.error(f"API Error [{response.status_code}]: {response.text}")
    except Exception as e:
      st.error(
          f"Connection failed: Could not reach backend server. Error: {e}"
      )

with tab2:
  st.subheader("Immutable Regulatory Audit Trail")
  st.markdown(
      "Real-time view of all historical decisions logged in the SQLite audit"
      " database."
  )

  if st.button("Refresh Audit Logs"):
    pass

  try:
    conn = sqlite3.connect("artifacts/institutional_fraud_audit.db")
    df_audit = pd.read_sql_query(
        "SELECT * FROM fraud_decisions ORDER BY id DESC", conn
    )
    conn.close()

    if not df_audit.empty:
      st.dataframe(df_audit, use_container_width=True)
    else:
      st.info("No audit logs recorded yet. Run an evaluation first.")
  except Exception as e:
    st.warning(f"Audit database not initialized yet or not found: {e}")