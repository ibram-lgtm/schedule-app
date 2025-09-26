import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
from io import BytesIO
import calendar

# ==================================
# 1. إعدادات التطبيق والواجهة الاحترافية
# ==================================
st.set_page_config(layout="wide", page_title="جدول المناوبات الذكي Pro")

# --- ستايل CSS مخصص واحترافي ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    
    html, body, [class*="st-"] {
        font-family: 'Tajawal', sans-serif;
    }

    /* === Global Color Variables === */
    :root {
        --primary-color: #667eea;
        --secondary-color: #764ba2;
        --background-color: #f0f4f8;
        --text-color: #262730;
        --card-bg: white;
        --border-color: #e9ecef;
        --tab-bg: #f0f4f8;
        --tab-selected-bg: #667eea;
        --tab-selected-color: white;
    }

    /* === Dark Mode Overrides === */
    body[data-theme="dark"] {
        --primary-color: #8A98F7;
        --secondary-color: #9B70E0;
        --background-color: #0e1117;
        --text-color: #fafafa;
        --card-bg: #1c1e24;
        --border-color: #31333F;
        --tab-bg: #262730;
        --tab-selected-bg: #8A98F7;
        --tab-selected-color: #0e1117;
    }
    
    .stApp { background-color: var(--background-color); }
    h1, h2, h3 { color: var(--primary-color); }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab"] { color: var(--text-color) !important; background-color: var(--tab-bg); }
    .stTabs [aria-selected="true"] { background-color: var(--tab-selected-bg); color: var(--tab-selected-color) !important; font-weight: bold; }
    
    /* Card View Styles */
    .day-card {
        border-radius: 8px;
        padding: 10px;
        margin: 4px 0;
        border: 1px solid var(--border-color);
        text-align: center;
        transition: all 0.2s ease-in-out;
        min-height: 80px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .day-card strong { font-size:



