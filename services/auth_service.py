import requests
import time

class SunatAuthService:
    def __init__(self, config):
        self.client_id = config["client_id"]
        self.client_secret = config["client_secret"]
        self.ruc = config["ruc"]
        self.usuario_sol = config["usuario_sol"]
        self.clave_sol = config["clave_sol"]
        self.token = None
        self.token_expiry = 0

    def get_token(self):
        # Si ya tenemos un token válido (con un margen de 60 segundos), lo reutilizamos
        if self.token and time.time() < self.token_expiry - 60:
            return self.token

        url = f"https://api-seguridad.sunat.gob.pe/v1/clientessol/{self.client_id}/oauth2/token/"
        data = {
            "grant_type": "password",
            "scope": "https://api-sire.sunat.gob.pe",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.ruc + self.usuario_sol,
            "password": self.clave_sol
        }
        
        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                data = response.json()
                self.token = data["access_token"]
                # Asumimos una duración típica de 3600s si no viene en la respuesta
                expires_in = data.get("expires_in", 3600) 
                self.token_expiry = time.time() + expires_in
                return self.token
            else:
                raise Exception(f"Error obteniendo token: {response.status_code} - {response.text}")
        except Exception as e:
            raise Exception(f"Error de conexión en autenticación: {str(e)}")
