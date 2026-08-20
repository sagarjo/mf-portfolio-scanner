import streamlit as st
import pandas as pd
from utils.data_loader import load_and_normalize, validate_and_parse_filename
from utils.ui_components import inject_custom_styles, render_kpi_card

st.set_page_config(
    page_title="MF Data Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_custom_styles()

st.title("🛡️ Mutual Fund Data Dashboard")
st.markdown("""
Upload monthly AMC portfolio disclosures below.

> **Naming Rule:** Files must follow the format:  
> `AMC-SchemeName-Month-Year.xlsx` or `.csv`  
> **Examples:** > * `Navi-NiftyNextFifty-May-2026.xlsx` * `Canara-Robeco-Small-Cap-Fund-July-2026.xlsx`
""")

# Initialize persistent session state
if 'portfolio_store' not in st.session_state:
    st.session_state.portfolio_store = {}

uploaded_files = st.file_uploader(
    "Upload Portfolio Files (.xlsx, .csv)",
    accept_multiple_files=True,
    type=['csv', 'xlsx'],
    help="Files must match the convention: AMC-SchemeName-Month-Year"
)

if uploaded_files:
    store = {}
    invalid_naming = []
    parsing_failed = []

    for f in uploaded_files:
        meta = validate_and_parse_filename(f.name)
        if not meta or 'display_name' not in meta:
            invalid_naming.append(f.name)
            continue

        df = load_and_normalize(f)
        if df is not None and not df.empty:
            store[meta['display_name']] = {"data": df, "meta": meta}
        else:
            parsing_failed.append(f.name)

    if store:
        st.session_state.portfolio_store = store

    if invalid_naming:
        for inv_f in invalid_naming:
            st.error(
                f"❌ **Invalid file name rejected:** `{inv_f}`\n\n"
                f"Please ensure the file has the Month and 4-digit Year at the end: `AMC-SchemeName-Month-Year`  \n"
                f"**Example:** `Navi-NiftyNextFifty-May-2026.xlsx`"
            )

    if parsing_failed:
        for fail_f in parsing_failed:
            st.warning(f"⚠️ **Could not extract equity data from:** `{fail_f}`. Ensure it contains valid Indian equity ISINs (`INE...`).")

    if store:
        st.success(f"✅ Loaded {len(store)} portfolio(s) into memory. Use the left sidebar to navigate to MoM Drift or Cross-AMC pages.")

# Render Overview if portfolios are present
if st.session_state.portfolio_store:
    st.divider()
    st.subheader("📂 Loaded Portfolios Overview")

    col1, col2, col3 = st.columns(3)
    total_files = len(st.session_state.portfolio_store)
    total_equities = sum(len(v.get('data', [])) for v in st.session_state.portfolio_store.values())

    with col1:
        render_kpi_card("Active Portfolios", str(total_files), "Loaded in memory")
    with col2:
        render_kpi_card("Total Equities Captured", str(total_equities), "Validated INE stocks")
    with col3:
        render_kpi_card("System Status", "Ready", "Proceed to analysis pages")

    summary_records = []
    for k, v in st.session_state.portfolio_store.items():
        meta = v.get('meta', {})
        df_len = len(v.get('data', []))
        summary_records.append({
            "Display Name": k,
            "AMC": meta.get('amc', 'N/A'),
            "Scheme Name": meta.get('scheme', 'N/A'),
            "Period": meta.get('period', 'N/A'),
            "Total Stocks": df_len
        })

    st.dataframe(pd.DataFrame(summary_records), hide_index=True, use_container_width=True)

    if st.button("🗑️ Clear All Loaded Portfolios"):
        st.session_state.portfolio_store = {}
        st.rerun()
else:
    if not uploaded_files:
        st.info("💡 **Tip:** Upload your AMC portfolio files above to get started.")
