import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.tableview import Tableview
from tkinter import filedialog
import pandas as pd

class DashboardView(ttk.Window):
    def __init__(self, controller=None):
        super().__init__(themename="flatly")
        self.controller = controller
        self.df_actual = None
        
        # Configuración de la ventana
        self.title("Sistema SIRE SUNAT - Dashboard")
        self.geometry("1200x800")
        
        # Configuración de columnas: {columna: (ancho, alineación)}
        self.COLUMN_CONFIG = {
            'FechaEmision': (100, 'center'),
            'FechaVencimiento': (100, 'center'),
            'CondicionPago': (100, 'center'),
            'DiasCredito': (80, 'center'),
            'TipoDocProveedor': (80, 'center'),
            'RucProveedor': (100, 'center'), 
            'RazonSocialProveedor': (300,'center'),
            'Serie': (80, 'center'),
            'Numero': (80, 'center'),
            'BaseImponible': (120, 'e'),
            'IGV': (110, 'e'),
            'ImporteTotal': (120, 'e'),
            'GlosaResumen': (300, 'w')
        }
        
        self._create_layout()

    def set_controller(self, controller):
        self.controller = controller

    def _create_layout(self):
        # 1. Header Principal
        header_frame = ttk.Frame(self, padding=20)
        header_frame.pack(fill=X)
        
        ttk.Label(header_frame, text="SIRE DOWNLOADER", font=("Helvetica", 20, "bold"), bootstyle="primary").pack(side=LEFT)
        ttk.Label(header_frame, text="v2.0", font=("Helvetica", 10), bootstyle="secondary").pack(side=LEFT, padx=10, pady=(10,0))

        # 2. Barra de Acciones (Periodo + Botones)
        action_bar = ttk.Frame(self, padding=(20, 0, 20, 20))
        action_bar.pack(fill=X)
        
        action_card = ttk.Labelframe(action_bar, text="Controles", padding=15, bootstyle="info")
        action_card.pack(fill=X)
        
        # Selector de Periodo
        ttk.Label(action_card, text="Periodo Tributario:").pack(side=LEFT, padx=(0, 10))
        
        self.periodo_var = ttk.StringVar()
        self.combo_periodo = ttk.Combobox(
            action_card, 
            textvariable=self.periodo_var,
            state="readonly",
            width=35,
            bootstyle="primary"
        )
        self.combo_periodo.pack(side=LEFT, padx=(0, 20))
        self.combo_periodo.set("Cargando periodos...")
        
        # Botones
        self.btn_descargar = ttk.Button(
            action_card, 
            text="Descargar y Procesar", 
            command=self._on_descargar_click,
            bootstyle="success",
            width=20
        )
        self.btn_descargar.pack(side=LEFT, padx=5)
        
        self.btn_exportar = ttk.Button(
            action_card,
            text="Exportar Excel",
            command=self._on_exportar_click,
            state="disabled",
            bootstyle="success-outline",
            width=20
        )
        self.btn_exportar.pack(side=LEFT, padx=5)

        # 3. KPI Cards Row
        self.kpi_frame = ttk.Frame(self, padding=(20, 0))
        self.kpi_frame.pack(fill=X, pady=10)
        
        self._create_kpi_card(self.kpi_frame, "Total Comprobantes", "0", "secondary")
        self._create_kpi_card(self.kpi_frame, "Base Imponible", "S/ 0.00", "primary")
        self._create_kpi_card(self.kpi_frame, "Total IGV", "S/ 0.00", "info")
        self._create_kpi_card(self.kpi_frame, "Importe Total", "S/ 0.00", "success")

        # 4. Buscador
        search_frame = ttk.Frame(self, padding=(20, 5))
        search_frame.pack(fill=X)
        
        ttk.Label(search_frame, text="Filtrar resultados:", bootstyle="secondary").pack(side=LEFT, padx=(0, 10))
        self.search_var = ttk.StringVar()
        self.search_var.trace("w", self._on_search_change)
        
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=50)
        search_entry.pack(side=LEFT)
        
        # 5. Tabla de Datos
        table_frame = ttk.Frame(self, padding=20)
        table_frame.pack(fill=BOTH, expand=True)
        
        # Usamos Treeview estándar pero con estilo de ttkbootstrap
        self.tree = ttk.Treeview(
            table_frame, 
            columns=list(self.COLUMN_CONFIG.keys()), 
            show='headings',
            bootstyle="primary"
        )
        
        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Configurar cabeceras
        for col, (width, anchor) in self.COLUMN_CONFIG.items():
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor=anchor)

        # Binding para doble click (copiar celda)
        self.tree.bind("<Double-1>", self._on_double_click)

        # 6. Status Bar / Progress
        status_frame = ttk.Frame(self, padding=(5, 2))
        status_frame.pack(fill=X, side=BOTTOM)
        
        self.lbl_status = ttk.Label(status_frame, text="Sistema listo.", font=("Consolas", 9))
        self.lbl_status.pack(side=LEFT)
        
        self.progress = ttk.Progressbar(status_frame, mode='indeterminate', length=200, bootstyle="success-striped")
        # El progress se mostrará solo cuando sea necesario

    def _on_double_click(self, event):
        """
        Muestra un Entry sobre la celda al hacer doble click para permitir copiar el texto.
        """
        # Identificar qué se clickeó
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        # Obtener coordenadas y datos
        column = self.tree.identify_column(event.x) # e.g. #1
        row_id = self.tree.identify_row(event.y)
        
        if not row_id:
            return

        # Obtener valor de la celda
        col_idx = int(column.replace('#', '')) - 1
        values = self.tree.item(row_id, 'values')
        
        if col_idx < 0 or col_idx >= len(values):
            return
            
        cell_value = values[col_idx]

        # Obtener posición exacta de la celda
        x, y, width, height = self.tree.bbox(row_id, column)
        
        # Crear Entry temporal
        entry = ttk.Entry(self.tree, width=width)
        entry.place(x=x, y=y, width=width, height=height)
        
        entry.insert(0, cell_value)
        entry.select_range(0, 'end')
        entry.focus_set()
        
        # Eventos para cerrar el entry
        def destroy_entry(e):
            entry.destroy()
            
        entry.bind("<FocusOut>", destroy_entry)
        entry.bind("<Return>", destroy_entry)
        entry.bind("<Escape>", destroy_entry)

    def _create_kpi_card(self, parent, title, initial_value, color):
        card = ttk.Frame(parent, padding=10, bootstyle=f"{color}")
        card.pack(side=LEFT, fill=BOTH, expand=True, padx=5)
        
        # Borde visual usando style frame
        inner = ttk.Frame(card)
        inner.pack(fill=BOTH, expand=True)

        ttk.Label(inner, text=title, font=("Helvetica", 9), bootstyle="secondary").pack(anchor=W)
        lbl_value = ttk.Label(inner, text=initial_value, font=("Helvetica", 16, "bold"), bootstyle=color)
        lbl_value.pack(anchor=W)
        
        # Guardar referencia para actualizar luego. 
        # Usamos atributo dinámico basado en titulo simplificado
        attr_name = f"lbl_kpi_{title.replace(' ', '_').lower()}"
        setattr(self, attr_name, lbl_value)

    # --- MÉTODOS DE INTERACCIÓN ---

    def actualizar_combo_periodos(self, lista_periodos):
        if not lista_periodos:
            self.combo_periodo['values'] = ["Sin periodos"]
            self.combo_periodo.current(0)
            return

        valores = [item['descripcion'] for item in lista_periodos]
        self.combo_periodo['values'] = valores
        if valores:
            self.combo_periodo.current(0)

    def get_periodo(self):
        texto = self.periodo_var.get()
        if not texto or "Cargando" in texto:
            return ""
        return texto.split(" - ")[0].strip()

    def _on_descargar_click(self):
        if self.controller:
            self.controller.iniciar_proceso()
    
    def _on_exportar_click(self):
        if self.controller:
            self.controller.exportar_excel()
            
    def _on_search_change(self, *args):
        query = self.search_var.get().lower()
        self.filter_table(query)

    def log(self, message):
        # Actualiza la barra de estado inferior en lugar de un log text area
        self.lbl_status.config(text=f"> {message}")
        print(message) # Mantener en consola por si acaso

    def set_loading(self, is_loading):
        if is_loading:
            self.btn_descargar.config(state="disabled", text="Procesando...")
            self.btn_exportar.config(state="disabled")
            self.progress.pack(side=RIGHT, padx=10)
            self.progress.start(10)
        else:
            self.btn_descargar.config(state="normal", text="Descargar y Procesar")
            if self.df_actual is not None:
                self.btn_exportar.config(state="normal")
            self.progress.stop()
            self.progress.pack_forget()

    def mostrar_datos_tabla(self, df):
        self.df_actual = df
        self._llenar_tabla(df)
        self.actualizar_kpis(df)
        self.btn_exportar.config(state="normal")

    def _llenar_tabla(self, df):
        # Limpiar
        self.tree.delete(*self.tree.get_children())
        
        if df is None or df.empty:
            return
            
        # Filtrar columnas
        cols = list(self.COLUMN_CONFIG.keys())
        cols_presentes = [c for c in cols if c in df.columns]
        
        # Insertar filas (limitado a 500 para UI fluida con tkinter puro)
        # Si usáramos Tableview de ttkbootstrap podríamos paginar, pero por ahora simple
        max_rows = 1000
        for idx, row in df.head(max_rows).iterrows():
            valores = []
            for col in cols_presentes:
                val = row[col]
                if pd.isna(val):
                    valores.append("")
                elif isinstance(val, pd.Timestamp):
                    valores.append(val.strftime('%d/%m/%Y'))
                elif isinstance(val, (int, float)) and col in ['BaseImponible', 'IGV', 'ImporteTotal']:
                    valores.append(f"{val:,.2f}")
                else:
                    valores.append(str(val))
            
            self.tree.insert('', 'end', values=valores)
            
        self.lbl_status.config(text=f"Mostrando {len(df)} registros.")

    def filter_table(self, query):
        if self.df_actual is None or self.df_actual.empty:
            return
            
        if not query:
            self._llenar_tabla(self.df_actual)
            return
            
        # Filtrado simple por texto en todas las columnas string
        mask = self.df_actual.astype(str).apply(lambda x: x.str.lower().str.contains(query, na=False)).any(axis=1)
        df_filtered = self.df_actual[mask]
        self._llenar_tabla(df_filtered)

    def actualizar_kpis(self, df):
        if df is None or df.empty:
            return
            
        total_docs = len(df)
        total_base = df['BaseImponible'].sum() if 'BaseImponible' in df.columns else 0
        total_igv = df['IGV'].sum() if 'IGV' in df.columns else 0
        total_importe = df['ImporteTotal'].sum() if 'ImporteTotal' in df.columns else 0
        
        # Actualizar labels (usando las referencias dinámicas guardadas con setattr)
        self.lbl_kpi_total_comprobantes.config(text=f"{total_docs}")
        self.lbl_kpi_base_imponible.config(text=f"S/ {total_base:,.2f}")
        self.lbl_kpi_total_igv.config(text=f"S/ {total_igv:,.2f}")
        self.lbl_kpi_importe_total.config(text=f"S/ {total_importe:,.2f}")

    def show_info(self, title, msg):
        ttk.dialogs.Messagebox.show_info(msg, title)

    def show_error(self, title, msg):
        ttk.dialogs.Messagebox.show_error(msg, title)
    
    def limpiar_tabla(self):
        self.tree.delete(*self.tree.get_children())
        self.btn_exportar.config(state="disabled")
        self.df_actual = None
        # Reset KPIs
        self.lbl_kpi_total_comprobantes.config(text="0")
        self.lbl_kpi_base_imponible.config(text="S/ 0.00")
        self.lbl_kpi_total_igv.config(text="S/ 0.00")
        self.lbl_kpi_importe_total.config(text="S/ 0.00")