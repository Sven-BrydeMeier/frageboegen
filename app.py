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
import io

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

CATEGORY_COLORS = {
    "Notariat": "#b45309",
    "Familienrecht": "#be185d",
    "Arbeitsrecht": "#1d4ed8",
    "Verkehrsrecht": "#059669",
    "Mietrecht": "#7c3aed",
    "Zivilrecht": "#dc2626",
    "Sonstiges": "#6b7280"
}

DEFAULT_EMPLOYEES = [
    {"name": "Sekretariat", "email": "info@ra-rhm.de", "default": True},
    {"name": "Sven-Bryde Meier (Notar)", "email": "notar@ra-rhm.de", "default": False},
    {"name": "Rechtsanwalt Müller", "email": "mueller@ra-rhm.de", "default": False},
    {"name": "Rechtsanwältin Schmidt", "email": "schmidt@ra-rhm.de", "default": False},
    {"name": "Rechtsanwalt Weber", "email": "weber@ra-rhm.de", "default": False},
]

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
        'show_success_toast': False,
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
    
    for form in json_data:
        form_id = form.get('id')
        if not form_id:
            continue
        
        # Felder parsen
        form_fields = form.get('form_fields', {})
        if isinstance(form_fields, str):
            try:
                form_fields = json.loads(form_fields)
            except:
                form_fields = {}
        
        raw_fields = form_fields.get('fields', [])
        
        # Felder flach machen (Container auflösen)
        flattened_fields = flatten_fields(raw_fields)
        
        parsed_form = {
            'id': form_id,
            'title': form.get('title', f'Formular {form_id}'),
            'status': form.get('status', 'published'),
            'fields': flattened_fields,
            'category': get_category_for_form(form_id),
            'field_count': len(flattened_fields)
        }
        
        forms[form_id] = parsed_form
    
    return forms

def flatten_fields(fields: List[Dict], parent_conditions: List = None) -> List[Dict]:
    """Flacht verschachtelte Felder (Container) ab"""
    result = []
    parent_conditions = parent_conditions or []
    
    for field in fields:
        element = field.get('element', '')
        
        # Container-Felder haben Spalten mit verschachtelten Feldern
        if element == 'container':
            columns = field.get('columns', [])
            container_conditions = field.get('settings', {}).get('conditional_logics', {})
            
            # Conditional Logic vom Container erben
            inherited_conditions = parent_conditions.copy()
            if container_conditions and container_conditions.get('status'):
                inherited_conditions.append(container_conditions)
            
            for column in columns:
                nested_fields = column.get('fields', [])
                result.extend(flatten_fields(nested_fields, inherited_conditions))
        else:
            # Normales Feld parsen
            parsed = parse_single_field(field, parent_conditions)
            if parsed:
                result.append(parsed)
    
    return result

def parse_single_field(field: Dict, inherited_conditions: List = None) -> Optional[Dict]:
    """Parst ein einzelnes Formularfeld"""
    element = field.get('element', '')
    attributes = field.get('attributes', {})
    settings = field.get('settings', {})
    
    # Leere oder unwichtige Felder überspringen
    if element in ['custom_html', 'form_step', 'input_hidden', 'chained_select']:
        return None
    
    parsed = {
        'type': element,
        'name': attributes.get('name', f'field_{uuid.uuid4().hex[:8]}'),
        'label': settings.get('label', ''),
        'placeholder': attributes.get('placeholder', settings.get('placeholder', '')),
        'required': False,
        'options': [],
        'conditional_logic': None,
        'description': settings.get('description', ''),
        'help_message': settings.get('help_message', ''),
        'subfields': {}
    }
    
    # Required prüfen
    validation = settings.get('validation_rules', {})
    if isinstance(validation, dict):
        required_rule = validation.get('required', {})
        if isinstance(required_rule, dict):
            parsed['required'] = required_rule.get('value', False)
    
    # Optionen für Select, Radio, Checkbox
    advanced_options = settings.get('advanced_options', [])
    if advanced_options:
        parsed['options'] = [
            {'label': opt.get('label', ''), 'value': opt.get('value', opt.get('label', ''))}
            for opt in advanced_options if opt.get('label')
        ]
    
    # Conditional Logic
    cond_logic = settings.get('conditional_logics', {})
    if isinstance(cond_logic, dict) and cond_logic.get('status'):
        parsed['conditional_logic'] = {
            'type': cond_logic.get('type', 'any'),
            'conditions': cond_logic.get('conditions', [])
        }
    
    # Geerbte Conditions hinzufügen
    if inherited_conditions:
        if not parsed['conditional_logic']:
            parsed['conditional_logic'] = {'type': 'all', 'conditions': []}
        for ic in inherited_conditions:
            if isinstance(ic, dict) and ic.get('conditions'):
                parsed['conditional_logic']['conditions'].extend(ic.get('conditions', []))
    
    # Spezielle Feldtypen mit Unterfeldern
    if element == 'input_name':
        subfields = field.get('fields', {})
        parsed['subfields'] = {
            'first_name': subfields.get('first_name', {}).get('settings', {}).get('label', 'Vorname'),
            'middle_name': subfields.get('middle_name', {}).get('settings', {}).get('label', 'Nachname'),
            'last_name': subfields.get('last_name', {}).get('settings', {}).get('label', 'Geburtsname'),
        }
        # Sichtbarkeit prüfen
        parsed['subfields_visible'] = {
            'first_name': subfields.get('first_name', {}).get('settings', {}).get('visible', True),
            'middle_name': subfields.get('middle_name', {}).get('settings', {}).get('visible', True),
            'last_name': subfields.get('last_name', {}).get('settings', {}).get('visible', True),
        }
    
    elif element == 'address':
        subfields = field.get('fields', {})
        parsed['subfields'] = {
            'address_line_1': subfields.get('address_line_1', {}).get('settings', {}).get('label', 'Straße'),
            'address_line_2': subfields.get('address_line_2', {}).get('settings', {}).get('label', 'Adresszusatz'),
            'city': subfields.get('city', {}).get('settings', {}).get('label', 'Stadt'),
            'state': subfields.get('state', {}).get('settings', {}).get('label', 'Bundesland'),
            'zip': subfields.get('zip', {}).get('settings', {}).get('label', 'PLZ'),
            'country': subfields.get('country', {}).get('settings', {}).get('label', 'Land'),
        }
        parsed['subfields_visible'] = {
            key: subfields.get(key, {}).get('settings', {}).get('visible', True)
            for key in parsed['subfields'].keys()
        }
    
    return parsed

def get_category_for_form(form_id: int) -> str:
    """Bestimmt die Kategorie eines Formulars"""
    for category, ids in CATEGORIES.items():
        if form_id in ids:
            return category
    return "Sonstiges"

# ============================================
# Conditional Logic Evaluierung
# ============================================

def evaluate_conditional_logic(field: Dict, form_values: Dict) -> bool:
    """Prüft ob ein Feld angezeigt werden soll"""
    cond = field.get('conditional_logic')
    if not cond:
        return True
    
    conditions = cond.get('conditions', [])
    if not conditions:
        return True
    
    logic_type = cond.get('type', 'any')
    results = []
    
    for condition in conditions:
        target_field = condition.get('field', '')
        target_value = condition.get('value', '')
        operator = condition.get('operator', '=')
        
        if not target_field:
            continue
        
        current_value = form_values.get(target_field, '')
        
        # Bei Listen (Checkboxen) prüfen
        if isinstance(current_value, list):
            current_value = ', '.join(current_value)
        
        # Operator auswerten
        if operator in ['=', '==']:
            result = str(current_value) == str(target_value)
        elif operator in ['!=', '<>']:
            result = str(current_value) != str(target_value)
        elif operator == 'contains':
            result = str(target_value).lower() in str(current_value).lower()
        elif operator == 'starts_with':
            result = str(current_value).lower().startswith(str(target_value).lower())
        elif operator == 'ends_with':
            result = str(current_value).lower().endswith(str(target_value).lower())
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
        elif operator == '>=':
            try:
                result = float(current_value) >= float(target_value)
            except:
                result = False
        elif operator == '<=':
            try:
                result = float(current_value) <= float(target_value)
            except:
                result = False
        else:
            result = str(current_value) == str(target_value)
        
        results.append(result)
    
    if not results:
        return True
    
    return all(results) if logic_type == 'all' else any(results)

# ============================================
# Formular-Rendering
# ============================================

def render_form_field(field: Dict, form_values: Dict, key_prefix: str = "") -> Tuple[str, Any]:
    """Rendert ein Formularfeld und gibt (name, value) zurück"""
    field_type = field.get('type', '')
    name = field.get('name', '')
    label = field.get('label', name)
    required = field.get('required', False)
    placeholder = field.get('placeholder', '')
    options = field.get('options', [])
    description = field.get('description', '')
    help_msg = field.get('help_message', '')
    subfields = field.get('subfields', {})
    subfields_visible = field.get('subfields_visible', {})
    
    key = f"{key_prefix}_{name}"
    
    # Label mit Pflichtfeld-Markierung
    if label:
        display_label = f"{label} *" if required else label
    else:
        display_label = ""
    
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
            option_labels = ["Bitte wählen..."] + [opt['label'] for opt in options]
            option_values = [""] + [opt['value'] for opt in options]
            selected_idx = st.selectbox(display_label, range(len(option_labels)), 
                                        format_func=lambda x: option_labels[x], 
                                        help=help_text, key=key)
            value = option_values[selected_idx] if selected_idx > 0 else ""
        else:
            value = st.text_input(display_label, placeholder=placeholder, help=help_text, key=key)
    
    # === Radio Buttons ===
    elif field_type == 'input_radio':
        if options:
            option_labels = [opt['label'] for opt in options]
            option_values = [opt['value'] for opt in options]
            selected = st.radio(display_label, option_labels, help=help_text, key=key, index=None, horizontal=len(options) <= 4)
            if selected:
                idx = option_labels.index(selected)
                value = option_values[idx]
            else:
                value = ""
        else:
            value = ""
    
    # === Checkbox (Single or Multiple) ===
    elif field_type == 'input_checkbox':
        if options and len(options) > 1:
            st.markdown(f"**{display_label}**")
            selected_values = []
            cols = st.columns(min(len(options), 3))
            for i, opt in enumerate(options):
                with cols[i % len(cols)]:
                    if st.checkbox(opt['label'], key=f"{key}_{i}"):
                        selected_values.append(opt['value'])
            value = selected_values
        elif options and len(options) == 1:
            checked = st.checkbox(f"{display_label}: {options[0]['label']}", help=help_text, key=key)
            value = options[0]['value'] if checked else ""
        else:
            checked = st.checkbox(display_label, help=help_text, key=key)
            value = "Ja" if checked else "Nein"
    
    # === Name Input (Composite) ===
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
    
    # === Address Input (Composite) ===
    elif field_type == 'address':
        if label:
            st.markdown(f"**{display_label}**")
        
        address_parts = {}
        
        # Straße
        if subfields_visible.get('address_line_1', True):
            address_parts['street'] = st.text_input(
                subfields.get('address_line_1', 'Straße & Hausnummer'), 
                key=f"{key}_street"
            )
        
        # Adresszusatz (optional)
        if subfields_visible.get('address_line_2', False):
            address_parts['line2'] = st.text_input(
                subfields.get('address_line_2', 'Adresszusatz'), 
                key=f"{key}_line2"
            )
        
        # PLZ und Stadt
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
        
        # Bundesland und Land (falls sichtbar)
        show_state = subfields_visible.get('state', False)
        show_country = subfields_visible.get('country', False)
        
        if show_state or show_country:
            col1, col2 = st.columns(2)
            with col1:
                if show_state:
                    address_parts['state'] = st.text_input(
                        subfields.get('state', 'Bundesland'), 
                        key=f"{key}_state"
                    )
            with col2:
                if show_country:
                    address_parts['country'] = st.text_input(
                        subfields.get('country', 'Land'), 
                        key=f"{key}_country"
                    )
        
        # Adresse zusammenbauen
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
    
    # === GDPR / Terms Agreement ===
    elif field_type in ['gdpr_agreement', 'terms_and_condition']:
        # HTML-Tags entfernen
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
    
    form_title = st.session_state.forms.get(form_id, {}).get('title', f'Formular {form_id}')
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
    """Erstellt Mailto-Link für Einladung"""
    form_title = st.session_state.forms.get(form_id, {}).get('title', f'Formular {form_id}')
    
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
    lines = []
    
    lines.append("=" * 70)
    lines.append(f"  {form.get('title', 'Formular')}")
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
    for field in form.get('fields', []):
        fname = field.get('name', '')
        flabel = field.get('label', fname)
        if fname and flabel:
            field_labels[fname] = flabel
    
    for name, value in form_data.items():
        if value and str(value).strip() and value not in ['Nein', 'Nicht zugestimmt', '[]', '']:
            label = field_labels.get(name, name)
            if label:
                # Listen formatieren
                if isinstance(value, list):
                    value = ", ".join(value)
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
# UI Komponenten
# ============================================

def render_header():
    """Rendert den App-Header"""
    col1, col2 = st.columns([1, 4])
    with col1:
        st.markdown("# ⚖️")
    with col2:
        st.markdown("# RA-RHM Rechtsanwaltskanzlei")
        st.caption("Fragebogen-System für Mandanten")

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
        
        # Statistiken
        st.markdown("### 📊 Statistiken")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Formulare", len(st.session_state.forms))
        with col2:
            st.metric("Einladungen", len(st.session_state.invitations))
        
        # Schnellzugriff
        if st.session_state.forms:
            st.markdown("---")
            st.markdown("### ⚡ Schnellzugriff")
            
            # Nach Kategorie gruppieren
            for cat in CATEGORIES.keys():
                forms_in_cat = [f for f in st.session_state.forms.values() if f.get('category') == cat]
                if forms_in_cat:
                    with st.expander(f"{CATEGORY_ICONS.get(cat, '📋')} {cat}"):
                        for form in forms_in_cat:
                            if st.button(f"📝 {form['title'][:25]}...", key=f"quick_{form['id']}", use_container_width=True):
                                st.session_state.current_form = form['id']
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
        
        # JSON-Datei im Projektordner suchen
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
    
    # Formulare nach Kategorie anzeigen
    st.markdown("### 📋 Verfügbare Fragebögen")
    
    # Tabs für Kategorien
    categories_with_forms = [cat for cat in CATEGORIES.keys() 
                            if any(f.get('category') == cat for f in st.session_state.forms.values())]
    
    if categories_with_forms:
        tabs = st.tabs([f"{CATEGORY_ICONS.get(cat, '📋')} {cat}" for cat in categories_with_forms])
        
        for tab, category in zip(tabs, categories_with_forms):
            with tab:
                forms_in_cat = [f for f in st.session_state.forms.values() if f.get('category') == category]
                
                for form in forms_in_cat:
                    with st.container():
                        col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
                        
                        with col1:
                            st.markdown(f"**{form['title']}**")
                            st.caption(f"{form.get('field_count', 0)} Felder")
                        
                        with col2:
                            if st.button("📝 Ausfüllen", key=f"open_{form['id']}"):
                                st.session_state.current_form = form['id']
                                st.session_state.page = 'form'
                                st.session_state.form_values = {}
                                st.rerun()
                        
                        with col3:
                            if st.button("🔗 Einladung", key=f"invite_{form['id']}"):
                                st.session_state.current_form = form['id']
                                st.session_state.page = 'invite'
                                st.rerun()
                        
                        with col4:
                            if st.button("👁️ Vorschau", key=f"preview_{form['id']}"):
                                st.session_state.current_form = form['id']
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
    
    # Zurück-Button
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← Zurück"):
            st.session_state.page = 'dashboard'
            st.session_state.current_form = None
            st.session_state.form_values = {}
            st.rerun()
    with col2:
        st.markdown(f"### 📋 {form['title']}")
    
    st.markdown("---")
    
    # Formular
    with st.form(key=f"form_{form['id']}_main"):
        form_values = {}
        
        for field in form.get('fields', []):
            # Conditional Logic prüfen
            if not evaluate_conditional_logic(field, {**st.session_state.form_values, **form_values}):
                continue
            
            name, value = render_form_field(field, form_values, f"f{form['id']}")
            
            if name and value is not None:
                form_values[name] = value
                # Live-Update für Conditional Logic
                st.session_state.form_values[name] = value
        
        st.markdown("---")
        
        # Empfänger
        st.markdown("### 📧 Empfänger auswählen")
        employee_options = [f"{emp['name']} ({emp['email']})" for emp in st.session_state.employees]
        default_idx = next((i for i, emp in enumerate(st.session_state.employees) if emp.get('default')), 0)
        selected_emp = st.selectbox("An wen soll das Formular gesendet werden?", employee_options, index=default_idx)
        recipient_email = st.session_state.employees[employee_options.index(selected_emp)]['email']
        
        # Absenden
        submitted = st.form_submit_button("📤 Formular absenden", type="primary", use_container_width=True)
        
        if submitted:
            # Dokument erstellen
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
    
    st.success(f"Das Formular **{data['form']['title']}** wurde erfolgreich verarbeitet.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📥 Download")
        filename = f"{data['form']['title'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        st.download_button(
            "📄 Dokument herunterladen",
            data['document'],
            file_name=filename,
            mime="text/plain",
            use_container_width=True
        )
    
    with col2:
        st.markdown("### 📧 Per E-Mail senden")
        subject = f"Formular: {data['form']['title']}"
        mailto = f"mailto:{data['recipient']}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(data['document'][:1500])}"
        st.markdown(f"[📧 E-Mail öffnen]({mailto})")
        st.caption(f"Empfänger: {data['recipient']}")
    
    st.markdown("---")
    
    # Dokument-Vorschau
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
    
    if st.button("← Zurück"):
        st.session_state.page = 'dashboard'
        st.session_state.current_form = None
        st.rerun()
    
    st.markdown(f"## 🔗 Einladung erstellen")
    st.markdown(f"**Formular:** {form['title']}")
    
    st.markdown("---")
    
    # Basis-URL
    base_url = st.text_input(
        "🌐 App-URL (Ihre Streamlit-App)",
        value="https://ihre-app.streamlit.app",
        help="Die URL unter der Ihre App erreichbar ist"
    )
    
    # Mandantenname (optional)
    mandant_name = st.text_input("👤 Name des Mandanten (optional)", placeholder="Max Mustermann")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🔗 Einladungslink")
        
        if st.button("✨ Link generieren", type="primary", use_container_width=True):
            link, token = create_invitation_link(form['id'], mandant_name, base_url)
            st.session_state['generated_link'] = link
            st.session_state['generated_token'] = token
        
        if 'generated_link' in st.session_state:
            st.code(st.session_state['generated_link'])
            st.success("✅ Link erstellt! Gültig für 7 Tage.")
    
    with col2:
        st.markdown("### 📧 E-Mail-Einladung")
        
        recipient = st.text_input("E-Mail-Adresse", placeholder="mandant@beispiel.de")
        
        if st.button("📧 E-Mail erstellen", use_container_width=True) and recipient:
            link, _ = create_invitation_link(form['id'], mandant_name, base_url)
            mailto = create_email_mailto(form['id'], recipient, link)
            st.markdown(f"[📧 E-Mail-Programm öffnen]({mailto})")

def page_invitations():
    """Einladungsverwaltung"""
    st.markdown("## 📨 Einladungsverwaltung")
    
    if not st.session_state.invitations:
        st.info("📭 Noch keine Einladungen erstellt.")
        return
    
    st.markdown(f"**{len(st.session_state.invitations)} Einladungen**")
    st.markdown("---")
    
    for i, inv in enumerate(reversed(st.session_state.invitations)):
        expires = datetime.fromisoformat(inv['expires'])
        is_expired = datetime.now() > expires
        status_icon = "🔴" if is_expired else "🟢"
        status_text = "Abgelaufen" if is_expired else "Aktiv"
        
        with st.expander(f"{status_icon} {inv['form_title']} - {status_text}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Erstellt:** {inv['created'][:16].replace('T', ' ')}")
                st.write(f"**Gültig bis:** {inv['expires'][:16].replace('T', ' ')}")
            with col2:
                if inv.get('mandant'):
                    st.write(f"**Mandant:** {inv['mandant']}")
            
            if not is_expired:
                st.code(f"?invite={inv['token']}")

def page_settings():
    """Einstellungsseite"""
    st.markdown("## ⚙️ Einstellungen")
    
    # JSON Import
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
    
    # Mitarbeiter
    st.markdown("### 👥 Mitarbeiter verwalten")
    
    for i, emp in enumerate(st.session_state.employees):
        col1, col2, col3, col4 = st.columns([3, 3, 1, 1])
        
        with col1:
            new_name = st.text_input("Name", value=emp['name'], key=f"emp_name_{i}", label_visibility="collapsed")
            st.session_state.employees[i]['name'] = new_name
        
        with col2:
            new_email = st.text_input("E-Mail", value=emp['email'], key=f"emp_email_{i}", label_visibility="collapsed")
            st.session_state.employees[i]['email'] = new_email
        
        with col3:
            is_default = st.checkbox("Standard", value=emp.get('default', False), key=f"emp_def_{i}")
            if is_default:
                for j in range(len(st.session_state.employees)):
                    st.session_state.employees[j]['default'] = (j == i)
        
        with col4:
            if st.button("🗑️", key=f"del_emp_{i}"):
                st.session_state.employees.pop(i)
                st.rerun()
    
    st.markdown("---")
    
    # Neuer Mitarbeiter
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
    
    # Reset
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
    
    if st.button("← Zurück"):
        st.session_state.page = 'dashboard'
        st.session_state.current_form = None
        st.rerun()
    
    st.markdown(f"## 👁️ Vorschau: {form['title']}")
    st.markdown(f"**Kategorie:** {CATEGORY_ICONS.get(form['category'], '📋')} {form['category']}")
    st.markdown(f"**Anzahl Felder:** {form.get('field_count', len(form.get('fields', [])))}")
    
    st.markdown("---")
    st.markdown("### Feldübersicht")
    
    for i, field in enumerate(form.get('fields', []), 1):
        ftype = field.get('type', 'unknown')
        fname = field.get('name', '-')
        flabel = field.get('label', '-')
        freq = "✓" if field.get('required') else ""
        fcond = "🔀" if field.get('conditional_logic') else ""
        
        if ftype not in ['section_break', 'welcome_screen']:
            st.markdown(f"{i}. **{flabel}** `{ftype}` {freq} {fcond}")

# ============================================
# Hauptanwendung
# ============================================

def main():
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=APP_ICON,
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 50%, #f5f5f4 100%);
        }
        
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #78350f 0%, #92400e 100%);
        }
        
        section[data-testid="stSidebar"] * {
            color: white !important;
        }
        
        section[data-testid="stSidebar"] .stButton button {
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        section[data-testid="stSidebar"] .stButton button:hover {
            background: rgba(255,255,255,0.2);
        }
        
        h1, h2, h3 {
            color: #78350f !important;
        }
        
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            background-color: #fef3c7;
            border-radius: 8px 8px 0 0;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: #b45309 !important;
            color: white !important;
        }
        
        div[data-testid="stExpander"] {
            background: white;
            border-radius: 8px;
            border: 1px solid #e5e5e5;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialisierung
    init_session_state()
    
    # URL-Parameter prüfen (Einladungslink)
    query_params = st.query_params
    if 'invite' in query_params:
        token = query_params['invite']
        data = decode_invitation_token(token)
        if data:
            # Prüfen ob Formular geladen ist
            if not st.session_state.forms:
                # Versuchen JSON zu laden
                json_path = Path("fluentform-export-forms-29-20-01-2026.json")
                if json_path.exists():
                    json_data = load_json_file(str(json_path))
                    if json_data:
                        st.session_state.forms = parse_fluentform_json(json_data)
            
            if data['form_id'] in st.session_state.forms:
                st.session_state.current_form = data['form_id']
                st.session_state.page = 'form'
            else:
                st.error("❌ Formular nicht gefunden. Bitte importieren Sie die JSON-Datei.")
        else:
            st.error("❌ Ungültiger oder abgelaufener Einladungslink.")
    
    # Sidebar
    render_sidebar()
    
    # Hauptbereich
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
