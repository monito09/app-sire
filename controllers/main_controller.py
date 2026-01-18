import threading
import json
import os
import time
from typing import Optional, List, Dict, Any, Callable
import logging

# Services
from services.auth_service import SunatAuthService
from services.sunat_api import SunatApiService
from services.excel_processor import ExcelProcessor
from services.sunat_pdf_downloader import SunatPdfDownloader
from repositories.file_repository import FileRepository
from models.periodo import Periodo

# Utils
from utils.logger_utils import format_log_message

# Views
# Importamos dentro de los métodos o aquí si no hay ciclo.
# Como el controller gestiona las vistas, es mejor importarlas.
from views.login_view import LoginView
from views.main_view import DashboardView

class MainController:
    """
    Controller principal de la aplicación.
    Maneja la lógica de interacción entre la vista (UI) y los servicios de negocio.
    """

    def __init__(self) -> None:
        self.view: Any = None
        self.login_view: Any = None
        
        # Inicializar Repositorio (manejo de archivos)
        # Asumimos que la raíz del proyecto es el CWD o dos niveles arriba de este archivo
        base_dir = os.getcwd()
        self.repository = FileRepository(base_dir)
        
        self.config: Dict[str, Any] = self.repository.load_config()
        
        # Servicios se inicializan luego del login/config
        self.auth_service: Optional[SunatAuthService] = None
        self.api_service: Optional[SunatApiService] = None
        self.excel_processor: Optional[ExcelProcessor] = None
        self.pdf_downloader: Optional[SunatPdfDownloader] = None

        # Inicializar Ventana Raíz Única
        import ttkbootstrap as ttk
        self.root = ttk.Window(themename="flatly")
        self.root.withdraw() # Ocultar hasta decidir qué mostrar

    def start(self) -> None:
        """Punto de entrada: Siempre inicia en Login."""
        # Cargamos config por defecto si existe, para pre-llenar el login
        self._start_login(self.config)
        
        # Iniciar loop principal de la raíz
        self.root.mainloop()

    def _is_config_valid(self, config: Dict) -> bool:
        required = ["client_id", "client_secret", "ruc", "usuario_sol", "clave_sol"]
        return all(k in config and config[k] for k in required)

    def _start_login(self, prefill_data: Dict = None) -> None:
        self.root.deiconify() # Mostrar ventana
        self.login_view = LoginView(self.root, self, prefill_data)

    def logout(self) -> None:
        """Cierra la sesión actual y vuelve al login."""
        if self.view:
            self.view.destroy()
            self.view = None
            
        # Reiniciar servicios
        self.auth_service = None
        self.api_service = None
        
        self._start_login(self.config)

    def handle_login_attempt(self, credentials: Dict, save_local: bool) -> None:
        """Maneja el intento de login desde la vista."""
        try:
            # 1. Intentar inicializar servicio de auth y obtener token para validar
            temp_service = SunatAuthService(credentials)
            # Intentamos obtener token (esto validará si las credenciales API funcionan)
            temp_service.get_token() 
            
            # 2. Si pasa, guardamos y procedemos
            self.config = credentials
            if save_local:
                self.repository.save_config(credentials)
            
            self._init_services(self.config)
            
            # 3. Cerrar Login (destruir frame) y abrir Dashboard
            if self.login_view:
                self.login_view.destroy() 
                self.login_view = None
            
            self._start_dashboard()
            
        except Exception as e:
            # Error de autenticación
            if self.login_view:
                self.login_view.show_error(f"Error de autenticación API:\n{str(e)}")

    def _start_dashboard(self) -> None:
        self.root.deiconify()
        # DashboardView es un Frame ahora
        self.view = DashboardView(self.root, self)
        self.view.pack(fill='both', expand=True)
        self.set_view(self.view)
        
        # Cargar periodos al iniciar
        self.view.after(100, self.listar_periodos)
        # mainloop ya está corriendo en start()

    def _init_services(self, config: Dict) -> None:
        self.auth_service = SunatAuthService(config)
        self.api_service = SunatApiService(self.auth_service)
        self.excel_processor = ExcelProcessor()
        self.pdf_downloader = SunatPdfDownloader(config, self.repository)

    def set_view(self, view: Any) -> None:
        """Asigna la vista principal al controlador."""
        self.view = view

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
        
        if self.repository.has_pdf(serie, numero):
            self.view.log(format_log_message(f"Abriendo PDF local: {nombre_pdf}"))
            os.startfile(self.repository.get_pdf_path(serie, numero))
        else:
            self.view.show_info("PDF No Disponible", "Primero debe descargar el comprobante desde la columna 'VerDescripcion'.")

    def descargar_comprobante(self, ruc_proveedor: str, serie: str, numero: str) -> None:
        """
        Inicia la descarga del PDF y XML.
        """
        if not self.pdf_downloader:
            self.view.show_error("Error", "Servicio de descarga no inicializado.")
            return

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
        if not self.api_service:
             self.view.show_error("Error", "Servicio API no inicializado.")
             return

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
        if not self.api_service:
            # Si se llama antes de init (no debería pasar con el nuevo flujo pero por seguridad)
            return

        self.view.set_loading(True)
        self.view.log(format_log_message("Consultando periodos disponibles en SUNAT..."))
        
        self._run_async(self._worker_listar_periodos)

    def _worker_listar_periodos(self) -> None:
        try:
            # 1. Consultar a SUNAT (puede ser lento)
            todos_los_periodos = self.api_service.consultar_periodos()
            
            periodos_lista = []
            
            # 2. Procesar TODOS los periodos con su estado
            for p_dict in todos_los_periodos:
                cod = p_dict.get('perTributario')
                est = p_dict.get('desEstado', 'Sin estado')
                if cod:
                    periodo_obj = Periodo(codigo=cod, estado=est)
                    periodos_lista.append(periodo_obj)
            
            # Ordenar por periodo descendente (más recientes primero)
            periodos_lista.sort(key=lambda x: x.codigo, reverse=True)
            
            # 3. Datos formateados para la vista
            opciones_ui = [p.descripcion for p in periodos_lista]
            
            # 3. Actualizar UI (Thread-safe usando after)
            self.view.after(0, lambda: self.view.actualizar_combo_periodos(opciones_ui))
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
                if not self.excel_processor:
                    self.excel_processor = ExcelProcessor() # Fallback safe
                    
                df = self.excel_processor.procesar_zip(ruta_zip, update_log)
                
                # 4.1. ENRIQUECER CON ESTADO DE ARCHIVOS (Repository Check)
                if df is not None and not df.empty:
                    df['has_pdf'] = df.apply(lambda row: self.repository.has_pdf(str(row['Serie']), str(row['Numero'])), axis=1)
                    df['has_detail'] = df.apply(lambda row: self.repository.has_json_detail(str(row['Serie']), str(row['Numero'])), axis=1)
                
                # 5. ACTUALIZAR VISTA
                self.view.df_actual = df
                self.view.after(0, lambda: self.view.mostrar_datos_tabla(df))
                
                if df is not None and not df.empty:
                    update_log(f"✅ Proceso completado. {len(df)} registros cargados.")
                    self.view.after(0, lambda: self.view.show_info("Éxito", f"Se han cargado {len(df)} comprobantes."))
                else:
                    # Caso: Archivo ZIP válido pero sin registros de compras (periodo "vacío")
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