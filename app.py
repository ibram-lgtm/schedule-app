import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
from io import BytesIO
import calendar

# ==================================
# 1. إعدادات التطبيق والواجهة
# ==================================
st.set_page_config(layout="wide", page_title="جدول المناوبات الذكي Pro")

# --- كود التصميم المخصص (الوضع النهاري فقط) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    
    html, body, [class*="st-"] {
        font-family: 'Tajawal', sans-serif;
        color: #121212; /* لون الخط الأساسي غامق */
    }

    :root {
        --primary-color: #667eea;
        --background-color: #f0f4f8;
        --card-bg: white;
        --border-color: #e9ecef;
        --tab-selected-bg: #667eea;
        --tab-selected-color: white;
    }

    .stApp { 
        background-color: var(--background-color);
    }

    h1, h2, h3 { 
        color: var(--primary-color); 
    }

    .stTabs [aria-selected="true"] { 
        background-color: var(--tab-selected-bg); 
        color: var(--tab-selected-color) !important; 
        font-weight: bold; 
    }

    .day-card {
        border-radius: 8px;
        padding: 10px;
        margin: 4px 0;
        border: 1px solid var(--border-color);
        text-align: center;
        min-height: 80px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }

    .day-card strong { font-size: 1.1em; display: block; }
    .day-card span { font-size: 0.8em; line-height: 1.2; }

    /* ألوان المناوبات بخط غامق وواضح */
    .shift-morning { background-color: #E6F3FF; color: #004085; }
    .shift-evening { background-color: #FFF2E6; color: #856404; }
    .shift-night   { background-color: #E6E6FA; color: #38006b; }
    .shift-rest    { background-color: #f8f9fa; color: #6c757d; }

</style>
""", unsafe_allow_html=True)

st.title("🗓️ جدول المناوبات الذكي Pro")
st.markdown("### نظام متكامل لعرض وإدارة جداول المناوبات")

# ==================================
# 2. تهيئة البيانات وإدارة الحالة
# ==================================
if 'doctors' not in st.session_state:
    st.session_state.doctors = [f"طبيب {i+1}" for i in range(65)]
if 'constraints' not in st.session_state:
    st.session_state.constraints = {doc: {"max_shifts": 18} for doc in st.session_state.doctors}
if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = None
if 'roster_view' not in st.session_state:
    st.session_state.roster_view = None

# ==================================
# 3. الخوارزمية (بدون تغيير)
# ==================================
@st.cache_data(ttl=600)
def generate_schedule_pro(num_days, doctors, constraints):
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
                            data.append({"الطبيب": doc, "اليوم": day + 1, "المناوبة": f"{shift} - {area}"})
        return pd.DataFrame(data)
    return None

# ==================================
# 4. دوال مساعدة
# ==================================
def create_roster_view(df, num_days, doctors):
    if df is None or df.empty:
        return pd.DataFrame(index=doctors, columns=range(1, num_days + 1)).fillna("راحة")
    roster = df.pivot_table(index="الطبيب", columns="اليوم", values="المناوبة", aggfunc='first').fillna("راحة")
    roster = roster.reindex(index=doctors, columns=range(1, num_days + 1), fill_value="راحة")
    return roster

def get_shift_class(shift_val):
    if "☀️" in shift_val: return "shift-morning"
    if "🌙" in shift_val: return "shift-evening"
    if "🌃" in shift_val: return "shift-night"
    return "shift-rest"

def display_cards_view(roster_df, year, month):
    arabic_weekdays = {"Sun": "الأحد", "Mon": "الاثنين", "Tue": "الثلاثاء", "Wed": "الأربعاء", "Thu": "الخميس", "Fri": "الجمعة", "Sat": "السبت"}
    for doctor in roster_df.index:
        with st.expander(f"👨‍⚕️ **{doctor}** - عرض الجدول الشهري"):
            cols = st.columns(7)
            for day in roster_df.columns:
                shift = roster_df.loc[doctor, day]
                shift_class = get_shift_class(shift)
                try:
                    weekday_abbr = calendar.day_abbr[calendar.weekday(year, month, day)]
                    weekday_name = arabic_weekdays.get(weekday_abbr, weekday_abbr)
                except (ValueError, TypeError):
                    weekday_name = ""
                with cols[(day - 1) % 7]:
                    st.markdown(f"""
                    <div class="day-card {shift_class}">
                        <strong>{day} <small>({weekday_name})</small></strong>
                        <span>{shift}</span>
                    </div>
                    """, unsafe_allow_html=True)

# ==================================
# 5. بناء الواجهة التفاعلية
# ==================================
tab1, tab2, tab3 = st.tabs(["📊 عرض الجدول", "👨‍⚕️ إدارة الأطباء", "📈 إحصائيات"])

with tab1:
    st.header("التحكم وعرض الجدول")
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            num_days_input = st.slider("🗓️ عدد أيام الشهر", 28, 31, 30, key="num_days")
            year_input = st.number_input("السنة", value=2025)
            month_input = st.number_input("الشهر", value=9, min_value=1, max_value=12)
        with col2:
            st.write("")
            if st.button("🚀 توليد / تحديث الجدول", use_container_width=True):
                with st.spinner("🧠 الخوارزمية تعمل بجد..."):
                    schedule = generate_schedule_pro(num_days_input, st.session_state.doctors, st.session_state.constraints)
                    st.session_state.schedule_df = schedule
                    roster = create_roster_view(schedule, num_days_input, st.session_state.doctors)
                    st.session_state.roster_view = roster
                    st.success("🎉 تم إنشاء الجدول بنجاح!")
            if 'roster_view' in st.session_state and st.session_state.roster_view is not None:
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    st.session_state.roster_view.to_excel(writer, sheet_name='جدول المناوبات')
                st.download_button("📥 تصدير إلى Excel", output.getvalue(), "جدول_المناوبات.xlsx", "application/vnd.ms-excel", use_container_width=True)
    
    st.divider()

    if 'roster_view' in st.session_state and st.session_state.roster_view is not None:
        st.subheader("📅 عرض الجدول بنظام البطاقات")
        display_cards_view(st.session_state.roster_view, year_input, month_input)
    else:
        st.info("اضغط على 'توليد الجدول الآن' لبدء العملية.")

with tab2:
    st.header("إدارة الأطباء والقيود")
    with st.expander("➕ إضافة طبيب جديد"):
        new_doc_name = st.text_input("اسم الطبيب الجديد")
        if st.button("إضافة الطبيب"):
            if new_doc_name and new_doc_name not in st.session_state.doctors:
                st.session_state.doctors.append(new_doc_name)
                st.session_state.constraints[new_doc_name] = {"max_shifts": 18}
                st.success(f"تمت إضافة الطبيب '{new_doc_name}'")
                st.rerun()
    st.subheader("📋 تعديل قيود الأطباء")
    for doc in st.session_state.doctors:
        with st.container(border=True):
            max_shifts = st.slider(f"أقصى عدد شفتات لـ **{doc}**", 1, 30, st.session_state.constraints.get(doc, {}).get('max_shifts', 18), key=f"max_{doc}")
            st.session_state.constraints[doc]['max_shifts'] = max_shifts

with tab3:
    st.header("تحليلات وإحصائيات")
    if 'schedule_df' in st.session_state and st.session_state.schedule_df is not None:
        df = st.session_state.schedule_df
        st.subheader("📊 عدد الشفتات لكل طبيب")
        st.bar_chart(df['الطبيب'].value_counts())
        st.subheader("🏢 توزيع الشفتات على الأقسام")
        df['القسم'] = df['المناوبة'].apply(lambda x: x.split(' - ')[-1])
        st.bar_chart(df['القسم'].value_counts())
    else:
        st.info("يجب توليد جدول أولاً لعرض الإحصائيات.")




