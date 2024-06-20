import os
from dotenv import load_dotenv

def load_env_files():
    # Intenta cargar .env.local
    if os.path.exists('.env.local'):
        load_dotenv('.env.local')
        print("Cargadas variables de entorno desde .env.local")
    else:
        print(".env.local no encontrado, continuando...")

    # Intenta cargar .env
    if os.path.exists('.env'):
        load_dotenv('.env')
        print("Cargadas variables de entorno desde .env")
    else:
        print(".env no encontrado, continuando...")