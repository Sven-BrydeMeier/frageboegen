"""
RA-RHM Fragebogen-System
Vollständige Streamlit-App für Mandanten-Fragebögen
Mit JSON-Import, E-Mail-Routing, Einladungslinks und Dokumentengenerierung
"""

import streamlit as st
import json
import base64
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import re
import urllib.parse
from pathlib import Path

# ============================================
# Konfiguration & Konstanten
# ============================================

APP_TITLE = "RA-RHM Fragebogen-System"
APP_ICON = "⚖️"

CATEGORIES = {
    "Notariat": [3, 8, 10, 13, 18],
    "Familienrecht": [5, 6, 16],
    "Arbeitsrecht": [12, 26, 27, 28, 29, 30, 31],
    "Verkehrsrecht": [22],
    "Mietrecht": [24, 25],
    "Zivilrecht": [23],
    "Sonstiges": []
}

CATEGORY_ICONS = {
    "Notariat": "📜",
    "Familienrecht": "👨‍👩‍👧‍👦",
    "Arbeitsrecht": "💼",
    "Verkehrsrecht": "🚗",
    "Mietrecht": "🏠",
    "Zivilrecht": "⚖️",
    "Sonstiges": "📋"
}

DEFAULT_EMPLOYEES = [
    {"name": "Sekretariat", "email": "info@ra-rhm.de", "default": True},
    {"name": "Sven-Bryde Meier (Notar)", "email": "notar@ra-rhm.de", "default": False},
    {"name": "Rechtsanwalt Müller", "email": "mueller@ra-rhm.de", "default": False},
    {"name": "Rechtsanwältin Schmidt", "email": "schmidt@ra-rhm.de", "default": False},
    {"name": "Rechtsanwalt Weber", "email": "weber@ra-rhm.de", "default": False},
]

# ============================================
# Hilfsfunktionen für sichere Dictionary-Zugriffe
# ============================================

def safe_get(obj: Any, key: str, default: Any = None) -> Any:
    """Sicherer Zugriff auf Dictionary-Werte"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default

def ensure_dict(obj: Any) -> Dict:
    """Stellt sicher, dass ein Objekt ein Dictionary ist"""
    if isinstance(obj, dict):
        return obj
    return {}

def ensure_list(obj: Any) -> List:
    """Stellt sicher, dass ein Objekt eine Liste ist"""
    if isinstance(obj, list):
        return obj
    return []

# ============================================
# Session State Initialisierung
# ============================================

def init_session_state():
    """Initialisiert alle Session-State-Variablen"""
    defaults = {
        'forms': {},
        'employees': DEFAULT_EMPLOYEES.copy(),
        'invitations': [],
        'current_form': None,
        'form_values': {},
        'page': 'dashboard',
        'submitted_data': None,
        'json_loaded': False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# ============================================
# JSON Import & Parsing
# ============================================

@st.cache_data
def load_json_file(file_path: str) -> List[Dict]:
    """Lädt JSON-Datei aus dem Dateisystem"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Fehler beim Laden der JSON-Datei: {e}")
        return []

def parse_fluentform_json(json_data: List[Dict]) -> Dict[int, Dict]:
    """Parst FluentForms-Export und konvertiert in internes Format"""
    forms = {}
    
    for form in ensure_list(json_data):
        form = ensure_dict(form)
        form_id = safe_get(form, 'id')
        if not form_id:
            continue
        
        # Felder parsen
        form_fields = safe_get(form, 'form_fields', {})
        if isinstance(form_fields, str):
            try:
                form_fields = json.loads(form_fields)
            except:
                form_fields = {}
        form_fields = ensure_dict(form_fields)
        
        raw_fields = ensure_list(safe_get(form_fields, 'fields', []))
        
        # Felder flach machen (Container auflösen)
        flattened_fields = flatten_fields(raw_fields)
        
        parsed_form = {
            'id': form_id,
            'title': safe_get(form, 'title', f'Formular {form_id}'),
            'status': safe_get(form, 'status', 'published'),
            'fields': flattened_fields,
            'category': get_category_for_form(form_id),
            'field_count': len(flattened_fields)
        }
        
        forms[form_id] = parsed_form
    
    return forms

def get_category_for_form(form_id: int) -> str:
    """Bestimmt die Kategorie eines Formulars"""
    for category, ids in CATEGORIES.items():
        if form_id in ids:
            return category
    return "Sonstiges"

def flatten_fields(fields: List, parent_conditions: List = None) -> List[Dict]:
    """Flacht verschachtelte Felder (Container) ab"""
    result = []
    parent_conditions = parent_conditions or []
    
    for field in ensure_list(fields):
        field = ensure_dict(field)
        element = safe_get(field, 'element', '')
        
        # Container-Felder haben Spalten mit verschachtelten Feldern
        if element == 'container':
            columns = ensure_list(safe_get(field, 'columns', []))
            settings = ensure_dict(safe_get(field, 'settings', {}))
            container_conditions = safe_get(settings, 'conditional_logics', {})
            
            # Conditional Logic vom Container erben
            inherited_conditions = parent_conditions.copy()
            if isinstance(container_conditions, dict) and safe_get(container_conditions, 'status'):
                inherited_conditions.append(container_conditions)
            
            for column in columns:
                column = ensure_dict(column)
                nested_fields = ensure_list(safe_get(column, 'fields', []))
                result.extend(flatten_fields(nested_fields, inherited_conditions))
        else:
            # Normales Feld parsen
            parsed = parse_single_field(field, parent_conditions)
            if parsed:
                result.append(parsed)
    
    return result

def parse_single_field(field: Dict, inherited_conditions: List = None) -> Optional[Dict]:
    """Parst ein einzelnes Formularfeld"""
    field = ensure_dict(field)
    element = safe_get(field, 'element', '')
    attributes = ensure_dict(safe_get(field, 'attributes', {}))
    settings = ensure_dict(safe_get(field, 'settings', {}))
    
    # Leere oder unwichtige Felder überspringen
    if element in ['custom_html', 'form_step', 'input_hidden', 'chained_select', '']:
        return None
    
    # Feldname ermitteln
    field_name = safe_get(attributes, 'name', '')
    if not field_name:
        field_name = f'field_{uuid.uuid4().hex[:8]}'
    
    parsed = {
        'type': element,
        'name': field_name,
        'label': safe_get(settings, 'label', ''),
        'placeholder': safe_get(attributes, 'placeholder', safe_get(settings, 'placeholder', '')),
        'required': False,
        'options': [],
        'conditional_logic': None,
        'description': safe_get(settings, 'description', ''),
        'help_message': safe_get(settings, 'help_message', ''),
        'subfields': {},
        'subfields_visible': {}
    }
    
    # Required prüfen - mehrere mögliche Strukturen
    validation = safe_get(settings, 'validation_rules', {})
    if isinstance(validation, dict):
        required_rule = safe_get(validation, 'required', {})
        if isinstance(required_rule, dict):
            parsed['required'] = bool(safe_get(required_rule, 'value', False))
        elif isinstance(required_rule, bool):
            parsed['required'] = required_rule
    
    # Optionen für Select, Radio, Checkbox
    advanced_options = ensure_list(safe_get(settings, 'advanced_options', []))
    for opt in advanced_options:
        opt = ensure_dict(opt)
        opt_label = safe_get(opt, 'label', '')
        if opt_label:
            parsed['options'].append({
                'label': opt_label,
                'value': safe_get(opt, 'value', opt_label)
            })
    
    # Conditional Logic - kann Dict oder Liste sein!
    cond_logic = safe_get(settings, 'conditional_logics', None)
    if cond_logic is None:
        cond_logic = safe_get(settings, 'conditional_logic', None)
    
    if isinstance(cond_logic, dict) and safe_get(cond_logic, 'status'):
        parsed['conditional_logic'] = {
            'type': safe_get(cond_logic, 'type', 'any'),
            'conditions': ensure_list(safe_get(cond_logic, 'conditions', []))
        }
    elif isinstance(cond_logic, list) and len(cond_logic) > 0:
        # Manchmal ist es direkt eine Liste von Conditions
        parsed['conditional_logic'] = {
            'type': 'any',
            'conditions': cond_logic
        }
    
    # Geerbte Conditions hinzufügen
    if inherited_conditions:
        if not parsed['conditional_logic']:
            parsed['conditional_logic'] = {'type': 'all', 'conditions': []}
        for ic in inherited_conditions:
            if isinstance(ic, dict):
                conditions = ensure_list(safe_get(ic, 'conditions', []))
                parsed['conditional_logic']['conditions'].extend(conditions)
    
    # Spezielle Feldtypen mit Unterfeldern
    if element == 'input_name':
        subfields = ensure_dict(safe_get(field, 'fields', {}))
        for sub_key in ['first_name', 'middle_name', 'last_name']:
            sub_field = ensure_dict(safe_get(subfields, sub_key, {}))
            sub_settings = ensure_dict(safe_get(sub_field, 'settings', {}))
            parsed['subfields'][sub_key] = safe_get(sub_settings, 'label', sub_key.replace('_', ' ').title())
            parsed['subfields_visible'][sub_key] = safe_get(sub_settings, 'visible', True)
    
    elif element == 'address':
        subfields = ensure_dict(safe_get(field, 'fields', {}))
        address_keys = ['address_line_1', 'address_line_2', 'city', 'state', 'zip', 'country']
        default_labels = {
            'address_line_1': 'Straße & Hausnummer',
            'address_line_2': 'Adresszusatz',
            'city': 'Stadt',
            'state': 'Bundesland',
            'zip': 'PLZ',
            'country': 'Land'
        }
        for sub_key in address_keys:
            sub_field = ensure_dict(safe_get(subfields, sub_key, {}))
            sub_settings = ensure_dict(safe_get(sub_field, 'settings', {}))
            parsed['subfields'][sub_key] = safe_get(sub_settings, 'label', default_labels.get(sub_key, sub_key))
            parsed['subfields_visible'][sub_key] = safe_get(sub_settings, 'visible', sub_key in ['address_line_1', 'city', 'zip'])
    
    return parsed

# ============================================
# Conditional Logic Evaluierung
# ============================================

def evaluate_conditional_logic(field: Dict, form_values: Dict) -> bool:
    """Prüft ob ein Feld angezeigt werden soll"""
    cond = safe_get(field, 'conditional_logic')
    if not cond:
        return True
    
    cond = ensure_dict(cond)
    conditions = ensure_list(safe_get(cond, 'conditions', []))
    if not conditions:
        return True
    
    logic_type = safe_get(cond, 'type', 'any')
    results = []
    
    for condition in conditions:
        condition = ensure_dict(condition)
        target_field = safe_get(condition, 'field', '')
        target_value = safe_get(condition, 'value', '')
        operator = safe_get(condition, 'operator', '=')
        
        if not target_field:
            continue
        
        current_value = form_values.get(target_field, '')
        
        # Bei Listen (Checkboxen) prüfen
        if isinstance(current_value, list):
            current_value = ', '.join(str(v) for v in current_value)
        
        # Operator auswerten
        current_str = str(current_value).strip()
        target_str = str(target_value).strip()
        
        if operator in ['=', '==']:
            result = current_str == target_str
        elif operator in ['!=', '<>']:
            result = current_str != target_str
        elif operator == 'contains':
            result = target_str.lower() in current_str.lower()
        elif operator == 'starts_with':
            result = current_str.lower().startswith(target_str.lower())
        elif operator == 'ends_with':
            result = current_str.lower().endswith(target_str.lower())
        elif operator == '>':
            try:
                result = float(current_value) > float(target_value)
            except:
                result = False
        elif operator == '<':
            try:
                result = float(current_value) < float(target_value)
            except:
                result = False
        else:
            result = current_str == target_str
        
        results.append(result)
    
    if not results:
        return True
    
    return all(results) if logic_type == 'all' else any(results)

# ============================================
# Formular-Rendering
# ============================================

def render_form_field(field: Dict, form_values: Dict, key_prefix: str = "") -> Tuple[str, Any]:
    """Rendert ein Formularfeld und gibt (name, value) zurück"""
    field = ensure_dict(field)
    field_type = safe_get(field, 'type', '')
    name = safe_get(field, 'name', '')
    label = safe_get(field, 'label', name)
    required = safe_get(field, 'required', False)
    placeholder = safe_get(field, 'placeholder', '')
    options = ensure_list(safe_get(field, 'options', []))
    description = safe_get(field, 'description', '')
    help_msg = safe_get(field, 'help_message', '')
    subfields = ensure_dict(safe_get(field, 'subfields', {}))
    subfields_visible = ensure_dict(safe_get(field, 'subfields_visible', {}))
    
    key = f"{key_prefix}_{name}"
    
    # Label mit Pflichtfeld-Markierung
    display_label = f"{label} *" if (required and label) else (label or "")
    help_text = help_msg if help_msg else None
    value = None
    
    # === Section Break ===
    if field_type == 'section_break':
        st.markdown("---")
        if label:
            st.markdown(f"### {label}")
        if description:
            st.markdown(description, unsafe_allow_html=True)
        return (name, None)
    
    # === Welcome Screen ===
    elif field_type == 'welcome_screen':
        if label:
            st.markdown(f"## {label}")
        if description:
            st.markdown(description, unsafe_allow_html=True)
        return (name, None)
    
    # === Text Input ===
    elif field_type == 'input_text':
        value = st.text_input(display_label, placeholder=placeholder, help=help_text, key=key)
    
    # === Email Input ===
    elif field_type == 'input_email':
        value = st.text_input(display_label, placeholder=placeholder or "email@beispiel.de", help=help_text, key=key)
    
    # === Phone Input ===
    elif field_type == 'phone':
        value = st.text_input(display_label, placeholder=placeholder or "+49 123 456789", help=help_text, key=key)
    
    # === Number Input ===
    elif field_type == 'input_number':
        value = st.number_input(display_label, help=help_text, key=key, step=1, value=None, min_value=None)
    
    # === Date Input ===
    elif field_type == 'input_date':
        date_val = st.date_input(display_label, help=help_text, key=key, value=None)
        value = date_val.strftime("%d.%m.%Y") if date_val else ""
    
    # === Textarea ===
    elif field_type == 'textarea':
        value = st.text_area(display_label, placeholder=placeholder, help=help_text, key=key, height=120)
    
    # === Select / Dropdown ===
    elif field_type in ['select', 'select_country']:
        if options:
            option_labels = ["Bitte wählen..."] + [safe_get(o, 'label', '') for o in options]
            option_values = [""] + [safe_get(o, 'value', '') for o in options]
            selected_idx = st.selectbox(display_label, range(len(option_labels)), 
                                        format_func=lambda x: option_labels[x], 
                                        help=help_text, key=key)
            value = option_values[selected_idx] if selected_idx > 0 else ""
        else:
            value = st.text_input(display_label, placeholder=placeholder, help=help_text, key=key)
    
    # === Radio Buttons ===
    elif field_type == 'input_radio':
        if options:
            option_labels = [safe_get(o, 'label', '') for o in options]
            option_values = [safe_get(o, 'value', '') for o in options]
            selected = st.radio(display_label, option_labels, help=help_text, key=key, index=None, horizontal=len(options) <= 4)
            if selected:
                idx = option_labels.index(selected)
                value = option_values[idx]
            else:
                value = ""
        else:
            value = ""
    
    # === Checkbox ===
    elif field_type == 'input_checkbox':
        if options and len(options) > 1:
            st.markdown(f"**{display_label}**")
            selected_values = []
            cols = st.columns(min(len(options), 3))
            for i, opt in enumerate(options):
                opt = ensure_dict(opt)
                with cols[i % len(cols)]:
                    if st.checkbox(safe_get(opt, 'label', ''), key=f"{key}_{i}"):
                        selected_values.append(safe_get(opt, 'value', ''))
            value = selected_values
        elif options and len(options) == 1:
            opt = ensure_dict(options[0])
            checked = st.checkbox(f"{display_label}: {safe_get(opt, 'label', '')}", help=help_text, key=key)
            value = safe_get(opt, 'value', '') if checked else ""
        else:
            checked = st.checkbox(display_label, help=help_text, key=key)
            value = "Ja" if checked else "Nein"
    
    # === Name Input ===
    elif field_type == 'input_name':
        if label:
            st.markdown(f"**{display_label}**")
        
        visible_fields = [(k, v) for k, v in subfields.items() if subfields_visible.get(k, True)]
        
        if len(visible_fields) >= 2:
            cols = st.columns(len(visible_fields))
            name_parts = {}
            for i, (sub_key, sub_label) in enumerate(visible_fields):
                with cols[i]:
                    name_parts[sub_key] = st.text_input(sub_label, key=f"{key}_{sub_key}")
            value = " ".join([v for v in name_parts.values() if v])
        else:
            value = st.text_input(display_label, placeholder=placeholder, key=key)
    
    # === Address Input ===
    elif field_type == 'address':
        if label:
            st.markdown(f"**{display_label}**")
        
        address_parts = {}
        
        if subfields_visible.get('address_line_1', True):
            address_parts['street'] = st.text_input(
                subfields.get('address_line_1', 'Straße & Hausnummer'), 
                key=f"{key}_street"
            )
        
        if subfields_visible.get('address_line_2', False):
            address_parts['line2'] = st.text_input(
                subfields.get('address_line_2', 'Adresszusatz'), 
                key=f"{key}_line2"
            )
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if subfields_visible.get('zip', True):
                address_parts['zip'] = st.text_input(
                    subfields.get('zip', 'PLZ'), 
                    key=f"{key}_zip"
                )
        with col2:
            if subfields_visible.get('city', True):
                address_parts['city'] = st.text_input(
                    subfields.get('city', 'Stadt'), 
                    key=f"{key}_city"
                )
        
        if subfields_visible.get('state', False) or subfields_visible.get('country', False):
            col1, col2 = st.columns(2)
            with col1:
                if subfields_visible.get('state', False):
                    address_parts['state'] = st.text_input(
                        subfields.get('state', 'Bundesland'), 
                        key=f"{key}_state"
                    )
            with col2:
                if subfields_visible.get('country', False):
                    address_parts['country'] = st.text_input(
                        subfields.get('country', 'Land'), 
                        key=f"{key}_country"
                    )
        
        parts = []
        if address_parts.get('street'):
            parts.append(address_parts['street'])
        if address_parts.get('line2'):
            parts.append(address_parts['line2'])
        if address_parts.get('zip') or address_parts.get('city'):
            parts.append(f"{address_parts.get('zip', '')} {address_parts.get('city', '')}".strip())
        if address_parts.get('state'):
            parts.append(address_parts['state'])
        if address_parts.get('country'):
            parts.append(address_parts['country'])
        
        value = ", ".join([p for p in parts if p])
    
    # === File Upload ===
    elif field_type == 'input_file':
        uploaded = st.file_uploader(display_label, help=help_text, key=key)
        value = uploaded.name if uploaded else ""
    
    # === GDPR / Terms ===
    elif field_type in ['gdpr_agreement', 'terms_and_condition']:
        clean_label = re.sub('<[^<]+?>', '', description or label or "Ich stimme den Bedingungen zu")
        clean_label = clean_label[:300] + "..." if len(clean_label) > 300 else clean_label
        
        if description and len(description) > 100:
            with st.expander("📋 Details anzeigen"):
                st.markdown(description, unsafe_allow_html=True)
        
        checked = st.checkbox(f"✓ {clean_label}", key=key)
        value = "Zugestimmt" if checked else "Nicht zugestimmt"
    
    # === Fallback ===
    else:
        if label:
            value = st.text_input(display_label, placeholder=placeholder, help=help_text, key=key)
    
    return (name, value)

# ============================================
# Einladungssystem
# ============================================

def generate_invitation_token(form_id: int, mandant_name: str = "", expires_days: int = 7) -> str:
    """Generiert einen Einladungstoken"""
    expires = datetime.now() + timedelta(days=expires_days)
    data = {
        'form_id': form_id,
        'expires': expires.isoformat(),
        'mandant': mandant_name,
        'uuid': uuid.uuid4().hex[:8]
    }
    token = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    return token

def decode_invitation_token(token: str) -> Optional[Dict]:
    """Dekodiert einen Einladungstoken"""
    try:
        data = json.loads(base64.urlsafe_b64decode(token.encode()).decode())
        expires = datetime.fromisoformat(data['expires'])
        if datetime.now() > expires:
            return None
        return data
    except:
        return None

def create_invitation_link(form_id: int, mandant_name: str = "", base_url: str = "") -> Tuple[str, str]:
    """Erstellt Einladungslink und Token"""
    token = generate_invitation_token(form_id, mandant_name)
    
    form = st.session_state.forms.get(form_id, {})
    form_title = safe_get(form, 'title', f'Formular {form_id}')
    invitation = {
        'token': token,
        'form_id': form_id,
        'form_title': form_title,
        'mandant': mandant_name,
        'created': datetime.now().isoformat(),
        'expires': (datetime.now() + timedelta(days=7)).isoformat()
    }
    st.session_state.invitations.append(invitation)
    
    link = f"{base_url}?invite={token}" if base_url else f"?invite={token}"
    return link, token

def create_email_mailto(form_id: int, recipient_email: str, invite_link: str) -> str:
    """Erstellt Mailto-Link"""
    form = st.session_state.forms.get(form_id, {})
    form_title = safe_get(form, 'title', f'Formular {form_id}')
    
    subject = f"Einladung: {form_title} - RA-RHM Rechtsanwaltskanzlei"
    body = f"""Sehr geehrte Damen und Herren,

Sie wurden eingeladen, den folgenden Fragebogen auszufüllen:

📋 {form_title}

Bitte klicken Sie auf den folgenden Link:
{invite_link}

⏰ Der Link ist 7 Tage gültig.

Mit freundlichen Grüßen
RA-RHM Rechtsanwaltskanzlei

---
Tel: 04331 732970
E-Mail: info@ra-rhm.de
"""
    
    return f"mailto:{recipient_email}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"

# ============================================
# Dokumentengenerierung
# ============================================

def generate_document(form: Dict, form_data: Dict, recipient_email: str) -> str:
    """Generiert Textdokument aus Formulardaten"""
    form = ensure_dict(form)
    form_title = safe_get(form, 'title', 'Formular')
    
    lines = []
    lines.append("=" * 70)
    lines.append(f"  {form_title}")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"📅 Erstellt am: {datetime.now().strftime('%d.%m.%Y um %H:%M Uhr')}")
    lines.append(f"📧 Empfänger: {recipient_email}")
    lines.append("")
    lines.append("-" * 70)
    lines.append("  FORMULARDATEN")
    lines.append("-" * 70)
    lines.append("")
    
    # Feld-Labels aus Form extrahieren
    field_labels = {}
    for field in ensure_list(safe_get(form, 'fields', [])):
        field = ensure_dict(field)
        fname = safe_get(field, 'name', '')
        flabel = safe_get(field, 'label', fname)
        if fname and flabel:
            field_labels[fname] = flabel
    
    for name, value in form_data.items():
        if value and str(value).strip() and str(value) not in ['Nein', 'Nicht zugestimmt', '[]', '']:
            label = field_labels.get(name, name)
            if label:
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                lines.append(f"▸ {label}:")
                lines.append(f"  {value}")
                lines.append("")
    
    lines.append("-" * 70)
    lines.append("")
    lines.append("📌 Dieses Dokument wurde automatisch generiert.")
    lines.append("   RA-RHM Rechtsanwaltskanzlei")
    lines.append("   Tel: 04331 732970 | E-Mail: info@ra-rhm.de")
    lines.append("")
    lines.append("=" * 70)
    
    return "\n".join(lines)

# ============================================
# Sidebar
# ============================================

def render_sidebar():
    """Rendert die Sidebar-Navigation"""
    with st.sidebar:
        st.markdown("## 📂 Navigation")
        
        if st.button("🏠 Dashboard", use_container_width=True, type="primary" if st.session_state.page == 'dashboard' else "secondary"):
            st.session_state.page = 'dashboard'
            st.session_state.current_form = None
            st.rerun()
        
        if st.button("📨 Einladungen", use_container_width=True, type="primary" if st.session_state.page == 'invitations' else "secondary"):
            st.session_state.page = 'invitations'
            st.rerun()
        
        if st.button("⚙️ Einstellungen", use_container_width=True, type="primary" if st.session_state.page == 'settings' else "secondary"):
            st.session_state.page = 'settings'
            st.rerun()
        
        st.markdown("---")
        
        st.markdown("### 📊 Statistiken")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Formulare", len(st.session_state.forms))
        with col2:
            st.metric("Einladungen", len(st.session_state.invitations))
        
        if st.session_state.forms:
            st.markdown("---")
            st.markdown("### ⚡ Schnellzugriff")
            
            for cat in CATEGORIES.keys():
                forms_in_cat = [f for f in st.session_state.forms.values() if safe_get(f, 'category') == cat]
                if forms_in_cat:
                    with st.expander(f"{CATEGORY_ICONS.get(cat, '📋')} {cat}"):
                        for form in forms_in_cat:
                            form = ensure_dict(form)
                            title = safe_get(form, 'title', 'Unbenannt')[:25]
                            form_id = safe_get(form, 'id')
                            if st.button(f"📝 {title}...", key=f"quick_{form_id}", use_container_width=True):
                                st.session_state.current_form = form_id
                                st.session_state.page = 'form'
                                st.rerun()
        
        st.markdown("---")
        st.caption("© 2025 RA-RHM")
        st.caption("Tel: 04331 732970")

# ============================================
# Seiten
# ============================================

def page_dashboard():
    """Dashboard-Seite"""
    st.markdown("## 📊 Dashboard")
    
    if not st.session_state.forms:
        st.warning("⚠️ Keine Formulare geladen.")
        
        st.markdown("### 📥 Formulare importieren")
        
        json_path = Path("fluentform-export-forms-29-20-01-2026.json")
        
        if json_path.exists():
            if st.button("📂 Formulare aus JSON laden", type="primary"):
                with st.spinner("Lade Formulare..."):
                    json_data = load_json_file(str(json_path))
                    if json_data:
                        st.session_state.forms = parse_fluentform_json(json_data)
                        st.session_state.json_loaded = True
                        st.success(f"✅ {len(st.session_state.forms)} Formulare geladen!")
                        st.rerun()
        
        st.markdown("**Oder JSON-Datei hochladen:**")
        uploaded = st.file_uploader("FluentForms Export (.json)", type=['json'])
        if uploaded:
            try:
                json_data = json.load(uploaded)
                st.session_state.forms = parse_fluentform_json(json_data)
                st.session_state.json_loaded = True
                st.success(f"✅ {len(st.session_state.forms)} Formulare importiert!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Fehler: {e}")
        return
    
    st.markdown("### 📋 Verfügbare Fragebögen")
    
    categories_with_forms = [cat for cat in CATEGORIES.keys() 
                            if any(safe_get(f, 'category') == cat for f in st.session_state.forms.values())]
    
    if categories_with_forms:
        tabs = st.tabs([f"{CATEGORY_ICONS.get(cat, '📋')} {cat}" for cat in categories_with_forms])
        
        for tab, category in zip(tabs, categories_with_forms):
            with tab:
                forms_in_cat = [f for f in st.session_state.forms.values() if safe_get(f, 'category') == category]
                
                for form in forms_in_cat:
                    form = ensure_dict(form)
                    form_id = safe_get(form, 'id')
                    form_title = safe_get(form, 'title', 'Unbenannt')
                    field_count = safe_get(form, 'field_count', 0)
                    
                    with st.container():
                        col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
                        
                        with col1:
                            st.markdown(f"**{form_title}**")
                            st.caption(f"{field_count} Felder")
                        
                        with col2:
                            if st.button("📝 Ausfüllen", key=f"open_{form_id}"):
                                st.session_state.current_form = form_id
                                st.session_state.page = 'form'
                                st.session_state.form_values = {}
                                st.rerun()
                        
                        with col3:
                            if st.button("🔗 Einladung", key=f"invite_{form_id}"):
                                st.session_state.current_form = form_id
                                st.session_state.page = 'invite'
                                st.rerun()
                        
                        with col4:
                            if st.button("👁️ Vorschau", key=f"preview_{form_id}"):
                                st.session_state.current_form = form_id
                                st.session_state.page = 'preview'
                                st.rerun()
                        
                        st.markdown("---")

def page_form():
    """Formular-Seite"""
    if not st.session_state.current_form:
        st.session_state.page = 'dashboard'
        st.rerun()
        return
    
    form = st.session_state.forms.get(st.session_state.current_form)
    if not form:
        st.error("Formular nicht gefunden")
        return
    
    form = ensure_dict(form)
    
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← Zurück"):
            st.session_state.page = 'dashboard'
            st.session_state.current_form = None
            st.session_state.form_values = {}
            st.rerun()
    with col2:
        st.markdown(f"### 📋 {safe_get(form, 'title', 'Formular')}")
    
    st.markdown("---")
    
    with st.form(key=f"form_{safe_get(form, 'id')}_main"):
        form_values = {}
        
        for field in ensure_list(safe_get(form, 'fields', [])):
            field = ensure_dict(field)
            
            if not evaluate_conditional_logic(field, {**st.session_state.form_values, **form_values}):
                continue
            
            name, value = render_form_field(field, form_values, f"f{safe_get(form, 'id')}")
            
            if name and value is not None:
                form_values[name] = value
                st.session_state.form_values[name] = value
        
        st.markdown("---")
        
        st.markdown("### 📧 Empfänger auswählen")
        employee_options = [f"{safe_get(e, 'name', '')} ({safe_get(e, 'email', '')})" for e in st.session_state.employees]
        default_idx = next((i for i, e in enumerate(st.session_state.employees) if safe_get(e, 'default', False)), 0)
        selected_emp = st.selectbox("An wen soll das Formular gesendet werden?", employee_options, index=default_idx)
        recipient_email = safe_get(st.session_state.employees[employee_options.index(selected_emp)], 'email', 'info@ra-rhm.de')
        
        submitted = st.form_submit_button("📤 Formular absenden", type="primary", use_container_width=True)
        
        if submitted:
            document = generate_document(form, form_values, recipient_email)
            st.session_state.submitted_data = {
                'form': form,
                'data': form_values,
                'document': document,
                'recipient': recipient_email
            }
            st.session_state.page = 'success'
            st.rerun()

def page_success():
    """Erfolgsseite"""
    st.markdown("## ✅ Formular erfolgreich ausgefüllt!")
    
    data = st.session_state.submitted_data
    if not data:
        st.session_state.page = 'dashboard'
        st.rerun()
        return
    
    form = ensure_dict(data.get('form', {}))
    form_title = safe_get(form, 'title', 'Formular')
    st.success(f"Das Formular **{form_title}** wurde erfolgreich verarbeitet.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📥 Download")
        filename = f"{form_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        st.download_button(
            "📄 Dokument herunterladen",
            data['document'],
            file_name=filename,
            mime="text/plain",
            use_container_width=True
        )
    
    with col2:
        st.markdown("### 📧 Per E-Mail senden")
        subject = f"Formular: {form_title}"
        mailto = f"mailto:{data['recipient']}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(data['document'][:1500])}"
        st.markdown(f"[📧 E-Mail öffnen]({mailto})")
        st.caption(f"Empfänger: {data['recipient']}")
    
    st.markdown("---")
    
    with st.expander("📄 Dokument-Vorschau", expanded=True):
        st.text(data['document'])
    
    st.markdown("---")
    
    if st.button("← Zurück zum Dashboard", type="primary"):
        st.session_state.submitted_data = None
        st.session_state.page = 'dashboard'
        st.session_state.current_form = None
        st.session_state.form_values = {}
        st.rerun()

def page_invite():
    """Einladungsseite"""
    if not st.session_state.current_form:
        st.session_state.page = 'dashboard'
        st.rerun()
        return
    
    form = st.session_state.forms.get(st.session_state.current_form)
    if not form:
        st.error("Formular nicht gefunden")
        return
    
    form = ensure_dict(form)
    
    if st.button("← Zurück"):
        st.session_state.page = 'dashboard'
        st.session_state.current_form = None
        st.rerun()
    
    st.markdown(f"## 🔗 Einladung erstellen")
    st.markdown(f"**Formular:** {safe_get(form, 'title', 'Unbenannt')}")
    
    st.markdown("---")
    
    base_url = st.text_input(
        "🌐 App-URL (Ihre Streamlit-App)",
        value="https://ihre-app.streamlit.app",
        help="Die URL unter der Ihre App erreichbar ist"
    )
    
    mandant_name = st.text_input("👤 Name des Mandanten (optional)", placeholder="Max Mustermann")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🔗 Einladungslink")
        
        if st.button("✨ Link generieren", type="primary", use_container_width=True):
            link, token = create_invitation_link(safe_get(form, 'id'), mandant_name, base_url)
            st.session_state['generated_link'] = link
        
        if 'generated_link' in st.session_state:
            st.code(st.session_state['generated_link'])
            st.success("✅ Link erstellt! Gültig für 7 Tage.")
    
    with col2:
        st.markdown("### 📧 E-Mail-Einladung")
        
        recipient = st.text_input("E-Mail-Adresse", placeholder="mandant@beispiel.de")
        
        if st.button("📧 E-Mail erstellen", use_container_width=True) and recipient:
            link, _ = create_invitation_link(safe_get(form, 'id'), mandant_name, base_url)
            mailto = create_email_mailto(safe_get(form, 'id'), recipient, link)
            st.markdown(f"[📧 E-Mail-Programm öffnen]({mailto})")

def page_invitations():
    """Einladungsverwaltung"""
    st.markdown("## 📨 Einladungsverwaltung")
    
    if not st.session_state.invitations:
        st.info("📭 Noch keine Einladungen erstellt.")
        return
    
    st.markdown(f"**{len(st.session_state.invitations)} Einladungen**")
    st.markdown("---")
    
    for inv in reversed(st.session_state.invitations):
        inv = ensure_dict(inv)
        expires_str = safe_get(inv, 'expires', '')
        try:
            expires = datetime.fromisoformat(expires_str)
            is_expired = datetime.now() > expires
        except:
            is_expired = True
        
        status_icon = "🔴" if is_expired else "🟢"
        status_text = "Abgelaufen" if is_expired else "Aktiv"
        
        with st.expander(f"{status_icon} {safe_get(inv, 'form_title', 'Formular')} - {status_text}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Erstellt:** {safe_get(inv, 'created', '')[:16].replace('T', ' ')}")
                st.write(f"**Gültig bis:** {expires_str[:16].replace('T', ' ')}")
            with col2:
                mandant = safe_get(inv, 'mandant', '')
                if mandant:
                    st.write(f"**Mandant:** {mandant}")
            
            if not is_expired:
                st.code(f"?invite={safe_get(inv, 'token', '')}")

def page_settings():
    """Einstellungsseite"""
    st.markdown("## ⚙️ Einstellungen")
    
    st.markdown("### 📥 Formulare importieren")
    
    uploaded = st.file_uploader("FluentForms-Export hochladen", type=['json'], key="settings_upload")
    
    if uploaded:
        try:
            json_data = json.load(uploaded)
            st.session_state.forms = parse_fluentform_json(json_data)
            st.success(f"✅ {len(st.session_state.forms)} Formulare importiert!")
        except Exception as e:
            st.error(f"❌ Fehler: {e}")
    
    st.markdown("---")
    
    st.markdown("### 👥 Mitarbeiter verwalten")
    
    for i, emp in enumerate(st.session_state.employees):
        emp = ensure_dict(emp)
        col1, col2, col3, col4 = st.columns([3, 3, 1, 1])
        
        with col1:
            new_name = st.text_input("Name", value=safe_get(emp, 'name', ''), key=f"emp_name_{i}", label_visibility="collapsed")
            st.session_state.employees[i]['name'] = new_name
        
        with col2:
            new_email = st.text_input("E-Mail", value=safe_get(emp, 'email', ''), key=f"emp_email_{i}", label_visibility="collapsed")
            st.session_state.employees[i]['email'] = new_email
        
        with col3:
            is_default = st.checkbox("Standard", value=safe_get(emp, 'default', False), key=f"emp_def_{i}")
            if is_default:
                for j in range(len(st.session_state.employees)):
                    st.session_state.employees[j]['default'] = (j == i)
        
        with col4:
            if st.button("🗑️", key=f"del_emp_{i}"):
                st.session_state.employees.pop(i)
                st.rerun()
    
    st.markdown("---")
    
    st.markdown("**Neuen Mitarbeiter hinzufügen:**")
    col1, col2, col3 = st.columns([3, 3, 1])
    
    with col1:
        new_name = st.text_input("Name", key="new_emp_name", placeholder="Name")
    with col2:
        new_email = st.text_input("E-Mail", key="new_emp_email", placeholder="email@ra-rhm.de")
    with col3:
        if st.button("➕", key="add_emp"):
            if new_name and new_email:
                st.session_state.employees.append({
                    'name': new_name,
                    'email': new_email,
                    'default': False
                })
                st.success(f"✅ {new_name} hinzugefügt!")
                st.rerun()
    
    st.markdown("---")
    
    st.markdown("### 🔄 Zurücksetzen")
    
    if st.button("🗑️ Alle Daten zurücksetzen", type="secondary"):
        st.session_state.forms = {}
        st.session_state.employees = DEFAULT_EMPLOYEES.copy()
        st.session_state.invitations = []
        st.session_state.json_loaded = False
        st.success("✅ Alle Daten zurückgesetzt!")
        st.rerun()

def page_preview():
    """Formular-Vorschau"""
    if not st.session_state.current_form:
        st.session_state.page = 'dashboard'
        st.rerun()
        return
    
    form = st.session_state.forms.get(st.session_state.current_form)
    if not form:
        st.error("Formular nicht gefunden")
        return
    
    form = ensure_dict(form)
    
    if st.button("← Zurück"):
        st.session_state.page = 'dashboard'
        st.session_state.current_form = None
        st.rerun()
    
    st.markdown(f"## 👁️ Vorschau: {safe_get(form, 'title', 'Formular')}")
    st.markdown(f"**Kategorie:** {CATEGORY_ICONS.get(safe_get(form, 'category', 'Sonstiges'), '📋')} {safe_get(form, 'category', 'Sonstiges')}")
    st.markdown(f"**Anzahl Felder:** {safe_get(form, 'field_count', 0)}")
    
    st.markdown("---")
    st.markdown("### Feldübersicht")
    
    for i, field in enumerate(ensure_list(safe_get(form, 'fields', [])), 1):
        field = ensure_dict(field)
        ftype = safe_get(field, 'type', 'unknown')
        flabel = safe_get(field, 'label', '-')
        freq = "✓" if safe_get(field, 'required', False) else ""
        fcond = "🔀" if safe_get(field, 'conditional_logic') else ""
        
        if ftype not in ['section_break', 'welcome_screen']:
            st.markdown(f"{i}. **{flabel}** `{ftype}` {freq} {fcond}")

# ============================================
# Main
# ============================================

def main():
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=APP_ICON,
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 50%, #f5f5f4 100%); }
        section[data-testid="stSidebar"] { background: linear-gradient(180deg, #78350f 0%, #92400e 100%); }
        section[data-testid="stSidebar"] * { color: white !important; }
        section[data-testid="stSidebar"] .stButton button { background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); }
        section[data-testid="stSidebar"] .stButton button:hover { background: rgba(255,255,255,0.2); }
        h1, h2, h3 { color: #78350f !important; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .stTabs [data-baseweb="tab"] { background-color: #fef3c7; border-radius: 8px 8px 0 0; }
        .stTabs [aria-selected="true"] { background-color: #b45309 !important; color: white !important; }
        div[data-testid="stExpander"] { background: white; border-radius: 8px; border: 1px solid #e5e5e5; }
    </style>
    """, unsafe_allow_html=True)
    
    init_session_state()
    
    # URL-Parameter prüfen
    query_params = st.query_params
    if 'invite' in query_params:
        token = query_params['invite']
        data = decode_invitation_token(token)
        if data:
            if not st.session_state.forms:
                json_path = Path("fluentform-export-forms-29-20-01-2026.json")
                if json_path.exists():
                    json_data = load_json_file(str(json_path))
                    if json_data:
                        st.session_state.forms = parse_fluentform_json(json_data)
            
            form_id = safe_get(data, 'form_id')
            if form_id and form_id in st.session_state.forms:
                st.session_state.current_form = form_id
                st.session_state.page = 'form'
            else:
                st.error("❌ Formular nicht gefunden.")
        else:
            st.error("❌ Ungültiger oder abgelaufener Einladungslink.")
    
    render_sidebar()
    
    if st.session_state.page == 'dashboard':
        page_dashboard()
    elif st.session_state.page == 'form':
        page_form()
    elif st.session_state.page == 'success':
        page_success()
    elif st.session_state.page == 'invite':
        page_invite()
    elif st.session_state.page == 'invitations':
        page_invitations()
    elif st.session_state.page == 'settings':
        page_settings()
    elif st.session_state.page == 'preview':
        page_preview()

if __name__ == "__main__":
    main()
