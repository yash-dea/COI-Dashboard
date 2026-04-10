import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import requests
import os
from dotenv import load_dotenv

# --- LOAD ENVIRONMENT VARIABLES ---
load_dotenv()
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "5eaf5e9a")
ADZUNA_API_KEY = os.getenv("ADZUNA_API_KEY", "843e2ffe3f338257d79a547fa386d743")

# --- PAGE CONFIG ---
st.set_page_config(page_title="Cost of Inaction | Career Audit", layout="wide")

# --- ADZUNA API FUNCTION ---
@st.cache_data(ttl=3600)
def fetch_target_salary(role, location, country="us"):
    """Fetches min, median, and max salary data from Adzuna API."""
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_API_KEY,
        "what": role,
        "where": location,
        "results_per_page": 50
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if results:
                mins = [r.get("salary_min") for r in results if r.get("salary_min")]
                maxs = [r.get("salary_max") for r in results if r.get("salary_max")]
                
                if mins and maxs:
                    return {
                        "min": np.min(mins),
                        "median": np.median(mins + maxs),
                        "max": np.max(maxs),
                        "success": True
                    }
    except Exception as e:
        pass
    
    # Fallback Data
    return {"min": 85000, "median": 145000, "max": 280000, "success": False}

# --- SESSION STATE INITIALIZATION ---
today = date.today()
if 'career_history' not in st.session_state:
    st.session_state.career_history = [
        {"id": 0, "title": "Senior Analyst", "start": today - relativedelta(years=3), "end": today, "is_current": True, "base": 90000, "bonus": 5000, "equity": 0},
        {"id": 1, "title": "Data Analyst", "start": today - relativedelta(years=6), "end": today - relativedelta(years=3, months=1), "is_current": False, "base": 70000, "bonus": 2000, "equity": 0},
        {"id": 2, "title": "Junior Analyst", "start": today - relativedelta(years=9), "end": today - relativedelta(years=6, months=2), "is_current": False, "base": 50000, "bonus": 0, "equity": 0}
    ]
    st.session_state.next_id = 3

def add_role():
    st.session_state.career_history.insert(0, 
        {"id": st.session_state.next_id, "title": "New Role", "start": today, "end": today, "is_current": False, "base": 100000, "bonus": 0, "equity": 0}
    )
    st.session_state.next_id += 1

def delete_role(role_id):
    st.session_state.career_history = [r for r in st.session_state.career_history if r["id"] != role_id]

# --- LAYOUT ---
col_left, col_right = st.columns([1, 2.5], gap="large")

# ==========================================
# LEFT COLUMN: INPUTS & ASSUMPTIONS
# ==========================================
with col_left:
    st.subheader("Career History")
    
    for i, role in enumerate(st.session_state.career_history):
        with st.container(border=True):
            total_comp = role['base'] + role['bonus'] + role['equity']
            head_col1, head_col2 = st.columns([3, 1])
            role['title'] = head_col1.text_input("Job Title", value=role['title'], key=f"t_{role['id']}")
            head_col2.markdown(f"<h4 style='text-align: right; color: #4A5568;'>${total_comp:,}</h4>", unsafe_allow_html=True)
            
            d1, d2, d3 = st.columns([2, 2, 1])
            role['start'] = d1.date_input("Start Date", value=role['start'], key=f"ds_{role['id']}")
            role['is_current'] = d3.checkbox("Current", value=role['is_current'], key=f"cur_{role['id']}")
            
            if role['is_current']:
                role['end'] = today
                d2.markdown("<div style='padding-top: 35px; color: gray;'>Present</div>", unsafe_allow_html=True)
            else:
                role['end'] = d2.date_input("End Date", value=role['end'], key=f"de_{role['id']}")

            b_col, bn_col, e_col = st.columns(3)
            role['base'] = b_col.number_input("Base ($)", value=role['base'], step=5000, key=f"b_{role['id']}")
            role['bonus'] = bn_col.number_input("Bonus ($)", value=role['bonus'], step=1000, key=f"bn_{role['id']}")
            role['equity'] = e_col.number_input("Equity ($)", value=role['equity'], step=1000, key=f"e_{role['id']}")
            
            if st.button("Delete Role", key=f"del_{role['id']}", type="secondary", use_container_width=True):
                delete_role(role['id'])
                st.rerun()

    st.button("+ Add Historical Role", on_click=add_role, type="primary", use_container_width=True)

    st.markdown("---")
    st.subheader("Data Career Target")
    target_role = st.selectbox("Target Role", ["Data Engineer", "Data Scientist", "AI Engineer", "Machine Learning Engineer", "Data Analyst"])
    target_location = st.text_input("Target Location", "New York, NY")

    st.markdown("---")
    st.subheader("Modeling Engine Parameters")
    
    st.markdown("**Past Path Assumptions (Actuals)**")
    past_appraisal_pct = st.slider("Past Appraisal/Increment (%)", 0, 20, 5) / 100
    past_appraisal_freq = st.slider("Appraisal Frequency (Years)", 1, 5, 1)

    st.markdown("**Future Appraisals & Hopping**")
    forecast_years = st.slider("Forecast Horizon (Years)", 3, 15, 10)
    safe_growth = st.slider("Future Annual Appraisal (%)", 1, 10, 4) / 100
    hop_cadence = st.slider("Hop Cadence (Years)", 1, 5, 3)
    hop_raise = st.slider("Current Field Hop Inc. (%)", 5, 40, 20) / 100
    
    st.markdown("**Data Career Change**")
    data_hop_raise = st.slider("Data Hop Increment (%)", 10, 60, 30) / 100
    
    with st.expander("Advanced: Soft Limitations & Decay"):
        st.caption("Decay now starts counting from TODAY for future paths, preserving initial aggressive growth.")
        decay_start_yr = st.number_input("Start Decay After (Years from today)", min_value=1, value=6)
        decay_rate = st.slider("Annual Growth Decay (%)", 0.0, 10.0, 2.0, step=0.5) / 100
        current_field_ceiling_multiplier = st.slider("Current Field Ceiling (x Current Pay)", 1.5, 5.0, 2.0)

# ==========================================
# DATA PROCESSING & MATHEMATICAL ENGINE
# ==========================================
market_data = fetch_target_salary(target_role, target_location)
data_median = market_data["median"]
data_ceiling = market_data["max"]
data_min = market_data["min"]

sorted_roles = sorted([r for r in st.session_state.career_history if r['start'] <= r['end']], key=lambda x: x['start'])

if len(sorted_roles) > 0:
    start_date = sorted_roles[0]['start']
    end_date = today + relativedelta(years=forecast_years)
    
    date_range = pd.date_range(start=start_date, end=end_date, freq='MS')
    df = pd.DataFrame({"Date": date_range})
    
    # 1. ACTUAL / SAFE PATH BASELINE (WITH PAST APPRAISALS)
    df['Current_Path'] = np.nan
    for _, row in df.iterrows():
        d = row['Date'].date()
        if d <= today:
            employed = False
            for role in sorted_roles:
                if role['start'] <= d <= role['end']:
                    months_in_role = (d.year - role['start'].year) * 12 + (d.month - role['start'].month)
                    appraisals_received = months_in_role // (past_appraisal_freq * 12)
                    
                    base_comp = role['base'] + role['bonus'] + role['equity']
                    current_comp_in_role = base_comp * ((1 + past_appraisal_pct) ** appraisals_received)
                    
                    df.at[row.name, 'Current_Path'] = current_comp_in_role
                    employed = True
                    break
            if not employed and row.name > 0:
                df.at[row.name, 'Current_Path'] = df.at[row.name-1, 'Current_Path']

    df['Current_Path'] = df['Current_Path'].interpolate(method='linear', limit_direction='forward')
    current_comp = df.loc[df['Date'].dt.date <= today, 'Current_Path'].iloc[-1]
    current_field_ceiling = current_comp * current_field_ceiling_multiplier

    # 3. CALCULATE IMMEDIATE JUMPS FOR TODAY
    immediate_hop_salary = current_comp * (1 + hop_raise)
    
    # EXACT RULE: Max of 20% increase on current OR 20% higher than Adzuna Min
    data_start_salary = max(current_comp * 1.20, data_min * 1.20)

    # Simulation Arrays
    hop_past_vals = []
    hop_future_vals = []
    data_future_vals = []
    
    current_sim_past = sorted_roles[0]['base'] + sorted_roles[0]['bonus'] + sorted_roles[0]['equity']
    current_sim_future = immediate_hop_salary
    current_sim_data = data_start_salary
    
    first_hop_month = hop_cadence * 12

    for i, row in df.iterrows():
        d = row['Date'].date()
        months_from_start = i
        
        # --- PAST SIMULATION ---
        if d <= today:
            actual_val = df.at[i, 'Current_Path']
            
            if months_from_start < first_hop_month - 1:
                current_sim_past = np.nan
            elif months_from_start == first_hop_month - 1:
                current_sim_past = actual_val
            elif months_from_start == first_hop_month:
                current_sim_past = df.at[i-1, 'Current_Path'] * (1 + hop_raise)
            else:
                # Appraisals & Hops (Staircase Function)
                if months_from_start % (hop_cadence * 12) == 0:
                    current_sim_past *= (1 + hop_raise)
                elif months_from_start % (past_appraisal_freq * 12) == 0:
                    current_sim_past *= (1 + past_appraisal_pct)
                
                fomo_multiplier = 1.15 + hop_raise 
                current_sim_past = max(current_sim_past, actual_val * fomo_multiplier) 
            
            hop_past_vals.append(current_sim_past)
            hop_future_vals.append(np.nan)
            data_future_vals.append(np.nan)
            
        # --- FUTURE SIMULATION ---
        else:
            months_from_today = len(hop_future_vals) - len(df[df['Date'].dt.date <= today]) + 1
            years_from_today = months_from_today / 12
            
            is_hop_month = (months_from_today > 0 and months_from_today % (hop_cadence * 12) == 0)
            is_appraisal_month = (months_from_today > 0 and months_from_today % 12 == 0)

            # 1. Safe Path Continuation (Annual Staircase)
            if is_appraisal_month:
                df.at[i, 'Current_Path'] = df.at[i-1, 'Current_Path'] * (1 + safe_growth)
            else:
                df.at[i, 'Current_Path'] = df.at[i-1, 'Current_Path']
            
            # 2. Hop Future (Current Field - Annual Staircase)
            if is_hop_month:
                raise_pct = hop_raise
                if years_from_today > decay_start_yr:
                    raise_pct *= ((1 - decay_rate) ** (years_from_today - decay_start_yr))
                sat = max(0.4, 1.0 - (current_sim_future / current_field_ceiling)**3)
                current_sim_future *= (1 + (raise_pct * sat))
            elif is_appraisal_month:
                raise_pct = safe_growth
                if years_from_today > decay_start_yr:
                    raise_pct *= ((1 - decay_rate) ** (years_from_today - decay_start_yr))
                sat = max(0.4, 1.0 - (current_sim_future / current_field_ceiling)**3)
                current_sim_future *= (1 + (raise_pct * sat))
                
            current_sim_future = max(current_sim_future, df.at[i, 'Current_Path'] * 1.05)
            hop_future_vals.append(current_sim_future)
            
            # 3. Data Career Future (Annual Staircase)
            if months_from_today == 1:
                current_sim_data = data_start_salary
            else:
                if is_hop_month:
                    raise_pct = data_hop_raise
                    if years_from_today > decay_start_yr:
                        raise_pct *= ((1 - decay_rate) ** (years_from_today - decay_start_yr))
                    sat = max(0.4, 1.0 - (current_sim_data / data_ceiling)**3)
                    current_sim_data *= (1 + (raise_pct * sat))
                elif is_appraisal_month:
                    raise_pct = safe_growth
                    if years_from_today > decay_start_yr:
                        raise_pct *= ((1 - decay_rate) ** (years_from_today - decay_start_yr))
                    sat = max(0.4, 1.0 - (current_sim_data / data_ceiling)**3)
                    current_sim_data *= (1 + (raise_pct * sat))
            
            current_sim_data = max(current_sim_data, current_sim_future * 1.05)
            data_future_vals.append(current_sim_data)
            hop_past_vals.append(np.nan)

    df['Hop_Past'] = hop_past_vals
    df['Hop_Future'] = hop_future_vals
    df['Data_Future'] = data_future_vals

# ==========================================
# RIGHT COLUMN: GRAPH & FOMO METRICS
# ==========================================
with col_right:
    title_col, btn_col = st.columns([4, 1])
    with title_col:
        st.title("The Cost of Inaction")
    with btn_col:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh Chart", use_container_width=True, type="primary"):
            st.rerun()
    
    if len(sorted_roles) > 0:
        df_past = df[df['Date'].dt.date <= today]
        df_future = df[df['Date'].dt.date > today]
        
        hop_past_metric_series = df_past['Hop_Past'].fillna(df_past['Current_Path'])
        lost_to_date = (hop_past_metric_series.sum() / 12) - (df_past['Current_Path'].sum() / 12)
        
        future_loss_no_data = (df_future['Hop_Future'].sum() / 12) - (df_future['Current_Path'].sum() / 12)
        future_loss_with_data = (df_future['Data_Future'].sum() / 12) - (df_future['Current_Path'].sum() / 12)

        m1, m2, m3 = st.columns(3)
        with m1.container(border=True):
            st.markdown("🔴 **Wealth Lost To Date**")
            st.markdown(f"<h2 style='color: #ef4444;'>-${lost_to_date:,.0f}</h2>", unsafe_allow_html=True)
            
        with m2.container(border=True):
            st.markdown("🟡 **Future Gain (Hopping)**")
            st.markdown(f"<h2 style='color: #eab308;'>+${future_loss_no_data:,.0f}</h2>", unsafe_allow_html=True)

        with m3.container(border=True):
            st.markdown(f"🔵 **Future Gain ({target_role})**")
            st.markdown(f"<h2 style='color: #3b82f6;'>+${future_loss_with_data:,.0f}</h2>", unsafe_allow_html=True)

        # --- PLOTLY VISUALIZATION ---
        fig = go.Figure()

        # 1. Current Path
        fig.add_trace(go.Scatter(
            x=df['Date'], y=df['Current_Path'],
            mode='lines', name='Current Path (Actual History & Appraisals)',
            line=dict(color='#94a3b8', width=4)
        ))

        # 1.5 THE BLEED FIX
        fig.add_trace(go.Scatter(
            x=df_past['Date'], y=df_past['Current_Path'],
            mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'
        ))

        # 2. Hop Past
        fig.add_trace(go.Scatter(
            x=df_past['Date'], y=df_past['Hop_Past'],
            mode='lines', name='Past Potential (If Hopped)',
            line=dict(color='#ef4444', width=3, dash='dash'),
            fill='tonexty', fillcolor='rgba(239, 68, 68, 0.1)'
        ))

        future_start_date = df_past['Date'].iloc[-1]
        
        # 3. Hop Future
        x_future_hop = [future_start_date] + list(df_future['Date'])
        y_future_hop = [immediate_hop_salary] + list(df_future['Hop_Future'])
        
        fig.add_trace(go.Scatter(
            x=x_future_hop, y=y_future_hop,
            mode='lines', name='Future Hopping (Current Field)',
            line=dict(color='#eab308', width=3)
        ))

        # 4. Data Future
        x_future_data = [future_start_date] + list(df_future['Date'])
        y_future_data = [data_start_salary] + list(df_future['Data_Future'])
        
        fig.add_trace(go.Scatter(
            x=x_future_data, y=y_future_data,
            mode='lines', name=f'{target_role} Path',
            line=dict(color='#3b82f6', width=4),
            fill='tonexty', fillcolor='rgba(59, 130, 246, 0.15)'
        ))
        
        today_ts = pd.Timestamp(today)
        fig.add_vline(x=today_ts, line_width=2, line_dash="dash", line_color="white")
        fig.add_annotation(
            x=today_ts, 
            y=1.0, 
            yref="paper", 
            text="TODAY", 
            showarrow=False, 
            xanchor="left", 
            yanchor="bottom", 
            font=dict(color="white")
        )

        fig.update_layout(
            hovermode="x unified",
            xaxis=dict(
                title="Timeline", 
                showgrid=True, 
                gridcolor='rgba(255,255,255,0.1)',
                dtick="M12",  
                tickformat="%Y"
            ),
            yaxis=dict(tickformat="$s", title="Annualized Compensation", showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            height=550,
            template="plotly_dark",
            margin=dict(l=0, r=0, t=50, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

        # --- MARKET DATA DISPLAY ---
        st.markdown("---")
        st.markdown(f"### Live Market Insights: **{target_role}** in **{target_location}**")
        
        if market_data["success"]:
            st.success("Successfully pulled live data from Adzuna API.")
        else:
            st.warning("Using industry average fallback data. Live API data was unavailable for this specific role/location.")
            
        st.markdown(f"The simulation models an immediate strategic salary bump upon switching to {target_role}. This starting point is calculated as the **higher** of a 20% increase on your current salary, or 20% above the Adzuna market minimum.")
        
        col_min, col_med, col_max = st.columns(3)
        with col_min.container(border=True):
            st.metric("Market Minimum", f"${data_min:,.0f}")
            st.caption("Entry-level or lower percentile representation.")
            
        with col_med.container(border=True):
            st.metric("Market Median", f"${data_median:,.0f}")
            st.caption("The standard midpoint for this role.")
            
        with col_max.container(border=True):
            st.metric("Market Ceiling (Max)", f"${data_ceiling:,.0f}")
            st.caption("Top earners in the market (used as the saturation cap).")

    else:
        st.info("Please enter your career history on the left to generate your analysis.")