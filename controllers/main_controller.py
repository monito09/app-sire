import threading
import json
import os
from services.auth_service import SunatAuthService
from services.sunat_api import SunatApiService
from services.excel_processor import ExcelProcessor

class MainController:
    def __init__(self):
        self.view = None
        self.config = self._load_config()
        
        # Inicializar servicios
        self.auth_service = SunatAuthService(self.config)
        self.api_service = SunatApiService(self.auth_service)
        self.excel_processor = ExcelProcessor()

    def set_view(self, view):
        self.view = view

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def iniciar_proceso(self):
        periodo = self.view.get_periodo()
        
        # Validación básica
        if not periodo or len(periodo) != 6 or not periodo.isdigit():
            self.view.show_error("Error de Validación", "El periodo debe tener formato AAAAMM (Ej: 202503)")
            return

        # Bloquear UI
        self.view.set_loading(True)
        self.view.log(f"Iniciando proceso para periodo: {periodo}")
        
        # Ejecutar descarga en hilo separado
        thread = threading.Thread(target=self._run_process_thread, args=(periodo,))
        thread.daemon = True
        thread.start()

    # --- CORRECCIÓN 1: Hilo para listar periodos ---
    def listar_periodos_presentados(self):
        """
        Inicia la carga de periodos en un hilo secundario para no congelar la UI.
        """
        self.view.set_loading(True) # Bloquear o mostrar carga
        self.view.log("Consultando periodos disponibles en SUNAT...")
        
        thread = threading.Thread(target=self._worker_listar_periodos)
        thread.daemon = True
        thread.start()

    def _worker_listar_periodos(self):
        try:
            # 1. Consultar a SUNAT (Lento)
            todos_los_periodos = self.api_service.consultar_periodos()
            
            periodos_presentados = []
            
            # 2. Filtrar solo los "Presentado"
            for p in todos_los_periodos:
                estado = p.get('desEstado', '').upper()
                periodo = p.get('perTributario')
                
                if "PRESENTADO" in estado:
                    periodos_presentados.append({
                        "periodo": periodo,
                        "descripcion": f"{periodo} - {p.get('desEstado')}"
                    })
            
            # 3. Actualizar UI (Thread-safe usando after)
            self.view.after(0, lambda: self.view.actualizar_combo_periodos(periodos_presentados))
            self.view.after(0, lambda: self.view.log(f"Se encontraron {len(periodos_presentados)} periodos presentados."))

        except Exception as e:
            error_msg = str(e)
            self.view.after(0, lambda: self.view.show_error("Error", f"No se pudieron cargar periodos: {error_msg}"))
            self.view.after(0, lambda: self.view.log(f"❌ Error listando periodos: {error_msg}"))
        finally:
            # Liberar UI
            self.view.after(0, lambda: self.view.set_loading(False))

    # --- CORRECCIÓN 2: Bloque Finally en descarga ---
    def _run_process_thread(self, periodo):
        try:
            # Helper para log
            def update_log(msg):
                self.view.after(0, lambda: self.view.log(msg))

            ticket = None
            nombre_archivo = None
            cod_tipo_archivo = None

            update_log(f"Procesando periodo PRESENTADO: {periodo}")
            
            try:
                # 1. Solicitar Preliminar
                ticket = self.api_service.solicitar_preliminar_compras(periodo, update_log)
                update_log(f"Ticket preliminar generado: {ticket}")
                
                # 2. Esperar ticket (devuelve diccionario ahora)
                datos_archivo = self.api_service.esperar_ticket(ticket, periodo, update_log)
                nombre_archivo = datos_archivo["nomArchivo"]
                cod_tipo_archivo = datos_archivo["codTipoArchivo"]
                
                update_log(f"Archivo listo: {nombre_archivo}")
                
                # 3. Descargar
                ruta_zip = self.api_service.descargar_archivo(nombre_archivo, cod_tipo_archivo, update_log)
                
                # 4. Procesar Excel
                ruta_excel = self.excel_processor.procesar_zip(ruta_zip, update_log)
                update_log(f"✅ Excel generado: {ruta_excel}")
                
                # Mensaje final de éxito
                self.view.after(0, lambda: self.view.show_info("Éxito", f"Archivo generado:\n{ruta_excel}"))
                
            except Exception as e:
                # Manejo específico del error 1070
                if "1070" in str(e):
                    update_log(f"⚠️ El periodo {periodo} no tiene movimientos.")
                    self.view.after(0, lambda: self.view.show_info("Información", "El periodo seleccionado no tiene movimientos de compras."))
                else:
                    raise e

        except Exception as e:
            error_msg = str(e)
            self.view.after(0, lambda: self.view.log(f"❌ ERROR: {error_msg}"))
            self.view.after(0, lambda: self.view.show_error("Error", error_msg))
        
        finally:
            # IMPORTANTE: Siempre desbloquear la interfaz al terminar (éxito o error)
            self.view.after(0, lambda: self.view.set_loading(False))