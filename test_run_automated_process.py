#!/usr/bin/env python3
"""
Test específico para run_automated_process
"""

import os
import sys
sys.path.append('.')
sys.path.append('./app')

from app.load_env import load_env_files
from app.agents.automated_trends_agent import AutomatedTrendsAgent

def test_run_automated_process():
    print("🔍 TESTEANDO run_automated_process")
    print("=" * 50)
    
    # Cargar variables de entorno
    load_env_files()
    
    try:
        # Crear agente
        print("1. Creando agente...")
        agent = AutomatedTrendsAgent()
        print(f"   ✅ Agente creado: {agent.agent_name}")
        
        # Ejecutar proceso automatizado normal
        print("\n2. Ejecutando run_automated_process...")
        result = agent.run_automated_process(topic_position=1)
        
        print(f"   Estado final: {result.get('status')}")
        print(f"   Mensaje: {result.get('message', 'N/A')}")
        
        if result.get('status') == 'success':
            print("   ✅ ¡ÉXITO! Proceso automatizado funcionó")
            print(f"   Artículo: {result.get('article_data', {}).get('title', 'N/A')}")
            print(f"   Tendencia: {result.get('trend_title', 'N/A')}")
        elif result.get('status') == 'error':
            print(f"   ❌ ERROR: {result.get('message', 'Error desconocido')}")
            if 'article_data' in result:
                print(f"   Detalles artículo: {result.get('article_data', 'N/A')}")
        elif result.get('status') == 'skipped':
            print(f"   ⏭️ SALTADO: {result.get('message', 'Motivo desconocido')}")
        
        # Mostrar información adicional si está disponible
        if 'publish_result' in result:
            pub_result = result['publish_result']
            print(f"\n   📤 Resultado de publicación:")
            print(f"      Estado: {pub_result.get('status', 'N/A')}")
            print(f"      Mensaje: {pub_result.get('message', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Error en test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_run_automated_process()