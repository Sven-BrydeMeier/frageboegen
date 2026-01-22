"""
RA-RHM Formular-System Module
Optimiert für Streamlit Cloud
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

# Document Engine (mit optionalen Features)
try:
    from .document_engine import DocumentEngine, DEFAULT_PDF_CSS, DEFAULT_PDF_HTML
    HAS_DOCUMENT_ENGINE = True
except Exception as e:
    HAS_DOCUMENT_ENGINE = False
    print(f"Warning: DocumentEngine nicht verfügbar: {e}")

# Email Engine
try:
    from .email_engine import (
        EmailEngine, EmailMessage, EmailAttachment,
        SMTPConfig, SendGridConfig, EmailProvider, EmailStatus,
        EMAIL_TEMPLATE_CONFIRMATION, EMAIL_TEMPLATE_INTERNAL
    )
    HAS_EMAIL_ENGINE = True
except Exception as e:
    HAS_EMAIL_ENGINE = False
    print(f"Warning: EmailEngine nicht verfügbar: {e}")

# Workflow Engine
try:
    from .workflow_engine import (
        WorkflowEngine, WorkflowExecutionStatus,
        ActionResult, WorkflowExecutionLog,
        create_example_workflow
    )
    HAS_WORKFLOW_ENGINE = True
except Exception as e:
    HAS_WORKFLOW_ENGINE = False
    print(f"Warning: WorkflowEngine nicht verfügbar: {e}")

# Database
try:
    from .database import (
        DatabaseManager, FormTemplate, Submission,
        UploadedFile, GeneratedDocument, EmailLog, WorkflowLog,
        User, AuditLog
    )
    HAS_DATABASE = True
except Exception as e:
    HAS_DATABASE = False
    print(f"Warning: Database nicht verfügbar: {e}")

# Auth (wichtig für die App!)
from .auth import (
    AuthManager, UserRole, Tenant,
    init_auth_state, get_current_user, login_user, logout_user,
    require_auth, render_login_form, render_user_menu,
    render_user_management, ROLE_PERMISSIONS
)
# User-Klasse umbenennen um Konflikt zu vermeiden
from .auth import User as AuthUser

__version__ = "1.0.0"
