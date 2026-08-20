import streamlit as st

def inject_custom_styles():
    st.markdown("""
        <style>
        .metric-card {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 10px;
            padding: 16px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.04);
        }
        .metric-title {
            font-size: 0.85rem;
            font-weight: 600;
            color: #6c757d;
            text-transform: uppercase;
            margin-bottom: 6px;
        }
        .metric-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: #1f2937;
        }
        .metric-sub {
            font-size: 0.8rem;
            color: #10b981;
            margin-top: 4px;
        }
        </style>
    """, unsafe_allow_html=True)

def render_kpi_card(title: str, value: str, subtext: str = ""):
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">{title}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-sub">{subtext}</div>
        </div>
    """, unsafe_allow_html=True)
