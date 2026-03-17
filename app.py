import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from openai import OpenAI

# 1. HARDCODED HISTORICAL DATA
HISTORICAL_MAPPING = {
    "OKT72": "CZ", "OKT73": "DE", "OKT74": "CZ", "OKT75": "DE", 
    "OKT76": "DE", "OKT77": "CZ", "OKT78": "DE", "OKT79": "CZ", 
    "OKT80": "DE", "OKT81": "CZ", "OKT82": "DE", "OKT83": "DE", 
    "OKT84": "CZ"
}

# OKTAGON BRAND COLORS
OKT_YELLOW = "#FFCC00"
OKT_DARK_YELLOW = "#E6B800"
OKT_BLACK = "#000000"
OKT_WHITE = "#FFFFFF"

st.set_page_config(page_title="OKTAGON AI Insights", layout="wide")

# CUSTOM CSS FOR OKTAGON BRANDING
st.markdown(f"""
    <style>
    .stApp {{ background-color: {OKT_BLACK}; color: {OKT_WHITE}; }}
    h1, h2, h3, p, span, label {{ color: {OKT_WHITE} !important; font-family: 'Arial Black', sans-serif; }}
    .stMetric {{ background-color: #1a1a1a; padding: 15px; border-radius: 10px; border: 1px solid {OKT_YELLOW}; }}
    .stSelectbox label, .stTextInput label {{ color: {OKT_YELLOW} !important; }}
    .plus-box {{ background-color: #28a745; color: white; padding: 12px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #1e7e34; }}
    .minus-box {{ background-color: #dc3545; color: white; padding: 12px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #a71d2a; }}
    .kpi-card {{ background-color: #1a1a1a; padding: 20px; border-radius: 15px; border-top: 4px solid {OKT_YELLOW}; margin-bottom: 20px; }}
    </style>
    """, unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
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
st.sidebar.image("https://oktagonmma.com/wp-content/uploads/2022/07/logo-oktagon-white.png", width=200)
st.sidebar.title("Configuration")
api_key = st.sidebar.text_input("OpenAI API Key", type="password", help="Needed for the AI Presentation Bullets")
uploaded_file = st.sidebar.file_uploader("Upload Tournament Spreadsheet", type="xlsx")

if uploaded_file:
    df_gen = pd.read_excel(uploaded_file, sheet_name="TICKETING GENERAL")
    df_vip = pd.read_excel(uploaded_file, sheet_name="TICKETING VIP")

    # 1. AUTOMATIC NEW TOURNAMENT DISCOVERY
    # Find the column before "AVERAGE"
    all_cols = list(df_gen.columns)
    avg_index = next((i for i, col in enumerate(all_cols) if "AVERAGE" in str(col).upper()), len(all_cols))
    
    # Tournament columns are between Question (idx 1) and Average
    tourn_cols = [c for c in all_cols[3:avg_index] if "OKT" in str(c) and "Responses" not in str(c)]
    newest_tournament = tourn_cols[-1]
    
    st.sidebar.success(f"Detected Newest: {newest_tournament}")
    new_tourn_reg = st.sidebar.selectbox(f"Select Region for {newest_tournament}", ["CZ", "DE"])

    # Update Mapping
    mapping = HISTORICAL_MAPPING.copy()
    mapping[newest_tournament] = new_tourn_reg

    # Select Tournament for Detailed Focus
    selected_tour = st.sidebar.selectbox("🎯 Focus Tournament", tourn_cols, index=len(tourn_cols)-1)
    focus_region = mapping.get(selected_tour, "CZ")

    # --- DATA INDEXING (Based on Row References) ---
    # Python is 0-indexed. Row 53 in Excel = index 51.
    row_sat = 51   # Overall Satisfaction
    row_cat_g = 33 # General Catering
    row_cat_v = 26 # VIP Catering
    row_pos = 58   # Positives Header
    row_neg = 68   # Negatives Header

    # Get scores and averages
    cz_avg_sat = get_regional_avg(df_gen, row_sat, "CZ", tourn_cols, mapping)
    de_avg_sat = get_regional_avg(df_gen, row_sat, "DE", tourn_cols, mapping)
    current_sat = clean_val(df_gen.iloc[row_sat, df_gen.columns.get_loc(selected_tour)])

    # 2. KPI SELECTION (Automatic Deviation Logic)
    rating_rows = df_gen[df_gen.iloc[:, 2].str.contains("Rating", na=False)].index.tolist()
    kpi_candidates = []
    for idx in rating_rows:
        if idx == row_sat: continue
        score = clean_val(df_gen.iloc[idx, df_gen.columns.get_loc(selected_tour)])
        reg_avg = get_regional_avg(df_gen, idx, focus_region, tourn_cols, mapping)
        if score > 0:
            kpi_candidates.append({
                'name': df_gen.iloc[idx, 1],
                'score': score,
                'avg_cz': get_regional_avg(df_gen, idx, "CZ", tourn_cols, mapping),
                'avg_de': get_regional_avg(df_gen, idx, "DE", tourn_cols, mapping),
                'deviation': abs(score - reg_avg)
            })
    
    # Pick Top 2 based on highest deviation (the most "interesting" results)
    top_kpis = sorted(kpi_candidates, key=lambda x: x['deviation'], reverse=True)[:2]

    # --- AI ANALYSIS SECTION ---
    if api_key:
        client = OpenAI(api_key=api_key)
        
        # Prepare Data for AI
        ai_data = {
            "tournament": selected_tour,
            "region": focus_region,
            "overall_score": current_sat,
            "cz_avg": cz_avg_sat,
            "de_avg": de_avg_sat,
            "kpis": top_kpis,
            "catering_gen": clean_val(df_gen.iloc[row_cat_g, df_gen.columns.get_loc(selected_tour)]),
            "catering_vip": clean_val(df_vip.iloc[row_cat_v, df_vip.columns.get_loc(selected_tour)]),
            "positives": df_gen.iloc[row_pos+1:row_pos+6, [2, df_gen.columns.get_loc(selected_tour)]].values.tolist(),
            "negatives": df_gen.iloc[row_neg+1:row_neg+6, [2, df_gen.columns.get_loc(selected_tour)]].values.tolist()
        }

        with st.spinner("AI is analyzing tournament performance..."):
            prompt = f"""
            Generate a complex, data-driven bullet point presentation report for OKTAGON MMA. 
            Context: {ai_data['tournament']} held in {ai_data['region']}.
            Data:
            - Overall Sat: {ai_data['overall_score']} (CZ Avg: {ai_data['cz_avg']:.2f}, DE Avg: {ai_data['de_avg']:.2f})
            - KPIs: {ai_data['kpis']}
            - Catering: Gen ({ai_data['catering_gen']}), VIP ({ai_data['catering_vip']})
            - Top Positives: {ai_data['positives']}
            - Top Negatives: {ai_data['negatives']}

            Follow the exact structure:
            1. OKTAGON Market Insight: CZ vs. DE Performance
            2. Key Performance Indicators (KPIs) with comparisons.
            3. Written Feedback Summary (+/-) with detailed insights based on percentages.
            4. Catering Result Comparison (General vs. VIP) with market insight.
            
            Keep the tone professional, like a high-level sports executive report.
            """
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            ai_report = response.choices[0].message.content
            st.markdown(f"<div style='background-color:#111; padding:20px; border:1px solid {OKT_YELLOW}; border-radius:10px;'>{ai_report}</div>", unsafe_allow_html=True)
    else:
        st.warning("Please enter your OpenAI API Key in the sidebar to generate the AI Presentation Bullets.")

    st.divider()

    # --- 4. VISUALIZATIONS (OKTAGON STYLE) ---
    
    # KPI SECTION
    st.header("🏆 Performance Indicators")
    k1, k2 = st.columns(2)
    for i, k_col in enumerate([k1, k2]):
        with k_col:
            st.markdown(f"""
                <div class='kpi-card'>
                    <h3 style='color:{OKT_YELLOW}'>{top_kpis[i]['name']}</h3>
                    <h1 style='color:white; font-size: 50px;'>{top_kpis[i]['score']:.2f}</h1>
                    <p>CZ Market: {top_kpis[i]['avg_cz']:.2f} | DE Market: {top_kpis[i]['avg_de']:.2f}</p>
                </div>
            """, unsafe_allow_html=True)

    # CHARTS
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Market Comparison: Overall Score")
        fig_market = go.Figure(data=[
            go.Bar(name='Current Tournament', x=[selected_tour], y=[current_sat], marker_color=OKT_YELLOW),
            go.Bar(name='CZ Average', x=[selected_tour], y=[cz_avg_sat], marker_color='#FFFFFF'),
            go.Bar(name='DE Average', x=[selected_tour], y=[de_avg_sat], marker_color='#555555')
        ])
        fig_market.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', barmode='group')
        st.plotly_chart(fig_market, use_container_width=True)

    with c2:
        st.subheader("Catering Satisfaction Tiering")
        cat_g = clean_val(df_gen.iloc[row_cat_g, df_gen.columns.get_loc(selected_tour)])
        cat_v = clean_val(df_vip.iloc[row_cat_v, df_vip.columns.get_loc(selected_tour)])
        fig_cat = go.Figure(data=[
            go.Bar(name='General', x=['Catering'], y=[cat_g], marker_color=OKT_YELLOW),
            go.Bar(name='VIP', x=['Catering'], y=[cat_v], marker_color=OKT_WHITE)
        ])
        fig_cat.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_cat, use_container_width=True)

    # FEEDBACK BLOCKS
    st.header("📝 Fan Feedback Summary")
    f_p, f_m = st.columns(2)
    with f_p:
        st.markdown(f"<h3 style='color:#28a745'>Positives (+)</h3>", unsafe_allow_html=True)
        for i in range(1, 6):
            ans = df_gen.iloc[row_pos+i, 2]
            val = df_gen.iloc[row_pos+i, df_gen.columns.get_loc(selected_tour)]
            if clean_val(val) > 0:
                st.markdown(f"<div class='plus-box'><b>{val}%</b> - {ans}</div>", unsafe_allow_html=True)
    
    with f_m:
        st.markdown(f"<h3 style='color:#dc3545'>Negatives (-)</h3>", unsafe_allow_html=True)
        for i in range(1, 6):
            ans = df_gen.iloc[row_neg+i, 2]
            val = df_gen.iloc[row_neg+i, df_gen.columns.get_loc(selected_tour)]
            if clean_val(val) > 0:
                st.markdown(f"<div class='minus-box'><b>{val}%</b> - {ans}</div>", unsafe_allow_html=True)

else:
    st.title("🥊 OKTAGON MMA: AI Survey Analyst")
    st.info("Upload the Excel file to generate the market insight report.")
