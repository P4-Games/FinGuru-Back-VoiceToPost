import os
import json
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from openai import OpenAI
from utils.trends_functions import TrendsAPI
from load_env import load_env_files
import html
import re
import string
import random
import io
import traceback

# Importar los nuevos módulos
from .cache_manager import CacheManager
from .article_manager import ArticleManager
from .search_services import SearchServices
from .content_processor import ContentProcessor
from .image_handler import ImageHandler
from .agent_manager import AgentManager

load_env_files()

class AutomatedTrendsAgent:
    def __init__(self, agent_config: Optional[Dict[str, Any]] = None):
        self.openai_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
        self.serper_api_key = "59e9db682aa8fd5c126e4fa6def959279d7167d4"
        self.trends_api = TrendsAPI()
        self.api_endpoint = "https://fin.guru/api/agent-publish-article"
        
        self.next_public_api_url = os.getenv("NEXT_PUBLIC_API_URL")
        self.sudo_api_key = os.getenv("SUDO_API_KEY")
        
        # Configuración específica del agente si se proporciona
        self.agent_config = agent_config or {}
        self.agent_id = self.agent_config.get('id')
        self.agent_name = self.agent_config.get('name', 'default-agent')
        self.personality = self.agent_config.get('personality', 'Eres un periodista especializado en tendencias de Argentina que debe crear contenido en Markdown')
        self.trending_prompt = self.agent_config.get('trending', 'Considera: - Relevancia para Argentina - Potencial de generar interés - Actualidad e importancia - Impacto social, económico o cultural')
        self.format_markdown = self.agent_config.get('format_markdown', '')
        
        # Inicializar los módulos auxiliares
        self.cache_manager = CacheManager()
        self.article_manager = ArticleManager()
        self.search_services = SearchServices(self.serper_api_key)
        self.content_processor = ContentProcessor(self.openai_client)
        self.image_handler = ImageHandler()
        self.agent_manager = AgentManager(self.next_public_api_url, self.sudo_api_key)
        
    def _is_topic_similar_to_recent_articles(self, topic_title: str, recent_articles: List[Dict]) -> bool:
        """Verifica si un tópico es similar a los artículos recientes usando palabras clave específicas"""
        return self.article_manager.is_topic_similar_to_recent_articles(topic_title, recent_articles)

    def get_agent_recent_articles(self, user_id: int) -> Dict[str, Any]:
        """Obtiene los últimos 2 artículos del agente para evitar repetir temas"""
        return self.article_manager.get_agent_recent_articles(user_id)

    def get_all_agents_recent_articles(self, limit_per_agent: int = 2) -> Dict[str, Any]:
        """Obtiene los artículos recientes de TODOS los agentes para evitar repetir temas"""
        return self.article_manager.get_all_agents_recent_articles(
            self.agent_manager.get_available_agents, 
            limit_per_agent
        )

    def get_available_agents(self) -> Dict[str, Any]:
        """Obtiene todos los agentes disponibles desde la API"""
        return self.agent_manager.get_available_agents()

    def initialize_agents(self) -> List['AutomatedTrendsAgent']:
        """Inicializa todos los agentes disponibles con sus configuraciones únicas"""
        return self.agent_manager.initialize_agents(AutomatedTrendsAgent)

    def get_trending_topics(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Obtiene los temas trending de Google Trends Argentina con caché"""
        cache_key = "trending_topics_AR"
        
        # Verificar caché existente
        if not force_refresh and self.cache_manager.is_cache_valid(cache_key):
            print("   📁 Obteniendo temas trending desde el caché...")
            return self.cache_manager.get_cached_data(cache_key)
        
        print("🔍 Obteniendo temas trending desde Google Trends Argentina...")
        try:
            trends_data = self.trends_api.get_trending_topics("AR")
            self.cache_manager.set_cached_data(cache_key, trends_data)
            return trends_data
        except Exception as e:
            print(f"Error obteniendo tendencias: {str(e)}")
            # Intentar retornar datos del caché aunque estén expirados
            cached_data = self.cache_manager.get_cached_data(cache_key)
            if cached_data:
                print("   ⚠️ Usando datos de caché expirados como fallback")
                return cached_data
            return {}

    def search_google_news(self, query: str) -> Dict[str, Any]:
        """Busca información adicional sobre el tema en Google usando Serper API"""
        return self.search_services.search_google_news(query)

    def search_google_images(self, query: str) -> str:
        """Busca una imagen relevante usando Serper API con múltiples intentos"""
        return self.search_services.search_google_images(query)

    def _convert_serper_to_serpapi_format(self, serper_results: Dict[str, Any]) -> Dict[str, Any]:
        """Convierte el formato de Serper al formato esperado por SerpAPI"""
        return self.search_services._convert_serper_to_serpapi_format(serper_results)

    def _is_valid_image_url(self, url: str) -> bool:
        """Verifica si la URL de imagen es válida - VERSIÓN MUY PERMISIVA"""
        return self.image_handler.is_valid_image_url(url)

    def download_image_from_url(self, url: str) -> Optional[bytes]:
        """Descarga una imagen desde una URL con validaciones mejoradas"""
        return self.image_handler.download_image_from_url(url)

    def create_prompt(self, trends_data: Dict[str, Any], search_results: Dict[str, Any], selected_trend: str, topic_position: int = None) -> str:
        """Crea el prompt para ChatGPT basado en las tendencias y búsquedas"""
        return self.content_processor.create_prompt(
            trends_data, search_results, selected_trend, 
            self.personality, self.trending_prompt, self.format_markdown, 
            topic_position
        )

    def generate_article_content(self, prompt: str) -> str:
        """Genera el contenido del artículo usando ChatGPT"""
        return self.content_processor.generate_article_content(prompt, self.personality)

    def markdown_to_html(self, md: str) -> str:
        """Convierte Markdown simple a HTML"""
        return self.content_processor.markdown_to_html(md)

    def process_article_data(self, agent_response: str) -> Dict[str, Any]:
        """Procesa la respuesta del agente para la API de fin.guru"""
        return self.content_processor.process_article_data(agent_response)

    def publish_article(self, article_data: Dict[str, Any], trend_title: str, search_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """Publica el artículo usando la API de fin.guru con imagen automática"""
        try:
            print(f"📤 Publicando artículo: {article_data.get('title', 'Sin título')[:50]}...")
            
            headers = {
                "Content-Type": "application/json",
            }
            
            # Configurar userId según el agente
            user_id = self.agent_config.get('userId', 5822)
            
            payload = {
                **article_data,
                "userId": user_id,
                "image": ""
            }
            
            # Buscar imagen automáticamente
            image_query = trend_title
            search_attempts = [
                {"query": image_query, "source": "trend_title"},
                {"query": f"{image_query} Argentina", "source": "trend_with_country"},
                {"query": article_data.get('title', '')[:50], "source": "article_title"}
            ]
            
            # Intentar también con resultados de búsqueda si están disponibles
            if search_results:
                if "top_stories" in search_results and search_results["top_stories"]:
                    for i, story in enumerate(search_results["top_stories"][:2]):
                        story_title = story.get("title", "")
                        if story_title:
                            search_attempts.append({
                                "query": story_title[:50],
                                "source": f"top_story_{i+1}"
                            })
            
            image_found = False
            
            for attempt_num, attempt in enumerate(search_attempts, 1):
                if image_found:
                    break
                    
                try:
                    query = attempt["query"]
                    source_type = attempt["source"]
                    
                    print(f"      🖼️ Intento #{attempt_num}: Buscando imagen para '{query[:30]}...' (fuente: {source_type})")
                    
                    image_url = self.search_google_images(query)
                    
                    if image_url:
                        downloaded_data = self.download_image_from_url(image_url)
                        
                        if downloaded_data:
                            image_source = f"google_images_from_{source_type}_attempt_{attempt_num}"
                            
                            files = {
                                'data': (None, json.dumps(payload), 'application/json'),
                                'files.image': (
                                    article_data.get('fileName', 'image.jpg'),
                                    io.BytesIO(downloaded_data),
                                    'image/jpeg'
                                )
                            }
                            
                            # Headers para multipart/form-data (sin Content-Type manual)
                            multipart_headers = {}
                            
                            print(f"         📎 Enviando artículo con imagen desde {image_source}...")
                            response = requests.post(self.api_endpoint, files=files, headers=multipart_headers)
                            
                            if response.ok:
                                result = response.json()
                                print(f"         ✅ Artículo publicado exitosamente con imagen!")
                                print(f"         🔗 URL de imagen utilizada: {image_url}")
                                result['image_source'] = image_source
                                result['image_url_used'] = image_url
                                result['attempt_number'] = attempt_num
                                result['query_used'] = query
                                image_found = True
                                return result
                            else:
                                print(f"         ❌ Error publicando con imagen: HTTP {response.status_code}")
                                if response.text:
                                    print(f"            Respuesta: {response.text[:200]}")
                        else:
                            print(f"         ❌ No se pudo descargar la imagen")
                    else:
                        print(f"         ❌ No se encontró imagen para la consulta")
                        
                except Exception as e:
                    print(f"         ❌ Error en intento #{attempt_num}: {str(e)}")
                    continue
            
            if not image_found:
                print(f"      ⚠️ No se pudo obtener imagen después de {len(search_attempts)} intentos")
                print(f"      📝 Publicando artículo SIN imagen...")
                
                response = requests.post(self.api_endpoint, json=payload, headers=headers)
                
                if response.ok:
                    result = response.json()
                    print(f"      ✅ Artículo publicado exitosamente SIN imagen")
                    result['image_source'] = 'none'
                    result['image_attempts'] = len(search_attempts)
                    return result
                else:
                    print(f"      ❌ Error publicando sin imagen: HTTP {response.status_code}")
                    if response.text:
                        print(f"         Respuesta: {response.text[:200]}")
                    return {
                        "success": False,
                        "error": f"HTTP error: {response.status_code}",
                        "response": response.text
                    }
            
        except Exception as e:
            print(f"❌ Error general publicando artículo: {str(e)}")
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def run_automated_process(self, topic_position: int = None) -> Dict[str, Any]:
        """Ejecuta el proceso completo automatizado para un solo agente"""
        try:
            print(f"\n{'='*60}")
            print(f"🤖 PROCESO AUTOMATIZADO INICIADO")
            print(f"{'='*60}")
            print(f"Agente: {self.agent_name} (ID: {self.agent_id})")
            print(f"UserId: {self.agent_config.get('userId', 'No definido')}")
            
            # Obtener tendencias
            trends_data = self.get_trending_topics()
            
            if not trends_data or 'trending_topics' not in trends_data:
                return {"status": "error", "message": "No se pudieron obtener tendencias"}
            
            trending_topics = trends_data.get('trending_topics', [])
            
            if not trending_topics:
                return {"status": "error", "message": "No hay temas trending disponibles"}
            
            print(f"\n📊 Tendencias disponibles: {len(trending_topics)}")
            for i, topic in enumerate(trending_topics[:10], 1):
                title = topic.get('title', topic) if isinstance(topic, dict) else str(topic)
                if isinstance(title, dict):
                    title = title.get('query', str(title))
                print(f"   {i}. {title}")
            
            # Obtener artículos recientes del agente para evitar duplicados
            user_id = self.agent_config.get('userId', 5822)
            recent_articles_result = self.get_agent_recent_articles(user_id)
            recent_articles = recent_articles_result.get('articles', []) if recent_articles_result.get('status') == 'success' else []
            
            # Seleccionar tema
            selected_trend = None
            selected_position = None
            
            if topic_position is not None:
                if 1 <= topic_position <= len(trending_topics):
                    topic = trending_topics[topic_position - 1]
                    selected_trend = topic.get('title', topic) if isinstance(topic, dict) else str(topic)
                    if isinstance(selected_trend, dict):
                        selected_trend = selected_trend.get('query', str(selected_trend))
                    selected_position = topic_position
                    print(f"🎯 Tema seleccionado por posición #{topic_position}: {selected_trend}")
                else:
                    return {"status": "error", "message": f"Posición {topic_position} inválida. Debe estar entre 1 y {len(trending_topics)}"}
            else:
                # Selección automática evitando similares
                for i, topic in enumerate(trending_topics):
                    topic_title = topic.get('title', topic) if isinstance(topic, dict) else str(topic)
                    if isinstance(topic_title, dict):
                        topic_title = topic_title.get('query', str(topic_title))
                    
                    if not self._is_topic_similar_to_recent_articles(topic_title, recent_articles):
                        selected_trend = topic_title
                        selected_position = i + 1
                        print(f"🎯 Tema seleccionado automáticamente: {selected_trend} (posición #{selected_position})")
                        break
                
                if not selected_trend:
                    selected_trend = trending_topics[0].get('title', trending_topics[0]) if isinstance(trending_topics[0], dict) else str(trending_topics[0])
                    if isinstance(selected_trend, dict):
                        selected_trend = selected_trend.get('query', str(selected_trend))
                    selected_position = 1
                    print(f"⚠️ Usando primer tema como fallback: {selected_trend}")
            
            # Búsqueda adicional
            print(f"\n🔍 Buscando información adicional...")
            search_results = self.search_google_news(selected_trend)
            
            # Crear prompt
            print(f"\n✍️ Generando prompt para ChatGPT...")
            prompt = self.create_prompt(trends_data, search_results, selected_trend, selected_position)
            
            # Generar contenido
            print(f"\n🤖 Generando contenido del artículo...")
            agent_response = self.generate_article_content(prompt)
            
            if not agent_response:
                return {"status": "error", "message": "No se pudo generar contenido"}
            
            # Procesar datos del artículo
            article_data = self.process_article_data(agent_response)
            
            # Publicar artículo
            print(f"\n📤 Publicando artículo...")
            publish_result = self.publish_article(article_data, selected_trend, search_results)
            
            final_result = {
                "status": "success",
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
                "user_id": user_id,
                "selected_trend": selected_trend,
                "selected_position": selected_position,
                "article_title": article_data.get('title'),
                "article_category": article_data.get('category'),
                "publish_result": publish_result,
                "trends_total": len(trending_topics)
            }
            
            print(f"\n✅ PROCESO COMPLETADO EXITOSAMENTE")
            print(f"📰 Título: {article_data.get('title')}")
            print(f"📁 Categoría: {article_data.get('category')}")
            print(f"🎯 Tema: {selected_trend}")
            print(f"{'='*60}\n")
            
            return final_result
            
        except Exception as e:
            error_msg = f"Error en proceso automatizado: {str(e)}"
            print(f"❌ {error_msg}")
            traceback.print_exc()
            return {"status": "error", "message": error_msg}

    def run_multi_agent_process(self, topic_position: int = None) -> Dict[str, Any]:
        """Ejecuta el proceso usando múltiples agentes especializados"""
        try:
            print(f"\n{'='*80}")
            print(f"🚀 PROCESO MULTI-AGENTE INICIADO")
            print(f"{'='*80}")
            
            # Obtener tendencias
            trends_data = self.get_trending_topics()
            
            if not trends_data or 'trending_topics' not in trends_data:
                return {"status": "error", "message": "No se pudieron obtener tendencias"}
            
            trending_topics = trends_data.get('trending_topics', [])
            
            if not trending_topics:
                return {"status": "error", "message": "No hay temas trending disponibles"}
            
            print(f"\n📊 Tendencias disponibles: {len(trending_topics)}")
            for i, topic in enumerate(trending_topics[:10], 1):
                title = topic.get('title', topic) if isinstance(topic, dict) else str(topic)
                if isinstance(title, dict):
                    title = title.get('query', str(title))
                print(f"   {i}. {title}")
            
            # Inicializar agentes
            agents = self.initialize_agents()
            
            if not agents:
                return {"status": "error", "message": "No se pudieron inicializar agentes"}
            
            print(f"\n🤖 {len(agents)} agentes inicializados:")
            for agent in agents:
                print(f"   - {agent.agent_name} (ID: {agent.agent_id})")
            
            # Obtener artículos recientes de TODOS los agentes para evitar duplicados
            all_recent_articles_result = self.get_all_agents_recent_articles(limit_per_agent=2)
            all_recent_articles = all_recent_articles_result.get('articles', []) if all_recent_articles_result.get('status') == 'success' else []
            
            print(f"\n📚 Se encontraron {len(all_recent_articles)} artículos recientes de todos los agentes")
            
            # Seleccionar tema evitando duplicados y temas ya usados en esta sesión
            selected_trend = None
            selected_position = None
            
            if topic_position is not None:
                # Posición específica solicitada
                if 1 <= topic_position <= len(trending_topics):
                    topic = trending_topics[topic_position - 1]
                    selected_trend = topic.get('title', topic) if isinstance(topic, dict) else str(topic)
                    if isinstance(selected_trend, dict):
                        selected_trend = selected_trend.get('query', str(selected_trend))
                    selected_position = topic_position
                    print(f"🎯 Tema seleccionado por posición #{topic_position}: {selected_trend}")
                else:
                    return {"status": "error", "message": f"Posición {topic_position} inválida. Debe estar entre 1 y {len(trending_topics)}"}
            else:
                # Selección automática con lógica mejorada
                print(f"\n🔍 Buscando tema no usado en esta sesión...")
                
                # Obtener temas y posiciones ya seleccionadas
                selected_trends_session = self.cache_manager.get_selected_trends()
                selected_positions_session = self.cache_manager.get_selected_positions()
                
                print(f"   Temas ya seleccionados en esta sesión: {len(selected_trends_session)}")
                print(f"   Posiciones ya usadas: {sorted(list(selected_positions_session))}")
                
                for i, topic in enumerate(trending_topics):
                    position = i + 1
                    topic_title = topic.get('title', topic) if isinstance(topic, dict) else str(topic)
                    if isinstance(topic_title, dict):
                        topic_title = topic_title.get('query', str(topic_title))
                    
                    # Verificar si ya fue seleccionado en esta sesión
                    if topic_title in selected_trends_session:
                        print(f"   ⏭️ Saltando '{topic_title}' - Ya seleccionado en esta sesión")
                        continue
                    
                    if position in selected_positions_session:
                        print(f"   ⏭️ Saltando posición #{position} - Ya usada en esta sesión")
                        continue
                    
                    # Verificar similitud con artículos recientes
                    if not self._is_topic_similar_to_recent_articles(topic_title, all_recent_articles):
                        selected_trend = topic_title
                        selected_position = position
                        print(f"   ✅ Tema único encontrado: {selected_trend} (posición #{selected_position})")
                        break
                    else:
                        print(f"   ⚠️ Tema '{topic_title}' muy similar a artículos recientes - Saltando")
                
                if not selected_trend:
                    # Si no encontramos tema único, usar el primero disponible que no esté en sesión
                    for i, topic in enumerate(trending_topics):
                        position = i + 1
                        topic_title = topic.get('title', topic) if isinstance(topic, dict) else str(topic)
                        if isinstance(topic_title, dict):
                            topic_title = topic_title.get('query', str(topic_title))
                        
                        if topic_title not in selected_trends_session and position not in selected_positions_session:
                            selected_trend = topic_title
                            selected_position = position
                            print(f"   🔄 Usando tema como fallback: {selected_trend} (posición #{selected_position})")
                            break
                
                if not selected_trend:
                    # Último recurso: usar el primer tema aunque ya haya sido usado
                    topic = trending_topics[0]
                    selected_trend = topic.get('title', topic) if isinstance(topic, dict) else str(topic)
                    if isinstance(selected_trend, dict):
                        selected_trend = selected_trend.get('query', str(selected_trend))
                    selected_position = 1
                    print(f"   🆘 Último recurso - usando: {selected_trend}")
            
            # Marcar tema y posición como seleccionados en esta sesión
            self.cache_manager.add_selected_trend(selected_trend)
            self.cache_manager.add_selected_position(selected_position)
            
            # Seleccionar agente aleatorio para este tema
            selected_agent = random.choice(agents)
            print(f"\n🎲 Agente seleccionado aleatoriamente: {selected_agent.agent_name} (ID: {selected_agent.agent_id})")
            
            # Búsqueda adicional
            print(f"\n🔍 Buscando información adicional sobre: {selected_trend}")
            search_results = selected_agent.search_google_news(selected_trend)
            
            # Crear prompt con la configuración específica del agente
            print(f"\n✍️ Generando prompt personalizado...")
            prompt = selected_agent.create_prompt(trends_data, search_results, selected_trend, selected_position)
            
            # Generar contenido usando el agente seleccionado
            print(f"\n🤖 Generando contenido con {selected_agent.agent_name}...")
            agent_response = selected_agent.generate_article_content(prompt)
            
            if not agent_response:
                return {"status": "error", "message": "No se pudo generar contenido"}
            
            # Procesar datos del artículo
            article_data = selected_agent.process_article_data(agent_response)
            
            # Publicar artículo
            print(f"\n📤 Publicando artículo...")
            publish_result = selected_agent.publish_article(article_data, selected_trend, search_results)
            
            final_result = {
                "status": "success",
                "selected_agent_id": selected_agent.agent_id,
                "selected_agent_name": selected_agent.agent_name,
                "user_id": selected_agent.agent_config.get('userId'),
                "selected_trend": selected_trend,
                "selected_position": selected_position,
                "article_title": article_data.get('title'),
                "article_category": article_data.get('category'),
                "publish_result": publish_result,
                "trends_total": len(trending_topics),
                "agents_available": len(agents),
                "session_trends_used": len(self.cache_manager.get_selected_trends()),
                "session_positions_used": len(self.cache_manager.get_selected_positions())
            }
            
            print(f"\n✅ PROCESO MULTI-AGENTE COMPLETADO EXITOSAMENTE")
            print(f"🤖 Agente usado: {selected_agent.agent_name}")
            print(f"📰 Título: {article_data.get('title')}")
            print(f"📁 Categoría: {article_data.get('category')}")
            print(f"🎯 Tema: {selected_trend}")
            print(f"📊 Temas usados en sesión: {len(self.cache_manager.get_selected_trends())}/{len(trending_topics)}")
            print(f"{'='*80}\n")
            
            return final_result
            
        except Exception as e:
            error_msg = f"Error en proceso multi-agente: {str(e)}"
            print(f"❌ {error_msg}")
            traceback.print_exc()
            return {"status": "error", "message": error_msg}

    @classmethod
    def clear_trends_cache(cls):
        """Limpia el caché de tendencias manualmente"""
        CacheManager.clear_trends_cache()
    
    @classmethod
    def clear_session_cache(cls):
        """Limpia el caché de sesión de tendencias seleccionadas manualmente"""
        CacheManager.clear_session_cache()
    
    @classmethod
    def get_cache_status(cls) -> Dict[str, Any]:
        """Obtiene el estado actual del caché"""
        return CacheManager.get_cache_status()

    def _validate_and_parse_data(self, data: Any, data_type: str = "unknown") -> Dict[str, Any]:
        """Valida y parsea datos, retornando un diccionario válido"""
        return self.content_processor._validate_and_parse_data(data, data_type)

    def _extract_trend_title(self, trends_data: Dict[str, Any], position: int = 1) -> str:
        """Extrae el título de una tendencia por posición"""
        trending_topics = trends_data.get("trending_topics", [])
        
        if not trending_topics or position < 1 or position > len(trending_topics):
            return ""
        
        topic = trending_topics[position - 1]
        
        if isinstance(topic, dict):
            title = topic.get('title', '')
            if isinstance(title, dict):
                return title.get('query', str(title))
            return str(title)
        
        return str(topic)


# Funciones independientes para compatibilidad
def run_automated_agent_process(topic_position: int = None):
    """Función independiente para ejecutar proceso de un solo agente"""
    agent = AutomatedTrendsAgent()
    return agent.run_automated_process(topic_position)

def run_multi_agent_process(topic_position: int = None):
    """Función independiente para ejecutar proceso multi-agente"""
    coordinator = AutomatedTrendsAgent()
    return coordinator.run_multi_agent_process(topic_position)

def get_available_agents():
    """Función independiente para obtener agentes disponibles de la API"""
    agent = AutomatedTrendsAgent()
    return agent.get_available_agents()

def get_all_agents_recent_articles(limit_per_agent: int = 2):
    """Función independiente para obtener artículos recientes de TODOS los agentes"""
    agent = AutomatedTrendsAgent()
    return agent.get_all_agents_recent_articles(limit_per_agent)

def initialize_agents_from_api():
    """Función independiente para inicializar agentes desde la API"""
    agent = AutomatedTrendsAgent()
    return agent.initialize_agents()

def clear_trends_cache():
    """Función independiente para limpiar el caché de tendencias"""
    AutomatedTrendsAgent.clear_trends_cache()
    return {"status": "success", "message": "Caché limpiado exitosamente"}

def clear_session_cache():
    """Función independiente para limpiar caché de sesión (tendencias ya seleccionadas)"""
    AutomatedTrendsAgent.clear_session_cache()
    return {"status": "success", "message": "Caché de sesión limpiado exitosamente"}

def get_cache_status():
    """Función independiente para obtener el estado del caché"""
    return AutomatedTrendsAgent.get_cache_status()

def get_trending_topics_cached():
    """Función independiente para obtener tendencias con caché"""
    agent = AutomatedTrendsAgent()
    return agent.get_trending_topics()