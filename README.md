# ⚖️ RA-RHM Formular-System

Professionelles Fragebogen-Management-System für Rechtsanwaltskanzleien.

## 🚀 Features

### Formular-Editor
- ✅ **21 Feldtypen** (Text, Dropdown, Datum, Datei-Upload, Signatur, etc.)
- ✅ **Mehrseitiger Wizard** mit Fortschrittsanzeige
- ✅ **Bedingte Logik** (Felder ein-/ausblenden basierend auf Antworten)
- ✅ **Berechnungen** (Summe, Durchschnitt, Formeln)
- ✅ **Wiederholbare Abschnitte** (z.B. mehrere Kinder, Positionen)
- ✅ **Validierung** (Pflichtfelder, Regex, Min/Max)
- ✅ **Autosave / Entwürfe**
- ✅ **Review-Seite** vor Absenden

### Dokumenten-Generierung
- ✅ **DOCX aus Templates** (mit Jinja2-Syntax)
- ✅ **PDF aus HTML** (WeasyPrint)
- ✅ **PDF programmatisch** (ReportLab)
- ✅ **PDF-Formulare befüllen** (AcroForm)
- ✅ **PDF Merge/Split/Verschlüsselung**
- ✅ **DOCX→PDF Konvertierung** (LibreOffice)

### E-Mail-Versand
- ✅ **SMTP** (Standard)
- ✅ **SendGrid** (Cloud)
- ✅ **Microsoft Graph** (M365)
- ✅ **Gmail API** (Google Workspace)
- ✅ **Templates mit Jinja2**
- ✅ **Anhänge**

### Workflows
- ✅ **Automatische Aktionen** nach Formular-Einreichung
- ✅ **Dokument generieren → E-Mail senden → Archivieren**
- ✅ **Webhooks**
- ✅ **Background Jobs** (Celery)

### Sicherheit
- ✅ **Authentifizierung** mit Rollen (Admin, Editor, Viewer, Mandant)
- ✅ **Mandanten-Einladungslinks** (zeitlich begrenzt)
- ✅ **Virenscan** für Uploads (ClamAV)
- ✅ **Audit-Logging**
- ✅ **Multi-Tenancy** (Grundstruktur)

### Integration
- ✅ **Docusign eSignature** (digitale Unterschriften)
- ✅ **st.secrets** (sichere Konfiguration)
- ✅ **JSON Import/Export**

---

## 📦 Installation

### Minimal-Installation

```bash
# Repository klonen
git clone <repo-url>
cd fragebogen-system

# Virtuelle Umgebung
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Basis-Abhängigkeiten
pip install streamlit pydantic sqlalchemy jinja2 \
            docxtpl python-docx pypdf

# Starten
streamlit run app.py
```

### Vollständige Installation

```bash
# Alle Abhängigkeiten
pip install -r requirements.txt

# System-Pakete für WeasyPrint (Ubuntu)
sudo apt install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0

# LibreOffice für DOCX→PDF
sudo apt install libreoffice

# ClamAV für Virenscan
sudo apt install clamav clamav-daemon
sudo systemctl start clamav-daemon

# Redis für Background Jobs
sudo apt install redis-server
```

---

## 🏃 Starten

### Entwicklung

```bash
streamlit run app.py
```

### Produktion

```bash
# Mit Gunicorn (empfohlen)
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app

# Oder mit Streamlit
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

### Background Worker (optional)

```bash
# Celery Worker
celery -A modules.tasks worker --loglevel=info

# Celery Beat (Scheduled Tasks)
celery -A modules.tasks beat --loglevel=info
```

---

## ⚙️ Konfiguration

### Secrets (.streamlit/secrets.toml)

```toml
[auth]
secret_key = "ihr-geheimer-schlüssel-hier"

[smtp]
host = "smtp.beispiel.de"
port = 587
username = "user@beispiel.de"
password = "passwort"
from_email = "noreply@beispiel.de"

[sendgrid]
api_key = "SG.xxxxx"

[microsoft]
tenant_id = "xxxxx"
client_id = "xxxxx"
client_secret = "xxxxx"
sender_email = "kanzlei@beispiel.de"

[docusign]
integration_key = "xxxxx"
user_id = "xxxxx"
account_id = "xxxxx"
private_key_path = "/path/to/private.pem"

[database]
url = "sqlite:///data/forms.db"
# Produktion: "postgresql://user:pass@host/db"
```

---

## 📁 Projektstruktur

```
fragebogen-system/
├── app.py                    # Streamlit Hauptanwendung
├── requirements.txt          # Python-Abhängigkeiten
├── README.md                 # Diese Datei
│
├── modules/                  # Backend-Module
│   ├── __init__.py
│   ├── form_schema.py        # Pydantic-Modelle
│   ├── document_engine.py    # DOCX/PDF-Generierung
│   ├── email_engine.py       # E-Mail-Versand
│   ├── workflow_engine.py    # Automatisierung
│   ├── database.py           # SQLAlchemy ORM
│   ├── auth.py               # Authentifizierung
│   ├── cloud_email.py        # MS Graph / Gmail
│   ├── docusign.py           # eSignature
│   ├── virus_scanner.py      # ClamAV Integration
│   ├── converter.py          # DOCX→PDF
│   ├── pdf_form_filler.py    # PDF-Formulare
│   ├── tasks.py              # Celery Jobs
│   └── caching.py            # st.cache Wrapper
│
├── templates/                # Dokumenten-Templates
│   ├── docx/
│   │   └── mandantenbogen.docx
│   ├── html/
│   │   └── default.html
│   └── email/
│       ├── confirmation.html
│       └── internal.html
│
├── schemas/                  # JSON-Schemas
│   └── example_form.json
│
├── storage/                  # Uploads & generierte Docs
│   ├── uploads/
│   └── documents/
│
└── .streamlit/
    └── secrets.toml          # Konfiguration (nicht committen!)
```

---

## 🔐 Benutzerrollen

| Rolle | Rechte |
|-------|--------|
| **Admin** | Alles (Formulare, Benutzer, Einstellungen) |
| **Editor** | Formulare erstellen/bearbeiten, Submissions ansehen |
| **Viewer** | Nur lesen, Submissions exportieren |
| **User** | Nur Formulare ausfüllen |
| **Mandant** | Externes Ausfüllen über Einladungslink |

### Demo-Zugänge

| Benutzer | Passwort | Rolle |
|----------|----------|-------|
| admin | admin123 | Admin |
| editor | editor123 | Editor |
| viewer | viewer123 | Viewer |

---

## 📝 Feldtypen

| Typ | Beschreibung |
|-----|--------------|
| `text` | Einzeiliges Textfeld |
| `textarea` | Mehrzeiliges Textfeld |
| `email` | E-Mail mit Validierung |
| `phone` | Telefonnummer |
| `number` | Zahl (mit Min/Max) |
| `date` | Datum |
| `time` | Uhrzeit |
| `datetime` | Datum + Uhrzeit |
| `select` | Dropdown (Einzelauswahl) |
| `multi_select` | Dropdown (Mehrfachauswahl) |
| `radio` | Radio-Buttons |
| `checkbox` | Einzelne Checkbox |
| `checkbox_group` | Checkbox-Gruppe |
| `toggle` | Schalter (An/Aus) |
| `file_upload` | Datei-Upload |
| `signature` | Unterschrift |
| `calculated` | Berechnetes Feld |
| `section` | Abschnitts-Überschrift |
| `info_text` | Info-Box |
| `hidden` | Verstecktes Feld |

---

## 🔄 Workflow-Aktionen

| Aktion | Beschreibung |
|--------|--------------|
| `generate_document` | Dokument aus Template erstellen |
| `send_email` | E-Mail versenden |
| `webhook` | HTTP-Request an externe URL |
| `set_field` | Feldwert setzen |
| `merge_pdf` | PDFs zusammenführen |
| `notify` | Interne Benachrichtigung |
| `archive` | Submission archivieren |

---

## 🧪 API-Beispiele

### Formular programmatisch erstellen

```python
from modules.form_schema import FormSchema, FormField, FormPage, FieldType

form = FormSchema(
    name="kontaktformular",
    title="Kontaktformular",
    pages=[
        FormPage(
            title="Kontakt",
            fields=[
                FormField(type=FieldType.TEXT, label="Name", validation={"required": True}),
                FormField(type=FieldType.EMAIL, label="E-Mail", validation={"required": True}),
                FormField(type=FieldType.TEXTAREA, label="Nachricht"),
            ]
        )
    ]
)
```

### Dokument generieren

```python
from modules.document_engine import DocumentEngine

engine = DocumentEngine()

# DOCX aus Template
docx_bytes = engine.generate_docx_from_template(
    template_path="templates/docx/mandantenbogen.docx",
    data={"vorname": "Max", "nachname": "Mustermann"}
)

# PDF aus HTML
pdf_bytes = engine.generate_pdf_from_html(
    html_content="<h1>Hallo {{ name }}</h1>",
    data={"name": "Max"}
)
```

### E-Mail senden

```python
from modules.email_engine import EmailEngine, EmailMessage, SMTPConfig

engine = EmailEngine()
engine.configure_smtp(SMTPConfig(
    host="smtp.beispiel.de",
    port=587,
    username="user",
    password="pass"
))

message = EmailMessage(
    to=["mandant@beispiel.de"],
    subject="Ihre Anfrage",
    body_html="<p>Vielen Dank!</p>"
)

log = engine.send(message)
```

---

## 🐛 Troubleshooting

### WeasyPrint-Fehler
```bash
# Ubuntu
sudo apt install libpango-1.0-0 libpangocairo-1.0-0

# macOS
brew install pango
```

### LibreOffice-Konvertierung hängt
```bash
# Profile-Verzeichnis löschen
rm -rf ~/.config/libreoffice
```

### ClamAV nicht erreichbar
```bash
sudo systemctl status clamav-daemon
sudo systemctl start clamav-daemon
```

### Celery-Worker startet nicht
```bash
# Redis prüfen
redis-cli ping  # Sollte PONG zurückgeben

# Worker mit Debug-Ausgabe
celery -A modules.tasks worker --loglevel=debug
```

---

## 📄 Lizenz

MIT License - siehe LICENSE Datei

---

## 🤝 Support

Bei Fragen oder Problemen:
- Issue erstellen
- E-Mail an support@ra-rhm.de
