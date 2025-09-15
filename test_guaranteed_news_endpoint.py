"""
Script de prueba para el nuevo endpoint de noticias garantizadas
"""

import requests
import json
import os
from load_env import load_env_files

# Cargar variables de entorno
load_env_files()

# Configuración
BASE_URL = "http://localhost:8000"  # Cambia esto según tu servidor
SUDO_API_KEY = os.getenv("SUDO_API_KEY")

def test_guaranteed_news_endpoint(topic_position=None, allow_no_image=False):
    """
    Prueba el endpoint /run_trends_agent_guaranteed_news
    """
    url = f"{BASE_URL}/run_trends_agent_guaranteed_news"
    
    headers = {
        "Content-Type": "application/json",
        "X-SUDO-API-KEY": SUDO_API_KEY
    }
    
    params = {}
    if topic_position is not None:
        params["topic_position"] = topic_position
    if allow_no_image:
        params["allow_no_image"] = allow_no_image
    
    print(f"🚀 Probando endpoint: {url}")
    print(f"📋 Parámetros: {params}")
    print(f"🔑 Headers: {headers}")
    print("=" * 60)
    
    try:
        response = requests.post(url, headers=headers, params=params, timeout=300)  # 5 minutos timeout
        
        print(f"📡 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            print("✅ RESPUESTA EXITOSA:")
            print(f"   Status: {result.get('status', 'N/A')}")
            print(f"   Message: {result.get('message', 'N/A')}")
            print(f"   Trend Title: {result.get('trend_title', 'N/A')}")
            print(f"   News Guaranteed: {result.get('news_guaranteed', 'N/A')}")
            print(f"   News Count: {result.get('news_count', 'N/A')}")
            print(f"   News Query Used: {result.get('news_query_used', 'N/A')}")
            print(f"   News Search Type: {result.get('news_search_type', 'N/A')}")
            
            if result.get('article_data'):
                article = result['article_data']
                print(f"   Article Title: {article.get('title', 'N/A')}")
                print(f"   Article Category: {article.get('category', 'N/A')}")
            
            # Guardar respuesta completa en archivo
            with open("test_guaranteed_news_response.json", "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print("   💾 Respuesta completa guardada en 'test_guaranteed_news_response.json'")
            
        else:
            print(f"❌ ERROR: {response.status_code}")
            print(f"   Respuesta: {response.text}")
            
    except requests.exceptions.Timeout:
        print("⏰ TIMEOUT: La petición tardó más de 5 minutos")
    except requests.exceptions.ConnectionError:
        print(f"🔌 ERROR DE CONEXIÓN: No se pudo conectar a {BASE_URL}")
        print("   Verifica que el servidor esté ejecutándose")
    except Exception as e:
        print(f"❌ ERROR INESPERADO: {str(e)}")


def test_normal_endpoint_comparison(topic_position=None):
    """
    Compara el endpoint normal vs el garantizado
    """
    print("🔄 COMPARANDO ENDPOINTS:")
    print("=" * 60)
    
    # Test endpoint normal
    print("1️⃣ PROBANDO ENDPOINT NORMAL:")
    url_normal = f"{BASE_URL}/run_trends_agent"
    headers = {"X-SUDO-API-KEY": SUDO_API_KEY}
    
    try:
        response = requests.post(url_normal, headers=headers, timeout=300)
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Normal - Status: {result.get('status')}")
            print(f"   📰 Normal - Trend: {result.get('trend_used', 'N/A')}")
        else:
            print(f"   ❌ Normal - Error: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Normal - Exception: {str(e)}")
    
    print("\n2️⃣ PROBANDO ENDPOINT GARANTIZADO:")
    test_guaranteed_news_endpoint(topic_position)


if __name__ == "__main__":
    print("🧪 SCRIPT DE PRUEBA - NOTICIAS GARANTIZADAS")
    print("=" * 60)
    
    if not SUDO_API_KEY:
        print("❌ ERROR: No se encontró SUDO_API_KEY en las variables de entorno")
        exit(1)
    
    print("Opciones de prueba:")
    print("1. Probar endpoint garantizado con tendencia automática")
    print("2. Probar endpoint garantizado con posición específica")
    print("3. Comparar endpoint normal vs garantizado")
    print("4. Probar con allow_no_image=True")
    
    choice = input("\nElige una opción (1-4): ").strip()
    
    if choice == "1":
        test_guaranteed_news_endpoint()
    elif choice == "2":
        pos = input("Ingresa la posición de tendencia (1-10): ").strip()
        try:
            pos = int(pos)
            test_guaranteed_news_endpoint(topic_position=pos)
        except ValueError:
            print("❌ Posición inválida")
    elif choice == "3":
        test_normal_endpoint_comparison()
    elif choice == "4":
        test_guaranteed_news_endpoint(allow_no_image=True)
    else:
        print("❌ Opción inválida")