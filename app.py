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
        color: #121212;
    }

    :root {
        --primary-color: #667eea;
        --background-color: #f0f4f8;
        --card-bg: white;
        --border-color: #e9ecef;
        --tab-selected-bg: #667eea;
        --tab-selected-color: white;
    }

    .stApp { background-color: var(--background-color); }
    h1, h2, h3 { color: var(--primary-color); }
    .stTabs [aria-selected="true"] { background-color: var(--tab-selected-bg); color: var(--tab-selected-color) !important; font-weight: bold; }

    /* Daily View Styles */
    .daily-view-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
        gap: 15px;
    }
    .day-column {
        background-color: var(--card-bg);
        border-radius: 10px;
        padding: 15px;
        border: 1px solid var(--border-color);
    }
    .day-column h4 {
        border-bottom: 2px solid var(--border-color);
        padding-bottom: 10px;
        margin-bottom: 10px;
    }
    .shift-group h5 {
        font-weight: bold;
        margin-top: 15px;
        margin-bottom: 5px;
    }
    .doctor-card {
        background-color: #f8f9fa;
        border-radius: 6px;
        padding: 8px;
        margin-bottom: 5px;
        font-size: 0.9em;
        border-left: 5px solid var(--primary-color);
    }
    
    /* Employee View Styles */
    .employee-day-card {
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
    .employee-day-card strong { font-size: 1.1em; display: block; }
    .employee-day-card span { font-size: 0.8em; line-height: 1.2; }
    .shift-morning { background-color: #E6F3FF; color: #004085; }
    .shift-evening { background-color: #FFF2E6; color: #856404; }
    .shift-night   { background-color: #E6E6FA; color: #38006b; }
    .shift-rest    { background-color: #f8f9fa; color: #6c757d; }

</style>
""", unsafe_allow_html=True)

st.title("🗓️ جدول المناوبات الذكي Pro")
st.markdown("### نظام متكامل مع عرض يومي وعرض لكل طبيب")

# ==================================
# 2. تهيئة البيانات وإدارة الحالة
# ==================================
if 'doctors' not in st.session_state: st.session_state.doctors = [f"طبيب {i+1}" for i in range(65)]
if 'constraints' not in st.session_state: st.session_state.constraints = {doc: {"max_shifts": 18} for doc in st.session_state.doctors}
if 'schedule_df' not in st.session_state: st.session_state.schedule_df = None
if 'roster_view' not in st.session_state: st.session_state.roster_view = None

# ==================================
# 3. الخوارزمية (بدون تغيير)
# ==================================
@st.cache_data(ttl=600)
def generate_schedule_pro(num_days, doctors, constraints):
    # ... (نفس الكود السابق للخوارزمية)
    # This function is unchanged.
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
                            data.append({"الطبيب": doc, "اليوم": day + 1, "المناوبة": f"{shift}", "القسم": area})
        return pd.DataFrame(data)
    return None

# ==================================
# 4. دوال العرض الجديدة والمحسّنة
# ==================================
def create_roster_view(df, num_days, doctors):
    if df is None or df.empty:
        return pd.DataFrame(index=doctors, columns=range(1, num_days + 1)).fillna("راحة")
    roster = df.pivot_table(index="الطبيب", columns="اليوم", values="المناوبة", aggfunc='first').fillna("راحة")
    roster = roster.reindex(index=doctors, columns=range(1, num_days + 1), fill_value="راحة")
    return roster

def display_daily_view(df, year, month):
    st.markdown('<div class="daily-view-grid">', unsafe_allow_html=True)
    for day in range(1, month_days(year, month) + 1):
        st.markdown(f'<div class="day-column">', unsafe_allow_html=True)
        day_df = df[df['اليوم'] == day]
        weekday_name = get_weekday_name(year, month, day)
        st.markdown(f"<h4>اليوم {day} <small>({weekday_name})</small></h4>", unsafe_allow_html=True)
        
        if day_df.empty:
            st.write("لا توجد مناوبات لهذا اليوم.")
        else:
            for shift_name in ["☀️ صبح", "🌙 مساء", "🌃 ليل"]:
                shift_df = day_df[day_df['المناوبة'] == shift_name]
                if not shift_df.empty:
                    st.markdown(f'<h5>{shift_name}</h5>', unsafe_allow_html=True)
                    for _, row in shift_df.iterrows():
                        st.markdown(f'<div class="doctor-card">{row["الطبيب"]} - {row["القسم"]}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def display_employee_view(roster_df, year, month):
    for doctor in roster_df.index:
        with st.expander(f"👨‍⚕️ **{doctor}** - عرض الجدول الشهري"):
            cols = st.columns(7)
            for day in roster_df.columns:
                shift = roster_df.loc[doctor, day]
                shift_class = get_shift_class(shift)
                weekday_name = get_weekday_name(year, month, day)
                with cols[(day - 1) % 7]:
                    st.markdown(f'<div class="employee-day-card {shift_class}"><strong>{day} <small>({weekday_name})</small></strong><span>{shift}</span></div>', unsafe_allow_html=True)

def get_weekday_name(year, month, day):
    try:
        arabic_weekdays = {"Sun": "الأحد", "Mon": "الاثنين", "Tue": "الثلاثاء", "Wed": "الأربعاء", "Thu": "الخميس", "Fri": "الجمعة", "Sat": "السبت"}
        weekday_abbr = calendar.day_abbr[calendar.weekday(year, month, day)]
        return arabic_weekdays.get(weekday_abbr, weekday_abbr)
    except (ValueError, TypeError):
        return ""

def month_days(year, month):
    return calendar.monthrange(year, month)[1]

def get_shift_class(shift_val):
    if "☀️" in shift_val: return "shift-morning"
    if "🌙" in shift_val: return "shift-evening"
    if "🌃" in shift_val: return "shift-night"
    return "shift-rest"
# ==================================
# 5. بناء الواجهة التفاعلية
# ==================================
tab1, tab2, tab3, tab4 = st.tabs(["📅 العرض اليومي", "👨‍⚕️ العرض لكل طبيب", "⚙️ إدارة الأطباء", "📈 إحصائيات"])

with st.sidebar:
    st.header("التحكم في الجدول")
    year_input = st.number_input("السنة", value=2025)
    month_input = st.number_input("الشهر", value=9, min_value=1, max_value=12)
    num_days_input = month_days(year_input, month_input)
    st.info(f"عدد أيام الشهر المحدد: {num_days_input} يوم")
    
    if st.button("🚀 توليد / تحديث الجدول", use_container_width=True):
        with st.spinner("🧠 الخوارزمية تعمل بجد..."):
            schedule = generate_schedule_pro(num_days_input, st.session_state.doctors, st.session_state.constraints)
            if schedule is not None:
                st.session_state.schedule_df = schedule
                roster = create_roster_view(schedule, num_days_input, st.session_state.doctors)
                st.session_state.roster_view = roster
                st.success("🎉 تم إنشاء الجدول بنجاح!")
            else:
                st.error("لم يتم العثور على حل. حاول تغيير القيود.")
    
    if st.session_state.schedule_df is not None:
        st.divider()
        st.header("📥 تصدير إلى Excel")
        output = BytesIO()
        export_df = st.session_state.schedule_df.pivot_table(index="اليوم", columns="المناوبة", values="الطبيب", aggfunc=lambda x: '، '.join(x))
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            export_df.to_excel(writer, sheet_name='جدول المناوبات اليومي')
            st.session_state.roster_view.to_excel(writer, sheet_name='جدول الأطباء')
        st.download_button("تنزيل ملف Excel", output.getvalue(), "جدول_المناوبات_الكامل.xlsx", "application/vnd.ms-excel", use_container_width=True)

with tab1:
    st.header("📅 العرض اليومي للمناوبات")
    if st.session_state.schedule_df is not None:
        display_daily_view(st.session_state.schedule_df, year_input, month_input)
    else:
        st.info("اضغط على 'توليد الجدول' في الشريط الجانبي لبدء العملية.")

with tab2:
    st.header("👨‍⚕️ عرض المناوبات لكل طبيب")
    if st.session_state.roster_view is not None:
        display_employee_view(st.session_state.roster_view, year_input, month_input)
    else:
        st.info("يجب توليد جدول أولاً لعرض البيانات.")

with tab3:
    st.header("⚙️ إدارة الأطباء والقيود")
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

with tab4:
    st.header("📈 تحليلات وإحصائيات")
    if st.session_state.schedule_df is not None:
        df = st.session_state.schedule_df
        st.subheader("📊 عدد الشفتات لكل طبيب")
        st.bar_chart(df['الطبيب'].value_counts())
        st.subheader("🏢 توزيع الأطباء على الأقسام")
        st.bar_chart(df['القسم'].value_counts())
    else:
        st.info("يجب توليد جدول أولاً لعرض الإحصائيات.")



