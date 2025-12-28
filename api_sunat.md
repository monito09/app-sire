Aquí tienes el código detallado para cada uno de los requerimientos técnicos necesarios, basado estrictamente en los endpoints y parámetros definidos en el manual (PDF) que proporcionaste.

Puedes copiar estos métodos dentro de tu archivo `services/sunat_api.py`.

### Requisitos Previos (Librerías)
```bash
pip install requests pandas openpyxl
```

---

### 1. Autenticación (Obtener Token)
**Referencia Manual:** 5.1 Servicio Api Seguridad (Pág. 38).
Este método intercambia tus credenciales (Client ID/Secret) por un *Token Bearer* que dura 3600 segundos.

```python
import requests

def obtener_token(client_id, client_secret, ruc, usuario_sol, clave_sol):
    url = f"https://api-seguridad.sunat.gob.pe/v1/clientessol/{client_id}/oauth2/token/"
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "password",
        "scope": "https://api-sire.sunat.gob.pe",
        "client_id": client_id,
        "client_secret": client_secret,
        "username": ruc + usuario_sol, # IMPORTANTE: Se concatena RUC + Usuario
        "password": clave_sol
    }

    response = requests.post(url, headers=headers, data=data)
    
    if response.status_code == 200:
        # Retorna el access_token para usarlo en las siguientes llamadas
        return response.json().get("access_token")
    else:
        raise Exception(f"Error Autenticación (HTTP {response.status_code}): {response.text}")
```

---

### 2. Solicitar Descarga Masiva (Propuesta de Compras)
**Referencia Manual:** 5.34 Servicio Web Api descargar propuesta (Pág. 84).
Este servicio no descarga el archivo directamente, sino que le pide a SUNAT que lo genere. Retorna un `numTicket`.

```python
def solicitar_propuesta_compras(token, periodo_tributario):
    """
    periodo_tributario: Formato YYYYMM (ej. "202501")
    """
    base_url = "https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/propuesta/web/propuesta"
    endpoint = f"{base_url}/{periodo_tributario}/exportacioncomprobantepropuesta"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    # Parámetros según Pág 84
    params = {
        "codTipoArchivo": "0",   # 0: TXT (Zipeado), 1: CSV
        "codOrigenEnvio": "2"    # 2: Servicio Web API
    }

    response = requests.get(endpoint, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        return data.get("numTicket") # Guardar este ticket
    else:
        raise Exception(f"Error Solicitud (HTTP {response.status_code}): {response.text}")
```

---

### 3. Consultar Estado del Ticket (Polling)
**Referencia Manual:** 5.31 Servicio Web Api consultar estado ticket (Pág. 79).
Debes consultar repetidamente este servicio hasta que el estado sea "Terminado". Aquí obtenemos el nombre del archivo final.

```python
import time

def esperar_ticket_terminado(token, num_ticket, periodo):
    url = "https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/gestionprocesosmasivos/web/masivo/consultaestadotickets"
    
    headers = {"Authorization": f"Bearer {token}"}
    
    params = {
        "perIni": periodo,   # Obligatorio según Pág 79
        "perFin": periodo,   # Obligatorio
        "page": 1,
        "perPage": 20,
        "numTicket": num_ticket
    }

    intentos = 0
    max_intentos = 20 # Evitar bucle infinito
    
    while intentos < max_intentos:
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            registros = data.get("registros", [])
            
            # Buscar nuestro ticket
            ticket_data = next((item for item in registros if item["numTicket"] == num_ticket), None)
            
            if ticket_data:
                estado = ticket_data.get("desEstadoProceso") # Ej: "Terminado", "Proceso", "Error"
                
                if estado == "Terminado":
                    # Extraer datos para la descarga (Pág 80 - Detalle Ticket)
                    # La estructura suele ser anidada
                    archivos = ticket_data.get("archivoReporte", [])
                    if archivos:
                        return {
                            "nomArchivo": archivos[0].get("nomArchivoReporte"),
                            "codTipoArchivo": archivos[0].get("codTipoArchivoReporte") # Usualmente 01
                        }
                elif estado == "Error":
                    raise Exception("El ticket terminó con errores en SUNAT.")
                    
        # Si no terminó, esperar 5 segundos y reintentar
        print(f"Ticket {num_ticket} en proceso... intento {intentos+1}")
        time.sleep(5)
        intentos += 1
        
    raise Exception("Tiempo de espera agotado para el ticket.")
```

---

### 4. Descargar el Archivo (ZIP)
**Referencia Manual:** 5.32 Servicio Web Api descargar archivo (Pág. 82).
Descarga el flujo de bytes (el ZIP) usando el nombre obtenido en el paso anterior.

```python
def descargar_archivo_zip(token, nom_archivo, cod_tipo_archivo="01"):
    url = "https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/gestionprocesosmasivos/web/masivo/archivoreporte"
    
    headers = {"Authorization": f"Bearer {token}"}
    
    params = {
        "nomArchivoReporte": nom_archivo,
        "codTipoArchivoReporte": cod_tipo_archivo
    }

    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        return response.content # Retorna bytes (el ZIP)
    else:
        raise Exception(f"Error Descarga (HTTP {response.status_code}): {response.text}")
```

---

### 5. Procesamiento y Generación de Excel (Lógica de Negocio)
Este código cumple tu requerimiento de **identificar glosa, montos y condición de pago (crédito/contado)** usando Pandas.

```python
import pandas as pd
import zipfile
import io
import numpy as np

def generar_excel_inteligente(contenido_zip_bytes, nombre_salida="Reporte_SIRE.xlsx"):
    # 1. Descomprimir en memoria
    with zipfile.ZipFile(io.BytesIO(contenido_zip_bytes)) as z:
        # Normalmente hay un solo TXT o CSV dentro
        nombre_txt = z.namelist()[0]
        
        with z.open(nombre_txt) as f:
            # 2. Leer el archivo TXT/CSV
            # NOTA: El separador suele ser "|" en los TXT de SIRE. 
            # La codificación suele ser 'latin-1' o 'utf-8'.
            df = pd.read_csv(f, sep="|", encoding="latin-1", header=None)

    # 3. Asignar Nombres de Columnas (Basado en estructura estándar RCE Propuesta)
    # Esta estructura puede variar levemente, valida con un archivo real descargado.
    # Columnas típicas: Ruc, RazonSocial, Serie, Numero, FecEmision, FecVencimiento, Montos...
    
    # Ejemplo aproximado de columnas clave (ajustar índices según archivo real):
    # Supongamos que: Col 4=FecEmision, Col 5=FecVencimiento, Col 14=MontoBase, Col 20=Total, Col 2=RazonSocial
    # Tienes que inspeccionar tu primer archivo descargado para ajustar estos índices.
    
    try:
        # Renombramos columnas clave para trabajar (ajusta los índices)
        df.rename(columns={
            2: 'RazonSocialProveedor',
            3: 'FechaEmision',
            4: 'FechaVencimiento',
            6: 'Serie',
            7: 'Numero',
            10: 'TipoDoc', # 01 Factura
            14: 'BaseImponible',
            15: 'IGV',
            23: 'ImporteTotal'
        }, inplace=True)
    except:
        print("Advertencia: Verifica los índices de columnas del TXT de SUNAT")

    # 4. Lógica: Crédito o Contado
    # Convertimos a formato fecha
    df['FechaEmision'] = pd.to_datetime(df['FechaEmision'], dayfirst=True, errors='coerce')
    df['FechaVencimiento'] = pd.to_datetime(df['FechaVencimiento'], dayfirst=True, errors='coerce')

    # Si hay fecha vencimiento Y es mayor a emisión + 1 día, es crédito (regla simple)
    df['CondicionPago'] = np.where(
        (df['FechaVencimiento'].notnull()) & (df['FechaVencimiento'] > df['FechaEmision']),
        'CREDITO',
        'CONTADO'
    )
    
    # Calcular días de crédito
    df['DiasCredito'] = (df['FechaVencimiento'] - df['FechaEmision']).dt.days
    df['DiasCredito'] = df['DiasCredito'].fillna(0).astype(int)

    # 5. Generar Glosa Automática (Concatenando datos)
    # Como el SIRE no siempre trae el detalle del producto, creamos una glosa resumen
    df['GlosaResumen'] = (
        "COMPRA A " + df['RazonSocialProveedor'].astype(str) + 
        " DOC: " + df['Serie'].astype(str) + "-" + df['Numero'].astype(str)
    )

    # 6. Seleccionar y ordenar columnas para el Excel Final
    columnas_finales = [
        'FechaEmision', 'FechaVencimiento', 'CondicionPago', 'DiasCredito',
        'RazonSocialProveedor', 'Serie', 'Numero', 'GlosaResumen',
        'BaseImponible', 'IGV', 'ImporteTotal'
    ]
    
    # Filtrar solo si existen en el DF (para evitar errores si el mapeo falló)
    cols_a_exportar = [c for c in columnas_finales if c in df.columns]
    
    df_final = df[cols_a_exportar]

    # 7. Exportar
    df_final.to_excel(nombre_salida, index=False)
    print(f"Excel generado: {nombre_salida}")
```

### Cómo unir todo en tu Botón de Tkinter

Dentro de la función que ejecuta tu botón "Descargar" (usando hilos como recomendé en la respuesta anterior):

```python
def logica_negocio_completa():
    # 1. Login
    token = obtener_token(CLIENT_ID, CLIENT_SECRET, RUC, USUARIO, CLAVE)
    
    # 2. Solicitar
    ticket = solicitar_propuesta_compras(token, "202501")
    
    # 3. Esperar
    datos_archivo = esperar_ticket_terminado(token, ticket, "202501")
    nombre_archivo = datos_archivo["nomArchivo"]
    
    # 4. Descargar
    contenido_zip = descargar_archivo_zip(token, nombre_archivo)
    
    # 5. Generar Excel
    generar_excel_inteligente(contenido_zip, "Compras_Enero_2025.xlsx")
```