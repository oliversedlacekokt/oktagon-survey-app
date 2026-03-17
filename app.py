import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import google.generativeai as genai

# 1. HARDCODED HISTORICAL DATA
HISTORICAL_MAPPING = {
    "OKT72": "CZ", "OKT73": "DE", "OKT74": "CZ", "OKT75": "DE", 
    "OKT76": "DE", "OKT77": "CZ", "OKT78": "DE", "OKT79": "CZ", 
    "OKT80": "DE", "OKT81": "CZ", "OKT82": "DE", "OKT83": "DE", 
    "OKT84": "CZ"
}

# OKTAGON BRAND COLORS
OKT_YELLOW = "#FFCC00"
OKT_BLACK = "#000000"
OKT_WHITE = "#FFFFFF"

st.set_page_config(page_title="OKTAGON Gemini Insights", layout="wide")

# CUSTOM CSS FOR OKTAGON BRANDING
st.markdown(f"""
    <style>
    .stApp {{ background-color: {OKT_BLACK}; color: {OKT_WHITE}; }}
    h1, h2, h3, p, span, label {{ color: {OKT_WHITE} !important; font-family: 'Arial Black', sans-serif; }}
    .stMetric {{ background-color: #1a1a1a; padding: 15px; border-radius: 10px; border: 1px solid {OKT_YELLOW}; }}
    .stSelectbox label, .stTextInput label {{ color: {OKT_YELLOW} !important; }}
    .plus-box {{ background-color: #28a745; color: white; padding: 12px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #1e7e34; }}
    .minus-box {{ background-color: #dc3545; color: white; padding: 12px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #a71d2a; }}
    .kpi-card {{ background-color: #1a1a1a; padding: 20px; border-radius: 15px; border-top: 4px solid {OKT_YELLOW}; margin-bottom: 20px; min-height: 180px; }}
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
st.sidebar.title("Gemini Configuration")
gemini_key = st.sidebar.text_input("Gemini API Key", type="password")
uploaded_file = st.sidebar.file_uploader("Upload Tournament Spreadsheet", type="xlsx")

if uploaded_file:
    # Read sheets
    df_gen = pd.read_excel(uploaded_file, sheet_name="TICKETING GENERAL")
    df_vip = pd.read_excel(uploaded_file, sheet_name="TICKETING VIP")

    # 1. AUTOMATIC TOURNAMENT DISCOVERY
    all_cols = list(df_gen.columns)
    # Find where AVERAGE column starts
    avg_index = next((i for i, col in enumerate(all_cols) if "AVERAGE" in str(col).upper()), len(all_cols))
    # Extract OKT columns between Row C (idx 2) and Average
    tourn_cols = [c for c in all_cols[3:avg_index] if "OKT" in str(c) and "Responses" not in str(c)]
    
    newest_tournament = tourn_cols[-1]
    st.sidebar.markdown(f"**Newest Detected:** {newest_tournament}")
    new_tourn_reg = st.sidebar.selectbox(f"Region for {newest_tournament}", ["CZ", "DE"])

    # Update Mapping
    mapping = HISTORICAL_MAPPING.copy()
    mapping[newest_tournament] = new_tourn_reg

    # Focus selection
    selected_tour = st.sidebar.selectbox("🎯 Tournament for Detailed Report", tourn_cols, index=len(tourn_cols)-1)
    focus_region = mapping.get(selected_tour, "CZ")

    # Row Indices (Excel Row 53 = Index 51, etc.)
    row_sat = 51   
    row_cat_g = 33 
    row_cat_v = 26 
    row_pos = 58   
    row_neg = 68   

    # Stats for Overall Sat
    cz_avg_sat = get_regional_avg(df_gen, row_sat, "CZ", tourn_cols, mapping)
    de_avg_sat = get_regional_avg(df_gen, row_sat, "DE", tourn_cols, mapping)
    current_sat = clean_val(df_gen.iloc[row_sat, df_gen.columns.get_loc(selected_tour)])

    # 2. KPI SELECTION (Highest Deviation Logic)
    rating_rows = df_gen[df_gen.iloc[:, 2].str.contains("Rating", na=False, case=False)].index.tolist()
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
    
    # Pick top 2 most interesting (highest deviation from market average)
    top_kpis = sorted(kpi_candidates, key=lambda x: x['deviation'], reverse=True)[:2]

    # --- 3. GEMINI AI REPORT ---
    st.header(f"🥊 OKTAGON Insights: {selected_tour}")

    if gemini_key:
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Prepare Positives/Negatives for AI
            pos_list = df_gen.iloc[row_pos+1:row_pos+6, [2, df_gen.columns.get_loc(selected_tour)]].values.tolist()
            neg_list = df_gen.iloc[row_neg+1:row_neg+6, [2, df_gen.columns.get_loc(selected_tour)]].values.tolist()
            
            prompt = f"""
            You are an elite sports business analyst for OKTAGON MMA. 
            Generate a detailed presentation report for {selected_tour} ({focus_region}).

            DATA SUMMARY:
            - Overall Sat: {current_sat:.2f} (CZ Market Avg: {cz_avg_sat:.2f}, DE Market Avg: {de_avg_sat:.2f})
            - KPI 1: {top_kpis[0]['name']} at {top_kpis[0]['score']:.2f} vs {focus_region} Avg {top_kpis[0]['avg_cz'] if focus_region=='CZ' else top_kpis[0]['avg_de']:.2f}
            - KPI 2: {top_kpis[1]['name']} at {top_kpis[1]['score']:.2f} vs {focus_region} Avg {top_kpis[1]['avg_cz'] if focus_region=='CZ' else top_kpis[1]['avg_de']:.2f}
            - Catering: General {clean_val(df_gen.iloc[row_cat_g, df_gen.columns.get_loc(selected_tour)])}, VIP {clean_val(df_vip.iloc[row_cat_v, df_vip.columns.get_loc(selected_tour)])}
            - Positive Feedback: {pos_list}
            - Negative Feedback: {neg_list}

            STRUCTURE REQUIREMENTS:
            1. OKTAGON Market Insight: CZ vs. DE Performance (Including satisfaction averages).
            2. Key Performance Indicators (KPIs): Compare the top 2 indicators to regional benchmarks.
            3. {selected_tour} Feedback Summary (+/-): Detailed breakdown of logistics, atmosphere, and production.
            4. Catering Result Comparison: Breakdown of the General vs VIP gap with specific market context.

            TONE: Professional, aggressive, data-heavy.
            """
            
            with st.spinner("Gemini is analyzing market data..."):
                response = model.generate_content(prompt)
                st.markdown(f"<div style='background-color:#111; padding:20px; border:1px solid {OKT_YELLOW}; border-radius:10px; font-family:sans-serif;'>{response.text}</div>", unsafe_allow_html=True)
        
        except Exception as e:
            st.error(f"Gemini Error: {e}")
    else:
        st.warning("Enter Gemini API Key in sidebar to see AI Analysis.")

    st.divider()

    # --- 4. GRAPHICS (OKTAGON STYLE) ---
    st.header("🏆 Performance Benchmarks")
    k1, k2 = st.columns(2)
    for i, k_col in enumerate([k1, k2]):
        with k_col:
            st.markdown(f"""
                <div class='kpi-card'>
                    <h3 style='color:{OKT_YELLOW}; margin:0;'>{top_kpis[i]['name']}</h3>
                    <h1 style='color:white; font-size: 55px; margin:10px 0;'>{top_kpis[i]['score']:.2f}</h1>
                    <p style='color:#bbb;'>CZ Avg: {top_kpis[i]['avg_cz']:.2f} | DE Avg: {top_kpis[i]['avg_de']:.2f}</p>
                </div>
            """, unsafe_allow_html=True)

    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Market Comparison: Overall Score")
        fig_m = go.Figure(data=[
            go.Bar(name='Selected Event', x=[selected_tour], y=[current_sat], marker_color=OKT_YELLOW, text=[f"{current_sat:.2f}"], textposition='auto'),
            go.Bar(name='CZ Average', x=[selected_tour], y=[cz_avg_sat], marker_color='#FFFFFF'),
            go.Bar(name='DE Average', x=[selected_tour], y=[de_avg_sat], marker_color='#666666')
        ])
        fig_m.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', barmode='group')
        st.plotly_chart(fig_m, use_container_width=True)

    with g2:
        st.subheader("Catering Result Comparison")
        c_g = clean_val(df_gen.iloc[row_cat_g, df_gen.columns.get_loc(selected_tour)])
        c_v = clean_val(df_vip.iloc[row_cat_v, df_vip.columns.get_loc(selected_tour)])
        fig_c = go.Figure(data=[
            go.Bar(name='General', x=['Catering'], y=[c_g], marker_color=OKT_YELLOW, text=[f"{c_g:.2f}"], textposition='auto'),
            go.Bar(name='VIP', x=['Catering'], y=[c_v], marker_color=OKT_WHITE, text=[f"{c_v:.2f}"], textposition='auto')
        ])
        fig_c.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis_range=[0,5])
        st.plotly_chart(fig_c, use_container_width=True)

    # FEEDBACK BLOCKS
    st.header("📝 Fan Feedback Summary")
    f_p, f_m = st.columns(2)
    with f_p:
        st.markdown(f"<h3 style='color:#28a745'>Positives (+)</h3>", unsafe_allow_html=True)
        for i in range(1, 6):
            ans = df_gen.iloc[row_pos+i, 2]
            val = df_gen.iloc[row_pos+i, df_gen.columns.get_loc(selected_tour)]
            if clean_val(val) > 0:
                st.markdown(f"<div class='plus-box'><b>{val}%</b> — {ans}</div>", unsafe_allow_html=True)
    
    with f_m:
        st.markdown(f"<h3 style='color:#dc3545'>Negatives (-)</h3>", unsafe_allow_html=True)
        for i in range(1, 6):
            ans = df_gen.iloc[row_neg+i, 2]
            val = df_gen.iloc[row_neg+i, df_gen.columns.get_loc(selected_tour)]
            if clean_val(val) > 0:
                st.markdown(f"<div class='minus-box'><b>{val}%</b> — {ans}</div>", unsafe_allow_html=True)

else:
    st.title("🥊 OKTAGON MMA: Survey Analyst (Gemini)")
    st.info("Upload the tournament .xlsx file in the sidebar to begin.")
