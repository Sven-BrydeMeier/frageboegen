"""
PDF-Formular-Befüllung
Befüllt bestehende PDF-Formulare (AcroForm) mit Daten
"""

import io
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, BooleanObject, TextStringObject
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False


class PDFFormFiller:
    """Befüllt PDF-Formulare (AcroForm)"""
    
    def __init__(self):
        if not HAS_PYPDF:
            raise ImportError("pypdf ist nicht installiert: pip install pypdf")
    
    def get_form_fields(self, pdf_path: Union[str, Path, bytes]) -> Dict[str, Dict[str, Any]]:
        """
        Liest alle Formularfelder aus einem PDF
        
        Returns:
            Dict mit Feldnamen und deren Eigenschaften
        """
        if isinstance(pdf_path, bytes):
            reader = PdfReader(io.BytesIO(pdf_path))
        else:
            reader = PdfReader(str(pdf_path))
        
        fields = {}
        
        if reader.get_fields():
            for field_name, field_data in reader.get_fields().items():
                field_type = field_data.get('/FT', '')
                if hasattr(field_type, 'name'):
                    field_type = field_type.name
                
                fields[field_name] = {
                    'type': str(field_type),
                    'value': field_data.get('/V', ''),
                    'default': field_data.get('/DV', ''),
                    'options': self._get_field_options(field_data),
                    'required': bool(field_data.get('/Ff', 0) & 2),
                    'readonly': bool(field_data.get('/Ff', 0) & 1),
                }
        
        return fields
    
    def _get_field_options(self, field_data: Dict) -> List[str]:
        """Extrahiert Optionen aus Select/Radio-Feldern"""
        options = []
        opt = field_data.get('/Opt', [])
        if opt:
            for o in opt:
                if isinstance(o, list):
                    options.append(str(o[1]) if len(o) > 1 else str(o[0]))
                else:
                    options.append(str(o))
        return options
    
    def fill_form(
        self,
        pdf_path: Union[str, Path, bytes],
        data: Dict[str, Any],
        output_path: Optional[Union[str, Path]] = None,
        flatten: bool = False
    ) -> bytes:
        """
        Befüllt ein PDF-Formular mit Daten
        
        Args:
            pdf_path: Pfad zum PDF oder Bytes
            data: Dict mit Feldname -> Wert
            output_path: Optionaler Ausgabepfad
            flatten: Wenn True, werden Formularfelder "eingefroren" (nicht mehr editierbar)
        
        Returns:
            Befülltes PDF als Bytes
        """
        if isinstance(pdf_path, bytes):
            reader = PdfReader(io.BytesIO(pdf_path))
        else:
            reader = PdfReader(str(pdf_path))
        
        writer = PdfWriter()
        
        # Alle Seiten kopieren
        for page in reader.pages:
            writer.add_page(page)
        
        # Formularfelder befüllen
        if reader.get_fields():
            writer.update_page_form_field_values(
                writer.pages[0],  # Meist sind Felder auf der ersten Seite
                data,
                auto_regenerate=True
            )
        
        # Alternativ: Felder auf allen Seiten aktualisieren
        for page_num in range(len(writer.pages)):
            try:
                writer.update_page_form_field_values(
                    writer.pages[page_num],
                    data,
                    auto_regenerate=True
                )
            except:
                pass
        
        # Flatten wenn gewünscht
        if flatten:
            for page in writer.pages:
                if "/Annots" in page:
                    for annot in page["/Annots"]:
                        annot_obj = annot.get_object()
                        if annot_obj.get("/Subtype") == "/Widget":
                            # Feld-Flags setzen um es "einzufrieren"
                            annot_obj[NameObject("/Ff")] = NameObject("1")
        
        # Ausgabe
        buffer = io.BytesIO()
        writer.write(buffer)
        pdf_bytes = buffer.getvalue()
        
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
        
        return pdf_bytes
    
    def fill_form_with_mapping(
        self,
        pdf_path: Union[str, Path, bytes],
        form_data: Dict[str, Any],
        field_mapping: Dict[str, str],
        output_path: Optional[Union[str, Path]] = None,
        flatten: bool = False
    ) -> bytes:
        """
        Befüllt PDF mit Feld-Mapping
        
        Args:
            pdf_path: Pfad zum PDF
            form_data: Formulardaten (aus Web-Formular)
            field_mapping: Dict mit pdf_field_name -> form_field_name
            output_path: Optionaler Ausgabepfad
            flatten: Formular einfrieren
        
        Example:
            mapping = {
                'Name': 'vorname',          # PDF-Feld 'Name' <- form_data['vorname']
                'Nachname': 'nachname',
                'Geburtsdatum': 'geburtsdatum',
            }
        """
        # Daten mit Mapping transformieren
        pdf_data = {}
        for pdf_field, form_field in field_mapping.items():
            if form_field in form_data:
                value = form_data[form_field]
                # Werte formatieren
                if isinstance(value, bool):
                    pdf_data[pdf_field] = 'Yes' if value else 'Off'
                elif isinstance(value, list):
                    pdf_data[pdf_field] = ', '.join(str(v) for v in value)
                else:
                    pdf_data[pdf_field] = str(value) if value else ''
        
        return self.fill_form(pdf_path, pdf_data, output_path, flatten)
    
    def create_field_mapping_template(
        self,
        pdf_path: Union[str, Path, bytes]
    ) -> Dict[str, str]:
        """
        Erstellt ein leeres Mapping-Template basierend auf den PDF-Feldern
        
        Returns:
            Dict mit pdf_field -> "" (zum Ausfüllen)
        """
        fields = self.get_form_fields(pdf_path)
        return {field_name: "" for field_name in fields.keys()}
    
    def validate_mapping(
        self,
        pdf_path: Union[str, Path, bytes],
        field_mapping: Dict[str, str],
        form_fields: List[str]
    ) -> Dict[str, List[str]]:
        """
        Validiert ein Feld-Mapping
        
        Returns:
            Dict mit 'missing_pdf_fields', 'missing_form_fields', 'valid'
        """
        pdf_fields = set(self.get_form_fields(pdf_path).keys())
        mapped_pdf_fields = set(field_mapping.keys())
        mapped_form_fields = set(field_mapping.values())
        form_fields_set = set(form_fields)
        
        return {
            'missing_pdf_fields': list(mapped_pdf_fields - pdf_fields),
            'missing_form_fields': list(mapped_form_fields - form_fields_set),
            'unmapped_pdf_fields': list(pdf_fields - mapped_pdf_fields),
            'valid': not (mapped_pdf_fields - pdf_fields) and not (mapped_form_fields - form_fields_set)
        }


def get_form_fields_info(pdf_path: Union[str, Path, bytes]) -> str:
    """Gibt Feld-Informationen als formatierte Tabelle zurück"""
    filler = PDFFormFiller()
    fields = filler.get_form_fields(pdf_path)
    
    if not fields:
        return "Keine Formularfelder gefunden."
    
    lines = ["| Feldname | Typ | Pflicht | Optionen |", "|----------|-----|---------|----------|"]
    
    for name, info in fields.items():
        opts = ", ".join(info['options'][:3]) if info['options'] else "-"
        if len(info['options']) > 3:
            opts += f" (+{len(info['options'])-3})"
        required = "✓" if info['required'] else ""
        lines.append(f"| {name} | {info['type']} | {required} | {opts} |")
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Test
    print("PDF Form Filler geladen")
    print(f"pypdf verfügbar: {HAS_PYPDF}")
