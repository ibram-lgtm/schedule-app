import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
from io import BytesIO
import calendar

# ==================================
# 1. إعدادات التطبيق وتصميم الواجهة
# ==================================
st.set_page_config(layout="wide", page_title="جدول المناوبات الشبكي")

# --- كود التصميم المخصص (CSS) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    
    html, body, [class*="st-"] {
        font-family: 'Tajawal', sans-serif;
    }

    :root {
        --primary-color: #667eea;
        --background-color: #f0f4f8;
        --card-bg: white;
        --border-color: #e9ecef;
        --header-bg: #495057;
    }

    .stApp { background-color: var(--background-color); }
    h1, h2, h3 { color: var(--primary-color); text-align: center; }

    /* Grid Card Styling */
    .grid-card-day {
        background-color: var(--card-bg);
        border-radius: 12px;
        padding: 15px;
        border: 1px solid var(--border-color);
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        min-height: 250px;
        display: flex;
        flex-direction: column;
    }
    .grid-card-empty {
        background-color: #f8f9fa;
        border-radius: 12px;
        min-height: 250px;
        border: 1px dashed #ced4da;
    }
    .day-header {
        font-weight: bold;
        font-size: 1.5em;
        color: var(--primary-color);
        margin-bottom: 10px;
        border-bottom: 2px solid var(--border-color);
        padding-bottom: 5px;
    }
    .shift-title {
        font-weight: bold;
        margin-top: 10px;
        font-size: 0.9em;
    }
    .doctor-name {
        font-size: 0.85em;
        padding-right: 10px;
    }
    .weekday-header {
        text-align: center;
        font-weight: 700;
        color: var(--header-bg);
        padding: 10px;
        background-color: var(--card-bg);
        border-radius: 8px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🗓️ جدول المناوبات الشبكي")

# ==================================
# 2. تهيئة البيانات والخوارزمية (بدون تغيير)
# ==================================
if 'doctors' not in st.session_state: st.session_state.doctors = [f"طبيب {i+1}" for i in range(65)]
if 'constraints' not in st.session_state: st.session_state.constraints = {doc: {"max_shifts": 18} for doc in st.session_state.doctors}
if 'schedule_df' not in st.session_state: st.session_state.schedule_df = None

@st.cache_data(ttl=600)
def generate_schedule_grid(num_days, doctors, constraints):
    SHIFTS = ["☀️ صبح", "🌙 مساء", "🌃 ليل"]
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
            total_in_shift = [shifts_vars[(doc, day, shift, area)] for doc in doctors for area in ALL_AREAS]
            model.Add(sum(total_in_shift) >= 10)
            model.Add(sum(total_in_shift) <= 13)
    for day in range(num_days):
        for doc in doctors:
            model.Add(sum(shifts_vars[(doc, day, shift, area)] for shift in SHIFTS for area in ALL_AREAS) <= 1)
    for doc, doc_constraints in constraints.items():
        if doc in doctors:
            max_s = doc_constraints.get("max_shifts", 18)
            model.Add(sum(shifts_vars[(doc, day, s, a)] for day in range(num_days) for s in SHIFTS for a in ALL_AREAS) <= max_s)
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
# 4. دالة عرض البطاقات الشبكية الجديدة
# ==================================
def display_grid_card_view(df, year, month):
    st.header(f"عرض تقويم شهر {calendar.month_name[month]}، {year}")
    
    month_calendar = calendar.monthcalendar(year, month)
    arabic_weekdays = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]

    # عرض رؤوس أيام الأسبوع
    cols = st.columns(7)
    for i, day_name in enumerate(arabic_weekdays):
        with cols[i]:
            st.markdown(f'<div class="weekday-header">{day_name}</div>', unsafe_allow_html=True)

    # عرض بطاقات الأيام
    for week in month_calendar:
        cols = st.columns(7)
        for i, day in enumerate(week):
            with cols[i]:
                if day == 0:
                    st.markdown('<div class="grid-card-empty"></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="grid-card-day">', unsafe_allow_html=True)
                    st.markdown(f'<div class="day-header">{day}</div>', unsafe_allow_html=True)
                    
                    day_df = df[df['اليوم'] == day] if df is not None else pd.DataFrame()
                    
                    if day_df.empty:
                        st.write("لا توجد مناوبات")
                    else:
                        for shift_name in ["☀️ صبح", "🌙 مساء", "🌃 ليل"]:
                            shift_df = day_df[day_df['المناوبة'] == shift_name]
                            if not shift_df.empty:
                                st.markdown(f'<p class="shift-title">{shift_name}</p>', unsafe_allow_html=True)
                                for _, row in shift_df.iterrows():
                                    st.markdown(f'<p class="doctor-name">{row["الطبيب"]} <small>({row["القسم"]})</small></p>', unsafe_allow_html=True)
                    
                    st.markdown('</div>', unsafe_allow_html=True)
    
# ==================================
# 5. بناء الواجهة التفاعلية
# ==================================
with st.sidebar:
    st.header("التحكم في الجدول")
    current_date = pd.to_datetime("today")
    year_input = st.number_input("السنة", value=current_date.year)
    month_input = st.number_input("الشهر", value=current_date.month, min_value=1, max_value=12)
    
    if st.button("🚀 توليد / تحديث الجدول", use_container_width=True):
        num_days_input = calendar.monthrange(year_input, month_input)[1]
        with st.spinner("🧠 الخوارزمية تعمل..."):
            schedule = generate_schedule_grid(num_days_input, st.session_state.doctors, st.session_state.constraints)
            if schedule is not None:
                st.session_state.schedule_df = schedule
                st.success("🎉 تم إنشاء الجدول بنجاح!")
            else:
                st.error("لم يتم العثور على حل.")

# --- عرض الواجهة الرئيسية ---
if st.session_state.schedule_df is not None:
    display_grid_card_view(st.session_state.schedule_df, year_input, month_input)
else:
    st.info("اضغط على 'توليد الجدول' في الشريط الجانبي لبدء العملية.")
