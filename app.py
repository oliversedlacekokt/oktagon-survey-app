import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from groq import Groq

# 1. SETTINGS & API KEY
# The API key is read from Streamlit secrets / environment first so it is not
# hard-coded in the repository. The literal below is kept only as a fallback so
# the existing deployment keeps working. IMPORTANT: this key is public in the git
# history -> rotate it in the Groq console and store the new one in
# Streamlit "Secrets" (key: GROQ_API_KEY).
GROQ_API_KEY = (
    st.secrets.get("GROQ_API_KEY", "")
    or os.environ.get("GROQ_API_KEY", "")
    or "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"
)

# Default region classification for historical tournaments. This is only the
# starting point now - the user can override every tournament in the sidebar.
HISTORICAL_MAPPING = {
    "OKT72": "CZ", "OKT73": "DE", "OKT74": "CZ", "OKT75": "DE",
    "OKT76": "DE", "OKT77": "CZ", "OKT78": "DE", "OKT79": "CZ",
    "OKT80": "DE", "OKT81": "CZ", "OKT82": "DE", "OKT83": "DE",
    "OKT84": "CZ", "OKT85": "DE", "OKT86": "CZ", "OKT87": "CZ"
}

REGION_OPTIONS = ["CZ", "DE"]  # CZ = CZ/SK market, DE = German market

OKT_YELLOW = "#FFCC00"
OKT_BLACK = "#000000"
OKT_WHITE = "#FFFFFF"

st.set_page_config(page_title="OKTAGON Pro Analyst", layout="wide")

# PROFESSIONAL CSS (INTER FONT, CLEANER WEIGHTS)
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');

    .stApp {{ background-color: {OKT_BLACK}; color: {OKT_WHITE}; font-family: 'Inter', sans-serif; }}
    h1, h2, h3 {{ color: {OKT_WHITE} !important; font-weight: 600 !important; }}
    p, span, label, div {{ color: {OKT_WHITE} !important; font-weight: 400 !important; }}

    .stMetric {{ background-color: #111; padding: 15px; border-radius: 10px; border: 1px solid {OKT_YELLOW}; }}
    .plus-box {{ background-color: #28a745; color: white !important; padding: 12px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #1e7e34; font-size: 14px; }}
    .minus-box {{ background-color: #dc3545; color: white !important; padding: 12px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #a71d2a; font-size: 14px; }}
    .kpi-card {{ background-color: #111; padding: 20px; border-radius: 12px; border-top: 3px solid {OKT_YELLOW}; margin-bottom: 15px; }}
    .source-tag {{ font-size: 10px; color: {OKT_YELLOW}; font-weight: 600; text-transform: uppercase; border: 1px solid {OKT_YELLOW}; padding: 2px 5px; border-radius: 4px; margin-right: 5px; }}
    .report-container {{ background-color: #0c0c0c; padding: 30px; border: 1px solid #333; border-radius: 10px; line-height: 1.7; color: #efefef !important; font-size: 15px; }}
    .stSelectbox label {{ color: {OKT_YELLOW} !important; font-weight: 600 !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- UTILITIES ---
def clean_val(val):
    try:
        if pd.isna(val) or val == "-" or val == "–": return 0.0
        clean = str(val).replace('%', '').replace(',', '.').replace('★', '').strip()
        return float(clean)
    except: return 0.0

def get_avg(df, row_idx, region_name, tourn_cols, mapping):
    vals = [clean_val(df.iloc[row_idx, df.columns.get_loc(c)]) for c in tourn_cols if mapping.get(c) == region_name]
    vals = [v for v in vals if v > 0]
    return sum(vals)/len(vals) if vals else 0

@st.cache_data(show_spinner=False)
def load_sheets(file):
    """Read both worksheets once and cache them so re-runs are instant."""
    df_gen = pd.read_excel(file, sheet_name="TICKETING GENERAL")
    df_vip = pd.read_excel(file, sheet_name="TICKETING VIP")
    return df_gen, df_vip

# --- DATA PROCESSING ---
uploaded_file = st.sidebar.file_uploader("Upload Tournament Spreadsheet", type="xlsx")

if uploaded_file:
    df_gen, df_vip = load_sheets(uploaded_file)

    # Detect Columns
    all_cols = list(df_gen.columns)
    avg_index = next((i for i, col in enumerate(all_cols) if "AVERAGE" in str(col).upper()), len(all_cols))
    tourn_cols = [c for c in all_cols[3:avg_index] if "OKT" in str(c) and "Responses" not in str(c)]

    # --- EDITABLE REGION MAPPING (CZ/SK vs DE) ---
    # Every detected tournament can be re-classified here. Defaults come from
    # HISTORICAL_MAPPING; anything unknown (e.g. the newest event) defaults to CZ.
    st.sidebar.subheader("🗺️ Tournament Region Mapping")
    st.sidebar.caption("CZ = CZ/SK market • DE = German market")
    region_df = pd.DataFrame({
        "Tournament": tourn_cols,
        "Region": [HISTORICAL_MAPPING.get(c, "CZ") for c in tourn_cols],
    })
    edited_regions = st.sidebar.data_editor(
        region_df,
        column_config={
            "Tournament": st.column_config.TextColumn("Tournament", disabled=True),
            "Region": st.column_config.SelectboxColumn("Region", options=REGION_OPTIONS, required=True),
        },
        hide_index=True,
        use_container_width=True,
        key="region_editor",
    )
    mapping = dict(zip(edited_regions["Tournament"], edited_regions["Region"]))

    # --- RESPONDENT COUNTS ---
    st.sidebar.subheader("👥 Respondent Counts")
    resp_general = st.sidebar.number_input("Respondents GENERAL", min_value=0, value=0, step=1)
    resp_vip = st.sidebar.number_input("Respondents VIP", min_value=0, value=0, step=1)

    # Sidebar Selection
    selected_tour = st.sidebar.selectbox("🎯 Focus Tournament", tourn_cols, index=len(tourn_cols)-1)
    focus_region = mapping.get(selected_tour, "CZ")

    # Mapping Ratings from both sheets
    rating_rows_gen = df_gen[df_gen.iloc[:, 2].str.contains("Rating", na=False, case=False)].index.tolist()
    rating_rows_vip = df_vip[df_vip.iloc[:, 2].str.contains("Rating", na=False, case=False)].index.tolist()

    all_measurable_kpis = []

    # Extract General Ratings
    for idx in rating_rows_gen:
        name = df_gen.iloc[idx, 1]
        all_measurable_kpis.append({'name': name, 'idx': idx, 'source': 'GENERAL', 'df': 'gen'})

    # Extract VIP Ratings
    for idx in rating_rows_vip:
        name = df_vip.iloc[idx, 1]
        all_measurable_kpis.append({'name': name, 'idx': idx, 'source': 'VIP', 'df': 'vip'})

    # Calculate Deviations for all
    processed_kpis = []
    for k in all_measurable_kpis:
        df_target = df_gen if k['df'] == 'gen' else df_vip
        score = clean_val(df_target.iloc[k['idx'], df_target.columns.get_loc(selected_tour)])
        avg_cz = get_avg(df_target, k['idx'], "CZ", tourn_cols, mapping)
        avg_de = get_avg(df_target, k['idx'], "DE", tourn_cols, mapping)
        market_avg = avg_cz if focus_region == "CZ" else avg_de

        if score > 0:
            processed_kpis.append({
                'name': k['name'], 'source': k['source'], 'score': score,
                'avg_cz': avg_cz, 'avg_de': avg_de, 'market_avg': market_avg,
                'dev': abs(score - market_avg), 'idx': k['idx'], 'df_type': k['df']
            })

    # Fast lookup by display label so we don't rescan the list repeatedly
    kpi_by_label = {f"[{k['source']}] {k['name']}": k for k in processed_kpis}

    # --- 1. OVERALL SCORE & KPI PICKER ---
    st.title(f"🥊 {selected_tour} Executive Report")

    # Respondent overview
    m1, m2 = st.columns(2)
    m1.metric("Respondents GENERAL", f"{resp_general:,}")
    m2.metric("Respondents VIP", f"{resp_vip:,}")

    # Custom Selection for "Featured KPIs"
    st.subheader("Select KPIs to include in AI Analysis & Benchmarks")
    sorted_devs = sorted(processed_kpis, key=lambda x: x['dev'], reverse=True)
    kpi_options = [f"[{k['source']}] {k['name']}" for k in sorted_devs]
    selected_kpi_names = st.multiselect("Pick indicators (Recommended: top deviators selected by default)", kpi_options, default=kpi_options[:3])

    final_selected_kpis = [kpi_by_label[label] for label in selected_kpi_names]

    # --- 2. GROQ AI REPORT ---
    if final_selected_kpis:
        try:
            client = Groq(api_key=GROQ_API_KEY)

            # Prepare data for AI
            row_pos, row_neg = 58, 68
            pos_data = df_gen.iloc[row_pos+1:row_pos+7, [2, df_gen.columns.get_loc(selected_tour)]].values.tolist()
            neg_data = df_gen.iloc[row_neg+1:row_neg+7, [2, df_gen.columns.get_loc(selected_tour)]].values.tolist()

            # Extract current sat for AI
            sat_row_idx = 51
            cur_sat = clean_val(df_gen.iloc[sat_row_idx, df_gen.columns.get_loc(selected_tour)])
            cz_sat_avg = get_avg(df_gen, sat_row_idx, "CZ", tourn_cols, mapping)
            de_sat_avg = get_avg(df_gen, sat_row_idx, "DE", tourn_cols, mapping)

            prompt = f"""
            You are an OKTAGON MMA Market Researcher. Analyze {selected_tour} ({focus_region}).

            Sample size: GENERAL respondents = {resp_general}, VIP respondents = {resp_vip}.

            Overall Sat: {cur_sat} (CZ Avg: {cz_sat_avg:.2f}, DE Avg: {de_sat_avg:.2f})

            KPI DATA (Source labeled):
            {[{'name': k['name'], 'source': k['source'], 'score': k['score'], 'cz_avg': k['avg_cz'], 'de_avg': k['avg_de']} for k in final_selected_kpis]}

            Feedback: Positives {pos_data}, Negatives {neg_data}

            INSTRUCTIONS:
            - Provide detailed market insights.
            - For EVERY KPI listed, explicitly mention the CZ and DE market averages to provide context.
            - Compare General vs VIP performance where applicable.
            - Take the sample sizes into account when judging how reliable the findings are.
            - Professional MMA industry tone.
            """

            with st.spinner("Groq AI is generating the executive summary..."):
                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile",
                )
                st.markdown(f"<div class='report-container'>{response.choices[0].message.content}</div>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"AI Analysis Error: {e}")

    st.divider()

    # --- 3. INTERACTIVE GRAPHICS SECTION ---
    st.header("📊 Interactive Data Audit")

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Market Comparison Tool")
        selected_graph_kpi = st.selectbox("Select Indicator for Graph 1", kpi_options, index=0)
        k_data = kpi_by_label[selected_graph_kpi]

        fig = go.Figure(data=[
            go.Bar(name='Event', x=[selected_tour], y=[k_data['score']], marker_color=OKT_YELLOW, text=[k_data['score']], textposition='auto'),
            go.Bar(name='CZ Market', x=[selected_tour], y=[k_data['avg_cz']], marker_color='#FFF', text=[f"{k_data['avg_cz']:.2f}"], textposition='auto'),
            go.Bar(name='DE Market', x=[selected_tour], y=[k_data['avg_de']], marker_color='#666', text=[f"{k_data['avg_de']:.2f}"], textposition='auto')
        ])
        fig.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', barmode='group', yaxis_range=[0,5.5])
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Performance Benchmark Tool")
        selected_graph_kpi_2 = st.selectbox("Select Indicator for Graph 2", kpi_options, index=min(1, len(kpi_options)-1))
        k_data_2 = kpi_by_label[selected_graph_kpi_2]

        fig2 = go.Figure(data=[
            go.Bar(name='Score', x=[selected_tour], y=[k_data_2['score']], marker_color=OKT_YELLOW),
            go.Scatter(name='CZ Avg', x=[selected_tour], y=[k_data_2['avg_cz']], mode='markers+lines', marker=dict(color='white', size=15)),
            go.Scatter(name='DE Avg', x=[selected_tour], y=[k_data_2['avg_de']], mode='markers+lines', marker=dict(color='#666', size=15))
        ])
        fig2.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis_range=[0,5.5])
        st.plotly_chart(fig2, use_container_width=True)

    # --- 4. FEATURED KPI CARDS ---
    st.header("🏆 Featured KPI Analysis")
    if final_selected_kpis:
        cols = st.columns(len(final_selected_kpis))
        for i, k in enumerate(final_selected_kpis):
            with cols[i]:
                st.markdown(f"""
                    <div class='kpi-card'>
                        <span class='source-tag'>{k['source']}</span>
                        <p style='color:{OKT_YELLOW}; font-weight:600; margin-top:10px;'>{k['name']}</p>
                        <h1 style='color:white; margin:5px 0;'>{k['score']:.2f}</h1>
                        <p style='color:#777; font-size:12px;'>CZ Market: {k['avg_cz']:.2f}<br>DE Market: {k['avg_de']:.2f}</p>
                    </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Select at least one KPI above to populate the featured cards.")

    # --- 5. FEEDBACK ---
    st.header("📝 Qualitative Feedback (General)")
    f_p, f_m = st.columns(2)
    with f_p:
        st.markdown("<p style='color:#28a745; font-weight:600;'>Positives (+)</p>", unsafe_allow_html=True)
        for i in range(1, 7):
            ans, val = df_gen.iloc[58+i, 2], df_gen.iloc[58+i, df_gen.columns.get_loc(selected_tour)]
            if clean_val(val) > 0: st.markdown(f"<div class='plus-box'><b>{val}%</b> — {ans}</div>", unsafe_allow_html=True)
    with f_m:
        st.markdown("<p style='color:#dc3545; font-weight:600;'>Negatives (-)</p>", unsafe_allow_html=True)
        for i in range(1, 7):
            ans, val = df_gen.iloc[68+i, 2], df_gen.iloc[68+i, df_gen.columns.get_loc(selected_tour)]
            if clean_val(val) > 0: st.markdown(f"<div class='minus-box'><b>{val}%</b> — {ans}</div>", unsafe_allow_html=True)

else:
    st.title("🥊 OKTAGON MMA: Pro AI Analyst")
    st.info("Upload the tournament survey results to generate your executive report.")
