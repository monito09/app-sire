
def format_quantity(value: str) -> str:
    """
    Formatea la cantidad para eliminar ceros decimales innecesarios.
    Ejemplo: '1.000000' -> '1', '172.80000' -> '172.8'
    """
    if not value or not value.strip():
        return ""
    try:
        # Convertir a float primero para limpiar formato
        num = float(value)
        # Usar formato general 'g' que elimina ceros no significativos
        # o verificar si es entero
        if num.is_integer():
            return str(int(num))
        else:
            return f"{num:g}"
    except ValueError:
        return value

def get_unit_description(code: str) -> str:
    """
    Mapea códigos de unidad UN/ECE (estándar SUNAT) a descripciones legibles.
    """
    if not code:
        return ""
    
    code = code.upper().strip()
    
    # Mapeo de códigos comunes
    MAPPING = {
        'NIU': 'UNIDAD',
        'ZZ': 'UNIDAD',
        'KGM': 'KILOGRAMO',
        'LTR': 'LITRO',
        'GLL': 'GALON',
        'MTR': 'METRO',
        'BX': 'CAJA',
        'DZN': 'DOCENA',
        'EA': 'UNIDAD' # A veces usan EA como Each
    }
    
    return MAPPING.get(code, code)
