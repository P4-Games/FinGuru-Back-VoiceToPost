#!/usr/bin/env python3
"""
Script para testear el nuevo endpoint /test_trends_agent
"""

import requests
import json
import os
from datetime import datetime

# Configuración
BASE_URL = "http://localhost:8000"  # Ajusta según tu configuración
SUDO_API_KEY = os.getenv("SUDO_API_KEY", "tu-sudo-api-key-aqui")

def test_endpoint(endpoint, method="GET", data=None, headers=None):
    """Función auxiliar para testear endpoints"""
    if headers is None:
        headers = {"X-SUDO-API-KEY": SUDO_API_KEY}
    
    url = f"{BASE_URL}{endpoint}"
    print(f"\n🧪 Testeando {method} {endpoint}")
    print(f"📡 URL: {url}")
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, json=data, headers=headers)
        
        print(f"📊 Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}...")
            return result
        else:
            print(f"❌ Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"💥 Exception: {str(e)}")
        return None

def main():
    print("🚀 Iniciando tests del endpoint de tendencias")
    print(f"⏰ Timestamp: {datetime.now().isoformat()}")
    
    # Test 1: Obtener estado del caché
    print("\n" + "="*60)
    print("TEST 1: Estado del caché")
    test_endpoint("/test_trends_agent/cache_status")
    
    # Test 2: Obtener agentes disponibles
    print("\n" + "="*60)
    print("TEST 2: Agentes disponibles")
    test_endpoint("/test_trends_agent/available_agents")
    
    # Test 3: Solo tendencias
    print("\n" + "="*60)
    print("TEST 3: Solo obtener tendencias")
    test_data = {
        "test_mode": "trends_only",
        "force_refresh": True,
        "include_metrics": True
    }
    test_endpoint("/test_trends_agent", "POST", test_data)
    
    # Test 4: Solo generar contenido (dry run)
    print("\n" + "="*60)
    print("TEST 4: Solo generar contenido")
    test_data = {
        "test_mode": "generate_only",
        "topic_position": 1,
        "include_metrics": True,
        "dry_run": True
    }
    test_endpoint("/test_trends_agent", "POST", test_data)
    
    # Test 5: Proceso completo en modo dry run
    print("\n" + "="*60)
    print("TEST 5: Proceso completo (dry run)")
    test_data = {
        "test_mode": "complete",
        "topic_position": 1,
        "include_metrics": True,
        "dry_run": True
    }
    test_endpoint("/test_trends_agent", "POST", test_data)
    
    # Test 6: Test con tópico específico
    print("\n" + "="*60)
    print("TEST 6: Generar con tópico específico")
    test_data = {
        "test_mode": "generate_only",
        "topic_title": "Inteligencia Artificial y el futuro del trabajo",
        "include_metrics": True
    }
    test_endpoint("/test_trends_agent", "POST", test_data)
    
    print("\n🎉 Tests completados!")
    print("📝 Revisa los resultados arriba para verificar el funcionamiento")

if __name__ == "__main__":
    main()