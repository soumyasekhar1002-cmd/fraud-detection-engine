import pandas as pd
import requests
import streamlit as st
import time

st.set_page_config(
    page_title="Institutional Fraud Intelligence Portal",
    page_icon="🛡️",
    layout="wide",
)

# --- SESSION STATE INITIALIZATION FOR AUTHENTICATION ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "institution_name" not in st.session_state:
    st.session_state["institution_name"] = ""
if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""

# Valid institutional API keys mapping
VALID_INSTITUTIONS = {
    "bank_alpha_secret_key_991": "Alpha Bank Corp",
    "global_trust_key_777": "Global Trust Bank"
}

# --- LOGIN SCREEN GATEKEEPER ---
if not st.session_state["authenticated"]:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center;'>🛡️ Secure Portal Login</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Institutional Fraud Detection & Audit Gateway</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            input_key = st.text_input("Institutional API Key (`x-api-key`)", type="password")
            submit_login = st.form_submit_button("Authenticate Access", use_container_width=True)
            
            if submit_login:
                if input_key in VALID_INSTITUTIONS:
                    st.session_state["authenticated"] = True
                    st.session_state["institution_name"] = VALID_INSTITUTIONS[input_key]
                    st.session_state["api_key"] = input_key
                    st.success(f"Successfully authenticated as {VALID_INSTITUTIONS[input_key]}!")
                    time.sleep(0.8)
                    st.rerun()
                else:
                    st.error("Invalid API Key. Access Denied.")
        
        st.info("ℹ️ **Demo Keys for Testing:**\n* `bank_alpha_secret_key_991`\n* `global_trust_key_777`")
    
    st.stop()  # Halt execution of the rest of the app until authenticated

# --- MAIN DASHBOARD (GATED BEHIND LOGIN) ---
st.title("🛡️ Institutional Real-Time Fraud Detection Portal")
st.markdown(f"Enterprise-grade transaction risk scoring and regulatory audit viewer. | **Logged in as:** `{st.session_state['institution_name']}`")

# Sidebar for Session Controls
st.sidebar.header("🔐 Session Management")
st.sidebar.write(f"**Institution:** {st.session_state['institution_name']}")
if st.sidebar.button("🔒 Logout", use_container_width=True):
    st.session_state["authenticated"] = False
    st.session_state["institution_name"] = ""
    st.session_state["api_key"] = ""
    st.rerun()

api_endpoint = st.sidebar.text_input(
    "FastAPI Gateway URL", value="https://fraud-detection-engine-v5wj.onrender.com/v1/evaluate-fraud"
)

institution_api_key = st.session_state["api_key"]

# Define 4 distinct functional tabs
tab1, tab2, tab3, tab4 = st.tabs(
    ["🚀 Live Transaction Scoring", "📂 Batch CSV Evaluation", "📊 Regulatory Audit Logs", "📈 Analytics"]
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
  st.subheader("Bulk Batch CSV Risk Evaluation (Fault-Tolerant Chunked Processing)")
  st.markdown("Upload large transaction CSV files (e.g., 50,000+ records). Files are processed securely in chunks with automated error recovery.")
  
  chunk_size = st.slider("Chunk Size per Request", min_value=100, max_value=1000, value=500, step=100)
  uploaded_file = st.file_uploader("Upload Transaction CSV", type=["csv"])

  if uploaded_file is not None:
    preview_df = pd.read_csv(uploaded_file, nrows=5)
    st.write("Preview of Uploaded Data:", preview_df)

    if st.button("Evaluate Batch CSV (Robust)", type="primary"):
      batch_endpoint = api_endpoint.replace("/evaluate-fraud", "/batch-evaluate")
      headers = {"x-api-key": institution_api_key, "Content-Type": "application/json"}
      
      all_evaluations = []
      total_processed_count = 0
      failed_chunks = 0
      
      uploaded_file.seek(0)

      try:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        chunks = list(pd.read_csv(uploaded_file, chunksize=chunk_size))
        total_chunks = len(chunks)

        for i, chunk in enumerate(chunks):
          status_text.text(f"Processing chunk {i + 1} of {total_chunks} ({len(chunk)} records)...")
          
          transactions_list = chunk.to_dict(orient="records")
          batch_payload = {"transactions": transactions_list}
          
          try:
            response = requests.post(batch_endpoint, json=batch_payload, headers=headers, timeout=60)
            
            if response.status_code == 200:
              res_data = response.json()
              evaluations = res_data.get("evaluations", [])
              all_evaluations.extend(evaluations)
              total_processed_count += res_data.get("total_processed", len(evaluations))
            else:
              failed_chunks += 1
          except Exception:
            failed_chunks += 1
            
          progress_bar.progress((i + 1) / total_chunks)
          time.sleep(0.1)

        status_text.text("Batch processing complete!")
        
        if all_evaluations:
          st.success(f"Successfully processed {total_processed_count} records across chunks! (Failed chunks: {failed_chunks})")
          
          df_results = pd.DataFrame(all_evaluations)
          st.dataframe(df_results, use_container_width=True)
          
          csv_export = df_results.to_csv(index=False).encode('utf-8')
          st.download_button(
              label="Download Full Evaluation Results CSV",
              data=csv_export,
              file_name="fraud_evaluation_results_chunked.csv",
              mime="text/csv",
          )
        else:
          st.error("Batch processing failed to retrieve evaluations. Check backend logs.")
          
      except Exception as e:
        st.error(f"Batch connection failed: {e}")

with tab3:
  st.subheader("Immutable Regulatory Audit Trail")
  st.markdown(
      "Real-time view of historical decisions fetched securely from the Render cloud backend."
  )

  if st.button("Refresh Audit Logs", key="btn_audit_refresh"):
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

with tab4:
  st.subheader("Comprehensive Executive Risk Analytics")
  st.markdown(
      "Comprehensive analysis of **all available historical records** in your audit database."
  )

  if st.button("Refresh Analytics", key="btn_analytics_refresh"):
    st.rerun()

  try:
    audit_endpoint = api_endpoint.replace("/evaluate-fraud", "/audit-logs")
    headers = {"x-api-key": institution_api_key}
    
    response = requests.get(audit_endpoint, headers=headers)
    
    if response.status_code == 200:
      audit_data = response.json()
      
      if isinstance(audit_data, list) and audit_data:
        df_audit = pd.DataFrame(audit_data)
        
        # 1. Global Metrics across all rows
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        total_records = len(df_audit)
        
        decision_col = "decision_tier" if "decision_tier" in df_audit.columns else ("action" if "action" in df_audit.columns else None)
        total_blocked = len(df_audit[df_audit[decision_col] == "BLOCK"]) if decision_col else 0
        
        avg_risk = df_audit["fraud_probability"].mean() * 100 if "fraud_probability" in df_audit.columns else 0.0
        total_volume = df_audit["amount"].sum() if "amount" in df_audit.columns else 0.0

        col_m1.metric("Total Records Analyzed", f"{total_records:,}")
        col_m2.metric("Total Blocked Threats", f"{total_blocked:,}")
        col_m3.metric("Average Fraud Probability", f"{avg_risk:.2f}%")
        col_m4.metric("Total Portfolio Value", f"${total_volume:,.2f}")

        st.markdown("---")

        # 2. Comprehensive Multi-Chart Breakdown
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
          st.markdown("#### 🛡️ Decision Tier Breakdown")
          if decision_col:
            decision_counts = df_audit[decision_col].value_counts()
            st.bar_chart(decision_counts)
          else:
            st.info("Decision column unavailable.")
            
        with chart_col2:
          st.markdown("#### 🛍️ Merchant Category Volume Spread")
          if "merchant_category" in df_audit.columns:
            merchant_counts = df_audit["merchant_category"].value_counts()
            st.bar_chart(merchant_counts)
          else:
            st.info("Merchant category field not found in audit logs.")

        st.markdown("---")
        st.markdown("#### 📈 Full Dataset Fraud Risk Distribution (All Records)")
        if "fraud_probability" in df_audit.columns:
          st.line_chart(df_audit["fraud_probability"].reset_index(drop=True))
        else:
          st.info("Probability vector unavailable.")
            
      elif isinstance(audit_data, dict) and "error" in audit_data:
        st.warning(audit_data["error"])
      else:
        st.info("No analytics data available yet. Evaluate some transactions first.")
    else:
      st.error(f"API Error [{response.status_code}]: {response.text}")
      
  except Exception as e:
    st.warning(f"Could not connect to analytics gateway: {e}")