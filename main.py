from controllers.main_controller import MainController

def main():
    # El controlador decide si mostrar Login o Dashboard según si existe config
    controller = MainController()
    controller.start()

if __name__ == "__main__":
    main()