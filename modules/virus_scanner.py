"""
Virenscan für Datei-Uploads
Integration mit ClamAV (Open Source Antivirus)
"""

import os
import io
import socket
import struct
import hashlib
from typing import Dict, Any, Optional, Tuple, Union
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# ClamAV Daemon
try:
    import clamd
    HAS_CLAMD = True
except ImportError:
    HAS_CLAMD = False


class ScanResult(str, Enum):
    """Ergebnis eines Virenscans"""
    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class ScanReport:
    """Bericht eines Virenscans"""
    result: ScanResult
    filename: str
    file_hash: str  # SHA-256
    file_size: int
    scan_time: float  # Sekunden
    scanned_at: datetime
    threat_name: Optional[str] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'result': self.result.value,
            'filename': self.filename,
            'file_hash': self.file_hash,
            'file_size': self.file_size,
            'scan_time': self.scan_time,
            'scanned_at': self.scanned_at.isoformat(),
            'threat_name': self.threat_name,
            'error_message': self.error_message,
        }
    
    @property
    def is_safe(self) -> bool:
        return self.result == ScanResult.CLEAN


class VirusScanner:
    """
    Virenscan mit ClamAV
    
    ClamAV muss installiert und der Daemon (clamd) laufen:
    - Ubuntu: sudo apt install clamav clamav-daemon
    - Start: sudo systemctl start clamav-daemon
    
    Alternativ kann auch ein Remote-ClamAV verwendet werden.
    """
    
    def __init__(
        self,
        socket_path: str = "/var/run/clamav/clamd.ctl",
        host: Optional[str] = None,
        port: int = 3310,
        timeout: int = 60,
        max_file_size: int = 100 * 1024 * 1024,  # 100 MB
    ):
        """
        Args:
            socket_path: Unix Socket Pfad (lokal)
            host: Hostname für Remote-ClamAV
            port: Port für Remote-ClamAV
            timeout: Timeout in Sekunden
            max_file_size: Maximale Dateigröße für Scan
        """
        self.socket_path = socket_path
        self.host = host
        self.port = port
        self.timeout = timeout
        self.max_file_size = max_file_size
        
        self._client = None
    
    def _get_client(self):
        """Erstellt ClamAV Client"""
        if not HAS_CLAMD:
            raise ImportError("clamd ist nicht installiert: pip install clamd")
        
        if self._client:
            return self._client
        
        if self.host:
            # Remote-ClamAV
            self._client = clamd.ClamdNetworkSocket(
                host=self.host,
                port=self.port,
                timeout=self.timeout
            )
        else:
            # Lokaler Unix Socket
            self._client = clamd.ClamdUnixSocket(
                path=self.socket_path,
                timeout=self.timeout
            )
        
        return self._client
    
    def ping(self) -> bool:
        """Prüft ob ClamAV erreichbar ist"""
        try:
            client = self._get_client()
            return client.ping() == "PONG"
        except Exception:
            return False
    
    def get_version(self) -> str:
        """Holt ClamAV Version"""
        try:
            client = self._get_client()
            return client.version()
        except Exception as e:
            return f"Fehler: {e}"
    
    def scan_bytes(
        self,
        data: bytes,
        filename: str = "upload"
    ) -> ScanReport:
        """
        Scannt Bytes auf Viren
        
        Args:
            data: Dateiinhalt als Bytes
            filename: Name der Datei (für Report)
        
        Returns:
            ScanReport
        """
        import time
        start_time = time.time()
        
        # Hash berechnen
        file_hash = hashlib.sha256(data).hexdigest()
        file_size = len(data)
        
        # Größenprüfung
        if file_size > self.max_file_size:
            return ScanReport(
                result=ScanResult.SKIPPED,
                filename=filename,
                file_hash=file_hash,
                file_size=file_size,
                scan_time=time.time() - start_time,
                scanned_at=datetime.now(),
                error_message=f"Datei zu groß ({file_size} > {self.max_file_size})"
            )
        
        try:
            client = self._get_client()
            
            # Stream-Scan
            result = client.instream(io.BytesIO(data))
            
            scan_time = time.time() - start_time
            
            # Ergebnis parsen
            # Format: {'stream': ('OK', None)} oder {'stream': ('FOUND', 'Virus.Name')}
            status = result.get('stream', ('ERROR', 'Unknown'))
            
            if status[0] == 'OK':
                return ScanReport(
                    result=ScanResult.CLEAN,
                    filename=filename,
                    file_hash=file_hash,
                    file_size=file_size,
                    scan_time=scan_time,
                    scanned_at=datetime.now(),
                )
            elif status[0] == 'FOUND':
                return ScanReport(
                    result=ScanResult.INFECTED,
                    filename=filename,
                    file_hash=file_hash,
                    file_size=file_size,
                    scan_time=scan_time,
                    scanned_at=datetime.now(),
                    threat_name=status[1],
                )
            else:
                return ScanReport(
                    result=ScanResult.ERROR,
                    filename=filename,
                    file_hash=file_hash,
                    file_size=file_size,
                    scan_time=scan_time,
                    scanned_at=datetime.now(),
                    error_message=str(status),
                )
                
        except Exception as e:
            return ScanReport(
                result=ScanResult.ERROR,
                filename=filename,
                file_hash=file_hash,
                file_size=file_size,
                scan_time=time.time() - start_time,
                scanned_at=datetime.now(),
                error_message=str(e),
            )
    
    def scan_file(self, filepath: Union[str, Path]) -> ScanReport:
        """
        Scannt eine Datei auf Viren
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            return ScanReport(
                result=ScanResult.ERROR,
                filename=filepath.name,
                file_hash="",
                file_size=0,
                scan_time=0,
                scanned_at=datetime.now(),
                error_message="Datei nicht gefunden",
            )
        
        with open(filepath, 'rb') as f:
            data = f.read()
        
        return self.scan_bytes(data, filepath.name)
    
    def scan_streamlit_upload(self, uploaded_file) -> ScanReport:
        """
        Scannt einen Streamlit UploadedFile
        """
        data = uploaded_file.getvalue()
        return self.scan_bytes(data, uploaded_file.name)


# ============================================
# Fallback Scanner (ohne ClamAV)
# ============================================

class SimpleFileChecker:
    """
    Einfache Dateiprüfung ohne ClamAV
    Prüft auf verdächtige Muster und Dateitypen
    """
    
    # Gefährliche Dateierweiterungen
    DANGEROUS_EXTENSIONS = {
        '.exe', '.dll', '.bat', '.cmd', '.com', '.msi',
        '.vbs', '.vbe', '.js', '.jse', '.ws', '.wsf',
        '.scr', '.pif', '.hta', '.cpl', '.msc', '.jar',
        '.ps1', '.psm1', '.reg', '.inf', '.scf',
    }
    
    # Erlaubte Erweiterungen für Formulare
    ALLOWED_EXTENSIONS = {
        '.pdf', '.doc', '.docx', '.xls', '.xlsx',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff',
        '.txt', '.csv', '.rtf', '.odt', '.ods',
    }
    
    # Verdächtige Byte-Sequenzen (Magic Bytes)
    SUSPICIOUS_PATTERNS = [
        b'MZ',  # Windows Executable
        b'PK\x03\x04',  # ZIP (kann gefährlich sein)
        b'<%@ ',  # ASP
        b'<?php',  # PHP
        b'<script',  # JavaScript
    ]
    
    def __init__(self, strict_mode: bool = True):
        """
        Args:
            strict_mode: Wenn True, nur erlaubte Erweiterungen akzeptieren
        """
        self.strict_mode = strict_mode
    
    def check_extension(self, filename: str) -> Tuple[bool, str]:
        """Prüft Dateierweiterung"""
        ext = Path(filename).suffix.lower()
        
        if ext in self.DANGEROUS_EXTENSIONS:
            return False, f"Gefährliche Dateierweiterung: {ext}"
        
        if self.strict_mode and ext not in self.ALLOWED_EXTENSIONS:
            return False, f"Dateityp nicht erlaubt: {ext}"
        
        return True, ""
    
    def check_content(self, data: bytes, filename: str) -> Tuple[bool, str]:
        """Prüft Dateiinhalt auf verdächtige Muster"""
        # Magic Bytes prüfen
        for pattern in self.SUSPICIOUS_PATTERNS:
            if data.startswith(pattern):
                # Einige Ausnahmen
                if pattern == b'PK\x03\x04':
                    ext = Path(filename).suffix.lower()
                    if ext in {'.docx', '.xlsx', '.pptx', '.odt', '.ods'}:
                        continue  # Office-Dateien sind ZIP-basiert
                
                return False, f"Verdächtiger Dateiinhalt erkannt"
        
        return True, ""
    
    def check_file(self, data: bytes, filename: str) -> ScanReport:
        """
        Führt alle Prüfungen durch
        """
        import time
        start_time = time.time()
        
        file_hash = hashlib.sha256(data).hexdigest()
        file_size = len(data)
        
        # Extension prüfen
        ext_ok, ext_msg = self.check_extension(filename)
        if not ext_ok:
            return ScanReport(
                result=ScanResult.INFECTED,
                filename=filename,
                file_hash=file_hash,
                file_size=file_size,
                scan_time=time.time() - start_time,
                scanned_at=datetime.now(),
                threat_name="DangerousFileType",
                error_message=ext_msg,
            )
        
        # Content prüfen
        content_ok, content_msg = self.check_content(data, filename)
        if not content_ok:
            return ScanReport(
                result=ScanResult.INFECTED,
                filename=filename,
                file_hash=file_hash,
                file_size=file_size,
                scan_time=time.time() - start_time,
                scanned_at=datetime.now(),
                threat_name="SuspiciousContent",
                error_message=content_msg,
            )
        
        return ScanReport(
            result=ScanResult.CLEAN,
            filename=filename,
            file_hash=file_hash,
            file_size=file_size,
            scan_time=time.time() - start_time,
            scanned_at=datetime.now(),
        )


# ============================================
# Unified Scanner Interface
# ============================================

class FileScanner:
    """
    Einheitliche Schnittstelle für Datei-Scans
    Verwendet ClamAV wenn verfügbar, sonst Fallback
    """
    
    def __init__(
        self,
        use_clamav: bool = True,
        clamav_socket: str = "/var/run/clamav/clamd.ctl",
        clamav_host: Optional[str] = None,
        clamav_port: int = 3310,
        strict_mode: bool = True,
    ):
        self.use_clamav = use_clamav and HAS_CLAMD
        self.strict_mode = strict_mode
        
        if self.use_clamav:
            self.scanner = VirusScanner(
                socket_path=clamav_socket,
                host=clamav_host,
                port=clamav_port,
            )
            # Prüfen ob erreichbar
            if not self.scanner.ping():
                self.use_clamav = False
        
        self.fallback = SimpleFileChecker(strict_mode=strict_mode)
    
    def scan(self, data: bytes, filename: str) -> ScanReport:
        """
        Scannt eine Datei
        """
        # Immer erst Fallback-Prüfung
        fallback_result = self.fallback.check_file(data, filename)
        if not fallback_result.is_safe:
            return fallback_result
        
        # Dann ClamAV wenn verfügbar
        if self.use_clamav:
            return self.scanner.scan_bytes(data, filename)
        
        return fallback_result
    
    def scan_streamlit_upload(self, uploaded_file) -> ScanReport:
        """Scannt einen Streamlit Upload"""
        data = uploaded_file.getvalue()
        return self.scan(data, uploaded_file.name)
    
    @property
    def scanner_info(self) -> Dict[str, Any]:
        """Informationen über den Scanner"""
        info = {
            'clamav_available': HAS_CLAMD,
            'clamav_active': self.use_clamav,
            'strict_mode': self.strict_mode,
        }
        
        if self.use_clamav:
            info['clamav_version'] = self.scanner.get_version()
        
        return info


# ============================================
# Streamlit Integration
# ============================================

def render_scan_result(report: ScanReport):
    """Rendert Scan-Ergebnis in Streamlit"""
    import streamlit as st
    
    if report.result == ScanResult.CLEAN:
        st.success(f"✅ **{report.filename}** - Keine Bedrohung erkannt")
    elif report.result == ScanResult.INFECTED:
        st.error(f"🦠 **{report.filename}** - Bedrohung erkannt: {report.threat_name}")
    elif report.result == ScanResult.ERROR:
        st.warning(f"⚠️ **{report.filename}** - Scan-Fehler: {report.error_message}")
    else:
        st.info(f"⏭️ **{report.filename}** - Übersprungen: {report.error_message}")
    
    with st.expander("Details"):
        st.write(f"**Hash (SHA-256):** `{report.file_hash[:16]}...`")
        st.write(f"**Größe:** {report.file_size:,} Bytes")
        st.write(f"**Scan-Zeit:** {report.scan_time:.3f}s")


if __name__ == "__main__":
    print(f"ClamAV (clamd) verfügbar: {HAS_CLAMD}")
    
    # Test
    scanner = FileScanner(use_clamav=False)
    
    # Test mit normalem Text
    report = scanner.scan(b"Hello World", "test.txt")
    print(f"test.txt: {report.result.value}")
    
    # Test mit verdächtiger Datei
    report = scanner.scan(b"MZ...", "test.exe")
    print(f"test.exe: {report.result.value}")
