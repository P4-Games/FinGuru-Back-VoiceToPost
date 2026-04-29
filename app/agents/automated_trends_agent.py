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
import uuid

# Refactored utils
from .agent_api_utils import (
    get_available_agents,
    get_agent_recent_articles,
    get_all_agents_recent_articles,
    get_recent_finguru_articles,
    search_google_news,
    search_google_images,
    download_image_from_url
)
from .agent_content_utils import (
    _is_topic_similar_to_recent_articles,
    _is_topic_trivial_or_contextual,
    _validate_article_depth,
    create_prompt,
    generate_article_content,
    process_article_data,
    _extract_trend_title,
    _validate_and_parse_data
)
from .agent_profile import AgentProfile
from .market_data_utils import get_market_data_snapshot
from .trends_pipeline import TrendsPipeline

load_env_files()

class AutomatedTrendsAgent:
    _trends_cache = {}
    _cache_timeout_minutes = 20
    
    _selected_trends_session = set()
    _selected_positions_session = set()
    
    def __init__(self, agent_config: Optional[Dict[str, Any]] = None):
        self.openai_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
        self.serper_api_key = "59e9db682aa8fd5c126e4fa6def959279d7167d4"
        self.trends_api = TrendsAPI()
        self.api_endpoint = "https://fin.guru/api/agent-publish-article"
        
        self.next_public_api_url = os.getenv("NEXT_PUBLIC_API_URL")
        self.sudo_api_key = os.getenv("SUDO_API_KEY")
        
        profile = AgentProfile.from_flat_payload(agent_config or {})
        self.agent_config = profile.to_agent_dict()
        self.agent_id = self.agent_config.get('id')
        self.agent_name = self.agent_config.get('name', 'default-agent')
        self.personality = self.agent_config.get('personality', 'Eres un periodista especializado en tendencias de Argentina que debe crear contenido en Markdown')
        self.trending_prompt = self.agent_config.get('trending', 'Considera: - Relevancia para Argentina - Potencial de generar interés - Actualidad e importancia - Impacto social, económico o cultural')
        self.format_markdown = self.agent_config.get('format_markdown', '')
        self.writing_style = self.agent_config.get('writing_style', 'periodistico')
        self.tone = self.agent_config.get('tone', 'neutral')
        self.target_audience = self.agent_config.get('target_audience', 'audiencia general argentina')
        self.preferred_categories = self.agent_config.get('preferred_categories', [])
        self.example_article = self.agent_config.get('example_article', '')
        self.forbidden_topics = self.agent_config.get('forbidden_topics', [])
        self.temperature = self.agent_config.get('temperature', 0.6)
        self.max_tokens = self.agent_config.get('max_tokens', 1400)
        self.pipeline_v2 = TrendsPipeline()

    def initialize_agents(self) -> List['AutomatedTrendsAgent']:
        """Inicializa todos los agentes disponibles con sus configuraciones únicas"""
        try:
            print("Inicializando agentes múltiples...")
            
            agents_response = get_available_agents(self)
            
            if agents_response.get('status') != 'success':
                print(f"Error obteniendo agentes: {agents_response.get('message')}")
                return []
            
            agents_data = agents_response.get('details', [])
            initialized_agents = []
            
            for agent_data in agents_data:
                try:
                    profile = AgentProfile.from_flat_payload(agent_data)
                    agent_id = profile.id
                    agent_user_id = profile.user_id
                    
                    if not agent_user_id:
                        print(f"No se encontró userId para el agente {agent_id}, usando ID por defecto")
                        agent_user_id = 5822
                        profile.user_id = agent_user_id

                    if profile.format_markdown:
                        profile.format_markdown = html.unescape(profile.format_markdown)
                    
                    agent_config = profile.to_agent_dict()
                    
                    agent_instance = AutomatedTrendsAgent(agent_config)
                    initialized_agents.append(agent_instance)
                    
                    user_status = "real (bd)" if agent_data.get('userId') else "fallback"
                    print(f"Agente inicializado: ID {agent_config['id']} - {agent_config['name']} (UserId: {agent_user_id} - {user_status})")
                    
                except Exception as e:
                    print(f"Error inicializando agente {agent_data.get('id', 'unknown')}: {str(e)}")
                    continue
            
            print(f"Total de agentes inicializados: {len(initialized_agents)}")
            return initialized_agents
            
        except Exception as e:
            print(f"Error general inicializando agentes: {str(e)}")
            return []

    def get_trending_topics(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Obtiene los temas de tendencia actuales con sistema de caché optimizado"""
        cache_key = "trending_topics_AR"
        current_time = datetime.now()
        
        if not force_refresh and cache_key in self._trends_cache:
            cached_data = self._trends_cache[cache_key]
            cache_time = datetime.fromisoformat(cached_data['cache_timestamp'])
            
            if current_time - cache_time < timedelta(minutes=self._cache_timeout_minutes):
                print(f"Usando caché de tendencias (válido por {self._cache_timeout_minutes} min)")
                print(f"   Caché creado: {cache_time.strftime('%H:%M:%S')}")
                print(f"   Tiempo actual: {current_time.strftime('%H:%M:%S')}")
                return cached_data['data']
        
        print("Realizando llamada a SerpAPI para obtener tendencias...")
        trends_data = self.trends_api.get_trending_searches_by_category(
            geo="AR", 
            hours=24,
            language="es-419",
            count=16
        )
        
        if trends_data.get("status") == "success":
            self._trends_cache[cache_key] = {
                'data': trends_data,
                'cache_timestamp': current_time.isoformat()
            }
            print(f"Tendencias guardadas en caché hasta: {(current_time + timedelta(minutes=self._cache_timeout_minutes)).strftime('%H:%M:%S')}")
        
        return trends_data

    def _enrich_search_inputs(
        self,
        search_results: Dict[str, Any],
        selected_trend: str,
        trends_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Inyecta contexto relacionado y cotizaciones al paquete de contexto editorial."""
        if not isinstance(search_results, dict):
            search_results = {}

        geo = "AR"
        if isinstance(trends_data, dict):
            geo = trends_data.get("geo", "AR") or "AR"

        try:
            related_context = self.trends_api.get_related_trend_context(
                query=selected_trend,
                geo=geo,
                language="es-419",
            )
        except Exception as exc:
            related_context = {
                "status": "error",
                "message": str(exc),
                "query": selected_trend,
                "related_queries": [],
                "related_topics": [],
            }

        market_data = get_market_data_snapshot()
        links_context = get_recent_finguru_articles(limit=5)
        internal_links = links_context.get("articles", []) if isinstance(links_context, dict) else []

        search_results["related_context"] = related_context
        search_results["market_data"] = market_data
        search_results["internal_links"] = internal_links
        return search_results

    def publish_article(self, article_data: Dict[str, Any], trend_title: str, search_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """Publica el artículo en fin.guru con imagen descargada"""
        try:
            cover_image_data = None
            image_source = "none"
            search_attempts = []
        
            search_queries = []
            
            if isinstance(search_results, dict) and "top_stories" in search_results:
                top_stories = search_results["top_stories"]
                if isinstance(top_stories, list) and top_stories:
                    for story in top_stories[:2]: 
                        if isinstance(story, dict):
                            story_title = story.get('title', '')
                            if story_title:
                                search_queries.append(("top_story", story_title))
            
            if isinstance(search_results, dict) and "organic_results" in search_results:
                organic_results = search_results["organic_results"]
                if isinstance(organic_results, list) and organic_results:
                    for result in organic_results[:2]: 
                        if isinstance(result, dict):
                            result_title = result.get('title', '')
                            if result_title:
                                search_queries.append(("organic_result", result_title))
            
            search_queries.append(("trend_title", trend_title))
            
            search_queries.append(("generic_argentina", f"argentina noticias {trend_title.split()[0] if trend_title else 'actualidad'}"))
            search_queries.append(("generic_news", f"noticias argentina tendencias"))
            search_queries.append(("fallback", "argentina noticias actualidad"))
            
            print(f"   Intentando buscar imagen con {len(search_queries)} estrategias diferentes...")
            
            for attempt_num, (source_type, query) in enumerate(search_queries, 1):
                try:
                    print(f"   Intento {attempt_num}/{len(search_queries)}: Buscando con '{query}' ({source_type})")
                    search_attempts.append(f"{attempt_num}. {source_type}: {query[:50]}...")
                    
                    image_url = search_google_images(self, query)
                    if image_url:
                        print(f"   ✅ URL de imagen encontrada: {image_url}")
                        downloaded_data = download_image_from_url(image_url)
                        if downloaded_data:
                            cover_image_data = downloaded_data
                            image_source = f"google_images_from_{source_type}_attempt_{attempt_num}"
                            print(f"   ✅ Imagen descargada exitosamente en intento {attempt_num}")
                            break
                        else:
                            print(f"   ❌ Error descargando imagen en intento {attempt_num}")
                    else:
                        print(f"   ❌ No se encontró URL de imagen en intento {attempt_num}")
                        
                except Exception as e:
                    print(f"   ❌ Error en intento {attempt_num}: {str(e)}")
                    continue
            
            if not cover_image_data:
                print(f"   🚫 CRÍTICO: No se pudo obtener imagen después de {len(search_queries)} intentos")
                print("   📋 Intentos realizados:")
                for attempt in search_attempts:
                    print(f"      {attempt}")
                return {
                    "status": "error", 
                    "message": "CRÍTICO: No se pudo encontrar ninguna imagen válida para el artículo después de múltiples intentos",
                    "search_attempts": search_attempts,
                    "queries_tried": [q[1] for q in search_queries]
                }
            
            print(f"   Fuente de imagen utilizada: {image_source}")
            
            if not cover_image_data or len(cover_image_data) == 0:
                print("   🚫 ERROR CRÍTICO: cover_image_data está vacío justo antes de subir")
                return {
                    "status": "error", 
                    "message": "ERROR CRÍTICO: No hay datos de imagen válidos para subir el artículo"
                }
            
            filename = article_data['fileName']
            print(f"   Creando archivo: {filename} ({len(cover_image_data)} bytes)")
            
            try:
                image_file = io.BytesIO(cover_image_data)
                image_file.name = filename
                
                image_file.seek(0, 2)
                size = image_file.tell() 
                image_file.seek(0)
                
                if size == 0:
                    print("   🚫 ERROR CRÍTICO: El archivo BytesIO está vacío")
                    return {
                        "status": "error", 
                        "message": "ERROR CRÍTICO: El archivo de imagen está vacío"
                    }
                
                print(f"   ✅ Archivo BytesIO creado correctamente: {size} bytes")
                
            except Exception as e:
                print(f"   🚫 ERROR CRÍTICO creando BytesIO: {str(e)}")
                return {
                    "status": "error", 
                    "message": f"ERROR CRÍTICO creando archivo de imagen: {str(e)}"
                }
            
            files = {
                'cover': (filename, image_file, 'image/jpeg')
            }
            if 'cover' not in files or not files['cover']:
                print("   🚫 ERROR CRÍTICO: files['cover'] no está definido correctamente")
                return {
                    "status": "error", 
                    "message": "ERROR CRÍTICO: Estructura de archivos inválida"
                }
            
            data = {
                'title': article_data['title'],
                'excerpt': article_data['excerpt'],
                'content': article_data['content'],
                'category': article_data['category'],
                'tags': article_data['tags'],
                'publishAs': '-1' if not article_data['publishAs'] else str(article_data['publishAs']),
                'userId': str(self.agent_config.get('userId', 5822))
            }

            # Envío opcional de metadata extendida para no romper integraciones actuales.
            send_extended_seo = os.getenv("SEND_SEO_FIELDS_TO_API", "false").strip().lower() in {
                "1", "true", "yes", "y", "on"
            }
            if send_extended_seo:
                seo_metadata = article_data.get("seo_metadata", {})
                if isinstance(seo_metadata, dict):
                    if seo_metadata.get("slug"):
                        data["slug"] = str(seo_metadata.get("slug"))
                    if seo_metadata.get("meta_description"):
                        data["metaDescription"] = str(seo_metadata.get("meta_description"))
                    if seo_metadata.get("image_alt_text"):
                        data["imageAltText"] = str(seo_metadata.get("image_alt_text"))

                internal_links = article_data.get("internal_links", [])
                if isinstance(internal_links, list) and internal_links:
                    data["internalLinks"] = json.dumps(internal_links, ensure_ascii=False)
            
            print(f"   - Enviando datos: {data}")
            print(f"   - Con archivo: {filename}")
            print(f"   - Sin headers manuales (requests genera automáticamente)")
            
            response = requests.post(
                self.api_endpoint,
                files=files,
                data=data,
            )
            
            print(f"   - Response status: {response.status_code}")
            print(f"   - Response headers: {dict(response.headers)}")
            print(f"   - Response text: {response.text}")
            
            if response.status_code == 200:
                response_text = response.text.lower()
                if 'sin imagen' in response_text or 'no image' in response_text or 'missing image' in response_text:
                    print("   🚫 ADVERTENCIA: La respuesta del servidor sugiere problema con la imagen")
                    print(f"   📝 Respuesta completa: {response.text}")
                    return {
                        "status": "error", 
                        "message": f"El servidor indica problema con la imagen: {response.text}"
                    }
                
                print("   ✅ Artículo publicado exitosamente CON imagen")
                return {"status": "success", "message": "Artículo publicado exitosamente CON imagen validada"}
            else:
                print(f"   ❌ Error del servidor: {response.status_code}")
                return {"status": "error", "message": f"Error {response.status_code}: {response.text}"}
                
        except Exception as e:
            error_detail = traceback.format_exc()
            print(f"   Error completo: {error_detail}")
            return {"status": "error", "message": str(e)}

    def run_automated_process(self, topic_position: int = None) -> Dict[str, Any]:
        """Ejecuta el proceso completo automatizado"""
        try:
            print(f"[{datetime.now()}] Iniciando proceso automatizado de tendencias...")
            
            print("1. Obteniendo tendencias...")
            trends_data = self.get_trending_topics()
            
            if trends_data.get("status") != "success" or not trends_data.get("trending_topics"):
                return {"status": "error", "message": "No se pudieron obtener tendencias"}
            
            if topic_position is None:
                print("2. Permitiendo que ChatGPT seleccione la tendencia más relevante...")
                user_id = self.agent_config.get('userId', 5822)
                selection_result = self.select_trending_topic(trends_data, user_id)
                
                if selection_result.get("status") == "no_suitable_topic":
                    print(f"   🚫 Agente NO creará artículo - No hay temas adecuados")
                    return {
                        "status": "skipped",
                        "agent_name": self.agent_name,
                        "agent_id": self.agent_id,
                        "message": "Agente omitido - No se encontraron temas que cumplan los criterios de calidad",
                        "reason": selection_result.get("reason", ""),
                        "timestamp": datetime.now().isoformat()
                    }
                
                if selection_result.get("status") != "success":
                    return {"status": "error", "message": "No se pudo seleccionar tendencia"}
                
                topic_position = selection_result["selected_position"]
                selected_trend = selection_result["selected_title"]
                selection_reason = selection_result["selected_reason"]
                
                print(f"   ChatGPT eligió posición #{topic_position}: {selected_trend}")
                print(f"   Razón: {selection_reason}")
            else:
                print(f"2. Usando tendencia en posición manual #{topic_position}...")
                selected_trend = _extract_trend_title(trends_data, topic_position)
                if not selected_trend:
                    return {"status": "error", "message": f"No se pudo extraer título de la tendencia en posición {topic_position}"}
                print(f"   Tendencia seleccionada: {selected_trend}")
            
            print("3. Buscando información adicional...")
            search_results = search_google_news(self, selected_trend)
            search_results = self._enrich_search_inputs(search_results, selected_trend, trends_data)
            
            print("4. Creando prompt...")
            prompt = create_prompt(self, trends_data, search_results, selected_trend, topic_position)
            
            print("5. Generando artículo...")
            article_content = generate_article_content(self, prompt)
            
            if not article_content:
                return {"status": "error", "message": "No se pudo generar contenido"}
            
            # NUEVO: Validar profundidad del artículo
            print("5.5. Validando profundidad del análisis...")
            depth_validation = _validate_article_depth(article_content)
            
            if not depth_validation['is_valid']:
                print(f"   ⚠️  RECHAZO: Artículo no tiene suficiente profundidad")
                print(f"   📊 Puntuación: {depth_validation['depth_score']:.0f}/100")
                for issue in depth_validation['issues']:
                    print(f"      - {issue}")
                return {
                    "status": "skipped",
                    "message": "Artículo rechazado por falta de profundidad",
                    "reason": " | ".join(depth_validation['issues']),
                    "depth_score": depth_validation['depth_score']
                }
            
            print(f"   ✅ Profundidad validada: {depth_validation['depth_score']:.0f}/100")
            
            print("6. Procesando datos del artículo...")
            article_data = process_article_data(
                article_content,
                selected_trend=selected_trend,
                search_results=search_results,
            )
            
            print("7. Publicando artículo...")
            publish_result = self.publish_article(article_data, selected_trend, search_results)
            
            print(f"[{datetime.now()}] Proceso completado!")
            return {
                "status": "success",
                "trend_used": selected_trend,
                "article_title": article_data["title"],
                "publish_result": publish_result,
                "timestamp": datetime.now().isoformat()
            }            
        except Exception as e:
            error_msg = f"Error en proceso automatizado: {str(e)}"
            print(error_msg)
            return {"status": "error", "message": error_msg}
    
    def run_multi_agent_process(self, topic_position: int = None) -> Dict[str, Any]:
        """Ejecuta múltiples agentes en paralelo usando sus configuraciones únicas"""
        try:
            print(f"[{datetime.now()}] Iniciando proceso multi-agente...")
            
            self._selected_trends_session.clear()
            self._selected_positions_session.clear()
            print("🔄 Cache de sesión limpiado - tendencias frescas para todos los agentes")
            
            print("Obteniendo tendencias una sola vez para todos los agentes...")
            shared_trends_data = self.get_trending_topics()
            
            if shared_trends_data.get("status") != "success" or not shared_trends_data.get("trending_topics"):
                return {"status": "error", "message": "No se pudieron obtener tendencias compartidas"}
            
            print(f"Tendencias obtenidas exitosamente. Total: {len(shared_trends_data.get('trending_topics', []))}")
            
            agents = self.initialize_agents()
            
            if not agents:
                return {"status": "error", "message": "No se pudieron inicializar agentes"}
            
            print(f"Ejecutando proceso con {len(agents)} agentes...")
            
            all_results = []
            
            for i, agent in enumerate(agents):
                try:
                    print(f"\n{'='*50}")
                    print(f"Ejecutando Agente {i+1}/{len(agents)}")
                    print(f"   ID: {agent.agent_id}")
                    print(f"   Nombre: {agent.agent_name}")
                    print(f"   Tendencias ya usadas: {len(self._selected_trends_session)}")
                    if self._selected_trends_session:
                        print(f"   Posiciones usadas: {sorted(list(self._selected_positions_session))}")
                    print(f"{ '='*50}")
                    
                    result = agent.run_automated_process_with_shared_trends(shared_trends_data, topic_position)
                    
                    if result.get("status") == "success":
                        result["agent_info"] = {
                            "agent_id": agent.agent_id,
                            "agent_name": agent.agent_name,
                            "personality": agent.personality,
                            "trending": agent.trending_prompt,
                            "writing_style": agent.writing_style,
                            "tone": agent.tone,
                            "target_audience": agent.target_audience,
                            "preferred_categories": agent.preferred_categories,
                            "forbidden_topics": agent.forbidden_topics,
                            "temperature": agent.temperature,
                            "max_tokens": agent.max_tokens
                        }
                    
                    all_results.append(result)
                    
                    print(f"Agente {agent.agent_name} completado: {result.get('status')}")
                    
                except Exception as e:
                    print(f"Error ejecutando agente {agent.agent_name}: {str(e)}")
                    all_results.append({
                        "status": "error",
                        "message": str(e),
                        "agent_info": {
                            "agent_id": agent.agent_id,
                            "agent_name": agent.agent_name
                        }
                    })
            
            successful_agents = [r for r in all_results if r.get("status") == "success"]
            failed_agents = [r for r in all_results if r.get("status") == "error"]
            skipped_agents = [r for r in all_results if r.get("status") == "skipped"]
            
            print(f"\nRESUMEN MULTI-AGENTE:")
            print(f"   ✅ Exitosos: {len(successful_agents)}")
            print(f"   ❌ Fallidos: {len(failed_agents)}")
            print(f"   🚫 Omitidos (sin temas adecuados): {len(skipped_agents)}")
            print(f"   📊 Total procesados: {len(all_results)}")
            print(f"   🔄 Total tendencias únicas usadas: {len(self._selected_trends_session)}")
            
            if self._selected_trends_session:
                print(f"   📋 Tendencias seleccionadas: {list(self._selected_trends_session)}")
                
            if skipped_agents:
                print(f"   🚫 Agentes omitidos:")
                for skipped in skipped_agents:
                    agent_name = skipped.get("agent_name", "unknown")
                    reason = skipped.get("reason", "No especificado")
                    print(f"      - {agent_name}: {reason[:100]}...")
            
            return {
                "status": "success",
                "message": f"Proceso multi-agente completado: {len(successful_agents)} exitosos, {len(skipped_agents)} omitidos, {len(failed_agents)} fallidos",
                "results": all_results,
                "summary": {
                    "total_agents": len(all_results),
                    "successful": len(successful_agents),
                    "failed": len(failed_agents),
                    "skipped": len(skipped_agents),
                    "unique_trends_used": len(self._selected_trends_session),
                    "trends_selected": list(self._selected_trends_session)
                }
            }
            
        except Exception as e:
            print(f"Error general en proceso multi-agente: {str(e)}")
            return {
                "status": "error", 
                "message": str(e),
                "results": [],
                "summary": {"total_agents": 0, "successful": 0, "failed": 0}
            }
    
    @classmethod
    def clear_trends_cache(cls):
        cls._trends_cache.clear()
        print("Caché de tendencias limpiado manualmente")
    
    @classmethod
    def clear_session_cache(cls):
        cls._selected_trends_session.clear()
        cls._selected_positions_session.clear()
        print("🔄 Caché de sesión limpiado - tendencias ya seleccionadas reiniciadas")
    
    @classmethod
    def get_cache_status(cls) -> Dict[str, Any]:
        cache_key = "trending_topics_AR"
        current_time = datetime.now()
        
        if cache_key not in cls._trends_cache:
            return {
                "status": "empty",
                "message": "No hay datos en caché"
            }
        
        cached_data = cls._trends_cache[cache_key]
        cache_time = datetime.fromisoformat(cached_data['cache_timestamp'])
        time_diff = current_time - cache_time
        remaining_time = timedelta(minutes=cls._cache_timeout_minutes) - time_diff
        
        is_valid = time_diff < timedelta(minutes=cls._cache_timeout_minutes)
        
        return {
            "status": "valid" if is_valid else "expired",
            "cache_created": cache_time.strftime('%Y-%m-%d %H:%M:%S'),
            "current_time": current_time.strftime('%Y-%m-%d %H:%M:%S'),
            "time_since_cache": str(time_diff).split('.')[0],
            "remaining_time": str(remaining_time).split('.')[0] if is_valid else "0:00:00",
            "trends_count": len(cached_data['data'].get('trending_topics', []))
        }

    def select_trending_topic(self, trends_data: Dict[str, Any], user_id: int = None) -> Dict[str, Any]:
        """Permite que ChatGPT seleccione la tendencia más relevante evitando repetir temas de TODOS los agentes"""
        try:
            trends_data = _validate_and_parse_data(trends_data, "trends_data")
            
            if user_id is None:
                user_id = self.agent_config.get('userId', 5822)
            
            all_recent_articles = get_all_agents_recent_articles(self, limit_per_agent=2)
            recent_articles_text = ""
            
            if all_recent_articles.get("status") == "success" and all_recent_articles.get("articles"):
                recent_articles_text = "\nARTÍCULOS RECIENTES DE TODOS LOS AGENTES (para evitar repetir temas):\n"
                recent_articles_text += f"🔍 Total: {all_recent_articles.get('total', 0)} artículos de {all_recent_articles.get('agents_processed', 0)} agentes\n\n"
                
                for i, article in enumerate(all_recent_articles["articles"][:15], 1):
                    title = article.get('title', 'Sin título')
                    excerpt = article.get('excerpt', 'Sin descripción')
                    category = article.get('category', 'Sin categoría')
                    agent_name = article.get('agent_name', 'Agente desconocido')
                    
                    if len(excerpt) > 100:
                        excerpt = excerpt[:97] + "..."
                    
                    recent_articles_text += f"{i}. 📰 {title}\n"
                    recent_articles_text += f"   👤 Agente: {agent_name}\n"
                    recent_articles_text += f"   📝 {excerpt}\n"
                    recent_articles_text += f"   🏷️ Categoría: {category}\n"
                    recent_articles_text += "\n"
                
                if all_recent_articles.get('total', 0) > 15:
                    remaining = all_recent_articles.get('total', 0) - 15
                    recent_articles_text += f"... y {remaining} artículos más de otros agentes\n\n"
                
                recent_articles_text += "🚫 IMPORTANTE: EVITA ELEGIR TENDENCIAS que sean muy similares en CONTENIDO ESPECÍFICO a estos artículos recientes.\n"
                recent_articles_text += "✅ Puedes elegir la MISMA CATEGORÍA (deportes, política, etc.) pero con un TEMA DIFERENTE.\n"
                recent_articles_text += "💡 Ejemplo: Si hay un artículo sobre 'Messi gana Balón de Oro', puedes escribir sobre 'River vs Boca' (ambos deportes, pero temas diferentes).\n"
                recent_articles_text += "🎯 Solo evita temas que hablen exactamente del mismo evento, persona o noticia específica.\n"
            else:
                recent_articles_text = "\n✨ (No se encontraron artículos recientes de ningún agente - primera ejecución del sistema)\n"
            
            already_selected_text = ""
            if self._selected_trends_session:
                already_selected_text = "\nTENDENCIAS YA SELECCIONADAS EN ESTA SESIÓN (NO ELEGIR ESTAS):\n"
                for i, (pos, trend) in enumerate(zip(self._selected_positions_session, self._selected_trends_session), 1):
                    already_selected_text += f"  ❌ Posición {pos}: {trend}\n"
                already_selected_text += "\nEVITA ESTAS TENDENCIAS COMPLETAMENTE - Ya fueron elegidas por otros agentes en esta misma ejecución.\n"
            
            trends_text = ""
            trending_topics = trends_data.get("trending_topics", [])
            if isinstance(trending_topics, list) and trending_topics:
                for i, topic in enumerate(trending_topics, 1):
                    title = ""
                    categories_text = ""
                    search_volume = ""
                    
                    if isinstance(topic, dict):
                        title = topic.get('title', '')
                        if isinstance(title, dict):
                            title = title.get('query', str(title))
                        
                        categories = topic.get('categories', [])
                        if isinstance(categories, list) and categories:
                            category_names = []
                            for cat in categories:
                                if isinstance(cat, dict):
                                    cat_name = cat.get('name', '')
                                    if cat_name:
                                        category_names.append(cat_name)
                                elif isinstance(cat, str):
                                    category_names.append(cat)
                            
                            if category_names:
                                categories_text = f" [Categorías: {', '.join(category_names)} ]"
                        
                        volume = topic.get('search_volume')
                        if volume:
                            search_volume = f" (Vol: {volume:,})"
                            
                    elif isinstance(topic, str):
                        title = topic
                    
                    if title:
                        if i in self._selected_positions_session or title in self._selected_trends_session:
                            trends_text += f"{i}. ❌ {title}{categories_text}{search_volume} - [YA SELECCIONADA - NO USAR]\n"
                        else:
                            trends_text += f"{i}. {title}{categories_text}{search_volume}\n"
            
            selection_prompt = f"""Eres un editor de noticias especializado en Argentina. Te proporciono las 16 tendencias actuales más populares en Argentina.

TENDENCIAS ACTUALES (últimas 24h):
{trends_text}
{recent_articles_text}
{already_selected_text}

🎯 OBJETIVO: ELEGIR UNA SOLA tendencia que sea MÁS RELEVANTE e INTERESANTE para el público argentino.

💰 PRIORIDAD FIN.GURU (OBLIGATORIA):
- Prioriza tendencias de economía, mercados, dólar, inflación, tasas, bancos, deuda, inversión y política fiscal.
- Si una tendencia es masiva pero no financiera (farándula, reality, chimentos), debe descartarse.

📋 CRITERIOS DE SELECCIÓN:
{self.trending_prompt}

👤 PERFIL DEL AGENTE (RESPETAR):
- Audiencia objetivo: {self.target_audience}
- Estilo: {self.writing_style}
- Tono: {self.tone}
- Categorías preferidas: {', '.join(self.preferred_categories) if self.preferred_categories else 'Sin preferencias explícitas'}
- Temas prohibidos: {', '.join(self.forbidden_topics) if self.forbidden_topics else 'Sin temas prohibidos explícitos'}

🚫 REGLAS ESTRICTAS - NO VIOLAR:
- ❌ PROHIBIDO: NO elijas tendencias marcadas con "❌ [YA SELECCIONADA - NO USAR]"
- ❌ PROHIBIDO: NO elijas tendencias triviales (efemérides, "noches temáticas", paros sin análisis, etc.)
- ❌ PROHIBIDO: NO elijas tendencias sobre el MISMO evento/persona/noticia específica de los artículos recientes
- ❌ PROHIBIDO: NO elijas tendencias alineadas con temas prohibidos del perfil
- ✅ PERMITIDO: Puedes elegir la MISMA CATEGORÍA pero con tema específico diferente
- ✅ OBLIGATORIO: SOLO elige entre las tendencias SIN marca ❌
- 🔍 VALIDACIÓN: Si NINGUNA tendencia cumple con criterios, responde "NO_SUITABLE_TOPIC"

🔍 ANÁLISIS REQUERIDO:
1. RECHAZA: Temas triviales/contextuales (efemérides, "noche de X", paros sin contexto profundo)
2. Revisa cada tendencia disponible (sin ❌)
3. Compara CONTENIDO ESPECÍFICO (no categorías) con artículos recientes 
4. Evalúa si habla del mismo evento/persona/noticia específica
5. Elige tendencia con contenido diferente y valor investigativo
6. Si NO encuentras tendencia adecuada, responde "NO_SUITABLE_TOPIC"

FORMATO DE RESPUESTA OBLIGATORIO:
POSICIÓN: [número del 1 al 16 O "NO_SUITABLE_TOPIC"]
TÍTULO: [título exacto de la tendencia elegida O "NINGUNO"]
RAZÓN: [explicación detallada de por qué la elegiste y cómo el CONTENIDO ESPECÍFICO es diferente a los artículos recientes, O por qué ninguna tendencia es adecuada]

Ejemplo exitoso:
POSICIÓN: 3
TÍTULO: Dólar blue Argentina
RAZÓN: Aunque hay artículos de economía recientes, este tema específico sobre el dólar blue es diferente del contenido ya publicado sobre inflación

Ejemplo sin tema adecuado:
POSICIÓN: NO_SUITABLE_TOPIC
TÍTULO: NINGUNO
RAZÓN: Las tendencias disponibles hablan exactamente de los mismos eventos específicos ya cubiertos en artículos recientes"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un editor experto en seleccionar noticias relevantes para Argentina. Evita repetir temas ya cubiertos y NUNCA elijas tendencias marcadas como YA SELECCIONADAS. Responde exactamente en el formato solicitado."}, 
                    {"role": "user", "content": selection_prompt}
                ],
                max_tokens=150,  
                temperature=0.3 
            )
            
            selection_response = response.choices[0].message.content.strip()
            print(f"   Respuesta de selección: {selection_response}")
            
            lines = selection_response.split('\n')
            selected_position = None
            selected_title = None
            selected_reason = None
            
            for line in lines:
                line = line.strip()
                if line.startswith('POSICIÓN:'):
                    position_text = line.replace('POSICIÓN:', '').strip()
                    if position_text == "NO_SUITABLE_TOPIC":
                        selected_position = "NO_SUITABLE_TOPIC"
                    else:
                        try:
                            selected_position = int(position_text)
                        except ValueError:
                            pass
                elif line.startswith('TÍTULO:'):
                    selected_title = line.replace('TÍTULO:', '').strip()
                    if selected_title == "NINGUNO":
                        selected_title = "NO_SUITABLE_TOPIC"
                elif line.startswith('RAZÓN:'):
                    selected_reason = line.replace('RAZÓN:', '').strip()
            
            if selected_position == "NO_SUITABLE_TOPIC" or selected_title == "NO_SUITABLE_TOPIC":
                print(f"   🚫 ChatGPT determinó que NO hay temas adecuados")
                print(f"   Razón: {selected_reason}")
                return {
                    "status": "no_suitable_topic",
                    "message": "No se encontró ningún tema que cumpla con los criterios de calidad",
                    "reason": selected_reason
                }

            selected_categories = []
            if isinstance(selected_position, int):
                trending_topics = trends_data.get("trending_topics", [])
                if isinstance(trending_topics, list) and 1 <= selected_position <= len(trending_topics):
                    selected_topic_payload = trending_topics[selected_position - 1]
                    if isinstance(selected_topic_payload, dict):
                        selected_categories = selected_topic_payload.get("categories", [])

            financial_relevance = self.pipeline_v2.policy_engine.evaluate_financial_relevance(
                selected_title,
                selected_categories,
            )

            if not financial_relevance.get("allowed"):
                print(f"   🚫 Tema rechazado por baja relevancia financiera: {selected_title}")
                return {
                    "status": "no_suitable_topic",
                    "message": "Tema fuera de foco financiero para FinGuru",
                    "reason": (
                        f"Score financiero insuficiente ({financial_relevance.get('score', 0)}) "
                        f"| hard_block_hits={financial_relevance.get('hard_block_hits', [])}"
                    ),
                }

            forbidden_hits = []
            if selected_title:
                selected_title_lc = selected_title.lower()
                forbidden_hits = [
                    topic
                    for topic in self.forbidden_topics
                    if isinstance(topic, str) and topic.strip() and topic.strip().lower() in selected_title_lc
                ]

            if forbidden_hits:
                print(f"   🚫 Tema rechazado por forbidden_topics: {forbidden_hits}")
                return {
                    "status": "no_suitable_topic",
                    "message": "Tema rechazado por restricciones del perfil del agente",
                    "reason": f"Coincide con forbidden_topics: {', '.join(forbidden_hits)}"
                }
            
            if selected_position in self._selected_positions_session or selected_title in self._selected_trends_session:
                print(f"   ⚠️  ADVERTENCIA: ChatGPT eligió una tendencia ya seleccionada. Buscando alternativa...")
                
                trending_topics = trends_data.get("trending_topics", [])
                for i, topic in enumerate(trending_topics, 1):
                    if i not in self._selected_positions_session:
                        title = ""
                        if isinstance(topic, dict):
                            title = topic.get('title', '')
                            if isinstance(title, dict):
                                title = title.get('query', str(title))
                        elif isinstance(topic, str):
                            title = topic
                        
                        if title and title not in self._selected_trends_session:
                            all_articles_list = all_recent_articles.get("articles", [])
                            if not _is_topic_similar_to_recent_articles(title, all_articles_list):
                                selected_position = i
                                selected_title = title
                                selected_reason = "Selección automática para evitar duplicados"
                                print(f"   ✅ Alternativa encontrada: Posición #{i} - {title}")
                                break
                else:
                    return {"status": "error", "message": "No hay tendencias disponibles que no se relacionen con artículos recientes de todos los agentes"}
            
            if selected_title and all_recent_articles.get("articles"):
                all_articles_list = all_recent_articles.get("articles", [])
                if _is_topic_similar_to_recent_articles(selected_title, all_articles_list):
                    print(f"   ⚠️  ADVERTENCIA: La tendencia '{selected_title}' es muy similar a artículos recientes de todos los agentes")
                    
                    trending_topics = trends_data.get("trending_topics", [])
                    for i, topic in enumerate(trending_topics, 1):
                        if i not in self._selected_positions_session:
                            title = _extract_trend_title(trends_data, i)
                            if title and title not in self._selected_trends_session:
                                if not _is_topic_similar_to_recent_articles(title, all_articles_list):
                                    selected_position = i
                                    selected_title = title
                                    selected_reason = "Selección automática para evitar repetición temática"
                                    print(f"   ✅ Alternativa sin similitud encontrada: Posición #{i} - {title}")
                                    break
                    else:
                        print(f"   ⚠️  No se encontró alternativa, procediendo con la selección original (puede haber similitud con todos los agentes)")
            
            if selected_position and selected_title:
                # NUEVO: Verificar que no sea un tema trivial/contextual
                if _is_topic_trivial_or_contextual(selected_title):
                    print(f"   ⚠️  RECHAZO: Tema '{selected_title}' es trivial/contextual")
                    return {
                        "status": "no_suitable_topic",
                        "message": "Tema seleccionado es trivial o contextual sin valor investigativo",
                        "reason": "El tema seleccionado no cumple estándares de calidad editorial (tema superficial, sin análisis profundo)"
                    }
                
                self._selected_positions_session.add(selected_position)
                self._selected_trends_session.add(selected_title)
                
                print(f"   ChatGPT eligió: Posición #{selected_position} - {selected_title}")
                print(f"   Razón: {selected_reason}")
                print(f"   📝 Registrado para evitar duplicados futuros")
                
                return {
                    "status": "success",
                    "selected_position": selected_position,
                    "selected_title": selected_title,
                    "selected_reason": selected_reason
                }
            else:
                print(f"   No se pudo parsear la respuesta de selección")
                return {"status": "error", "message": "No se pudo parsear la selección"}
                
        except Exception as e:
            print(f"   Error en selección de tendencia: {str(e)}")
            return {"status": "error", "message": str(e)}

    def run_automated_process_with_shared_trends(self, shared_trends_data: Dict[str, Any], topic_position: int = None) -> Dict[str, Any]:
        """Ejecuta el proceso completo automatizado usando tendencias compartidas (OPTIMIZADO)"""
        try:
            print(f"[{datetime.now()}] Iniciando proceso automatizado con tendencias compartidas...")
            
            print("1. Usando tendencias compartidas (SIN llamada API adicional)...")
            trends_data = shared_trends_data
            
            if topic_position is None:
                print("2. Permitiendo que ChatGPT seleccione la tendencia más relevante...")
                user_id = self.agent_config.get('userId', 5822)
                selection_result = self.select_trending_topic(trends_data, user_id)
                
                if selection_result.get("status") == "no_suitable_topic":
                    print(f"   🚫 Agente '{self.agent_name}' NO creará artículo - No hay temas adecuados")
                    return {
                        "status": "skipped",
                        "agent_name": self.agent_name,
                        "agent_id": self.agent_id,
                        "message": "Agente omitido - No se encontraron temas que cumplan los criterios de calidad",
                        "reason": selection_result.get("reason", ""),
                        "timestamp": datetime.now().isoformat()
                    }
                
                if selection_result.get("status") != "success":
                    return {"status": "error", "message": "No se pudo seleccionar tendencia"}
                
                topic_position = selection_result["selected_position"]
                selected_trend = selection_result["selected_title"]
                selection_reason = selection_result["selected_reason"]
                
                print(f"   ChatGPT eligió posición #{topic_position}: {selected_trend}")
                print(f"   Razón: {selection_reason}")
            else:
                print(f"2. Usando tendencia en posición manual #{topic_position}...")
                selected_trend = _extract_trend_title(trends_data, topic_position)
                if not selected_trend:
                    return {"status": "error", "message": f"No se pudo extraer título de la tendencia en posición {topic_position}"}
                print(f"   Tendencia seleccionada: {selected_trend}")
            
            print("3. Buscando información adicional...")
            search_results = search_google_news(self, selected_trend)
            search_results = self._enrich_search_inputs(search_results, selected_trend, trends_data)
            
            print("4. Creando prompt...")
            prompt = create_prompt(self, trends_data, search_results, selected_trend, topic_position)
            
            print("5. Generando artículo...")
            article_content = generate_article_content(self, prompt)
            
            if not article_content:
                return {"status": "error", "message": "No se pudo generar contenido"}
            
            # NUEVO: Validar profundidad del artículo
            print("5.5. Validando profundidad del análisis...")
            depth_validation = _validate_article_depth(article_content)
            
            if not depth_validation['is_valid']:
                print(f"   ⚠️  RECHAZO: Artículo no tiene suficiente profundidad")
                print(f"   📊 Puntuación: {depth_validation['depth_score']:.0f}/100")
                for issue in depth_validation['issues']:
                    print(f"      - {issue}")
                return {
                    "status": "skipped",
                    "agent_name": self.agent_name,
                    "agent_id": self.agent_id,
                    "message": "Artículo rechazado por falta de profundidad analítica",
                    "reason": " | ".join(depth_validation['issues']),
                    "depth_score": depth_validation['depth_score'],
                    "timestamp": datetime.now().isoformat()
                }
            
            print(f"   ✅ Profundidad validada: {depth_validation['depth_score']:.0f}/100")
            
            print("6. Procesando datos del artículo...")
            article_data = process_article_data(
                article_content,
                selected_trend=selected_trend,
                search_results=search_results,
            )
            
            print("7. Publicando artículo...")
            publish_result = self.publish_article(article_data, selected_trend, search_results)
            
            print(f"[{datetime.now()}] Proceso completado!")
            return {
                "status": "success",
                "trend_used": selected_trend,
                "article_title": article_data["title"],
                "publish_result": publish_result,
                "timestamp": datetime.now().isoformat(),
                "optimization_note": "Usado tendencias compartidas - SIN llamada API adicional"
            }
            
        except Exception as e:
            error_msg = f"Error en proceso automatizado con tendencias compartidas: {str(e)}"
            print(error_msg)
            return {"status": "error", "message": error_msg}

    def run_automated_process_with_shared_trends_v2(
        self,
        shared_trends_data: Dict[str, Any],
        topic_position: int = None,
        dry_run: bool = False,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Ejecuta pipeline v2 desacoplado con respuesta estructurada y trazabilidad."""
        return self.pipeline_v2.execute(
            agent=self,
            trends_data=shared_trends_data,
            topic_position=topic_position,
            dry_run=dry_run,
            correlation_id=correlation_id,
        )

    def run_multi_agent_process_v2(
        self,
        topic_position: int = None,
        dry_run: bool = False,
        request_correlation_id: Optional[str] = None,
        agent_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Ejecuta múltiples agentes bajo el contrato v2 con trazabilidad por ejecución."""
        try:
            request_correlation_id = request_correlation_id or str(uuid.uuid4())
            print(f"[{datetime.now()}] Iniciando proceso multi-agente v2 (correlation_id={request_correlation_id})...")

            self._selected_trends_session.clear()
            self._selected_positions_session.clear()

            requested_agent_ids: Optional[List[int]] = None
            if agent_ids is not None:
                seen = set()
                normalized: List[int] = []
                for aid in agent_ids:
                    if aid not in seen:
                        seen.add(aid)
                        normalized.append(aid)
                if not normalized:
                    return {
                        "status": "error",
                        "contract_version": "v2",
                        "correlation_id": request_correlation_id,
                        "message": "agent_ids no puede ser una lista vacía; omita el campo para ejecutar todos los agentes",
                    }
                requested_agent_ids = normalized

            shared_trends_data = self.get_trending_topics()
            if shared_trends_data.get("status") != "success" or not shared_trends_data.get("trending_topics"):
                return {
                    "status": "error",
                    "contract_version": "v2",
                    "correlation_id": request_correlation_id,
                    "message": "No se pudieron obtener tendencias compartidas",
                }

            agents = self.initialize_agents()
            if not agents:
                return {
                    "status": "error",
                    "contract_version": "v2",
                    "correlation_id": request_correlation_id,
                    "message": "No se pudieron inicializar agentes",
                }

            if requested_agent_ids is not None:
                loaded_ids = {a.agent_id for a in agents if a.agent_id is not None}
                requested_set = set(requested_agent_ids)
                unknown_agent_ids = sorted(requested_set - loaded_ids)
                if unknown_agent_ids:
                    return {
                        "status": "error",
                        "contract_version": "v2",
                        "correlation_id": request_correlation_id,
                        "message": (
                            "Uno o más agent_ids no existen entre los agentes disponibles: "
                            f"{unknown_agent_ids}"
                        ),
                        "unknown_agent_ids": unknown_agent_ids,
                    }

                order = {aid: i for i, aid in enumerate(requested_agent_ids)}
                agents = sorted(
                    [a for a in agents if a.agent_id in requested_set],
                    key=lambda ag: order.get(ag.agent_id, 10**9),
                )
                if not agents:
                    return {
                        "status": "error",
                        "contract_version": "v2",
                        "correlation_id": request_correlation_id,
                        "message": "No hay agentes para ejecutar tras aplicar agent_ids",
                        "unknown_agent_ids": [],
                    }

            results = []
            for agent in agents:
                agent_correlation_id = f"{request_correlation_id}:{agent.agent_id}"
                result = agent.run_automated_process_with_shared_trends_v2(
                    shared_trends_data=shared_trends_data,
                    topic_position=topic_position,
                    dry_run=dry_run,
                    correlation_id=agent_correlation_id,
                )
                results.append(result)

            successful = [r for r in results if r.get("status") == "success"]
            skipped = [r for r in results if r.get("status") == "skipped"]
            failed = [r for r in results if r.get("status") == "error"]

            execution_payload = {
                "topic_position": topic_position,
                "dry_run": dry_run,
                "agents_total": len(results),
                "successful": len(successful),
                "skipped": len(skipped),
                "failed": len(failed),
                "requested_agent_ids": requested_agent_ids,
            }

            return {
                "status": "success",
                "contract_version": "v2",
                "correlation_id": request_correlation_id,
                "timestamp": datetime.now().isoformat(),
                "execution": execution_payload,
                "results": results,
            }
        except Exception as e:
            return {
                "status": "error",
                "contract_version": "v2",
                "correlation_id": request_correlation_id or "unknown",
                "message": f"Error general en proceso multi-agente v2: {str(e)}",
            }

def run_trends_agent(topic_position: int = None):
    agent = AutomatedTrendsAgent()
    return agent.run_automated_process(topic_position)

def run_multi_trends_agents(topic_position: int = None):
    coordinator = AutomatedTrendsAgent()
    return coordinator.run_multi_agent_process(topic_position)


def run_multi_trends_agents_v2(
    topic_position: int = None,
    dry_run: bool = False,
    correlation_id: Optional[str] = None,
    agent_ids: Optional[List[int]] = None,
):
    coordinator = AutomatedTrendsAgent()
    return coordinator.run_multi_agent_process_v2(
        topic_position=topic_position,
        dry_run=dry_run,
        request_correlation_id=correlation_id,
        agent_ids=agent_ids,
    )

def get_available_agents_standalone():
    agent = AutomatedTrendsAgent()
    return get_available_agents(agent)

def get_all_agents_recent_articles_standalone(limit_per_agent: int = 2):
    agent = AutomatedTrendsAgent()
    return get_all_agents_recent_articles(agent, limit_per_agent)

def initialize_agents_from_api():
    agent = AutomatedTrendsAgent()
    return agent.initialize_agents()

def clear_trends_cache_standalone():
    AutomatedTrendsAgent.clear_trends_cache()
    return {"status": "success", "message": "Caché limpiado exitosamente"}

def clear_session_cache_standalone():
    AutomatedTrendsAgent.clear_session_cache()
    return {"status": "success", "message": "Caché de sesión limpiado exitosamente"}

def get_cache_status_standalone():
    return AutomatedTrendsAgent.get_cache_status()

def get_trending_topics_cached():
    agent = AutomatedTrendsAgent()
    return agent.get_trending_topics()
