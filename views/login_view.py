import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from typing import Dict, Any

class LoginView(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master, padding=30)
        self.controller = controller
        
        # Configurar ventana principal (master)
        self.master.title("Configuración de Acceso SUNAT")
        self.master.geometry("500x600")
        self.master.resizable(False, False)
        
        self._create_ui()
        
        # Centrar ventana
        self.master.eval('tk::PlaceWindow . center')
        self.pack(fill=BOTH, expand=True)

    def _create_ui(self):
        container = self # Usamos self como container principal
        
        # Header
        ttk.Label(container, text="Credenciales SUNAT", font=("Helvetica", 18, "bold"), bootstyle="primary").pack(pady=(0, 20))
        
        # Formulario
        self.entries = {}
        
        fields = [
            ("RUC (Empresa/Emisor)", "ruc"),
            ("Usuario SOL", "usuario_sol"),
            ("Clave SOL", "clave_sol"),
            ("Client ID (API SIRE)", "client_id"),
            ("Client Secret (API SIRE)", "client_secret")
        ]
        
        for label_text, key in fields:
            frame = ttk.Frame(container)
            frame.pack(fill=X, pady=5)
            
            ttk.Label(frame, text=label_text, bootstyle="secondary").pack(anchor=W)
            
            entry = ttk.Entry(frame, bootstyle="default")
            entry.pack(fill=X, pady=(2, 0))
            
            if "clave" in key or "secret" in key:
                entry.configure(show="•")
                
            self.entries[key] = entry

        # Checkbox para guardar
        self.save_var = ttk.BooleanVar(value=True)
        ttk.Checkbutton(container, text="Guardar credenciales localmente", variable=self.save_var, bootstyle="round-toggle").pack(pady=20, anchor=W)

        # Botón
        self.btn_login = ttk.Button(
            container, 
            text="INGRESAR AL SISTEMA", 
            command=self._on_login,
            bootstyle="primary",
            width=30
        )
        self.btn_login.pack(pady=10)
        
        # Footer info
        ttk.Label(container, text="Estos datos se usarán para la API y descargas.", font=("Arial", 8), bootstyle="secondary").pack(side=BOTTOM)

    def _on_login(self):
        data = {key: entry.get().strip() for key, entry in self.entries.items()}
        save_local = self.save_var.get()
        
        # Validación simple
        if not all(data.values()):
            ttk.dialogs.Messagebox.show_error("Por favor complete todos los campos.", "Campos Incompletos")
            return

        self.btn_login.config(state="disabled", text="Verificando...")
        self.controller.handle_login_attempt(data, save_local)

    def show_error(self, message):
        self.btn_login.config(state="normal", text="INGRESAR AL SISTEMA")
        ttk.dialogs.Messagebox.show_error(message, "Error de Acceso")
    
    def close(self):
        self.destroy()
