"""
E-Mail-Engine
Versendet E-Mails über SMTP oder APIs (SendGrid, Microsoft Graph, Gmail)
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib

from jinja2 import Environment, BaseLoader, FileSystemLoader


class EmailProvider(str, Enum):
    SMTP = "smtp"
    SENDGRID = "sendgrid"
    MICROSOFT_GRAPH = "microsoft_graph"
    GMAIL_API = "gmail_api"


class EmailStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


@dataclass
class EmailAttachment:
    """E-Mail-Anhang"""
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"
    
    @classmethod
    def from_file(cls, filepath: Union[str, Path]) -> "EmailAttachment":
        """Erstellt Attachment aus Datei"""
        filepath = Path(filepath)
        with open(filepath, 'rb') as f:
            content = f.read()
        
        # Content-Type bestimmen
        suffix = filepath.suffix.lower()
        content_types = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.txt': 'text/plain',
            '.html': 'text/html',
            '.csv': 'text/csv',
            '.zip': 'application/zip',
        }
        
        return cls(
            filename=filepath.name,
            content=content,
            content_type=content_types.get(suffix, 'application/octet-stream')
        )


@dataclass
class EmailMessage:
    """E-Mail-Nachricht"""
    to: List[str]
    subject: str
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    cc: List[str] = field(default_factory=list)
    bcc: List[str] = field(default_factory=list)
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    attachments: List[EmailAttachment] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)
    
    # Tracking
    message_id: Optional[str] = None
    status: EmailStatus = EmailStatus.PENDING
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def add_attachment(self, attachment: EmailAttachment):
        """Fügt Anhang hinzu"""
        self.attachments.append(attachment)
    
    def add_attachment_from_file(self, filepath: Union[str, Path]):
        """Fügt Anhang aus Datei hinzu"""
        self.attachments.append(EmailAttachment.from_file(filepath))
    
    def add_attachment_from_bytes(self, filename: str, content: bytes, content_type: str = "application/octet-stream"):
        """Fügt Anhang aus Bytes hinzu"""
        self.attachments.append(EmailAttachment(filename, content, content_type))


@dataclass
class SMTPConfig:
    """SMTP-Konfiguration"""
    host: str
    port: int = 587
    username: Optional[str] = None
    password: Optional[str] = None
    use_tls: bool = True
    use_ssl: bool = False
    timeout: int = 30
    
    # Absender-Defaults
    default_from_email: Optional[str] = None
    default_from_name: Optional[str] = None


@dataclass
class SendGridConfig:
    """SendGrid-Konfiguration"""
    api_key: str
    default_from_email: Optional[str] = None
    default_from_name: Optional[str] = None


@dataclass
class EmailLog:
    """E-Mail-Log-Eintrag"""
    id: str
    message_id: Optional[str]
    provider: EmailProvider
    to: List[str]
    cc: List[str]
    bcc: List[str]
    subject: str
    status: EmailStatus
    sent_at: Optional[datetime]
    error_message: Optional[str]
    attachment_count: int
    content_hash: str  # Hash des Inhalts für Audit
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'message_id': self.message_id,
            'provider': self.provider.value,
            'to': self.to,
            'cc': self.cc,
            'bcc': self.bcc,
            'subject': self.subject,
            'status': self.status.value,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'error_message': self.error_message,
            'attachment_count': self.attachment_count,
            'content_hash': self.content_hash,
            'metadata': self.metadata,
        }


class EmailEngine:
    """Haupt-Engine für E-Mail-Versand"""
    
    def __init__(self, template_dir: Optional[str] = None):
        self.template_dir = Path(template_dir) if template_dir else Path("templates/email")
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.template_dir)) if self.template_dir.exists() else BaseLoader()
        )
        self._setup_jinja_filters()
        
        self.smtp_config: Optional[SMTPConfig] = None
        self.sendgrid_config: Optional[SendGridConfig] = None
        
        self.logs: List[EmailLog] = []
    
    def _setup_jinja_filters(self):
        """Registriert Jinja2-Filter"""
        
        def format_date(value, format="%d.%m.%Y"):
            if isinstance(value, str):
                try:
                    value = datetime.fromisoformat(value)
                except:
                    return value
            if isinstance(value, datetime):
                return value.strftime(format)
            return value
        
        self.jinja_env.filters['date'] = format_date
    
    def configure_smtp(self, config: SMTPConfig):
        """Konfiguriert SMTP"""
        self.smtp_config = config
    
    def configure_sendgrid(self, config: SendGridConfig):
        """Konfiguriert SendGrid"""
        self.sendgrid_config = config
    
    # ========================================
    # Template-Rendering
    # ========================================
    
    def render_template(self, template_name: str, data: Dict[str, Any]) -> str:
        """Rendert ein E-Mail-Template"""
        template = self.jinja_env.get_template(template_name)
        return template.render(**data)
    
    def render_template_string(self, template_str: str, data: Dict[str, Any]) -> str:
        """Rendert einen Template-String"""
        template = self.jinja_env.from_string(template_str)
        return template.render(**data)
    
    def create_message_from_template(
        self,
        to: Union[str, List[str]],
        template_name: str,
        data: Dict[str, Any],
        subject_template: Optional[str] = None,
        **kwargs
    ) -> EmailMessage:
        """Erstellt E-Mail aus Template"""
        
        if isinstance(to, str):
            to = [to]
        
        # Body rendern
        body_html = self.render_template(template_name, data)
        
        # Subject rendern
        subject = subject_template or data.get('subject', 'Keine Betreffzeile')
        subject = self.render_template_string(subject, data)
        
        return EmailMessage(
            to=to,
            subject=subject,
            body_html=body_html,
            **kwargs
        )
    
    # ========================================
    # SMTP-Versand
    # ========================================
    
    def send_smtp(self, message: EmailMessage) -> EmailLog:
        """Versendet E-Mail via SMTP"""
        
        if not self.smtp_config:
            raise ValueError("SMTP nicht konfiguriert. Rufen Sie configure_smtp() auf.")
        
        config = self.smtp_config
        
        # MIME-Message erstellen
        msg = MIMEMultipart('mixed')
        msg['Subject'] = message.subject
        msg['From'] = f"{message.from_name or config.default_from_name} <{message.from_email or config.default_from_email}>"
        msg['To'] = ', '.join(message.to)
        
        if message.cc:
            msg['Cc'] = ', '.join(message.cc)
        if message.reply_to:
            msg['Reply-To'] = message.reply_to
        
        # Custom Headers
        for key, value in message.headers.items():
            msg[key] = value
        
        # Body
        body_part = MIMEMultipart('alternative')
        
        if message.body_text:
            body_part.attach(MIMEText(message.body_text, 'plain', 'utf-8'))
        
        if message.body_html:
            body_part.attach(MIMEText(message.body_html, 'html', 'utf-8'))
        elif message.body_text:
            # Nur Text, kein HTML
            pass
        else:
            body_part.attach(MIMEText("", 'plain', 'utf-8'))
        
        msg.attach(body_part)
        
        # Attachments
        for attachment in message.attachments:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.content)
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="{attachment.filename}"'
            )
            part.add_header('Content-Type', attachment.content_type)
            msg.attach(part)
        
        # Senden
        log_id = hashlib.md5(f"{datetime.now().isoformat()}{message.to}".encode()).hexdigest()[:16]
        content_hash = hashlib.sha256((message.body_text or message.body_html or "").encode()).hexdigest()[:16]
        
        try:
            if config.use_ssl:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(config.host, config.port, context=context, timeout=config.timeout)
            else:
                server = smtplib.SMTP(config.host, config.port, timeout=config.timeout)
                if config.use_tls:
                    server.starttls()
            
            if config.username and config.password:
                server.login(config.username, config.password)
            
            all_recipients = message.to + message.cc + message.bcc
            server.sendmail(
                message.from_email or config.default_from_email,
                all_recipients,
                msg.as_string()
            )
            server.quit()
            
            message.status = EmailStatus.SENT
            message.sent_at = datetime.now()
            message.message_id = msg.get('Message-ID')
            
            log = EmailLog(
                id=log_id,
                message_id=message.message_id,
                provider=EmailProvider.SMTP,
                to=message.to,
                cc=message.cc,
                bcc=message.bcc,
                subject=message.subject,
                status=EmailStatus.SENT,
                sent_at=datetime.now(),
                error_message=None,
                attachment_count=len(message.attachments),
                content_hash=content_hash,
            )
            
        except Exception as e:
            message.status = EmailStatus.FAILED
            message.error_message = str(e)
            
            log = EmailLog(
                id=log_id,
                message_id=None,
                provider=EmailProvider.SMTP,
                to=message.to,
                cc=message.cc,
                bcc=message.bcc,
                subject=message.subject,
                status=EmailStatus.FAILED,
                sent_at=None,
                error_message=str(e),
                attachment_count=len(message.attachments),
                content_hash=content_hash,
            )
        
        self.logs.append(log)
        return log
    
    # ========================================
    # SendGrid-Versand
    # ========================================
    
    def send_sendgrid(self, message: EmailMessage) -> EmailLog:
        """Versendet E-Mail via SendGrid"""
        
        if not self.sendgrid_config:
            raise ValueError("SendGrid nicht konfiguriert. Rufen Sie configure_sendgrid() auf.")
        
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
        except ImportError:
            raise ImportError("sendgrid ist nicht installiert: pip install sendgrid")
        
        config = self.sendgrid_config
        
        # Mail erstellen
        mail = Mail(
            from_email=(message.from_email or config.default_from_email, message.from_name or config.default_from_name),
            to_emails=message.to,
            subject=message.subject,
            html_content=message.body_html,
            plain_text_content=message.body_text,
        )
        
        # CC/BCC
        for cc in message.cc:
            mail.add_cc(cc)
        for bcc in message.bcc:
            mail.add_bcc(bcc)
        
        # Attachments
        for attachment in message.attachments:
            import base64
            encoded = base64.b64encode(attachment.content).decode()
            mail.add_attachment(Attachment(
                FileContent(encoded),
                FileName(attachment.filename),
                FileType(attachment.content_type),
                Disposition('attachment')
            ))
        
        log_id = hashlib.md5(f"{datetime.now().isoformat()}{message.to}".encode()).hexdigest()[:16]
        content_hash = hashlib.sha256((message.body_text or message.body_html or "").encode()).hexdigest()[:16]
        
        try:
            sg = SendGridAPIClient(config.api_key)
            response = sg.send(mail)
            
            message.status = EmailStatus.SENT
            message.sent_at = datetime.now()
            message.message_id = response.headers.get('X-Message-Id')
            
            log = EmailLog(
                id=log_id,
                message_id=message.message_id,
                provider=EmailProvider.SENDGRID,
                to=message.to,
                cc=message.cc,
                bcc=message.bcc,
                subject=message.subject,
                status=EmailStatus.SENT,
                sent_at=datetime.now(),
                error_message=None,
                attachment_count=len(message.attachments),
                content_hash=content_hash,
                metadata={'status_code': response.status_code}
            )
            
        except Exception as e:
            message.status = EmailStatus.FAILED
            message.error_message = str(e)
            
            log = EmailLog(
                id=log_id,
                message_id=None,
                provider=EmailProvider.SENDGRID,
                to=message.to,
                cc=message.cc,
                bcc=message.bcc,
                subject=message.subject,
                status=EmailStatus.FAILED,
                sent_at=None,
                error_message=str(e),
                attachment_count=len(message.attachments),
                content_hash=content_hash,
            )
        
        self.logs.append(log)
        return log
    
    # ========================================
    # Mailto-Link (für Browser-basiertes Senden)
    # ========================================
    
    def create_mailto_link(
        self,
        to: Union[str, List[str]],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> str:
        """Erstellt einen mailto-Link"""
        import urllib.parse
        
        if isinstance(to, list):
            to = ','.join(to)
        
        params = {
            'subject': subject,
            'body': body,
        }
        
        if cc:
            params['cc'] = ','.join(cc)
        if bcc:
            params['bcc'] = ','.join(bcc)
        
        query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        return f"mailto:{to}?{query}"
    
    # ========================================
    # Hilfsfunktionen
    # ========================================
    
    def send(self, message: EmailMessage, provider: Optional[EmailProvider] = None) -> EmailLog:
        """Versendet E-Mail über konfigurierten Provider"""
        
        if provider == EmailProvider.SENDGRID or (provider is None and self.sendgrid_config):
            return self.send_sendgrid(message)
        elif provider == EmailProvider.SMTP or (provider is None and self.smtp_config):
            return self.send_smtp(message)
        else:
            raise ValueError("Kein E-Mail-Provider konfiguriert")
    
    def get_logs(self, limit: int = 100) -> List[EmailLog]:
        """Gibt die letzten Logs zurück"""
        return self.logs[-limit:]
    
    def get_logs_by_status(self, status: EmailStatus) -> List[EmailLog]:
        """Filtert Logs nach Status"""
        return [log for log in self.logs if log.status == status]


# ============================================
# Standard E-Mail-Templates
# ============================================

EMAIL_TEMPLATE_CONFIRMATION = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #b45309; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; background: #f9f9f9; }
        .footer { padding: 15px; text-align: center; font-size: 12px; color: #666; }
        .button { display: inline-block; background: #b45309; color: white; padding: 12px 24px; 
                  text-decoration: none; border-radius: 4px; margin: 15px 0; }
        .field { margin: 10px 0; }
        .field-label { font-weight: bold; color: #555; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ kanzlei_name | default('RA-RHM Rechtsanwaltskanzlei') }}</h1>
        </div>
        <div class="content">
            <h2>{{ anrede | default('Sehr geehrte Damen und Herren') }},</h2>
            
            <p>vielen Dank für Ihre Anfrage. Wir haben Ihre Angaben erhalten und werden uns 
            zeitnah bei Ihnen melden.</p>
            
            <h3>Ihre Angaben im Überblick:</h3>
            
            {% for field in fields %}
            <div class="field">
                <span class="field-label">{{ field.label }}:</span>
                <span>{{ field.value }}</span>
            </div>
            {% endfor %}
            
            {% if vorgangsnummer %}
            <p><strong>Ihre Vorgangsnummer:</strong> {{ vorgangsnummer }}</p>
            {% endif %}
            
            <p>Bei Rückfragen stehen wir Ihnen gerne zur Verfügung.</p>
            
            <p>Mit freundlichen Grüßen<br>
            {{ kanzlei_name | default('RA-RHM Rechtsanwaltskanzlei') }}</p>
        </div>
        <div class="footer">
            <p>{{ kanzlei_name | default('RA-RHM Rechtsanwaltskanzlei') }}<br>
            Tel: {{ kanzlei_telefon | default('04331 732970') }} | 
            E-Mail: {{ kanzlei_email | default('info@ra-rhm.de') }}</p>
        </div>
    </div>
</body>
</html>
"""

EMAIL_TEMPLATE_INTERNAL = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .alert { background: #fef3c7; border-left: 4px solid #b45309; padding: 15px; margin: 15px 0; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background: #f5f5f5; }
        .priority-high { color: #dc2626; font-weight: bold; }
        .priority-normal { color: #059669; }
    </style>
</head>
<body>
    <div class="alert">
        <strong>Neue Anfrage eingegangen</strong><br>
        Eingang: {{ datum }} {{ uhrzeit }}
    </div>
    
    <h2>{{ formular_name }}</h2>
    
    {% if prioritaet == 'hoch' %}
    <p class="priority-high">⚠️ HOHE PRIORITÄT</p>
    {% endif %}
    
    <table>
        <tr>
            <th colspan="2">Kontaktdaten</th>
        </tr>
        {% if vorname or nachname %}
        <tr>
            <td><strong>Name</strong></td>
            <td>{{ vorname }} {{ nachname }}</td>
        </tr>
        {% endif %}
        {% if email %}
        <tr>
            <td><strong>E-Mail</strong></td>
            <td><a href="mailto:{{ email }}">{{ email }}</a></td>
        </tr>
        {% endif %}
        {% if telefon %}
        <tr>
            <td><strong>Telefon</strong></td>
            <td>{{ telefon }}</td>
        </tr>
        {% endif %}
    </table>
    
    <h3>Alle Angaben:</h3>
    <table>
        {% for field in fields %}
        <tr>
            <td><strong>{{ field.label }}</strong></td>
            <td>{{ field.value }}</td>
        </tr>
        {% endfor %}
    </table>
    
    {% if attachments %}
    <h3>Anhänge:</h3>
    <ul>
        {% for attachment in attachments %}
        <li>{{ attachment.filename }}</li>
        {% endfor %}
    </ul>
    {% endif %}
    
    <p>---<br>
    Automatisch generiert vom Formular-System</p>
</body>
</html>
"""


if __name__ == "__main__":
    # Test
    engine = EmailEngine()
    
    # Mailto-Link testen
    link = engine.create_mailto_link(
        to="test@example.com",
        subject="Test-Betreff",
        body="Test-Nachricht"
    )
    print("Mailto-Link:", link)
