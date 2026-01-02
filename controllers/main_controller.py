import threading
import json
import os
import time
from typing import Optional, List, Dict, Any, Callable

# Services
from services.auth_service import SunatAuthService
from services.sunat_api import SunatApiService
from services.excel_processor import ExcelProcessor
from services.sunat_pdf_downloader import SunatPdfDownloader

# Utils
from utils.file_utils import ensure_directory_exists, get_file_path, file_exists
from utils.logger_utils import format_log_message

class MainController:
    """
    Controller principal de la aplicación.
    Maneja la lógica de interacción entre la vista (UI) y los servicios de negocio.
    """

    def __init__(self) -> None:
        self.view: Any = None
        self.config: Dict[str, Any] = self._load_config()
        self._initialize_directories()
        
        # Inicializar servicios
        self.auth_service = SunatAuthService(self.config)
        self.api_service = SunatApiService(self.auth_service)
        self.excel_processor = ExcelProcessor()
        self.pdf_downloader = SunatPdfDownloader(self.config)

    def set_view(self, view: Any) -> None:
        """Asigna la vista principal al controlador."""
        self.view = view

    def _load_config(self) -> Dict[str, Any]:
        """Carga la configuración desde config.json."""
        config_path = get_file_path(os.path.dirname(os.path.dirname(__file__)), 'config.json')
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def _initialize_directories(self) -> None:
        """Crea la estructura de carpetas necesaria usando file_utils."""
        base_dir = os.getcwd()
        dirs = [
            get_file_path(base_dir, os.path.join('downloads', 'zip')),
            get_file_path(base_dir, os.path.join('downloads', 'excel')),
            get_file_path(base_dir, os.path.join('downloads', 'pdf')),
            get_file_path(base_dir, os.path.join('downloads', 'xml'))
        ]
        for d in dirs:
            ensure_directory_exists(d)

    def _run_async(self, target: Callable, *args: Any) -> None:
        """Ejecuta una función en un hilo separado para no congelar la UI."""
        thread = threading.Thread(target=target, args=args)
        thread.daemon = True
        thread.start()

    def abrir_pdf(self, ruc_proveedor: str, serie: str, numero: str) -> None:
        """
        Abre el PDF si existe localmente.
        """
        if not all([ruc_proveedor, serie, numero]):
            return

        nombre_pdf = f"{serie}-{numero}.pdf"
        ruta_pdf = get_file_path(os.path.join(os.getcwd(), 'downloads', 'pdf'), nombre_pdf)
        
        if file_exists(ruta_pdf):
            self.view.log(format_log_message(f"Abriendo PDF local: {nombre_pdf}"))
            os.startfile(ruta_pdf)
        else:
            self.view.show_info("PDF No Disponible", "Primero debe descargar el comprobante desde la columna 'VerDescripcion'.")

    def descargar_comprobante(self, ruc_proveedor: str, serie: str, numero: str) -> None:
        """
        Inicia la descarga del PDF y XML.
        """
        self.view.log(format_log_message(f"Iniciando descarga para {serie}-{numero}..."))
        self.view.set_loading(True)
        self._run_async(self._worker_descargar_pdf, ruc_proveedor, serie, numero)

    def _worker_descargar_pdf(self, ruc_proveedor: str, serie: str, numero: str) -> None:
        try:
            def update_log(msg: str) -> None:
                self.view.after(0, lambda: self.view.log(format_log_message(msg)))
            
            ruta_pdf = self.pdf_downloader.download_pdf(ruc_proveedor, serie, numero, update_log)
            
            update_log(f"✅ Descarga completada: {ruta_pdf}")
            
            # Actualizar la tabla para mostrar la descripción y habilitar el PDF
            if self.view.df_actual is not None:
                self.view.after(0, lambda: self.view.mostrar_datos_tabla(self.view.df_actual))
            
        except Exception as e:
            update_log(f"❌ Error descargando PDF: {str(e)}")
            self.view.after(0, lambda: self.view.show_error("Error de Descarga", f"No se pudo descargar el PDF.\n\nDetalle: {str(e)}"))
        finally:
            self.view.after(0, lambda: self.view.set_loading(False))

    def iniciar_proceso(self) -> None:
        """Inicia el proceso de descarga masiva para un periodo."""
        periodo = self.view.get_periodo()
        
        # Validación básica
        if not periodo or len(periodo) != 6 or not periodo.isdigit():
            self.view.show_error("Error de Validación", "El periodo debe tener formato AAAAMM (Ej: 202503)")
            return

        # Bloquear UI
        self.view.set_loading(True)
        self.view.limpiar_tabla()
        
        # Ejecutar en hilo separado
        self._run_async(self._worker_iniciar_proceso, periodo)

    def listar_periodos(self) -> None:
        """
        Inicia la carga de periodos en un hilo secundario para no congelar la UI.
        Carga TODOS los periodos (presentados y no presentados).
        """
        self.view.set_loading(True)
        self.view.log(format_log_message("Consultando periodos disponibles en SUNAT..."))
        
        self._run_async(self._worker_listar_periodos)

    def _worker_listar_periodos(self) -> None:
        try:
            # 1. Consultar a SUNAT (puede ser lento)
            todos_los_periodos = self.api_service.consultar_periodos()
            
            periodos_lista = []
            
            # 2. Procesar TODOS los periodos con su estado
            for p in todos_los_periodos:
                estado = p.get('desEstado', 'Sin estado')
                periodo = p.get('perTributario')
                
                if periodo:
                    periodos_lista.append({
                        "periodo": periodo,
                        "descripcion": f"{periodo} - {estado}"
                    })
            
            # Ordenar por periodo descendente (más recientes primero)
            periodos_lista.sort(key=lambda x: x['periodo'], reverse=True)
            
            # 3. Actualizar UI (Thread-safe usando after)
            self.view.after(0, lambda: self.view.actualizar_combo_periodos(periodos_lista))
            self.view.after(0, lambda: self.view.log(format_log_message(f"Se encontraron {len(periodos_lista)} periodos disponibles.")))

        except Exception as e:
            error_msg = str(e)
            self.view.after(0, lambda: self.view.show_error("Error", f"No se pudieron cargar periodos: {error_msg}"))
            self.view.after(0, lambda: self.view.log(format_log_message(f"❌ Error listando periodos: {error_msg}")))
        finally:
            self.view.after(0, lambda: self.view.set_loading(False))

    def _worker_iniciar_proceso(self, periodo: str) -> None:
        try:
            def update_log(msg: str) -> None:
                self.view.after(0, lambda: self.view.log(format_log_message(msg)))

            # 1. Solicitar Propuesta
            ticket = self.api_service.solicitar_propuesta_compras(periodo, update_log)
            update_log(f"Ticket generado: {ticket}")

            # 2. Esperar a que el ticket termine
            info_archivo = self.api_service.esperar_ticket(ticket, periodo, update_log)
            
            if info_archivo and info_archivo.get('nomArchivo'):
                nombre_zip = info_archivo['nomArchivo']
                cod_tipo = info_archivo.get('codTipoArchivo', '01')
                cod_proceso = info_archivo.get('codProceso')
                
                # 3. Descargar el archivo con los 6 parámetros críticos
                update_log(f"Descargando archivo con código de proceso: {cod_proceso}...")
                ruta_zip = self.api_service.descargar_archivo(
                    nombre_archivo=nombre_zip,
                    cod_tipo_archivo=cod_tipo,
                    callback_status=update_log,
                    cod_proceso=cod_proceso,
                    periodo=periodo,
                    ticket=ticket
                )

                # 4. PROCESAR EL ZIP
                update_log("📦 Extrayendo y procesando datos del archivo ZIP...")
                df = self.excel_processor.procesar_zip(ruta_zip, update_log)
                
                # 5. ACTUALIZAR VISTA
                self.view.df_actual = df
                self.view.after(0, lambda: self.view.mostrar_datos_tabla(df))
                
                if df is not None and not df.empty:
                    update_log(f"✅ Proceso completado. {len(df)} registros cargados.")
                    self.view.after(0, lambda: self.view.show_info("Éxito", f"Se han cargado {len(df)} comprobantes."))
                else:
                    update_log("⚠️ No se encontraron comprobantes para este periodo.")
                    self.view.after(0, lambda: self.view.show_warning(
                        "Sin Datos", 
                        "No existe información de Comprobantes de Pago para el período"
                    ))
            
            else:
                raise Exception("No se encontró información del archivo en el ticket.")

        except Exception as e:
            error_msg = str(e)
            update_log(f"❌ ERROR: {error_msg}")
            self.view.after(0, lambda: self.view.show_error("Error en el Proceso", error_msg))
        
        finally:
            self.view.after(0, lambda: self.view.set_loading(False))
    
    def exportar_excel(self) -> None:
        """
        Exporta los datos actuales de la tabla a Excel.
        """
        if self.view.df_actual is None or self.view.df_actual.empty:
            self.view.show_error("Error", "No hay datos para exportar. Primero descargue un periodo.")
            return
        
        self.view.set_loading(True)
        self.view.log(format_log_message("Iniciando exportación a Excel..."))
        
        self._run_async(self._worker_exportar_excel)
    
    def _worker_exportar_excel(self) -> None:
        try:
            def update_log(msg: str) -> None:
                self.view.after(0, lambda: self.view.log(format_log_message(msg)))
            
            # Exportar usando el procesador
            ruta_excel = self.excel_processor.exportar_a_excel(
                df=self.view.df_actual,
                callback_status=update_log
            )
            
            update_log(f"✅ Excel guardado: {ruta_excel}")
            self.view.after(0, lambda: self.view.show_info("Éxito", f"Archivo generado:\n{ruta_excel}"))
            
        except Exception as e:
            update_log(f"❌ Error en exportación: {str(e)}")
            self.view.after(0, lambda: self.view.show_error("Error de Exportación", str(e)))
        finally:
            self.view.after(0, lambda: self.view.set_loading(False))