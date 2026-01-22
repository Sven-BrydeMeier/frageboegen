"""
Docusign eSignature Integration
Digitale Unterschriften für Dokumente
"""

import os
import base64
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json

# Docusign SDK
try:
    from docusign_esign import ApiClient, EnvelopesApi, EnvelopeDefinition
    from docusign_esign import Document, Signer, CarbonCopy, SignHere, Tabs, Recipients
    from docusign_esign.client.api_exception import ApiException
    HAS_DOCUSIGN = True
except ImportError:
    HAS_DOCUSIGN = False


class SignatureStatus(str, Enum):
    """Status einer Signatur-Anfrage"""
    CREATED = "created"
    SENT = "sent"
    DELIVERED = "delivered"
    SIGNED = "signed"
    COMPLETED = "completed"
    DECLINED = "declined"
    VOIDED = "voided"
    EXPIRED = "expired"


@dataclass
class DocusignConfig:
    """Docusign API Konfiguration"""
    integration_key: str  # Client ID
    user_id: str  # Impersonated User ID
    account_id: str  # Account ID
    private_key_path: Optional[str] = None  # Pfad zur RSA Private Key Datei
    private_key: Optional[str] = None  # Oder direkt der Key als String
    base_path: str = "https://demo.docusign.net/restapi"  # Demo oder Produktion
    oauth_host: str = "account-d.docusign.com"  # Demo OAuth Host
    
    # Für Produktion:
    # base_path = "https://www.docusign.net/restapi"
    # oauth_host = "account.docusign.com"
    
    # Token Caching
    access_token: Optional[str] = None
    token_expires: Optional[datetime] = None


@dataclass
class SignerInfo:
    """Informationen zu einem Unterzeichner"""
    email: str
    name: str
    recipient_id: str = "1"
    routing_order: str = "1"
    
    # Signatur-Position (optional)
    anchor_string: Optional[str] = None  # z.B. "/sig1/" im Dokument
    anchor_x_offset: str = "0"
    anchor_y_offset: str = "0"
    
    # Oder absolute Position
    page_number: str = "1"
    x_position: str = "100"
    y_position: str = "100"


@dataclass 
class SignatureRequest:
    """Signatur-Anfrage"""
    id: str
    envelope_id: Optional[str] = None
    status: SignatureStatus = SignatureStatus.CREATED
    document_name: str = ""
    signers: List[SignerInfo] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    # Tracking
    submission_id: Optional[str] = None
    form_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'envelope_id': self.envelope_id,
            'status': self.status.value,
            'document_name': self.document_name,
            'signers': [{'email': s.email, 'name': s.name} for s in self.signers],
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class DocusignClient:
    """
    Docusign eSignature Client
    
    Verwendet JWT Grant für Server-zu-Server Authentifizierung
    """
    
    def __init__(self, config: DocusignConfig):
        if not HAS_DOCUSIGN:
            raise ImportError(
                "docusign-esign ist nicht installiert: "
                "pip install docusign-esign"
            )
        
        self.config = config
        self.api_client = ApiClient()
        self.api_client.set_base_path(config.base_path)
    
    def _get_private_key(self) -> str:
        """Lädt den Private Key"""
        if self.config.private_key:
            return self.config.private_key
        
        if self.config.private_key_path:
            with open(self.config.private_key_path, 'r') as f:
                return f.read()
        
        raise ValueError("Kein Private Key konfiguriert")
    
    def _authenticate(self) -> str:
        """
        Authentifiziert mit JWT Grant
        Returns: Access Token
        """
        # Prüfen ob Token noch gültig
        if (self.config.access_token and 
            self.config.token_expires and 
            datetime.now() < self.config.token_expires):
            return self.config.access_token
        
        private_key = self._get_private_key()
        
        # JWT Token anfordern
        response = self.api_client.request_jwt_user_token(
            client_id=self.config.integration_key,
            user_id=self.config.user_id,
            oauth_host_name=self.config.oauth_host,
            private_key_bytes=private_key.encode(),
            expires_in=3600,
            scopes=["signature", "impersonation"]
        )
        
        self.config.access_token = response.access_token
        self.config.token_expires = datetime.now() + timedelta(seconds=3500)
        
        # Token setzen
        self.api_client.set_default_header(
            "Authorization",
            f"Bearer {response.access_token}"
        )
        
        return response.access_token
    
    def send_for_signature(
        self,
        document_bytes: bytes,
        document_name: str,
        signers: List[SignerInfo],
        email_subject: str = "Bitte unterschreiben Sie dieses Dokument",
        email_body: str = "Bitte überprüfen und unterschreiben Sie das beigefügte Dokument.",
        cc_recipients: Optional[List[Dict[str, str]]] = None
    ) -> SignatureRequest:
        """
        Sendet ein Dokument zur Unterschrift
        
        Args:
            document_bytes: Dokument als Bytes (PDF empfohlen)
            document_name: Name des Dokuments
            signers: Liste der Unterzeichner
            email_subject: E-Mail Betreff
            email_body: E-Mail Text
            cc_recipients: CC-Empfänger [{'email': '', 'name': ''}]
        
        Returns:
            SignatureRequest mit Envelope-ID
        """
        self._authenticate()
        
        # Dokument Base64 kodieren
        doc_base64 = base64.b64encode(document_bytes).decode('ascii')
        
        # Document Definition
        document = Document(
            document_base64=doc_base64,
            name=document_name,
            file_extension="pdf",
            document_id="1"
        )
        
        # Signer mit Tabs (Unterschriftsfelder)
        signer_list = []
        for signer_info in signers:
            # Signatur-Tab erstellen
            if signer_info.anchor_string:
                sign_here = SignHere(
                    anchor_string=signer_info.anchor_string,
                    anchor_units="pixels",
                    anchor_x_offset=signer_info.anchor_x_offset,
                    anchor_y_offset=signer_info.anchor_y_offset
                )
            else:
                sign_here = SignHere(
                    document_id="1",
                    page_number=signer_info.page_number,
                    x_position=signer_info.x_position,
                    y_position=signer_info.y_position
                )
            
            signer = Signer(
                email=signer_info.email,
                name=signer_info.name,
                recipient_id=signer_info.recipient_id,
                routing_order=signer_info.routing_order,
                tabs=Tabs(sign_here_tabs=[sign_here])
            )
            signer_list.append(signer)
        
        # CC Recipients
        cc_list = []
        if cc_recipients:
            for i, cc in enumerate(cc_recipients):
                cc_list.append(CarbonCopy(
                    email=cc['email'],
                    name=cc['name'],
                    recipient_id=str(len(signers) + i + 1),
                    routing_order=str(len(signers) + 1)
                ))
        
        # Recipients
        recipients = Recipients(
            signers=signer_list,
            carbon_copies=cc_list if cc_list else None
        )
        
        # Envelope Definition
        envelope_definition = EnvelopeDefinition(
            email_subject=email_subject,
            email_blurb=email_body,
            documents=[document],
            recipients=recipients,
            status="sent"  # Direkt senden
        )
        
        # Envelope erstellen und senden
        envelopes_api = EnvelopesApi(self.api_client)
        
        try:
            envelope_summary = envelopes_api.create_envelope(
                account_id=self.config.account_id,
                envelope_definition=envelope_definition
            )
            
            # Request erstellen
            request = SignatureRequest(
                id=f"sig_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:12]}",
                envelope_id=envelope_summary.envelope_id,
                status=SignatureStatus.SENT,
                document_name=document_name,
                signers=signers,
            )
            
            return request
            
        except ApiException as e:
            raise Exception(f"Docusign API Fehler: {e.body}")
    
    def get_envelope_status(self, envelope_id: str) -> Dict[str, Any]:
        """
        Holt den Status eines Envelopes
        """
        self._authenticate()
        
        envelopes_api = EnvelopesApi(self.api_client)
        
        envelope = envelopes_api.get_envelope(
            account_id=self.config.account_id,
            envelope_id=envelope_id
        )
        
        return {
            'envelope_id': envelope.envelope_id,
            'status': envelope.status,
            'status_changed_date': envelope.status_changed_date_time,
            'sent_date': envelope.sent_date_time,
            'completed_date': envelope.completed_date_time,
            'voided_reason': envelope.voided_reason,
        }
    
    def get_signed_document(self, envelope_id: str) -> bytes:
        """
        Lädt das unterschriebene Dokument herunter
        """
        self._authenticate()
        
        envelopes_api = EnvelopesApi(self.api_client)
        
        # Dokument als Bytes holen
        document = envelopes_api.get_document(
            account_id=self.config.account_id,
            envelope_id=envelope_id,
            document_id="combined"  # Alle Dokumente kombiniert
        )
        
        return document
    
    def void_envelope(self, envelope_id: str, reason: str = "Storniert") -> bool:
        """
        Storniert einen Envelope
        """
        self._authenticate()
        
        envelopes_api = EnvelopesApi(self.api_client)
        
        from docusign_esign import Envelope
        envelope = Envelope(status="voided", voided_reason=reason)
        
        try:
            envelopes_api.update(
                account_id=self.config.account_id,
                envelope_id=envelope_id,
                envelope=envelope
            )
            return True
        except ApiException:
            return False
    
    def create_embedded_signing_url(
        self,
        envelope_id: str,
        signer_email: str,
        signer_name: str,
        return_url: str,
        recipient_id: str = "1"
    ) -> str:
        """
        Erstellt eine URL für Embedded Signing
        (Unterschrift direkt in der App)
        """
        self._authenticate()
        
        envelopes_api = EnvelopesApi(self.api_client)
        
        from docusign_esign import RecipientViewRequest
        
        view_request = RecipientViewRequest(
            authentication_method="none",
            client_user_id=recipient_id,
            recipient_id=recipient_id,
            return_url=return_url,
            user_name=signer_name,
            email=signer_email
        )
        
        results = envelopes_api.create_recipient_view(
            account_id=self.config.account_id,
            envelope_id=envelope_id,
            recipient_view_request=view_request
        )
        
        return results.url


# ============================================
# Webhook Handler für Docusign Connect
# ============================================

class DocusignWebhookHandler:
    """
    Verarbeitet Docusign Connect Webhooks
    """
    
    @staticmethod
    def parse_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parst einen Docusign Connect Webhook
        """
        envelope_id = payload.get('envelopeId')
        status = payload.get('status')
        
        # Recipients Status
        recipients = []
        for recipient in payload.get('recipients', {}).get('signers', []):
            recipients.append({
                'email': recipient.get('email'),
                'name': recipient.get('name'),
                'status': recipient.get('status'),
                'signed_date': recipient.get('signedDateTime'),
            })
        
        return {
            'envelope_id': envelope_id,
            'status': status,
            'status_changed': payload.get('statusChangedDateTime'),
            'recipients': recipients,
            'completed': status == 'completed',
        }
    
    @staticmethod
    def verify_hmac(
        payload: bytes,
        signature: str,
        secret: str
    ) -> bool:
        """
        Verifiziert die HMAC Signatur eines Webhooks
        """
        import hmac as hmac_lib
        
        expected = hmac_lib.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).digest()
        
        expected_b64 = base64.b64encode(expected).decode()
        
        return hmac_lib.compare_digest(expected_b64, signature)


# ============================================
# Streamlit Integration
# ============================================

def render_signature_status(request: SignatureRequest):
    """Rendert den Signatur-Status in Streamlit"""
    import streamlit as st
    
    status_colors = {
        SignatureStatus.CREATED: "🟡",
        SignatureStatus.SENT: "🔵",
        SignatureStatus.DELIVERED: "🔵",
        SignatureStatus.SIGNED: "🟢",
        SignatureStatus.COMPLETED: "✅",
        SignatureStatus.DECLINED: "🔴",
        SignatureStatus.VOIDED: "⚫",
        SignatureStatus.EXPIRED: "🟠",
    }
    
    icon = status_colors.get(request.status, "⚪")
    
    st.markdown(f"### {icon} Signatur: {request.document_name}")
    st.write(f"**Status:** {request.status.value}")
    st.write(f"**Erstellt:** {request.created_at.strftime('%d.%m.%Y %H:%M')}")
    
    if request.envelope_id:
        st.code(f"Envelope-ID: {request.envelope_id}")
    
    st.markdown("**Unterzeichner:**")
    for signer in request.signers:
        st.write(f"- {signer.name} ({signer.email})")


if __name__ == "__main__":
    print(f"Docusign SDK verfügbar: {HAS_DOCUSIGN}")
