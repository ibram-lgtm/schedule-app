import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
from io import BytesIO
import calendar

# ==================================
# 1. إعدادات التطبيق والواجهة
# ==================================
st.set_page_config(layout="wide", page_title="جدول المناوبات")

st.title("🗓️ جدول المناوبات الشهري")
st.markdown("### نظام لعرض وتصدير جداول المناوبات")

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
# 4. دوال إنشاء الجدول والتصدير
# ==================================
def create_roster_table(df, year, month):
    num_days = calendar.monthrange(year, month)[1]
    doctors = sorted(df['الطبيب'].unique().tolist())
    
    # إنشاء جدول فارغ
    schedule_grid = pd.DataFrame(index=doctors, columns=range(1, num_days + 1)).fillna("راحة")
    
    # ملء الجدول بالبيانات
    for _, row in df.iterrows():
        schedule_grid.loc[row['الطبيب'], row['اليوم']] = f"{row['المناوبة']} {row['القسم']}"
        
    return schedule_grid

def create_professional_excel(roster_table, year, month):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        roster_table.to_excel(writer, sheet_name=f'مناوبات {month}-{year}')
        workbook = writer.book
        worksheet = writer.sheets[f'مناوبات {month}-{year}']
        
        # تعريف التنسيقات
        header_format = workbook.add_format({'bold': True, 'font_size': 11, 'bg_color': '#4472C4', 'font_color': 'white', 'align': 'center', 'valign': 'vcenter', 'border': 1})
        doctor_name_format = workbook.add_format({'bold': True, 'font_size': 10, 'bg_color': '#D9E1F2', 'align': 'right', 'valign': 'vcenter', 'border': 1})
        shift_formats = {
            '☀️': workbook.add_format({'bg_color': '#92D050', 'font_color': '#000000', 'align': 'center', 'valign': 'vcenter', 'font_size': 9, 'bold': True, 'border': 1}),
            '🌙': workbook.add_format({'bg_color': '#FFC000', 'font_color': '#000000', 'align': 'center', 'valign': 'vcenter', 'font_size': 9, 'bold': True, 'border': 1}),
            '🌃': workbook.add_format({'bg_color': '#5B9BD5', 'font_color': '#FFFFFF', 'align': 'center', 'valign': 'vcenter', 'font_size': 9, 'bold': True, 'border': 1}),
            'راحة': workbook.add_format({'bg_color': '#D9D9D9', 'font_color': '#666666', 'align': 'center', 'valign': 'vcenter', 'font_size': 9, 'border': 1})
        }
        
        # تطبيق التنسيق
        worksheet.write(0, 0, 'الطبيب / الأطباء', doctor_name_format)
        worksheet.set_column(0, 0, 25)
        for col_num in range(1, len(roster_table.columns) + 1):
            worksheet.write(0, col_num, col_num, header_format)
            worksheet.set_column(col_num, col_num, 15)
        
        for row_num, doctor in enumerate(roster_table.index, 1):
            worksheet.write(row_num, 0, doctor, doctor_name_format)
            for col_num, day in enumerate(roster_table.columns, 1):
                cell_value = roster_table.loc[doctor, day]
                cell_format = shift_formats['راحة']
                display_text = ""
                for shift_key, fmt in shift_formats.items():
                    if shift_key in str(cell_value):
                        cell_format = fmt
                        display_text = cell_value.replace(shift_key, "").strip()
                        break
                worksheet.write(row_num, col_num, display_text, cell_format)
        worksheet.freeze_panes(1, 1)
    
    return output.getvalue()

# ==================================
# 5. بناء الواجهة التفاعلية
# ==================================
with st.sidebar:
    st.header("التحكم في الجدول")
    year_input = st.number_input("السنة", value=2025)
    month_input = st.number_input("الشهر", value=9, min_value=1, max_value=12)
    
    if st.button("🚀 توليد / تحديث الجدول", use_container_width=True):
        num_days_input = calendar.monthrange(year_input, month_input)[1]
        with st.spinner("🧠 الخوارزمية تعمل..."):
            schedule = generate_schedule_pro(num_days_input, st.session_state.doctors, st.session_state.constraints)
            if schedule is not None:
                st.session_state.schedule_df = schedule
                st.success("🎉 تم إنشاء الجدول بنجاح!")
            else:
                st.error("لم يتم العثور على حل.")
    
    if st.session_state.schedule_df is not None:
        st.divider()
        st.header("📥 تصدير احترافي")
        roster_table = create_roster_table(st.session_state.schedule_df, year_input, month_input)
        excel_data = create_professional_excel(roster_table, year_input, month_input)
        st.download_button(
            label="📊 تنزيل جدول Excel احترافي",
            data=excel_data,
            file_name=f"جدول_مناوبات_{year_input}_{month_input:02d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# العرض الرئيسي
if st.session_state.schedule_df is not None:
    roster_table_to_display = create_roster_table(st.session_state.schedule_df, year_input, month_input)
    st.dataframe(roster_table_to_display, use_container_width=True)
else:
    st.info("اضغط على 'توليد الجدول' في الشريط الجانبي لبدء العملية.")



