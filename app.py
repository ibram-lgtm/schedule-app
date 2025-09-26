# app.py
# -----------------------------------------------------------
# Rota Matrix (Days as columns, Doctors as rows)
# - AI (Genetic Algorithm) generator + optional CP-SAT (if OR-Tools available)
# - Modern Streamlit UI
# - Matrix view + (اختياري) تصدير
# -----------------------------------------------------------
import streamlit as st
import pandas as pd
import numpy as np
import calendar
from io import BytesIO
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# محاولة تفعيل OR-Tools (اختياري)
try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except Exception:
    ORTOOLS_AVAILABLE = False

# ----------------------
# إعدادات وواجهة حديثة
# ----------------------
st.set_page_config(page_title="Rota Matrix AI", layout="wide")

CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
  * { font-family: 'Tajawal', sans-serif; }
  :root {
    --primary: #5b74ff; --bg: #f5f7fb; --text: #1c1f2a;
    --card: #ffffff; --border: #e6e8ef; --muted: #6b7280;
  }
  body[data-theme="dark"] {
    --primary:#93a2ff; --bg:#0e1117; --text:#f5f6f8; --card:#171a21; --border:#2a2f37; --muted:#9aa1ae;
  }
  .stApp { background: var(--bg); }
  h1,h2,h3 { color: var(--primary); }
  .panel { background: var(--card); border:1px solid var(--border); border-radius:16px; padding:16px; }
  .kpi { display:grid; grid-template-columns:repeat(4, minmax(160px,1fr)); gap:12px; }
  .kpi .box { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:12px; }
  .kpi .label { font-size:12px; color:var(--muted); }
  .kpi .value { font-size:22px; font-weight:700; color:var(--text); }
  /* Styled HTML table */
  table.rota { border-collapse: separate; border-spacing: 0; width: 100%; }
  table.rota th, table.rota td { border:1px solid var(--border); padding:8px 10px; text-align:center; }
  table.rota th { position: sticky; top: 0; background: var(--card); z-index: 1; }
  table.rota td.doc { text-align: right; font-weight: 700; color: var(--primary); background: var(--card); position: sticky; left: 0; }
  .m { background:#eaf3ff; }  /* morning */
  .e { background:#fff2e6; }  /* evening */
  .n { background:#eee8ff; }  /* night */
  .r { background:#f2f3f7; color:#6b7280; } /* rest */
  body[data-theme="dark"] .m { background:#14243a; }
  body[data-theme="dark"] .e { background:#3b2e1e; }
  body[data-theme="dark"] .n { background:#2b2440; }
  body[data-theme="dark"] .r { background:#20232b; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------
# ثوابت
# ----------------------
SHIFTS = ["☀️ صبح", "🌙 مساء", "🌃 ليل"]
AREAS = ["فرز", "تنفسية", "ملاحظة", "انعاش"]
SHIFT_AREA = [(s, a) for s in SHIFTS for a in AREAS]  # 12 تركيبة

# ----------------------
# الشريط الجانبي
# ----------------------
with st.sidebar:
    st.header("⚙️ إعدادات الجدولة")
    year = st.number_input("السنة", value=2025, step=1)
    month = st.number_input("الشهر", value=9, min_value=1, max_value=12, step=1)
    days = st.slider("عدد الأيام", 5, 31, 30)
    doctors_n = st.slider("عدد الأطباء", 5, 150, 40)
    per_doc_cap = st.slider("الحد الأعلى للشفتات لكل طبيب", 1, 60, 18)
    st.divider()
    st.caption("حدود إجمالي كل وردية (يوميًا)")
    min_total = st.slider("أدنى إجمالي للوردية", 0, 80, 10)
    max_total = st.slider("أقصى إجمالي للوردية", 0, 100, 13)
    st.caption("الحد الأدنى لتغطية الأقسام (في كل وردية/يوم)")
    colA, colB = st.columns(2)
    with colA:
        cov_frz = st.number_input("فرز", 0, 40, 2)
        cov_tnf = st.number_input("تنفسية", 0, 40, 1)
    with colB:
        cov_mlh = st.number_input("ملاحظة", 0, 40, 4)
        cov_inash = st.number_input("إنعاش", 0, 40, 3)

    st.divider()
    engine = st.radio(
        "طريقة التوليد",
        ["ذكاء اصطناعي (GA)", "محلّل قيود (CP-SAT)"],
        index=0,
        help="GA أسرع ومرن، CP-SAT يحاول حلًا مثاليًا إذا توفرت OR-Tools."
    )
    if engine == "ذكاء اصطناعي (GA)":
        gens = st.slider("عدد الأجيال (GA)", 10, 500, 120)
        pop = st.slider("حجم المجتمع (GA)", 10, 200, 40)
        mut = st.slider("معدل الطفرة (GA)", 0.0, 0.2, 0.03, 0.01)
        rest_bias = st.slider("ميل للراحة (GA)", 0.0, 0.95, 0.6, 0.05)
    else:
        cp_limit = st.slider("مهلة CP-SAT (ثواني)", 5, 300, 90)
        cp_balance = st.checkbox("توازن الأحمال هدفًا إضافيًا", True)
    st.divider()
    run_btn = st.button("🚀 توليد الجدول (Matrix Rota)", use_container_width=True)

# ----------------------
# وظائف GA
# ----------------------
@dataclass
class AIParams:
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

def ga_random(doctors:int, days:int, rest_bias:float)->np.ndarray:
    genes = np.full((doctors, days), -1, dtype=np.int16)
    mask = (np.random.rand(doctors, days) < (1.0 - rest_bias))
    genes[mask] = np.random.randint(0, len(SHIFT_AREA), size=mask.sum(), dtype=np.int16)
    return genes

def ga_decode(genes:np.ndarray, p:AIParams):
    per_doc = (genes >= 0).sum(axis=1)
    totals_shift = { (d, s):0 for d in range(p.days) for s in SHIFTS }
    totals_area  = { (d, s, a):0 for d in range(p.days) for s in SHIFTS for a in AREAS }
    for day in range(p.days):
        g = genes[:, day]
        for val in g[g>=0]:
            s, a = SHIFT_AREA[int(val)]
            totals_shift[(day, s)] += 1
            totals_area[(day, s, a)] += 1
    return per_doc, totals_shift, totals_area

def ga_fitness(genes:np.ndarray, p:AIParams)->float:
    per_doc, totals_shift, totals_area = ga_decode(genes, p)
    penalty = 0.0
    over = np.clip(per_doc - p.per_doc_cap, 0, None).sum()
    penalty += over * p.penalty_scale
    for day in range(p.days):
        for s in SHIFTS:
            t = totals_shift[(day, s)]
            if t < p.min_total: penalty += (p.min_total - t) * p.penalty_scale
            if t > p.max_total: penalty += (t - p.max_total) * p.penalty_scale
            for a in AREAS:
                req = p.coverage[a]
                ta = totals_area[(day, s, a)]
                if ta < req: penalty += (req - ta) * p.penalty_scale
    var = np.var(per_doc.astype(np.float32))
    penalty += var * p.balance_weight
    return -penalty

def ga_mutate(ind:np.ndarray, rate:float)->np.ndarray:
    out = ind.copy()
    mask = (np.random.rand(*out.shape) < rate)
    rnd = np.random.randint(-1, len(SHIFT_AREA), size=out.shape, dtype=np.int16)
    out[mask] = rnd[mask]
    return out

def ga_crossover(a:np.ndarray, b:np.ndarray)->np.ndarray:
    mask = (np.random.rand(*a.shape) < 0.5)
    return np.where(mask, a, b)

def ga_evolve(p:AIParams, progress=None)->np.ndarray:
    pop = [ga_random(p.doctors, p.days, p.rest_bias) for _ in range(p.population_size)]
    fits = np.array([ga_fitness(x, p) for x in pop], dtype=np.float64)
    elite_k = max(1, int(0.15 * p.population_size))
    for g in range(p.generations):
        order = np.argsort(fits)[::-1]
        elites = [pop[i] for i in order[:elite_k]]
        kids = elites.copy()
        while len(kids) < p.population_size:
            i, j = np.random.randint(0, p.population_size, size=2)
            child = ga_crossover(pop[order[i]], pop[order[j]])
            child = ga_mutate(child, p.mutation_rate)
            kids.append(child)
        pop = kids
        fits = np.array([ga_fitness(x, p) for x in pop], dtype=np.float64)
        if progress:
            progress.progress((g+1)/p.generations, text=f"تحسين التوزيع… جيل {g+1}/{p.generations}")
    return pop[int(np.argmax(fits))]

# ----------------------
# CP-SAT (اختياري)
# ----------------------
def cpsat_schedule(doctors:int, days:int, cap:int, min_total:int, max_total:int, coverage:Dict[str,int], time_limit:int, balance:bool):
    model = cp_model.CpModel()
    x = {}
    for d in range(doctors):
        for day in range(days):
            for s in SHIFTS:
                for a in AREAS:
                    x[(d, day, s, a)] = model.NewBoolVar(f"x_{d}_{day}_{s}_{a}")
    for day in range(days):
        for s in SHIFTS:
            for a in AREAS:
                model.Add(sum(x[(d, day, s, a)] for d in range(doctors)) >= int(coverage[a]))
            tot = [x[(d, day, s, a)] for d in range(doctors) for a in AREAS]
            model.Add(sum(tot) >= int(min_total))
            model.Add(sum(tot) <= int(max_total))
    for day in range(days):
        for d in range(doctors):
            model.Add(sum(x[(d, day, s, a)] for s in SHIFTS for a in AREAS) <= 1)
    totals = {}
    for d in range(doctors):
        tot = sum(x[(d, day, s, a)] for day in range(days) for s in SHIFTS for a in AREAS)
        model.Add(tot <= int(cap))
        totals[d] = tot
    if balance:
        approx = days * len(SHIFTS) * ((min_total + max_total) / 2.0)
        target = int(round(approx / max(1, doctors)))
        devs = []
        for d in range(doctors):
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
    for d in range(doctors):
        for day in range(days):
            for s in SHIFTS:
                for a in AREAS:
                    if solver.Value(x[(d, day, s, a)]) == 1:
                        rows.append({"الطبيب": f"طبيب {d+1}", "اليوم": day+1, "المناوبة": f"{s} - {a}"})
    return pd.DataFrame(rows), ("OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE")

# ----------------------
# تحويلات وعرض Matrix
# ----------------------
def to_matrix(df: pd.DataFrame, days:int, doctors_n:int) -> pd.DataFrame:
    doctors = [f"طبيب {i+1}" for i in range(doctors_n)]
    if df is None or df.empty:
        return pd.DataFrame(index=doctors, columns=range(1, days+1)).fillna("راحة")
    t = df.pivot_table(index="الطبيب", columns="اليوم", values="المناوبة", aggfunc="first").fillna("راحة")
    return t.reindex(index=doctors, columns=range(1, days+1), fill_value="راحة")

def cell_class(v:str)->str:
    if "☀️" in v: return "m"     # morning
    if "🌙" in v: return "e"     # evening
    if "🌃" in v: return "n"     # night
    return "r"                   # rest/empty

def render_matrix_html(roster: pd.DataFrame, year:int, month:int):
    # رأس الأعمدة: الأيام + اسم اليوم
    arabic_weekdays = {"Mon":"الاثنين","Tue":"الثلاثاء","Wed":"الأربعاء","Thu":"الخميس","Fri":"الجمعة","Sat":"السبت","Sun":"الأحد"}
    cols = roster.columns.tolist()
    header_cells = "".join([
        f"<th>{day}<br><small>{arabic_weekdays.get(calendar.day_abbr[calendar.weekday(year, int(month), int(day))], '')}</small></th>"
        for day in cols
    ])
    thead = f"<thead><tr><th>الطبيب</th>{header_cells}</tr></thead>"

    # جسم الجدول
    body_rows = []
    for doc in roster.index:
        tds = [f"<td class='doc'>{doc}</td>"]
        for day in cols:
            v = str(roster.loc[doc, day])
            tds.append(f"<td class='{cell_class(v)}'>{v}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"
    st.markdown(f"<div class='panel'><div style='overflow:auto; max-height:70vh;'><table class='rota'>{thead}{tbody}</table></div></div>", unsafe_allow_html=True)

# ----------------------
# الواجهة الرئيسية
# ----------------------
st.title("🗓️ Rota Matrix AI — الأيام أعمدة، الأطباء صفوف")

cov = {"فرز": cov_frz, "تنفسية": cov_tnf, "ملاحظة": cov_mlh, "انعاش": cov_inash}
min_needed = days * 3 * min_total
max_capacity = doctors_n * per_doc_cap

# KPIs
st.markdown("<div class='kpi'>", unsafe_allow_html=True)
st.markdown(f"<div class='box'><div class='label'>الأطباء</div><div class='value'>{doctors_n}</div></div>", unsafe_allow_html=True)
st.markdown(f"<div class='box'><div class='label'>الأيام</div><div class='value'>{days}</div></div>", unsafe_allow_html=True)
st.markdown(f"<div class='box'><div class='label'>سقف الطبيب</div><div class='value'>{per_doc_cap}</div></div>", unsafe_allow_html=True)
st.markdown(f"<div class='box'><div class='label'>الجدوى التقريبية</div><div class='value'>{min_needed} / {max_capacity}</div></div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

result_df, method_used = None, None
if run_btn:
    if engine == "ذكاء اصطناعي (GA)":
        if min_needed > max_capacity:
            st.warning("⚠️ الحد الأدنى المطلوب أكبر من السعة — سأرفع سقف الطبيب تلقائيًا قليلًا لمجاراة المتطلبات.")
            per_doc_cap = max(per_doc_cap, int(min_needed // max(1, doctors_n) + 1))
        with st.spinner("الذكاء الاصطناعي يعمل على تحسين الجدول…"):
            p = AIParams(
                days=days, doctors=doctors_n, per_doc_cap=per_doc_cap,
                coverage=cov, min_total=min_total, max_total=max_total,
                generations=gens, population_size=pop, mutation_rate=mut, rest_bias=rest_bias
            )
            progress = st.progress(0.0, text="بدء التطوير…")
            best = ga_evolve(p, progress=progress)
            # تحويل إلى سجل طويل
            rows = []
            for d in range(doctors_n):
                for day in range(days):
                    val = int(best[d, day])
                    if val >= 0:
                        s, a = SHIFT_AREA[val]
                        rows.append({"الطبيب": f"طبيب {d+1}", "اليوم": day+1, "المناوبة": f"{s} - {a}"})
            result_df = pd.DataFrame(rows)
            method_used = "GA"
            st.success("🎉 تم التوليد بالذكاء الاصطناعي!")
    else:
        if not ORTOOLS_AVAILABLE:
            st.error("CP-SAT غير متاح في هذه البيئة. استخدم وضع الذكاء الاصطناعي (GA).")
        else:
            with st.spinner("محاولة حل مثالي عبر CP-SAT…"):
                result_df, status = cpsat_schedule(
                    doctors=doctors_n, days=days, cap=per_doc_cap,
                    min_total=min_total, max_total=max_total, coverage=cov,
                    time_limit=cp_limit, balance=cp_balance
                )
                if result_df is None or result_df.empty:
                    st.error("لم يُعثر على حل ضمن المهلة. جرّب مهلة أطول أو خفّف القيود.")
                else:
                    method_used = f"CP-SAT ({status})"
                    st.success(f"✅ تم التوليد عبر {method_used}")

# ----------------------
# عرض Matrix + تصدير
# ----------------------
if result_df is not None and not result_df.empty:
    st.subheader(f"📅 Matrix Rota — الأيام أعمدة، الأطباء صفوف ({method_used})")
    rota = to_matrix(result_df, days, doctors_n)
    render_matrix_html(rota, int(year), int(month))

    with st.expander("📤 تصدير (اختياري)"):
        c1, c2 = st.columns(2)
        with c1:
            out = BytesIO()
            with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
                rota.to_excel(writer, sheet_name="Rota")
            st.download_button(
                "تنزيل Excel (Matrix)", out.getvalue(),
                file_name="rota_matrix.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        with c2:
            st.download_button(
                "تنزيل CSV (سجل طويل)", result_df.to_csv(index=False).encode("utf-8-sig"),
                file_name="assignments_long.csv", mime="text/csv",
                use_container_width=True
            )
else:
    st.info("اضبط الإعدادات في الشريط الجانبي ثم اضغط «🚀 توليد الجدول (Matrix Rota)».")

