import zipfile
import xml.etree.ElementTree as ET
import json
import os
from typing import Optional, List, Dict, Any

class XmlProcessor:
    """
    Servicio dedicado al procesamiento de archivos XML (UBL) de SUNAT.
    """

    def extract_description_from_zip(self, zip_path: str, output_json_path: str) -> Optional[str]:
        """
        Extrae el XML del ZIP, busca datos (Descripción, Cantidad, Unidad) y los guarda en JSON.
        """
        try:
            items_data = [] # Lista de dicts
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Buscar archivos XML dentro del ZIP
                xml_files = [f for f in zip_ref.namelist() if f.endswith('.xml')]
                
                for xml_file in xml_files:
                    with zip_ref.open(xml_file) as xml_f:
                        tree = ET.parse(xml_f)
                        root = tree.getroot()
                        
                        # Namespaces comunes en UBL SUNAT
                        namespaces = {
                            'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
                            'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
                        }
                        
                        # Buscar items (InvoiceLine o CreditNoteLine)
                        lines = root.findall('.//cac:InvoiceLine', namespaces)
                        if not lines:
                            lines = root.findall('.//cac:CreditNoteLine', namespaces)
                            
                        for line in lines:
                            item = line.find('cac:Item', namespaces)
                            
                            descripcion = ""
                            if item is not None:
                                desc_node = item.find('cbc:Description', namespaces)
                                if desc_node is not None and desc_node.text:
                                    descripcion = desc_node.text.strip()
                            
                            cantidad = ""
                            unidad = ""
                            qty_node = line.find('cbc:InvoicedQuantity', namespaces)
                            if qty_node is None:
                                qty_node = line.find('cbc:CreditedQuantity', namespaces) # Para notas de crédito
                                
                            if qty_node is not None:
                                cantidad = qty_node.text.strip() if qty_node.text else ""
                                unidad = qty_node.get('unitCode', "")
                                
                            items_data.append({
                                "descripcion": descripcion,
                                "cantidad": cantidad,
                                "unidad": unidad
                            })
            
            # Guardar en JSON si hay datos
            if items_data:
                # Asegurar directorio (aunque el repo ya lo hace, doble check)
                os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
                
                with open(output_json_path, 'w', encoding='utf-8') as f:
                    json.dump(items_data, f, ensure_ascii=False, indent=2)
                return output_json_path
                
            return None
            
        except Exception as e:
            print(f"Error procesando XML desde ZIP {zip_path}: {e}")
            return None
