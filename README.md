# ⚖️ RA-RHM Fragebogen-System

Streamlit-basierte Web-App für Mandanten-Fragebögen.

## 🚀 Deployment auf Streamlit Cloud

### Schritt 1: GitHub Repository
Laden Sie alle Dateien in ein neues GitHub Repository hoch.

### Schritt 2: Streamlit Cloud
1. Öffnen Sie [share.streamlit.io](https://share.streamlit.io)
2. Melden Sie sich mit GitHub an
3. "New app" → Repository wählen → `app.py` als Main file
4. **Deploy!**

### Schritt 3: Secrets konfigurieren (WICHTIG!)

**Nach dem Deployment müssen Sie die Secrets konfigurieren:**

1. Gehen Sie zu [share.streamlit.io](https://share.streamlit.io)
2. Klicken Sie auf Ihre deployed App
3. Klicken Sie auf ⚙️ **Settings** (oben rechts)
4. Wählen Sie **Secrets** im linken Menü
5. Fügen Sie folgendes ein:

```toml
# WICHTIG: Ersetzen Sie die URL mit Ihrer echten App-URL!
APP_URL = "https://IHRE-APP-NAME.streamlit.app"

# Optional: OpenAI API Key (falls Sie diesen bereits haben)
OPENAI_API_KEY = "sk-..."
```

6. Klicken Sie auf **Save**

**Hinweis:** Die `APP_URL` muss Ihre echte Streamlit-App-URL sein. Diese finden Sie in der Adressleiste Ihres Browsers, wenn die App geöffnet ist.

---

## 📋 Funktionen

- ✅ **29 Fragebögen** aus FluentForms-Import
- ✅ **Einladungslinks** mit 7-Tage-Gültigkeit
- ✅ **E-Mail-Routing** an konfigurierbare Mitarbeiter
- ✅ **Dokumentengenerierung** mit Download
- ✅ **Conditional Logic** (dynamische Felder)

## 📁 Projektstruktur

```
├── app.py                              # Hauptanwendung
├── requirements.txt                    # Python-Abhängigkeiten
├── README.md                           # Diese Datei
├── secrets.toml.example                # Beispiel für Secrets
├── fluentform-export-*.json            # Formulardaten (29 Formulare)
├── .gitignore                          # Git-Ignore
└── .streamlit/
    └── config.toml                     # Theme-Konfiguration
```

## 🔐 Secrets erklärt

| Secret | Beschreibung | Beispiel |
|--------|--------------|----------|
| `APP_URL` | Die URL Ihrer Streamlit-App. Wird für Einladungslinks benötigt. | `https://ra-rhm-fragebogen.streamlit.app` |
| `OPENAI_API_KEY` | Optional. Falls Sie KI-Funktionen nutzen möchten. | `sk-...` |

### Wo finde ich meine App-URL?

Nach dem Deployment zeigt Streamlit Cloud Ihre App-URL an. Sie sieht etwa so aus:
```
https://[ihr-github-username]-[repo-name]-[random].streamlit.app
```

Kopieren Sie diese URL und fügen Sie sie als `APP_URL` in die Secrets ein.

---

## 📖 Verwendung

### Für Administratoren

1. **Formulare laden**: Dashboard → "Formulare aus JSON laden"
2. **Einladungslink erstellen**: Formular → 🔗 Einladung → Link generieren
3. **Mitarbeiter verwalten**: ⚙️ Einstellungen

### Für Mandanten

1. Einladungslink öffnen
2. Formular ausfüllen
3. Absenden
4. Dokument herunterladen oder per E-Mail senden

---

## 🔧 Lokale Entwicklung

```bash
# Repository klonen
git clone https://github.com/IHR-USERNAME/ra-rhm-fragebogen.git
cd ra-rhm-fragebogen

# Dependencies installieren
pip install -r requirements.txt

# Secrets lokal konfigurieren
mkdir -p .streamlit
cp secrets.toml.example .streamlit/secrets.toml
# Dann secrets.toml bearbeiten

# App starten
streamlit run app.py
```

---

## 📞 Support

**RA-RHM Rechtsanwaltskanzlei**
- 📧 info@ra-rhm.de
- 📞 04331 732970

---

© 2025 RA-RHM Rechtsanwaltskanzlei
