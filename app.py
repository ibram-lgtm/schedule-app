# app.py — ED Rota Pro (Color Chips + Tooltip + Excel/PDF match + Calendar Offdays + Fix slider)
# ----------------------------------------------------------------------------------------------
# الجديد في هذا الإصدار:
# - مربعات لونية (chips) بدل النص داخل خلايا الجدول، بألوان المناطق، وحجم صغير + تلميح بالكود (F1..C3).
# - Excel/PDF يطابق العرض: تلوين بدون نص، مع وضع الكود كـ comment في Excel.
# - إصلاح SyntaxError في st.slider (إغلاق القوس).
# - يحتفظ بكل ما سبق: القوالب اللونية، الموازن، القيود المتقدمة، التقويم لاختيار الإجازات، التحرير داخل الجدول.

import streamlit as st
import pandas as pd
import random
from io import BytesIO
from typing import Dict, List, Tuple
import calendar, html
from datetime import date

# Optional deps
try:
    import xlsxwriter
    XLSX_AVAILABLE = True
except Exception:
    XLSX_AVAILABLE = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

st.set_page_config(page_title="ED Rota Pro", layout="wide")

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
        "colors": "الألوان",
        "area_colors": "ألوان المناطق",
        "templates": "قالب ألوان",
        "calm": "هادئة",
        "contrast": "عالية التباين",
        "apply_template": "تطبيق القالب",
        "yellow": "أصفر",
        "green": "أخضر",
        "blue": "أزرق",
        "red": "أحمر",
        "reset_colors": "استعادة الألوان الافتراضية",
        "run_tab": "توليد",
        "run": "توليد عشوائي وفق القيود",
        "balance": "موازنة العبء وملء النواقص",
        "balanced_ok": "تمت موازنة النواقص قدر الإمكان.",
        "view_mode": "طريقة العرض",
        "view_day_doctor": "يوم × طبيب",
        "view_doctor_day": "طبيب × يوم",
        "view_day_shift": "يوم × شفت",
        "cards_view": "عرض الشبكة (بطاقات)",
        "gaps": "النواقص",
        "remain": "السعة المتبقية",
        "export": "تصدير",
        "download_xlsx": "تنزيل Excel (منسّق)",
        "download_pdf": "تنزيل PDF (مطبوع)",
        "pdf_na": "تعذّر إنشاء PDF لعدم توفر مكتبة ReportLab على الخادم.",
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
        "offdays": "أيام الإجازة (حتى 3 أيام)",
        "rules_global": "قواعد عامة",
        "min_off": "أقل عدد أيام إجازة/شهر",
        "max_consec": "أقصى أيام عمل متتالية",
        "min_rest": "أقل ساعات راحة بين الشفتات",
        "adv_rules": "قيود متقدمة",
        "max_night": "أقصى شفتات ليلية/شهر (للطبيب)",
        "max_week": "أقصى شفتات/أسبوع (للطبيب)",
        "holidays": "تواريخ العطل (أيام الشهر، مفصولة بفواصل)",
        "avoid_holidays": "يفضّل عدم العمل في العطل",
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
        "daily_table": "جدول المناطق اليومي (قابل للسحب)",
        "assigned": "مسند",
        "required": "المطلوب",
        "ok": "مكتمل",
        "short": "نقص",
        "off_calendar": "اختر أيام الإجازة لهذا الطبيب (حد أقصى 3)",
        "clear_off": "مسح الإجازات",
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
        "colors": "Colors",
        "area_colors": "Area colors",
        "templates": "Color template",
        "calm": "Calm",
        "contrast": "High Contrast",
        "apply_template": "Apply template",
        "yellow": "Yellow",
        "green": "Green",
        "blue": "Blue",
        "red": "Red",
        "reset_colors": "Reset to defaults",
        "run_tab": "Generate",
        "run": "Randomize (respect constraints)",
        "balance": "Balance workload & fill gaps",
        "balanced_ok": "Balancing complete where possible.",
        "view_mode": "View mode",
        "view_day_doctor": "Day × Doctor",
        "view_doctor_day": "Doctor × Day",
        "view_day_shift": "Day × Shift",
        "cards_view": "Cards grid",
        "gaps": "Coverage gaps",
        "remain": "Remaining capacity",
        "export": "Export",
        "download_xlsx": "Download Excel (styled)",
        "download_pdf": "Download PDF (print)",
        "pdf_na": "ReportLab not available on server; PDF export disabled.",
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
        "offdays": "Off-days (up to 3)",
        "rules_global": "Global rules",
        "min_off": "Min off-days / month",
        "max_consec": "Max consecutive duty days",
        "min_rest": "Min rest hours between shifts",
        "adv_rules": "Advanced constraints",
        "max_night": "Max night shifts / month (per doctor)",
        "max_week": "Max shifts / week (per doctor)",
        "holidays": "Holiday dates (month days, comma-separated)",
        "avoid_holidays": "Prefer off on holidays",
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
        "daily_table": "Daily area table (scrollable)",
        "assigned": "Assigned",
        "required": "Required",
        "ok": "OK",
        "short": "Short",
        "off_calendar": "Pick off-days for this doctor (max 3)",
        "clear_off": "Clear off-days",
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

# ===== Colors & Templates =====
PALETTE = {"yellow":"#FFF7C2","green":"#E7F7E9","blue":"#E6F3FF","red":"#FDEAEA"}
DEFAULT_AREA_COLOR_NAMES = {"fast":"yellow","resp_triage":"green","acute":"blue","resus":"red"}
TEMPLATES = {"calm": {"fast":"yellow","resp_triage":"green","acute":"blue","resus":"red"},
             "contrast": {"fast":"red","resp_triage":"blue","acute":"yellow","resus":"green"}}

# ===== State =====
def _init_session():
    ss = st.session_state
    if "lang" not in ss: ss.lang = "ar"
    if "year" not in ss: ss.year = 2025
    if "month" not in ss: ss.month = 9
    if "days" not in ss: ss.days = 30
    if "cov" not in ss: ss.cov = {
        ("fast","morning"):2, ("fast","evening"):2, ("fast","night"):2,
        ("resp_triage","morning"):1, ("resp_triage","evening"):1, ("resp_triage","night"):1,
        ("acute","morning"):3, ("acute","evening"):4, ("acute","night"):3,
        ("resus","morning"):3, ("resus","evening"):3, ("resus","night"):3,
    }
    if "group_map" not in ss:
        ss.group_map = {
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
    if "doctors" not in ss: ss.doctors = list(ss.group_map.keys())
    if "cap_map" not in ss:
        GROUP_CAP = {"senior":16,"g1":18,"g2":18,"g3":18,"g4":18,"g5":18}
        ss.cap_map = {n: GROUP_CAP[ss.group_map[n]] for n in ss.doctors}
    if "allowed_shifts" not in ss:
        FIXED_SHIFT = {"Dr.Sharif":{"night"}, "Dr.Rashif":{"morning"}, "Dr.Jobi":{"evening"},
                       "Dr.Bashir":{"morning"}, "Dr.nashwa":{"morning"}, "Dr.Lena":{"morning"}}
        base = {n:set(SHIFTS) for n in ss.doctors}
        for n, only in FIXED_SHIFT.items():
            if n in base: base[n] = set(only)
        ss.allowed_shifts = base
    if "offdays" not in ss: ss.offdays = {n:set() for n in ss.doctors}
    if "min_off" not in ss: ss.min_off = 12
    if "max_consec" not in ss: ss.max_consec = 6
    if "min_rest" not in ss: ss.min_rest = 16
    if "max_night_map" not in ss: ss.max_night_map = {n: 6 for n in ss.doctors}
    if "max_week_map" not in ss: ss.max_week_map = {n: 5 for n in ss.doctors}
    if "avoid_holidays_map" not in ss: ss.avoid_holidays_map = {n: False for n in ss.doctors}
    if "holidays" not in ss: ss.holidays = set()
    if "result_df" not in ss: ss.result_df = pd.DataFrame()
    if "gaps" not in ss: ss.gaps = pd.DataFrame()
    if "remain" not in ss: ss.remain = pd.DataFrame()
    if "view_mode" not in ss: ss.view_mode = "day_doctor"
    if "area_color_names" not in ss:
        ss.area_color_names = DEFAULT_AREA_COLOR_NAMES.copy()
    if "area_colors" not in ss:
        ss.area_colors = {a: PALETTE[ss.area_color_names[a]] for a in AREAS}
_init_session()

def LBL_AREA(a): return AREA_LABEL[st.session_state.lang][a]
def LBL_SHIFT(s): return SHIFT_LABEL[st.session_state.lang][s]
def area_color(area: str) -> str: return st.session_state.area_colors.get(area, "#ffffff")

# ===== Utilities =====
def weekday_name(y:int, m:int, d:int) -> str:
    wd = calendar.weekday(y, m, d)
    return I18N[st.session_state.lang]["weekday"][wd]

def is_weekend(y:int, m:int, d:int) -> bool:
    wd = calendar.weekday(y, m, d)  # Mon=0
    return wd in (4,5)  # Fri, Sat

def iso_week(y:int, m:int, d:int) -> int:
    return date(y,m,d).isocalendar()[1]

def rest_ok(prev_shift: str, cur_shift: str, min_rest: int) -> bool:
    start_cur = {"morning":7,"evening":15,"night":23}[cur_shift]
    end_prev  = {"morning":15,"evening":23,"night":7}[prev_shift]
    rest = start_cur - end_prev
    if rest < 0: rest += 24
    return rest >= int(min_rest)

def constraints_ok(name:str, day:int, area:str, shift:str,
                   assigned_map:Dict[Tuple[str,int],Tuple[str,str]],
                   counts:Dict[str,int]) -> Tuple[bool,str]:
    ss = st.session_state
    if day in ss.offdays.get(name,set()): return False, "off-day"
    if ss.avoid_holidays_map.get(name, False) and (day in ss.holidays): return False, "holiday preference"

    GROUP_AREAS = {
        "senior":{"resus"},
        "g1":{"resp_triage"},
        "g2":{"acute"},
        "g3":{"fast","acute"},
        "g4":{"resp_triage","fast","acute"},
        "g5":{"acute","resus"},
    }
    grp = ss.group_map[name]
    if area not in GROUP_AREAS[grp]: return False, "area not allowed"
    if shift not in ss.allowed_shifts.get(name,set(SHIFTS)): return False, "shift not allowed"
    if (name, day) in assigned_map: return False, "already assigned"

    cap = int(ss.cap_map[name]); taken = counts.get(name,0)
    if taken >= cap: return False, "cap reached"
    if taken >= (ss.days - ss.min_off): return False, "min off-days"

    if shift == "night":
        night_taken = 0
        for (n,d),(_,sh) in assigned_map.items():
            if n==name and sh=="night": night_taken += 1
        if night_taken >= int(ss.max_night_map.get(name, 999)):
            return False, "max night reached"

    week = iso_week(int(ss.year), int(ss.month), int(day))
    w_count = 0
    for (n,d),(_,sh) in assigned_map.items():
        if n==name and iso_week(int(ss.year), int(ss.month), int(d)) == week:
            w_count += 1
    if w_count >= int(ss.max_week_map.get(name, 999)): return False, "weekly limit"

    if ss.min_rest > 0:
        prev = assigned_map.get((name, day-1))
        if prev:
            _, p_shift = prev
            if not rest_ok(p_shift, shift, ss.min_rest):
                return False, "rest (prev→today)"
        nxt = assigned_map.get((name, day+1))
        if nxt:
            _, n_shift = nxt
            end_cur  = {"morning":15,"evening":23,"night":7}[shift]
            start_nx = {"morning":7,"evening":15,"night":23}[n_shift]
            rest2 = start_nx - end_cur
            if rest2 < 0: rest2 += 24
            if rest2 < int(ss.min_rest): return False, "rest (today→next)"

    streak = 0; t = day-1
    while t>=1 and ((name,t) in assigned_map):
        streak += 1; t -= 1
    if streak+1 > int(ss.max_consec): return False, "max consecutive days"
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
                slots += [(day, area, shift)]*req
    random.shuffle(slots)

    assigned_map: Dict[Tuple[str,int], Tuple[str,str]] = {}
    counts = {n:0 for n in docs}

    for (day, area, shift) in slots:
        candidates = []
        for name in docs:
            ok, _ = constraints_ok(name, day, area, shift, assigned_map, counts)
            if ok:
                candidates.append(name)
        if candidates:
            def score(nm):
                assigned = counts.get(nm,0)
                wk_cnt = 0
                for (n,d),(a,s) in assigned_map.items():
                    if n==nm and is_weekend(int(st.session_state.year), int(st.session_state.month), int(d)):
                        wk_cnt += 1
                remaining = int(st.session_state.cap_map[nm]) - assigned
                return (assigned, wk_cnt, -remaining)
            candidates.sort(key=score)
            pick = candidates[0]
            assigned_map[(pick, day)] = (area, shift)
            counts[pick] += 1

    rows = [{"doctor":n,"day":d,"area":a,"shift":s,"code":code_for(a,s)}
            for (n,d),(a,s) in assigned_map.items()]
    df = pd.DataFrame(rows)
    st.session_state.result_df = df
    recompute_tables(df)
    st.warning(L("no_solution_warn"))

def balance_workload():
    if st.session_state.result_df.empty or st.session_state.gaps.empty:
        return
    df = st.session_state.result_df.copy()
    assigned_map = {(r.doctor, int(r.day)):(r.area, r.shift) for r in df.itertuples(index=False)}
    counts = df.groupby("doctor").size().to_dict()
    gaps_sorted = st.session_state.gaps.sort_values(["short_by","day"], ascending=[False, True])
    for row in gaps_sorted.itertuples(index=False):
        need = int(row.short_by); day = int(row.day); area = row.area; shift = row.shift
        for _ in range(need):
            cands = []
            for nm in st.session_state.doctors:
                ok, _msg = constraints_ok(nm, day, area, shift, assigned_map, counts)
                if ok:
                    rem = int(st.session_state.cap_map[nm]) - counts.get(nm,0)
                    wk = 0
                    night_cnt = 0
                    for (n,d),(a,s) in assigned_map.items():
                        if n==nm and is_weekend(int(st.session_state.year), int(st.session_state.month), int(d)):
                            wk += 1
                        if n==nm and s=="night":
                            night_cnt += 1
                    cands.append((nm, rem, wk, night_cnt))
            if not cands: break
            cands.sort(key=lambda x: (-x[1], x[2], x[3], x[0]))
            pick = cands[0][0]
            assigned_map[(pick, day)] = (area, shift)
            counts[pick] = counts.get(pick,0) + 1
            df = pd.concat([df, pd.DataFrame([{
                "doctor":pick,"day":day,"area":area,"shift":shift,"code":code_for(area,shift)
            }])], ignore_index=True)
    st.session_state.result_df = df
    recompute_tables(df)

# ===== Views helpers =====
def sheet_day_doctor(df: pd.DataFrame, days:int, doctors:List[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(index=range(1, days+1), columns=doctors)
    p = df.pivot_table(index="day", columns="doctor", values="code", aggfunc="first")
    return p.reindex(index=range(1, days+1), columns=doctors)

def grid_doctor_day(df: pd.DataFrame, days:int, doctors:List[str]) -> pd.DataFrame:
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
        d = int(r.day); code = str(r.code)
        if code in m[d]:
            m[d][code].append(r.doctor)
    for d in m:
        for c in m[d]: m[d][c] = sorted(m[d][c])
    return m

def daily_counts(df: pd.DataFrame, days:int) -> Dict[int, Dict[str, Tuple[int,int,int]]]:
    res = {d:{c:(0,0,0) for c in SHIFT_COLS_ORDER} for d in range(1, days+1)}
    ct = df.groupby(["day","code"]).size().to_dict() if not df.empty else {}
    req_map = {code_for(a,s): int(st.session_state.cov[(a,s)]) for a in AREAS for s in SHIFTS}
    for d in range(1, days+1):
        for c in SHIFT_COLS_ORDER:
            a = ct.get((d,c), 0); r = req_map[c]
            short = max(0, r - a)
            res[d][c] = (a, r, short)
    return res

def area_totals_from_daily_counts(dc: Dict[int, Dict[str, Tuple[int,int,int]]]) -> Dict[int, Dict[str, Tuple[int,int,int]]]:
    area_codes = {"fast": ["F1","F2","F3"], "resp_triage": ["R1","R2","R3"], "acute": ["A1","A2","A3"], "resus": ["C1","C2","C3"]}
    out = {d:{a:(0,0,0) for a in AREAS} for d in dc.keys()}
    for d in dc.keys():
        for area, codes in area_codes.items():
            A = R = 0
            for c in codes:
                a, r, _ = dc[d][c]
                A += a; R += r
            short = max(0, R - A)
            out[d][area] = (A, R, short)
    return out

# ---------- THEME-AWARE CSS + CHIP ----------
def inject_css():
    css = """
    <style>
      :root {
        --text: #111827;
        --bg: #ffffff;
        --card-bg: #ffffff;
        --thead-bg: #f8f9fe;
        --border: #e6e8ef;
        --badge-text: #111111;
      }
      @media (prefers-color-scheme: dark) {
        :root {
          --text: #e5e7eb;
          --bg: #0f172a;
          --card-bg: #111827;
          --thead-bg: #1f2937;
          --border: #374151;
          --badge-text: #111111;
        }
      }
      .wrap { overflow:auto; max-height: 74vh; border:1px solid var(--border); border-radius:14px; background:var(--card-bg); }
      table.tbl { border-collapse: separate; border-spacing:0; width: 100%; min-width: 900px; color: var(--text); }
      table.tbl th, table.tbl td { border:1px solid var(--border); padding:6px 8px; vertical-align:middle; }
      table.tbl thead th { position:sticky; top:0; background:var(--thead-bg); z-index:2; text-align:center; font-weight:700; }
      table.tbl tbody th.sticky { position:sticky; left:0; background:var(--card-bg); z-index:1; white-space:nowrap; font-weight:700; }
      .cell { display:flex; align-items:center; justify-content:center; min-height:40px; }
      .chip { display:inline-block; width:18px; height:18px; border-radius:6px; border:1px solid var(--border); }
      .chip-lg { width:20px; height:20px; border-radius:6px; border:1px solid var(--border); }
      .badge { display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; font-weight:700; border:1px solid var(--border); color: var(--badge-text); }
      .ok    { background:#E7F7E9; color:#14532d; }
      .short { background:#FDEAEA; color:#7f1d1d; }
      .sub { font-size:11px; font-weight:500; opacity:.85; }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# ---------- Renderers (chips instead of text) ----------
def chip_html(area:str, code:str, large=False):
    size_cls = "chip-lg" if large else "chip"
    color = area_color(area)
    return f"<span class='{size_cls}' style='background:{color}' title='{html.escape(code)}'></span>"

def render_day_doctor_cards(sheet: pd.DataFrame, year:int, month:int, doctors:List[str]):
    inject_css()
    head = ["<th>"+html.escape(L("day"))+"</th>"] + [f"<th>{html.escape(doc)}</th>" for doc in doctors]
    thead = "<thead><tr>" + "".join(head) + "</tr></thead>"
    body_rows = []
    for day in sheet.index:
        dname = weekday_name(int(year), int(month), int(day))
        left = f"<th class='sticky'>{int(day)} / {int(month)}<div class='sub'>{html.escape(dname)}</div></th>"
        cells = []
        for doc in doctors:
            val = sheet.loc[day, doc] if doc in sheet.columns else ""
            if pd.isna(val) or str(val).strip()=="":
                cells.append(f"<td><div class='cell'></div></td>")
            else:
                code = str(val)
                area = LETTER_TO_AREA.get(code[0], None)
                cells.append(f"<td><div class='cell'>{chip_html(area, code, large=False)}</div></td>")
        body_rows.append("<tr>"+left+"".join(cells)+"</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"
    st.markdown(f"<div class='wrap'><table class='tbl'>{thead}{tbody}</table></div>", unsafe_allow_html=True)

def render_doctor_day_cards(sheet: pd.DataFrame, year:int, month:int, doctors:List[str]):
    inject_css()
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
            val = sheet.loc[day, doc] if doc in sheet.columns else ""
            if pd.isna(val) or str(val).strip()=="":
                cells.append(f"<td><div class='cell'></div></td>")
            else:
                code = str(val); area = LETTER_TO_AREA.get(code[0], None)
                cells.append(f"<td><div class='cell'>{chip_html(area, code, large=False)}</div></td>")
        body_rows.append("<tr>"+left+"".join(cells)+"</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"
    st.markdown(f"<div class='wrap'><table class='tbl'>{thead}{tbody}</table></div>", unsafe_allow_html=True)

def render_day_shift_cards(day_map: Dict[int, Dict[str, List[str]]], year:int, month:int):
    inject_css()
    head = ["<th>"+html.escape(L("day"))+"</th>"]
    for code in SHIFT_COLS_ORDER:
        head.append(f"<th>{html.escape(code)}</th>")
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
                # اسم الطبيب يبقى كنص صغير مع chip قبل الاسم
                inner = "".join([f"<span style='display:inline-flex;align-items:center;gap:6px;margin:2px'>{chip_html(area, code, large=False)}<span style='font-size:12px'>{html.escape(n)}</span></span>" for n in docs])
                cells.append(f"<td><div class='cell' style='flex-wrap:wrap; gap:6px; justify-content:flex-start'>{inner}</div></td>")
        body_rows.append("<tr>"+left+"".join(cells)+"</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"
    st.markdown(f"<div class='wrap'><table class='tbl'>{thead}{tbody}</table></div>", unsafe_allow_html=True)

def render_daily_area_table(area_totals: Dict[int, Dict[str, Tuple[int,int,int]]], year:int, month:int):
    inject_css()
    st.subheader(L("daily_table"))
    head = ["<th>"+html.escape("Area" if st.session_state.lang=="en" else "القسم")+"</th>"]
    days = list(range(1, st.session_state.days+1))
    for d in days:
        dname = weekday_name(int(year), int(month), int(d))
        head.append(f"<th>{int(d)}/{int(month)}<div class='sub'>{html.escape(dname)}</div></th>")
    thead = "<thead><tr>" + "".join(head) + "</tr></thead>"
    body_rows = []
    for area in ["fast","resp_triage","acute","resus"]:
        left = f"<th class='sticky'>{html.escape(AREA_LABEL[st.session_state.lang][area])}</th>"
        cells = []
        for d in days:
            a, r, short = area_totals[d][area]
            cls = "ok" if short==0 else "short"
            cells.append(f"<td><div class='cell'><span class='badge {cls}'>{a}/{r}</span></div></td>")
        body_rows.append("<tr>"+left+"".join(cells)+"</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"
    st.markdown(f"<div class='wrap'><table class='tbl'>{thead}{tbody}</table></div>", unsafe_allow_html=True)

# ---------- Calendar Offday Picker ----------
def render_offday_calendar(doc: str):
    inject_css()
    st.caption(L("off_calendar"))
    y = int(st.session_state.year); m = int(st.session_state.month)
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(y, m)
    selected = set(st.session_state.offdays.get(doc, set()))
    max_days = int(st.session_state.days)

    head_cols = st.columns(7)
    day_names = I18N[st.session_state.lang]["weekday"]
    for i, col in enumerate(head_cols):
        col.markdown(f"<div class='sub' style='text-align:center'><b>{html.escape(day_names[i])}</b></div>", unsafe_allow_html=True)

    for w in weeks:
        cols = st.columns(7)
        for i, d in enumerate(w):
            with cols[i]:
                if d == 0 or d > max_days:
                    st.markdown("&nbsp;")
                else:
                    key = f"off_{doc}_{y}_{m}_{d}"
                    default_val = d in selected
                    val = st.checkbox(str(d), value=default_val, key=key)
                    if val: selected.add(d)
                    else: selected.discard(d)

    if len(selected) > 3:
        keep = set(sorted(selected)[:3])
        for d in selected - keep:
            k = f"off_{doc}_{y}_{m}_{d}"
            if k in st.session_state: st.session_state[k] = False
        selected = keep
        st.warning("Max 3 off-days per month.")

    st.session_state.offdays[doc] = selected
    c1, c2 = st.columns(2)
    with c2:
        if st.button(L("clear_off"), key=f"clear_off_{doc}"):
            for w in weeks:
                for d in w:
                    if d and d <= max_days:
                        k = f"off_{doc}_{y}_{m}_{d}"
                        if k in st.session_state: st.session_state[k] = False
            st.session_state.offdays[doc] = set()
            st.experimental_rerun()

# ---------- Inline editor ----------
ALL_CODES = [""] + SHIFT_COLS_ORDER
def parse_code(code: str) -> Tuple[str,str]:
    code = (code or "").strip().upper()
    if code == "" or len(code) < 2: return ("","")
    area = LETTER_TO_AREA.get(code[0], "")
    shift = DIGIT_TO_SHIFT.get(code[-1], "")
    if area in AREAS and shift in SHIFTS: return area, shift
    return ("","")

def apply_inline_changes(grid_new: pd.DataFrame, validate: bool, force: bool):
    df_old = st.session_state.result_df.copy()
    assigned_map = {(r.doctor, int(r.day)):(r.area, r.shift) for r in df_old.itertuples(index=False)}
    counts = df_old.groupby("doctor").size().to_dict()
    invalid = []
    for doc in st.session_state.doctors:
        if doc not in grid_new.index: continue
        for d_str in grid_new.columns:
            day = int(d_str)
            new_code = str(grid_new.at[doc, d_str]).strip().upper()
            old_code = ""
            if (doc, day) in assigned_map:
                old_code = code_for(*assigned_map[(doc,day)])
            if new_code == old_code: continue
            if (doc, day) in assigned_map:
                counts[doc] = max(0, counts.get(doc,0) - 1)
                assigned_map.pop((doc, day), None)
                df_old = df_old[~((df_old["doctor"]==doc) & (df_old["day"]==day))]
            if new_code == "" or len(new_code)<2: continue
            area, shift = parse_code(new_code)
            if area=="" or shift=="":
                invalid.append((doc, day, new_code, "bad code"))
            else:
                if validate and not force:
                    ok, msg = constraints_ok(doc, day, area, shift, assigned_map, counts)
                    if not ok:
                        invalid.append((doc, day, new_code, msg))
                        continue
                assigned_map[(doc, day)] = (area, shift)
                counts[doc] = counts.get(doc,0) + 1
                df_old = pd.concat([df_old, pd.DataFrame([{
                    "doctor":doc,"day":day,"area":area,"shift":shift,"code":code_for(area,shift)
                }])], ignore_index=True)
    st.session_state.result_df = df_old
    recompute_tables(df_old)
    return invalid

# ===== Sidebar =====
with st.sidebar:
    st.header(L("general"))
    lang_choice = st.radio(L("language"), [I18N["ar"]["arabic"], I18N["en"]["english"]],
                           index=0 if st.session_state.lang=="ar" else 1, horizontal=True, key="lang_radio")
    st.session_state.lang = "ar" if lang_choice == I18N["ar"]["arabic"] else "en"

    st.number_input(L("year"), 2024, 2100, key="year_input", value=st.session_state.year)
    st.number_input(L("month"), 1, 12, key="month_input", value=st.session_state.month)
    st.slider(L("days"), 28, 31, value=st.session_state.days, key="days_slider")  # ← fixed: closed parentheses
    _ = st.text_input(L("seed"), value=st.session_state.get("seed_input_txt",""), key="seed_input_txt")

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
tab_rules, tab_docs, tab_gen, tab_export = st.tabs([L("rules"), L("doctors_tab"), L("run_tab"), L("export")])

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
                value=int(st.session_state.get(f"gcap_{g}", {"senior":16,"g1":18,"g2":18,"g3":18,"g4":18,"g5":18}[g])),
                key=f"gcap_{g}"
            )
    st.caption("Per-doctor caps are set below; these are defaults for new doctors.")

    st.subheader(L("adv_rules"))
    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption(L("max_night") + " — per doctor (edit in Doctors tab)")
    with c2:
        st.caption(L("max_week") + " — per doctor (edit in Doctors tab)")
    with c3:
        hol_txt = st.text_input(L("holidays"), ",".join(map(str, sorted(st.session_state.holidays))), key="hol_txt_rules")
        hols = set()
        for t in hol_txt.replace(" ", "").split(","):
            if t.isdigit():
                d = int(t)
                if 1 <= d <= st.session_state.days:
                    hols.add(d)
        st.session_state.holidays = hols

    st.subheader(L("colors"))
    tcol1, tcol2 = st.columns([2,1])
    def apply_template(name):
        st.session_state.area_color_names = TEMPLATES[name].copy()
        st.session_state.area_colors = {a: PALETTE[st.session_state.area_color_names[a]] for a in AREAS}
    with tcol1:
        st.caption(L("templates"))
        tpl = st.selectbox(" ", [L("calm"), L("contrast")], index=0, key="tpl_select")
        inv_tpl = {I18N["ar"]["calm"]:"calm", I18N["ar"]["contrast"]:"contrast",
                   I18N["en"]["calm"]:"calm", I18N["en"]["contrast"]:"contrast"}
        if st.button(L("apply_template"), key="btn_apply_tpl"):
            apply_template(inv_tpl[tpl]); st.success("Template applied.")
    with tcol2:
        if st.button(L("reset_colors"), use_container_width=True, key="btn_reset_colors"):
            st.session_state.area_color_names = DEFAULT_AREA_COLOR_NAMES.copy()
            st.session_state.area_colors = {a: PALETTE[DEFAULT_AREA_COLOR_NAMES[a]] for a in AREAS}
            st.success("Colors reset.")
    st.caption(L("area_colors"))
    sel_cols = st.columns(4)
    color_labels = [L("yellow"), L("green"), L("blue"), L("red")]
    key_from_label = {I18N["ar"]["yellow"]:"yellow", I18N["ar"]["green"]:"green", I18N["ar"]["blue"]:"blue", I18N["ar"]["red"]:"red",
                      I18N["en"]["yellow"]:"yellow", I18N["en"]["green"]:"green", I18N["en"]["blue"]:"blue", I18N["en"]["red"]:"red"}
    for idx, area in enumerate(AREAS):
        with sel_cols[idx]:
            label = LBL_AREA(area)
            current = st.session_state.area_color_names.get(area, DEFAULT_AREA_COLOR_NAMES[area])
            choice = st.selectbox(label, color_labels, index=["yellow","green","blue","red"].index(current), key=f"clr_{area}")
            ckey = key_from_label[choice]
            st.session_state.area_color_names[area] = ckey
            st.session_state.area_colors[area] = PALETTE[ckey]

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
                st.session_state.cap_map[n] = int(st.session_state.get("gcap_g3", 18))
                st.session_state.allowed_shifts[n] = set(SHIFTS)
                st.session_state.offdays[n] = set()
                st.session_state.max_night_map[n] = 6
                st.session_state.max_week_map[n] = 5
                st.session_state.avoid_holidays_map[n] = False
                added += 1
        st.success(f"Added {added}")

    st.divider()
    rem_col1, rem_col2 = st.columns([2,1])
    with rem_col2:
        to_remove = st.selectbox(L("remove_doc"), ["—"] + st.session_state.doctors, key="rem_sel")
        if st.button(L("remove"), key="rem_btn") and to_remove != "—":
            st.session_state.doctors.remove(to_remove)
            for d in ["group_map","cap_map","allowed_shifts","offdays","max_night_map","max_week_map","avoid_holidays_map"]:
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
                                                       value=int(st.session_state.cap_map.get(doc, 18)),
                                                       key=f"cap_{doc}")
        ch0, ch1, ch2 = st.columns(3)
        checks = {}
        for i, sh in enumerate(SHIFTS):
            col = ch0 if i==0 else ch1 if i==1 else ch2
            with col:
                checks[sh] = st.checkbox(LBL_SHIFT(sh),
                                         value=(sh in st.session_state.allowed_shifts.get(doc,set(SHIFTS))),
                                         key=f"allow_{doc}_{sh}")
        st.session_state.allowed_shifts[doc] = {s for s,v in checks.items() if v} or set(SHIFTS)

        st.markdown(f"**{L('offdays')}**")
        render_offday_calendar(doc)

        st.markdown(f"**{L('adv_rules')}**")
        a1, a2, a3 = st.columns(3)
        with a1:
            st.session_state.max_night_map[doc] = st.number_input(L("max_night"), 0, 31,
                                                                  value=int(st.session_state.max_night_map.get(doc,6)),
                                                                  key=f"maxN_{doc}")
        with a2:
            st.session_state.max_week_map[doc] = st.number_input(L("max_week"), 0, 7,
                                                                 value=int(st.session_state.max_week_map.get(doc,5)),
                                                                 key=f"maxW_{doc}")
        with a3:
            st.session_state.avoid_holidays_map[doc] = st.checkbox(L("avoid_holidays"),
                                                                   value=bool(st.session_state.avoid_holidays_map.get(doc,False)),
                                                                   key=f"avoidH_{doc}")

# ---------- Generate tab ----------
with tab_gen:
    row1 = st.columns([2,1])
    with row1[0]:
        if st.button(L("run"), key="run_btn", type="primary", use_container_width=True):
            random_generate()
    with row1[1]:
        if st.button(L("balance"), key="balance_btn", use_container_width=True):
            balance_workload(); st.success(L("balanced_ok"))

    if st.session_state.result_df.empty:
        st.info(L("need_generate"))
    else:
        sheet = sheet_day_doctor(st.session_state.result_df, st.session_state.days, st.session_state.doctors)
        dmap  = day_shift_map(st.session_state.result_df, st.session_state.days)
        dcnts = daily_counts(st.session_state.result_df, st.session_state.days)
        atot  = area_totals_from_daily_counts(dcnts)

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
            render_day_doctor_cards(sheet, int(st.session_state.year), int(st.session_state.month), st.session_state.doctors)
        elif st.session_state.view_mode == "doctor_day":
            render_doctor_day_cards(sheet, int(st.session_state.year), int(st.session_state.month), st.session_state.doctors)
        else:
            render_day_shift_cards(dmap, int(st.session_state.year), int(st.session_state.month))

        st.divider()
        render_daily_area_table(atot, int(st.session_state.year), int(st.session_state.month))

        st.divider()
        st.markdown(f"**{L('inline_edit')}**")
        st.caption(L("inline_hint"))
        base_grid = grid_doctor_day(st.session_state.result_df, st.session_state.days, st.session_state.doctors)
        col_cfg = {str(d): st.column_config.SelectboxColumn(label=f"{d}/{st.session_state.month}",
                                                            options=([""]+SHIFT_COLS_ORDER),
                                                            required=False)
                   for d in range(1, st.session_state.days+1)}
        edited = st.data_editor(base_grid, column_config=col_cfg, num_rows="fixed",
                                use_container_width=True, key="inline_grid", height=480)
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
                 year:int, month:int, df_assign: pd.DataFrame) -> bytes:
    if not XLSX_AVAILABLE: return b""
    out = BytesIO()
    wb = xlsxwriter.Workbook(out, {"in_memory": True})
    hdr = wb.add_format({"bold":True,"align":"center","valign":"vcenter","bg_color":"#E8EEF9","border":1})
    day_hdr = wb.add_format({"bold":True,"align":"center","valign":"vcenter","bg_color":"#EEF5FF","border":1})
    cell = wb.add_format({"align":"center","valign":"vcenter","border":1})
    left_hdr = wb.add_format({"bold":True,"align":"left","valign":"vcenter","bg_color":"#F8F9FE","border":1})
    left_wrap = wb.add_format({"align":"left","valign":"top","border":1,"text_wrap":True})
    blank = wb.add_format({"align":"center","valign":"vcenter","border":1})
    ok_fmt = wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color":"#E7F7E9"})
    short_fmt = wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color":"#FDEAEA"})

    area_fmt = {
        "fast": wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color": st.session_state.area_colors["fast"]}),
        "resp_triage": wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color": st.session_state.area_colors["resp_triage"]}),
        "acute": wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color": st.session_state.area_colors["acute"]}),
        "resus": wb.add_format({"align":"center","valign":"vcenter","border":1,"bg_color": st.session_state.area_colors["resus"]}),
    }

    # Rota (Day×Doctor): cells colored, no text; add comment with code
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
        ws.set_row(i, 24)
        for j, doc in enumerate(sheet.columns, start=1):
            v = sheet.loc[day, doc]
            if pd.isna(v) or str(v).strip()=="":
                ws.write(i,j,"",blank)
            else:
                code = str(v)
                area = LETTER_TO_AREA.get(code[0], None)
                fmt = area_fmt.get(area, cell)
                ws.write(i,j, "", fmt)
                try:
                    ws.write_comment(i, j, code)  # tooltip with code
                except: pass

    # Doctor×Day (colored)
    wsD = wb.add_worksheet("Doctor×Day")
    wsD.freeze_panes(1,1)
    wsD.set_column(0, 0, 24)
    for c in range(len(sheet.index)): wsD.set_column(c+1, c+1, 12)
    wsD.write(0,0, L("doctor"), hdr)
    for j, day in enumerate(sheet.index, start=1):
        wd = calendar.weekday(year, month, int(day))
        wd_name = I18N[st.session_state.lang]["weekday"][wd]
        wsD.write(0,j, f"{int(day)}/{int(month)}\n{wd_name}", hdr)
    for i, doc in enumerate(sheet.columns, start=1):
        wsD.write(i,0, doc, left_hdr)
        wsD.set_row(i, 20)
        for j, day in enumerate(sheet.index, start=1):
            v = sheet.loc[day, doc]
            if pd.isna(v) or str(v).strip()=="":
                wsD.write(i,j,"", blank)
            else:
                code = str(v)
                area = LETTER_TO_AREA.get(code[0], None)
                fmt = area_fmt.get(area, cell)
                wsD.write(i,j, "", fmt)
                try:
                    wsD.write_comment(i, j, code)
                except: pass

    # Coverage gaps
    ws2 = wb.add_worksheet("Coverage gaps")
    cols = ["day","shift","area","abbr","required","assigned","short_by"]
    for j,cname in enumerate(cols): ws2.write(0,j,cname,hdr)
    for i,row in enumerate(gaps.itertuples(index=False), start=1):
        for j,cname in enumerate(cols):
            ws2.write(i,j, getattr(row,cname) if hasattr(row,cname) else row[j], cell)

    # Remaining capacity
    ws3 = wb.add_worksheet("Remaining capacity")
    cols2 = ["doctor","assigned","cap","remaining"]
    for j,cname in enumerate(cols2): ws3.write(0,j,cname,hdr)
    for i,row in enumerate(st.session_state.remain.itertuples(index=False), start=1):
        for j,cname in enumerate(cols2):
            ws3.write(i,j, getattr(row,cname) if hasattr(row,cname) else row[j], cell)

    # ByShift (names listed; keep text)
    ws4 = wb.add_worksheet("ByShift")
    ws4.freeze_panes(1,1)
    ws4.set_column(0, 0, 14)
    for c in range(len(SHIFT_COLS_ORDER)): ws4.set_column(c+1, c+1, 24)
    ws4.write(0,0, L("day"), hdr)
    for j, code in enumerate(SHIFT_COLS_ORDER, start=1): ws4.write(0,j, f"{code}", hdr)
    def day_shift_map_export(df: pd.DataFrame, days:int):
        m = {d:{c:[] for c in SHIFT_COLS_ORDER} for d in range(1, days+1)}
        if df.empty: return m
        for r in df.itertuples(index=False):
            d = int(r.day); code = str(r.code)
            if code in m[d]: m[d][code].append(r.doctor)
        for d in m:
            for c in m[d]: m[d][c] = sorted(m[d][c])
        return m
    dmap = day_shift_map_export(df_assign, st.session_state.days)
    for i, day in enumerate(sorted(dmap.keys()), start=1):
        wd = calendar.weekday(year, month, int(day))
        wd_name = I18N[st.session_state.lang]["weekday"][wd]
        ws4.write(i,0, f"{int(day)}/{int(month)}\n{wd_name}", hdr)
        ws4.set_row(i, 30)
        for j, code in enumerate(SHIFT_COLS_ORDER, start=1):
            names = dmap[day].get(code, [])
            area = LETTER_TO_AREA.get(code[0], None)
            fmt = area_fmt.get(area, left_wrap)
            ws4.write(i,j, "\n".join(names), fmt)

    # Daily Dashboard (a/r)
    ws5 = wb.add_worksheet("Daily Dashboard")
    ws5.freeze_panes(1,1)
    ws5.set_column(0, 0, 16)
    for c in range(len(SHIFT_COLS_ORDER)): ws5.set_column(c+1, c+1, 12)
    ws5.write(0,0, L("day"), hdr)
    for j, code in enumerate(SHIFT_COLS_ORDER, start=1): ws5.write(0,j, code, hdr)
    dcnts = daily_counts(df_assign, st.session_state.days)
    for i, day in enumerate(range(1, st.session_state.days+1), start=1):
        wd = calendar.weekday(year, month, int(day))
        wd_name = I18N[st.session_state.lang]["weekday"][wd]
        ws5.write(i,0, f"{int(day)}/{int(month)}\n{wd_name}", hdr)
        ws5.set_row(i, 20)
        for j, code in enumerate(SHIFT_COLS_ORDER, start=1):
            a, r, short = dcnts[day][code]
            fmt = ok_fmt if short==0 else short_fmt
            ws5.write(i,j, f"{a}/{r}", fmt)

    # Area Totals
    ws6 = wb.add_worksheet("Area Totals")
    ws6.freeze_panes(1,1)
    ws6.set_column(0, 0, 22)
    for c in range(st.session_state.days): ws6.set_column(c+1, c+1, 12)
    ws6.write(0,0, "Area" if st.session_state.lang=="en" else "القسم", hdr)
    for j, d in enumerate(range(1, st.session_state.days+1), start=1):
        wd = calendar.weekday(year, month, int(d))
        wd_name = I18N[st.session_state.lang]["weekday"][wd]
        ws6.write(0,j, f"{int(d)}/{int(month)}\n{wd_name}", hdr)
    dcnts = daily_counts(df_assign, st.session_state.days)
    atot = area_totals_from_daily_counts(dcnts)
    for i, area in enumerate(["fast","resp_triage","acute","resus"], start=1):
        ws6.write(i,0, AREA_LABEL[st.session_state.lang][area], left_hdr)
        ws6.set_row(i, 20)
        for j, d in enumerate(range(1, st.session_state.days+1), start=1):
            a, r, short = atot[d][area]
            fmt = ok_fmt if short==0 else short_fmt
            ws6.write(i,j, f"{a}/{r}", fmt)

    wb.close()
    return out.getvalue()

def export_pdf(sheet: pd.DataFrame, year:int, month:int) -> bytes:
    if not REPORTLAB_AVAILABLE:
        return b""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
    styles = getSampleStyleSheet()
    story = []
    title = f"ED Rota — {month}/{year}"
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 6))

    header = ["Day"] + list(sheet.columns)
    data = [header]
    for day in sheet.index:
        wd = I18N[st.session_state.lang]["weekday"][calendar.weekday(year, month, int(day))]
        row = [f"{int(day)}/{int(month)}\n{wd}"]
        for docname in sheet.columns:
            v = sheet.loc[day, docname]
            row.append("" if (pd.isna(v) or str(v).strip()=="") else "")  # لا نص داخل الخلية
        data.append(row)

    tbl = Table(data, repeatRows=1)
    base = [
        ('FONT', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#EEF5FF")),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor("#CCCCCC")),
    ]
    for i, day in enumerate(sheet.index, start=1):
        for j, docname in enumerate(sheet.columns, start=1):
            v = sheet.loc[day, docname]
            if pd.isna(v) or str(v).strip()=="": continue
            code = str(v)
            area = LETTER_TO_AREA.get(code[0], None)
            bg = st.session_state.area_colors.get(area, "#FFFFFF")
            base.append(('BACKGROUND', (j,i), (j,i), colors.HexColor(bg)))
    tbl.setStyle(TableStyle(base))
    story.append(tbl)
    doc.build(story)
    return buf.getvalue()

# ---------- Export tab ----------
tab_export_placeholder = tab_export
with tab_export_placeholder:
    if st.session_state.result_df.empty:
        st.info(L("need_generate"))
    else:
        sheet = sheet_day_doctor(st.session_state.result_df, st.session_state.days, st.session_state.doctors)
        if XLSX_AVAILABLE:
            data_x = export_excel(sheet, st.session_state.gaps, st.session_state.remain,
                                  int(st.session_state.year), int(st.session_state.month), st.session_state.result_df)
            st.download_button(L("download_xlsx"), data=data_x,
                               file_name="ED_rota.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="dl_xlsx", use_container_width=True)
        pdf_bytes = export_pdf(sheet, int(st.session_state.year), int(st.session_state.month))
        if REPORTLAB_AVAILABLE and pdf_bytes:
            st.download_button(L("download_pdf"), data=pdf_bytes,
                               file_name="ED_rota.pdf",
                               mime="application/pdf",
                               key="dl_pdf", use_container_width=True)
        else:
            st.info(L("pdf_na"))
