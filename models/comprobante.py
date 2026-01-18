from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

@dataclass
class Comprobante:
    """
    Representa un Comprobante de Pago Electrónico (Factura, Nota de Crédito/Débito)
    obtenido desde el SIRE (RCE).
    """
    # Claves principales (Primary Key compuesta)
    ruc_proveedor: str
    serie: str
    numero: str
    tipo_documento: str = "01" # 01: Factura por defecto

    # Datos del Emisor
    razon_social: str = ""

    # Datos financieros (Floats para cálculos, aunque Decimal es mejor para contabilidad estricta)
    # Por ahora mantenemos compatibilidad con lo que extrae ExcelProcessor (floats)
    base_imponible: float = 0.0
    igv: float = 0.0
    importe_total: float = 0.0
    moneda: str = "PEN"

    # Fechas
    fecha_emision: Optional[datetime] = None
    fecha_vencimiento: Optional[datetime] = None

    # Estado del archivo adjunto (Gestión local)
    tiene_pdf: bool = False
    tiene_xml: bool = False
    
    # Detalle (Opcional, cargado bajo demanda)
    cantidad_items: Optional[float] = None
    unidad_medida: Optional[str] = None
    descripcion_principal: Optional[str] = None

    @property
    def id_unico(self) -> str:
        """Retorna un ID único para uso interno (ej. claves de diccionarios)."""
        return f"{self.ruc_proveedor}-{self.serie}-{self.numero}"
