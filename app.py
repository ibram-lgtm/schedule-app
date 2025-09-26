# app.py — Rota Matrix Cards (كامل)
# ----------------------------------
# - GA (ذكاء اصطناعي) + CP-SAT (إن توفر OR-Tools)
# - قيد: لا يزيد عن 6 شفتات متتالية
# - إدارة الأسماء (لصق جماعي / إضافة فردية)
# - تخصيص توزيع لطبيب بصيغة 1:صباح-فرز,2:راحة,...
# - عرض مصفوفي ببطاقات داخل الخلايا
# - تصدير Excel منسق (وأيضًا PDF عند توفر reportlab)

import streamlit as st
import pandas as pd
import numpy as np
import calendar
from io import BytesIO
from dataclasses import dataclass
from typing import Dict, Tuple, List

# محاولة OR-Tools (اختياري)
try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except Exception:
    ORTOOLS_AVAILABLE = False

# محاولة ReportLab (PDF اختياري)
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

# -----------------------
# إعداد الواجهة و الـCSS
# -----------------------
st.set_page_config(page_title="Rota Matrix Cards", layout="wide")

CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
  * { font-family: 'Tajawal', sans-serif; }
  :root {
    --primary:#5b74ff; --bg:#f5f7fb; --text:#1c1f2a; --muted:#6b7280;
    --card:#ffffff; --border:#e6e8ef;
    --m:#eaf3ff; --e:#fff2e6; --n:#eee8ff; --r:#f2f3f7;
  }
  body[data-theme="dark"] {
    --primary:#93a2ff; --bg:#0e1117; --text:#f5f6f8; --muted:#9aa1ae;
    --card:#171a21; --border:#2a2f37;
    --m:#14243a; --e:#3b2e1e; --n:#2b2440; --r:#20232b;
  }
  .stApp { background: var(--bg); }
  h1,h2,h3 { color: var(--primary); }

  .panel { background:var(--card); border:1px solid var(--border);
           border-radius:16px; padding:12px; }

  /* جدول لاصق للرأس والعمود الأول */
  table.rota { border-collapse: separate; border-spacing:0; width:100%; }
  table.rota th, table.rota td { border:1px solid var(--border); padding:6px 8px; vertical-align:middle; }
  table.rota thead th { position:sticky; top:0; background:var(--card); z-index:2; text-align:center; }
  table.rota td.doc { position:sticky; left:0; background:var(--card); z-index:1;
                      font-weight:700; color:var(--primary); white-space:nowrap; }

  /* كروت الشفت داخل الخلايا */
  .cell { display:flex; gap:6px; flex-wrap:wrap; justify-content:center; }
  .card { display:inline-flex; flex-direction:column; align-items:center; justify-content:center;
          padding:6px 10px; border-radius:10px; font-size:13px; font-weight:700;
          box-shadow:0 1px 0 rgba(0,0,0,.05); border:1px solid var(--border); min-width:90px; }
  .card .sub { font-size:11px; font-weight:500; color:var(--muted); margin-top:2px; }

  .m { background:var(--m); }  /* صباح */
  .e { background:var(--e); }  /* مساء */
  .n { background:var(--n); }  /* ليل */
  .r { background:var(--r); color:var(--muted); } /* راحة */
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# -----------------------
# ثوابت
# -----------------------
SHIFTS = ["صباح", "مساء", "ليل"]
AREAS  = ["فرز", "تنفسية", "ملاحظة", "انعاش"]
SHIFT_AREA: List[Tuple[str,str]] = [(s, a) for s in SHIFTS for a in AREAS]  # 12 تركيبة
CODE_REST = -1
CODE_FREE = -2  # لقفل الخلية: -2 يعني غير مقفلة

def arabic_weekday_name(y:int, m:int, d:int) -> str:
    week_ar = {"Mon":"الاثنين","Tue":"الثلاثاء","Wed":"الأربعاء",
               "Thu":"الخميس","Fri":"الجمعة","Sat":"السبت","Sun":"الأحد"}
    try:
        w = calendar.day_abbr[calendar.weekday(y, m, d)]
        return week_ar.get(w, w)
    except Exception:
        return ""

# -----------------------
# حالة التطبيق
# -----------------------
if "doctors" not in st.session_state:
    st.session_state.doctors = [f"طبيب {i+1}" for i in range(40)]
if "overrides" not in st.session_state:
    # overrides[doctor][day] = CODE or -1 للراحة
    st.session_state.overrides: Dict[str, Dict[int, int]] = {}

# -----------------------
# الشريط الجانبي
# -----------------------
with st.sidebar:
    st.header("الإعدادات")
    year  = st.number_input("السنة", value=2025, step=1)
    month = st.number_input("الشهر", value=9, min_value=1, max_value=12, step=1)
    days  = st.slider("عدد الأيام", 5, 31, 30)
    per_doc_cap = st.slider("سقف الشفتات للطبيب", 1, 60, 18)
    max_consecutive = st.slider("الحد الأقصى للتوالي", 2, 14, 6)

    st.caption("حدود إجمالي كل وردية (يوميًا)")
    min_total = st.slider("أدنى إجمالي للوردية", 0, 100, 10)
    max_total = st.slider("أقصى إجمالي للوردية", 0, 100, 13)

    st.caption("الحد الأدنى لتغطية الأقسام (في كل وردية/يوم)")
    c1, c2 = st.columns(2)
    with c1:
        cov_frz = st.number_input("فرز", 0, 40, 2)
        cov_tnf = st.number_input("تنفسية", 0, 40, 1)
    with c2:
        cov_mlh = st.number_input("ملاحظة", 0, 40, 4)
        cov_inash = st.number_input("إنعاش", 0, 40, 3)

    engine = st.radio("طريقة التوليد", ["ذكاء اصطناعي (GA)", "محلّل قيود (CP-SAT)"], index=0)

    if engine == "ذكاء اصطناعي (GA)":
        gens = st.slider("عدد الأجيال (GA)", 10, 500, 120)
        pop  = st.slider("حجم المجتمع (GA)", 10, 200, 40)
        mut  = st.slider("معدل الطفرة (GA)", 0.0, 0.2, 0.03, 0.01)
        rest_bias = st.slider("ميل للراحة (GA)", 0.0, 0.95, 0.6, 0.05)
    else:
        cp_limit   = st.slider("مهلة CP-SAT (ثواني)", 5, 300, 90)
        cp_balance = st.checkbox("توازن الأحمال هدفًا إضافيًا", True)

# -----------------------
# إدارة الأسماء + تخصيصات
# -----------------------
st.header("إدارة الأطباء")
with st.expander("إضافة مجموعة أسماء باللصق"):
    pasted = st.text_area("ألصق الأسماء هنا (اسم في كل سطر)", height=150, placeholder="مثال:\nأحمد سعيد\nمحمد علي\n...").strip()
    mode = st.radio("طريقة الإضافة", ["استبدال القائمة الحالية", "إضافة إلى القائمة الحالية"], horizontal=True)
    if st.button("تطبيق الأسماء المضافة"):
        if pasted:
            new_names = [x.strip() for x in pasted.splitlines() if x.strip()]
            if mode == "استبدال القائمة الحالية":
                st.session_state.doctors = new_names
                st.session_state.overrides = {}
            else:
                # إضافة مع منع التكرار
                base = set(st.session_state.doctors)
                for n in new_names:
                    if n not in base:
                        st.session_state.doctors.append(n)
                # لا نلمس overrides القديمة
            st.success(f"تم تحديث قائمة الأطباء. العدد الحالي: {len(st.session_state.doctors)}")
        else:
            st.warning("لم يتم العثور على أسماء.")

with st.expander("إضافة طبيب واحد"):
    one_name = st.text_input("اسم الطبيب الجديد", "")
    if st.button("إضافة الطبيب"):
        if one_name.strip():
            if one_name not in st.session_state.doctors:
                st.session_state.doctors.append(one_name.strip())
                st.success("تمت الإضافة.")
            else:
                st.info("الاسم موجود مسبقًا.")

st.header("تخصيص توزيع لطبيب (اختياري)")
with st.expander("تعيين مخصص لأيام محددة"):
    if len(st.session_state.doctors) == 0:
        st.warning("أضف أسماء أولًا.")
    else:
        target_doc = st.selectbox("اختر الطبيب", st.session_state.doctors)
        spec = st.text_area(
            "أدخل الخريطة بصيغة: يوم:شفت-قسم ، وافصل بفواصل أو أسطر",
            placeholder="مثال: 1:صباح-فرز, 2:راحة, 3:ليل-ملاحظة",
            height=100
        )
        def parse_spec(txt:str) -> Dict[int, int]:
            mapping = {}
            if not txt.strip(): return mapping
            tokens = []
            for line in txt.splitlines():
                tokens.extend([t.strip() for t in line.split(",") if t.strip()])
            for tok in tokens:
                # أمثلة: "1:صباح-فرز" أو "2:راحة"
                if ":" not in tok: continue
                day_str, rhs = [x.strip() for x in tok.split(":", 1)]
                if not day_str.isdigit(): continue
                day = int(day_str)
                if day < 1 or day > days: continue
                if rhs == "راحة":
                    mapping[day] = CODE_REST
                else:
                    if "-" not in rhs: continue
                    sh, ar = [x.strip() for x in rhs.split("-", 1)]
                    if sh not in SHIFTS or ar not in AREAS: continue
                    code = SHIFT_AREA.index((sh, ar))
                    mapping[day] = code
            return mapping

        if st.button("تطبيق التخصيص"):
            mp = parse_spec(spec)
            if target_doc not in st.session_state.overrides:
                st.session_state.overrides[target_doc] = {}
            st.session_state.overrides[target_doc].update(mp)
            st.success(f"تم تطبيق {len(mp)} تخصيص(ات) على {target_doc}.")

# -----------------------
# مولدات الجدولة
# -----------------------
def build_locks(doctors: List[str], days_cnt:int) -> np.ndarray:
    locks = np.full((len(doctors), days_cnt), CODE_FREE, dtype=np.int16)
    for i, name in enumerate(doctors):
        if name in st.session_state.overrides:
            for day, code in st.session_state.overrides[name].items():
                locks[i, day-1] = code  # 1-based -> 0-based
    return locks

@dataclass
class GAParams:
    days: int
    doctors: int
    per_doc_cap: int
    coverage: Dict[str, int]
    min_total: int
    max_total: int
    generations: int = 120
    population_size: int = 40
    mutation_rate: float = 0.03
    rest_bias: float = 0.6
    balance_weight: float = 1.0
    penalty_scale: float = 50.0
    max_consecutive: int = 6

def ga_random(doctors:int, days:int, rest_bias:float)->np.ndarray:
    genes = np.full((doctors, days), CODE_REST, dtype=np.int16)
    mask  = (np.random.rand(doctors, days) < (1.0 - rest_bias))
    genes[mask] = np.random.randint(0, len(SHIFT_AREA), size=mask.sum(), dtype=np.int16)
    return genes

def enforce_max_consec(genes: np.ndarray, max_consecutive:int, locks: np.ndarray) -> np.ndarray:
    g = genes.copy()
    D, T = g.shape
    for d in range(D):
        run = 0
        for t in range(T):
            if g[d, t] >= 0:
                run += 1
                if run > max_consecutive:
                    # نكسر السلسلة إن لم تكن الخلية مقفلة على عمل
                    if locks[d, t] == CODE_FREE:
                        g[d, t] = CODE_REST
                        run = 0
            else:
                run = 0
    # إعادة فرض الأقفال (إن وجدت) فوق أي تعديلات
    for d in range(D):
        for t in range(T):
            if locks[d, t] != CODE_FREE:
                g[d, t] = locks[d, t]
    return g

def ga_decode(genes:np.ndarray, days:int):
    per_doc = (genes >= 0).sum(axis=1)
    totals_shift = {(d, s):0 for d in range(days) for s in SHIFTS}
    totals_area  = {(d, s, a):0 for d in range(days) for s in SHIFTS for a in AREAS}
    for day in range(days):
        vals = genes[:, day]
        for v in vals[vals>=0]:
            s, a = SHIFT_AREA[int(v)]
            totals_shift[(day, s)] += 1
            totals_area[(day, s, a)] += 1
    return per_doc, totals_shift, totals_area

def ga_fitness(genes:np.ndarray, p:GAParams) -> float:
    per_doc, totals_shift, totals_area = ga_decode(genes, p.days)
    pen = 0.0
    over = np.clip(per_doc - p.per_doc_cap, 0, None).sum()
    pen += over * p.penalty_scale
    # إجمالي الوردية والتغطية الدنيا
    for day in range(p.days):
        for s in SHIFTS:
            t = totals_shift[(day, s)]
            if t < p.min_total: pen += (p.min_total - t) * p.penalty_scale
            if t > p.max_total: pen += (t - p.max_total) * p.penalty_scale
            for a in AREAS:
                req = p.coverage[a]
                ta = totals_area[(day, s, a)]
                if ta < req: pen += (req - ta) * p.penalty_scale
    # توازن الأحمال
    var = float(np.var(per_doc.astype(np.float32)))
    pen += var * p.balance_weight
    # عقوبة السلاسل الزائدة
    D, T = genes.shape
    over_runs = 0
    for d in range(D):
        run = 0
        for t in range(T):
            if genes[d, t] >= 0:
                run += 1
                if run > p.max_consecutive:
                    over_runs += 1
            else:
                run = 0
    pen += over_runs * p.penalty_scale * 10
    return -pen

def ga_cross(a:np.ndarray, b:np.ndarray)->np.ndarray:
    mask = (np.random.rand(*a.shape) < 0.5)
    return np.where(mask, a, b)

def ga_mutate(ind:np.ndarray, rate:float, locks:np.ndarray, max_consecutive:int)->np.ndarray:
    out = ind.copy()
    mask = (np.random.rand(*out.shape) < rate)
    rnd  = np.random.randint(-1, len(SHIFT_AREA), size=out.shape, dtype=np.int16)
    out[mask] = rnd[mask]
    # إعادة فرض الأقفال
    locked_positions = (locks != CODE_FREE)
    out[locked_positions] = locks[locked_positions]
    # كسر السلاسل
    out = enforce_max_consec(out, max_consecutive, locks)
    return out

def ga_evolve(p:GAParams, locks:np.ndarray, progress=None)->np.ndarray:
    pop = [ga_random(p.doctors, p.days, p.rest_bias) for _ in range(p.population_size)]
    # فرض الأقفال + السلاسل
    pop = [enforce_max_consec(np.where(locks!=CODE_FREE, locks, ind), p.max_consecutive, locks) for ind in pop]
    fits = np.array([ga_fitness(x, p) for x in pop], dtype=np.float64)
    elite_k = max(1, int(0.15 * p.population_size))
    for g in range(p.generations):
        order = np.argsort(fits)[::-1]
        elites = [pop[i] for i in order[:elite_k]]
        kids = elites.copy()
        while len(kids) < p.population_size:
            i, j = np.random.randint(0, p.population_size, size=2)
            child = ga_cross(pop[order[i]], pop[order[j]])
            # إعادة فرض الأقفال
            child = np.where(locks!=CODE_FREE, locks, child)
            child = ga_mutate(child, p.mutation_rate, locks, p.max_consecutive)
            kids.append(child)
        pop = kids
        # ضمان الأقفال والسلاسل بعد الجيل
        pop = [enforce_max_consec(np.where(locks!=CODE_FREE, locks, ind), p.max_consecutive, locks) for ind in pop]
        fits = np.array([ga_fitness(x, p) for x in pop], dtype=np.float64)
        if progress:
            progress.progress((g+1)/p.generations, text=f"تحسين الجدول… جيل {g+1}/{p.generations}")
    return pop[int(np.argmax(fits))]

def cpsat_schedule(doctors:List[str], days_cnt:int, cap:int, min_total:int, max_total:int,
                   cov:Dict[str,int], time_limit:int, balance:bool,
                   max_consecutive:int, locks:np.ndarray):
    model = cp_model.CpModel()
    D = len(doctors)
    # x[d,day,shift,area]
    x = {}
    for d in range(D):
        for day in range(days_cnt):
            for s in SHIFTS:
                for a in AREAS:
                    x[(d, day, s, a)] = model.NewBoolVar(f"x_{d}_{day}_{s}_{a}")

    # تغطيات + إجماليات
    for day in range(days_cnt):
        for s in SHIFTS:
            for a in AREAS:
                model.Add(sum(x[(d, day, s, a)] for d in range(D)) >= int(cov[a]))
            tot = [x[(d, day, s, a)] for d in range(D) for a in AREAS]
            model.Add(sum(tot) >= int(min_total))
            model.Add(sum(tot) <= int(max_total))

    # وردية واحدة/يوم/طبيب
    for day in range(days_cnt):
        for d in range(D):
            model.Add(sum(x[(d, day, s, a)] for s in SHIFTS for a in AREAS) <= 1)

    # أقفال التخصيص
    for d in range(D):
        for day in range(days_cnt):
            lock = int(locks[d, day])
            if lock == CODE_FREE:
                continue
            if lock == CODE_REST:
                model.Add(sum(x[(d, day, s, a)] for s in SHIFTS for a in AREAS) == 0)
            else:
                s, a = SHIFT_AREA[lock]
                model.Add(x[(d, day, s, a)] == 1)
                # باقي التركيبات = 0
                for ss in SHIFTS:
                    for aa in AREAS:
                        if (ss, aa) != (s, a):
                            model.Add(x[(d, day, ss, aa)] == 0)

    # سقف الطبيب
    totals = {}
    for d in range(D):
        tot = sum(x[(d, day, s, a)] for day in range(days_cnt) for s in SHIFTS for a in AREAS)
        model.Add(tot <= int(cap))
        totals[d] = tot

    # قيد السلاسل المتتالية
    y = {}
    for d in range(D):
        for day in range(days_cnt):
            y[(d, day)] = model.NewIntVar(0, 1, f"y_{d}_{day}")
            model.Add(y[(d, day)] == sum(x[(d, day, s, a)] for s in SHIFTS for a in AREAS))
    win = max_consecutive + 1
    for d in range(D):
        for start in range(0, days_cnt - win + 1):
            model.Add(sum(y[(d, start+k)] for k in range(win)) <= max_consecutive)

    # هدف توازن (اختياري)
    if balance:
        approx = days_cnt * len(SHIFTS) * ((min_total + max_total) / 2.0)
        target = int(round(approx / max(1, D)))
        devs = []
        for d in range(D):
            over = model.NewIntVar(0, 10000, f"over_{d}")
            under = model.NewIntVar(0, 10000, f"under_{d}")
            model.Add(totals[d] - target - over + under == 0)
            devs.extend([over, under])
        model.Minimize(sum(devs))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit)
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return pd.DataFrame(), "UNSOLVED"

    rows = []
    for d in range(D):
        for day in range(days_cnt):
            for s in SHIFTS:
                for a in AREAS:
                    if solver.Value(x[(d, day, s, a)]) == 1:
                        rows.append({"الطبيب": doctors[d], "اليوم": day+1, "المناوبة": f"{s} - {a}"})
    return pd.DataFrame(rows), ("OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE")

# -----------------------
# تحويلات وعرض Matrix Cards
# -----------------------
def to_long_df_from_genes(genes:np.ndarray, days_cnt:int, doctors:List[str])->pd.DataFrame:
    rows=[]
    for i, name in enumerate(doctors):
        for day in range(days_cnt):
            v = int(genes[i, day])
            if v >= 0:
                s,a = SHIFT_AREA[v]
                rows.append({"الطبيب": name, "اليوم": day+1, "المناوبة": f"{s} - {a}"})
    return pd.DataFrame(rows)

def to_matrix(df: pd.DataFrame, days_cnt:int, doctors:List[str]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(index=doctors, columns=range(1, days_cnt+1)).fillna("راحة")
    t = df.pivot_table(index="الطبيب", columns="اليوم", values="المناوبة", aggfunc="first").fillna("راحة")
    return t.reindex(index=doctors, columns=range(1, days_cnt+1), fill_value="راحة")

def cell_cls(v:str)->str:
    if "صباح" in v: return "m"
    if "مساء" in v: return "e"
    if "ليل" in v: return "n"
    return "r"

def render_matrix_cards(roster: pd.DataFrame, year:int, month:int):
    cols = roster.columns.tolist()
    # Header
    head_cells = []
    for d in cols:
        head_cells.append(
            f"<th><div>{arabic_weekday_name(year, int(month), int(d))}</div>"
            f"<div class='sub'>{int(d)}/{int(month)}</div></th>"
        )
    thead = "<thead><tr><th>الطبيب</th>" + "".join(head_cells) + "</tr></thead>"

    # Body
    body_rows = []
    for doc in roster.index:
        tds = [f"<td class='doc'>{doc}</td>"]
        for d in cols:
            val = str(roster.loc[doc, d])
            if val == "راحة":
                inner = "<div class='cell'><div class='card r'>راحة</div></div>"
            else:
                part = val.split(" - ")
                shift = part[0] if part else val
                sec   = part[1] if len(part) > 1 else ""
                inner = f"<div class='cell'><div class='card {cell_cls(val)}'>{shift}<span class='sub'>{sec}</span></div></div>"
            tds.append(f"<td>{inner}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"

    st.markdown(
        f"<div class='panel'><div style='overflow:auto; max-height:75vh;'>"
        f"<table class='rota'>{thead}{tbody}</table></div></div>",
        unsafe_allow_html=True
    )

# -----------------------
# تصدير Excel منسّق (مطابق للألوان)
# -----------------------
def export_matrix_to_excel(rota: pd.DataFrame, year:int, month:int) -> bytes:
    output = BytesIO()
    import xlsxwriter
    wb = xlsxwriter.Workbook(output, {'in_memory': True})
    ws = wb.add_worksheet('Rota')

    # تنسيق عام
    ws.right_to_left()
    header_fmt = wb.add_format({'bold': True, 'align':'center', 'valign':'vcenter',
                                'text_wrap': True, 'border':1, 'fg_color':'#FFFFFF',
                                'reading_order':2})
    doc_fmt = wb.add_format({'bold': True, 'align':'right', 'valign':'vcenter',
                             'fg_color':'#FFFFFF', 'border':1, 'reading_order':2})
    base_cell = wb.add_format({'align':'center', 'valign':'vcenter', 'text_wrap':True,
                               'border':1, 'reading_order':2})

    m_fmt = wb.add_format({'align':'center','valign':'vcenter','text_wrap':True,'border':1,
                           'fg_color':'#EAF3FF','reading_order':2})
    e_fmt = wb.add_format({'align':'center','valign':'vcenter','text_wrap':True,'border':1,
                           'fg_color':'#FFF2E6','reading_order':2})
    n_fmt = wb.add_format({'align':'center','valign':'vcenter','text_wrap':True,'border':1,
                           'fg_color':'#EEE8FF','reading_order':2})
    r_fmt = wb.add_format({'align':'center','valign':'vcenter','text_wrap':True,'border':1,
                           'fg_color':'#F2F3F7','font_color':'#6B7280','reading_order':2})

    # أحجام
    ws.set_row(0, 38)
    ws.set_column(0, 0, 22)
    ws.set_column(1, rota.shape[1], 14)

    # رأس
    ws.write(0, 0, "الطبيب", header_fmt)
    for j, day in enumerate(rota.columns, start=1):
        title = f"{arabic_weekday_name(year, int(month), int(day))}\n{int(day)}/{int(month)}"
        ws.write(0, j, title, header_fmt)

    # جسم
    for i, doc in enumerate(rota.index, start=1):
        ws.set_row(i, 34)
        ws.write(i, 0, doc, doc_fmt)
        for j, day in enumerate(rota.columns, start=1):
            val = str(rota.loc[doc, day])
            if val == "راحة":
                ws.write(i, j, "راحة", r_fmt)
            else:
                part = val.split(" - ")
                shift = part[0] if part else val
                sec   = part[1] if len(part) > 1 else ""
                text = f"{shift}\n{sec}" if sec else shift
                fmt = m_fmt if "صباح" in shift else e_fmt if "مساء" in shift else n_fmt
                ws.write(i, j, text, fmt)

    ws.freeze_panes(1, 1)
    wb.close()
    return output.getvalue()

# -----------------------
# تصدير PDF (عند توفر ReportLab)
# -----------------------
def export_matrix_to_pdf(rota: pd.DataFrame, year:int, month:int) -> bytes:
    if not REPORTLAB_AVAILABLE:
        return b""
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A3), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    data = []
    header = ["الطبيب"] + [f"{arabic_weekday_name(year, int(month), int(d))}\n{int(d)}/{int(month)}" for d in rota.columns]
    data.append(header)
    for doc_name in rota.index:
        row = [doc_name]
        for d in rota.columns:
            val = str(rota.loc[doc_name, d])
            if val == "راحة":
                row.append("راحة")
            else:
                part = val.split(" - ")
                shift = part[0] if part else val
                sec   = part[1] if len(part) > 1 else ""
                row.append(f"{shift}\n{sec}" if sec else shift)
        data.append(row)
    table = Table(data, repeatRows=1)
    ts = TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('ALIGN', (0,1), (0,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.3, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
    ])
    # تلوين الخلايا حسب الشفت
    for r in range(1, len(data)):
        for c in range(1, len(header)):
            v = data[r][c]
            if v == "راحة":
                ts.add('BACKGROUND', (c, r), (c, r), colors.HexColor('#F2F3F7'))
            elif "صباح" in v:
                ts.add('BACKGROUND', (c, r), (c, r), colors.HexColor('#EAF3FF'))
            elif "مساء" in v:
                ts.add('BACKGROUND', (c, r), (c, r), colors.HexColor('#FFF2E6'))
            elif "ليل" in v:
                ts.add('BACKGROUND', (c, r), (c, r), colors.HexColor('#EEE8FF'))
    table.setStyle(ts)
    story = [table]
    doc.build(story)
    return output.getvalue()

# -----------------------
# التشغيل والعرض
# -----------------------
st.title("جدولة المناوبات — عرض مصفوفي ببطاقات داخل الخلايا")

doctors = st.session_state.doctors
coverage = {"فرز": cov_frz, "تنفسية": cov_tnf, "ملاحظة": cov_mlh, "انعاش": cov_inash}
locks = build_locks(doctors, days)

col1, col2, col3 = st.columns(3)
col1.metric("عدد الأطباء", len(doctors))
col2.metric("عدد الأيام", days)
col3.metric("توفر OR-Tools", "نعم" if ORTOOLS_AVAILABLE else "لا")

result_df = None
method_used = None

if st.button("توليد الجدول"):
    # جدوى تقريبية (للـ GA فقط)
    min_needed = days * 3 * min_total
    max_capacity = len(doctors) * per_doc_cap
    if engine == "ذكاء اصطناعي (GA)" and min_needed > max_capacity:
        st.warning("الحد الأدنى المطلوب أكبر من السعة — تم رفع سقف الطبيب تلقائيًا.")
        per_doc_cap = max(per_doc_cap, int(min_needed // max(1, len(doctors)) + 1))

    if engine == "ذكاء اصطناعي (GA)":
        with st.spinner("الذكاء الاصطناعي يولّد الجدول..."):
            p = GAParams(days=days, doctors=len(doctors), per_doc_cap=per_doc_cap,
                         coverage=coverage, min_total=min_total, max_total=max_total,
                         generations=gens, population_size=pop, mutation_rate=mut,
                         rest_bias=rest_bias, max_consecutive=max_consecutive)
            prog = st.progress(0.0, text="بدء التطوير...")
            genes = ga_evolve(p, locks=locks, progress=prog)
            result_df = to_long_df_from_genes(genes, days, doctors)
            method_used = "GA"
            st.success("تم التوليد بالذكاء الاصطناعي.")
    else:
        if not ORTOOLS_AVAILABLE:
            st.error("CP-SAT غير متاح. اختر وضع GA.")
        else:
            with st.spinner("محاولة حل مثالي عبر CP-SAT..."):
                result_df, status = cpsat_schedule(
                    doctors=doctors, days_cnt=days, cap=per_doc_cap,
                    min_total=min_total, max_total=max_total, cov=coverage,
                    time_limit=cp_limit, balance=cp_balance,
                    max_consecutive=max_consecutive, locks=locks
                )
                if result_df is None or result_df.empty:
                    st.error("لم يُعثر على حل ضمن المهلة. زد المهلة أو خفّف القيود.")
                else:
                    method_used = f"CP-SAT ({status})"
                    st.success(f"تم التوليد عبر {method_used}.")

# عرض المصفوفة + تصدير
if result_df is not None and not result_df.empty:
    rota = to_matrix(result_df, days, doctors)
    st.subheader(f"النتيجة ({method_used})")
    render_matrix_cards(rota, int(year), int(month))

    with st.expander("تصدير"):
        c1, c2 = st.columns(2)
        with c1:
            excel_bytes = export_matrix_to_excel(rota, int(year), int(month))
            st.download_button("تنزيل Excel منسّق", data=excel_bytes,
                               file_name="rota_matrix.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)
        with c2:
            if REPORTLAB_AVAILABLE:
                pdf_bytes = export_matrix_to_pdf(rota, int(year), int(month))
                st.download_button("تنزيل PDF", data=pdf_bytes,
                                   file_name="rota_matrix.pdf", mime="application/pdf",
                                   use_container_width=True)
            else:
                st.info("توليد PDF يتطلب مكتبة reportlab. التصدير إلى Excel متاح بالكامل.")
else:
    st.info("اضبط الإعدادات، أدخل الأسماء (إن رغبت)، ثم اضغط «توليد الجدول».")

