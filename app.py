import streamlit as st
from utils.data_loader import load_and_normalize, parse_filename_metadata
from utils.ui_components import inject_custom_styles, render_kpi_card

st.set_page_config(
    page_title="MF Data Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_custom_styles()

st.title("🛡️ Mutual Fund Data Dashboard")
st.markdown("Upload monthly AMC portfolio disclosures below. Cleaned holdings and metadata are automatically processed across all analytical pages.")

# Upload Engine
uploaded_files = st.file_uploader(
    "Upload Portfolio Files (.xlsx, .csv)",
    accept_multiple_files=True,
    type=['csv', 'xlsx'],
    help="Upload official monthly AMC portfolio disclosures containing valid ISIN details."
)

if uploaded_files:
    if 'portfolio_store' not in st.session_state or st.button("🔄 Reload / Refresh Uploaded Data"):
        store = {}
        for f in uploaded_files:
            df = load_and_normalize(f)
            if df is not None and not df.empty:
                meta = parse_filename_metadata(f.name)
                store[meta['display_name']] = {"data": df, "meta": meta}
        st.session_state.portfolio_store = store
        st.success(f"✅ Successfully processed {len(store)} portfolio(s). Use the sidebar to navigate to MoM Drift or Cross-AMC Analysis.")

if 'portfolio_store' in st.session_state and st.session_state.portfolio_store:
    st.divider()
    st.subheader("📂 Loaded Portfolios Overview")
    
    col1, col2, col3 = st.columns(3)
    total_files = len(st.session_state.portfolio_store)
    total_equities = sum(len(v['data']) for v in st.session_state.portfolio_store.values())
    
    with col1:
        render_kpi_card("Active Portfolios", str(total_files), "Loaded in memory")
    with col2:
        render_kpi_card("Total Rows Captured", str(total_equities), "Cleaned INE equities")
    with col3:
        render_kpi_card("Status", "Ready", "Proceed to analytical pages")

    summary_records = [
        {
            "Display Name": k,
            "Detected AMC": v['meta']['amc'],
            "Period": v['meta']['period'],
            "Total Stocks": len(v['data'])
        }
        for k, v in st.session_state.portfolio_store.items()
    ]
    st.table(summary_records)
else:
    st.info("💡 **Tip:** Upload files above, then switch pages in the left sidebar to begin.")
