import streamlit as st
import pandas as pd
import plotly.express as px
from utils.ui_components import inject_custom_styles, render_kpi_card

st.set_page_config(page_title="MoM Portfolio Drift", page_icon="📅", layout="wide")
inject_custom_styles()

st.title("📅 Month-on-Month Portfolio Drift")

if 'portfolio_store' not in st.session_state or not st.session_state.portfolio_store:
    st.warning("⚠️ No portfolios loaded. Please upload valid files on the **Home Page (`app.py`)** first.")
    st.stop()

portfolios = st.session_state.portfolio_store
keys = list(portfolios.keys())

c1, c2 = st.columns(2)
curr_key = c1.selectbox("📌 Current / Later Month", keys, index=0, help="Select the latest month disclosure.")
prev_key = c2.selectbox("⏪ Previous / Baseline Month", keys, index=min(1, len(keys)-1), help="Select the baseline comparison month disclosure.")

if curr_key == prev_key:
    st.warning("Please choose two different portfolio periods to compute MoM differences.")
    st.stop()

curr_df = portfolios[curr_key]['data']
prev_df = portfolios[prev_key]['data']

curr_isins = set(curr_df['ISIN'])
prev_isins = set(prev_df['ISIN'])

new_isins = curr_isins - prev_isins
exit_isins = prev_isins - curr_isins

hero_row = curr_df.sort_values(by="Weight (%)", ascending=False).iloc[0] if not curr_df.empty else None
hero_stock_label = f"{hero_row['Stock Name']} ({hero_row['Weight (%)']:.2f}%)" if hero_row is not None else "N/A"

# KPI Square Boards
st.markdown("### 📊 Key Portfolio Snapshot")
k1, k2, k3, k4 = st.columns(4)
with k1:
    render_kpi_card("Total Equities", f"{len(curr_df)}", f"Baseline: {len(prev_df)}")
with k2:
    render_kpi_card("New Entries", f"{len(new_isins)}", "Added this month")
with k3:
    render_kpi_card("Complete Exits", f"{len(exit_isins)}", "Liquidated fully")
with k4:
    render_kpi_card("Hero Stock", hero_stock_label, "Highest single allocation")

st.divider()

# Sector Shift Chart
st.subheader("🧭 Sectoral Allocation Shifts (MoM)")
curr_sec = curr_df.groupby('Sector')['Weight (%)'].sum()
prev_sec = prev_df.groupby('Sector')['Weight (%)'].sum()
sec_drift = (curr_sec - prev_sec).fillna(curr_sec).fillna(-prev_sec).reset_index()
sec_drift.columns = ['Sector', 'Weight Change (%)']
sec_drift = sec_drift.sort_values(by='Weight Change (%)', ascending=True)

fig = px.bar(
    sec_drift, x='Weight Change (%)', y='Sector', orientation='h',
    color='Weight Change (%)', color_continuous_scale='RdYlGn',
    title="Sector Rotation Momentum (MoM Net Weightage Delta)"
)
fig.update_layout(height=400, margin=dict(l=20, r=20, t=40, b=20))
st.plotly_chart(fig, use_container_width=True)

# Holding Tables
st.subheader("📋 Holding Details")
t_new, t_common, t_exit = st.tabs(["🆕 New Entries", "⚖️ Common Holdings (Weight Drift)", "❌ Complete Exits"])

with t_new:
    st.dataframe(curr_df[curr_df['ISIN'].isin(new_isins)][['Stock Name', 'Sector', 'Weight (%)']].sort_values('Weight (%)', ascending=False), hide_index=True, use_container_width=True)

with t_common:
    merged = pd.merge(curr_df[['ISIN', 'Stock Name', 'Sector', 'Weight (%)']], prev_df[['ISIN', 'Weight (%)']], on='ISIN', suffixes=('_Current', '_Previous'))
    merged['Delta (%)'] = (merged['Weight (%)_Current'] - merged['Weight (%)_Previous']).round(2)
    st.dataframe(merged[['Stock Name', 'Sector', 'Weight (%)_Current', 'Weight (%)_Previous', 'Delta (%)']].sort_values('Delta (%)', ascending=False), hide_index=True, use_container_width=True)

with t_exit:
    st.dataframe(prev_df[prev_df['ISIN'].isin(exit_isins)][['Stock Name', 'Sector', 'Weight (%)']].sort_values('Weight (%)', ascending=False), hide_index=True, use_container_width=True)
