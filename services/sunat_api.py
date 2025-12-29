import requests
import time
import os
from typing import Optional, List, Dict, Any, Union, Callable

from utils.file_utils import ensure_directory_exists, get_file_path

class SunatApiService:
    """
    Servicio encargado de la comunicación directa con la API REST de SUNAT SIRE.
    Maneja la autenticación, solicitud de propuestas, consulta de tickets y descarga de archivos.
    """
    
    def __init__(self, auth_service: Any) -> None:
        self.auth_service = auth_service
        self.base_url = "https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv" # Base URL común para SIRE

    def _get_headers(self) -> Dict[str, str]:
        """Genera los headers necesarios para la autenticación con SUNAT."""
        token = self.auth_service.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def solicitar_propuesta_compras(self, periodo: str, callback_status: Callable) -> str:
        """
        Solicita la descarga de la propuesta del RCE (Registro de Compras Electrónico).
        USAR SOLO para periodos NO PRESENTADOS.
        Retorna el número de ticket.
        """
        # URL ajustada según manual (Pág 84)
        url = f"{self.base_url}/libros/rce/propuesta/web/propuesta/{periodo}/exportacioncomprobantepropuesta"
        
        callback_status(f"Solicitando propuesta para el periodo {periodo}...")
        
        # Parámetros según manual
        params = {
            "codTipoArchivo": "0",   # 0: TXT (Zipeado), 1: CSV
            "codOrigenEnvio": "2"    # 2: Servicio Web API
        }

        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            
            if response.status_code == 200:
                ticket = response.json().get("numTicket")
                if not ticket:
                    raise Exception("La respuesta de SUNAT no contiene un número de ticket.")
                return str(ticket)
            else:
                raise Exception(f"Error solicitando propuesta: {response.status_code} - {response.text}")
        except Exception as e:
            raise Exception(f"Error de conexión al solicitar propuesta: {str(e)}")

    def esperar_ticket(self, ticket: str, periodo: str, callback_status: Callable) -> Dict[str, Any]:
        """
        Consulta el estado del ticket hasta que termine o falle.
        Retorna la información del archivo generado si es exitoso.
        """
        # Endpoint de consulta de tickets usa rvierce (no rce)
        url = f"{self.base_url}/libros/rvierce/gestionprocesosmasivos/web/masivo/consultaestadotickets"
        
        params = {
            "perIni": periodo, 
            "perFin": periodo,
            "numTicket": ticket,
            "page": 1,
            "perPage": 20
        }
        
        intentos = 0
        max_intentos = 30
        
        callback_status(f"Consultando estado del ticket {ticket}...")
        
        while intentos < max_intentos:
            try:
                callback_status(f"Intento {intentos+1}/{max_intentos} - Consultando SUNAT...")
                response = requests.get(url, headers=self._get_headers(), params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    registros = data.get("registros", [])
                    
                    # Buscamos nuestro ticket en la lista
                    ticket_data = next((item for item in registros if str(item.get("numTicket")) == str(ticket)), None)
                    
                    if ticket_data:
                        estado = str(ticket_data.get("desEstadoProceso", "")).upper()
                        callback_status(f"✓ Ticket encontrado - Estado: {estado}")
                        
                        if estado in ["TERMINADO", "PROCESADO", "COMPLETADO"]:
                            return self._extract_file_info(ticket_data, periodo, ticket, callback_status)
                        
                        elif "ERROR" in estado:
                            error_msg = ticket_data.get("desError", "Error desconocido en SUNAT")
                            raise Exception(f"SUNAT rechazó el ticket: {error_msg}")
                        else:
                            callback_status(f"Estado: {estado} - Esperando procesamiento...")
                    else:
                        callback_status(f"⏳ Ticket {ticket} no aparece en la lista. Esperando...")
                
                elif response.status_code == 429:
                    callback_status("⚠ Demasiadas peticiones. Esperando 10 segundos...")
                    time.sleep(10)
                else:
                    callback_status(f"⚠ Error HTTP {response.status_code}: {response.text[:200]}")
                
            except Exception as e:
                # No re-lanzamos excepciones de conexión para seguir intentando, excepto si es rechazo explícito
                if "rechazó" in str(e) or "terminó pero" in str(e):
                    raise e
                callback_status(f"⚠ Excepción en consulta: {str(e)[:200]}")
                
            time.sleep(5) 
            intentos += 1
        
        raise Exception(f"Límite de intentos alcanzado ({max_intentos}). El servidor de SUNAT está demorando más de lo normal.")

    def _extract_file_info(self, ticket_data: Dict[str, Any], periodo: str, ticket: str, callback_status: Callable) -> Dict[str, Any]:
        """Extrae la información del archivo desde los datos del ticket."""
        callback_status("Estado TERMINADO - Extrayendo información del archivo...")
        
        # Intento 1: Directo en la raíz del ticket
        archivos = ticket_data.get("archivoReporte")
        
        # Intento 2: Dentro de detalleTicket (común en Compras)
        if not archivos:
            detalle = ticket_data.get("detalleTicket")
            if detalle and isinstance(detalle, list) and len(detalle) > 0:
                archivos = detalle[0].get("archivoReporte")

        if archivos and len(archivos) > 0:
            nom_archivo = archivos[0].get("nomArchivoReporte")
            # IMPORTANTE: El campo tiene un typo en la API de SUNAT: "Achivo" en lugar de "Archivo"
            cod_tipo = archivos[0].get("codTipoAchivoReporte") or archivos[0].get("codTipoArchivoReporte")
            
            # CRÍTICO: Extraer codProceso (necesario para descarga)
            cod_proceso = ticket_data.get("codProceso")
            
            callback_status(f"Archivo encontrado: {nom_archivo}")
            
            return {
                "nomArchivo": nom_archivo,
                "codTipoArchivo": cod_tipo or '01',
                "codProceso": cod_proceso,
                "periodo": periodo,
                "ticket": ticket
            }
        else:
            callback_status("⚠ Ticket terminado pero sin archivos")
            raise Exception("El proceso terminó pero SUNAT no generó archivos (posiblemente sin movimientos).")

    def descargar_archivo(self, nombre_archivo: str, cod_tipo_archivo: str, callback_status: Optional[Callable] = None, cod_proceso: Optional[str] = None, periodo: Optional[str] = None, ticket: Optional[str] = None) -> str:
        """
        Servicio 5.32 - Descarga de archivo de reporte masivo.
        CRÍTICO: Se requieren 6 parámetros exactos para evitar Error 500/422.
        """
        # Endpoint correcto según test.py funcional
        url = f"{self.base_url}/libros/rvierce/gestionprocesosmasivos/web/masivo/archivoreporte"
        
        # Normalización: '0' o '00' -> '01' (formato ZIP)
        if str(cod_tipo_archivo) in ["0", "00"]:
            cod_tipo_archivo = "01"
        
        # LA LLAVE MAESTRA: 6 parámetros obligatorios según test.py
        params = {
            "nomArchivoReporte": nombre_archivo,
            "codTipoArchivoReporte": cod_tipo_archivo,
            "codLibro": "080000",           # Código RCE
            "perTributario": periodo,
            "numTicket": ticket,
            "codProceso": cod_proceso        # VITAL - sin esto da Error 500
        }

        if callback_status:
            callback_status(f"Descargando: {nombre_archivo} (Proceso: {cod_proceso})")
        
        headers = {
            "Authorization": f"Bearer {self.auth_service.get_token()}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                # Asegurar que existe la carpeta downloads
                base_dir = os.getcwd()
                download_dir = get_file_path(base_dir, os.path.join('downloads', 'zip'))
                ensure_directory_exists(download_dir)
                
                ruta_local = get_file_path(download_dir, nombre_archivo)
                with open(ruta_local, "wb") as f:
                    f.write(response.content)
                if callback_status:
                    callback_status(f"✓ Descarga exitosa: {nombre_archivo}")
                return ruta_local
            else:
                raise Exception(f"Error {response.status_code}: {response.text}")
                
        except Exception as e:
            raise Exception(f"Fallo en descarga: {str(e)}")

    def consultar_periodos(self) -> List[Dict[str, Any]]:
        """
        Servicio 5.33: Consultar año y mes del RCE (Pág. 83)
        CORREGIDO: Maneja la respuesta como una lista de ejercicios.
        Retorna la lista de periodos encontrados.
        """
        cod_libro = "080000" 
        url = f"{self.base_url}/libros/rvierce/padron/web/omisos/{cod_libro}/periodos"
        
        try:
            response = requests.get(url, headers=self._get_headers())
            
            if response.status_code == 200:
                data = response.json()
                
                # Lista acumulada final
                todos_los_periodos = []

                # CASO 1: SUNAT devuelve una LISTA de años (Lo estándar según Pág. 84)
                if isinstance(data, list):
                    for ejercicio in data:
                        # Extraemos la lista de periodos dentro de cada año
                        periodos_anio = ejercicio.get("lisPeriodos", [])
                        todos_los_periodos.extend(periodos_anio)
                
                # CASO 2: Fallback por si devuelve un solo objeto (Diccionario)
                elif isinstance(data, dict):
                    todos_los_periodos = data.get("lisPeriodos", [])

                return todos_los_periodos
            else:
                raise Exception(f"Error consultando periodos: {response.status_code} - {response.text}")
        except Exception as e:
            raise Exception(f"Error de conexión al consultar periodos: {str(e)}")