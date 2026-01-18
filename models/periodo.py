from dataclasses import dataclass

@dataclass
class Periodo:
    """
    Representa un periodo tributario (Mes/Año).
    """
    codigo: str  # Formato: YYYYMM (Ej: 202501)
    estado: str  # Ej: "PRESENTADO", "NO PRESENTADO"
    
    @property
    def anio(self) -> int:
        return int(self.codigo[:4])
    
    @property
    def mes(self) -> int:
        return int(self.codigo[4:])
    
    @property
    def descripcion(self) -> str:
        return f"{self.codigo} - {self.estado}"
