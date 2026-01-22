"""
Caching-Strategien für Streamlit
st.cache_data und st.cache_resource Wrapper
"""

import streamlit as st
import hashlib
import json
import time
from typing import Any, Dict, Optional, Callable, List
from functools import wraps
from datetime import datetime, timedelta
from pathlib import Path


# ============================================
# Konfigurierbare TTL-Werte
# ============================================

class CacheTTL:
    """Standard TTL-Werte"""
    VERY_SHORT = 60  # 1 Minute
    SHORT = 300  # 5 Minuten
    MEDIUM = 1800  # 30 Minuten
    LONG = 3600  # 1 Stunde
    VERY_LONG = 86400  # 1 Tag


# ============================================
# Formulare cachen
# ============================================

@st.cache_data(ttl=CacheTTL.MEDIUM)
def get_cached_form(form_id: str, forms_dict: Dict) -> Optional[Dict]:
    """
    Cached Formular-Zugriff
    
    Hinweis: forms_dict muss hashable sein (wird als JSON serialisiert)
    """
    return forms_dict.get(form_id)


@st.cache_data(ttl=CacheTTL.SHORT)
def get_cached_form_list(forms_json: str) -> List[Dict]:
    """
    Cached Formular-Liste
    """
    forms = json.loads(forms_json)
    return [
        {
            'id': f.get('id'),
            'title': f.get('title'),
            'category': f.get('category'),
            'status': f.get('status'),
        }
        for f in forms.values()
    ]


# ============================================
# Datenbankabfragen cachen
# ============================================

@st.cache_resource(ttl=CacheTTL.VERY_LONG)
def get_database_connection():
    """
    Cached Datenbankverbindung
    Wird nur einmal pro Session erstellt
    """
    from modules.database import DatabaseManager
    return DatabaseManager()


@st.cache_data(ttl=CacheTTL.SHORT)
def get_cached_submissions(
    form_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    _cache_key: str = ""
) -> List[Dict]:
    """
    Cached Submission-Abfrage
    
    _cache_key wird für manuelle Cache-Invalidierung verwendet
    """
    db = get_database_connection()
    return db.search_submissions(
        form_id=form_id,
        status=status,
        limit=limit
    )


def invalidate_submissions_cache():
    """Invalidiert den Submissions-Cache"""
    get_cached_submissions.clear()


# ============================================
# Template cachen
# ============================================

@st.cache_data(ttl=CacheTTL.LONG)
def get_cached_template(template_path: str) -> str:
    """
    Cached Template-Laden
    """
    path = Path(template_path)
    if path.exists():
        return path.read_text(encoding='utf-8')
    return ""


@st.cache_resource(ttl=CacheTTL.VERY_LONG)
def get_jinja_environment():
    """
    Cached Jinja2 Environment
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    
    return Environment(
        loader=FileSystemLoader(['templates', 'schemas']),
        autoescape=select_autoescape(['html', 'xml']),
        trim_blocks=True,
        lstrip_blocks=True,
    )


# ============================================
# Engine-Instanzen cachen
# ============================================

@st.cache_resource
def get_document_engine():
    """Cached Document Engine"""
    from modules.document_engine import DocumentEngine
    return DocumentEngine()


@st.cache_resource
def get_email_engine():
    """Cached Email Engine"""
    from modules.email_engine import EmailEngine
    return EmailEngine()


@st.cache_resource
def get_workflow_engine():
    """Cached Workflow Engine"""
    from modules.workflow_engine import WorkflowEngine
    return WorkflowEngine(
        document_engine=get_document_engine(),
        email_engine=get_email_engine()
    )


@st.cache_resource
def get_file_scanner():
    """Cached File Scanner"""
    from modules.virus_scanner import FileScanner
    return FileScanner(use_clamav=True, strict_mode=True)


@st.cache_resource
def get_document_converter():
    """Cached Document Converter"""
    from modules.converter import DocumentConverter
    try:
        return DocumentConverter()
    except RuntimeError:
        return None


# ============================================
# Berechnung cachen
# ============================================

@st.cache_data(ttl=CacheTTL.MEDIUM)
def compute_form_statistics(forms_json: str) -> Dict[str, Any]:
    """
    Cached Formular-Statistiken
    """
    forms = json.loads(forms_json)
    
    total = len(forms)
    by_status = {}
    by_category = {}
    total_fields = 0
    
    for form in forms.values():
        status = form.get('status', 'draft')
        by_status[status] = by_status.get(status, 0) + 1
        
        category = form.get('category', 'Allgemein')
        by_category[category] = by_category.get(category, 0) + 1
        
        for page in form.get('pages', []):
            total_fields += len(page.get('fields', []))
    
    return {
        'total_forms': total,
        'by_status': by_status,
        'by_category': by_category,
        'total_fields': total_fields,
        'avg_fields_per_form': total_fields / total if total > 0 else 0,
    }


@st.cache_data(ttl=CacheTTL.SHORT)
def compute_submission_statistics(
    submissions_json: str,
    form_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Cached Submission-Statistiken
    """
    submissions = json.loads(submissions_json)
    
    if form_id:
        submissions = [s for s in submissions if s.get('form_id') == form_id]
    
    total = len(submissions)
    by_status = {}
    by_date = {}
    
    for sub in submissions:
        status = sub.get('status', 'unknown')
        by_status[status] = by_status.get(status, 0) + 1
        
        created = sub.get('created_at', '')[:10]  # Nur Datum
        by_date[created] = by_date.get(created, 0) + 1
    
    return {
        'total': total,
        'by_status': by_status,
        'by_date': dict(sorted(by_date.items())[-30:]),  # Letzte 30 Tage
    }


# ============================================
# Datei-Hash cachen
# ============================================

@st.cache_data(ttl=CacheTTL.LONG)
def compute_file_hash(data: bytes) -> str:
    """Cached Datei-Hash"""
    return hashlib.sha256(data).hexdigest()


# ============================================
# Conditional Logic cachen
# ============================================

@st.cache_data(ttl=CacheTTL.MEDIUM)
def get_field_dependencies(form_json: str) -> Dict[str, List[str]]:
    """
    Berechnet Feld-Abhängigkeiten für Conditional Logic
    Returns: {field_id: [abhängige_field_ids]}
    """
    form = json.loads(form_json)
    dependencies = {}
    
    for page in form.get('pages', []):
        for field in page.get('fields', []):
            cond = field.get('conditional_logic', {})
            if cond.get('enabled'):
                for condition in cond.get('conditions', []):
                    dep_field = condition.get('field')
                    if dep_field:
                        if dep_field not in dependencies:
                            dependencies[dep_field] = []
                        dependencies[dep_field].append(field.get('id'))
    
    return dependencies


# ============================================
# Cache Management UI
# ============================================

def render_cache_management():
    """Rendert Cache-Management UI für Admin"""
    st.markdown("### 🗄️ Cache-Verwaltung")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🗑️ Formular-Cache leeren"):
            get_cached_form.clear()
            get_cached_form_list.clear()
            compute_form_statistics.clear()
            st.success("Formular-Cache geleert")
    
    with col2:
        if st.button("🗑️ Submission-Cache leeren"):
            get_cached_submissions.clear()
            compute_submission_statistics.clear()
            st.success("Submission-Cache geleert")
    
    with col3:
        if st.button("🗑️ Alle Caches leeren"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.success("Alle Caches geleert")
    
    st.markdown("---")
    st.caption("Cache-TTL-Werte:")
    st.write(f"- Kurz: {CacheTTL.SHORT}s")
    st.write(f"- Mittel: {CacheTTL.MEDIUM}s")
    st.write(f"- Lang: {CacheTTL.LONG}s")


# ============================================
# Custom Cache Decorator mit Logging
# ============================================

def cached_with_logging(ttl: int = 300, show_spinner: bool = True):
    """
    Custom Cache Decorator mit Logging
    """
    def decorator(func: Callable) -> Callable:
        # Streamlit Cache anwenden
        cached_func = st.cache_data(ttl=ttl, show_spinner=show_spinner)(func)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = cached_func(*args, **kwargs)
            duration = time.time() - start
            
            # Logging (nur wenn langsam = vermutlich kein Cache-Hit)
            if duration > 0.1:
                print(f"[CACHE MISS] {func.__name__}: {duration:.3f}s")
            
            return result
        
        # Clear-Methode weiterreichen
        wrapper.clear = cached_func.clear
        
        return wrapper
    
    return decorator


# ============================================
# Session State Cache Helpers
# ============================================

def get_or_compute(key: str, compute_func: Callable, ttl_seconds: int = 300) -> Any:
    """
    Holt Wert aus Session State oder berechnet ihn
    Mit einfachem TTL-Management
    """
    cache_key = f"_cache_{key}"
    timestamp_key = f"_cache_ts_{key}"
    
    now = datetime.now()
    
    # Prüfen ob Cache gültig
    if cache_key in st.session_state and timestamp_key in st.session_state:
        cached_time = st.session_state[timestamp_key]
        if (now - cached_time).total_seconds() < ttl_seconds:
            return st.session_state[cache_key]
    
    # Neu berechnen
    value = compute_func()
    st.session_state[cache_key] = value
    st.session_state[timestamp_key] = now
    
    return value


def invalidate_session_cache(key: str):
    """Invalidiert einen Session-Cache-Eintrag"""
    cache_key = f"_cache_{key}"
    timestamp_key = f"_cache_ts_{key}"
    
    if cache_key in st.session_state:
        del st.session_state[cache_key]
    if timestamp_key in st.session_state:
        del st.session_state[timestamp_key]


def clear_all_session_caches():
    """Löscht alle Session-Caches"""
    keys_to_delete = [
        k for k in st.session_state.keys()
        if k.startswith('_cache_')
    ]
    for key in keys_to_delete:
        del st.session_state[key]
