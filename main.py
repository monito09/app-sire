from views.main_view import DashboardView
import tkinter as tk
from controllers.main_controller import MainController

def main():
    # 1. Crear Controlador
    controller = MainController()
    
    # 2. Crear Vista
    app = DashboardView()
    
    # 3. Conectar Vista y Controlador
    app.set_controller(controller)
    controller.set_view(app)
    
    # 4. Cargar la lista de periodos al iniciar (ESTO ES NUEVO)
    # Usamos 'after' para que la ventana aparezca primero y luego cargue
    app.after(100, controller.listar_periodos_presentados)
    
    # 5. Iniciar Loop
    app.mainloop()

if __name__ == "__main__":
    main()