# app.py — Rota Matrix Pro (كامل)
# ------------------------------------------------------------
# - GA + CP-SAT (إن توفر OR-Tools) مع قيد: لا يزيد عن 6 شفتات متتالية
# - إدارة أطباء: لصق جماعي / إضافة فردية مع قيود لكل طبيب
# - تخصيص: إضافة شفت جديد وتعديل ألوان الشفتات
# - لغة: عربي / English
# - حفظ/تحميل/تفريغ التهيئة (JSON)
# - عرض مصفوفي (اليوم+التاريخ في الأعلى) وبطاقات داخل الخلايا
# - عرض حسب الوردية (من في الشفت)
# - تصدير Excel ملوّن يطابق العرض + PDF (إن توفر reportlab)
# - إصلاح اختلاف "إنعاش/انعاش" وتطبيع الأسماء

import streamlit as st
import pandas as pd
import numpy as np
import calendar
from io import BytesIO
import json
from dataclasses import dataclass
from typing import Dict, Tuple, List, Optional

# محاولات مكتبات اختيارية
try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except Exception:
    ORTOOLS_AVAILABLE = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

st.set_page_config(page_title="Rota Matrix Pro", layout="wide")

# ===== اللغات =====
LANGS = {
    "ar": {
        "title": "جدولة المناوبات — عرض مصفوفي ببطاقات",
        "settings": "الإعدادات",
        "language": "اللغة",
        "arabic": "العربية",
        "english": "English",
        "year": "السنة",
        "month": "الشهر",
        "days": "عدد الأيام",
        "per_doc_cap": "سقف الشفتات للطبيب",
        "max_consecutive": "الحد الأقصى للشفتات المتتالية",
        "min_total": "أدنى إجمالي للوردية (يوميًا)",
        "max_total": "أقصى إجمالي للوردية (يوميًا)",
        "coverage_caption": "الحد الأدنى لتغطية الأقسام (في كل وردية/يوم)",
        "triage": "فرز",
        "resp": "تنفسية",
        "obs": "ملاحظة",
        "icu": "إنعاش",
        "engine": "طريقة التوليد",
        "ga": "ذكاء اصطناعي (GA)",
        "cpsat": "محلّل قيود (CP-SAT)",
        "gens": "عدد الأجيال (GA)",
        "pop": "حجم المجتمع (GA)",
        "mut": "معدل الطفرة (GA)",
        "rest_bias": "ميل للراحة (GA)",
        "customization": "التخصيص (الشفتات والألوان)",
        "add_shift": "إضافة شفت",
        "shift_name": "اسم الشفت",
        "shift_color": "لون الشفت (HEX)",
        "add_btn": "إضافة",
        "apply_colors": "تطبيق تعديل الألوان",
        "doctors_mgmt": "إدارة الأطباء",
        "paste_list": "إضافة مجموعة أسماء باللصق (اسم بكل سطر)",
        "mode_replace": "استبدال القائمة الحالية",
        "mode_append": "إضافة إلى القائمة الحالية",
        "apply_names": "تطبيق الأسماء",
        "add_one": "إضافة طبيب واحد",
        "doctor_name": "اسم الطبيب",
        "add_doc": "إضافة الطبيب",
        "per_doc_prefs": "قيود/تفضيلات للطبيب",
        "select_doctor": "اختر الطبيب",
        "cap_for_doc": "سقف شفتات هذا الطبيب",
        "days_off": "أيام غير متاح (أدخل أرقام الأيام مفصولة بفواصل)",
        "pref_shifts": "الشفتات المفضلة (اختياري)",
        "ban_shifts": "الشفتات الممنوعة (اختياري)",
        "apply_prefs": "تطبيق قيود الطبيب",
        "manual_override": "تخصيص يدوي (اختياري)",
        "manual_hint": "صيغة: يوم:شفت-قسم ، مثال: 1:صباح-فرز, 2:راحة, 3:ليل-ملاحظة",
        "apply_override": "تطبيق التخصيص",
        "save_load": "حفظ/تحميل التهيئة",
        "save": "حفظ",
        "load": "تحميل",
        "clear": "تفريغ",
        "generate": "توليد الجدول",
        "kpi_docs": "عدد الأطباء",
        "kpi_days": "عدد الأيام",
        "kpi_ortools": "توفر OR-Tools",
        "kpi_yes": "نعم",
        "kpi_no": "لا",
        "result": "النتيجة",
        "export": "تصدير",
        "excel": "تنزيل Excel منسّق",
        "pdf": "تنزيل PDF",
        "matrix_view": "عرض مصفوفي",
        "shift_view": "عرض حسب الوردية",
        "choose_day": "اختر اليوم",
        "choose_shift": "اختر الشفت",
        "choose_area": "اختر القسم",
        "doctors_in_shift": "الأطباء في الشفت المحدد",
        "info_first": "اضبط الإعدادات/الأسماء ثم اضغط «توليد الجدول».",
        "warn_capacity": "الحد الأدنى المطلوب أكبر من السعة — تم رفع سقف الطبيب تلقائيًا.",
        "ga_ok": "تم التوليد بالذكاء الاصطناعي.",
        "cpsat_na": "CP-SAT غير متاح. اختر وضع GA.",
        "cpsat_fail": "لم يُعثر على حل ضمن المهلة. زد المهلة أو خفّف القيود.",
        "cpsat_ok": "تم التوليد عبر",
        "doctor": "الطبيب",
        "rest": "راحة",
    },
    "en": {
        "title": "Rota Scheduling — Matrix with Cards",
        "settings": "Settings",
        "language": "Language",
        "arabic": "Arabic",
        "english": "English",
        "year": "Year",
        "month": "Month",
        "days": "Days",
        "per_doc_cap": "Per-doctor cap",
        "max_consecutive": "Max consecutive shifts",
        "min_total": "Min headcount per shift/day",
        "max_total": "Max headcount per shift/day",
        "coverage_caption": "Min coverage per area (each shift/day)",
        "triage": "Triage",
        "resp": "Respiratory",
        "obs": "Observation",
        "icu": "Resuscitation",
        "engine": "Generation engine",
        "ga": "Genetic Algorithm (GA)",
        "cpsat": "Constraint Solver (CP-SAT)",
        "gens": "Generations (GA)",
        "pop": "Population (GA)",
        "mut": "Mutation rate (GA)",
        "rest_bias": "Rest bias (GA)",
        "customization": "Customization (Shifts & Colors)",
        "add_shift": "Add shift",
        "shift_name": "Shift name",
        "shift_color": "Shift color (HEX)",
        "add_btn": "Add",
        "apply_colors": "Apply color changes",
        "doctors_mgmt": "Doctors Management",
        "paste_list": "Paste doctors list (one per line)",
        "mode_replace": "Replace current list",
        "mode_append": "Append to current list",
        "apply_names": "Apply names",
        "add_one": "Add single doctor",
        "doctor_name": "Doctor name",
        "add_doc": "Add doctor",
        "per_doc_prefs": "Doctor-specific constraints",
        "select_doctor": "Select doctor",
        "cap_for_doc": "Cap for this doctor",
        "days_off": "Unavailable days (comma-separated)",
        "pref_shifts": "Preferred shifts (optional)",
        "ban_shifts": "Forbidden shifts (optional)",
        "apply_prefs": "Apply doctor constraints",
        "manual_override": "Manual overrides (optional)",
        "manual_hint": "Format: day:shift-area, e.g. 1:Morning-Triage, 2:Rest",
        "apply_override": "Apply overrides",
        "save_load": "Save/Load configuration",
        "save": "Save",
        "load": "Load",
        "clear": "Clear",
        "generate": "Generate rota",
        "kpi_docs": "Doctors",
        "kpi_days": "Days",
        "kpi_ortools": "OR-Tools Available",
        "kpi_yes": "Yes",
        "kpi_no": "No",
        "result": "Result",
        "export": "Export",
        "excel": "Download styled Excel",
        "pdf": "Download PDF",
        "matrix_view": "Matrix view",
        "shift_view": "Shift-centric view",
        "choose_day": "Choose day",
        "choose_shift": "Choose shift",
        "choose_area": "Choose area",
        "doctors_in_shift": "Doctors in selected shift",
        "info_first": "Set options/add names, then click “Generate rota”.",
        "warn_capacity": "Minimum required > capacity — per-doctor cap increased automatically.",
        "ga_ok": "Generated by AI (GA).",
        "cpsat_na": "CP-SAT not available. Please use GA.",
        "cpsat_fail": "No solution within time limit. Increase limit or relax constraints.",
        "cpsat_ok": "Generated via",
        "doctor": "Doctor",
        "rest": "Rest",
    }
}

def L(key):  # ترجمة سريعة
    lang = st.session_state.get("lang", "ar")
    return LANGS[lang][key]

# ===== تهيئة الحالة =====
def init_state():
    if "lang" not in st.session_state:
        st.session_state.lang = "ar"
    if "doctors" not in st.session_state:
        st.session_state.doctors = [f"طبيب {i+1}" for i in range(20)]
    if "overrides" not in st.session_state:
        # overrides[name][day:int] = "راحة" أو "صباح - فرز"
        st.session_state.overrides: Dict[str, Dict[int, str]] = {}
    if "doctor_prefs" not in st.session_state:
        # doctor_prefs[name] = {"cap": None, "days_off": set(), "preferred": set(), "forbidden": set()}
        st.session_state.doctor_prefs: Dict[str, Dict] = {}
    if "shifts" not in st.session_state:
        st.session_state.shifts = ["صباح", "مساء", "ليل"]
    if "shift_colors" not in st.session_state:
        st.session_state.shift_colors = {"صباح": "#EAF3FF", "مساء": "#FFF2E6", "ليل": "#EEE8FF", "راحة": "#F2F3F7"}
    if "areas" not in st.session_state:
        st.session_state.areas = ["فرز", "تنفسية", "ملاحظة", "إنعاش"]
    if "coverage" not in st.session_state:
        st.session_state.coverage = {"فرز": 2, "تنفسية": 1, "ملاحظة": 4, "إنعاش": 3}

init_state()

# تطبيع أسماء الأقسام (حل اختلاف إنعاش/انعاش)
def normalize_vocab():
    cov = st.session_state.get("coverage", {})
    if "انعاش" in cov and "إنعاش" not in cov:
        cov["إنعاش"] = cov.pop("انعاش")
    st.session_state.coverage = {
        ("إنعاش" if k in ("انعاش", "إنعاش") else k): v
        for k, v in cov.items()
    }
    st.session_state.areas = [
        ("إنعاش" if a in ("انعاش", "إنعاش") else a)
        for a in st.session_state.get("areas", [])
    ]
normalize_vocab()

# ===== أنماط CSS ديناميكية حسب ألوان الشفتات =====
def inject_dynamic_css():
    css = "<style>"
    for idx, s in enumerate(st.session_state.shifts):
        color = st.session_state.shift_colors.get(s, "#F0F0F0")
        css += f".s-{idx}{{background:{color};}}"
    rest_color = st.session_state.shift_colors.get("راحة", "#F2F3F7")
    css += f".s-rest{{background:{rest_color};color:#6B7280;}}"
    css += """
      table.rota{border-collapse:separate;border-spacing:0;width:100%;}
      table.rota th, table.rota td{border:1px solid #e6e8ef;padding:6px 8px;vertical-align:middle;}
      table.rota thead th{position:sticky;top:0;background:#fff;z-index:2;text-align:center;}
      table.rota td.doc{position:sticky;left:0;background:#fff;z-index:1;font-weight:700;color:#5b74ff;white-space:nowrap;}
      .cell{display:flex;gap:6px;flex-wrap:wrap;justify-content:center;}
      .card{display:inline-flex;flex-direction:column;align-items:center;justify-content:center;
            padding:6px 10px;border-radius:10px;font-size:13px;font-weight:700;box-shadow:0 1px 0 rgba(0,0,0,.05);
            border:1px solid #e6e8ef;min-width:90px;}
      .sub{font-size:11px;font-weight:500;color:#6b7280;margin-top:2px;}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
inject_dynamic_css()

# ===== أدوات مساعدة =====
def arabic_weekday_name(y:int, m:int, d:int) -> str:
    week_ar = {"Mon":"الاثنين","Tue":"الثلاثاء","Wed":"الأربعاء","Thu":"الخميس","Fri":"الجمعة","Sat":"السبت","Sun":"الأحد"}
    try:
        w = calendar.day_abbr[calendar.weekday(y, m, d)]
        return week_ar.get(w, w)
    except Exception:
        return ""

def get_SHIFT_AREA() -> List[Tuple[str,str]]:
    return [(s, a) for s in st.session_state.shifts for a in st.session_state.areas]

def parse_days_list(text: str, days_max: int) -> List[int]:
    if not text.strip(): return []
    out = []
    for token in text.replace("،", ",").split(","):
        token = token.strip()
        if token.isdigit():
            v = int(token)
            if 1 <= v <= days_max:
                out.append(v)
    return sorted(set(out))

def normalize_area(ar: str) -> str:
    return "إنعاش" if ar in ("انعاش", "إنعاش") else ar

# ===== الشريط الجانبي =====
with st.sidebar:
    st.header(L("settings"))

    # لغة
    lang_choice = st.radio(L("language"), [LANGS['ar']['arabic'], LANGS['en']['english']],
                           index=0 if st.session_state.lang=="ar" else 1, horizontal=True)
    st.session_state.lang = "ar" if lang_choice == LANGS['ar']['arabic'] else "en"

    year  = st.number_input(L("year"), value=2025, step=1)
    month = st.number_input(L("month"), value=9, min_value=1, max_value=12, step=1)
    days  = st.slider(L("days"), 5, 31, 30)

    per_doc_cap = st.slider(L("per_doc_cap"), 1, 60, 18)
    max_consecutive = st.slider(L("max_consecutive"), 2, 14, 6)

    min_total = st.slider(L("min_total"), 0, 100, 10)
    max_total = st.slider(L("max_total"), 0, 100, 13)

    st.caption(L("coverage_caption"))
    c1, c2 = st.columns(2)
    with c1:
        cov_frz = st.number_input(L("triage"), 0, 40, st.session_state.coverage.get("فرز", 2))
        cov_tnf = st.number_input(L("resp"), 0, 40, st.session_state.coverage.get("تنفسية", 1))
    with c2:
        cov_mlh = st.number_input(L("obs"), 0, 40, st.session_state.coverage.get("ملاحظة", 4))
        cov_inash = st.number_input(L("icu"), 0, 40, st.session_state.coverage.get("إنعاش", st.session_state.coverage.get("انعاش", 3)))

    st.session_state.coverage = {"فرز":cov_frz, "تنفسية":cov_tnf, "ملاحظة":cov_mlh, "إنعاش":cov_inash}

    engine = st.radio(L("engine"), [L("ga"), L("cpsat")], index=0)
    if engine == L("ga"):
        gens = st.slider(L("gens"), 10, 500, 120)
        pop  = st.slider(L("pop"), 10, 200, 40)
        mut  = st.slider(L("mut"), 0.0, 0.2, 0.03, 0.01)
        rest_bias = st.slider(L("rest_bias"), 0.0, 0.95, 0.6, 0.05)
    else:
        cp_limit   = st.slider("CP-SAT time limit (s)", 5, 300, 90)
        cp_balance = st.checkbox("Balance load (objective)", True)

    # تخصيص الشفتات والألوان
    with st.expander(L("customization")):
        cols = st.columns([2,1,1])
        with cols[0]:
            new_shift = st.text_input(L("shift_name"), "")
        with cols[1]:
            new_shift_color = st.text_input(L("shift_color"), "#E0F0FF")
        with cols[2]:
            if st.button(L("add_btn")) and new_shift.strip():
                s = new_shift.strip()
                if s not in st.session_state.shifts:
                    st.session_state.shifts.append(s)
                    st.session_state.shift_colors[s] = new_shift_color.strip() or "#E0F0FF"
                    st.success("تمت الإضافة.")
                else:
                    st.info("الشفت موجود مسبقًا.")
        st.write(L("apply_colors"))
        for s in list(st.session_state.shifts) + ["راحة"]:
            st.session_state.shift_colors[s] = st.text_input(f"{s} color", st.session_state.shift_colors.get(s, "#F0F0F0"), key=f"col_{s}")

# ===== إدارة الأطباء =====
st.title(L("title"))
st.header(L("doctors_mgmt"))

with st.expander(L("paste_list")):
    pasted = st.text_area("", height=150, placeholder="مثال:\nأحمد سعيد\nمحمد علي\n...").strip()
    mode = st.radio("Mode", [L("mode_replace"), L("mode_append")], horizontal=True)
    if st.button(L("apply_names")):
        if pasted:
            new_names = [x.strip() for x in pasted.splitlines() if x.strip()]
            if mode == L("mode_replace"):
                st.session_state.doctors = new_names
                st.session_state.overrides = {}
                st.session_state.doctor_prefs = {}
            else:
                base = set(st.session_state.doctors)
                for n in new_names:
                    if n not in base:
                        st.session_state.doctors.append(n)
            st.success(f"{len(st.session_state.doctors)} {L('kpi_docs')}")
        else:
            st.warning("لم يتم العثور على أسماء.")

with st.expander(L("add_one")):
    one_name = st.text_input(L("doctor_name"), "")
    if st.button(L("add_doc")) and one_name.strip():
        if one_name not in st.session_state.doctors:
            st.session_state.doctors.append(one_name.strip())
            st.success("تمت الإضافة.")
        else:
            st.info("الاسم موجود مسبقًا.")

# ===== قيود/تفضيلات لكل طبيب =====
st.header(L("per_doc_prefs"))
with st.expander(L("per_doc_prefs")):
    if not st.session_state.doctors:
        st.warning("أضف أسماء أولًا.")
    else:
        target_doc = st.selectbox(L("select_doctor"), st.session_state.doctors)
        current = st.session_state.doctor_prefs.get(target_doc, {"cap": None, "days_off": set(), "preferred": set(), "forbidden": set()})
        cap_doc = st.number_input(L("cap_for_doc"), 0, 200, int(current["cap"] or 0))
        days_off_txt = st.text_input(L("days_off"), ",".join(map(str, sorted(current["days_off"]))) if current["days_off"] else "")
        pref = st.multiselect(L("pref_shifts"), st.session_state.shifts, default=sorted(current["preferred"]) if current["preferred"] else [])
        ban  = st.multiselect(L("ban_shifts"),  st.session_state.shifts, default=sorted(current["forbidden"]) if current["forbidden"] else [])
        if st.button(L("apply_prefs")):
            st.session_state.doctor_prefs[target_doc] = {
                "cap": int(cap_doc) if cap_doc>0 else None,
                "days_off": set(parse_days_list(days_off_txt, days)),
                "preferred": set(pref),
                "forbidden": set(ban),
            }
            st.success("تم الحفظ.")

# ===== تخصيص يدوي =====
st.header(L("manual_override"))
with st.expander(L("manual_override")):
    if not st.session_state.doctors:
        st.warning("أضف أسماء أولًا.")
    else:
        doc_o = st.selectbox(L("select_doctor")+" (override)", st.session_state.doctors, key="ov_doctor")
        spec = st.text_area(L("manual_hint"), height=100, key="ov_spec")
        def parse_override_spec(txt:str) -> Dict[int, str]:
            mapping = {}
            if not txt.strip(): return mapping
            tokens = []
            for line in txt.splitlines():
                tokens.extend([t.strip() for t in line.split(",") if t.strip()])
            for tok in tokens:
                if ":" not in tok: continue
                d_str, rhs = [x.strip() for x in tok.split(":", 1)]
                if not d_str.isdigit(): continue
                d = int(d_str)
                if d<1 or d>days: continue
                if rhs == L("rest") or rhs == "راحة":
                    mapping[d] = "راحة"
                else:
                    if "-" not in rhs: continue
                    sh, ar = [x.strip() for x in rhs.split("-", 1)]
                    ar = normalize_area(ar)
                    mapping[d] = f"{sh} - {ar}"
            return mapping
        if st.button(L("apply_override")):
            mp = parse_override_spec(spec)
            st.session_state.overrides.setdefault(doc_o, {}).update(mp)
            st.success(f"تم تطبيق {len(mp)} عنصرًا.")

# ===== حفظ/تحميل/تفريغ =====
st.header(L("save_load"))
c1, c2, c3 = st.columns(3)
with c1:
    if st.button(L("save")):
        data = {
            "lang": st.session_state.lang,
            "doctors": st.session_state.doctors,
            "overrides": st.session_state.overrides,
            "doctor_prefs": {k: {"cap": v.get("cap"),
                                 "days_off": list(v.get("days_off", [])),
                                 "preferred": list(v.get("preferred", [])),
                                 "forbidden": list(v.get("forbidden", []))}
                             for k,v in st.session_state.doctor_prefs.items()},
            "shifts": st.session_state.shifts,
            "shift_colors": st.session_state.shift_colors,
            "areas": st.session_state.areas,
            "coverage": st.session_state.coverage,
        }
        st.download_button("Download JSON", data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
                           file_name="rota_config.json", mime="application/json")
with c2:
    uploaded = st.file_uploader(L("load"), type=["json"])
    if uploaded:
        try:
            data = json.load(uploaded)
            st.session_state.lang = data.get("lang", "ar")
            st.session_state.doctors = data.get("doctors", [])
            st.session_state.overrides = {k: {int(d): v for d,v in mp.items()} for k, mp in data.get("overrides", {}).items()}
            dp = data.get("doctor_prefs", {})
            st.session_state.doctor_prefs = {
                k: {"cap": v.get("cap"),
                    "days_off": set(v.get("days_off", [])),
                    "preferred": set(v.get("preferred", [])),
                    "forbidden": set(v.get("forbidden", []))}
                for k, v in dp.items()
            }
            st.session_state.shifts = data.get("shifts", ["صباح","مساء","ليل"])
            st.session_state.shift_colors = data.get("shift_colors", {"صباح":"#EAF3FF","مساء":"#FFF2E6","ليل":"#EEE8FF","راحة":"#F2F3F7"})
            st.session_state.areas = [normalize_area(a) for a in data.get("areas", ["فرز","تنفسية","ملاحظة","إنعاش"])]
            cov_in = data.get("coverage", {"فرز":2,"تنفسية":1,"ملاحظة":4,"إنعاش":3})
            # تطبيع "انعاش"
            if "انعاش" in cov_in and "إنعاش" not in cov_in:
                cov_in["إنعاش"] = cov_in.pop("انعاش")
            st.session_state.coverage = cov_in
            st.success("تم التحميل.")
        except Exception as e:
            st.error(f"Load error: {e}")
with c3:
    if st.button(L("clear")):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ===== خوارزميات الجدولة =====
CODE_REST = -1
CODE_FREE = -2

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
    doc_caps: Optional[List[Optional[int]]] = None
    preferred: Optional[List[set]] = None
    forbidden: Optional[List[set]] = None

def build_locks(doctors: List[str], days_cnt:int) -> np.ndarray:
    locks = np.full((len(doctors), days_cnt), CODE_FREE, dtype=np.int16)
    SHIFT_AREA = get_SHIFT_AREA()
    name_to_idx = {d:i for i,d in enumerate(doctors)}
    # days-off
    for name, prefs in st.session_state.doctor_prefs.items():
        if name not in name_to_idx: continue
        i = name_to_idx[name]
        for d in prefs.get("days_off", set()):
            if 1<=d<=days_cnt:
                locks[i, d-1] = CODE_REST
    # manual overrides
    for name, mp in st.session_state.overrides.items():
        if name not in name_to_idx: continue
        i = name_to_idx[name]
        for d, val in mp.items():
            if 1<=d<=days_cnt:
                if val == L("rest") or val == "راحة":
                    locks[i, d-1] = CODE_REST
                else:
                    try:
                        sh, ar = [x.strip() for x in val.split("-", 1)]
                        ar = normalize_area(ar)
                        code = SHIFT_AREA.index((sh, ar))
                        locks[i, d-1] = code
                    except Exception:
                        locks[i, d-1] = CODE_REST
    return locks

def ga_random(doctors:int, days:int, rest_bias:float)->np.ndarray:
    genes = np.full((doctors, days), CODE_REST, dtype=np.int16)
    mask  = (np.random.rand(doctors, days) < (1.0 - rest_bias))
    genes[mask] = np.random.randint(0, len(get_SHIFT_AREA()), size=mask.sum(), dtype=np.int16)
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
                    if locks[d, t] == CODE_FREE:
                        g[d, t] = CODE_REST
                        run = 0
            else:
                run = 0
    g = np.where(locks!=CODE_FREE, locks, g)
    return g

def ga_decode(genes:np.ndarray, days_cnt:int):
    SHIFT_AREA = get_SHIFT_AREA()
    per_doc = (genes >= 0).sum(axis=1)
    totals_shift = {(d, s):0 for d in range(days_cnt) for s in st.session_state.shifts}
    totals_area  = {(d, s, a):0 for d in range(days_cnt) for s in st.session_state.shifts for a in st.session_state.areas}
    for day in range(days_cnt):
        vals = genes[:, day]
        for v in vals[vals>=0]:
            s, a = SHIFT_AREA[int(v)]
            totals_shift[(day, s)] += 1
            totals_area[(day, s, a)] += 1
    return per_doc, totals_shift, totals_area

def ga_fitness(genes:np.ndarray, p:GAParams) -> float:
    per_doc, totals_shift, totals_area = ga_decode(genes, p.days)
    pen = 0.0
    # per-doctor caps
    if p.doc_caps:
        for i, cap in enumerate(p.doc_caps):
            limit = cap if cap is not None else p.per_doc_cap
            over = max(0, int(per_doc[i]) - int(limit))
            pen += over * p.penalty_scale
    else:
        over = np.clip(per_doc - p.per_doc_cap, 0, None).sum()
        pen += over * p.penalty_scale

    # totals & coverage
    for day in range(p.days):
        for s in st.session_state.shifts:
            t = totals_shift[(day, s)]
            if t < p.min_total: pen += (p.min_total - t) * p.penalty_scale
            if t > p.max_total: pen += (t - p.max_total) * p.penalty_scale
            for a in st.session_state.areas:
                req = p.coverage[a]
                ta = totals_area[(day, s, a)]
                if ta < req: pen += (req - ta) * p.penalty_scale

    # preferences/forbidden
    SHIFT_AREA = get_SHIFT_AREA()
    for i in range(p.doctors):
        for day in range(p.days):
            v = int(genes[i, day])
            if v >= 0:
                s, a = SHIFT_AREA[v]
                if p.forbidden and p.forbidden[i] and s in p.forbidden[i]:
                    pen += p.penalty_scale * 6
                if p.preferred and p.preferred[i] and s not in p.preferred[i]:
                    pen += p.penalty_scale * 0.5

    # balance
    var = float(np.var(per_doc.astype(np.float32)))
    pen += var * p.balance_weight

    # max-consecutive penalty
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
    rnd  = np.random.randint(-1, len(get_SHIFT_AREA()), size=out.shape, dtype=np.int16)
    out[mask] = rnd[mask]
    out = np.where(locks!=CODE_FREE, locks, out)
    out = enforce_max_consec(out, max_consecutive, locks)
    return out

def ga_evolve(p:GAParams, locks:np.ndarray, progress=None)->np.ndarray:
    pop = [ga_random(p.doctors, p.days, p.rest_bias) for _ in range(p.population_size)]
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
            child = np.where(locks!=CODE_FREE, locks, child)
            child = ga_mutate(child, p.mutation_rate, locks, p.max_consecutive)
            kids.append(child)
        pop = kids
        pop = [enforce_max_consec(np.where(locks!=CODE_FREE, locks, ind), p.max_consecutive, locks) for ind in pop]
        fits = np.array([ga_fitness(x, p) for x in pop], dtype=np.float64)
        if progress:
            progress.progress((g+1)/p.generations, text=f"{g+1}/{p.generations}")
    return pop[int(np.argmax(fits))]

def cpsat_schedule(doctors:List[str], days_cnt:int, cap:int, min_total:int, max_total:int,
                   cov:Dict[str,int], time_limit:int, balance:bool,
                   max_consecutive:int, locks:np.ndarray, per_doc_caps:List[Optional[int]]):
    SHIFT_AREA = get_SHIFT_AREA()
    model = cp_model.CpModel()
    D = len(doctors)
    x = {}
    for d in range(D):
        for day in range(days_cnt):
            for s in st.session_state.shifts:
                for a in st.session_state.areas:
                    x[(d, day, s, a)] = model.NewBoolVar(f"x_{d}_{day}_{s}_{a}")

    # تغطيات وإجماليات
    for day in range(days_cnt):
        for s in st.session_state.shifts:
            for a in st.session_state.areas:
                model.Add(sum(x[(d, day, s, a)] for d in range(D)) >= int(cov[a]))
            tot = [x[(d, day, s, a)] for d in range(D) for a in st.session_state.areas]
            model.Add(sum(tot) >= int(min_total))
            model.Add(sum(tot) <= int(max_total))

    # وردية واحدة/يوم/طبيب
    for day in range(days_cnt):
        for d in range(D):
            model.Add(sum(x[(d, day, s, a)] for s in st.session_state.shifts for a in st.session_state.areas) <= 1)

    # أقفال: أيام راحة / overrides
    for d in range(D):
        for day in range(days_cnt):
            lock = int(locks[d, day])
            if lock == CODE_FREE:
                continue
            if lock == CODE_REST:
                model.Add(sum(x[(d, day, s, a)] for s in st.session_state.shifts for a in st.session_state.areas) == 0)
            else:
                s, a = SHIFT_AREA[lock]
                model.Add(x[(d, day, s, a)] == 1)
                for ss in st.session_state.shifts:
                    for aa in st.session_state.areas:
                        if (ss, aa) != (s, a):
                            model.Add(x[(d, day, ss, aa)] == 0)

    # سقف الطبيب (فردي/عام)
    totals = {}
    for d in range(D):
        tot = sum(x[(d, day, s, a)] for day in range(days_cnt) for s in st.session_state.shifts for a in st.session_state.areas)
        cap_d = per_doc_caps[d] if per_doc_caps[d] is not None else cap
        model.Add(tot <= int(cap_d))
        totals[d] = tot

    # قيد السلاسل المتتالية
    y = {}
    for d in range(D):
        for day in range(days_cnt):
            y[(d, day)] = model.NewIntVar(0, 1, f"y_{d}_{day}")
            model.Add(y[(d, day)] == sum(x[(d, day, s, a)] for s in st.session_state.shifts for a in st.session_state.areas))
    win = max_consecutive + 1
    for d in range(D):
        for start in range(0, days_cnt - win + 1):
            model.Add(sum(y[(d, start+k)] for k in range(win)) <= max_consecutive)

    # توازن (اختياري)
    if balance:
        approx = days_cnt * len(st.session_state.shifts) * ((min_total + max_total) / 2.0)
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
            for s in st.session_state.shifts:
                for a in st.session_state.areas:
                    if solver.Value(x[(d, day, s, a)]) == 1:
                        rows.append({"الطبيب": doctors[d], "اليوم": day+1, "المناوبة": f"{s} - {a}"})
    return pd.DataFrame(rows), ("OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE")

# ===== تحويلات وعرض =====
def to_long_df_from_genes(genes:np.ndarray, days_cnt:int, doctors:List[str])->pd.DataFrame:
    SHIFT_AREA = get_SHIFT_AREA()
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
        return pd.DataFrame(index=doctors, columns=range(1, days_cnt+1)).fillna(L("rest"))
    t = df.pivot_table(index="الطبيب", columns="اليوم", values="المناوبة", aggfunc="first").fillna(L("rest"))
    return t.reindex(index=doctors, columns=range(1, days_cnt+1), fill_value=L("rest"))

def shift_css_class(shift_name:str) -> str:
    if shift_name == L("rest") or shift_name == "راحة": return "s-rest"
    try:
        idx = st.session_state.shifts.index(shift_name)
        return f"s-{idx}"
    except ValueError:
        return "s-rest"

def render_matrix_cards(rota: pd.DataFrame, year:int, month:int):
    cols = rota.columns.tolist()
    head_cells = []
    for d in cols:
        head_cells.append(
            f"<th><div>{arabic_weekday_name(year, int(month), int(d))}</div>"
            f"<div class='sub'>{int(d)}/{int(month)}</div></th>"
        )
    thead = "<thead><tr><th>"+L("doctor")+"</th>" + "".join(head_cells) + "</tr></thead>"

    body_rows = []
    for doc in rota.index:
        tds = [f"<td class='doc'>{doc}</td>"]
        for d in cols:
            val = str(rota.loc[doc, d])
            if val == L("rest") or val == "راحة":
                inner = f"<div class='cell'><div class='card s-rest'>{L('rest')}</div></div>"
            else:
                part = val.split(" - ")
                sh = part[0].strip()
                ar = part[1].strip() if len(part)>1 else ""
                cls = shift_css_class(sh)
                text = f"{sh}<span class='sub'>{ar}</span>" if ar else sh
                inner = f"<div class='cell'><div class='card {cls}'>{text}</div></div>"
            tds.append(f"<td>{inner}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"

    st.markdown(
        f"<div style='overflow:auto; max-height:75vh;'>"
        f"<table class='rota'>{thead}{tbody}</table></div>",
        unsafe_allow_html=True
    )

def export_matrix_to_excel(rota: pd.DataFrame, year:int, month:int) -> bytes:
    output = BytesIO()
    import xlsxwriter
    wb = xlsxwriter.Workbook(output, {'in_memory': True})
    ws = wb.add_worksheet('Rota')
    ws.right_to_left()
    header_fmt = wb.add_format({'bold': True, 'align':'center', 'valign':'vcenter',
                                'text_wrap': True, 'border':1, 'fg_color':'#FFFFFF',
                                'reading_order':2})
    doc_fmt = wb.add_format({'bold': True, 'align':'right', 'valign':'vcenter',
                             'fg_color':'#FFFFFF', 'border':1, 'reading_order':2})
    rest_fmt = wb.add_format({'align':'center','valign':'vcenter','text_wrap':True,'border':1,
                              'fg_color': st.session_state.shift_colors.get("راحة", "#F2F3F7"),
                              'font_color':'#6B7280','reading_order':2})
    shift_fmts = {}
    for s in st.session_state.shifts:
        shift_fmts[s] = wb.add_format({'align':'center','valign':'vcenter','text_wrap':True,'border':1,
                                       'fg_color': st.session_state.shift_colors.get(s, "#F0F0F0"),
                                       'reading_order':2})
    ws.set_row(0, 38)
    ws.set_column(0, 0, 22)
    ws.set_column(1, rota.shape[1], 14)
    ws.write(0, 0, L("doctor"), header_fmt)
    for j, day in enumerate(rota.columns, start=1):
        title = f"{arabic_weekday_name(year, int(month), int(day))}\n{int(day)}/{int(month)}"
        ws.write(0, j, title, header_fmt)
    for i, doc in enumerate(rota.index, start=1):
        ws.set_row(i, 34)
        ws.write(i, 0, doc, doc_fmt)
        for j, day in enumerate(rota.columns, start=1):
            val = str(rota.loc[doc, day])
            if val == L("rest") or val == "راحة":
                ws.write(i, j, L("rest"), rest_fmt)
            else:
                part = val.split(" - ")
                sh = part[0].strip()
                ar = part[1].strip() if len(part) > 1 else ""
                text = f"{sh}\n{ar}" if ar else sh
                fmt = shift_fmts.get(sh, rest_fmt)
                ws.write(i, j, text, fmt)
    ws.freeze_panes(1, 1)
    wb.close()
    return output.getvalue()

def export_matrix_to_pdf(rota: pd.DataFrame, year:int, month:int) -> bytes:
    if not REPORTLAB_AVAILABLE:
        return b""
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A3), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    data = []
    header = [L("doctor")] + [f"{arabic_weekday_name(year, int(month), int(d))}\n{int(d)}/{int(month)}" for d in rota.columns]
    data.append(header)
    for doc_name in rota.index:
        row = [doc_name]
        for d in rota.columns:
            val = str(rota.loc[doc_name, d])
            if val == L("rest") or val == "راحة":
                row.append(L("rest"))
            else:
                part = val.split(" - ")
                sh = part[0].strip()
                ar = part[1].strip() if len(part) > 1 else ""
                row.append(f"{sh}\n{ar}" if ar else sh)
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
    for r in range(1, len(data)):
        for c in range(1, len(header)):
            v = data[r][c]
            if v == L("rest"):
                ts.add('BACKGROUND', (c, r), (c, r), colors.HexColor(st.session_state.shift_colors.get("راحة","#F2F3F7")))
            else:
                sh = v.split("\n",1)[0]
                ts.add('BACKGROUND', (c, r), (c, r), colors.HexColor(st.session_state.shift_colors.get(sh, "#F0F0F0")))
    table.setStyle(ts)
    doc.build([table])
    return output.getvalue()

# ===== التوليد والعرض =====
doctors = st.session_state.doctors
coverage = st.session_state.coverage

k1, k2, k3 = st.columns(3)
k1.metric(L("kpi_docs"), len(doctors))
k2.metric(L("kpi_days"), days)
k3.metric(L("kpi_ortools"), L("kpi_yes") if ORTOOLS_AVAILABLE else L("kpi_no"))

result_df = None
method_used = None

if st.button(L("generate")):
    locks = build_locks(doctors, days)

    # per-doctor caps & preferences
    caps = []
    preferred = []
    forbidden = []
    for name in doctors:
        p = st.session_state.doctor_prefs.get(name, {})
        caps.append(p.get("cap", None))
        preferred.append(set(p.get("preferred", set())))
        forbidden.append(set(p.get("forbidden", set())))

    # جدوى تقريبية (للـ GA فقط)
    min_needed = days * len(st.session_state.shifts) * min_total
    max_capacity = len(doctors) * per_doc_cap
    if engine == L("ga") and min_needed > max_capacity:
        st.warning(L("warn_capacity"))
        per_doc_cap = max(per_doc_cap, int(np.ceil(min_needed / max(1, len(doctors)))))

    if engine == L("ga"):
        with st.spinner("AI scheduling..."):
            p = GAParams(days=days, doctors=len(doctors), per_doc_cap=per_doc_cap,
                         coverage=coverage, min_total=min_total, max_total=max_total,
                         generations=gens, population_size=pop, mutation_rate=mut,
                         rest_bias=rest_bias, max_consecutive=max_consecutive,
                         doc_caps=caps, preferred=preferred, forbidden=forbidden)
            prog = st.progress(0.0, text="Optimizing…")
            genes = ga_evolve(p, locks=locks, progress=prog)
            result_df = to_long_df_from_genes(genes, days, doctors)
            method_used = "GA"
            st.success(L("ga_ok"))
    else:
        if not ORTOOLS_AVAILABLE:
            st.error(L("cpsat_na"))
        else:
            with st.spinner("CP-SAT..."):
                result_df, status = cpsat_schedule(
                    doctors=doctors, days_cnt=days, cap=per_doc_cap,
                    min_total=min_total, max_total=max_total,
                    cov=coverage, time_limit=cp_limit, balance=cp_balance,
                    max_consecutive=max_consecutive, locks=locks, per_doc_caps=caps
                )
                if result_df is None or result_df.empty:
                    st.error(L("cpsat_fail"))
                else:
                    method_used = f"CP-SAT ({status})"
                    st.success(f"{L('cpsat_ok')} {method_used}")

# ===== تبويبات العرض والتصدير =====
if result_df is not None and not result_df.empty:
    rota = to_matrix(result_df, days, doctors)
    tab1, tab2, tab3 = st.tabs([L("matrix_view"), L("shift_view"), L("export")])

    with tab1:
        render_matrix_cards(rota, int(year), int(month))

    with tab2:
        day_sel = st.number_input(L("choose_day"), 1, days, 1)
        shift_sel = st.selectbox(L("choose_shift"), st.session_state.shifts)
        area_sel  = st.selectbox(L("choose_area"), st.session_state.areas)
        mask = (result_df["اليوم"] == int(day_sel)) & (result_df["المناوبة"] == f"{shift_sel} - {area_sel}")
        names = result_df.loc[mask, "الطبيب"].tolist()
        st.subheader(L("doctors_in_shift"))
        st.write(", ".join(names) if names else "—")

    with tab3:
        c1, c2 = st.columns(2)
        with c1:
            excel_bytes = export_matrix_to_excel(rota, int(year), int(month))
            st.download_button(L("excel"), data=excel_bytes,
                               file_name="rota_matrix.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)
        with c2:
            if REPORTLAB_AVAILABLE:
                pdf_bytes = export_matrix_to_pdf(rota, int(year), int(month))
                st.download_button(L("pdf"), data=pdf_bytes,
                                   file_name="rota_matrix.pdf", mime="application/pdf",
                                   use_container_width=True)
            else:
                st.info("PDF يتطلب مكتبة reportlab.")
else:
    st.info(L("info_first"))

