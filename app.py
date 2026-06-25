import streamlit as st
import pandas as pd
from supabase import create_client, Client
import datetime
import urllib.request
import hashlib

st.set_page_config(page_title="Enterprise WMS Platform", page_icon="📦", layout="centered")
st.markdown("<style>.stButton>button { width: 100%; height: 50px; font-size: 16px; }</style>", unsafe_allow_html=True)

# --- SECURE SUPABASE CONNECTION CONFIGURATION ---
# Safely reading from Streamlit's hidden cloud secrets settings
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
operator_username = user_profile["username"] # Capturing current operator profile name

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
        
    location_input = st.selectbox("📍 Location Matrix:", options=configured_locations)

    scanned_metadata = {}
    if configured_custom_bars:
        st.markdown("---")
        st.caption("📝 Additional Custom Attributes Entry:")
        for bar_field in configured_custom_bars:
            scanned_metadata[bar_field] = st.text_input(f"Enter {bar_field}:", key=f"scan_meta_{bar_field}").strip()

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
                
                current_meta = existing_records[0].get("metadata") or {}
                if not isinstance(current_meta, dict):
                    current_meta = {}
                for k, v in scanned_metadata.items():
                    if v: current_meta[k] = v

                if new_qty < 0:
                    st.error(f"❌ Aborted: Insufficient stock. Current Level: {current_qty}")
                elif new_qty == 0:
                    supabase.table("inventory_items").delete().eq("id", existing_records[0]["id"]).execute()
                    # 🛠️ FIXED: Added operator tracking to ledger write
                    supabase.table("stock_ledger").insert({"sku": sku_input, "movement_type": movement_type, "quantity": qty, "access_code": user_code, "operator": operator_username}).execute()
                    st.success("🗑️ Row cleared.")
                else:
                    supabase.table("inventory_items").update({"quantity": new_qty, "metadata": current_meta, "last_updated": datetime.datetime.now().isoformat()}).eq("id", existing_records[0]["id"]).execute()
                    # 🛠️ FIXED: Added operator tracking to ledger write
                    supabase.table("stock_ledger").insert({"sku": sku_input, "movement_type": movement_type, "quantity": qty, "access_code": user_code, "operator": operator_username}).execute()
                    st.success(f"✅ Updated Stock! New Total: {new_qty}")
            else:
                if movement_type == "OUT":
                    st.error("❌ Aborted: Cannot pick an item from a non-existent location.")
                else:
                    supabase.table("inventory_items").insert({"sku": sku_input, "item_name": f"Item {sku_input}", "location": location_input, "quantity": qty, "metadata": scanned_metadata, "access_code": user_code}).execute()
                    # 🛠️ FIXED: Added operator tracking to ledger write
                    supabase.table("stock_ledger").insert({"sku": sku_input, "movement_type": movement_type, "quantity": qty, "access_code": user_code, "operator": operator_username}).execute()
                    st.success(f"📦 Created new batch at location: {location_input}!")

# ==========================================
# TAB 2: CASE-INSENSITIVE SEARCH (WILDCARD)
# ==========================================
with tab2:
    st.subheader("Smart SKU Finder")
    search_sku = st.text_input("🔍 Search SKU (Partial Matching Active):").strip()
    
    if search_sku:
        wildcard_search = f"%{search_sku}%"
        res = supabase.table("inventory_items").select("*").ilike("sku", wildcard_search).eq("access_code", user_code).execute()
        
        if res.data:
            df = pd.DataFrame(res.data)
            st.success(f"Found {len(df)} matching item trace(s) in your workspace:")
            
            for _, row in df.iterrows():
                metadata_disp = f" | Notes: {row['metadata']}" if row['metadata'] else ""
                st.info(f"📦 **SKU:** `{row['sku']}` | 📍 **Location:** `{row['location']}` | 🔢 **Stock:** {row['quantity']} units{metadata_disp}")
        else:
            st.info("No matching item inventory trace located in your workspace.")

# ==========================================
# TAB 3: LIVE STOCK TRACKING & EDITS
# ==========================================
with tab3:
    st.subheader("Global Inventory Grid Management")
    all_items = supabase.table("inventory_items").select("*").eq("access_code", user_code).order("location", desc=False).execute()
    
    if all_items.data:
        rows = []
        for r in all_items.data:
            flat_row = {
                "Internal DB ID": r["id"],
                "SKU": r["sku"],
                "Item Name": r["item_name"],
                "Location": r["location"],
                "Quantity": r["quantity"]
            }
            for custom_f in configured_custom_bars:
                flat_row[custom_f] = ""
                
            if isinstance(r["metadata"], dict):
                for k, v in r["metadata"].items():
                    flat_row[k] = v
            rows.append(flat_row)
            
        base_df = pd.DataFrame(rows)
        
        for extra_col in configured_custom_bars:
            if extra_col not in base_df.columns:
                base_df[extra_col] = ""

        if "custom_columns" not in st.session_state:
            st.session_state.custom_columns = []
        for extra_col in st.session_state.custom_columns:
            if extra_col not in base_df.columns:
                base_df[extra_col] = ""

        edited_df = st.data_editor(base_df, hide_index=True, use_container_width=True, disabled=["Internal DB ID"])
        
        if st.button("💾 Save Grid Configuration Updates"):
            with st.spinner("Synchronizing batch edits..."):
                fixed_sys_cols = ["Internal DB ID", "SKU", "Item Name", "Location", "Quantity"]
                
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
    else:
        st.info("Your workspace inventory database is currently empty.")

# ==========================================
# TAB 4: HISTORICAL LEDGER (PAST RECORDS)
# ==========================================
with tab4:
    st.subheader("📜 Continuous Stock Ledger Audit Track")
    ledger_query = supabase.table("stock_ledger").select("*").eq("access_code", user_code).order("timestamp", desc=True).execute()
    
    if ledger_query.data:
        ledger_df = pd.DataFrame(ledger_query.data)
        ledger_df["Time Logged"] = ledger_df["timestamp"].str.slice(0, 19).str.replace("T", " ")
        
        # Fallback handling for older legacy rows created before this migration field existed
        if "operator" not in ledger_df.columns:
            ledger_df["operator"] = "System"
        ledger_df["operator"] = ledger_df["operator"].fillna("System")
        
        # 🛠️ FIXED: Included the new "Operator Identity" column into the display data frame mapping
        st.dataframe(
            ledger_df[["Time Logged", "sku", "movement_type", "quantity", "operator"]].rename(
                columns={
                    "sku": "Product SKU",
                    "movement_type": "Operation",
                    "quantity": "Quantity Shift",
                    "operator": "Operator Identity"
                }
            ), 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("No transaction history records discovered inside your workspace.")

# ==========================================
# TAB 5: PREFERENCES & TERMINAL CONFIGURATION
# ==========================================
with tab5:
    st.subheader("⚙️ Terminal View Configurations")
    
    new_title = st.text_input("Modify App Dashboard Title:", value=user_profile.get("terminal_title", "Mobile WMS Terminal")).strip()
    
    st.markdown("---")
    
    st.subheader("📍 Manage Warehouse Locations Dropdown")
    locations_str = st.text_area("Enter active locations separated by commas:", value=", ".join(configured_locations))
    parsed_locations = [x.strip().upper() for x in locations_str.split(",") if x.strip()]
    
    st.markdown("---")
    
    st.subheader("📊 Manage Additional Information Bars")
    custom_bars_str = st.text_area("Enter custom data entry fields separated by commas (e.g. Value, Weight, Supplier):", value=", ".join(configured_custom_bars))
    parsed_custom_fields = [x.strip() for x in custom_bars_str.split(",") if x.strip()]
    
    if st.button("💾 Apply Configuration Parameters"):
        if new_title and parsed_locations:
            update_payload = {
                "terminal_title": new_title,
                "authorized_locations": parsed_locations,
                "custom_data_fields": parsed_custom_fields
            }
            supabase.table("user_profiles").update(update_payload).eq("id", profile_db_id).execute()
            
            st.session_state.user_session["terminal_title"] = new_title
            st.session_state.user_session["authorized_locations"] = parsed_locations
            st.session_state.user_session["custom_data_fields"] = parsed_custom_fields
            
            st.success("Preferences saved successfully across your corporate account channel context!")
            st.rerun()
