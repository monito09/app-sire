import pandas as pd
import numpy as np
import zipfile
import os
import json
from utils.sunat_formatting import format_quantity, get_unit_description

class ExcelProcessor:
    COLUMN_MAPPING = {
        13: 'RazonSocialProveedor',
        12: 'RucProveedor', 
        11: 'TipoDocProveedor',         
        4: 'FechaEmision',
        5: 'FechaVencimiento',
        25: 'Moneda',
        7: 'Serie',
        9: 'Numero',
        14: 'BaseImponible',
        15: 'IGV',
        23: 'ImporteTotal'
    }

    COLUMNS_FINAL = [
        'FechaEmision', 'FechaVencimiento', 'CondicionPago', 'Moneda','TipoDocProveedor', 
        'RucProveedor', 'RazonSocialProveedor', 'Serie', 'Numero', 
        'GlosaResumen', 'BaseImponible', 'IGV', 'ImporteTotal'
    ]

    def __init__(self):
        self.df_actual = None
        self.ruta_zip_actual = None

    def procesar_zip(self, ruta_zip, callback_status):
        """
        Procesa el ZIP descargado de SUNAT y retorna un DataFrame.
        """
        callback_status("Procesando archivo ZIP...")
        
        try:
            with zipfile.ZipFile(ruta_zip, 'r') as z:
                archivos = z.namelist()
                archivo_datos = [a for a in archivos if a.endswith('.txt') or a.endswith('.csv')]
                
                if not archivo_datos:
                    raise Exception("No se encontró un archivo de datos (.txt o .csv) dentro del ZIP.")
                
                nombre_archivo_interno = archivo_datos[0]
                
                with z.open(nombre_archivo_interno) as f:
                    df = pd.read_csv(f, sep="|", encoding="latin-1", header=None, on_bad_lines='skip')
                    
                    df.rename(columns=self.COLUMN_MAPPING, inplace=True)

                    # Verificar columnas críticas
                    # Si el archivo es "vacío" o tiene formato incorrecto, el mapeo no encontrará column 12 (RUC)
                    required_cols = ['RucProveedor', 'Serie']
                    missing_cols = [c for c in required_cols if c not in df.columns]
                    
                    if missing_cols:
                        callback_status("⚠️ Archivo sin estructura válida de comprobantes.")
                        return pd.DataFrame()

                    df = self._clean_data(df)

                    # Validación Estricta: Eliminar filas que no tengan RUC válido (debe ser numérico)
                    # 1. Eliminar nulos/vacíos
                    df = df[df['RucProveedor'].notna() & (df['RucProveedor'].astype(str).str.strip() != '')]
                    # 2. Asegurar que sea numérico (elimina cabeceras o metadatos)
                    # Convertimos a string, quitamos .0 por si acaso parseó como float, y verificamos dígitos
                    df = df[df['RucProveedor'].astype(str).str.replace(r'\.0$', '', regex=True).str.isdigit()]

                    if df.empty:
                         callback_status("⚠️ El archivo procesado no contiene comprobantes válidos.")
                         return pd.DataFrame() # Return empty DF

                    cols_a_exportar = [c for c in self.COLUMNS_FINAL if c in df.columns]
                    df_final = df[cols_a_exportar]
                    
                    if df_final.empty:
                        return pd.DataFrame()

                    # Guardar referencia para exportación posterior
                    self.df_actual = df_final
                    self.ruta_zip_actual = ruta_zip
                    
                    callback_status(f"Datos procesados: {len(df_final)} registros")
                    return df_final

        except Exception as e:
            raise Exception(f"Error procesando ZIP: {str(e)}")

    def _clean_data(self, df):
        """Limpia y transforma los datos del DataFrame."""

        if 'RazonSocialProveedor' in df.columns:
             # Limpieza básica para quitar espacios extra
             df['RazonSocialProveedor'] = df['RazonSocialProveedor'].astype(str).str.strip()

        # 1. Fechas y Filtrado de Cabeceras
        if 'FechaEmision' in df.columns:
            df['FechaEmision'] = pd.to_datetime(df['FechaEmision'], format='%d/%m/%Y', dayfirst=True, errors='coerce')
            df = df.dropna(subset=['FechaEmision']).copy() # FIX: .copy() para evitar SettingWithCopyWarning

        if 'FechaVencimiento' in df.columns:
            df['FechaVencimiento'] = pd.to_datetime(df['FechaVencimiento'], format='%d/%m/%Y', dayfirst=True, errors='coerce')
        
        # 2. Numéricos
        cols_num = ['BaseImponible', 'IGV', 'ImporteTotal']
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        # 3. Recalcular Total
        if 'BaseImponible' in df.columns and 'IGV' in df.columns:
            df['ImporteTotal'] = df['BaseImponible'] + df['IGV']

        # 4. Campos Calculados
        
        if 'FechaVencimiento' in df.columns and 'FechaEmision' in df.columns:
            df['CondicionPago'] = np.where(
                (df['FechaVencimiento'].notnull()) & (df['FechaVencimiento'] > df['FechaEmision']),
                'CREDITO',
                'CONTADO'
            )
            
            df['DiasCredito'] = (df['FechaVencimiento'] - df['FechaEmision']).dt.days
            df['DiasCredito'] = df['DiasCredito'].fillna(0).astype(int)
        else:
            df['CondicionPago'] = 'CONTADO'
            df['DiasCredito'] = 0
        
        if all(col in df.columns for col in ['RazonSocialProveedor', 'Serie', 'Numero']):
            df['GlosaResumen'] = (
                "COMPRA A " + df['RazonSocialProveedor'].astype(str) + 
                " DOC: " + df['Serie'].astype(str) + "-" + df['Numero'].astype(str)
            )
            df['VerGlosaResumen'] = "📥 VER"
        else:
            df['GlosaResumen'] = "SIN DATOS SUFICIENTES"
            df['VerGlosaResumen'] = ""
            
        return df
    
    def exportar_a_excel(self, df=None, ruta_salida=None, callback_status=None):
        """
        Exporta el DataFrame a Excel.
        Si no se proporciona df, usa el último procesado.
        """
        try:
            df_a_exportar = df if df is not None else self.df_actual
            
            if df_a_exportar is None or df_a_exportar.empty:
                raise Exception("No hay datos para exportar")
            
            # --- ENRIQUECIMIENTO CON DESCRIPCIONES, CANTIDAD Y UNIDAD ---
            df_final = df_a_exportar.copy()
            xml_desc_dir = os.path.join(os.getcwd(), 'downloads', 'xml')
            
            # Preparar listas para nuevas columnas
            descripciones = []
            cantidades = []
            unidades = []
            
            for idx, row in df_final.iterrows():
                desc = ""
                cant = ""
                und = ""
                
                try:
                    if 'Serie' in row and 'Numero' in row:
                        s = str(row['Serie'])
                        n = str(row['Numero'])
                        
                        json_path = os.path.join(xml_desc_dir, f"{s}-{n}.json")
                        txt_path = os.path.join(xml_desc_dir, f"{s}-{n}.txt")
                        
                        if os.path.exists(json_path):
                            with open(json_path, 'r', encoding='utf-8') as f:
                                items = json.load(f)
                                if items:
                                    first_item = items[0]
                                    desc = first_item.get('descripcion', '')
                                    cant = format_quantity(first_item.get('cantidad', ''))
                                    und = get_unit_description(first_item.get('unidad', ''))
                        elif os.path.exists(txt_path):
                            # Fallback
                            with open(txt_path, 'r', encoding='utf-8') as f:
                                desc = f.read().strip()
                except:
                    pass
                
                descripciones.append(desc)
                cantidades.append(cant)
                unidades.append(und)

            if callback_status:
                callback_status("Agregando descripciones y detalles descargados...")
            
            df_final['Descripcion'] = descripciones
            df_final['Cantidad'] = cantidades
            df_final['Unidad de Medida'] = unidades
            
            # Reordenar para poner estos campos al final o cerca del Importe Total
            # El usuario pidió "al lado de la ultima columna", por defecto se agregan al final.
            # Solo moveremos Descripcion para que esté antes de Cantidad si ya no lo está.
            # Como se agregan secuencialmente, estarán al final en orden: Descripcion, Cantidad, Unidad_Medida
            # -----------------------------------------

            if ruta_salida is None:
                # Generar nombre legible: Reporte_SIRE_YYYYMMDD_HHMMSS.xlsx
                import time
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                nombre_base = f"Reporte_SIRE_{timestamp}.xlsx"
                
                # Guardar en la carpeta downloads
                ruta_salida = os.path.join(os.getcwd(), 'downloads', 'excel', nombre_base)
            
            # Asegurar directorio
            os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)

            if callback_status:
                callback_status(f"Exportando {len(df_final)} registros a Excel...")
            
            df_final.to_excel(ruta_salida, index=False)
            
            if callback_status:
                callback_status(f"Excel generado: {ruta_salida}")
            
            return ruta_salida
            
        except Exception as e:
            raise Exception(f"Error exportando Excel: {str(e)}")
