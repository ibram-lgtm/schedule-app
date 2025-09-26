import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
from io import BytesIO
import calendar

# ==================================
# 1. إعدادات التطبيق والواجهة
# ==================================
st.set_page_config(layout="wide", page_title="جدول المناوبات الذكي Pro")

# --- كود التصميم المخصص ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Tajawal', sans-serif; color: #121212; }
    :root { --primary-color: #667eea; --background-color: #f0f4f8; --card-bg: white; --border-color: #e9ecef; }
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

st.title("🗓️ جدول المناوبات الذكي Pro")
st.markdown("### نظام متكامل لعرض وإدارة وتصدير جداول المناوبات")

# ==================================
# 2. تهيئة البيانات
# ==================================
if 'doctors' not in st.session_state: st.session_state.doctors = [f"طبيب {i+1}" for i in range(65)]
if 'constraints' not in st.session_state: st.session_state.constraints = {doc: {"max_shifts": 18} for doc in st.session_state.doctors}
if 'schedule_df' not in st.session_state: st.session_state.schedule_df = None

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
                            data.append({"الطبيب": doc, "اليوم": day + 1, "المناوبة": f"{shift}", "القسم": area})
        return pd.DataFrame(data)
    return None

# ==================================
# 4. دوال العرض والتصدير
# ==================================
def create_styled_excel(df, roster_df, year, month):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # ورقة العرض اليومي
        daily_view = df.pivot_table(index=["اليوم", "المناوبة"], columns="القسم", values="الطبيب", aggfunc=lambda x: ', '.join(x)).fillna('')
        daily_view.to_excel(writer, sheet_name="العرض اليومي")

        # ورقة عرض الأطباء (الملونة)
        roster_df.to_excel(writer, sheet_name="عرض الأطباء")
        
        workbook = writer.book
        worksheet = writer.sheets["عرض الأطباء"]
        
        # تعريف التنسيقات الملونة
        colors = {
            "☀️": workbook.add_format({'bg_color': '#E6F3FF', 'font_color': '#004085'}),
            "🌙": workbook.add_format({'bg_color': '#FFF2E6', 'font_color': '#856404'}),
            "🌃": workbook.add_format({'bg_color': '#E6E6FA', 'font_color': '#38006b'}),
        }

        # تطبيق التنسيق على الخلايا
        for col_num, value in enumerate(roster_df.columns.values):
            for row_num, val_cell in enumerate(roster_df[value]):
                for key, color_format in colors.items():
                    if key in str(val_cell):
                        worksheet.write(row_num + 1, col_num + 1, val_cell, color_format)
                        break
        
        # ضبط عرض الأعمدة
        worksheet.set_column(0, 0, 20) # عمود أسماء الأطباء
        worksheet.set_column(1, len(roster_df.columns), 15) # أعمدة الأيام

    return output.getvalue()

def display_daily_view(df, year, month):
    st.header("📅 العرض اليومي للمناوبات")
    html_content = '<div class="daily-view-container">'
    num_days_in_month = calendar.monthrange(year, month)[1]
    arabic_weekdays = {"Sun": "الأحد", "Mon": "الاثنين", "Tue": "الثلاثاء", "Wed": "الأربعاء", "Thu": "الخميس", "Fri": "الجمعة", "Sat": "السبت"}
    for day in range(1, num_days_in_month + 1):
        day_df = df[df['اليوم'] == day]
        weekday_abbr = calendar.day_abbr[calendar.weekday(year, month, day)]
        weekday_name = arabic_weekdays.get(weekday_abbr, weekday_abbr)
        html_content += f'<div class="day-column"><h4>اليوم {day} <small>({weekday_name})</small></h4>'
        if day_df.empty:
            html_content += "<p><i>لا توجد مناوبات</i></p>"
        else:
            for shift_name in ["☀️ صبح", "🌙 مساء", "🌃 ليل"]:
                shift_df = day_df[day_df['المناوبة'] == shift_name]
                if not shift_df.empty:
                    html_content += f'<div class="shift-group"><h5>{shift_name}</h5>'
                    for _, row in shift_df.iterrows():
                        html_content += f'<div class="doctor-card">{row["الطبيب"]} - {row["القسم"]}</div>'
                    html_content += '</div>'
        html_content += '</div>'
    html_content += '</div>'
    st.markdown(html_content, unsafe_allow_html=True)

# ==================================
# 5. بناء الواجهة التفاعلية
# ==================================
with st.sidebar:
    st.header("التحكم في الجدول")
    year_input = st.number_input("السنة", value=2025, min_value=2020, max_value=2050)
    month_input = st.number_input("الشهر", value=9, min_value=1, max_value=12)
    num_days_input = calendar.monthrange(year_input, month_input)[1]
    
    if st.button("🚀 توليد / تحديث الجدول", use_container_width=True):
        with st.spinner("🧠 الخوارزمية تعمل..."):
            schedule = generate_schedule_pro(num_days_input, st.session_state.doctors, st.session_state.constraints)
            if schedule is not None:
                st.session_state.schedule_df = schedule
                st.success("🎉 تم إنشاء الجدول بنجاح!")
            else:
                st.error("لم يتم العثور على حل.")
    
    if st.session_state.schedule_df is not None:
        st.divider()
        st.header("📥 تصدير الجدول")
        roster_df = st.session_state.schedule_df.pivot_table(index="الطبيب", columns="اليوم", values="المناوبة", aggfunc=lambda x: ' / '.join(x)).fillna("راحة")
        excel_data = create_styled_excel(st.session_state.schedule_df, roster_df, year_input, month_input)
        st.download_button(
            label="تنزيل جدول Excel الملون",
            data=excel_data,
            file_name=f"جدول_المناوبات_{year_input}-{month_input}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# العرض الرئيسي
if st.session_state.schedule_df is not None:
    display_daily_view(st.session_state.schedule_df, year_input, month_input)
else:
    st.info("اضغط على 'توليد الجدول' في الشريط الجانبي لبدء العملية.")

