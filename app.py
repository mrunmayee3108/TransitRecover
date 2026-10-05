# pyrefly: ignore [missing-import]
from prometheus_client import start_http_server, Counter, Gauge, REGISTRY
import streamlit as st
import sqlite3
import pandas as pd
from datetime import date

# ==============================================================================
# PROMETHEUS METRICS EXPORTER SETUP (Port 8000)
# ==============================================================================
# Start Prometheus metrics server on port 8000 at top of script
try:
    start_http_server(8000)
except OSError:
    # Port already active across Streamlit reruns
    pass

# Helper to prevent collector re-registration errors during Streamlit reruns
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
    # Create Lost_Items table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Lost_Items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT NOT NULL,
            date TEXT NOT NULL,
            route TEXT NOT NULL
        )
    """)
    # Create Found_Items table
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

# Initialize DB on load
init_db()

# Synchronize Prometheus Gauge values with DB state
try:
    lost_df_init = fetch_items("Lost_Items")
    found_df_init = fetch_items("Found_Items")
    LOST_GAUGE.set(len(lost_df_init))
    FOUND_GAUGE.set(len(found_df_init))
except Exception:
    pass

# ==============================================================================
# STREAMLIT PAGE CONFIGURATION & FORMAL CIVIC STYLING
# ==============================================================================
st.set_page_config(
    page_title="TransitRecover - Central Lost and Found Portal",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for an authentic civic/governmental portal design
st.markdown("""
<style>
    :root {
        --saffron-gov: #E06A00;
        --saffron-subtle: #FFF7ED;
        --saffron-border: #FDBA74;
        
        --green-gov: #116828;
        --green-subtle: #F0FDF4;
        --green-border: #86EFAC;
        
        --navy-gov: #0B2545;
        --slate-bg: #F4F6F9;
        --border-color: #D1D5DB;
        --text-color: #1F2937;
        --muted-color: #4B5563;
    }

    .stApp {
        background-color: var(--slate-bg);
        color: var(--text-color);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }

    /* Top Tricolor Strip */
    .gov-top-bar {
        height: 4px;
        background: linear-gradient(90deg, #FF9933 0%, #FF9933 33.3%, #FFFFFF 33.3%, #FFFFFF 66.6%, #138808 66.6%, #138808 100%);
        margin-bottom: 1rem;
        border-radius: 2px;
    }

    /* Formal Government Header */
    .gov-header {
        background-color: #FFFFFF;
        border: 1px solid var(--border-color);
        border-top: 4px solid var(--saffron-gov);
        border-radius: 4px;
        padding: 1.25rem 1.75rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    
    .gov-agency-title {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted-color);
        margin-bottom: 0.2rem;
    }

    .gov-title {
        font-size: 1.85rem;
        font-weight: 800;
        color: var(--navy-gov);
        margin: 0;
        letter-spacing: -0.01em;
    }
    
    .gov-subtitle {
        color: var(--muted-color);
        font-size: 0.9rem;
        margin-top: 0.25rem;
    }

    /* Civic Indicator Badges */
    .gov-badge-green {
        display: inline-block;
        background-color: var(--green-subtle);
        color: var(--green-gov);
        border: 1px solid var(--green-border);
        padding: 0.2rem 0.6rem;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        border-radius: 3px;
    }
    
    .gov-badge-saffron {
        display: inline-block;
        background-color: var(--saffron-subtle);
        color: var(--saffron-gov);
        border: 1px solid var(--saffron-border);
        padding: 0.2rem 0.6rem;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        border-radius: 3px;
    }

    /* Metric Panels */
    .gov-metric-box {
        background-color: #FFFFFF;
        border: 1px solid var(--border-color);
        border-radius: 4px;
        padding: 0.9rem 1.1rem;
        border-top: 3px solid #64748B;
    }
    .gov-metric-box.saffron {
        border-top: 3px solid var(--saffron-gov);
    }
    .gov-metric-box.green {
        border-top: 3px solid var(--green-gov);
    }

    .gov-metric-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        font-weight: 700;
        letter-spacing: 0.05em;
        color: var(--muted-color);
    }

    .gov-metric-number {
        font-size: 1.75rem;
        font-weight: 800;
        color: var(--navy-gov);
        margin: 0.15rem 0;
    }

    .gov-metric-subtext {
        font-size: 0.75rem;
        color: var(--muted-color);
    }

    /* Section Cards */
    .gov-card {
        background-color: #FFFFFF;
        border: 1px solid var(--border-color);
        border-radius: 4px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.25rem;
    }

    .gov-card-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: var(--navy-gov);
        margin: 0 0 0.35rem 0;
        border-bottom: 1px solid #E5E7EB;
        padding-bottom: 0.4rem;
    }

    /* Notice Panels */
    .gov-notice-saffron {
        background-color: var(--saffron-subtle);
        border-left: 4px solid var(--saffron-gov);
        border-top: 1px solid var(--saffron-border);
        border-right: 1px solid var(--saffron-border);
        border-bottom: 1px solid var(--saffron-border);
        padding: 0.85rem 1rem;
        font-size: 0.85rem;
        color: #7C2D12;
        border-radius: 2px;
        margin-bottom: 1rem;
    }

    .gov-notice-green {
        background-color: var(--green-subtle);
        border-left: 4px solid var(--green-gov);
        border-top: 1px solid var(--green-border);
        border-right: 1px solid var(--green-border);
        border-bottom: 1px solid var(--green-border);
        padding: 0.85rem 1rem;
        font-size: 0.85rem;
        color: #14532D;
        border-radius: 2px;
        margin-bottom: 1rem;
    }

    /* Sidebar Notice Containers */
    .gov-sidebar-section {
        background-color: #FFFFFF;
        border: 1px solid var(--border-color);
        border-radius: 4px;
        padding: 0.85rem 1rem;
        margin-bottom: 0.85rem;
    }
    
    .gov-sidebar-heading {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--navy-gov);
        margin: 0 0 0.35rem 0;
        border-bottom: 1px solid #E5E7EB;
        padding-bottom: 0.25rem;
    }

    /* Government Form Buttons */
    div.stButton > button:first-child {
        border-radius: 3px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.03em;
        font-size: 0.85rem;
        padding: 0.5rem 1rem;
    }

    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 2px solid #E5E7EB;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 3px 3px 0 0;
        font-weight: 600;
        font-size: 0.9rem;
        padding: 10px 18px;
    }
    .stTabs [aria-selected="true"] {
        color: var(--navy-gov) !important;
        border-bottom: 3px solid var(--saffron-gov) !important;
        background-color: #FFFFFF;
    }
</style>
""", unsafe_allow_html=True)

# Top civic tricolor rule
st.markdown('<div class="gov-top-bar"></div>', unsafe_allow_html=True)

# ==============================================================================
# DATA RETRIEVAL & CORRELATION
# ==============================================================================
lost_df = fetch_items("Lost_Items")
found_df = fetch_items("Found_Items")

# Update Gauges
LOST_GAUGE.set(len(lost_df))
FOUND_GAUGE.set(len(found_df))

# Compute algorithmic matches
matches = []
if not lost_df.empty and not found_df.empty:
    for _, lost_row in lost_df.iterrows():
        lost_words = set(w for w in lost_row['item'].lower().split() if len(w) > 2)
        for _, found_row in found_df.iterrows():
            found_words = set(w for w in found_row['item'].lower().split() if len(w) > 2)
            common_words = lost_words.intersection(found_words)
            same_route = (lost_row['route'].strip().lower() == found_row['route'].strip().lower())
            
            if len(common_words) > 0 or same_route:
                matches.append({
                    "Verification Status": "Route and Description Match" if (same_route and len(common_words) > 0) else ("Route Correlated" if same_route else f"Keyword Match ({', '.join(common_words)})"),
                    "Reported Lost Item": lost_row['item'],
                    "Date Reported Lost": lost_row['date'],
                    "Corridor / Route": lost_row['route'],
                    "Custodial Item": found_row['item'],
                    "Date Handed In": found_row['date'],
                    "Custodial Location": found_row['route']
                })

all_routes = set(lost_df['route'].tolist() + found_df['route'].tolist()) if (not lost_df.empty or not found_df.empty) else set()

# ==============================================================================
# GOVERNMENT HEADER BAR
# ==============================================================================
st.markdown("""
<div class="gov-header">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
        <div>
            <div class="gov-agency-title">Municipal Transit Authority | Public Property Grievance Division</div>
            <h1 class="gov-title">TransitRecover</h1>
            <div class="gov-subtitle">Centralized Registry for Lost and Found Articles Across Public Transit Networks</div>
        </div>
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <span class="gov-badge-green">Registry Online</span>
            <span class="gov-badge-saffron">Official Record System</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# FORMAL SUMMARY METRIC PANELS
# ==============================================================================
col_m1, col_m2, col_m3, col_m4 = st.columns(4)

with col_m1:
    st.markdown(f"""
    <div class="gov-metric-box saffron">
        <div class="gov-metric-label">Lost Property Notices</div>
        <div class="gov-metric-number">{len(lost_df)}</div>
        <div class="gov-metric-subtext">Active inquiries recorded</div>
    </div>
    """, unsafe_allow_html=True)

with col_m2:
    st.markdown(f"""
    <div class="gov-metric-box green">
        <div class="gov-metric-label">Secured Articles in Custody</div>
        <div class="gov-metric-number">{len(found_df)}</div>
        <div class="gov-metric-subtext">Deposited at station offices</div>
    </div>
    """, unsafe_allow_html=True)

with col_m3:
    st.markdown(f"""
    <div class="gov-metric-box">
        <div class="gov-metric-label">Active Transit Corridors</div>
        <div class="gov-metric-number">{len(all_routes)}</div>
        <div class="gov-metric-subtext">Rail, metro, and bus lines</div>
    </div>
    """, unsafe_allow_html=True)

with col_m4:
    st.markdown(f"""
    <div class="gov-metric-box">
        <div class="gov-metric-label">Correlated Match Candidates</div>
        <div class="gov-metric-number">{len(matches)}</div>
        <div class="gov-metric-subtext">Eligible for claim review</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# ==============================================================================
# MAIN NAVIGATION TABS (NO EMOJIS, FORMAL TITLES)
# ==============================================================================
tab_search, tab_lost, tab_found, tab_correlations = st.tabs([
    "Public Registry Search",
    "Lodge Lost Property Notice",
    "Register Found Property",
    "Correlation and Matches"
])

# ------------------------------------------------------------------------------
# TAB 1: REGISTRY SEARCH
# ------------------------------------------------------------------------------
with tab_search:
    st.markdown("""
    <div class="gov-card">
        <div class="gov-card-title">Search Public Property Records</div>
        <p style="margin: 0; color: #4B5563; font-size: 0.88rem;">
            Search the public registry for articles surrendered to station authorities, or inspect active missing property declarations filed by passengers.
        </p>
    </div>
    """, unsafe_allow_html=True)

    filter_c1, filter_c2 = st.columns([2, 1])
    with filter_c1:
        search_query = st.text_input(
            "Search by Article Keyword or Description",
            placeholder="Enter search terms (e.g. umbrella, backpack, wallet, glasses, electronics)..."
        ).strip().lower()
    with filter_c2:
        route_options = ["All Transit Lines"] + sorted(list(all_routes)) if all_routes else ["All Transit Lines"]
        selected_route = st.selectbox("Filter by Transit Corridor / Route", route_options)

    col_found_view, col_lost_view = st.columns(2)

    with col_found_view:
        st.markdown("""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <span style="font-weight: 700; color: #116828; font-size: 0.95rem;">Articles in Official Custody</span>
            <span class="gov-badge-green">Table: Found_Items</span>
        </div>
        """, unsafe_allow_html=True)

        filtered_found = found_df.copy()
        if not filtered_found.empty:
            if search_query:
                filtered_found = filtered_found[filtered_found['item'].str.lower().str.contains(search_query)]
            if selected_route != "All Transit Lines":
                filtered_found = filtered_found[filtered_found['route'] == selected_route]

        if filtered_found.empty:
            st.info("No recorded articles match the specified search parameters.")
        else:
            display_found = filtered_found.rename(columns={
                'id': 'Record ID',
                'item': 'Article Description',
                'date': 'Date Surrendered',
                'route': 'Station / Transit Route'
            })
            st.dataframe(
                display_found,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Record ID": st.column_config.NumberColumn(width="small"),
                    "Article Description": st.column_config.TextColumn(width="medium"),
                    "Date Surrendered": st.column_config.TextColumn(width="small"),
                    "Station / Transit Route": st.column_config.TextColumn(width="medium")
                }
            )
            st.caption("Note: Claimants must cite the Record ID and furnish verification of ownership at the station counter.")

    with col_lost_view:
        st.markdown("""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <span style="font-weight: 700; color: #9A3412; font-size: 0.95rem;">Missing Property Notices Filed</span>
            <span class="gov-badge-saffron">Table: Lost_Items</span>
        </div>
        """, unsafe_allow_html=True)

        filtered_lost = lost_df.copy()
        if not filtered_lost.empty:
            if search_query:
                filtered_lost = filtered_lost[filtered_lost['item'].str.lower().str.contains(search_query)]
            if selected_route != "All Transit Lines":
                filtered_lost = filtered_lost[filtered_lost['route'] == selected_route]

        if filtered_lost.empty:
            st.info("No missing property notices match the specified search parameters.")
        else:
            display_lost = filtered_lost.rename(columns={
                'id': 'Notice ID',
                'item': 'Article Description',
                'date': 'Date of Loss',
                'route': 'Transit Route'
            })
            st.dataframe(
                display_lost,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Notice ID": st.column_config.NumberColumn(width="small"),
                    "Article Description": st.column_config.TextColumn(width="medium"),
                    "Date of Loss": st.column_config.TextColumn(width="small"),
                    "Transit Route": st.column_config.TextColumn(width="medium")
                }
            )
            st.caption("Note: Public inquiries remain active until verified restoration or expiry of the filing cycle.")

# ------------------------------------------------------------------------------
# TAB 2: LODGE LOST PROPERTY NOTICE
# ------------------------------------------------------------------------------
with tab_lost:
    st.markdown("""
    <div class="gov-notice-saffron">
        <b>Official Notice:</b> Passengers reporting missing items must provide precise descriptions. False declarations or fraudulent ownership claims are subject to municipal transit regulations.
    </div>
    """, unsafe_allow_html=True)

    with st.form("form_report_lost", clear_on_submit=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            lost_item_name = st.text_input(
                "Article Description (Make, Color, Model, Distinct Markings) *",
                placeholder="e.g. Black Lenovo ThinkPad laptop with orange sticker, Leather bi-fold wallet"
            ).strip()
            lost_item_route = st.text_input(
                "Transit Route / Line / Train Number / Vehicle Number *",
                placeholder="e.g. Metro Blue Line (Coach 3), Suburban Express Local, Bus Route 412"
            ).strip()
        with col_f2:
            lost_item_date = st.date_input("Date of Occurrence *", value=date.today(), max_value=date.today())
            st.markdown("""
            <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 3px; padding: 0.75rem; font-size: 0.8rem; color: #475569; margin-top: 1.5rem;">
                <b>Filing Instructions:</b> State any identifiable particulars such as serial numbers, engraved monograms, or exterior scratches to assist verification officers.
            </div>
            """, unsafe_allow_html=True)

        submitted_lost = st.form_submit_button("Submit Missing Property Notice", use_container_width=True)

        if submitted_lost:
            if not lost_item_name:
                st.error("Submission failed: Article description is mandatory.")
            elif not lost_item_route:
                st.error("Submission failed: Transit route or line must be specified.")
            else:
                add_lost_item(lost_item_name, str(lost_item_date), lost_item_route)
                st.success(f"Notice registered successfully. Record for '{lost_item_name}' added to Lost_Items.")
                st.rerun()

# ------------------------------------------------------------------------------
# TAB 3: REGISTER FOUND PROPERTY
# ------------------------------------------------------------------------------
with tab_found:
    st.markdown("""
    <div class="gov-notice-green">
        <b>Custodial Protocol:</b> Surrendered articles must be deposited with the authorized Station Master or Transit Operations Desk within 24 hours of discovery.
    </div>
    """, unsafe_allow_html=True)

    with st.form("form_report_found", clear_on_submit=True):
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            found_item_name = st.text_input(
                "Surrendered Article Description *",
                placeholder="e.g. Silver metallic water flask, Set of brass door keys with tag"
            ).strip()
            found_item_route = st.text_input(
                "Recovery Location / Station Platform / Vehicle Corridor *",
                placeholder="e.g. Station Concourse Platform 2, Bus Terminal Bay 4, Metro Green Line"
            ).strip()
        with col_g2:
            found_item_date = st.date_input("Date of Recovery *", value=date.today(), max_value=date.today())
            st.markdown("""
            <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 3px; padding: 0.75rem; font-size: 0.8rem; color: #475569; margin-top: 1.5rem;">
                <b>Official Acknowledgment:</b> Depositing lost items with authorized personnel ensures transparent logging and prevents unlawful misappropriation.
            </div>
            """, unsafe_allow_html=True)

        submitted_found = st.form_submit_button("Register Article into Official Custody", use_container_width=True)

        if submitted_found:
            if not found_item_name:
                st.error("Submission failed: Description of the article is mandatory.")
            elif not found_item_route:
                st.error("Submission failed: Recovery location or transit line must be specified.")
            else:
                add_found_item(found_item_name, str(found_item_date), found_item_route)
                st.success(f"Article successfully logged. Record for '{found_item_name}' added to Found_Items.")
                st.rerun()

# ------------------------------------------------------------------------------
# TAB 4: CORRELATION AND MATCHES
# ------------------------------------------------------------------------------
with tab_correlations:
    st.markdown("""
    <div class="gov-card">
        <div class="gov-card-title">System Correlated Match Recommendations</div>
        <p style="margin: 0; color: #4B5563; font-size: 0.88rem;">
            The central registry programmatically correlates active missing property declarations against newly registered custodial articles based on geographic corridor and descriptive parameters.
        </p>
    </div>
    """, unsafe_allow_html=True)

    if not matches:
        st.info("No system correlations detected between active lost notices and surrendered articles at this time.")
    else:
        st.success(f"Total correlated entries identified: {len(matches)}. Review records below:")
        match_df = pd.DataFrame(matches)
        st.dataframe(match_df, use_container_width=True, hide_index=True)
        
        with st.expander("Claim Verification and Retrieval Protocol"):
            st.markdown("""
            1. **Identification Verification:** Claimants must present official government-issued photo identification (Aadhaar, Passport, Driver's License, or Voter ID).
            2. **Proof of Ownership:** Claimants must supply descriptive confirmation (e.g. proof of purchase, serial number documentation, unlock credentials, or detailed specifications of contents).
            3. **Physical Custody Handover:** Processing occurs exclusively at the Central Lost Property Counter during designated public hours.
            """)

# ==============================================================================
# FORMAL GOVERNMENT SIDEBAR
# ==============================================================================
with st.sidebar:
    st.markdown("""
    <div style="padding: 0.5rem 0 0.85rem 0; border-bottom: 2px solid #E5E7EB; margin-bottom: 1rem;">
        <div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #64748B;">
            Public Transit Administration
        </div>
        <div style="font-size: 1.25rem; font-weight: 800; color: #0B2545;">
            TransitRecover
        </div>
        <div style="font-size: 0.78rem; color: #475569;">
            Central Property Custody Service
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="gov-sidebar-section">
        <div class="gov-sidebar-heading">Central Lost Property Office</div>
        <div style="font-size: 0.8rem; color: #374151; line-height: 1.45;">
            <b>Address:</b> Public Concourse, Ground Floor, Central Transit Terminal<br>
            <b>Public Hours:</b> 08:00 to 20:00 (All Days)<br>
            <b>Official Helpline:</b> 1800-11-TRANSIT<br>
            <b>Email:</b> property.custody@transit.gov.in
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="gov-sidebar-section" style="border-left: 3px solid #116828;">
        <div class="gov-sidebar-heading" style="color: #116828;">Claim Procedure</div>
        <ol style="margin: 0; padding-left: 1.1rem; font-size: 0.78rem; color: #374151; line-height: 1.45;">
            <li>Identify article in Registry Search</li>
            <li>Note designated Record ID number</li>
            <li>Produce government photo identification</li>
            <li>Furnish satisfactory proof of ownership</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="gov-sidebar-section" style="border-left: 3px solid #E06A00;">
        <div class="gov-sidebar-heading" style="color: #9A3412;">Statutory Holding Period</div>
        <div style="font-size: 0.78rem; color: #374151; line-height: 1.4;">
            Unclaimed articles are retained in municipal custody for thirty (30) calendar days prior to statutory auction or disposal under transit property by-laws.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Refresh Registry Data", use_container_width=True):
        st.rerun()
