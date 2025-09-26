import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
from io import BytesIO
import calendar

# ==================================
# 1. إعدادات التطبيق
# ==================================
st.set_page_config(layout="wide", page_title="جدول المناوبات الاحترافي")

# --- كود التصميم المخصص ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Tajawal', sans-serif; }
    .stApp { background-color: #f0f4f8; }
    h1, h2, h3 { text-align: center; }
</style>
""", unsafe_allow_html=True)

st.title("🗓️ جدول المناوبات الاحترافي (Roster View)")

# ==================================
# 2. تهيئة البيانات والخوارزمية (بدون تغيير)
# ==================================
if 'doctors' not in st.session_state: st.session_state.doctors = [f"طبيب {i+1}" for i in range(65)]
if 'constraints' not in st.session_state: st.session_state.constraints = {doc: {"max_shifts": 18} for doc in st.session_state.doctors}
if 'roster_df' not in st.session_state: st.session_state.roster_df = None

@st.cache_data(ttl=600)
def generate_schedule_final(num_days, doctors, constraints):
    SHIFTS = ["☀️", "🌙", "🌃"]
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
# 4. دوال إنشاء وتلوين الجدول الاحترافي
# ==================================
def create_roster_dataframe(df, doctors_list, num_days):
    if df is None:
        return pd.DataFrame(index=doctors_list, columns=range(1, num_days + 1)).fillna("راحة")
    
    # دمج المناوبة والقسم في خلية واحدة
    df['cell_value'] = df['المناوبة'] + " - " + df['القسم']
    
    roster = df.pivot_table(index="الطبيب", columns="اليوم", values="cell_value", aggfunc='first')
    roster = roster.reindex(index=doctors_list, columns=range(1, num_days + 1)).fillna("راحة")
    return roster

def apply_roster_styling(styler):
    def get_color(val):
        val = str(val)
        if "☀️" in val: return "background-color: #FFF3CD; color: #664D03;"  # Yellow
        if "🌙" in val: return "background-color: #FFDDC2; color: #6F4A2B;"  # Orange
        if "🌃" in val: return "background-color: #D1E7DD; color: #0F5132;"  # Green
        if "راحة" in val: return "background-color: #F8F9FA; color: #6C757D;"  # Gray
        return ""
    
    styler.applymap(get_color)
    styler.set_properties(**{
        'border': '1px solid #dee2e6',
        'text-align': 'center',
        'font-size': '14px',
    })
    styler.format(lambda val: val.replace("☀️ - ", "").replace("🌙 - ", "").replace("🌃 - ", "") if isinstance(val, str) else val)
    styler.set_table_styles([
        {'selector': 'th', 'props': [('background-color', '#343A40'), ('color', 'white'), ('font-size', '16px')]},
        {'selector': 'th.row_heading', 'props': [('text-align', 'right'), ('font-weight', 'bold')]},
    ])
    return styler

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
        with st.spinner("🧠 الخوارزمية تعمل على إيجاد أفضل توزيع..."):
            schedule = generate_schedule_final(num_days_input, st.session_state.doctors, st.session_state.constraints)
            if schedule is not None:
                st.session_state.roster_df = create_roster_dataframe(schedule, st.session_state.doctors, num_days_input)
                st.success("🎉 تم إنشاء الجدول بنجاح!")
            else:
                st.error("لم يتم العثور على حل.")

# --- العرض الرئيسي ---
if st.session_state.roster_df is not None:
    st.header("🗓️ الجدول الشهري للمناوبات (للعرض)")
    st.dataframe(st.session_state.roster_df.style.pipe(apply_roster_styling), height=800)
    
    with st.expander("✏️ تعديل الجدول يدويًا"):
        st.info("يمكنك تعديل أي خانة بالضغط عليها. التعديلات ستنعكس على ملف Excel عند التصدير.")
        edited_df = st.data_editor(st.session_state.roster_df, height=800)
        st.session_state.roster_df = edited_df

    st.header("📥 تصدير إلى Excel")
    output = BytesIO()
    # سنقوم بتصدير النسخة المعدلة يدويًا
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        st.session_state.roster_df.to_excel(writer, sheet_name='جدول المناوبات')
    
    st.download_button(
        label="📊 تنزيل جدول Excel",
        data=output.getvalue(),
        file_name=f"جدول_مناوبات_{year_input}_{month_input:02d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
else:
    st.info("اضغط على 'توليد الجدول' في الشريط الجانبي لبدء العملية.")
