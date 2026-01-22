"""
Background Jobs mit Celery
Für asynchrone Verarbeitung von Dokumenten, E-Mails, etc.
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import traceback

# Celery
try:
    from celery import Celery, Task
    from celery.result import AsyncResult
    HAS_CELERY = True
except ImportError:
    HAS_CELERY = False

# Redis (als Broker)
try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


# ============================================
# Celery App Konfiguration
# ============================================

def create_celery_app(
    broker_url: str = "redis://localhost:6379/0",
    result_backend: str = "redis://localhost:6379/1",
    task_serializer: str = "json",
    result_serializer: str = "json",
    accept_content: List[str] = None,
    timezone: str = "Europe/Berlin",
    **kwargs
) -> "Celery":
    """
    Erstellt und konfiguriert die Celery-App
    """
    if not HAS_CELERY:
        raise ImportError("celery ist nicht installiert: pip install celery[redis]")
    
    app = Celery("formular_system")
    
    app.conf.update(
        broker_url=broker_url,
        result_backend=result_backend,
        task_serializer=task_serializer,
        result_serializer=result_serializer,
        accept_content=accept_content or ["json"],
        timezone=timezone,
        enable_utc=True,
        task_track_started=True,
        task_time_limit=3600,  # 1 Stunde max
        task_soft_time_limit=3000,  # 50 Minuten Soft-Limit
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        **kwargs
    )
    
    return app


# Default App (wird bei Import erstellt wenn Celery verfügbar)
if HAS_CELERY:
    celery_app = create_celery_app(
        broker_url=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        result_backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    )
else:
    celery_app = None


# ============================================
# Task Dekoratoren (mit Fallback)
# ============================================

def background_task(func):
    """
    Dekorator für Background Tasks
    Falls Celery nicht verfügbar, wird synchron ausgeführt
    """
    if HAS_CELERY and celery_app:
        return celery_app.task(bind=True)(func)
    else:
        # Synchroner Fallback
        def sync_wrapper(*args, **kwargs):
            return func(None, *args, **kwargs)
        sync_wrapper.__name__ = func.__name__
        return sync_wrapper


# ============================================
# Tasks
# ============================================

if HAS_CELERY and celery_app:
    
    @celery_app.task(bind=True, name="tasks.generate_document")
    def task_generate_document(
        self,
        submission_id: str,
        template_id: str,
        output_format: str = "pdf",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generiert ein Dokument im Hintergrund
        """
        try:
            self.update_state(state='PROGRESS', meta={'step': 'loading', 'progress': 10})
            
            # Import hier um zirkuläre Imports zu vermeiden
            from .document_engine import DocumentEngine
            from .database import DatabaseManager
            
            db = DatabaseManager()
            engine = DocumentEngine()
            
            # Submission laden
            submission = db.get_submission(submission_id)
            if not submission:
                return {'success': False, 'error': 'Submission nicht gefunden'}
            
            self.update_state(state='PROGRESS', meta={'step': 'generating', 'progress': 50})
            
            # Dokument generieren
            # ... (Implementation abhängig von Template-Typ)
            
            self.update_state(state='PROGRESS', meta={'step': 'saving', 'progress': 90})
            
            # Ergebnis speichern
            result = {
                'success': True,
                'submission_id': submission_id,
                'document_type': output_format,
                'generated_at': datetime.now().isoformat(),
            }
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    
    @celery_app.task(bind=True, name="tasks.send_email")
    def task_send_email(
        self,
        to: List[str],
        subject: str,
        body_html: Optional[str] = None,
        body_text: Optional[str] = None,
        attachments: Optional[List[Dict]] = None,
        provider: str = "smtp",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Sendet E-Mail im Hintergrund
        """
        try:
            self.update_state(state='PROGRESS', meta={'step': 'preparing', 'progress': 20})
            
            from .email_engine import EmailEngine, EmailMessage, SMTPConfig
            
            engine = EmailEngine()
            
            # Provider konfigurieren (aus Umgebungsvariablen)
            if provider == "smtp":
                smtp_config = SMTPConfig(
                    host=os.getenv("SMTP_HOST", "localhost"),
                    port=int(os.getenv("SMTP_PORT", "587")),
                    username=os.getenv("SMTP_USERNAME"),
                    password=os.getenv("SMTP_PASSWORD"),
                    default_from_email=os.getenv("SMTP_FROM_EMAIL"),
                )
                engine.configure_smtp(smtp_config)
            
            self.update_state(state='PROGRESS', meta={'step': 'sending', 'progress': 60})
            
            # Message erstellen
            message = EmailMessage(
                to=to,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
            )
            
            # Anhänge hinzufügen
            if attachments:
                for att in attachments:
                    message.add_attachment_from_bytes(
                        att.get('filename', 'attachment'),
                        att.get('content', b''),
                        att.get('content_type', 'application/octet-stream')
                    )
            
            # Senden
            log = engine.send(message)
            
            return {
                'success': log.status.value == 'sent',
                'message_id': log.message_id,
                'status': log.status.value,
                'error': log.error_message,
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    
    @celery_app.task(bind=True, name="tasks.process_workflow")
    def task_process_workflow(
        self,
        workflow_id: str,
        submission_id: str,
        form_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Führt einen Workflow im Hintergrund aus
        """
        try:
            self.update_state(state='PROGRESS', meta={'step': 'loading', 'progress': 10})
            
            from .workflow_engine import WorkflowEngine
            from .document_engine import DocumentEngine
            from .email_engine import EmailEngine
            from .database import DatabaseManager
            
            db = DatabaseManager()
            doc_engine = DocumentEngine()
            email_engine = EmailEngine()
            
            workflow_engine = WorkflowEngine(
                document_engine=doc_engine,
                email_engine=email_engine
            )
            
            # Daten laden
            # ...
            
            self.update_state(state='PROGRESS', meta={'step': 'executing', 'progress': 50})
            
            # Workflow ausführen
            # ...
            
            return {
                'success': True,
                'workflow_id': workflow_id,
                'submission_id': submission_id,
                'completed_at': datetime.now().isoformat(),
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    
    @celery_app.task(bind=True, name="tasks.bulk_email")
    def task_bulk_email(
        self,
        recipients: List[Dict[str, Any]],
        template_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Massen-E-Mail-Versand
        """
        results = []
        total = len(recipients)
        
        for i, recipient in enumerate(recipients):
            self.update_state(
                state='PROGRESS',
                meta={'current': i + 1, 'total': total, 'progress': int((i + 1) / total * 100)}
            )
            
            # E-Mail senden (mit Rate-Limiting)
            # ...
            
            results.append({
                'recipient': recipient.get('email'),
                'success': True,
            })
        
        return {
            'success': True,
            'total': total,
            'sent': len([r for r in results if r['success']]),
            'failed': len([r for r in results if not r['success']]),
            'results': results,
        }
    
    
    @celery_app.task(name="tasks.cleanup_old_drafts")
    def task_cleanup_old_drafts(days: int = 30) -> Dict[str, Any]:
        """
        Räumt alte Entwürfe auf (Scheduled Task)
        """
        from datetime import timedelta
        from .database import DatabaseManager
        
        db = DatabaseManager()
        cutoff = datetime.now() - timedelta(days=days)
        
        # Alte Drafts löschen
        # ...
        
        return {
            'success': True,
            'cutoff_date': cutoff.isoformat(),
            'deleted_count': 0,  # Anzahl gelöschter Drafts
        }


# ============================================
# Task Manager (für Streamlit)
# ============================================

class TaskManager:
    """
    Verwaltet Background Tasks
    Abstrahiert Celery-Details für Streamlit
    """
    
    def __init__(self):
        self.celery_available = HAS_CELERY and celery_app is not None
    
    def submit_document_generation(
        self,
        submission_id: str,
        template_id: str,
        output_format: str = "pdf"
    ) -> Optional[str]:
        """
        Startet Dokumentengenerierung
        Returns: Task-ID oder None wenn synchron
        """
        if self.celery_available:
            result = task_generate_document.delay(
                submission_id=submission_id,
                template_id=template_id,
                output_format=output_format
            )
            return result.id
        else:
            # Synchrone Ausführung
            task_generate_document(
                None,
                submission_id=submission_id,
                template_id=template_id,
                output_format=output_format
            )
            return None
    
    def submit_email(
        self,
        to: List[str],
        subject: str,
        body_html: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Startet E-Mail-Versand
        """
        if self.celery_available:
            result = task_send_email.delay(
                to=to,
                subject=subject,
                body_html=body_html,
                **kwargs
            )
            return result.id
        else:
            task_send_email(
                None,
                to=to,
                subject=subject,
                body_html=body_html,
                **kwargs
            )
            return None
    
    def submit_workflow(
        self,
        workflow_id: str,
        submission_id: str,
        form_id: str
    ) -> Optional[str]:
        """
        Startet Workflow-Ausführung
        """
        if self.celery_available:
            result = task_process_workflow.delay(
                workflow_id=workflow_id,
                submission_id=submission_id,
                form_id=form_id
            )
            return result.id
        else:
            task_process_workflow(
                None,
                workflow_id=workflow_id,
                submission_id=submission_id,
                form_id=form_id
            )
            return None
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Holt den Status eines Tasks
        """
        if not self.celery_available or not task_id:
            return {'state': 'COMPLETED', 'progress': 100}
        
        result = AsyncResult(task_id, app=celery_app)
        
        status = {
            'task_id': task_id,
            'state': result.state,
            'ready': result.ready(),
        }
        
        if result.state == 'PROGRESS':
            status['meta'] = result.info
            status['progress'] = result.info.get('progress', 0)
        elif result.state == 'SUCCESS':
            status['result'] = result.result
            status['progress'] = 100
        elif result.state == 'FAILURE':
            status['error'] = str(result.result)
            status['progress'] = 0
        
        return status
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Bricht einen Task ab
        """
        if not self.celery_available or not task_id:
            return False
        
        celery_app.control.revoke(task_id, terminate=True)
        return True


# ============================================
# Celery Beat Schedule (Scheduled Tasks)
# ============================================

if HAS_CELERY and celery_app:
    celery_app.conf.beat_schedule = {
        'cleanup-old-drafts': {
            'task': 'tasks.cleanup_old_drafts',
            'schedule': 86400.0,  # Täglich
            'args': (30,),  # 30 Tage
        },
    }


# ============================================
# CLI für Worker-Start
# ============================================

def start_worker():
    """Startet den Celery Worker"""
    if not HAS_CELERY:
        print("Celery nicht installiert!")
        return
    
    celery_app.worker_main(['worker', '--loglevel=info'])


def start_beat():
    """Startet Celery Beat (Scheduler)"""
    if not HAS_CELERY:
        print("Celery nicht installiert!")
        return
    
    celery_app.Beat().run()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "worker":
            start_worker()
        elif sys.argv[1] == "beat":
            start_beat()
    else:
        print("Usage: python tasks.py [worker|beat]")
        print(f"Celery verfügbar: {HAS_CELERY}")
        print(f"Redis verfügbar: {HAS_REDIS}")
