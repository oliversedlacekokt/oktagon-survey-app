import os
import re
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from groq import Groq

# 1. SETTINGS & API KEY
def get_setting(name, default=""):
    """Read from Streamlit secrets, then environment. st.secrets raises when no
    secrets.toml exists (typical for local runs), so it is guarded."""
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return value or os.environ.get(name, "") or default


# Store the key in Streamlit "Secrets" (key: GROQ_API_KEY) or in the environment.
# Never commit it - an earlier revision of this file leaked one into the git
# history, so that key must stay rotated.
GROQ_API_KEY = get_setting("GROQ_API_KEY")

# Groq decommissioned llama-3.3-70b-versatile on 2026-06-17, which is why the
# old model id now returns "model_not_found". The candidates are tried in order
# so a future decommission degrades to the next model instead of breaking the
# report. Override the preferred one with the GROQ_MODEL secret.
GROQ_MODEL_CANDIDATES = [
    m for m in [
        get_setting("GROQ_MODEL"),
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
    ] if m
]

# Default region classification per tournament, covering both past events and
# the scheduled ones up to OKT100. This is only the starting point - the user
# can override every tournament in the sidebar.
HISTORICAL_MAPPING = {
    "OKT72": "CZ", "OKT73": "DE", "OKT74": "CZ", "OKT75": "DE",
    "OKT76": "DE", "OKT77": "CZ", "OKT78": "DE", "OKT79": "CZ",
    "OKT80": "DE", "OKT81": "CZ", "OKT82": "DE", "OKT83": "DE",
    "OKT84": "CZ", "OKT85": "DE", "OKT86": "CZ", "OKT87": "CZ",
    # Scheduled events
    "OKT88": "DE", "OKT89": "CZ", "OKT90": "DE", "OKT91": "DE",
    "OKT92": "CZ", "OKT93": "CZ", "OKT94": "DE", "OKT95": "CZ",
    "OKT96": "DE", "OKT97": "DE", "OKT98": "CZ", "OKT99": "DE",
    "OKT100": "CZ",
}

REGION_OPTIONS = ["CZ", "DE"]  # CZ = CZ/SK market, DE = German market

# --- BRAND CONSTANTS (OKTAGON Design Guide V01) ---
# Exact primary palette. The previous revision used #FFCC00 / #000000 / #FFFFFF,
# none of which are the specified values.
OKT_YELLOW = "#FFD100"   # RGB 255,210,0
OKT_BLACK = "#1F1F1F"    # RGB 30,30,30
OKT_LIGHT = "#F0F0F0"    # RGB 240,240,240

# Neutral steps derived from OKTAGON BLACK, used only for surfaces, borders and
# lower-hierarchy text. The guide does not publish a secondary palette, so
# nothing here introduces a new hue - these are shades of the primary black.
OKT_SURFACE = "#262626"
OKT_SURFACE_DEEP = "#171717"
OKT_LINE = "#3A3A3A"
OKT_MUTED = "#8C8C8C"
OKT_GREY = "#6E6E6E"

# Futura Now (headlines) and Bebas Neue Pro (support) are licensed typefaces and
# cannot be pulled from a CDN. The stacks name them first so a self-hosted or
# locally installed copy wins, then fall back to the closest free geometric
# equivalents: Jost for Futura, Bebas Neue for Bebas Neue Pro.
FONT_DISPLAY = "'Futura Now Headline', 'Futura Now', 'FuturaNowHeadline', 'Jost', 'Futura', sans-serif"
FONT_SUPPORT = "'Bebas Neue Pro', 'BebasNeuePro', 'Bebas Neue', 'Jost', sans-serif"

# The symbol: an octagon formed by two intersecting squares, per the symbol
# philosophy (two opponents, two squares, the balance between them). This is a
# geometric stand-in - drop the official SVG in assets/ when available.
OKT_SYMBOL_SVG = f"""
<svg viewBox="0 0 100 100" width="100%" height="100%" aria-hidden="true">
  <rect x="20" y="20" width="60" height="60" fill="none"
        stroke="{OKT_YELLOW}" stroke-width="7"/>
  <rect x="20" y="20" width="60" height="60" fill="none"
        stroke="{OKT_YELLOW}" stroke-width="7" transform="rotate(45 50 50)"/>
</svg>
"""

st.set_page_config(page_title="OKTAGON | Survey Analyst", layout="wide")

# --- BRAND CSS ---
# Geometric, square-cornered, high contrast. Headlines are uppercase Futura with
# kerning -25 (= -0.025em); numbers and technical annotations run in Bebas.
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Jost:ital,wght@0,400;0,500;0,600;0,700;0,800;0,900;1,700;1,800&family=Bebas+Neue&display=swap');

    .stApp {{
        background-color: {OKT_BLACK};
        color: {OKT_LIGHT};
        font-family: {FONT_DISPLAY};
    }}

    /* Headlines: Futura Now Headline XBold, uppercase, kerning -25 */
    h1, h2, h3, h4 {{
        color: {OKT_LIGHT} !important;
        font-family: {FONT_DISPLAY} !important;
        font-weight: 800 !important;
        text-transform: uppercase !important;
        letter-spacing: -0.025em !important;
        line-height: 1.05 !important;
    }}
    h1 {{ font-size: 2.9rem !important; }}
    h2 {{ font-size: 1.55rem !important; }}
    h3 {{ font-size: 1.15rem !important; }}

    /* Section headings carry a yellow rule - the structural grid cue */
    .stApp h2 {{
        border-left: 5px solid {OKT_YELLOW};
        padding-left: 14px;
        margin-top: 2.4rem !important;
        margin-bottom: 1.1rem !important;
    }}

    p, span, label, div, li {{ color: {OKT_LIGHT}; font-weight: 400; }}

    /* Technical annotations / lower hierarchy: Bebas Neue Pro Expanded */
    .okt-tech, [data-testid="stCaptionContainer"] p {{
        font-family: {FONT_SUPPORT} !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
        color: {OKT_MUTED} !important;
        font-size: 0.85rem !important;
    }}

    /* --- BRAND HEADER --- */
    .okt-header {{
        display: flex; align-items: center; gap: 20px;
        padding: 6px 0 22px 0; border-bottom: 1px solid {OKT_LINE}; margin-bottom: 8px;
    }}
    .okt-symbol {{ width: 62px; height: 62px; flex: 0 0 62px; }}
    .okt-wordmark {{
        font-family: {FONT_DISPLAY}; font-weight: 900; font-size: 2.6rem;
        letter-spacing: -0.025em; line-height: 1; color: {OKT_LIGHT};
    }}
    .okt-descriptor {{
        font-family: {FONT_SUPPORT}; font-size: 1rem; letter-spacing: 0.22em;
        text-transform: uppercase; color: {OKT_YELLOW}; margin-top: 4px;
    }}

    /* --- METRICS --- */
    [data-testid="stMetric"] {{
        background-color: {OKT_SURFACE}; padding: 18px 20px; border-radius: 0;
        border-left: 4px solid {OKT_YELLOW};
    }}
    [data-testid="stMetricValue"] {{
        font-family: {FONT_SUPPORT} !important; font-size: 2.6rem !important;
        color: {OKT_LIGHT} !important; letter-spacing: 0.02em;
    }}
    [data-testid="stMetricLabel"] p {{
        font-family: {FONT_SUPPORT} !important; text-transform: uppercase !important;
        letter-spacing: 0.14em !important; color: {OKT_MUTED} !important;
    }}

    /* --- KPI CARDS --- */
    .kpi-card {{
        background-color: {OKT_SURFACE}; padding: 22px; border-radius: 0;
        border-top: 4px solid {OKT_YELLOW}; margin-bottom: 15px; height: 100%;
    }}
    .kpi-name {{
        font-family: {FONT_DISPLAY}; font-weight: 800; text-transform: uppercase;
        letter-spacing: -0.02em; font-size: 1.05rem; color: {OKT_LIGHT};
        margin: 14px 0 6px 0; line-height: 1.15;
    }}
    .kpi-score {{
        font-family: {FONT_SUPPORT}; font-size: 3.4rem; line-height: 1;
        color: {OKT_YELLOW}; letter-spacing: 0.01em; margin: 2px 0 10px 0;
    }}
    .kpi-bench {{
        font-family: {FONT_SUPPORT}; font-size: 0.9rem; letter-spacing: 0.1em;
        text-transform: uppercase; color: {OKT_MUTED}; line-height: 1.6;
    }}
    .source-tag {{
        font-family: {FONT_SUPPORT}; font-size: 0.8rem; color: {OKT_BLACK} !important;
        background-color: {OKT_YELLOW}; letter-spacing: 0.16em;
        text-transform: uppercase; padding: 3px 9px; border-radius: 0;
    }}

    /* --- QUALITATIVE FEEDBACK ---
       Positives and negatives are separated structurally (yellow vs neutral rule)
       rather than with a red/green pair, which sits outside the brand palette. */
    .fb-row {{
        display: flex; align-items: baseline; gap: 14px;
        background-color: {OKT_SURFACE_DEEP}; padding: 13px 16px;
        margin-bottom: 8px; border-left: 3px solid {OKT_LINE};
    }}
    .fb-row.pos {{ border-left-color: {OKT_YELLOW}; }}
    .fb-row.neg {{ border-left-color: {OKT_GREY}; }}
    .fb-pct {{
        font-family: {FONT_SUPPORT}; font-size: 1.5rem; line-height: 1;
        flex: 0 0 auto; min-width: 62px; letter-spacing: 0.02em;
    }}
    .fb-row.pos .fb-pct {{ color: {OKT_YELLOW}; }}
    .fb-row.neg .fb-pct {{ color: {OKT_LIGHT}; }}
    .fb-text {{ font-size: 0.95rem; color: {OKT_LIGHT}; line-height: 1.45; }}
    .fb-head {{
        font-family: {FONT_SUPPORT}; text-transform: uppercase;
        letter-spacing: 0.18em; font-size: 1rem; margin-bottom: 12px;
        padding-bottom: 6px; border-bottom: 1px solid {OKT_LINE};
    }}
    .fb-head.pos {{ color: {OKT_YELLOW}; }}
    .fb-head.neg {{ color: {OKT_MUTED}; }}

    /* --- AI REPORT --- */
    .report-container {{
        background-color: {OKT_SURFACE_DEEP}; padding: 34px 38px;
        border-radius: 0; border-left: 4px solid {OKT_YELLOW};
        line-height: 1.75; color: {OKT_LIGHT}; font-size: 1rem;
    }}
    .report-container h2 {{
        font-size: 1.3rem !important; border-left: none !important;
        padding-left: 0 !important; color: {OKT_YELLOW} !important;
        margin-top: 1.8rem !important;
    }}
    .report-container h2:first-child {{ margin-top: 0 !important; }}

    /* --- CONTROLS --- */
    .stSelectbox label, .stMultiSelect label, .stNumberInput label,
    .stFileUploader label {{
        font-family: {FONT_SUPPORT} !important; text-transform: uppercase !important;
        letter-spacing: 0.13em !important; color: {OKT_YELLOW} !important;
        font-size: 0.9rem !important;
    }}
    [data-testid="stSidebar"] {{
        background-color: {OKT_SURFACE_DEEP};
        border-right: 1px solid {OKT_LINE};
    }}
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
        border-left: none !important; padding-left: 0 !important;
        font-size: 1rem !important; color: {OKT_LIGHT} !important;
        margin-top: 1.6rem !important;
    }}
    .stMultiSelect [data-baseweb="tag"] {{
        background-color: {OKT_YELLOW} !important; border-radius: 0 !important;
    }}
    .stMultiSelect [data-baseweb="tag"] span {{
        color: {OKT_BLACK} !important; font-family: {FONT_SUPPORT} !important;
        letter-spacing: 0.06em !important;
    }}
    hr {{ border-color: {OKT_LINE}; }}
    </style>
    """, unsafe_allow_html=True)


def render_brand_header(descriptor):
    """Primary (horizontal) logotype lock-up: symbol left, wordmark right.
    The guide removed the 'MMA' descriptor from the brand name - OKTAGON alone
    carries it - so the descriptor slot names the tool, never the sport."""
    st.markdown(
        f"""<div class='okt-header'>
              <div class='okt-symbol'>{OKT_SYMBOL_SVG}</div>
              <div>
                <div class='okt-wordmark'>OKTAGON</div>
                <div class='okt-descriptor'>{descriptor}</div>
              </div>
            </div>""",
        unsafe_allow_html=True,
    )


def style_fig(fig, **layout):
    """Apply the brand chart treatment: transparent ground, geometric type,
    minimal rules, yellow as the only accent."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Jost, sans-serif", color=OKT_LIGHT, size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Bebas Neue, sans-serif", size=15)),
        margin=dict(l=10, r=10, t=48, b=10),
        xaxis=dict(showgrid=False, linecolor=OKT_LINE,
                   tickfont=dict(family="Bebas Neue, sans-serif", size=17)),
        yaxis=dict(range=[0, 5.5], gridcolor=OKT_LINE, zerolinecolor=OKT_LINE,
                   tickfont=dict(family="Bebas Neue, sans-serif", size=15)),
        **layout,
    )
    return fig


# --- UTILITIES ---
def clean_val(val):
    try:
        if pd.isna(val) or val == "-" or val == "–": return 0.0
        clean = str(val).replace('%', '').replace(',', '.').replace('★', '').strip()
        return float(clean)
    except: return 0.0

def default_region(col):
    """Default region for an Excel column header. The header is normalised to
    the bare event id first ("okt 88", "OKT88 ", "OKT088" -> "OKT88") so a stray
    space or case difference does not silently fall back to CZ."""
    m = re.search(r"OKT\s*0*(\d+)", str(col).upper())
    return HISTORICAL_MAPPING.get(f"OKT{m.group(1)}", "CZ") if m else "CZ"

def get_avg(df, row_idx, region_name, tourn_cols, mapping):
    vals = [clean_val(df.iloc[row_idx, df.columns.get_loc(c)]) for c in tourn_cols if mapping.get(c) == region_name]
    vals = [v for v in vals if v > 0]
    return sum(vals)/len(vals) if vals else 0

def row_anchor(df, r):
    """First meaningful text cell in a row - used as a section-title anchor."""
    if r is None or r >= len(df):
        return None
    for c in range(min(4, df.shape[1])):
        v = df.iloc[r, c]
        if isinstance(v, str) and v.strip() and not v.strip().replace('.', '').replace(',', '').isdigit():
            return v.strip()
    return None

def find_header_row(df, anchor):
    """Locate the row whose leading cells contain the given section title."""
    if not anchor:
        return None
    for r in range(len(df)):
        for c in range(min(4, df.shape[1])):
            v = df.iloc[r, c]
            if isinstance(v, str) and anchor.lower() in v.lower():
                return r
    return None

def extract_feedback(df, header_row, tour_col):
    """Return [(answer, pct), ...] for the 6 rows below a feedback header."""
    out = []
    if header_row is None:
        return out
    for i in range(1, 7):
        r = header_row + i
        if r >= len(df):
            break
        ans = df.iloc[r, 2]
        pct = clean_val(df.iloc[r, df.columns.get_loc(tour_col)])
        if pct > 0 and pd.notna(ans) and str(ans).strip():
            out.append((str(ans).strip(), pct))
    return out

def generate_report(client, prompt):
    """Ask the first Groq model the account can actually serve.
    Returns (report_text, model_used)."""
    unavailable = []
    for model in GROQ_MODEL_CANDIDATES:
        try:
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model,
            )
            return response.choices[0].message.content, model
        except Exception as e:
            msg = str(e)
            if "model_not_found" in msg or "does not exist" in msg:
                unavailable.append(model)
                continue
            raise
    raise RuntimeError(
        "None of these Groq models is available to this account: "
        f"{', '.join(unavailable)}. Check the current list at "
        "https://console.groq.com/docs/models and set the GROQ_MODEL secret."
    )


@st.cache_data(show_spinner=False)
def load_sheets(file):
    """Read both worksheets once and cache them so re-runs are instant."""
    df_gen = pd.read_excel(file, sheet_name="TICKETING GENERAL")
    df_vip = pd.read_excel(file, sheet_name="TICKETING VIP")
    return df_gen, df_vip

# --- DATA PROCESSING ---
uploaded_file = st.sidebar.file_uploader("Tournament Spreadsheet", type="xlsx")

if uploaded_file:
    df_gen, df_vip = load_sheets(uploaded_file)

    # Detect Columns
    all_cols = list(df_gen.columns)
    avg_index = next((i for i, col in enumerate(all_cols) if "AVERAGE" in str(col).upper()), len(all_cols))
    tourn_cols = [c for c in all_cols[3:avg_index] if "OKT" in str(c) and "Responses" not in str(c)]

    # --- EDITABLE REGION MAPPING (CZ/SK vs DE) ---
    # Every detected tournament can be re-classified here. Defaults come from
    # HISTORICAL_MAPPING; anything not listed there defaults to CZ.
    st.sidebar.subheader("Region Mapping")
    st.sidebar.caption("CZ = CZ/SK market • DE = German market")
    region_df = pd.DataFrame({
        "Tournament": tourn_cols,
        "Region": [default_region(c) for c in tourn_cols],
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
    st.sidebar.subheader("Respondent Counts")
    resp_general = st.sidebar.number_input("Respondents GENERAL", min_value=0, value=0, step=1)
    resp_vip = st.sidebar.number_input("Respondents VIP", min_value=0, value=0, step=1)

    # Sidebar Selection
    selected_tour = st.sidebar.selectbox("Focus Tournament", tourn_cols, index=len(tourn_cols)-1)
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

    # --- WRITTEN FEEDBACK (positives / negatives in %) for GENERAL and VIP ---
    # GENERAL block sits at known rows; VIP block is located by matching the same
    # section titles inside the VIP sheet (its rows differ from GENERAL).
    GEN_POS_ROW, GEN_NEG_ROW = 58, 68
    vip_pos_row = find_header_row(df_vip, row_anchor(df_gen, GEN_POS_ROW))
    vip_neg_row = find_header_row(df_vip, row_anchor(df_gen, GEN_NEG_ROW))
    feedback = {
        'GENERAL': {
            'pos': extract_feedback(df_gen, GEN_POS_ROW, selected_tour),
            'neg': extract_feedback(df_gen, GEN_NEG_ROW, selected_tour),
        },
        'VIP': {
            'pos': extract_feedback(df_vip, vip_pos_row, selected_tour),
            'neg': extract_feedback(df_vip, vip_neg_row, selected_tour),
        },
    }

    # --- 1. OVERALL SCORE & KPI PICKER ---
    render_brand_header("Survey Analyst")
    st.title(f"{selected_tour} Executive Report")

    # Respondent overview
    m1, m2 = st.columns(2)
    m1.metric("Respondents GENERAL", f"{resp_general:,}")
    m2.metric("Respondents VIP", f"{resp_vip:,}")

    # Custom Selection for "Featured KPIs"
    st.header("KPI Selection")
    sorted_devs = sorted(processed_kpis, key=lambda x: x['dev'], reverse=True)
    kpi_options = [f"[{k['source']}] {k['name']}" for k in sorted_devs]
    selected_kpi_names = st.multiselect("Pick indicators (Recommended: top deviators selected by default)", kpi_options, default=kpi_options[:3])

    final_selected_kpis = [kpi_by_label[label] for label in selected_kpi_names]

    # --- 2. GROQ AI REPORT ---
    if processed_kpis and not GROQ_API_KEY:
        st.warning(
            "No Groq API key found. Add **GROQ_API_KEY** to the Streamlit app "
            "Secrets (Manage app -> Settings -> Secrets) or to your local "
            "environment, then rerun. The dashboard below works without it."
        )
    elif processed_kpis:
        try:
            client = Groq(api_key=GROQ_API_KEY)

            # Extract current sat for AI
            sat_row_idx = 51
            cur_sat = clean_val(df_gen.iloc[sat_row_idx, df_gen.columns.get_loc(selected_tour)])
            cz_sat_avg = get_avg(df_gen, sat_row_idx, "CZ", tourn_cols, mapping)
            de_sat_avg = get_avg(df_gen, sat_row_idx, "DE", tourn_cols, mapping)

            # Split ALL indicators by source so each gets its own full analysis
            def kpi_lines(kpis):
                return [{'name': k['name'], 'score': k['score'],
                         'cz_avg': round(k['avg_cz'], 2), 'de_avg': round(k['avg_de'], 2)}
                        for k in kpis]

            def fb_lines(items):
                return [f"{ans} ({pct:g}%)" for ans, pct in items] or ["(no data)"]

            general_kpis = [k for k in processed_kpis if k['source'] == 'GENERAL']
            vip_kpis = [k for k in processed_kpis if k['source'] == 'VIP']
            total_resp = resp_general + resp_vip

            prompt = f"""
            You are an OKTAGON Market Researcher. Analyze {selected_tour} ({focus_region}).

            TOTAL RESPONDENTS: GENERAL = {resp_general}, VIP = {resp_vip}, COMBINED TOTAL = {total_resp}.

            Overall Satisfaction (GENERAL): {cur_sat} (CZ Avg: {cz_sat_avg:.2f}, DE Avg: {de_sat_avg:.2f})

            === GENERAL DATA (respondents = {resp_general}) ===
            ALL indicators: {kpi_lines(general_kpis)}
            Written feedback - biggest POSITIVES (% of respondents): {fb_lines(feedback['GENERAL']['pos'])}
            Written feedback - biggest NEGATIVES (% of respondents): {fb_lines(feedback['GENERAL']['neg'])}

            === VIP DATA (respondents = {resp_vip}) ===
            ALL indicators: {kpi_lines(vip_kpis)}
            Written feedback - biggest POSITIVES (% of respondents): {fb_lines(feedback['VIP']['pos'])}
            Written feedback - biggest NEGATIVES (% of respondents): {fb_lines(feedback['VIP']['neg'])}

            FORMAT - THIS IS THE MOST IMPORTANT RULE:
            Write the entire report as continuous prose, the way an analyst writes a
            written summary. It must read as connected sentences and paragraphs.
            - NEVER output a table. No markdown tables, no pipe characters (|), no
              ASCII/grid layouts, no aligned columns, no "Indicator: 4.2" label rows.
            - NEVER output bullet points or numbered lists. No lines starting with
              "-", "*" or "1.".
            - Weave every number into a sentence instead of listing it. Write
              "Atmosphere landed at 4.6, comfortably clear of the 4.2 CZ average and
              the 4.1 DE average", NOT "Atmosphere | 4.6 | 4.2 | 4.1".
            - Group related indicators into the same paragraph and connect them with
              real transitions, so each paragraph makes a point rather than reciting
              values.

            CONTENT:
            - Open with one sentence stating the respondent counts: GENERAL, VIP and the combined total.
            - Then produce TWO clearly separated sections using markdown headings exactly: "## GENERAL Analysis" and "## VIP Analysis".
            - Each section MUST open by stating its own respondent count.
            - In each section cover EVERY listed indicator (do not skip any), and for each mention the CZ and DE market averages for context.
            - In each section include a closing paragraph on the written feedback that
              covers the biggest positives and the biggest negatives with their exact
              percentages, ordered from highest to lowest, phrased as sentences.
            - Keep each section self-contained and concise enough to fit on a single presentation slide.
            - Take the sample sizes into account when judging how reliable the findings are.
            - Professional MMA industry tone.
            """

            with st.spinner("Groq AI is generating the executive summary..."):
                report, model_used = generate_report(client, prompt)
                # The blank lines let the first line become its own <p>; glued
                # straight onto the opening div it renders as bare text and loses
                # the paragraph spacing under the heading.
                st.markdown(
                    f"<div class='report-container'>\n\n{report}\n\n</div>",
                    unsafe_allow_html=True,
                )
                st.caption(f"Generated by Groq model: {model_used}")
        except Exception as e:
            msg = str(e)
            if "invalid_api_key" in msg or "Invalid API Key" in msg or "401" in msg:
                st.error(
                    "AI Analysis Error: the Groq API key was rejected. Generate a "
                    "fresh key at https://console.groq.com/keys and update the "
                    "GROQ_API_KEY secret."
                )
            else:
                st.error(f"AI Analysis Error: {e}")

    st.divider()

    # --- 3. INTERACTIVE GRAPHICS SECTION ---
    st.header("Interactive Data Audit")

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Market Comparison Tool")
        selected_graph_kpi = st.selectbox("Select Indicator for Graph 1", kpi_options, index=0)
        k_data = kpi_by_label[selected_graph_kpi]

        fig = go.Figure(data=[
            go.Bar(name='Event', x=[selected_tour], y=[k_data['score']], marker_color=OKT_YELLOW, text=[k_data['score']], textposition='auto'),
            go.Bar(name='CZ Market', x=[selected_tour], y=[k_data['avg_cz']], marker_color=OKT_LIGHT, text=[f"{k_data['avg_cz']:.2f}"], textposition='auto'),
            go.Bar(name='DE Market', x=[selected_tour], y=[k_data['avg_de']], marker_color=OKT_GREY, text=[f"{k_data['avg_de']:.2f}"], textposition='auto')
        ])
        style_fig(fig, barmode='group')
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Performance Benchmark Tool")
        selected_graph_kpi_2 = st.selectbox("Select Indicator for Graph 2", kpi_options, index=min(1, len(kpi_options)-1))
        k_data_2 = kpi_by_label[selected_graph_kpi_2]

        fig2 = go.Figure(data=[
            go.Bar(name='Score', x=[selected_tour], y=[k_data_2['score']], marker_color=OKT_YELLOW),
            go.Scatter(name='CZ Avg', x=[selected_tour], y=[k_data_2['avg_cz']], mode='markers+lines', marker=dict(color=OKT_LIGHT, size=15)),
            go.Scatter(name='DE Avg', x=[selected_tour], y=[k_data_2['avg_de']], mode='markers+lines', marker=dict(color=OKT_GREY, size=15))
        ])
        style_fig(fig2)
        st.plotly_chart(fig2, use_container_width=True)

    # --- 4. FEATURED KPI CARDS ---
    st.header("Featured KPI Analysis")
    if final_selected_kpis:
        cols = st.columns(len(final_selected_kpis))
        for i, k in enumerate(final_selected_kpis):
            with cols[i]:
                st.markdown(f"""
                    <div class='kpi-card'>
                        <span class='source-tag'>{k['source']}</span>
                        <div class='kpi-name'>{k['name']}</div>
                        <div class='kpi-score'>{k['score']:.2f}</div>
                        <div class='kpi-bench'>CZ Market {k['avg_cz']:.2f}<br>DE Market {k['avg_de']:.2f}</div>
                    </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Select at least one KPI above to populate the featured cards.")

    # --- 5. FEEDBACK (GENERAL + VIP) ---
    def render_feedback(label, fb):
        st.header(f"Qualitative Feedback — {label}")
        f_p, f_m = st.columns(2)
        with f_p:
            st.markdown("<div class='fb-head pos'>Positives</div>", unsafe_allow_html=True)
            for ans, pct in sorted(fb['pos'], key=lambda x: x[1], reverse=True):
                st.markdown(
                    f"<div class='fb-row pos'><span class='fb-pct'>{pct:g}%</span>"
                    f"<span class='fb-text'>{ans}</span></div>",
                    unsafe_allow_html=True,
                )
            if not fb['pos']:
                st.caption("No positive feedback detected for this sheet.")
        with f_m:
            st.markdown("<div class='fb-head neg'>Negatives</div>", unsafe_allow_html=True)
            for ans, pct in sorted(fb['neg'], key=lambda x: x[1], reverse=True):
                st.markdown(
                    f"<div class='fb-row neg'><span class='fb-pct'>{pct:g}%</span>"
                    f"<span class='fb-text'>{ans}</span></div>",
                    unsafe_allow_html=True,
                )
            if not fb['neg']:
                st.caption("No negative feedback detected for this sheet.")

    render_feedback("General", feedback['GENERAL'])
    render_feedback("VIP", feedback['VIP'])

else:
    render_brand_header("Survey Analyst")
    st.info("Upload the tournament survey results to generate your executive report.")
