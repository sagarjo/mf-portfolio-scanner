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
> **Example:** `Navi-NiftyNext50-May-2026.xlsx` or `Canara-Robeco-Small-Cap-Fund-July-2026.xlsx`
""")

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
        if not meta:
            invalid_naming.append(f.name)
            continue

        df = load_and_normalize(f)
        if df is not None and not df.empty:
            store[meta['display_name']] = {"data": df, "meta": meta}
        else:
            parsing_failed.append(f.name)

    st.session_state.portfolio_store = store

    if invalid_naming:
        for inv_f in invalid_naming:
            st.error(
                f"❌ **Invalid file name rejected:** `{inv_f}`\n\n"
                f"Please ensure the file has the Month and 4-digit Year at the end: `AMC-SchemeName-Month-Year`  \n"
                f"**Examples:** \n"
                f"* `Navi-NiftyNext50-May-2026.xlsx`  \n"
                f"* `Canara-Robeco-Small-Cap-Fund-July-2026.xlsx`"
            )

    if parsing_failed:
        for fail_f in parsing_failed:
            st.warning(f"⚠️ **Could not extract equity data from:** `{fail_f}`. Ensure it contains valid equity rows with `INE...` ISINs.")

    if store:
        st.success(f"✅ Successfully loaded {len(store)} portfolio(s) into memory! Use the left sidebar to navigate to MoM Drift or Cross-AMC pages.")

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
    st.dataframe(pd.DataFrame(summary_records), hide_index=True, use_container_width=True)
else:
    if not uploaded_files:
        st.info("💡 **Tip:** Upload your AMC portfolio files above to get started.")
