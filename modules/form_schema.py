"""
Formular-Schema-Definitionen mit Pydantic
Validierung, Typisierung und Serialisierung für Formularstrukturen
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal, Union
from enum import Enum
from datetime import datetime
import uuid
import json


# ============================================
# Enums für Feldtypen und Operatoren
# ============================================

class FieldType(str, Enum):
    TEXT = "text"
    TEXTAREA = "textarea"
    EMAIL = "email"
    PHONE = "phone"
    NUMBER = "number"
    CURRENCY = "currency"
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    CHECKBOX_GROUP = "checkbox_group"
    TOGGLE = "toggle"
    SLIDER = "slider"
    ADDRESS = "address"
    NAME = "name"
    FILE_UPLOAD = "file_upload"
    SIGNATURE = "signature"
    CALCULATED = "calculated"
    SECTION = "section"
    SECTION_START = "section_start"
    SECTION_END = "section_end"
    REPEATABLE = "repeatable"
    REPEATABLE_TABLE = "repeatable_table"
    HIDDEN = "hidden"
    INFO_TEXT = "info_text"
    HTML = "html"
    DIVIDER = "divider"
    SPACER = "spacer"


class ConditionOperator(str, Enum):
    EQUALS = "eq"
    NOT_EQUALS = "neq"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    GREATER_THAN = "gt"
    GREATER_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_EQUAL = "lte"
    IS_EMPTY = "empty"
    IS_NOT_EMPTY = "not_empty"
    IN_LIST = "in"
    NOT_IN_LIST = "not_in"
    REGEX_MATCH = "regex"


class CalculationType(str, Enum):
    SUM = "sum"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    COUNT_IF = "count_if"
    CONCAT = "concat"
    DATE_DIFF = "date_diff"
    DATE_ADD = "date_add"
    CUSTOM_FORMULA = "formula"


class WorkflowActionType(str, Enum):
    GENERATE_DOCUMENT = "generate_document"
    SEND_EMAIL = "send_email"
    WEBHOOK = "webhook"
    SET_FIELD = "set_field"
    CREATE_TASK = "create_task"
    NOTIFY = "notify"
    MERGE_PDF = "merge_pdf"
    ARCHIVE = "archive"


class FormStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class SubmissionStatus(str, Enum):
    STARTED = "started"
    SAVED = "saved"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


# ============================================
# Validierungs-Regeln
# ============================================

class ValidationRule(BaseModel):
    """Einzelne Validierungsregel"""
    type: Literal["required", "min_length", "max_length", "min_value", "max_value", 
                  "pattern", "email", "url", "date_range", "file_type", "file_size",
                  "custom"]
    value: Optional[Any] = None
    message: Optional[str] = None  # Benutzerdefinierte Fehlermeldung
    
    class Config:
        extra = "allow"


class FieldValidation(BaseModel):
    """Alle Validierungsregeln für ein Feld"""
    required: bool = False
    rules: List[ValidationRule] = Field(default_factory=list)
    
    # Kurzformen für häufige Validierungen
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = None
    pattern_message: Optional[str] = None


# ============================================
# Bedingte Logik
# ============================================

class Condition(BaseModel):
    """Einzelne Bedingung"""
    field: str  # Feld-ID auf das sich die Bedingung bezieht
    operator: ConditionOperator
    value: Optional[Any] = None
    
    def evaluate(self, form_data: Dict[str, Any]) -> bool:
        """Wertet die Bedingung gegen Formulardaten aus"""
        field_value = form_data.get(self.field)
        
        if self.operator == ConditionOperator.IS_EMPTY:
            return field_value is None or field_value == "" or field_value == []
        
        if self.operator == ConditionOperator.IS_NOT_EMPTY:
            return field_value is not None and field_value != "" and field_value != []
        
        if field_value is None:
            return False
            
        if self.operator == ConditionOperator.EQUALS:
            return str(field_value) == str(self.value)
        elif self.operator == ConditionOperator.NOT_EQUALS:
            return str(field_value) != str(self.value)
        elif self.operator == ConditionOperator.CONTAINS:
            return str(self.value).lower() in str(field_value).lower()
        elif self.operator == ConditionOperator.NOT_CONTAINS:
            return str(self.value).lower() not in str(field_value).lower()
        elif self.operator == ConditionOperator.STARTS_WITH:
            return str(field_value).lower().startswith(str(self.value).lower())
        elif self.operator == ConditionOperator.ENDS_WITH:
            return str(field_value).lower().endswith(str(self.value).lower())
        elif self.operator == ConditionOperator.GREATER_THAN:
            try:
                return float(field_value) > float(self.value)
            except:
                return False
        elif self.operator == ConditionOperator.GREATER_EQUAL:
            try:
                return float(field_value) >= float(self.value)
            except:
                return False
        elif self.operator == ConditionOperator.LESS_THAN:
            try:
                return float(field_value) < float(self.value)
            except:
                return False
        elif self.operator == ConditionOperator.LESS_EQUAL:
            try:
                return float(field_value) <= float(self.value)
            except:
                return False
        elif self.operator == ConditionOperator.IN_LIST:
            if isinstance(self.value, list):
                return field_value in self.value
            return field_value in str(self.value).split(",")
        elif self.operator == ConditionOperator.NOT_IN_LIST:
            if isinstance(self.value, list):
                return field_value not in self.value
            return field_value not in str(self.value).split(",")
        elif self.operator == ConditionOperator.REGEX_MATCH:
            import re
            try:
                return bool(re.match(str(self.value), str(field_value)))
            except:
                return False
        
        return False


class ConditionalLogic(BaseModel):
    """Bedingte Logik mit mehreren Bedingungen"""
    enabled: bool = False
    logic_type: Literal["all", "any"] = "all"  # AND / OR
    conditions: List[Condition] = Field(default_factory=list)
    
    def evaluate(self, form_data: Dict[str, Any]) -> bool:
        """Wertet alle Bedingungen aus"""
        if not self.enabled or not self.conditions:
            return True
        
        results = [cond.evaluate(form_data) for cond in self.conditions]
        
        if self.logic_type == "all":
            return all(results)
        else:  # any
            return any(results)


# ============================================
# Berechnungen
# ============================================

class Calculation(BaseModel):
    """Berechnungsdefinition für berechnete Felder"""
    type: CalculationType
    fields: List[str] = Field(default_factory=list)  # Referenzierte Feld-IDs
    formula: Optional[str] = None  # Für custom formulas
    options: Dict[str, Any] = Field(default_factory=dict)  # Zusatzoptionen
    
    def compute(self, form_data: Dict[str, Any]) -> Any:
        """Berechnet den Wert basierend auf Formulardaten"""
        values = []
        for field_id in self.fields:
            val = form_data.get(field_id)
            if val is not None:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    if self.type == CalculationType.CONCAT:
                        values.append(str(val))
        
        if self.type == CalculationType.SUM:
            return sum(values) if values else 0
        elif self.type == CalculationType.SUBTRACT:
            if len(values) >= 2:
                result = values[0]
                for v in values[1:]:
                    result -= v
                return result
            return values[0] if values else 0
        elif self.type == CalculationType.MULTIPLY:
            result = 1
            for v in values:
                result *= v
            return result if values else 0
        elif self.type == CalculationType.DIVIDE:
            if len(values) >= 2 and values[1] != 0:
                return values[0] / values[1]
            return 0
        elif self.type == CalculationType.AVERAGE:
            return sum(values) / len(values) if values else 0
        elif self.type == CalculationType.MIN:
            return min(values) if values else 0
        elif self.type == CalculationType.MAX:
            return max(values) if values else 0
        elif self.type == CalculationType.COUNT:
            return len([v for v in values if v])
        elif self.type == CalculationType.CONCAT:
            separator = self.options.get("separator", " ")
            return separator.join([str(v) for v in values])
        elif self.type == CalculationType.DATE_DIFF:
            # Differenz in Tagen
            if len(self.fields) >= 2:
                from datetime import datetime
                try:
                    d1 = datetime.fromisoformat(str(form_data.get(self.fields[0], "")))
                    d2 = datetime.fromisoformat(str(form_data.get(self.fields[1], "")))
                    return (d2 - d1).days
                except:
                    return 0
            return 0
        elif self.type == CalculationType.CUSTOM_FORMULA and self.formula:
            # Sichere Formelauswertung (eingeschränkt!)
            try:
                # Nur einfache mathematische Operationen erlauben
                allowed_names = {"abs": abs, "round": round, "min": min, "max": max}
                for field_id in self.fields:
                    allowed_names[field_id] = form_data.get(field_id, 0)
                return eval(self.formula, {"__builtins__": {}}, allowed_names)
            except:
                return None
        
        return None


# ============================================
# Feld-Optionen (für Select, Radio, etc.)
# ============================================

class FieldOption(BaseModel):
    """Eine Auswahloption"""
    label: str
    value: str
    disabled: bool = False
    description: Optional[str] = None
    icon: Optional[str] = None
    
    # Für abhängige Optionen
    show_if: Optional[ConditionalLogic] = None


# ============================================
# Unterfeld-Konfiguration
# ============================================

class SubfieldConfig(BaseModel):
    """Konfiguration für Unterfelder (z.B. bei Name, Adresse)"""
    id: str
    label: str
    placeholder: Optional[str] = None
    required: bool = False
    visible: bool = True
    width: Optional[str] = None  # z.B. "50%", "1/2"
    order: int = 0


# ============================================
# Haupt-Felddefinition
# ============================================

class RepeatableSection(BaseModel):
    """Wiederholbarer Abschnitt (z.B. mehrere Kinder, Positionen)"""
    id: str = Field(default_factory=lambda: f"section_{uuid.uuid4().hex[:8]}")
    label: str
    description: Optional[str] = None
    
    # Felder innerhalb des Abschnitts
    fields: List["FormField"] = Field(default_factory=list)
    
    # Limits
    min_items: int = 0
    max_items: Optional[int] = None
    
    # Labels
    add_button_text: str = "Weiteren Eintrag hinzufügen"
    remove_button_text: str = "Entfernen"
    item_label_template: str = "Eintrag {n}"  # z.B. "Kind {n}", "Position {n}"
    
    # Bedingte Anzeige
    conditional_logic: Optional["ConditionalLogic"] = None


class RepeatableSection(BaseModel):
    """Wiederholbare Sektion (z.B. mehrere Kinder, Positionen)"""
    id: str = Field(default_factory=lambda: f"repeat_{uuid.uuid4().hex[:8]}")
    label: str
    description: Optional[str] = None
    
    # Felder innerhalb der Sektion
    fields: List["FormField"] = Field(default_factory=list)
    
    # Limits
    min_items: int = 0
    max_items: Optional[int] = None
    
    # Labels
    item_label: str = "Eintrag {n}"  # z.B. "Kind {n}", "Position {n}"
    add_button_text: str = "Weiteren Eintrag hinzufügen"
    remove_button_text: str = "Entfernen"
    
    # Darstellung
    collapsed_by_default: bool = False
    show_item_numbers: bool = True
    
    # Bedingte Logik für gesamte Sektion
    conditional_logic: ConditionalLogic = Field(default_factory=ConditionalLogic)


class FormField(BaseModel):
    """Vollständige Felddefinition"""
    id: str = Field(default_factory=lambda: f"field_{uuid.uuid4().hex[:8]}")
    type: FieldType
    label: str
    name: Optional[str] = None  # Technischer Name für Mappings
    
    # Darstellung
    placeholder: Optional[str] = None
    description: Optional[str] = None
    help_text: Optional[str] = None
    prefix: Optional[str] = None  # z.B. "€" vor Zahlenfeld
    suffix: Optional[str] = None  # z.B. "kg" nach Zahlenfeld
    
    # Verhalten
    default_value: Optional[Any] = None
    readonly: bool = False
    hidden: bool = False
    
    # Validierung
    validation: FieldValidation = Field(default_factory=FieldValidation)
    
    # Optionen (für Select, Radio, Checkbox)
    options: List[FieldOption] = Field(default_factory=list)
    allow_other: bool = False  # "Sonstiges" Option
    
    # Unterfelder (für Name, Adresse)
    subfields: List[SubfieldConfig] = Field(default_factory=list)
    
    # Bedingte Logik
    conditional_logic: ConditionalLogic = Field(default_factory=ConditionalLogic)
    
    # Berechnung
    calculation: Optional[Calculation] = None
    
    # Wiederholbare Felder (einfach)
    repeatable: bool = False
    min_items: int = 0
    max_items: Optional[int] = None
    item_label: Optional[str] = None  # z.B. "Kind {n}"
    
    # Wiederholbare Sektion (komplex) - enthält mehrere Felder
    repeatable_section: Optional[RepeatableSection] = None
    
    # Upload-spezifisch
    allowed_file_types: List[str] = Field(default_factory=list)  # z.B. [".pdf", ".jpg"]
    max_file_size_mb: Optional[float] = None
    max_files: int = 1
    
    # Layout
    width: Optional[str] = None  # "full", "half", "third", "quarter"
    css_class: Optional[str] = None
    order: int = 0
    
    # Mapping für Dokumente
    template_variable: Optional[str] = None  # Variable in DOCX/PDF Template
    
    class Config:
        extra = "allow"
    
    @field_validator("name", mode="before")
    @classmethod
    def set_name_from_id(cls, v, info):
        if v is None and "id" in info.data:
            return info.data["id"]
        return v


# Forward reference auflösen
RepeatableSection.model_rebuild()


# ============================================
# Formular-Seite (für Wizard)
# ============================================

class FormPage(BaseModel):
    """Eine Seite im mehrseitigen Formular"""
    id: str = Field(default_factory=lambda: f"page_{uuid.uuid4().hex[:8]}")
    title: str
    description: Optional[str] = None
    fields: List[FormField] = Field(default_factory=list)
    
    # Bedingte Anzeige der Seite
    conditional_logic: ConditionalLogic = Field(default_factory=ConditionalLogic)
    
    order: int = 0


# ============================================
# Workflow-Aktionen
# ============================================

class WorkflowAction(BaseModel):
    """Eine Aktion im Workflow"""
    id: str = Field(default_factory=lambda: f"action_{uuid.uuid4().hex[:8]}")
    type: WorkflowActionType
    name: str
    
    # Aktion-spezifische Konfiguration
    config: Dict[str, Any] = Field(default_factory=dict)
    
    # Bedingung für Ausführung
    condition: Optional[ConditionalLogic] = None
    
    # Fehlerbehandlung
    on_error: Literal["stop", "continue", "retry"] = "stop"
    retry_count: int = 0
    
    order: int = 0


class WorkflowRule(BaseModel):
    """Workflow-Regel mit Trigger und Aktionen"""
    id: str = Field(default_factory=lambda: f"workflow_{uuid.uuid4().hex[:8]}")
    name: str
    description: Optional[str] = None
    
    # Trigger
    trigger: Literal["on_submit", "on_save", "on_field_change", "scheduled", "manual"] = "on_submit"
    trigger_config: Dict[str, Any] = Field(default_factory=dict)
    
    # Globale Bedingung für den gesamten Workflow
    condition: Optional[ConditionalLogic] = None
    
    # Aktionen
    actions: List[WorkflowAction] = Field(default_factory=list)
    
    enabled: bool = True
    order: int = 0


# ============================================
# Haupt-Formularschema
# ============================================

class FormSchema(BaseModel):
    """Vollständiges Formularschema"""
    id: str = Field(default_factory=lambda: f"form_{uuid.uuid4().hex[:8]}")
    
    # Metadaten
    name: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    
    # Versionierung
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: Optional[str] = None
    
    # Status
    status: FormStatus = FormStatus.DRAFT
    
    # Struktur
    pages: List[FormPage] = Field(default_factory=list)  # Für mehrseitige Formulare
    fields: List[FormField] = Field(default_factory=list)  # Für einseitige Formulare
    
    # Workflows
    workflows: List[WorkflowRule] = Field(default_factory=list)
    
    # Einstellungen
    settings: Dict[str, Any] = Field(default_factory=lambda: {
        "show_progress": True,
        "allow_save_draft": True,
        "show_review_page": True,
        "submit_button_text": "Absenden",
        "success_message": "Vielen Dank für Ihre Eingabe!",
        "redirect_url": None,
    })
    
    # Template-Zuordnungen
    document_templates: List[Dict[str, Any]] = Field(default_factory=list)
    email_templates: List[Dict[str, Any]] = Field(default_factory=list)
    
    class Config:
        extra = "allow"
    
    def get_all_fields(self) -> List[FormField]:
        """Gibt alle Felder zurück (aus pages oder fields)"""
        all_fields = list(self.fields)
        for page in self.pages:
            all_fields.extend(page.fields)
        return all_fields
    
    def get_field_by_id(self, field_id: str) -> Optional[FormField]:
        """Findet ein Feld anhand seiner ID"""
        for field in self.get_all_fields():
            if field.id == field_id:
                return field
        return None
    
    def to_json(self) -> str:
        """Serialisiert das Schema zu JSON"""
        return self.model_dump_json(indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "FormSchema":
        """Lädt ein Schema aus JSON"""
        return cls.model_validate_json(json_str)
    
    def duplicate(self, new_name: Optional[str] = None) -> "FormSchema":
        """Erstellt eine Kopie des Schemas"""
        data = self.model_dump()
        data["id"] = f"form_{uuid.uuid4().hex[:8]}"
        data["name"] = new_name or f"{self.name} (Kopie)"
        data["version"] = 1
        data["created_at"] = datetime.now()
        data["updated_at"] = datetime.now()
        data["status"] = FormStatus.DRAFT
        return FormSchema.model_validate(data)


# ============================================
# Submission (ausgefülltes Formular)
# ============================================

class FormSubmission(BaseModel):
    """Eine Formular-Einreichung"""
    id: str = Field(default_factory=lambda: f"sub_{uuid.uuid4().hex[:8]}")
    form_id: str
    form_version: int
    
    # Daten
    data: Dict[str, Any] = Field(default_factory=dict)
    
    # Metadaten
    status: SubmissionStatus = SubmissionStatus.STARTED
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    
    # Benutzer
    created_by: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Uploads
    uploaded_files: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Generierte Dokumente
    generated_documents: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Workflow-Status
    workflow_results: List[Dict[str, Any]] = Field(default_factory=list)
    
    class Config:
        extra = "allow"


# ============================================
# Beispiel-Schema erstellen
# ============================================

def create_example_schema() -> FormSchema:
    """Erstellt ein Beispiel-Formularschema"""
    return FormSchema(
        name="mandantenaufnahme",
        title="Mandantenaufnahme",
        description="Ersterfassung neuer Mandanten",
        category="Allgemein",
        status=FormStatus.ACTIVE,
        pages=[
            FormPage(
                id="page_1",
                title="Persönliche Daten",
                order=0,
                fields=[
                    FormField(
                        id="anrede",
                        type=FieldType.RADIO,
                        label="Anrede",
                        validation=FieldValidation(required=True),
                        options=[
                            FieldOption(label="Herr", value="herr"),
                            FieldOption(label="Frau", value="frau"),
                            FieldOption(label="Divers", value="divers"),
                        ],
                        template_variable="anrede",
                    ),
                    FormField(
                        id="vorname",
                        type=FieldType.TEXT,
                        label="Vorname",
                        placeholder="Ihr Vorname",
                        validation=FieldValidation(required=True, min_length=2),
                        width="half",
                        template_variable="vorname",
                    ),
                    FormField(
                        id="nachname",
                        type=FieldType.TEXT,
                        label="Nachname",
                        placeholder="Ihr Nachname",
                        validation=FieldValidation(required=True, min_length=2),
                        width="half",
                        template_variable="nachname",
                    ),
                    FormField(
                        id="geburtsdatum",
                        type=FieldType.DATE,
                        label="Geburtsdatum",
                        validation=FieldValidation(required=True),
                        template_variable="geburtsdatum",
                    ),
                    FormField(
                        id="familienstand",
                        type=FieldType.SELECT,
                        label="Familienstand",
                        options=[
                            FieldOption(label="Ledig", value="ledig"),
                            FieldOption(label="Verheiratet", value="verheiratet"),
                            FieldOption(label="Geschieden", value="geschieden"),
                            FieldOption(label="Verwitwet", value="verwitwet"),
                        ],
                        template_variable="familienstand",
                    ),
                    FormField(
                        id="ehepartner_name",
                        type=FieldType.TEXT,
                        label="Name des Ehepartners",
                        conditional_logic=ConditionalLogic(
                            enabled=True,
                            conditions=[
                                Condition(
                                    field="familienstand",
                                    operator=ConditionOperator.EQUALS,
                                    value="verheiratet"
                                )
                            ]
                        ),
                        template_variable="ehepartner_name",
                    ),
                ]
            ),
            FormPage(
                id="page_2",
                title="Kontaktdaten",
                order=1,
                fields=[
                    FormField(
                        id="email",
                        type=FieldType.EMAIL,
                        label="E-Mail-Adresse",
                        validation=FieldValidation(required=True),
                        template_variable="email",
                    ),
                    FormField(
                        id="telefon",
                        type=FieldType.PHONE,
                        label="Telefonnummer",
                        template_variable="telefon",
                    ),
                    FormField(
                        id="strasse",
                        type=FieldType.TEXT,
                        label="Straße und Hausnummer",
                        template_variable="strasse",
                    ),
                    FormField(
                        id="plz",
                        type=FieldType.TEXT,
                        label="PLZ",
                        validation=FieldValidation(
                            pattern=r"^\d{5}$",
                            pattern_message="Bitte geben Sie eine gültige 5-stellige PLZ ein"
                        ),
                        width="quarter",
                        template_variable="plz",
                    ),
                    FormField(
                        id="ort",
                        type=FieldType.TEXT,
                        label="Ort",
                        width="half",
                        template_variable="ort",
                    ),
                ]
            ),
            FormPage(
                id="page_3",
                title="Anliegen",
                order=2,
                fields=[
                    FormField(
                        id="rechtsgebiet",
                        type=FieldType.SELECT,
                        label="Rechtsgebiet",
                        validation=FieldValidation(required=True),
                        options=[
                            FieldOption(label="Familienrecht", value="familienrecht"),
                            FieldOption(label="Arbeitsrecht", value="arbeitsrecht"),
                            FieldOption(label="Mietrecht", value="mietrecht"),
                            FieldOption(label="Verkehrsrecht", value="verkehrsrecht"),
                            FieldOption(label="Erbrecht", value="erbrecht"),
                            FieldOption(label="Sonstiges", value="sonstiges"),
                        ],
                        template_variable="rechtsgebiet",
                    ),
                    FormField(
                        id="sachverhalt",
                        type=FieldType.TEXTAREA,
                        label="Schildern Sie Ihr Anliegen",
                        placeholder="Bitte beschreiben Sie Ihren Fall...",
                        validation=FieldValidation(required=True, min_length=50),
                        template_variable="sachverhalt",
                    ),
                    FormField(
                        id="unterlagen",
                        type=FieldType.FILE_UPLOAD,
                        label="Relevante Unterlagen hochladen",
                        description="Sie können mehrere Dateien hochladen (PDF, JPG, PNG)",
                        allowed_file_types=[".pdf", ".jpg", ".jpeg", ".png"],
                        max_file_size_mb=10,
                        max_files=5,
                    ),
                ]
            ),
        ],
        workflows=[
            WorkflowRule(
                name="Standard-Workflow",
                trigger="on_submit",
                actions=[
                    WorkflowAction(
                        type=WorkflowActionType.GENERATE_DOCUMENT,
                        name="Mandantenbogen erstellen",
                        config={
                            "template": "mandantenbogen.docx",
                            "output_format": "pdf",
                            "filename": "Mandantenbogen_{nachname}_{datum}.pdf"
                        },
                        order=0
                    ),
                    WorkflowAction(
                        type=WorkflowActionType.SEND_EMAIL,
                        name="Bestätigung an Mandant",
                        config={
                            "template": "bestaetigung_mandant",
                            "to_field": "email",
                            "attach_documents": True
                        },
                        order=1
                    ),
                    WorkflowAction(
                        type=WorkflowActionType.SEND_EMAIL,
                        name="Benachrichtigung Kanzlei",
                        config={
                            "template": "neue_anfrage_kanzlei",
                            "to": "info@ra-rhm.de",
                            "attach_documents": True
                        },
                        order=2
                    ),
                ]
            )
        ],
        document_templates=[
            {
                "id": "mandantenbogen",
                "name": "Mandantenbogen",
                "file": "mandantenbogen.docx",
                "type": "docx"
            }
        ],
        email_templates=[
            {
                "id": "bestaetigung_mandant",
                "name": "Bestätigung an Mandant",
                "subject": "Ihre Anfrage bei RA-RHM - Eingangsbestätigung",
                "body_template": "email_bestaetigung.html"
            },
            {
                "id": "neue_anfrage_kanzlei",
                "name": "Neue Anfrage (intern)",
                "subject": "Neue Mandantenanfrage: {{ nachname }}, {{ vorname }}",
                "body_template": "email_kanzlei.html"
            }
        ]
    )


if __name__ == "__main__":
    # Test: Schema erstellen und serialisieren
    schema = create_example_schema()
    print(schema.to_json())
