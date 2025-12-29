import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import pandas as pd

class DashboardView(tk.Tk):
    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller
        self.df_actual = None
        
        # Configuración de la ventana
        self.title("Descarga Masiva SIRE SUNAT")
        self.geometry("1100x650")
        self.resizable(True, True)
        
        # Estilos
        self.style = ttk.Style()
        self.style.configure("TButton", font=("Helvetica", 10))
        self.style.configure("TLabel", font=("Helvetica", 10))
        
        self._create_widgets()

    def set_controller(self, controller):
        self.controller = controller

    def _create_widgets(self):
        # Frame Principal
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        lbl_title = ttk.Label(main_frame, text="Sistema de Descarga SIRE", font=("Helvetica", 14, "bold"))
        lbl_title.pack(pady=(0, 10))
        
        # --- SECCIÓN DE PARÁMETROS ---
        param_frame = ttk.LabelFrame(main_frame, text="Parámetros de Consulta", padding="10")
        param_frame.pack(fill=tk.X, pady=5)
        
        # Selección de Periodo
        frame_combo = ttk.Frame(param_frame)
        frame_combo.pack(fill=tk.X)
        
        ttk.Label(frame_combo, text="Periodo:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.periodo_var = tk.StringVar()
        self.combo_periodo = ttk.Combobox(
            frame_combo, 
            textvariable=self.periodo_var,
            state="readonly",
            width=40
        )
        self.combo_periodo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.combo_periodo.set("Cargando periodos...")
        
        # Botón de Descarga
        self.btn_descargar = ttk.Button(
            frame_combo, 
            text=" Descargar y Visualizar", 
            command=self._on_descargar_click
        )
        self.btn_descargar.pack(side=tk.LEFT, padx=5)
        
        # --- SECCIÓN DE TABLA DE DATOS ---
        tabla_frame = ttk.LabelFrame(main_frame, text="Datos SUNAT", padding="10")
        tabla_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Frame para TreeView con scrollbars
        tree_container = ttk.Frame(tabla_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_container, orient="vertical")
        hsb = ttk.Scrollbar(tree_container, orient="horizontal")
        
        # TreeView
        self.tree = ttk.Treeview(
            tree_container,
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            height=15
        )
        
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)
        
        # Layout
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)
        
        # Botón de Exportación (inicialmente deshabilitado)
        self.btn_exportar = ttk.Button(
            tabla_frame,
            text=" Exportar a Excel",
            command=self._on_exportar_click,
            state="disabled"
        )
        self.btn_exportar.pack(pady=5)
        
        # --- SECCIÓN DE LOGS ---
        log_frame = ttk.LabelFrame(main_frame, text="Registro de Actividad", padding="5")
        log_frame.pack(fill=tk.X, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, height=6, state='disabled', font=("Consolas", 8))
        self.log_area.pack(fill=tk.BOTH, expand=True)

    # --- MÉTODOS DE INTERACCIÓN ---

    def actualizar_combo_periodos(self, lista_periodos):
        """
        Recibe una lista de diccionarios [{'periodo': '202501', 'descripcion': '202501 - Presentado'}, ...]
        y llena el Combobox.
        """
        if not lista_periodos:
            self.combo_periodo['values'] = ["Sin periodos disponibles"]
            self.combo_periodo.current(0)
            return

        # Extraemos solo las descripciones para mostrar
        valores_visuales = [item['descripcion'] for item in lista_periodos]
        self.combo_periodo['values'] = valores_visuales
        
        # Seleccionar el primero por defecto (generalmente el más reciente)
        if valores_visuales:
            self.combo_periodo.current(0)

    def get_periodo(self):
        """
        Obtiene el periodo limpio (ej: '202501') del texto seleccionado (ej: '202501 - Presentado')
        """
        texto_seleccionado = self.periodo_var.get()
        if not texto_seleccionado or "Cargando" in texto_seleccionado:
            return ""
        # Extraemos solo los primeros 6 caracteres (el periodo)
        return texto_seleccionado.split(" - ")[0].strip()

    def _on_descargar_click(self):
        if self.controller:
            self.controller.iniciar_proceso()
    
    def _on_exportar_click(self):
        if self.controller:
            self.controller.exportar_excel()

    def log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"> {message}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def mostrar_datos_tabla(self, df):
        """
        Muestra los datos del DataFrame en el TreeView.
        """
        try:
            # Guardar referencia al DataFrame COMPLETO (para exportar)
            self.df_actual = df
            
            # Limpiar tabla
            self.tree.delete(*self.tree.get_children())
            
            if df is None or df.empty:
                self.log("No hay datos para mostrar")
                return
            
            # CONFIGURAR COLUMNAS A MOSTRAR EN LA VISTA
            # Define aquí las columnas que quieres ver en la tabla
            # IMPORTANTE: Usar los nombres exactos que vienen del excel_processor
            
            # Configuración de columnas: {columna: (ancho, alineación)}
            self.COLUMN_CONFIG = {
                'FechaEmision': (100, 'center'),
                'FechaVencimiento': (100, 'center'),
                'CondicionPago': (80, 'center'),
                'DiasCredito': (70, 'center'),
                'RazonSocialProveedor': (250, 'w'),
                'GlosaResumen': (250, 'w'),
                'Serie': (80, 'center'),
                'Numero': (80, 'center'),
                'BaseImponible': (100, 'e'),
                'IGV': (100, 'e'),
                'ImporteTotal': (100, 'e')
            }
            
            columnas_visibles = list(self.COLUMN_CONFIG.keys())
            
            # Filtrar solo las columnas que existen en el DataFrame
            columnas = [col for col in columnas_visibles if col in df.columns]
            
            # Si no hay columnas configuradas, mostrar las primeras 10
            if not columnas:
                columnas = list(df.columns)[:10]
            
            # Crear DataFrame filtrado solo para visualización
            df_vista = df[columnas].copy()
            self.tree['columns'] = columnas
            self.tree['show'] = 'headings'
            
            # Definir encabezados y columnas
            for col in columnas:
                self.tree.heading(col, text=col)
                
                # Obtener configuración o usar valores por defecto
                width, anchor = self.COLUMN_CONFIG.get(col, (100, 'w'))
                self.tree.column(col, width=width, anchor=anchor)
            
            # Insertar datos (limitar a 1000 registros para rendimiento)
            max_rows = min(1000, len(df_vista))
            for idx, row in df_vista.head(max_rows).iterrows():
                # Formatear valores para visualización
                valores = []
                for col in columnas:
                    val = row[col]
                    if pd.isna(val):
                        valores.append('')
                    elif isinstance(val, pd.Timestamp):
                        valores.append(val.strftime('%Y-%m-%d') if pd.notna(val) else '')
                    elif isinstance(val, (int, float)):
                        valores.append(f"{val:.2f}" if isinstance(val, float) else str(val))
                    else:
                        valores.append(str(val))
                
                self.tree.insert('', 'end', values=valores)
            
            # Habilitar botón de exportación
            self.btn_exportar.config(state="normal")
            
            if len(df) > max_rows:
                self.log(f"Mostrando {max_rows} de {len(df)} registros en la tabla")
            else:
                self.log(f"Mostrando {len(df)} registros")
                
        except Exception as e:
            self.log(f"Error mostrando datos: {str(e)}")
    
    def set_loading(self, is_loading):
        if is_loading:
            self.btn_descargar.config(state="disabled", text="Procesando...")
            self.btn_exportar.config(state="disabled")
            self.config(cursor="watch")
        else:
            self.btn_descargar.config(state="normal", text=" Descargar y Visualizar")
            self.config(cursor="")

    def show_info(self, title, msg):
        messagebox.showinfo(title, msg)

    def show_error(self, title, msg):
        messagebox.showerror(title, msg)
    
    def limpiar_tabla(self):
        """Limpia la tabla de datos"""
        self.tree.delete(*self.tree.get_children())
        self.btn_exportar.config(state="disabled")
        self.df_actual = None