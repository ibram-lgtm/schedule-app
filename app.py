# app.py — ED Rota (Random Feasible Generator + Card Editing + Add Empty Slot)
# ----------------------------------------------------------------------------
# - Random assignment each run subject to constraints (no ML/AI layer)
# - Constraints: coverage per area/shift/day, 1 shift/day/doctor, caps, min off, rest≥16h, ≤6 consecutive days, off-days
# - Views: Day×Doctor, Doctor×Day, Day×Shift (cards; empty = no card)
# - Edit tab: set/clear a doctor's assignment per day; add a shift into empty areas
# - Bilingual (AR/EN), styled Excel export (Rota, Doctor×Day, ByShift, Gaps, Remaining)

import streamlit as st
import pandas as pd
import numpy as np
import random
from io import BytesIO
from dataclasses import dataclass
from typing import Dict, List, Tuple
import calendar, html

# ===== Optional deps =====
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
        "edit_tab": "التحرير",
        "set_assign": "تعيين/تعديل شفت لطبيب",
        "select_doctor": "اختر الطبيب",
        "select_day": "اختر اليوم",
        "select_area": "اختر القسم",
        "select_shift": "اختر الوردية",
        "apply": "تطبيق",
        "clear_assign": "إزالة التكليف",
        "force": "تجاوز القيود (لا يُنصح)",
        "add_empty": "إضافة شفت في خانة خالية",
        "pick_code": "اختر الكود",
        "no_solution_warn": "تم التوليد العشوائي، قد تبقى نواقص إذا لم تتوافر أهلية كافية.",
        "need_generate": "شغّل التوليد أولاً.",
        "weekday": ["الاثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"],
        "by_shift_grid": "شبكة يوم × شفت (بطاقات = أسماء الأطباء)",
        "seed": "بذرة العشوائية (اختياري)",
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
        "edit_tab": "Editor",
        "set_assign": "Set/Edit doctor's shift",
        "select_doctor": "Select doctor",
        "select_day": "Select day",
        "select_area": "Select area",
        "select_shift": "Select shift",
        "apply": "Apply",
        "clear_assign": "Clear assignment",
        "force": "Force (bypass constraints)",
        "add_empty": "Add shift into empty slot",
        "pick_code": "Pick code",
        "no_solution_warn": "Randomized; gaps may remain if eligibility is insufficient.",
        "need_generate": "Run the generator first.",
        "weekday": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
        "by_shift_grid": "Day × Shift grid (cards = doctor names)",
        "seed": "Random seed (optional)",
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

# ===== Defaults (حسب المواصفات) =====
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

# ===== State init =====
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
tab_rules, tab_docs, tab_edit, tab_gen, tab_export = st.tabs(
    [L("rules"), L("doctors_tab"), L("edit_tab"), L("run"), L("export")]
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

def constraints_ok(name:str, day:int, area:str, shift:str, assigned_map:Dict[Tuple[str,int],Tuple[str,str]],
                   counts:Dict[str,int]) -> Tuple[bool,str]:
    # off-day
    if day in st.session_state.offdays.get(name,set()):
        return False, "off-day"
    # area eligibility by group
    grp = st.session_state.group_map[name]
    if area not in GROUP_AREAS[grp]:
        return False, "area not allowed for group"
    # shift allowed
    if shift not in st.session_state.allowed_shifts.get(name,set(SHIFTS)):
        return False, "shift not allowed"
    # one per day
    if (name, day) in assigned_map:
        return False, "already assigned this day"
    # cap & min off
    cap = int(st.session_state.cap_map[name])
    taken = counts.get(name,0)
    if taken >= cap: return False, "cap reached"
    if taken >= (st.session_state.days - st.session_state.min_off):
        return False, "min off-days constraint"
    # rest ≥16h (approx): forbid E->M, N->M, N->E
    prev = assigned_map.get((name, day-1))
    if prev:
        p_area, p_shift = prev
        if (p_shift=="evening" and shift=="morning"): return False, "rest (E→M)"
        if (p_shift=="night" and shift in ["morning","evening"]): return False, "rest (N→M/E)"
    # ≤6 consecutive duty days
    # compute streak ending at day-1
    streak = 0
    t = day-1
    while t>=1 and ((name,t) in assigned_map):
        streak += 1; t -= 1
    if streak+1 > int(st.session_state.max_consec):
        return False, "max consecutive days"
    return True, "ok"

def recompute_tables(df: pd.DataFrame):
    days = st.session_state.days
    # gaps
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
    seed_txt = st.session_state.get("seed_input_txt","")
    if seed_txt:
        try: random.seed(int(seed_txt))
        except: random.seed()
    else:
        random.seed()

    days = st.session_state.days
    docs = st.session_state.doctors
    # slots: list of (day, area, shift) repeated "required" times
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
        # build eligible list
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
        # else leave empty (gap)

    # build df
    rows = []
    for (name, day), (area, shift) in assigned_map.items():
        rows.append({"doctor":name,"day":day,"area":area,"shift":shift,"code":code_for(area,shift)})
    df = pd.DataFrame(rows)
    st.session_state.result_df = df
    recompute_tables(df)
    st.warning(L("no_solution_warn"))

def sheet_from_df(df: pd.DataFrame, days:int, doctors:List[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(index=range(1, days+1), columns=doctors)
    p = df.pivot_table(index="day", columns="doctor", values="code", aggfunc="first")
    return p.reindex(index=range(1, days+1), columns=doctors)

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

# ---------- Renderers (empty = no card) ----------
def render_day_doctor_grid(sheet: pd.DataFrame, year:int, month:int, doctors:List[str]):
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

def render_doctor_day_grid(sheet: pd.DataFrame, year:int, month:int, doctors:List[str]):
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

def render_day_shift_grid(day_map: Dict[int, Dict[str, List[str]]], year:int, month:int):
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

# ---------- Edit tab ----------
def assign_set(name:str, day:int, area:str, shift:str, force:bool=False):
    df = st.session_state.result_df.copy()
    # remove existing for (name, day)
    df = df[~((df["doctor"]==name) & (df["day"]==day))]
    if not force:
        # build maps for validation
        assigned_map = {(r.doctor, r.day):(r.area,r.shift) for r in df.itertuples(index=False)}
        counts = df.groupby("doctor").size().to_dict()
        ok, msg = constraints_ok(name, day, area, shift, assigned_map, counts)
        if not ok:
            st.error(f"Cannot assign: {msg}")
            return
    # add new
    df = pd.concat([df, pd.DataFrame([{
        "doctor":name,"day":day,"area":area,"shift":shift,"code":code_for(area,shift)
    }])], ignore_index=True)
    st.session_state.result_df = df
    recompute_tables(df)
    st.success("Applied.")

def assign_clear(name:str, day:int):
    df = st.session_state.result_df.copy()
    before = len(df)
    df = df[~((df["doctor"]==name) & (df["day"]==day))]
    st.session_state.result_df = df
    if len(df)<before:
        recompute_tables(df)
        st.success("Cleared.")
    else:
        st.info("Nothing to clear.")

with tab_edit:
    if st.session_state.result_df.empty:
        st.info(L("need_generate"))
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**{L('set_assign')}**")
            name = st.selectbox(L("select_doctor"), st.session_state.doctors, key="ed_doc")
            day = st.number_input(L("select_day"), 1, st.session_state.days, 1, key="ed_day")
            area = st.selectbox(L("select_area"), AREAS, format_func=LBL_AREA, key="ed_area")
            shift = st.selectbox(L("select_shift"), SHIFTS, format_func=LBL_SHIFT, key="ed_shift")
            force = st.checkbox(L("force"), value=False, key="ed_force")
            bA, bB = st.columns(2)
            if bA.button(L("apply"), use_container_width=True, key="ed_apply"):
                assign_set(name, int(day), str(area), str(shift), force)
            if bB.button(L("clear_assign"), use_container_width=True, key="ed_clear"):
                assign_clear(name, int(day))

        with c2:
            st.markdown(f"**{L('add_empty')}**")
            day2 = st.number_input(L("select_day")+" ▸", 1, st.session_state.days, 1, key="emp_day")
            area2 = st.selectbox(L("select_area")+" ▸", AREAS, format_func=LBL_AREA, key="emp_area")
            shift2 = st.selectbox(L("select_shift")+" ▸", SHIFTS, format_func=LBL_SHIFT, key="emp_shift")
            # show only eligible doctors quickly
            # build current maps
            df = st.session_state.result_df
            assigned_map = {(r.doctor, r.day):(r.area,r.shift) for r in df.itertuples(index=False)}
            counts = df.groupby("doctor").size().to_dict()
            elig = []
            for n in st.session_state.doctors:
                ok, _ = constraints_ok(n, int(day2), str(area2), str(shift2), assigned_map, counts)
                if ok: elig.append(n)
            pick = st.selectbox(L("select_doctor")+" ▸", elig if elig else st.session_state.doctors, key="emp_doc")
            if st.button(L("apply"), use_container_width=True, key="emp_apply"):
                assign_set(str(pick), int(day2), str(area2), str(shift2), force=False)

# ---------- Generate tab ----------
with tab_gen:
    seed_in = st.text_input(L("seed"), value="", key="seed_input_txt")
    if st.button(L("run"), key="run_btn", type="primary", use_container_width=True):
        random_generate()

    if st.session_state.result_df.empty:
        st.info(L("need_generate"))
    else:
        sheet = sheet_from_df(st.session_state.result_df, st.session_state.days, st.session_state.doctors)
        dmap = day_shift_map(st.session_state.result_df, st.session_state.days)

        vlabels = {"day_doctor": L("view_day_doctor"), "doctor_day": L("view_doctor_day"), "day_shift": L("view_day_shift")}
        mode = st.radio(L("view_mode"),
                        [vlabels["day_doctor"], vlabels["doctor_day"], vlabels["day_shift"]],
                        index=["day_doctor","doctor_day","day_shift"].index(st.session_state.view_mode)
                               if st.session_state.view_mode in ["day_doctor","doctor_day","day_shift"] else 0,
                        key="view_select", horizontal=True)
        inv = {v:k for k,v in vlabels.items()}
        st.session_state.view_mode = inv.get(mode, "day_doctor")

        st.subheader(L("cards_view"))
        if st.session_state.view_mode == "day_doctor":
            render_day_doctor_grid(sheet, int(st.session_state.year), int(st.session_state.month), st.session_state.doctors)
        elif st.session_state.view_mode == "doctor_day":
            render_doctor_day_grid(sheet, int(st.session_state.year), int(st.session_state.month), st.session_state.doctors)
        else:
            render_day_shift_grid(dmap, int(st.session_state.year), int(st.session_state.month))

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
    # build day_shift map again from df
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
        sheet = sheet_from_df(st.session_state.result_df, st.session_state.days, st.session_state.doctors)
        data = export_excel(sheet, st.session_state.gaps, st.session_state.remain,
                            int(st.session_state.year), int(st.session_state.month), {})
        st.download_button(L("download_xlsx"), data=data,
                           file_name="ED_rota.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="dl_xlsx", use_container_width=True)
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
        "ai_tab": "الذكاء الاصطناعي (اختياري)",
        "prefs": "تعلّم التفضيلات",
        "upload_rota": "تحميل جدول سابق (CSV: doctor,day,code أو doctor,day,area,shift)",
        "apply_prefs": "تفعيل التفضيلات في الهدف",
        "forecast": "تنبؤ الطلب",
        "upload_arrivals": "تحميل بيانات الوصولات (CSV: datetime,count)",
        "apply_forecast": "تفعيل التنبؤ وضبط التغطية",
        "mult_weekend": "مضاعِف الويكند",
        "mult_evening": "مضاعِف المساء",
        "mult_night": "مضاعِف الليل",
        "nlc": "قيود بلغة طبيعية",
        "nlc_hint": "أدخل قيودًا سطرًا/سطر: no Dr.Rayan on 12 | Dr.Sharif only night | prefer Dr.Bashir in acute | increase acute evening +1 on Fri",
        "apply_nlc": "تطبيق القيود",
        "swaps": "اقتراحات ذكية للتبديل",
        "gen_swaps": "اقتراح حلول للنواقص",
        "apply_swaps": "تطبيق الاقتراحات",
        "suggestions": "الاقتراحات",
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
        "ai_tab": "AI (optional)",
        "prefs": "Preference learning",
        "upload_rota": "Upload prior rota (CSV: doctor,day,code or doctor,day,area,shift)",
        "apply_prefs": "Enable preferences in objective",
        "forecast": "Demand forecasting",
        "upload_arrivals": "Upload arrivals (CSV: datetime,count)",
        "apply_forecast": "Enable forecast & adjust coverage",
        "mult_weekend": "Weekend multiplier",
        "mult_evening": "Evening multiplier",
        "mult_night": "Night multiplier",
        "nlc": "Natural-language constraints",
        "nlc_hint": "One per line: no Dr.Rayan on 12 | Dr.Sharif only night | prefer Dr.Bashir in acute | increase acute evening +1 on Fri",
        "apply_nlc": "Apply constraints",
        "swaps": "Smart swaps suggestions",
        "gen_swaps": "Suggest fixes for gaps",
        "apply_swaps": "Apply suggestions",
        "suggestions": "Suggestions",
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
    # AI state
    if "pref_weights" not in ss: ss.pref_weights = {}        # (doctor, area, shift) -> float
    if "nlc_edits" not in ss: ss.nlc_edits = {"forbid": set(), "only_shift": {}, "prefer": set(), "avoid": set()}
    if "suggestions" not in ss: ss.suggestions = []
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

# ===== Defaults per your spec =====
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
tab_rules, tab_docs, tab_ai, tab_gen, tab_export = st.tabs(
    [L("rules"), L("doctors_tab"), L("ai_tab"), L("generate"), L("export")]
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
                key = f"cov_{area}_{sh}"
                new_cov[(area, sh)] = st.number_input(
                    f"{AREA_LABEL[st.session_state.lang][area]} — {SHIFT_LABEL[st.session_state.lang][sh]}",
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

# ---------- AI tab ----------
with tab_ai:
    st.markdown(f"### {L('prefs')}")
    rota_file = st.file_uploader(L("upload_rota"), type=["csv"], key="u_rota")
    _ = st.checkbox(L("apply_prefs"), key="ai_apply_prefs", value=True)
    if rota_file is not None:
        dfp = pd.read_csv(rota_file)
        # Normalize columns
        if {"doctor","day","code"}.issubset(dfp.columns):
            tmp = dfp.copy()
            tmp["area"] = tmp["code"].astype(str).str[0].map(LETTER_TO_AREA)
            tmp["shift"] = tmp["code"].astype(str).str[-1].map(DIGIT_TO_SHIFT)
            dfp = tmp
        elif {"doctor","day","area","shift"}.issubset(dfp.columns):
            pass
        else:
            st.warning("CSV must contain columns: doctor,day,code OR doctor,day,area,shift")
            dfp = None
        if dfp is not None:
            # simple frequency -> weights
            w = {}
            for r in dfp.itertuples(index=False):
                key = (str(r.doctor), str(r.area), str(r.shift))
                w[key] = w.get(key, 0.0) + 1.0
            # normalize
            if w:
                maxv = max(w.values())
                for k in list(w.keys()):
                    w[k] = w[k] / maxv  # [0..1]
                st.session_state.pref_weights = w
                st.success(f"Loaded {len(w)} preference weights.")
    st.divider()

    st.markdown(f"### {L('forecast')}")
    arr_file = st.file_uploader(L("upload_arrivals"), type=["csv"], key="u_arr")
    _ = st.checkbox(L("apply_forecast"), key="ai_apply_forecast", value=False)
    colW, colE, colN = st.columns(3)
    with colW: st.number_input(L("mult_weekend"), 0.5, 3.0, 1.2, 0.1, key="mult_weekend")
    with colE: st.number_input(L("mult_evening"), 0.5, 3.0, 1.15, 0.05, key="mult_evening")
    with colN: st.number_input(L("mult_night"), 0.5, 3.0, 1.3, 0.05, key="mult_night")
    if arr_file is not None:
        try:
            dfa = pd.read_csv(arr_file, parse_dates=["datetime"])
            st.write("Arrivals sample:", dfa.head())
            st.session_state.arrivals_df = dfa
        except Exception as e:
            st.warning(f"Arrivals CSV parse error: {e}")
    st.divider()

    st.markdown(f"### {L('nlc')}")
    nlc_text = st.text_area(L("nlc_hint"), key="nlc_box", height=120)
    if st.button(L("apply_nlc"), key="btn_nlc"):
        # reset edits
        st.session_state.nlc_edits = {"forbid": set(), "only_shift": {}, "prefer": set(), "avoid": set()}
        for raw in nlc_text.splitlines():
            s = raw.strip()
            if not s: continue
            # no NAME on D
            m = re.match(r"no\s+(.+)\s+on\s+(\d+)$", s, flags=re.I)
            if m:
                name, day = m.group(1).strip(), int(m.group(2))
                st.session_state.nlc_edits["forbid"].add((name, day))
                continue
            # NAME only shift
            m = re.match(r"(.+)\s+only\s+(morning|evening|night)$", s, flags=re.I)
            if m:
                name, sh = m.group(1).strip(), m.group(2).lower()
                st.session_state.nlc_edits["only_shift"][name] = sh
                continue
            # prefer NAME in area
            m = re.match(r"prefer\s+(.+)\s+in\s+(fast|resp_triage|acute|resus)$", s, flags=re.I)
            if m:
                name, area = m.group(1).strip(), m.group(2).lower()
                st.session_state.nlc_edits["prefer"].add((name, area))
                continue
            # avoid NAME shift
            m = re.match(r"avoid\s+(.+)\s+(morning|evening|night)$", s, flags=re.I)
            if m:
                name, sh = m.group(1).strip(), m.group(2).lower()
                st.session_state.nlc_edits["avoid"].add((name, sh))
                continue
            # increase area shift +N on Fri|Sat|Sun|Mon|...
            m = re.match(r"increase\s+(fast|resp_triage|acute|resus)\s+(morning|evening|night)\s+\+(\d+)\s+on\s+(Mon|Tue|Wed|Thu|Fri|Sat|Sun)$", s, flags=re.I)
            if m:
                area, sh, inc, dow = m.groups()
                inc = int(inc)
                dow_map = {"Mon":0,"Tue":1,"Wed":2,"Thu":3,"Fri":4,"Sat":5,"Sun":6}
                if "forecast_overrides" not in st.session_state: st.session_state.forecast_overrides = []
                st.session_state.forecast_overrides.append((area.lower(), sh.lower(), inc, dow_map[dow]))
                continue
        st.success("Applied natural-language constraints.")

    st.divider()
    st.markdown(f"### {L('swaps')}")
    if st.button(L("gen_swaps"), key="btn_swaps"):
        st.session_state.suggestions = []  # will be filled after solve in tab_gen

# ---------- Helper: Forecast adjust ----------
def build_forecast_cov(base_cov: Dict[Tuple[str,str], int]) -> Dict[Tuple[str,str], int]:
    cov = dict(base_cov)
    if not st.session_state.get("ai_apply_forecast", False):
        return cov

    # multipliers
    mult_evening = float(st.session_state.get("mult_evening", 1.15))
    mult_night = float(st.session_state.get("mult_night", 1.3))

    # Apply global shift multipliers
    for (area, sh), val in list(cov.items()):
        if sh == "evening":
            cov[(area, sh)] = max(val, int(np.ceil(val * mult_evening)))
        if sh == "night":
            cov[(area, sh)] = max(val, int(np.ceil(val * mult_night)))

    # Apply weekend multiplier to night/evening if needed
    # (This is a coarse adjustment; per-day adjustments happen via overrides below)
    # Per-day overrides from NLC like "increase acute evening +1 on Fri"
    for ov in st.session_state.get("forecast_overrides", []):
        pass  # handled inside solver per day

    return cov

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

    # Decision vars
    x = {(di,t,s,a): model.NewBoolVar(f"x_{di}_{t}_{s}_{a}")
         for di in range(D) for t in range(days) for s in range(S) for a in range(A)}
    # slack for unmet coverage
    slack = {(t,s,a): model.NewIntVar(0, 100, f"slack_{t}_{s}_{a}")
             for t in range(days) for s in range(S) for a in range(A)}

    # Coverage (with forecast base)
    cov_base = build_forecast_cov(st.session_state.cov)

    # natural-language per-day increases
    perday_boost = {(t,s,a):0 for t in range(days) for s in range(S) for a in range(A)}
    for item in st.session_state.get("forecast_overrides", []):
        area, sh, inc, dow = item
        for t in range(days):
            y, m = int(st.session_state.year), int(st.session_state.month)
            if calendar.weekday(y, m, t+1) == dow:
                a = AREAS.index(area); s = SHIFTS.index(sh)
                perday_boost[(t,s,a)] += inc

    # coverage constraints
    for t in range(days):
        for s, sh in enumerate(SHIFTS):
            for a, ar in enumerate(AREAS):
                req = int(cov_base[(ar, sh)]) + perday_boost[(t,s,a)]
                model.Add(sum(x[(di,t,s,a)] for di in range(D)) + slack[(t,s,a)] >= req)

    # one shift per day per doctor
    for di in range(D):
        for t in range(days):
            model.Add(sum(x[(di,t,s,a)] for s in range(S) for a in range(A)) <= 1)

    name_to_i = {n:i for i,n in enumerate(doctors)}

    # qualifications / personal & NLC constraints
    only_shift = st.session_state.nlc_edits.get("only_shift", {})
    forbid_pairs = st.session_state.nlc_edits.get("forbid", set())
    avoid_pairs = st.session_state.nlc_edits.get("avoid", set())
    prefer_pairs = st.session_state.nlc_edits.get("prefer", set())

    for name in doctors:
        di = name_to_i[name]
        grp = st.session_state.group_map[name]
        allowed_areas = GROUP_AREAS[grp].copy()

        if name in only_shift:
            # restrict allowed_shifts to one shift
            st.session_state.allowed_shifts[name] = {only_shift[name]}

        allowed_shifts = st.session_state.allowed_shifts[name] if st.session_state.allowed_shifts.get(name) else set(SHIFTS)

        for t in range(days):
            # personal off day & NLC no NAME on D
            if (t+1) in st.session_state.offdays.get(name,set()) or (name, t+1) in forbid_pairs:
                model.Add(sum(x[(di,t,s,a)] for s in range(S) for a in range(A)) == 0)
            # forbid disallowed area/shift
            for s, sh in enumerate(SHIFTS):
                for a, ar in enumerate(AREAS):
                    ok = (ar in allowed_areas) and (sh in allowed_shifts)
                    if not ok:
                        model.Add(x[(di,t,s,a)] == 0)

        # caps & min off
        total = sum(x[(di,t,s,a)] for t in range(days) for s in range(S) for a in range(A))
        model.Add(total <= int(st.session_state.cap_map[name]))
        model.Add(total <= int(days - st.session_state.min_off))

    # Rest ≥16h (approx)
    MOR, EVE, NGT = 0, 1, 2
    for di in range(D):
        for t in range(1, days):
            model.Add(sum(x[(di,t-1,EVE,a)] for a in range(A)) + sum(x[(di,t,MOR,a)] for a in range(A)) <= 1)
            model.Add(sum(x[(di,t-1,NGT,a)] for a in range(A)) + sum(x[(di,t,MOR,a)] for a in range(A)) <= 1)
            model.Add(sum(x[(di,t-1,NGT,a)] for a in range(A)) + sum(x[(di,t,EVE,a)] for a in range(A)) <= 1)

    # Max consecutive duty days ≤ K
    K = int(st.session_state.max_consec)
    y = {(di,t): model.NewBoolVar(f"y_{di}_{t}") for di in range(D) for t in range(days)}
    for di in range(D):
        for t in range(days):
            model.Add(y[(di,t)] == sum(x[(di,t,s,a)] for s in range(S) for a in range(A)))
        for start in range(0, days-(K+1)+1):
            model.Add(sum(y[(di,start+i)] for i in range(K+1)) <= K)

    # Objective
    obj_terms = []
    # (1) minimize slack strongly
    for t in range(days):
        for s in range(S):
            for a in range(A):
                obj_terms.append(slack[(t,s,a)] * 1000)
    # (2) balance around average
    demand_total = sum(build_forecast_cov(st.session_state.cov)[(ar,sh)] for ar in AREAS for sh in SHIFTS) * days
    avg = int(round(demand_total / max(1,len(doctors))))
    for di in range(D):
        tot = sum(x[(di,t,s,a)] for t in range(days) for s in range(S) for a in range(A))
        over = model.NewIntVar(0, 500, f"over_{di}")
        under = model.NewIntVar(0, 500, f"under_{di}")
        model.Add(tot - avg == over - under)
        obj_terms += [over, under]
    # (3) preference rewards (negative cost)
    if st.session_state.get("ai_apply_prefs", True) and st.session_state.pref_weights:
        for (name, area, sh), w in st.session_state.pref_weights.items():
            if (name in name_to_i) and (area in AREAS) and (sh in SHIFTS):
                di = name_to_i[name]; a = AREAS.index(area); s = SHIFTS.index(sh)
                # negative coefficient to reward assignment (scale small vs slack)
                obj_terms.append( x[(di,0,s,a)] * 0 )  # anchor var to avoid empty list for sum
                # add term across all days
                for t in range(days):
                    obj_terms.append( x[(di,t,s,a)] * (-5.0 * w) )

    model.Minimize(sum(obj_terms))

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 95.0
    solver.parameters.num_search_workers = 8
    solver.Solve(model)

    # Build result
    rows = []
    assign_cnt = {(t,s,a):0 for t in range(days) for s in range(S) for a in range(A)}
    name_to_i_local = {n:i for i,n in enumerate(doctors)}
    for name, di in name_to_i_local.items():
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
                req = int(cov_base[(ar,sh)]) + perday_boost[(t,s,a)]
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

# ---------- Build views ----------
def sheet_from_df(df: pd.DataFrame, days:int, doctors:List[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(index=range(1, days+1), columns=doctors)
    p = df.pivot_table(index="day", columns="doctor", values="code", aggfunc="first")
    return p.reindex(index=range(1, days+1), columns=doctors)

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
    days = list(sheet.index)
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
    head = ["<th>"+html.escape(L("day"))+"</th>"]
    for code in SHIFT_COLS_ORDER:
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
                inner = "".join([f"<div class='mini {cls}'>{html.escape(n)}</div>" for n in docs])
                cells.append(f"<td><div class='mini-wrap'>{inner}</div></td>")
        body_rows.append("<tr>"+left+"".join(cells)+"</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"
    st.subheader(L("by_shift_grid"))
    st.markdown(f"<div class='rota-wrap'><table class='rota'>{thead}{tbody}</table></div>", unsafe_allow_html=True)

# ---------- Smart swaps ----------
def gen_suggestions(df: pd.DataFrame, gaps: pd.DataFrame) -> List[Dict]:
    """Return list of suggestions: each is {day, area, shift, assign: name} or {swap: (name1,name2,...)}"""
    if df.empty or gaps.empty: return []
    doctors = st.session_state.doctors
    days = st.session_state.days
    # Build quick lookup
    assigned = {(r.doctor, r.day): (r.area, r.shift) for r in df.itertuples(index=False)}

    suggestions = []
    # Remaining capacity
    cap = st.session_state.cap_map
    taken = df.groupby("doctor").size().to_dict()

    def free_on(name, day):
        return (name, day) not in assigned

    def allowed(name, area, shift):
        grp = st.session_state.group_map[name]
        if area not in GROUP_AREAS[grp]: return False
        if shift not in st.session_state.allowed_shifts.get(name,set(SHIFTS)): return False
        return True

    # simple rest check vs previous day
    def rest_ok(name, day, shift):
        MOR, EVE, NGT = "morning","evening","night"
        prev = assigned.get((name, day-1))
        if not prev: return True
        p_area, p_shift = prev
        if (p_shift == "evening" and shift == "morning"): return False
        if (p_shift == "night" and shift in ["morning","evening"]): return False
        return True

    for g in gaps.itertuples(index=False):
        day, area, shift, short = int(g.day), str(g.area), str(g.shift), int(g.short_by)
        for _ in range(short):
            # direct assign
            picked = None
            for name in doctors:
                if (taken.get(name,0) < cap.get(name,0)) and free_on(name, day) and allowed(name, area, shift) and rest_ok(name, day, shift):
                    picked = name
                    break
            if picked:
                suggestions.append({"type":"assign","day":day,"area":area,"shift":shift,"doctor":picked})
                assigned[(picked, day)] = (area, shift)
                taken[picked] = taken.get(picked,0)+1
                continue
            # try swap: find someone assigned that day to other area; replace if they can serve gap
            # and the freed slot can be filled by another available doc
            for name_a in doctors:
                if not free_on(name_a, day):
                    a_area, a_shift = assigned[(name_a, day)]
                    if not allowed(name_a, area, shift) or not rest_ok(name_a, day, shift):
                        continue
                    # find replacement for a_area/a_shift
                    repl = None
                    for name_b in doctors:
                        if name_b == name_a: continue
                        if (taken.get(name_b,0) < cap.get(name_b,0)) and free_on(name_b, day) and allowed(name_b, a_area, a_shift) and rest_ok(name_b, day, a_shift):
                            repl = name_b
                            break
                    if repl:
                        suggestions.append({"type":"swap","day":day,"gap":(area,shift),
                                            "move": {"name":name_a,"to":(area,shift)},
                                            "fill": {"name":repl,"to":(a_area,a_shift)}})
                        assigned[(name_a, day)] = (area, shift)
                        assigned[(repl, day)] = (a_area, a_shift)
                        taken[repl] = taken.get(repl,0)+1
                        break
    return suggestions

def apply_suggestions(df: pd.DataFrame, sugg: List[Dict]) -> pd.DataFrame:
    if df.empty or not sugg: return df
    data = df.copy()
    for s in sugg:
        d = int(s["day"])
        if s["type"]=="assign":
            name, area, shift = s["doctor"], s["area"], s["shift"]
            data = data[~((data["doctor"]==name) & (data["day"]==d))]  # ensure single per day
            data = pd.concat([data, pd.DataFrame([{
                "doctor":name,"day":d,"area":area,"shift":shift,"code":code_for(area,shift)
            }])], ignore_index=True)
        else:  # swap
            name_a = s["move"]["name"]; to_area, to_shift = s["move"]["to"]
            name_b = s["fill"]["name"]; fill_area, fill_shift = s["fill"]["to"]
            data = data[~((data["doctor"].isin([name_a,name_b])) & (data["day"]==d))]
            data = pd.concat([data, pd.DataFrame([
                {"doctor":name_a,"day":d,"area":to_area,"shift":to_shift,"code":code_for(to_area,to_shift)},
                {"doctor":name_b,"day":d,"area":fill_area,"shift":fill_shift,"code":code_for(fill_area,fill_shift)},
            ])], ignore_index=True)
    return data

# ---------- Generate & Views ----------
with tab_gen:
    cA, cB = st.columns([1,1])
    if cA.button(L("run"), key="run_btn", type="primary", use_container_width=True):
        res = solve()
        st.session_state.result_df = res.df
        st.session_state.gaps = res.gaps
        st.session_state.remain = res.remain
        st.session_state.suggestions = []  # reset
        st.success(L("ok_no_gaps") if res.gaps.empty else L("gaps"))

    # Smart swaps (generate & apply)
    if not st.session_state.result_df.empty:
        c1, c2 = st.columns([1,1])
        if c1.button(L("gen_swaps"), key="btn_swaps_gen", use_container_width=True):
            st.session_state.suggestions = gen_suggestions(st.session_state.result_df, st.session_state.gaps)
        if c2.button(L("apply_swaps"), key="btn_swaps_apply", use_container_width=True) and st.session_state.suggestions:
            st.session_state.result_df = apply_suggestions(st.session_state.result_df, st.session_state.suggestions)
            # recompute tables after apply
            sheet_tmp = sheet_from_df(st.session_state.result_df, st.session_state.days, st.session_state.doctors)
            # quick recompute gaps and remain (reuse solve-like logic lightweight)
            # Here we recompute via counts:
            days = st.session_state.days
            cnt = {(t,s,a):0 for t in range(days) for s,_ in enumerate(SHIFTS) for a,_ in enumerate(AREAS)}
            for r in st.session_state.result_df.itertuples(index=False):
                t = int(r.day)-1; s = SHIFTS.index(r.shift); a = AREAS.index(r.area)
                cnt[(t,s,a)] += 1
            cov_base = build_forecast_cov(st.session_state.cov)
            gap_rows=[]
            for t in range(days):
                for s, sh in enumerate(SHIFTS):
                    for a, ar in enumerate(AREAS):
                        req = int(cov_base[(ar,sh)])
                        done = cnt[(t,s,a)]
                        if req-done>0:
                            gap_rows.append({"day":t+1,"shift":sh,"area":ar,"abbr":code_for(ar,sh),
                                             "required":req,"assigned":done,"short_by":req-done})
            st.session_state.gaps = pd.DataFrame(gap_rows)
            tot = st.session_state.result_df.groupby("doctor").size().to_dict()
            rem = [{"doctor":n,"assigned":tot.get(n,0),"cap":int(st.session_state.cap_map[n]),
                    "remaining":max(0,int(st.session_state.cap_map[n])-tot.get(n,0))}
                   for n in st.session_state.doctors]
            st.session_state.remain = pd.DataFrame(rem).sort_values(["remaining","doctor"], ascending=[False,True])
            st.success("Applied suggestions.")

    if st.session_state.result_df.empty:
        st.info(L("need_generate"))
    else:
        sheet = sheet_from_df(st.session_state.result_df, st.session_state.days, st.session_state.doctors)
        dmap = day_shift_map(st.session_state.result_df, st.session_state.days)

        vlabels = {"day_doctor": L("view_day_doctor"), "doctor_day": L("view_doctor_day"), "day_shift": L("view_day_shift")}
        mode = st.radio(L("view_mode"),
                        [vlabels["day_doctor"], vlabels["doctor_day"], vlabels["day_shift"]],
                        index=["day_doctor","doctor_day","day_shift"].index(st.session_state.view_mode)
                               if st.session_state.view_mode in ["day_doctor","doctor_day","day_shift"] else 0,
                        key="view_select", horizontal=True)
        inv = {v:k for k,v in vlabels.items()}
        st.session_state.view_mode = inv.get(mode, "day_doctor")

        st.subheader(L("cards_view"))
        if st.session_state.view_mode == "day_doctor":
            render_day_doctor_grid(sheet, int(st.session_state.year), int(st.session_state.month), st.session_state.doctors)
        elif st.session_state.view_mode == "doctor_day":
            render_doctor_day_grid(sheet, int(st.session_state.year), int(st.session_state.month), st.session_state.doctors)
        else:
            render_day_shift_grid(dmap, int(st.session_state.year), int(st.session_state.month))

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader(L("gaps"))
            st.dataframe(st.session_state.gaps, use_container_width=True, height=320)
        with c2:
            st.subheader(L("remain"))
            st.dataframe(st.session_state.remain, use_container_width=True, height=320)

        if st.session_state.suggestions:
            st.subheader(L("suggestions"))
            st.dataframe(pd.DataFrame(st.session_state.suggestions), use_container_width=True, height=240)

# ---------- Export (Styled Excel + Doctor×Day + ByShift + Suggestions) ----------
def export_excel(sheet: pd.DataFrame, gaps: pd.DataFrame, remain: pd.DataFrame,
                 year:int, month:int, dmap: Dict[int, Dict[str, List[str]]], suggestions: List[Dict]) -> bytes:
    if not XLSX_AVAILABLE: return b""
    out = BytesIO()
    wb = xlsxwriter.Workbook(out, {"in_memory": True})
    hdr = wb.add_format({"bold":True,"align":"center","valign":"vcenter","bg_color":"#E8EEF9","border":1})
    day_hdr = wb.add_format({"bold":True,"align":"center","valign":"vcenter","bg_color":"#EEF5FF","border":1})
    cell = wb.add_format({"align":"center","valign":"vcenter","border":1})
    left_hdr = wb.add_format({"bold":True,"align":"left","valign":"vcenter","bg_color":"#F8F9FE","border":1})
    left_cell = wb.add_format({"align":"left","valign":"vcenter","border":1})
    left_wrap = wb.add_format({"align":"left","valign":"top","border":1,"text_wrap":True})
    blank = wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color":AREA_COLORS["blank"]})

    area_fmt = {
        "fast": wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color":AREA_COLORS["fast"]}),
        "resp_triage": wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color":AREA_COLORS["resp_triage"]}),
        "acute": wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color":AREA_COLORS["acute"]}),
        "resus": wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color":AREA_COLORS["resus"]}),
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

    # Sheet 2 — Doctor×Day
    wsD = wb.add_worksheet("Doctor×Day")
    wsD.freeze_panes(1,1)
    wsD.set_column(0, 0, 24)
    for c in range(len(sheet.index)): wsD.set_column(c+1, c+1, 14)
    wsD.write(0,0, L("doctor"), hdr)
    for j, day in enumerate(sheet.index, start=1):
        wd = calendar.weekday(year, month, int(day))
        wd_name = L("weekday")[wd]
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
    for i,row in enumerate(remain.itertuples(index=False), start=1):
        for j,cname in enumerate(cols2):
            ws3.write(i,j, getattr(row,cname) if hasattr(row,cname) else row[j], cell)

    # Sheet 5 — ByShift (Day×Shift; names per code)
    ws4 = wb.add_worksheet("ByShift")
    ws4.freeze_panes(1,1)
    ws4.set_column(0, 0, 14)
    for c in range(len(SHIFT_COLS_ORDER)): ws4.set_column(c+1, c+1, 24)
    ws4.write(0,0, L("day"), hdr)
    for j, code in enumerate(SHIFT_COLS_ORDER, start=1): ws4.write(0,j, f"{code}", hdr)
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

    # Sheet 6 — Suggestions (if any)
    ws5 = wb.add_worksheet("Suggestions")
    cols3 = ["type","day","area","shift","doctor","move_name","move_to","fill_name","fill_to"]
    for j,cname in enumerate(cols3): ws5.write(0,j,cname,hdr)
    if suggestions:
        r = 1
        for s in suggestions:
            if s["type"]=="assign":
                ws5.write_row(r,0,[s["type"], s["day"], s["area"], s["shift"], s["doctor"], "", "", "", ""], cell)
                r += 1
            else:
                ws5.write_row(r,0,[s["type"], s["day"], s["gap"][0], s["gap"][1], "",
                                   s["move"]["name"], f"{s['move']['to'][0]}-{s['move']['to'][1]}",
                                   s["fill"]["name"], f"{s['fill']['to'][0]}-{s['fill']['to'][1]}"], cell)
                r += 1

    wb.close()
    return out.getvalue()

# ---------- Export Tab ----------
with tab_export:
    if st.session_state.result_df.empty:
        st.info(L("need_generate"))
    else:
        sheet = sheet_from_df(st.session_state.result_df, st.session_state.days, st.session_state.doctors)
        dmap = day_shift_map(st.session_state.result_df, st.session_state.days)
        data = export_excel(sheet, st.session_state.gaps, st.session_state.remain,
                            int(st.session_state.year), int(st.session_state.month),
                            dmap, st.session_state.suggestions)
        st.download_button(L("download_xlsx"), data=data,
                           file_name="ED_rota.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="dl_xlsx", use_container_width=True)
