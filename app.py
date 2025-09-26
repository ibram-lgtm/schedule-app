import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
from io import BytesIO

# ==================================
# 1. إعدادات الصفحة وحقن الأنماط (CSS)
# ==================================
st.set_page_config(layout="wide", page_title="نظام الشفتات الطبي")

# نسخ الـ CSS من ملف HTML وحقنه في الصفحة
CSS = """
:root {
    --primary-color: #667eea;
    --secondary-color: #764ba2;
    --light-gray: #f0f4f8;
    --white: #fff;
    --dark-gray: #495057;
    --border-color: #e9ecef;
}
.stApp {
    background: var(--light-gray);
}
.header {
    background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
    color: var(--white);
    padding: 2rem;
    border-radius: 15px;
    text-align: center;
    margin-bottom: 20px;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}
.controls-card, .table-card {
    background: var(--white);
    padding: 25px;
    border-radius: 15px;
    margin-bottom: 20px;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
}
/* تخصيص شكل الأزرار */
.stButton>button {
    width: 100%;
    border-radius: 10px;
    font-weight: 600;
    padding: 12px;
    border: none;
    color: white;
    background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
    transition: all 0.3s ease;
}
.stButton>button:hover {
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
    color: white;
    border: none;
}
"""
st.markdown(f'<style>{CSS}</style>', unsafe_allow_html=True)

# ==================================
# 2. البيانات الأساسية والخوارزمية (بدون تغيير)
# ==================================
SHIFTS = ["☀️ صبح", "🌙 مساء", "🌃 ليل"]
AREAS_MIN_COVERAGE = {"فرز": 2, "تنفسية": 1, "ملاحظة": 4, "انعاش": 3}
ALL_AREAS = list(AREAS_MIN_COVERAGE.keys())
NUM_DAYS = 30

@st.cache_data(ttl=600)
def generate_schedule(doctors_list):
    model = cp_model.CpModel()
    shifts_vars = {}
    for doc in doctors_list:
        for day in range(NUM_DAYS):
            for shift in SHIFTS:
                for area in ALL_AREAS:
                    shifts_vars[(doc, day, shift, area)] = model.NewBoolVar(f"shift_{doc}_{day}_{shift}_{area}")

    for day in range(NUM_DAYS):
        for shift in SHIFTS:
            for area, min_count in AREAS_MIN_COVERAGE.items():
                model.Add(sum(shifts_vars[(doc, day, shift, area)] for doc in doctors_list) >= min_count)
            total_doctors_in_shift = [shifts_vars[(doc, day, shift, area)] for doc in doctors_list for area in ALL_AREAS]
            model.Add(sum(total_doctors_in_shift) >= 10)
            model.Add(sum(total_doctors_in_shift) <= 13)

    for day in range(NUM_DAYS):
        for doc in doctors_list:
            model.Add(sum(shifts_vars[(doc, day, shift, area)] for shift in SHIFTS for area in ALL_AREAS) <= 1)

    for doc in doctors_list:
        model.Add(sum(shifts_vars[(doc, d, s, a)] for d in range(NUM_DAYS) for s in SHIFTS for a in ALL_AREAS) <= 18)
        for day in range(NUM_DAYS - 6):
            model.Add(sum(shifts_vars[(doc, d, s, a)] for d in range(day, day + 7) for s in SHIFTS for a in ALL_AREAS) <= 6)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 90.0
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        schedule_data = []
        for doc in doctors_list:
            for day in range(NUM_DAYS):
                for shift in SHIFTS:
                    for area in ALL_AREAS:
                        if solver.Value(shifts_vars[(doc, day, shift, area)]) == 1:
                            schedule_data.append({"الطبيب": doc, "اليوم": day + 1, "المناوبة": f"{shift} - {area}"})
        return pd.DataFrame(schedule_data)
    return None

def create_roster_view(df, doctors_list):
    if df is None or df.empty:
        # إنشاء جدول فارغ إذا لم يتم العثور على حل
        empty_roster = pd.DataFrame(index=doctors_list, columns=range(1, NUM_DAYS + 1)).fillna("راحة")
        return empty_roster

    roster = df.pivot_table(index="الطبيب", columns="اليوم", values="المناوبة", aggfunc='first').fillna("راحة")
    all_days = [i for i in range(1, NUM_DAYS + 1)]
    roster = roster.reindex(columns=all_days, index=doctors_list, fill_value="راحة")
    return roster

# ==================================
# 3. بناء الواجهة التفاعلية بالتصميم الجديد
# ==================================

# --- Header ---
st.markdown('<div class="header"><h1>🏥 نظام إدارة الشفتات الطبي</h1></div>', unsafe_allow_html=True)

# --- State Management ---
if 'doctors' not in st.session_state:
    st.session_state.doctors = [f"طبيب {i+1}" for i in range(65)]
if 'roster_view' not in st.session_state:
    st.session_state.roster_view = create_roster_view(None, st.session_state.doctors)
if 'show_add_doctor' not in st.session_state:
    st.session_state.show_add_doctor = False

# --- Controls Card ---
with st.container():
    st.markdown('<div class="controls-card">', unsafe_allow_html=True)
    
    cols = st.columns(4)
    with cols[0]:
        if st.button("🎯 إنشاء / تحديث الجدول", use_container_width=True):
            with st.spinner("🧠 الخوارزمية تعمل... جاري تحليل آلاف الاحتمالات"):
                raw_schedule = generate_schedule(st.session_state.doctors)
                if raw_schedule is not None:
                    st.session_state.roster_view = create_roster_view(raw_schedule, st.session_state.doctors)
                    st.toast("🎉 تم إنشاء الجدول بنجاح!", icon="🎉")
                else:
                    st.error("لم يتم العثور على حل. قد تكون الشروط متضاربة.")

    with cols[1]:
        if st.button("👨‍⚕️ إضافة طبيب", use_container_width=True):
            st.session_state.show_add_doctor = not st.session_state.show_add_doctor

    with cols[2]:
        # زر التصدير سيكون بالأسفل بعد الجدول
        st.write("") 

    with cols[3]:
        st.write("") 

    # --- نموذج إضافة طبيب (بديل للـ Modal) ---
    if st.session_state.show_add_doctor:
        with st.form("new_doctor_form"):
            st.subheader("👨‍⚕️ إضافة طبيب جديد")
            new_doctor_name = st.text_input("اسم الطبيب")
            submitted = st.form_submit_button("إضافة")
            if submitted and new_doctor_name:
                if new_doctor_name not in st.session_state.doctors:
                    st.session_state.doctors.append(new_doctor_name)
                    # تحديث الجدول الفارغ ليشمل الطبيب الجديد
                    st.session_state.roster_view = create_roster_view(None, st.session_state.doctors)
                    st.toast(f"تمت إضافة الطبيب {new_doctor_name}", icon="👨‍⚕️")
                    st.session_state.show_add_doctor = False
                    st.experimental_rerun()
                else:
                    st.warning("هذا الطبيب موجود بالفعل.")

    st.markdown('</div>', unsafe_allow_html=True)


# --- Table Card ---
with st.container():
    st.markdown('<div class="table-card">', unsafe_allow_html=True)
    
    st.header("📅 عرض الجدول الشهري (قابل للتعديل)")
    st.markdown("يمكنك تعديل أي خانة مباشرة بالضغط عليها. التغييرات تنحفظ تلقائيًا.")
    
    edited_roster = st.data_editor(st.session_state.roster_view, height=800, use_container_width=True)
    
    # حفظ التعديلات اليدوية
    if not edited_roster.equals(st.session_state.roster_view):
        st.session_state.roster_view = edited_roster
        st.toast("تم حفظ التعديل اليدوي", icon="📝")

    # --- زر التصدير ---
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        st.session_state.roster_view.to_excel(writer, sheet_name='جدول المناوبات')
    
    st.download_button(
        label="📥 تصدير الجدول إلى Excel",
        data=output.getvalue(),
        file_name="جدول_المناوبات_الشهري.xlsx",
        mime="application/vnd.ms-excel"
    )

    st.markdown('</div>', unsafe_allow_html=True)


