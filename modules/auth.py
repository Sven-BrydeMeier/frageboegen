"""
Authentifizierung und Autorisierung
Login, Rollen, Sessions, Multi-Tenancy
"""

import streamlit as st
import hashlib
import secrets
import hmac
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import json


class UserRole(str, Enum):
    """Benutzerrollen"""
    SUPER_ADMIN = "super_admin"  # Voller Zugriff, alle Tenants
    ADMIN = "admin"             # Formular-Verwaltung, Benutzer-Verwaltung
    EDITOR = "editor"           # Formulare bearbeiten
    VIEWER = "viewer"           # Nur lesen, Submissions ansehen
    USER = "user"               # Nur Formulare ausfüllen
    MANDANT = "mandant"         # Externe Mandanten mit Token-Zugang


# Berechtigungen pro Rolle
ROLE_PERMISSIONS = {
    UserRole.SUPER_ADMIN: [
        "forms.create", "forms.edit", "forms.delete", "forms.view",
        "submissions.view", "submissions.edit", "submissions.delete", "submissions.export",
        "users.create", "users.edit", "users.delete", "users.view",
        "workflows.create", "workflows.edit", "workflows.delete",
        "templates.create", "templates.edit", "templates.delete",
        "settings.edit", "tenants.manage", "audit.view"
    ],
    UserRole.ADMIN: [
        "forms.create", "forms.edit", "forms.delete", "forms.view",
        "submissions.view", "submissions.edit", "submissions.export",
        "users.create", "users.edit", "users.view",
        "workflows.create", "workflows.edit", "workflows.delete",
        "templates.create", "templates.edit", "templates.delete",
        "settings.edit", "audit.view"
    ],
    UserRole.EDITOR: [
        "forms.create", "forms.edit", "forms.view",
        "submissions.view",
        "workflows.create", "workflows.edit",
        "templates.create", "templates.edit"
    ],
    UserRole.VIEWER: [
        "forms.view",
        "submissions.view", "submissions.export"
    ],
    UserRole.USER: [
        "forms.view",
        "submissions.create"
    ],
    UserRole.MANDANT: [
        "submissions.create"
    ],
}


@dataclass
class User:
    """Benutzer-Objekt"""
    id: str
    username: str
    email: str
    full_name: str
    role: UserRole
    tenant_id: Optional[str] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    settings: Dict[str, Any] = field(default_factory=dict)
    
    def has_permission(self, permission: str) -> bool:
        """Prüft ob Benutzer eine Berechtigung hat"""
        return permission in ROLE_PERMISSIONS.get(self.role, [])
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role.value,
            'tenant_id': self.tenant_id,
            'is_active': self.is_active,
        }


@dataclass
class Tenant:
    """Mandant/Organisation für Multi-Tenancy"""
    id: str
    name: str
    slug: str  # URL-freundlicher Name
    settings: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    
    # Branding
    logo_url: Optional[str] = None
    primary_color: str = "#b45309"
    
    # Limits
    max_users: int = 10
    max_forms: int = 50
    max_submissions_per_month: int = 1000
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'is_active': self.is_active,
            'logo_url': self.logo_url,
            'primary_color': self.primary_color,
        }


class AuthManager:
    """Verwaltet Authentifizierung und Sessions"""
    
    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or secrets.token_hex(32)
        self._users: Dict[str, Dict] = {}  # username -> user_data
        self._tenants: Dict[str, Tenant] = {}
        self._tokens: Dict[str, Dict] = {}  # token -> {user_id, expires}
        
        # Demo-Benutzer erstellen
        self._create_demo_users()
    
    def _create_demo_users(self):
        """Erstellt Demo-Benutzer"""
        demo_users = [
            {
                'id': 'user_admin',
                'username': 'admin',
                'email': 'admin@ra-rhm.de',
                'password': 'admin123',  # In Produktion: sichere Passwörter!
                'full_name': 'Administrator',
                'role': UserRole.ADMIN,
            },
            {
                'id': 'user_editor',
                'username': 'editor',
                'email': 'editor@ra-rhm.de',
                'password': 'editor123',
                'full_name': 'Sachbearbeiter',
                'role': UserRole.EDITOR,
            },
            {
                'id': 'user_viewer',
                'username': 'viewer',
                'email': 'viewer@ra-rhm.de',
                'password': 'viewer123',
                'full_name': 'Nur Lesen',
                'role': UserRole.VIEWER,
            },
        ]
        
        for user_data in demo_users:
            password = user_data.pop('password')
            self._users[user_data['username']] = {
                **user_data,
                'password_hash': self._hash_password(password),
            }
    
    def _hash_password(self, password: str) -> str:
        """Hasht ein Passwort"""
        return hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            self.secret_key.encode(),
            100000
        ).hex()
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verifiziert ein Passwort"""
        return hmac.compare_digest(
            self._hash_password(password),
            password_hash
        )
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authentifiziert einen Benutzer"""
        user_data = self._users.get(username)
        
        if not user_data:
            return None
        
        if not self._verify_password(password, user_data['password_hash']):
            return None
        
        if not user_data.get('is_active', True):
            return None
        
        # User-Objekt erstellen
        user = User(
            id=user_data['id'],
            username=user_data['username'],
            email=user_data['email'],
            full_name=user_data['full_name'],
            role=user_data['role'],
            tenant_id=user_data.get('tenant_id'),
        )
        
        # Last Login aktualisieren
        user_data['last_login'] = datetime.now()
        
        return user
    
    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: str,
        role: UserRole,
        tenant_id: Optional[str] = None
    ) -> User:
        """Erstellt einen neuen Benutzer"""
        if username in self._users:
            raise ValueError(f"Benutzer '{username}' existiert bereits")
        
        user_id = f"user_{secrets.token_hex(8)}"
        
        self._users[username] = {
            'id': user_id,
            'username': username,
            'email': email,
            'password_hash': self._hash_password(password),
            'full_name': full_name,
            'role': role,
            'tenant_id': tenant_id,
            'is_active': True,
            'created_at': datetime.now(),
        }
        
        return User(
            id=user_id,
            username=username,
            email=email,
            full_name=full_name,
            role=role,
            tenant_id=tenant_id,
        )
    
    def create_token(self, user_id: str, expires_hours: int = 24) -> str:
        """Erstellt ein Zugangs-Token"""
        token = secrets.token_urlsafe(32)
        self._tokens[token] = {
            'user_id': user_id,
            'expires': datetime.now() + timedelta(hours=expires_hours),
        }
        return token
    
    def verify_token(self, token: str) -> Optional[str]:
        """Verifiziert ein Token und gibt die User-ID zurück"""
        token_data = self._tokens.get(token)
        
        if not token_data:
            return None
        
        if datetime.now() > token_data['expires']:
            del self._tokens[token]
            return None
        
        return token_data['user_id']
    
    def create_mandant_token(
        self,
        form_id: str,
        recipient_name: str,
        recipient_email: str,
        expires_days: int = 7
    ) -> str:
        """Erstellt ein Einladungs-Token für Mandanten"""
        token = secrets.token_urlsafe(16)
        self._tokens[token] = {
            'type': 'mandant',
            'form_id': form_id,
            'recipient_name': recipient_name,
            'recipient_email': recipient_email,
            'expires': datetime.now() + timedelta(days=expires_days),
            'created_at': datetime.now(),
        }
        return token
    
    def verify_mandant_token(self, token: str) -> Optional[Dict]:
        """Verifiziert ein Mandanten-Token"""
        token_data = self._tokens.get(token)
        
        if not token_data:
            return None
        
        if token_data.get('type') != 'mandant':
            return None
        
        if datetime.now() > token_data['expires']:
            return None
        
        return token_data
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Holt einen Benutzer anhand der ID"""
        for username, data in self._users.items():
            if data['id'] == user_id:
                return User(
                    id=data['id'],
                    username=data['username'],
                    email=data['email'],
                    full_name=data['full_name'],
                    role=data['role'],
                    tenant_id=data.get('tenant_id'),
                )
        return None
    
    def get_all_users(self, tenant_id: Optional[str] = None) -> List[User]:
        """Holt alle Benutzer (optional gefiltert nach Tenant)"""
        users = []
        for username, data in self._users.items():
            if tenant_id and data.get('tenant_id') != tenant_id:
                continue
            users.append(User(
                id=data['id'],
                username=data['username'],
                email=data['email'],
                full_name=data['full_name'],
                role=data['role'],
                tenant_id=data.get('tenant_id'),
            ))
        return users
    
    # === Tenant Management ===
    
    def create_tenant(
        self,
        name: str,
        slug: str,
        **kwargs
    ) -> Tenant:
        """Erstellt einen neuen Tenant"""
        if slug in self._tenants:
            raise ValueError(f"Tenant '{slug}' existiert bereits")
        
        tenant = Tenant(
            id=f"tenant_{secrets.token_hex(8)}",
            name=name,
            slug=slug,
            **kwargs
        )
        
        self._tenants[slug] = tenant
        return tenant
    
    def get_tenant(self, slug: str) -> Optional[Tenant]:
        """Holt einen Tenant"""
        return self._tenants.get(slug)


# ============================================
# Streamlit Integration
# ============================================

def init_auth_state():
    """Initialisiert Auth im Session State"""
    if 'auth_manager' not in st.session_state:
        # Secret Key aus st.secrets oder generieren
        try:
            secret_key = st.secrets.get("auth", {}).get("secret_key")
        except:
            secret_key = None
        
        st.session_state.auth_manager = AuthManager(secret_key)
    
    if 'current_user' not in st.session_state:
        st.session_state.current_user = None
    
    if 'auth_token' not in st.session_state:
        st.session_state.auth_token = None


def login_user(username: str, password: str) -> bool:
    """Loggt einen Benutzer ein"""
    init_auth_state()
    
    user = st.session_state.auth_manager.authenticate(username, password)
    
    if user:
        st.session_state.current_user = user
        st.session_state.auth_token = st.session_state.auth_manager.create_token(user.id)
        return True
    
    return False


def logout_user():
    """Loggt den aktuellen Benutzer aus"""
    st.session_state.current_user = None
    st.session_state.auth_token = None


def get_current_user() -> Optional[User]:
    """Gibt den aktuell eingeloggten Benutzer zurück"""
    init_auth_state()
    return st.session_state.current_user


def require_auth(permission: Optional[str] = None):
    """Decorator/Check für geschützte Seiten"""
    user = get_current_user()
    
    if not user:
        return False
    
    if permission and not user.has_permission(permission):
        return False
    
    return True


def render_login_form():
    """Rendert das Login-Formular"""
    st.markdown("## 🔐 Anmeldung")
    
    with st.form("login_form"):
        username = st.text_input("Benutzername")
        password = st.text_input("Passwort", type="password")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            submitted = st.form_submit_button("Anmelden", type="primary", use_container_width=True)
        
        if submitted:
            if login_user(username, password):
                st.success("✅ Erfolgreich angemeldet!")
                st.rerun()
            else:
                st.error("❌ Ungültige Anmeldedaten")
    
    st.markdown("---")
    st.caption("Demo-Zugänge: admin/admin123, editor/editor123, viewer/viewer123")


def render_user_menu():
    """Rendert das Benutzer-Menü in der Sidebar"""
    user = get_current_user()
    
    if user:
        st.markdown(f"👤 **{user.full_name}**")
        st.caption(f"Rolle: {user.role.value}")
        
        if st.button("🚪 Abmelden", use_container_width=True):
            logout_user()
            st.rerun()
    else:
        st.warning("Nicht angemeldet")


def render_user_management():
    """Rendert die Benutzerverwaltung"""
    st.markdown("## 👥 Benutzerverwaltung")
    
    user = get_current_user()
    if not user or not user.has_permission("users.view"):
        st.error("Keine Berechtigung")
        return
    
    auth = st.session_state.auth_manager
    users = auth.get_all_users()
    
    # Benutzer-Liste
    st.markdown("### Benutzer")
    
    for u in users:
        col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
        col1.write(f"**{u.full_name}** ({u.username})")
        col2.write(u.email)
        col3.write(u.role.value)
        if user.has_permission("users.edit"):
            col4.button("✏️", key=f"edit_{u.id}")
    
    # Neuer Benutzer
    if user.has_permission("users.create"):
        st.markdown("---")
        st.markdown("### Neuen Benutzer anlegen")
        
        with st.form("new_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_username = st.text_input("Benutzername *")
                new_email = st.text_input("E-Mail *")
            with col2:
                new_fullname = st.text_input("Vollständiger Name *")
                new_password = st.text_input("Passwort *", type="password")
            
            new_role = st.selectbox(
                "Rolle",
                [r for r in UserRole if r != UserRole.SUPER_ADMIN],
                format_func=lambda r: r.value
            )
            
            if st.form_submit_button("Benutzer anlegen", type="primary"):
                try:
                    auth.create_user(
                        username=new_username,
                        email=new_email,
                        password=new_password,
                        full_name=new_fullname,
                        role=new_role
                    )
                    st.success("✅ Benutzer angelegt!")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
