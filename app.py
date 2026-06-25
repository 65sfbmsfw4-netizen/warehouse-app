import streamlit as st
import pandas as pd
from supabase import create_client, Client
import datetime

st.set_page_config(page_title="Multi-Tenant WMS", page_icon="📦", layout="centered")
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

# ==========================================
# FEATURE: GATEKEEPER LOGIN MECHANISM
# ==========================================
if "access_code" not in st.session_state:
    st.session_state.access_code = None

if st.session_state.access_code is None:
    st.title("🔒 Inventory Gatekeeper")
    st.write("Please enter your unique Access Code to initialize your dedicated inventory terminal.")
    
    input_code = st.text_input("🔑 Access Code:", type="password").strip().upper()
    
    if st.button("🚪 Enter Terminal"):
        if input_code:
            st.session_state.access_code = input_code
            st.success(f"Connected to terminal workspace: {input_code}")
            st.rerun()
        else:
            st.warning("Please enter a valid code to proceed.")
    st.stop() # Stops the rest of the script from rendering until logged in

# --- APP ACTIVE TERMINAL STATE ---
user_code = st.session_state.access_code

# Navigation Header Layout
col_title, col_logout = st.columns([4, 1])
with col_title:
    st.title("📦 Mobile WMS Terminal")
    st.caption(f"Active Workspace Security Context: **{user_code}**")
with col_logout:
    st.write("") # Padding
    if st.button("🔒 Logout"):
        st.session_state.access_code = None
        st.rerun()

tab1, tab2, tab3, tab4 = st.tabs(["🔄 Scan In/Out", "🔍 Case-Insensitive Search", "📊 Live Stock & Edit", "📜 Past Records"])

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
            # FILTER FIX: Look for match with identical SKU, Location, AND matching Access Code
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
                    st.success(f"🗑️ Row cleared.")
                else:
                    supabase.table("inventory_items").update({"quantity": new_qty, "last_updated": datetime.datetime.now().isoformat()}).eq("id", existing_records[0]["id"]).execute()
                    supabase.table("stock_ledger").insert({"sku": sku_input, "movement_type": movement_type, "quantity": qty, "access_code": user_code}).execute()
                    st.success(f"✅ Updated Stock! New Total: {new_qty}")
            else:
                if movement_type == "OUT":
                    st.error(f"❌ Aborted: Cannot pick an item from a non-existent location.")
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
        # FILTER FIX: Only find items belonging to this specific user's access code context
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
with tab3:
    st.subheader("Global Inventory Grid Management")
    
    # FILTER FIX: Only fetch rows assigned to the current active user code context
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
            if isinstance(r["metadata"], dict):
                for k, v in r["metadata"].items():
                    flat_row[k] = v
            rows.append(flat_row)
            
        base_df = pd.DataFrame(rows)
        
        with st.expander("🛠️ Column Management Tools"):
            new_col_name = st.text_input("Enter New Custom Column Name:").strip()
            if "custom_columns" not in st.session_state:
                st.session_state.custom_columns = []
            if st.button("➕ Inject Custom Attribute Column"):
                if new_col_name and new_col_name not in base_df.columns and new_col_name not in st.session_state.custom_columns:
                    st.session_state.custom_columns.append(new_col_name)
                    st.rerun()

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
    
    # FILTER FIX: Only load transaction histories that matching this user's active access code
    ledger_query = supabase.table("stock_ledger").select("*").eq("access_code", user_code).order("timestamp", desc=True).execute()
    
    if ledger_query.data:
        ledger_df = pd.DataFrame(ledger_query.data)
        ledger_df["Time Logged"] = ledger_df["timestamp"].str.slice(0, 19).str.replace("T", " ")
        st.dataframe(
            ledger_df[["Time Logged", "sku", "movement_type", "quantity"]].rename(columns={"sku":"Product SKU","movement_type":"Operation","quantity":"Quantity Shift"}), 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("No transaction history records discovered inside your workspace.")
