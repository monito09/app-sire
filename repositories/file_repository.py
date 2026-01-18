import os
import json
from typing import Optional, Dict, List, Any
from utils.file_utils import ensure_directory_exists, get_file_path, file_exists

class FileRepository:
    """
    Encapsula todas las operaciones de acceso al sistema de archivos local.
    Gestiona rutas de descargas (PDF, XML, ZIP) y persistencia de configuración.
    """
    
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.downloads_dir = get_file_path(base_dir, 'downloads')
        self.pdf_dir = get_file_path(self.downloads_dir, 'pdf')
        self.xml_dir = get_file_path(self.downloads_dir, 'xml')
        self.zip_dir = get_file_path(self.downloads_dir, 'zip')
        self.excel_dir = get_file_path(self.downloads_dir, 'excel')

        # Asegurar existencia de carpetas críticas
        self._initialize_directories()

    def _initialize_directories(self) -> None:
        ensure_directory_exists(self.downloads_dir)
        ensure_directory_exists(self.pdf_dir)
        ensure_directory_exists(self.xml_dir)
        ensure_directory_exists(self.zip_dir)
        ensure_directory_exists(self.excel_dir)

    def get_pdf_path(self, serie: str, numero: str) -> str:
        """Retorna la ruta absoluta esperada del PDF."""
        return get_file_path(self.pdf_dir, f"{serie}-{numero}.pdf")

    def has_pdf(self, serie: str, numero: str) -> bool:
        """Verifica si el PDF existe físicamente."""
        return file_exists(self.get_pdf_path(serie, numero))

    def get_json_detail_path(self, serie: str, numero: str) -> str:
        """Retorna la ruta del JSON de detalle (extraído del XML)."""
        return get_file_path(self.xml_dir, f"{serie}-{numero}.json")

    def has_json_detail(self, serie: str, numero: str) -> bool:
        return file_exists(self.get_json_detail_path(serie, numero))

    def get_invoice_detail(self, serie: str, numero: str) -> List[Dict[str, Any]]:
        """
        Lee y retorna el contenido del JSON de detalle.
        Si no existe, retorna lista vacía.
        """
        path = self.get_json_detail_path(serie, numero)
        if not file_exists(path):
            return []
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error leyendo detalle JSON {path}: {e}")
            return []

    def get_config_path(self) -> str:
        return get_file_path(self.base_dir, 'config.json')

    def save_config(self, config: Dict[str, Any]) -> None:
        with open(self.get_config_path(), 'w') as f:
            json.dump(config, f, indent=4)

    def load_config(self) -> Dict[str, Any]:
        path = self.get_config_path()
        if not file_exists(path):
            return {}
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except:
            return {}
