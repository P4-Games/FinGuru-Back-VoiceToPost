#!/usr/bin/env python3
"""
Script de diagnóstico para el sistema de tendencias
"""

import os
import sys
sys.path.append('.')
sys.path.append('./app')

from dotenv import load_dotenv
from serpapi import GoogleSearch

def main():
    print("🔍 DIAGNÓSTICO DEL SISTEMA DE TENDENCIAS")
    print("=" * 50)
    
    # Cargar variables de entorno
    load_dotenv('.env.local')
    
    # Verificar claves API
    print("\n1. VERIFICANDO VARIABLES DE ENTORNO:")
    serpapi_key = os.getenv("SERPAPI_KEY")
    serpapi_key2 = os.getenv("SERPAPI_KEY2")
    
    print(f"   SERPAPI_KEY: {'✅ Configurada' if serpapi_key else '❌ No encontrada'}")
    if serpapi_key:
        print(f"   SERPAPI_KEY (primeros 10 chars): {serpapi_key[:10]}...")
    
    print(f"   SERPAPI_KEY2: {'✅ Configurada' if serpapi_key2 else '❌ No encontrada'}")
    if serpapi_key2:
        print(f"   SERPAPI_KEY2 (primeros 10 chars): {serpapi_key2[:10]}...")
    
    # Testear SerpAPI directamente
    print("\n2. TESTEANDO SERPAPI DIRECTAMENTE:")
    if not serpapi_key:
        print("   ❌ No se puede testear, no hay clave API")
        return
        
    try:
        print("   Intentando obtener tendencias...")
        params = {
            "engine": "google_trends_trending_now",
            "geo": "AR",
            "api_key": serpapi_key,
            "hours": "24",
            "hl": "es-419"
        }
        
        search = GoogleSearch(params)
        results = search.get_dict()
        
        print(f"   Respuesta obtenida. Claves en respuesta: {list(results.keys())}")
        
        if "error" in results:
            print(f"   ❌ Error de SerpAPI: {results['error']}")
        elif "trending_searches" in results:
            trends = results["trending_searches"]
            print(f"   ✅ Éxito! Encontradas {len(trends)} tendencias")
            for i, trend in enumerate(trends[:3], 1):
                if isinstance(trend, dict):
                    title = trend.get("query", trend.get("title", str(trend)))
                else:
                    title = str(trend)
                print(f"      {i}. {title}")
        else:
            print(f"   ⚠️ Respuesta inesperada: {results}")
            
    except Exception as e:
        print(f"   ❌ Excepción: {str(e)}")
    
    # Sugerir solución de fallback
    print("\n3. SOLUCIÓN RECOMENDADA:")
    print("   💡 Crear sistema de fallback con tendencias hardcodeadas para testing")

if __name__ == "__main__":
    main()