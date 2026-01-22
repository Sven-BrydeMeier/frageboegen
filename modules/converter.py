"""
Dokumenten-Konvertierung
DOCX → PDF und andere Formate mit LibreOffice/unoconv
"""

import os
import subprocess
import tempfile
import shutil
from typing import Optional, Union, List, Dict, Any
from pathlib import Path
from enum import Enum
import time


class OutputFormat(str, Enum):
    """Unterstützte Ausgabeformate"""
    PDF = "pdf"
    HTML = "html"
    TXT = "txt"
    ODT = "odt"
    RTF = "rtf"
    DOCX = "docx"
    PNG = "png"  # Erste Seite als Bild


class ConversionMethod(str, Enum):
    """Konvertierungsmethode"""
    LIBREOFFICE = "libreoffice"
    UNOCONV = "unoconv"
    PANDOC = "pandoc"


def find_libreoffice() -> Optional[str]:
    """Findet LibreOffice Installation"""
    possible_paths = [
        "/usr/bin/libreoffice",
        "/usr/bin/soffice",
        "/usr/local/bin/libreoffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    
    # Erst über PATH suchen
    for cmd in ["libreoffice", "soffice"]:
        path = shutil.which(cmd)
        if path:
            return path
    
    # Dann bekannte Pfade
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None


def find_unoconv() -> Optional[str]:
    """Findet unoconv"""
    return shutil.which("unoconv")


def find_pandoc() -> Optional[str]:
    """Findet pandoc"""
    return shutil.which("pandoc")


class DocumentConverter:
    """
    Dokumenten-Konverter
    
    Unterstützt verschiedene Backends:
    - LibreOffice (empfohlen)
    - unoconv
    - pandoc (eingeschränkt)
    """
    
    def __init__(
        self,
        method: Optional[ConversionMethod] = None,
        timeout: int = 120,
        temp_dir: Optional[str] = None,
    ):
        """
        Args:
            method: Konvertierungsmethode (auto-detect wenn None)
            timeout: Timeout in Sekunden
            temp_dir: Temporäres Verzeichnis
        """
        self.timeout = timeout
        self.temp_dir = temp_dir or tempfile.gettempdir()
        
        # Auto-detect
        if method is None:
            if find_libreoffice():
                self.method = ConversionMethod.LIBREOFFICE
            elif find_unoconv():
                self.method = ConversionMethod.UNOCONV
            elif find_pandoc():
                self.method = ConversionMethod.PANDOC
            else:
                raise RuntimeError(
                    "Kein Konverter gefunden. Bitte installieren:\n"
                    "- LibreOffice: apt install libreoffice\n"
                    "- oder unoconv: apt install unoconv\n"
                    "- oder pandoc: apt install pandoc"
                )
        else:
            self.method = method
        
        # Pfade speichern
        self.libreoffice_path = find_libreoffice()
        self.unoconv_path = find_unoconv()
        self.pandoc_path = find_pandoc()
    
    def convert(
        self,
        input_path: Union[str, Path],
        output_format: OutputFormat = OutputFormat.PDF,
        output_path: Optional[Union[str, Path]] = None,
    ) -> bytes:
        """
        Konvertiert ein Dokument
        
        Args:
            input_path: Eingabedatei
            output_format: Zielformat
            output_path: Optionaler Ausgabepfad
        
        Returns:
            Konvertiertes Dokument als Bytes
        """
        input_path = Path(input_path)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Datei nicht gefunden: {input_path}")
        
        # Ausgabepfad bestimmen
        if output_path:
            output_path = Path(output_path)
        else:
            output_path = Path(self.temp_dir) / f"{input_path.stem}.{output_format.value}"
        
        # Konvertieren
        if self.method == ConversionMethod.LIBREOFFICE:
            self._convert_libreoffice(input_path, output_path, output_format)
        elif self.method == ConversionMethod.UNOCONV:
            self._convert_unoconv(input_path, output_path, output_format)
        elif self.method == ConversionMethod.PANDOC:
            self._convert_pandoc(input_path, output_path, output_format)
        
        # Ergebnis lesen
        with open(output_path, 'rb') as f:
            result = f.read()
        
        # Temporäre Datei löschen (wenn nicht explizit angegeben)
        if not output_path:
            os.unlink(output_path)
        
        return result
    
    def convert_bytes(
        self,
        data: bytes,
        input_format: str,
        output_format: OutputFormat = OutputFormat.PDF,
    ) -> bytes:
        """
        Konvertiert Bytes
        
        Args:
            data: Eingabedaten
            input_format: Eingabeformat (z.B. "docx")
            output_format: Zielformat
        
        Returns:
            Konvertiertes Dokument
        """
        # Temporäre Eingabedatei erstellen
        with tempfile.NamedTemporaryFile(
            suffix=f".{input_format}",
            delete=False
        ) as f:
            f.write(data)
            input_path = f.name
        
        try:
            return self.convert(input_path, output_format)
        finally:
            os.unlink(input_path)
    
    def _convert_libreoffice(
        self,
        input_path: Path,
        output_path: Path,
        output_format: OutputFormat
    ):
        """Konvertiert mit LibreOffice"""
        # Output-Verzeichnis
        outdir = output_path.parent
        
        # LibreOffice Kommando
        cmd = [
            self.libreoffice_path,
            "--headless",
            "--invisible",
            "--nodefault",
            "--nofirststartwizard",
            "--nolockcheck",
            "--nologo",
            "--norestore",
            f"--convert-to", output_format.value,
            "--outdir", str(outdir),
            str(input_path)
        ]
        
        # Umgebungsvariablen für bessere Isolation
        env = os.environ.copy()
        env["HOME"] = self.temp_dir  # Eigenes Home für Profile
        
        # Ausführen
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.timeout,
                env=env,
                cwd=self.temp_dir,
            )
            
            if result.returncode != 0:
                raise RuntimeError(
                    f"LibreOffice Fehler: {result.stderr.decode()}"
                )
            
            # LibreOffice benennt Output nach Input-Name
            expected_output = outdir / f"{input_path.stem}.{output_format.value}"
            
            # Umbenennen wenn nötig
            if expected_output != output_path and expected_output.exists():
                shutil.move(str(expected_output), str(output_path))
                
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Konvertierung dauerte länger als {self.timeout}s")
    
    def _convert_unoconv(
        self,
        input_path: Path,
        output_path: Path,
        output_format: OutputFormat
    ):
        """Konvertiert mit unoconv"""
        cmd = [
            self.unoconv_path,
            "-f", output_format.value,
            "-o", str(output_path),
            str(input_path)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.timeout,
            )
            
            if result.returncode != 0:
                raise RuntimeError(
                    f"unoconv Fehler: {result.stderr.decode()}"
                )
                
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Konvertierung dauerte länger als {self.timeout}s")
    
    def _convert_pandoc(
        self,
        input_path: Path,
        output_path: Path,
        output_format: OutputFormat
    ):
        """Konvertiert mit pandoc (eingeschränkt)"""
        # Pandoc unterstützt nicht alle Formate direkt
        if output_format == OutputFormat.PDF:
            # PDF braucht LaTeX
            cmd = [
                self.pandoc_path,
                str(input_path),
                "-o", str(output_path),
                "--pdf-engine=xelatex"
            ]
        else:
            cmd = [
                self.pandoc_path,
                str(input_path),
                "-o", str(output_path)
            ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.timeout,
            )
            
            if result.returncode != 0:
                raise RuntimeError(
                    f"pandoc Fehler: {result.stderr.decode()}"
                )
                
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Konvertierung dauerte länger als {self.timeout}s")
    
    @property
    def info(self) -> Dict[str, Any]:
        """Informationen über verfügbare Konverter"""
        return {
            'method': self.method.value,
            'libreoffice': self.libreoffice_path,
            'unoconv': self.unoconv_path,
            'pandoc': self.pandoc_path,
            'timeout': self.timeout,
        }


# ============================================
# Convenience Functions
# ============================================

def docx_to_pdf(
    docx_data: bytes,
    timeout: int = 60
) -> bytes:
    """
    Konvertiert DOCX zu PDF
    
    Args:
        docx_data: DOCX als Bytes
        timeout: Timeout in Sekunden
    
    Returns:
        PDF als Bytes
    """
    converter = DocumentConverter(timeout=timeout)
    return converter.convert_bytes(docx_data, "docx", OutputFormat.PDF)


def xlsx_to_pdf(
    xlsx_data: bytes,
    timeout: int = 60
) -> bytes:
    """Konvertiert XLSX zu PDF"""
    converter = DocumentConverter(timeout=timeout)
    return converter.convert_bytes(xlsx_data, "xlsx", OutputFormat.PDF)


def pptx_to_pdf(
    pptx_data: bytes,
    timeout: int = 60
) -> bytes:
    """Konvertiert PPTX zu PDF"""
    converter = DocumentConverter(timeout=timeout)
    return converter.convert_bytes(pptx_data, "pptx", OutputFormat.PDF)


def html_to_pdf(
    html_data: bytes,
    timeout: int = 60
) -> bytes:
    """Konvertiert HTML zu PDF"""
    converter = DocumentConverter(timeout=timeout)
    return converter.convert_bytes(html_data, "html", OutputFormat.PDF)


# ============================================
# Batch Conversion
# ============================================

class BatchConverter:
    """
    Stapel-Konvertierung mehrerer Dokumente
    """
    
    def __init__(
        self,
        converter: Optional[DocumentConverter] = None,
        parallel: int = 1,
    ):
        self.converter = converter or DocumentConverter()
        self.parallel = parallel
    
    def convert_directory(
        self,
        input_dir: Union[str, Path],
        output_dir: Union[str, Path],
        input_formats: List[str] = None,
        output_format: OutputFormat = OutputFormat.PDF,
    ) -> List[Dict[str, Any]]:
        """
        Konvertiert alle Dateien in einem Verzeichnis
        """
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if input_formats is None:
            input_formats = ['docx', 'doc', 'xlsx', 'xls', 'pptx', 'ppt', 'odt', 'ods', 'odp']
        
        results = []
        
        for ext in input_formats:
            for input_file in input_dir.glob(f"*.{ext}"):
                output_file = output_dir / f"{input_file.stem}.{output_format.value}"
                
                try:
                    start_time = time.time()
                    self.converter.convert(input_file, output_format, output_file)
                    
                    results.append({
                        'input': str(input_file),
                        'output': str(output_file),
                        'success': True,
                        'time': time.time() - start_time,
                    })
                except Exception as e:
                    results.append({
                        'input': str(input_file),
                        'output': str(output_file),
                        'success': False,
                        'error': str(e),
                    })
        
        return results


# ============================================
# CLI
# ============================================

if __name__ == "__main__":
    import sys
    
    print("Dokumenten-Konverter")
    print("=" * 40)
    print(f"LibreOffice: {find_libreoffice() or 'Nicht gefunden'}")
    print(f"unoconv: {find_unoconv() or 'Nicht gefunden'}")
    print(f"pandoc: {find_pandoc() or 'Nicht gefunden'}")
    
    if len(sys.argv) > 2:
        input_file = sys.argv[1]
        output_format = sys.argv[2]
        
        try:
            converter = DocumentConverter()
            result = converter.convert(
                input_file,
                OutputFormat(output_format)
            )
            
            output_file = f"{Path(input_file).stem}.{output_format}"
            with open(output_file, 'wb') as f:
                f.write(result)
            
            print(f"✅ Konvertiert: {output_file}")
            
        except Exception as e:
            print(f"❌ Fehler: {e}")
    else:
        print("\nUsage: python converter.py <input> <format>")
        print("Beispiel: python converter.py dokument.docx pdf")
