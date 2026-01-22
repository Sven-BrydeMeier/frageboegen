"""
DocuSign eSignature Integration
Für elektronische Unterschriften in Dokumenten
"""

import os
import json
import base64
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

# DocuSign
try:
    from docusign_esign import ApiClient, EnvelopesApi, EnvelopeDefinition
    from docusign_esign import Document, Signer, SignHere, Tabs, Recipients
    from docusign_esign.client.api_exception import ApiException
    HAS_DOCUSIGN = True
except ImportError:
    HAS_DOCUSIGN = False


class SignatureStatus(str, Enum):
    """Status einer Unterschrifts-Anfrage"""
    CREATED = "created"
    SENT = "sent"
    DELIVERED = "delivered"
    SIGNED = "signed"
    COMPLETED = "completed"
    DECLINED = "declined"
    VOIDED = "voided"
    EXPIRED = "expired"


@dataclass
class DocuSignConfig:
    """DocuSign API Konfiguration"""
    integration_key: str  # Client ID
    user_id: str  # Impersonation User ID
    account_id: str  # DocuSign Account ID
    private_key_path: Optional[str] = None  # Pfad zur RSA Private Key Datei
    private_key: Optional[str] = None  # RSA Private Key direkt
    base_path: str = "https://demo.docusign.net/restapi"  # Demo oder Prod
    oauth_host_name: str = "account-d.docusign.com"  # Demo OAuth
    
    # Für Produktion:
    # base_path = "https://www.docusign.net/restapi"
    # oauth_host_name = "account.docusign.com"
    
    scopes: List[str] = field(default_factory=lambda: ["signature", "impersonation"])


@dataclass
class SignatureRequest:
    """Unterschrifts-Anfrage"""
    document_name: str
    document_bytes: bytes
    document_extension: str  # pdf, docx
    
    signers: List[Dict[str, Any]]  # [{email, name, recipient_id, order}]
    
    email_subject: str = "Bitte unterschreiben Sie dieses Dokument"
    email_body: str = "Bitte überprüfen und unterschreiben Sie das beigefügte Dokument."
    
    # Optionen
    expire_after_days: int = 30
    reminder_delay_days: int = 3
    reminder_frequency_days: int = 2
    
    # Callback URL
    webhook_url: Optional[str] = None


@dataclass
class SignatureResult:
    """Ergebnis einer Unterschrifts-Anfrage"""
    envelope_id: str
    status: SignatureStatus
    created_at: datetime
    sent_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    signers_status: List[Dict[str, Any]] = field(default_factory=list)
    signed_document_bytes: Optional[bytes] = None
    
    error: Optional[str] = None


class DocuSignClient:
    """
    DocuSign eSignature Client
    """
    
    def __init__(self, config: DocuSignConfig):
        if not HAS_DOCUSIGN:
            raise ImportError(
                "docusign-esign nicht installiert: "
                "pip install docusign-esign"
            )
        
        self.config = config
        self.api_client = self._create_api_client()
    
    def _create_api_client(self) -> ApiClient:
        """Erstellt und authentifiziert den API Client"""
        api_client = ApiClient()
        api_client.set_base_path(self.config.base_path)
        api_client.set_oauth_host_name(self.config.oauth_host_name)
        
        # Private Key laden
        if self.config.private_key:
            private_key = self.config.private_key
        elif self.config.private_key_path:
            with open(self.config.private_key_path, 'r') as f:
                private_key = f.read()
        else:
            raise ValueError("Private Key erforderlich")
        
        # JWT Token abrufen
        token_response = api_client.request_jwt_user_token(
            client_id=self.config.integration_key,
            user_id=self.config.user_id,
            oauth_host_name=self.config.oauth_host_name,
            private_key_bytes=private_key.encode(),
            expires_in=3600,
            scopes=self.config.scopes
        )
        
        api_client.set_default_header(
            "Authorization",
            f"Bearer {token_response.access_token}"
        )
        
        return api_client
    
    def send_for_signature(self, request: SignatureRequest) -> SignatureResult:
        """
        Sendet ein Dokument zur Unterschrift
        
        Args:
            request: SignatureRequest mit Dokument und Unterzeichnern
        
        Returns:
            SignatureResult mit Envelope-ID und Status
        """
        try:
            # Dokument erstellen
            document = Document(
                document_base64=base64.b64encode(request.document_bytes).decode(),
                name=request.document_name,
                file_extension=request.document_extension,
                document_id="1"
            )
            
            # Unterzeichner erstellen
            signers = []
            for i, signer_info in enumerate(request.signers):
                # Unterschrifts-Position (kann angepasst werden)
                sign_here = SignHere(
                    anchor_string="/sig/",  # Sucht nach /sig/ im Dokument
                    anchor_units="pixels",
                    anchor_y_offset="10",
                    anchor_x_offset="20",
                    recipient_id=str(signer_info.get('recipient_id', i + 1)),
                    tab_label=f"SignHere_{i + 1}"
                )
                
                # Alternativ: Feste Position
                if 'page_number' in signer_info:
                    sign_here = SignHere(
                        document_id="1",
                        page_number=str(signer_info.get('page_number', 1)),
                        x_position=str(signer_info.get('x_position', 100)),
                        y_position=str(signer_info.get('y_position', 700)),
                        recipient_id=str(signer_info.get('recipient_id', i + 1)),
                        tab_label=f"SignHere_{i + 1}"
                    )
                
                tabs = Tabs(sign_here_tabs=[sign_here])
                
                signer = Signer(
                    email=signer_info['email'],
                    name=signer_info['name'],
                    recipient_id=str(signer_info.get('recipient_id', i + 1)),
                    routing_order=str(signer_info.get('order', i + 1)),
                    tabs=tabs
                )
                signers.append(signer)
            
            recipients = Recipients(signers=signers)
            
            # Envelope erstellen
            envelope_definition = EnvelopeDefinition(
                email_subject=request.email_subject,
                email_blurb=request.email_body,
                documents=[document],
                recipients=recipients,
                status="sent"  # Sofort senden
            )
            
            # Event Notification (Webhook)
            if request.webhook_url:
                from docusign_esign import EventNotification, EnvelopeEvent
                
                event_notification = EventNotification(
                    url=request.webhook_url,
                    logging_enabled=True,
                    envelope_events=[
                        EnvelopeEvent(envelope_event_status_code="completed"),
                        EnvelopeEvent(envelope_event_status_code="declined"),
                        EnvelopeEvent(envelope_event_status_code="delivered"),
                    ]
                )
                envelope_definition.event_notification = event_notification
            
            # Envelope senden
            envelopes_api = EnvelopesApi(self.api_client)
            
            result = envelopes_api.create_envelope(
                account_id=self.config.account_id,
                envelope_definition=envelope_definition
            )
            
            return SignatureResult(
                envelope_id=result.envelope_id,
                status=SignatureStatus.SENT,
                created_at=datetime.now(),
                sent_at=datetime.now()
            )
            
        except ApiException as e:
            return SignatureResult(
                envelope_id="",
                status=SignatureStatus.CREATED,
                created_at=datetime.now(),
                error=f"DocuSign API Fehler: {e.body}"
            )
        except Exception as e:
            return SignatureResult(
                envelope_id="",
                status=SignatureStatus.CREATED,
                created_at=datetime.now(),
                error=str(e)
            )
    
    def get_envelope_status(self, envelope_id: str) -> SignatureResult:
        """
        Holt den Status eines Envelopes
        """
        try:
            envelopes_api = EnvelopesApi(self.api_client)
            
            envelope = envelopes_api.get_envelope(
                account_id=self.config.account_id,
                envelope_id=envelope_id
            )
            
            # Unterzeichner-Status holen
            recipients = envelopes_api.list_recipients(
                account_id=self.config.account_id,
                envelope_id=envelope_id
            )
            
            signers_status = []
            for signer in recipients.signers or []:
                signers_status.append({
                    'email': signer.email,
                    'name': signer.name,
                    'status': signer.status,
                    'signed_at': signer.signed_date_time,
                })
            
            # Status mappen
            status_map = {
                'created': SignatureStatus.CREATED,
                'sent': SignatureStatus.SENT,
                'delivered': SignatureStatus.DELIVERED,
                'signed': SignatureStatus.SIGNED,
                'completed': SignatureStatus.COMPLETED,
                'declined': SignatureStatus.DECLINED,
                'voided': SignatureStatus.VOIDED,
            }
            
            status = status_map.get(envelope.status, SignatureStatus.CREATED)
            
            return SignatureResult(
                envelope_id=envelope_id,
                status=status,
                created_at=datetime.fromisoformat(envelope.created_date_time.replace('Z', '+00:00')) if envelope.created_date_time else datetime.now(),
                sent_at=datetime.fromisoformat(envelope.sent_date_time.replace('Z', '+00:00')) if envelope.sent_date_time else None,
                completed_at=datetime.fromisoformat(envelope.completed_date_time.replace('Z', '+00:00')) if envelope.completed_date_time else None,
                signers_status=signers_status
            )
            
        except ApiException as e:
            return SignatureResult(
                envelope_id=envelope_id,
                status=SignatureStatus.CREATED,
                created_at=datetime.now(),
                error=f"DocuSign API Fehler: {e.body}"
            )
    
    def download_signed_document(self, envelope_id: str) -> Optional[bytes]:
        """
        Lädt das unterschriebene Dokument herunter
        """
        try:
            envelopes_api = EnvelopesApi(self.api_client)
            
            # Combined Document (alle Dokumente zusammengeführt)
            document = envelopes_api.get_document(
                account_id=self.config.account_id,
                envelope_id=envelope_id,
                document_id="combined"
            )
            
            return document
            
        except ApiException as e:
            print(f"Fehler beim Download: {e.body}")
            return None
    
    def void_envelope(self, envelope_id: str, reason: str = "Storniert") -> bool:
        """
        Storniert einen Envelope
        """
        try:
            from docusign_esign import Envelope
            
            envelopes_api = EnvelopesApi(self.api_client)
            
            envelope = Envelope(
                status="voided",
                voided_reason=reason
            )
            
            envelopes_api.update(
                account_id=self.config.account_id,
                envelope_id=envelope_id,
                envelope=envelope
            )
            
            return True
            
        except ApiException:
            return False
    
    def resend_envelope(self, envelope_id: str) -> bool:
        """
        Sendet Erinnerungs-E-Mail
        """
        try:
            envelopes_api = EnvelopesApi(self.api_client)
            
            envelopes_api.update_recipients(
                account_id=self.config.account_id,
                envelope_id=envelope_id,
                recipients=Recipients(signers=[]),
                resend_envelope="true"
            )
            
            return True
            
        except ApiException:
            return False


# ============================================
# Einfacher Signature Manager (ohne DocuSign)
# ============================================

class SimpleSignatureManager:
    """
    Einfache Unterschriften-Verwaltung ohne DocuSign
    Verwendet Zeitstempel und Hashes als "Signatur"
    """
    
    def __init__(self, storage_path: str = "./signatures"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
    
    def create_signature_request(
        self,
        document_bytes: bytes,
        document_name: str,
        signers: List[Dict[str, str]]
    ) -> str:
        """
        Erstellt eine einfache Signatur-Anfrage
        Returns: Request-ID
        """
        import hashlib
        import secrets
        
        request_id = secrets.token_urlsafe(16)
        
        # Dokument-Hash
        doc_hash = hashlib.sha256(document_bytes).hexdigest()
        
        # Request speichern
        request_data = {
            'id': request_id,
            'document_name': document_name,
            'document_hash': doc_hash,
            'signers': signers,
            'signatures': [],
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
        }
        
        # Dokument speichern
        doc_path = os.path.join(self.storage_path, f"{request_id}_document.pdf")
        with open(doc_path, 'wb') as f:
            f.write(document_bytes)
        
        # Request-Daten speichern
        request_path = os.path.join(self.storage_path, f"{request_id}_request.json")
        with open(request_path, 'w') as f:
            json.dump(request_data, f)
        
        return request_id
    
    def sign_document(
        self,
        request_id: str,
        signer_email: str,
        signature_data: str,  # Base64 PNG der Unterschrift
        ip_address: str = ""
    ) -> bool:
        """
        Fügt eine Unterschrift hinzu
        """
        request_path = os.path.join(self.storage_path, f"{request_id}_request.json")
        
        if not os.path.exists(request_path):
            return False
        
        with open(request_path, 'r') as f:
            request_data = json.load(f)
        
        # Prüfen ob Signer berechtigt
        signer = next((s for s in request_data['signers'] if s['email'] == signer_email), None)
        if not signer:
            return False
        
        # Prüfen ob bereits unterschrieben
        existing = next((s for s in request_data['signatures'] if s['email'] == signer_email), None)
        if existing:
            return False
        
        # Signatur hinzufügen
        import hashlib
        
        signature_hash = hashlib.sha256(
            f"{signer_email}{datetime.now().isoformat()}{ip_address}".encode()
        ).hexdigest()
        
        request_data['signatures'].append({
            'email': signer_email,
            'name': signer.get('name', ''),
            'signature_data': signature_data,
            'signature_hash': signature_hash,
            'signed_at': datetime.now().isoformat(),
            'ip_address': ip_address,
        })
        
        # Status aktualisieren
        if len(request_data['signatures']) == len(request_data['signers']):
            request_data['status'] = 'completed'
            request_data['completed_at'] = datetime.now().isoformat()
        
        with open(request_path, 'w') as f:
            json.dump(request_data, f)
        
        return True
    
    def get_request_status(self, request_id: str) -> Optional[Dict]:
        """
        Holt den Status einer Anfrage
        """
        request_path = os.path.join(self.storage_path, f"{request_id}_request.json")
        
        if not os.path.exists(request_path):
            return None
        
        with open(request_path, 'r') as f:
            return json.load(f)
    
    def generate_signed_pdf(self, request_id: str) -> Optional[bytes]:
        """
        Generiert PDF mit eingebetteten Unterschriften
        """
        # Dies würde ReportLab oder PyPDF verwenden
        # um die Unterschriften in das Dokument einzufügen
        pass


if __name__ == "__main__":
    print(f"DocuSign SDK verfügbar: {HAS_DOCUSIGN}")
