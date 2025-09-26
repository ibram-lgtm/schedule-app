import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
from io import BytesIO

# ==================================
# 1. إعدادات التطبيق والبيانات الأساسية
# ==================================

st.set_page_config(layout="wide", page_title="أداة توزيع المناوبات")
st.title("👨‍⚕️ أداة توزيع المناوبات التلقائي")
st.write("تم تحديث الأداة لتضمن توزيعًا عادلًا، عدد أطباء مرن (10-13) لكل شفت، والالتزام بحصص الأقسام.")

SHIFTS = ["صبح", "مساء", "ليل"]
# تحديد الحد الأدنى من الأطباء لكل قسم
AREAS_MIN_COVERAGE = {
    "فرز": 2,
    "تنفسية": 1,
    "ملاحظة": 4,
    "انعاش": 3
}
# قائمة بجميع المناطق المتاحة للعمل
ALL_AREAS = list(AREAS_MIN_COVERAGE.keys())

NUM_DAYS = 30
ALL_DOCTORS = [f"طبيب {i+1}" for i in range(43)]

# يمكنك تعديل هذه القيود لتناسب فريقك
DOCTOR_CONSTRAINTS = {
    "طبيب 1": {"max_shifts": 16, "fixed_area": "انعاش", "fixed_shift": None},
    "طبيب 2": {"max_shifts": 16, "fixed_area": "انعاش", "fixed_shift": None},
    "طبيب 3": {"max_shifts": 18, "fixed_area": None, "fixed_shift": "صبح"},
    "طبيب 4": {"max_shifts": 18, "fixed_area": "فرز", "fixed_shift": None},
}

for doc in ALL_DOCTORS:
    if doc not in DOCTOR_CONSTRAINTS:
        DOCTOR_CONSTRAINTS[doc] = {"max_shifts": 18, "fixed_area": None, "fixed_shift": None}

# ==================================
# 3. دالة حل وتوليد الجدول
# ==================================
def generate_schedule():
    model = cp_model.CpModel()

    shifts = {}
    for doc in ALL_DOCTORS:
        for day in range(NUM_DAYS):
            for shift in SHIFTS:
                for area in ALL_AREAS:
                    shifts[(doc, day, shift, area)] = model.NewBoolVar(f"shift_{doc}_{day}_{shift}_{area}")

    # --- إضافة القيود المحدثة ---

    for day in range(NUM_DAYS):
        for shift in SHIFTS:
            # 1. قيد حصص الأقسام (الحد الأدنى لكل قسم)
            for area, min_count in AREAS_MIN_COVERAGE.items():
                model.Add(sum(shifts[(doc, day, shift, area)] for doc in ALL_DOCTORS) >= min_count)

            # 2. قيد العدد الإجمالي للأطباء في الشفت (بين 10 و 13)
            total_doctors_in_shift = [shifts[(doc, day, shift, area)] for doc in ALL_DOCTORS for area in ALL_AREAS]
            model.Add(sum(total_doctors_in_shift) >= 10)
            model.Add(sum(total_doctors_in_shift) <= 13)

    # 3. قيد الطبيب الواحد: كل طبيب يمكنه العمل في شفت واحد ومنطقة واحدة فقط في اليوم
    for day in range(NUM_DAYS):
        for doc in ALL_DOCTORS:
            model.Add(sum(shifts[(doc, day, shift, area)] for shift in SHIFTS for area in ALL_AREAS) <= 1)

    # 4. قيد الحد الأقصى للمناوبات الشهرية
    for doc in ALL_DOCTORS:
        max_s = DOCTOR_CONSTRAINTS[doc]["max_shifts"]
        model.Add(sum(shifts[(doc, day, shift, area)] for day in range(NUM_DAYS) for shift in SHIFTS for area in ALL_AREAS) <= max_s)

    # 5. قيد عدم تجاوز 6 شفتات متتالية
    for doc in ALL_DOCTORS:
        for day in range(NUM_DAYS - 6):
            model.Add(sum(shifts[(doc, d, s, a)] for d in range(day, day + 7) for s in SHIFTS for a in ALL_AREAS) <= 6)

    # 6. القيود المخصصة (مكان ثابت، شفت ثابت)
    for doc, constraints in DOCTOR_CONSTRAINTS.items():
        if constraints["fixed_area"]:
            fixed_area = constraints["fixed_area"]
            for day in range(NUM_DAYS):
                for shift in SHIFTS:
                    for area in ALL_AREAS:
                        if area != fixed_area:
                            model.Add(shifts[(doc, day, shift, area)] == 0)

        if constraints["fixed_shift"]:
            fixed_shift = constraints["fixed_shift"]
            for day in range(NUM_DAYS):
                for shift in SHIFTS:
                     if shift != fixed_shift:
                        for area in ALL_AREAS:
                            model.Add(shifts[(doc, day, shift, area)] == 0)

    # --- حل النموذج ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 90.0 # زيادة الوقت قليلاً للتعقيد الإضافي
    status = solver.Solve(model)

    # --- عرض النتائج ---
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        schedule_data = []
        all_assigned_slots = set()
        
        for day in range(NUM_DAYS):
            for shift in SHIFTS:
                for area in ALL_AREAS:
                    for doc in ALL_DOCTORS:
                        if solver.Value(shifts[(doc, day, shift, area)]) == 1:
                            # إنشاء معرف فريد لكل خانة لتجنب التكرار
                            slot_id = (day, shift, area, doc)
                            if slot_id not in all_assigned_slots:
                                schedule_data.append({
                                    "اليوم": day + 1, "المناوبة": shift, "المنطقة": area, "الطبيب": doc
                                })
                                all_assigned_slots.add(slot_id)

        if not schedule_data:
             return None # لا يوجد حل

        df = pd.DataFrame(schedule_data)
        # تحويل الجدول ليكون أكثر قراءة
        pivot_df = df.pivot_table(index=["اليوم", "المنطقة"], columns="المناوبة", values="الطبيب", aggfunc=lambda x: ', '.join(x)).reset_index()
        # إعادة ترتيب الأعمدة
        pivot_df = pivot_df.reindex(columns=["اليوم", "المنطقة", "صبح", "مساء", "ليل"], fill_value="").sort_values(by=["اليوم", "المنطقة"])
        return pivot_df
    else:
        return None

# ==================================
# 4. دالة تنسيق وتصدير Excel
# ==================================
def to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='الجدول', startrow=1, header=False)
    
    workbook = writer.book
    worksheet = writer.sheets['الجدول']
    
    header_format = workbook.add_format({
        'bold': True, 'text_wrap': True, 'valign': 'top',
        'fg_color': '#D7E4BC', 'border': 1, 'align': 'center'
    })
    for col_num, value in enumerate(df.columns.values):
        worksheet.write(0, col_num, value, header_format)

    cell_format = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
    cell_wrap_format = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})

    worksheet.conditional_format('A1:E1000', {'type': 'no_blanks', 'format': cell_format})
    
    red_format = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'border': 1, 'align': 'center'})
    worksheet.conditional_format('C2:E1000', {'type': 'cell', 'criteria': '==', 'value': '"شاغر"', 'format': red_format})
    
    worksheet.set_column('A:A', 5) # اليوم
    worksheet.set_column('B:B', 15) # المنطقة
    worksheet.set_column('C:E', 25) # الشفتات (عرض أكبر لاستيعاب أسماء متعددة)

    writer.close()
    processed_data = output.getvalue()
    return processed_data

# ==================================
# 5. بناء واجهة المستخدم التفاعلية
# ==================================

if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = None

if st.button("🚀 توليد جدول المناوبات الآن"):
    with st.spinner("جاري تحليل القيود الجديدة وتوزيع المناوبات... قد تستغرق العملية دقيقة ونصف."):
        result_df = generate_schedule()
        if result_df is not None and not result_df.empty:
            st.session_state.schedule_df = result_df
            st.success("🎉 تم إنشاء الجدول المحدث بنجاح!")
        else:
            st.error("لم يتم العثور على حل يوافق جميع القيود المعقدة. قد تكون الشروط متضاربة.")

if st.session_state.schedule_df is not None:
    df_to_show = st.session_state.schedule_df.fillna('')

    st.header("🗓️ جدول المناوبات المقترح")
    
    st.dataframe(df_to_show)

    excel_data = to_excel(df_to_show)
    st.download_button(
        label="📥 تصدير إلى Excel",
        data=excel_data,
        file_name="جدول_المناوبات_المحدث.xlsx",
        mime="application/vnd.ms-excel"
    )
