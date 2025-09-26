# app.py
# -----------------------------------------------------------
# Rota Matrix - Header: DayName + Date | First Col: Doctors
# Each cell renders a "card" for the shift (Morning/Evening/Night/Rest).
# GA (AI) generator + optional CP-SAT (if OR-Tools is available).
# -----------------------------------------------------------
import streamlit as st
import pandas as pd
import numpy as np
import calendar
from io import BytesIO
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# Try OR-Tools (optional)
try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except Exception:
    ORTOOLS_AVAILABLE = False

# ----------------------
# UI & Styles
# ----------------------
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
    --m:#122a46; --e:#3b2e1e; --n:#2b2440; --r:#20232b;
  }
  .stApp { background: var(--bg); }
  h1,h2,h3 { color: var(--primary); }

  .panel { background:var(--card); border:1px solid var(--border); border-radius:16px; padding:12px; }

  /* Sticky matrix table */
  .rota { border-collapse: separate; border-spacing:0; width:100%; }
  .rota th, .rota td { border:1px solid var(--border); padding:6px 8px; vertical-align:middle; }
  .rota thead th { position:sticky; top:0; background:var(--card); z-index:2; text-align:center; }
  .rota td.doc { position:sticky; left:0; background:var(--card); z-index:1; font-weight:700; color:var(--primary); white-space:nowrap; }

  /* Shift cards inside cells */
  .cell { display:flex; gap:6px; flex-wrap:wrap; justify-content:center; }
  .card {
    display:inline-flex; align-items:center; justify-content:center;
    padding:6px 10px; border-radius:10px; font-size:13px; font-weight:600;
    box-shadow:0 1px 0 rgba(0,0,0,.04); border:1px solid var(--border);
    min-width:86px;
  }
  .m { background:var(--m); }  /* morning */
  .e { background:var(--e); }  /* evening */
  .n { background:var(--n); }  /* night */
  .r { background:var(--r); color:var(--muted); } /* rest */
  .sub { display:block; font-size:11px; font-weight:500; color:var(--muted); margin-top:2px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------
# Constants
# ----------------------
SHIFTS = ["☀️ صبح", "🌙 مساء", "🌃 ليل"]
AREAS  = ["فرز", "تنفسية", "ملاحظة", "انعاش"]
SHIFT_AREA = [(s, a) for s in SHIFTS for a in AREAS]  # 12 combos

# ----------------------
# Sidebar Controls
# ----------------------
with st.sidebar:
    st.header("⚙️ الإعدادات")
    year  = st.number_input("السنة", value=2025, step=1)
    month = st.number_input("الشهر", value=9, min_value=1, max_value=12, step=1)
    days  = st.slider("عدد الأيام", 5, 31, 30)
    doctors_n  = st.slider("عدد الأطباء", 5, 120, 40)
    per_doc_cap = st.slider("سقف الشفتات للطبيب", 1, 60, 18)

    st.divider()
    st.caption("حدود إجمالي كل وردية (يوميًا)")
    min_total = st.slider("أدنى إجمالي للوردية", 0, 80, 10)
    max_total = st.slider("أقصى إجمالي للوردية", 0, 100, 13)

    st.caption("الحد الأدنى لتغطية الأقسام (في كل وردية/يوم)")
    c1, c2 = st.columns(2)
    with c1:
        cov_frz = st.number_input("فرز", 0, 40, 2)
        cov_tnf = st.number_input("تنفسية", 0, 40, 1)
    with c2:
        cov_mlh = st.number_input("ملاحظة", 0, 40, 4)
        cov_inash = st.number_input("إنعاش", 0, 40, 3)

    st.divider()
    engine = st.radio("طريقة التوليد", ["ذكاء اصطناعي (GA)", "محلّل قيود (CP-SAT)"], index=0)
    if engine == "ذكاء اصطناعي (GA)":
        gens = st.slider("عدد الأجيال (GA)", 10, 500, 120)
        pop  = st.slider("حجم المجتمع (GA)", 10, 200, 40)
        mut  = st.slider("معدل الطفرة (GA)", 0.0, 0.2, 0.03, 0.01)
        rest_bias = st.slider("ميل للراحة (GA)", 0.0, 0.95, 0.6, 0.05)
    else:
        cp_limit   = st.slider("مهلة CP-SAT (ثواني)", 5, 300, 90)
        cp_balance = st.checkbox("توازن الأحمال هدفًا إضافيًا", True)

    st.divider()
    run_btn = st.button("🚀 توليد الجدول (Matrix Cards)", use_container_width=True)

# ----------------------
# GA Generator
# ----------------------
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

def ga_random(doctors:int, days:int, rest_bias:float)->np.ndarray:
    genes = np.full((doctors, days), -1, dtype=np.int16)
    mask  = (np.random.rand(doctors, days) < (1.0 - rest_bias))
    genes[mask] = np.random.randint(0, len(SHIFT_AREA), size=mask.sum(), dtype=np.int16)
    return genes

def ga_decode(genes:np.ndarray, p:GAParams):
    per_doc = (genes >= 0).sum(axis=1)
    totals_shift = { (d, s):0 for d in range(p.days) for s in SHIFTS }
    totals_area  = { (d, s, a):0 for d in range(p.days) for s in SHIFTS for a in AREAS }
    for day in range(p.days):
        g = genes[:, day]
        for v in g[g>=0]:
            s, a = SHIFT_AREA[int(v)]
            totals_shift[(day, s)] += 1
            totals_area[(day, s, a)] += 1
    return per_doc, totals_shift, totals_area

def ga_fitness(genes:np.ndarray, p:GAParams)->float:
    per_doc, totals_shift, totals_area = ga_decode(genes, p)
    pen = 0.0
    over = np.clip(per_doc - p.per_doc_cap, 0, None).sum()
    pen += over * p.penalty_scale
    for day in range(p.days):
        for s in SHIFTS:
            t = totals_shift[(day, s)]
            if t < p.min_total: pen += (p.min_total - t) * p.penalty_scale
            if t > p.max_total: pen += (t - p.max_total) * p.penalty_scale
            for a in AREAS:
                req = p.coverage[a]
                ta = totals_area[(day, s, a)]
                if ta < req: pen += (req - ta) * p.penalty_scale
    var = np.var(per_doc.astype(np.float32))
    pen += var * p.balance_weight
    return -pen

def ga_mutate(ind:np.ndarray, rate:float)->np.ndarray:
    out = ind.copy()
    mask = (np.random.rand(*out.shape) < rate)
    rnd  = np.random.randint(-1, len(SHIFT_AREA), size=out.shape, dtype=np.int16)
    out[mask] = rnd[mask]
    return out

def ga_cross(a:np.ndarray, b:np.ndarray)->np.ndarray:
    mask = (np.random.rand(*a.shape) < 0.5)
    return np.where(mask, a, b)

def ga_evolve(p:GAParams, progress=None)->np.ndarray:
    pop = [ga_random(p.doctors, p.days, p.rest_bias) for _ in range(p.population_size)]
    fits = np.array([ga_fitness(x, p) for x in pop], dtype=np.float64)
    elite_k = max(1, int(0.15 * p.population_size))
    for g in range(p.generations):
        order = np.argsort(fits)[::-1]
        elites = [pop[i] for i in order[:elite_k]]
        kids = elites.copy()
        while len(kids) < p.population_size:
            i, j = np.random.randint(0, p.population_size, size=2)
            child = ga_cross(pop[order[i]], pop[order[j]])
            child = ga_mutate(child, p.mutation_rate)
            kids.append(child)
        pop = kids
        fits = np.array([ga_fitness(x, p) for x in pop], dtype=np.float64)
        if progress:
            progress.progress((g+1)/p.generations, text=f"تحسين الجدول… جيل {g+1}/{p.generations}")
    return pop[int(np.argmax(fits))]

# ----------------------
# Optional CP-SAT
# ----------------------
def cpsat_schedule(doctors:int, days:int, cap:int, min_total:int, max_total:int, cov:Dict[str,int], time_limit:int, balance:bool):
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
                model.Add(sum(x[(d, day, s, a)] for d in range(doctors)) >= int(cov[a]))
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
    solver = cp_model.CpS_


