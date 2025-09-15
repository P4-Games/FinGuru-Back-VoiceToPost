#!/usr/bin/env python3
"""
Test directo de la función garantizada
"""

import os
import sys
sys.path.append('.')
sys.path.append('./app')

from app.load_env import load_env_files
from app.agents.automated_trends_agent import AutomatedTrendsAgent

def test_guaranteed_function():
    print("🔍 TESTEANDO FUNCIÓN GARANTIZADA DIRECTAMENTE")
    print("=" * 60)
    
    # Cargar variables de entorno
    load_env_files()
    
    try:
        # Crear agente
        print("1. Creando agente...")
        agent = AutomatedTrendsAgent()
        print(f"   ✅ Agente creado: {agent.agent_name}")
        
        # Testear obtención de tendencias
        print("\n2. Obteniendo tendencias...")
        trends_data = agent.get_trending_topics()
        print(f"   Estado: {trends_data.get('status')}")
        
        if trends_data.get('status') == 'success':
            # Buscar las claves correctas
            keys = list(trends_data.keys())
            print(f"   Claves disponibles: {keys}")
            
            # Intentar diferentes claves posibles
            trending_searches = None
            for key in ['trending_topics', 'trending_searches', 'trending_searches_argentina']:
                if key in trends_data:
                    trending_searches = trends_data[key]
                    print(f"   ✅ Encontrado {key}: {len(trending_searches)} items")
                    break
            
            if not trending_searches:
                print("   ❌ No se encontraron tendencias en ninguna clave conocida")
                return
            
            # Mostrar algunas tendencias
            print(f"   Primeras 3 tendencias:")
            for i, trend in enumerate(trending_searches[:3], 1):
                if isinstance(trend, dict):
                    title = trend.get('title', trend.get('query', str(trend)))
                else:
                    title = str(trend)
                print(f"      {i}. {title}")
        else:
            print(f"   ❌ Error obteniendo tendencias: {trends_data.get('message')}")
            return
        
        # Ejecutar proceso garantizado
        print("\n3. Ejecutando proceso garantizado...")
        result = agent.run_news_guaranteed_process(topic_position=1, allow_no_image=True)
        
        print(f"   Estado final: {result.get('status')}")
        print(f"   Mensaje: {result.get('message', 'N/A')}")
        
        if result.get('status') == 'success':
            print("   ✅ ¡ÉXITO! Proceso garantizado funcionó")
            print(f"   Artículo: {result.get('article_data', {}).get('title', 'N/A')}")
            print(f"   Tendencia: {result.get('trend_title', 'N/A')}")
            print(f"   Noticias: {result.get('news_count', 0)}")
        else:
            print(f"   ❌ FALLO: {result.get('message', 'Error desconocido')}")
            if 'details' in result:
                print(f"   Detalles: {result['details']}")
        
    except Exception as e:
        print(f"❌ Error en test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_guaranteed_function()