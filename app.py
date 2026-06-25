import streamlit as st
import pandas as pd
from supabase import create_client, Client
import datetime
import urllib.request
import hashlib

st.set_page_config(page_title="Enterprise WMS Platform", page_icon="📦", layout="centered")
st.markdown("<style>.stButton>button { width: 100%; height: 50px; font-size: 16px; }</style>", unsafe_allow_html=True)

# --- BACKEND SUPABASE CONNECTION ---
SUPABASE_URL = "https://nnkxlobacrvfcisnaazf.supabase.co"
SUPABASE_KEY = "sb_publishable_PqVWQyb9xcCysxxx93UJMA_G-g3LQHS"

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error("Database connection failure. Please review credentials.")
    st.stop()

# --- HELPER SECURITY UTILITIES ---
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@st.cache_data(ttl=60)
def get_client_ip():
    try:
        # Resolves the public IP address routing this browser thread
        return urllib.request.urlopen('https://api.ipify.org').read().decode('utf8')
    except:
        return "127.0.0.1"

# --- CORE SESSION STATE STATE ENGINES ---
if "user_session" not in st.session_state:
    st.session_state.user_session = None

current_ip = get_client_ip()

# --- AUTOMATED IP PASS-THROUGH LOG-IN TRACE ---
if st.session_state.user_session is None and current_ip != "127.0.0.1":
    try:
        auto_ip_check = supabase.table("user_profiles").select("*").eq("last_known_ip", current_ip).execute()
        if auto_ip_check.data:
            st.session_state.user_session = auto_ip_check.data[0]
    except Exception:
        pass # Gracefully handle cases where the user table isn't fully ready yet

# ==========================================
# AUTHENTICATION PORTAL (SIGN IN / SIGN UP)
# ==========================================
if st.session_state.user_session is None:
    st.title("🔐 Enterprise Inventory Gatekeeper")
    auth_mode = st.tabs(["Sign In", "Create Corporate Account"])
    
    with auth_mode[0]:
        st.subheader("Sign In")
        login_user = st.text_input("Username:", key="log_user").strip()
        login_pass = st.text_input("Password:", type="password", key="log_pass").strip()
        
        if st.button("🔑 Log In to Workspace"):
            if login_user and login_pass:
                target_hash = hash_password(login_pass)
                user_query = supabase.table("user_profiles").select("*").eq("username", login_user).eq("password_hash", target_hash).execute()
                
                if user_query.data:
                    user_record = user_query.data[0]
                    # Bind the client device IP to keep them logged in dynamically
                    supabase.table("user_profiles").update({"last_known_ip": current_ip}).eq("id", user_record["id"]).execute()
                    user_record["last_known_ip"] = current_ip
                    st.session_state.user_session = user_record
                    st.success("Access authorized. Redirecting...")
                    st.rerun()
                else:
                    st.error("Invalid username or password configuration match.")
            else:
                st.warning("Please input both login fields.")
                
    with auth_mode[1]:
        st.subheader("Create Corporate Account")
        reg_user = st.text_input("Choose Username:", key="reg_user").strip()
        reg_pass = st.text_input("Choose Strong Password:", type="password", key="reg_pass").strip()
        reg_code = st.text_input("⚠️ One-Time Inventory Activation Access Code:", type="password", key="reg_code").strip().upper()
        
        if st.button("➕ Register Account"):
            if not reg_user or not reg_pass or not reg_code:
                st.warning("All verification and creation forms require completion inputs.")
            else:
                check_dup = supabase.table("user_profiles").select("username").eq("username", reg_user).execute()
                if check_dup.data:
                    st.error("That account identity username is already claimed.")
                else:
                    # Construct and insert the fresh user database entity block
                    hashed_p = hash_password(reg_pass)
                    new_user_data = {
                        "username": reg_user,
                        "password_hash": hashed_p,
                        "access_code": reg_code,
                        "last_known_ip": current_ip
                    }
                    supabase.table("user_profiles").insert(new_user_data).execute()
                    st.success("Account constructed cleanly! Please toggle to Sign In to lock in authorization access.")
    st.stop()

# ==========================================
# SYSTEM WORKSPACE CONTEXT LOADED
# ==========================================
user_profile = st.session_state.user_session
user_code = user_profile["access_code"]
profile_db_id = user_profile["id"]

# Dynamic Header Display
col_header, col_exit = st.columns([4, 1])
with col_header:
    st.title(user_profile["terminal_title"])
    st.caption(f"Operator identity: **{user_profile['username']}** | Channel Context: `{user_code}`")
with col_exit:
    st.write("") # Layout alignment element
    if st.button("🔒 Sign Out"):
        # Strip persistent device token links when logging out intentionally
        supabase.table("user_profiles").update({"last_known_ip": None}).eq("id", profile_db_id).execute()
        st.session_state.user_session = None
        st.rerun()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔄 Scan In/Out", "🔍 Search", "📊 Live Stock & Edit", "📜 Past Records", "⚙️ Preferences"])

# ==========================================
# TAB 1: OPERATIONAL TERMINAL (IN / OUT FLOW)
# ==========================================
with tab1:
    st.subheader("Process Stock Movement")
    sku_input = st.text_input("📋 Enter or Scan SKU / Barcode:").strip()
    col1, col2 = st.columns(2)
    with col1:
        action = st.radio("Movement Direction:", ["IN (Receive)", "OUT (Pick)"])
    with col2:
        qty = st.number_input("Quantity:", min_value=1, value=1)
    location_input = st.text_input("📍 Location Matrix:").strip().upper()

    if st.button("🚀 Commit Transaction to Database"):
        if not sku_input or not location_input:
            st.warning("Validation Error: SKU and Location fields are required.")
        else:
            query = supabase.table("inventory_items").select("*").eq("sku", sku_input).eq("location", location_input).eq("access_code", user_code).execute()
            existing_records = query.data
            movement_type = "IN" if "IN" in action else "OUT"
            final_qty_change = qty if movement_type == "IN" else -qty
            
            if existing_records:
                current_qty = existing_records[0]["quantity"]
                new_qty = current_qty + final_qty_change
                if new_qty < 0:
                    st.error(f"❌ Aborted: Insufficient stock. Current Level: {current_qty}")
                elif new_qty == 0:
                    supabase.table("inventory_items").delete().eq("id", existing_records[0]["id"]).execute()
                    supabase.table("stock_ledger").insert({"sku": sku_input, "movement_type": movement_type, "quantity": qty, "access_code": user_code}).execute()
                    st.success("🗑️ Row cleared.")
                else:
                    supabase.table("inventory_items").update({"quantity": new_qty, "last_updated": datetime.datetime.now().isoformat()}).eq("id", existing_records[0]["id"]).execute()
                    supabase.table("stock_ledger").insert({"sku": sku_input, "movement_type": movement_type, "quantity": qty, "access_code": user_code}).execute()
                    st.success(f"✅ Updated Stock! New Total: {new_qty}")
            else:
                if movement_type == "OUT":
                    st.error("❌ Aborted: Cannot pick an item from a non-existent location.")
                else:
                    supabase.table("inventory_items").insert({"sku": sku_input, "item_name": f"Item {sku_input}", "location": location_input, "quantity": qty, "access_code": user_code}).execute()
                    supabase.table("stock_ledger").insert({"sku": sku_input, "movement_type": movement_type, "quantity": qty, "access_code": user_code}).execute()
                    st.success(f"📦 Created new batch at location: {location_input}!")

# ==========================================
# TAB 2: CASE-INSENSITIVE SEARCH
# ==========================================
with tab2:
    st.subheader("Smart SKU Finder")
    search_sku = st.text_input("🔍 Search SKU (Case Insensitive):").strip()
    
    if search_sku:
        res = supabase.table("inventory_items").select("*").ilike("sku", search_sku).eq("access_code", user_code).execute()
        if res.data:
            df = pd.DataFrame(res.data)
            for _, row in df.iterrows():
                metadata_disp = f" | Notes: {row['metadata']}" if row['metadata'] else ""
                st.info(f"📍 **Location:** `{row['location']}` | 🔢 **Stock:** {row['quantity']} units{metadata_disp}")
        else:
            st.info("No matching item inventory trace located in your workspace.")

# ==========================================
# TAB 3: LIVE STOCK TRACKING & EDITS
# ==========================================
if st.button("💾 Save Grid Configuration Updates"):
            with st.spinner("Synchronizing batch edits..."):
                fixed_sys_cols = ["Internal DB ID", "SKU", "Item Name", "Location", "Quantity"]
                
                # 🛠️ FIXED: Indentation reset cleanly for the active row loop iteration
                for idx, row in edited_df.iterrows():
                    db_id = row["Internal DB ID"]
                    meta_payload = {}
                    
                    for col in edited_df.columns:
                        if col not in fixed_sys_cols and pd.notna(row[col]) and str(row[col]).strip() != "":
                            meta_payload[col] = str(row[col])
                            
                    update_data = {
                        "sku": str(row["SKU"]),
                        "item_name": str(row["Item Name"]),
                        "location": str(row["Location"]),
                        "quantity": int(row["Quantity"]),
                        "metadata": meta_payload,
                        "last_updated": datetime.datetime.now().isoformat()
                    }
                    supabase.table("inventory_items").update(update_data).eq("id", db_id).execute()
                    
                st.session_state.custom_columns = []
                st.success("🎉 Grid updates saved successfully!")
                st.rerun()
