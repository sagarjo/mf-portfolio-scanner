import streamlit as st
import pandas as pd
import plotly.express as px
from thefuzz import process, fuzz

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="MF Portfolio Pro-Analyzer", layout="wide")

BLUEPRINT = {
    "required_cols": ['Stock Name', 'Weight (%)', 'Sector', 'ISIN'],
    "mapping": {
        'Name of the Instrument': 'Stock Name', 'Company Name': 'Stock Name',
        'Issuer': 'Stock Name', 'Security': 'Stock Name',
        'Industry Classification': 'Sector', 'Industry/Rating': 'Sector',
        '% to Net Assets': 'Weight (%)', 'Weightage': 'Weight (%)',
        'ISIN Code': 'ISIN', 'ISIN': 'ISIN'
    }
}

# --- 2. CORE ENGINE FUNCTIONS ---

def find_header_row(df_preview):
    """Scans for headers using ISIN as the anchor to avoid noise."""
    for i, row in df_preview.iterrows():
        row_values = [str(val).lower() if val is not None else "" for val in row.values]
        row_str = " ".join(row_values)
        if "isin" in row_str:
            return i
    return 0

def load_and_normalize(uploaded_file):
    try:
        if uploaded_file.name.endswith('csv'):
            df = pd.read_csv(uploaded_file, skiprows=find_header_row(pd.read_csv(uploaded_file, nrows=30, header=None)))
        else:
            df = pd.read_excel(uploaded_file, skiprows=find_header_row(pd.read_excel(uploaded_file, nrows=30, header=None)))
        
        df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
        df = df.rename(columns=BLUEPRINT["mapping"])
        
        # Recover Weight column if mapping missed it
        if 'Weight (%)' not in df.columns:
            for col in df.columns:
                if '%' in col or 'assets' in col.lower():
                    df = df.rename(columns={col: 'Weight (%)'})
                    break

        # STRICT ISIN FILTER: Remove anything that isn't a security (Total, SubTotal, Cash)
        if 'ISIN' in df.columns:
            df = df.dropna(subset=['ISIN'])
            df['ISIN'] = df['ISIN'].astype(str).str.strip()
            df = df[df['ISIN'].str.len() >= 10] 
        else:
            st.warning(f"No ISIN column detected in {uploaded_file.name}. Results may be noisy.")

        cols_to_keep = [c for c in BLUEPRINT["required_cols"] if c in df.columns]
        df = df[cols_to_keep].copy()
        
        if not df.empty and 'Weight (%)' in df.columns:
            df['Weight (%)'] = pd.to_numeric(df['Weight (%)'].astype(str).str.replace(r'[^0-9.]', '', regex=True), errors='coerce').fillna(0.0)
            
        return df.reset_index(drop=True)
    except Exception as e:
        st.error(f"Error processing {uploaded_file.name}: {e}")
        return None

def harmonized_fuzzy_match(df_dict):
    """Uses ISIN to ensure 'Vedanta Ltd' and 'Vedanta' are treated as identical."""
    if not df_dict: return {}
    
    isin_map = {}
    for df in df_dict.values():
        if 'ISIN' in df.columns:
            for _, row in df.iterrows():
                isin_map[row['ISIN']] = row['Stock Name']

    for name in df_dict:
        if 'ISIN' in df_dict[name].columns:
            df_dict[name]['Stock Name'] = df_dict[name]['ISIN'].map(isin_map)
            
    return df_dict

# --- 3. UI LOGIC ---

def main():
    st.title("🛡️ ISIN-Verified Portfolio Analyzer")
    
    analysis_goal = st.sidebar.radio(
        "Choose Analysis Goal:",
        ["Time-Series (Same Fund, Different Months)", "Cross-Portfolio (Compare Different AMCs)"]
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
        st.warning("Upload files containing 'ISIN' columns for accurate Stock-only analysis.")
        return

    funds = list(st.session_state.normalized_dfs.keys())

    if analysis_goal == "Time-Series (Same Fund, Different Months)":
        st.header("🕒 ISIN-Tracked Portfolio Dynamics")
        c1, c2 = st.columns(2)
        curr_name = c1.selectbox("Current Month", funds, index=0)
        prev_name = c2.selectbox("Previous Month", funds, index=min(1, len(funds)-1))

        if curr_name != prev_name:
            curr_df, prev_df = st.session_state.normalized_dfs[curr_name], st.session_state.normalized_dfs[prev_name]
            
            # Metrics
            curr_isins, prev_isins = set(curr_df['ISIN']), set(prev_df['ISIN'])
            new_isins, exit_isins = curr_isins - prev_isins, prev_isins - curr_isins
            
            m1, m2, m3 = st.columns(3)
            m1.metric("New Stock Entries", len(new_isins))
            m2.metric("Retained Stocks", len(curr_isins & prev_isins))
            m3.metric("Complete Exits", len(exit_isins))

            # Restored Sector Drift Chart
            st.divider()
            st.subheader("Sectoral Weightage Shifts (MoM)")
            curr_sec = curr_df.groupby('Sector')['Weight (%)'].sum()
            prev_sec = prev_df.groupby('Sector')['Weight (%)'].sum()
            sec_drift = (curr_sec - prev_sec).fillna(0).reset_index()
            sec_drift.columns = ['Sector', 'Weight Change (%)']
            
            fig = px.bar(sec_drift.sort_values('Weight Change (%)'), x='Weight Change (%)', y='Sector', 
                         orientation='h', color='Weight Change (%)', 
                         color_continuous_scale='RdYlGn', title="Sectoral Rotation (Bullish vs Bearish)")
            st.plotly_chart(fig, width="stretch")

            # Summary Tables
            st.divider()
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.write("**🆕 New Entries**")
                st.dataframe(curr_df[curr_df['ISIN'].isin(new_isins)][['Stock Name', 'Weight (%)', 'Sector']], hide_index=True)
            with col_b:
                st.write("**✅ Common (MoM Change)**")
                drift_df = pd.merge(curr_df, prev_df, on='ISIN', suffixes=('_curr', '_prev'))
                drift_df['Change'] = drift_df['Weight (%)_curr'] - drift_df['Weight (%)_prev']
                st.dataframe(drift_df[['Stock Name_curr', 'Weight (%)_curr', 'Change']].rename(columns={'Stock Name_curr':'Stock Name'}).sort_values('Change', ascending=False), hide_index=True)
            with col_c:
                st.write("**❌ Complete Exits**")
                st.dataframe(prev_df[prev_df['ISIN'].isin(exit_isins)][['Stock Name', 'Weight (%)', 'Sector']], hide_index=True)

    else:
        st.header("🤝 Cross-AMC Overlap (ISIN Verified)")
        if len(funds) > 1:
            matrix = pd.DataFrame(index=funds, columns=funds)
            for f1 in funds:
                for f2 in funds:
                    s1, s2 = set(st.session_state.normalized_dfs[f1]['ISIN']), set(st.session_state.normalized_dfs[f2]['ISIN'])
                    matrix.loc[f1, f2] = round((len(s1 & s2) / len(s1 | s2)) * 100, 2) if (s1 | s2) else 0
            st.plotly_chart(px.imshow(matrix.astype(float), text_auto=True, title="Portfolio Intersection %"), width="stretch")
            
        st.subheader("Shared Conviction (Stocks held by >1 AMC)")
        all_data = pd.concat(st.session_state.normalized_dfs.values())
        common_agg = all_data.groupby(['Stock Name', 'Sector']).agg({'Weight (%)': 'sum', 'Stock Name': 'count'})
        common_agg.columns = ['Total Exposure (%)', 'AMC Count']
        st.dataframe(common_agg[common_agg['AMC Count'] > 1].sort_values('AMC Count', ascending=False), width="stretch")

if __name__ == "__main__":
    main()
    
