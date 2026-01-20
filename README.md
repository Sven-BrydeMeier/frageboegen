# ⚖️ RA-RHM Fragebogen-System

Ein vollständiges Fragebogen-Management-System für Rechtsanwaltskanzleien, basierend auf Streamlit.

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red)
![License](https://img.shields.io/badge/License-Private-gray)

## ✨ Funktionen

### 📋 Formular-Management
- **29 vorkonfigurierte Fragebögen** aus FluentForms-Import
- **Kategorien**: Notariat, Familienrecht, Arbeitsrecht, Verkehrsrecht, Mietrecht, Zivilrecht
- **Dynamische Felder** mit Conditional Logic (Felder erscheinen basierend auf vorherigen Antworten)
- **Alle Feldtypen**: Text, E-Mail, Telefon, Datum, Dropdown, Radio, Checkbox, Adresse, Datei-Upload

### 🔗 Einladungssystem
- **Einladungslinks** mit 7-Tage-Gültigkeit
- **E-Mail-Einladungen** mit vorgefertigtem Text
- **Mandantenzuordnung** für bessere Nachverfolgung
- **Einladungsverwaltung** mit Status-Übersicht

### 📧 E-Mail-Routing
- **Konfigurierbare Mitarbeiter-E-Mails**
- **Standard-Empfänger** einstellbar
- **Direkter Mailto-Link** nach Formularabsendung

### 📄 Dokumentengenerierung
- **Automatische Dokument-Erstellung** aus Formulardaten
- **Formatiertes Textdokument** mit allen Eingaben
- **Download-Funktion** (.txt)
- **E-Mail-Versand** direkt aus der App

## 🚀 Deployment auf Streamlit Cloud

### Schritt 1: GitHub Repository erstellen

1. Erstellen Sie ein neues Repository auf [github.com](https://github.com)
2. Benennen Sie es z.B. `ra-rhm-fragebogen`

### Schritt 2: Dateien hochladen

Laden Sie alle Dateien aus diesem Ordner hoch:

```
ra-rhm-fragebogen/
├── app.py                                    # Hauptanwendung
├── requirements.txt                          # Dependencies
├── README.md                                 # Diese Datei
├── fluentform-export-forms-29-20-01-2026.json  # Formulardaten
├── .gitignore                                # Git-Ignore
└── .streamlit/
    └── config.toml                           # Streamlit-Konfiguration
```

**Option A: GitHub Web-Interface**
1. Repository öffnen
2. "Add file" → "Upload files"
3. Alle Dateien hochladen
4. "Commit changes"

**Option B: Git Kommandozeile**
```bash
cd /pfad/zum/projekt
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/IHR-USERNAME/ra-rhm-fragebogen.git
git push -u origin main
```

### Schritt 3: Streamlit Cloud Deployment

1. Öffnen Sie [share.streamlit.io](https://share.streamlit.io)
2. Melden Sie sich mit GitHub an
3. Klicken Sie "New app"
4. Konfigurieren Sie:
   - **Repository**: `IHR-USERNAME/ra-rhm-fragebogen`
   - **Branch**: `main`
   - **Main file path**: `app.py`
5. Klicken Sie "Deploy!"

Die App ist dann unter einer URL wie `https://ihr-app-name.streamlit.app` erreichbar.

## 📖 Bedienungsanleitung

### Für Administratoren

#### Formulare laden
1. App öffnen
2. Auf Dashboard: "Formulare aus JSON laden" klicken
3. Oder: Einstellungen → JSON-Datei hochladen

#### Einladungslink erstellen
1. Dashboard → Formular auswählen → "🔗 Einladung"
2. App-URL eingeben
3. Optional: Mandantenname eingeben
4. "Link generieren" klicken
5. Link kopieren und versenden

#### Per E-Mail einladen
1. Wie oben, aber E-Mail-Adresse eingeben
2. "E-Mail erstellen" klicken
3. E-Mail-Programm öffnet sich mit vorgefertigtem Text

#### Mitarbeiter verwalten
1. Einstellungen öffnen
2. Mitarbeiter hinzufügen/bearbeiten/löschen
3. Standard-Empfänger festlegen

### Für Mandanten

1. Einladungslink öffnen
2. Formular ausfüllen
3. Empfänger auswählen (oder Standard verwenden)
4. "Formular absenden" klicken
5. Dokument herunterladen oder per E-Mail senden

## 🔧 Lokale Entwicklung

```bash
# Repository klonen
git clone https://github.com/IHR-USERNAME/ra-rhm-fragebogen.git
cd ra-rhm-fragebogen

# Virtuelle Umgebung (optional aber empfohlen)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder: venv\Scripts\activate  # Windows

# Dependencies installieren
pip install -r requirements.txt

# App starten
streamlit run app.py
```

Die App öffnet sich unter `http://localhost:8501`

## 📁 Enthaltene Formulare

| Kategorie | Formulare |
|-----------|-----------|
| 📜 Notariat | Urkundsauswahl, Vorsorgevollmacht, Erbscheinsantrag, Erbausschlagung |
| 👨‍👩‍👧‍👦 Familienrecht | Mandantenfragebogen, Scheidungsfragebogen, Familienrecht Aufnahme |
| 💼 Arbeitsrecht | Arbeitnehmer-Aufnahme, Arbeitgeber-Aufnahme, BEM-Gespräch, Aufhebungsvertrag |
| 🚗 Verkehrsrecht | Fragebogen Verkehrsrecht |
| 🏠 Mietrecht | Fragebogen Mieter, Fragebogen Vermieter |
| ⚖️ Zivilrecht | Fragebogen Zivilrecht |

## 🔒 Datenschutz & Sicherheit

- ✅ **Keine Datenbank**: Alle Daten nur im Browser-Session
- ✅ **Keine Server-Speicherung**: Formulardaten werden nicht gespeichert
- ✅ **Einladungslinks mit Ablauf**: 7 Tage Gültigkeit
- ✅ **DSGVO-Checkboxen**: In relevanten Formularen enthalten
- ✅ **Lokale Verarbeitung**: Dokumente werden clientseitig generiert

## 🛠️ Anpassung

### Mitarbeiter ändern

In `app.py` die `DEFAULT_EMPLOYEES` Liste anpassen:

```python
DEFAULT_EMPLOYEES = [
    {"name": "Sekretariat", "email": "info@ra-rhm.de", "default": True},
    {"name": "Ihr Name", "email": "ihre@email.de", "default": False},
]
```

### Kategorien ändern

In `app.py` die `CATEGORIES` Dictionary anpassen:

```python
CATEGORIES = {
    "Notariat": [3, 8, 10, 13, 18],  # Formular-IDs
    "Neue Kategorie": [1, 2, 3],
}
```

### Theme anpassen

In `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#b45309"      # Hauptfarbe
backgroundColor = "#fffbeb"    # Hintergrund
textColor = "#1c1917"          # Textfarbe
```

## 📞 Support

**RA-RHM Rechtsanwaltskanzlei**
- 📧 E-Mail: info@ra-rhm.de
- 📞 Telefon: 04331 732970

---

© 2025 RA-RHM Rechtsanwaltskanzlei | Alle Rechte vorbehalten
