import streamlit as st
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
> **Example:** `Navi-NiftyNext50-May-2026.xlsx`
""")

# Initialize storage in session state if not present
if 'portfolio_store' not in st.session_state:
    st.session_state.portfolio_store = {}

# File Uploader
uploaded_files = st.file_uploader(
    "Upload Portfolio Files (.xlsx, .csv)",
    accept_multiple_files=True,
    type=['csv', 'xlsx'],
    help="Files must strictly match the naming convention: AMC-SchemeName-Month-Year (e.g. Navi-NiftyNext50-May-2026.xlsx)"
)

# Explicit Action Button
if uploaded_files:
    if st.button("🔄 Process / Refresh Files", type="primary", use_container_width=True):
        store = {}
        invalid_naming = []
        parsing_failed = []

        with st.spinner("Processing and normalizing portfolio holdings..."):
            for f in uploaded_files:
                # Step 1: Validate filename
                meta = validate_and_parse_filename(f.name)
                if not meta:
                    invalid_naming.append(f.name)
                    continue

                # Step 2: Extract & clean data
                df = load_and_normalize(f)
                if df is not None and not df.empty:
                    store[meta['display_name']] = {"data": df, "meta": meta}
                else:
                    parsing_failed.append(f.name)

        # Update Session State
        st.session_state.portfolio_store = store

        # Display Feedback
        if invalid_naming:
            for inv_f in invalid_naming:
                st.error(
                    f"❌ **Invalid file name rejected:** `{inv_f}`\n\n"
                    f"Please rename the file using the format: `AMC-SchemeName-Month-Year`  \n"
                    f"**Example:** `Navi-NiftyNext50-May-2026.xlsx`"
                )

        if parsing_failed:
            for fail_f in parsing_failed:
                st.warning(
                    f"⚠️ **Could not extract equity data from:** `{fail_f}`\n\n"
                    f"Check that the sheet contains valid column headers (`ISIN`, `Weight (%)` / `% of Net Assets`, `Stock Name`) "
                    f"and valid equity ISINs starting with `INE`."
                )

        if store:
            st.success(f"✅ Successfully loaded {len(store)} valid portfolio(s)!")
            st.rerun()

# Render Overview if portfolios are present
if st.session_state.portfolio_store:
    st.divider()
    st.subheader("📂 Loaded Portfolios Overview")
    
    col1, col2, col3 = st.columns(3)
    total_files = len(st.session_state.portfolio_store)
    total_equities = sum(len(v['data']) for v in st.session_state.portfolio_store.values())
    
    with col1:
        render_kpi_card("Active Portfolios", str(total_files), "Loaded in memory")
    with col2:
        render_kpi_card("Total Equities Captured", str(total_equities), "Validated INE stocks")
    with col3:
        render_kpi_card("System Status", "Ready", "Proceed to analysis pages")

    summary_records = [
        {
            "Display Name": k,
            "AMC": v['meta']['amc'],
            "Scheme Name": v['meta']['scheme'],
            "Period": v['meta']['period'],
            "Total Stocks": len(v['data'])
        }
        for k, v in st.session_state.portfolio_store.items()
    ]
    st.dataframe(summary_records, hide_index=True, use_container_width=True)
else:
    if uploaded_files:
        st.info("👆 Click the **'🔄 Process / Refresh Files'** button above to parse your uploaded files.")
    else:
        st.info("💡 **Tip:** Upload files meeting the naming requirement above to start.")
