"""
Módulo para gestión y validación de artículos.
"""

import os
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta


class ArticleManager:
    """Gestiona la obtención y validación de artículos"""
    
    def __init__(self, next_public_api_url: str = None, sudo_api_key: str = None):
        self.next_public_api_url = next_public_api_url or os.getenv("NEXT_PUBLIC_API_URL")
        self.sudo_api_key = sudo_api_key or os.getenv("SUDO_API_KEY")
    
    def get_agent_recent_articles(self, user_id: int) -> Dict[str, Any]:
        """Obtiene artículos recientes de un agente específico"""
        try:
            print(f"Obteniendo artículos recientes para userId: {user_id}")
            
            endpoint = f"{self.next_public_api_url}/articles"
            
            headers = {
                "Authorization": f"Bearer {self.sudo_api_key}",
                "Content-Type": "application/json",
            }
            
            params = {
                "populate": "*",
                "filters[userId]": user_id,
                "sort": "createdAt:desc",
                "pagination[limit]": 5
            }
            
            response = requests.get(endpoint, headers=headers, params=params)
            
            if not response.ok:
                raise Exception(f"HTTP error! status: {response.status_code}")
            
            data = response.json()
            
            if 'data' in data:
                articles = data['data']
            else:
                articles = data.get('details', [])
            
            if not articles:
                return {"status": "success", "articles": [], "count": 0}
            
            # Filtrar artículos de las últimas 24 horas
            cutoff_date = datetime.now() - timedelta(hours=24)
            recent_articles = []
            
            for article in articles:
                try:
                    created_at_str = article.get('createdAt', '')
                    if created_at_str:
                        # Parsear diferentes formatos de fecha
                        try:
                            if '.' in created_at_str:
                                # Formato con microsegundos
                                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                            else:
                                # Formato estándar
                                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        except:
                            # Fallback para otros formatos
                            created_at = datetime.strptime(created_at_str[:19], '%Y-%m-%dT%H:%M:%S')
                        
                        # Si el artículo es de las últimas 24 horas, incluirlo
                        if created_at.replace(tzinfo=None) >= cutoff_date:
                            recent_articles.append({
                                'id': article.get('id'),
                                'title': article.get('title', ''),
                                'excerpt': article.get('excerpt', ''),
                                'category': article.get('category', ''),
                                'tags': article.get('tags', ''),
                                'createdAt': created_at_str,
                                'userId': user_id
                            })
                except Exception as date_error:
                    print(f"   Error procesando fecha para artículo {article.get('id')}: {str(date_error)}")
                    continue
            
            print(f"   Artículos recientes encontrados: {len(recent_articles)}")
            for article in recent_articles:
                title = article.get('title', 'Sin título')[:50]
                print(f"      - {title}...")
            
            return {
                "status": "success",
                "articles": recent_articles,
                "count": len(recent_articles)
            }
            
        except Exception as e:
            error_msg = f"Error obteniendo artículos del agente {user_id}: {str(e)}"
            print(error_msg)
            return {"status": "error", "message": error_msg, "articles": []}

    def get_all_agents_recent_articles(self, limit_per_agent: int = 2) -> Dict[str, Any]:
        """Obtiene artículos recientes de TODOS los agentes disponibles"""
        try:
            print(f"Obteniendo artículos recientes de TODOS los agentes (límite: {limit_per_agent} por agente)...")
            
            # Primero obtener todos los agentes disponibles
            agents_response = self.get_available_agents()
            if agents_response.get('status') != 'success':
                print(f"Error obteniendo agentes: {agents_response.get('message')}")
                return {"status": "error", "message": "No se pudieron obtener agentes", "articles": []}
            
            all_agents = agents_response.get('details', [])
            all_articles = []
            agents_processed = 0
            
            for agent in all_agents:
                try:
                    agent_id = agent.get('id')
                    agent_name = agent.get('name', f'Agent-{agent_id}')
                    user_id = agent.get('userId')
                    
                    if not user_id:
                        print(f"   Agente {agent_name} (ID: {agent_id}) sin userId, saltando...")
                        continue
                    
                    print(f"   Obteniendo artículos del agente: {agent_name} (UserID: {user_id})")
                    
                    # Obtener artículos de este agente específico
                    agent_articles = self.get_agent_recent_articles(user_id)
                    
                    if agent_articles.get("status") == "success" and agent_articles.get("articles"):
                        articles = agent_articles.get("articles", [])
                        
                        # Agregar información del agente a cada artículo
                        for article in articles:
                            article['agent_name'] = agent_name
                            article['agent_id'] = agent_id
                            article['user_id'] = user_id
                            all_articles.append(article)
                        
                        print(f"      - {len(articles)} artículos encontrados")
                        agents_processed += 1
                    else:
                        print(f"      - Sin artículos recientes")
                
                except Exception as e:
                    print(f"   Error procesando agente {agent.get('name', 'unknown')}: {str(e)}")
                    continue
            
            # Ordenar todos los artículos por fecha de creación (más recientes primero)
            all_articles.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
            
            # Limitar la cantidad total si es necesario
            max_total_articles = len(all_agents) * limit_per_agent
            if len(all_articles) > max_total_articles:
                all_articles = all_articles[:max_total_articles]
            
            print(f"RESUMEN: {len(all_articles)} artículos recientes de {agents_processed} agentes")
            print("Últimos artículos encontrados:")
            for i, article in enumerate(all_articles[:10]):  # Mostrar solo los primeros 10
                agent_name = article.get('agent_name', 'N/A')
                title = article.get('title', 'Sin título')
                category = article.get('category', 'N/A')
                print(f"   {i+1}. [{agent_name}] {title} - {category}")
            
            if len(all_articles) > 10:
                print(f"   ... y {len(all_articles) - 10} artículos más")
            
            return {
                "status": "success",
                "articles": all_articles,
                "total": len(all_articles),
                "agents_processed": agents_processed
            }
            
        except Exception as e:
            print(f"Error obteniendo artículos de todos los agentes: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "articles": []
            }

    def get_available_agents(self) -> Dict[str, Any]:
        """Obtiene todos los agentes disponibles desde la API"""
        try:
            print("Obteniendo agentes disponibles desde la API...")
            
            endpoint = f"{self.next_public_api_url}/agent-ias?populate=*"
            
            headers = {
                "Authorization": f"Bearer {self.sudo_api_key}",
                "Content-Type": "application/json",
            }
            
            response = requests.get(endpoint, headers=headers)
            
            if not response.ok:
                raise Exception(f"HTTP error! status: {response.status_code}")
            
            data = response.json()
            
            if 'details' in data:
                agents = data['details']
            else:
                agents = data.get('data', [])
                if isinstance(agents, list) and agents:
                    # Transformar estructura si es necesario
                    transformed_agents = []
                    for agent in agents:
                        if isinstance(agent, dict):
                            agent_data = agent
                            if 'attributes' in agent:
                                # Formato Strapi
                                attrs = agent['attributes']
                                agent_data = {
                                    'id': agent.get('id'),
                                    'name': attrs.get('name'),
                                    'userId': attrs.get('userId'),
                                    'personality': attrs.get('personality'),
                                    'trending': attrs.get('trending'),
                                    'format_markdown': attrs.get('format_markdown')
                                }
                            transformed_agents.append(agent_data)
                    agents = transformed_agents
            
            if not isinstance(agents, list):
                agents = []
            
            print(f"Agentes encontrados: {len(agents)}")
            for agent in agents:
                name = agent.get('name', 'Sin nombre')
                agent_id = agent.get('id', 'N/A')
                user_id = agent.get('userId', 'N/A')
                print(f"   - {name} (ID: {agent_id}, UserID: {user_id})")
            
            return {"status": "success", "details": agents, "count": len(agents)}
            
        except Exception as e:
            error_msg = f"Error obteniendo agentes disponibles: {str(e)}"
            print(error_msg)
            return {"status": "error", "message": error_msg, "details": []}

    def validate_article_data(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """Valida los datos de un artículo antes de publicar"""
        try:
            required_fields = ['title', 'excerpt', 'content', 'category']
            missing_fields = []
            
            for field in required_fields:
                if not article_data.get(field):
                    missing_fields.append(field)
            
            if missing_fields:
                return {
                    "status": "error",
                    "message": f"Campos requeridos faltantes: {', '.join(missing_fields)}"
                }
            
            # Validar longitud de campos
            if len(article_data['title']) < 10:
                return {"status": "error", "message": "El título debe tener al menos 10 caracteres"}
            
            if len(article_data['excerpt']) < 50:
                return {"status": "error", "message": "El extracto debe tener al menos 50 caracteres"}
            
            if len(article_data['content']) < 200:
                return {"status": "error", "message": "El contenido debe tener al menos 200 caracteres"}
            
            return {"status": "success", "message": "Artículo validado correctamente"}
            
        except Exception as e:
            return {"status": "error", "message": f"Error validando artículo: {str(e)}"}

    def check_article_similarity(self, title: str, recent_articles: List[Dict]) -> Dict[str, Any]:
        """Verifica si un artículo es similar a artículos recientes"""
        try:
            from .text_utils import TextUtils
            
            is_similar = TextUtils.is_topic_similar_to_recent_articles(title, recent_articles)
            
            return {
                "status": "success",
                "is_similar": is_similar,
                "message": "Artículo similar encontrado" if is_similar else "Artículo único"
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Error verificando similitud: {str(e)}"}

    def format_article_for_api(self, article_data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """Formatea los datos del artículo para la API"""
        try:
            formatted_data = {
                'title': article_data.get('title', ''),
                'excerpt': article_data.get('excerpt', ''),
                'content': article_data.get('content', ''),
                'category': article_data.get('category', ''),
                'tags': article_data.get('tags', ''),
                'publishAs': '-1' if not article_data.get('publishAs') else str(article_data['publishAs']),
                'userId': str(user_id)
            }
            
            return {"status": "success", "data": formatted_data}
            
        except Exception as e:
            return {"status": "error", "message": f"Error formateando artículo: {str(e)}"}