"""
Multi-Tenancy Unterstützung
Ermöglicht mehrere Mandanten/Organisationen in einer Installation
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import json

try:
    from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer, JSON
    from sqlalchemy.orm import relationship
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


class TenantStatus(str, Enum):
    """Tenant-Status"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    CANCELLED = "cancelled"


@dataclass
class TenantSettings:
    """Einstellungen pro Tenant"""
    # Branding
    logo_url: Optional[str] = None
    primary_color: str = "#b45309"
    secondary_color: str = "#f59e0b"
    
    # E-Mail
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    
    # Dokumente
    document_header: Optional[str] = None
    document_footer: Optional[str] = None
    
    # Features
    allow_public_forms: bool = True
    allow_file_uploads: bool = True
    max_upload_size_mb: int = 10
    
    # Limits
    max_forms: int = 50
    max_submissions_per_month: int = 1000
    max_users: int = 10
    max_storage_gb: float = 5.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'logo_url': self.logo_url,
            'primary_color': self.primary_color,
            'secondary_color': self.secondary_color,
            'smtp_host': self.smtp_host,
            'smtp_port': self.smtp_port,
            'from_email': self.from_email,
            'from_name': self.from_name,
            'document_header': self.document_header,
            'document_footer': self.document_footer,
            'allow_public_forms': self.allow_public_forms,
            'allow_file_uploads': self.allow_file_uploads,
            'max_upload_size_mb': self.max_upload_size_mb,
            'max_forms': self.max_forms,
            'max_submissions_per_month': self.max_submissions_per_month,
            'max_users': self.max_users,
            'max_storage_gb': self.max_storage_gb,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TenantSettings":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Tenant:
    """Tenant/Organisation"""
    id: str
    name: str
    slug: str  # URL-freundlicher Name (eindeutig)
    
    status: TenantStatus = TenantStatus.ACTIVE
    settings: TenantSettings = field(default_factory=TenantSettings)
    
    # Kontakt
    contact_email: Optional[str] = None
    contact_name: Optional[str] = None
    
    # Abrechnung
    plan: str = "free"  # free, starter, professional, enterprise
    billing_email: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    
    # Statistiken (cached)
    form_count: int = 0
    user_count: int = 0
    submission_count_this_month: int = 0
    storage_used_mb: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'status': self.status.value,
            'settings': self.settings.to_dict(),
            'contact_email': self.contact_email,
            'contact_name': self.contact_name,
            'plan': self.plan,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
    
    def is_active(self) -> bool:
        return self.status in [TenantStatus.ACTIVE, TenantStatus.TRIAL]
    
    def can_create_form(self) -> bool:
        return self.form_count < self.settings.max_forms
    
    def can_add_user(self) -> bool:
        return self.user_count < self.settings.max_users
    
    def can_receive_submission(self) -> bool:
        return self.submission_count_this_month < self.settings.max_submissions_per_month
    
    def storage_remaining_mb(self) -> float:
        return (self.settings.max_storage_gb * 1024) - self.storage_used_mb


class TenantManager:
    """
    Verwaltet Tenants
    """
    
    def __init__(self, storage_path: str = "./tenants"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
        self._cache: Dict[str, Tenant] = {}
    
    def _get_tenant_path(self, tenant_id: str) -> str:
        return os.path.join(self.storage_path, f"{tenant_id}.json")
    
    def create_tenant(
        self,
        name: str,
        slug: str,
        contact_email: Optional[str] = None,
        plan: str = "free",
        **kwargs
    ) -> Tenant:
        """
        Erstellt einen neuen Tenant
        """
        import secrets
        
        # Slug validieren
        if not slug or not slug.replace('-', '').replace('_', '').isalnum():
            raise ValueError("Slug darf nur Buchstaben, Zahlen, - und _ enthalten")
        
        # Prüfen ob Slug bereits existiert
        if self.get_tenant_by_slug(slug):
            raise ValueError(f"Slug '{slug}' ist bereits vergeben")
        
        tenant_id = f"tenant_{secrets.token_hex(8)}"
        
        tenant = Tenant(
            id=tenant_id,
            name=name,
            slug=slug.lower(),
            contact_email=contact_email,
            plan=plan,
            settings=TenantSettings(**kwargs.get('settings', {})),
        )
        
        self.save_tenant(tenant)
        
        return tenant
    
    def save_tenant(self, tenant: Tenant):
        """Speichert einen Tenant"""
        tenant.updated_at = datetime.now()
        
        data = tenant.to_dict()
        data['settings'] = tenant.settings.to_dict()
        
        path = self._get_tenant_path(tenant.id)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        self._cache[tenant.id] = tenant
        self._cache[f"slug:{tenant.slug}"] = tenant
    
    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Holt einen Tenant per ID"""
        if tenant_id in self._cache:
            return self._cache[tenant_id]
        
        path = self._get_tenant_path(tenant_id)
        if not os.path.exists(path):
            return None
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        settings = TenantSettings.from_dict(data.get('settings', {}))
        
        tenant = Tenant(
            id=data['id'],
            name=data['name'],
            slug=data['slug'],
            status=TenantStatus(data.get('status', 'active')),
            settings=settings,
            contact_email=data.get('contact_email'),
            contact_name=data.get('contact_name'),
            plan=data.get('plan', 'free'),
        )
        
        self._cache[tenant_id] = tenant
        return tenant
    
    def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        """Holt einen Tenant per Slug"""
        cache_key = f"slug:{slug}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Alle Tenants durchsuchen
        for filename in os.listdir(self.storage_path):
            if filename.endswith('.json'):
                tenant_id = filename[:-5]
                tenant = self.get_tenant(tenant_id)
                if tenant and tenant.slug == slug:
                    self._cache[cache_key] = tenant
                    return tenant
        
        return None
    
    def list_tenants(
        self,
        status: Optional[TenantStatus] = None,
        plan: Optional[str] = None
    ) -> List[Tenant]:
        """Listet alle Tenants"""
        tenants = []
        
        for filename in os.listdir(self.storage_path):
            if filename.endswith('.json'):
                tenant_id = filename[:-5]
                tenant = self.get_tenant(tenant_id)
                
                if tenant:
                    if status and tenant.status != status:
                        continue
                    if plan and tenant.plan != plan:
                        continue
                    tenants.append(tenant)
        
        return sorted(tenants, key=lambda t: t.name)
    
    def update_tenant_stats(
        self,
        tenant_id: str,
        form_count: Optional[int] = None,
        user_count: Optional[int] = None,
        submission_count_this_month: Optional[int] = None,
        storage_used_mb: Optional[float] = None
    ):
        """Aktualisiert Tenant-Statistiken"""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return
        
        if form_count is not None:
            tenant.form_count = form_count
        if user_count is not None:
            tenant.user_count = user_count
        if submission_count_this_month is not None:
            tenant.submission_count_this_month = submission_count_this_month
        if storage_used_mb is not None:
            tenant.storage_used_mb = storage_used_mb
        
        self.save_tenant(tenant)
    
    def delete_tenant(self, tenant_id: str) -> bool:
        """Löscht einen Tenant (soft delete)"""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False
        
        tenant.status = TenantStatus.CANCELLED
        self.save_tenant(tenant)
        
        return True


# ============================================
# Tenant Context für Streamlit
# ============================================

class TenantContext:
    """
    Kontext-Manager für Tenant-bezogene Operationen
    """
    
    def __init__(self, tenant: Tenant):
        self.tenant = tenant
    
    def get_branding(self) -> Dict[str, Any]:
        """Gibt Branding-Einstellungen zurück"""
        return {
            'logo_url': self.tenant.settings.logo_url,
            'primary_color': self.tenant.settings.primary_color,
            'secondary_color': self.tenant.settings.secondary_color,
            'name': self.tenant.name,
        }
    
    def get_css(self) -> str:
        """Generiert Custom CSS für den Tenant"""
        return f"""
        <style>
            :root {{
                --tenant-primary: {self.tenant.settings.primary_color};
                --tenant-secondary: {self.tenant.settings.secondary_color};
            }}
            
            section[data-testid="stSidebar"] {{
                background: linear-gradient(180deg, 
                    {self.tenant.settings.primary_color}, 
                    {self.tenant.settings.secondary_color});
            }}
            
            .stButton > button[kind="primary"] {{
                background-color: {self.tenant.settings.primary_color};
            }}
        </style>
        """
    
    def get_storage_path(self) -> str:
        """Gibt den Storage-Pfad für den Tenant zurück"""
        return f"./storage/{self.tenant.id}"
    
    def can_upload(self, file_size_mb: float) -> bool:
        """Prüft ob Upload erlaubt ist"""
        if not self.tenant.settings.allow_file_uploads:
            return False
        if file_size_mb > self.tenant.settings.max_upload_size_mb:
            return False
        if self.tenant.storage_remaining_mb() < file_size_mb:
            return False
        return True


# ============================================
# Streamlit Integration
# ============================================

def get_tenant_from_url() -> Optional[str]:
    """
    Extrahiert Tenant-Slug aus URL
    Unterstützt: subdomain, query param, path
    """
    import streamlit as st
    
    # 1. Query Parameter: ?tenant=slug
    params = st.query_params
    if 'tenant' in params:
        return params['tenant']
    
    # 2. Für Subdomain oder Path müsste man 
    #    st.runtime.scriptrunner.get_script_run_ctx() verwenden
    #    (nicht trivial in Streamlit)
    
    return None


def init_tenant_context():
    """
    Initialisiert Tenant-Kontext im Session State
    """
    import streamlit as st
    
    if 'tenant_manager' not in st.session_state:
        st.session_state.tenant_manager = TenantManager()
    
    if 'current_tenant' not in st.session_state:
        slug = get_tenant_from_url()
        if slug:
            tenant = st.session_state.tenant_manager.get_tenant_by_slug(slug)
            if tenant and tenant.is_active():
                st.session_state.current_tenant = tenant
            else:
                st.session_state.current_tenant = None
        else:
            st.session_state.current_tenant = None


def require_tenant():
    """
    Stellt sicher dass ein Tenant aktiv ist
    """
    import streamlit as st
    
    init_tenant_context()
    
    if not st.session_state.get('current_tenant'):
        st.error("Kein gültiger Mandant ausgewählt")
        st.stop()
    
    return st.session_state.current_tenant


def apply_tenant_branding():
    """
    Wendet Tenant-Branding an
    """
    import streamlit as st
    
    tenant = st.session_state.get('current_tenant')
    if not tenant:
        return
    
    ctx = TenantContext(tenant)
    st.markdown(ctx.get_css(), unsafe_allow_html=True)
    
    # Logo in Sidebar
    if tenant.settings.logo_url:
        with st.sidebar:
            st.image(tenant.settings.logo_url, width=150)


if __name__ == "__main__":
    # Test
    manager = TenantManager("./test_tenants")
    
    # Tenant erstellen
    tenant = manager.create_tenant(
        name="Test Kanzlei",
        slug="test-kanzlei",
        contact_email="test@example.com",
        plan="professional"
    )
    
    print(f"Tenant erstellt: {tenant.id}")
    print(f"Slug: {tenant.slug}")
    print(f"Status: {tenant.status}")
