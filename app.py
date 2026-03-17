import streamlit as st
import pandas as pd
import numpy as np

# 1. Configuration & Historical Mapping
HISTORICAL_MAPPING = {
    "OKT72": "CZ", "OKT73": "DE", "OKT74": "CZ", "OKT75": "DE", 
    "OKT76": "DE", "OKT77": "CZ", "OKT78": "DE", "OKT79": "CZ", 
    "OKT80": "DE", "OKT81": "CZ", "OKT82": "DE", "OKT83": "DE", 
    "OKT84": "CZ", "OKT85": "DE"
}

st.set_page_config(page_title="OKTAGON Insight Engine", layout="wide")

# --- Helper Function to extract specific metrics from your summary layout ---
def get_metric(df, question_text, answer_option, tournament_col):
    try:
        # Locate the row where Question matches and Answer Option matches
        val = df[(df['Question'].str.contains(question_text, na=False, case=False)) & 
                 (df['Answer Option'].str.contains(answer_option, na=False, case=False))][tournament_col].values[0]
        return float(str(val).replace('%', '').replace(',', '.'))
    except:
        return 0.0

st.title("🥊 OKTAGON Tournament Report Generator")

# --- Sidebar Configuration ---
st.sidebar.header("Data Upload")
uploaded_file = st.sidebar.file_uploader("Upload XLSX file", type="xlsx")

new_tourn = st.sidebar.text_input("Add New Tournament (e.g., OKT86)")
new_reg = st.sidebar.selectbox("Region of New Tournament", ["CZ", "DE"])

if uploaded_file:
    # Load Sheets
    # Based on your paste, I'm assuming sheet names are 'TICKETING GENERAL' and 'TICKETING VIP'
    try:
        df_gen = pd.read_excel(uploaded_file, sheet_name="TICKETING GENERAL")
        df_vip = pd.read_excel(uploaded_file, sheet_name="TICKETING VIP")
    except:
        st.error("Sheet names must be 'TICKETING GENERAL' and 'TICKETING VIP'")
        st.stop()

    # Update Mapping
    mapping = HISTORICAL_MAPPING.copy()
    if new_tourn:
        mapping[new_tourn] = new_reg

    # Identify all tournaments available in the file columns
    all_cols = [c for c in df_gen.columns if "OKT" in str(c) and "Responses" not in str(c)]
    
    # --- 2. CALCULATE REGIONAL AVERAGES ---
    cz_tours = [t for t, r in mapping.items() if r == "CZ" and t in all_cols]
    de_tours = [t for t, r in mapping.items() if r == "DE" and t in all_cols]

    def get_avg_for_region(tour_list):
        sats = []
        for t in tour_list:
            # Get General Experience Rating
            val = get_metric(df_gen, "overall experience", "Rating", t)
            if val > 0: sats.append(val)
        return np.mean(sats) if sats else 0

    cz_avg = get_avg_for_region(cz_tours)
    de_avg = get_avg_for_region(de_tours)

    st.header("🌍 Regional Performance Benchmarks")
    c1, c2 = st.columns(2)
    c1.metric("CZ Average Satisfaction", f"{cz_avg:.2f} ★")
    c2.metric("DE Average Satisfaction", f"{de_avg:.2f} ★")
    
    st.info(f"**Insight:** {'CZ' if cz_avg > de_avg else 'DE'} tournaments currently lead in fan satisfaction by {abs(cz_avg-de_avg):.2f} points.")

    st.divider()

    # --- 3. TOURNAMENT FOCUS ---
    st.header("🎯 Tournament Focus Report")
    selected_tour = st.selectbox("Select tournament for detailed report:", all_cols)

    if selected_tour:
        # Extract specific values for the selected tournament
        # General Data
        gen_sat = get_metric(df_gen, "overall experience", "Rating", selected_tour)
        gen_cat = get_metric(df_gen, "catering / services", "Rating", selected_tour)
        
        # VIP Data
        vip_sat = get_metric(df_vip, "Overall, how satisfied", "Average Rating", selected_tour)
        vip_cat = get_metric(df_vip, "catering & refreshments", "Average Rating", selected_tour)

        # A) 1-SLIDE PRESENTATION BULLETS
        st.subheader("📋 Presentation Slide Bullets")
        region = mapping.get(selected_tour, "Unknown")
        reg_avg = cz_avg if region == "CZ" else de_avg
        diff_vs_avg = gen_sat - reg_avg

        bullet_points = f"""
        • **Overall Event Rating:** {selected_tour} ({region}) achieved a {gen_sat}★ rating.
        • **Market Context:** This is {'higher' if diff_vs_avg > 0 else 'lower'} than the {region} regional average of {reg_avg:.2f}.
        • **VIP Experience:** VIP satisfaction stands at {vip_sat}★, showing a {vip_sat - gen_sat:.2f} delta from General Admission.
        • **Catering Performance:** VIP catering ({vip_cat}★) vs. General catering ({gen_cat}★).
        """
        st.code(bullet_points, language=None)

        # B) CATERING COMPARISON
        st.subheader("🍴 Catering Analysis: General vs VIP")
        cat_data = pd.DataFrame({
            "Category": ["General Catering", "VIP Catering"],
            "Score": [gen_cat, vip_cat]
        })
        st.bar_chart(data=cat_data, x="Category", y="Score")
        
        # C) PLUS/MINUS SUMMARY (Based on the "Positives/Negatives" sections in your sheet)
        st.subheader("📝 Structured Feedback Summary (Next Meeting)")
        
        # We extract the Top Positive and Top Negative rows from your sheet
        try:
            # Get the top % row under Positives and Negatives
            pos_row = df_gen[df_gen['Section'] == 'Positives'].iloc[1:4] # Top 3 positives
            neg_row = df_gen[df_gen['Section'] == 'Negatives'].iloc[1:4] # Top 3 negatives
            
            col_p, col_m = st.columns(2)
            with col_p:
                st.success("**STRENGTHS (+)**")
                for _, row in pos_row.iterrows():
                    st.write(f"• {row['Answer Option']} ({row[selected_tour]}%)")
            with col_m:
                st.error("**PAIN POINTS (-)**")
                for _, row in neg_row.iterrows():
                    st.write(f"• {row['Answer Option']} ({row[selected_tour]}%)")
        except:
            st.write("Feedback summary unavailable in this sheet format.")

else:
    st.info("Upload the survey results to begin.")