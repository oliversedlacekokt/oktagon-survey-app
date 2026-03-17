import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import google.generativeai as genai

# 1. HISTORICAL DATA
HISTORICAL_MAPPING = {
    "OKT72": "CZ", "OKT73": "DE", "OKT74": "CZ", "OKT75": "DE", 
    "OKT76": "DE", "OKT77": "CZ", "OKT78": "DE", "OKT79": "CZ", 
    "OKT80": "DE", "OKT81": "CZ", "OKT82": "DE", "OKT83": "DE", 
    "OKT84": "CZ"
}

OKT_YELLOW = "#FFCC00"
OKT_BLACK = "#000000"
OKT_WHITE = "#FFFFFF"

st.set_page_config(page_title="OKTAGON AI Insights", layout="wide")

# CSS FOR BLACK & GOLD THEME
st.markdown(f"""
    <style>
    .stApp {{ background-color: {OKT_BLACK}; color: {OKT_WHITE}; }}
    h1, h2, h3, p, span, label, div {{ color: {OKT_WHITE} !important; font-family: 'Arial', sans-serif; }}
    .stMetric {{ background-color: #111; padding: 15px; border-radius: 10px; border: 1px solid {OKT_YELLOW}; }}
    .plus-box {{ background-color: #28a745; color: white !important; padding: 12px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #1e7e34; }}
    .minus-box {{ background-color: #dc3545; color: white !important; padding: 12px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #a71d2a; }}
    .kpi-card {{ background-color: #111; padding: 20px; border-radius: 15px; border-top: 4px solid {OKT_YELLOW}; margin-bottom: 20px; }}
    .report-container {{ background-color: #111; padding: 25px; border: 1px solid {OKT_YELLOW}; border-radius: 10px; line-height: 1.6; }}
    </style>
    """, unsafe_allow_html=True)

def clean_val(val):
    try:
        if pd.isna(val) or val == "-" or val == "–": return 0.0
        clean = str(val).replace('%', '').replace(',', '.').replace('★', '').strip()
        return float(clean)
    except: return 0.0

def get_regional_avg(df, row_idx, region_name, tourn_cols, mapping):
    vals = [clean_val(df.iloc[row_idx, df.columns.get_loc(c)]) for c in tourn_cols if mapping.get(c) == region_name]
    vals = [v for v in vals if v > 0]
    return sum(vals)/len(vals) if vals else 0

# --- SIDEBAR ---
st.sidebar.image("https://oktagonmma.com/wp-content/uploads/2022/07/logo-oktagon-white.png", width=180)
st.sidebar.title("Configuration")
gemini_key = st.sidebar.text_input("Gemini API Key", type="password")

# Model Discovery Logic
available_model = None
if gemini_key:
    try:
        genai.configure(api_key=gemini_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Preference order
        for target in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']:
            if target in models:
                available_model = target
                break
        if available_model:
            st.sidebar.success(f"Connected: {available_model.split('/')[-1]}")
    except Exception as e:
        st.sidebar.error("Could not verify API Key")

uploaded_file = st.sidebar.file_uploader("Upload Tournament Spreadsheet", type="xlsx")

if uploaded_file:
    df_gen = pd.read_excel(uploaded_file, sheet_name="TICKETING GENERAL")
    df_vip = pd.read_excel(uploaded_file, sheet_name="TICKETING VIP")

    # Detect newest tournament
    all_cols = list(df_gen.columns)
    avg_index = next((i for i, col in enumerate(all_cols) if "AVERAGE" in str(col).upper()), len(all_cols))
    tourn_cols = [c for c in all_cols[3:avg_index] if "OKT" in str(c) and "Responses" not in str(c)]
    
    newest_tourn = tourn_cols[-1]
    new_tourn_reg = st.sidebar.selectbox(f"Select Region for {newest_tourn}", ["CZ", "DE"])

    mapping = HISTORICAL_MAPPING.copy()
    mapping[newest_tourn] = new_tourn_reg

    selected_tour = st.sidebar.selectbox("🎯 Focus Tournament", tourn_cols, index=len(tourn_cols)-1)
    focus_region = mapping.get(selected_tour, "CZ")

    # Excel Row Indexing
    row_sat, row_cat_g, row_cat_v, row_pos, row_neg = 51, 33, 26, 58, 68

    # Stats
    cz_avg_sat = get_regional_avg(df_gen, row_sat, "CZ", tourn_cols, mapping)
    de_avg_sat = get_regional_avg(df_gen, row_sat, "DE", tourn_cols, mapping)
    current_sat = clean_val(df_gen.iloc[ro
