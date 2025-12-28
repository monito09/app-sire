import requests
import time
import zipfile
import io
import pandas as pd

# TUS DATOS
RUC = "20605730541" # Tu RUC
USUARIO_SOL = "ITTENTOR" # Tu usuario SOL
CLAVE_SOL = "nstatexpe"
CLIENT_ID = "704c2889-f59d-4b43-af5b-9f429849e66a"
CLIENT_SECRET = "szaO0p3L1W5gDfd3HeFfxQ=="

# 1. AUTENTICACIÓN
def obtener_token():
    url = f"https://api-seguridad.sunat.gob.pe/v1/clientessol/{CLIENT_ID}/oauth2/token/"
    data = {
        "grant_type": "password",
        "scope": "https://api-sire.sunat.gob.pe",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "username": RUC + USUARIO_SOL,
        "password": CLAVE_SOL
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Error login: {response.text}")

try:
    print("Iniciando autenticación con SUNAT...")
    token = obtener_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print("✅ ¡Conexión exitosa! Token de acceso obtenido correctamente.")
    print(f"Token (primeros 20 caracteres): {token[:20]}...")
except Exception as e:
    print(f"❌ Error en la conexión: {e}")
