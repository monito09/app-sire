from playwright.sync_api import sync_playwright
import time
import os

class SunatPdfDownloader:
    def __init__(self, config):
        self.ruc_sol = config["ruc"]
        self.usuario_sol = config["usuario_sol"]
        self.clave_sol = config["clave_sol"]

    def download_pdf(self, ruc_emisor, serie, numero, callback_status):
        """
        Descarga el PDF de la factura usando Playwright a la carpeta downloads/pdf.
        Retorna la ruta absoluta del archivo descargado.
        Basado estrictamente en la lógica de test2.py.
        """
        callback_status(f"Iniciando descarga de PDF {serie}-{numero} de {ruc_emisor}...")
        
        # Preparar directorio de descarga
        download_dir = os.path.join(os.getcwd(), 'downloads', 'pdf')
        os.makedirs(download_dir, exist_ok=True)
        # Nombre final esperado
        nombre_pdf = f"{serie}-{numero}.pdf"
        target_path = os.path.join(download_dir, nombre_pdf)

        start_time = time.time()
        
        # IMPORTANTE: headless=False como en test2.py para evitar bloqueos
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={'width': 1600, 'height': 900})
            page = context.new_page()

            try:
                callback_status("Accediendo al login de SUNAT...")
                page.goto("https://api-seguridad.sunat.gob.pe/v1/clientessol/4f3b88b3-d9d6-402a-b85d-6a0bc857746a/oauth2/loginMenuSol?lang=es-PE&showDni=true&showLanguages=false&originalUrl=https://e-menu.sunat.gob.pe/cl-ti-itmenu/AutenticaMenuInternet.htm&state=rO0ABXNyABFqYXZhLnV0aWwuSGFzaE1hcAUH2sHDFmDRAwACRgAKbG9hZEZhY3RvckkACXRocmVzaG9sZHhwP0AAAAAAAAx3CAAAABAAAAADdAADZXhlcHQABnBhcmFtc3QASyomKiYvY2wtdGktaXRtZW51L01lbnVJbnRlcm5ldC5odG0mYjY0ZDI2YThiNWFmMDkxOTIzYjIzYjY0MDdhMWMxZGI0MWU3MzNhNnQABGV4ZWNweA==")
                
                page.fill("#txtRuc", self.ruc_sol)
                page.fill("#txtUsuario", self.usuario_sol)
                page.fill("#txtContrasena", self.clave_sol)
                page.click("#btnAceptar")

                # --- 1. MANEJO DE BLOQUEOS ---
                print("Esperando modales de campaña...")
                try:
                    # Esperamos al iframe de la campaña
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
                    
                    # Pausa necesaria para que la capa gris (overlay) desaparezca naturalmente
                    time.sleep(2) 
                except Exception as e:
                    print("- No se detectó el modal o tardó demasiado. Continuando...")

                # --- 2. NAVEGACIÓN AL MENÚ ---
                callback_status("Navegando al menú de Comprobantes...")
                try:
                    page.locator(".list-group-item").filter(has_text="Empresas").first.click(force=True)
                    time.sleep(1.5)

                    def navegar_lista(texto):
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
                    raise e # Re-raise porque sin esto no podemos seguir

                # --- 3. LOCALIZACIÓN DEL FORMULARIO ---
                callback_status("Buscando formulario...")
                app_frame = page.frame_locator("#iframeApplication")
                
                try:
                    page.wait_for_selector("ngx-spinner", state="hidden", timeout=15000)
                    
                    radio_recibido = app_frame.get_by_text("Recibido", exact=True)
                    radio_recibido.wait_for(state="visible", timeout=15000)
                    radio_recibido.click()
                    callback_status("✓ Cambio a 'Recibido' realizado.")
                    
                    time.sleep(2)
                except Exception as e:
                    callback_status(f"❌ Error accediendo al formulario: {e}")
                    raise e

                # --- 4. LLENADO DEL FORMULARIO ---
                try:
                    callback_status("Configurando filtros...")
                    
                    # Re-confirmar 'Recibido' por seguridad (como en test2.py)
                    try:
                        app_frame.get_by_text("Recibido", exact=True).click()
                    except:
                        pass
                    time.sleep(2)

                    txt_ruc = app_frame.locator("#rucEmisor, [formcontrolname='rucEmisor']").first
                    txt_ruc.fill(ruc_emisor)
                    callback_status(f"✓ RUC {ruc_emisor} ingresado.")

                    # --- SELECTOR DE TIPO (PrimeNG) ---
                    try:
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
                        
                        # --- SERIE Y NÚMERO ---
                        app_frame.locator("input[formcontrolname='serieComprobante'], #serie").first.fill(serie)
                        app_frame.locator("input[formcontrolname='numeroComprobante'], #numero").first.fill(numero)
                        
                        callback_status("Consultando...")
                        app_frame.get_by_role("button", name="Consultar").click()

                    except Exception as e:
                        callback_status(f"Error en formulario (PrimeNG): {e}")
                        raise e

                    # --- 5. DESCARGA DEL PDF ---
                    try:
                        callback_status("Esperando resultado...")
                        app_frame.get_by_text("Resultado", exact=True).wait_for(state="visible", timeout=20000)
                        
                        btn_pdf = app_frame.locator("button[ngbtooltip='Descargar PDF']").first
                        btn_pdf.wait_for(state="visible", timeout=10000)
                        
                        callback_status("✓ Botón PDF detectado. Descargando...")
                        
                        with page.expect_download() as download_info:
                            btn_pdf.click()
                        
                        download = download_info.value
                        download.save_as(target_path)
                        
                        callback_status(f"✓ ¡ÉXITO! PDF descargado.")
                        return target_path

                    except Exception as e:
                        callback_status(f"Error descargando PDF: {e}")
                        raise e

                except Exception as e:
                    callback_status(f"Error procesando datos: {e}")
                    raise e
            
            finally:
                browser.close()
