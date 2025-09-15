"""
Agente automatizado refactorizado para generación de contenido basado en tendencias.
Esta versión utiliza módulos especializados para mejor mantenibilidad.
"""

import os
import json
import requests
import io
import traceback
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from openai import OpenAI

# Importar módulos especializados
from .text_utils import TextUtils
from .search_api import SearchAPI
from .article_manager import ArticleManager
from .content_processor import ContentProcessor
from .agent_manager import AgentManager
from load_env import load_env_files

load_env_files()


class AutomatedTrendsAgent:
    """
    Agente automatizado refactorizado que coordina la generación de contenido
    basado en tendencias usando módulos especializados.
    """
    
    # Cache estático para compartir entre instancias
    _trends_cache = {}
    _cache_timeout_minutes = 20
    
    def __init__(self, agent_config: Optional[Dict[str, Any]] = None):
        """Inicializa el agente con configuración opcional"""
        # Configuración de APIs
        self.openai_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
        self.api_endpoint = "https://fin.guru/api/agent-publish-article"
        
        self.next_public_api_url = os.getenv("NEXT_PUBLIC_API_URL")
        self.sudo_api_key = os.getenv("SUDO_API_KEY")
        
        # Configuración específica del agente
        self.agent_config = agent_config or {}
        self.agent_id = self.agent_config.get('id')
        self.agent_name = self.agent_config.get('name', 'default-agent')
        
        # Inicializar módulos especializados
        self.search_api = SearchAPI()
        self.article_manager = ArticleManager(self.next_public_api_url, self.sudo_api_key)
        self.content_processor = ContentProcessor()
        self.agent_manager = AgentManager(self.next_public_api_url, self.sudo_api_key)

    @classmethod
    def clear_trends_cache(cls):
        """Limpia el caché de tendencias"""
        cls._trends_cache.clear()
        print("🧹 Caché de tendencias limpiado")

    @classmethod
    def clear_session_cache(cls):
        """Limpia el caché de la sesión multi-agente"""
        # Esto ahora se maneja en AgentManager
        print("🧹 Caché de sesión limpiado")

    @classmethod
    def get_cache_status(cls) -> Dict[str, Any]:
        """Obtiene el estado actual del caché"""
        return {
            "trends_cache_size": len(cls._trends_cache),
            "cache_keys": list(cls._trends_cache.keys()),
            "cache_timeout_minutes": cls._cache_timeout_minutes
        }

    def get_trending_topics(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Obtiene temas trending con caché"""
        cache_key = "trending_topics"
        current_time = datetime.now()
        
        # Verificar caché
        if not force_refresh and cache_key in self._trends_cache:
            cached_data, cached_time = self._trends_cache[cache_key]
            if (current_time - cached_time).total_seconds() < (self._cache_timeout_minutes * 60):
                print(f"📦 Usando tendencias desde caché (edad: {(current_time - cached_time).total_seconds():.0f}s)")
                return cached_data
        
        # Obtener datos frescos
        print("🔄 Obteniendo tendencias frescas...")
        result = self.search_api.get_trending_topics(force_refresh)
        
        # Guardar en caché si es exitoso
        if result.get("status") == "success":
            self._trends_cache[cache_key] = (result, current_time)
            print(f"💾 Tendencias guardadas en caché por {self._cache_timeout_minutes} minutos")
        
        return result

    def publish_article(self, article_data: Dict[str, Any], trend_title: str, 
                       search_results: Dict[str, Any] = None, allow_no_image: bool = False) -> Dict[str, Any]:
        """Publica un artículo con imagen o sin ella como fallback de emergencia"""
        try:
            print(f"📤 Iniciando publicación del artículo: '{article_data['title']}'")
            
            # Validar datos del artículo
            validation_result = self.article_manager.validate_article_data(article_data)
            if validation_result.get("status") != "success":
                return validation_result
            
            # Buscar imagen con reintentos
            cover_image_data = None
            max_retries = 3
            
            for attempt in range(max_retries):
                print(f"🔍 Buscando imagen para el artículo... (intento {attempt + 1}/{max_retries})")
                try:
                    cover_image_data = self.search_api.search_image_with_multiple_queries(trend_title)
                    
                    if cover_image_data and len(cover_image_data) > 0:
                        print(f"✅ Imagen encontrada exitosamente ({len(cover_image_data)} bytes)")
                        break
                    else:
                        print(f"⚠️ No se obtuvo imagen válida en intento {attempt + 1}")
                        
                except Exception as e:
                    print(f"❌ Error en búsqueda de imagen (intento {attempt + 1}): {str(e)}")
                    
                if attempt < max_retries - 1:
                    import time
                    print(f"⏳ Esperando 2 segundos antes del siguiente intento...")
                    time.sleep(2)
            
            # Si no se encuentra imagen después de todos los intentos
            if not cover_image_data or len(cover_image_data) == 0:
                print(f"❌ No se pudo obtener imagen después de {max_retries} intentos")
                
                if allow_no_image:
                    print("🚨 Publicando sin imagen como último recurso...")
                    return self.publish_article_without_image(article_data)
                else:
                    return {
                        "status": "error",
                        "message": f"No se pudo obtener imagen para el artículo después de {max_retries} intentos"
                    }
            
            # Preparar datos para la API
            format_result = self.article_manager.format_article_for_api(
                article_data, 
                self.agent_config.get('userId', 5822)
            )
            
            if format_result.get("status") != "success":
                return format_result
            
            formatted_data = format_result["data"]
            filename = article_data['fileName']
            
            # Crear archivo de imagen
            try:
                image_file = io.BytesIO(cover_image_data)
                image_file.name = filename
                
                files = {
                    'cover': (filename, image_file, 'image/jpeg')
                }
                
                print(f"📤 Enviando artículo con imagen ({len(cover_image_data)} bytes)")
                
                # Realizar petición POST
                response = requests.post(
                    self.api_endpoint,
                    files=files,
                    data=formatted_data
                )
                
                print(f"📡 Response status: {response.status_code}")
                
                if response.status_code == 200:
                    response_text = response.text.lower()
                    if any(phrase in response_text for phrase in ['sin imagen', 'no image', 'missing image']):
                        return {
                            "status": "error",
                            "message": f"El servidor indica problema con la imagen: {response.text}"
                        }
                    
                    print("✅ Artículo publicado exitosamente CON imagen")
                    return {
                        "status": "success",
                        "message": "Artículo publicado exitosamente CON imagen",
                        "response": response.text,
                        "article_title": article_data['title'],
                        "cover_image_size": len(cover_image_data),
                        "filename": filename
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"Error del servidor: {response.status_code} - {response.text}"
                    }
                    
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Error preparando imagen: {str(e)}"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error publicando artículo: {str(e)}"
            }

    def publish_article_without_image(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """Publica un artículo sin imagen como fallback de emergencia"""
        try:
            print("🚨 FALLBACK: Publicando artículo SIN imagen")
            
            # Preparar datos para la API
            format_result = self.article_manager.format_article_for_api(
                article_data, 
                self.agent_config.get('userId', 5822)
            )
            
            if format_result.get("status") != "success":
                return format_result
            
            formatted_data = format_result["data"]
            
            print("📤 Enviando artículo SIN imagen al servidor")
            
            # Realizar petición POST sin archivos
            response = requests.post(
                self.api_endpoint,
                data=formatted_data
            )
            
            print(f"📡 Response status: {response.status_code}")
            
            if response.status_code == 200:
                print("⚠️ Artículo publicado exitosamente SIN imagen (fallback)")
                return {
                    "status": "success",
                    "message": "Artículo publicado exitosamente SIN imagen (fallback de emergencia)",
                    "response": response.text,
                    "article_title": article_data['title'],
                    "warning": "Publicado sin imagen por fallo en búsqueda"
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error del servidor al publicar sin imagen: {response.status_code} - {response.text}"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error publicando artículo sin imagen: {str(e)}"
            }

    def run_news_guaranteed_process(self, topic_position: int = None, allow_no_image: bool = False) -> Dict[str, Any]:
        """Ejecuta el proceso automatizado garantizando que se obtenga una noticia"""
        try:
            print(f"🚀 Iniciando proceso GARANTIZADO CON NOTICIA para agente: {self.agent_name}")
            
            # 1. Obtener tendencias
            trends_data = self.get_trending_topics()
            if trends_data.get("status") != "success":
                return {"status": "error", "message": "No se pudieron obtener tendencias"}
            
            # 2. Seleccionar tendencia
            trending_searches = trends_data.get("trending_topics", [])
            if not trending_searches:
                return {"status": "error", "message": "No hay tendencias disponibles"}
            
            if topic_position and 1 <= topic_position <= len(trending_searches):
                selected_trend = trending_searches[topic_position - 1]
                trend_title = selected_trend.get("title", "")
                print(f"🎯 Usando posición específica {topic_position}: {trend_title}")
            else:
                # Selección automática (podríamos usar GPT aquí)
                selected_trend = trending_searches[0]  # Por simplicidad, usar el primero
                trend_title = selected_trend.get("title", "")
                topic_position = 1
                print(f"🎯 Selección automática: #{topic_position} - {trend_title}")
            
            # 3. Verificar similitud con artículos recientes
            recent_articles = self.article_manager.get_agent_recent_articles(
                self.agent_config.get('userId', 5822)
            )
            
            if recent_articles.get("status") == "success":
                articles = recent_articles.get("articles", [])
                similarity_check = self.article_manager.check_article_similarity(trend_title, articles)
                
                if similarity_check.get("is_similar"):
                    print("⚠️ Tema similar ya fue cubierto recientemente")
                    return {
                        "status": "skipped",
                        "message": f"Tema '{trend_title}' ya fue cubierto recientemente",
                        "similar_article": similarity_check.get("message", "")
                    }
            
            # 4. 🔥 GARANTIZAR OBTENCIÓN DE NOTICIAS 🔥
            print("📰 GARANTIZANDO OBTENCIÓN DE NOTICIAS...")
            search_results = self.search_api.search_guaranteed_news(trend_title, max_attempts=8)
            
            if search_results.get("status") != "success":
                print(f"❌ CRÍTICO: No se pudieron obtener noticias después de múltiples intentos")
                return {
                    "status": "error",
                    "message": f"No se pudieron obtener noticias para '{trend_title}' después de múltiples estrategias",
                    "details": search_results.get("message", "")
                }
            
            # Validar que tenemos noticias reales
            news_results = search_results.get("results", {}).get("news", [])
            if not news_results or len(news_results) == 0:
                return {
                    "status": "error", 
                    "message": "No se obtuvieron noticias válidas después de búsqueda garantizada"
                }
            
            print(f"✅ NOTICIAS OBTENIDAS: {len(news_results)} noticias válidas")
            print(f"   Query utilizada: '{search_results.get('query_used', 'N/A')}'")
            print(f"   Tipo de búsqueda: {search_results.get('query_type', 'N/A')}")
            
            # Mostrar las primeras 3 noticias encontradas
            for i, news in enumerate(news_results[:3], 1):
                title = news.get("title", "Sin título")[:60]
                print(f"   📰 {i}. {title}...")
            
            # 5. Crear prompt y generar contenido
            prompt = self.content_processor.create_prompt(
                trends_data, search_results.get("results", {}), trend_title, topic_position, self.agent_config
            )
            
            agent_response = self.content_processor.generate_article_content(prompt)
            
            # 6. Procesar datos del artículo
            article_result = self.content_processor.process_article_data(agent_response)
            if article_result.get("status") != "success":
                return article_result
            
            article_data = article_result["data"]
            
            # 7. Validar contenido generado
            validation_result = self.content_processor.validate_generated_content(article_data)
            if validation_result.get("status") != "success":
                return validation_result
            
            # 8. Publicar artículo
            publish_result = self.publish_article(
                article_data, 
                trend_title, 
                search_results.get("results", {}), 
                allow_no_image=allow_no_image
            )
            
            return {
                "status": publish_result.get("status"),
                "message": publish_result.get("message"),
                "article_data": article_data,
                "trend_title": trend_title,
                "trend_position": topic_position,
                "news_guaranteed": True,
                "news_count": len(news_results),
                "news_query_used": search_results.get('query_used', 'N/A'),
                "news_search_type": search_results.get('query_type', 'N/A'),
                "publish_result": publish_result,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            error_msg = f"Error en proceso garantizado con noticias: {str(e)}"
            print(f"❌ {error_msg}")
            traceback.print_exc()
            return {"status": "error", "message": error_msg}

    def run_automated_process(self, topic_position: int = None) -> Dict[str, Any]:
        """Ejecuta el proceso automatizado completo para un solo agente"""
        try:
            print(f"🚀 Iniciando proceso automatizado para agente: {self.agent_name}")
            
            # 1. Obtener tendencias
            trends_data = self.get_trending_topics()
            if trends_data.get("status") != "success":
                return {"status": "error", "message": "No se pudieron obtener tendencias"}
            
            # 2. Seleccionar tendencia
            trending_searches = trends_data.get("trending_topics", [])
            if not trending_searches:
                return {"status": "error", "message": "No hay tendencias disponibles"}
            
            if topic_position and 1 <= topic_position <= len(trending_searches):
                selected_trend = trending_searches[topic_position - 1]
                trend_title = selected_trend.get("title", "")
                print(f"🎯 Usando posición específica {topic_position}: {trend_title}")
            else:
                # Selección automática (podríamos usar GPT aquí)
                selected_trend = trending_searches[0]  # Por simplicidad, usar el primero
                trend_title = selected_trend.get("title", "")
                topic_position = 1
                print(f"🎯 Selección automática: #{topic_position} - {trend_title}")
            
            # 3. Verificar similitud con artículos recientes
            recent_articles = self.article_manager.get_agent_recent_articles(
                self.agent_config.get('userId', 5822)
            )
            
            if recent_articles.get("status") == "success":
                articles = recent_articles.get("articles", [])
                similarity_check = self.article_manager.check_article_similarity(trend_title, articles)
                
                if similarity_check.get("is_similar"):
                    print("⚠️ Tema similar ya fue cubierto recientemente")
                    return {
                        "status": "skipped",
                        "message": f"Tema '{trend_title}' ya fue cubierto recientemente",
                        "similar_article": similarity_check.get("message", "")
                    }
            
            # 4. Buscar información adicional
            search_results = self.search_api.search_google_news(trend_title)
            
            # 5. Crear prompt y generar contenido
            prompt = self.content_processor.create_prompt(
                trends_data, search_results, trend_title, topic_position, self.agent_config
            )
            
            agent_response = self.content_processor.generate_article_content(prompt)
            
            # 6. Procesar datos del artículo
            article_result = self.content_processor.process_article_data(agent_response)
            if article_result.get("status") != "success":
                return article_result
            
            article_data = article_result["data"]
            
            # 7. Validar contenido generado
            validation_result = self.content_processor.validate_generated_content(article_data)
            if validation_result.get("status") != "success":
                return validation_result
            
            # 8. Publicar artículo (sin fallback sin imagen por defecto)
            publish_result = self.publish_article(article_data, trend_title, search_results, allow_no_image=False)
            
            return {
                "status": publish_result.get("status"),
                "message": publish_result.get("message"),
                "article_data": article_data,
                "trend_title": trend_title,
                "trend_position": topic_position,
                "publish_result": publish_result,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            error_msg = f"Error en proceso automatizado: {str(e)}"
            print(f"❌ {error_msg}")
            traceback.print_exc()
            return {"status": "error", "message": error_msg}

    def run_multi_agent_process(self, topic_position: int = None) -> Dict[str, Any]:
        """Ejecuta proceso con múltiples agentes desde la API"""
        try:
            print("🚀 Iniciando proceso multi-agente...")
            
            # 1. Obtener tendencias
            trends_data = self.get_trending_topics()
            if trends_data.get("status") != "success":
                return {"status": "error", "message": "No se pudieron obtener tendencias"}
            
            # 2. Inicializar agentes desde API
            agents = self.agent_manager.initialize_agents(self.article_manager)
            if not agents:
                return {"status": "error", "message": "No se pudieron inicializar agentes"}
            
            # 3. Distribuir agentes entre tópicos
            assignments = self.agent_manager.distribute_agents_across_topics(agents, trends_data, max_agents=5)
            if not assignments:
                return {"status": "error", "message": "No se pudieron asignar tópicos a los agentes"}
            
            # 4. Coordinar publicación
            def publish_callback(article_data, trend_title, search_results, agent_config):
                """Callback para publicar artículos de cada agente"""
                # Crear instancia temporal con configuración del agente
                temp_agent = AutomatedTrendsAgent(agent_config)
                return temp_agent.publish_article(article_data, trend_title, search_results, allow_no_image=False)
            
            results = self.agent_manager.coordinate_multi_agent_publishing(
                assignments, 
                self.search_api, 
                self.content_processor, 
                publish_callback
            )
            
            # 5. Estadísticas finales
            success_count = len(results["successful_publications"])
            total_count = results["total_agents"]
            
            print(f"\\n📊 RESUMEN FINAL:")
            print(f"   ✅ Exitosos: {success_count}/{total_count}")
            print(f"   ❌ Fallidos: {len(results['failed_publications'])}")
            print(f"   📈 Tasa de éxito: {results.get('success_rate', 0):.1%}")
            
            return {
                "status": "success",
                "message": f"Proceso multi-agente completado: {success_count}/{total_count} exitosos",
                "results": results,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            error_msg = f"Error en proceso multi-agente: {str(e)}"
            print(f"❌ {error_msg}")
            traceback.print_exc()
            return {"status": "error", "message": error_msg}

    # Métodos de conveniencia que delegan a los módulos especializados
    def get_agent_recent_articles(self, user_id: int) -> Dict[str, Any]:
        """Obtiene artículos recientes de un agente"""
        return self.article_manager.get_agent_recent_articles(user_id)

    def get_all_agents_recent_articles(self, limit_per_agent: int = 2) -> Dict[str, Any]:
        """Obtiene artículos recientes de todos los agentes"""
        return self.article_manager.get_all_agents_recent_articles(limit_per_agent)

    def get_available_agents(self) -> Dict[str, Any]:
        """Obtiene agentes disponibles"""
        return self.article_manager.get_available_agents()

    def initialize_agents(self) -> List[Dict[str, Any]]:
        """Inicializa agentes desde la API"""
        return self.agent_manager.initialize_agents(self.article_manager)

    def search_google_news(self, query: str) -> Dict[str, Any]:
        """Búsqueda de noticias"""
        return self.search_api.search_google_news(query)

    def search_google_images(self, query: str) -> str:
        """Búsqueda de imágenes"""
        return self.search_api.search_google_images(query)


# Funciones independientes para compatibilidad con el código existente
def run_trends_agent(topic_position: int = None):
    """Función independiente para ejecutar el agente"""
    agent = AutomatedTrendsAgent()
    return agent.run_automated_process(topic_position)


def run_trends_agent_with_guaranteed_news(topic_position: int = None, allow_no_image: bool = False):
    """Función independiente para ejecutar el agente GARANTIZANDO noticias"""
    agent = AutomatedTrendsAgent()
    return agent.run_news_guaranteed_process(topic_position, allow_no_image)


def run_multi_trends_agents(topic_position: int = None):
    """Función independiente para ejecutar múltiples agentes"""
    coordinator = AutomatedTrendsAgent()
    return coordinator.run_multi_agent_process(topic_position)


def get_available_agents():
    """Función independiente para obtener agentes disponibles"""
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
    """Función independiente para limpiar caché de sesión"""
    AutomatedTrendsAgent.clear_session_cache()
    return {"status": "success", "message": "Caché de sesión limpiado exitosamente"}


def get_cache_status():
    """Función independiente para obtener el estado del caché"""
    return AutomatedTrendsAgent.get_cache_status()


def get_trending_topics_cached():
    """Función independiente para obtener tendencias con caché"""
    agent = AutomatedTrendsAgent()
    return agent.get_trending_topics()