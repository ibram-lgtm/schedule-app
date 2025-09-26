import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
from io import BytesIO

# ==================================
# 1. إعدادات التطبيق والواجهة العصرية
# ==================================
st.set_page_config(layout="wide", page_title="جدول المناوبات الذكي")

# --- ستايل CSS مخصص ---
st.markdown("""
<style>
    /* تحسين الخطوط والألوان */
    .stApp {
        background-color: #f0f4f8;
    }
    .st-emotion-cache-16txtl3 {
        padding: 2rem 1.5rem;
    }
    h1 {
        color: #667eea;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .stButton>button {
        background-color: #667eea;
        color: white;
        border-radius: 10px;
        border: none;
        padding: 10px 20px;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #764ba2;
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

st.image("https://images.unsplash.com/photo-1576091160550-2173dba999ef?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3wzNzc0fDB8MXxzZWFyY2h8N3x8ZG9jdG9yJTIwc2NoZWR1bGV8ZW58MHx8fHwxNzI3MzQ4MTY0fDA&ixlib=rb-4.0.3&q=80&w=1080", use_column_width=True)
st.title("🗓️ جدول المناوبات الذكي")
st.markdown("### واجهة عصرية لتوليد وتعديل جداول مناوبات الأطباء بذكاء وسهولة.")

# ==================================
# 2. البيانات الأساسية (أصبحت تفاعلية)
# ==================================
with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    NUM_DAYS = st.slider("عدد أيام الشهر", 28, 31, 30)
    NUM_DOCTORS = st.number_input("عدد الأطباء الإجمالي", min_value=10, max_value=100, value=65)

SHIFTS = ["☀️ صبح", "🌙 مساء", "🌃 ليل"]
AREAS_MIN_COVERAGE = {"فرز": 2, "تنفسية": 1, "ملاحظة": 4, "انعاش": 3}
ALL_AREAS = list(AREAS_MIN_COVERAGE.keys())
ALL_DOCTORS = [f"طبيب {i+1}" for i in range(NUM_DOCTORS)]

# --- قيود الأطباء (يمكن تطويرها لتكون ديناميكية) ---
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
# 3. دالة حل وتوليد الجدول (مع تحسينات طفيفة)
# ==================================
@st.cache_data(ttl=600)
def generate_schedule(num_days, all_doctors, doctor_constraints):
    model = cp_model.CpModel()
    shifts_vars = {}
    for doc in all_doctors:
        for day in range(num_days):
            for shift in SHIFTS:
                for area in ALL_AREAS:
                    shifts_vars[(doc, day, shift, area)] = model.NewBoolVar(f"shift_{doc}_{day}_{shift}_{area}")

    for day in range(num_days):
        for shift in SHIFTS:
            for area, min_count in AREAS_MIN_COVERAGE.items():
                model.Add(sum(shifts_vars[(doc, day, shift, area)] for doc in all_doctors) >= min_count)
            total_doctors_in_shift = [shifts_vars[(doc, day, shift, area)] for doc in all_doctors for area in ALL_AREAS]
            model.Add(sum(total_doctors_in_shift) >= 10)
            model.Add(sum(total_doctors_in_shift) <= 13)

    for day in range(num_days):
        for doc in all_doctors:
            model.Add(sum(shifts_vars[(doc, day, shift, area)] for shift in SHIFTS for area in ALL_AREAS) <= 1)

    for doc, constraints in doctor_constraints.items():
        if doc in all_doctors:
            max_s = constraints.get("max_shifts", 18)
            model.Add(sum(shifts_vars[(doc, day, s, a)] for day in range(num_days) for s in SHIFTS for a in ALL_AREAS) <= max_s)

    for doc in all_doctors:
        for day in range(num_days - 6):
            model.Add(sum(shifts_vars[(doc, d, s, a)] for d in range(day, day + 7) for s in SHIFTS for a in ALL_AREAS) <= 6)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 90.0
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        schedule_data = []
        for doc in all_doctors:
            for day in range(num_days):
                for shift in SHIFTS:
                    for area in ALL_AREAS:
                        if solver.Value(shifts_vars[(doc, day, shift, area)]) == 1:
                            schedule_data.append({"الطبيب": doc, "اليوم": day + 1, "المناوبة": f"{shift} - {area}"})
        return pd.DataFrame(schedule_data)
    return None

# ==================================
# 4. دالة عرض وتنسيق الجدول الجديد (مع تحسينات)
# ==================================
def create_roster_view(df, num_days):
    if df is None or df.empty:
        return pd.DataFrame()
    
    roster = df.pivot_table(index="الطبيب", columns="اليوم", values="المناوبة", aggfunc='first').fillna("راحة")
    all_days = [i for i in range(1, num_days + 1)]
    roster = roster.reindex(columns=all_days, fill_value="راحة")
    return roster

def style_roster(roster_df):
    def get_color(val):
        if "☀️" in val: return "background-color: #E6F3FF"
        if "🌙" in val: return "background-color: #FFF2E6"
        if "🌃" in val: return "background-color: #E6E6FA"
        if "راحة" in val: return "background-color: #f8f9fa"
        return ""
    
    return roster_df.style.applymap(get_color)

# ==================================
# 5. بناء الواجهة التفاعلية المحسّنة
# ==================================
if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = None
    st.session_state.roster_view = None

with st.sidebar:
    if st.button("🚀 توليد جدول جديد", use_container_width=True):
        with st.spinner("🧠 الخوارزمية تعمل... جاري تحليل آلاف الاحتمالات، قد يستغرق الأمر دقيقة..."):
            raw_schedule = generate_schedule(NUM_DAYS, ALL_DOCTORS, DOCTOR_CONSTRAINTS)
            if raw_schedule is not None:
                st.session_state.schedule_df = raw_schedule
                st.session_state.roster_view = create_roster_view(raw_schedule, NUM_DAYS)
                st.success("🎉 تم إنشاء الجدول بنجاح!")
            else:
                st.error("لم يتم العثور على حل. قد تكون الشروط متضاربة أو تحتاج إلى وقت أطول للمعالجة.")

if st.session_state.roster_view is not None:
    st.header("📅 عرض الجدول الشهري (Roster View)")
    st.markdown("هذا الجدول **قابل للتعديل مباشرة**. يمكنك تعديل أي خانة بالضغط عليها.")

    edited_roster = st.data_editor(st.session_state.roster_view, height=600, use_container_width=True)
    st.session_state.roster_view = edited_roster

    st.info("💡 بعد تعديل الجدول، يمكنك تصديره إلى Excel بالتنسيق الجديد.")

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

