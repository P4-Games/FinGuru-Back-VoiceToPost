"""
Módulo para el manejo de artículos del sistema de tendencias automatizado.
Proporciona funcionalidades para obtener, validar y comparar artículos.
"""

import requests
from typing import Dict, Any, List


class ArticleManager:
    """Gestor de artículos para el sistema de tendencias automatizado"""
    
    @staticmethod
    def is_topic_similar_to_recent_articles(topic_title: str, recent_articles: List[Dict]) -> bool:
        """Verifica si un tópico es similar a los artículos recientes usando palabras clave específicas"""
        if not recent_articles or not topic_title:
            return False
        
        generic_words = {
            'argentina', 'argentino', 'argentinos', 'argentinas', 'país', 'nacional', 'gobierno', 
            'política', 'político', 'políticos', 'políticas', 'deportes', 'deporte', 'deportivos',
            'economia', 'económico', 'económicos', 'económicas', 'tecnología', 'tecnológico',
            'entretenimiento', 'cultura', 'cultural', 'sociales', 'social', 'nuevo', 'nueva',
            'últimas', 'último', 'noticias', 'noticia', 'actualidad', 'hoy', 'ayer', 'semana',
            'mes', 'año', 'día', 'mundo', 'internacional', 'global', 'local', 'nacional',
            'público', 'pública', 'privado', 'privada', 'importante', 'gran', 'grande', 'mayor',
            'mejor', 'primera', 'primer', 'segundo', 'tercero', 'sobre', 'para', 'con', 'sin',
            'desde', 'hasta', 'entre', 'por', 'en', 'de', 'del', 'la', 'el', 'los', 'las',
            'un', 'una', 'unos', 'unas', 'este', 'esta', 'estos', 'estas', 'ese', 'esa'
        }
        
        topic_keywords = set(word.lower() for word in topic_title.lower().split() 
                           if word.lower() not in generic_words and len(word) > 2)
        
        for article in recent_articles:
            article_title = article.get('title', '').lower()
            article_excerpt = article.get('excerpt', '').lower()
            
            # Palabras clave del artículo (sin palabras genéricas)
            article_keywords = set()
            for word in (article_title + ' ' + article_excerpt).split():
                if word.lower() not in generic_words and len(word) > 2:
                    article_keywords.add(word.lower())
            
            # Calcular similitud (intersección de palabras clave específicas)
            common_keywords = topic_keywords.intersection(article_keywords)
            
            # Ser más estricto: requiere al menos 3 palabras específicas en común Y alta similitud
            if len(common_keywords) >= 3:
                similarity_ratio = len(common_keywords) / max(len(topic_keywords), 1)
                if similarity_ratio > 0.6:  # Aumentar el umbral a 60%
                    print(f"   ⚠️ Tópico '{topic_title}' MUY similar a artículo '{article.get('title')}' (similitud: {similarity_ratio:.2f})")
                    print(f"   🔑 Palabras específicas en común: {list(common_keywords)}")
                    return True
        
        return False

    @staticmethod
    def get_agent_recent_articles(user_id: int) -> Dict[str, Any]:
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
            print(f"Error obteniendo artículos del agente: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "articles": []
            }

    @staticmethod
    def get_all_agents_recent_articles(get_available_agents_func, limit_per_agent: int = 2) -> Dict[str, Any]:
        """Obtiene los artículos recientes de TODOS los agentes para evitar repetir temas"""
        try:
            print(f"Obteniendo últimos {limit_per_agent} artículos de TODOS los agentes...")
            
            # Primero obtener todos los agentes
            agents_response = get_available_agents_func()
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
                    agent_articles = ArticleManager.get_agent_recent_articles(user_id)
                    
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