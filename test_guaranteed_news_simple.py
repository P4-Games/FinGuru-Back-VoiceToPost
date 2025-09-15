"""
Script de prueba simple para el endpoint de noticias garantizadas
Ejecuta desde el directorio raíz del proyecto: python test_guaranteed_news_simple.py
"""

import sys
import os
sys.path.append('app')

import requests
import json
from load_env import load_env_files

# Cargar variables de entorno
load_env_files()

# Configuración
BASE_URL = "http://localhost:8000"
SUDO_API_KEY = os.getenv("SUDO_API_KEY")

def test_endpoint():
    """Prueba básica del endpoint"""
    url = f"{BASE_URL}/run_trends_agent_guaranteed_news"
    
    headers = {
        "Content-Type": "application/json",
        "X-SUDO-API-KEY": SUDO_API_KEY
    }
    
    # Parámetros opcionales
    params = {
        "topic_position": 1,  # Usa la primera tendencia
        "allow_no_image": False
    }
    
    print(f"🚀 Probando: {url}")
    print(f"📋 Parámetros: {params}")
    
    try:
        print("⏳ Enviando petición (puede tardar varios minutos)...")
        response = requests.post(url, headers=headers, params=params, timeout=600)
        
        print(f"📡 Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ ¡ÉXITO!")
            print(f"   Tendencia: {result.get('trend_title', 'N/A')}")
            print(f"   Noticias garantizadas: {result.get('news_guaranteed', False)}")
            print(f"   Cantidad de noticias: {result.get('news_count', 0)}")
            print(f"   Query usado: {result.get('news_query_used', 'N/A')}")
            print(f"   Tipo de búsqueda: {result.get('news_search_type', 'N/A')}")
            
            # Guardar resultado
            with open("resultado_test.json", "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print("   📄 Resultado guardado en 'resultado_test.json'")
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    if not SUDO_API_KEY:
        print("❌ No se encontró SUDO_API_KEY")
        exit(1)
    
    test_endpoint()