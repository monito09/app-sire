import pandas as pd
import numpy as np
import zipfile
import os

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
                    df = self._clean_data(df)
                    
                    cols_a_exportar = [c for c in self.COLUMNS_FINAL if c in df.columns]
                    df_final = df[cols_a_exportar]
                    
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
            
            # --- ENRIQUECIMIENTO CON DESCRIPCIONES ---
            df_final = df_a_exportar.copy()
            xml_desc_dir = os.path.join(os.getcwd(), 'downloads', 'xml')
            
            def get_descripcion(row):
                try:
                    if 'Serie' in row and 'Numero' in row:
                        s = str(row['Serie'])
                        n = str(row['Numero'])
                        txt_path = os.path.join(xml_desc_dir, f"{s}-{n}.txt")
                        if os.path.exists(txt_path):
                            with open(txt_path, 'r', encoding='utf-8') as f:
                                return f.read().strip()
                except:
                    pass
                return ""

            if callback_status:
                callback_status("Agregando descripciones descargadas...")
            
            df_final['Descripcion'] = df_final.apply(get_descripcion, axis=1)
            
            # Reordenar columnas para poner Descripcion después de ImporteTotal
            cols = list(df_final.columns)
            if 'ImporteTotal' in cols and 'Descripcion' in cols:
                cols.remove('Descripcion')
                idx = cols.index('ImporteTotal') + 1
                cols.insert(idx, 'Descripcion')
                df_final = df_final[cols]
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
