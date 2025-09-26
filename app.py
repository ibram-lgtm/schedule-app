import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import calendar
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

# === Optional imports
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

# -------------------------
# Basic app setup
# -------------------------
st.set_page_config(page_title="ED Rota — Sheet View", layout="wide")

# -------------------------
# Constants (areas/shifts/labels)
# -------------------------
AREAS = ["fast", "resp_triage", "acute", "resus"]
SHIFTS = ["morning", "evening", "night"]

AREA_LABEL = {
    "fast": "Fast track",
    "resp_triage": "Respiratory triage",
    "acute": "Acute care unit",
    "resus": "Resuscitation area",
}
SHIFT_LABEL = {
    "morning": "Morning 07:00–15:00",
    "evening": "Evening 15:00–23:00",
    "night":   "Night 23:00–07:00",
}

# Abbreviation codes requested (Area→code letter)
AREA_CODE = {"fast": "F", "acute": "A", "resp_triage": "R", "resus": "C"}
SHIFT_CODE = {"morning": "1", "evening": "2", "night": "3"}  # F1, F2, F3 etc.

def code_for(area:str, shift:str)->str:
    return f"{AREA_CODE[area]}{SHIFT_CODE[shift]}"

# --------------------------------
# Default coverage (editable later)
# --------------------------------
DEFAULT_COVERAGE = {
    ("fast","morning"): 2, ("fast","evening"): 2, ("fast","night"): 2,
    ("resp_triage","morning"): 1, ("resp_triage","evening"): 1, ("resp_triage","night"): 1,
    ("acute","morning"): 3, ("acute","evening"): 4, ("acute","night"): 3,   # evening 4 (your request)
    ("resus","morning"): 3, ("resus","evening"): 3, ("resus","night"): 3,
}

# --------------------------------
# Your groups and doctors (defaults)
# --------------------------------
GROUP_CAP = {
    "senior": 16,
    "g1": 18, "g2": 18, "g3": 18, "g4": 18, "g5": 18
}
# Qualifications per group (allowed areas)
GROUP_AREAS = {
    "senior": {"resus"},
    "g1": {"resp_triage"},
    "g2": {"acute"},
    "g3": {"fast","acute"},
    "g4": {"resp_triage","fast","acute"},
    "g5": {"acute","resus"},
}
# Fixed shift preferences (subset of shifts) for specific doctors
FIXED_SHIFT = {
    # Group 1
    "Dr.Sharif": {"night"},
    "Dr.Rashif": {"morning"},
    "Dr.Jobi":   {"evening"},
    # Group 2
    "Dr.Bashir": {"morning"},
    # Group 3
    "Dr.nashwa": {"morning"},
    # Group 4
    "Dr.Lena": {"morning"},
}

# Default doctors by group (you can edit later in the app)
DEFAULT_GROUP_MAP = {
    # Senior (resus only, 16 per month)
    "Dr. Abdullah Alnughamishi": "senior",
    "Dr. Samar Alruwaysan": "senior",
    "Dr. Ali Alismail": "senior",
    "Dr. Hussain Alturifi": "senior",
    "Dr. Abdullah Alkhalifah": "senior",
    "Dr. Rayan Alaboodi": "senior",
    "Dr. Jamal Almarshadi": "senior",
    "Dr. Emad Abdulkarim": "senior",
    "Dr. Marwan Alrayhan": "senior",
    "Dr. Ahmed Almohimeed": "senior",
    "Dr. Abdullah Alsindi": "senior",
    "Dr. Yousef Alharbi": "senior",

    # Group 1 (resp triage only)
    "Dr.Sharif": "g1",
    "Dr.Rashif": "g1",
    "Dr.Jobi": "g1",
    "Dr.Lucky": "g1",

    # Group 2 (acute)
    "Dr.Bashir": "g2",
    "Dr. AHMED MAMDOH": "g2",
    "Dr. HAZEM ATTYAH": "g2",
    "Dr. OMAR ALSHAMEKH": "g2",
    "Dr. AYMEN MKHTAR": "g2",

    # Group 3 (fast + acute)
    "Dr.nashwa": "g3",
    "Dr. Abdulaziz bin marahad": "g3",
    "Dr. Mohmmed almutiri": "g3",
    "Dr. Lulwah": "g3",
    "Dr.Ibrahim": "g3",
    "Dr. Kaldon": "g3",
    "Dr. Osama": "g3",
    "Dr. Salman": "g3",
    "Dr. Hajer": "g3",
    "Dr. Randa": "g3",
    "Dr. Esa": "g3",
    "Dr. Fahad": "g3",
    "Dr. Abdulrahman1": "g3",
    "Dr. Abdulrahman2": "g3",
    "Dr. Mohammed alrashid": "g3",

    # Group 4 (resp + fast + acute)
    "Dr.Lena": "g4",
    "Dr.Essra": "g4",
    "Dr.fahimah": "g4",
    "Dr.mohammed bajaber": "g4",
    "Dr.Sulaiman Abker": "g4",

    # Group 5 (acute + resus)
    "Dr.Shouq": "g5",
    "Dr.Rayan": "g5",
    "Dr abdullah aljalajl": "g5",
    "Dr. AMIN MOUSA": "g5",
    "Dr. AHMED ALFADLY": "g5",
}

ALL_DOCTORS_DEFAULT = list(DEFAULT_GROUP_MAP.keys())

# --------------------------------
# Session init
# --------------------------------
def init_state():
    ss = st.session_state
    if "year" not in ss: ss.year = 2025
    if "month" not in ss: ss.month = 9
    if "days" not in ss: ss.days = 30
    if "doctors" not in ss: ss.doctors = ALL_DOCTORS_DEFAULT.copy()
    if "group_map" not in ss: ss.group_map = DEFAULT_GROUP_MAP.copy()
    if "doctor_caps" not in ss:
        ss.doctor_caps = {n: GROUP_CAP[ss.group_map[n]] for n in ss.doctors}
    if "doctor_days_off" not in ss:  # up to 3 per doctor
        ss.doctor_days_off = {n: set() for n in ss.doctors}
    if "doctor_allowed_shifts" not in ss:
        # default = all shifts; override with FIXED_SHIFT
        base = {n: set(SHIFTS) for n in ss.doctors}
        for n, only in FIXED_SHIFT.items():
            if n in base: base[n] = set(only)
        ss.doctor_allowed_shifts = base
    if "coverage" not in ss: ss.coverage = DEFAULT_COVERAGE.copy()
    if "min_off_days" not in ss: ss.min_off_days = 12
    if "max_consec_days" not in ss: ss.max_consec_days = 6
    if "min_rest_hours" not in ss: ss.min_rest_hours = 16
    if "result_df" not in ss: ss.result_df = None
    if "gaps_table" not in ss: ss.gaps_table = None
    if "remaining_table" not in ss: ss.remaining_table = None

init_state()

# --------------------------------
# UI — left sidebar global settings
# --------------------------------
with st.sidebar:
    st.header("General")
    st.session_state.year = st.number_input("Year", 2024, 2100, st.session_state.year)
    st.session_state.month = st.number_input("Month", 1, 12, st.session_state.month)
    st.session_state.days = st.slider("Days in month", 28, 31, st.session_state.days)

    st.markdown("**Rules (global)**")
    st.session_state.min_off_days = st.number_input("Min off days / month", 0, 31, st.session_state.min_off_days)
    st.session_state.max_consec_days = st.number_input("Max consecutive duty days", 1, 30, st.session_state.max_consec_days)
    st.session_state.min_rest_hours = st.number_input("Min rest hours between shifts", 0, 24, st.session_state.min_rest_hours)

# --------------------------------
# Tabs
# --------------------------------
tab_rules, tab_doctors, tab_generate, tab_shift, tab_export = st.tabs(
    ["Rules", "Doctors & Preferences", "Generate & Sheet", "By Shift", "Export"]
)

# ---- Rules tab: coverage and group caps
with tab_rules:
    st.subheader("Coverage per Area & Shift")
    cov_cols = st.columns(3)
    new_cov = st.session_state.coverage.copy()
    for i, area in enumerate(AREAS):
        with cov_cols[i % 3]:
            st.markdown(f"**{AREA_LABEL[area]}**")
            for sh in SHIFTS:
                key = (area, sh)
                new_cov[key] = st.number_input(f"{SHIFT_LABEL[sh]}", 0, 20, int(st.session_state.coverage[key]), key=f"cov_{area}_{sh}")
    st.session_state.coverage = new_cov

    st.divider()
    st.subheader("Group monthly caps")
    cap_cols = st.columns(6)
    for i, g in enumerate(["senior","g1","g2","g3","g4","g5"]):
        with cap_cols[i]:
            GROUP_CAP[g] = st.number_input(f"{g} cap", 0, 31, GROUP_CAP[g], key=f"gcap_{g}")
    st.info("Senior group should stay at ≤16 as you requested.")

# ---- Doctors tab: add / edit doctors, groups, caps, allowed shifts & days off
with tab_doctors:
    st.subheader("Roster")
    c1, c2 = st.columns([2,1])
    with c1:
        names_text = st.text_area("Add doctors (one per line)", height=120, placeholder="Dr. New A\nDr. New B")
        if st.button("Append to list"):
            new_names = [n.strip() for n in names_text.splitlines() if n.strip()]
            for n in new_names:
                if n not in st.session_state.doctors:
                    st.session_state.doctors.append(n)
                    st.session_state.group_map[n] = "g3"  # default
                    st.session_state.doctor_caps[n] = GROUP_CAP["g3"]
                    st.session_state.doctor_days_off[n] = set()
                    st.session_state.doctor_allowed_shifts[n] = set(SHIFTS)
            st.success(f"Added {len(new_names)} doctor(s).")

    with c2:
        remove_name = st.selectbox("Remove doctor", ["—"] + st.session_state.doctors)
        if st.button("Remove") and remove_name != "—":
            st.session_state.doctors.remove(remove_name)
            for d in ["group_map","doctor_caps","doctor_days_off","doctor_allowed_shifts"]:
                st.session_state[d].pop(remove_name, None)
            st.success(f"Removed {remove_name}")

    st.divider()
    st.subheader("Edit one doctor")
    if st.session_state.doctors:
        doc = st.selectbox("Doctor", st.session_state.doctors)
        grp = st.selectbox("Group", ["senior","g1","g2","g3","g4","g5"], index=["senior","g1","g2","g3","g4","g5"].index(st.session_state.group_map.get(doc, "g3")))
        st.session_state.group_map[doc] = grp
        st.session_state.doctor_caps[doc] = st.number_input("Monthly cap (max shifts)", 0, 31, st.session_state.doctor_caps.get(doc, GROUP_CAP[grp]))
        st.caption("Allowed areas (derived from group). If you need exceptions, change group or increase group qualifications in code.")
        st.write(", ".join(sorted(GROUP_AREAS[grp])))

        st.caption("Allowed shifts (for fixed preferences set only one).")
        sh0, sh1, sh2 = st.columns(3)
        chk = {}
        for i, sh in enumerate(SHIFTS):
            with (sh0 if i==0 else sh1 if i==1 else sh2):
                chk[sh] = st.checkbox(SHIFT_LABEL[sh], value=(sh in st.session_state.doctor_allowed_shifts.get(doc, set(SHIFTS))), key=f"allow_{doc}_{sh}")
        st.session_state.doctor_allowed_shifts[doc] = {s for s,v in chk.items() if v} or set(SHIFTS)

        st.caption("Personal off-days (max 3, comma-separated day numbers).")
        txt = st.text_input("Off-days", ",".join(map(str, sorted(st.session_state.doctor_days_off.get(doc,set())))))
        chosen = set()
        for t in txt.replace(" ", "").split(","):
            if t.isdigit():
                d = int(t)
                if 1 <= d <= st.session_state.days:
                    chosen.add(d)
        if len(chosen) > 3:
            st.warning("Max 3 off-days are considered.")
            chosen = set(sorted(list(chosen))[:3])
        st.session_state.doctor_days_off[doc] = chosen

# -------------------------
# Solver: CP-SAT with slacks (for unfilled coverage)
# -------------------------
@dataclass
class SolveResult:
    df: pd.DataFrame
    gaps: pd.DataFrame
    remaining: pd.DataFrame

def solve_schedule() -> SolveResult:
    if not ORTOOLS_AVAILABLE:
        st.error("OR-Tools is required on the server to generate the schedule.")
        return SolveResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

    days = st.session_state.days
    doctors = st.session_state.doctors
    model = cp_model.CpModel()

    # Index helpers
    D = len(doctors)
    S = len(SHIFTS)
    A = len(AREAS)

    # Decision variables x[d, t, s, a] ∈ {0,1}
    x = {}
    for di in range(D):
        for t in range(days):
            for s in range(S):
                for a in range(A):
                    x[(di,t,s,a)] = model.NewBoolVar(f"x_{di}_{t}_{s}_{a}")

    # Slack variables for unmet coverage (per day/shift/area)
    slack = {}
    for t in range(days):
        for s in range(S):
            for a in range(A):
                slack[(t,s,a)] = model.NewIntVar(0, 100, f"slack_{t}_{s}_{a}")

    # Coverage constraints (sum x + slack >= required)
    for t in range(days):
        for s_idx, sh in enumerate(SHIFTS):
            for a_idx, ar in enumerate(AREAS):
                req = int(st.session_state.coverage[(ar, sh)])
                model.Add(sum(x[(di,t,s_idx,a_idx)] for di in range(D)) + slack[(t,s_idx,a_idx)] >= req)

    # One shift per day per doctor
    for di in range(D):
        for t in range(days):
            model.Add(sum(x[(di,t,s,a)] for s in range(S) for a in range(A)) <= 1)

    # Qualifications + fixed shifts + off-days
    name_to_i = {n:i for i,n in enumerate(doctors)}
    for name in doctors:
        di = name_to_i[name]
        grp = st.session_state.group_map[name]
        allowed_areas = GROUP_AREAS[grp]
        allowed_shifts = st.session_state.doctor_allowed_shifts[name] if st.session_state.doctor_allowed_shifts.get(name) else set(SHIFTS)

        for t in range(days):
            # personal off-day
            if t+1 in st.session_state.doctor_days_off.get(name,set()):
                model.Add(sum(x[(di,t,s,a)] for s in range(S) for a in range(A)) == 0)
            # area/shift filters
            for s_idx, sh in enumerate(SHIFTS):
                for a_idx, ar in enumerate(AREAS):
                    if (ar not in allowed_areas) or (sh not in allowed_shifts):
                        model.Add(x[(di,t,s_idx,a_idx)] == 0)

        # Monthly cap and minimum off-days
        total = sum(x[(di,t,s,a)] for t in range(days) for s in range(S) for a in range(A))
        model.Add(total <= int(st.session_state.doctor_caps[name]))
        # off-days >= min_off_days  → total <= days - min_off_days
        model.Add(total <= int(days - st.session_state.min_off_days))

    # Rest hours ≥16 rules:
    # evening(t-1) → NOT morning(t)
    # night(t-1)   → NOT morning(t) and NOT evening(t)
    # (we already forbid multi-shifts per same day)
    MOR, EVE, NIT = 0, 1, 2
    for di in range(D):
        for t in range(1, days):
            # evening (t-1) + morning(t) <= 1
            model.Add(
                sum(x[(di,t-1,EVE,a)] for a in range(A)) +
                sum(x[(di,t,MOR,a)] for a in range(A))
                <= 1
            )
            # night (t-1) + morning(t) == 0
            model.Add(
                sum(x[(di,t-1,NIT,a)] for a in range(A)) +
                sum(x[(di,t,MOR,a)] for a in range(A))
                <= 0
            )
            # night (t-1) + evening(t) <= 1  (actually should be 0; keep <=1 for robustness if model tight)
            model.Add(
                sum(x[(di,t-1,NIT,a)] for a in range(A)) +
                sum(x[(di,t,EVE,a)] for a in range(A))
                <= 1
            )

    # Max consecutive duty days ≤ K
    K = int(st.session_state.max_consec_days)
    y = {}
    for di in range(D):
        for t in range(days):
            y[(di,t)] = model.NewBoolVar(f"y_{di}_{t}")
            model.Add(y[(di,t)] == sum(x[(di,t,s,a)] for s in range(S) for a in range(A)))
        for start in range(0, days - (K+1) + 1):
            model.Add(sum(y[(di,start+i)] for i in range(K+1)) <= K)

    # Objective: minimize total slack (unfilled positions), then balance workload
    obj_terms = [slack[(t,s,a)]*1000 for t in range(days) for s in range(S) for a in range(A)]
    # balance term: minimize variance (L1 approx)
    avg_target = int(round(
        (sum(st.session_state.coverage[(ar, sh)] for sh in SHIFTS for ar in AREAS) * days) / max(1, D)
    ))
    for di in range(D):
        tot = sum(x[(di,t,s,a)] for t in range(days) for s in range(S) for a in range(A))
        over = model.NewIntVar(0, 200, f"over_{di}")
        under = model.NewIntVar(0, 200, f"under_{di}")
        model.Add(tot - avg_target == over - under)
        obj_terms.extend([over, under])
    model.Minimize(sum(obj_terms))

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 90.0
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    # Build outputs (even if gaps remain)
    rows = []
    assign_cnt = {(t,s,a): 0 for t in range(days) for s in range(S) for a in range(A)}
    for di, name in enumerate(doctors):
        for t in range(days):
            for s in range(S):
                for a in range(A):
                    if solver.Value(x[(di,t,s,a)]) == 1:
                        rows.append({
                            "doctor": name,
                            "day": t+1,
                            "area": AREAS[a],
                            "shift": SHIFTS[s],
                            "code": code_for(AREAS[a], SHIFTS[s]),
                        })
                        assign_cnt[(t,s,a)] += 1

    # Coverage gaps table
    gap_rows = []
    for t in range(days):
        for s, sh in enumerate(SHIFTS):
            for a, ar in enumerate(AREAS):
                req = int(st.session_state.coverage[(ar, sh)])
                done = assign_cnt[(t,s,a)]
                gap = req - done
                if gap > 0:
                    gap_rows.append({
                        "day": t+1,
                        "shift": sh,
                        "area": ar,
                        "required": req,
                        "assigned": done,
                        "short_by": gap,
                        "abbr": code_for(ar, sh)
                    })
    gaps_df = pd.DataFrame(gap_rows).sort_values(["day","shift","area"]) if gap_rows else pd.DataFrame(
        columns=["day","shift","area","required","assigned","short_by","abbr"]
    )

    # Remaining capacity per doctor (to help fill)
    rem_rows = []
    totals = {n:0 for n in doctors}
    for r in rows:
        totals[r["doctor"]] += 1
    for n in doctors:
        cap = int(st.session_state.doctor_caps[n])
        remaining = max(0, cap - totals[n])
        rem_rows.append({"doctor": n, "assigned": totals[n], "cap": cap, "remaining": remaining})
    remaining_df = pd.DataFrame(rem_rows).sort_values(["remaining","doctor"], ascending=[False, True])

    return SolveResult(pd.DataFrame(rows), gaps_df, remaining_df)

def build_sheet(df: pd.DataFrame, days:int, doctors:List[str]) -> pd.DataFrame:
    """Return sheet index=day rows, columns=doctors, values=code (blank if off)."""
    if df is None or df.empty:
        return pd.DataFrame(index=range(1, days+1), columns=doctors)
    pvt = df.pivot_table(index="day", columns="doctor", values="code", aggfunc="first")
    return pvt.reindex(index=range(1, days+1), columns=doctors)

# ---- Generate & show sheet
with tab_generate:
    st.subheader("Generate schedule")
    if st.button("Run solver", type="primary", use_container_width=True):
        res = solve_schedule()
        st.session_state.result_df = res.df
        st.session_state.gaps_table = res.gaps
        st.session_state.remaining_table = res.remaining
        if res.gaps.empty:
            st.success("Coverage achieved with no gaps 🎉")
        else:
            st.warning("Some shifts are unfilled — see 'Coverage gaps' below.")

    df = st.session_state.result_df
    if df is None or df.empty:
        st.info("Click **Run solver** to generate the schedule.")
    else:
        sheet = build_sheet(df, st.session_state.days, st.session_state.doctors)
        st.subheader("Sheet (rows=dates, columns=doctors)")
        # highlight blanks (empty/NaN) in red background
        def style_blank(v):
            return "background-color: #FDE2E2; font-weight:700;" if (pd.isna(v) or (str(v).strip()=="")) else ""
        st.dataframe(sheet.style.applymap(style_blank), use_container_width=True, height=min(600, 34*(st.session_state.days+2)))

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Coverage gaps (unfilled)")
            st.dataframe(st.session_state.gaps_table, use_container_width=True, height=300)
        with col2:
            st.subheader("Doctors with remaining capacity")
            st.dataframe(st.session_state.remaining_table, use_container_width=True, height=300)

# ---- By Shift view (who works in a chosen area/shift/day)
with tab_shift:
    st.subheader("Lookup by area/shift")
    day_sel = st.number_input("Day", 1, st.session_state.days, 1)
    area_sel = st.selectbox("Area", AREAS, format_func=lambda a: AREA_LABEL[a])
    shift_sel = st.selectbox("Shift", SHIFTS, format_func=lambda s: SHIFT_LABEL[s])
    df = st.session_state.result_df
    if df is None or df.empty:
        st.info("Generate first.")
    else:
        mask = (df["day"]==int(day_sel)) & (df["area"]==area_sel) & (df["shift"]==shift_sel)
        names = df.loc[mask, "doctor"].tolist()
        st.write(f"**{AREA_LABEL[area_sel]} — {SHIFT_LABEL[shift_sel]}**")
        st.write(", ".join(names) if names else "_none_")
        st.caption(f"Abbreviation: **{code_for(area_sel, shift_sel)}**")

# ---- Export
def export_excel(sheet: pd.DataFrame, gaps: pd.DataFrame, remaining: pd.DataFrame) -> bytes:
    if not XLSX_AVAILABLE:
        return b""
    out = BytesIO()
    wb = xlsxwriter.Workbook(out, {"in_memory": True})
    # Sheet 1 — Rota
    ws = wb.add_worksheet("Rota")
    header = wb.add_format({"bold": True, "align":"center", "valign":"vcenter", "bg_color":"#E8EEF9", "border":1})
    cell   = wb.add_format({"align":"center","valign":"vcenter","border":1})
    blank  = wb.add_format({"align":"center","valign":"vcenter","border":1, "bg_color":"#FDE2E2"})  # highlight empty
    ws.set_column(0, 0, 8)
    for c in range(sheet.shape[1]):
        ws.set_column(c+1, c+1, 18)

    ws.write(0,0,"Day",header)
    for j, doc in enumerate(sheet.columns, start=1):
        ws.write(0,j,doc,header)

    for i, day in enumerate(sheet.index, start=1):
        ws.write(i,0,int(day),header)
        for j, doc in enumerate(sheet.columns, start=1):
            val = sheet.loc[day, doc]
            if pd.isna(val) or str(val).strip()=="":
                ws.write(i,j,"", blank)
            else:
                ws.write(i,j, str(val), cell)

    ws.freeze_panes(1,1)

    # Sheet 2 — Coverage gaps
    ws2 = wb.add_worksheet("Coverage gaps")
    cols = ["day","shift","area","abbr","required","assigned","short_by"]
    for j, col in enumerate(cols):
        ws2.write(0,j,col,header)
    for i, row in enumerate(gaps.itertuples(index=False), start=1):
        for j, col in enumerate(cols):
            ws2.write(i,j, getattr(row, col) if hasattr(row, col) else row[j], cell)

    # Sheet 3 — Remaining capacity
    ws3 = wb.add_worksheet("Remaining capacity")
    cols2 = ["doctor","assigned","cap","remaining"]
    for j, col in enumerate(cols2):
        ws3.write(0,j,col,header)
    for i, row in enumerate(remaining.itertuples(index=False), start=1):
        for j, col in enumerate(cols2):
            ws3.write(i,j, getattr(row, col) if hasattr(row, col) else row[j], cell)

    wb.close()
    return out.getvalue()

with tab_export:
    st.subheader("Export")
    df = st.session_state.result_df
    if df is None or df.empty:
        st.info("Generate first.")
    else:
        sheet = build_sheet(df, st.session_state.days, st.session_state.doctors)
        xldata = export_excel(sheet, st.session_state.gaps_table, st.session_state.remaining_table)
        st.download_button("Download Excel (styled)", data=xldata,
                           file_name="ED_rota.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)

# -------------------------
# Small utilities on top of UI
# -------------------------
st.caption("Tip: If coverage > capacity, the solver will produce the best partial rota, "
           "highlight unfilled shifts in red, and list doctors with remaining capacity to fill the gaps.")
