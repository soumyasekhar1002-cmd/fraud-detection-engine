import os
import pandas as pd
import requests
import streamlit as st
import time

st.set_page_config(
    page_title="Institutional Fraud Intelligence Portal",
    page_icon="🛡️",
    layout="wide",
)

# --- REMOVE TOP WHITE SPACE / STREAMLIT HEADER GAP ---
st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 0rem !important;
        }
        header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- BACKEND API CONFIGURATION ---
BACKEND_URL = "https://fraud-detection-engine-v5wj.onrender.com"

# --- OAUTH CONFIGURATION ---
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", st.secrets.get("GOOGLE_CLIENT_ID", "YOUR_GOOGLE_CLIENT_ID"))
REDIRECT_URI = os.getenv("REDIRECT_URI", st.secrets.get("REDIRECT_URI", "https://fraud-detection-engine-eo9csc49cqkfpvm6ygvsqy.streamlit.app/"))

# --- SESSION STATE INITIALIZATION ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "user_email" not in st.session_state:
    st.session_state["user_email"] = ""
if "institution_name" not in st.session_state:
    st.session_state["institution_name"] = ""
if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False
if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""

# --- HANDLE GOOGLE OAUTH CALLBACK FROM QUERY PARAMS ---
query_params = st.query_params
if "code" in query_params and not st.session_state["authenticated"]:
    code = query_params["code"]
    provider = query_params.get("provider", "")
    
    if provider == "google":
        try:
            res = requests.post(f"{BACKEND_URL}/auth/google?code={code}")
            if res.status_code == 200:
                user_data = res.json()
                st.session_state["authenticated"] = True
                st.session_state["user_email"] = user_data["email"]
                st.session_state["institution_name"] = user_data["institution_name"]
                st.session_state["api_key"] = user_data["api_key"]
                st.session_state["is_admin"] = user_data["is_admin"]
                st.success("Successfully authenticated with Google!")
                st.query_params.clear()
                time.sleep(0.5)
                st.rerun()
            else:
                try:
                    err_detail = res.json().get("detail", "Google authentication failed.")
                except Exception:
                    err_detail = f"Server Error [{res.status_code}]"
                st.error(err_detail)
        except Exception as e:
            st.error(f"Google auth connection error: {e}")

# --- SECURE LOGIN / SIGNUP / RECOVERY GATEKEEPER ---
if not st.session_state["authenticated"]:
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center;'>🛡️ Secure Portal Access</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Enterprise Fraud Detection & Regulatory Audit Gateway</p>", unsafe_allow_html=True)
        
        auth_mode = st.radio(
            "Authentication Mode", 
            ["🔑 Sign In", "📝 Register Account", "✉️ Verify Email", "🔄 Forgot Password"], 
            horizontal=True, 
            label_visibility="collapsed"
        )
        
        if auth_mode == "🔑 Sign In":
            with st.form("signin_form"):
                email_input = st.text_input("Corporate or Personal Email", placeholder="you@company.com")
                password_input = st.text_input("Password", type="password")
                submit_signin = st.form_submit_button("Sign In", use_container_width=True)
                
                if submit_signin:
                    if not email_input or not password_input:
                        st.warning("Please enter both email and password.")
                    else:
                        try:
                            response = requests.post(
                                f"{BACKEND_URL}/login",
                                json={"email": email_input, "password": password_input}
                            )
                            if response.status_code == 200:
                                user_data = response.json()
                                st.session_state["authenticated"] = True
                                st.session_state["user_email"] = user_data["email"]
                                st.session_state["institution_name"] = user_data["institution_name"]
                                st.session_state["api_key"] = user_data["api_key"]
                                st.session_state["is_admin"] = user_data["is_admin"]
                                st.success("Signed in successfully!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                try:
                                    err_detail = response.json().get("detail", "Invalid credentials or unverified email.")
                                except Exception:
                                    err_detail = f"Server Error [{response.status_code}]"
                                st.error(err_detail)
                        except Exception as e:
                            st.error(f"Connection failed: {e}")
            
            st.markdown("<p style='text-align: center; color: gray; font-size: 0.85em;'>— Or continue with Enterprise SSO —</p>", unsafe_allow_html=True)
            google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={GOOGLE_CLIENT_ID}&redirect_uri={REDIRECT_URI}?provider=google&response_type=code&scope=email%20profile"
            st.markdown(f'''
                <a href="{google_auth_url}" target="_self" style="text-decoration:none;">
                    <button style="width:100%; padding:10px; background-color:#ffffff; color:#24292e; border:1px solid #d1d5db; border-radius:6px; cursor:pointer; font-weight:500; font-size:14px; display:flex; align-items:center; justify-content:center; gap:8px;">
                        🌐 Continue with Google
                    </button>
                </a>
            ''', unsafe_allow_html=True)

        elif auth_mode == "📝 Register Account":
            with st.form("signup_form"):
                new_email = st.text_input("Work Email Address", placeholder="you@company.com")
                new_institution = st.text_input("Institution / Company Name", placeholder="Acme Financial")
                new_password = st.text_input("Create Password", type="password")
                submit_signup = st.form_submit_button("Create Account", use_container_width=True)
                
                if submit_signup:
                    if not new_email or not new_password or not new_institution:
                        st.warning("Please fill out all fields.")
                    else:
                        try:
                            response = requests.post(
                                f"{BACKEND_URL}/signup",
                                json={"email": new_email, "password": new_password, "institution_name": new_institution}
                            )
                            if response.status_code == 200:
                                data = response.json()
                                st.success(data["message"])
                                if "verification_token_demo" in data:
                                    st.info(f"Verification Token (Copy this for testing): `{data['verification_token_demo']}`")
                            else:
                                st.error("Registration failed.")
                        except Exception as e:
                            st.error(f"Connection failed: {e}")

        elif auth_mode == "✉️ Verify Email":
            with st.form("verify_form"):
                st.markdown("### Verify Your Email Address")
                v_token = st.text_input("Enter Verification Token")
                submit_verify = st.form_submit_button("Verify Account", use_container_width=True)
                
                if submit_verify:
                    try:
                        res = requests.post(f"{BACKEND_URL}/verify-email?token={v_token}")
                        if res.status_code == 200:
                            st.success(res.json()["message"])
                        else:
                            st.error("Verification failed.")
                    except Exception as e:
                        st.error(f"Error: {e}")

        elif auth_mode == "🔄 Forgot Password":
            with st.form("forgot_form"):
                st.markdown("### Request Password Reset")
                f_email = st.text_input("Registered Email")
                submit_forgot = st.form_submit_button("Send Reset Token", use_container_width=True)
                
                if submit_forgot:
                    try:
                        res = requests.post(f"{BACKEND_URL}/forgot-password?email={f_email}")
                        if res.status_code == 200:
                            data = res.json()
                            st.success(data["message"])
                            if "reset_token_demo" in data:
                                st.info(f"Password Reset Token: `{data['reset_token_demo']}`")
                        else:
                            st.error("Request failed.")
                    except Exception as e:
                        st.error(f"Error: {e}")
            
            with st.form("reset_form"):
                st.markdown("### Complete Password Reset")
                r_token = st.text_input("Reset Token")
                r_pass = st.text_input("New Password", type="password")
                submit_reset = st.form_submit_button("Update Password", use_container_width=True)
                
                if submit_reset:
                    try:
                        res = requests.post(f"{BACKEND_URL}/reset-password?token={r_token}&new_password={r_pass}")
                        if res.status_code == 200:
                            st.success(res.json()["message"])
                        else:
                            st.error("Password reset failed.")
                    except Exception as e:
                        st.error(f"Error: {e}")

    st.stop()

# --- MAIN DASHBOARD (GATED BEHIND AUTHENTICATION) ---

# --- SIDEBAR NAVIGATION & PROFILE POPOVER ---
with st.sidebar:
    # User Profile Popover Button
    with st.popover("👤 User Profile", use_container_width=True):
        st.markdown(f"**User:** `{st.session_state['user_email']}`")
        role_label = "Master Administrator" if st.session_state["is_admin"] else "Standard Analyst"
        st.markdown(f"**Role:** {role_label}")
        st.markdown(f"**Institution:** {st.session_state['institution_name']}")
        st.markdown("---")
        if st.button("🔒 Sign Out", use_container_width=True, key="popover_signout"):
            st.session_state["authenticated"] = False
            st.session_state["user_email"] = ""
            st.session_state["institution_name"] = ""
            st.session_state["is_admin"] = False
            st.session_state["api_key"] = ""
            st.rerun()

    st.markdown("---")
    st.subheader("🛡️ Navigation Menu")
    
    nav_options = [
        "📊 Dashboard & Overview",
        "🚀 Live Transaction Scoring",
        "📂 Batch CSV Evaluation",
        "📊 Regulatory Audit Logs",
        "📈 Analytics"
    ]
    
    if st.session_state["is_admin"]:
        nav_options.append("👥 User Management")

    selected_page = st.radio(
        "Select Portal View",
        nav_options,
        label_visibility="collapsed"
    )

    if st.session_state["is_admin"]:
        st.markdown("---")
        st.subheader("👑 Admin Controls")
        admin_view_mode = st.radio("View Scope", ["Global (All Tenants)", "Single Institution"])
    else:
        admin_view_mode = "Single Institution"

# --- MAIN CONTENT HEADER ---
role_badge = "👑 [MASTER ADMIN]" if st.session_state["is_admin"] else "👤 [ANALYST]"
st.title("🛡️ Institutional Real-Time Fraud Detection Portal")
st.markdown(f"Enterprise risk scoring and audit gateway. | **Signed in as:** `{st.session_state['user_email']}` {role_badge} ({st.session_state['institution_name']})")
st.markdown("---")

api_endpoint = f"{BACKEND_URL}/v1/evaluate-fraud"
institution_api_key = st.session_state["api_key"]

if selected_page == "📊 Dashboard & Overview":
    st.subheader("Comprehensive Executive Risk Analytics & Dashboard")
    if st.button("Refresh Dashboard", key="btn_dash_refresh"):
        st.rerun()

    try:
        audit_endpoint = api_endpoint.replace("/evaluate-fraud", "/audit-logs")
        headers = {"x-api-key": institution_api_key}
        response = requests.get(audit_endpoint, headers=headers)

        if response.status_code == 200:
            audit_data = response.json()
            if isinstance(audit_data, list) and audit_data:
                df_all = pd.DataFrame(audit_data)
                if st.session_state["is_admin"] and admin_view_mode == "Global (All Tenants)":
                    df_user = df_all
                    scope_label = "🌐 Global System-Wide (All Tenants)"
                else:
                    scope_label = st.session_state['institution_name']
                    if "evaluated_institution" in df_all.columns:
                        df_user = df_all[df_all["evaluated_institution"] == scope_label]
                        if df_user.empty:
                            df_user = df_all
                    else:
                        df_user = df_all
                
                st.markdown(f"### 📊 Dashboard View: `{scope_label}`")
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                user_records = len(df_user)
                user_blocked = len(df_user[df_user["decision"] == "BLOCK"]) if "decision" in df_user.columns and not df_user.empty else 0
                user_avg_risk = df_user["fraud_probability"].mean() * 100 if "fraud_probability" in df_user.columns and not df_user.empty else 0.0
                user_volume = df_user["amount"].sum() if "amount" in df_user.columns and not df_user.empty else 0.0

                col_m1.metric("Total Records", f"{user_records:,}")
                col_m2.metric("Blocked Threats", f"{user_blocked:,}")
                col_m3.metric("Avg Risk Probability", f"{user_avg_risk:.2f}%")
                col_m4.metric("Portfolio Value", f"${user_volume:,.2f}")

                st.markdown("---")
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    st.markdown("#### Decision Tier Breakdown")
                    if "decision" in df_user.columns:
                        decision_counts = df_user["decision"].value_counts()
                        st.bar_chart(decision_counts)
                    else:
                        st.info("No decision metrics available.")
                with col_c2:
                    st.markdown("#### Risk Probability Trend")
                    if "fraud_probability" in df_user.columns:
                        st.line_chart(df_user["fraud_probability"] * 100)
                    else:
                        st.info("No probability trends available.")
            else:
                st.info("No records found in audit logs for dashboard.")
        else:
            st.error(f"API Error [{response.status_code}]")
    except Exception as e:
        st.warning(f"Could not connect to backend: {e}")

elif selected_page == "🚀 Live Transaction Scoring":
    st.subheader("Single Transaction Risk Evaluation Form")
    col1, col2 = st.columns(2)
    with col1:
        transaction_id = st.text_input("Transaction ID", value=f"TXN_{pd.Timestamp.now().strftime('%H%M%S')}")
        cardholder_id = st.text_input("Cardholder ID", value="USER_4392")
        amount = st.number_input("Transaction Amount ($)", min_value=1.0, value=250.0)
        merchant_category = st.selectbox("Merchant Category", ["retail", "electronics", "travel", "grocery", "digital_goods"])
    with col2:
        distance_from_home = st.number_input("Distance From Home (miles)", min_value=0.0, value=12.5)
        velocity_1h = st.slider("Velocity (Transactions in last 1 hour)", 0, 20, 1)
        velocity_24h = st.slider("Velocity (Transactions in last 24 hours)", 0, 50, 3)
        is_international = st.selectbox("Is International Transaction?", [0, 1], format_func=lambda x: "Yes" if x == 1 else "No")

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
                action = res_data.get("decision", "REVIEW")
                institution = res_data.get("evaluated_institution", st.session_state['institution_name'])

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
            st.error(f"Connection failed: {e}")

elif selected_page == "📂 Batch CSV Evaluation":
    st.subheader("Bulk Batch CSV Risk Evaluation")
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
            uploaded_file.seek(0)

            try:
                progress_bar = st.progress(0)
                status_text = st.empty()
                chunks = list(pd.read_csv(uploaded_file, chunksize=chunk_size))
                total_chunks = len(chunks)

                for i, chunk in enumerate(chunks):
                    status_text.text(f"Processing chunk {i + 1} of {total_chunks}...")
                    transactions_list = chunk.to_dict(orient="records")
                    batch_payload = {"transactions": transactions_list}
                    try:
                        response = requests.post(batch_endpoint, json=batch_payload, headers=headers, timeout=60)
                        if response.status_code == 200:
                            res_data = response.json()
                            evaluations = res_data.get("evaluations", [])
                            all_evaluations.extend(evaluations)
                            total_processed_count += res_data.get("total_processed", len(evaluations))
                    except Exception:
                        pass
                    progress_bar.progress((i + 1) / total_chunks)

                status_text.text("Batch processing complete!")
                if all_evaluations:
                    st.success(f"Successfully processed {total_processed_count} records!")
                    df_results = pd.DataFrame(all_evaluations)
                    st.dataframe(df_results, use_container_width=True)
                else:
                    st.error("Batch processing failed.")
            except Exception as e:
                st.error(f"Batch connection failed: {e}")

elif selected_page == "📊 Regulatory Audit Logs":
    st.subheader("Immutable Regulatory Audit Trail")
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
                if st.session_state["is_admin"] and admin_view_mode == "Single Institution":
                    all_institutions = df_audit["evaluated_institution"].unique().tolist() if "evaluated_institution" in df_audit.columns else []
                    if all_institutions:
                        selected_audit_inst = st.selectbox("Filter Audit Logs by Institution", all_institutions, key="audit_inst_filter")
                        df_audit = df_audit[df_audit["evaluated_institution"] == selected_audit_inst]
                st.dataframe(df_audit, use_container_width=True)
            else:
                st.info("No audit logs recorded yet.")
        else:
            st.error(f"API Error [{response.status_code}]")
    except Exception as e:
        st.warning(f"Could not connect: {e}")

elif selected_page == "📈 Analytics":
    st.subheader("Comprehensive Executive Risk Analytics")
    if st.button("Refresh Analytics", key="btn_analytics_refresh"):
        st.rerun()

    try:
        audit_endpoint = api_endpoint.replace("/evaluate-fraud", "/audit-logs")
        headers = {"x-api-key": institution_api_key}
        response = requests.get(audit_endpoint, headers=headers)

        if response.status_code == 200:
            audit_data = response.json()
            if isinstance(audit_data, list) and audit_data:
                df_all = pd.DataFrame(audit_data)
                scope_label = st.session_state['institution_name']
                if "evaluated_institution" in df_all.columns:
                    df_user = df_all[df_all["evaluated_institution"] == scope_label]
                    if df_user.empty:
                        df_user = df_all
                else:
                    df_user = df_all
                
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("Total Records", f"{len(df_user):,}")
                col_m2.metric("Blocked Threats", f"{len(df_user[df_user['decision'] == 'BLOCK']):,}" if 'decision' in df_user.columns else "0")
                col_m3.metric("Avg Risk Probability", f"{(df_user['fraud_probability'].mean() * 100):.2f}%" if 'fraud_probability' in df_user.columns else "0.0%")
                col_m4.metric("Portfolio Value", f"${df_user['amount'].sum():,.2f}" if 'amount' in df_user.columns else "$0.00")
            else:
                st.info("No analytics data available.")
        else:
            st.error(f"API Error [{response.status_code}]")
    except Exception as e:
        st.warning(f"Could not connect: {e}")

elif selected_page == "👥 User Management":
    st.subheader("👥 User Account Verification & Management")
    st.markdown("Manage and activate registered user accounts directly from the application.")
    
    if st.button("Refresh User Directory", key="btn_users_refresh"):
        st.rerun()

    try:
        users_endpoint = f"{BACKEND_URL}/admin/users"
        headers = {"x-api-key": institution_api_key}
        res = requests.get(users_endpoint, headers=headers)
        
        if res.status_code == 200:
            users_list = res.json()
            if users_list:
                df_users = pd.DataFrame(users_list)
                st.dataframe(df_users, use_container_width=True)
                
                st.markdown("#### ⚡ Quick Account Activation")
                with st.form("activate_user_form"):
                    target_email = st.text_input("Enter User Email to Activate/Verify")
                    submit_activate = st.form_submit_button("Activate & Verify User Profile", type="primary")
                    
                    if submit_activate:
                        if not target_email:
                            st.warning("Please enter a valid email address.")
                        else:
                            act_res = requests.post(f"{BACKEND_URL}/admin/verify-user?email={target_email}", headers=headers)
                            if act_res.status_code == 200:
                                st.success(f"User `{target_email}` has been successfully verified and activated!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error(f"Failed to activate user: {act_res.text}")
            else:
                st.info("No registered users found.")
        else:
            st.info("User management endpoint is initializing or awaiting backend route support. You can also verify users directly via database SQL: `UPDATE users SET is_verified = TRUE WHERE email = '...';`")
    except Exception as e:
        st.warning(f"Could not fetch user directory: {e}")