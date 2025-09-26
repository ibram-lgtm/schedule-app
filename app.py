import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
from io import BytesIO

# ==================================
# 1. إعدادات التطبيق والواجهة الاحترافية مع دعم الوضع الليلي/النهاري
# ==================================
st.set_page_config(layout="wide", page_title="جدول المناوبات الذكي Pro")

# --- ستايل CSS مخصص واحترافي ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    
    html, body, [class*="st-"] {
        font-family: 'Tajawal', sans-serif;
    }

    /* === Light Mode Colors === */
    :root {
        --primary-color: #667eea;
        --secondary-color: #764ba2;
        --background-color: #f0f4f8;
        --text-color: #262730;
        --tab-bg: #f0f4f8;
        --tab-selected-bg: #667eea;
        --tab-selected-color: white;
    }

    /* === Dark Mode Colors === */
    body[data-theme="dark"] {
        --primary-color: #8A98F7;
        --secondary-color: #9B70E0;
        --background-color: #0e1117;
        --text-color: #fafafa;
        --tab-bg: #262730;
        --tab-selected-bg: #8A98F7;
        --tab-selected-color: #0e1117;
    }
    
    .stApp {
        background-color: var(--background-color);
    }
    
    h1, h2, h3 {
        color: var(--primary-color);
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: var(--tab-bg);
        border-radius: 4px 4px 0 0;
        color: var(--text-color);
    }
    
    .stTabs [aria-selected="true"] {
        background-color: var(--tab-selected-bg);
        color: var(--tab-selected-color);
        font-weight: bold;
    }
    
    .stButton>button {
        background-image: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
        color: white;
        border-radius: 10px;
        border: none;
        padding: 10px 20px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .stButton>button:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.15);
    }
</style>
""", unsafe_allow_html=True)

st.title("🗓️ جدول المناوبات الذكي Pro")
st.markdown("### نظام متكامل لتوليد وتخصيص جداول المناوبات الطبية بكفاءة ومرونة")

# ==================================
# 2. تهيئة البيانات وإدارة الحالة
# ==================================
if 'doctors' not in st.session_state:
    st.session_state.doctors = [f"طبيب {i+1}" for i in range(65)]
if 'constraints' not in st.session_state:
    st.session_state.constraints = {doc: {"max_shifts": 18} for doc in st.session_state.doctors}
if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = None

# ==================================
# 3. الخوارزمية (بدون تغيير في المنطق الأساسي)
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
# 4. دوال مساعدة (عرض وتنسيق)
# ==================================
def create_roster_view_pro(df, num_days, doctors):
    if df is None or df.empty:
        return pd.DataFrame(index=doctors, columns=range(1, num_days + 1)).fillna("راحة")
    
    roster = df.pivot_table(index="الطبيب", columns="اليوم", values="المناوبة", aggfunc='first').fillna("راحة")
    roster = roster.reindex(index=doctors, columns=range(1, num_days + 1), fill_value="راحة")
    return roster

def style_roster_pro(roster_df):
    def get_color(val):
        colors = {
            "☀️": "#E6F3FF", "🌙": "#FFF2E6", "🌃": "#E6E6FA",
            "فرز": "#FFEBE6", "تنفسية": "#E6FFFA", "ملاحظة": "#F9E6FF", "انعاش": "#FFFAE6"
        }
        for key, color in colors.items():
            if key in val: return f"background-color: {color}"
        return "background-color: #f8f9fa" if "راحة" in val else ""
    return roster_df.style.applymap(get_color)

# ==================================
# 5. بناء الواجهة التفاعلية باستخدام التبويبات
# ==================================
tab1, tab2, tab3 = st.tabs(["📊 لوحة التحكم الرئيسية", "👨‍⚕️ إدارة الأطباء والقيود", "📈 إحصائيات وتحليلات"])

with tab1:
    st.header("التحكم في توليد الجدول")
    col1, col2 = st.columns(2)
    with col1:
        num_days_input = st.slider("🗓️ عدد أيام الشهر", 28, 31, 30, key="num_days")
    with col2:
        if st.button("🚀 توليد الجدول الآن", use_container_width=True):
            with st.spinner("🧠 الخوارزمية تعمل بجد... قد يستغرق الأمر ما يصل إلى دقيقتين..."):
                schedule = generate_schedule_pro(num_days_input, st.session_state.doctors, st.session_state.constraints)
                st.session_state.schedule_df = schedule
                if schedule is not None:
                    st.success("🎉 تم إنشاء الجدول بنجاح!")
                else:
                    st.error("لم يتم العثور على حل. حاول تخفيف القيود أو زيادة مدة البحث.")

    if st.session_state.schedule_df is not None:
        roster = create_roster_view_pro(st.session_state.schedule_df, num_days_input, st.session_state.doctors)
        st.subheader("📅 عرض الجدول (قابل للتعديل)")
        edited_roster = st.data_editor(roster, height=600, use_container_width=True)

        st.subheader("📥 تصدير الجدول")
        output = BytesIO()
        # استخدام try-except للتعامل مع أي خطأ في التصدير
        try:
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                edited_roster.to_excel(writer, sheet_name='جدول المناوبات')
            
            st.download_button(
                label="تصدير إلى Excel",
                data=output.getvalue(),
                file_name="جدول_المناوبات_الشهري.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True
            )
        except ImportError:
            st.error("خطأ في التصدير: مكتبة 'xlsxwriter' غير مثبتة. الرجاء إضافتها إلى ملف requirements.txt.")
    else:
        st.info("اضغط على 'توليد الجدول الآن' لبدء العملية.")

with tab2:
    st.header("إدارة الأطباء والقيود الخاصة بهم")
    
    with st.expander("➕ إضافة طبيب جديد"):
        new_doc_name = st.text_input("اسم الطبيب الجديد")
        if st.button("إضافة الطبيب"):
            if new_doc_name and new_doc_name not in st.session_state.doctors:
                st.session_state.doctors.append(new_doc_name)
                st.session_state.constraints[new_doc_name] = {"max_shifts": 18}
                st.success(f"تمت إضافة الطبيب '{new_doc_name}'")
                st.rerun()
            else:
                st.warning("الرجاء إدخال اسم فريد للطبيب.")

    st.subheader("📋 قائمة الأطباء والقيود الحالية")
    all_docs = st.session_state.doctors
    constraints_copy = st.session_state.constraints.copy()

    for doc in all_docs:
        with st.container():
            col1, col2 = st.columns([3, 2])
            with col1:
                st.write(f"**{doc}**")
            with col2:
                max_shifts = st.number_input(f"أقصى عدد شفتات لـ {doc}", 1, 30, constraints_copy.get(doc, {}).get('max_shifts', 18), key=f"max_{doc}")
                st.session_state.constraints[doc]['max_shifts'] = max_shifts

with tab3:
    st.header("تحليلات وإحصائيات الجدول")
    if st.session_state.schedule_df is not None and not st.session_state.schedule_df.empty:
        df = st.session_state.schedule_df
        
        st.subheader("📊 عدد الشفتات لكل طبيب")
        shift_counts = df['الطبيب'].value_counts()
        st.bar_chart(shift_counts)

        st.subheader("🏢 توزيع الشفتات على الأقسام")
        df['القسم'] = df['المناوبة'].apply(lambda x: x.split(' - ')[-1])
        area_counts = df['القسم'].value_counts()
        st.bar_chart(area_counts)
    else:
        st.info("يجب توليد جدول أولاً لعرض الإحصائيات.")



