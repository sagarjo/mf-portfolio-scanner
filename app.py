import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from thefuzz import process, fuzz
import io

# --- 1. CONFIGURATION & BLUEPRINT ---
st.set_page_config(page_title="MF Portfolio Pro-Analyzer", layout="wide")

# The "Blueprint" defines our expected schema
BLUEPRINT = {
    "required_cols": ['Stock Name', 'Weight (%)', 'Sector'],
    "mapping": {
        'Company': 'Stock Name',
        'Issuer': 'Stock Name',
        'Security': 'Stock Name',
        'Weightage': 'Weight (%)',
        'Allocation': 'Weight (%)',
        'Industry': 'Sector',
        'Group': 'Sector'
    }
}

# --- 2. CORE FUNCTIONS ---

def normalize_dataframe(df):
    """Maps raw AMC data to the Blueprint schema."""
    # Clean column names
    df.columns = [str(c).strip() for c in df.columns]
    
    # Rename based on mapping
    df = df.rename(columns=BLUEPRINT["mapping"])
    
    # Ensure required columns exist
    for col in BLUEPRINT["required_cols"]:
        if col not in df.columns:
            df[col] = "Unknown" if col != 'Weight (%)' else 0.0
            
    # Clean numeric data
    if 'Weight (%)' in df.columns:
        df['Weight (%)'] = pd.to_numeric(
            df['Weight (%)'].astype(str).str.replace('%', '').str.replace('[^0-9.]', '', regex=True),
            errors='coerce'
        ).fillna(0.0)
        
    return df[BLUEPRINT["required_cols"]]

def harmonized_fuzzy_match(df_dict):
    """Ensures stock names are identical across all uploaded files."""
    all_stocks = pd.concat([df['Stock Name'] for df in df_dict.values()]).unique().tolist()
    master_map = {}
    processed_stocks = []

    for stock in all_stocks:
        if not processed_stocks:
            master_map[stock] = stock
            processed_stocks.append(stock)
        else:
            # Check if stock exists in processed list with 90% similarity
            match, score = process.extractOne(stock, processed_stocks, scorer=fuzz.token_sort_ratio)
            if score >= 90:
                master_map[stock] = match
            else:
                master_map[stock] = stock
                processed_stocks.append(stock)
                
    for name in df_dict:
        df_dict[name]['Stock Name'] = df_dict[name]['Stock Name'].map(master_map)
    
    return df_dict

# --- 3. UI & STATE MANAGEMENT ---

def main():
    st.title("📈 Mutual Fund Portfolio Analyzer")
    st.subheader("Deep-Dive Cross-Portfolio Insights & Drift Tracking")

    # Initialize Session State
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    if 'normalized_dfs' not in st.session_state:
        st.session_state.normalized_dfs = {}

    with st.sidebar:
        st.header("Upload Center")
        st.info("Upload up to 5 CSV/Excel files. Use files from different months for Drift tracking.")
        files = st.file_uploader("Drop files here", accept_multiple_files=True, type=['csv', 'xlsx'])
        
        if st.button("Process & Normalize"):
            if files:
                temp_dict = {}
                for f in files[:5]:
                    raw_df = pd.read_excel(f) if f.name.endswith('xlsx') else pd.read_csv(f)
                    temp_dict[f.name] = normalize_dataframe(raw_df)
                
                # Run Fuzzy Matching
                st.session_state.normalized_dfs = harmonized_fuzzy_match(temp_dict)
                st.session_state.data_loaded = True
                st.success("Normalization Complete!")
            else:
                st.error("Please upload files first.")

    if not st.session_state.data_loaded:
        st.warning("Please upload and process data from the sidebar to view the dashboard.")
        return

    # --- 4. DASHBOARD TABS ---
    tab_overlap, tab_drift, tab_sector = st.tabs(["Overlap Matrix", "Drift Tracker", "Concentration & Sector"])

    with tab_overlap:
        st.header("Portfolio Intersection")
        funds = list(st.session_state.normalized_dfs.keys())
        if len(funds) > 1:
            matrix = pd.DataFrame(index=funds, columns=funds)
            for f1 in funds:
                for f2 in funds:
                    s1 = set(st.session_state.normalized_dfs[f1]['Stock Name'])
                    s2 = set(st.session_state.normalized_dfs[f2]['Stock Name'])
                    intersect = len(s1.intersection(s2))
                    union = len(s1.union(s2))
                    matrix.loc[f1, f2] = round((intersect / union) * 100, 2)
            
            fig = px.imshow(matrix.astype(float), text_auto=True, color_continuous_scale='Viridis',
                            title="Overlap Percentage (%)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Upload at least 2 funds to see the overlap matrix.")

    with tab_drift:
        st.header("The Drift Tracker (Month-on-Month)")
        col1, col2 = st.columns(2)
        curr = col1.selectbox("Current Portfolio", funds, index=0)
        prev = col2.selectbox("Previous Portfolio", funds, index=min(1, len(funds)-1))

        if curr != prev:
            curr_df = st.session_state.normalized_dfs[curr]
            prev_df = st.session_state.normalized_dfs[prev]
            
            new_entries = set(curr_df['Stock Name']) - set(prev_df['Stock Name'])
            exits = set(prev_df['Stock Name']) - set(curr_df['Stock Name'])
            
            c1, c2 = st.columns(2)
            c1.metric("New Entries", len(new_entries))
            c2.metric("Complete Exits", len(exits))
            
            st.subheader("Stake Changes")
            drift_merge = pd.merge(curr_df, prev_df, on='Stock Name', how='inner', suffixes=('_curr', '_prev'))
            drift_merge['Change'] = drift_merge['Weight (%)_curr'] - drift_merge['Weight (%)_prev']
            st.dataframe(drift_merge[['Stock Name', 'Weight (%)_prev', 'Weight (%)_curr', 'Change']].sort_values('Change', ascending=False), use_container_width=True)

    with tab_sector:
        st.header("Sectoral Over-Exposure")
        all_data = pd.concat(st.session_state.normalized_dfs.values())
        
        # Sector Pie Chart
        sector_agg = all_data.groupby('Sector')['Weight (%)'].sum().reset_index()
        fig_sector = px.pie(sector_agg, values='Weight (%)', names='Sector', hole=0.5, 
                            title="Aggregated Sector Distribution (All Funds)")
        st.plotly_chart(fig_sector, use_container_width=True)
        
        # Stock Concentration Table
        st.subheader("Global Stock Concentration")
        stock_agg = all_data.groupby(['Stock Name', 'Sector'])['Weight (%)'].agg(['sum', 'count']).reset_index()
        stock_agg.columns = ['Stock Name', 'Sector', 'Total Weight (%)', 'Fund Count']
        st.dataframe(stock_agg.sort_values('Total Weight (%)', ascending=False), use_container_width=True)

        # Export
        csv = stock_agg.to_csv(index=False).encode('utf-8')
        st.download_button("Download Full Analysis", data=csv, file_name="consolidated_portfolio.csv", mime='text/csv')

if __name__ == "__main__":
    main()
