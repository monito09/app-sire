# App SIRE - Descarga Masiva de Comprobantes SUNAT

Herramienta automatizada para la consulta y descarga masiva de comprobantes de pago electrónicos (PDF y XML) y propuestas del Registro de Compras Electrónico (RCE) desde el portal SOL de SUNAT.

## Características Nuevas (v2.1)

- **Extracción de Detalles desde XML**: Ahora se extrae automáticamente la **Descripción**, **Cantidad** y **Unidad de Medida** del primer ítem de cada factura para mostrarlo en el dashboard.
- **Formato Inteligente**: Las cantidades se muestran limpias (sin ceros innecesarios) y las unidades con nombres legibles (ej: "UNIDAD" en vez de "NIU").
- **Validación de Antigüedad**: Advierte si seleccionas un periodo mayor a 24 meses, donde la descarga directa de PDF/XML está restringida por SUNAT.
- **Detección de Datos Vacíos**: Identifica correctamente cuando un periodo no tiene movimientos, evitando reportes con registros fantasma.

## Características Principales

- **Descarga Automatizada**: Utiliza Playwright para navegar el portal SOL invisiblemente (headless) y descargar comprobantes.
- **Acceso API**: Se conecta a la API SIRE para descargar reportes masivos y propuestas RCE.
- **Lectura de Reportes**: Procesa automáticamente los archivos ZIP descargados y muestra el contenido en una tabla interactiva.
- **Exportación a Excel**: Exporta el reporte completo incluyendo las nuevas columnas (Cantidad, Unidad, Descripción) extraídas del XML.
- **Anti-Bloqueo**: Implementa técnicas para evadir detección de automatización por parte de SUNAT.

## Requisitos Previos

- Python 3.9 o superior
- Google Chrome instalado

## Instalación

1.  **Clonar el repositorio o descargar el código fuente.**

2.  **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Instalar navegadores de Playwright:**
    ```bash
    playwright install chromium
    ```

## Configuración

Crea un archivo `config.json` en la raíz del proyecto con tus credenciales SOL:

```json
{
    "ruc": "20XXXXXXXXX",
    "usuario_sol": "TU_USUARIO",
    "clave_sol": "TU_CLAVE"
}
```

> **Nota:** El archivo `config.json` contiene credenciales sensibles. Asegúrate de añadirlo a tu `.gitignore` para no subirlo a repositorios públicos.

## Uso

1.  **Ejecutar la aplicación:**
    ```bash
    python main.py
    ```

2.  **Interfaz Gráfica:**
    - Selecciona o ingresa el **Periodo** (Formato AAAAMM, ej: 202501).
    - Clic en **"Descargar y Procesar"** para obtener la propuesta.
    - La tabla se llenará con los comprobantes encontrados.
        - *Nota*: Si el periodo es muy antiguo (>24 meses), solo verás datos generales.
    - Usa la columna **"VerDescripcion"** (botón "📥 OBTENER") para descargar PDF/XML individuales y extraer sus detalles.
    - Clic en **"Exportar Excel"** para guardar el reporte enriquecido con los detalles extraídos.

## Estructura del Proyecto

- `controllers/`: Lógica de control y coordinación.
- `services/`: Lógica de negocio (API SUNAT, Playwright, ExcelProcessor).
- `views/`: Interfaz gráfica moderna usando `ttkbootstrap`.
- `utils/`: Utilidades para formateo (SUNAT), archivos y logs.
- `downloads/`: Carpeta donde se guardan los archivos descargados (PDF, XML, ZIP, Excel).

## Tecnologías Utilizadas

- **ttkbootstrap**: Interfaz de usuario moderna y responsiva.
- **Playwright**: Automatización de navegador para descargas difíciles.
- **Requests**: Comunicación con la API REST de SUNAT.
- **Pandas**: Procesamiento de datos y Excel.
- **XML/JSON**: Procesamiento de la estructura de facturas electrónicas.
