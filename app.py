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
    .metric-card { background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 5px solid #ff4b4b; }
    .plus-box { background-color: #d4edda; padding: 15px; border-radius: 5px; border-left: 5px solid #28a745; margin-bottom: 10px; }
    .minus-box { background-color: #f8d7da; padding: 15px; border-radius: 5px; border-left: 5px solid #dc3545; margin-bottom: 10px; }
    </style>
    """, unsafe_content_label=True)

# Helper function to clean numeric values from Excel strings
def clean_val(val):
    try:
        if pd.isna(val) or val == "-": return 0.0
        return float(str(val).replace('%', '').replace(',', '.').strip())
    except:
        return 0.0

# --- SIDEBAR ---
st.sidebar.header("Tournament Configuration")
uploaded_file = st.sidebar.file_uploader("Upload Survey XLSX", type="xlsx")

new_tourn_name = st.sidebar.text_input("New Tournament Name", value="OKT85")
new_tourn_region = st.sidebar.selectbox("New Tournament Region", ["DE", "CZ"])

if uploaded_file:
    # Load Sheets
    df_gen = pd.read_excel(uploaded_file, sheet_name="TICKETING GENERAL")
    df_vip = pd.read_excel(uploaded_file, sheet_name="TICKETING VIP")

    # Mapping logic
    mapping = HISTORICAL_MAPPING.copy()
    mapping[new_tourn_name] = new_tourn_region

    # Identify Tournament Columns (Starting from Column D/Index 3 until "AVERAGE")
    columns = list(df_gen.columns)
    tourn_cols = []
    for col in columns[3:]:
        if "AVERAGE" in str(col).upper():
            break
        tourn_cols.append(col)

    # --- TOURNAMENT SELECTION ---
    selected_tour = st.sidebar.selectbox("Select Tournament for Detailed Report", tourn_cols, index=len(tourn_cols)-1)
    focus_region = mapping.get(selected_tour, "CZ")

    # --- DATA EXTRACTION LOGIC (Based on user-provided row references) ---
    # Note: Excel Row 53 is Pandas Index 51 (assuming header is Row 1)
    
    # 1. Overall Satisfaction (General Row B53)
    sat_row_idx = 51 
    
    # 2. Catering (General Row B35, VIP Row B28)
    cat_gen_idx = 33
    cat_vip_idx = 26 

    # 3. KPIs: Look for all rows labeled "Rating" in Column C
    rating_rows = df_gen[df_gen.iloc[:, 2] == "Rating"].index.tolist()
    
    # --- CALCULATIONS ---
    def get_regional_avg(df, row_idx, region_name):
        vals = [clean_val(df.iloc[row_idx, columns.index(c)]) for c in tourn_cols if mapping.get(c) == region_name]
        return sum(vals)/len(vals) if vals else 0

    cz_avg_sat = get_regional_avg(df_gen, sat_row_idx, "CZ")
    de_avg_sat = get_regional_avg(df_gen, sat_row_idx, "DE")
    current_sat = clean_val(df_gen.iloc[sat_row_idx, columns.index(selected_tour)])
    
    # --- OUTPUT 1: BULLETPOINT REPORT ---
    st.title(f"📊 Report: {selected_tour}")
    
    with st.expander("📝 Copy-Paste Presentation Bullets", expanded=True):
        market_avg = cz_avg_sat if focus_region == "CZ" else de_avg_sat
        diff = ((current_sat - market_avg) / market_avg) * 100 if market_avg != 0 else 0
        
        # KPI Analysis logic
        kpi_results = []
        for idx in rating_rows:
            if idx == sat_row_idx: continue
            q_name = df_gen.iloc[idx, 1]
            score = clean_val(df_gen.iloc[idx, columns.index(selected_tour)])
            reg_avg = get_regional_avg(df_gen, idx, focus_region)
            kpi_results.append({'name': q_name, 'score': score, 'avg': reg_avg, 'diff': score - reg_avg})
        
        # Sort to find best 2
        top_kpis = sorted(kpi_results, key=lambda x: x['score'], reverse=True)[:2]

        report_text = f"""
        **1. Overall Tournament Score**
        • {selected_tour} Scored {current_sat:.2f}. 
        • Comparison: This is {abs(diff):.1f}% {'above' if diff > 0 else 'below'} the {focus_region} market average ({market_avg:.2f}).

        **2. Key Performance Indicators (KPIs)**
        • {top_kpis[0]['name']}: {selected_tour} ({top_kpis[0]['score']:.2f}) vs {focus_region} Avg ({top_kpis[0]['avg']:.2f}).
        • {top_kpis[1]['name']}: {selected_tour} ({top_kpis[1]['score']:.2f}) vs {focus_region} Avg ({top_kpis[1]['avg']:.2f}).

        **3. Catering Analysis**
        • General Catering: {clean_val(df_gen.iloc[cat_gen_idx, columns.index(selected_tour)]):.2f} ★
        • VIP Catering: {clean_val(df_vip.iloc[cat_vip_idx, columns.index(selected_tour)]):.2f} ★
        • Insight: VIP catering is performing {clean_val(df_vip.iloc[cat_vip_idx, columns.index(selected_tour)]) - clean_val(df_gen.iloc[cat_gen_idx, columns.index(selected_tour)]):.2f} points higher than General.
        """
        st.code(report_text, language=None)

    st.divider()

    # --- OUTPUT 2: GRAPHICS ---
    
    # ROW 1: Overall Satisfaction
    st.header("1. Overall Tournament Score")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric(label=f"{selected_tour} Score", value=f"{current_sat:.2f} / 5", delta=f"{diff:.1f}% vs {focus_region} Avg")
    with col2:
        # Comparison Graph
        hist_data = pd.DataFrame({
            'Tournament': [selected_tour, f'{focus_region} Average', 'Other Region Avg'],
            'Score': [current_sat, market_avg, de_avg_sat if focus_region == "CZ" else cz_avg_sat]
        })
        fig_sat = px.bar(hist_data, x='Tournament', y='Score', color='Tournament', text_auto=True, height=300)
        st.plotly_chart(fig_sat, use_container_width=True)

    # ROW 2: KPIs
    st.header("2. Key Performance Indicators")
    k1, k2 = st.columns(2)
    for i, col in enumerate([k1, k2]):
        with col:
            st.markdown(f"""<div class='metric-card'>
                <h4>🏆 {top_kpis[i]['name']}</h4>
                <h2 style='color:#ff4b4b;'>{top_kpis[i]['score']:.2f}</h2>
                <p>Regional Avg: {top_kpis[i]['avg']:.2f}</p>
                </div>""", unsafe_allow_html=True)

    # ROW 3: FeedBack (Plus/Minus)
    st.header("3. Feedback Summary (General)")
    pos_idx = 58 # Excel B59
    neg_idx = 68 # Excel B69
    
    c_plus, c_minus = st.columns(2)
    with c_plus:
        st.subheader("(+) Positives")
        # Extract next 5 rows of answers
        for i in range(1, 6):
            ans = df_gen.iloc[pos_idx + i, 2]
            val = df_gen.iloc[pos_idx + i, columns.index(selected_tour)]
            if pd.notna(ans) and clean_val(val) > 0:
                st.markdown(f"<div class='plus-box'><b>{val}%</b> - {ans}</div>", unsafe_allow_html=True)

    with c_minus:
        st.subheader("(-) Negatives")
        for i in range(1, 6):
            ans = df_gen.iloc[neg_idx + i, 2]
            val = df_gen.iloc[neg_idx + i, columns.index(selected_tour)]
            if pd.notna(ans) and clean_val(val) > 0:
                st.markdown(f"<div class='minus-box'><b>{val}%</b> - {ans}</div>", unsafe_allow_html=True)

    # ROW 4: Catering
    st.header("4. Catering Analysis")
    cat_g = clean_val(df_gen.iloc[cat_gen_idx, columns.index(selected_tour)])
    cat_v = clean_val(df_vip.iloc[cat_vip_idx, columns.index(selected_tour)])
    
    fig_cat = go.Figure(data=[
        go.Bar(name='General', x=[selected_tour], y=[cat_g], marker_color='#333'),
        go.Bar(name='VIP', x=[selected_tour], y=[cat_v], marker_color='#ff4b4b'),
        go.Bar(name=f'{focus_region} Gen Avg', x=[selected_tour], y=[get_regional_avg(df_gen, cat_gen_idx, focus_region)], marker_color='#999')
    ])
    fig_cat.update_layout(barmode='group', height=400)
    st.plotly_chart(fig_cat, use_container_width=True)

else:
    st.warning("Please upload the tournament survey file to generate the report.")
