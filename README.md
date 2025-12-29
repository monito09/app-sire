# App SIRE - Descarga Masiva de Comprobantes SUNAT

Herramienta automatizada para la consulta y descarga masiva de comprobantes de pago electrónicos (PDF y XML) y propuestas del Registro de Compras Electrónico (RCE) desde el portal SOL de SUNAT.

## Características

- **Descarga Automatizada**: Utiliza Playwright para navegar el portal SOL invisiblemente (headless) y descargar comprobantes.
- **Acceso API**: Se conecta a la API SIRE para descargar reportes masivos y propuestas RCE.
- **Lectura de Reportes**: Procesa automáticamente los archivos ZIP descargados y muestra el contenido en una tabla interactiva.
- **Exportación a Excel**: Permite exportar los datos visualizados a archivos Excel.
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
    - Clic en **"Iniciar Proceso"** para descargar la propuesta.
    - La tabla se llenará con los comprobantes.
    - Usa **"VerDescripcion"** (botón "📥 BAJAR") para descargar PDF/XML individuales.
    - Clic en **"Exportar Excel"** para guardar el reporte.

## Estructura del Proyecto

- `controllers/`: Lógica de control y coordinación.
- `services/`: Lógica de negocio (API SUNAT, Playwright, Excel).
- `views/`: Interfaz gráfica (CustomTkinter).
- `utils/`: Utilidades comunes (archivos, logs).
- `downloads/`: Carpeta donde se guardan los archivos descargados (PDF, XML, ZIP, Excel).

## Tecnologías Utilizadas

- **CustomTkinter**: Interfaz de usuario moderna.
- **Playwright**: Automatización de navegador para descargas difíciles.
- **Requests**: Comunicación con la API REST de SUNAT.
- **Pandas**: Procesamiento de datos y Excel.
