import streamlit as st
import pandas as pd
from supabase import create_client, Client
import datetime
import urllib.request
import hashlib
from zoneinfo import ZoneInfo

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

# --- TIMEZONE DETECTION ENGINE ---
user_tz_str = st.context.timezone or "UTC"
user_tz = ZoneInfo(user_tz_str)

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
                
                # --- TEMPORARY DEBUG HOOK ---
                try:
                    user_query = supabase.table("user_profiles").select("*").eq("username", login_user).eq("password_hash", target_hash).execute()
                except Exception as db_err:
                    st.error("⚠️ Raw Supabase Error Caught:")
                    st.code(str(db_err))
                    st.stop()
                # -----------------------------
                
                if user_query.data:
                    user_record = user_query.data[0]
                    supabase.table("user_profiles").update({"last_known_ip": current_ip}).eq("id", user_record["id"]).execute()
                    user_record["last_known_ip"] = current_ip
                    st.session_state.user_session = user_record
                    st.success("Access authorized. Redirecting...")
                    st.rerun()
                else:
                    st.error("Invalid username or password configuration match.")
                
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
    st.caption(f"Operator identity: **{operator_username}** | Zone Context: `{user_tz_str}`")
with col_exit:
    st.write("") 
    if st.button("🔒 Sign Out"):
        supabase.table("user_profiles").update({"last_known_ip": None}).eq("id", profile_db_id).execute()
        st.session_state.user_session = None
        st.session_state.batch_queue = []
        st.rerun()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔄 Movement & Transfer", "🔍 Smart Finder", "📊 Live Stock", "📜 History", "⚙️ Preferences"])

# ==========================================
# TAB 1: OPERATIONAL TERMINAL (HEADER REMOVED)
# ==========================================
with tab1:
    op_mode = st.radio("Logistics Action Mode:", ["Single Entry", "Multiple Entry"], horizontal=True)
    
    st.markdown("---")
    
    if op_mode == "Single Entry":
        sku_input = st.text_input("📋 Enter SKU Code:", key="wms_single_input_bar").strip()
    else:
        sku_stream = st.text_area("📋 Scan Continuous Barcode Stream (use commas to separate, e.g., apple, apple):", key="wms_multiple_input_bar").strip()
    
    col_dir, col_qt = st.columns(2)
    with col_dir:
        action = st.radio("Action:", ["IN", "OUT", "TRANSFER"])
    with col_qt:
        qty = st.number_input("Quantity:", min_value=1, value=1)
        
    if action == "TRANSFER":
        col_f, col_t = st.columns(2)
        with col_f:
            loc_from = st.selectbox("Source Location (FROM):", options=configured_locations, key="src_loc")
            location_input = loc_from
        with col_t:
            loc_to = st.selectbox("Destination Location (TO):", options=configured_locations, key="dst_loc")
    else:
        location_input = st.selectbox("Location:", options=configured_locations)
        loc_from, loc_to = None, None

    scanned_metadata = {}
    if configured_custom_bars and action != "TRANSFER":
        st.caption("📝 Transaction Extra Attributes Payload:")
        for bar_field in configured_custom_bars:
            scanned_metadata[bar_field] = st.text_input(f"Enter {bar_field}:", key=f"scan_m_{bar_field}").strip()

    def execute_transaction(sku, act, q, loc, l_from=None, l_to=None, meta=None):
        if meta is None: meta = {}
        movement_type = "IN" if "IN" in act else "OUT" if "OUT" in act else "TRANSFER"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
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
                supabase.table("inventory_items").update({"quantity": new_dst_q, "is_archived": False, "last_updated": now_iso}).eq("id", dst_q.data[0]["id"]).execute()
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
                    if v: current_meta[k] = v

                if new_qty < 0:
                    return False, f"❌ Aborted '{sku}': Insufficient levels inside system matrix storage path. Available: {current_qty}"
                
                is_archived_flag = True if new_qty == 0 else False
                supabase.table("inventory_items").update({"quantity": new_qty, "is_archived": is_archived_flag, "metadata": current_meta, "last_updated": now_iso}).eq("id", record["id"]).execute()
                supabase.table("stock_ledger").insert({"sku": sku, "movement_type": movement_type, "quantity": q, "access_code": user_code, "operator": operator_username}).execute()
                return True, f"✅ Sync operation complete for {sku}! Revised Total Balance: {new_qty}"
            else:
                if movement_type == "OUT":
                    return False, f"❌ Aborted: Target tracking segment empty for {sku} inside location node {loc}."
                else:
                    supabase.table("inventory_items").insert({"sku": sku, "item_name": f"Item {sku}", "location": loc, "quantity": q, "metadata": meta, "access_code": user_code, "is_archived": False}).execute()
                    supabase.table("stock_ledger").insert({"sku": sku, "movement_type": movement_type, "quantity": q, "access_code": user_code, "operator": operator_username}).execute()
                    return True, f"📦 Created fresh batch entry tracking for {sku} inside matrix sector {loc}."

    if op_mode == "Single Entry":
        if st.button("🚀 Commit Direct Single Transaction"):
            if not sku_input:
                st.warning("SKU entry identifier string required.")
            elif "," in sku_input:
                st.error("Detecting tokens structure. Please navigate to Multiple Entry Mode to run comma separated scanner chains.")
            else:
                success, msg = execute_transaction(sku_input, action, qty, location_input, loc_from, loc_to, scanned_metadata)
                if success: st.success(msg)
                else: st.error(msg)
    else:
        col_queue, col_clear = st.columns(2)
        with col_queue:
            if st.button("📥 Check scanned"):
                if not sku_stream:
                    st.warning("Provide item tracking parameters inside the top entry field input.")
                else:
                    raw_tokens = sku_stream.split(",")
                    parsed_skus = [token.strip() for token in raw_tokens if token.strip()]
                    
                    for scanned_sku in parsed_skus:
                        st.session_state.batch_queue.append({
                            "sku": scanned_sku, "action": action, "qty": qty, "location": location_input,
                            "loc_from": loc_from, "loc_to": loc_to, "metadata": scanned_metadata
                        })
                    st.toast(f"Parsed and added {len(parsed_skus)} item entries to execution layout queue staging table.")
        with col_clear:
            if st.button("🗑️ Reset scanned"):
                st.session_state.batch_queue = []
                st.rerun()
        
        if st.session_state.batch_queue:
            st.markdown("---")
            st.markdown("### 📋 Staged Group Manifest Grid Details:")
            raw_q_df = pd.DataFrame(st.session_state.batch_queue)
            display_grouping = raw_q_df.groupby(["sku", "action", "location"]).size().reset_index(name="Total Scanned Entries Instances")
            st.dataframe(display_grouping, use_container_width=True, hide_index=True)
            
            if st.button("🏁 Execute Entire Multiple Entry Batch Sequence"):
                queue_df = pd.DataFrame(st.session_state.batch_queue)
                consolidated_tasks = queue_df.groupby(["sku", "action", "location"]).size().reset_index(name="scanned_count")
                
                success_count, fail_count = 0, 0
                for _, row_task in consolidated_tasks.iterrows():
                    sku = row_task["sku"]
                    act = row_task["action"]
                    loc = row_task["location"]
                    
                    match_slice = queue_df[(queue_df["sku"] == sku) & (queue_df["action"] == act) & (queue_df["location"] == loc)].iloc[0]
                    base_qty_factor = match_slice["qty"]
                    meta_payload = match_slice["metadata"]
                    
                    l_from = match_slice["loc_from"] if pd.notna(match_slice["loc_from"]) else None
                    l_to = match_slice["loc_to"] if pd.notna(match_slice["loc_to"]) else None
                    
                    total_consolidated_qty = int(row_task["scanned_count"] * base_qty_factor)
                    
                    ok, res_msg = execute_transaction(sku, act, total_consolidated_qty, loc, l_from, l_to, meta_payload)
                    if ok:
                        success_count += 1
                    else:
                        st.error(res_msg)
                        fail_count += 1
                        
                st.success(f"Processing sequence complete! Consolidated Synced Groups: {success_count} | Aborted runs: {fail_count}")
                st.session_state.batch_queue = []
                st.rerun()

# ==========================================
# TAB 2: SMART FINDER (HEADER REMOVED)
# ==========================================
with tab2:
    search_sku = st.text_input("🔍 Search SKU:").strip()
    
    if search_sku:
        wildcard_search = f"%{search_sku}%"
        res = supabase.table("inventory_items").select("*").ilike("sku", wildcard_search).eq("access_code", user_code).eq("is_archived", False).execute()
        
        if res.data:
            df = pd.DataFrame(res.data)
            st.success(f"Discovered {len(df)} corresponding matches:")
            for _, row in df.iterrows():
                alert_flag = "⚠️ LOW STOCK LEVEL WARNING" if row['quantity'] <= row.get('min_stock', 0) else ""
                metadata_disp = f" | Notes: {row['metadata']}" if row['metadata'] else ""
                st.info(f"📦 **SKU:** `{row['sku']}` | 📍 **Location Matrix:** `{row['location']}` | 🔢 **Quantity:** {row['quantity']} units {alert_flag}{metadata_disp}")
        else:
            st.info("No matching item metrics located.")

# ==========================================
# TAB 3: LIVE STOCK (HEADER REMOVED)
# ==========================================
with tab3:
    all_items = supabase.table("inventory_items").select("*").eq("access_code", user_code).eq("is_archived", False).order("location", desc=False).execute()
    
    if all_items.data:
        rows = []
        low_stock_critical_warnings = []
        
        for r in all_items.data:
            flat_row = {
                "Internal DB ID": r["id"],
                "SKU": r["sku"],
                "Item Name": r["item_name"],
                "Location": r["location"],
                "Quantity": r["quantity"],
                "Alert Threshold (Min)": r.get("min_stock", 0)
            }
            for custom_f in configured_custom_bars:
                flat_row[custom_f] = ""
            if isinstance(r["metadata"], dict):
                for k, v in r["metadata"].items():
                    flat_row[k] = v
            rows.append(flat_row)
            
            if r["quantity"] <= r.get("min_stock", 0):
                low_stock_critical_warnings.append(f"🚨 **SKU {r['sku']}** at Location **{r['location']}** has dropped beneath safety limits! Current level: {r['quantity']} (Min: {r.get('min_stock', 0)})")
        
        if low_stock_critical_warnings:
            with st.expander("⚠️ UNRESOLVED SYSTEM BALANCING WARNINGS ALERT PANEL", expanded=True):
                for alert in low_stock_critical_warnings:
                    st.markdown(f'<div class="low-stock-alert">{alert}</div>', unsafe_allow_html=True)
                    
        base_df = pd.DataFrame(rows)
        
        for extra_col in configured_custom_bars:
            if extra_col not in base_df.columns: base_df[extra_col] = ""

        edited_df = st.data_editor(base_df, hide_index=True, use_container_width=True, disabled=["Internal DB ID"])
        
        col_sv, col_exp = st.columns(2)
        with col_sv:
            if st.button("💾 Apply Grid Parameter Modifications"):
                with st.spinner("Synchronizing backend databases..."):
                    fixed_sys_cols = ["Internal DB ID", "SKU", "Item Name", "Location", "Quantity", "Alert Threshold (Min)"]
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
                            "min_stock": int(row["Alert Threshold (Min)"]),
                            "metadata": meta_payload,
                            "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat()
                        }
                        supabase.table("inventory_items").update(update_data).eq("id", db_id).execute()
                    st.success("🎉 Interface dashboard parameters synchronized cleanly!")
                    st.rerun()
                    
        with col_exp:
            export_csv_data = base_df.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Export Ledger Analysis Data to CSV", data=export_csv_data, file_name=f"WMS_Inventory_Report_{datetime.date.today()}.csv", mime="text/csv")
    else:
        st.info("Your workspace channels contain zero product assets data rows.")

# ==========================================
# TAB 4: HISTORY (HEADER REMOVED)
# ==========================================
with tab4:
    ledger_query = supabase.table("stock_ledger").select("*").eq("access_code", user_code).order("timestamp", desc=True).execute()
    
    if ledger_query.data:
        ledger_df = pd.DataFrame(ledger_query.data)
        
        def localize_timestamp(ts_str):
            try:
                clean_ts = ts_str.split("+")[0].split(".")[0]
                utc_dt = datetime.datetime.strptime(clean_ts, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc)
                local_dt = utc_dt.astimezone(user_tz)
                return local_dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                return ts_str[:19].replace("T", " ")

        ledger_df["Time Logged"] = ledger_df["timestamp"].apply(localize_timestamp)
        
        if "operator" not in ledger_df.columns: ledger_df["operator"] = "System Trace"
        ledger_df["operator"] = ledger_df["operator"].fillna("System Trace")
        
        display_df = ledger_df[["Time Logged", "sku", "movement_type", "quantity", "operator"]].rename(
            columns={"sku": "Product SKU", "movement_type": "Logistics Operation", "quantity": "Quantity Shift", "operator": "Operator Identity"}
        )
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        st.download_button(label="📥 Download Transaction Audit Logs", data=display_df.to_csv(index=False).encode('utf-8'), file_name=f"WMS_Audit_Trail_{datetime.date.today()}.csv", mime="text/csv")
    else:
        st.info("No transaction history records discovered inside your workspace.")

# ==========================================
# TAB 5: PREFERENCES (HEADER KEPT)
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
