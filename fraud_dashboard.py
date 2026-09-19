import pandas as pd
import requests
import streamlit as st

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

# Define 3 distinct functional tabs
tab1, tab2, tab3 = st.tabs(
    ["🚀 Live Transaction Scoring", "📂 Batch CSV Evaluation", "📊 Regulatory Audit Logs"]
)

with tab1:
  st.subheader("Single Transaction Risk Evaluation Form")

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
        
        prob = res_data.get("fraud_probability", 0.0)
        action = res_data.get("decision", res_data.get("action", "REVIEW"))
        institution = res_data.get("evaluated_institution", res_data.get("evaluated_for_institution", "Default Institution"))

        st.markdown("---")
        st.subheader("Evaluation Results")
        mcol1, mcol2, mcol3 = st.columns(3)
        mcol1.metric("Fraud Probability", f"{prob * 100:.2f}%")
        mcol2.metric("Evaluated Institution", institution)

        if action == "BLOCK":
          mcol3.error(f"Decision: {action}")
        elif action == "CHALLENGE_2FA":
          mcol3.warning(f"Decision: {action}")
        else:
          mcol3.success(f"Decision: {action}")

        with st.expander("View Raw API Response"):
            st.json(res_data)

      else:
        st.error(f"API Error [{response.status_code}]: {response.text}")
    except Exception as e:
      st.error(
          f"Connection failed: Could not reach backend server. Error: {e}"
      )

with tab2:
  st.subheader("Bulk Batch CSV Risk Evaluation")
  st.markdown("Upload a CSV file containing multiple transactions (e.g., your 500+ record dataset) to process them concurrently.")
  
  uploaded_file = st.file_uploader("Upload Transaction CSV", type=["csv"])

  if uploaded_file is not None:
    df_input = pd.read_csv(uploaded_file)
    st.write(f"Preview of Uploaded Data ({len(df_input)} total records loaded):", df_input.head())

    if st.button("Evaluate Batch CSV", type="primary"):
      transactions_list = df_input.to_dict(orient="records")
      batch_payload = {"transactions": transactions_list}
      
      batch_endpoint = api_endpoint.replace("/evaluate-fraud", "/batch-evaluate")
      headers = {"x-api-key": institution_api_key, "Content-Type": "application/json"}

      try:
        with st.spinner("Processing batch evaluation through Render gateway..."):
          response = requests.post(batch_endpoint, json=batch_payload, headers=headers)
          
        if response.status_code == 200:
          res_data = response.json()
          evaluations = res_data.get("evaluations", [])
          
          st.success(f"Successfully processed {res_data.get('total_processed')} transactions for {res_data.get('evaluated_institution')}")
          
          df_results = pd.DataFrame(evaluations)
          st.dataframe(df_results, use_container_width=True)
          
          csv_export = df_results.to_csv(index=False).encode('utf-8')
          st.download_button(
              label="Download Evaluation Results CSV",
              data=csv_export,
              file_name="fraud_evaluation_results.csv",
              mime="text/csv",
          )
        else:
          st.error(f"API Error [{response.status_code}]: {response.text}")
      except Exception as e:
        st.error(f"Connection failed: {e}")

with tab3:
  st.subheader("Immutable Regulatory Audit Trail")
  st.markdown(
      "Real-time view of historical decisions fetched securely from the Render cloud backend."
  )

  if st.button("Refresh Audit Logs"):
    st.rerun()

  try:
    audit_endpoint = api_endpoint.replace("/evaluate-fraud", "/audit-logs")
    headers = {"x-api-key": institution_api_key}
    
    response = requests.get(audit_endpoint, headers=headers)
    
    if response.status_code == 200:
      audit_data = response.json()
      
      if isinstance(audit_data, list) and audit_data:
        df_audit = pd.DataFrame(audit_data)
        st.dataframe(df_audit, use_container_width=True)
      elif isinstance(audit_data, dict) and "error" in audit_data:
        st.warning(audit_data["error"])
      else:
        st.info("No audit logs recorded yet. Run an evaluation first.")
    else:
      st.error(f"API Error [{response.status_code}]: {response.text}")
      
  except Exception as e:
    st.warning(f"Could not connect to audit gateway: {e}")