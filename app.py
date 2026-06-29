import streamlit as st
import pandas as pd
from supabase import create_client, Client
import datetime
import urllib.request
import hashlib
import uuid
from zoneinfo import ZoneInfo
import io  
import requests  
from openpyxl import Workbook  
from openpyxl.drawing.image import Image as OpenpyxlImage  
from PIL import Image as PILImage  

st.set_page_config(page_title="Enterprise WMS Platform", page_icon="📦", layout="centered")

# --- CUSTOM INTERFACE STYLING ---
st.markdown("""
<style>
    .stButton>button { width: 100%; height: 50px; font-size: 16px; }
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
                
                try:
                    user_query = supabase.table("user_profiles").select("*").eq("username", login_user).eq("password_hash", target_hash).execute()
                except Exception as db_err:
                    st.error("⚠️ Raw Supabase Error Caught:")
                    st.code(str(db_err))
                    st.stop()
                
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
# TAB 1: OPERATIONAL TERMINAL (WITH DIMENSIONS INPUT)
# ==========================================
with tab1:
    op_mode = st.radio("Logistics Action Mode:", ["Single Entry", "Multiple Entry"], horizontal=True)
    
    st.markdown("---")
    
    uploaded_image_url = None
    
    if op_mode == "Single Entry":
        sku_input = st.text_input("📋 Enter Object ID:", key="wms_single_input_bar").strip()
        
        # Split layout into 3 separate number inputs with a preset 'x' partition structure
        st.write("📏 **Dimensions Assignment Segment:**")
        dim_col1, dim_spacer1, dim_col2, dim_spacer2, dim_col3 = st.columns([3, 1, 3, 1, 3])
        with dim_col1:
            l_num = st.number_input("Length", min_value=0, step=1, key="input_dim_l")
        with dim_spacer1:
            st.markdown("<h3 style='text-align: center; margin-top: 25px;'>x</h3>", unsafe_allow_html=True)
        with dim_col2:
            w_num = st.number_input("Weight", min_value=0, step=1, key="input_dim_w")
        with dim_spacer2:
            st.markdown("<h3 style='text-align: center; margin-top: 25px;'>x</h3>", unsafe_allow_html=True)
        with dim_col3:
            h_num = st.number_input("Height", min_value=0, step=1, key="input_dim_h")
        
        # Combine parameters cleanly into a text token string pattern
        dimensions_input = f"{l_num} x {w_num} x {h_num}"
        
        uploaded_file = st.file_uploader("📸 Optional: Attach Object Photo Asset", type=["png", "jpg", "jpeg", "webp"])
        if uploaded_file:
            st.image(uploaded_file, width=150, caption="Staged visual preview")
            
        col_dir, col_qt = st.columns(2)
        with col_dir:
            action = st.radio("Action:", ["IN", "OUT", "TRANSFER"])
            
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

    else:
        sku_stream = st.text_area("📋 Scan Continuous ID Stream (use commas to separate, e.g., obj101, obj102):", key="wms_multiple_input_bar").strip()
        dimensions_input = "0 x 0 x 0" 
        
        col_dir, col_qt = st.columns(2)
        with col_dir:
            action = st.radio("Action:", ["TRANSFER", "OUT"]) 
            
        col_f, col_t = st.columns(2)
        with col_f:
            loc_from = st.selectbox("Source Location (FROM):", options=configured_locations, key="src_loc_multi")
            location_input = loc_from
        with col_t:
            loc_to = st.selectbox("Destination Location (TO):", options=configured_locations, key="dst_loc_multi")

    scanned_metadata = {}
    if op_mode == "Single Entry" and action != "TRANSFER":
        scanned_metadata["dimensions"] = dimensions_input
        if configured_custom_bars:
            st.caption("📝 Transaction Extra Attributes Payload:")
            for bar_field in configured_custom_bars:
                scanned_metadata[bar_field] = st.text_input(f"Enter {bar_field}:", key=f"scan_m_{bar_field}").strip()

    def execute_transaction(sku, act, q, loc, l_from=None, l_to=None, meta=None, img_url=None):
        if meta is None: meta = {}
        movement_type = "IN" if "IN" in act else "OUT" if "OUT" in act else "TRANSFER"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        if movement_type == "TRANSFER":
            src_q = supabase.table("inventory_items").select("*").eq("object_id", sku).eq("location", l_from).eq("access_code", user_code).eq("is_archived", False).execute()
            if not src_q.data:
                return False, f"❌ Aborted '{sku}': Object not found inside source node {l_from}."
            
            supabase.table("inventory_items").update({"quantity": 0, "is_archived": True}).eq("id", src_q.data[0]["id"]).execute()
                
            dst_q = supabase.table("inventory_items").select("*").eq("object_id", sku).eq("location", l_to).eq("access_code", user_code).execute()
            if dst_q.data:
                update_payload = {"quantity": 1, "is_archived": False, "last_updated": now_iso}
                if img_url: update_payload["image_url"] = img_url
                supabase.table("inventory_items").update(update_payload).eq("id", dst_q.data[0]["id"]).execute()
            else:
                supabase.table("inventory_items").insert({"object_id": sku, "item_name": f"Object {sku}", "location": l_to, "quantity": 1, "access_code": user_code, "image_url": img_url, "metadata": src_q.data[0].get("metadata", {})}).execute()
                
            supabase.table("stock_ledger").insert({"object_id": sku, "movement_type": "OUT", "quantity": 1, "access_code": user_code, "operator": operator_username}).execute()
            supabase.table("stock_ledger").insert({"object_id": sku, "movement_type": "IN", "quantity": 1, "access_code": user_code, "operator": operator_username}).execute()
            return True, f"✅ Successfully transferred {sku} from {l_from} to {l_to}!"
            
        else:
            query = supabase.table("inventory_items").select("*").eq("object_id", sku).eq("location", loc).eq("access_code", user_code).execute()
            
            if query.data:
                record = query.data[0]
                current_meta = record.get("metadata") or {}
                for k, v in meta.items():
                    if v: current_meta[k] = v

                is_archived_flag = True if movement_type == "OUT" else False
                update_payload = {"quantity": 0 if is_archived_flag else 1, "is_archived": is_archived_flag, "metadata": current_meta, "last_updated": now_iso}
                if img_url: update_payload["image_url"] = img_url
                
                supabase.table("inventory_items").update(update_payload).eq("id", record["id"]).execute()
                supabase.table("stock_ledger").insert({"object_id": sku, "movement_type": movement_type, "quantity": 1, "access_code": user_code, "operator": operator_username}).execute()
                return True, f"✅ Sync operation complete for {sku}!"
            else:
                if movement_type == "OUT":
                    return False, f"❌ Aborted: Target tracking segment empty for {sku} inside location node {loc}."
                else:
                    supabase.table("inventory_items").insert({"object_id": sku, "item_name": f"Object {sku}", "location": loc, "quantity": 1, "metadata": meta, "access_code": user_code, "is_archived": False, "image_url": img_url}).execute()
                    supabase.table("stock_ledger").insert({"object_id": sku, "movement_type": movement_type, "quantity": 1, "access_code": user_code, "operator": operator_username}).execute()
                    return True, f"📦 Created fresh batch entry tracking for {sku} inside matrix sector {loc}."

    if op_mode == "Single Entry":
        if st.button("🚀 Commit Direct Single Transaction"):
            if not sku_input:
                st.warning("Object ID entry identifier string required.")
            elif "," in sku_input:
                st.error("Detecting tokens structure. Please navigate to Multiple Entry Mode to run comma separated scanner chains.")
            else:
                if uploaded_file:
                    with st.spinner("Uploading photo asset to bucket storage..."):
                        try:
                            file_extension = uploaded_file.name.split(".")[-1]
                            unique_filename = f"{sku_input}_{uuid.uuid4().hex[:8]}.{file_extension}"
                            file_bytes = uploaded_file.read()
                            
                            supabase.storage.from_("item-images").upload(unique_filename, file_bytes, {"content-type": f"image/{file_extension}"})
                            uploaded_image_url = supabase.storage.from_("item-images").get_public_url(unique_filename)
                        except Exception as upload_err:
                            st.error(f"Failed to save visual asset: {str(upload_err)}")
                
                success, msg = execute_transaction(sku_input, action, 1, location_input, loc_from, loc_to, scanned_metadata, uploaded_image_url)
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
                            "sku": scanned_sku, "action": action, "qty": 1, "location": location_input,
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
                    meta_payload = match_slice["metadata"]
                    l_from = match_slice["loc_from"] if pd.notna(match_slice["loc_from"]) else None
                    l_to = match_slice["loc_to"] if pd.notna(match_slice["loc_to"]) else None
                    
                    ok, res_msg = execute_transaction(sku, act, 1, loc, l_from, l_to, meta_payload)
                    if ok: success_count += 1
                    else:
                        st.error(res_msg)
                        fail_count += 1
                        
                st.success(f"Processing sequence complete! Consolidated Synced Groups: {success_count} | Aborted runs: {fail_count}")
                st.session_state.batch_queue = []
                st.rerun()

# ==========================================
# TAB 2: SMART FINDER (WITH DIMENSIONS FALLBACK)
# ==========================================
with tab2:
    search_sku = st.text_input("🔍 Search Object ID:").strip()
    
    if search_sku:
        wildcard_search = f"%{search_sku}%"
        res = supabase.table("inventory_items").select("*").ilike("object_id", wildcard_search).eq("access_code", user_code).eq("is_archived", False).execute()
        
        if res.data:
            df = pd.DataFrame(res.data)
            st.success(f"Discovered {len(df)} corresponding matches:")
            for _, row in df.iterrows():
                metadata_dict = row.get("metadata") or {}
                # If sizes missing or blank, fallback to clean placeholder context
                dims = metadata_dict.get("dimensions", "0 x 0 x 0")
                if not dims or str(dims).strip() == "":
                    dims = "0 x 0 x 0"
                
                clean_meta_notes = {k: v for k, v in metadata_dict.items() if k != "dimensions"}
                metadata_disp = f" | Notes: {clean_meta_notes}" if clean_meta_notes else ""
                
                st.info(f"📦 **Object ID:** `{row['object_id']}` | 📍 **Location:** `{row['location']}` | 📏 **Size (L x W x H):** `{dims}`{metadata_disp}")
                
                img_url = row.get("image_url")
                if img_url and img_url.strip() != "":
                    st.image(img_url, caption=f"Visual asset link for Object: {row['object_id']}", use_container_width=True)
        else:
            st.info("No matching object metrics located.")

# ==========================================
# TAB 3: LIVE STOCK (000 X 000 X 000 PRESET FORMAT)
# ==========================================
with tab3:
    all_items = supabase.table("inventory_items").select("*").eq("access_code", user_code).eq("is_archived", False).order("location", desc=False).execute()
    
    if all_items.data:
        rows = []
        for r in all_items.data:
            metadata_dict = r.get("metadata") or {}
            
            # Extract and check dimensions, inject baseline preset layout values if not present
            fetched_dims = metadata_dict.get("dimensions", "0 x 0 x 0")
            if not fetched_dims or str(fetched_dims).strip() == "":
                fetched_dims = "0 x 0 x 0"
                
            flat_row = {
                "Internal DB ID": r["id"],
                "Image Preview": r.get("image_url", ""), 
                "Object ID": r["object_id"],
                "Item Name": r["item_name"],
                "Location": r["location"],
                "Length x Weight x Height": fetched_dims
            }
            
            for custom_f in configured_custom_bars:
                flat_row[custom_f] = metadata_dict.get(custom_f, "")
                
            if isinstance(metadata_dict, dict):
                for k, v in metadata_dict.items():
                    if k not in ["dimensions"] and k not in configured_custom_bars:
                        flat_row[k] = v
            rows.append(flat_row)
                    
        base_df = pd.DataFrame(rows)
        
        for extra_col in configured_custom_bars:
            if extra_col not in base_df.columns: base_df[extra_col] = ""

        visible_columns = [col for col in base_df.columns if col != "Internal DB ID"]

        edited_df = st.data_editor(
            base_df[visible_columns], 
            hide_index=True, 
            use_container_width=True, 
            column_config={
                "Image Preview": st.column_config.ImageColumn(
                    "Image Preview", 
                    help="Compressed high-speed visual thumbnail assets",
                    width="small"
                )
            }
        )
        
        col_sv, col_exp = st.columns(2)
        with col_sv:
            if st.button("💾 Apply Grid Parameter Modifications"):
                with st.spinner("Synchronizing backend databases..."):
                    fixed_sys_cols = ["Image Preview", "Object ID", "Item Name", "Location", "Length x Weight x Height"]
                    for idx, row in edited_df.iterrows():
                        db_id = base_df.loc[idx, "Internal DB ID"]
                        
                        # Fallback control loop check when updating data table inline
                        save_dims = str(row["Length x Weight x Height"]).strip()
                        if not save_dims or save_dims == "":
                            save_dims = "0 x 0 x 0"
                            
                        meta_payload = {
                            "dimensions": save_dims
                        }
                        for col in edited_df.columns:
                            if col not in fixed_sys_cols and pd.notna(row[col]) and str(row[col]).strip() != "":
                                meta_payload[col] = str(row[col])
                                
                        update_data = {
                            "object_id": str(row["Object ID"]),
                            "item_name": str(row["Item Name"]),
                            "location": str(row["Location"]),
                            "image_url": str(row["Image Preview"]).strip(),
                            "metadata": meta_payload,
                            "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat()
                        }
                        supabase.table("inventory_items").update(update_data).eq("id", db_id).execute()
                    st.success("🎉 Interface dashboard parameters synchronized cleanly!")
                    st.rerun()
                    
        with col_exp:
            excel_buffer = io.BytesIO()
            if st.button("📊 Compile & Export Rich Excel Report (.xlsx)"):
                with st.spinner("Downloading image tokens and building report layout..."):
                    wb = Workbook()
                    ws = wb.active
                    ws.title = "Live Inventory Assets"
                    
                    headers = ["Image Preview", "Object ID", "Item Name", "Location", "Length x Weight x Height"] + configured_custom_bars
                    ws.append(headers)
                    
                    ws.row_dimensions[1].height = 25
                    for col_idx in range(1, len(headers) + 1):
                        ws.column_dimensions[chr(64 + col_idx)].width = 22
                    ws.column_dimensions['A'].width = 12
                    
                    for idx, row in edited_df.iterrows():
                        row_num = idx + 2
                        ws.row_dimensions[row_num].height = 45
                        
                        save_excel_dims = str(row["Length x Weight x Height"]).strip()
                        if not save_excel_dims or save_excel_dims == "":
                            save_excel_dims = "0 x 0 x 0"
                            
                        data_payload = [
                            "", 
                            str(row["Object ID"]),
                            str(row["Item Name"]),
                            str(row["Location"]),
                            save_excel_dims
                        ]
                        for custom_f in configured_custom_bars:
                            data_payload.append(str(row.get(custom_f, "")))
                            
                        ws.append(data_payload)
                        
                        img_url = row["Image Preview"]
                        if img_url and str(img_url).strip() != "":
                            try:
                                response = requests.get(img_url.strip(), timeout=5)
                                if response.status_code == 200:
                                    img_data = io.BytesIO(response.content)
                                    pil_img = PILImage.open(img_data)
                                    pil_img.thumbnail((55, 55))
                                    
                                    temp_img_buffer = io.BytesIO()
                                    pil_img.save(temp_img_buffer, format="PNG")
                                    temp_img_buffer.seek(0)
                                    
                                    excel_img = OpenpyxlImage(temp_img_buffer)
                                    ws.add_image(excel_img, f"A{row_num}")
                            except Exception:
                                ws[f"A{row_num}"] = "Image Error"
                    
                    wb.save(excel_buffer)
                    excel_buffer.seek(0)
                    
                    st.success("Excel sheet compilation successful!")
                    st.download_button(
                        label="📥 Download Rich Excel File (.xlsx)",
                        data=excel_buffer,
                        file_name=f"WMS_Detailed_Report_{datetime.date.today()}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
    else:
        st.info("Your workspace channels contain zero product assets data rows.")

# ==========================================
# TAB 4: HISTORY
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
        ledger_df["operator"] = ledger_df.get("operator", "System Trace").fillna("System Trace")
        
        display_df = ledger_df[["Time Logged", "object_id", "movement_type", "operator"]].rename(
            columns={"object_id": "Object ID", "movement_type": "Logistics Operation", "operator": "Operator Identity"}
        )
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        st.download_button(label="📥 Download Transaction Audit Logs", data=display_df.to_csv(index=False).encode('utf-8'), file_name=f"WMS_Audit_Trail_{datetime.date.today()}.csv", mime="text/csv")
    else:
        st.info("No transaction history records discovered inside your workspace.")

# ==========================================
# TAB 5: PREFERENCES
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
