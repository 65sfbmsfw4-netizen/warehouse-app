import streamlit as st
import pandas as pd
from supabase import create_client, Client
import datetime
import urllib.request
import hashlib

st.set_page_config(page_title="Enterprise WMS Platform", page_icon="📦", layout="centered")

# --- CUSTOM INTERFACE STYLING ---
st.markdown("""
<style>
    .stButton>button { width: 100%; height: 50px; font-size: 16px; }
    .low-stock-alert { background-color: #ffcccc; padding: 10px; border-radius: 5px; border-left: 5px solid #ff0000; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- SECURE SUPABASE CONNECTION CONFIGURATION ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

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
        return urllib.request.urlopen('https://api.ipify.org').read().decode('utf8')
    except:
        return "127.0.0.1"

# --- CORE SESSION STATE ENGINES ---
if "user_session" not in st.session_state:
    st.session_state.user_session = None
if "batch_queue" not in st.session_state:
    st.session_state.batch_queue = []

current_ip = get_client_ip()

# --- AUTOMATED IP PASS-THROUGH LOG-IN TRACE ---
if st.session_state.user_session is None and current_ip != "127.0.0.1":
    try:
        auto_ip_check = supabase.table("user_profiles").select("*").eq("last_known_ip", current_ip).execute()
        if auto_ip_check.data:
            st.session_state.user_session = auto_ip_check.data[0]
    except Exception:
        pass 

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
                user_query = supabase.table("user_profiles").select("*").ilike("username", login_user).eq("password_hash", target_hash).execute()
                
                if user_query.data:
                    user_record = user_query.data[0]
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
                check_dup = supabase.table("user_profiles").select("username").ilike("username", reg_user).execute()
                if check_dup.data:
                    st.error("That account identity username is already claimed.")
                else:
                    hashed_p = hash_password(reg_pass)
                    new_user_data = {
                        "username": reg_user,
                        "password_hash": hashed_p,
                        "access_code": reg_code,
                        "last_known_ip": current_ip,
                        "authorized_locations": ["A1", "B1", "C1"],
                        "custom_data_fields": []
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
operator_username = user_profile["username"]

configured_locations = user_profile.get("authorized_locations") or ["A1", "B1", "C1"]
configured_custom_bars = user_profile.get("custom_data_fields") or []

col_header, col_exit = st.columns([4, 1])
with col_header:
    st.title(user_profile.get("terminal_title", "Mobile WMS Terminal"))
    st.caption(f"Operator identity: **{operator_username}** | Channel Context: `{user_code}`")
with col_exit:
    st.write("") 
    if st.button("🔒 Sign Out"):
        supabase.table("user_profiles").update({"last_known_ip": None}).eq("id", profile_db_id).execute()
        st.session_state.user_session = None
        st.session_state.batch_queue = []
        st.rerun()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔄 Movement & Transfer", "🔍 Smart Finder", "📊 Live Stock Grid", "📜 Audit Ledger", "⚙️ Preferences"])

# ==========================================
# TAB 1: OPERATIONAL TERMINAL (UPDATED LAYOUT ENGINE)
# ==========================================
with tab1:
    st.subheader("Process Stock Logistics Flow")
    
    # 🛠️ RENAMED: Mode selection row
    op_mode = st.radio("Logistics Action Mode:", ["Single Entry", "Multiple Entry"], horizontal=True)
    
    st.markdown("---")
    
    # 📍 RESTORED: Input line returned to the top context tier row
    sku_or_stream = st.text_area("📋 Enter SKU Code or Scan Continuous Barcode Stream (use commas to separate context, e.g., apple, apple):", key="wms_unified_input_bar").strip()
    
    col_dir, col_qt = st.columns(2)
    with col_dir:
        action = st.radio("Action Assignment Type:", ["IN (Receive Stock)", "OUT (Pick Stock)", "TRANSFER (Relocate Matrix)"])
    with col_qt:
        qty = st.number_input("Base Transaction Quantity Factor:", min_value=1, value=1)
        
    if action == "TRANSFER (Relocate Matrix)":
        col_f, col_t = st.columns(2)
        with col_f:
            loc_from = st.selectbox("Source Location (FROM):", options=configured_locations, key="src_loc")
            location_input = loc_from
        with col_t:
            loc_to = st.selectbox("Destination Location (TO):", options=configured_locations, key="dst_loc")
    else:
        location_input = st.selectbox("Target Warehouse Location Matrix:", options=configured_locations)
        loc_from, loc_to = None, None

    # Gather additional metadata configuration profiles attributes
    scanned_metadata = {}
    if configured_custom_bars and action != "TRANSFER (Relocate Matrix)":
        st.caption("📝 Transaction Extra Attributes Payload:")
        for bar_field in configured_custom_bars:
            scanned_metadata[bar_field] = st.text_input(f"Enter {bar_field}:", key=f"scan_m_{bar_field}").strip()

    # Core engine transaction router
    def execute_transaction(sku, act, q, loc, l_from=None, l_to=None, meta=None):
        if meta is None: meta = {}
        movement_type = "IN" if "IN" in act else "OUT" if "OUT" in act else "TRANSFER"
        
        if movement_type == "TRANSFER":
            src_q = supabase.table("inventory_items").select("*").eq("sku", sku).eq("location", l_from).eq("access_code", user_code).eq("is_archived", False).execute()
            if not src_q.data or src_q.data[0]["quantity"] < q:
                return False, f"❌ Aborted '{sku}': Insufficient quantities inside source node {l_from}."
            
            rem_qty = src_q.data[0]["quantity"] - q
            if rem_qty == 0:
                supabase.table("inventory_items").update({"quantity": 0, "is_archived": True}).eq("id", src_q.data[0]["id"]).execute()
            else:
                supabase.table("inventory_items").update({"quantity": rem_qty}).eq("id", src_q.data[0]["id"]).execute()
                
            dst_q = supabase.table("inventory_items").select("*").eq("sku", sku).eq("location", l_to).eq("access_code", user_code).execute()
            if dst_q.data:
                new_dst_q = dst_q.data[0]["quantity"] + q
                supabase.table("inventory_items").update({"quantity": new_dst_q, "is_archived": False, "last_updated": datetime.datetime.now().isoformat()}).eq("id", dst_q.data[0]["id"]).execute()
            else:
                supabase.table("inventory_items").insert({"sku": sku, "item_name": f"Item {sku}", "location": l_to, "quantity": q, "access_code": user_code, "metadata": src_q.data[0].get("metadata", {})}).execute()
                
            supabase.table("stock_ledger").insert({"sku": sku, "movement_type": "OUT", "quantity": q, "access_code": user_code, "operator": operator_username}).execute()
            supabase.table("stock_ledger").insert({"sku": sku, "movement_type": "IN", "quantity": q, "access_code": user_code, "operator": operator_username}).execute()
            return True, f"✅ Successfully transferred {q} units of {sku} from {l_from} to {l_to}!"
            
        else:
            query = supabase.table("inventory_items").select("*").eq("sku", sku).eq("location", loc).eq("access_code", user_code).execute()
            final_qty_change = q if movement_type == "IN" else -q
            
            if query.data:
                record = query.data[0]
                current_qty = record["quantity"] if not record["is_archived"] else 0
                new_qty = current_qty + final_qty_change
                
                current_meta = record.get("metadata") or {}
                for k, v in meta.items():
                    if v: current_meta
