# app.py — ED Rota (Random + Inline Editing in-table) + Cards + Styled Excel
# -------------------------------------------------------------------------
# - Random assignment each run subject to constraints (no ML layer)
# - Inline edit inside the Generate tab using a Doctor×Day editable grid (st.data_editor)
# - Cards views: Day×Doctor, Doctor×Day, Day×Shift (empty = no card)
# - Constraints: coverage, 1 shift/day/doctor, per-group caps, min off, rest≥16h, ≤6 consecutive days, off-days
# - Export: Rota, Doctor×Day, ByShift, Coverage gaps, Remaining (styled)
#
# Tips:
# - Use Inline edit for quick add/remove/edit by clicking cells (codes F1..C3 or empty)
# - "Validate constraints" checks before applying; "Force override" applies regardless

import streamlit as st
import pandas as pd
import numpy as np
import random
from io import BytesIO
from dataclasses import dataclass
from typing import Dict, List, Tuple
import calendar, html

# Optional dependency for Excel styling
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
        "group_caps": "سقوف المجموعات الشهرية (افتراضي للمضافين الجدد)",
        "run_tab": "توليد",
        "run": "توليد عشوائي وفق القيود",
        "view_mode": "طريقة العرض",
        "view_day_doctor": "يوم × طبيب",
        "view_doctor_day": "طبيب × يوم",
        "view_day_shift": "يوم × شفت",
        "cards_view": "عرض الشبكة (بطاقات)",
        "gaps": "النواقص (Coverage gaps)",
        "remain": "السعة المتبقية للأطباء",
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
        "day": "اليوم",
        "need_generate": "شغّل التوليد أولاً.",
        "weekday": ["الاثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"],
        "by_shift_grid": "شبكة يوم × شفت (بطاقات = أسماء الأطباء)",
        "seed": "بذرة العشوائية (اختياري)",
        "no_solution_warn": "تم التوليد العشوائي، قد تبقى نواقص إذا لم تتوافر أهلية كافية.",
        "inline_edit": "التحرير داخل الجدول (Doctor×Day)",
        "inline_hint": "حرّر الخلايا مباشرة؛ اتركها فارغة للراحة أو اختر كودًا (F1..C3).",
        "apply_changes": "تطبيق التغييرات",
        "validate_constraints": "التحقق من القيود قبل التطبيق",
        "force_override": "تجاوز القيود (لا يُنصح)",
        "invalid_edits": "تغييرات مرفوضة (مخالفة للقيود)",
        "applied_ok": "تم تطبيق التغييرات.",
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
        "group_caps": "Group monthly caps (defaults for new doctors)",
        "run_tab": "Generate",
        "run": "Randomize (respect constraints)",
        "view_mode": "View mode",
        "view_day_doctor": "Day × Doctor",
        "view_doctor_day": "Doctor × Day",
        "view_day_shift": "Day × Shift",
        "cards_view": "Cards grid",
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
        "day": "Day",
        "need_generate": "Run the generator first.",
        "weekday": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
        "by_shift_grid": "Day × Shift grid (cards = doctor names)",
        "seed": "Random seed (optional)",
        "no_solution_warn": "Randomized; gaps may remain if eligibility is insufficient.",
        "inline_edit": "Inline edit (Doctor×Day)",
        "inline_hint": "Edit cells directly; leave blank for off, or pick a code (F1..C3).",
        "apply_changes": "Apply changes",
        "validate_constraints": "Validate constraints before applying",
        "force_override": "Force override (not recommended)",
        "invalid_edits": "Rejected edits (constraint violations)",
        "applied_ok": "Changes applied.",
    }
}
def L(k): return I18N[st.session_state.get("lang","en")][k]

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

# ===== Defaults =====
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

# ===== State =====
def _init_session():
    ss = st.session_state
    if "lang" not in ss: ss.lang = "ar"
    if "year" not in ss: ss.year = 2025
    if "month" not in ss: ss.month = 9
    if "days" not in ss: ss.days = 30
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
    if "result_df" not in ss: ss.result_df = pd.DataFrame()
    if "gaps" not in ss: ss.gaps = pd.DataFrame()
    if "remain" not in ss: ss.remain = pd.DataFrame()
    if "view_mode" not in ss: ss.view_mode = "day_doctor"
    if "sheet_cache" not in ss: ss.sheet_cache = pd.DataFrame()
_init_session()

def LBL_AREA(a): return AREA_LABEL[st.session_state.lang][a]
def LBL_SHIFT(s): return SHIFT_LABEL[st.session_state.lang][s]

# ===== Sidebar =====
with st.sidebar:
    st.header(L("general"))
    lang_choice = st.radio(L("language"), [I18N["ar"]["arabic"], I18N["en"]["english"]],
                           index=0 if st.session_state.lang=="ar" else 1, horizontal=True, key="lang_radio")
    st.session_state.lang = "ar" if lang_choice == I18N["ar"]["arabic"] else "en"

    st.number_input(L("year"), 2024, 2100, key="year_input", value=st.session_state.year)
    st.number_input(L("month"), 1, 12, key="month_input", value=st.session_state.month)
    st.slider(L("days"), 28, 31, key="days_slider", value=st.session_state.days)
    seed_val = st.text_input(L("seed"), value="")
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
    [L("rules"), L("doctors_tab"), L("run_tab"), L("export")]
)

# ---------- Rules tab ----------
with tab_rules:
    st.subheader(L("coverage"))
    cols = st.columns(3)
    new_cov = st.session_state.cov.copy()
    for i, area in enumerate(AREAS):
        with cols[i%3]:
            st.markdown(f"**{LBL_AREA(area)}**")
            for sh in SHIFTS:
                key = f"cov_{area}_{sh}"
                new_cov[(area, sh)] = st.number_input(
                    f"{LBL_AREA(area)} — {LBL_SHIFT(sh)}",
                    0, 40, int(st.session_state.cov[(area,sh)]), key=key
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
    st.caption("Per-doctor caps are set below; these are defaults for new doctors.")

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
                checks[sh] = st.checkbox(LBL_SHIFT(sh),
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

# ---------- Helpers ----------
def weekday_name(y:int, m:int, d:int) -> str:
    wd = calendar.weekday(y, m, d)
    return I18N[st.session_state.lang]["weekday"][wd]

def constraints_ok(name:str, day:int, area:str, shift:str,
                   assigned_map:Dict[Tuple[str,int],Tuple[str,str]],
                   counts:Dict[str,int]) -> Tuple[bool,str]:
    if day in st.session_state.offdays.get(name,set()):
        return False, "off-day"
    grp = st.session_state.group_map[name]
    if area not in GROUP_AREAS[grp]:
        return False, "area not allowed"
    if shift not in st.session_state.allowed_shifts.get(name,set(SHIFTS)):
        return False, "shift not allowed"
    if (name, day) in assigned_map:
        return False, "already assigned"
    cap = int(st.session_state.cap_map[name])
    taken = counts.get(name,0)
    if taken >= cap: return False, "cap reached"
    if taken >= (st.session_state.days - st.session_state.min_off):
        return False, "min off-days"
    prev = assigned_map.get((name, day-1))
    if prev:
        _, p_shift = prev
        if (p_shift=="evening" and shift=="morning"): return False, "rest (E→M)"
        if (p_shift=="night" and shift in ["morning","evening"]): return False, "rest (N→M/E)"
    # ≤6 consecutive duty days
    streak = 0
    t = day-1
    while t>=1 and ((name,t) in assigned_map):
        streak += 1; t -= 1
    if streak+1 > int(st.session_state.max_consec):
        return False, "max consecutive days"
    return True, "ok"

def recompute_tables(df: pd.DataFrame):
    days = st.session_state.days
    cnt = {(t,s,a):0 for t in range(days) for s,_ in enumerate(SHIFTS) for a,_ in enumerate(AREAS)}
    for r in df.itertuples(index=False):
        t = int(r.day)-1; s = SHIFTS.index(r.shift); a = AREAS.index(r.area)
        cnt[(t,s,a)] += 1
    gap_rows=[]
    for t in range(days):
        for s, sh in enumerate(SHIFTS):
            for a, ar in enumerate(AREAS):
                req = int(st.session_state.cov[(ar,sh)])
                done = cnt[(t,s,a)]
                if req-done>0:
                    gap_rows.append({"day":t+1,"shift":sh,"area":ar,"abbr":code_for(ar,sh),
                                     "required":req,"assigned":done,"short_by":req-done})
    gaps = pd.DataFrame(gap_rows)
    tot = df.groupby("doctor").size().to_dict()
    rem = [{"doctor":n,"assigned":tot.get(n,0),"cap":int(st.session_state.cap_map[n]),
            "remaining":max(0,int(st.session_state.cap_map[n])-tot.get(n,0))}
           for n in st.session_state.doctors]
    remain = pd.DataFrame(rem).sort_values(["remaining","doctor"], ascending=[False,True])
    st.session_state.gaps = gaps
    st.session_state.remain = remain

def random_generate():
    # seed
    try:
        if st.session_state.get("seed_input_txt",""):
            random.seed(int(st.session_state["seed_input_txt"]))
        else:
            random.seed()
    except:
        random.seed()

    days = st.session_state.days
    docs = st.session_state.doctors
    slots = []
    for day in range(1, days+1):
        for area in AREAS:
            for shift in SHIFTS:
                req = int(st.session_state.cov[(area, shift)])
                for _ in range(req):
                    slots.append((day, area, shift))
    random.shuffle(slots)

    assigned_map: Dict[Tuple[str,int], Tuple[str,str]] = {}
    counts = {n:0 for n in docs}
    for (day, area, shift) in slots:
        candidates = []
        for name in docs:
            ok, _ = constraints_ok(name, day, area, shift, assigned_map, counts)
            if ok:
                candidates.append(name)
        random.shuffle(candidates)
        if candidates:
            pick = candidates[0]
            assigned_map[(pick, day)] = (area, shift)
            counts[pick] += 1
    rows = []
    for (name, day), (area, shift) in assigned_map.items():
        rows.append({"doctor":name,"day":day,"area":area,"shift":shift,"code":code_for(area,shift)})
    df = pd.DataFrame(rows)
    st.session_state.result_df = df
    recompute_tables(df)
    st.warning(L("no_solution_warn"))

def sheet_day_doctor(df: pd.DataFrame, days:int, doctors:List[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(index=range(1, days+1), columns=doctors)
    p = df.pivot_table(index="day", columns="doctor", values="code", aggfunc="first")
    return p.reindex(index=range(1, days+1), columns=doctors)

def grid_doctor_day(df: pd.DataFrame, days:int, doctors:List[str]) -> pd.DataFrame:
    """Editable grid: rows=doctors, cols=days; values are codes or ''."""
    g = pd.DataFrame(index=doctors, columns=[str(d) for d in range(1, days+1)])
    g[:] = ""
    if df.empty: return g
    for r in df.itertuples(index=False):
        g.at[r.doctor, str(int(r.day))] = str(r.code)
    return g

def day_shift_map(df: pd.DataFrame, days:int) -> Dict[int, Dict[str, List[str]]]:
    m = {d:{c:[] for c in SHIFT_COLS_ORDER} for d in range(1, days+1)}
    if df.empty: return m
    for r in df.itertuples(index=False):
        d = int(r.day)
        code = str(r.code)
        if len(code)>=2 and code in m[d]:
            m[d][code].append(r.doctor)
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
      .a-fast {{ background:{AREA_COLORS["fast"]}; }}
      .a-resp_triage {{ background:{AREA_COLORS["resp_triage"]}; }}
      .a-acute {{ background:{AREA_COLORS["acute"]}; }}
      .a-resus {{ background:{AREA_COLORS["resus"]}; }}
      .mini-wrap {{ display:flex; flex-wrap: wrap; gap:6px; justify-content:flex-start; }}
      .mini {{ background:#fff; border:1px solid #e6e8ef; border-radius:10px; padding:4px 8px; font-size:12px; font-weight:600; }}
      .mini.a-fast {{ background:{AREA_COLORS["fast"]}; }}
      .mini.a-resp_triage {{ background:{AREA_COLORS["resp_triage"]}; }}
      .mini.a-acute {{ background:{AREA_COLORS["acute"]}; }}
      .mini.a-resus {{ background:{AREA_COLORS["resus"]}; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# ---------- Renderers (cards; empty = no card) ----------
def render_day_doctor_cards(sheet: pd.DataFrame, year:int, month:int, doctors:List[str]):
    inject_cards_css()
    head = ["<th>"+html.escape(L("day"))+"</th>"] + [f"<th>{html.escape(doc)}</th>" for doc in doctors]
    thead = "<thead><tr>" + "".join(head) + "</tr></thead>"
    body_rows = []
    for day in sheet.index:
        dname = weekday_name(int(year), int(month), int(day))
        left = f"<th class='sticky'>{int(day)} / {int(month)}<div class='sub'>{html.escape(dname)}</div></th>"
        cells = []
        for doc in doctors:
            val = sheet.loc[day, doc]
            if pd.isna(val) or str(val).strip()=="":
                cells.append(f"<td><div class='cell'></div></td>")
            else:
                code = str(val)
                area = LETTER_TO_AREA.get(code[0], None)
                cls = f"a-{area}" if area else ""
                sh = DIGIT_TO_SHIFT.get(code[-1], None)
                sub = LBL_SHIFT(sh) if sh else ""
                cells.append(f"<td><div class='cell'><div class='card {cls}'>{html.escape(code)}<div class='sub'>{html.escape(sub)}</div></div></div></td>")
        body_rows.append("<tr>"+left+"".join(cells)+"</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"
    st.markdown(f"<div class='rota-wrap'><table class='rota'>{thead}{tbody}</table></div>", unsafe_allow_html=True)

def render_doctor_day_cards(sheet: pd.DataFrame, year:int, month:int, doctors:List[str]):
    inject_cards_css()
    days = list(sheet.index)
    head = ["<th>"+html.escape(L("doctor"))+"</th>"] + [
        f"<th>{int(d)}/{int(month)}<div class='sub'>{html.escape(weekday_name(int(year),int(month),int(d)))}</div></th>"
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
                cells.append(f"<td><div class='cell'></div></td>")
            else:
                code = str(val)
                area = LETTER_TO_AREA.get(code[0], None)
                cls = f"a-{area}" if area else ""
                sh = DIGIT_TO_SHIFT.get(code[-1], None)
                sub = LBL_SHIFT(sh) if sh else ""
                cells.append(f"<td><div class='cell'><div class='card {cls}'>{html.escape(code)}<div class='sub'>{html.escape(sub)}</div></div></div></td>")
        body_rows.append("<tr>"+left+"".join(cells)+"</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"
    st.markdown(f"<div class='rota-wrap'><table class='rota'>{thead}{tbody}</table></div>", unsafe_allow_html=True)

def render_day_shift_cards(day_map: Dict[int, Dict[str, List[str]]], year:int, month:int):
    inject_cards_css()
    head = ["<th>"+html.escape(L("day"))+"</th>"]
    for code in SHIFT_COLS_ORDER:
        area = LETTER_TO_AREA.get(code[0], "")
        sh = DIGIT_TO_SHIFT.get(code[-1], "")
        sub = f"{AREA_LABEL[st.session_state.lang][area]} — {SHIFT_LABEL[st.session_state.lang][sh]}"
        head.append(f"<th>{html.escape(code)}<div class='sub'>{html.escape(sub)}</div></th>")
    thead = "<thead><tr>" + "".join(head) + "</tr></thead>"
    body_rows = []
    for day in sorted(day_map.keys()):
        dname = weekday_name(int(year), int(month), int(day))
        left = f"<th class='sticky'>{int(day)} / {int(month)}<div class='sub'>{html.escape(dname)}</div></th>"
        cells = []
        for code in SHIFT_COLS_ORDER:
            docs = day_map[day].get(code, [])
            if not docs:
                cells.append(f"<td><div class='cell'></div></td>")
            else:
                area = LETTER_TO_AREA.get(code[0], None)
                cls = f"a-{area}" if area else ""
                inner = "".join([f"<div class='mini {cls}'>{html.escape(n)}</div>" for n in docs])
                cells.append(f"<td><div class='mini-wrap'>{inner}</div></td>")
        body_rows.append("<tr>"+left+"".join(cells)+"</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"
    st.subheader(L("by_shift_grid"))
    st.markdown(f"<div class='rota-wrap'><table class='rota'>{thead}{tbody}</table></div>", unsafe_allow_html=True)

# ---------- Inline editor helpers ----------
ALL_CODES = [""] + SHIFT_COLS_ORDER  # '' means off/empty

def parse_code(code: str) -> Tuple[str,str]:
    code = (code or "").strip().upper()
    if code == "" or len(code) < 2: return ("","")
    area = LETTER_TO_AREA.get(code[0], "")
    shift = DIGIT_TO_SHIFT.get(code[-1], "")
    if area in AREAS and shift in SHIFTS:
        return area, shift
    return ("","")

def apply_inline_changes(grid_new: pd.DataFrame, validate: bool, force: bool):
    """grid_new: rows=doctors, cols=days (str), values are codes or ''."""
    df_old = st.session_state.result_df.copy()
    # Build a working assignment map and counts from old DF
    assigned_map = {(r.doctor, int(r.day)):(r.area, r.shift) for r in df_old.itertuples(index=False)}
    counts = df_old.groupby("doctor").size().to_dict()

    invalid = []  # list of (doctor, day, code, reason)

    # Iterate all cells; compare old vs new
    for doc in st.session_state.doctors:
        for d_str in grid_new.columns:
            day = int(d_str)
            new_code = str(grid_new.at[doc, d_str]).strip().upper() if doc in grid_new.index else ""
            old_code = ""
            if (doc, day) in assigned_map:
                old_code = code_for(*assigned_map[(doc,day)])
            if new_code == old_code:
                continue  # no change

            # remove existing if present
            if (doc, day) in assigned_map:
                # adjust counts and map
                counts[doc] = max(0, counts.get(doc,0) - 1)
                assigned_map.pop((doc, day), None)
                # also drop from df_old
                df_old = df_old[~((df_old["doctor"]==doc) & (df_old["day"]==day))]

            # if new is blank -> it's a deletion, continue
            if new_code == "" or len(new_code)<2:
                continue

            area, shift = parse_code(new_code)
            if area=="" or shift=="":
                invalid.append((doc, day, new_code, "bad code"))
                continue

            if validate and not force:
                ok, msg = constraints_ok(doc, day, area, shift, assigned_map, counts)
                if not ok:
                    invalid.append((doc, day, new_code, msg))
                    continue

            # apply
            assigned_map[(doc, day)] = (area, shift)
            counts[doc] = counts.get(doc,0) + 1
            df_old = pd.concat([df_old, pd.DataFrame([{
                "doctor":doc,"day":day,"area":area,"shift":shift,"code":code_for(area,shift)
            }])], ignore_index=True)

    st.session_state.result_df = df_old
    recompute_tables(df_old)
    return invalid

# ---------- Generate tab ----------
with tab_gen:
    seed_in = st.text_input(L("seed"), value="", key="seed_input_txt")
    if st.button(L("run"), key="run_btn", type="primary", use_container_width=True):
        random_generate()

    if st.session_state.result_df.empty:
        st.info(L("need_generate"))
    else:
        # Build the standard tables
        sheet = sheet_day_doctor(st.session_state.result_df, st.session_state.days, st.session_state.doctors)
        dmap = day_shift_map(st.session_state.result_df, st.session_state.days)

        # View selector
        vlabels = {"day_doctor": L("view_day_doctor"), "doctor_day": L("view_doctor_day"), "day_shift": L("view_day_shift")}
        mode = st.radio(L("view_mode"),
                        [vlabels["day_doctor"], vlabels["doctor_day"], vlabels["day_shift"]],
                        index=["day_doctor","doctor_day","day_shift"].index(st.session_state.view_mode)
                               if st.session_state.view_mode in ["day_doctor","doctor_day","day_shift"] else 0,
                        key="view_select", horizontal=True)
        inv = {v:k for k,v in vlabels.items()}
        st.session_state.view_mode = inv.get(mode, "day_doctor")

        # Cards display
        st.subheader(L("cards_view"))
        if st.session_state.view_mode == "day_doctor":
            render_day_doctor_cards(sheet, int(st.session_state.year), int(st.session_state.month), st.session_state.doctors)
        elif st.session_state.view_mode == "doctor_day":
            render_doctor_day_cards(sheet, int(st.session_state.year), int(st.session_state.month), st.session_state.doctors)
        else:
            render_day_shift_cards(dmap, int(st.session_state.year), int(st.session_state.month))

        st.divider()

        # Inline editor (Doctor×Day grid)
        st.markdown(f"**{L('inline_edit')}**")
        st.caption(L("inline_hint"))

        # Build editable grid (rows=doctors, cols=days as strings)
        base_grid = grid_doctor_day(st.session_state.result_df, st.session_state.days, st.session_state.doctors)
        # Column config: selectable codes list for each day column
        col_cfg = {}
        for d in range(1, st.session_state.days+1):
            col_cfg[str(d)] = st.column_config.SelectboxColumn(
                label=f"{d}/{st.session_state.month}",
                options=ALL_CODES,
                required=False
            )

        edited = st.data_editor(
            base_grid,
            column_config=col_cfg,
            num_rows="fixed",
            use_container_width=True,
            key="inline_grid",
            height=480
        )

        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            validate = st.checkbox(L("validate_constraints"), value=True, key="inline_validate")
        with c2:
            force = st.checkbox(L("force_override"), value=False, key="inline_force")
        with c3:
            if st.button(L("apply_changes"), use_container_width=True, key="inline_apply"):
                invalid = apply_inline_changes(edited, validate=validate, force=force)
                if invalid:
                    st.error(L("invalid_edits"))
                    st.dataframe(pd.DataFrame(invalid, columns=["doctor","day","code","reason"]),
                                 use_container_width=True, height=220)
                else:
                    st.success(L("applied_ok"))

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader(L("gaps"))
            st.dataframe(st.session_state.gaps, use_container_width=True, height=320)
        with c2:
            st.subheader(L("remain"))
            st.dataframe(st.session_state.remain, use_container_width=True, height=320)

# ---------- Export ----------
def export_excel(sheet: pd.DataFrame, gaps: pd.DataFrame, remain: pd.DataFrame,
                 year:int, month:int, dmap: Dict[int, Dict[str, List[str]]]) -> bytes:
    if not XLSX_AVAILABLE: return b""
    out = BytesIO()
    wb = xlsxwriter.Workbook(out, {"in_memory": True})
    hdr = wb.add_format({"bold":True,"align":"center","valign":"vcenter","bg_color":"#E8EEF9","border":1})
    day_hdr = wb.add_format({"bold":True,"align":"center","valign":"vcenter","bg_color":"#EEF5FF","border":1})
    cell = wb.add_format({"align":"center","valign":"vcenter","border":1})
    left_hdr = wb.add_format({"bold":True,"align":"left","valign":"vcenter","bg_color":"#F8F9FE","border":1})
    left_wrap = wb.add_format({"align":"left","valign":"top","border":1,"text_wrap":True})
    blank = wb.add_format({"align":"center","valign":"vcenter","border":1})

    area_fmt = {
        "fast": wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color":"#E6F3FF"}),
        "resp_triage": wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color":"#E8FBF0"}),
        "acute": wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color":"#FFF2E6"}),
        "resus": wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color":"#EEE8FF"}),
    }

    # Sheet 1 — Rota (Day×Doctor)
    ws = wb.add_worksheet("Rota")
    ws.freeze_panes(1,1)
    ws.set_column(0, 0, 14)
    for c in range(sheet.shape[1]): ws.set_column(c+1, c+1, 18)
    ws.write(0,0, L("day"), hdr)
    for j, doc in enumerate(sheet.columns, start=1): ws.write(0,j, doc, hdr)
    for i, day in enumerate(sheet.index, start=1):
        wd = calendar.weekday(year, month, int(day))
        wd_name = I18N[st.session_state.lang]["weekday"][wd]
        ws.write(i,0, f"{int(day)}/{int(month)}\n{wd_name}", day_hdr)
        ws.set_row(i, 28)
        for j, doc in enumerate(sheet.columns, start=1):
            v = sheet.loc[day, doc]
            if pd.isna(v) or str(v).strip()=="":
                ws.write(i,j,"",blank)
            else:
                code = str(v)
                area = LETTER_TO_AREA.get(code[0], None)
                fmt = area_fmt.get(area, cell)
                ws.write(i,j, code, fmt)

    # Sheet 2 — Doctor×Day
    wsD = wb.add_worksheet("Doctor×Day")
    wsD.freeze_panes(1,1)
    wsD.set_column(0, 0, 24)
    for c in range(len(sheet.index)): wsD.set_column(c+1, c+1, 14)
    wsD.write(0,0, L("doctor"), hdr)
    for j, day in enumerate(sheet.index, start=1):
        wd = calendar.weekday(year, month, int(day))
        wd_name = I18N[st.session_state.lang]["weekday"][wd]
        wsD.write(0,j, f"{int(day)}/{int(month)}\n{wd_name}", hdr)
    for i, doc in enumerate(sheet.columns, start=1):
        wsD.write(i,0, doc, left_hdr)
        wsD.set_row(i, 22)
        for j, day in enumerate(sheet.index, start=1):
            v = sheet.loc[day, doc]
            if pd.isna(v) or str(v).strip()=="":
                wsD.write(i,j,"", blank)
            else:
                code = str(v)
                area = LETTER_TO_AREA.get(code[0], None)
                fmt = area_fmt.get(area, cell)
                wsD.write(i,j, code, fmt)

    # Sheet 3 — Coverage gaps
    ws2 = wb.add_worksheet("Coverage gaps")
    cols = ["day","shift","area","abbr","required","assigned","short_by"]
    for j,cname in enumerate(cols): ws2.write(0,j,cname,hdr)
    for i,row in enumerate(gaps.itertuples(index=False), start=1):
        for j,cname in enumerate(cols):
            ws2.write(i,j, getattr(row,cname) if hasattr(row,cname) else row[j], cell)

    # Sheet 4 — Remaining capacity
    ws3 = wb.add_worksheet("Remaining capacity")
    cols2 = ["doctor","assigned","cap","remaining"]
    for j,cname in enumerate(cols2): ws3.write(0,j,cname,hdr)
    for i,row in enumerate(st.session_state.remain.itertuples(index=False), start=1):
        for j,cname in enumerate(cols2):
            ws3.write(i,j, getattr(row,cname) if hasattr(row,cname) else row[j], cell)

    # Sheet 5 — ByShift
    ws4 = wb.add_worksheet("ByShift")
    ws4.freeze_panes(1,1)
    ws4.set_column(0, 0, 14)
    for c in range(len(SHIFT_COLS_ORDER)): ws4.set_column(c+1, c+1, 24)
    ws4.write(0,0, L("day"), hdr)
    for j, code in enumerate(SHIFT_COLS_ORDER, start=1):
        ws4.write(0,j, f"{code}", hdr)
    dmap = day_shift_map(st.session_state.result_df, st.session_state.days)
    for i, day in enumerate(sorted(dmap.keys()), start=1):
        wd = calendar.weekday(year, month, int(day))
        wd_name = I18N[st.session_state.lang]["weekday"][wd]
        ws4.write(i,0, f"{int(day)}/{int(month)}\n{wd_name}", day_hdr)
        ws4.set_row(i, 34)
        for j, code in enumerate(SHIFT_COLS_ORDER, start=1):
            names = dmap[day].get(code, [])
            area = LETTER_TO_AREA.get(code[0], None)
            fmt = area_fmt.get(area, left_wrap)
            ws4.write(i,j, "\n".join(names), fmt)

    wb.close()
    return out.getvalue()

with tab_export:
    if st.session_state.result_df.empty:
        st.info(L("need_generate"))
    else:
        sheet = sheet_day_doctor(st.session_state.result_df, st.session_state.days, st.session_state.doctors)
        data = export_excel(sheet, st.session_state.gaps, st.session_state.remain,
                            int(st.session_state.year), int(st.session_state.month), {})
        st.download_button(L("download_xlsx"), data=data,
                           file_name="ED_rota.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="dl_xlsx", use_container_width=True)
