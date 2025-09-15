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
        """Obtiene los últimos 2 artículos del agente para evitar repetir temas"""
        try:
            print(f"Obteniendo últimos artículos del agente (User ID: {user_id})...")
            
            endpoint = f"https://backend.fin.guru/api/articles?filters[author][id][$eq]={user_id}&sort=createdAt:desc&pagination[limit]=2&fields[0]=title&fields[1]=excerpt&populate=category"
            
            headers = {
                "Content-Type": "application/json",
            }
            
            response = requests.get(endpoint, headers=headers)
            
            if not response.ok:
                print(f"Error obteniendo artículos del agente: HTTP {response.status_code}")
                return {"status": "error", "message": f"HTTP error: {response.status_code}", "articles": []}
            
            data = response.json()
            articles = []
            
            if 'data' in data and isinstance(data['data'], list):
                for article in data['data']:
                    if isinstance(article, dict) and 'attributes' in article:
                        attr = article['attributes']
                        
                        category_name = ""
                        category_data = attr.get('category', {})
                        if isinstance(category_data, dict) and 'data' in category_data:
                            category_attrs = category_data.get('data', {}).get('attributes', {})
                            category_name = category_attrs.get('name', '')
                        
                        articles.append({
                            'id': article.get('id'),
                            'title': attr.get('title', ''),
                            'excerpt': attr.get('excerpt', ''),
                            'category': category_name,
                            'createdAt': attr.get('createdAt', '')
                        })
            
            print(f"Se encontraron {len(articles)} artículos recientes")
            for i, article in enumerate(articles):
                print(f"   {i+1}. {article.get('title', 'Sin título')} (ID: {article.get('id')}) - Categoría: {article.get('category', 'N/A')}")
            
            return {
                "status": "success",
                "articles": articles,
                "total": len(articles)
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
                    processed_agents = []
                    for agent in agents:
                        if isinstance(agent, dict):
                            # Extraer userId del usuario poblado
                            user_id = None
                            user_data = agent.get('attributes', {}).get('user', {})
                            if isinstance(user_data, dict) and 'data' in user_data:
                                user_id = user_data.get('data', {}).get('id')
                            elif isinstance(user_data, dict) and 'id' in user_data:
                                user_id = user_data.get('id')
                            
                            processed_agent = {
                                'id': agent.get('id'),
                                'name': agent.get('attributes', {}).get('name', f"agent-{agent.get('id')}"),
                                'personality': agent.get('attributes', {}).get('personality', ''),
                                'trending': agent.get('attributes', {}).get('trending', ''),
                                'format_markdown': agent.get('attributes', {}).get('format_markdown', ''),
                                'userId': user_id,
                                'createdAt': agent.get('attributes', {}).get('createdAt', ''),
                                'updatedAt': agent.get('attributes', {}).get('updatedAt', ''),
                                'publishedAt': agent.get('attributes', {}).get('publishedAt', '')
                            }
                            processed_agents.append(processed_agent)
                    agents = processed_agents
            
            print(f"Se encontraron {len(agents)} agentes disponibles")
            for agent in agents:
                print(f"   - ID: {agent.get('id')}, Nombre: {agent.get('name')}")
            
            return {
                'status': 'success',
                'details': agents,
                'total': len(agents)
            }
            
        except Exception as e:
            print(f"Error obteniendo agentes desde la API: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'details': [],
                'total': 0
            }

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