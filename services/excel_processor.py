import pandas as pd
import numpy as np
import zipfile
import os
import io

class ExcelProcessor:
    def __init__(self):
        self.df_actual = None
        self.ruta_zip_actual = None

    def procesar_zip(self, ruta_zip, callback_status):
        """
        Procesa el ZIP descargado de SUNAT y retorna un DataFrame.
        NO genera Excel, solo procesa los datos.
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
                    
                    try:
                        df.rename(columns={
                            2: 'RazonSocialProveedor',
                            3: 'FechaEmision',
                            4: 'FechaVencimiento',
                            6: 'Serie',
                            7: 'Numero',
                            10: 'TipoDoc',
                            14: 'BaseImponible',
                            15: 'IGV',
                            23: 'ImporteTotal'
                        }, inplace=True)
                    except Exception as e:
                        callback_status(f"Advertencia: Estructura de columnas inesperada. {str(e)}")

                    df['FechaEmision'] = pd.to_datetime(df['FechaEmision'], dayfirst=True, errors='coerce')
                    df['FechaVencimiento'] = pd.to_datetime(df['FechaVencimiento'], dayfirst=True, errors='coerce')

                    df['CondicionPago'] = np.where(
                        (df['FechaVencimiento'].notnull()) & (df['FechaVencimiento'] > df['FechaEmision']),
                        'CREDITO',
                        'CONTADO'
                    )
                    
                    df['DiasCredito'] = (df['FechaVencimiento'] - df['FechaEmision']).dt.days
                    df['DiasCredito'] = df['DiasCredito'].fillna(0).astype(int)

                    if 'RazonSocialProveedor' in df.columns and 'Serie' in df.columns and 'Numero' in df.columns:
                        df['GlosaResumen'] = (
                            "COMPRA A " + df['RazonSocialProveedor'].astype(str) + 
                            " DOC: " + df['Serie'].astype(str) + "-" + df['Numero'].astype(str)
                        )
                    else:
                        df['GlosaResumen'] = "SIN DATOS SUFICIENTES"

                    columnas_finales = [
                        'FechaEmision', 'FechaVencimiento', 'CondicionPago', 'DiasCredito',
                        'RazonSocialProveedor', 'Serie', 'Numero', 'GlosaResumen',
                        'BaseImponible', 'IGV', 'ImporteTotal'
                    ]
                    
                    cols_a_exportar = [c for c in columnas_finales if c in df.columns]
                    df_final = df[cols_a_exportar]
                    
                    # Guardar referencia para exportación posterior
                    self.df_actual = df_final
                    self.ruta_zip_actual = ruta_zip
                    
                    callback_status(f"Datos procesados: {len(df_final)} registros")
                    return df_final

        except Exception as e:
            raise Exception(f"Error procesando ZIP: {str(e)}")
    
    def exportar_a_excel(self, df=None, ruta_salida=None, callback_status=None):
        """
        Exporta el DataFrame a Excel.
        Si no se proporciona df, usa el último procesado.
        """
        try:
            df_a_exportar = df if df is not None else self.df_actual
            
            if df_a_exportar is None or df_a_exportar.empty:
                raise Exception("No hay datos para exportar")
            
            if ruta_salida is None:
                if self.ruta_zip_actual:
                    ruta_salida = self.ruta_zip_actual.replace(".zip", "_Resumen.xlsx")
                else:
                    ruta_salida = "Resumen_SUNAT.xlsx"
            
            if callback_status:
                callback_status(f"Exportando {len(df_a_exportar)} registros a Excel...")
            
            df_a_exportar.to_excel(ruta_salida, index=False)
            
            if callback_status:
                callback_status(f"Excel generado: {ruta_salida}")
            
            return ruta_salida
            
        except Exception as e:
            raise Exception(f"Error exportando Excel: {str(e)}")
