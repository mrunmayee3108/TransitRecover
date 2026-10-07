# pyrefly: ignore [missing-import]
from prometheus_client import start_http_server, Counter, Gauge, REGISTRY
import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
import re

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

# ==============================================================================
# STREAMLIT PAGE CONFIG & CLEAN, SIMPLE STYLING
# ==============================================================================
st.set_page_config(
    page_title="TransitRecover - Lost & Found",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Clean, modern, accessible CSS
st.markdown("""
<style>
    /* Clean base styling */
    .stApp {
        background-color: #F8FAFC;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
        color: #1E293B;
    }

    /* Main Header */
    .app-header {
        background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%);
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .app-title {
        font-size: 2rem;
        font-weight: 800;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .app-subtitle {
        font-size: 0.95rem;
        color: #DBEAFE;
        margin-top: 0.35rem;
        margin-bottom: 0;
    }

    /* Stat Cards */
    .stat-card {
        background: white;
        border-radius: 10px;
        padding: 1.1rem 1.25rem;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        display: flex;
        flex-direction: column;
        transition: transform 0.15s ease;
    }
    .stat-card:hover {
        transform: translateY(-2px);
    }
    .stat-label {
        font-size: 0.85rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }
    .stat-value {
        font-size: 1.85rem;
        font-weight: 800;
        color: #0F172A;
        margin: 0.2rem 0;
    }
    .stat-hint {
        font-size: 0.78rem;
        color: #94A3B8;
    }

    /* Tabs Styling - Clean & High Contrast */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 2px solid #E2E8F0;
        margin-bottom: 1rem;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 0.65rem 1.25rem;
        border-radius: 8px 8px 0 0;
        font-size: 0.95rem;
        font-weight: 600;
        color: #475569 !important;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #2563EB !important;
        background-color: #EFF6FF;
    }
    .stTabs [aria-selected="true"] {
        color: #2563EB !important;
        background-color: white !important;
        border-bottom: 3px solid #2563EB !important;
    }

    /* Action & Status Cards */
    .match-found-card {
        background: #F0FDF4;
        border: 2px solid #22C55E;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
    }
    .match-pending-card {
        background: #FEF9C3;
        border: 1px solid #FDE047;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
    }

    .badge-found {
        background: #DCFCE7;
        color: #15803D;
        font-weight: 700;
        font-size: 0.75rem;
        padding: 0.2rem 0.5rem;
        border-radius: 6px;
        display: inline-block;
    }
    .badge-searching {
        background: #FEF3C7;
        color: #B45309;
        font-weight: 700;
        font-size: 0.75rem;
        padding: 0.2rem 0.5rem;
        border-radius: 6px;
        display: inline-block;
    }

    /* Sidebar Clean Card */
    .side-card {
        background: white;
        border-radius: 8px;
        padding: 1rem;
        border: 1px solid #E2E8F0;
        margin-bottom: 0.85rem;
    }
    .side-title {
        font-weight: 700;
        font-size: 0.9rem;
        color: #1E293B;
        margin-bottom: 0.4rem;
    }

    /* Form submit button */
    div.stButton > button {
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1.25rem;
        background-color: #2563EB;
        color: white;
        border: none;
        transition: background 0.15s ease;
    }
    div.stButton > button:hover {
        background-color: #1D4ED8;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Fetch latest data
lost_df = fetch_items("Lost_Items")
found_df = fetch_items("Found_Items")

LOST_GAUGE.set(len(lost_df))
FOUND_GAUGE.set(len(found_df))

# Compute overall matches
all_matches = []
if not lost_df.empty and not found_df.empty:
    for _, l_row in lost_df.iterrows():
        matches_for_l = find_matches_for_lost(l_row['item'], l_row['route'], found_df)
        for m in matches_for_l:
            all_matches.append({
                "Lost Item": l_row['item'],
                "Date Lost": l_row['date'],
                "Lost Route": l_row['route'],
                "Matched Found Item": m['found_item'],
                "Found Location": m['found_route'],
                "Found Date": m['found_date'],
                "Found Record ID": m['found_id'],
                "Match Type": m['match_type']
            })

# ==============================================================================
# CLEAN & SIMPLE HEADER
# ==============================================================================
st.markdown("""
<div class="app-header">
    <h1 class="app-title">🚆 TransitRecover</h1>
    <p class="app-subtitle">Simple Lost & Found Portal — Report lost belongings and immediately check if they have been found.</p>
</div>
""", unsafe_allow_html=True)

# Top Summary Stats
col_s1, col_s2, col_s3 = st.columns(3)
with col_s1:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-label">Lost Items Reported</div>
        <div class="stat-value">{len(lost_df)}</div>
        <div class="stat-hint">Items reported by passengers</div>
    </div>
    """, unsafe_allow_html=True)

with col_s2:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-label">Found Items In Custody</div>
        <div class="stat-value">{len(found_df)}</div>
        <div class="stat-hint">Recovered and waiting at station</div>
    </div>
    """, unsafe_allow_html=True)

with col_s3:
    st.markdown(f"""
    <div class="stat-card" style="border-left: 4px solid #10B981;">
        <div class="stat-label" style="color: #059669;">Matches Found</div>
        <div class="stat-value" style="color: #059669;">{len(all_matches)}</div>
        <div class="stat-hint">Ready for owners to claim</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# Check session state for newly submitted item to show instant result
if "recent_logged_item" not in st.session_state:
    st.session_state.recent_logged_item = None

# ==============================================================================
# MAIN TABS (SIMPLE & INTUITIVE)
# ==============================================================================
tab_check, tab_log_lost, tab_log_found, tab_browse = st.tabs([
    "Check If Found",
    "Log a Lost Item",
    "Report a Found Item",
    "Browse All Items"
])

# ------------------------------------------------------------------------------
# TAB 1: CHECK IF FOUND (Instant Check for Users)
# ------------------------------------------------------------------------------
with tab_check:
    st.subheader("Check If Your Lost Item Was Found")
    st.caption("Search our custody registry to see if someone has already turned in your item.")

    # Search Bar
    check_query = st.text_input(
        "Enter your item name or keyword (e.g. umbrella, wallet, bag, keys):",
        placeholder="Type what you lost...",
        key="search_check_input"
    ).strip()

    if check_query:
        # Search against found items
        matching_found = []
        q_words = extract_keywords(check_query)
        for _, f_row in found_df.iterrows():
            f_words = extract_keywords(f_row['item'])
            common = q_words.intersection(f_words)
            is_sub = (check_query.lower() in f_row['item'].lower()) or (f_row['item'].lower() in check_query.lower())
            if len(common) > 0 or is_sub:
                matching_found.append(f_row)

        if matching_found:
            st.success(f"Great news! We found {len(matching_found)} matching item(s) in custody:")
            for item in matching_found:
                st.markdown(f"""
                <div class="match-found-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                        <span style="font-size: 1.15rem; font-weight: 800; color: #166534;">{item['item']}</span>
                        <span class="badge-found">Custody ID #{item['id']}</span>
                    </div>
                    <div style="font-size: 0.9rem; color: #374151;">
                        <b>Found at:</b> {item['route']} &nbsp;|&nbsp; 
                        <b>Turned in on:</b> {item['date']}
                    </div>
                    <div style="margin-top: 0.5rem; font-size: 0.85rem; color: #15803D; font-weight: 600;">
                         To claim: Visit the Station Counter or call 1800-11-TRANSIT quoting Custody ID #{item['id']}.
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning(f"No items matching '{check_query}' have been turned in yet.")
            st.info("If you haven't already, please go to the **'Log a Lost Item'** tab to record your item so we can alert you when it arrives.")

    st.divider()

    # Track Status of All Reported Lost Items
    st.subheader("Status of Reported Lost Items")
    if lost_df.empty:
        st.info("No lost items reported yet. Use the 'Log a Lost Item' tab to report one.")
    else:
        for _, l_row in lost_df.iterrows():
            matches_for_this = find_matches_for_lost(l_row['item'], l_row['route'], found_df)
            has_match = len(matches_for_this) > 0
            
            with st.container():
                if has_match:
                    best_match = matches_for_this[0]
                    st.markdown(f"""
                    <div class="match-found-card">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <span style="font-weight: 700; font-size: 1.05rem; color: #1E293B;">{l_row['item']}</span>
                                <span style="font-size: 0.82rem; color: #64748B; margin-left: 0.5rem;">(Lost on {l_row['date']} • {l_row['route']})</span>
                            </div>
                            <span class="badge-found">MATCH FOUND!</span>
                        </div>
                        <div style="margin-top: 0.6rem; padding-top: 0.5rem; border-top: 1px solid #BBF7D0; font-size: 0.9rem; color: #166534;">
                            <b>Matched with:</b> '{best_match['found_item']}' (Custody ID #{best_match['found_id']})<br>
                            <b>Location:</b> {best_match['found_route']} &nbsp;|&nbsp; <b>Date:</b> {best_match['found_date']}<br>
                            <b>How to claim:</b> Quote <b>Custody ID #{best_match['found_id']}</b> at station counter with a valid ID.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="match-pending-card">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <span style="font-weight: 700; font-size: 1.05rem; color: #1E293B;">{l_row['item']}</span>
                                <span style="font-size: 0.82rem; color: #64748B; margin-left: 0.5rem;">(Lost on {l_row['date']} • {l_row['route']})</span>
                            </div>
                            <span class="badge-searching">SEARCHING...</span>
                        </div>
                        <div style="margin-top: 0.4rem; font-size: 0.82rem; color: #854D0E;">
                            No matching item turned in yet. We check every new item automatically.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# TAB 2: LOG A LOST ITEM (Simple Form + Instant Match Detection)
# ------------------------------------------------------------------------------
with tab_log_lost:
    st.subheader("Report a Lost Item")
    st.caption("Fill in the details below. We will instantly check if someone already turned it in!")

    # Show alert if user just logged an item
    if st.session_state.recent_logged_item:
        rec = st.session_state.recent_logged_item
        instant_matches = find_matches_for_lost(rec['item'], rec['route'], found_df)
        if instant_matches:
            st.success(f"**Great news! A match was found for '{rec['item']}'!**")
            for m in instant_matches:
                st.info(f"**Custody ID #{m['found_id']}**: '{m['found_item']}' at **{m['found_route']}** (Found on {m['found_date']}). Visit station desk to claim!")
        else:
            st.success(f"Successfully logged '{rec['item']}'. We are actively watching for matches!")
        # Reset banner state after displaying once
        st.session_state.recent_logged_item = None

    with st.form("form_simple_lost", clear_on_submit=True):
        col_l1, col_l2 = st.columns(2)
        with col_l1:
            item_name = st.text_input(
                "What did you lose? *",
                placeholder="e.g. Blue Umbrella, Black Backpack, iPhone 13, Leather Wallet"
            ).strip()
            item_route = st.text_input(
                "Where was it lost? (Transit Line / Station / Bus) *",
                placeholder="e.g. Metro Line 1, Central Station, Bus 412"
            ).strip()
        with col_l2:
            item_date = st.date_input("When did you lose it? *", value=date.today(), max_value=date.today())
            st.info("**Tip:** Be descriptive (color, brand) so our match system can instantly pair it with items in custody.")

        submitted = st.form_submit_button("Submit Lost Item & Check Matches", use_container_width=True)

        if submitted:
            if not item_name:
                st.error("Please enter what you lost.")
            elif not item_route:
                st.error("Please enter the transit line or station where it was lost.")
            else:
                add_lost_item(item_name, str(item_date), item_route)
                # Save into session state for immediate feedback
                st.session_state.recent_logged_item = {
                    "item": item_name,
                    "date": str(item_date),
                    "route": item_route
                }
                st.rerun()

# ------------------------------------------------------------------------------
# TAB 3: REPORT A FOUND ITEM
# ------------------------------------------------------------------------------
with tab_log_found:
    st.subheader("Report an Item You Found")
    st.caption("Help return lost belongings by entering what was handed in or discovered.")

    with st.form("form_simple_found", clear_on_submit=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            found_name = st.text_input(
                "Item Description *",
                placeholder="e.g. Blue Umbrella, Set of Keys, Black Dell Laptop"
            ).strip()
            found_route = st.text_input(
                "Where was it found? (Station / Line) *",
                placeholder="e.g. Metro Line 1, Platform 2 Concourse, Bus 10"
            ).strip()
        with col_f2:
            found_date = st.date_input("Date Found *", value=date.today(), max_value=date.today())
            st.info(" **Thank you!** Submitting found items helps passengers recover their essentials quickly.")

        submitted_found = st.form_submit_button("Register Found Item", use_container_width=True)

        if submitted_found:
            if not found_name:
                st.error("Please enter the item description.")
            elif not found_route:
                st.error("Please enter where it was found.")
            else:
                add_found_item(found_name, str(found_date), found_route)
                st.success(f" '{found_name}' has been added to found items inventory!")
                st.rerun()

# ------------------------------------------------------------------------------
# TAB 4: BROWSE ALL ITEMS
# ------------------------------------------------------------------------------
with tab_browse:
    st.subheader("Browse All Records")
    
    search_filter = st.text_input("Filter items by name:", placeholder="Filter by keyword...", key="browse_search").strip().lower()

    col_view1, col_view2 = st.columns(2)

    with col_view1:
        st.markdown("#### Found Items (In Custody)")
        filtered_found = found_df.copy()
        if search_filter and not filtered_found.empty:
            filtered_found = filtered_found[filtered_found['item'].str.lower().str.contains(search_filter)]

        if filtered_found.empty:
            st.info("No found items match the filter.")
        else:
            display_f = filtered_found.rename(columns={
                'id': 'ID',
                'item': 'Item',
                'date': 'Date Found',
                'route': 'Station / Line'
            })
            st.dataframe(display_f, use_container_width=True, hide_index=True)

    with col_view2:
        st.markdown("#### Lost Items (Reported)")
        filtered_lost = lost_df.copy()
        if search_filter and not filtered_lost.empty:
            filtered_lost = filtered_lost[filtered_lost['item'].str.lower().str.contains(search_filter)]

        if filtered_lost.empty:
            st.info("No lost items match the filter.")
        else:
            display_l = filtered_lost.rename(columns={
                'id': 'ID',
                'item': 'Item',
                'date': 'Date Lost',
                'route': 'Station / Line'
            })
            st.dataframe(display_l, use_container_width=True, hide_index=True)

# ==============================================================================
# SIMPLE SIDEBAR
# ==============================================================================
with st.sidebar:
    st.markdown("""
    <div style="padding: 0.5rem 0 1rem 0; border-bottom: 1px solid #E2E8F0; margin-bottom: 1rem;">
        <h2 style="font-size: 1.35rem; font-weight: 800; color: #1E3A8A; margin: 0;">🚆 TransitRecover</h2>
        <span style="font-size: 0.8rem; color: #64748B;">Public Transit Lost & Found</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="side-card">
        <div class="side-title">⚡ How to Claim an Item</div>
        <ol style="margin: 0; padding-left: 1.15rem; font-size: 0.82rem; color: #334155; line-height: 1.5;">
            <li>Find your item in the <b>Check If Found</b> tab</li>
            <li>Note the <b>Custody ID #</b></li>
            <li>Visit the station office with a valid Photo ID to collect it</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="side-card">
        <div class="side-title">📞 Lost Property Desk</div>
        <div style="font-size: 0.82rem; color: #334155; line-height: 1.5;">
            <b>Helpline:</b> 1800-11-TRANSIT<br>
            <b>Hours:</b> 8:00 AM – 8:00 PM Daily<br>
            <b>Location:</b> Central Station Concourse
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()
