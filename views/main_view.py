import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

class DashboardView(tk.Tk):
    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller
        
        # Configuración de la ventana
        self.title("Descarga Masiva SIRE SUNAT")
        self.geometry("600x450")
        self.resizable(False, False)
        
        # Estilos
        self.style = ttk.Style()
        self.style.configure("TButton", font=("Helvetica", 10))
        self.style.configure("TLabel", font=("Helvetica", 10))
        
        self._create_widgets()

    def set_controller(self, controller):
        self.controller = controller

    def _create_widgets(self):
        # Frame Principal
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        lbl_title = ttk.Label(main_frame, text="Sistema de Descarga SIRE", font=("Helvetica", 16, "bold"))
        lbl_title.pack(pady=(0, 20))
        
        # --- SECCIÓN DE PARÁMETROS ---
        param_frame = ttk.LabelFrame(main_frame, text="Parámetros de Consulta", padding="15")
        param_frame.pack(fill=tk.X, pady=10)
        
        # Selección de Periodo (AHORA ES UN COMBOBOX)
        frame_combo = ttk.Frame(param_frame)
        frame_combo.pack(fill=tk.X)
        
        ttk.Label(frame_combo, text="Seleccione Periodo:").pack(side=tk.LEFT, padx=(0, 10))
        
        # Variable para almacenar la selección
        self.periodo_var = tk.StringVar()
        
        # El widget Combobox reemplaza al Entry
        self.combo_periodo = ttk.Combobox(
            frame_combo, 
            textvariable=self.periodo_var,
            state="readonly", # Para que no puedan escribir, solo seleccionar
            width=35
        )
        self.combo_periodo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.combo_periodo.set("Cargando periodos...") # Texto inicial
        
        # Botón de Acción
        self.btn_descargar = ttk.Button(
            main_frame, 
            text="↓ sar", 
            command=self._on_descargar_click
        )
        self.btn_descargar.pack(pady=15, ipadx=10, ipady=5)
        
        # --- SECCIÓN DE LOGS ---
        ttk.Label(main_frame, text="Registro de Actividad:").pack(anchor=tk.W)
        
        self.log_area = scrolledtext.ScrolledText(main_frame, height=10, state='disabled', font=("Consolas", 9))
        self.log_area.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

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

    def log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"> {message}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def set_loading(self, is_loading):
        if is_loading:
            self.btn_descargar.config(state="disabled", text="Procesando...")
            self.config(cursor="watch")
        else:
            self.btn_descargar.config(state="normal", text="↓ Descargar y Procesar")
            self.config(cursor="")

    def show_info(self, title, msg):
        messagebox.showinfo(title, msg)

    def show_error(self, title, msg):
        messagebox.showerror(title, msg)