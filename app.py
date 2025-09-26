import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
from io import BytesIO

# ==================================
# 1. إعدادات التطبيق والواجهة العصرية
# ==================================
st.set_page_config(layout="wide", page_title="جدول المناوبات الذكي")

st.image("https://images.unsplash.com/photo-1576091160550-2173dba999ef?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3wzNzc0fDB8MXxzZWFyY2h8N3x8ZG9jdG9yJTIwc2NoZWR1bGV8ZW58MHx8fHwxNzI3MzQ4MTY0fDA&ixlib=rb-4.0.3&q=80&w=1080", use_column_width=True)
st.title("🗓️ جدول المناوبات الذكي")
st.markdown("واجهة عصرية لتوليد وتعديل جداول مناوبات الأطباء بذكاء وسهولة.")

# ==================================
# 2. البيانات الأساسية (نفس الخوارزمية)
# ==================================
SHIFTS = ["☀️ صبح", "🌙 مساء", "🌃 ليل"]
AREAS_MIN_COVERAGE = {"فرز": 2, "تنفسية": 1, "ملاحظة": 4, "انعاش": 3}
ALL_AREAS = list(AREAS_MIN_COVERAGE.keys())
NUM_DAYS = 30
ALL_DOCTORS = [f"طبيب {i+1}" for i in range(65)]

DOCTOR_CONSTRAINTS = {
    "طبيب 1": {"max_shifts": 16, "fixed_area": "انعاش", "fixed_shift": None},
    "طبيب 2": {"max_shifts": 16, "fixed_area": "انعاش", "fixed_shift": None},
    "طبيب 3": {"max_shifts": 18, "fixed_area": None, "fixed_shift": "☀️ صبح"},
    "طبيب 4": {"max_shifts": 18, "fixed_area": "فرز", "fixed_shift": None},
}

for doc in ALL_DOCTORS:
    if doc not in DOCTOR_CONSTRAINTS:
        DOCTOR_CONSTRAINTS[doc] = {"max_shifts": 18, "fixed_area": None, "fixed_shift": None}

# ==================================
# 3. دالة حل وتوليد الجدول (بدون تغيير في المنطق)
# ==================================
@st.cache_data(ttl=600) # تخزين النتائج مؤقتاً لتسريع الأداء
def generate_schedule():
    model = cp_model.CpModel()
    shifts_vars = {}
    for doc in ALL_DOCTORS:
        for day in range(NUM_DAYS):
            for shift in SHIFTS:
                for area in ALL_AREAS:
                    shifts_vars[(doc, day, shift, area)] = model.NewBoolVar(f"shift_{doc}_{day}_{shift}_{area}")

    for day in range(NUM_DAYS):
        for shift in SHIFTS:
            for area, min_count in AREAS_MIN_COVERAGE.items():
                model.Add(sum(shifts_vars[(doc, day, shift, area)] for doc in ALL_DOCTORS) >= min_count)
            total_doctors_in_shift = [shifts_vars[(doc, day, shift, area)] for doc in ALL_DOCTORS for area in ALL_AREAS]
            model.Add(sum(total_doctors_in_shift) >= 10)
            model.Add(sum(total_doctors_in_shift) <= 13)

    for day in range(NUM_DAYS):
        for doc in ALL_DOCTORS:
            model.Add(sum(shifts_vars[(doc, day, shift, area)] for shift in SHIFTS for area in ALL_AREAS) <= 1)

    for doc, constraints in DOCTOR_CONSTRAINTS.items():
        max_s = constraints.get("max_shifts", 18)
        model.Add(sum(shifts_vars[(doc, day, s, a)] for day in range(NUM_DAYS) for s in SHIFTS for a in ALL_AREAS) <= max_s)

    for doc in ALL_DOCTORS:
        for day in range(NUM_DAYS - 6):
            model.Add(sum(shifts_vars[(doc, d, s, a)] for d in range(day, day + 7) for s in SHIFTS for a in ALL_AREAS) <= 6)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 90.0
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        schedule_data = []
        for doc in ALL_DOCTORS:
            for day in range(NUM_DAYS):
                for shift in SHIFTS:
                    for area in ALL_AREAS:
                        if solver.Value(shifts_vars[(doc, day, shift, area)]) == 1:
                            schedule_data.append({"الطبيب": doc, "اليوم": day + 1, "المناوبة": f"{shift} - {area}"})
        return pd.DataFrame(schedule_data)
    return None

# ==================================
# 4. دالة عرض وتنسيق الجدول الجديد
# ==================================
def create_roster_view(df):
    if df is None or df.empty:
        return pd.DataFrame()
    
    roster = df.pivot_table(index="الطبيب", columns="اليوم", values="المناوبة", aggfunc='first').fillna("راحة")
    # التأكد من وجود جميع الأيام في الأعمدة
    all_days = [i for i in range(1, NUM_DAYS + 1)]
    roster = roster.reindex(columns=all_days, fill_value="راحة")
    return roster

def style_roster(roster_df):
    def get_color(val):
        if "☀️" in val: return "background-color: #E6F3FF"  # Light Blue for Morning
        if "🌙" in val: return "background-color: #FFF2E6"  # Light Orange for Evening
        if "🌃" in val: return "background-color: #E6E6FA"  # Lavender for Night
        return ""
    
    return roster_df.style.applymap(get_color)

# ==================================
# 5. بناء الواجهة التفاعلية
# ==================================
if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = None
    st.session_state.roster_view = None

with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    if st.button("🚀 توليد جدول جديد", use_container_width=True):
        with st.spinner("🧠 الخوارزمية تعمل... جاري تحليل آلاف الاحتمالات"):
            raw_schedule = generate_schedule()
            if raw_schedule is not None:
                st.session_state.schedule_df = raw_schedule
                st.session_state.roster_view = create_roster_view(raw_schedule)
                st.success("🎉 تم إنشاء الجدول بنجاح!")
            else:
                st.error("لم يتم العثور على حل. قد تكون الشروط متضاربة.")

if st.session_state.roster_view is not None:
    st.header("📅 عرض الجدول الشهري (Roster View)")
    st.markdown("هذا الجدول ملون لتسهيل القراءة. **يمكنك تعديل أي خانة مباشرة بالضغط عليها.**")

    # --- الجدول القابل للتعديل ---
    edited_roster = st.data_editor(st.session_state.roster_view, height=600, use_container_width=True)
    st.session_state.roster_view = edited_roster # حفظ التعديلات

    st.info("💡 بعد تعديل الجدول، يمكنك تصديره إلى Excel بالتنسيق الجديد.")

    # --- التصدير ---
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        edited_roster.to_excel(writer, sheet_name='جدول المناوبات')
    
    st.download_button(
        label="📥 تصدير الجدول المعدل إلى Excel",
        data=output.getvalue(),
        file_name="جدول_المناوبات_الشهري.xlsx",
        mime="application/vnd.ms-excel",
        use_container_width=True
    )

    st.header("🎨 عرض الجدول الملون (للقراءة فقط)")
    st.dataframe(style_roster(edited_roster), use_container_width=True)
else:
    st.info("اضغط على زر 'توليد جدول جديد' في الشريط الجانبي لبدء العملية.")
