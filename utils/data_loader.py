import re
import io
import pandas as pd
import streamlit as st

BLUEPRINT = {
    "required_cols": ['Stock Name', 'Weight (%)', 'Sector', 'ISIN'],
    "mapping": {
        'Name of the Instrument': 'Stock Name', 'Company Name': 'Stock Name',
        'Issuer': 'Stock Name', 'Security': 'Stock Name', 'Instrument Name': 'Stock Name',
        'Name of Instrument': 'Stock Name', 'Security Name': 'Stock Name',
        'Industry Classification': 'Sector', 'Industry/Rating': 'Sector', 'Industry': 'Sector',
        '% to Net Assets': 'Weight (%)', 'Weightage': 'Weight (%)', '% of Total AUM': 'Weight (%)',
        '% to NAV': 'Weight (%)', '% of Net Assets': 'Weight (%)', '% to AUM': 'Weight (%)',
        'Market value / Net Assets (%)': 'Weight (%)', '% to Total Net Assets': 'Weight (%)',
        'ISIN Code': 'ISIN', 'ISIN': 'ISIN', 'Isin': 'ISIN', 'Security ISIN': 'ISIN'
    }
}

VALID_MONTHS = {
    'jan': 'January', 'january': 'January', 'feb': 'February', 'february': 'February',
    'mar': 'March', 'march': 'March', 'apr': 'April', 'april': 'April',
    'may': 'May', 'jun': 'June', 'june': 'June', 'jul': 'July', 'july': 'July',
    'aug': 'August', 'august': 'August', 'sep': 'September', 'september': 'September',
    'oct': 'October', 'october': 'October', 'nov': 'November', 'november': 'November',
    'dec': 'December', 'december': 'December'
}

def validate_and_parse_filename(filename: str):
    """
    Robustly parses filename format: AMC-SchemeName-Month-Year
    Handles:
    - Scheme names with multiple hyphens (e.g. Canara-Robeco-Small-Cap-Fund)
    - En-dashes (–), Em-dashes (—), underscores (_)
    - Export suffixes like '.xlsx - Sheet1.csv' or '.xlsx - SC.csv'
    """
    # 1. Clean out export suffixes and extensions
    clean_name = filename
    clean_name = re.sub(r'\.(xlsx|xls|csv)(\s*-\s*[A-Za-z0-9_]+)?\.(csv|xlsx|xls)$', '', clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r'\.(xlsx|xls|csv)$', '', clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r'\s*-\s*(Sheet\d+|SC|JBFLEXI)$', '', clean_name, flags=re.IGNORECASE)

    # 2. Normalize all dash variants to a single standard hyphen
    clean_name = clean_name.replace('–', '-').replace('—', '-').replace('_', '-')
    # Collapse multiple consecutive hyphens or spaces around hyphens
    clean_name = re.sub(r'\s*-\s*', '-', clean_name).strip('-')

    tokens = [t.strip() for t in clean_name.split('-') if t.strip()]

    if len(tokens) < 3:
        return None

    # AMC is the first token
    amc = tokens[0]

    # Look for Year and Month at the end of the tokens
    year = None
    month = None
    year_idx = None
    month_idx = None

    # Scan from the right side for Year (4-digit)
    for idx in range(len(tokens) - 1, 0, -1):
        if re.match(r'^\d{4}$', tokens[idx]):
            year = tokens[idx]
            year_idx = idx
            break

    # Scan for Month immediately before or near the Year
    if year_idx is not None:
        for idx in range(year_idx - 1, 0, -1):
            cleaned_m = tokens[idx].lower()
            if cleaned_m in VALID_MONTHS:
                month = VALID_MONTHS[cleaned_m]
                month_idx = idx
                break

    # If Year or Month couldn't be located at the end
    if not year or not month or month_idx is None:
        return None

    # Everything between AMC and Month is the Scheme Name
    scheme_tokens = tokens[1:month_idx]
    if not scheme_tokens:
        return None

    scheme = " ".join(scheme_tokens)

    return {
        "amc": amc,
        "scheme": scheme,
        "month": month,
        "year": year,
        "period": f"{month} {year}",
        "display_name": f"{amc} - {scheme} ({month} {year})"
    }

parse_filename_metadata = validate_and_parse_filename

def find_header_row(df_raw: pd.DataFrame) -> int:
    """Scans rows for the header row containing 'isin'."""
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
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)

        # Check if CSV or Excel
        if uploaded_file.name.lower().endswith('.csv'):
            preview = pd.read_csv(io.BytesIO(file_bytes), nrows=40, header=None)
            header_idx = find_header_row(preview)
            df = pd.read_csv(io.BytesIO(file_bytes), skiprows=header_idx)
        else:
            preview = pd.read_excel(io.BytesIO(file_bytes), nrows=40, header=None)
            header_idx = find_header_row(preview)
            df = pd.read_excel(io.BytesIO(file_bytes), skiprows=header_idx)

        # Standardize column headers
        df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
        df = df.rename(columns=BLUEPRINT["mapping"])

        # Fallback search for Weight column if mapping missed it
        if 'Weight (%)' not in df.columns:
            for col in df.columns:
                c_low = col.lower()
                if '%' in col or 'assets' in c_low or 'nav' in c_low or 'aum' in c_low:
                    df = df.rename(columns={col: 'Weight (%)'})
                    break

        if 'ISIN' not in df.columns or 'Stock Name' not in df.columns:
            st.error(f"❌ '{uploaded_file.name}': Could not detect 'ISIN' or 'Stock Name' columns.")
            return None

        # Clean ISIN values and filter strictly for valid Indian Equity ISINs (INE...)
        df['ISIN'] = df['ISIN'].fillna('').astype(str).str.strip().str.upper()
        df = df[df['ISIN'].apply(is_valid_equity_isin)].copy()

        if df.empty:
            st.error(f"❌ '{uploaded_file.name}': No valid equity ISINs (`INE...`) found.")
            return None

        # Clean Sector
        df['Sector'] = df['Sector'].fillna('Unclassified').astype(str).str.strip() if 'Sector' in df.columns else 'Unclassified'

        # Clean Weights
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
