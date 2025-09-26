# app.py — ED Rota (Cards Grid Views + By-Shift Grid + Styled Excel, Arabic/English)
# ----------------------------------------------------------------------------------
# - 3 views: Day×Doctor (rows=days, cols=doctors), Doctor×Day (rows=doctors, cols=days),
#            Day×Shift (cols=F1..C3; cells contain doctor name cards)
# - CP-SAT solver with slacks; highlights gaps & shows remaining capacity
# - Bilingual UI with stable keys; styled Excel export (Rota, Coverage gaps, Remaining, ByShift)

import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from dataclasses import dataclass
from typing import Dict, List
import calendar
import html

# ===== Optional deps =====
try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except Exception:
    ORTOOLS_AVAILABLE = False

try:
    import xlsxwriter
    XLSX_AVAILABLE = True
except Exception:
    XLSX_AVAILABLE = False

st.set_page_config(page_title="ED Rota", layout="wide")

# ================= i18n =================
I18N = {
    "ar": {
        "general": "عام",
        "language": "اللغة",
        "arabic": "العربية",
        "english": "English",
        "year": "السنة",
        "month": "الشهر",
        "days": "عدد الأيام",
        "rules": "القواعد",
        "coverage": "التغطية لكل منطقة/وردية",
        "group_caps": "سقوف المجموعات الشهرية",
        "run": "تشغيل المُحلل",
        "generate": "إنشاء الجدول",
        "view_mode": "طريقة العرض",
        "view_day_doctor": "يوم × طبيب",
        "view_doctor_day": "طبيب × يوم",
        "view_day_shift": "يوم × شفت",
        "cards_view": "عرض الشبكة (بطاقات)",
        "table_view": "عرض الجدول (اختياري)",
        "sheet": "الجدول (صفوف=أيام، أعمدة=أطباء)",
        "gaps": "النواقص (Coverage gaps)",
        "remain": "الأطباء ذوو السعة المتبقية",
        "export": "تصدير",
        "download_xlsx": "تنزيل Excel (منسّق)",
        "doctors_tab": "الأطباء وتفضيلاتهم",
        "add_list": "إضافة أطباء (سطر لكل اسم)",
        "append": "إضافة",
        "remove_doc": "حذف طبيب",
        "remove": "حذف",
        "edit_one": "تعديل طبيب",
        "doctor": "الطبيب",
        "group": "المجموعة",
        "cap": "السقف الشهري (عدد الشفتات)",
        "allowed_shifts": "الفترات المسموح بها",
        "offdays": "أيام الإجازة (حتى 3، مفصولة بفواصل)",
        "rules_global": "قواعد عامة",
        "min_off": "أقل عدد أيام إجازة/شهر",
        "max_consec": "أقصى أيام عمل متتالية",
        "min_rest": "أقل ساعات راحة بين الشفتات",
        "by_shift": "حسب الوردية",
        "sel_day": "اليوم",
        "sel_area": "القسم",
        "sel_shift": "الوردية",
        "who": "المكلفون",
        "ok_no_gaps": "تمت التغطية بلا نواقص",
        "need_generate": "اضغط تشغيل المُحلل أولاً.",
        "requires_ortools": "هذه الميزة تتطلب OR-Tools على الخادم.",
        "weekday": ["الاثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"],
        "day": "اليوم",
        "by_shift_grid": "شبكة يوم × شفت (البطاقات = أسماء الأطباء)",
    },
    "en": {
        "general": "General",
        "language": "Language",
        "arabic": "Arabic",
        "english": "English",
        "year": "Year",
        "month": "Month",
        "days": "Days",
        "rules": "Rules",
        "coverage": "Coverage per area/shift",
        "group_caps": "Group monthly caps",
        "run": "Run solver",
        "generate": "Generate",
        "view_mode": "View mode",
        "view_day_doctor": "Day × Doctor",
        "view_doctor_day": "Doctor × Day",
        "view_day_shift": "Day × Shift",
        "cards_view": "Cards grid",
        "table_view": "Table view (optional)",
        "sheet": "Sheet (rows=days, cols=doctors)",
        "gaps": "Coverage gaps",
        "remain": "Doctors with remaining capacity",
        "export": "Export",
        "download_xlsx": "Download Excel (styled)",
        "doctors_tab": "Doctors & Preferences",
        "add_list": "Add doctors (one per line)",
        "append": "Append",
        "remove_doc": "Remove doctor",
        "remove": "Remove",
        "edit_one": "Edit one doctor",
        "doctor": "Doctor",
        "group": "Group",
        "cap": "Monthly cap (shifts)",
        "allowed_shifts": "Allowed shifts",
        "offdays": "Off-days (up to 3, comma-separated)",
        "rules_global": "Global rules",
        "min_off": "Min off-days / month",
        "max_consec": "Max consecutive duty days",
        "min_rest": "Min rest hours between shifts",
        "by_shift": "By shift",
        "sel_day": "Day",
        "sel_area": "Area",
        "sel_shift": "Shift",
        "who": "Assigned",
        "ok_no_gaps": "Coverage achieved with no gaps",
        "need_generate": "Run the solver first.",
        "requires_ortools": "This feature requires OR-Tools on the server.",
        "weekday": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
        "day": "Day",
        "by_shift_grid": "Day × Shift grid (cards = doctor names)",
    }
}
def L(k): return I18N[st.session_state.get("lang","en")][k]

# ===== init session =====
def _init_session():
    ss = st.session_state
    if "lang" not in ss: ss.lang = "en"
    if "year" not in ss: ss.year = 2025
    if "month" not in ss: ss.month = 9
    if "days" not in ss: ss.days = 30
    if "result_df" not in ss: ss.result_df = pd.DataFrame()
    if "gaps" not in ss: ss.gaps = pd.DataFrame()
    if "remain" not in ss: ss.remain = pd.DataFrame()
    if "view_mode" not in ss: ss.view_mode = "day_doctor"
_init_session()

# ===== Static labels =====
AREAS = ["fast", "resp_triage", "acute", "resus"]
SHIFTS = ["morning", "evening", "night"]
AREA_LABEL = {
    "en": {"fast":"Fast track","resp_triage":"Respiratory triage","acute":"Acute care unit","resus":"Resuscitation area"},
    "ar": {"fast":"المسار السريع","resp_triage":"فرز تنفسي","acute":"العناية الحادة","resus":"الإنعاش"}
}
SHIFT_LABEL = {
    "en": {"morning":"Morning 07:00–15:00","evening":"Evening 15:00–23:00","night":"Night 23:00–07:00"},
    "ar": {"morning":"صباح 07:00–15:00","evening":"مساء 15:00–23:00","night":"ليل 23:00–07:00"}
}
AREA_CODE = {"fast":"F","resp_triage":"R","acute":"A","resus":"C"}
SHIFT_CODE = {"morning":"1","evening":"2","night":"3"}
DIGIT_TO_SHIFT = {"1":"morning","2":"evening","3":"night"}
LETTER_TO_AREA = {"F":"fast","R":"resp_triage","A":"acute","C":"resus"}

SHIFT_COLS_ORDER = ["F1","F2","F3","R1","R2","R3","A1","A2","A3","C1","C2","C3"]

def code_for(area,shift): return f"{AREA_CODE[area]}{SHIFT_CODE[shift]}"

# ===== Defaults per brief =====
DEFAULT_COVERAGE = {
    ("fast","morning"):2, ("fast","evening"):2, ("fast","night"):2,
    ("resp_triage","morning"):1, ("resp_triage","evening"):1, ("resp_triage","night"):1,
    ("acute","morning"):3, ("acute","evening"):4, ("acute","night"):3,
    ("resus","morning"):3, ("resus","evening"):3, ("resus","night"):3,
}
GROUP_CAP = {"senior":16,"g1":18,"g2":18,"g3":18,"g4":18,"g5":18}
GROUP_AREAS = {
    "senior":{"resus"},
    "g1":{"resp_triage"},
    "g2":{"acute"},
    "g3":{"fast","acute"},
    "g4":{"resp_triage","fast","acute"},
    "g5":{"acute","resus"},
}
FIXED_SHIFT = {"Dr.Sharif":{"night"}, "Dr.Rashif":{"morning"}, "Dr.Jobi":{"evening"},
               "Dr.Bashir":{"morning"}, "Dr.nashwa":{"morning"}, "Dr.Lena":{"morning"}}
DEFAULT_GROUP_MAP = {
    # seniors
    "Dr. Abdullah Alnughamishi":"senior","Dr. Samar Alruwaysan":"senior","Dr. Ali Alismail":"senior",
    "Dr. Hussain Alturifi":"senior","Dr. Abdullah Alkhalifah":"senior","Dr. Rayan Alaboodi":"senior",
    "Dr. Jamal Almarshadi":"senior","Dr. Emad Abdulkarim":"senior","Dr. Marwan Alrayhan":"senior",
    "Dr. Ahmed Almohimeed":"senior","Dr. Abdullah Alsindi":"senior","Dr. Yousef Alharbi":"senior",
    # g1
    "Dr.Sharif":"g1","Dr.Rashif":"g1","Dr.Jobi":"g1","Dr.Lucky":"g1",
    # g2
    "Dr.Bashir":"g2","Dr. AHMED MAMDOH":"g2","Dr. HAZEM ATTYAH":"g2","Dr. OMAR ALSHAMEKH":"g2","Dr. AYMEN MKHTAR":"g2",
    # g3
    "Dr.nashwa":"g3","Dr. Abdulaziz bin marahad":"g3","Dr. Mohmmed almutiri":"g3","Dr. Lulwah":"g3","Dr.Ibrahim":"g3",
    "Dr. Kaldon":"g3","Dr. Osama":"g3","Dr. Salman":"g3","Dr. Hajer":"g3","Dr. Randa":"g3","Dr. Esa":"g3","Dr. Fahad":"g3",
    "Dr. Abdulrahman1":"g3","Dr. Abdulrahman2":"g3","Dr. Mohammed alrashid":"g3",
    # g4
    "Dr.Lena":"g4","Dr.Essra":"g4","Dr.fahimah":"g4","Dr.mohammed bajaber":"g4","Dr.Sulaiman Abker":"g4",
    # g5
    "Dr.Shouq":"g5","Dr.Rayan":"g5","Dr abdullah aljalajl":"g5","Dr. AMIN MOUSA":"g5","Dr. AHMED ALFADLY":"g5",
}
ALL_DOCTORS = list(DEFAULT_GROUP_MAP.keys())

# ===== State for doctors/rules =====
def ensure_roster_state():
    ss = st.session_state
    if "cov" not in ss: ss.cov = DEFAULT_COVERAGE.copy()
    if "group_map" not in ss: ss.group_map = DEFAULT_GROUP_MAP.copy()
    if "doctors" not in ss: ss.doctors = ALL_DOCTORS.copy()
    if "cap_map" not in ss: ss.cap_map = {n: GROUP_CAP[ss.group_map[n]] for n in ss.doctors}
    if "allowed_shifts" not in ss:
        base = {n:set(SHIFTS) for n in ss.doctors}
        for n, only in FIXED_SHIFT.items():
            if n in base: base[n] = set(only)
        ss.allowed_shifts = base
    if "offdays" not in ss: ss.offdays = {n:set() for n in ss.doctors}
    if "min_off" not in ss: ss.min_off = 12
    if "max_consec" not in ss: ss.max_consec = 6
    if "min_rest" not in ss: ss.min_rest = 16
ensure_roster_state()

# ===== Sidebar (language + globals) =====
with st.sidebar:
    st.header(L("general"))
    lang_choice = st.radio(L("language"), [I18N["ar"]["arabic"], I18N["en"]["english"]],
                           index=0 if st.session_state.lang=="ar" else 1, horizontal=True, key="lang_radio")
    st.session_state.lang = "ar" if lang_choice == I18N["ar"]["arabic"] else "en"

    st.number_input(L("year"), 2024, 2100, key="year_input", value=st.session_state.year)
    st.number_input(L("month"), 1, 12, key="month_input", value=st.session_state.month)
    st.slider(L("days"), 28, 31, key="days_slider", value=st.session_state.days)
    st.session_state.year = st.session_state.year_input
    st.session_state.month = st.session_state.month_input
    st.session_state.days = st.session_state.days_slider

    st.markdown(f"**{L('rules_global')}**")
    st.number_input(L("min_off"), 0, 31, key="min_off_input", value=st.session_state.min_off)
    st.number_input(L("max_consec"), 1, 30, key="max_consec_input", value=st.session_state.max_consec)
    st.number_input(L("min_rest"), 0, 24, key="min_rest_input", value=st.session_state.min_rest)
    st.session_state.min_off = st.session_state.min_off_input
    st.session_state.max_consec = st.session_state.max_consec_input
    st.session_state.min_rest = st.session_state.min_rest_input

# ===== Tabs =====
tab_rules, tab_docs, tab_gen, tab_export = st.tabs(
    [L("rules"), L("doctors_tab"), L("generate"), L("export")]
)

# ---------- Rules tab ----------
with tab_rules:
    st.subheader(L("coverage"))
    cols = st.columns(3)
    new_cov = st.session_state.cov.copy()
    for i, area in enumerate(AREAS):
        with cols[i%3]:
            st.markdown(f"**{AREA_LABEL[st.session_state.lang][area]}**")
            for sh in SHIFTS:
                key = f"cov_{area}_{sh}"  # stable key
                new_cov[(area, sh)] = st.number_input(
                    f"{AREA_LABEL[st.session_state.lang][area]} — {SHIFT_LABEL[st.session_state.lang][sh]}",
                    0, 20, int(st.session_state.cov[(area,sh)]), key=key
                )
    st.session_state.cov = new_cov

    st.subheader(L("group_caps"))
    gc = st.columns(6)
    for i, g in enumerate(["senior","g1","g2","g3","g4","g5"]):
        with gc[i]:
            _ = st.number_input(
                f"{g}", min_value=0, max_value=31,
                value=int(st.session_state.get(f"gcap_{g}", GROUP_CAP[g])),
                key=f"gcap_{g}"
            )
    st.caption("Tip: per-doctor caps are set in Doctors tab; group caps here are defaults for new doctors.")

# ---------- Doctors tab ----------
with tab_docs:
    st.subheader(L("add_list"))
    txt = st.text_area(" ", height=120, key="add_list_box", placeholder="Dr. New A\nDr. New B")
    if st.button(L("append"), key="btn_append"):
        new_names = [n.strip() for n in txt.splitlines() if n.strip()]
        added = 0
        for n in new_names:
            if n not in st.session_state.doctors:
                st.session_state.doctors.append(n)
                st.session_state.group_map[n] = "g3"
                default_cap = int(st.session_state.get("gcap_g3", GROUP_CAP["g3"]))
                st.session_state.cap_map[n] = default_cap
                st.session_state.allowed_shifts[n] = set(SHIFTS)
                st.session_state.offdays[n] = set()
                added += 1
        st.success(f"Added {added}")

    st.divider()
    rem_col1, rem_col2 = st.columns([2,1])
    with rem_col2:
        to_remove = st.selectbox(L("remove_doc"), ["—"] + st.session_state.doctors, key="rem_sel")
        if st.button(L("remove"), key="rem_btn") and to_remove != "—":
            st.session_state.doctors.remove(to_remove)
            for d in ["group_map","cap_map","allowed_shifts","offdays"]:
                st.session_state[d].pop(to_remove, None)
            st.success(f"Removed {to_remove}")

    st.divider()
    st.subheader(L("edit_one"))
    if st.session_state.doctors:
        doc = st.selectbox(L("doctor"), st.session_state.doctors, key="edit_doc_sel")
        grp = st.selectbox(L("group"), ["senior","g1","g2","g3","g4","g5"],
                           index=["senior","g1","g2","g3","g4","g5"].index(st.session_state.group_map.get(doc,"g3")),
                           key=f"group_{doc}")
        st.session_state.group_map[doc] = grp
        st.session_state.cap_map[doc] = st.number_input(L("cap"), 0, 31,
                                                       value=int(st.session_state.cap_map.get(doc, int(st.session_state.get(f"gcap_{grp}", GROUP_CAP.get(grp,18))))),
                                                       key=f"cap_{doc}")

        st.caption(L("allowed_shifts"))
        ch0, ch1, ch2 = st.columns(3)
        checks = {}
        for i, sh in enumerate(SHIFTS):
            col = ch0 if i==0 else ch1 if i==1 else ch2
            with col:
                checks[sh] = st.checkbox(SHIFT_LABEL[st.session_state.lang][sh],
                                         value=(sh in st.session_state.allowed_shifts.get(doc,set(SHIFTS))),
                                         key=f"allow_{doc}_{sh}")
        st.session_state.allowed_shifts[doc] = {s for s,v in checks.items() if v} or set(SHIFTS)

        st.caption(L("offdays"))
        off_txt = st.text_input(" ", ",".join(map(str, sorted(st.session_state.offdays.get(doc,set())))),
                                key=f"off_{doc}")
        chosen = set()
        for t in off_txt.replace(" ", "").split(","):
            if t.isdigit():
                d = int(t)
                if 1 <= d <= st.session_state.days:
                    chosen.add(d)
        if len(chosen) > 3:
            chosen = set(sorted(list(chosen))[:3])
        st.session_state.offdays[doc] = chosen

# ---------- Solver ----------
@dataclass
class SolveResult:
    df: pd.DataFrame
    gaps: pd.DataFrame
    remain: pd.DataFrame

def solve() -> SolveResult:
    if not ORTOOLS_AVAILABLE:
        st.error(L("requires_ortools"))
        return SolveResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

    days = st.session_state.days
    doctors = st.session_state.doctors
    model = cp_model.CpModel()
    D, S, A = len(doctors), len(SHIFTS), len(AREAS)

    # decision vars
    x = {(di,t,s,a): model.NewBoolVar(f"x_{di}_{t}_{s}_{a}")
         for di in range(D) for t in range(days) for s in range(S) for a in range(A)}
    # slack for unmet coverage
    slack = {(t,s,a): model.NewIntVar(0, 100, f"slack_{t}_{s}_{a}")
             for t in range(days) for s in range(S) for a in range(A)}

    # coverage
    for t in range(days):
        for s, sh in enumerate(SHIFTS):
            for a, ar in enumerate(AREAS):
                req = int(st.session_state.cov[(ar, sh)])
                model.Add(sum(x[(di,t,s,a)] for di in range(D)) + slack[(t,s,a)] >= req)

    # one shift per day per doctor
    for di in range(D):
        for t in range(days):
            model.Add(sum(x[(di,t,s,a)] for s in range(S) for a in range(A)) <= 1)

    name_to_i = {n:i for i,n in enumerate(doctors)}

    # qualifications / personal constraints
    for name in doctors:
        di = name_to_i[name]
        grp = st.session_state.group_map[name]
        allowed_areas = GROUP_AREAS[grp]
        allowed_shifts = st.session_state.allowed_shifts[name] if st.session_state.allowed_shifts.get(name) else set(SHIFTS)

        for t in range(days):
            # personal off day
            if (t+1) in st.session_state.offdays.get(name,set()):
                model.Add(sum(x[(di,t,s,a)] for s in range(S) for a in range(A)) == 0)
            # forbid disallowed area/shift
            for s, sh in enumerate(SHIFTS):
                for a, ar in enumerate(AREAS):
                    if (ar not in allowed_areas) or (sh not in allowed_shifts):
                        model.Add(x[(di,t,s,a)] == 0)

        # caps & min off
        total = sum(x[(di,t,s,a)] for t in range(days) for s in range(S) for a in range(A))
        model.Add(total <= int(st.session_state.cap_map[name]))
        model.Add(total <= int(days - st.session_state.min_off))

    # rest >=16h (approx by forbidding adjacent patterns)
    MOR, EVE, NGT = 0, 1, 2
    for di in range(D):
        for t in range(1, days):
            model.Add(
                sum(x[(di,t-1,EVE,a)] for a in range(A)) +
                sum(x[(di,t,MOR,a)] for a in range(A))
                <= 1
            )
            model.Add(
                sum(x[(di,t-1,NGT,a)] for a in range(A)) +
                sum(x[(di,t,MOR,a)] for a in range(A))
                <= 1
            )
            model.Add(
                sum(x[(di,t-1,NGT,a)] for a in range(A)) +
                sum(x[(di,t,EVE,a)] for a in range(A))
                <= 1
            )

    # max consecutive duty days ≤ K
    K = int(st.session_state.max_consec)
    y = {(di,t): model.NewBoolVar(f"y_{di}_{t}") for di in range(D) for t in range(days)}
    for di in range(D):
        for t in range(days):
            model.Add(y[(di,t)] == sum(x[(di,t,s,a)] for s in range(S) for a in range(A)))
        for start in range(0, days-(K+1)+1):
            model.Add(sum(y[(di,start+i)] for i in range(K+1)) <= K)

    # objective: minimize slack then balance
    obj = [slack[(t,s,a)]*1000 for t in range(days) for s in range(S) for a in range(A)]
    demand_total = sum(st.session_state.cov[(ar,sh)] for ar in AREAS for sh in SHIFTS) * days
    avg = int(round(demand_total / max(1,len(doctors))))
    for di in range(D):
        tot = sum(x[(di,t,s,a)] for t in range(days) for s in range(S) for a in range(A))
        over = model.NewIntVar(0, 500, f"over_{di}")
        under = model.NewIntVar(0, 500, f"under_{di}")
        model.Add(tot - avg == over - under)
        obj += [over, under]
    model.Minimize(sum(obj))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 90.0
    solver.parameters.num_search_workers = 8
    solver.Solve(model)

    # build result tables
    rows = []
    assign_cnt = {(t,s,a):0 for t in range(days) for s in range(S) for a in range(A)}
    for name, di in name_to_i.items():
        for t in range(days):
            for s in range(S):
                for a in range(A):
                    if solver.Value(x[(di,t,s,a)]) == 1:
                        rows.append({"doctor":name,"day":t+1,"area":AREAS[a],"shift":SHIFTS[s],
                                     "code":code_for(AREAS[a],SHIFTS[s])})
                        assign_cnt[(t,s,a)] += 1
    df = pd.DataFrame(rows)

    gap_rows=[]
    for t in range(days):
        for s, sh in enumerate(SHIFTS):
            for a, ar in enumerate(AREAS):
                req = int(st.session_state.cov[(ar,sh)])
                done = assign_cnt[(t,s,a)]
                if req-done>0:
                    gap_rows.append({"day":t+1,"shift":sh,"area":ar,"abbr":code_for(ar,sh),
                                     "required":req,"assigned":done,"short_by":req-done})
    gaps = pd.DataFrame(gap_rows)

    tot = df.groupby("doctor").size().to_dict()
    rem = [{"doctor":n,"assigned":tot.get(n,0),"cap":int(st.session_state.cap_map[n]),
            "remaining":max(0,int(st.session_state.cap_map[n])-tot.get(n,0))}
           for n in doctors]
    remain = pd.DataFrame(rem).sort_values(["remaining","doctor"], ascending=[False,True])

    return SolveResult(df,gaps,remain)

def sheet_from_df(df: pd.DataFrame, days:int, doctors:List[str]) -> pd.DataFrame:
    """rows=days, cols=doctors, values=code (F1/A2/…), blanks for off."""
    if df.empty:
        return pd.DataFrame(index=range(1, days+1), columns=doctors)
    p = df.pivot_table(index="day", columns="doctor", values="code", aggfunc="first")
    return p.reindex(index=range(1, days+1), columns=doctors)

def day_shift_map(df: pd.DataFrame, days:int) -> Dict[int, Dict[str, List[str]]]:
    """Return {day: {code: [doctors...]}} with codes in SHIFT_COLS_ORDER."""
    m = {d:{c:[] for c in SHIFT_COLS_ORDER} for d in range(1, days+1)}
    if df.empty: return m
    for r in df.itertuples(index=False):
        d = int(r.day)
        code = str(r.code)
        if len(code)>=2 and code in m[d]:
            m[d][code].append(r.doctor)
    # sort names for consistency
    for d in m:
        for c in m[d]:
            m[d][c] = sorted(m[d][c])
    return m

# ---------- Cards CSS ----------
AREA_COLORS = {
    "fast": "#E6F3FF",
    "resp_triage": "#E8FBF0",
    "acute": "#FFF2E6",
    "resus": "#EEE8FF",
    "blank": "#FDE2E2",
}
def inject_cards_css():
    css = f"""
    <style>
      .rota-wrap {{ overflow:auto; max-height: 76vh; border:1px solid #e6e8ef; border-radius:14px; background:#fff; }}
      table.rota {{ border-collapse: separate; border-spacing:0; width: 100%; }}
      table.rota th, table.rota td {{ border:1px solid #e6e8ef; padding:6px 8px; vertical-align:middle; }}
      table.rota thead th {{ position:sticky; top:0; background:#f8f9fe; z-index:2; text-align:center; font-weight:700; }}
      table.rota tbody th.sticky {{ position:sticky; left:0; background:#fff; z-index:1; white-space:nowrap; font-weight:700; color:#3b57ff; }}
      .cell {{ display:flex; justify-content:center; align-items:center; min-height:54px; }}
      .card {{ display:flex; flex-direction:column; gap:2px; align-items:center; justify-content:center;
               min-width:72px; padding:6px 10px; border-radius:10px; font-size:13px; font-weight:700;
               border:1px solid #e6e8ef; box-shadow:0 1px 0 rgba(0,0,0,.05); text-align:center; }}
      .sub {{ font-size:11px; font-weight:500; color:#6b7280; }}
      .blank {{ background:{AREA_COLORS["blank"]}; }}
      .a-fast {{ background:{AREA_COLORS["fast"]}; }}
      .a-resp_triage {{ background:{AREA_COLORS["resp_triage"]}; }}
      .a-acute {{ background:{AREA_COLORS["acute"]}; }}
      .a-resus {{ background:{AREA_COLORS["resus"]}; }}

      /* Mini cards for Day×Shift view (doctor name cards) */
      .mini-wrap {{ display:flex; flex-wrap: wrap; gap:6px; justify-content:flex-start; }}
      .mini {{ background:#fff; border:1px solid #e6e8ef; border-radius:10px; padding:4px 8px; font-size:12px; font-weight:600; }}
      .mini.a-fast {{ background:{AREA_COLORS["fast"]}; }}
      .mini.a-resp_triage {{ background:{AREA_COLORS["resp_triage"]}; }}
      .mini.a-acute {{ background:{AREA_COLORS["acute"]}; }}
      .mini.a-resus {{ background:{AREA_COLORS["resus"]}; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

def weekday_name(lang:str, y:int, m:int, d:int) -> str:
    wd = calendar.weekday(y, m, d)
    return L("weekday")[wd]

# ---------- Renderers ----------
def render_day_doctor_grid(sheet: pd.DataFrame, year:int, month:int, doctors:List[str]):
    inject_cards_css()
    head = ["<th>"+html.escape(L("day"))+"</th>"] + [f"<th>{html.escape(doc)}</th>" for doc in doctors]
    thead = "<thead><tr>" + "".join(head) + "</tr></thead>"

    body_rows = []
    for day in sheet.index:
        dname = weekday_name(st.session_state.lang, int(year), int(month), int(day))
        left = f"<th class='sticky'>{int(day)} / {int(month)}<div class='sub'>{html.escape(dname)}</div></th>"
        cells = []
        for doc in doctors:
            val = sheet.loc[day, doc]
            if pd.isna(val) or str(val).strip()=="":
                cells.append(f"<td><div class='cell'><div class='card blank'></div></div></td>")
            else:
                code = str(val)
                area = LETTER_TO_AREA.get(code[0], None)
                cls = f"a-{area}" if area else "blank"
                sh = DIGIT_TO_SHIFT.get(code[-1], None)
                sub = SHIFT_LABEL[st.session_state.lang][sh] if sh else ""
                cells.append(f"<td><div class='cell'><div class='card {cls}'>{html.escape(code)}<div class='sub'>{html.escape(sub)}</div></div></div></td>")
        body_rows.append("<tr>"+left+"".join(cells)+"</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"
    st.markdown(f"<div class='rota-wrap'><table class='rota'>{thead}{tbody}</table></div>", unsafe_allow_html=True)

def render_doctor_day_grid(sheet: pd.DataFrame, year:int, month:int, doctors:List[str]):
    inject_cards_css()
    days = list(sheet.index)  # 1..N
    head = ["<th>"+html.escape(L("doctor"))+"</th>"] + [
        f"<th>{int(d)}/{int(month)}<div class='sub'>{html.escape(weekday_name(st.session_state.lang,int(year),int(month),int(d)))}</div></th>"
        for d in days
    ]
    thead = "<thead><tr>" + "".join(head) + "</tr></thead>"

    body_rows = []
    for doc in doctors:
        left = f"<th class='sticky'>{html.escape(doc)}</th>"
        cells = []
        for day in days:
            val = sheet.loc[day, doc]
            if pd.isna(val) or str(val).strip()=="":
                cells.append(f"<td><div class='cell'><div class='card blank'></div></div></td>")
            else:
                code = str(val)
                area = LETTER_TO_AREA.get(code[0], None)
                cls = f"a-{area}" if area else "blank"
                sh = DIGIT_TO_SHIFT.get(code[-1], None)
                sub = SHIFT_LABEL[st.session_state.lang][sh] if sh else ""
                cells.append(f"<td><div class='cell'><div class='card {cls}'>{html.escape(code)}<div class='sub'>{html.escape(sub)}</div></div></div></td>")
        body_rows.append("<tr>"+left+"".join(cells)+"</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"
    st.markdown(f"<div class='rota-wrap'><table class='rota'>{thead}{tbody}</table></div>", unsafe_allow_html=True)

def render_day_shift_grid(day_map: Dict[int, Dict[str, List[str]]], year:int, month:int):
    inject_cards_css()
    # Header: Day, then codes in SHIFT_COLS_ORDER
    head = ["<th>"+html.escape(L("day"))+"</th>"]
    for code in SHIFT_COLS_ORDER:
        # show area & shift label as sub
        area = LETTER_TO_AREA.get(code[0], "")
        sh = DIGIT_TO_SHIFT.get(code[-1], "")
        sub = f"{AREA_LABEL[st.session_state.lang][area]} — {SHIFT_LABEL[st.session_state.lang][sh]}"
        head.append(f"<th>{html.escape(code)}<div class='sub'>{html.escape(sub)}</div></th>")
    thead = "<thead><tr>" + "".join(head) + "</tr></thead>"

    body_rows = []
    for day in sorted(day_map.keys()):
        dname = weekday_name(st.session_state.lang, int(year), int(month), int(day))
        left = f"<th class='sticky'>{int(day)} / {int(month)}<div class='sub'>{html.escape(dname)}</div></th>"
        cells = []
        for code in SHIFT_COLS_ORDER:
            docs = day_map[day].get(code, [])
            if not docs:
                cells.append(f"<td><div class='cell'><div class='card blank'></div></div></td>")
            else:
                area = LETTER_TO_AREA.get(code[0], None)
                cls = f"a-{area}" if area else ""
                # stack mini cards (names)
                inner = "".join([f"<div class='mini {cls}'>{html.escape(n)}</div>" for n in docs])
                cells.append(f"<td><div class='mini-wrap'>{inner}</div></td>")
        body_rows.append("<tr>"+left+"".join(cells)+"</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"
    st.subheader(L("by_shift_grid"))
    st.markdown(f"<div class='rota-wrap'><table class='rota'>{thead}{tbody}</table></div>", unsafe_allow_html=True)

# ---------- Generate & Views ----------
with tab_gen:
    if st.button(L("run"), key="run_btn", type="primary", use_container_width=True):
        res = solve()
        st.session_state.result_df = res.df
        st.session_state.gaps = res.gaps
        st.session_state.remain = res.remain
        st.success(L("ok_no_gaps") if res.gaps.empty else L("gaps"))

    if st.session_state.result_df.empty:
        st.info(L("need_generate"))
    else:
        # Build base matrices once
        sheet = sheet_from_df(st.session_state.result_df, st.session_state.days, st.session_state.doctors)
        dmap = day_shift_map(st.session_state.result_df, st.session_state.days)

        vlabels = {
            "day_doctor": L("view_day_doctor"),
            "doctor_day": L("view_doctor_day"),
            "day_shift": L("view_day_shift"),
        }
        # Choose view
        mode = st.radio(L("view_mode"),
                        [vlabels["day_doctor"], vlabels["doctor_day"], vlabels["day_shift"]],
                        index=["day_doctor","doctor_day","day_shift"].index(st.session_state.view_mode)
                               if st.session_state.view_mode in ["day_doctor","doctor_day","day_shift"] else 0,
                        key="view_select", horizontal=True)
        # Keep internal key
        inv = {v:k for k,v in vlabels.items()}
        st.session_state.view_mode = inv.get(mode, "day_doctor")

        st.subheader(L("cards_view"))
        if st.session_state.view_mode == "day_doctor":
            render_day_doctor_grid(sheet, int(st.session_state.year), int(st.session_state.month), st.session_state.doctors)
        elif st.session_state.view_mode == "doctor_day":
            render_doctor_day_grid(sheet, int(st.session_state.year), int(st.session_state.month), st.session_state.doctors)
        else:  # day_shift
            render_day_shift_grid(dmap, int(st.session_state.year), int(st.session_state.month))

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader(L("gaps"))
            st.dataframe(st.session_state.gaps, use_container_width=True, height=320)
        with c2:
            st.subheader(L("remain"))
            st.dataframe(st.session_state.remain, use_container_width=True, height=320)

# ---------- Export (Styled Excel + ByShift) ----------
def export_excel(sheet: pd.DataFrame, gaps: pd.DataFrame, remain: pd.DataFrame,
                 year:int, month:int, dmap: Dict[int, Dict[str, List[str]]]) -> bytes:
    if not XLSX_AVAILABLE: return b""
    out = BytesIO()
    wb = xlsxwriter.Workbook(out, {"in_memory": True})
    hdr = wb.add_format({"bold":True,"align":"center","valign":"vcenter","bg_color":"#E8EEF9","border":1})
    day_hdr = wb.add_format({"bold":True,"align":"center","valign":"vcenter","bg_color":"#EEF5FF","border":1})
    cell = wb.add_format({"align":"center","valign":"vcenter","border":1})
    left_wrap = wb.add_format({"align":"left","valign":"top","border":1,"text_wrap":True})
    blank = wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color":AREA_COLORS["blank"]})

    area_fmt = {
        "fast": wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color":AREA_COLORS["fast"]}),
        "resp_triage": wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color":AREA_COLORS["resp_triage"]}),
        "acute": wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color":AREA_COLORS["acute"]}),
        "resus": wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color":AREA_COLORS["resus"]}),
    }

    # Sheet 1 — Rota (Day×Doctor codes)
    ws = wb.add_worksheet("Rota")
    ws.freeze_panes(1,1)
    ws.set_column(0, 0, 14)
    for c in range(sheet.shape[1]): ws.set_column(c+1, c+1, 18)

    ws.write(0,0, L("day"), hdr)
    for j, doc in enumerate(sheet.columns, start=1):
        ws.write(0,j, doc, hdr)

    for i, day in enumerate(sheet.index, start=1):
        wd = calendar.weekday(year, month, int(day))
        wd_name = L("weekday")[wd]
        ws.write(i,0, f"{int(day)}/{int(month)}\n{wd_name}", day_hdr)
        ws.set_row(i, 32)
        for j, doc in enumerate(sheet.columns, start=1):
            v = sheet.loc[day, doc]
            if pd.isna(v) or str(v).strip()=="":
                ws.write(i,j,"",blank)
            else:
                code = str(v)
                area = LETTER_TO_AREA.get(code[0], None)
                fmt = area_fmt.get(area, cell)
                ws.write(i,j, code, fmt)

    # Sheet 2 — Coverage gaps
    ws2 = wb.add_worksheet("Coverage gaps")
    cols = ["day","shift","area","abbr","required","assigned","short_by"]
    for j,cname in enumerate(cols): ws2.write(0,j,cname,hdr)
    for i,row in enumerate(gaps.itertuples(index=False), start=1):
        for j,cname in enumerate(cols):
            ws2.write(i,j, getattr(row,cname) if hasattr(row,cname) else row[j], cell)

    # Sheet 3 — Remaining capacity
    ws3 = wb.add_worksheet("Remaining capacity")
    cols2 = ["doctor","assigned","cap","remaining"]
    for j,cname in enumerate(cols2): ws3.write(0,j,cname,hdr)
    for i,row in enumerate(remain.itertuples(index=False), start=1):
        for j,cname in enumerate(cols2):
            ws3.write(i,j, getattr(row,cname) if hasattr(row,cname) else row[j], cell)

    # Sheet 4 — ByShift (Day×Shift; cells list doctor names)
    ws4 = wb.add_worksheet("ByShift")
    ws4.freeze_panes(1,1)
    ws4.set_column(0, 0, 14)
    for c in range(len(SHIFT_COLS_ORDER)): ws4.set_column(c+1, c+1, 24)

    ws4.write(0,0, L("day"), hdr)
    for j, code in enumerate(SHIFT_COLS_ORDER, start=1):
        area = LETTER_TO_AREA.get(code[0], "")
        sh = DIGIT_TO_SHIFT.get(code[-1], "")
        ws4.write(0,j, f"{code}", hdr)

    for i, day in enumerate(sorted(dmap.keys()), start=1):
        wd = calendar.weekday(year, month, int(day))
        wd_name = L("weekday")[wd]
        ws4.write(i,0, f"{int(day)}/{int(month)}\n{wd_name}", day_hdr)
        ws4.set_row(i, 36)
        for j, code in enumerate(SHIFT_COLS_ORDER, start=1):
            names = dmap[day].get(code, [])
            if not names:
                ws4.write(i,j,"", blank)
            else:
                area = LETTER_TO_AREA.get(code[0], None)
                fmt = area_fmt.get(area, left_wrap)
                ws4.write(i,j, "\n".join(names), fmt)

    wb.close()
    return out.getvalue()

with tab_export:
    if st.session_state.result_df.empty:
        st.info(L("need_generate"))
    else:
        sheet = sheet_from_df(st.session_state.result_df, st.session_state.days, st.session_state.doctors)
        dmap = day_shift_map(st.session_state.result_df, st.session_state.days)
        data = export_excel(sheet, st.session_state.gaps, st.session_state.remain,
                            int(st.session_state.year), int(st.session_state.month), dmap)
        st.download_button(L("download_xlsx"), data=data,
                           file_name="ED_rota.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="dl_xlsx", use_container_width=True)
