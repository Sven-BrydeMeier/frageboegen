"""
Datenbank-Modul
SQLAlchemy ORM für Formulare, Submissions, Dokumente und Logs
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, 
    Boolean, ForeignKey, Enum as SQLEnum, JSON, LargeBinary
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.sql import func

from .form_schema import FormStatus, SubmissionStatus


Base = declarative_base()


# ============================================
# ORM Modelle
# ============================================

class FormTemplate(Base):
    """Formular-Vorlage"""
    __tablename__ = 'form_templates'
    
    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    
    # Schema als JSON
    schema_json = Column(JSON, nullable=False)
    
    # Versionierung
    version = Column(Integer, default=1)
    is_latest = Column(Boolean, default=True)
    parent_id = Column(String(64), ForeignKey('form_templates.id'), nullable=True)
    
    # Status
    status = Column(String(20), default='draft')
    
    # Metadaten
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(String(255))
    
    # Beziehungen
    submissions = relationship("Submission", back_populates="form_template")
    versions = relationship("FormTemplate", backref="parent", remote_side=[id])
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'schema': self.schema_json,
            'version': self.version,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Submission(Base):
    """Formular-Einreichung"""
    __tablename__ = 'submissions'
    
    id = Column(String(64), primary_key=True)
    form_id = Column(String(64), ForeignKey('form_templates.id'), nullable=False)
    form_version = Column(Integer)
    
    # Daten
    data_json = Column(JSON, nullable=False)
    
    # Status
    status = Column(String(20), default='started')
    
    # Metadaten
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    submitted_at = Column(DateTime)
    
    # Benutzer
    created_by = Column(String(255))
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    
    # Beziehungen
    form_template = relationship("FormTemplate", back_populates="submissions")
    uploaded_files = relationship("UploadedFile", back_populates="submission")
    generated_documents = relationship("GeneratedDocument", back_populates="submission")
    email_logs = relationship("EmailLog", back_populates="submission")
    workflow_logs = relationship("WorkflowLog", back_populates="submission")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'form_id': self.form_id,
            'form_version': self.form_version,
            'data': self.data_json,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
        }


class UploadedFile(Base):
    """Hochgeladene Datei"""
    __tablename__ = 'uploaded_files'
    
    id = Column(String(64), primary_key=True)
    submission_id = Column(String(64), ForeignKey('submissions.id'), nullable=False)
    
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255))
    content_type = Column(String(100))
    file_size = Column(Integer)
    
    # Speicherort
    storage_path = Column(String(500))
    storage_url = Column(String(500))
    
    # Integrität
    checksum = Column(String(64))  # SHA-256
    
    # Metadaten
    created_at = Column(DateTime, default=func.now())
    field_id = Column(String(100))  # Welches Formularfeld
    
    # Beziehungen
    submission = relationship("Submission", back_populates="uploaded_files")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'content_type': self.content_type,
            'file_size': self.file_size,
            'checksum': self.checksum,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class GeneratedDocument(Base):
    """Generiertes Dokument"""
    __tablename__ = 'generated_documents'
    
    id = Column(String(64), primary_key=True)
    submission_id = Column(String(64), ForeignKey('submissions.id'), nullable=False)
    
    filename = Column(String(255), nullable=False)
    doc_type = Column(String(20))  # docx, pdf
    template_used = Column(String(255))
    
    # Speicherort
    storage_path = Column(String(500))
    storage_url = Column(String(500))
    file_size = Column(Integer)
    
    # Integrität
    checksum = Column(String(64))  # SHA-256
    
    # Metadaten
    created_at = Column(DateTime, default=func.now())
    generator_version = Column(String(50))
    
    # Beziehungen
    submission = relationship("Submission", back_populates="generated_documents")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'filename': self.filename,
            'doc_type': self.doc_type,
            'template_used': self.template_used,
            'file_size': self.file_size,
            'checksum': self.checksum,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class EmailTemplate(Base):
    """E-Mail-Vorlage"""
    __tablename__ = 'email_templates'
    
    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    
    subject_template = Column(String(500))
    body_template = Column(Text)
    body_html = Column(Boolean, default=True)
    
    # Kategorisierung
    category = Column(String(100))
    language = Column(String(10), default='de')
    
    # Metadaten
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'subject_template': self.subject_template,
            'body_template': self.body_template,
            'category': self.category,
            'language': self.language,
        }


class EmailLog(Base):
    """E-Mail-Versand-Log"""
    __tablename__ = 'email_logs'
    
    id = Column(String(64), primary_key=True)
    submission_id = Column(String(64), ForeignKey('submissions.id'))
    
    # Versand
    provider = Column(String(50))  # smtp, sendgrid, etc.
    message_id = Column(String(255))
    
    # Empfänger
    to_addresses = Column(JSON)
    cc_addresses = Column(JSON)
    bcc_addresses = Column(JSON)
    
    # Inhalt (Metadaten)
    subject = Column(String(500))
    content_hash = Column(String(64))
    attachment_count = Column(Integer, default=0)
    
    # Status
    status = Column(String(20))  # sent, failed, bounced
    error_message = Column(Text)
    
    # Metadaten
    created_at = Column(DateTime, default=func.now())
    sent_at = Column(DateTime)
    
    # Beziehungen
    submission = relationship("Submission", back_populates="email_logs")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'provider': self.provider,
            'message_id': self.message_id,
            'to': self.to_addresses,
            'subject': self.subject,
            'status': self.status,
            'error_message': self.error_message,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
        }


class WorkflowLog(Base):
    """Workflow-Ausführungs-Log"""
    __tablename__ = 'workflow_logs'
    
    id = Column(String(64), primary_key=True)
    submission_id = Column(String(64), ForeignKey('submissions.id'), nullable=False)
    
    workflow_id = Column(String(64))
    workflow_name = Column(String(255))
    
    # Status
    status = Column(String(20))
    
    # Details
    action_results = Column(JSON)
    
    # Metadaten
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Beziehungen
    submission = relationship("Submission", back_populates="workflow_logs")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'workflow_id': self.workflow_id,
            'workflow_name': self.workflow_name,
            'status': self.status,
            'action_results': self.action_results,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class User(Base):
    """Benutzer"""
    __tablename__ = 'users'
    
    id = Column(String(64), primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True)
    password_hash = Column(String(255))
    
    # Profil
    full_name = Column(String(255))
    role = Column(String(50), default='user')  # admin, user, readonly
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Metadaten
    created_at = Column(DateTime, default=func.now())
    last_login = Column(DateTime)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'is_active': self.is_active,
        }


class AuditLog(Base):
    """Audit-Log für alle Änderungen"""
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Was
    entity_type = Column(String(50))  # form, submission, user, etc.
    entity_id = Column(String(64))
    action = Column(String(50))  # create, update, delete, view
    
    # Details
    changes = Column(JSON)
    old_values = Column(JSON)
    new_values = Column(JSON)
    
    # Wer
    user_id = Column(String(64))
    user_name = Column(String(255))
    ip_address = Column(String(45))
    
    # Wann
    created_at = Column(DateTime, default=func.now())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'action': self.action,
            'user_name': self.user_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ============================================
# Database Manager
# ============================================

class DatabaseManager:
    """Verwaltet die Datenbankverbindung und Operationen"""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or "sqlite:///data/formular_system.db"
        
        # Verzeichnis erstellen
        if self.database_url.startswith("sqlite:///"):
            db_path = Path(self.database_url.replace("sqlite:///", ""))
            db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.engine = create_engine(self.database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def create_tables(self):
        """Erstellt alle Tabellen"""
        Base.metadata.create_all(self.engine)
    
    def get_session(self) -> Session:
        """Gibt eine neue Session zurück"""
        return self.SessionLocal()
    
    # ========================================
    # Form Template Operations
    # ========================================
    
    def save_form_template(self, form_data: Dict[str, Any], user_id: Optional[str] = None) -> FormTemplate:
        """Speichert ein Formular-Template"""
        session = self.get_session()
        try:
            template = FormTemplate(
                id=form_data.get('id'),
                name=form_data.get('name'),
                title=form_data.get('title'),
                description=form_data.get('description'),
                category=form_data.get('category'),
                schema_json=form_data,
                version=form_data.get('version', 1),
                status=form_data.get('status', 'draft'),
                created_by=user_id,
            )
            session.merge(template)
            session.commit()
            
            self._audit_log(session, 'form', template.id, 'save', user_id)
            
            return template
        finally:
            session.close()
    
    def get_form_template(self, form_id: str) -> Optional[FormTemplate]:
        """Lädt ein Formular-Template"""
        session = self.get_session()
        try:
            return session.query(FormTemplate).filter(FormTemplate.id == form_id).first()
        finally:
            session.close()
    
    def get_all_form_templates(self, status: Optional[str] = None) -> List[FormTemplate]:
        """Lädt alle Formular-Templates"""
        session = self.get_session()
        try:
            query = session.query(FormTemplate)
            if status:
                query = query.filter(FormTemplate.status == status)
            return query.order_by(FormTemplate.updated_at.desc()).all()
        finally:
            session.close()
    
    def delete_form_template(self, form_id: str, user_id: Optional[str] = None):
        """Löscht ein Formular-Template (setzt Status auf archived)"""
        session = self.get_session()
        try:
            template = session.query(FormTemplate).filter(FormTemplate.id == form_id).first()
            if template:
                template.status = 'archived'
                session.commit()
                self._audit_log(session, 'form', form_id, 'delete', user_id)
        finally:
            session.close()
    
    # ========================================
    # Submission Operations
    # ========================================
    
    def save_submission(self, submission_data: Dict[str, Any], user_id: Optional[str] = None) -> Submission:
        """Speichert eine Submission"""
        session = self.get_session()
        try:
            submission = Submission(
                id=submission_data.get('id'),
                form_id=submission_data.get('form_id'),
                form_version=submission_data.get('form_version'),
                data_json=submission_data.get('data', {}),
                status=submission_data.get('status', 'started'),
                created_by=user_id,
                ip_address=submission_data.get('ip_address'),
                user_agent=submission_data.get('user_agent'),
            )
            session.merge(submission)
            session.commit()
            
            self._audit_log(session, 'submission', submission.id, 'save', user_id)
            
            return submission
        finally:
            session.close()
    
    def get_submission(self, submission_id: str) -> Optional[Submission]:
        """Lädt eine Submission"""
        session = self.get_session()
        try:
            return session.query(Submission).filter(Submission.id == submission_id).first()
        finally:
            session.close()
    
    def get_submissions_for_form(self, form_id: str, limit: int = 100) -> List[Submission]:
        """Lädt alle Submissions für ein Formular"""
        session = self.get_session()
        try:
            return session.query(Submission)\
                .filter(Submission.form_id == form_id)\
                .order_by(Submission.created_at.desc())\
                .limit(limit)\
                .all()
        finally:
            session.close()
    
    def update_submission_status(self, submission_id: str, status: str, user_id: Optional[str] = None):
        """Aktualisiert den Status einer Submission"""
        session = self.get_session()
        try:
            submission = session.query(Submission).filter(Submission.id == submission_id).first()
            if submission:
                old_status = submission.status
                submission.status = status
                if status == 'submitted':
                    submission.submitted_at = datetime.now()
                session.commit()
                
                self._audit_log(
                    session, 'submission', submission_id, 'update_status', user_id,
                    {'old_status': old_status, 'new_status': status}
                )
        finally:
            session.close()
    
    # ========================================
    # Document Operations
    # ========================================
    
    def save_generated_document(self, doc_data: Dict[str, Any]) -> GeneratedDocument:
        """Speichert ein generiertes Dokument"""
        session = self.get_session()
        try:
            doc = GeneratedDocument(
                id=doc_data.get('id'),
                submission_id=doc_data.get('submission_id'),
                filename=doc_data.get('filename'),
                doc_type=doc_data.get('doc_type'),
                template_used=doc_data.get('template_used'),
                storage_path=doc_data.get('storage_path'),
                file_size=doc_data.get('file_size'),
                checksum=doc_data.get('checksum'),
            )
            session.merge(doc)
            session.commit()
            return doc
        finally:
            session.close()
    
    def save_uploaded_file(self, file_data: Dict[str, Any]) -> UploadedFile:
        """Speichert eine hochgeladene Datei"""
        session = self.get_session()
        try:
            file = UploadedFile(
                id=file_data.get('id'),
                submission_id=file_data.get('submission_id'),
                filename=file_data.get('filename'),
                original_filename=file_data.get('original_filename'),
                content_type=file_data.get('content_type'),
                file_size=file_data.get('file_size'),
                storage_path=file_data.get('storage_path'),
                checksum=file_data.get('checksum'),
                field_id=file_data.get('field_id'),
            )
            session.merge(file)
            session.commit()
            return file
        finally:
            session.close()
    
    # ========================================
    # Audit Logging
    # ========================================
    
    def _audit_log(
        self,
        session: Session,
        entity_type: str,
        entity_id: str,
        action: str,
        user_id: Optional[str] = None,
        changes: Optional[Dict] = None
    ):
        """Erstellt einen Audit-Log-Eintrag"""
        log = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=user_id,
            changes=changes,
        )
        session.add(log)
        session.commit()
    
    def get_audit_logs(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """Lädt Audit-Logs"""
        session = self.get_session()
        try:
            query = session.query(AuditLog)
            if entity_type:
                query = query.filter(AuditLog.entity_type == entity_type)
            if entity_id:
                query = query.filter(AuditLog.entity_id == entity_id)
            return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
        finally:
            session.close()
    
    # ========================================
    # Search
    # ========================================
    
    def search_submissions(
        self,
        form_id: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        search_text: Optional[str] = None,
        limit: int = 100
    ) -> List[Submission]:
        """Sucht Submissions nach Kriterien"""
        session = self.get_session()
        try:
            query = session.query(Submission)
            
            if form_id:
                query = query.filter(Submission.form_id == form_id)
            if status:
                query = query.filter(Submission.status == status)
            if date_from:
                query = query.filter(Submission.created_at >= date_from)
            if date_to:
                query = query.filter(Submission.created_at <= date_to)
            
            # Textsuche in JSON (SQLite-spezifisch)
            if search_text and self.database_url.startswith("sqlite"):
                query = query.filter(
                    Submission.data_json.cast(String).contains(search_text)
                )
            
            return query.order_by(Submission.created_at.desc()).limit(limit).all()
        finally:
            session.close()


if __name__ == "__main__":
    # Test
    db = DatabaseManager()
    db.create_tables()
    print("Datenbank-Tabellen erstellt")
