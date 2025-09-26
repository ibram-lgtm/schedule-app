# app.py
# -----------------------------------------------------------
# Streamlit Rota Scheduler (AI-based GA + optional CP-SAT)
# واجهة حديثة + توليد الجدول + عرض Rota View كبطاقات
# -----------------------------------------------------------
import streamlit as st
import pandas as pd
import numpy as np
import calendar
from io import BytesIO
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# حاول استخدام OR-Tools إن توفّر (اختياري)
try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except Exception:
    ORTOOLS_AVAILABLE = False

# =========================
# إعدادات عامة + ستايل UI
# =========================
st.set_page_config(page_title="Rota AI Pro", layout="wide")

CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
  * { font-family: 'Tajawal', sans-serif; }
  :root {
    --primary: #5b74ff;
    --bg: #f5f7fb;
    --text: #1c1f2a;
    --card: #ffffff;
    --border: #e6e8ef;
    --muted: #6b7280;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
  }
  body[data-theme="dark"] {
    --primary: #93a2ff;
    --bg: #0e1117;
    --text: #f5f6f8;
    --card: #181b21;
    --border: #2b2f37;
    --muted: #9aa1ae;
  }
  .stApp { background: var(--bg); }
  h1, h2, h3 { color: var(--primary); }
  .panel {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 16px; padding: 16px;
  }
  .kpi { display: grid; grid-template-columns: repeat(4, minmax(160px,1fr)); gap: 12px; }
  .kpi .box {
    background: var(--card); border:1px solid var(--border); border-radius:12px;
    padding:12px;
  }
  .kpi .label { font-size: 12px; color: var(--muted); }
  .kpi .value { font-size: 22px; font-weight: 700; color: var(--text); }

  /* Rota View cards */
  .doctor-section { margin: 18px 0 26px; }
  .doctor-name {
    font-weight: 700; color: var(--primary); margin-bottom: 10px; font-size: 18px;
  }
  .rota-grid { display: grid; grid-template-columns: repeat(7, minmax(140px,1fr)); gap: 8px; }
  .day-card {
    background: var(--card); border:1px solid var(--border); border-radius:12px;
    min-height: 92px; padding: 10px; text-align:center; display:flex; flex-direction:column; justify-content:center;
  }
  .day-card strong { font-size: 14px; color: var(--text); }
  .day-card span { font-size: 13px; color: var(--muted); }

  .shift-morning { background: #eaf3ff; }
  .shift-evening { background: #fff2e6; }
  .shift-night   { background: #eee8ff; }
  .shift-rest    { background: #f2f3f7; }

  body[data-theme="dark"] .shift-morning { background: #15243a; }
  body[data-theme="dark"] .shift-evening { background: #3b2e1e; }
  body[data-theme="dark"] .shift-night   { background: #2b2440; }
  body[data-theme="dark"] .shift-rest    { background: #22252d; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# =========================
# ثوابت
# =========================
SHIFTS = ["☀️ صبح", "🌙 مساء", "🌃 ليل"]
AREAS = ["فرز", "تنفسية", "ملاحظة", "انعاش"]
SHIFT_AREA = [(s, a) for s in SHIFTS for a in AREAS]  # 12 تركيبة

# =========================
# Sidebar Controls
# =========================
with st.sidebar:
    st.header("⚙️ إعدادات الأداة")
    year = st.number_input("السنة", value=2025, step=1)
    month = st.number_input("الشهر", value=9, min_value=1, max_value=12, step=1)
    days = st.slider("عدد الأيام", 28, 31, 30)
    doctors_n = st.slider("عدد الأطباء", 5, 120, 65)
    per_doc_cap = st.slider("الحد الأعلى للشفتات لكل طبيب", 1, 40, 18)
    st.divider()
    st.caption("حدود إجمالي كل وردية (يوميًا)")
    min_total = st.slider("أدنى إجمالي للوردية", 0, 50, 10)
    max_total = st.slider("أقصى إجمالي للوردية", 0, 60, 13)
    st.caption("الحد الأدنى لتغطية الأقسام (في كل وردية/يوم)")
    colA, colB = st.columns(2)
    with colA:
        cov_frz = st.number_input("فرز", 0, 30, 2)
        cov_tnf = st.number_input("تنفسية", 0, 30, 1)
    with colB:
        cov_mlh = st.number_input("ملاحظة", 0, 30, 4)
        cov_inash = st.number_input("إنعاش", 0, 30, 3)

    st.divider()
    st.caption("محرك التوليد")
    use_ai = st.radio("طريقة التوليد", ["ذكاء اصطناعي (GA)", "محلّل قيود (CP-SAT)"], index=0,
                      help="الذكاء الاصطناعي يعطي حلولًا جيدة سريعًا، CP-SAT يحاول حلولًا مثالية إذا كانت البيئة تدعم OR-Tools.")
    if use_ai == "ذكاء اصطناعي (GA)":
        gens = st.slider("عدد الأجيال (GA)", 10, 400, 120)
        pop = st.slider("حجم المجتمع (GA)", 10, 100, 40)
        mut = st.slider("معدل الطفرة (GA)", 0.0, 0.2, 0.03, 0.01)
        rest_bias = st.slider("ميل للراحة (GA)", 0.0, 0.95, 0.6, 0.05,
                              help="كلما زاد كانت البداية تميل لإجازات أكثر ثم يتحسن الحل تدريجيًا.")
    else:
        cp_limit = st.slider("مهلة CP-SAT (ثواني)", 5, 180, 60)
        cp_balance = st.checkbox("توازن الأحمال هدفًا إضافيًا", True)
    st.divider()
    generate = st.button("🚀 توليد الجدول الآن", use_container_width=True)

# =========================
# وظائف التوليد (GA)
# =========================
def ga_random_individual(doctors: int, days: int, rest_bias: float) -> np.ndarray:
    genes = np.full((doctors, days), -1, dtype=np.int16)
    assign_prob = 1.0 - rest_bias
    rand_vals = np.random.rand(doctors, days)
    mask = rand_vals < assign_prob
    genes[mask] = np.random.randint(0, len(SHIFT_AREA), size=mask.sum(), dtype=np.int16)
    return genes

def ga_decode_counts(genes: np.ndarray, min_total: int, max_total: int,
                     coverage: Dict[str, int]) -> Tuple[np.ndarray, Dict, Dict]:
    D, T = genes.shape
    per_doc = (genes >= 0).sum(axis=1)
    totals_shift = {}
    totals_area = {}
    for day in range(T):
        for s in SHIFTS:
            totals_shift[(day, s)] = 0
            for a in AREAS:
                totals_area[(day, s, a)] = 0
    for day in range(T):
        g_day = genes[:, day]
        active = g_day[g_day >= 0]
        for val in active:
            s, a = SHIFT_AREA[int(val)]
            totals_shift[(day, s)] += 1
            totals_area[(day, s, a)] += 1
    return per_doc, totals_shift, totals_area

def ga_fitness(genes: np.ndarray, per_doc_cap: int, min_total: int, max_total: int,
               coverage: Dict[str, int], balance_weight: float = 1.0, penalty_scale: float = 50.0) -> float:
    per_doc, totals_shift, totals_area = ga_decode_counts(genes, min_total, max_total, coverage)
    penalty = 0.0
    # سقف الطبيب
    over = np.clip(per_doc - per_doc_cap, 0, None).sum()
    penalty += over * penalty_scale
    # حدود كل وردية/يوم + تغطيات الأقسام
    T = genes.shape[1]
    for day in range(T):
        for s in SHIFTS:
            t = totals_shift[(day, s)]
            if t < min_total:
                penalty += (min_total - t) * penalty_scale
            if t > max_total:
                penalty += (t - max_total) * penalty_scale
            for a in AREAS:
                req = coverage[a]
                ta = totals_area[(day, s, a)]
                if ta < req:
                    penalty += (req - ta) * penalty_scale
    # توازن الأحمال (خفض التفاوت)
    var = np.var(per_doc.astype(np.float32))
    penalty += var * balance_weight
    return -penalty  # أعلى أفضل

def ga_evolve(doctors: int, days: int, per_doc_cap: int, min_total: int, max_total: int,
              coverage: Dict[str, int], generations: int, population: int,
              mutation_rate: float, rest_bias: float, progress=None) -> Tuple[np.ndarray, List[float]]:
    pop = [ga_random_individual(doctors, days, rest_bias) for _ in range(population)]
    fit = np.array([ga_fitness(ind, per_doc_cap, min_total, max_total, coverage) for ind in pop], dtype=np.float64)
    history = [float(fit.max())]
    elite_k = max(1, int(0.15 * population))

    for g in range(generations):
        idx = np.argsort(fit)[::-1]
        elites = [pop[i] for i in idx[:elite_k]]
        # إنتاج أبناء
        children = elites.copy()
        while len(children) < population:
            i, j = np.random.randint(0, population, size=2)
            p1, p2 = pop[idx[i]], pop[idx[j]]
            mask = np.random.rand(doctors, days) < 0.5
            child = np.where(mask, p1, p2)
            # طفرة
            mut_mask = np.random.rand(doctors, days) < mutation_rate
            rand_vals = np.random.randint(-1, len(SHIFT_AREA), size=(doctors, days), dtype=np.int16)
            child[mut_mask] = rand_vals[mut_mask]
            children.append(child)
        pop = children
        fit = np.array([ga_fitness(ind, per_doc_cap, min_total, max_total, coverage) for ind in pop], dtype=np.float64)
        history.append(float(fit.max()))
        if progress:
            progress.progress((g + 1) / generations, text=f"تحسين التوزيع بالذكاء الاصطناعي… جيل {g+1}/{generations}")
    best_idx = int(np.argmax(fit))
    return pop[best_idx], history

# =========================
# CP-SAT (اختياري)
# =========================
def cpsat_schedule(doctors: int, days: int, per_doc_cap: int, min_total: int, max_total: int,
                   coverage: Dict[str, int], time_limit: int, balance: bool):
    model = cp_model.CpModel()
    x = {}
    for d in range(doctors):
        for day in range(days):
            for s in SHIFTS:
                for a in AREAS:
                    x[(d, day, s, a)] = model.NewBoolVar(f"x_{d}_{day}_{s}_{a}")
    # قيود
    for day in range(days):
        for s in SHIFTS:
            # تغطيات الأقسام
            for a in AREAS:
                model.Add(sum(x[(d, day, s, a)] for d in range(doctors)) >= int(coverage[a]))
            # إجمالي الوردية
            tot = [x[(d, day, s, a)] for d in range(doctors) for a in AREAS]
            model.Add(sum(tot) >= int(min_total))
            model.Add(sum(tot) <= int(max_total))
    # وردية واحدة يوميًا للطبيب
    for day in range(days):
        for d in range(doctors):
            model.Add(sum(x[(d, day, s, a)] for s in SHIFTS for a in AREAS) <= 1)
    # سقف الطبيب
    totals = {}
    for d in range(doctors):
        tot = sum(x[(d, day, s, a)] for day in range(days) for s in SHIFTS for a in AREAS)
        model.Add(tot <= int(per_doc_cap))
        totals[d] = tot
    # هدف توازن (اختياري)
    if balance:
        approx_total = days * len(SHIFTS) * ((min_total + max_total) / 2.0)
        target = int(round(approx_total / max(1, doctors)))
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
                        rows.append({"الطبيب": f"طبيب {d+1}", "اليوم": day + 1, "المناوبة": f"{s} - {a}"})
    return pd.DataFrame(rows), ("OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE")

# =========================
# تحويلات وعرض
# =========================
def to_roster(df: pd.DataFrame, days: int, doctors_n: int) -> pd.DataFrame:
    doctors = [f"طبيب {i+1}" for i in range(doctors_n)]
    if df is None or df.empty:
        return pd.DataFrame(index=doctors, columns=range(1, days + 1)).fillna("راحة")
    t = df.pivot_table(index="الطبيب", columns="اليوم", values="المناوبة", aggfunc="first").fillna("راحة")
    return t.reindex(index=doctors, columns=range(1, days + 1), fill_value="راحة")

def shift_class(label: str) -> str:
    if "☀️" in label: return "shift-morning"
    if "🌙" in label: return "shift-evening"
    if "🌃" in label: return "shift-night"
    if "راحة" in label: return "shift-rest"
    return ""

def render_rota_cards(roster: pd.DataFrame, year: int, month: int):
    arabic_weekdays = {"Mon": "الاثنين", "Tue": "الثلاثاء", "Wed": "الأربعاء",
                       "Thu": "الخميس", "Fri": "الجمعة", "Sat": "السبت", "Sun": "الأحد"}
    for doc in roster.index:
        st.markdown(f"<div class='doctor-section'><div class='doctor-name'>👨‍⚕️ {doc}</div>", unsafe_allow_html=True)
        st.markdown("<div class='rota-grid'>", unsafe_allow_html=True)
        for day in roster.columns:
            val = roster.loc[doc, day]
            try:
                wd = calendar.day_abbr[calendar.weekday(year, int(month), int(day))]
                wd_ar = arabic_weekdays.get(wd, wd)
            except Exception:
                wd_ar = ""
            st.markdown(
                f"""
                <div class="day-card {shift_class(str(val))}">
                  <strong>{day} <small>({wd_ar})</small></strong>
                  <span>{val}</span>
                </div>
                """, unsafe_allow_html=True
            )
        st.markdown("</div></div>", unsafe_allow_html=True)

# =========================
# Main Panel
# =========================
st.title("🗓️ Rota AI Pro — مولّد مناوبات ذكي")
st.markdown("واجهة حديثة لتوليد جداول المناوبات اعتمادًا على **ذكاء اصطناعي (GA)** مع خيار **CP-SAT** عندما يكون متاحًا.")

coverage = {"فرز": cov_frz, "تنفسية": cov_tnf, "ملاحظة": cov_mlh, "انعاش": cov_inash}

# مؤشرات سريعة
k1, k2, k3, k4 = st.columns(4)
with k1: st.metric("الأطباء", doctors_n)
with k2: st.metric("الأيام", days)
with k3: st.metric("حد الطبيب (شفتات)", per_doc_cap)
with k4: st.metric("OR-Tools", "جاهز" if ORTOOLS_AVAILABLE else "غير متاح")

result_df = None
method_used = None
history = None

if generate:
    # فحص جدوى تقريبي
    min_needed = days * len(SHIFTS) * min_total
    max_capacity = doctors_n * per_doc_cap
    if min_needed > max_capacity:
        st.warning(f"⚠️ غير ممكن نظريًا: الحد الأدنى المطلوب {min_needed} > السعة {max_capacity}. "
                   f"ارفع حد الطبيب أو خفّض الحدود الدنيا.")
    if use_ai == "ذكاء اصطناعي (GA)":
        progress = st.progress(0.0, text="بدء التوليد بالذكاء الاصطناعي…")
        best, history = ga_evolve(
            doctors=doctors_n, days=days, per_doc_cap=per_doc_cap,
            min_total=min_total, max_total=max_total, coverage=coverage,
            generations=gens, population=pop, mutation_rate=mut, rest_bias=rest_bias,
            progress=progress
        )
        # تحويل إلى DF
        rows = []
        for d in range(doctors_n):
            for day in range(days):
                val = int(best[d, day])
                if val >= 0:
                    s, a = SHIFT_AREA[val]
                    rows.append({"الطبيب": f"طبيب {d+1}", "اليوم": day + 1, "المناوبة": f"{s} - {a}"})
        result_df = pd.DataFrame(rows)
        method_used = "GA"
        st.success("🎉 تم التوليد بالذكاء الاصطناعي!")
    else:
        if not ORTOOLS_AVAILABLE:
            st.error("محلّل القيود (CP-SAT) غير متاح في هذه البيئة. استخدم وضع الذكاء الاصطناعي (GA).")
        else:
            with st.spinner("محاولة إيجاد حل مثالي عبر CP-SAT…"):
                result_df, status = cpsat_schedule(
                    doctors=doctors_n, days=days, per_doc_cap=per_doc_cap,
                    min_total=min_total, max_total=max_total, coverage=coverage,
                    time_limit=cp_limit, balance=cp_balance
                )
                if result_df is None or result_df.empty:
                    st.error("لم يتم إيجاد حل ضمن المهلة. جرّب مهلة أطول أو خفّف القيود.")
                else:
                    method_used = f"CP-SAT ({status})"
                    st.success(f"✅ تم التوليد عبر {method_used}")

# =========================
# عرض النتائج — Rota View
# =========================
if result_df is not None and not result_df.empty:
    # لوحة موجزة
    colL, colR = st.columns([1, 1])
    with colL:
        st.subheader("📊 إحصائيات سريعة")
        per_doc = result_df["الطبيب"].value_counts().sort_index()
        st.dataframe(per_doc.rename("عدد الشفتات").to_frame(), use_container_width=True)
    with colR:
        st.subheader("ℹ️ تفاصيل الجيل (لـ GA)")
        if history:
            st.line_chart(history, height=180)
        else:
            st.info("لا توجد بيانات GA لأن التوليد تم عبر CP-SAT.")

    st.divider()
    st.subheader(f"📅 Rota View — بطاقات الجدول ({method_used})")
    roster = to_roster(result_df, days, doctors_n)
    render_rota_cards(roster, int(year), int(month))

    # تصدير (اختياري)
    with st.expander("📤 تصدير"):
        c1, c2 = st.columns(2)
        with c1:
            out = BytesIO()
            with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
                roster.to_excel(writer, sheet_name="Rota")
            st.download_button("تنزيل Excel", data=out.getvalue(),
                               file_name="rota.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with c2:
            st.download_button("تنزيل CSV (سجل طويل)",
                               data=result_df.to_csv(index=False).encode("utf-8-sig"),
                               file_name="assignments.csv", mime="text/csv")
else:
    st.info("اضبط الإعدادات من الشريط الجانبي ثم اضغط «🚀 توليد الجدول الآن».")

