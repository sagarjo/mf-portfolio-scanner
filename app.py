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
    """Scans for headers. Now strictly looks for ISIN as an anchor."""
    for i, row in df_preview.iterrows():
        row_values = [str(val).lower() if val is not None else "" for val in row.values]
        row_str = " ".join(row_values)
        # ISIN is the most reliable anchor for the start of the data table
        if "isin" in row_str:
            return i
    return 0

def load_and_normalize(uploaded_file):
    try:
        # Initial read to find the header
        if uploaded_file.name.endswith('csv'):
            df = pd.read_csv(uploaded_file, skiprows=find_header_row(pd.read_csv(uploaded_file, nrows=30, header=None)))
        else:
            df = pd.read_excel(uploaded_file, skiprows=find_header_row(pd.read_excel(uploaded_file, nrows=30, header=None)))
        
        # Standardize Columns
        df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
        df = df.rename(columns=BLUEPRINT["mapping"])
        
        # Ensure 'Weight (%)' recovery
        if 'Weight (%)' not in df.columns:
            for col in df.columns:
                if '%' in col or 'assets' in col.lower():
                    df = df.rename(columns={col: 'Weight (%)'})
                    break

        # NEW STRICTOR FILTERING: Only keep rows where ISIN is present and valid
        if 'ISIN' in df.columns:
            # Drop rows where ISIN is NaN or empty
            df = df.dropna(subset=['ISIN'])
            # Remove rows where ISIN is 'nan', 'nil', or doesn't look like an ISIN (usually 12 chars)
            df['ISIN'] = df['ISIN'].astype(str).str.strip()
            df = df[df['ISIN'].str.len() >= 10] # Standard ISIN is 12, but we allow 10 for safety
        else:
            # If no ISIN column found, we fall back to noise filtering, but warn user
            st.warning(f"No ISIN column detected in {uploaded_file.name}. Noise rows might appear.")

        # Final column selection and type conversion
        cols_to_keep = [c for c in BLUEPRINT["required_cols"] if c in df.columns]
        df = df[cols_to_keep].copy()
        
        if not df.empty and 'Weight (%)' in df.columns:
            df['Weight (%)'] = pd.to_numeric(df['Weight (%)'].astype(str).str.replace(r'[^0-9.]', '', regex=True), errors='coerce').fillna(0.0)
            
        return df.reset_index(drop=True)
    except Exception as e:
        st.error(f"Error processing {uploaded_file.name}: {e}")
        return None

def harmonized_fuzzy_match(df_dict):
    """Uses ISIN as the primary key for matching, falling back to name only if ISIN differs."""
    if not df_dict: return {}
    
    # We can now be much more accurate because we have ISINs
    # Step 1: Create an ISIN to Name Master Map
    isin_map = {}
    for df in df_dict.values():
        if 'ISIN' in df.columns:
            for _, row in df.iterrows():
                isin_map[row['ISIN']] = row['Stock Name']

    # Step 2: Apply the master name for each ISIN across all files
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
                # Now using ISIN-based harmonization
                st.session_state.normalized_dfs = harmonized_fuzzy_match(temp_dict)
                st.success(f"Portfolios Loaded: {len(st.session_state.normalized_dfs)}")
            else:
                st.error("Please upload files.")

    if not st.session_state.normalized_dfs:
        st.warning("Please upload files that contain an 'ISIN' column for maximum accuracy.")
        return

    funds = list(st.session_state.normalized_dfs.keys())

    if analysis_goal == "Time-Series (Same Fund, Different Months)":
        st.header("🕒 ISIN-Tracked Portfolio Dynamics")
        c1, c2 = st.columns(2)
        curr_name = c1.selectbox("Current Month", funds, index=0)
        prev_name = c2.selectbox("Previous Month", funds, index=min(1, len(funds)-1))

        if curr_name != prev_name:
            curr_df, prev_df = st.session_state.normalized_dfs[curr_name], st.session_state.normalized_dfs[prev_name]
            
            # Using ISIN for the most accurate Set logic
            curr_isins = set(curr_df['ISIN'])
            prev_isins = set(prev_df['ISIN'])
            
            new_isins = curr_isins - prev_isins
            exit_isins = prev_isins - curr_isins
            
            m1, m2, m3 = st.columns(3)
            m1.metric("New Stock Entries", len(new_isins))
            m2.metric("Common Stocks", len(curr_isins & prev_isins))
            m3.metric("Complete Exits", len(exit_isins))

            # Tables based on ISIN matches
            st.divider()
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.write("**🆕 New Entries**")
                st.dataframe(curr_df[curr_df['ISIN'].isin(new_isins)][['Stock Name', 'Weight (%)', 'ISIN']], hide_index=True)
            with col_b:
                st.write("**✅ Common (By ISIN)**")
                drift_df = pd.merge(curr_df, prev_df, on='ISIN', suffixes=('_curr', '_prev'))
                drift_df['Change'] = drift_df['Weight (%)_curr'] - drift_df['Weight (%)_prev']
                st.dataframe(drift_df[['Stock Name_curr', 'Weight (%)_curr', 'Change']].rename(columns={'Stock Name_curr':'Stock Name'}), hide_index=True)
            with col_c:
                st.write("**❌ Complete Exits**")
                st.dataframe(prev_df[prev_df['ISIN'].isin(exit_isins)][['Stock Name', 'Weight (%)', 'ISIN']], hide_index=True)

    else:
        st.header("🤝 Cross-AMC Overlap (ISIN Verified)")
        # Overlap matrix using ISIN instead of names
        if len(funds) > 1:
            matrix = pd.DataFrame(index=funds, columns=funds)
            for f1 in funds:
                for f2 in funds:
                    s1, s2 = set(st.session_state.normalized_dfs[f1]['ISIN']), set(st.session_state.normalized_dfs[f2]['ISIN'])
                    matrix.loc[f1, f2] = round((len(s1 & s2) / len(s1 | s2)) * 100, 2) if (s1 | s2) else 0
            st.plotly_chart(px.imshow(matrix.astype(float), text_auto=True, title="Overlap % based on ISIN"), width="stretch")

if __name__ == "__main__":
    main()
    
