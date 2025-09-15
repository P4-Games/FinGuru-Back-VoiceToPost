#!/usr/bin/env python3
"""
Test para debuggear la respuesta de ChatGPT
"""

import os
import sys
sys.path.append('.')
sys.path.append('./app')

from app.load_env import load_env_files
from app.agents.automated_trends_agent import AutomatedTrendsAgent

def debug_gpt_response():
    print("🔍 DEBUGGEANDO RESPUESTA DE ChatGPT")
    print("=" * 50)
    
    # Cargar variables de entorno
    load_env_files()
    
    try:
        # Crear agente
        agent = AutomatedTrendsAgent()
        
        # Obtener tendencias
        print("1. Obteniendo tendencias...")
        trends_data = agent.get_trending_topics()
        if trends_data.get("status") != "success":
            print("❌ No se pudieron obtener tendencias")
            return
        
        trending_searches = trends_data.get("trending_topics", [])
        if not trending_searches:
            print("❌ No hay tendencias disponibles")
            return
        
        # Seleccionar primera tendencia
        selected_trend = trending_searches[0]
        trend_title = selected_trend.get("title", "")
        print(f"   Tendencia seleccionada: {trend_title}")
        
        # Buscar noticias
        print("2. Buscando noticias...")
        search_results = agent.search_api.search_google_news(trend_title)
        
        # Crear prompt
        print("3. Creando prompt...")
        prompt = agent.content_processor.create_prompt(
            trends_data, search_results, trend_title, 1, agent.agent_config
        )
        
        print("4. PROMPT GENERADO:")
        print("-" * 40)
        print(prompt[:1000])  # Mostrar primeros 1000 caracteres
        print("-" * 40)
        
        # Generar contenido
        print("5. Enviando a ChatGPT...")
        agent_response = agent.content_processor.generate_article_content(prompt)
        
        print("6. RESPUESTA DE ChatGPT:")
        print("-" * 40)
        print(agent_response)
        print("-" * 40)
        
        # Intentar procesar
        print("7. Procesando respuesta...")
        article_result = agent.content_processor.process_article_data(agent_response)
        
        if article_result.get("status") == "success":
            print("✅ Procesamiento exitoso!")
            data = article_result["data"]
            print(f"   Título: {data.get('title', 'N/A')}")
        else:
            print(f"❌ Error en procesamiento: {article_result.get('message', 'Error desconocido')}")
        
    except Exception as e:
        print(f"❌ Error en debug: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_gpt_response()