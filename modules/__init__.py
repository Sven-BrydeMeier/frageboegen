"""
RA-RHM Formular-System Module
Professionelles Fragebogen-Management für Rechtsanwaltskanzleien
"""

# Core Schema
from .form_schema import (
    FormSchema, FormField, FormPage, FieldType,
    ConditionalLogic, Condition, ConditionOperator,
    Calculation, CalculationType, FieldValidation,
    WorkflowRule, WorkflowAction, WorkflowActionType,
    FormSubmission, FormStatus, SubmissionStatus,
    create_example_schema
)

# Document Engine
from .document_engine import DocumentEngine, DEFAULT_PDF_CSS, DEFAULT_PDF_HTML

# Email Engine
from .email_engine import (
    EmailEngine, EmailMessage, EmailAttachment,
    SMTPConfig, SendGridConfig, EmailProvider, EmailStatus,
    EMAIL_TEMPLATE_CONFIRMATION, EMAIL_TEMPLATE_INTERNAL
)

# Workflow Engine
from .workflow_engine import (
    WorkflowEngine, WorkflowExecutionStatus,
    ActionResult, WorkflowExecutionLog,
    create_example_workflow
)

# Database
from .database import (
    DatabaseManager, FormTemplate, Submission,
    UploadedFile, GeneratedDocument, EmailLog, WorkflowLog,
    User, AuditLog
)

# Auth
from .auth import (
    AuthManager, User as AuthUser, UserRole, Tenant,
    init_auth_state, get_current_user, login_user, logout_user,
    require_auth, render_login_form, render_user_menu,
    render_user_management, ROLE_PERMISSIONS
)

# Optional modules (graceful degradation wenn Dependencies fehlen)

# Cloud Email
try:
    from .cloud_email import (
        MicrosoftGraphMailer, MicrosoftGraphConfig,
        GmailMailer, GmailConfig,
        CloudMailer
    )
    HAS_CLOUD_EMAIL = True
except ImportError:
    HAS_CLOUD_EMAIL = False

# Docusign
try:
    from .docusign import (
        DocusignClient, DocusignConfig,
        SignerInfo, SignatureRequest, SignatureStatus,
        DocusignWebhookHandler, render_signature_status
    )
    HAS_DOCUSIGN = True
except ImportError:
    HAS_DOCUSIGN = False

# Virus Scanner
try:
    from .virus_scanner import (
        FileScanner, VirusScanner, SimpleFileChecker,
        ScanResult, ScanReport, render_scan_result
    )
    HAS_VIRUS_SCANNER = True
except ImportError:
    HAS_VIRUS_SCANNER = False

# Document Converter
try:
    from .converter import (
        DocumentConverter, BatchConverter,
        OutputFormat, ConversionMethod,
        docx_to_pdf, xlsx_to_pdf, pptx_to_pdf, html_to_pdf
    )
    HAS_CONVERTER = True
except ImportError:
    HAS_CONVERTER = False

# PDF Form Filler
try:
    from .pdf_form_filler import (
        PDFFormFiller, get_form_fields_info
    )
    HAS_PDF_FILLER = True
except ImportError:
    HAS_PDF_FILLER = False

# Background Tasks
try:
    from .tasks import (
        TaskManager, celery_app,
        task_generate_document, task_send_email,
        task_process_workflow, task_bulk_email
    )
    HAS_CELERY = True
except ImportError:
    HAS_CELERY = False

# Caching
try:
    from .caching import (
        CacheTTL, get_database_connection,
        get_document_engine, get_email_engine, get_workflow_engine,
        get_file_scanner, get_document_converter,
        render_cache_management, invalidate_submissions_cache
    )
    HAS_CACHING = True
except ImportError:
    HAS_CACHING = False


__version__ = "1.0.0"
__author__ = "RA-RHM"

__all__ = [
    # Schema
    'FormSchema', 'FormField', 'FormPage', 'FieldType',
    'ConditionalLogic', 'Condition', 'ConditionOperator',
    'Calculation', 'CalculationType', 'FieldValidation',
    'WorkflowRule', 'WorkflowAction', 'WorkflowActionType',
    'FormSubmission', 'FormStatus', 'SubmissionStatus',
    'create_example_schema',
    
    # Document
    'DocumentEngine', 'DEFAULT_PDF_CSS', 'DEFAULT_PDF_HTML',
    
    # Email
    'EmailEngine', 'EmailMessage', 'EmailAttachment',
    'SMTPConfig', 'SendGridConfig', 'EmailProvider', 'EmailStatus',
    
    # Workflow
    'WorkflowEngine', 'WorkflowExecutionStatus',
    'ActionResult', 'WorkflowExecutionLog',
    
    # Database
    'DatabaseManager', 'FormTemplate', 'Submission',
    'UploadedFile', 'GeneratedDocument', 'EmailLog', 'WorkflowLog',
    'User', 'AuditLog',
    
    # Auth
    'AuthManager', 'AuthUser', 'UserRole', 'Tenant',
    'init_auth_state', 'get_current_user', 'login_user', 'logout_user',
    
    # Feature Flags
    'HAS_CLOUD_EMAIL', 'HAS_DOCUSIGN', 'HAS_VIRUS_SCANNER',
    'HAS_CONVERTER', 'HAS_PDF_FILLER', 'HAS_CELERY', 'HAS_CACHING',
]
