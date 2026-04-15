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
        'Name of the Instrument': 'Stock Name', 'Company Name': 'Stock Name',
        'Issuer': 'Stock Name', 'Security': 'Stock Name',
        'Industry Classification': 'Sector', 'Industry/Rating': 'Sector',
        '% to Net Assets': 'Weight (%)', 'Weightage': 'Weight (%)'
    }
}

# --- 2. CORE ENGINE FUNCTIONS ---

def find_header_row(df_preview):
    """Scans rows to find the table start; converts all to str to avoid float errors."""
    for i, row in df_preview.iterrows():
        row_values = [str(val).lower() if val is not None else "" for val in row.values]
        row_str = " ".join(row_values)
        if any(key in row_str for key in ["isin", "instrument", "stock name", "issuer"]):
            [span_1](start_span)return i[span_1](end_span)
    return 0

def load_and_normalize(uploaded_file):
    """Reads file, finds headers, and maps to Blueprint columns."""
    try:
        if uploaded_file.name.endswith('csv'):
            df = pd.read_csv(uploaded_file, skiprows=find_header_row(pd.read_csv(uploaded_file, nrows=20, header=None)))
        else:
            df = pd.read_excel(uploaded_file, skiprows=find_header_row(pd.read_excel(uploaded_file, nrows=20, header=None)))
        
        df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
        df = df.rename(columns=BLUEPRINT["mapping"])
        
        # Recovery for Weight column if mapping fails
        if 'Weight (%)' not in df.columns:
            for col in df.columns:
                if '%' in col or 'assets' in col.lower():
                    df = df.rename(columns={col: 'Weight (%)'})
                    break

        df = df[[c for c in BLUEPRINT["required_cols"] if c in df.columns]].copy()
        if not df.empty:
            df = df.dropna(subset=[df.columns[0]])
            df['Weight (%)'] = pd.to_numeric(df['Weight (%)'].astype(str).str.replace(r'[^0-9.]', '', regex=True), errors='coerce').fillna(0.0)
        return df.reset_index(drop=True)
    except Exception as e:
        st.error(f"Error processing {uploaded_file.name}: {e}")
        [span_2](start_span)return None[span_2](end_span)

def harmonized_fuzzy_match(df_dict):
    """Standardizes stock names across all portfolios to ensure analysis accuracy."""
    if not df_dict: return {}
    all_stocks = pd.concat([df['Stock Name'] for df in df_dict.values() if 'Stock Name' in df.columns]).dropna().unique().tolist()
    
    master_map, processed = {}, []
    for stock in all_stocks:
        stock_str = str(stock)
        if not processed:
            master_map[stock] = stock_str
            processed.append(stock_str)
        else:
            match, score = process.extractOne(stock_str, processed, scorer=fuzz.token_sort_ratio)
            if score >= 90: master_map[stock] = match
            else:
                master_map[stock] = stock_str
                processed.append(stock_str)
    
    for name in df_dict:
        if 'Stock Name' in df_dict[name].columns:
            df_dict[name]['Stock Name'] = df_dict[name]['Stock Name'].map(master_map)
    [span_3](start_span)return df_dict[span_3](end_span)

# --- 3. UI LOGIC ---

def main():
    st.title("📈 Mutual Fund Portfolio Pro-Analyzer")
    
    # NEW: Analysis Goal Selector
    analysis_goal = st.sidebar.radio(
        "What is your analysis goal?",
        ["Time-Series (Same Fund, Different Months)", "Cross-Portfolio (Compare Different AMCs)"],
        help="Time-Series focuses on MoM changes. Cross-Portfolio focuses on overlaps and shared bets."
    )

    if 'normalized_dfs' not in st.session_state:
        st.session_state.normalized_dfs = {}

    with st.sidebar:
        st.header("1. Upload Data")
        files = st.file_uploader("Upload MF Disclosures", accept_multiple_files=True, type=['csv', 'xlsx'])
        if st.button("Process & Analyze"):
            if files:
                temp_dict = {f.name: load_and_normalize(f) for f in files if load_and_normalize(f) is not None}
                st.session_state.normalized_dfs = harmonized_fuzzy_match(temp_dict)
                st.success(f"Portfolios Loaded: {len(st.session_state.normalized_dfs)}")
            else:
                st.error("Please upload files.")

    if not st.session_state.normalized_dfs:
        st.warning("Please upload and process files in the sidebar.")
        return

    funds = list(st.session_state.normalized_dfs.keys())

    # --- MODE 1: TIME-SERIES ---
    if analysis_goal == "Time-Series (Same Fund, Different Months)":
        st.header("🕒 Month-on-Month Performance & Churn")
        c1, c2 = st.columns(2)
        curr_name = c1.selectbox("Current Month File", funds, index=0)
        prev_name = c2.selectbox("Previous Month File", funds, index=min(1, len(funds)-1))

        if curr_name != prev_name:
            curr_df, prev_df = st.session_state.normalized_dfs[curr_name], st.session_state.normalized_dfs[prev_name]
            
            # Stock Drift
            new_in = set(curr_df['Stock Name']) - set(prev_df['Stock Name'])
            exits = set(prev_df['Stock Name']) - set(curr_df['Stock Name'])
            
            m1, m2 = st.columns(2)
            m1.metric("New Stock Entries", len(new_in))
            m2.metric("Complete Exits", len(exits))

            # Sector Drift (Where is the AMC increasing bets?)
            st.subheader("Sectoral Weightage Shifts")
            curr_sec = curr_df.groupby('Sector')['Weight (%)'].sum()
            prev_sec = prev_df.groupby('Sector')['Weight (%)'].sum()
            sec_drift = (curr_sec - prev_sec).dropna().reset_index()
            sec_drift.columns = ['Sector', 'Weight Change (%)']
            
            fig = px.bar(sec_drift.sort_values('Weight Change (%)'), x='Weight Change (%)', y='Sector', 
                         orientation='h', color='Weight Change (%)', color_continuous_scale='RdYlGn',
                         title="Where the AMC Increased/Decreased Bets")
            [span_4](start_span)st.plotly_chart(fig, width="stretch")[span_4](end_span)

    # --- MODE 2: CROSS-PORTFOLIO ---
    else:
        st.header("🤝 Cross-AMC Comparison & Shared Conviction")
        
        # Overlap Matrix
        if len(funds) > 1:
            matrix = pd.DataFrame(index=funds, columns=funds)
            for f1 in funds:
                for f2 in funds:
                    s1, s2 = set(st.session_state.normalized_dfs[f1]['Stock Name']), set(st.session_state.normalized_dfs[f2]['Stock Name'])
                    matrix.loc[f1, f2] = round((len(s1 & s2) / len(s1 | s2)) * 100, 2) if (s1 | s2) else 0
            [span_5](start_span)st.plotly_chart(px.imshow(matrix.astype(float), text_auto=True, title="Portfolio Overlap %"), width="stretch")[span_5](end_span)

        # Common Bets (High Conviction Stocks)
        st.subheader("Common Holdings Across Different AMCs")
        all_data = pd.concat(st.session_state.normalized_dfs.values())
        common = all_data.groupby(['Stock Name', 'Sector']).agg({'Weight (%)': 'sum', 'Stock Name': 'count'})
        common.columns = ['Total Aggregated Weight (%)', 'Number of AMCs Holding This']
        [span_6](start_span)st.dataframe(common[common['Number of AMCs Holding This'] > 1].sort_values('Number of AMCs Holding This', ascending=False), width="stretch")[span_6](end_span)

if __name__ == "__main__":
    main()
    
