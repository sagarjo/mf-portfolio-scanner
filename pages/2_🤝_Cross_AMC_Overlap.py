import streamlit as st
import pandas as pd
import plotly.express as px
from utils.ui_components import inject_custom_styles, render_kpi_card

st.set_page_config(page_title="Cross-AMC Overlap", page_icon="🤝", layout="wide")
inject_custom_styles()

st.title("🤝 Cross-AMC Overlap & Momentum")

if 'portfolio_store' not in st.session_state or not st.session_state.portfolio_store:
    st.warning("⚠️ No portfolios loaded. Please upload valid files on the **Home Page (`app.py`)** first.")
    st.stop()

portfolios = st.session_state.portfolio_store
keys = list(portfolios.keys())

if len(keys) < 2:
    st.info("ℹ️ Please upload at least 2 valid portfolios on the Home Page to perform comparison analysis.")
    st.stop()

combined_list = []
for name, pdata in portfolios.items():
    temp = pdata['data'].copy()
    temp['Portfolio'] = name
    combined_list.append(temp)
combined_df = pd.concat(combined_list, ignore_index=True)

# Overlap Matrix
matrix = pd.DataFrame(index=keys, columns=keys)
for f1 in keys:
    for f2 in keys:
        s1 = set(portfolios[f1]['data']['ISIN'])
        s2 = set(portfolios[f2]['data']['ISIN'])
        overlap = (len(s1 & s2) / len(s1 | s2)) * 100 if (s1 | s2) else 0.0
        matrix.loc[f1, f2] = round(overlap, 1)

conviction = combined_df.groupby(['ISIN', 'Stock Name', 'Sector']).agg(
    AMC_Count=('Portfolio', 'nunique'),
    Avg_Weight=('Weight (%)', 'mean'),
    Total_Weight=('Weight (%)', 'sum')
).reset_index().sort_values(by=['AMC_Count', 'Total_Weight'], ascending=[False, False])

top_stock = conviction.iloc[0]['Stock Name'] if not conviction.empty else "N/A"
top_stock_count = conviction.iloc[0]['AMC_Count'] if not conviction.empty else 0
top_sector = combined_df.groupby('Sector')['Weight (%)'].sum().idxmax()

# KPI Metric Cards
st.markdown("### 📊 Cross-Portfolio Summary")
k1, k2, k3, k4 = st.columns(4)
with k1:
    render_kpi_card("Total Portfolios", str(len(keys)), "Valid files analyzed")
with k2:
    render_kpi_card("Unique Equities", str(combined_df['ISIN'].nunique()), "Across all portfolios")
with k3:
    render_kpi_card("Top Conviction Stock", top_stock, f"In {top_stock_count} portfolios")
with k4:
    render_kpi_card("Dominant Sector", top_sector, "Highest aggregate weight")

st.divider()

# Heatmap
st.subheader("🔥 Overlap Heatmap (% Jaccard Overlap)")
fig_heat = px.imshow(matrix.astype(float), text_auto=True, color_continuous_scale="Blues", title="Holding Intersection Percentage")
fig_heat.update_layout(height=450)
st.plotly_chart(fig_heat, use_container_width=True)

# Shared Conviction
st.divider()
st.subheader("🌟 Shared Conviction Holdings (Held by 2+ AMCs)")
shared = conviction[conviction['AMC_Count'] > 1].copy()
shared['Avg_Weight'] = shared['Avg_Weight'].round(2)
shared['Total_Weight'] = shared['Total_Weight'].round(2)

st.dataframe(
    shared[['Stock Name', 'Sector', 'AMC_Count', 'Avg_Weight', 'Total_Weight']],
    hide_index=True,
    use_container_width=True
)
