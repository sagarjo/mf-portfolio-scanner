import streamlit as st
import pandas as pd
import plotly.express as px
from thefuzz import process, fuzz
import io
import re

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="MF Portfolio Pro-Analyzer", layout="wide")

BLUEPRINT = {
    "required_cols": ['Stock Name', 'Weight (%)', 'Sector'],
    "mapping": {
        'Name of the Instrument': 'Stock Name',
        'Company Name': 'Stock Name',
        'Issuer': 'Stock Name',
        'Security': 'Stock Name',
        'Industry Classification': 'Sector',
        'Industry/Rating': 'Sector',
        'Industry / Rating': 'Sector',
        'Industry': 'Sector',
        'Group': 'Sector',
        '% to Net Assets': 'Weight (%)',
        'Weightage': 'Weight (%)',
        'Allocation (%)': 'Weight (%)'
    }
}

# --- 2. CORE ROBUST FUNCTIONS ---

def find_header_row(df_preview):
    """Scans rows to find where the actual table starts."""
    for i, row in df_preview.iterrows():
        row_str = " ".join(row.astype(str).values).lower()
        if "isin" in row_str or "instrument" in row_str or "stock name" in row_str:
            return i
    return 0

def load_any_file(uploaded_file):
    """Handles dynamic headers and different file types."""
    try:
        if uploaded_file.name.endswith('csv'):
            preview = pd.read_csv(uploaded_file, nrows=20, header=None)
            header_idx = find_header_row(preview)
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, skiprows=header_idx)
        else:
            preview = pd.read_excel(uploaded_file, nrows=20, header=None)
            header_idx = find_header_row(preview)
            df = pd.read_excel(uploaded_file, skiprows=header_idx)
        return df
    except Exception as e:
        st.error(f"Error reading {uploaded_file.name}: {e}")
        return None

def normalize_dataframe(df):
    """Clean the raw data by stripping headers and formatting noise."""
    df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
    df = df.rename(columns=BLUEPRINT["mapping"])
    
    if 'Weight (%)' not in df.columns:
        for col in df.columns:
            if '%' in col or 'assets' in col.lower():
                df = df.rename(columns={col: 'Weight (%)'})
                break

    cols_to_keep = [c for c in BLUEPRINT["required_cols"] if c in df.columns]
    df = df[cols_to_keep]

    if not df.empty:
        df = df.dropna(subset=[df.columns[0]])
        noise_keywords = ['total', 'equity', 'listed', 'subtotal', 'grand', 'isin', 'instrument', 'cash']
        df = df[~df[df.columns[0]].astype(str).str.contains('|'.join(noise_keywords), case=False, na=False)]

        if 'Weight (%)' in df.columns:
            df['Weight (%)'] = (
                df['Weight (%)'].astype(str)
                .str.replace('%', '', regex=False)
                .str.replace(r'[^0-9.]', '', regex=True)
            )
            df['Weight (%)'] = pd.to_numeric(df['Weight (%)'], errors='coerce').fillna(0.0)
        
    return df.reset_index(drop=True)

def harmonized_fuzzy_match(df_dict):
    """Ensures stock names are identical across all uploaded files."""
    if not df_dict:
        return {}
        
    all_stocks_list = [df['Stock Name'] for df in df_dict.values() if 'Stock Name' in df.columns]
    if not all_stocks_list:
        return df_dict
        
    all_stocks = pd.concat(all_stocks_list)
    unique_stocks = all_stocks.unique().tolist()
    
    master_map = {}
    processed_list = []

    for stock in unique_stocks:
        if not processed_list:
            master_map[stock] = stock
            processed_list.append(stock)
        else:
            match, score = process.extractOne(stock, processed_list, scorer=fuzz.token_sort_ratio)
            if score >= 90:
                master_map[stock] = match
            else:
                master_map[stock] = stock
                processed_list.append(stock)
                
    for name in df_dict:
        if 'Stock Name' in df_dict[name].columns:
            df_dict[name]['Stock Name'] = df_dict[name]['Stock Name'].map(master_map)
    
    return df_dict

# --- 3. UI & DASHBOARD ---

def main():
    st.title("📈 Mutual Fund Portfolio Pro-Analyzer")
    st.subheader("Deep-Dive Insights from Any AMC Statement")

    if 'normalized_dfs' not in st.session_state:
        st.session_state.normalized_dfs = {}

    with st.sidebar:
        st.header("Upload Center")
        st.info("Upload CSV/Excel files. The engine will automatically detect headers.")
        files = st.file_uploader("Drop files here", accept_multiple_files=True, type=['csv', 'xlsx'])
        
        if st.button("Process & Analyze"):
            if files:
                temp_dict = {}
                for f in files:
                    raw_df = load_any_file(f)
                    if raw_df is not None:
                        temp_dict[f.name] = normalize_dataframe(raw_df)
                
                st.session_state.normalized_dfs = harmonized_fuzzy_match(temp_dict)
                st.success(f"Processed {len(st.session_state.normalized_dfs)} portfolios.")
            else:
                st.error("Please upload files first.")

    if not st.session_state.normalized_dfs:
        st.warning("Upload data from the sidebar to begin.")
        return

    tab_overlap, tab_drift, tab_sector = st.tabs(["Overlap Matrix", "Drift Tracker", "Concentration & Sector"])

    funds = list(st.session_state.normalized_dfs.keys())

    with tab_overlap:
        st.header("Portfolio Intersection")
        if len(funds) > 1:
            matrix = pd.DataFrame(index=funds, columns=funds)
            for f1 in funds:
                for f2 in funds:
                    s1 = set(st.session_state.normalized_dfs[f1]['Stock Name'])
                    s2 = set(st.session_state.normalized_dfs[f2]['Stock Name'])
                    intersect = len(s1.intersection(s2))
                    union = len(s1.union(s2))
                    matrix.loc[f1, f2] = round((intersect / union) * 100, 2)
            
            fig = px.imshow(matrix.astype(float), text_auto=True, color_continuous_scale='Viridis')
            st.plotly_chart(fig, width="stretch") 
        else:
            st.info("Upload at least 2 funds to see the overlap matrix.")

    with tab_drift:
        st.header("Drift Tracker (Comparison)")
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
            
            drift_merge = pd.merge(curr_df, prev_df, on='Stock Name', how='inner', suffixes=('_curr', '_prev'))
            if not drift_merge.empty:
                drift_merge['Change'] = drift_merge['Weight (%)_curr'] - drift_merge['Weight (%)_prev']
                st.dataframe(drift_merge[['Stock Name', 'Weight (%)_prev', 'Weight (%)_curr', 'Change']].sort_values('Change', ascending=False), width="stretch")
            else:
                st.info("No common stocks found to track drift.")

    with tab_sector:
        st.header("Sector & Global Concentration")
        
        dfs_to_concat = list(st.session_state.normalized_dfs.values())
        if dfs_to_concat:
            all_data = pd.concat(dfs_to_concat)
            
            sector_agg = all_data.groupby('Sector')['Weight (%)'].sum().reset_index()
            fig_sector = px.pie(sector_agg, values='Weight (%)', names='Sector', hole=0.4, title="Overall Sector Distribution")
            st.plotly_chart(fig_sector, width="stretch") 
            
            stock_agg = all_data.groupby(['Stock Name', 'Sector'])['Weight (%)'].agg(['sum', 'count']).reset_index()
            stock_agg.columns = ['Stock Name', 'Sector', 'Total Weight (%)', 'Fund Count']
            st.dataframe(stock_agg.sort_values('Total Weight (%)', ascending=False), width="stretch")
        else:
            st.error("No valid data available for sector aggregation.")

if __name__ == "__main__":
    main()
    
