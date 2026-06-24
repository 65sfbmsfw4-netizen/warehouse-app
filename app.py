import streamlit as st
import pandas as pd
from supabase import create_client, Client
import datetime

st.set_page_config(page_title="WMS Terminal v2", page_icon="📦", layout="centered")
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

st.title("📦 Advanced WMS Mobile Terminal")
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
    location_input = st.text_input("📍 Location Matrix (e.g., A-12-3-B):").strip().upper()

    if st.button("🚀 Commit Transaction to Database"):
        if not sku_input or not location_input:
            st.warning("Validation Error: SKU and Location fields are required.")
        else:
            # Match exact item batch at exact location
            query = supabase.table("inventory_items").select("*").eq("sku", sku_input).eq("location", location_input).execute()
            existing_records = query.data
            movement_type = "IN" if "IN" in action else "OUT"
            final_qty_change = qty if movement_type == "IN" else -qty
            
            if existing_records:
                current_qty = existing_records[0]["quantity"]
                new_qty = current_qty + final_qty_change
                if new_qty < 0:
                    st.error(f"❌ Aborted: Insufficient stock at location {location_input}. Current Level: {current_qty}")
                elif new_qty == 0:
                    supabase.table("inventory_items").delete().eq("id", existing_records[0]["id"]).execute()
                    supabase.table("stock_ledger").insert({"sku": sku_input, "movement_type": movement_type, "quantity": qty}).execute()
                    st.success(f"🗑️ Location {location_input} is now empty. Row cleared.")
                else:
                    supabase.table("inventory_items").update({"quantity": new_qty, "last_updated": datetime.datetime.now().isoformat()}).eq("id", existing_records[0]["id"]).execute()
                    supabase.table("stock_ledger").insert({"sku": sku_input, "movement_type": movement_type, "quantity": qty}).execute()
                    st.success(f"✅ Updated Stock! Total at {location_input} is now: {new_qty}")
            else:
                if movement_type == "OUT":
                    st.error(f"❌ Aborted: Cannot pick an item from a non-existent location.")
                else:
                    supabase.table("inventory_items").insert({"sku": sku_input, "item_name": f"Item {sku_input}", "location": location_input, "quantity": qty}).execute()
                    supabase.table("stock_ledger").insert({"sku": sku_input, "movement_type": movement_type, "quantity": qty}).execute()
                    st.success(f"📦 Created new separate batch for '{sku_input}' at location: {location_input}!")

# ==========================================
# TAB 2: CASE-INSENSITIVE SEARCH (Apple = apple)
# ==========================================
with tab2:
    st.subheader("Smart SKU Finder")
    search_sku = st.text_input("🔍 Search SKU (Case Insensitive):").strip()
    
    if search_sku:
        # 'ilike' acts exactly like SQL LIKE but ignores casing differences automatically
        res = supabase.table("inventory_items").select("*").ilike("sku", search_sku).execute()
        if res.data:
            df = pd.DataFrame(res.data)
            for _, row in df.iterrows():
                metadata_disp = f" | Notes: {row['metadata']}" if row['metadata'] else ""
                st.info(f"📍 **Location:** `{row['location']}` | 🔢 **Stock:** {row['quantity']} units{metadata_disp}")
        else:
            st.info("No matching item inventory trace located.")

# ==========================================
# TAB 3: LIVE STOCK TRACKING, EDITS, & DYNAMIC COLUMNS
# ==========================================
with tab3:
    st.subheader("Global Inventory Grid Management")
    
    # 1. Fetch live snapshot from Supabase
    all_items = supabase.table("inventory_items").select("*").order("location", desc=False).execute()
    
    if all_items.data:
        # Parse data, flattening metadata contents out into columns for display
        rows = []
        for r in all_items.data:
            flat_row = {
                "Internal DB ID": r["id"],
                "SKU": r["sku"],
                "Item Name": r["item_name"],
                "Location": r["location"],
                "Quantity": r["quantity"]
            }
            # Append anything stored dynamically inside JSONB as an apparent table column
            if isinstance(r["metadata"], dict):
                for k, v in r["metadata"].items():
                    flat_row[k] = v
            rows.append(flat_row)
            
        base_df = pd.DataFrame(rows)
        
# 2. FEATURE: Add/Rename Custom Metadata Fields (With Session State Storage)
        st.write("---")
        with st.expander("🛠️ Column Management Tools"):
            new_col_name = st.text_input("Enter New Custom Column Name (e.g. Remarks, Supplier):").strip()
            
            # Initialize our app's long-term memory for custom columns if it doesn't exist yet
            if "custom_columns" not in st.session_state:
                st.session_state.custom_columns = []
                
            if st.button("➕ Inject Custom Attribute Column"):
                if new_col_name:
                    if new_col_name not in base_df.columns and new_col_name not in st.session_state.custom_columns:
                        st.session_state.custom_columns.append(new_col_name)
                        st.success(f"Column '{new_col_name}' injected! Type your inputs below and click Save.")
                        st.rerun()
                    else:
                        st.warning("That attribute column already exists.")

        # Force the table to display any custom columns saved in our app's browser memory
        for extra_col in st.session_state.custom_columns:
            if extra_col not in base_df.columns:
                base_df[extra_col] = ""

        st.write("---")
        st.caption("Double click any cell below to change values directly, then click Save at the bottom:")
        
        # 3. FEATURE: Data Editor Interface
        edited_df = st.data_editor(
            base_df, 
            hide_index=True, 
            use_container_width=True,
            disabled=["Internal DB ID"]
        )
        
        # 4. Save Button Processing Logic
        if st.button("💾 Save Grid Configuration Updates"):
            with st.spinner("Synchronizing batch edits to cloud storage..."):
                fixed_sys_cols = ["Internal DB ID", "SKU", "Item Name", "Location", "Quantity"]
                
                for idx, row in edited_df.iterrows():
                    db_id = row["Internal DB ID"]
                    
                    # Extract custom metadata key-value parameters safely
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
                
                # Clear out our temporary column tracker memory once saved to Supabase cleanly
                st.session_state.custom_columns = []
                st.success("🎉 Global grid state synchronized perfectly with your cloud database instance!")
                st.rerun()

# ==========================================
# TAB 4: HISTORICAL LEDGER (PAST RECORDS)
# ==========================================
with tab4:
    st.subheader("📜 Continuous Stock Ledger Audit Track")
    
    # Grab all historical rows sorted so the newest action shows first
    ledger_query = supabase.table("stock_ledger").select("*").order("timestamp", desc=True).execute()
    
    if ledger_query.data:
        ledger_df = pd.DataFrame(ledger_query.data)
        
        # Visual cleanup for clean mobile phone presentation
        ledger_df["Time Logged"] = ledger_df["timestamp"].str.slice(0, 19).str.replace("T", " ")
        ledger_df["Operation"] = ledger_df["movement_type"]
        ledger_df["Product SKU"] = ledger_df["sku"]
        ledger_df["Quantity Shift"] = ledger_df["quantity"]
        
        # Display only human-readable structured columns
        st.dataframe(
            ledger_df[["Time Logged", "Product SKU", "Operation", "Quantity Shift"]], 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("No transaction history records discovered inside the logging layer tables yet.")