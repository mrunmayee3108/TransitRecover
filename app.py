# pyrefly: ignore [missing-import]
from prometheus_client import start_http_server, Counter, Gauge, REGISTRY
import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
import re
import os
import base64

# ==============================================================================
# PROMETHEUS METRICS EXPORTER SETUP (Port 8000)
# ==============================================================================
try:
    start_http_server(8000, addr='0.0.0.0')
except OSError:
    pass

def get_or_create_metric(collector_cls, name, documentation):
    if name in REGISTRY._names_to_collectors:
        return REGISTRY._names_to_collectors[name]
    return collector_cls(name, documentation)

LOST_ITEMS_COUNTER = get_or_create_metric(Counter, 'transit_lost_items_total', 'Total lost items reported')
FOUND_ITEMS_COUNTER = get_or_create_metric(Counter, 'transit_found_items_total', 'Total found items reported')
LOST_GAUGE = get_or_create_metric(Gauge, 'transit_current_lost_items', 'Current total lost items in database')
FOUND_GAUGE = get_or_create_metric(Gauge, 'transit_current_found_items', 'Current total found items in database')

# ==============================================================================
# DATABASE CONFIGURATION & OPERATIONS
# ==============================================================================
DB_PATH = "transit_recover.db"

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Lost_Items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT NOT NULL,
            date TEXT NOT NULL,
            route TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Found_Items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT NOT NULL,
            date TEXT NOT NULL,
            route TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_lost_item(item: str, item_date: str, route: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Lost_Items (item, date, route) VALUES (?, ?, ?)",
        (item.strip(), item_date, route.strip())
    )
    conn.commit()
    conn.close()
    LOST_ITEMS_COUNTER.inc()

def add_found_item(item: str, item_date: str, route: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Found_Items (item, date, route) VALUES (?, ?, ?)",
        (item.strip(), item_date, route.strip())
    )
    conn.commit()
    conn.close()
    FOUND_ITEMS_COUNTER.inc()

def fetch_items(table_name: str) -> pd.DataFrame:
    conn = get_connection()
    query = f"SELECT id, item, date, route FROM {table_name} ORDER BY id DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# Initialize DB
init_db()

# Synchronize Prometheus Gauges
try:
    lost_df_init = fetch_items("Lost_Items")
    found_df_init = fetch_items("Found_Items")
    LOST_GAUGE.set(len(lost_df_init))
    FOUND_GAUGE.set(len(found_df_init))
except Exception:
    pass

# ==============================================================================
# HELPER: SMART MATCHING LOGIC
# ==============================================================================
def extract_keywords(text: str) -> set:
    words = re.findall(r'[a-zA-Z0-9]+', text.lower())
    stop_words = {'the', 'a', 'an', 'and', 'or', 'in', 'on', 'at', 'with', 'of', 'for', 'by', 'my', 'is', 'it'}
    return {w for w in words if len(w) > 2 and w not in stop_words}

def find_matches_for_lost(lost_name: str, lost_route: str, found_df: pd.DataFrame):
    """Finds matching found items for a given lost item description and route."""
    if found_df.empty:
        return []
    
    lost_keywords = extract_keywords(lost_name)
    results = []
    
    for _, found_row in found_df.iterrows():
        found_keywords = extract_keywords(found_row['item'])
        common = lost_keywords.intersection(found_keywords)
        same_route = lost_route.strip().lower() == found_row['route'].strip().lower()
        
        # Consider a match if keywords overlap or substring match
        is_sub = (lost_name.strip().lower() in found_row['item'].lower()) or (found_row['item'].lower() in lost_name.strip().lower())
        
        if len(common) > 0 or is_sub:
            match_type = "Exact Match" if (len(common) >= 2 and same_route) else ("Route & Item Match" if same_route else "Item Match")
            results.append({
                "found_id": found_row['id'],
                "found_item": found_row['item'],
                "found_route": found_row['route'],
                "found_date": found_row['date'],
                "match_type": match_type,
                "keywords": ", ".join(common) if common else "Name match"
            })
    return results

# Helper to load hero illustration
def get_hero_illustration_base64():
    candidates = [
        "hero_illustration.jpg",
        "/app/hero_illustration.jpg",
        os.path.join(os.path.dirname(__file__), "hero_illustration.jpg")
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
            except Exception:
                pass
    return ""

# ==============================================================================
# STREAMLIT PAGE CONFIG & EDITORIAL DESIGN SYSTEM
# ==============================================================================
st.set_page_config(
    page_title="TransitRecover — Lost & Found Service",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Design System CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Playfair+Display:ital,wght@0,600;0,700;0,800;1,600&display=swap');

    /* Hide Streamlit Header, Sidebar and Footer Chrome completely */
    [data-testid="stSidebar"],
    [data-testid="collapsedControl"],
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    header[data-testid="stHeader"] {
        display: none !important;
    }
    #MainMenu, footer {
        visibility: hidden !important;
    }
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        max-width: 1200px !important;
    }

    :root {
        color-scheme: light !important;
        --text-color: #111827 !important;
        --background-color: #FAF9F6 !important;
        --secondary-background-color: #FFFFFF !important;
    }

    /* Global Typography & Palette */
    html, body, [data-testid="stAppViewContainer"], .stApp {
        color-scheme: light !important;
        background-color: #FAF9F6 !important;
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        color: #111827 !important;
    }

    /* Top Navigation Bar */
    .nav-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.75rem 0 1.25rem 0;
        border-bottom: 1px solid #E5E7EB;
        margin-bottom: 2rem;
    }
    .nav-wordmark {
        font-family: 'Playfair Display', 'DM Serif Display', Georgia, serif;
        font-size: 1.65rem;
        font-weight: 700;
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
        letter-spacing: -0.02em;
        text-decoration: none;
        display: flex;
        align-items: baseline;
        gap: 0.35rem;
    }
    .nav-tagline {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #6B7280 !important;
        -webkit-text-fill-color: #6B7280 !important;
    }

    /* Minimalist Top Radio Navigation - Always Visible & High Contrast across all browsers including Edge */
    div[data-testid="stRadio"] {
        margin: 0 !important;
    }
    div[data-testid="stRadio"] > label {
        display: none !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 1.5rem !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0.2rem 0 !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] label {
        margin: 0 !important;
        padding: 0.45rem 0.25rem !important;
        border-radius: 0 !important;
        cursor: pointer !important;
        transition: color 0.15s ease, border-color 0.15s ease !important;
        border: none !important;
        border-bottom: 2px solid transparent !important;
        background: transparent !important;
    }
    /* Guarantee dark high-contrast text on all radio labels and descendants */
    div[data-testid="stRadio"],
    div[data-testid="stRadio"] *,
    div[data-testid="stRadio"] label,
    div[data-testid="stRadio"] label *,
    div[data-testid="stRadio"] p,
    div[data-testid="stRadio"] span,
    div[data-testid="stRadio"] div {
        color: #1F2937 !important;
        -webkit-text-fill-color: #1F2937 !important;
        font-weight: 600 !important;
        font-size: 0.98rem !important;
        opacity: 1 !important;
        visibility: visible !important;
    }
    div[data-testid="stRadio"] label:hover,
    div[data-testid="stRadio"] label:hover *,
    div[data-testid="stRadio"] label:hover p {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }
    div[data-testid="stRadio"] label > div:first-child {
        display: none !important;
    }
    div[data-testid="stRadio"] label[data-checked="true"],
    div[data-testid="stRadio"] label:has(input:checked) {
        background: transparent !important;
        border-bottom: 2.5px solid #111827 !important;
    }
    div[data-testid="stRadio"] label[data-checked="true"] *,
    div[data-testid="stRadio"] label:has(input:checked) *,
    div[data-testid="stRadio"] label[data-checked="true"] p,
    div[data-testid="stRadio"] label:has(input:checked) p {
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
        font-weight: 800 !important;
    }

    /* Hero Section (Soft Aqua Banner enclosing text, buttons, and illustration) */
    .hero-box {
        background-color: #D4F4F1 !important;
        border-radius: 20px !important;
        padding: 3.5rem 3.5rem !important;
        margin-bottom: 3.5rem !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.02) !important;
    }
    .hero-eyebrow {
        font-size: 0.82rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: #1A535C !important;
        -webkit-text-fill-color: #1A535C !important;
        margin-bottom: 1.1rem;
    }
    .hero-headline {
        font-family: 'Playfair Display', 'DM Serif Display', Georgia, serif;
        font-size: 3.4rem;
        font-weight: 700;
        line-height: 1.12;
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
        margin: 0 0 1.25rem 0;
        letter-spacing: -0.025em;
    }
    .hero-subtext {
        font-size: 1.12rem;
        color: #374151 !important;
        -webkit-text-fill-color: #374151 !important;
        line-height: 1.6;
        margin: 0 0 1.5rem 0;
        max-width: 520px;
    }
    .hero-illustration-frame {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0.5rem;
    }
    .hero-illustration-img {
        width: 100%;
        max-width: 480px;
        height: auto;
        border-radius: 14px;
        object-fit: cover;
        box-shadow: 0 8px 30px rgba(26, 83, 92, 0.08);
    }

    /* Dedicated Hero Action Buttons - Maximum Legibility & Placement */
    .hero-btn-primary {
        background-color: #0F172A !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 0.98rem !important;
        padding: 0.8rem 1.6rem !important;
        border-radius: 8px !important;
        text-decoration: none !important;
        display: inline-block !important;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.15) !important;
        border: 1.5px solid #0F172A !important;
        transition: all 0.15s ease !important;
        cursor: pointer !important;
    }
    .hero-btn-primary:hover {
        background-color: #1E293B !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        transform: translateY(-1px) !important;
    }

    .hero-btn-secondary {
        background-color: transparent !important;
        color: #0F172A !important;
        -webkit-text-fill-color: #0F172A !important;
        border: 2px solid #0F172A !important;
        font-weight: 700 !important;
        font-size: 0.98rem !important;
        padding: 0.75rem 1.5rem !important;
        border-radius: 8px !important;
        text-decoration: none !important;
        display: inline-block !important;
        transition: all 0.15s ease !important;
        cursor: pointer !important;
    }
    .hero-btn-secondary:hover {
        background-color: rgba(15, 23, 42, 0.08) !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }

    .nav-cta-link {
        background-color: #0F172A !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 0.92rem !important;
        padding: 0.65rem 1.35rem !important;
        border-radius: 8px !important;
        text-decoration: none !important;
        display: inline-block !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
        transition: background 0.15s ease !important;
        cursor: pointer !important;
    }
    .nav-cta-link:hover {
        background-color: #1E293B !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    .service-btn {
        background-color: #0F172A !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 0.92rem !important;
        padding: 0.65rem 1.25rem !important;
        border-radius: 8px !important;
        text-decoration: none !important;
        display: inline-block !important;
        transition: background 0.15s ease !important;
        cursor: pointer !important;
    }
    .service-btn:hover {
        background-color: #1E293B !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    /* All Streamlit Buttons - Visible White Text & Dark Background */
    div[data-testid="stButton"] > button,
    div[data-testid="stButton"] button,
    button[data-testid*="stBaseButton"],
    div[data-testid="stFormSubmitButton"] > button,
    button {
        background-color: #111827 !important;
        color: #FFFFFF !important;
        border: 1.5px solid #111827 !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        padding: 0.65rem 1.4rem !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
    }

    div[data-testid="stButton"] > button p,
    div[data-testid="stButton"] > button span,
    div[data-testid="stButton"] > button div,
    div[data-testid="stButton"] button p,
    div[data-testid="stButton"] button span,
    div[data-testid="stButton"] button div,
    button[data-testid*="stBaseButton"] p,
    button[data-testid*="stBaseButton"] span,
    button[data-testid*="stBaseButton"] div,
    div[data-testid="stFormSubmitButton"] button p,
    div[data-testid="stFormSubmitButton"] button span,
    button p,
    button span {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    div[data-testid="stButton"] > button:hover,
    div[data-testid="stButton"] button:hover,
    button[data-testid*="stBaseButton"]:hover,
    div[data-testid="stFormSubmitButton"] > button:hover,
    button:hover {
        background-color: #1F2937 !important;
        border-color: #1F2937 !important;
        color: #FFFFFF !important;
    }

    div[data-testid="stButton"] > button:hover p,
    div[data-testid="stButton"] > button:hover span,
    div[data-testid="stButton"] button:hover p,
    div[data-testid="stButton"] button:hover span,
    button[data-testid*="stBaseButton"]:hover p,
    button[data-testid*="stBaseButton"]:hover span,
    div[data-testid="stFormSubmitButton"] button:hover p,
    div[data-testid="stFormSubmitButton"] button:hover span,
    button:hover p,
    button:hover span {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    div[data-testid="stButton"] > button:focus,
    div[data-testid="stButton"] button:focus,
    button[data-testid*="stBaseButton"]:focus,
    div[data-testid="stFormSubmitButton"] > button:focus,
    button:focus {
        color: #FFFFFF !important;
        box-shadow: 0 0 0 2px #FFFFFF, 0 0 0 4px #111827 !important;
    }

    div[data-testid="stButton"] > button:focus p,
    div[data-testid="stButton"] > button:focus span,
    div[data-testid="stButton"] button:focus p,
    div[data-testid="stButton"] button:focus span,
    button[data-testid*="stBaseButton"]:focus p,
    button[data-testid*="stBaseButton"]:focus span,
    div[data-testid="stFormSubmitButton"] button:focus p,
    div[data-testid="stFormSubmitButton"] button:focus span,
    button:focus p,
    button:focus span {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    /* Editorial Section Headers */
    .editorial-heading {
        font-family: 'Playfair Display', 'DM Serif Display', Georgia, serif;
        font-size: 2.3rem;
        font-weight: 700;
        color: #111827;
        margin: 0 0 0.5rem 0;
        letter-spacing: -0.02em;
    }
    .editorial-subhead {
        font-size: 1.05rem;
        color: #6B7280;
        margin: 0 0 2.25rem 0;
        line-height: 1.5;
    }

    /* Steps Section */
    .step-unit {
        padding: 1.5rem 0.5rem;
    }
    .step-digit {
        font-family: 'Playfair Display', serif;
        font-size: 2.2rem;
        font-weight: 700;
        color: #1A535C;
        margin-bottom: 0.5rem;
        line-height: 1;
    }
    .step-name {
        font-size: 1.2rem;
        font-weight: 700;
        color: #111827;
        margin-bottom: 0.5rem;
    }
    .step-desc {
        font-size: 0.92rem;
        color: #4B5563;
        line-height: 1.55;
        margin: 0;
    }

    /* Service Cards */
    .service-block {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 2rem 1.75rem;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .service-block:hover {
        border-color: #111827;
        transform: translateY(-2px);
    }
    .service-block-title {
        font-family: 'Playfair Display', serif;
        font-size: 1.35rem;
        font-weight: 700;
        color: #111827;
        margin-bottom: 0.65rem;
    }
    .service-block-desc {
        font-size: 0.94rem;
        color: #4B5563;
        line-height: 1.5;
        margin-bottom: 1.5rem;
    }

    /* Registry Status Numbers */
    .stat-display {
        border-top: 2px solid #111827;
        padding-top: 1.25rem;
        margin-top: 0.5rem;
    }
    .stat-figure {
        font-family: 'Playfair Display', serif;
        font-size: 2.8rem;
        font-weight: 700;
        color: #111827;
        line-height: 1;
        margin-bottom: 0.35rem;
    }
    .stat-caption-title {
        font-size: 0.92rem;
        font-weight: 700;
        color: #111827;
        margin-bottom: 0.2rem;
    }
    .stat-caption-detail {
        font-size: 0.82rem;
        color: #6B7280;
        line-height: 1.4;
    }

    /* Form Card & High Contrast Inputs for Edge and Dark Mode Browsers */
    .form-wrapper {
        background: #FFFFFF !important;
        border: 1.5px solid #CBD5E1 !important;
        border-radius: 14px;
        padding: 2.5rem 2.25rem;
        margin-bottom: 2.5rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
    }
    
    /* Custom Field Labels */
    .field-header {
        font-size: 0.98rem !important;
        font-weight: 700 !important;
        color: #0F172A !important;
        -webkit-text-fill-color: #0F172A !important;
        margin-bottom: 0.25rem !important;
        display: block !important;
    }
    .field-desc {
        font-size: 0.84rem !important;
        color: #475569 !important;
        -webkit-text-fill-color: #475569 !important;
        margin-bottom: 0.55rem !important;
        line-height: 1.4 !important;
        display: block !important;
    }

    /* All Native Widget Labels */
    label,
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] *,
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] span {
        color: #0F172A !important;
        -webkit-text-fill-color: #0F172A !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        opacity: 1 !important;
        visibility: visible !important;
    }

    /* Text & Date Inputs - Clear, high contrast borders & dark text */
    div[data-testid="stTextInput"] input,
    div[data-testid="stDateInput"] input {
        border-radius: 8px !important;
        border: 2px solid #64748B !important;
        padding: 0.75rem 1rem !important;
        font-size: 1rem !important;
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        -webkit-text-fill-color: #0F172A !important;
        font-weight: 500 !important;
        box-shadow: none !important;
    }

    /* High-contrast placeholder text */
    div[data-testid="stTextInput"] input::placeholder,
    div[data-testid="stDateInput"] input::placeholder,
    input::placeholder {
        color: #64748B !important;
        -webkit-text-fill-color: #64748B !important;
        opacity: 1 !important;
        font-weight: 400 !important;
    }

    div[data-testid="stTextInput"] input:focus,
    div[data-testid="stDateInput"] input:focus {
        border-color: #0F172A !important;
        box-shadow: 0 0 0 2px #0F172A !important;
    }

    /* Clean Confirmation Banners */
    .alert-banner {
        background-color: #F0FDF4;
        border: 1.5px solid #BBF7D0;
        border-radius: 10px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.75rem;
    }
    .alert-banner-title {
        font-size: 1rem;
        font-weight: 700;
        color: #166534;
        margin-bottom: 0.3rem;
    }
    .alert-banner-text {
        font-size: 0.88rem;
        color: #15803D;
        line-height: 1.5;
        margin: 0;
    }

    /* Match Presentation */
    .match-result-card {
        background: #FFFFFF;
        border: 1.5px solid #111827;
        border-radius: 12px;
        padding: 1.5rem 1.75rem;
        margin-bottom: 1.25rem;
    }
    .match-result-title {
        font-family: 'Playfair Display', serif;
        font-size: 1.35rem;
        font-weight: 700;
        color: #111827;
        margin-bottom: 0.35rem;
    }
    .match-badge {
        display: inline-block;
        background-color: #ECFDF5;
        color: #047857;
        border: 1px solid #A7F3D0;
        padding: 0.2rem 0.65rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.75rem;
    }
    .match-meta {
        font-size: 0.9rem;
        color: #4B5563;
        line-height: 1.55;
    }

    /* Footer */
    .footer-strip {
        margin-top: 4.5rem;
        padding-top: 2rem;
        border-top: 1px solid #E5E7EB;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 1rem;
        color: #6B7280;
        font-size: 0.85rem;
    }
    .footer-wordmark {
        font-family: 'Playfair Display', serif;
        font-weight: 700;
        color: #111827;
        font-size: 1.05rem;
    }
</style>
""", unsafe_allow_html=True)

# Fetch latest data from database
lost_df = fetch_items("Lost_Items")
found_df = fetch_items("Found_Items")

# Update Prometheus Gauges
LOST_GAUGE.set(len(lost_df))
FOUND_GAUGE.set(len(found_df))

# Compute overall matches using existing matching logic
all_matches = []
if not lost_df.empty and not found_df.empty:
    for _, l_row in lost_df.iterrows():
        matches_for_l = find_matches_for_lost(l_row['item'], l_row['route'], found_df)
        for m in matches_for_l:
            all_matches.append({
                "lost_id": l_row['id'],
                "lost_item": l_row['item'],
                "lost_date": l_row['date'],
                "lost_route": l_row['route'],
                "found_id": m['found_id'],
                "found_item": m['found_item'],
                "found_route": m['found_route'],
                "found_date": m['found_date'],
                "match_type": m['match_type']
            })

# Navigation pages and session state
PAGES = ["Home", "Report Lost", "Report Found", "Find an Item", "About"]

if "nav_target" in st.session_state and st.session_state["nav_target"]:
    st.session_state["nav_selection"] = st.session_state["nav_target"]
    st.session_state["nav_target"] = None

if "nav_selection" not in st.session_state:
    st.session_state["nav_selection"] = "Home"

if "recent_lost_submission" not in st.session_state:
    st.session_state.recent_lost_submission = None

if "recent_found_submission" not in st.session_state:
    st.session_state.recent_found_submission = None

# ==============================================================================
# MINIMAL TOP NAVIGATION BAR (NO DASHBOARD SIDEBAR)
# ==============================================================================
col_logo, col_nav, col_cta = st.columns([1.2, 2.3, 0.9])

with col_logo:
    st.markdown("""
    <div style="padding: 0.35rem 0;">
        <div class="nav-wordmark">TransitRecover</div>
        <div class="nav-tagline">Transit Lost & Found</div>
    </div>
    """, unsafe_allow_html=True)

with col_nav:
    nav_choice = st.radio(
        "Navigation",
        PAGES,
        horizontal=True,
        key="nav_selection",
        label_visibility="collapsed"
    )

with col_cta:
    st.write("")
    if st.button("Report an Item", key="nav_top_cta", use_container_width=True):
        st.session_state["nav_target"] = "Report Lost"
        st.rerun()

st.markdown("<div style='height: 1.25rem;'></div>", unsafe_allow_html=True)

# ==============================================================================
# PAGE 1: HOME PAGE
# ==============================================================================
if nav_choice == "Home":
    # --------------------------------------------------------------------------
    # LARGE HERO SECTION (Soft Aqua Background, Left Typography, Right Visual)
    # --------------------------------------------------------------------------
    hero_b64 = get_hero_illustration_base64()
    if hero_b64:
        illustration_html = f'<img src="data:image/jpeg;base64,{hero_b64}" alt="Travel items illustration" class="hero-illustration-img" />'
    else:
        illustration_html = '<svg viewBox="0 0 400 300" width="100%" height="auto" style="max-width: 420px;" fill="none" stroke="#111827" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="60" y="80" width="110" height="150" rx="20" fill="#E0F7FA"/><path d="M90 80V60a25 25 0 0 1 50 0v20"/><rect x="80" y="140" width="70" height="70" rx="10" fill="#FFFFFF"/><line x1="95" y1="80" x2="95" y2="210"/><line x1="135" y1="80" x2="135" y2="210"/><rect x="200" y="120" width="65" height="110" rx="12" fill="#FFFFFF"/><rect x="208" y="132" width="49" height="78" rx="6" fill="#F8FAFC"/><circle cx="232" cy="126" r="2" fill="#111827"/><rect x="280" y="80" width="80" height="55" rx="8" fill="#FEF3C7"/><circle cx="310" cy="180" r="16"/><path d="M322 192l30 30m-12-8l8 8m-4-14l6 6"/></svg>'

    # Large Hero Container - Seamless Soft Aqua Section
    with st.container():
        st.markdown('<div class="hero-anchor"></div>', unsafe_allow_html=True)
        col_hero_text, col_hero_img = st.columns([1.1, 0.9])
        with col_hero_text:
            st.markdown("""
            <div style="padding-top: 0.5rem;">
                <div class="hero-eyebrow">TRANSIT LOST & FOUND</div>
                <h1 class="hero-headline">Lost something during your journey?</h1>
                <p class="hero-subtext">
                    Report a lost item, report something you've found, or check whether your belongings have been recovered.
                </p>
            </div>
            """, unsafe_allow_html=True)

            hero_btn_col1, hero_btn_col2, _ = st.columns([1.2, 1.2, 0.6])
            with hero_btn_col1:
                if st.button("Report Lost Item", key="hero_primary_report", use_container_width=True):
                    st.session_state["nav_target"] = "Report Lost"
                    st.rerun()

            with hero_btn_col2:
                if st.button("Find an Item", key="hero_secondary_find", use_container_width=True):
                    st.session_state["nav_target"] = "Find an Item"
                    st.rerun()

        with col_hero_img:
            st.markdown(f'<div class="hero-illustration-frame">{illustration_html}</div>', unsafe_allow_html=True)

    st.markdown("<div style='height: 4rem;'></div>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # HOW IT WORKS (Three Simple Editorial Steps)
    # --------------------------------------------------------------------------
    st.markdown('<div class="editorial-heading">How TransitRecover works</div>', unsafe_allow_html=True)
    st.markdown('<div class="editorial-subhead">A straightforward three-step process to connect passengers with their lost property.</div>', unsafe_allow_html=True)

    step_col1, step_col2, step_col3 = st.columns(3)
    with step_col1:
        st.markdown("""
        <div class="step-unit">
            <div class="step-digit">01</div>
            <div class="step-name">Report</div>
            <p class="step-desc">Tell us what you lost or found with key identifying details and transit route.</p>
        </div>
        """, unsafe_allow_html=True)

    with step_col2:
        st.markdown("""
        <div class="step-unit">
            <div class="step-digit">02</div>
            <div class="step-name">Search</div>
            <p class="step-desc">Check reported items and possible matches across our central registry.</p>
        </div>
        """, unsafe_allow_html=True)

    with step_col3:
        st.markdown("""
        <div class="step-unit">
            <div class="step-digit">03</div>
            <div class="step-name">Recover</div>
            <p class="step-desc">Connect the item with its owner and collect it from our station custody desk.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 3.5rem;'></div>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # HOW CAN WE HELP? (Service Section)
    # --------------------------------------------------------------------------
    st.markdown('<div class="editorial-heading">How can we help?</div>', unsafe_allow_html=True)
    st.markdown('<div class="editorial-subhead">Choose the service you need today.</div>', unsafe_allow_html=True)

    serv_c1, serv_c2, serv_c3 = st.columns(3)
    with serv_c1:
        st.markdown("""
        <div class="service-block">
            <div>
                <div class="service-block-title">Report a Lost Item</div>
                <div class="service-block-desc">Tell us what you lost and where you last saw it so our custody team can monitor incoming property.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Report Lost Item", key="serv_card_lost", use_container_width=True):
            st.session_state["nav_target"] = "Report Lost"
            st.rerun()

    with serv_c2:
        st.markdown("""
        <div class="service-block">
            <div>
                <div class="service-block-title">Report a Found Item</div>
                <div class="service-block-desc">Help return an item you found to its owner by registering details before turning it in to station staff.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Report Found Item", key="serv_card_found", use_container_width=True):
            st.session_state["nav_target"] = "Report Found"
            st.rerun()

    with serv_c3:
        st.markdown("""
        <div class="service-block">
            <div>
                <div class="service-block-title">Find an Item</div>
                <div class="service-block-desc">Search reported items and check for possible matches across our active custody database.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Find an Item", key="serv_card_search", use_container_width=True):
            st.session_state["nav_target"] = "Find an Item"
            st.rerun()

    st.markdown("<div style='height: 4rem;'></div>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # REGISTRY STATUS (Subtle Real Statistics Lower Down the Page)
    # --------------------------------------------------------------------------
    st.markdown('<div class="editorial-heading" style="font-size: 1.85rem;">Registry status</div>', unsafe_allow_html=True)
    st.markdown('<div class="editorial-subhead">Verified real-time statistics across the transit network custody desks.</div>', unsafe_allow_html=True)

    stat_col1, stat_col2, stat_col3 = st.columns(3)
    with stat_col1:
        st.markdown(f"""
        <div class="stat-display">
            <div class="stat-figure">{len(lost_df)}</div>
            <div class="stat-caption-title">Lost Items Reported</div>
            <div class="stat-caption-detail">Inquiries submitted by passengers across all lines</div>
        </div>
        """, unsafe_allow_html=True)

    with stat_col2:
        st.markdown(f"""
        <div class="stat-display">
            <div class="stat-figure">{len(found_df)}</div>
            <div class="stat-caption-title">Found Items In Custody</div>
            <div class="stat-caption-detail">Property safely secured at station lost property counters</div>
        </div>
        """, unsafe_allow_html=True)

    with stat_col3:
        st.markdown(f"""
        <div class="stat-display">
            <div class="stat-figure">{len(all_matches)}</div>
            <div class="stat-caption-title">Matches Found</div>
            <div class="stat-caption-detail">Potential pairings identified for passenger review</div>
        </div>
        """, unsafe_allow_html=True)

# ==============================================================================
# PAGE 2: REPORT LOST
# ==============================================================================
elif nav_choice == "Report Lost":
    st.markdown('<div class="editorial-heading">Report a Lost Item</div>', unsafe_allow_html=True)
    st.markdown('<div class="editorial-subhead">Provide details about the item you lost so we can help identify it in our custody registry.</div>', unsafe_allow_html=True)

    # Confirmation banner if just submitted
    if st.session_state.recent_lost_submission:
        sub = st.session_state.recent_lost_submission
        st.markdown(f"""
        <div class="alert-banner">
            <div class="alert-banner-title">Lost item reported successfully.</div>
            <p class="alert-banner-text">
                Your report for <b>{sub['item']}</b> has been registered in the database. Our system actively monitors incoming items.
            </p>
        </div>
        """, unsafe_allow_html=True)

        immediate_matches = find_matches_for_lost(sub['item'], sub['route'], found_df)
        if immediate_matches:
            st.markdown('<div class="editorial-heading" style="font-size: 1.5rem; margin-top: 1rem;">Possible Match</div>', unsafe_allow_html=True)
            for im in immediate_matches:
                st.markdown(f"""
                <div class="match-result-card">
                    <span class="match-badge">Possible Match</span>
                    <div class="match-result-title">{im['found_item']}</div>
                    <div class="match-meta">
                        <b>Location:</b> {im['found_route']} &nbsp;&bull;&nbsp;
                        <b>Date:</b> {im['found_date']} &nbsp;&bull;&nbsp;
                        <b>Custody ID:</b> #{im['found_id']}<br>
                        <b>To claim:</b> Visit Central Station Lost Property Counter quoting Custody ID #{im['found_id']} with valid photo ID.
                    </div>
                </div>
                """, unsafe_allow_html=True)
        st.session_state.recent_lost_submission = None

    with st.container():
        st.markdown('<div class="form-wrapper">', unsafe_allow_html=True)
        with st.form("form_report_lost", clear_on_submit=True):
            col_l1, col_l2 = st.columns(2)
            with col_l1:
                st.markdown('<label class="field-header">1. What did you lose? *</label><span class="field-desc">Enter the item name, color, brand, or distinguishing features</span>', unsafe_allow_html=True)
                item_name = st.text_input(
                    "Item Name and Description *",
                    placeholder="e.g., Black Leather Backpack, Blue Umbrella, iPhone 13",
                    label_visibility="collapsed"
                ).strip()

                st.markdown('<div style="height: 1.25rem;"></div>', unsafe_allow_html=True)

                st.markdown('<label class="field-header">2. Where was it lost? *</label><span class="field-desc">Specify the transit line, station, platform, or bus route</span>', unsafe_allow_html=True)
                item_route = st.text_input(
                    "Location / Transit Line / Station *",
                    placeholder="e.g., Metro Line 1, Central Station Concourse, Bus Route 42",
                    label_visibility="collapsed"
                ).strip()

            with col_l2:
                st.markdown('<label class="field-header">3. Date Lost *</label><span class="field-desc">When did the item go missing?</span>', unsafe_allow_html=True)
                item_date = st.date_input(
                    "Date Lost *",
                    value=date.today(),
                    max_value=date.today(),
                    label_visibility="collapsed"
                )

                st.markdown("""
                <div style="background-color: #F8FAFC; border: 1.5px solid #CBD5E1; border-radius: 8px; padding: 1.15rem 1.25rem; margin-top: 1.25rem;">
                    <div style="font-weight: 700; color: #0F172A; font-size: 0.92rem; margin-bottom: 0.25rem;">Filing Advice</div>
                    <div style="color: #475569; font-size: 0.85rem; line-height: 1.45;">
                        Include specific details like brand, case color, or stickers to help custody staff verify your belongings immediately.
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.write("")
            submitted_lost = st.form_submit_button("Submit Lost Item Report", use_container_width=True)

            if submitted_lost:
                if not item_name:
                    st.error("Please enter the item name or description.")
                elif not item_route:
                    st.error("Please specify where the item was lost.")
                else:
                    add_lost_item(item_name, str(item_date), item_route)
                    st.session_state.recent_lost_submission = {
                        "item": item_name,
                        "date": str(item_date),
                        "route": item_route
                    }
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="editorial-heading" style="font-size: 1.6rem;">Recent lost reports</div>', unsafe_allow_html=True)
    st.markdown('<div class="editorial-subhead">Recent inquiries registered by passengers across the network.</div>', unsafe_allow_html=True)

    if lost_df.empty:
        st.info("No lost items currently on record.")
    else:
        recent_lost_display = lost_df.head(10).rename(columns={
            "id": "Report ID",
            "item": "Item Description",
            "date": "Date Lost",
            "route": "Transit Line / Location"
        })
        st.dataframe(recent_lost_display, use_container_width=True, hide_index=True)

# ==============================================================================
# PAGE 3: REPORT FOUND
# ==============================================================================
elif nav_choice == "Report Found":
    st.markdown('<div class="editorial-heading">Report a Found Item</div>', unsafe_allow_html=True)
    st.markdown('<div class="editorial-subhead">If you found an item during your journey, provide its details so it can be returned to its owner.</div>', unsafe_allow_html=True)

    if st.session_state.recent_found_submission:
        sub_f = st.session_state.recent_found_submission
        st.markdown(f"""
        <div class="alert-banner">
            <div class="alert-banner-title">Found item reported successfully.</div>
            <p class="alert-banner-text">
                Thank you for reporting <b>{sub_f['item']}</b>. Please surrender the physical item to station staff or an authorized transit officer.
            </p>
        </div>
        """, unsafe_allow_html=True)
        st.session_state.recent_found_submission = None

    with st.container():
        st.markdown('<div class="form-wrapper">', unsafe_allow_html=True)
        with st.form("form_report_found", clear_on_submit=True):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                st.markdown('<label class="field-header">1. Item Description *</label><span class="field-desc">What item did you find?</span>', unsafe_allow_html=True)
                found_name = st.text_input(
                    "Item Name and Description *",
                    placeholder="e.g., Set of Keys, Black Dell Laptop, Blue Umbrella",
                    label_visibility="collapsed"
                ).strip()

                st.markdown('<div style="height: 1.25rem;"></div>', unsafe_allow_html=True)

                st.markdown('<label class="field-header">2. Where Was It Found? *</label><span class="field-desc">Station, transit line, train car, or platform location</span>', unsafe_allow_html=True)
                found_route = st.text_input(
                    "Where Was It Found? (Station / Line / Platform) *",
                    placeholder="e.g., Platform 2, Metro Line 1, Central Concourse",
                    label_visibility="collapsed"
                ).strip()

            with col_f2:
                st.markdown('<label class="field-header">3. Date Found *</label><span class="field-desc">When was the item discovered?</span>', unsafe_allow_html=True)
                found_date = st.date_input(
                    "Date Found *",
                    value=date.today(),
                    max_value=date.today(),
                    label_visibility="collapsed"
                )

                st.markdown("""
                <div style="background-color: #F8FAFC; border: 1.5px solid #CBD5E1; border-radius: 8px; padding: 1.15rem 1.25rem; margin-top: 1.25rem;">
                    <div style="font-weight: 700; color: #0F172A; font-size: 0.92rem; margin-bottom: 0.25rem;">Handover Responsibility</div>
                    <div style="color: #475569; font-size: 0.85rem; line-height: 1.45;">
                        Please deposit the physical item with the nearest station customer service desk or transit officer.
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.write("")
            submitted_found = st.form_submit_button("Submit Found Item Report", use_container_width=True)

            if submitted_found:
                if not found_name:
                    st.error("Please enter the item description.")
                elif not found_route:
                    st.error("Please enter the station or line where it was found.")
                else:
                    add_found_item(found_name, str(found_date), found_route)
                    st.session_state.recent_found_submission = {
                        "item": found_name,
                        "date": str(found_date),
                        "route": found_route
                    }
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="editorial-heading" style="font-size: 1.6rem;">Recent items in custody</div>', unsafe_allow_html=True)
    st.markdown('<div class="editorial-subhead">Items currently cataloged and safely stored at transit custody counters.</div>', unsafe_allow_html=True)

    if found_df.empty:
        st.info("No found items currently in custody.")
    else:
        recent_found_display = found_df.head(10).rename(columns={
            "id": "Custody ID",
            "item": "Item Description",
            "date": "Date Found",
            "route": "Transit Line / Location"
        })
        st.dataframe(recent_found_display, use_container_width=True, hide_index=True)

# ==============================================================================
# PAGE 4: FIND AN ITEM
# ==============================================================================
elif nav_choice == "Find an Item":
    st.markdown('<div class="editorial-heading">Find Your Lost Item</div>', unsafe_allow_html=True)
    st.markdown('<div class="editorial-subhead">Search reported items to see if your belongings have been recovered.</div>', unsafe_allow_html=True)

    # Prominent Search Input
    st.markdown('<label class="field-header" style="font-size: 1.05rem;">Search Registry by Keyword or Description</label><span class="field-desc">Type what you are searching for (e.g., backpack, wallet, keys, umbrella, Metro Line 1)</span>', unsafe_allow_html=True)
    search_query = st.text_input(
        "Search Registry by Keyword or Description:",
        placeholder="Type item description (e.g., backpack, wallet, keys, umbrella)...",
        key="main_search_query",
        label_visibility="collapsed"
    ).strip()

    st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

    # Possible Matches Section
    if all_matches:
        st.markdown('<div class="editorial-heading" style="font-size: 1.7rem;">Possible Matches</div>', unsafe_allow_html=True)
        st.markdown('<div class="editorial-subhead">Items reported lost that correspond with property currently held in station custody.</div>', unsafe_allow_html=True)

        display_matches = all_matches
        if search_query:
            display_matches = [
                m for m in all_matches
                if search_query.lower() in m['lost_item'].lower()
                or search_query.lower() in m['found_item'].lower()
                or search_query.lower() in m['found_route'].lower()
                or search_query.lower() in m['lost_route'].lower()
            ]

        if not display_matches and search_query:
            st.info(f"No match pairings correspond to '{search_query}'.")
        else:
            for m in display_matches[:8]:
                st.markdown(f"""
                <div class="match-result-card">
                    <span class="match-badge">Possible Match</span>
                    <div class="match-result-title">{m['found_item']}</div>
                    <div class="match-meta">
                        Possible match based on the reported item details.<br><br>
                        <b>Location:</b> {m['found_route']} &nbsp;&bull;&nbsp;
                        <b>Date:</b> {m['found_date']} &nbsp;&bull;&nbsp;
                        <b>Status:</b> Found &nbsp;&bull;&nbsp;
                        <b>Custody ID:</b> #{m['found_id']}<br>
                        <b>Reported Lost Reference:</b> '{m['lost_item']}' on {m['lost_date']} at {m['lost_route']}.<br>
                        <b>To claim:</b> Visit Central Station Lost Property Desk quoting <b>Custody ID #{m['found_id']}</b>.
                    </div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)

    # Full Records Catalog
    st.markdown('<div class="editorial-heading" style="font-size: 1.7rem;">Registry Catalog</div>', unsafe_allow_html=True)
    st.markdown('<div class="editorial-subhead">Filter and browse all cataloged records.</div>', unsafe_allow_html=True)

    col_view_found, col_view_lost = st.columns(2)

    with col_view_found:
        st.markdown("#### Items in Custody (Found)")
        filtered_f = found_df.copy()
        if search_query and not filtered_f.empty:
            filtered_f = filtered_f[
                filtered_f['item'].str.lower().str.contains(search_query.lower()) |
                filtered_f['route'].str.lower().str.contains(search_query.lower())
            ]

        if filtered_f.empty:
            st.info("No found items match the filter criteria.")
        else:
            display_f = filtered_f.rename(columns={
                'id': 'Custody ID',
                'item': 'Item Description',
                'date': 'Date Found',
                'route': 'Station / Line'
            })
            st.dataframe(display_f, use_container_width=True, hide_index=True)

    with col_view_lost:
        st.markdown("#### Items Reported Lost")
        filtered_l = lost_df.copy()
        if search_query and not filtered_l.empty:
            filtered_l = filtered_l[
                filtered_l['item'].str.lower().str.contains(search_query.lower()) |
                filtered_l['route'].str.lower().str.contains(search_query.lower())
            ]

        if filtered_l.empty:
            st.info("No lost reports match the filter criteria.")
        else:
            display_l = filtered_l.rename(columns={
                'id': 'Report ID',
                'item': 'Item Description',
                'date': 'Date Lost',
                'route': 'Station / Line'
            })
            st.dataframe(display_l, use_container_width=True, hide_index=True)

# ==============================================================================
# PAGE 5: ABOUT
# ==============================================================================
elif nav_choice == "About":
    st.markdown('<div class="editorial-heading">About TransitRecover</div>', unsafe_allow_html=True)
    st.markdown('<div class="editorial-subhead">Public transit lost-and-found service operations and passenger guidelines.</div>', unsafe_allow_html=True)

    st.markdown("""
    <div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 12px; padding: 2rem 2.25rem; margin-bottom: 2rem;">
        <div style="font-family: 'Playfair Display', serif; font-size: 1.4rem; font-weight: 700; color: #111827; margin-bottom: 0.75rem;">
            Mission & Overview
        </div>
        <p style="font-size: 0.98rem; color: #4B5563; line-height: 1.65; margin: 0;">
            TransitRecover serves as the official lost-and-found registry for the regional transit authority. 
            Every day, items misplaced across trains, buses, and stations are gathered by station staff and cataloged in a unified database to ensure rapid return to their rightful owners.
        </p>
    </div>
    """, unsafe_allow_html=True)

    about_col1, about_col2 = st.columns(2)

    with about_col1:
        st.markdown("""
        <div class="service-block">
            <div>
                <div class="service-block-title">How Property Is Handled</div>
                <div class="service-block-desc">
                    <b>1. Discovery and Intake:</b> Items found on vehicles or premises are deposited at local station counters.<br><br>
                    <b>2. Central Cataloging:</b> Each item is assigned an official Custody ID and entered into the registry.<br><br>
                    <b>3. Secure Custody:</b> Valuables and personal belongings are stored under secure custody protocols.<br><br>
                    <b>4. Identification & Release:</b> Claimants undergo identity verification prior to release of property.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with about_col2:
        st.markdown("""
        <div class="service-block">
            <div>
                <div class="service-block-title">Claiming Information</div>
                <div class="service-block-desc">
                    <b>Identification Required:</b> Valid photo identification (Driver's License, Passport, or National ID) must be presented for all claims.<br><br>
                    <b>Proof of Ownership:</b> For electronic devices, claimants must be able to unlock the device or present documentation. For bags and wallets, unique contents must be specified.<br><br>
                    <b>Holding Period:</b> Property is retained for sixty (60) days pursuant to transit regulations.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)

    st.markdown("""
    <div style="background: #D4F4F1; border-radius: 14px; padding: 2rem 2.25rem;">
        <div style="font-family: 'Playfair Display', serif; font-size: 1.35rem; font-weight: 700; color: #111827; margin-bottom: 0.65rem;">
            Central Lost Property Desk
        </div>
        <div style="font-size: 0.95rem; color: #1E293B; line-height: 1.6;">
            <b>Location:</b> Central Station Concourse, Level 1<br>
            <b>Telephone Helpline:</b> 1800-11-TRANSIT (Toll-Free)<br>
            <b>Operating Hours:</b> Monday through Sunday, 08:00 to 20:00<br>
            <b>Assistance:</b> In-person claim assistance is available throughout all operational hours.
        </div>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# FOOTER
# ==============================================================================
st.markdown("""
<div class="footer-strip">
    <div>
        <span class="footer-wordmark">TransitRecover</span> &mdash; Connecting passengers with their lost belongings.
    </div>
    <div>
        Central Lost Property Office &bull; Helpline: 1800-11-TRANSIT &bull; Official Public Service
    </div>
</div>
""", unsafe_allow_html=True)
