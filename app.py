import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
from io import BytesIO
import calendar

# ==================================
# 1. إعدادات التطبيق والواجهة
# ==================================
st.set_page_config(layout="wide", page_title="جدول المناوبات الذكي (Rota View)")

# --- كود التصميم المخصص ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Tajawal', sans-serif; color: #121212; }
    :root { --primary-color: #4A90E2; --background-color: #f0f4f8; --card-bg: white; --border-color: #e9ecef; }
    .stApp { background-color: var(--background-color); }
    h1, h2, h3, h4, h5 { color: var(--primary-color); }
    .daily-view-container { display: flex; overflow-x: auto; padding: 15px; background-color: var(--card-bg); border-radius: 12px; border: 1px solid var(--border-color); gap: 15px; }
    .day-column { min-width: 280px; flex-shrink: 0; border-right: 1px solid var(--border-color); padding-right: 15px; }
    .day-column:last-child { border-right: none; }
    .day-column h4 { margin-top: 0; padding-bottom: 10px; }
    .shift-group h5 { font-weight: bold; margin-top: 15px; margin-bottom: 8px; color: #333; font-size: 1.1em; }
    .doctor-card { background-color: #f8f9fa; border-radius: 6px; padding: 10px; margin-bottom: 6px; font-size: 0.95em; border-left: 4px solid var(--primary-color); box-shadow: 0 2px 4px rgba(0,0,0,0.04); }
</style>
""", unsafe_allow_html=True)

st.title("🗓️ جدول المناوبات الذكي (Rota View)")
st.markdown("### نظام احترافي لعرض وتصدير جداول المناوبات")

# ==================================
# 2. تهيئة البيانات
# ==================================
if 'doctors' not in st.session_state: st.session_state.doctors = [f"طبيب {i+1}" for i in range(65)]
if 'constraints' not in st.session_state: st.session_state.constraints = {doc: {"max_shifts": 18} for doc in st.session_state.doctors}
if 'schedule_df' not in st.session_state: st.session_state.schedule_df = None

# ==================================
# 3. الخوارزمية
# ==================================
@st.cache_data(ttl=600)
def generate_schedule_pro(num_days, doctors, constraints):
    SHIFTS = ["☀️", "🌙", "🌃"] # استخدام الرموز فقط
    AREAS_MIN_COVERAGE = {"فرز": 2, "تنفسية": 1, "ملاحظة": 4, "انعاش": 3}
    ALL_AREAS = list(AREAS_MIN_COVERAGE.keys())
    model = cp_model.CpModel()
    shifts_vars = {}
    for doc in doctors:
        for day in range(num_days):
            for shift in SHIFTS:
                for area in ALL_AREAS:
                    shifts_vars[(doc, day, shift, area)] = model.NewBoolVar(f"shift_{doc}_{day}_{shift}_{area}")
    for day in range(num_days):
        for shift in SHIFTS:
            for area, min_count in AREAS_MIN_COVERAGE.items():
                model.Add(sum(shifts_vars[(doc, day, shift, area)] for doc in doctors) >= min_count)
    for day in range(num_days):
        for doc in doctors:
            model.Add(sum(shifts_vars[(doc, day, shift, area)] for shift in SHIFTS for area in ALL_AREAS) <= 1)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 120.0
    status = solver.Solve(model)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        data = []
        for doc in doctors:
            for day in range(num_days):
                for shift in SHIFTS:
                    for area in ALL_AREAS:
                        if solver.Value(shifts_vars[(doc, day, shift, area)]) == 1:
                            data.append({"الطبيب": doc, "اليوم": day + 1, "المناوبة": shift, "القسم": area})
        return pd.DataFrame(data)
    return None

# ==================================
# 4. دوال العرض والتصدير الاحترافية
# ==================================
def create_professional_excel(df, year, month):
    output = BytesIO()
    num_days = calendar.monthrange(year, month)[1]
    doctors = sorted(df['الطبيب'].unique().tolist())
    schedule_grid = pd.DataFrame(index=doctors, columns=range(1, num_days + 1)).fillna("راحة")
    
    for _, row in df.iterrows():
        schedule_grid.loc[row['الطبيب'], row['اليوم']] = f"{row['المناوبة']} {row['القسم']}"

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:

