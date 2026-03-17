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

OKT_YELLOW = "#FFCC00"
OKT_BLACK = "#000000"
OKT_WHITE = "#FFFFFF"

st.set_page_config(page_title="OKTAGON AI Insights", layout="wide")

# CSS FOR OKTAGON BRANDING (LIGHTER FONTS)
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    .stApp {{ 
        background-color: {OKT_BLACK}; 
        color: {OKT_WHITE}; 
        font-family: 'Inter', sans-serif;
    }}
    
    /* Headers - Less bold than before */
    h1, h2, h3 {{ 
        color: {OKT_WHITE} !important; 
        font-weight: 600 !important; 
        letter-spacing: -0.5px;
    }}
    
    p, span, label, div {{ 
        color: {OKT_WHITE} !important; 
        font-weight: 400 !important; 
    }}
    
    .stMetric {{ 
        background-color: #111; 
        padding: 15px; 
        border-radius: 10px; 
        border: 1px solid {OKT_YELLOW}; 
    }}
    
    .plus-box {{ 
        background-color: #28a745; 
        color: white !important; 
        padding: 10px; 
        border-radius: 6px; 
        margin-bottom: 8px; 
        font-size: 14px;
    }}
    
    .minus-box {{ 
        background-color: #dc3545; 
        color: white !important; 
        padding: 10px; 
        border-radius: 6px; 
        margin-bottom: 8px; 
        font-size: 14px;
    }}
    
    .kpi-card {{ 
        background-color: #111; 
        padding: 20px; 
        border-radius: 12px; 
        border-top: 3px solid {OKT_YELLOW}; 
        margin-bottom: 20px;
    }}
    
    .report-container {{ 
        background-color: #0c0c0c; 
        padding: 25px; 
        border: 1px solid {OKT_YELLOW}; 
        border-radius: 8px; 
        line-height: 1.6; 
        color: #ddd !important;
        font-size: 15px;
    }}
    
    .stSelectbox label, .stTextInput label {{ 
        color: {OKT_YELLOW} !important; 
        font-weight: 600 !important;
    }}
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
st.sidebar.image("https://oktagonmma.com/wp-content/uploads/2022/07/logo-oktagon-white.png", width=160)
st.sidebar.title("Configuration")
gemini_key = st.sidebar.text_input("Gemini API Key", type="password")

# Fixed model names to avoid 404
model_choice = st.sidebar.selectbox("AI Version", ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0-pro"])

uploaded_file = st.sidebar.file_uploader("Upload Tournament Spreadsheet", type="xlsx")

if uploaded_file:
    df_gen = pd.read_excel(uploaded_file, sheet_name="TICKETING GENERAL")
    df_vip = pd.read_excel(uploaded_file, sheet_name="TICKETING VIP")

    all_cols = list(df_gen.columns)
    avg_index = next((i for i, col in enumerate(all_cols) if "AVERAGE" in str(col).upper()), len(all_cols))
    tourn_cols = [c for c in all_cols[3:avg_index] if "OKT" in str(c) and "Responses" not in str(c)]
    
    newest_tourn = tourn_cols[-1]
    new_tourn_reg = st.sidebar.selectbox(f"Region for {newest_tourn}", ["CZ", "DE"])
    mapping = HISTORICAL_MAPPING.copy()
    mapping[newest_tourn] = new_tourn_reg

    selected_tour = st.sidebar.selectbox("🎯 Focus Tournament", tourn_cols, index=len(tourn_cols)-1)
    focus_region = mapping.get(selected_tour, "CZ")

    # Data Coordinates
    row_sat, row_cat_g, row_cat_v, row_pos, row_neg = 51, 33, 26, 58, 68
    cz_avg_sat = get_regional_avg(df_gen, row_sat, "CZ", tourn_cols, mapping)
    de_avg_sat = get_regional_avg(df_gen, row_sat, "DE", tourn_cols, mapping)
    current_sat = clean_val(df_gen.iloc[row_sat, df_gen.columns.get_loc(selected_tour)])

    # KPI Selection (Logic: Highest Deviation from Region Avg)
    rating_rows = df_gen[df_gen.iloc[:, 2].str.contains("Rating", na=False, case=False)].index.tolist()
    kpis = []
    for idx in rating_rows:
        if idx == row_sat: continue
        score = clean_val(df_gen.iloc[idx, df_gen.columns.get_loc(selected_tour)])
        reg_avg = get_regional_avg(df_gen, idx, focus_region, tourn_cols, mapping)
        if score > 0:
            kpis.append({'name': df_gen.iloc[idx, 1], 'score': score, 'avg_cz': get_regional_avg(df_gen, idx, "CZ", tourn_cols, mapping), 'avg_de': get_regional_avg(df_gen, idx, "DE", tourn_cols, mapping), 'dev': abs(score - reg_avg)})
    top_kpis = sorted(kpis, key=lambda x: x['dev'], reverse=True)[:2]

    # --- 3. AI PRESENTATION BULLETS ---
    st.header(f"🥊 Market Insights: {selected_tour}")

    if gemini_key:
        try:
            genai.configure(api_key=gemini_key)
            # IMPORTANT: Using standard model name without 'models/' prefix inside GenerativeModel
            model = genai.GenerativeModel(model_name=model_choice)
            
            pos_data = df_gen.iloc[row_pos+1:row_pos+7, [2, df_gen.columns.get_loc(selected_tour)]].values.tolist()
            neg_data = df_gen.iloc[row_neg+1:row_neg+7, [2, df_gen.columns.get_loc(selected_tour)]].values.tolist()
            
            prompt = f"""
            You are an OKTAGON MMA business analyst. Generate a complex presentation report for {selected_tour} ({focus_region}).
            
            - Overall Score: {current_sat:.2f} (CZ Avg: {cz_avg_sat:.2f}, DE Avg: {de_avg_sat:.2f})
            - Key Deviations: {top_kpis[0]['name']} at {top_kpis[0]['score']}, {top_kpis[1]['name']} at {top_kpis[1]['score']}
            - Positives: {pos_data}
            - Negatives: {neg_data}
            - Catering: Gen {clean_val(df_gen.iloc[row_cat_g, df_gen.columns.get_loc(selected_tour)])}, VIP {clean_val(df_vip.iloc[row_cat_v, df_vip.columns.get_loc(selected_tour)])}
            
            Requirements:
            1. Title: OKTAGON Market Insight: CZ vs. DE Performance
            2. Detailed section for Key Performance Indicators (KPIs).
            3. Feedback Summary (+/-) using the percentage data.
            4. Catering Comparison (General vs VIP) with market insight.
            Use professional language. Do not use bold for everything.
            """
            with st.spinner(f"Analyzing via {model_choice}..."):
                response = model.generate_content(prompt)
                st.markdown(f"<div class='report-container'>{response.text}</div>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"AI Connection Error: {e}")
            st.info("Ensure your API key is correct and you have set up a project in Google AI Studio.")

    st.divider()

    # --- 4. GRAPHICS (CLEANER FONTS) ---
    st.header("🏆 Performance Benchmarks")
    k1, k2 = st.columns(2)
    for i, k_col in enumerate([k1, k2]):
        with k_col:
            st.markdown(f"""
                <div class='kpi-card'>
                    <p style='color:{OKT_YELLOW}; font-weight:600; margin:0;'>{top_kpis[i]['name']}</p>
                    <h1 style='color:white; margin:10px 0;'>{top_kpis[i]['score']:.2f}</h1>
                    <p style='color:#888; font-size:13px;'>CZ Market: {top_kpis[i]['avg_cz']:.2f} | DE Market: {top_kpis[i]['avg_de']:.2f}</p>
                </div>
            """, unsafe_allow_html=True)

    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Satisfaction: Market Context")
        fig_m = go.Figure(data=[
            go.Bar(name='This Event', x=[selected_tour], y=[current_sat], marker_color=OKT_YELLOW),
            go.Bar(name='CZ Average', x=[selected_tour], y=[cz_avg_sat], marker_color='#FFF'),
            go.Bar(name='DE Average', x=[selected_tour], y=[de_avg_sat], marker_color='#555')
        ])
        fig_m.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', barmode='group', font=dict(family="Inter"))
        st.plotly_chart(fig_m, use_container_width=True)

    with g2:
        st.subheader("Catering Result Comparison")
        cg = clean_val(df_gen.iloc[row_cat_g, df_gen.columns.get_loc(selected_tour)])
        cv = clean_val(df_vip.iloc[row_cat_v, df_vip.columns.get_loc(selected_tour)])
        fig_c = go.Figure(data=[
            go.Bar(name='General', x=['Catering'], y=[cg], marker_color=OKT_YELLOW, text=[cg], textposition='auto'),
            go.Bar(name='VIP', x=['Catering'], y=[cv], marker_color='#FFF', text=[cv], textposition='auto')
        ])
        fig_c.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis_range=[0,5], font=dict(family="Inter"))
        st.plotly_chart(fig_c, use_container_width=True)

    st.header("📝 Qualitative Feedback Summary")
    f_p, f_m = st.columns(2)
    with f_p:
        st.markdown(f"<p style='color:#28a745; font-weight:600;'>Positives (+)</p>", unsafe_allow_html=True)
        for i in range(1, 7):
            ans, val = df_gen.iloc[row_pos+i, 2], df_gen.iloc[row_pos+i, df_gen.columns.get_loc(selected_tour)]
            if clean_val(val) > 0: st.markdown(f"<div class='plus-box'><b>{val}%</b> — {ans}</div>", unsafe_allow_html=True)
    with f_m:
        st.markdown(f"<p style='color:#dc3545; font-weight:600;'>Negatives (-)</p>", unsafe_allow_html=True)
        for i in range(1, 7):
            ans, val = df_gen.iloc[row_neg+i, 2], df_gen.iloc[row_neg+i, df_gen.columns.get_loc(selected_tour)]
            if clean_val(val) > 0: st.markdown(f"<div class='minus-box'><b>{val}%</b> — {ans}</div>", unsafe_allow_html=True)

else:
    st.title("🥊 OKTAGON MMA AI Analyst")
    st.info("Upload the survey results .xlsx file in the sidebar to begin.")
