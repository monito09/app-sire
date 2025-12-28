import requests
import time
import zipfile
import io
import sys

# =============================================================================
# CONFIGURACIÓN DEL USUARIO
# =============================================================================
RUC = "20605730541"
USUARIO_SOL = "ITTENTOR"
CLAVE_SOL = "nstatexpe"
CLIENT_ID = "704c2889-f59d-4b43-af5b-9f429849e66a"
CLIENT_SECRET = "szaO0p3L1W5gDfd3HeFfxQ=="

PERIODO_TRIBUTARIO = "202307" 

# =============================================================================
# CONSTANTES
# =============================================================================
URL_AUTH = f"https://api-seguridad.sunat.gob.pe/v1/clientessol/{CLIENT_ID}/oauth2/token/"
URL_BASE = "https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv"

COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def log(mensaje):
    print(f"[LOG {time.strftime('%H:%M:%S')}] {mensaje}")

def obtener_token():
    log("1. Autenticando con SUNAT...")
    headers = COMMON_HEADERS.copy()
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
    data = {
        'grant_type': 'password',
        'scope': 'https://api-sire.sunat.gob.pe',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'username': RUC + USUARIO_SOL,
        'password': CLAVE_SOL
    }
    try:
        response = requests.post(URL_AUTH, data=data, headers=headers)
        response.raise_for_status()
        return response.json().get('access_token')
    except Exception as e:
        log(f"Error Auth: {e}")
        sys.exit()

def solicitar_propuesta(token):
    log(f"2. Solicitando Propuesta (TXT) para {PERIODO_TRIBUTARIO}...")
    endpoint = f"/libros/rce/propuesta/web/propuesta/{PERIODO_TRIBUTARIO}/exportacioncomprobantepropuesta"
    url = URL_BASE + endpoint
    params = {'codTipoArchivo': '0', 'codOrigenEnvio': '2'}
    headers = COMMON_HEADERS.copy()
    headers['Authorization'] = f'Bearer {token}'

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        ticket = response.json().get('numTicket')
        log(f"   > Ticket generado: {ticket}")
        return ticket
    except Exception as e:
        log(f"Error Solicitud: {e}")
        sys.exit()

def esperar_ticket(token, ticket):
    log(f"3. Monitoreando ticket {ticket}...")
    endpoint = "/libros/rvierce/gestionprocesosmasivos/web/masivo/consultaestadotickets"
    url = URL_BASE + endpoint
    
    params = {
        'numTicket': ticket,
        'perIni': PERIODO_TRIBUTARIO,
        'perFin': PERIODO_TRIBUTARIO,
        'page': 1,
        'perPage': 20
    }
    headers = COMMON_HEADERS.copy()
    headers['Authorization'] = f'Bearer {token}'

    intentos = 0
    while intentos < 20:
        try:
            response = requests.get(url, params=params, headers=headers)
            if response.status_code == 422:
                log(f"Error 422: {response.text}")
                sys.exit()
                
            data = response.json()
            if 'registros' in data and len(data['registros']) > 0:
                registro = data['registros'][0]
                estado = registro.get('desEstadoProceso')
                
                log(f"   > Intento {intentos+1}: Estado = {estado}")

                if estado == 'Terminado' or registro.get('codEstadoProceso') == '06':
                    # --- EXTRACCIÓN DE DATOS CRÍTICOS ---
                    raw_archivo = registro.get('archivoReporte')
                    archivo_info = raw_archivo[0] if isinstance(raw_archivo, list) else (raw_archivo or {})
                    
                    datos_descarga = {
                        'nomArchivo': archivo_info.get('nomArchivoReporte'),
                        'codTipo': registro.get('codTipoArchivoReporte') or '01',
                        'codProceso': registro.get('codProceso') # <--- ESTE FALTABA
                    }
                    
                    if not datos_descarga['nomArchivo']:
                        log("Error: No se encontró nombre de archivo en la respuesta.")
                        sys.exit()
                        
                    return datos_descarga
                
            time.sleep(5)
            intentos += 1
        except Exception as e:
            log(f"Error polling: {e}")
            time.sleep(5)
    sys.exit("Timeout")

def descargar_y_mostrar(token, datos, ticket_origen):
    """
    Servicio 5.32 CORREGIDO:
    Se envía la combinación exacta de 6 parámetros que exige el backend.
    """
    nom_archivo = datos['nomArchivo']
    cod_tipo = datos['codTipo']
    cod_proceso = datos['codProceso']
    
    # Ajuste TXT -> ZIP
    if str(cod_tipo) == '0' or str(cod_tipo) == '00': cod_tipo = '01'

    log(f"4. Descargando: {nom_archivo} (Proceso: {cod_proceso})...")
    
    endpoint = "/libros/rvierce/gestionprocesosmasivos/web/masivo/archivoreporte"
    url = URL_BASE + endpoint
    
    # --- LA LLAVE MAESTRA ---
    # Esta es la combinación exacta que evita el Error 500
    params = {
        'nomArchivoReporte': nom_archivo,
        'codTipoArchivoReporte': cod_tipo,
        'codLibro': '080000',           
        'perTributario': PERIODO_TRIBUTARIO,
        'numTicket': ticket_origen,
        'codProceso': cod_proceso        # <--- VITAL PARA NO ROMPER EL SERVIDOR
    }
    
    headers = COMMON_HEADERS.copy()
    headers['Authorization'] = f'Bearer {token}'

    try:
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code != 200:
            log(f"Fallo Servidor ({response.status_code})")
            log(f"URL Generada: {response.url}")
            response.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            nombre_txt = z.namelist()[0]
            log(f"5. Descomprimiendo {nombre_txt}...")
            with z.open(nombre_txt) as f:
                contenido = f.read().decode('latin-1')
                imprimir_tabla(contenido)

    except Exception as e:
        log(f"Error Descarga: {e}")

def imprimir_tabla(contenido_txt):
    lineas = contenido_txt.strip().split('\n')
    print("\n" + "="*110)
    print(f"| {'FECHA':<10} | {'TIPO':<3} | {'SERIE':<5} | {'NUMERO':<8} | {'RUC PROV':<11} | {'RAZON SOCIAL':<25} | {'TOTAL':>10} |")
    print("="*110)

    for linea in lineas:
        if not linea.strip(): continue
        campos = linea.split('|')
        if len(campos) < 15: continue 
        try:
            print(f"| {campos[4]:<10} | {campos[6]:<3} | {campos[7]:<5} | {campos[9]:<8} | {campos[11]:<11} | {campos[12][:25]:<25} | {campos[14]:>10} |")
        except: pass
    print("="*110 + "\n")

if __name__ == "__main__":
    t = obtener_token()
    tick = solicitar_propuesta(t)
    datos_archivo = esperar_ticket(t, tick)
    descargar_y_mostrar(t, datos_archivo, tick)