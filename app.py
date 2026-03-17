import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# 1. SETUP & HISTORICAL DATA
HISTORICAL_MAPPING = {
    "OKT72": "CZ", "OKT73": "DE", "OKT74": "CZ", "OKT75": "DE", 
    "OKT76": "DE", "OKT77": "CZ", "OKT78": "DE", "OKT79": "CZ", 
    "OKT80": "DE", "OKT81": "CZ", "OKT82": "DE", "OKT83": "DE", 
    "OKT84": "CZ"
}

st.set_page_config(page_title="OKTAGON Reports", layout="wide")

# Custom CSS for nice graphics
st.markdown("""
    <style>
    .metric-card { 
        background-color: #f8f9fa; 
        padding: 20px; 
        border-radius: 10px; 
        border-left: 5px solid #ff4b4b; 
        box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
    }
    .plus-box { 
        background-color: #d4edda; 
        padding: 10px; 
        border-radius: 5px; 
        border-left: 5px solid #28a745; 
        margin-bottom: 8px;
        font-size: 14px;
    }
    .minus-box { 
        background-color: #f8d7da; 
        padding: 10px; 
        border-radius: 5px; 
        border-left: 5px solid #dc3545; 
        margin-bottom: 8px;
        font-size: 14px;
    }
    </style>
    """, unsafe_allow_html=True)

# Helper function to clean numeric values from Excel strings
def clean_val(val):
    try:
        if pd.isna(val) or val == "-" or val == "–": return 0.0
        # Handle cases like "4.3★" or "83%"
        clean = str(val).replace('%', '').replace(',', '.').replace('★', '').strip()
        return float(clean)
    except:
        return 0.0

# --- SIDEBAR ---
st.sidebar.header("Tournament Configuration")
uploaded_file = st.sidebar.file_uploader("Upload Survey XLSX", type="xlsx")

new_tourn_name = st.sidebar.text_input("New Tournament Name", value="OKT85")
new_tourn_region = st.sidebar.selectbox("New Tournament Region", ["DE", "CZ"])

if uploaded_file:
    # Load Sheets
    # header=0 means the first row (Section/Question/Answer) is the header
    df_gen = pd.read_excel(uploaded_file, sheet_name="TICKETING GENERAL")
    df_vip = pd.read_excel(uploaded_file, sheet_name="TICKETING VIP")

    # Mapping logic
    mapping = HISTORICAL_MAPPING.copy()
    mapping[new_tourn_name] = new_tourn_region

    # Identify Tournament Columns (Looking for OKT columns)
    columns = list(df_gen.columns)
    tourn_cols = []
    for col in columns:
        if "OKT" in str(col) and "Responses" not in str(col):
            tourn_cols.append(col)

    # --- TOURNAMENT SELECTION ---
    selected_tour = st.sidebar.selectbox("Select Tournament for Detailed Report", tourn_cols, index=len(tourn_cols)-1)
    focus_region = mapping.get(selected_tour, "CZ")

    # --- DATA EXTRACTION LOGIC ---
    # Rows are 0-indexed. Excel B53 = Row 52 in Python (if first row is header)
    sat_row_idx = 51   # Row 53 in Excel (Overall Experience)
    cat_gen_idx = 33  # Row 35 in Excel (Catering Gen)
    cat_vip_idx = 26  # Row 28 in Excel (Catering VIP)
    pos_idx = 58      # Row 60 in Excel (Positives)
    neg_idx = 68      # Row 70 in Excel (Negatives)

    # All rows that have "Rating" in the 3rd column
    rating_rows = df_gen[df_gen.iloc[:, 2].str.contains("Rating", na=False)].index.tolist()
    
    # --- CALCULATIONS ---
    def get_regional_avg(df, row_idx, region_name):
        vals = []
        for c in tourn_cols:
            if mapping.get(c) == region_name:
                v = clean_val(df.iloc[row_idx, columns.index(c)])
                if v > 0: vals.append(v)
        return sum(vals)/len(vals) if vals else 0

    cz_avg_sat = get_regional_avg(df_gen, sat_row_idx, "CZ")
    de_avg_sat = get_regional_avg(df_gen, sat_row_idx, "DE")
    current_sat = clean_val(df_gen.iloc[sat_row_idx, columns.index(selected_tour)])
    
    # --- OUTPUT 1: BULLETPOINT REPORT ---
    st.title(f"🥊 OKTAGON Insights: {selected_tour}")
    
    with st.expander("📝 Click to copy Presentation Bullets", expanded=True):
        market_avg = cz_avg_sat if focus_region == "CZ" else de_avg_sat
        diff = ((current_sat - market_avg) / market_avg) * 100 if market_avg != 0 else 0
        
        # KPI Selection Logic
        kpi_results = []
        for idx in rating_rows:
            if idx == sat_row_idx: continue
            q_name = df_gen.iloc[idx, 1]
            score = clean_val(df_gen.iloc[idx, columns.index(selected_tour)])
            reg_avg = get_regional_avg(df_gen, idx, focus_region)
            if score > 0:
                kpi_results.append({'name': q_name, 'score': score, 'avg': reg_avg, 'diff': score - reg_avg})
        
        top_kpis = sorted(kpi_results, key=lambda x: x['score'], reverse=True)[:2]

        report_text = f"""
1. Overall Tournament Score
• {selected_tour} Scored {current_sat:.2f} / 5.0. 
• Comparison: This is {abs(diff):.1f}% {'above' if diff > 0 else 'below'} the {focus_region} market average ({market_avg:.2f}).

2. Key Performance Indicators (KPIs)
• {top_kpis[0]['name']}: {selected_tour} ({top_kpis[0]['score']:.2f}) vs {focus_region} Avg ({top_kpis[0]['avg']:.2f}).
• {top_kpis[1]['name']}: {selected_tour} ({top_kpis[1]['score']:.2f}) vs {focus_region} Avg ({top_kpis[1]['avg']:.2f}).

3. Catering Analysis
• General Catering: {clean_val(df_gen.iloc[cat_gen_idx, columns.index(selected_tour)]):.2f} ★
• VIP Catering: {clean_val(df_vip.iloc[cat_vip_idx, columns.index(selected_tour)]):.2f} ★
• VIP vs General Delta: {clean_val(df_vip.iloc[cat_vip_idx, columns.index(selected_tour)]) - clean_val(df_gen.iloc[cat_gen_idx, columns.index(selected_tour)]):.2f} points.
        """
        st.code(report_text, language=None)

    st.divider()

    # --- OUTPUT 2: GRAPHICS ---
    
    # ROW 1: Overall Satisfaction
    st.header("1. Overall Tournament Score")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric(label=f"{selected_tour} Rating", value=f"{current_sat:.2f}", delta=f"{diff:.1f}% vs {focus_region} Market")
    with col2:
        hist_data = pd.DataFrame({
            'Category': [selected_tour, f'{focus_region} Market Avg', 'Other Region Avg'],
            'Rating': [current_sat, market_avg, de_avg_sat if focus_region == "CZ" else cz_avg_sat]
        })
        fig_sat = px.bar(hist_data, x='Category', y='Rating', color='Category', 
                         color_discrete_sequence=['#ff4b4b', '#333', '#999'], text_auto='.2f', height=350)
        st.plotly_chart(fig_sat, use_container_width=True)

    # ROW 2: KPIs
    st.header("2. Key Performance Indicators")
    k1, k2 = st.columns(2)
    for i, k_col in enumerate([k1, k2]):
        if i < len(top_kpis):
            with k_col:
                st.markdown(f"""<div class='metric-card'>
                    <h4 style='margin:0;'>🏆 {top_kpis[i]['name']}</h4>
                    <h1 style='color:#ff4b4b; margin:10px 0;'>{top_kpis[i]['score']:.2f}</h1>
                    <p style='margin:0; color:#666;'>Regional Average: {top_kpis[i]['avg']:.2f}</p>
                    </div>""", unsafe_allow_html=True)

    # ROW 3: Feedback Summary
    st.header("3. Feedback Summary (General Admission)")
    c_plus, c_minus = st.columns(2)
    with c_plus:
        st.subheader("✅ Positives (Top Recall)")
        for i in range(1, 7):
            ans = df_gen.iloc[pos_idx + i, 2]
            val = df_gen.iloc[pos_idx + i, columns.index(selected_tour)]
            if pd.notna(ans) and clean_val(val) > 0:
                st.markdown(f"<div class='plus-box'><b>{val}%</b> - {ans}</div>", unsafe_allow_html=True)

    with c_minus:
        st.subheader("❌ Negatives (Top Pain Points)")
        for i in range(1, 7):
            ans = df_gen.iloc[neg_idx + i, 2]
            val = df_gen.iloc[neg_idx + i, columns.index(selected_tour)]
            if pd.notna(ans) and clean_val(val) > 0:
                st.markdown(f"<div class='minus-box'><b>{val}%</b> - {ans}</div>", unsafe_allow_html=True)

    # ROW 4: Catering Comparison
    st.header("4. Catering Analysis")
    cat_g = clean_val(df_gen.iloc[cat_gen_idx, columns.index(selected_tour)])
    cat_v = clean_val(df_vip.iloc[cat_vip_idx, columns.index(selected_tour)])
    
    fig_cat = go.Figure(data=[
        go.Bar(name='General Catering', x=[selected_tour], y=[cat_g], marker_color='#333', text=[f"{cat_g:.2f}"], textposition='auto'),
        go.Bar(name='VIP Catering', x=[selected_tour], y=[cat_v], marker_color='#ff4b4b', text=[f"{cat_v:.2f}"], textposition='auto'),
        go.Scatter(name='Market Avg', x=[selected_tour], y=[get_regional_avg(df_gen, cat_gen_idx, focus_region)], mode='lines+markers', marker_color='black')
    ])
    fig_cat.update_layout(barmode='group', height=400, yaxis_range=[0,5])
    st.plotly_chart(fig_cat, use_container_width=True)

else:
    st.info("👋 Welcome! Please upload the survey .xlsx file in the sidebar to generate the OKTAGON report.")
