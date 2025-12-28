import requests
import time
import os

class SunatApiService:
    def __init__(self, auth_service):
        self.auth_service = auth_service
        self.base_url = "https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv" # Base URL común para SIRE

    def _get_headers(self):
        token = self.auth_service.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def solicitar_propuesta_compras(self, periodo, callback_status):
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
                return ticket
            else:
                raise Exception(f"Error solicitando propuesta: {response.status_code} - {response.text}")
        except Exception as e:
            raise Exception(f"Error de conexión al solicitar propuesta: {str(e)}")

    def solicitar_preliminar_compras(self, periodo, callback_status):
        """
        Solicita la descarga del preliminar registrado del RCE.
        USAR para periodos que dicen 'PRESENTADO' (ya declarados).
        Referencia: Manual Pág. 94 (Servicio 5.40)
        Retorna el número de ticket.
        """
        url = f"{self.base_url}/libros/rce/preliminar/web/registroslibros/{periodo}/exportareportepreliminar"
        
        callback_status(f"Solicitando preliminar registrado para el periodo {periodo}...")
        
        params = {
            "codTipoArchivo": "1",   # 1: CSV (Recomendado para Excel), 0: TXT
            "codOrigenEnvio": "2"    # 2: Servicio Web API
        }

        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            
            if response.status_code == 200:
                ticket = response.json().get("numTicket")
                if not ticket:
                    raise Exception("La respuesta de SUNAT no contiene un número de ticket.")
                return ticket
            else:
                raise Exception(f"Error solicitando preliminar: {response.status_code} - {response.text}")
        except Exception as e:
            raise Exception(f"Error de conexión al solicitar preliminar: {str(e)}")

    def esperar_ticket(self, ticket, periodo, callback_status):
        # Asegúrate de usar la ruta de RCE
        url = f"{self.base_url}/libros/rce/gestionprocesosmasivos/web/masivo/consultaestadotickets"
        
        params = {
            "perIni": periodo, 
            "perFin": periodo,
            "numTicket": ticket,
            "page": 1,
            "perPage": 20
        }
        
        intentos = 0
        max_intentos = 30  # Aumentamos a 30 intentos (aprox 2.5 minutos)
        
        while intentos < max_intentos:
            try:
                response = requests.get(url, headers=self._get_headers(), params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    registros = data.get("registros", [])
                    
                    # Buscamos nuestro ticket en la lista
                    ticket_data = next((item for item in registros if str(item.get("numTicket")) == str(ticket)), None)
                    
                    if ticket_data:
                        # Obtenemos el estado y lo normalizamos a mayúsculas para comparar
                        estado = str(ticket_data.get("desEstadoProceso", "")).upper()
                        callback_status(f"Ticket {ticket} - Estado actual: {estado} (Intento {intentos+1})")
                        
                        if estado in ["TERMINADO", "PROCESADO", "COMPLETADO"]:
                            # --- EXTRACCIÓN DEL ARCHIVO ---
                            archivo_info = None
                            
                            # Intento 1: Directo en la raíz del ticket
                            archivos = ticket_data.get("archivoReporte")
                            
                            # Intento 2: Dentro de detalleTicket (común en Compras)
                            if not archivos:
                                detalle = ticket_data.get("detalleTicket")
                                if detalle and isinstance(detalle, list) and len(detalle) > 0:
                                    archivos = detalle[0].get("archivoReporte")
                            
                            if archivos and len(archivos) > 0:
                                return {
                                    "nomArchivo": archivos[0].get("nomArchivoReporte"),
                                    "codTipoArchivo": archivos[0].get("codTipoArchivoReporte")
                                }
                            else:
                                # Si terminó pero no hay archivos, puede ser un periodo sin movimiento
                                raise Exception("El proceso terminó pero SUNAT no generó archivos (posiblemente sin movimientos).")
                        
                        elif "ERROR" in estado:
                            # Si el estado contiene la palabra ERROR, detenemos la espera
                            error_msg = ticket_data.get("desError", "Error desconocido en SUNAT")
                            raise Exception(f"SUNAT rechazó el ticket: {error_msg}")
                    else:
                        callback_status(f"Ticket {ticket} aún no aparece en la lista...")
                
                elif response.status_code == 429:
                    callback_status("Demasiadas peticiones. Esperando un poco más...")
                    time.sleep(10) # Si hay saturación, esperamos más
                
            except Exception as e:
                raise e
                
            time.sleep(5) 
            intentos += 1
        
        raise Exception("Límite de intentos alcanzado. El servidor de SUNAT está demorando más de lo normal.")

    def descargar_archivo(self, nombre_archivo, cod_tipo_archivo, callback_status=None):
        # CORRECCIÓN: Se cambia 'rvierce' por 'rce' (Pág. 98 Manual v22)
        url = f"{self.base_url}/libros/rce/gestionprocesosmasivos/web/masivo/archivoreporte"
        
        if callback_status:
            callback_status(f"Descargando archivo: {nombre_archivo}")
        
        params = {
            "nomArchivoReporte": nombre_archivo,
            "codTipoArchivoReporte": cod_tipo_archivo
        }
        
        response = requests.get(url, headers=self._get_headers(), params=params)
        
        if response.status_code == 200:
            # Guardar el archivo en la carpeta actual
            ruta_local = os.path.join(os.getcwd(), nombre_archivo)
            with open(ruta_local, "wb") as f:
                f.write(response.content)
            return ruta_local
        else:
            raise Exception(f"Error en descarga: {response.status_code} - {response.text}")
        

    def consultar_periodos(self):
        """
        Servicio 5.33: Consultar año y mes del RCE (Pág. 83)
        CORREGIDO: Maneja la respuesta como una lista de ejercicios.
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