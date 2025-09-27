# app.py — ED Rota Pro
# Squares-by-Area, Compact Cards, Tooltip Codes, Display Options, Styled Exports
# -----------------------------------------------------------------------------

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
        # NEW display options
        "display_opts": "خيارات العرض",
        "disp_mode": "نمط الخلية",
        "mode_squares": "مربعات ملونة (مضغطة)",
        "mode_badges": "شارات نصية",
        "mode_both": "مربعات + نص",
        "dot_size": "حجم المربّع",
        "legend": "دليل الألوان (المنطقة)",
        "export_codes": "إظهار الأكواد نصيًا في التصدير",
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
        # NEW display options
        "display_opts": "Display options",
        "disp_mode": "Cell mode",
        "mode_squares": "Color squares (compact)",
        "mode_badges": "Text badges",
        "mode_both": "Squares + text",
        "dot_size": "Square size",
        "legend": "Color legend (area)",
        "export_codes": "Show codes as text in export",
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

# ===== Shift times for rest rule =====
SHIFT_START = {"morning":7, "evening":15, "night":23}
SHIFT_END   = {"morning":15,"evening":23,"night":7}

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
    # Demo doctors/groups (اختصرنا القائمة؛ أضف كل أطبائك كما في نسختك)
    if "group_map" not in ss:
        ss.group_map = {"Dr.A":"g3","Dr.B":"g3","Dr.C":"g2","Dr.D":"g5","Dr.E":"senior"}
    if "doctors" not in ss: ss.doctors = list(ss.group_map.keys())
    if "cap_map" not in ss:
        GROUP_CAP = {"senior":16,"g1":18,"g2":18,"g3":18,"g4":18,"g5":18}
        ss.cap_map = {n: GROUP_CAP[ss.group_map[n]] for n in ss.doctors}
    if "allowed_shifts" not in ss:
        ss.allowed_shifts = {n:set(SHIFTS) for n in ss.doctors}
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
    # Display options
    if "disp_mode" not in ss: ss.disp_mode = "squares"  # "squares" | "badges" | "both"
    if "dot_size" not in ss: ss.dot_size = 14
    if "export_codes" not in ss: ss.export_codes = False
    # Colors
    if "area_colors" not in ss:
        ss.area_colors = {"fast":"#FFF7C2","resp_triage":"#E7F7E9","acute":"#E6F3FF","resus":"#FDEAEA"}
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
    return wd in (4,5)

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
    if ss.avoid_holidays_map.get(name, False) and (day in ss.holidays): return False, "holiday pref"

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
        night_taken = sum(1 for (n,d),(a,s) in assigned_map.items() if n==name and s=="night")
        if night_taken >= int(ss.max_night_map.get(name, 999)): return False, "max night"
    week = iso_week(int(ss.year), int(ss.month), int(day))
    w_count = sum(1 for (n,d),(a,s) in assigned_map.items() if n==name and iso_week(int(ss.year),int(ss.month),int(d))==week)
    if w_count >= int(ss.max_week_map.get(name, 999)): return False, "weekly limit"

    if ss.min_rest > 0:
        prev = assigned_map.get((name, day-1))
        if prev:
            _, p_shift = prev
            if not rest_ok(p_shift, shift, ss.min_rest): return False, "rest prev→today"
        nxt = assigned_map.get((name, day+1))
        if nxt:
            _, n_shift = nxt
            end_cur  = {"morning":15,"evening":23,"night":7}[shift]
            start_nx = {"morning":7,"evening":15,"night":23}[n_shift]
            rest2 = start_nx - end_cur
            if rest2 < 0: rest2 += 24
            if rest2 < int(ss.min_rest): return False, "rest today→next"

    streak = 0; t = day-1
    while t>=1 and ((name,t) in assigned_map): streak += 1; t -= 1
    if streak+1 > int(ss.max_consec): return False, "max consecutive"
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
                wk_cnt = sum(1 for (n,d),(a,s) in assigned_map.items() if n==nm and is_weekend(int(st.session_state.year), int(st.session_state.month), int(d)))
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
                    wk = sum(1 for (n,d),(a,s) in assigned_map.items() if n==nm and is_weekend(int(st.session_state.year), int(st.session_state.month), int(d)))
                    night_cnt = sum(1 for (n,d),(a,s) in assigned_map.items() if n==nm and s=="night")
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

# ===== Grids & maps =====
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

# ---------- THEME-AWARE CSS ----------
def inject_css():
    css = f"""
    <style>
      :root {{
        --text: #111827;
        --bg: #ffffff;
        --card-bg: #ffffff;
        --thead-bg: #f8f9fe;
        --border: #e6e8ef;
        --badge-text: #111111;
      }}
      @media (prefers-color-scheme: dark) {{
        :root {{
          --text: #e5e7eb;
          --bg: #0f172a;
          --card-bg: #111827;
          --thead-bg: #1f2937;
          --border: #374151;
          --badge-text: #111111;
        }}
      }}
      .wrap {{ overflow:auto; max-height: 74vh; border:1px solid var(--border); border-radius:14px; background:var(--card-bg); }}
      table.tbl {{ border-collapse: separate; border-spacing:0; width: 100%; min-width: 900px; color: var(--text); }}
      table.tbl th, table.tbl td {{ border:1px solid var(--border); padding:6px 8px; vertical-align:middle; }}
      table.tbl thead th {{ position:sticky; top:0; background:var(--thead-bg); z-index:2; text-align:center; font-weight:700; }}
      table.tbl tbody th.sticky {{ position:sticky; left:0; background:var(--card-bg); z-index:1; white-space:nowrap; font-weight:700; }}
      .cell {{ display:flex; align-items:center; justify-content:center; min-height:40px; }}
      .badge {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; font-weight:700; border:1px solid var(--border); color: var(--badge-text); }}
      .dot {{ display:inline-block; border:1px solid var(--border); border-radius:6px; }}
      .ok    {{ background:#E7F7E9; color:#14532d; }}
      .short {{ background:#FDEAEA; color:#7f1d1d; }}
      .sub {{ font-size:11px; font-weight:500; opacity:.85; }}
      .legend {{ display:flex; gap:10px; flex-wrap:wrap; margin:4px 0 8px; }}
      .legend-item {{ display:flex; align-items:center; gap:6px; font-size:12px; }}
      .legend-swatch {{ width:14px; height:14px; border:1px solid var(--border); border-radius:4px; display:inline-block; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# ---------- Helpers to render a cell ----------
def cell_content(code: str) -> str:
    """
    Returns HTML for a cell according to display mode:
    - squares: colored square only (by area), with title tooltip = code
    - badges: text badge with code
    - both: small square + code text
    """
    if not code: return "<div class='cell'></div>"
    area = LETTER_TO_AREA.get(code[0], None)
    bg = area_color(area)
    mode = st.session_state.disp_mode
    size = int(st.session_state.dot_size)
    sq = f"<span class='dot' title='{html.escape(code)}' style='background:{bg}; width:{size}px; height:{size}px;'></span>"
    bd = f"<span class='badge' style='background:{bg}'>{html.escape(code)}</span>"
    if mode == "squares":
        return f"<div class='cell'>{sq}</div>"
    elif mode == "badges":
        return f"<div class='cell'>{bd}</div>"
    else:  # both
        return f"<div class='cell' style='gap:6px'>{sq}{bd}</div>"

# ---------- Renderers ----------
def render_day_doctor_cards(sheet: pd.DataFrame, year:int, month:int, doctors:List[str]):
    inject_css()
    # legend
    st.markdown("<div class='legend'>" + "".join(
        [f"<div class='legend-item'><span class='legend-swatch' style='background:{area_color(a)}'></span>{html.escape(LBL_AREA(a))}</div>" for a in AREAS]
    ) + "</div>", unsafe_allow_html=True)

    head = ["<th>"+html.escape(L("day"))+"</th>"] + [f"<th>{html.escape(doc)}</th>" for doc in doctors]
    thead = "<thead><tr>" + "".join(head) + "</tr></thead>"
    body_rows = []
    for day in sheet.index:
        dname = weekday_name(int(year), int(month), int(day))
        left = f"<th class='sticky'>{int(day)} / {int(month)}<div class='sub'>{html.escape(dname)}</div></th>"
        cells = []
        for doc in doctors:
            val = sheet.loc[day, doc] if doc in sheet.columns else ""
            val = "" if (pd.isna(val) or str(val).strip()=="") else str(val)
            cells.append(f"<td>{cell_content(val)}</td>")
        body_rows.append("<tr>"+left+"".join(cells)+"</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"
    st.markdown(f"<div class='wrap'><table class='tbl'>{thead}{tbody}</table></div>", unsafe_allow_html=True)

def render_doctor_day_cards(sheet: pd.DataFrame, year:int, month:int, doctors:List[str]):
    inject_css()
    st.markdown("<div class='legend'>" + "".join(
        [f"<div class='legend-item'><span class='legend-swatch' style='background:{area_color(a)}'></span>{html.escape(LBL_AREA(a))}</div>" for a in AREAS]
    ) + "</div>", unsafe_allow_html=True)

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
            val = "" if (pd.isna(val) or str(val).strip()=="") else str(val)
            cells.append(f"<td>{cell_content(val)}</td>")
        body_rows.append("<tr>"+left+"".join(cells)+"</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"
    st.markdown(f"<div class='wrap'><table class='tbl'>{thead}{tbody}</table></div>", unsafe_allow_html=True)

def render_day_shift_cards(day_map: Dict[int, Dict[str, List[str]]], year:int, month:int):
    inject_css()
    head = ["<th>"+html.escape(L("day"))+"</th>"] + [f"<th>{html.escape(code)}</th>" for code in SHIFT_COLS_ORDER]
    thead = "<thead><tr>" + "".join(head) + "</tr></thead>"
    body_rows = []
    for day in sorted(day_map.keys()):
        dname = weekday_name(int(year), int(month), int(day))
        left = f"<th class='sticky'>{int(day)} / {int(month)}<div class='sub'>{html.escape(dname)}</div></th>"
        cells = []
        for code in SHIFT_COLS_ORDER:
            docs = day_map[day].get(code, [])
            if not docs:
                cells.append("<td><div class='cell'></div></td>")
            else:
                # names as compact "badges" (neutral), keep concise
                inner = "".join([f"<span class='badge' style='background:#f3f4f6'>{html.escape(n)}</span>" for n in docs])
                cells.append(f"<td><div class='cell' style='flex-wrap:wrap; gap:4px'>{inner}</div></td>")
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
        left = f"<th class='sticky'>{html.escape(LBL_AREA(area))}</th>"
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
        col.markdown(f"<div class='sub'><b>{html.escape(day_names[i])}</b></div>", unsafe_allow_html=True)

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
    r1, r2 = st.columns(2)
    with r2:
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
    st.slider(L("days"), 28, 31, key="days_slider", value=
