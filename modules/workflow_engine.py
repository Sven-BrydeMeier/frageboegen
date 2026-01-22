"""
Workflow-Engine
Führt automatisierte Aktionen basierend auf Formular-Submissions aus
"""

import os
import json
import hashlib
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import traceback

from .form_schema import (
    WorkflowRule, WorkflowAction, WorkflowActionType,
    ConditionalLogic, FormSchema, FormSubmission
)


class WorkflowExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PARTIALLY_COMPLETED = "partially_completed"


@dataclass
class ActionResult:
    """Ergebnis einer einzelnen Aktion"""
    action_id: str
    action_type: WorkflowActionType
    status: WorkflowExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    outputs: Dict[str, Any] = field(default_factory=dict)  # z.B. generierte Dokumente


@dataclass
class WorkflowExecutionLog:
    """Log einer Workflow-Ausführung"""
    id: str
    workflow_id: str
    workflow_name: str
    submission_id: str
    status: WorkflowExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    action_results: List[ActionResult] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'workflow_id': self.workflow_id,
            'workflow_name': self.workflow_name,
            'submission_id': self.submission_id,
            'status': self.status.value,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'action_results': [
                {
                    'action_id': r.action_id,
                    'action_type': r.action_type.value,
                    'status': r.status.value,
                    'started_at': r.started_at.isoformat(),
                    'completed_at': r.completed_at.isoformat() if r.completed_at else None,
                    'error': r.error,
                    'outputs': r.outputs,
                }
                for r in self.action_results
            ],
        }


class WorkflowEngine:
    """Haupt-Engine für Workflow-Ausführung"""
    
    def __init__(
        self,
        document_engine=None,
        email_engine=None,
        storage_path: Optional[str] = None
    ):
        self.document_engine = document_engine
        self.email_engine = email_engine
        self.storage_path = Path(storage_path) if storage_path else Path("storage")
        
        self.logs: List[WorkflowExecutionLog] = []
        
        # Action Handlers registrieren
        self.action_handlers: Dict[WorkflowActionType, Callable] = {
            WorkflowActionType.GENERATE_DOCUMENT: self._handle_generate_document,
            WorkflowActionType.SEND_EMAIL: self._handle_send_email,
            WorkflowActionType.WEBHOOK: self._handle_webhook,
            WorkflowActionType.SET_FIELD: self._handle_set_field,
            WorkflowActionType.MERGE_PDF: self._handle_merge_pdf,
            WorkflowActionType.NOTIFY: self._handle_notify,
            WorkflowActionType.ARCHIVE: self._handle_archive,
        }
        
        # Benutzerdefinierte Handler
        self.custom_handlers: Dict[str, Callable] = {}
    
    def register_handler(self, action_type: str, handler: Callable):
        """Registriert einen benutzerdefinierten Handler"""
        self.custom_handlers[action_type] = handler
    
    def execute_workflow(
        self,
        workflow: WorkflowRule,
        form_schema: FormSchema,
        submission: FormSubmission,
        context: Optional[Dict[str, Any]] = None
    ) -> WorkflowExecutionLog:
        """
        Führt einen Workflow aus
        
        Args:
            workflow: Die Workflow-Definition
            form_schema: Das Formular-Schema
            submission: Die Submission mit den Daten
            context: Zusätzlicher Kontext (z.B. User-Info)
        
        Returns:
            WorkflowExecutionLog mit allen Ergebnissen
        """
        
        log_id = hashlib.md5(
            f"{datetime.now().isoformat()}{workflow.id}{submission.id}".encode()
        ).hexdigest()[:16]
        
        execution_log = WorkflowExecutionLog(
            id=log_id,
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            submission_id=submission.id,
            status=WorkflowExecutionStatus.RUNNING,
            started_at=datetime.now(),
            context=context or {},
        )
        
        # Globale Workflow-Bedingung prüfen
        if workflow.condition and workflow.condition.enabled:
            if not workflow.condition.evaluate(submission.data):
                execution_log.status = WorkflowExecutionStatus.SKIPPED
                execution_log.completed_at = datetime.now()
                self.logs.append(execution_log)
                return execution_log
        
        # Kontext vorbereiten
        workflow_context = {
            'form': form_schema,
            'submission': submission,
            'data': submission.data,
            'generated_documents': [],
            'outputs': {},
            **(context or {}),
        }
        
        # Aktionen sortiert ausführen
        actions = sorted(workflow.actions, key=lambda a: a.order)
        
        all_successful = True
        
        for action in actions:
            action_result = self._execute_action(action, workflow_context)
            execution_log.action_results.append(action_result)
            
            if action_result.status == WorkflowExecutionStatus.FAILED:
                all_successful = False
                
                # Bei on_error="stop" abbrechen
                if action.on_error == "stop":
                    execution_log.status = WorkflowExecutionStatus.FAILED
                    break
            
            # Outputs für nachfolgende Aktionen verfügbar machen
            if action_result.outputs:
                workflow_context['outputs'][action.id] = action_result.outputs
        
        # Finalen Status setzen
        if all_successful:
            execution_log.status = WorkflowExecutionStatus.COMPLETED
        elif execution_log.status != WorkflowExecutionStatus.FAILED:
            execution_log.status = WorkflowExecutionStatus.PARTIALLY_COMPLETED
        
        execution_log.completed_at = datetime.now()
        self.logs.append(execution_log)
        
        return execution_log
    
    def _execute_action(
        self,
        action: WorkflowAction,
        context: Dict[str, Any]
    ) -> ActionResult:
        """Führt eine einzelne Aktion aus"""
        
        result = ActionResult(
            action_id=action.id,
            action_type=action.type,
            status=WorkflowExecutionStatus.RUNNING,
            started_at=datetime.now(),
        )
        
        # Aktions-Bedingung prüfen
        if action.condition and action.condition.enabled:
            if not action.condition.evaluate(context['data']):
                result.status = WorkflowExecutionStatus.SKIPPED
                result.completed_at = datetime.now()
                return result
        
        try:
            handler = self.action_handlers.get(action.type)
            
            if handler:
                outputs = handler(action, context)
                result.outputs = outputs or {}
                result.status = WorkflowExecutionStatus.COMPLETED
            else:
                # Vielleicht ein Custom-Handler?
                custom_handler = self.custom_handlers.get(action.type.value)
                if custom_handler:
                    outputs = custom_handler(action, context)
                    result.outputs = outputs or {}
                    result.status = WorkflowExecutionStatus.COMPLETED
                else:
                    result.status = WorkflowExecutionStatus.FAILED
                    result.error = f"Kein Handler für Aktion '{action.type}' registriert"
        
        except Exception as e:
            result.status = WorkflowExecutionStatus.FAILED
            result.error = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        
        result.completed_at = datetime.now()
        return result
    
    # ========================================
    # Action Handlers
    # ========================================
    
    def _handle_generate_document(
        self,
        action: WorkflowAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generiert ein Dokument"""
        
        if not self.document_engine:
            raise ValueError("DocumentEngine nicht konfiguriert")
        
        config = action.config
        template = config.get('template')
        output_format = config.get('output_format', 'docx')
        filename_template = config.get('filename', 'dokument_{datum}.{format}')
        
        # Dateinamen rendern
        from jinja2 import Environment
        env = Environment()
        filename = env.from_string(filename_template).render(
            **context['data'],
            datum=datetime.now().strftime("%Y%m%d"),
            format=output_format
        )
        
        # Daten für Template vorbereiten
        template_data = {
            **context['data'],
            'datum': datetime.now().strftime("%d.%m.%Y"),
            'uhrzeit': datetime.now().strftime("%H:%M"),
            'submission_id': context['submission'].id,
        }
        
        # Dokument generieren
        if output_format == 'docx' and template:
            doc_bytes = self.document_engine.generate_docx_from_template(
                template, template_data
            )
        elif output_format == 'pdf':
            if template and template.endswith('.html'):
                doc_bytes = self.document_engine.generate_pdf_from_html_template(
                    template, template_data
                )
            elif template and template.endswith('.docx'):
                # DOCX generieren und dann konvertieren (wenn möglich)
                doc_bytes = self.document_engine.generate_docx_from_template(
                    template, template_data
                )
                # TODO: Konvertierung zu PDF
            else:
                # Programmatische PDF-Generierung
                sections = config.get('sections', [
                    {'type': 'heading', 'level': 1, 'text': '{{ formular_name }}'},
                ])
                doc_bytes = self.document_engine.generate_pdf_reportlab(
                    config.get('title', 'Dokument'),
                    template_data,
                    sections
                )
        else:
            raise ValueError(f"Unbekanntes Ausgabeformat: {output_format}")
        
        # Speichern
        output_path = self.storage_path / "documents" / context['submission'].id
        output_path.mkdir(parents=True, exist_ok=True)
        
        filepath = output_path / filename
        with open(filepath, 'wb') as f:
            f.write(doc_bytes)
        
        # Hash berechnen
        doc_hash = hashlib.sha256(doc_bytes).hexdigest()
        
        # Zu Context hinzufügen
        doc_info = {
            'filename': filename,
            'path': str(filepath),
            'format': output_format,
            'size': len(doc_bytes),
            'hash': doc_hash,
            'created_at': datetime.now().isoformat(),
        }
        
        context['generated_documents'].append(doc_info)
        
        return {
            'document': doc_info,
            'bytes': doc_bytes,
        }
    
    def _handle_send_email(
        self,
        action: WorkflowAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Sendet eine E-Mail"""
        
        if not self.email_engine:
            raise ValueError("EmailEngine nicht konfiguriert")
        
        config = action.config
        
        # Empfänger bestimmen
        to = config.get('to')
        if config.get('to_field'):
            to = context['data'].get(config['to_field'])
        
        if not to:
            raise ValueError("Kein Empfänger angegeben")
        
        if isinstance(to, str):
            to = [to]
        
        # Template oder direkter Inhalt
        if config.get('template'):
            from .email_engine import EmailMessage
            
            # Template-Daten vorbereiten
            template_data = {
                **context['data'],
                'datum': datetime.now().strftime("%d.%m.%Y"),
                'uhrzeit': datetime.now().strftime("%H:%M"),
                'kanzlei_name': config.get('kanzlei_name', 'RA-RHM Rechtsanwaltskanzlei'),
                'kanzlei_telefon': config.get('kanzlei_telefon', '04331 732970'),
                'kanzlei_email': config.get('kanzlei_email', 'info@ra-rhm.de'),
                'fields': [
                    {'label': k, 'value': v}
                    for k, v in context['data'].items()
                    if v and not k.startswith('_')
                ],
            }
            
            message = self.email_engine.create_message_from_template(
                to=to,
                template_name=config['template'],
                data=template_data,
                subject_template=config.get('subject'),
                cc=config.get('cc', []),
                bcc=config.get('bcc', []),
            )
        else:
            from .email_engine import EmailMessage
            
            # Direkter Inhalt
            subject = self.email_engine.render_template_string(
                config.get('subject', 'Benachrichtigung'),
                context['data']
            )
            body = self.email_engine.render_template_string(
                config.get('body', ''),
                context['data']
            )
            
            message = EmailMessage(
                to=to,
                subject=subject,
                body_html=body if '<' in body else None,
                body_text=body if '<' not in body else None,
                cc=config.get('cc', []),
                bcc=config.get('bcc', []),
            )
        
        # Anhänge hinzufügen
        if config.get('attach_documents', False):
            for doc in context.get('generated_documents', []):
                if 'bytes' in context['outputs'].get(action.id, {}):
                    # Dokument aus vorheriger Aktion
                    pass
                else:
                    # Aus Datei laden
                    message.add_attachment_from_file(doc['path'])
        
        # Spezifische Anhänge
        for attachment_config in config.get('attachments', []):
            if attachment_config.get('from_action'):
                # Aus anderer Aktion
                action_output = context['outputs'].get(attachment_config['from_action'], {})
                if 'document' in action_output:
                    message.add_attachment_from_file(action_output['document']['path'])
        
        # Senden
        log = self.email_engine.send(message)
        
        return {
            'email_log': log.to_dict(),
            'to': to,
            'subject': message.subject,
        }
    
    def _handle_webhook(
        self,
        action: WorkflowAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ruft einen Webhook auf"""
        import requests
        
        config = action.config
        url = config.get('url')
        method = config.get('method', 'POST').upper()
        headers = config.get('headers', {'Content-Type': 'application/json'})
        
        # Payload vorbereiten
        payload = config.get('payload', context['data'])
        if isinstance(payload, str):
            from jinja2 import Environment
            env = Environment()
            payload = json.loads(env.from_string(payload).render(**context['data']))
        
        # Request ausführen
        response = requests.request(
            method=method,
            url=url,
            json=payload if method in ['POST', 'PUT', 'PATCH'] else None,
            params=payload if method == 'GET' else None,
            headers=headers,
            timeout=config.get('timeout', 30)
        )
        
        return {
            'status_code': response.status_code,
            'response': response.text[:1000],  # Begrenzt
            'success': response.ok,
        }
    
    def _handle_set_field(
        self,
        action: WorkflowAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Setzt ein Feld auf einen Wert"""
        
        config = action.config
        field_name = config.get('field')
        value = config.get('value')
        
        # Wert kann ein Template sein
        if isinstance(value, str) and '{{' in value:
            from jinja2 import Environment
            env = Environment()
            value = env.from_string(value).render(**context['data'])
        
        # Im Submission-Daten setzen
        context['data'][field_name] = value
        context['submission'].data[field_name] = value
        
        return {
            'field': field_name,
            'value': value,
        }
    
    def _handle_merge_pdf(
        self,
        action: WorkflowAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Führt PDFs zusammen"""
        
        if not self.document_engine:
            raise ValueError("DocumentEngine nicht konfiguriert")
        
        config = action.config
        
        # PDFs sammeln
        pdfs = []
        
        # Generierte Dokumente
        for doc in context.get('generated_documents', []):
            if doc['format'] == 'pdf':
                with open(doc['path'], 'rb') as f:
                    pdfs.append(f.read())
        
        # Aus anderen Aktionen
        for action_id in config.get('from_actions', []):
            action_output = context['outputs'].get(action_id, {})
            if action_output.get('bytes'):
                pdfs.append(action_output['bytes'])
        
        # Uploads
        for upload in context['submission'].uploaded_files:
            if upload.get('content_type') == 'application/pdf':
                # TODO: Upload laden
                pass
        
        if not pdfs:
            return {'merged': False, 'reason': 'Keine PDFs zum Zusammenführen'}
        
        # Zusammenführen
        merged_bytes = self.document_engine.merge_pdfs(pdfs)
        
        # Speichern
        filename = config.get('filename', 'merged_{datum}.pdf')
        from jinja2 import Environment
        env = Environment()
        filename = env.from_string(filename).render(
            datum=datetime.now().strftime("%Y%m%d"),
            **context['data']
        )
        
        output_path = self.storage_path / "documents" / context['submission'].id
        filepath = output_path / filename
        
        with open(filepath, 'wb') as f:
            f.write(merged_bytes)
        
        doc_info = {
            'filename': filename,
            'path': str(filepath),
            'format': 'pdf',
            'size': len(merged_bytes),
            'hash': hashlib.sha256(merged_bytes).hexdigest(),
        }
        
        context['generated_documents'].append(doc_info)
        
        return {
            'document': doc_info,
            'merged_count': len(pdfs),
            'bytes': merged_bytes,
        }
    
    def _handle_notify(
        self,
        action: WorkflowAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Sendet eine interne Benachrichtigung"""
        
        config = action.config
        
        notification = {
            'type': config.get('type', 'info'),
            'title': config.get('title', 'Benachrichtigung'),
            'message': config.get('message', ''),
            'recipients': config.get('recipients', []),
            'created_at': datetime.now().isoformat(),
            'submission_id': context['submission'].id,
        }
        
        # Nachricht rendern
        if '{{' in notification['message']:
            from jinja2 import Environment
            env = Environment()
            notification['message'] = env.from_string(notification['message']).render(**context['data'])
        
        # TODO: In DB speichern oder über WebSocket senden
        
        return notification
    
    def _handle_archive(
        self,
        action: WorkflowAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Archiviert die Submission und Dokumente"""
        
        config = action.config
        archive_path = self.storage_path / "archive" / context['submission'].id
        archive_path.mkdir(parents=True, exist_ok=True)
        
        # Submission-Daten speichern
        submission_file = archive_path / "submission.json"
        with open(submission_file, 'w', encoding='utf-8') as f:
            json.dump({
                'id': context['submission'].id,
                'form_id': context['submission'].form_id,
                'data': context['submission'].data,
                'created_at': context['submission'].created_at.isoformat(),
                'archived_at': datetime.now().isoformat(),
            }, f, indent=2, ensure_ascii=False)
        
        # Dokumente kopieren
        import shutil
        archived_docs = []
        for doc in context.get('generated_documents', []):
            src = Path(doc['path'])
            dst = archive_path / doc['filename']
            if src.exists():
                shutil.copy2(src, dst)
                archived_docs.append(doc['filename'])
        
        return {
            'archive_path': str(archive_path),
            'archived_documents': archived_docs,
            'archived_at': datetime.now().isoformat(),
        }
    
    # ========================================
    # Hilfsfunktionen
    # ========================================
    
    def get_logs(self, limit: int = 100) -> List[WorkflowExecutionLog]:
        """Gibt die letzten Logs zurück"""
        return self.logs[-limit:]
    
    def get_logs_for_submission(self, submission_id: str) -> List[WorkflowExecutionLog]:
        """Gibt alle Logs für eine Submission zurück"""
        return [log for log in self.logs if log.submission_id == submission_id]


# ============================================
# Beispiel-Workflow erstellen
# ============================================

def create_example_workflow() -> WorkflowRule:
    """Erstellt einen Beispiel-Workflow"""
    from .form_schema import Condition, ConditionOperator
    
    return WorkflowRule(
        id="workflow_standard",
        name="Standard-Workflow nach Einreichung",
        description="Generiert Dokumente und sendet E-Mails nach Formular-Einreichung",
        trigger="on_submit",
        actions=[
            WorkflowAction(
                id="action_1",
                type=WorkflowActionType.GENERATE_DOCUMENT,
                name="Mandantenbogen erstellen",
                config={
                    'template': 'mandantenbogen.docx',
                    'output_format': 'pdf',
                    'filename': 'Mandantenbogen_{{ nachname }}_{datum}.pdf',
                },
                order=0,
            ),
            WorkflowAction(
                id="action_2",
                type=WorkflowActionType.SEND_EMAIL,
                name="Bestätigung an Mandant",
                config={
                    'template': 'bestaetigung.html',
                    'to_field': 'email',
                    'subject': 'Ihre Anfrage bei RA-RHM - Eingangsbestätigung',
                    'attach_documents': True,
                },
                order=1,
            ),
            WorkflowAction(
                id="action_3",
                type=WorkflowActionType.SEND_EMAIL,
                name="Benachrichtigung Kanzlei",
                config={
                    'template': 'intern_benachrichtigung.html',
                    'to': 'info@ra-rhm.de',
                    'subject': 'Neue Mandantenanfrage: {{ nachname }}, {{ vorname }}',
                    'attach_documents': True,
                },
                condition=ConditionalLogic(
                    enabled=True,
                    conditions=[
                        Condition(
                            field="rechtsgebiet",
                            operator=ConditionOperator.NOT_EQUALS,
                            value=""
                        )
                    ]
                ),
                order=2,
            ),
            WorkflowAction(
                id="action_4",
                type=WorkflowActionType.ARCHIVE,
                name="Archivieren",
                config={},
                order=99,
            ),
        ],
        enabled=True,
    )


if __name__ == "__main__":
    workflow = create_example_workflow()
    print(json.dumps(workflow.model_dump(), indent=2, default=str))
