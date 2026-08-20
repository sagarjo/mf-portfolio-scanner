import re
import pandas as pd
import streamlit as st

BLUEPRINT = {
    "required_cols": ['Stock Name', 'Weight (%)', 'Sector', 'ISIN'],
    "mapping": {
        'Name of the Instrument': 'Stock Name', 'Company Name': 'Stock Name',
        'Issuer': 'Stock Name', 'Security': 'Stock Name', 'Instrument Name': 'Stock Name',
        'Industry Classification': 'Sector', 'Industry/Rating': 'Sector', 'Industry': 'Sector',
        '% to Net Assets': 'Weight (%)', 'Weightage': 'Weight (%)', '% of Total AUM': 'Weight (%)',
        '% to NAV': 'Weight (%)', '% of Net Assets': 'Weight (%)',
        'ISIN Code': 'ISIN', 'ISIN': 'ISIN', 'Isin': 'ISIN'
    }
}

VALID_MONTHS = {
    'jan', 'january', 'feb', 'february', 'mar', 'march', 'apr', 'april',
    'may', 'jun', 'june', 'jul', 'july', 'aug', 'august', 'sep', 'september',
    'oct', 'october', 'nov', 'november', 'dec', 'december'
}

def validate_and_parse_filename(filename: str):
    """
    Validates strictly for: AMC-SchemeName-Month-Year
    Example: Navi-NiftyNext50-May-2026.xlsx
    Returns dict if valid, None if invalid.
    """
    base_name = filename.rsplit('.', 1)[0].strip()
    parts = base_name.split('-')

    if len(parts) != 4:
        return None

    amc, scheme, month, year = [p.strip() for p in parts]

    # Validate month and 4-digit year
    if month.lower() not in VALID_MONTHS or not (year.isdigit() and len(year) == 4):
        return None

    if not amc or not scheme:
        return None

    return {
        "amc": amc,
        "scheme": scheme,
        "month": month.capitalize(),
        "year": year,
        "period": f"{month.capitalize()} {year}",
        "display_name": f"{amc} - {scheme} ({month.capitalize()} {year})"
    }

def find_header_row(df_raw: pd.DataFrame) -> int:
    for i, row in df_raw.iterrows():
        row_str = " ".join([str(val).lower() for val in row.values if pd.notna(val)])
        if "isin" in row_str:
            return i
    return 0

def is_valid_equity_isin(isin: str) -> bool:
    if not isin or len(isin) != 12:
        return False
    # Strictly match INE + 9 alphanumeric characters + 1 check digit
    return bool(re.match(r'^INE[A-Z0-9]{9}[0-9]$', str(isin).strip().upper()))

def load_and_normalize(uploaded_file):
    try:
        if uploaded_file.name.endswith('.csv'):
            preview = pd.read_csv(uploaded_file, nrows=35, header=None)
            header_idx = find_header_row(preview)
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, skiprows=header_idx)
        else:
            preview = pd.read_excel(uploaded_file, nrows=35, header=None)
            header_idx = find_header_row(preview)
            uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file, skiprows=header_idx)
        
        df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
        df = df.rename(columns=BLUEPRINT["mapping"])

        if 'Weight (%)' not in df.columns:
            for col in df.columns:
                if '%' in col or 'assets' in col.lower() or 'nav' in col.lower():
                    df = df.rename(columns={col: 'Weight (%)'})
                    break

        if 'ISIN' not in df.columns or 'Stock Name' not in df.columns:
            st.error(f"❌ '{uploaded_file.name}' is missing ISIN or Stock Name headers.")
            return None

        # Filter strictly for Indian Equities
        df['ISIN'] = df['ISIN'].fillna('').astype(str).str.strip().str.upper()
        df = df[df['ISIN'].apply(is_valid_equity_isin)].copy()

        df['Sector'] = df['Sector'].fillna('Unclassified').astype(str).str.strip() if 'Sector' in df.columns else 'Unclassified'
        df['Weight (%)'] = pd.to_numeric(
            df['Weight (%)'].astype(str).str.replace(r'[^0-9.]', '', regex=True),
            errors='coerce'
        ).fillna(0.0)

        df['Stock Name'] = df['Stock Name'].astype(str).str.strip()
        cols_to_keep = ['Stock Name', 'Weight (%)', 'Sector', 'ISIN']
        df = df[cols_to_keep].dropna(subset=['Stock Name']).reset_index(drop=True)
        
        return df.groupby(['ISIN', 'Stock Name', 'Sector'], as_index=False)['Weight (%)'].sum()
    except Exception as e:
        st.error(f"Error parsing {uploaded_file.name}: {e}")
        return None
