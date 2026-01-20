"""
FRAGEBOGEN-APP FÜR KANZLEI RHM - STREAMLIT CLOUD EDITION
========================================================
Optimiert für Streamlit Cloud mit maximalem Custom Design
"""

import streamlit as st
import sqlite3
import json
from datetime import datetime, timedelta
import secrets
from pathlib import Path
import os

# ============================================================================
# SEITEN-KONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Fragebogen-System | Kanzlei RHM",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================================
# 🎨 CUSTOM CSS - HIER KÖNNEN SIE DAS DESIGN ANPASSEN
# ============================================================================

def load_css():
    st.markdown("""
    <style>
    /* ========================================
       🎨 FARBEN - Hier anpassen!
       ======================================== */
    :root {
        --primary: #f59e0b;           /* Hauptfarbe (Amber) */
        --primary-hover: #d97706;     /* Hover-Farbe */
        --bg-main: #0f172a;           /* Haupthintergrund */
        --bg-card: rgba(30, 41, 59, 0.7);  /* Karten */
        --bg-input: rgba(30, 41, 59, 0.9); /* Eingabefelder */
        --border: rgba(71, 85, 105, 0.5);  /* Rahmen */
        --text-primary: #f1f5f9;      /* Haupttext */
        --text-secondary: #94a3b8;    /* Sekundärtext */
        --success: #22c55e;           /* Erfolg */
        --warning: #f59e0b;           /* Warnung */
        --error: #ef4444;             /* Fehler */
    }
    
    /* ========================================
       VERSTECKE STREAMLIT-ELEMENTE
       ======================================== */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* ========================================
       SCHRIFTART
       ======================================== */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* ========================================
       HINTERGRUND
       ======================================== */
    .stApp {
        background: linear-gradient(135deg, var(--bg-main) 0%, #1e293b 50%, var(--bg-main) 100%);
    }
    
    /* ========================================
       NAVIGATION HEADER
       ======================================== */
    .custom-header {
        background: rgba(15, 23, 42, 0.95);
        backdrop-filter: blur(20px);
        border-bottom: 1px solid rgba(251, 191, 36, 0.2);
        padding: 1rem 2rem;
        margin: -1rem -1rem 2rem -1rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    
    .logo-container {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .logo-icon {
        width: 45px;
        height: 45px;
        background: linear-gradient(135deg, var(--primary) 0%, #ea580c 100%);
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        box-shadow: 0 4px 15px rgba(245, 158, 11, 0.3);
    }
    
    .logo-text {
        color: var(--text-primary);
        font-size: 1.25rem;
        font-weight: 600;
    }
    
    .logo-subtext {
        color: var(--text-secondary);
        font-size: 0.75rem;
    }
    
    /* ========================================
       KARTEN
       ======================================== */
    .custom-card {
        background: var(--bg-card);
        backdrop-filter: blur(10px);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }
    
    .custom-card:hover {
        border-color: rgba(251, 191, 36, 0.5);
        transform: translateY(-3px);
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
    }
    
    /* ========================================
       STATISTIK-KARTEN
       ======================================== */
    .stat-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 1.5rem;
        text-align: center;
        transition: all 0.3s ease;
    }
    
    .stat-card:hover {
        border-color: rgba(251, 191, 36, 0.4);
        transform: scale(1.02);
    }
    
    .stat-value {
        font-size: 3rem;
        font-weight: 700;
        background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        line-height: 1.2;
    }
    
    .stat-label {
        color: var(--text-secondary);
        font-size: 0.9rem;
        margin-top: 0.5rem;
        font-weight: 500;
    }
    
    /* ========================================
       BUTTONS
       ======================================== */
    .stButton > button {
        background: linear-gradient(135deg, var(--primary) 0%, #ea580c 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 600 !important;
        font-family: 'Inter', sans-serif !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(245, 158, 11, 0.3) !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 25px rgba(245, 158, 11, 0.5) !important;
    }
    
    .stButton > button:active {
        transform: translateY(0) !important;
    }
    
    /* Secondary Buttons */
    div[data-testid="column"]:nth-child(n+2) .stButton > button {
        background: rgba(71, 85, 105, 0.5) !important;
        border: 1px solid var(--border) !important;
        box-shadow: none !important;
    }
    
    div[data-testid="column"]:nth-child(n+2) .stButton > button:hover {
        background: rgba(71, 85, 105, 0.7) !important;
        border-color: var(--primary) !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3) !important;
    }
    
    /* ========================================
       FORMULARE
       ======================================== */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stNumberInput > div > div > input {
        background: var(--bg-input) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        color: var(--text-primary) !important;
        font-family: 'Inter', sans-serif !important;
        padding: 0.75rem 1rem !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    .stNumberInput > div > div > input:focus {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2) !important;
    }
    
    .stSelectbox > div > div {
        background: var(--bg-input) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
    }
    
    /* Labels */
    .stTextInput > label,
    .stTextArea > label,
    .stSelectbox > label,
    .stNumberInput > label,
    .stDateInput > label,
    .stCheckbox > label {
        color: var(--text-secondary) !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
    }
    
    /* ========================================
       TABS
       ======================================== */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(30, 41, 59, 0.5);
        border-radius: 12px;
        padding: 5px;
        gap: 5px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        border-radius: 8px !important;
        color: var(--text-secondary) !important;
        font-weight: 500 !important;
        padding: 10px 20px !important;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, var(--primary) 0%, #ea580c 100%) !important;
        color: white !important;
    }
    
    /* ========================================
       EXPANDER
       ======================================== */
    .streamlit-expanderHeader {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        color: var(--text-primary) !important;
        font-weight: 500 !important;
    }
    
    .streamlit-expanderHeader:hover {
        border-color: var(--primary) !important;
    }
    
    .streamlit-expanderContent {
        background: rgba(15, 23, 42, 0.5) !important;
        border: 1px solid var(--border) !important;
        border-top: none !important;
        border-radius: 0 0 12px 12px !important;
    }
    
    /* ========================================
       BADGES
       ======================================== */
    .badge {
        display: inline-flex;
        align-items: center;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        gap: 6px;
    }
    
    .badge-amber {
        background: rgba(251, 191, 36, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(251, 191, 36, 0.3);
    }
    
    .badge-green {
        background: rgba(34, 197, 94, 0.15);
        color: #22c55e;
        border: 1px solid rgba(34, 197, 94, 0.3);
    }
    
    .badge-blue {
        background: rgba(59, 130, 246, 0.15);
        color: #3b82f6;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }
    
    .badge-purple {
        background: rgba(168, 85, 247, 0.15);
        color: #a855f7;
        border: 1px solid rgba(168, 85, 247, 0.3);
    }
    
    .badge-red {
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    
    /* ========================================
       ÜBERSCHRIFTEN
       ======================================== */
    h1 {
        color: var(--text-primary) !important;
        font-weight: 700 !important;
        font-size: 2.25rem !important;
    }
    
    h2 {
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        font-size: 1.5rem !important;
    }
    
    h3, h4 {
        color: var(--text-primary) !important;
        font-weight: 600 !important;
    }
    
    p {
        color: var(--text-secondary) !important;
    }
    
    /* ========================================
       DIVIDER
       ======================================== */
    hr {
        border-color: var(--border) !important;
        margin: 2rem 0 !important;
    }
    
    /* ========================================
       ALERTS / NOTIFICATIONS
       ======================================== */
    .stAlert {
        background: var(--bg-card) !important;
        border-radius: 12px !important;
    }
    
    .stSuccess {
        border-left: 4px solid var(--success) !important;
    }
    
    .stWarning {
        border-left: 4px solid var(--warning) !important;
    }
    
    .stError {
        border-left: 4px solid var(--error) !important;
    }
    
    .stInfo {
        border-left: 4px solid #3b82f6 !important;
    }
    
    /* ========================================
       METRIKEN
       ======================================== */
    [data-testid="stMetricValue"] {
        color: var(--text-primary) !important;
        font-size: 2rem !important;
    }
    
    [data-testid="stMetricLabel"] {
        color: var(--text-secondary) !important;
    }
    
    /* ========================================
       SCROLLBAR
       ======================================== */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(30, 41, 59, 0.5);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: rgba(100, 116, 139, 0.5);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(100, 116, 139, 0.8);
    }
    
    /* ========================================
       ANIMATIONEN
       ======================================== */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    
    .fade-in {
        animation: fadeInUp 0.5s ease forwards;
    }
    
    /* ========================================
       ERFOLGS-BILDSCHIRM
       ======================================== */
    .success-container {
        text-align: center;
        padding: 3rem;
        animation: fadeInUp 0.5s ease;
    }
    
    .success-icon {
        width: 100px;
        height: 100px;
        background: rgba(34, 197, 94, 0.2);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 1.5rem;
        font-size: 50px;
        border: 2px solid rgba(34, 197, 94, 0.3);
    }
    
    /* ========================================
       RESPONSIVE
       ======================================== */
    @media (max-width: 768px) {
        .stat-value {
            font-size: 2rem;
        }
        
        .custom-card {
            padding: 1rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# ============================================================================
# KONFIGURATION
# ============================================================================

DB_PATH = Path("fragebogen_data.db")
DEFAULT_EMAIL = "info@ra-rhm.de"

# ============================================================================
# DATENBANK
# ============================================================================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS forms (
        id TEXT PRIMARY KEY, title TEXT, description TEXT, category TEXT,
        access_mode TEXT, recipient_email TEXT, fields_json TEXT, is_active INTEGER DEFAULT 1
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS submissions (
        id TEXT PRIMARY KEY, form_id TEXT, data_json TEXT, recipient_email TEXT,
        status TEXT DEFAULT 'pending', submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        consent_given INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS employees (
        id TEXT PRIMARY KEY, name TEXT, email TEXT UNIQUE, role TEXT, is_active INTEGER DEFAULT 1
    )''')
    conn.commit()
    
    # Demo-Daten
    if c.execute("SELECT COUNT(*) FROM forms").fetchone()[0] == 0:
        demo_forms = [
            {
                "id": "kuendigung",
                "title": "Kündigungsschutzklage - Arbeitnehmer",
                "description": "Erfassung aller relevanten Daten für eine Kündigungsschutzklage",
                "category": "arbeitsrecht",
                "access_mode": "public",
                "fields": [
                    {"id": "anrede", "type": "select", "label": "Anrede", "required": True, "options": ["Herr", "Frau", "Divers"]},
                    {"id": "vorname", "type": "text", "label": "Vorname", "required": True},
                    {"id": "nachname", "type": "text", "label": "Nachname", "required": True},
                    {"id": "email", "type": "text", "label": "E-Mail", "required": True},
                    {"id": "telefon", "type": "text", "label": "Telefon", "required": False},
                    {"id": "strasse", "type": "text", "label": "Straße & Hausnummer", "required": True},
                    {"id": "plz", "type": "text", "label": "PLZ", "required": True},
                    {"id": "ort", "type": "text", "label": "Ort", "required": True},
                    {"id": "arbeitgeber", "type": "text", "label": "Arbeitgeber", "required": True},
                    {"id": "eintrittsdatum", "type": "date", "label": "Eintrittsdatum", "required": True},
                    {"id": "position", "type": "text", "label": "Position / Tätigkeit", "required": True},
                    {"id": "bruttogehalt", "type": "number", "label": "Bruttogehalt (€/Monat)", "required": True},
                    {"id": "kuendigungsdatum", "type": "date", "label": "Kündigungsdatum", "required": True},
                    {"id": "kuendigungsart", "type": "select", "label": "Art der Kündigung", "required": True, 
                     "options": ["Ordentliche Kündigung", "Außerordentliche Kündigung", "Änderungskündigung"]},
                    {"id": "rsv", "type": "select", "label": "Rechtsschutzversicherung?", "required": True, "options": ["Ja", "Nein"]},
                    {"id": "anmerkungen", "type": "textarea", "label": "Weitere Anmerkungen", "required": False},
                ]
            },
            {
                "id": "zeugnis",
                "title": "Zeugniskorrektur",
                "description": "Fragebogen für Zeugnisberichtigung",
                "category": "arbeitsrecht",
                "access_mode": "invite",
                "fields": [
                    {"id": "vorname", "type": "text", "label": "Vorname", "required": True},
                    {"id": "nachname", "type": "text", "label": "Nachname", "required": True},
                    {"id": "email", "type": "text", "label": "E-Mail", "required": True},
                    {"id": "arbeitgeber", "type": "text", "label": "Arbeitgeber", "required": True},
                    {"id": "position", "type": "text", "label": "Position", "required": True},
                    {"id": "zeugnis_art", "type": "select", "label": "Zeugnisart", "required": True,
                     "options": ["Einfaches Zeugnis", "Qualifiziertes Zeugnis", "Zwischenzeugnis"]},
                    {"id": "probleme", "type": "textarea", "label": "Was stört Sie am Zeugnis?", "required": True},
                ]
            },
            {
                "id": "lohnklage",
                "title": "Lohnklage",
                "description": "Ausstehende Gehaltszahlungen einklagen",
                "category": "arbeitsrecht",
                "access_mode": "public",
                "fields": [
                    {"id": "vorname", "type": "text", "label": "Vorname", "required": True},
                    {"id": "nachname", "type": "text", "label": "Nachname", "required": True},
                    {"id": "email", "type": "text", "label": "E-Mail", "required": True},
                    {"id": "arbeitgeber", "type": "text", "label": "Arbeitgeber", "required": True},
                    {"id": "bruttogehalt", "type": "number", "label": "Monatliches Bruttogehalt (€)", "required": True},
                    {"id": "ausstehend", "type": "text", "label": "Ausstehende Monate", "required": True},
                    {"id": "betrag", "type": "number", "label": "Gesamtbetrag (€)", "required": True},
                ]
            }
        ]
        
        for form in demo_forms:
            fields = form.pop("fields")
            c.execute("INSERT INTO forms (id, title, description, category, access_mode, recipient_email, fields_json) VALUES (?,?,?,?,?,?,?)",
                     (form["id"], form["title"], form.get("description"), form.get("category"), 
                      form.get("access_mode"), DEFAULT_EMAIL, json.dumps(fields)))
        
        for emp in [("e1", "RA Müller", "mueller@ra-rhm.de", "Partner"), 
                    ("e2", "RA Schmidt", "schmidt@ra-rhm.de", "Anwalt"),
                    ("e3", "Sekretariat", "info@ra-rhm.de", "Sekretariat")]:
            c.execute("INSERT INTO employees (id, name, email, role) VALUES (?,?,?,?)", emp)
        
        conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def load_forms():
    conn = get_db()
    rows = conn.execute("SELECT * FROM forms WHERE is_active = 1").fetchall()
    conn.close()
    forms = []
    for r in rows:
        f = dict(r)
        f["fields"] = json.loads(f["fields_json"]) if f["fields_json"] else []
        forms.append(f)
    return forms

def load_submissions():
    conn = get_db()
    rows = conn.execute("""
        SELECT s.*, f.title as form_title FROM submissions s 
        LEFT JOIN forms f ON s.form_id = f.id 
        ORDER BY s.submitted_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def load_employees():
    conn = get_db()
    rows = conn.execute("SELECT * FROM employees WHERE is_active = 1").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_submission(form_id, data, recipient, consent):
    conn = get_db()
    sub_id = secrets.token_hex(8)
    conn.execute(
        "INSERT INTO submissions (id, form_id, data_json, recipient_email, consent_given) VALUES (?,?,?,?,?)",
        (sub_id, form_id, json.dumps(data), recipient, 1 if consent else 0)
    )
    conn.commit()
    conn.close()
    return sub_id

def format_date(d):
    if not d: return ""
    try:
        if isinstance(d, str):
            d = datetime.fromisoformat(d.replace("Z", ""))
        return d.strftime("%d.%m.%Y")
    except:
        return str(d)

# ============================================================================
# UI KOMPONENTEN
# ============================================================================

def render_header():
    """Custom Header mit Logo und Navigation."""
    st.markdown("""
    <div class="custom-header">
        <div class="logo-container">
            <div class="logo-icon">⚖️</div>
            <div>
                <div class="logo-text">Fragebogen-System</div>
                <div class="logo-subtext">Kanzlei RHM</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_stat_card(value, label, icon):
    """Statistik-Karte."""
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-value">{value}</div>
        <div class="stat-label">{icon} {label}</div>
    </div>
    """, unsafe_allow_html=True)

def render_form_card(form):
    """Fragebogen-Karte."""
    fields = form.get("fields", [])
    access_icon = "🌐" if form.get("access_mode") == "public" else "🔗" if form.get("access_mode") == "invite" else "📧"
    access_class = "badge-green" if form.get("access_mode") == "public" else "badge-blue" if form.get("access_mode") == "invite" else "badge-purple"
    access_text = "Öffentlich" if form.get("access_mode") == "public" else "Einladung" if form.get("access_mode") == "invite" else "E-Mail"
    
    st.markdown(f"""
    <div class="custom-card">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
            <div style="width: 50px; height: 50px; background: linear-gradient(135deg, rgba(251, 191, 36, 0.2) 0%, rgba(234, 88, 12, 0.2) 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px;">📋</div>
            <span class="badge {access_class}">{access_icon} {access_text}</span>
        </div>
        <h3 style="margin: 0 0 0.5rem 0; color: var(--text-primary); font-size: 1.1rem;">{form.get('title', 'Fragebogen')}</h3>
        <p style="margin: 0; font-size: 0.9rem;">{form.get('description', 'Keine Beschreibung')} • {len(fields)} Felder</p>
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# SEITEN
# ============================================================================

def page_dashboard():
    render_header()
    
    st.markdown("# 🏠 Dashboard")
    st.markdown("Übersicht über Ihre Fragebögen und Eingaben")
    
    forms = load_forms()
    submissions = load_submissions()
    pending = [s for s in submissions if s.get("status") == "pending"]
    
    # Statistiken
    cols = st.columns(4)
    with cols[0]:
        render_stat_card(len(forms), "Fragebögen", "📋")
    with cols[1]:
        render_stat_card(len(submissions), "Eingaben", "📊")
    with cols[2]:
        week_ago = datetime.now() - timedelta(days=7)
        recent = len([s for s in submissions if datetime.fromisoformat(s["submitted_at"].replace("Z","")) > week_ago])
        render_stat_card(recent, "Diese Woche", "📅")
    with cols[3]:
        render_stat_card(len(pending), "Ausstehend", "⏳")
    
    st.markdown("---")
    
    # Schnellaktionen
    st.markdown("### ⚡ Schnellaktionen")
    
    cols = st.columns(3)
    
    with cols[0]:
        st.markdown("""
        <div class="custom-card">
            <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
                <div style="font-size: 2rem;">➕</div>
                <div>
                    <strong style="color: var(--text-primary);">Neuer Fragebogen</strong><br>
                    <span style="font-size: 0.85rem;">Erstellen oder importieren</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Erstellen", key="quick_create", use_container_width=True):
            st.session_state.page = "forms"
            st.rerun()
    
    with cols[1]:
        st.markdown("""
        <div class="custom-card">
            <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
                <div style="font-size: 2rem;">🔗</div>
                <div>
                    <strong style="color: var(--text-primary);">Einladungslink</strong><br>
                    <span style="font-size: 0.85rem;">Link für Mandanten erstellen</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Link erstellen", key="quick_link", use_container_width=True):
            st.session_state.page = "forms"
            st.rerun()
    
    with cols[2]:
        st.markdown("""
        <div class="custom-card">
            <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
                <div style="font-size: 2rem;">📧</div>
                <div>
                    <strong style="color: var(--text-primary);">E-Mail senden</strong><br>
                    <span style="font-size: 0.85rem;">Fragebogen per E-Mail</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("E-Mail senden", key="quick_email", use_container_width=True):
            st.session_state.page = "forms"
            st.rerun()
    
    st.markdown("---")
    
    # Letzte Eingaben
    st.markdown("### 📥 Letzte Eingaben")
    
    if submissions:
        for sub in submissions[:5]:
            data = json.loads(sub.get("data_json", "{}")) if sub.get("data_json") else {}
            name = f"{data.get('vorname', '')} {data.get('nachname', '')}".strip() or "Unbekannt"
            status_class = "badge-amber" if sub.get("status") == "pending" else "badge-green"
            status_text = "Offen" if sub.get("status") == "pending" else "Bearbeitet"
            
            st.markdown(f"""
            <div class="custom-card" style="padding: 1rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong style="color: var(--text-primary);">{sub.get('form_title', 'Fragebogen')}</strong>
                        <span style="margin-left: 8px;">— {name}</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 1rem;">
                        <span style="font-size: 0.85rem;">{format_date(sub.get('submitted_at'))}</span>
                        <span class="badge {status_class}">{status_text}</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Noch keine Eingaben vorhanden.")

def page_forms():
    render_header()
    
    st.markdown("# 📋 Fragebögen")
    
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("➕ Neu", use_container_width=True):
            st.info("Formular-Editor wird implementiert...")
    
    st.markdown("---")
    
    forms = load_forms()
    
    if not forms:
        st.info("Noch keine Fragebögen vorhanden.")
        return
    
    # Fragebögen in Grid anzeigen
    cols = st.columns(3)
    for i, form in enumerate(forms):
        with cols[i % 3]:
            render_form_card(form)
            
            btn_cols = st.columns(3)
            with btn_cols[0]:
                if st.button("👁️", key=f"preview_{form['id']}", help="Vorschau", use_container_width=True):
                    st.session_state.preview_form = form
                    st.session_state.page = "fill"
                    st.rerun()
            with btn_cols[1]:
                if st.button("🔗", key=f"link_{form['id']}", help="Link erstellen", use_container_width=True):
                    token = secrets.token_urlsafe(16)
                    st.code(f"?form={form['id']}&token={token}", language=None)
            with btn_cols[2]:
                if st.button("📧", key=f"email_{form['id']}", help="Per E-Mail senden", use_container_width=True):
                    st.info("E-Mail-Dialog...")

def page_fill_form():
    if "preview_form" not in st.session_state:
        st.session_state.page = "forms"
        st.rerun()
        return
    
    form = st.session_state.preview_form
    fields = form.get("fields", [])
    employees = load_employees()
    
    render_header()
    
    if st.button("← Zurück zur Übersicht"):
        st.session_state.page = "forms"
        del st.session_state.preview_form
        st.rerun()
    
    st.markdown(f"# 📋 {form.get('title', 'Fragebogen')}")
    if form.get("description"):
        st.markdown(form["description"])
    
    st.markdown("---")
    
    # DSGVO Hinweis
    with st.expander("🔒 Datenschutzhinweis"):
        st.markdown("""
        Ihre Daten werden ausschließlich zur Bearbeitung Ihrer Anfrage verwendet 
        und gemäß DSGVO verarbeitet. Sie haben jederzeit das Recht auf Auskunft, 
        Berichtigung und Löschung Ihrer Daten.
        
        **Verantwortlicher:** Kanzlei RHM, Musterstraße 1, 10115 Berlin
        """)
    
    with st.form("questionnaire"):
        form_data = {}
        
        # Felder in 2 Spalten
        for i in range(0, len(fields), 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                if i + j < len(fields):
                    field = fields[i + j]
                    with col:
                        label = field["label"] + (" *" if field.get("required") else "")
                        
                        if field["type"] == "select":
                            form_data[field["id"]] = st.selectbox(label, [""] + field.get("options", []), key=f"f_{field['id']}")
                        elif field["type"] == "textarea":
                            form_data[field["id"]] = st.text_area(label, key=f"f_{field['id']}")
                        elif field["type"] == "date":
                            form_data[field["id"]] = st.date_input(label, value=None, key=f"f_{field['id']}")
                        elif field["type"] == "number":
                            form_data[field["id"]] = st.number_input(label, min_value=0, key=f"f_{field['id']}")
                        else:
                            form_data[field["id"]] = st.text_input(label, key=f"f_{field['id']}")
        
        st.markdown("---")
        
        # Empfänger
        st.markdown("### 📧 Ergebnisse senden an:")
        emp_options = ["Standard (info@ra-rhm.de)"] + [f"{e['name']} ({e['email']})" for e in employees]
        selected_emp = st.selectbox("Mitarbeiter auswählen", emp_options)
        
        # Einwilligung
        consent = st.checkbox("✅ Ich stimme der Verarbeitung meiner Daten gemäß Datenschutzerklärung zu. *")
        
        submitted = st.form_submit_button("📤 Absenden", type="primary", use_container_width=True)
        
        if submitted:
            errors = []
            for field in fields:
                if field.get("required") and not form_data.get(field["id"]):
                    errors.append(f"'{field['label']}' ist erforderlich")
            
            if not consent:
                errors.append("Bitte stimmen Sie der Datenschutzerklärung zu")
            
            if errors:
                for e in errors:
                    st.error(e)
            else:
                # Daten konvertieren
                for k, v in form_data.items():
                    if hasattr(v, 'strftime'):
                        form_data[k] = v.strftime("%Y-%m-%d")
                
                recipient = DEFAULT_EMAIL
                if selected_emp != emp_options[0]:
                    recipient = selected_emp.split("(")[-1].rstrip(")")
                
                save_submission(form["id"], form_data, recipient, consent)
                
                st.balloons()
                st.markdown("""
                <div class="success-container">
                    <div class="success-icon">✅</div>
                    <h2 style="color: var(--text-primary);">Vielen Dank!</h2>
                    <p>Ihre Angaben wurden erfolgreich übermittelt.<br>Wir melden uns in Kürze bei Ihnen.</p>
                </div>
                """, unsafe_allow_html=True)

def page_submissions():
    render_header()
    
    st.markdown("# 📊 Eingaben")
    
    submissions = load_submissions()
    
    col1, col2 = st.columns([4, 1])
    with col2:
        status_filter = st.selectbox("Filter", ["Alle", "Offen", "Bearbeitet"], label_visibility="collapsed")
    
    if status_filter == "Offen":
        submissions = [s for s in submissions if s.get("status") == "pending"]
    elif status_filter == "Bearbeitet":
        submissions = [s for s in submissions if s.get("status") != "pending"]
    
    st.markdown("---")
    
    if not submissions:
        st.info("Keine Eingaben gefunden.")
        return
    
    for sub in submissions:
        data = json.loads(sub.get("data_json", "{}")) if sub.get("data_json") else {}
        name = f"{data.get('vorname', '')} {data.get('nachname', '')}".strip() or "Unbekannt"
        
        with st.expander(f"**{sub.get('form_title', 'Fragebogen')}** — {name} ({format_date(sub.get('submitted_at'))})"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📝 Eingabedaten:**")
                for k, v in data.items():
                    st.markdown(f"• **{k}:** {v}")
            
            with col2:
                st.markdown("**ℹ️ Meta-Daten:**")
                status_emoji = "🟡" if sub.get("status") == "pending" else "🟢"
                st.markdown(f"• **Status:** {status_emoji} {'Offen' if sub.get('status') == 'pending' else 'Bearbeitet'}")
                st.markdown(f"• **Empfänger:** {sub.get('recipient_email', 'Standard')}")
                st.markdown(f"• **DSGVO:** {'✅ Einwilligung' if sub.get('consent_given') else '❌ Keine'}")
                
                if sub.get("status") == "pending":
                    if st.button("✅ Als bearbeitet markieren", key=f"mark_{sub['id']}"):
                        conn = get_db()
                        conn.execute("UPDATE submissions SET status = 'processed' WHERE id = ?", (sub["id"],))
                        conn.commit()
                        conn.close()
                        st.rerun()

def page_settings():
    render_header()
    
    st.markdown("# ⚙️ Einstellungen")
    
    tab1, tab2, tab3 = st.tabs(["👥 Mitarbeiter", "📧 E-Mail", "🔒 DSGVO"])
    
    with tab1:
        employees = load_employees()
        
        for emp in employees:
            cols = st.columns([2, 2, 1, 0.5])
            with cols[0]:
                st.text(emp["name"])
            with cols[1]:
                st.text(emp["email"])
            with cols[2]:
                st.text(emp.get("role", "-"))
            with cols[3]:
                if st.button("🗑️", key=f"del_{emp['id']}"):
                    conn = get_db()
                    conn.execute("UPDATE employees SET is_active = 0 WHERE id = ?", (emp["id"],))
                    conn.commit()
                    conn.close()
                    st.rerun()
        
        st.markdown("---")
        st.markdown("### ➕ Neuer Mitarbeiter")
        
        with st.form("new_emp"):
            cols = st.columns(3)
            with cols[0]:
                new_name = st.text_input("Name")
            with cols[1]:
                new_email = st.text_input("E-Mail")
            with cols[2]:
                new_role = st.text_input("Rolle")
            
            if st.form_submit_button("Hinzufügen", use_container_width=True):
                if new_name and new_email:
                    conn = get_db()
                    conn.execute("INSERT INTO employees (id, name, email, role) VALUES (?,?,?,?)",
                               (secrets.token_hex(4), new_name, new_email, new_role))
                    conn.commit()
                    conn.close()
                    st.success("Mitarbeiter hinzugefügt!")
                    st.rerun()
    
    with tab2:
        st.warning("⚠️ Für Streamlit Cloud: Secrets in den App-Einstellungen konfigurieren!")
        st.code("""
# In Streamlit Cloud → App Settings → Secrets:
SMTP_SERVER = "smtp.example.com"
SMTP_PORT = "587"
SMTP_USER = "user@example.com"
SMTP_PASSWORD = "password"
        """)
    
    with tab3:
        st.markdown("""
        ### ✅ DSGVO-Maßnahmen
        
        - **Einwilligung**: Checkbox vor jeder Eingabe erforderlich
        - **Lokale Datenbank**: SQLite (auf Streamlit Cloud: temporär)
        - **Keine Tracking-Tools**: Kein Google Analytics
        - **Löschanfragen**: Hier bearbeitbar
        """)
        
        st.markdown("---")
        st.markdown("### 🗑️ Daten löschen")
        
        with st.form("delete_data"):
            email_to_delete = st.text_input("E-Mail-Adresse")
            
            if st.form_submit_button("Alle Daten dieser E-Mail löschen", type="primary"):
                if email_to_delete:
                    conn = get_db()
                    conn.execute("DELETE FROM submissions WHERE data_json LIKE ?", (f'%"{email_to_delete}"%',))
                    conn.commit()
                    conn.close()
                    st.success(f"Alle Daten für {email_to_delete} wurden gelöscht.")

# ============================================================================
# MAIN
# ============================================================================

def main():
    # CSS laden
    load_css()
    
    # Datenbank initialisieren
    init_db()
    
    # Session State
    if "page" not in st.session_state:
        st.session_state.page = "dashboard"
    
    # Navigation in Sidebar
    with st.sidebar:
        st.markdown("### Navigation")
        
        if st.button("🏠 Dashboard", use_container_width=True):
            st.session_state.page = "dashboard"
            st.rerun()
        
        if st.button("📋 Fragebögen", use_container_width=True):
            st.session_state.page = "forms"
            st.rerun()
        
        if st.button("📊 Eingaben", use_container_width=True):
            st.session_state.page = "submissions"
            st.rerun()
        
        if st.button("⚙️ Einstellungen", use_container_width=True):
            st.session_state.page = "settings"
            st.rerun()
    
    # Seiten-Routing
    if st.session_state.page == "dashboard":
        page_dashboard()
    elif st.session_state.page == "forms":
        page_forms()
    elif st.session_state.page == "fill":
        page_fill_form()
    elif st.session_state.page == "submissions":
        page_submissions()
    elif st.session_state.page == "settings":
        page_settings()
    else:
        page_dashboard()

if __name__ == "__main__":
    main()
