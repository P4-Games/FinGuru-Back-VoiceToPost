"""
Módulo para gestión y coordinación de múltiples agentes.
"""

import os
import requests
import random
from typing import Dict, Any, Optional, List
from datetime import datetime


class AgentManager:
    """Gestor de múltiples agentes y coordinación de procesos"""
    
    def __init__(self, next_public_api_url: str = None, sudo_api_key: str = None):
        self.next_public_api_url = next_public_api_url or os.getenv("NEXT_PUBLIC_API_URL")
        self.sudo_api_key = sudo_api_key or os.getenv("SUDO_API_KEY")
        
        # Cache estático para rastrear tendencias seleccionadas en la sesión multi-agente actual
        self._selected_trends_session = set()
        self._selected_positions_session = set()
    
    def initialize_agents(self, article_manager) -> List[Dict[str, Any]]:
        """Inicializa agentes desde la API y devuelve instancias configuradas"""
        try:
            print("🚀 Inicializando agentes desde la API...")
            
            # Obtener agentes disponibles
            agents_response = article_manager.get_available_agents()
            
            if agents_response.get('status') != 'success':
                print(f"❌ Error obteniendo agentes: {agents_response.get('message')}")
                return []
            
            api_agents = agents_response.get('details', [])
            
            if not api_agents:
                print("⚠️ No se encontraron agentes en la API")
                return []
            
            print(f"📋 {len(api_agents)} agentes encontrados en la API")
            
            initialized_agents = []
            
            for agent_data in api_agents:
                try:
                    agent_id = agent_data.get('id')
                    agent_name = agent_data.get('name', f'Agent-{agent_id}')
                    user_id = agent_data.get('userId')
                    
                    if not user_id:
                        print(f"   ⚠️ Agente {agent_name} sin userId, saltando...")
                        continue
                    
                    agent_config = {
                        'id': agent_id,
                        'name': agent_name,
                        'userId': user_id,
                        'personality': agent_data.get('personality', 'Eres un periodista especializado en tendencias de Argentina'),
                        'trending': agent_data.get('trending', 'Considera relevancia para Argentina'),
                        'format_markdown': agent_data.get('format_markdown', '')
                    }
                    
                    initialized_agents.append(agent_config)
                    print(f"   ✅ Agente configurado: {agent_name} (UserID: {user_id})")
                    
                except Exception as e:
                    print(f"   ❌ Error configurando agente {agent_data.get('name', 'unknown')}: {str(e)}")
                    continue
            
            print(f"🎯 {len(initialized_agents)} agentes inicializados correctamente")
            return initialized_agents
            
        except Exception as e:
            print(f"❌ Error inicializando agentes: {str(e)}")
            return []

    def select_topic_for_multi_agent(self, trends_data: Dict[str, Any], 
                                   topic_position: int = None, use_gpt: bool = True) -> Optional[Dict[str, Any]]:
        """Selecciona un tópico para el proceso multi-agente evitando repetidos"""
        try:
            if trends_data.get("status") != "success":
                print("❌ No hay datos de tendencias válidos")
                return None
            
            trending_searches = trends_data.get("trending_topics", [])
            if not trending_searches:
                print("❌ No hay tendencias disponibles")
                return None
            
            available_trends = []
            
            # Si se especifica posición, intentar usarla
            if topic_position and 1 <= topic_position <= len(trending_searches):
                target_trend = trending_searches[topic_position - 1]
                trend_title = target_trend.get("title", "")
                
                if topic_position not in self._selected_positions_session and trend_title not in self._selected_trends_session:
                    print(f"🎯 Usando posición específica {topic_position}: {trend_title}")
                    
                    # Marcar como seleccionado
                    self._selected_trends_session.add(trend_title)
                    self._selected_positions_session.add(topic_position)
                    
                    return {
                        "trend": target_trend,
                        "position": topic_position,
                        "title": trend_title,
                        "selection_method": "position_specified"
                    }
                else:
                    print(f"⚠️ Posición {topic_position} ya fue seleccionada, buscando alternativa...")
            
            # Construir lista de tendencias disponibles (no seleccionadas)
            for i, trend in enumerate(trending_searches, 1):
                trend_title = trend.get("title", "")
                if i not in self._selected_positions_session and trend_title not in self._selected_trends_session:
                    available_trends.append((i, trend, trend_title))
            
            if not available_trends:
                print("⚠️ No hay más tendencias disponibles (todas fueron seleccionadas)")
                # Limpiar caché si no hay tendencias disponibles
                self.clear_session_cache()
                # Volver a intentar con la primera tendencia
                if trending_searches:
                    first_trend = trending_searches[0]
                    first_title = first_trend.get("title", "")
                    self._selected_trends_session.add(first_title)
                    self._selected_positions_session.add(1)
                    return {
                        "trend": first_trend,
                        "position": 1,
                        "title": first_title,
                        "selection_method": "fallback_first"
                    }
                return None
            
            if use_gpt and len(available_trends) > 1:
                # Usar GPT para seleccionar
                selected = self._select_with_gpt(available_trends)
            else:
                # Selección aleatoria
                selected = random.choice(available_trends)
            
            position, trend, title = selected
            
            # Marcar como seleccionado
            self._selected_trends_session.add(title)
            self._selected_positions_session.add(position)
            
            print(f"🎯 Tendencia seleccionada: #{position} - {title}")
            print(f"📊 Tendencias ya seleccionadas en esta sesión: {len(self._selected_trends_session)}")
            
            return {
                "trend": trend,
                "position": position,
                "title": title,
                "selection_method": "gpt" if use_gpt else "random"
            }
            
        except Exception as e:
            print(f"❌ Error seleccionando tópico: {str(e)}")
            return None

    def _select_with_gpt(self, available_trends: List[tuple]) -> tuple:
        """Usa GPT para seleccionar la mejor tendencia"""
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
            
            # Crear prompt para GPT
            trends_list = ""
            for pos, trend, title in available_trends:
                traffic = trend.get("formattedTraffic", "N/A")
                trends_list += f"{pos}. {title} (Tráfico: {traffic})\\n"
            
            prompt = f"""Como experto en tendencias de Argentina, selecciona UNA tendencia de la siguiente lista para crear un artículo periodístico:

{trends_list}

Criterios de selección:
- Relevancia para Argentina
- Potencial de generar interés
- Actualidad e importancia
- Impacto social, económico o cultural

Responde ÚNICAMENTE con el número de posición (ejemplo: "3")"""
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=10
            )
            
            gpt_response = response.choices[0].message.content.strip()
            
            # Extraer número de la respuesta
            import re
            number_match = re.search(r'\\d+', gpt_response)
            if number_match:
                selected_pos = int(number_match.group())
                
                # Buscar la tendencia correspondiente
                for pos, trend, title in available_trends:
                    if pos == selected_pos:
                        print(f"🤖 GPT seleccionó: #{pos} - {title}")
                        return (pos, trend, title)
            
            # Fallback a selección aleatoria
            print("⚠️ GPT no devolvió una selección válida, usando selección aleatoria")
            return random.choice(available_trends)
            
        except Exception as e:
            print(f"⚠️ Error usando GPT para selección: {str(e)}")
            return random.choice(available_trends)

    def distribute_agents_across_topics(self, agents: List[Dict], trends_data: Dict[str, Any], 
                                      max_agents: int = None) -> List[Dict[str, Any]]:
        """Distribuye agentes entre diferentes tópicos"""
        try:
            if not agents:
                return []
            
            # Limitar número de agentes si se especifica
            if max_agents and len(agents) > max_agents:
                agents = random.sample(agents, max_agents)
            
            assignments = []
            
            for i, agent_config in enumerate(agents):
                # Seleccionar tópico para este agente
                topic_selection = self.select_topic_for_multi_agent(
                    trends_data, 
                    topic_position=None,  # Dejar que GPT/random seleccione
                    use_gpt=True
                )
                
                if topic_selection:
                    assignment = {
                        "agent": agent_config,
                        "topic": topic_selection,
                        "assignment_order": i + 1
                    }
                    assignments.append(assignment)
                    
                    print(f"📋 Agente {agent_config['name']} asignado a: {topic_selection['title']}")
                else:
                    print(f"⚠️ No se pudo asignar tópico al agente {agent_config['name']}")
            
            return assignments
            
        except Exception as e:
            print(f"❌ Error distribuyendo agentes: {str(e)}")
            return []

    def coordinate_multi_agent_publishing(self, assignments: List[Dict], 
                                        search_api, content_processor, 
                                        publish_callback) -> Dict[str, Any]:
        """Coordina la publicación de múltiples agentes"""
        try:
            results = {
                "successful_publications": [],
                "failed_publications": [],
                "total_agents": len(assignments),
                "start_time": datetime.now().isoformat()
            }
            
            for i, assignment in enumerate(assignments, 1):
                try:
                    agent_config = assignment["agent"]
                    topic_selection = assignment["topic"]
                    
                    print(f"\\n🤖 [{i}/{len(assignments)}] Procesando agente: {agent_config['name']}")
                    print(f"📝 Tópico: {topic_selection['title']}")
                    
                    # Buscar información sobre el tópico
                    search_results = search_api.search_google_news(topic_selection['title'])
                    
                    # Crear prompt
                    prompt = content_processor.create_prompt(
                        {"status": "success", "trending_topics": [topic_selection["trend"]]},
                        search_results,
                        topic_selection['title'],
                        topic_selection['position'],
                        agent_config
                    )
                    
                    # Generar contenido
                    agent_response = content_processor.generate_article_content(prompt)
                    
                    # Procesar artículo
                    article_result = content_processor.process_article_data(agent_response)
                    
                    if article_result.get("status") == "success":
                        article_data = article_result["data"]
                        
                        # Publicar usando callback
                        publish_result = publish_callback(
                            article_data, 
                            topic_selection['title'], 
                            search_results,
                            agent_config
                        )
                        
                        if publish_result.get("status") == "success":
                            results["successful_publications"].append({
                                "agent": agent_config['name'],
                                "topic": topic_selection['title'],
                                "article_title": article_data['title'],
                                "result": publish_result
                            })
                            print(f"✅ Agente {agent_config['name']} publicó exitosamente")
                        else:
                            results["failed_publications"].append({
                                "agent": agent_config['name'],
                                "topic": topic_selection['title'],
                                "error": publish_result.get("message", "Error desconocido"),
                                "stage": "publishing"
                            })
                            print(f"❌ Error publicando para agente {agent_config['name']}")
                    else:
                        results["failed_publications"].append({
                            "agent": agent_config['name'],
                            "topic": topic_selection['title'],
                            "error": article_result.get("message", "Error procesando artículo"),
                            "stage": "content_processing"
                        })
                        print(f"❌ Error procesando contenido para agente {agent_config['name']}")
                
                except Exception as e:
                    results["failed_publications"].append({
                        "agent": assignment["agent"]["name"],
                        "topic": assignment["topic"]["title"],
                        "error": str(e),
                        "stage": "general"
                    })
                    print(f"❌ Error general con agente {assignment['agent']['name']}: {str(e)}")
            
            # Estadísticas finales
            results["end_time"] = datetime.now().isoformat()
            results["success_rate"] = len(results["successful_publications"]) / len(assignments) if assignments else 0
            
            return results
            
        except Exception as e:
            return {
                "error": str(e),
                "successful_publications": [],
                "failed_publications": [],
                "total_agents": len(assignments) if assignments else 0
            }

    def clear_session_cache(self):
        """Limpia el caché de la sesión actual"""
        self._selected_trends_session.clear()
        self._selected_positions_session.clear()
        print("🧹 Caché de sesión limpiado")

    def get_session_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de la sesión actual"""
        return {
            "selected_trends_count": len(self._selected_trends_session),
            "selected_positions": sorted(list(self._selected_positions_session)),
            "selected_trends": list(self._selected_trends_session)
        }