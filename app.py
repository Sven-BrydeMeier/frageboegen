"""
RA-RHM Formular-System - Vollständige Implementierung
Professionelle Streamlit-App für Mandanten-Fragebögen

Features:
- Mehrseitiger Wizard mit st.form
- Repeatable Sections
- Auth & Rollen
- Autosave/Drafts
- Review-Seite
- st.secrets Integration
"""

import streamlit as st
import json
import uuid
import copy
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import hashlib
import urllib.parse

# Lokale Module
import sys
sys.path.insert(0, str(Path(__file__).parent))

from modules.form_schema import (
    FormSchema, FormField, FormPage, FieldType, FieldOption,
    ConditionalLogic, Condition, ConditionOperator,
    Calculation, CalculationType, FieldValidation,
    WorkflowRule, WorkflowAction, WorkflowActionType,
    FormSubmission, create_example_schema
)
from modules.auth import (
    init_auth_state, get_current_user, login_user, logout_user,
    require_auth, render_login_form, render_user_menu,
    render_user_management, User, UserRole, AuthManager
)

# ============================================
# Konfiguration
# ============================================

st.set_page_config(
    page_title="RA-RHM Formular-System",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Secrets laden
def get_secret(key: str, default: Any = None) -> Any:
    """Sicheres Laden von Secrets"""
    try:
        keys = key.split(".")
        value = st.secrets
        for k in keys:
            value = value[k]
        return value
    except:
        return default

# ============================================
# Session State Initialisierung
# ============================================

def init_session_state():
    """Initialisiert den Session State"""
    defaults = {
        # Navigation
        'page': 'dashboard',
        
        # Daten
        'forms': {},
        'submissions': {},
        'drafts': {},
        
        # Editor
        'editor_form_id': None,
        
        # Formular ausfüllen
        'current_form_id': None,
        'current_page_index': 0,
        'form_values': {},
        'repeatable_items': {},
        
        # Mandanten-Modus
        'is_mandant_mode': False,
        'mandant_token': None,
        'mandant_info': None,
        
        # Autosave
        'last_autosave': None,
        'autosave_enabled': True,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    # Auth initialisieren
    init_auth_state()
    
    # Beispiel-Formulare laden
    if not st.session_state.forms:
        load_example_forms()

def load_example_forms():
    """Lädt Beispiel-Formulare"""
    example = {
        'id': 'form_mandantenaufnahme',
        'name': 'mandantenaufnahme',
        'title': 'Mandantenaufnahme',
        'description': 'Ersterfassung neuer Mandanten',
        'category': 'Allgemein',
        'version': 1,
        'status': 'active',
        'pages': [
            {
                'id': 'page_1',
                'title': 'Persönliche Daten',
                'description': 'Bitte geben Sie Ihre persönlichen Daten ein.',
                'order': 0,
                'fields': [
                    {'id': 'anrede', 'type': 'radio', 'label': 'Anrede', 'options': [{'label': 'Herr', 'value': 'herr'}, {'label': 'Frau', 'value': 'frau'}, {'label': 'Divers', 'value': 'divers'}], 'validation': {'required': True}},
                    {'id': 'vorname', 'type': 'text', 'label': 'Vorname', 'placeholder': 'Ihr Vorname', 'validation': {'required': True, 'min_length': 2}},
                    {'id': 'nachname', 'type': 'text', 'label': 'Nachname', 'placeholder': 'Ihr Nachname', 'validation': {'required': True, 'min_length': 2}},
                    {'id': 'geburtsdatum', 'type': 'date', 'label': 'Geburtsdatum', 'validation': {'required': True}},
                    {'id': 'familienstand', 'type': 'select', 'label': 'Familienstand', 'options': [{'label': 'Ledig', 'value': 'ledig'}, {'label': 'Verheiratet', 'value': 'verheiratet'}, {'label': 'Geschieden', 'value': 'geschieden'}, {'label': 'Verwitwet', 'value': 'verwitwet'}]},
                    {'id': 'ehepartner_name', 'type': 'text', 'label': 'Name des Ehepartners', 'conditional_logic': {'enabled': True, 'logic_type': 'all', 'conditions': [{'field': 'familienstand', 'operator': 'eq', 'value': 'verheiratet'}]}},
                ]
            },
            {
                'id': 'page_2',
                'title': 'Kontaktdaten',
                'description': 'Wie können wir Sie erreichen?',
                'order': 1,
                'fields': [
                    {'id': 'email', 'type': 'email', 'label': 'E-Mail-Adresse', 'validation': {'required': True}},
                    {'id': 'telefon', 'type': 'phone', 'label': 'Telefonnummer'},
                    {'id': 'strasse', 'type': 'text', 'label': 'Straße und Hausnummer'},
                    {'id': 'plz', 'type': 'text', 'label': 'PLZ', 'validation': {'pattern': r'^\d{5}$', 'pattern_message': 'Bitte gültige 5-stellige PLZ eingeben'}},
                    {'id': 'ort', 'type': 'text', 'label': 'Ort'},
                ]
            },
            {
                'id': 'page_3',
                'title': 'Ihr Anliegen',
                'description': 'Beschreiben Sie Ihren Fall.',
                'order': 2,
                'fields': [
                    {'id': 'rechtsgebiet', 'type': 'select', 'label': 'Rechtsgebiet', 'validation': {'required': True}, 'options': [{'label': 'Familienrecht', 'value': 'familienrecht'}, {'label': 'Arbeitsrecht', 'value': 'arbeitsrecht'}, {'label': 'Mietrecht', 'value': 'mietrecht'}, {'label': 'Verkehrsrecht', 'value': 'verkehrsrecht'}, {'label': 'Erbrecht', 'value': 'erbrecht'}, {'label': 'Sonstiges', 'value': 'sonstiges'}]},
                    {'id': 'sachverhalt', 'type': 'textarea', 'label': 'Schildern Sie Ihr Anliegen', 'placeholder': 'Bitte beschreiben Sie Ihren Fall...', 'validation': {'required': True, 'min_length': 50}},
                    {'id': 'unterlagen', 'type': 'file_upload', 'label': 'Relevante Unterlagen', 'description': 'PDF, JPG, PNG (max. 5 Dateien)', 'allowed_file_types': ['.pdf', '.jpg', '.jpeg', '.png'], 'max_files': 5},
                ]
            },
        ],
        'repeatable_sections': [
            {
                'id': 'section_kinder',
                'label': 'Kinder',
                'description': 'Falls relevant, geben Sie Ihre Kinder an.',
                'page_id': 'page_1',
                'min_items': 0,
                'max_items': 10,
                'add_button_text': 'Kind hinzufügen',
                'item_label_template': 'Kind {n}',
                'fields': [
                    {'id': 'kind_vorname', 'type': 'text', 'label': 'Vorname'},
                    {'id': 'kind_nachname', 'type': 'text', 'label': 'Nachname'},
                    {'id': 'kind_geburtsdatum', 'type': 'date', 'label': 'Geburtsdatum'},
                ]
            }
        ],
        'workflows': [
            {
                'id': 'wf_standard',
                'name': 'Standard-Workflow',
                'trigger': 'on_submit',
                'enabled': True,
                'actions': [
                    {'type': 'generate_document', 'name': 'Mandantenbogen erstellen', 'config': {'template': 'mandantenbogen.docx', 'output_format': 'pdf'}},
                    {'type': 'send_email', 'name': 'Bestätigung an Mandant', 'config': {'to_field': 'email', 'subject': 'Ihre Anfrage bei RA-RHM'}},
                ]
            }
        ],
        'settings': {
            'show_progress': True,
            'allow_save_draft': True,
            'show_review_page': True,
            'submit_button_text': 'Absenden',
            'success_message': 'Vielen Dank für Ihre Anfrage! Wir melden uns zeitnah bei Ihnen.',
            'autosave_interval': 30,
        },
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
    }
    
    st.session_state.forms[example['id']] = example

init_session_state()

# ============================================
# CSS Styling
# ============================================

st.markdown("""
<style>
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #78350f, #92400e);
    }
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span {
        color: white !important;
    }
    section[data-testid="stSidebar"] .stButton button {
        color: white !important;
        border-color: rgba(255,255,255,0.3) !important;
    }
    .repeatable-item {
        border: 1px dashed #d1d5db;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        background: #f9fafb;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# Hilfsfunktionen
# ============================================

FIELD_TYPES = {
    'text': {'label': 'Textfeld', 'icon': '📝'},
    'textarea': {'label': 'Textbereich', 'icon': '📄'},
    'email': {'label': 'E-Mail', 'icon': '📧'},
    'phone': {'label': 'Telefon', 'icon': '📞'},
    'number': {'label': 'Zahl', 'icon': '🔢'},
    'date': {'label': 'Datum', 'icon': '📅'},
    'select': {'label': 'Dropdown', 'icon': '📋', 'has_options': True},
    'multi_select': {'label': 'Mehrfachauswahl', 'icon': '☑️', 'has_options': True},
    'radio': {'label': 'Einzelauswahl', 'icon': '🔘', 'has_options': True},
    'checkbox': {'label': 'Checkbox', 'icon': '✅'},
    'file_upload': {'label': 'Datei-Upload', 'icon': '📎'},
    'section': {'label': 'Abschnitt', 'icon': '➖'},
}

OPERATORS = {
    'eq': 'ist gleich',
    'neq': 'ist nicht gleich',
    'contains': 'enthält',
    'empty': 'ist leer',
    'not_empty': 'ist nicht leer',
}

def get_form(form_id: str) -> Optional[Dict]:
    return st.session_state.forms.get(form_id)

def save_form(form_data: Dict):
    form_data['updated_at'] = datetime.now().isoformat()
    st.session_state.forms[form_data['id']] = form_data

def evaluate_condition(condition: Dict, values: Dict) -> bool:
    field = condition.get('field', '')
    operator = condition.get('operator', 'eq')
    value = condition.get('value', '')
    field_value = values.get(field, '')
    
    if operator == 'eq':
        return str(field_value) == str(value)
    elif operator == 'neq':
        return str(field_value) != str(value)
    elif operator == 'contains':
        return str(value).lower() in str(field_value).lower()
    elif operator == 'empty':
        return not field_value
    elif operator == 'not_empty':
        return bool(field_value)
    return True

def evaluate_conditional_logic(field: Dict, values: Dict) -> bool:
    cond = field.get('conditional_logic', {})
    if not cond or not cond.get('enabled'):
        return True
    
    conditions = cond.get('conditions', [])
    if not conditions:
        return True
    
    results = [evaluate_condition(c, values) for c in conditions]
    
    if cond.get('logic_type') == 'all':
        return all(results)
    return any(results)

def validate_field(field: Dict, value: Any) -> Tuple[bool, str]:
    validation = field.get('validation', {})
    
    if validation.get('required'):
        if value is None or value == '' or value == []:
            return False, f"{field.get('label', 'Feld')} ist ein Pflichtfeld"
    
    if value is None or value == '':
        return True, ''
    
    if validation.get('min_length'):
        if len(str(value)) < validation['min_length']:
            return False, f"Mindestens {validation['min_length']} Zeichen"
    
    if validation.get('pattern'):
        import re
        if not re.match(validation['pattern'], str(value)):
            return False, validation.get('pattern_message', 'Ungültiges Format')
    
    return True, ''

def autosave_draft():
    if not st.session_state.autosave_enabled:
        return
    
    form_id = st.session_state.current_form_id
    if not form_id:
        return
    
    draft_id = f"draft_{form_id}"
    st.session_state.drafts[draft_id] = {
        'form_id': form_id,
        'values': st.session_state.form_values.copy(),
        'page_index': st.session_state.current_page_index,
        'repeatable_items': st.session_state.repeatable_items.copy(),
        'saved_at': datetime.now().isoformat(),
    }
    st.session_state.last_autosave = datetime.now()

# ============================================
# Sidebar
# ============================================

def render_sidebar():
    with st.sidebar:
        st.markdown("# ⚖️ RA-RHM")
        st.markdown("### Formular-System")
        
        st.markdown("---")
        render_user_menu()
        st.markdown("---")
        
        user = get_current_user()
        if not user:
            return
        
        pages = []
        if user.has_permission("forms.view"):
            pages.append(('dashboard', '🏠 Dashboard'))
        if user.has_permission("forms.edit"):
            pages.append(('editor', '✏️ Editor'))
        if user.has_permission("submissions.view"):
            pages.append(('submissions', '📥 Einreichungen'))
        if user.has_permission("users.view"):
            pages.append(('users', '👥 Benutzer'))
        if user.has_permission("settings.edit"):
            pages.append(('settings', '⚙️ Einstellungen'))
        
        for page_id, label in pages:
            btn_type = "primary" if st.session_state.page == page_id else "secondary"
            if st.button(label, key=f"nav_{page_id}", use_container_width=True, type=btn_type):
                st.session_state.page = page_id
                st.rerun()
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        col1.metric("Formulare", len(st.session_state.forms))
        col2.metric("Einreichungen", len(st.session_state.submissions))

# ============================================
# Wizard-Fortschritt
# ============================================

def render_wizard_progress(pages: List[Dict], current_index: int):
    if not pages:
        return
    
    cols = st.columns(len(pages))
    for i, (page, col) in enumerate(zip(pages, cols)):
        with col:
            if i < current_index:
                color = "#059669"
                icon = "✅"
            elif i == current_index:
                color = "#b45309"
                icon = str(i + 1)
            else:
                color = "#9ca3af"
                icon = str(i + 1)
            
            st.markdown(
                f"<div style='text-align:center;'>"
                f"<div style='width:30px;height:30px;border-radius:50%;background:{color};"
                f"color:white;display:inline-flex;align-items:center;justify-content:center;font-weight:bold;'>{icon}</div>"
                f"<br><small>{page.get('title', f'Seite {i+1}')}</small></div>",
                unsafe_allow_html=True
            )

# ============================================
# Formular-Feld rendern
# ============================================

def render_form_field(field: Dict, values: Dict, prefix: str = "") -> Tuple[str, Any]:
    field_id = field.get('id', '')
    field_type = field.get('type', 'text')
    label = field.get('label', 'Feld')
    placeholder = field.get('placeholder', '')
    description = field.get('description', '')
    validation = field.get('validation', {})
    
    if validation.get('required'):
        label = f"{label} *"
    
    if description:
        st.caption(description)
    
    current_value = values.get(field_id, field.get('default_value', ''))
    key = f"{prefix}_{field_id}" if prefix else field_id
    
    if field_type == 'text':
        value = st.text_input(label, value=current_value or '', placeholder=placeholder, key=key)
    elif field_type == 'textarea':
        value = st.text_area(label, value=current_value or '', placeholder=placeholder, key=key, height=150)
    elif field_type == 'email':
        value = st.text_input(label, value=current_value or '', placeholder=placeholder or 'name@beispiel.de', key=key)
    elif field_type == 'phone':
        value = st.text_input(label, value=current_value or '', placeholder=placeholder or '+49...', key=key)
    elif field_type == 'number':
        value = st.number_input(label, value=float(current_value) if current_value else 0.0, key=key)
    elif field_type == 'date':
        value = st.date_input(label, value=current_value if current_value else None, key=key)
    elif field_type == 'select':
        options = [o.get('label', o) if isinstance(o, dict) else o for o in field.get('options', [])]
        if options:
            value = st.selectbox(label, options, key=key)
            for o in field.get('options', []):
                if isinstance(o, dict) and o.get('label') == value:
                    value = o.get('value', value)
                    break
        else:
            value = None
    elif field_type == 'multi_select':
        options = [o.get('label', o) if isinstance(o, dict) else o for o in field.get('options', [])]
        value = st.multiselect(label, options, default=current_value if isinstance(current_value, list) else [], key=key)
    elif field_type == 'radio':
        options = [o.get('label', o) if isinstance(o, dict) else o for o in field.get('options', [])]
        if options:
            value = st.radio(label, options, key=key, horizontal=True)
            for o in field.get('options', []):
                if isinstance(o, dict) and o.get('label') == value:
                    value = o.get('value', value)
                    break
        else:
            value = None
    elif field_type == 'checkbox':
        value = st.checkbox(label, value=bool(current_value), key=key)
    elif field_type == 'file_upload':
        allowed = field.get('allowed_file_types', [])
        max_files = field.get('max_files', 1)
        value = st.file_uploader(label, type=allowed if allowed else None, accept_multiple_files=max_files > 1, key=key)
    elif field_type == 'section':
        st.markdown(f"### {label}")
        st.divider()
        value = None
    else:
        value = st.text_input(label, value=current_value or '', key=key)
    
    return field_id, value

# ============================================
# Repeatable Section rendern
# ============================================

def render_repeatable_section(section: Dict, values: Dict, prefix: str = ""):
    section_id = section.get('id', '')
    label = section.get('label', 'Abschnitt')
    description = section.get('description', '')
    min_items = section.get('min_items', 0)
    max_items = section.get('max_items', 10)
    add_text = section.get('add_button_text', 'Hinzufügen')
    item_template = section.get('item_label_template', 'Eintrag {n}')
    fields = section.get('fields', [])
    
    st.markdown(f"### {label}")
    if description:
        st.caption(description)
    
    if section_id not in st.session_state.repeatable_items:
        st.session_state.repeatable_items[section_id] = []
    
    items = st.session_state.repeatable_items[section_id]
    items_to_remove = []
    
    for i, item_data in enumerate(items):
        item_label = item_template.replace('{n}', str(i + 1))
        
        st.markdown(f"<div class='repeatable-item'><strong>{item_label}</strong>", unsafe_allow_html=True)
        
        cols = st.columns(len(fields)) if len(fields) <= 3 else [st.container()]
        
        for fi, field in enumerate(fields):
            col = cols[fi] if len(fields) <= 3 else cols[0]
            with col:
                item_field_id = f"{section_id}_{i}_{field.get('id', '')}"
                field_copy = field.copy()
                field_copy['id'] = item_field_id
                _, value = render_form_field(field_copy, item_data, prefix=f"{prefix}_rep")
                item_data[field.get('id', '')] = value
        
        if len(items) > min_items:
            if st.button(f"🗑️ {item_label} entfernen", key=f"remove_{section_id}_{i}"):
                items_to_remove.append(i)
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    for i in sorted(items_to_remove, reverse=True):
        items.pop(i)
    
    if items_to_remove:
        st.rerun()
    
    if len(items) < max_items:
        if st.button(f"➕ {add_text}", key=f"add_{section_id}"):
            items.append({})
            st.rerun()
    
    st.session_state.repeatable_items[section_id] = items

# ============================================
# Review-Seite
# ============================================

def render_review_page(form: Dict, values: Dict):
    st.markdown("## 📋 Zusammenfassung")
    st.markdown("Bitte überprüfen Sie Ihre Angaben vor dem Absenden.")
    
    for page in form.get('pages', []):
        st.markdown(f"### {page.get('title', 'Seite')}")
        
        for field in page.get('fields', []):
            if not evaluate_conditional_logic(field, values):
                continue
            
            field_id = field.get('id', '')
            label = field.get('label', 'Feld')
            value = values.get(field_id, '')
            
            if field.get('type') in ['section']:
                continue
            
            if isinstance(value, list):
                value = ', '.join(str(v) for v in value)
            elif isinstance(value, bool):
                value = 'Ja' if value else 'Nein'
            elif value is None:
                value = '—'
            
            col1, col2 = st.columns([1, 2])
            col1.markdown(f"**{label}:**")
            col2.markdown(str(value))
        
        st.markdown("---")
    
    # Repeatable Sections
    for section in form.get('repeatable_sections', []):
        section_id = section.get('id', '')
        items = st.session_state.repeatable_items.get(section_id, [])
        
        if items:
            st.markdown(f"### {section.get('label', 'Abschnitt')}")
            
            for i, item in enumerate(items):
                item_label = section.get('item_label_template', 'Eintrag {n}').replace('{n}', str(i + 1))
                st.markdown(f"**{item_label}:**")
                
                for field in section.get('fields', []):
                    label = field.get('label', '')
                    value = item.get(field.get('id', ''), '—')
                    st.write(f"  - {label}: {value}")
            
            st.markdown("---")

# ============================================
# Formular ausfüllen (Wizard)
# ============================================

def page_form_fill():
    form_id = st.session_state.current_form_id
    
    if not form_id or form_id not in st.session_state.forms:
        st.error("Formular nicht gefunden")
        return
    
    form = st.session_state.forms[form_id]
    pages = form.get('pages', [])
    settings = form.get('settings', {})
    
    st.markdown(f"# {form.get('title', 'Formular')}")
    if form.get('description'):
        st.markdown(form['description'])
    
    st.markdown("---")
    
    if not pages:
        pages = [{'id': 'single', 'title': 'Formular', 'fields': form.get('fields', [])}]
    
    current_page = st.session_state.current_page_index
    total_pages = len(pages)
    show_review = settings.get('show_review_page', True)
    is_review = current_page >= total_pages
    
    if settings.get('show_progress', True) and total_pages > 1:
        render_wizard_progress(pages, current_page if not is_review else total_pages)
    
    # Review-Seite
    if is_review:
        render_review_page(form, st.session_state.form_values)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Zurück zur Bearbeitung", use_container_width=True):
                st.session_state.current_page_index = total_pages - 1
                st.rerun()
        with col2:
            submit_text = settings.get('submit_button_text', 'Absenden')
            if st.button(f"📤 {submit_text}", type="primary", use_container_width=True):
                submission_id = f"sub_{uuid.uuid4().hex[:12]}"
                st.session_state.submissions[submission_id] = {
                    'id': submission_id,
                    'form_id': form_id,
                    'data': st.session_state.form_values.copy(),
                    'repeatable_data': st.session_state.repeatable_items.copy(),
                    'status': 'submitted',
                    'created_at': datetime.now().isoformat(),
                }
                
                st.session_state.form_values = {}
                st.session_state.repeatable_items = {}
                st.session_state.current_page_index = 0
                st.session_state.page = 'form_success'
                st.session_state.last_submission_id = submission_id
                st.rerun()
        return
    
    # Aktuelle Seite
    page = pages[current_page]
    
    st.markdown(f"### {page.get('title', f'Seite {current_page + 1}')}")
    if page.get('description'):
        st.markdown(page['description'])
    
    # st.form für gebündelten Submit
    with st.form(key=f"wizard_page_{current_page}"):
        for field in page.get('fields', []):
            if not evaluate_conditional_logic(field, st.session_state.form_values):
                continue
            
            field_id, value = render_form_field(field, st.session_state.form_values, f"page_{current_page}")
            
            if field_id and value is not None:
                st.session_state.form_values[field_id] = value
        
        # Repeatable Sections dieser Seite
        for section in form.get('repeatable_sections', []):
            if section.get('page_id') == page.get('id'):
                render_repeatable_section(section, st.session_state.form_values, f"page_{current_page}")
        
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            back = st.form_submit_button("⬅️ Zurück", use_container_width=True) if current_page > 0 else False
        
        with col2:
            save_draft = st.form_submit_button("💾 Speichern", use_container_width=True) if settings.get('allow_save_draft', True) else False
        
        with col3:
            if current_page < total_pages - 1:
                next_btn = st.form_submit_button("Weiter ➡️", type="primary", use_container_width=True)
            else:
                if show_review:
                    next_btn = st.form_submit_button("Zur Zusammenfassung ➡️", type="primary", use_container_width=True)
                else:
                    next_btn = st.form_submit_button(f"📤 {settings.get('submit_button_text', 'Absenden')}", type="primary", use_container_width=True)
    
    if back:
        st.session_state.current_page_index = max(0, current_page - 1)
        st.rerun()
    
    if save_draft:
        autosave_draft()
        st.success("✅ Entwurf gespeichert!")
    
    if next_btn:
        errors = []
        for field in page.get('fields', []):
            if not evaluate_conditional_logic(field, st.session_state.form_values):
                continue
            value = st.session_state.form_values.get(field.get('id', ''))
            valid, msg = validate_field(field, value)
            if not valid:
                errors.append(msg)
        
        if errors:
            for err in errors:
                st.error(err)
        else:
            st.session_state.current_page_index = current_page + 1
            st.rerun()

# ============================================
# Erfolgs-Seite
# ============================================

def page_form_success():
    form_id = st.session_state.current_form_id
    form = st.session_state.forms.get(form_id, {})
    settings = form.get('settings', {})
    
    st.markdown("# ✅ Vielen Dank!")
    st.success(settings.get('success_message', 'Ihre Anfrage wurde erfolgreich übermittelt.'))
    
    submission_id = st.session_state.get('last_submission_id', '')
    if submission_id:
        st.info(f"Ihre Vorgangsnummer: **{submission_id}**")
    
    st.markdown("---")
    
    if st.session_state.is_mandant_mode:
        st.markdown("Sie können dieses Fenster nun schließen.")
    else:
        if st.button("🏠 Zum Dashboard", type="primary"):
            st.session_state.page = 'dashboard'
            st.session_state.current_form_id = None
            st.rerun()

# ============================================
# Dashboard
# ============================================

def page_dashboard():
    st.markdown("# 🏠 Dashboard")
    
    user = get_current_user()
    st.markdown(f"Willkommen, **{user.full_name}**!")
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 📋 Formulare")
        
        for form_id, form in st.session_state.forms.items():
            status = form.get('status', 'draft')
            status_icon = "🟢" if status == 'active' else "🟡"
            
            with st.expander(f"{status_icon} {form.get('title', 'Unbenannt')}"):
                st.write(f"**Kategorie:** {form.get('category', '-')}")
                st.write(f"**Seiten:** {len(form.get('pages', []))}")
                
                col_a, col_b, col_c = st.columns(3)
                
                if user.has_permission("forms.edit"):
                    if col_a.button("✏️", key=f"edit_{form_id}", help="Bearbeiten"):
                        st.session_state.editor_form_id = form_id
                        st.session_state.page = 'editor'
                        st.rerun()
                
                if col_b.button("👁️", key=f"preview_{form_id}", help="Vorschau"):
                    st.session_state.current_form_id = form_id
                    st.session_state.page = 'form_fill'
                    st.rerun()
                
                if col_c.button("🔗", key=f"link_{form_id}", help="Link"):
                    st.code(f"?form={form_id}")
    
    with col2:
        st.markdown("### 📥 Letzte Einreichungen")
        
        submissions = list(st.session_state.submissions.values())[-5:]
        
        if submissions:
            for sub in reversed(submissions):
                form = st.session_state.forms.get(sub.get('form_id', ''), {})
                st.write(f"- **{sub['id'][:12]}...** ({form.get('title', '-')})")
        else:
            st.info("Keine Einreichungen")
    
    with col3:
        st.markdown("### ⚡ Schnellaktionen")
        
        if user.has_permission("forms.create"):
            if st.button("➕ Neues Formular", type="primary", use_container_width=True):
                new_form = {
                    'id': f"form_{uuid.uuid4().hex[:8]}",
                    'title': 'Neues Formular',
                    'status': 'draft',
                    'pages': [{'id': 'page_1', 'title': 'Seite 1', 'fields': []}],
                    'repeatable_sections': [],
                    'workflows': [],
                    'settings': {'show_progress': True, 'allow_save_draft': True, 'show_review_page': True},
                    'created_at': datetime.now().isoformat(),
                }
                st.session_state.forms[new_form['id']] = new_form
                st.session_state.editor_form_id = new_form['id']
                st.session_state.page = 'editor'
                st.rerun()

# ============================================
# Editor
# ============================================

def page_editor():
    st.markdown("# ✏️ Formular-Editor")
    
    col_sidebar, col_main = st.columns([1, 3])
    
    with col_sidebar:
        st.markdown("### 📋 Formulare")
        
        if st.button("➕ Neu", type="primary", use_container_width=True):
            new_form = {
                'id': f"form_{uuid.uuid4().hex[:8]}",
                'title': 'Neues Formular',
                'status': 'draft',
                'pages': [{'id': 'page_1', 'title': 'Seite 1', 'fields': []}],
                'repeatable_sections': [],
                'workflows': [],
                'settings': {},
                'created_at': datetime.now().isoformat(),
            }
            st.session_state.forms[new_form['id']] = new_form
            st.session_state.editor_form_id = new_form['id']
            st.rerun()
        
        st.markdown("---")
        
        for fid, form in st.session_state.forms.items():
            is_sel = st.session_state.editor_form_id == fid
            if st.button(form.get('title', 'Unbenannt')[:20], key=f"sel_{fid}", 
                        type="primary" if is_sel else "secondary", use_container_width=True):
                st.session_state.editor_form_id = fid
                st.rerun()
    
    with col_main:
        form_id = st.session_state.editor_form_id
        
        if not form_id or form_id not in st.session_state.forms:
            st.info("👈 Wählen Sie ein Formular")
            return
        
        form = st.session_state.forms[form_id]
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Seiten & Felder", "🔁 Wiederholbar", "⚙️ Einstellungen", "⚡ Workflows", "👁️ Vorschau"])
        
        with tab1:
            form['title'] = st.text_input("Titel", value=form.get('title', ''))
            
            pages = form.get('pages', [])
            page_titles = [p.get('title', f"Seite {i+1}") for i, p in enumerate(pages)]
            page_titles.append("➕ Neue Seite")
            
            selected_page = st.radio("Seite", page_titles, horizontal=True)
            
            if selected_page == "➕ Neue Seite":
                pages.append({'id': f'page_{len(pages)+1}', 'title': f'Seite {len(pages)+1}', 'fields': []})
                form['pages'] = pages
                st.rerun()
            
            page_idx = page_titles.index(selected_page) if selected_page in page_titles[:-1] else 0
            
            if pages and page_idx < len(pages):
                page = pages[page_idx]
                
                page['title'] = st.text_input("Seitentitel", value=page.get('title', ''), key="page_title")
                page['description'] = st.text_area("Beschreibung", value=page.get('description', ''), key="page_desc", height=80)
                
                st.markdown("---")
                st.markdown("### Felder")
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    new_type = st.selectbox("Neues Feld", list(FIELD_TYPES.keys()), 
                                           format_func=lambda x: f"{FIELD_TYPES[x]['icon']} {FIELD_TYPES[x]['label']}")
                with col2:
                    if st.button("➕ Hinzufügen", type="primary"):
                        page['fields'].append({
                            'id': f"field_{uuid.uuid4().hex[:8]}",
                            'type': new_type,
                            'label': f"Neues {FIELD_TYPES[new_type]['label']}",
                            'validation': {},
                        })
                        st.rerun()
                
                for i, field in enumerate(page.get('fields', [])):
                    ftype = field.get('type', 'text')
                    with st.expander(f"{FIELD_TYPES.get(ftype, {}).get('icon', '📝')} {field.get('label', 'Feld')}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            field['label'] = st.text_input("Label", value=field.get('label', ''), key=f"fl_{i}")
                            field['type'] = st.selectbox("Typ", list(FIELD_TYPES.keys()), 
                                                        index=list(FIELD_TYPES.keys()).index(ftype),
                                                        format_func=lambda x: FIELD_TYPES[x]['label'], key=f"ft_{i}")
                        with col2:
                            field['placeholder'] = st.text_input("Platzhalter", value=field.get('placeholder', ''), key=f"fp_{i}")
                            validation = field.get('validation', {})
                            validation['required'] = st.checkbox("Pflichtfeld", value=validation.get('required', False), key=f"fr_{i}")
                            field['validation'] = validation
                        
                        if FIELD_TYPES.get(ftype, {}).get('has_options'):
                            opts = field.get('options', [])
                            opts_text = "\n".join([o.get('label', o) if isinstance(o, dict) else str(o) for o in opts])
                            new_opts = st.text_area("Optionen (eine pro Zeile)", value=opts_text, key=f"fo_{i}", height=100)
                            field['options'] = [{'label': o.strip(), 'value': o.strip()} for o in new_opts.split('\n') if o.strip()]
                        
                        # Bedingte Logik
                        st.markdown("**Bedingte Anzeige:**")
                        cond = field.get('conditional_logic', {'enabled': False, 'conditions': []})
                        cond['enabled'] = st.checkbox("Aktivieren", value=cond.get('enabled', False), key=f"ce_{i}")
                        
                        if cond['enabled']:
                            other_fields = [f for pi, p in enumerate(pages) for f in p.get('fields', []) if f.get('id') != field.get('id')]
                            if other_fields:
                                cond['logic_type'] = st.radio("Logik", ['all', 'any'], format_func=lambda x: 'UND' if x == 'all' else 'ODER', key=f"clt_{i}", horizontal=True)
                                
                                conditions = cond.get('conditions', [])
                                for ci, c in enumerate(conditions):
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        field_opts = {f.get('id'): f.get('label') for f in other_fields}
                                        c['field'] = st.selectbox("Feld", list(field_opts.keys()), format_func=lambda x: field_opts.get(x, x), key=f"cf_{i}_{ci}")
                                    with col2:
                                        c['operator'] = st.selectbox("Op", list(OPERATORS.keys()), format_func=lambda x: OPERATORS.get(x, x), key=f"co_{i}_{ci}")
                                    with col3:
                                        c['value'] = st.text_input("Wert", value=c.get('value', ''), key=f"cv_{i}_{ci}")
                                
                                if st.button("➕ Bedingung", key=f"ca_{i}"):
                                    conditions.append({'field': '', 'operator': 'eq', 'value': ''})
                                    st.rerun()
                                
                                cond['conditions'] = conditions
                        
                        field['conditional_logic'] = cond
                        
                        if st.button("🗑️ Löschen", key=f"fd_{i}"):
                            page['fields'].pop(i)
                            st.rerun()
            
            if st.button("💾 Speichern", type="primary"):
                save_form(form)
                st.success("✅ Gespeichert!")
        
        with tab2:
            st.markdown("### 🔁 Wiederholbare Abschnitte")
            
            sections = form.get('repeatable_sections', [])
            
            if st.button("➕ Neuen Abschnitt"):
                sections.append({
                    'id': f'section_{uuid.uuid4().hex[:8]}',
                    'label': 'Neuer Abschnitt',
                    'page_id': pages[0]['id'] if pages else '',
                    'min_items': 0,
                    'max_items': 10,
                    'add_button_text': 'Hinzufügen',
                    'item_label_template': 'Eintrag {n}',
                    'fields': [],
                })
                form['repeatable_sections'] = sections
                st.rerun()
            
            for si, section in enumerate(sections):
                with st.expander(f"🔁 {section.get('label', 'Abschnitt')}"):
                    section['label'] = st.text_input("Bezeichnung", value=section.get('label', ''), key=f"sl_{si}")
                    section['page_id'] = st.selectbox("Auf Seite", [p['id'] for p in pages], 
                                                     format_func=lambda x: next((p['title'] for p in pages if p['id'] == x), x),
                                                     key=f"sp_{si}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        section['min_items'] = st.number_input("Min", value=section.get('min_items', 0), key=f"smin_{si}")
                    with col2:
                        section['max_items'] = st.number_input("Max", value=section.get('max_items', 10), key=f"smax_{si}")
                    
                    section['add_button_text'] = st.text_input("Button", value=section.get('add_button_text', 'Hinzufügen'), key=f"sadd_{si}")
                    section['item_label_template'] = st.text_input("Label ({n})", value=section.get('item_label_template', 'Eintrag {n}'), key=f"sitem_{si}")
                    
                    st.markdown("**Felder:**")
                    for fi, field in enumerate(section.get('fields', [])):
                        col1, col2, col3 = st.columns([2, 2, 1])
                        with col1:
                            field['label'] = st.text_input("Label", value=field.get('label', ''), key=f"sfl_{si}_{fi}")
                        with col2:
                            field['type'] = st.selectbox("Typ", list(FIELD_TYPES.keys()), key=f"sft_{si}_{fi}")
                        with col3:
                            if st.button("🗑️", key=f"sfd_{si}_{fi}"):
                                section['fields'].pop(fi)
                                st.rerun()
                    
                    if st.button("➕ Feld", key=f"sfa_{si}"):
                        section['fields'].append({'id': f'f_{uuid.uuid4().hex[:6]}', 'type': 'text', 'label': 'Neues Feld'})
                        st.rerun()
            
            form['repeatable_sections'] = sections
        
        with tab3:
            st.markdown("### ⚙️ Einstellungen")
            
            settings = form.get('settings', {})
            settings['show_progress'] = st.checkbox("Fortschrittsanzeige", value=settings.get('show_progress', True))
            settings['allow_save_draft'] = st.checkbox("Entwurf speichern", value=settings.get('allow_save_draft', True))
            settings['show_review_page'] = st.checkbox("Zusammenfassung", value=settings.get('show_review_page', True))
            settings['submit_button_text'] = st.text_input("Absenden-Button", value=settings.get('submit_button_text', 'Absenden'))
            settings['success_message'] = st.text_area("Erfolgsmeldung", value=settings.get('success_message', 'Vielen Dank!'))
            form['settings'] = settings
            
            st.markdown("---")
            form['status'] = st.selectbox("Status", ['draft', 'active', 'archived'], index=['draft', 'active', 'archived'].index(form.get('status', 'draft')))
            
            if st.button("💾 Speichern", type="primary", key="save_settings"):
                save_form(form)
                st.success("✅ Gespeichert!")
        
        with tab4:
            st.markdown("### ⚡ Workflows")
            
            workflows = form.get('workflows', [])
            
            if st.button("➕ Workflow"):
                workflows.append({
                    'id': f'wf_{uuid.uuid4().hex[:8]}',
                    'name': 'Neuer Workflow',
                    'trigger': 'on_submit',
                    'enabled': True,
                    'actions': [],
                })
                form['workflows'] = workflows
                st.rerun()
            
            for wi, wf in enumerate(workflows):
                with st.expander(f"{'✅' if wf.get('enabled') else '⏸️'} {wf.get('name', 'Workflow')}"):
                    wf['name'] = st.text_input("Name", value=wf.get('name', ''), key=f"wfn_{wi}")
                    wf['enabled'] = st.checkbox("Aktiv", value=wf.get('enabled', True), key=f"wfe_{wi}")
                    
                    for ai, action in enumerate(wf.get('actions', [])):
                        col1, col2, col3 = st.columns([2, 2, 1])
                        with col1:
                            action['type'] = st.selectbox("Typ", ['generate_document', 'send_email', 'webhook'], key=f"wat_{wi}_{ai}")
                        with col2:
                            action['name'] = st.text_input("Name", value=action.get('name', ''), key=f"wan_{wi}_{ai}")
                    
                    if st.button("➕ Aktion", key=f"waa_{wi}"):
                        wf['actions'].append({'type': 'send_email', 'name': 'Neue Aktion', 'config': {}})
                        st.rerun()
            
            form['workflows'] = workflows
        
        with tab5:
            st.markdown("### 👁️ Vorschau")
            
            if st.button("🚀 Formular testen", type="primary"):
                st.session_state.current_form_id = form_id
                st.session_state.current_page_index = 0
                st.session_state.form_values = {}
                st.session_state.repeatable_items = {}
                st.session_state.page = 'form_fill'
                st.rerun()

# ============================================
# Weitere Seiten
# ============================================

def page_submissions():
    st.markdown("# 📥 Einreichungen")
    
    if not st.session_state.submissions:
        st.info("Keine Einreichungen")
        return
    
    for sub_id, sub in st.session_state.submissions.items():
        form = st.session_state.forms.get(sub.get('form_id', ''), {})
        
        with st.expander(f"📄 {sub_id} - {form.get('title', 'Formular')}"):
            st.json(sub.get('data', {}))
            if sub.get('repeatable_data'):
                st.markdown("**Wiederholbar:**")
                st.json(sub.get('repeatable_data', {}))

def page_users():
    render_user_management()

def page_settings():
    st.markdown("# ⚙️ Einstellungen")
    
    tab1, tab2 = st.tabs(["📥 Import/Export", "🔐 Secrets"])
    
    with tab1:
        uploaded = st.file_uploader("JSON importieren", type=['json'])
        if uploaded:
            try:
                data = json.load(uploaded)
                if isinstance(data, list):
                    for form in data:
                        form['id'] = f"form_{uuid.uuid4().hex[:8]}"
                        st.session_state.forms[form['id']] = form
                    st.success(f"✅ {len(data)} Formular(e) importiert")
            except Exception as e:
                st.error(f"Fehler: {e}")
        
        if st.session_state.forms:
            export = json.dumps(list(st.session_state.forms.values()), indent=2, ensure_ascii=False, default=str)
            st.download_button("📥 Exportieren", export, "formulare.json", "application/json")
    
    with tab2:
        st.code("""
# .streamlit/secrets.toml
[auth]
secret_key = "your-secret-key"

[smtp]
host = "smtp.example.com"
port = 587
username = "user@example.com"
password = "password"
        """)

# ============================================
# Hauptanwendung
# ============================================

def main():
    params = st.query_params
    
    # Mandanten-Token?
    if 'invite' in params:
        token = params['invite']
        auth = st.session_state.auth_manager
        mandant_info = auth.verify_mandant_token(token)
        
        if mandant_info:
            st.session_state.is_mandant_mode = True
            st.session_state.mandant_token = token
            st.session_state.mandant_info = mandant_info
            st.session_state.current_form_id = mandant_info.get('form_id')
            st.session_state.page = 'form_fill'
        else:
            st.error("❌ Ungültiger Einladungslink")
            return
    
    # Direkt zu Formular?
    if 'form' in params and not st.session_state.is_mandant_mode:
        form_id = params['form']
        if form_id in st.session_state.forms:
            st.session_state.current_form_id = form_id
            st.session_state.page = 'form_fill'
    
    # Mandanten-Modus
    if st.session_state.is_mandant_mode:
        if st.session_state.page == 'form_fill':
            page_form_fill()
        elif st.session_state.page == 'form_success':
            page_form_success()
        return
    
    # Login
    user = get_current_user()
    
    if not user:
        render_login_form()
        return
    
    render_sidebar()
    
    pages = {
        'dashboard': page_dashboard,
        'editor': page_editor,
        'submissions': page_submissions,
        'users': page_users,
        'settings': page_settings,
        'form_fill': page_form_fill,
        'form_success': page_form_success,
    }
    
    page_func = pages.get(st.session_state.page, page_dashboard)
    page_func()


if __name__ == "__main__":
    main()
