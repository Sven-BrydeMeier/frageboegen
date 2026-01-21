"""
RA-RHM Fragebogen-System
Vollständige Streamlit-App für Mandanten-Fragebögen
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
# Konfiguration
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
    "Notariat": "📜", "Familienrecht": "👨‍👩‍👧‍👦", "Arbeitsrecht": "💼",
    "Verkehrsrecht": "🚗", "Mietrecht": "🏠", "Zivilrecht": "⚖️", "Sonstiges": "📋"
}

DEFAULT_EMPLOYEES = [
    {"name": "Sekretariat", "email": "info@ra-rhm.de", "default": True},
    {"name": "Sven-Bryde Meier (Notar)", "email": "notar@ra-rhm.de", "default": False},
    {"name": "Rechtsanwalt Müller", "email": "mueller@ra-rhm.de", "default": False},
]

# ============================================
# Secrets
# ============================================

def get_app_url() -> str:
    """Holt APP_URL aus Secrets"""
    try:
        if "APP_URL" in st.secrets:
            return st.secrets["APP_URL"]
    except:
        pass
    return ""

def get_openai_key() -> str:
    """Holt OpenAI API Key aus Secrets"""
    try:
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except:
        pass
    return ""

# ============================================
# Hilfsfunktionen
# ============================================

def safe_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default

def ensure_dict(obj: Any) -> Dict:
    return obj if isinstance(obj, dict) else {}

def ensure_list(obj: Any) -> List:
    return obj if isinstance(obj, list) else []

# ============================================
# Session State
# ============================================

def init_session_state():
    defaults = {
        'forms': {}, 'employees': DEFAULT_EMPLOYEES.copy(), 'invitations': [],
        'current_form': None, 'form_values': {}, 'page': 'dashboard',
        'submitted_data': None, 'json_loaded': False,
        'is_mandant_mode': False,  # Mandanten sehen nur ihr Formular
        'mandant_name': '',  # Name aus Einladung
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def load_forms_if_needed() -> bool:
    if st.session_state.forms:
        return True
    json_path = Path("fluentform-export-forms-29-20-01-2026.json")
    if json_path.exists():
        json_data = load_json_file(str(json_path))
        if json_data:
            st.session_state.forms = parse_fluentform_json(json_data)
            st.session_state.json_loaded = True
            return True
    return False

# ============================================
# JSON Parsing
# ============================================

@st.cache_data
def load_json_file(file_path: str) -> List[Dict]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return []

def parse_fluentform_json(json_data: List[Dict]) -> Dict[int, Dict]:
    forms = {}
    for form in ensure_list(json_data):
        form = ensure_dict(form)
        form_id = safe_get(form, 'id')
        if not form_id:
            continue
        form_id = int(form_id)
        
        form_fields = safe_get(form, 'form_fields', {})
        if isinstance(form_fields, str):
            try:
                form_fields = json.loads(form_fields)
            except:
                form_fields = {}
        form_fields = ensure_dict(form_fields)
        
        raw_fields = ensure_list(safe_get(form_fields, 'fields', []))
        flattened_fields = flatten_fields(raw_fields)
        
        forms[form_id] = {
            'id': form_id,
            'title': safe_get(form, 'title', f'Formular {form_id}'),
            'status': safe_get(form, 'status', 'published'),
            'fields': flattened_fields,
            'category': get_category_for_form(form_id),
            'field_count': len(flattened_fields)
        }
    return forms

def get_category_for_form(form_id: int) -> str:
    for category, ids in CATEGORIES.items():
        if form_id in ids:
            return category
    return "Sonstiges"

def flatten_fields(fields: List, parent_conditions: List = None) -> List[Dict]:
    result = []
    parent_conditions = parent_conditions or []
    
    for field in ensure_list(fields):
        field = ensure_dict(field)
        element = safe_get(field, 'element', '')
        
        if element == 'container':
            columns = ensure_list(safe_get(field, 'columns', []))
            settings = ensure_dict(safe_get(field, 'settings', {}))
            container_conditions = safe_get(settings, 'conditional_logics', {})
            
            inherited_conditions = parent_conditions.copy()
            if isinstance(container_conditions, dict) and safe_get(container_conditions, 'status'):
                inherited_conditions.append(container_conditions)
            
            for column in columns:
                column = ensure_dict(column)
                nested_fields = ensure_list(safe_get(column, 'fields', []))
                result.extend(flatten_fields(nested_fields, inherited_conditions))
        else:
            parsed = parse_single_field(field, parent_conditions)
            if parsed:
                result.append(parsed)
    return result

def parse_single_field(field: Dict, inherited_conditions: List = None) -> Optional[Dict]:
    field = ensure_dict(field)
    element = safe_get(field, 'element', '')
    attributes = ensure_dict(safe_get(field, 'attributes', {}))
    settings = ensure_dict(safe_get(field, 'settings', {}))
    
    if element in ['custom_html', 'form_step', 'input_hidden', 'chained_select', '']:
        return None
    
    field_name = safe_get(attributes, 'name', '') or f'field_{uuid.uuid4().hex[:8]}'
    
    parsed = {
        'type': element, 'name': field_name,
        'label': safe_get(settings, 'label', ''),
        'placeholder': safe_get(attributes, 'placeholder', safe_get(settings, 'placeholder', '')),
        'required': False, 'options': [], 'conditional_logic': None,
        'description': safe_get(settings, 'description', ''),
        'help_message': safe_get(settings, 'help_message', ''),
        'subfields': {}, 'subfields_visible': {}
    }
    
    # Required
    validation = safe_get(settings, 'validation_rules', {})
    if isinstance(validation, dict):
        required_rule = safe_get(validation, 'required', {})
        if isinstance(required_rule, dict):
            parsed['required'] = bool(safe_get(required_rule, 'value', False))
        elif isinstance(required_rule, bool):
            parsed['required'] = required_rule
    
    # Options
    for opt in ensure_list(safe_get(settings, 'advanced_options', [])):
        opt = ensure_dict(opt)
        opt_label = safe_get(opt, 'label', '')
        if opt_label:
            parsed['options'].append({'label': opt_label, 'value': safe_get(opt, 'value', opt_label)})
    
    # Conditional Logic
    cond_logic = safe_get(settings, 'conditional_logics', safe_get(settings, 'conditional_logic', None))
    if isinstance(cond_logic, dict) and safe_get(cond_logic, 'status'):
        parsed['conditional_logic'] = {
            'type': safe_get(cond_logic, 'type', 'any'),
            'conditions': ensure_list(safe_get(cond_logic, 'conditions', []))
        }
    elif isinstance(cond_logic, list) and cond_logic:
        parsed['conditional_logic'] = {'type': 'any', 'conditions': cond_logic}
    
    if inherited_conditions:
        if not parsed['conditional_logic']:
            parsed['conditional_logic'] = {'type': 'all', 'conditions': []}
        for ic in inherited_conditions:
            if isinstance(ic, dict):
                parsed['conditional_logic']['conditions'].extend(ensure_list(safe_get(ic, 'conditions', [])))
    
    # Subfields
    if element == 'input_name':
        subfields = ensure_dict(safe_get(field, 'fields', {}))
        for sub_key in ['first_name', 'middle_name', 'last_name']:
            sub_field = ensure_dict(safe_get(subfields, sub_key, {}))
            sub_settings = ensure_dict(safe_get(sub_field, 'settings', {}))
            parsed['subfields'][sub_key] = safe_get(sub_settings, 'label', sub_key.replace('_', ' ').title())
            parsed['subfields_visible'][sub_key] = safe_get(sub_settings, 'visible', True)
    elif element == 'address':
        subfields = ensure_dict(safe_get(field, 'fields', {}))
        defaults = {'address_line_1': 'Straße', 'address_line_2': 'Adresszusatz', 'city': 'Stadt', 'state': 'Bundesland', 'zip': 'PLZ', 'country': 'Land'}
        for sub_key, default_label in defaults.items():
            sub_field = ensure_dict(safe_get(subfields, sub_key, {}))
            sub_settings = ensure_dict(safe_get(sub_field, 'settings', {}))
            parsed['subfields'][sub_key] = safe_get(sub_settings, 'label', default_label)
            parsed['subfields_visible'][sub_key] = safe_get(sub_settings, 'visible', sub_key in ['address_line_1', 'city', 'zip'])
    
    return parsed

# ============================================
# Conditional Logic
# ============================================

def evaluate_conditional_logic(field: Dict, form_values: Dict) -> bool:
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
        if isinstance(current_value, list):
            current_value = ', '.join(str(v) for v in current_value)
        
        cs, ts = str(current_value).strip(), str(target_value).strip()
        
        if operator in ['=', '==']:
            result = cs == ts
        elif operator in ['!=', '<>']:
            result = cs != ts
        elif operator == 'contains':
            result = ts.lower() in cs.lower()
        else:
            result = cs == ts
        results.append(result)
    
    if not results:
        return True
    return all(results) if logic_type == 'all' else any(results)

# ============================================
# Form Rendering
# ============================================

def render_form_field(field: Dict, form_values: Dict, key_prefix: str = "") -> Tuple[str, Any]:
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
    display_label = f"{label} *" if (required and label) else (label or "")
    help_text = help_msg or None
    value = None
    
    if field_type == 'section_break':
        st.markdown("---")
        if label: st.markdown(f"### {label}")
        if description: st.markdown(description, unsafe_allow_html=True)
        return (name, None)
    elif field_type == 'welcome_screen':
        if label: st.markdown(f"## {label}")
        if description: st.markdown(description, unsafe_allow_html=True)
        return (name, None)
    elif field_type == 'input_text':
        value = st.text_input(display_label, placeholder=placeholder, help=help_text, key=key)
    elif field_type == 'input_email':
        value = st.text_input(display_label, placeholder=placeholder or "email@beispiel.de", help=help_text, key=key)
    elif field_type == 'phone':
        value = st.text_input(display_label, placeholder=placeholder or "+49 123 456789", help=help_text, key=key)
    elif field_type == 'input_number':
        value = st.number_input(display_label, help=help_text, key=key, step=1, value=None)
    elif field_type == 'input_date':
        date_val = st.date_input(display_label, help=help_text, key=key, value=None)
        value = date_val.strftime("%d.%m.%Y") if date_val else ""
    elif field_type == 'textarea':
        value = st.text_area(display_label, placeholder=placeholder, help=help_text, key=key, height=120)
    elif field_type in ['select', 'select_country']:
        if options:
            opt_labels = ["Bitte wählen..."] + [safe_get(o, 'label', '') for o in options]
            opt_values = [""] + [safe_get(o, 'value', '') for o in options]
            idx = st.selectbox(display_label, range(len(opt_labels)), format_func=lambda x: opt_labels[x], help=help_text, key=key)
            value = opt_values[idx] if idx > 0 else ""
        else:
            value = st.text_input(display_label, placeholder=placeholder, help=help_text, key=key)
    elif field_type == 'input_radio':
        if options:
            opt_labels = [safe_get(o, 'label', '') for o in options]
            opt_values = [safe_get(o, 'value', '') for o in options]
            selected = st.radio(display_label, opt_labels, help=help_text, key=key, index=None, horizontal=len(options) <= 4)
            value = opt_values[opt_labels.index(selected)] if selected else ""
    elif field_type == 'input_checkbox':
        if options and len(options) > 1:
            st.markdown(f"**{display_label}**")
            selected = []
            cols = st.columns(min(len(options), 3))
            for i, opt in enumerate(options):
                opt = ensure_dict(opt)
                with cols[i % len(cols)]:
                    if st.checkbox(safe_get(opt, 'label', ''), key=f"{key}_{i}"):
                        selected.append(safe_get(opt, 'value', ''))
            value = selected
        else:
            checked = st.checkbox(display_label, help=help_text, key=key)
            value = "Ja" if checked else "Nein"
    elif field_type == 'input_name':
        if label: st.markdown(f"**{display_label}**")
        visible = [(k, v) for k, v in subfields.items() if subfields_visible.get(k, True)]
        if len(visible) >= 2:
            cols = st.columns(len(visible))
            parts = {}
            for i, (sk, sl) in enumerate(visible):
                with cols[i]:
                    parts[sk] = st.text_input(sl, key=f"{key}_{sk}")
            value = " ".join([v for v in parts.values() if v])
        else:
            value = st.text_input(display_label, placeholder=placeholder, key=key)
    elif field_type == 'address':
        if label: st.markdown(f"**{display_label}**")
        parts = {}
        if subfields_visible.get('address_line_1', True):
            parts['street'] = st.text_input(subfields.get('address_line_1', 'Straße'), key=f"{key}_street")
        col1, col2 = st.columns([1, 3])
        with col1:
            if subfields_visible.get('zip', True):
                parts['zip'] = st.text_input(subfields.get('zip', 'PLZ'), key=f"{key}_zip")
        with col2:
            if subfields_visible.get('city', True):
                parts['city'] = st.text_input(subfields.get('city', 'Stadt'), key=f"{key}_city")
        addr_parts = []
        if parts.get('street'): addr_parts.append(parts['street'])
        if parts.get('zip') or parts.get('city'): addr_parts.append(f"{parts.get('zip', '')} {parts.get('city', '')}".strip())
        value = ", ".join([p for p in addr_parts if p])
    elif field_type == 'input_file':
        uploaded = st.file_uploader(display_label, help=help_text, key=key)
        value = uploaded.name if uploaded else ""
    elif field_type in ['gdpr_agreement', 'terms_and_condition']:
        clean = re.sub('<[^<]+?>', '', description or label or "Ich stimme zu")[:300]
        if description and len(description) > 100:
            with st.expander("📋 Details"): st.markdown(description, unsafe_allow_html=True)
        checked = st.checkbox(f"✓ {clean}", key=key)
        value = "Zugestimmt" if checked else "Nicht zugestimmt"
    else:
        if label:
            value = st.text_input(display_label, placeholder=placeholder, help=help_text, key=key)
    
    return (name, value)

# ============================================
# Einladungssystem
# ============================================

def generate_invitation_token(form_id: int, mandant_name: str = "", expires_days: int = 7) -> str:
    data = {
        'form_id': int(form_id),
        'expires': (datetime.now() + timedelta(days=expires_days)).isoformat(),
        'mandant': mandant_name,
        'uuid': uuid.uuid4().hex[:8]
    }
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()

def decode_invitation_token(token: str) -> Optional[Dict]:
    try:
        data = json.loads(base64.urlsafe_b64decode(token.encode()).decode())
        if datetime.now() > datetime.fromisoformat(data['expires']):
            return None
        data['form_id'] = int(data['form_id'])
        return data
    except:
        return None

def create_invitation_link(form_id: int, mandant_name: str = "", base_url: str = "") -> Tuple[str, str]:
    token = generate_invitation_token(form_id, mandant_name)
    form = st.session_state.forms.get(int(form_id), {})
    st.session_state.invitations.append({
        'token': token, 'form_id': int(form_id),
        'form_title': safe_get(form, 'title', f'Formular {form_id}'),
        'mandant': mandant_name,
        'created': datetime.now().isoformat(),
        'expires': (datetime.now() + timedelta(days=7)).isoformat()
    })
    link = f"{base_url.rstrip('/')}?invite={token}" if base_url else f"?invite={token}"
    return link, token

def create_email_mailto(form_id: int, recipient: str, invite_link: str) -> str:
    form = st.session_state.forms.get(int(form_id), {})
    title = safe_get(form, 'title', f'Formular {form_id}')
    subject = f"Einladung: {title} - RA-RHM"
    body = f"Sehr geehrte Damen und Herren,\n\nSie wurden eingeladen:\n\n📋 {title}\n\nLink: {invite_link}\n\n⏰ 7 Tage gültig.\n\nMfG\nRA-RHM\nTel: 04331 732970"
    return f"mailto:{recipient}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"

# ============================================
# Dokumentengenerierung
# ============================================

def generate_document(form: Dict, form_data: Dict, recipient: str) -> str:
    form = ensure_dict(form)
    title = safe_get(form, 'title', 'Formular')
    lines = ["=" * 60, f"  {title}", "=" * 60, "",
             f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}", f"📧 {recipient}", "",
             "-" * 60, "  FORMULARDATEN", "-" * 60, ""]
    
    labels = {safe_get(f, 'name', ''): safe_get(f, 'label', '') for f in ensure_list(safe_get(form, 'fields', []))}
    for name, value in form_data.items():
        if value and str(value) not in ['Nein', 'Nicht zugestimmt', '[]', '']:
            label = labels.get(name, name)
            if isinstance(value, list): value = ", ".join(str(v) for v in value)
            lines.extend([f"▸ {label}:", f"  {value}", ""])
    
    lines.extend(["-" * 60, "", "📌 RA-RHM Rechtsanwaltskanzlei | 04331 732970", "=" * 60])
    return "\n".join(lines)

# ============================================
# Sidebar
# ============================================

def render_sidebar():
    with st.sidebar:
        st.markdown("## 📂 Navigation")
        for page, label in [('dashboard', '🏠 Dashboard'), ('invitations', '📨 Einladungen'), ('settings', '⚙️ Einstellungen')]:
            if st.button(label, use_container_width=True, type="primary" if st.session_state.page == page else "secondary"):
                st.session_state.page = page
                st.session_state.current_form = None
                st.rerun()
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        col1.metric("Formulare", len(st.session_state.forms))
        col2.metric("Einladungen", len(st.session_state.invitations))
        
        if st.session_state.forms:
            st.markdown("---")
            st.markdown("### ⚡ Schnellzugriff")
            for cat in CATEGORIES:
                forms = [f for f in st.session_state.forms.values() if safe_get(f, 'category') == cat]
                if forms:
                    with st.expander(f"{CATEGORY_ICONS.get(cat, '📋')} {cat}"):
                        for f in forms:
                            if st.button(f"📝 {safe_get(f, 'title', '')[:25]}", key=f"q_{safe_get(f, 'id')}", use_container_width=True):
                                st.session_state.current_form = int(safe_get(f, 'id'))
                                st.session_state.page = 'form'
                                st.rerun()
        
        st.markdown("---")
        st.caption("© 2025 RA-RHM | 04331 732970")

# ============================================
# Seiten
# ============================================

def page_dashboard():
    st.markdown("## 📊 Dashboard")
    if not st.session_state.forms:
        st.warning("⚠️ Keine Formulare geladen.")
        json_path = Path("fluentform-export-forms-29-20-01-2026.json")
        if json_path.exists():
            if st.button("📂 Formulare laden", type="primary"):
                data = load_json_file(str(json_path))
                if data:
                    st.session_state.forms = parse_fluentform_json(data)
                    st.success(f"✅ {len(st.session_state.forms)} Formulare geladen!")
                    st.rerun()
        
        uploaded = st.file_uploader("Oder JSON hochladen", type=['json'])
        if uploaded:
            data = json.load(uploaded)
            st.session_state.forms = parse_fluentform_json(data)
            st.success(f"✅ {len(st.session_state.forms)} Formulare importiert!")
            st.rerun()
        return
    
    st.markdown("### 📋 Fragebögen")
    cats = [c for c in CATEGORIES if any(safe_get(f, 'category') == c for f in st.session_state.forms.values())]
    if cats:
        tabs = st.tabs([f"{CATEGORY_ICONS.get(c, '📋')} {c}" for c in cats])
        for tab, cat in zip(tabs, cats):
            with tab:
                for f in [f for f in st.session_state.forms.values() if safe_get(f, 'category') == cat]:
                    fid = int(safe_get(f, 'id'))
                    col1, col2, col3 = st.columns([5, 1, 1])
                    col1.markdown(f"**{safe_get(f, 'title')}** ({safe_get(f, 'field_count', 0)} Felder)")
                    if col2.button("📝", key=f"o_{fid}"):
                        st.session_state.current_form = fid
                        st.session_state.page = 'form'
                        st.session_state.form_values = {}
                        st.rerun()
                    if col3.button("🔗", key=f"i_{fid}"):
                        st.session_state.current_form = fid
                        st.session_state.page = 'invite'
                        st.rerun()

def page_form():
    if not st.session_state.current_form:
        st.session_state.page = 'dashboard'
        st.rerun()
        return
    
    fid = int(st.session_state.current_form)
    form = st.session_state.forms.get(fid)
    if not form:
        st.error(f"❌ Formular ID {fid} nicht gefunden.")
        st.info(f"Verfügbar: {list(st.session_state.forms.keys())[:10]}")
        if st.button("← Dashboard"): 
            st.session_state.page = 'dashboard'
            st.rerun()
        return
    
    if st.button("← Zurück"):
        st.session_state.page = 'dashboard'
        st.session_state.current_form = None
        st.rerun()
    
    st.markdown(f"### 📋 {safe_get(form, 'title')}")
    st.markdown("---")
    
    with st.form(key=f"form_{fid}"):
        values = {}
        for field in ensure_list(safe_get(form, 'fields', [])):
            if evaluate_conditional_logic(field, {**st.session_state.form_values, **values}):
                name, val = render_form_field(field, values, f"f{fid}")
                if name and val is not None:
                    values[name] = val
                    st.session_state.form_values[name] = val
        
        st.markdown("---")
        st.markdown("### 📧 Empfänger")
        opts = [f"{safe_get(e, 'name')} ({safe_get(e, 'email')})" for e in st.session_state.employees]
        default = next((i for i, e in enumerate(st.session_state.employees) if safe_get(e, 'default')), 0)
        sel = st.selectbox("Empfänger", opts, index=default)
        recipient = safe_get(st.session_state.employees[opts.index(sel)], 'email', 'info@ra-rhm.de')
        
        if st.form_submit_button("📤 Absenden", type="primary", use_container_width=True):
            st.session_state.submitted_data = {
                'form': form, 'data': values,
                'document': generate_document(form, values, recipient),
                'recipient': recipient
            }
            st.session_state.page = 'success'
            st.rerun()

def page_success():
    st.markdown("## ✅ Erfolgreich!")
    data = st.session_state.submitted_data
    if not data:
        st.session_state.page = 'dashboard'
        st.rerun()
        return
    
    title = safe_get(data['form'], 'title', 'Formular')
    st.success(f"**{title}** wurde verarbeitet.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 Download", data['document'], f"{title.replace(' ', '_')}.txt", "text/plain", use_container_width=True)
    with col2:
        mailto = f"mailto:{data['recipient']}?subject={urllib.parse.quote(f'Formular: {title}')}&body={urllib.parse.quote(data['document'][:1500])}"
        st.markdown(f"[📧 E-Mail senden]({mailto})")
    
    with st.expander("📄 Vorschau", expanded=True):
        st.text(data['document'])
    
    if st.button("← Dashboard", type="primary"):
        st.session_state.submitted_data = None
        st.session_state.page = 'dashboard'
        st.session_state.current_form = None
        st.rerun()

# ============================================
# Mandanten-Modus (eingeschränkte Ansicht)
# ============================================

def page_form_mandant():
    """Formular-Seite für Mandanten - nur das eine Formular, keine Navigation"""
    if not st.session_state.current_form:
        st.error("❌ Kein Formular ausgewählt.")
        return
    
    fid = int(st.session_state.current_form)
    form = st.session_state.forms.get(fid)
    if not form:
        st.error(f"❌ Formular nicht gefunden.")
        return
    
    # Header mit Kanzlei-Info
    st.markdown("# ⚖️ RA-RHM Rechtsanwaltskanzlei")
    st.markdown("---")
    
    # Begrüßung falls Mandantenname vorhanden
    if st.session_state.mandant_name:
        st.markdown(f"### Guten Tag, {st.session_state.mandant_name}!")
    
    st.markdown(f"## 📋 {safe_get(form, 'title')}")
    st.markdown("Bitte füllen Sie das folgende Formular vollständig aus.")
    st.markdown("---")
    
    with st.form(key=f"mandant_form_{fid}"):
        values = {}
        for field in ensure_list(safe_get(form, 'fields', [])):
            if evaluate_conditional_logic(field, {**st.session_state.form_values, **values}):
                name, val = render_form_field(field, values, f"mf{fid}")
                if name and val is not None:
                    values[name] = val
                    st.session_state.form_values[name] = val
        
        st.markdown("---")
        
        # Standard-Empfänger automatisch verwenden (keine Auswahl für Mandanten)
        default_emp = next((e for e in st.session_state.employees if safe_get(e, 'default')), st.session_state.employees[0] if st.session_state.employees else None)
        recipient = safe_get(default_emp, 'email', 'info@ra-rhm.de') if default_emp else 'info@ra-rhm.de'
        
        if st.form_submit_button("📤 Formular absenden", type="primary", use_container_width=True):
            st.session_state.submitted_data = {
                'form': form, 'data': values,
                'document': generate_document(form, values, recipient),
                'recipient': recipient
            }
            st.session_state.page = 'success_mandant'
            st.rerun()
    
    # Footer
    st.markdown("---")
    st.caption("📞 Bei Fragen: 04331 732970 | 📧 info@ra-rhm.de")

def page_success_mandant():
    """Erfolgsseite für Mandanten - ohne Navigation zurück"""
    st.markdown("# ⚖️ RA-RHM Rechtsanwaltskanzlei")
    st.markdown("---")
    
    data = st.session_state.submitted_data
    if not data:
        st.error("❌ Keine Daten vorhanden.")
        return
    
    title = safe_get(data['form'], 'title', 'Formular')
    
    st.markdown("## ✅ Vielen Dank!")
    st.success(f"Ihr Formular **{title}** wurde erfolgreich übermittelt.")
    
    st.markdown("""
    ### Was passiert jetzt?
    
    Ihre Angaben wurden an unsere Kanzlei gesendet. Ein Mitarbeiter wird sich 
    zeitnah mit Ihnen in Verbindung setzen.
    
    **Sie können dieses Fenster jetzt schließen.**
    """)
    
    st.markdown("---")
    
    # Optional: Download für den Mandanten
    with st.expander("📄 Ihre Angaben (Kopie für Ihre Unterlagen)"):
        st.text(data['document'])
        st.download_button(
            "📥 Als Datei speichern", 
            data['document'], 
            f"{title.replace(' ', '_')}_Kopie.txt", 
            "text/plain"
        )
    
    st.markdown("---")
    st.markdown("### 📞 Kontakt")
    st.markdown("""
    **RA-RHM Rechtsanwaltskanzlei**  
    Tel: 04331 732970  
    E-Mail: info@ra-rhm.de
    """)

def page_invite():
    if not st.session_state.current_form:
        st.session_state.page = 'dashboard'
        st.rerun()
        return
    
    fid = int(st.session_state.current_form)
    form = st.session_state.forms.get(fid)
    if not form:
        st.error("Formular nicht gefunden")
        return
    
    if st.button("← Zurück"):
        st.session_state.page = 'dashboard'
        st.session_state.current_form = None
        st.rerun()
    
    st.markdown(f"## 🔗 Einladung: {safe_get(form, 'title')}")
    st.markdown("---")
    
    default_url = get_app_url()
    if default_url:
        st.success(f"✅ URL aus Secrets: `{default_url}`")
        base_url = default_url
    else:
        base_url = st.text_input("🌐 App-URL", "https://ihre-app.streamlit.app", help="Tipp: In Secrets als APP_URL hinterlegen")
    
    mandant = st.text_input("👤 Mandant (optional)")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🔗 Link")
        if st.button("✨ Generieren", type="primary", use_container_width=True):
            link, _ = create_invitation_link(fid, mandant, base_url)
            st.session_state['gen_link'] = link
        if 'gen_link' in st.session_state:
            st.code(st.session_state['gen_link'])
            st.success("7 Tage gültig")
    
    with col2:
        st.markdown("### 📧 E-Mail")
        email = st.text_input("E-Mail-Adresse")
        if st.button("📧 E-Mail erstellen", use_container_width=True) and email:
            link, _ = create_invitation_link(fid, mandant, base_url)
            st.markdown(f"[📧 Öffnen]({create_email_mailto(fid, email, link)})")

def page_invitations():
    st.markdown("## 📨 Einladungen")
    if not st.session_state.invitations:
        st.info("📭 Keine Einladungen")
        return
    
    for inv in reversed(st.session_state.invitations):
        try:
            expired = datetime.now() > datetime.fromisoformat(safe_get(inv, 'expires', ''))
        except:
            expired = True
        icon = "🔴" if expired else "🟢"
        with st.expander(f"{icon} {safe_get(inv, 'form_title')}"):
            st.write(f"Erstellt: {safe_get(inv, 'created', '')[:16]}")
            st.write(f"Gültig bis: {safe_get(inv, 'expires', '')[:16]}")
            if not expired:
                st.code(f"?invite={safe_get(inv, 'token')}")

def page_settings():
    st.markdown("## ⚙️ Einstellungen")
    
    st.markdown("### 🔐 Secrets")
    col1, col2 = st.columns(2)
    url = get_app_url()
    key = get_openai_key()
    
    with col1:
        if url:
            st.success(f"✅ APP_URL: {url}")
        else:
            st.warning("⚠️ APP_URL fehlt")
    
    with col2:
        if key:
            st.success(f"✅ OPENAI_API_KEY: {key[:8]}...")
        else:
            st.info("ℹ️ OPENAI_API_KEY fehlt")
    
    st.markdown("---")
    st.markdown("### 📥 Import")
    uploaded = st.file_uploader("JSON hochladen", type=['json'])
    if uploaded:
        st.session_state.forms = parse_fluentform_json(json.load(uploaded))
        st.success(f"✅ {len(st.session_state.forms)} Formulare")
    
    st.markdown("---")
    st.markdown("### 👥 Mitarbeiter")
    for i, e in enumerate(st.session_state.employees):
        col1, col2, col3 = st.columns([4, 4, 1])
        with col1:
            st.session_state.employees[i]['name'] = st.text_input("N", safe_get(e, 'name'), key=f"en_{i}", label_visibility="collapsed")
        with col2:
            st.session_state.employees[i]['email'] = st.text_input("E", safe_get(e, 'email'), key=f"ee_{i}", label_visibility="collapsed")
        with col3:
            if st.button("🗑️", key=f"ed_{i}"):
                st.session_state.employees.pop(i)
                st.rerun()
    
    col1, col2, col3 = st.columns([4, 4, 1])
    with col1:
        nn = st.text_input("Name", key="nn", placeholder="Name")
    with col2:
        ne = st.text_input("Email", key="ne", placeholder="email@ra-rhm.de")
    with col3:
        if st.button("➕") and nn and ne:
            st.session_state.employees.append({'name': nn, 'email': ne, 'default': False})
            st.rerun()

# ============================================
# Main
# ============================================

def main():
    st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide")
    
    init_session_state()
    
    # Einladungslink verarbeiten - aktiviert Mandanten-Modus
    if 'invite' in st.query_params:
        token = st.query_params['invite']
        data = decode_invitation_token(token)
        if data:
            load_forms_if_needed()
            fid = int(data.get('form_id', 0))
            if fid in st.session_state.forms:
                st.session_state.current_form = fid
                st.session_state.is_mandant_mode = True
                st.session_state.mandant_name = data.get('mandant', '')
                st.session_state.page = 'form_mandant'
            else:
                st.error(f"❌ Formular nicht gefunden.")
                st.stop()
        else:
            st.error("❌ Dieser Link ist ungültig oder abgelaufen.")
            st.info("Bitte kontaktieren Sie die Kanzlei für einen neuen Link.")
            st.markdown("📞 **04331 732970** | 📧 **info@ra-rhm.de**")
            st.stop()
    
    # Mandanten-Modus: Eingeschränkte Ansicht ohne Sidebar
    if st.session_state.is_mandant_mode:
        # Kein CSS für Sidebar nötig, da sie nicht gerendert wird
        st.markdown("""<style>
            .stApp { background: linear-gradient(135deg, #fffbeb, #fef3c7, #f5f5f4); }
            h1, h2, h3 { color: #78350f !important; }
        </style>""", unsafe_allow_html=True)
        
        # Nur Mandanten-Seiten erlaubt
        if st.session_state.page == 'form_mandant':
            page_form_mandant()
        elif st.session_state.page == 'success_mandant':
            page_success_mandant()
        else:
            # Fallback
            st.session_state.page = 'form_mandant'
            st.rerun()
    
    # Admin-Modus: Volle Ansicht mit Sidebar
    else:
        st.markdown("""<style>
            /* Hauptbereich */
            .stApp { background: linear-gradient(135deg, #fffbeb, #fef3c7, #f5f5f4); }
            h1, h2, h3 { color: #78350f !important; }
            
            /* Sidebar Hintergrund */
            section[data-testid="stSidebar"] { background: linear-gradient(180deg, #78350f, #92400e); }
            
            /* Sidebar Text weiß */
            section[data-testid="stSidebar"] .stMarkdown { color: white !important; }
            section[data-testid="stSidebar"] .stMarkdown p { color: white !important; }
            section[data-testid="stSidebar"] .stMarkdown h1,
            section[data-testid="stSidebar"] .stMarkdown h2,
            section[data-testid="stSidebar"] .stMarkdown h3 { color: white !important; }
            section[data-testid="stSidebar"] label { color: white !important; }
            section[data-testid="stSidebar"] .stMetricLabel { color: white !important; }
            section[data-testid="stSidebar"] .stMetricValue { color: white !important; }
            section[data-testid="stSidebar"] span { color: white !important; }
            section[data-testid="stSidebar"] small { color: rgba(255,255,255,0.7) !important; }
            
            /* Sidebar Buttons - dunkle Schrift auf hellem Hintergrund */
            section[data-testid="stSidebar"] .stButton button {
                background: rgba(255,255,255,0.9) !important;
                color: #78350f !important;
                border: 1px solid rgba(255,255,255,0.3) !important;
            }
            section[data-testid="stSidebar"] .stButton button:hover {
                background: white !important;
                color: #78350f !important;
            }
            section[data-testid="stSidebar"] .stButton button p {
                color: #78350f !important;
            }
            
            /* Primary Buttons in Sidebar */
            section[data-testid="stSidebar"] .stButton button[kind="primary"] {
                background: #b45309 !important;
                color: white !important;
            }
            section[data-testid="stSidebar"] .stButton button[kind="primary"] p {
                color: white !important;
            }
            
            /* Expander in Sidebar */
            section[data-testid="stSidebar"] .streamlit-expanderHeader {
                color: white !important;
                background: rgba(255,255,255,0.1) !important;
            }
            section[data-testid="stSidebar"] .streamlit-expanderContent {
                background: rgba(0,0,0,0.1) !important;
            }
        </style>""", unsafe_allow_html=True)
        
        render_sidebar()
        
        pages = {
            'dashboard': page_dashboard, 
            'form': page_form, 
            'success': page_success,
            'invite': page_invite, 
            'invitations': page_invitations, 
            'settings': page_settings
        }
        pages.get(st.session_state.page, page_dashboard)()

if __name__ == "__main__":
    main()
