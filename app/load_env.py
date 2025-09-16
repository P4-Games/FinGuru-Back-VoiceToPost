import os
from dotenv import load_dotenv

def load_env_files():
    # En Cloud Run, las variables de entorno ya están disponibles
    if os.environ.get('CLOUD_RUN_SERVICE'):
        print("Ejecutándose en Cloud Run - usando variables de entorno del sistema")
        return
    
    # Intenta cargar .env.local (desarrollo local)
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
        
    # Verificar variables críticas
    required_vars = ['OPENAI_API_KEY', 'MONGODB_URI']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    if missing_vars:
        print(f"ADVERTENCIA: Faltan variables críticas: {missing_vars}")