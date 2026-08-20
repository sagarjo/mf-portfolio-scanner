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
        'ISIN Code': 'ISIN', 'ISIN': 'ISIN', 'Isin': 'ISIN', 'Security ISIN': 'ISIN',
        'Quantity': 'Quantity', 'Qty': 'Quantity', 'No. of Shares': 'Quantity', 'Shares': 'Quantity',
        'Market/Fair Value(Rs. in Lakhs)': 'Market Value (Lakhs)',
        'Market value(Rs. in Lakhs)': 'Market Value (Lakhs)',
        'Market Value (Rs. in Lakhs)': 'Market Value (Lakhs)',
        'Market/Fair Value (Rs. in Lakhs)': 'Market Value (Lakhs)',
        'Market Value (Rs. in Lakh)': 'Market Value (Lakhs)',
        'Market Value (Lakhs)': 'Market Value (Lakhs)',
        'Market/Fair Value': 'Market Value (Lakhs)'
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
    Validates strictly for: AMC_SchemeName_Month_Year_Other
    Example: Navi_NiftyNext50_June_2026_abc.xlsx
    """
    try:
        # Strip trailing extension variants and sheet suffixes
        clean_name = filename
        clean_name = re.sub(r'\.(xlsx|xls|csv)(\s*-\s*[A-Za-z0-9_]+)?\.(csv|xlsx|xls)$', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'\.(xlsx|xls|csv)$', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'\s*-\s*(Sheet\d+|SC|JBFLEXI).*$', '', clean_name, flags=re.IGNORECASE)

        # Split by underscore
        tokens = [t.strip() for t in clean_name.split('_') if t.strip()]

        # Must have at least 5 segments: AMC, SchemeName, Month, Year, Other
        if len(tokens) < 5:
            return None

        amc = tokens[0]
        other = tokens[-1]
        year = tokens[-2]
        month_raw = tokens[-3].lower()

        # Validate Year (4 digits) and Month
        if not (year.isdigit() and len(year) == 4):
            return None

        if month_raw not in VALID_MONTHS:
            return None

        month = VALID_MONTHS[month_raw]

        # Scheme name is all tokens between AMC and Month
        scheme_tokens = tokens[1:-3]
        scheme = "_".join(scheme_tokens) if scheme_tokens else "DefaultScheme"

        return {
            "amc": str(amc),
            "scheme": str(scheme),
            "month": str(month),
            "year": str(year),
            "other": str(other),
            "period": f"{month} {year}",
            "display_name": f"{amc} - {scheme} ({month} {year}) [{other}]"
        }
    except Exception:
        return None

parse_filename_metadata = validate_and_parse_filename

def find_header_row(df_raw: pd.DataFrame) -> int:
    for i, row in df_raw.iterrows():
        row_str = " ".join([str(val).lower() for val in row.values if pd.notna(val)])
        if "isin" in row_str:
            return i
    return 0

def is_valid_equity_isin(isin: str) -> bool:
    if not isin or len(isin) != 12:
        return False
    return bool(re.match(r'^INE[A-Z0-9]{9}[0-9]$', str(isin).strip().upper()))

def read_df_with_fallback(file_bytes, is_csv=True):
    if not is_csv:
        preview = pd.read_excel(io.BytesIO(file_bytes), nrows=40, header=None)
        h_idx = find_header_row(preview)
        return pd.read_excel(io.BytesIO(file_bytes), skiprows=h_idx)

    for enc in ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']:
        try:
            preview = pd.read_csv(io.BytesIO(file_bytes), nrows=40, header=None, encoding=enc)
            h_idx = find_header_row(preview)
            return pd.read_csv(io.BytesIO(file_bytes), skiprows=h_idx, encoding=enc)
        except Exception:
            continue
    return None

def load_and_normalize(uploaded_file):
    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)

        is_csv = uploaded_file.name.lower().endswith('.csv')
        df = read_df_with_fallback(file_bytes, is_csv=is_csv)

        if df is None:
            st.error(f"❌ '{uploaded_file.name}': Unable to decode file format.")
            return None

        # Clean column headers
        df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
        df = df.rename(columns=BLUEPRINT["mapping"])

        # Fallback for Weight column
        if 'Weight (%)' not in df.columns:
            for col in df.columns:
                c_low = col.lower()
                if '%' in col or 'assets' in c_low or 'nav' in c_low or 'aum' in c_low:
                    df = df.rename(columns={col: 'Weight (%)'})
                    break

        if 'ISIN' not in df.columns or 'Stock Name' not in df.columns:
            st.error(f"❌ '{uploaded_file.name}': Missing 'ISIN' or 'Stock Name' columns.")
            return None

        # Filter strictly for Indian Equities (INE...)
        df['ISIN'] = df['ISIN'].fillna('').astype(str).str.strip().str.upper()
        df = df[df['ISIN'].apply(is_valid_equity_isin)].copy()

        if df.empty:
            st.error(f"❌ '{uploaded_file.name}': No valid equity ISINs (`INE...`) found.")
            return None

        df['Stock Name'] = df['Stock Name'].astype(str).str.strip()
        df['Sector'] = df['Sector'].fillna('Unclassified').astype(str).str.strip() if 'Sector' in df.columns else 'Unclassified'

        # Clean numerical weights
        df['Weight (%)'] = pd.to_numeric(
            df['Weight (%)'].astype(str).str.replace(r'[^0-9.]', '', regex=True),
            errors='coerce'
        ).fillna(0.0)

        # Clean Market Value
        if 'Market Value (Lakhs)' in df.columns:
            df['Market Value (Lakhs)'] = pd.to_numeric(
                df['Market Value (Lakhs)'].astype(str).str.replace(r'[^0-9.]', '', regex=True),
                errors='coerce'
            ).fillna(0.0)
        else:
            df['Market Value (Lakhs)'] = 0.0

        # Clean Quantity
        if 'Quantity' in df.columns:
            df['Quantity'] = pd.to_numeric(
                df['Quantity'].astype(str).str.replace(r'[^0-9]', '', regex=True),
                errors='coerce'
            ).fillna(0).astype(int)
        else:
            df['Quantity'] = 0

        cols_to_keep = ['ISIN', 'Stock Name', 'Sector', 'Weight (%)', 'Market Value (Lakhs)', 'Quantity']
        df = df[cols_to_keep].dropna(subset=['Stock Name']).reset_index(drop=True)

        agg_map = {
            'Weight (%)': 'sum',
            'Market Value (Lakhs)': 'sum',
            'Quantity': 'sum'
        }
        return df.groupby(['ISIN', 'Stock Name', 'Sector'], as_index=False).agg(agg_map)
    except Exception as e:
        st.error(f"Error parsing {uploaded_file.name}: {e}")
        return None
