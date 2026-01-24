from playwright.sync_api import sync_playwright, Page, BrowserContext
import time
import os
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional, List, Any, Callable

from utils.file_utils import ensure_directory_exists, get_file_path
from utils.logger_utils import log_to_console

class SunatPdfDownloader:
    """
    Servicio encargado de interactuar con el portal SOL de SUNAT para
    descargar los comprobantes (PDF) y sus archivos XML asociados.
    """
    
    def __init__(self, config: dict):
        self.ruc_sol = config["ruc"]
        self.usuario_sol = config["usuario_sol"]
        self.clave_sol = config["clave_sol"]

    def _extract_description_from_zip(self, zip_path: str, output_dir: str, base_name: str) -> Optional[str]:
        """
        Extrae el XML del ZIP, busca datos (Descripción, Cantidad, Unidad) y los guarda en JSON.
        """
        try:
            items_data = [] # Lista de dicts: {descripcion, cantidad, unidad}
            
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
            
            # Guardar en JSON (reemplaza al TXT antiguo)
            if items_data:
                json_path = get_file_path(output_dir, f"{base_name}.json")
                with open(json_path, 'w', encoding='utf-8') as f:
                    import json
                    json.dump(items_data, f, ensure_ascii=False, indent=2)
                return json_path
            return None
            
        except Exception as e:
            print(f"Error extrayendo XML: {e}")
            return None

    def _init_browser_session(self, p: Any) -> tuple[Any, Any, Page]:
        """Inicia la sesión de navegador con configuración anti-detección."""
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--start-maximized', 
                '--no-sandbox'
            ]
        )
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        # Script para ocultar propiedades de automatización
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        return browser, context, page

    def _login(self, page: Page, callback_status: Callable) -> None:
        """Realiza el login en SUNAT SOL."""
        callback_status("Accediendo al login de SUNAT...")
        page.goto("https://api-seguridad.sunat.gob.pe/v1/clientessol/4f3b88b3-d9d6-402a-b85d-6a0bc857746a/oauth2/loginMenuSol?lang=es-PE&showDni=true&showLanguages=false&originalUrl=https://e-menu.sunat.gob.pe/cl-ti-itmenu/AutenticaMenuInternet.htm&state=rO0ABXNyABFqYXZhLnV0aWwuSGFzaE1hcAUH2sHDFmDRAwACRgAKbG9hZEZhY3RvckkACXRocmVzaG9sZHhwP0AAAAAAAAx3CAAAABAAAAADdAADZXhlcHQABnBhcmFtc3QASyomKiYvY2wtdGktaXRtZW51L01lbnVJbnRlcm5ldC5odG0mYjY0ZDI2YThiNWFmMDkxOTIzYjIzYjY0MDdhMWMxZGI0MWU3MzNhNnQABGV4ZWNweA==")
        
        page.fill("#txtRuc", self.ruc_sol)
        page.fill("#txtUsuario", self.usuario_sol)
        page.fill("#txtContrasena", self.clave_sol)
        page.click("#btnAceptar")

    def _handle_popups(self, page: Page) -> None:
        """Maneja los modales de campaña o publicidad inicial."""
        print("Esperando modales de campaña...")
        try:
            iframe_campana = page.frame_locator("#ifrVCE")
            
            # Click en Finalizar
            btn_finalizar = iframe_campana.get_by_role("button", name="Finalizar")
            btn_finalizar.wait_for(state="visible", timeout=10000)
            btn_finalizar.click()
            print("✓ Modal 'Finalizar' cerrado.")

            # Click en Continuar sin confirmar
            btn_continuar = iframe_campana.get_by_text("Continuar sin confirmar")
            btn_continuar.wait_for(state="visible", timeout=5000)
            btn_continuar.click()
            print("✓ Pantalla de validación saltada.")
            
            time.sleep(2) 
        except Exception:
            print("- No se detectó el modal o tardó demasiado. Continuando...")

    def _navigate_to_voucher_lookup(self, page: Page, callback_status: Callable) -> None:
        """Navega a través del menú hasta la opción de Consulta de Comprobantes."""
        callback_status("Navegando al menú de Comprobantes...")
        try:
            page.locator(".list-group-item").filter(has_text="Empresas").first.click(force=True)
            time.sleep(1.5)

            def navegar_lista(texto: str) -> None:
                item = page.get_by_text(texto, exact=True).first
                item.wait_for(state="visible", timeout=10000)
                item.click(force=True)
                time.sleep(0.8)

            navegar_lista("Comprobantes de pago")
            navegar_lista("Comprobantes de Pago")
            navegar_lista("Consulta de Comprobantes de Pago")
            
            link_final = page.get_by_text("Nueva Consulta de comprobantes de pago", exact=True).first
            link_final.wait_for(state="visible", timeout=10000)
            link_final.click(force=True)
            callback_status("✓ Ruta de navegación completada.")

        except Exception as e:
            callback_status(f"Fallo en navegación del menú: {e}")
            raise e

    def _fill_consultation_form(self, page: Page, ruc_emisor: str, serie: str, numero: str, callback_status: Callable) -> Any:
        """Llena el formulario de consulta de comprobantes."""
        callback_status("Buscando formulario...")
        app_frame = page.frame_locator("#iframeApplication")
        
        try:
            page.wait_for_selector("ngx-spinner", state="hidden", timeout=15000)
            
            radio_recibido = app_frame.get_by_text("Recibido", exact=True)
            radio_recibido.wait_for(state="visible", timeout=15000)
            radio_recibido.click()
            callback_status("✓ Cambio a 'Recibido' realizado.")
            time.sleep(2)

            # Re-confirmar 'Recibido'
            try:
                app_frame.get_by_text("Recibido", exact=True).click()
            except:
                pass
            time.sleep(2)

            txt_ruc = app_frame.locator("#rucEmisor, [formcontrolname='rucEmisor']").first
            txt_ruc.fill(ruc_emisor)
            callback_status(f"✓ RUC {ruc_emisor} ingresado.")

            # Selector de Tipo (PrimeNG)
            dropdown_tipo = app_frame.locator("p-dropdown[formcontrolname='tipoComprobanteI']")
            dropdown_tipo.wait_for(state="visible", timeout=10000)
            dropdown_tipo.click()
            
            buscador_interno = app_frame.locator("input.p-dropdown-filter")
            buscador_interno.wait_for(state="visible", timeout=5000)
            buscador_interno.fill("Factura")
            
            time.sleep(1.5)
            
            opcion_factura = app_frame.get_by_role("option", name="Factura", exact=True)
            opcion_factura.wait_for(state="visible", timeout=5000)
            opcion_factura.click()
            callback_status("✓ 'Factura' seleccionada.")
            
            # Serie y Número
            app_frame.locator("input[formcontrolname='serieComprobante'], #serie").first.fill(serie)
            app_frame.locator("input[formcontrolname='numeroComprobante'], #numero").first.fill(numero)
            
            callback_status("Consultando...")
            app_frame.get_by_role("button", name="Consultar").click()
            
            return app_frame

        except Exception as e:
            callback_status(f"⚠️ Error en interacción con formulario: {e}")
            raise e

    def _perform_file_downloads(self, page: Page, app_frame: Any, target_pdf_path: str, target_zip_path: str, callback_status: Callable) -> None:
        """Ejecuta la descarga del PDF y XML."""
        callback_status("Esperando resultado...")
        app_frame.get_by_text("Resultado", exact=True).wait_for(state="visible", timeout=20000)
        
        # 1. Descargar PDF
        btn_pdf = app_frame.locator("button[ngbtooltip='Descargar PDF']").first
        btn_pdf.wait_for(state="visible", timeout=10000)
        
        callback_status("✓ Botón PDF detectado. Descargando...")
        
        with page.expect_download() as download_info:
            btn_pdf.click()
        
        download = download_info.value
        download.save_as(target_pdf_path)
        callback_status(f"✓ PDF descargado.")

        time.sleep(1)

        # 2. Descargar XML
        try:
            btn_xml = app_frame.locator("button[ngbtooltip='Descargar XML']").first
            if btn_xml.is_visible():
                callback_status("Descargando XML...")
                with page.expect_download() as download_info_xml:
                    btn_xml.click()
                
                download_xml = download_info_xml.value
                download_xml.save_as(target_zip_path)
                callback_status("✓ XML descargado.")
            else:
                callback_status("⚠️ Botón XML no visible.")
        except Exception as ex_xml:
            callback_status(f"⚠️ Error descargando XML: {ex_xml}")
            # No bloqueamos si falla el XML

    def download_pdf(self, ruc_emisor: str, serie: str, numero: str, callback_status: Callable) -> str:
        """
        Descarga el PDF y el XML de la factura usando Playwright.
        Retorna la ruta del PDF descargado.
        """
        callback_status(f"Iniciando descarga de PDF y XML {serie}-{numero} de {ruc_emisor}...")
        
        # Preparar directorios
        base_dir = os.getcwd()
        pdf_dir = get_file_path(base_dir, os.path.join('downloads', 'pdf'))
        xml_dir = get_file_path(base_dir, os.path.join('downloads', 'xml'))
        zip_dir = get_file_path(base_dir, os.path.join('downloads', 'zip'))
        
        ensure_directory_exists(pdf_dir)
        ensure_directory_exists(xml_dir)
        ensure_directory_exists(zip_dir)

        nombre_base = f"{serie}-{numero}"
        target_pdf_path = get_file_path(pdf_dir, f"{nombre_base}.pdf")
        target_zip_path = get_file_path(zip_dir, f"{nombre_base}.zip")

        with sync_playwright() as p:
            browser, context, page = self._init_browser_session(p)
            try:
                self._login(page, callback_status)
                self._handle_popups(page)
                self._navigate_to_voucher_lookup(page, callback_status)
                app_frame = self._fill_consultation_form(page, ruc_emisor, serie, numero, callback_status)
                self._perform_file_downloads(page, app_frame, target_pdf_path, target_zip_path, callback_status)

                # Extraer descripción si se descargó el XML
                if os.path.exists(target_zip_path):
                     self._extract_description_from_zip(target_zip_path, xml_dir, nombre_base)
                
                callback_status(f"✓ ¡ÉXITO! Proceso completado.")
                return target_pdf_path

            except Exception as e:
                callback_status(f"Error descargando archivos: {e}")
                raise e
            finally:
                browser.close()
