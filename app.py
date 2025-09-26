import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
from io import BytesIO
import calendar

# ==================================
# 1. إعدادات التطبيق والواجهة
# ==================================
st.set_page_config(layout="wide", page_title="جدول المناوبات الذكي Pro")

# --- كود التصميم المخصص (الوضع النهاري فقط) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    
    html, body, [class*="st-"] {
        font-family: 'Tajawal', sans-serif;
        color: #121212;
    }

    :root {
        --primary-color: #667eea;
        --background-color: #f0f4f8;
        --card-bg: white;
        --border-color: #e9ecef;
        --tab-selected-bg: #667eea;
        --tab-selected-color: white;
    }

    .stApp { background-color: var(--background-color); }
    h1, h2, h3 { color: var(--primary-color); }
    .stTabs [aria-selected="true"] { background-color: var(--tab-selected-bg); color: var(--tab-selected-color) !important; font-weight: bold; }

    /* Daily View Styles */
    .daily-view-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
        gap: 15px;
    }
    .day-column {
        background-color: var(--card-bg);
        border-radius: 10px;
        padding: 15px;
        border: 1px solid var(--border-color);
    }
    .day-column h4 {
        border-bottom: 2px solid var(--border-color);
        padding-bottom: 10px;
        margin-bottom: 10px;
    }
    .shift-group h5 {
        font-weight: bold;
        margin-top: 15px;
        margin-bottom: 5px;
    }
    .doctor-card {
        background-color: #f8f9fa;
        border-radius: 6px;
        padding: 8px;
        margin-bottom: 5px;
        font-size: 0.9em;
        border-left: 5px solid var(--primary-color);
    }
    
    /* Employee View Styles */
    .employee-day-card {
        border-radius: 8px;
        padding: 10px;
        margin: 4px 0;
        border: 1px solid var(--border-color);
        text-align: center;
        min-height: 80px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .employee-day-card strong { font-size: 1.1em; display: block; }
    .employee-day-card span { font-size: 0.8em; line-height: 1.2; }
    .shift-morning { background-color: #E6F3FF; color: #004085; }
    .shift-evening { background-color: #FFF2E6; color: #856404; }
    .shift-night   { background-color: #E6E6FA; color: #38006b; }
    .shift-rest    { background-color: #f8f9fa; color: #6c757d; }

</style>
""", unsafe_allow_html=True)

st.title("🗓️ جدول المناوبات الذكي Pro")
st.markdown("###




