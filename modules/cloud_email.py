"""
E-Mail-Integration für Microsoft Graph und Gmail API
Erweitert die email_engine.py um Cloud-Provider
"""

import os
import base64
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

# Microsoft Graph
try:
    from msal import ConfidentialClientApplication
    import requests
    HAS_MSAL = True
except ImportError:
    HAS_MSAL = False

# Google Gmail
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email import encoders
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False


@dataclass
class MicrosoftGraphConfig:
    """Microsoft Graph API Konfiguration"""
    tenant_id: str
    client_id: str
    client_secret: str
    sender_email: str
    sender_name: Optional[str] = None
    
    # OAuth Scopes
    scopes: List[str] = None
    
    def __post_init__(self):
        if self.scopes is None:
            self.scopes = ["https://graph.microsoft.com/.default"]


@dataclass
class GmailConfig:
    """Gmail API Konfiguration"""
    service_account_file: Optional[str] = None
    service_account_info: Optional[Dict] = None
    delegated_user: str = ""  # E-Mail des Benutzers, als der gesendet wird
    
    # OAuth Scopes
    scopes: List[str] = None
    
    def __post_init__(self):
        if self.scopes is None:
            self.scopes = ["https://www.googleapis.com/auth/gmail.send"]


class MicrosoftGraphMailer:
    """
    E-Mail-Versand über Microsoft Graph API
    Für Microsoft 365 / Exchange Online
    """
    
    def __init__(self, config: MicrosoftGraphConfig):
        if not HAS_MSAL:
            raise ImportError("msal ist nicht installiert: pip install msal requests")
        
        self.config = config
        self.app = ConfidentialClientApplication(
            client_id=config.client_id,
            client_credential=config.client_secret,
            authority=f"https://login.microsoftonline.com/{config.tenant_id}"
        )
        self._token = None
        self._token_expires = None
    
    def _get_token(self) -> str:
        """Holt oder erneuert Access Token"""
        if self._token and self._token_expires and datetime.now() < self._token_expires:
            return self._token
        
        result = self.app.acquire_token_for_client(scopes=self.config.scopes)
        
        if "access_token" not in result:
            error = result.get("error_description", result.get("error", "Unbekannter Fehler"))
            raise Exception(f"Token-Abruf fehlgeschlagen: {error}")
        
        self._token = result["access_token"]
        # Token ist normalerweise 1 Stunde gültig
        from datetime import timedelta
        self._token_expires = datetime.now() + timedelta(minutes=55)
        
        return self._token
    
    def send_mail(
        self,
        to: List[str],
        subject: str,
        body_html: Optional[str] = None,
        body_text: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict]] = None,
        importance: str = "normal",
        save_to_sent: bool = True
    ) -> Dict[str, Any]:
        """
        Sendet eine E-Mail über Microsoft Graph
        
        Args:
            to: Liste von Empfänger-E-Mails
            subject: Betreff
            body_html: HTML-Body (bevorzugt)
            body_text: Text-Body (Fallback)
            cc: CC-Empfänger
            bcc: BCC-Empfänger
            attachments: Liste von Anhängen [{name, content_bytes, content_type}]
            importance: "low", "normal", "high"
            save_to_sent: Im "Gesendet"-Ordner speichern
        
        Returns:
            Dict mit Status und Message-ID
        """
        token = self._get_token()
        
        # Message aufbauen
        message = {
            "subject": subject,
            "body": {
                "contentType": "HTML" if body_html else "Text",
                "content": body_html or body_text or ""
            },
            "toRecipients": [{"emailAddress": {"address": addr}} for addr in to],
            "importance": importance,
        }
        
        if cc:
            message["ccRecipients"] = [{"emailAddress": {"address": addr}} for addr in cc]
        
        if bcc:
            message["bccRecipients"] = [{"emailAddress": {"address": addr}} for addr in bcc]
        
        if attachments:
            message["attachments"] = []
            for att in attachments:
                content = att.get("content_bytes", b"")
                if isinstance(content, bytes):
                    content = base64.b64encode(content).decode()
                
                message["attachments"].append({
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": att.get("name", "attachment"),
                    "contentType": att.get("content_type", "application/octet-stream"),
                    "contentBytes": content
                })
        
        # Request
        url = f"https://graph.microsoft.com/v1.0/users/{self.config.sender_email}/sendMail"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "message": message,
            "saveToSentItems": str(save_to_sent).lower()
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 202:
            return {
                "success": True,
                "status_code": 202,
                "message": "E-Mail erfolgreich gesendet"
            }
        else:
            error_data = response.json() if response.content else {}
            return {
                "success": False,
                "status_code": response.status_code,
                "error": error_data.get("error", {}).get("message", response.text)
            }
    
    def send_mail_mime(
        self,
        mime_content: bytes
    ) -> Dict[str, Any]:
        """
        Sendet eine MIME-formatierte E-Mail
        Nützlich für komplexe E-Mails oder S/MIME
        """
        token = self._get_token()
        
        url = f"https://graph.microsoft.com/v1.0/users/{self.config.sender_email}/sendMail"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "text/plain"
        }
        
        # Base64 kodieren
        encoded = base64.b64encode(mime_content).decode()
        
        response = requests.post(url, headers=headers, data=encoded)
        
        return {
            "success": response.status_code == 202,
            "status_code": response.status_code
        }


class GmailMailer:
    """
    E-Mail-Versand über Gmail API
    Für Google Workspace
    """
    
    def __init__(self, config: GmailConfig):
        if not HAS_GOOGLE:
            raise ImportError(
                "Google-Bibliotheken nicht installiert: "
                "pip install google-auth google-auth-oauthlib google-api-python-client"
            )
        
        self.config = config
        self.service = self._build_service()
    
    def _build_service(self):
        """Erstellt den Gmail API Service"""
        if self.config.service_account_file:
            credentials = service_account.Credentials.from_service_account_file(
                self.config.service_account_file,
                scopes=self.config.scopes
            )
        elif self.config.service_account_info:
            credentials = service_account.Credentials.from_service_account_info(
                self.config.service_account_info,
                scopes=self.config.scopes
            )
        else:
            raise ValueError("service_account_file oder service_account_info erforderlich")
        
        # Delegation für Workspace
        if self.config.delegated_user:
            credentials = credentials.with_subject(self.config.delegated_user)
        
        return build('gmail', 'v1', credentials=credentials)
    
    def send_mail(
        self,
        to: List[str],
        subject: str,
        body_html: Optional[str] = None,
        body_text: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict]] = None,
        reply_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sendet eine E-Mail über Gmail API
        
        Args:
            to: Empfänger
            subject: Betreff
            body_html: HTML-Body
            body_text: Text-Body
            cc: CC-Empfänger
            bcc: BCC-Empfänger
            attachments: Anhänge [{name, content_bytes, content_type}]
            reply_to: Reply-To Header
        
        Returns:
            Dict mit Status und Message-ID
        """
        # MIME Message erstellen
        if attachments:
            message = MIMEMultipart('mixed')
            
            # Body
            body_part = MIMEMultipart('alternative')
            if body_text:
                body_part.attach(MIMEText(body_text, 'plain', 'utf-8'))
            if body_html:
                body_part.attach(MIMEText(body_html, 'html', 'utf-8'))
            message.attach(body_part)
            
            # Attachments
            for att in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(att.get('content_bytes', b''))
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{att.get("name", "attachment")}"'
                )
                message.attach(part)
        else:
            if body_html:
                message = MIMEMultipart('alternative')
                if body_text:
                    message.attach(MIMEText(body_text, 'plain', 'utf-8'))
                message.attach(MIMEText(body_html, 'html', 'utf-8'))
            else:
                message = MIMEText(body_text or '', 'plain', 'utf-8')
        
        # Header
        message['Subject'] = subject
        message['To'] = ', '.join(to)
        message['From'] = self.config.delegated_user
        
        if cc:
            message['Cc'] = ', '.join(cc)
        if reply_to:
            message['Reply-To'] = reply_to
        
        # Base64 URL-safe encoding
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        try:
            sent_message = self.service.users().messages().send(
                userId='me',
                body={'raw': raw}
            ).execute()
            
            return {
                "success": True,
                "message_id": sent_message.get('id'),
                "thread_id": sent_message.get('threadId')
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# ============================================
# Unified Interface
# ============================================

class CloudMailer:
    """
    Einheitliche Schnittstelle für Cloud-E-Mail-Provider
    """
    
    def __init__(
        self,
        provider: str,
        config: Dict[str, Any]
    ):
        """
        Args:
            provider: "microsoft" oder "google"
            config: Provider-spezifische Konfiguration
        """
        self.provider = provider
        
        if provider == "microsoft":
            ms_config = MicrosoftGraphConfig(**config)
            self.mailer = MicrosoftGraphMailer(ms_config)
        elif provider == "google":
            gmail_config = GmailConfig(**config)
            self.mailer = GmailMailer(gmail_config)
        else:
            raise ValueError(f"Unbekannter Provider: {provider}")
    
    def send(
        self,
        to: List[str],
        subject: str,
        body_html: Optional[str] = None,
        body_text: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Sendet eine E-Mail"""
        return self.mailer.send_mail(
            to=to,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            **kwargs
        )


if __name__ == "__main__":
    print(f"Microsoft Graph verfügbar: {HAS_MSAL}")
    print(f"Gmail API verfügbar: {HAS_GOOGLE}")
