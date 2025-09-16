import os
import json
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime
from openai import OpenAI
from utils.trends_functions import TrendsAPI
from load_env import load_env_files
import html
import re
import string
import random
import io
import traceback

load_env_files()

class AutomatedTrendsAgent:
    # Cache estático para compartir entre instancias
    _trends_cache = {}
    _cache_timeout_minutes = 20
    
    # Cache estático para rastrear tendencias seleccionadas en la sesión multi-agente actual
    _selected_trends_session = set()
    _selected_positions_session = set()
    
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
        
    def _is_topic_similar_to_recent_articles(self, topic_title: str, recent_articles: List[Dict]) -> bool:
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
            print(f"Error obteniendo artículos del agente: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "articles": []
            }

    def get_all_agents_recent_articles(self, limit_per_agent: int = 2) -> Dict[str, Any]:
        """Obtiene los artículos recientes de TODOS los agentes para evitar repetir temas"""
        try:
            print(f"Obteniendo últimos {limit_per_agent} artículos de TODOS los agentes...")
            
            # Primero obtener todos los agentes
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
                'details': [],'total': 0
            }
    
    def initialize_agents(self) -> List['AutomatedTrendsAgent']:
        """Inicializa todos los agentes disponibles con sus configuraciones únicas"""
        try:
            print("Inicializando agentes múltiples...")
            
            agents_response = self.get_available_agents()
            
            if agents_response.get('status') != 'success':
                print(f"Error obteniendo agentes: {agents_response.get('message')}")
                return []
            
            agents_data = agents_response.get('details', [])
            initialized_agents = []
            
            for agent_data in agents_data:
                try:
                    format_markdown = agent_data.get('format_markdown', '')
                    if format_markdown:
                        format_markdown = html.unescape(format_markdown)
                    
                    agent_id = agent_data.get('id')
                    agent_user_id = agent_data.get('userId')
                    
                    if not agent_user_id:
                        print(f"No se encontró userId para el agente {agent_id}, usando ID por defecto")
                        agent_user_id = 5822
                    
                    agent_config = {
                        'id': agent_id,
                        'name': agent_data.get('name'),
                        'personality': agent_data.get('personality', ''),
                        'trending': agent_data.get('trending', ''),
                        'format_markdown': format_markdown,
                        'userId': agent_user_id,
                        'createdAt': agent_data.get('createdAt'),
                        'updatedAt': agent_data.get('updatedAt')
                    }
                    
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
    
    def search_google_news(self, query: str) -> Dict[str, Any]:
        """Busca información adicional sobre el tema en Google usando Serper API"""
        try:
            enhanced_query = f"{query}"
            
            url = "https://google.serper.dev/search"
            
            payload = json.dumps({
                "q": enhanced_query,
                "location": "Argentina",
                "gl": "ar",
                "hl": "es-419",
                "num": 10
            })
            
            headers = {
                'X-API-KEY': self.serper_api_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            
            results = response.json()
            
            converted_results = self._convert_serper_to_serpapi_format(results)
            
            print(f"   Búsqueda realizada con Serper: {enhanced_query}")
            print(f"   Resultados orgánicos encontrados: {len(converted_results.get('organic_results', []))}")
            print(f"   Top stories encontradas: {len(converted_results.get('top_stories', []))}")
            
            if "organic_results" in converted_results:
                print("   Primeros resultados orgánicos:")
                for i, result in enumerate(converted_results["organic_results"][:3]):
                    print(f"      {i+1}. {result.get('title', 'Sin título')}")
            
            if "top_stories" in converted_results:
                print("   Top stories:")
                for i, story in enumerate(converted_results["top_stories"][:3]):
                    print(f"      {i+1}. {story.get('title', 'Sin título')}")
            
            return converted_results
            
        except Exception as e:
            print(f"   Error searching Google with Serper: {str(e)}")
            return {}
    
    def search_google_images(self, query: str) -> str:
        """Busca una imagen relevante usando Serper API con múltiples intentos"""
        try:
            url = "https://google.serper.dev/images"
            
            payload = json.dumps({
                "q": query,
                "location": "Argentina",
                "gl": "ar",
                "hl": "es-419",
                "num": 15
            })
            
            headers = {
                'X-API-KEY': self.serper_api_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            
            results = response.json()
            
            print(f"      Buscando imágenes para: {query[:50]}...")
            
            if "images" in results and len(results["images"]) > 0:
                images_list = results["images"]
                print(f"      {len(images_list)} imágenes encontradas, tomando la primera válida...")
                
                # Intentar con cada imagen EN ORDEN hasta encontrar una válida
                for img_index, image_data in enumerate(images_list):
                    try:
                        image_url = image_data.get("imageUrl")
                        
                        if not image_url:
                            print(f"      ❌ Imagen #{img_index + 1}: Sin URL")
                            continue
                        
                        # Validación básica de URL (más permisiva)
                        if not (image_url.startswith('http://') or image_url.startswith('https://')):
                            print(f"      ❌ Imagen #{img_index + 1}: URL inválida")
                            continue
                        
                        # Verificar extensión - aceptar jpg, png, webp, gif
                        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
                        has_valid_extension = any(image_url.lower().endswith(ext) for ext in valid_extensions)
                        
                        # O verificar indicadores de imagen en la URL
                        image_indicators = ['images', 'img', 'photo', 'pic', 'thumb', 'avatar', 'logo']
                        has_image_indicator = any(indicator in image_url.lower() for indicator in image_indicators)
                        
                        if has_valid_extension or has_image_indicator:
                            title = image_data.get("title", "N/A")
                            source = image_data.get("source", "N/A")
                            
                            print(f"      ✅ PRIMERA imagen válida encontrada (#{img_index + 1}/{len(images_list)}):")
                            print(f"         - Título: {title[:50]}...")
                            print(f"         - Fuente: {source}")
                            print(f"         - URL: {image_url}")
                            print(f"         - Extensión válida: {has_valid_extension}")
                            print(f"         - Indicador válido: {has_image_indicator}")
                            
                            return image_url
                        else:
                            print(f"      ❌ Imagen #{img_index + 1}: No tiene extensión válida ni indicadores de imagen")
                            
                    except Exception as e:
                        print(f"      ❌ Error procesando imagen #{img_index + 1}: {str(e)}")
                        continue
                
                print(f"      ❌ Ninguna de las {len(images_list)} imágenes fue válida")
            else:
                print("      ❌ No se encontraron imágenes en la respuesta")
            
            return ""
            
        except Exception as e:
            print(f"      ❌ Error buscando imágenes con Serper: {str(e)}")
            return ""
    
    def _convert_serper_to_serpapi_format(self, serper_results: Dict[str, Any]) -> Dict[str, Any]:
        """Convierte el formato de Serper al formato esperado por SerpAPI"""
        converted = {
            "organic_results": [],
            "top_stories": []
        }
        
        if "organic" in serper_results and isinstance(serper_results["organic"], list):
            for result in serper_results["organic"]:
                converted_result = {
                    "title": result.get("title", ""),
                    "link": result.get("link", ""),
                    "snippet": result.get("snippet", ""),
                    "position": result.get("position", 0),
                    "date": result.get("date", "")
                }
                converted["organic_results"].append(converted_result)
        
        if "topStories" in serper_results and isinstance(serper_results["topStories"], list):
            for story in serper_results["topStories"]:
                converted_story = {
                    "title": story.get("title", ""),
                    "link": story.get("link", ""),
                    "source": story.get("source", ""),
                    "date": story.get("date", ""),
                    "thumbnail": story.get("imageUrl", "")
                }
                converted["top_stories"].append(converted_story)
        
        return converted
    
    def _is_valid_image_url(self, url: str) -> bool:
        """Verifica si la URL de imagen es válida - VERSIÓN MUY PERMISIVA"""
        if not url or len(url) < 10:
            return False
        
        # URLs claramente inválidas
        blocked_domains = ['data:', 'javascript:', 'blob:', 'chrome-extension:', 'about:', 'file:']
        if any(url.lower().startswith(blocked) for blocked in blocked_domains):
            return False
        
        # Debe ser una URL HTTP/HTTPS válida
        if not (url.lower().startswith('http://') or url.lower().startswith('https://')):
            return False
        
        # NUEVA LÓGICA: Aceptar prácticamente cualquier URL que parezca imagen
        # Extensiones de imagen válidas (muy amplio)
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.svg', '.tiff', '.ico']
        has_valid_extension = any(url.lower().endswith(ext) for ext in valid_extensions)
        
        # Indicadores de imagen en la URL (muy amplio)
        image_indicators = ['images', 'img', 'photo', 'pic', 'thumb', 'avatar', 'logo', 'banner', 
                           'media', 'upload', 'content', 'static', 'assets', 'file']
        has_image_indicator = any(indicator in url.lower() for indicator in image_indicators)
        
        # Dominios de imágenes conocidos (muy amplio)
        image_domains = ['imgur.com', 'flickr.com', 'cloudinary.com', 'amazonaws.com', 'googleusercontent.com', 
                        'fbcdn.net', 'cdninstagram.com', 'pinimg.com', 'wikimedia.org', 'unsplash.com',
                        'pexels.com', 'shutterstock.com', 'getty', 'adobe.com', 'istock']
        has_image_domain = any(domain in url.lower() for domain in image_domains)
        
        # NUEVA LÓGICA: Si tiene extensión válida, indicador O dominio conocido, es válida
        if has_valid_extension or has_image_indicator or has_image_domain:
            return True
        
        # NUEVA LÓGICA: Si no tiene nada obvio pero es una URL corta y simple, probablemente es válida
        if len(url) <= 200 and not any(suspicious in url.lower() for suspicious in ['javascript', 'data', 'void', 'null']):
            return True
        
        # Rechazar URLs muy largas (probablemente no son imágenes directas)
        if len(url) > 500:
            return False
            
        # Por defecto, aceptar (ser muy permisivo)
        return True
    
    def download_image_from_url(self, url: str) -> Optional[bytes]:
        """Descarga una imagen desde una URL con validaciones mejoradas"""
        try:
            print(f"      Descargando imagen desde: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()
            
            # NUEVA LÓGICA: Ser MUCHO más permisivo con el content-type
            content_type = response.headers.get('content-type', '').lower()
            print(f"      📋 Tipo de contenido: {content_type}")
            
            # NO rechazar por content-type, solo informar
            # (Muchas imágenes válidas tienen content-types raros)
            
            image_data = response.content
            
            # NUEVA LÓGICA: Validaciones de tamaño más flexibles
            if len(image_data) < 100:  # Reducir aún más el mínimo
                print(f"      ❌ Imagen muy pequeña: {len(image_data)} bytes")
                return None
                
            if len(image_data) > 15 * 1024 * 1024:  # Aumentar máximo a 15MB
                print(f"      ❌ Imagen muy grande: {len(image_data)} bytes")
                return None
            
            # NUEVA LÓGICA: Siempre aceptar la imagen sin verificación PIL obligatoria
            print(f"      ✅ Imagen descargada exitosamente: {len(image_data)} bytes")
            
            # Intentar validar con PIL si está disponible (pero no es obligatorio)
            try:
                from PIL import Image
                img_obj = Image.open(io.BytesIO(image_data))
                img_obj.verify()
                
                # Si PIL funciona, verificar dimensiones
                width, height = img_obj.size
                if width < 50 or height < 50:  # Reducir mínimo de dimensiones
                    print(f"      ⚠️ Imagen pequeña: {width}x{height} pixels - Pero la aceptamos de todos modos")
                    
                print(f"      ✅ Verificación PIL exitosa: {width}x{height} pixels")
                
            except ImportError:
                print(f"      ℹ️ PIL no disponible - Aceptando imagen sin verificación")
            except Exception as e:
                print(f"      ⚠️ PIL falló: {str(e)} - Pero aceptamos la imagen de todos modos")
            
            return image_data
                
        except requests.exceptions.Timeout:
            print(f"      ❌ Timeout descargando imagen")
            return None
        except requests.exceptions.RequestException as e:
            print(f"      ❌ Error descargando imagen: {str(e)}")
            return None
        except Exception as e:
            print(f"      ❌ Error inesperado descargando imagen: {str(e)}")            
            return None
    
    def create_prompt(self, trends_data: Dict[str, Any], search_results: Dict[str, Any], selected_trend: str, topic_position: int = None) -> str:
        """Crea el prompt para ChatGPT basado en las tendencias y búsquedas"""
        trends_data = self._validate_and_parse_data(trends_data, "trends_data")
        search_results = self._validate_and_parse_data(search_results, "search_results")
        
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
                            categories_text = f" [Categorías: {', '.join(category_names)}]"
                    
                    volume = topic.get('search_volume')
                    if volume:
                        search_volume = f" (Vol: {volume:,})"
                        
                elif isinstance(topic, str):
                    title = topic
                
                if title:
                    trends_text += f"{i}. {title}{categories_text}{search_volume}\n"
        
        additional_info = ""
        
        if isinstance(search_results, dict) and "top_stories" in search_results:
            top_stories = search_results["top_stories"]
            if isinstance(top_stories, list) and top_stories:
                additional_info += "NOTICIAS DESTACADAS:\n"
                for i, story in enumerate(top_stories[:3], 1):
                    if isinstance(story, dict):
                        title = story.get('title', 'Sin título')
                        source = story.get('source', 'Sin fuente')
                        date = story.get('date', 'Sin fecha')
                        additional_info += f"{i}. {title}\n   Fuente: {source} - {date}\n"
                additional_info += "\n"
        
        if isinstance(search_results, dict) and "organic_results" in search_results:
            organic_results = search_results["organic_results"]
            if isinstance(organic_results, list) and organic_results:
                additional_info += "INFORMACIÓN ADICIONAL:\n"
                organic_sorted = []
                for result in organic_results:
                    if isinstance(result, dict):
                        organic_sorted.append(result)
                
                organic_sorted = sorted(organic_sorted, key=lambda x: x.get('position', 999))[:3]
                
                for i, result in enumerate(organic_sorted, 1):
                    title = result.get('title', 'Sin título')
                    snippet = result.get('snippet', 'Sin descripción')
                    position = result.get('position', 'N/A')
                    if len(snippet) > 100:
                        snippet = snippet[:97] + "..."
                    additional_info += f"{i}. [Pos. {position}] {title}\n   {snippet}\n"
        
        personality = self.personality
        trending_instructions = self.trending_prompt
        format_template = self.format_markdown
        
        if format_template and format_template.strip():
            format_template = html.unescape(format_template)
            format_template = format_template.replace('<p>', '\n').replace('</p>', '\n')
            format_template = format_template.replace('<strong>', '**').replace('</strong>', '**')
            format_template = format_template.replace('<h2>', '## ').replace('</h2>', '')
            format_template = format_template.replace('<h3>', '### ').replace('</h3>', '')
            format_template = format_template.replace('<li>', '- ').replace('</li>', '')
            format_template = format_template.strip()
        else:
            format_template = """

## ¿Por qué es tendencia?

Párrafo explicativo con **palabras clave importantes** resaltadas en negrita.

## Contexto y Detalles

Información detallada sobre el tema con **datos relevantes** destacados.

### Puntos Clave

- **Punto importante 1**: Descripción
- **Punto importante 2**: Descripción  
- **Punto importante 3**: Descripción

## Impacto en Argentina

Análisis del impacto local con **cifras** y **fechas** importantes.

## Conclusión

Resumen final con **perspectiva futura** del tema."""

        prompt = f"""{personality}

TENDENCIAS ACTUALES (últimas 24h):
{trends_text}

{additional_info}

CATEGORÍAS DISPONIBLES (debes elegir UNA):
1. "Economía y Finanzas" - Para temas de: economía, dólar, inflación, bancos, inversiones, mercados, empresas, negocios
2. "Tecnología e Innovación" - Para temas de: tecnología, apps, internet, IA, smartphones, software, startups tech
3. "Política y Sociedad" - Para temas de: política, gobierno, elecciones, leyes, sociedad, protestas, justicia
4. "Entretenimiento y Bienestar" - Para temas de: deportes, famosos, música, TV, salud, lifestyle, turismo, futbol

INSTRUCCIONES:
1. Escribe un artículo sobre el tópico que fue seleccionado previamente: "{selected_trend}"
2. Analiza el tópico y asigna la categoría más apropiada de las 4 disponibles
3. Genera un artículo completo en formato Markdown puro
4. NO incluyas imágenes en el artículo - el sistema agregará automáticamente una imagen de portada

FORMATO MARKDOWN REQUERIDO:

# Título Principal del Tópico

**CATEGORÍA:** [Una de las 4 categorías exactas]

{format_template}

REGLAS IMPORTANTES:
- Usa **negrita** para palabras clave, nombres propios, cifras, fechas
- 1100-1200 palabras en total
- Cada párrafo entre 50-100 palabras
- Responde ÚNICAMENTE con el Markdown, sin texto adicional
- La categoría debe ser EXACTAMENTE una de las 4 opciones
- Mantén tono periodístico profesional argentino"""

        return prompt
    
    def generate_article_content(self, prompt: str) -> str:
        """Genera el contenido del artículo usando ChatGPT"""
        try:
            system_message = self.personality or "Eres un periodista especializado en tendencias argentinas. Responde ÚNICAMENTE con contenido en formato Markdown."
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1200,
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error generating content: {str(e)}")
            return ""
    
    def markdown_to_html(self, md: str) -> str:
        """Convierte Markdown simple a HTML"""
        html = md
        html = html.replace('### ', '<h3>').replace('\n### ', '</h3>\n<h3>')
        html = html.replace('## ', '<h2>').replace('\n## ', '</h2>\n<h2>')
        html = html.replace('# ', '<h1>').replace('\n# ', '</h1>\n<h1>')
        
        html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'^- (.*)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'\n{2,}', '</p>\n<p>', html)
        html = html.replace('\n', '<br>')
        
        if not html.startswith('<'):
            html = '<p>' + html
        if not html.endswith('>'):
            html = html + '</p>'
        
        html = re.sub(r'<h([123])>([^<]*?)(?=<|$)', r'<h\1>\2</h\1>', html)
        
        return html
    
    def process_article_data(self, agent_response: str) -> Dict[str, Any]:
        """Procesa la respuesta del agente para la API de fin.guru"""
        lines = agent_response.split('\n')
        
        title_line = next((line for line in lines if line.startswith('# ')), None)
        title = title_line.replace('# ', '').strip() if title_line else 'Artículo de Tendencia'
        
        category_line = next((line for line in lines if '**CATEGORÍA:**' in line or 'CATEGORÍA:' in line), None)
        category = "Entretenimiento y Bienestar"
        
        if category_line:
            category_match = re.search(r'(?:\*\*)?CATEGORÍA:(?:\*\*)?\s*(.+)', category_line)
            if category_match:
                category = category_match.group(1).strip()
        
        clean_markdown = agent_response
        clean_markdown = re.sub(r'(?:\*\*)?CATEGORÍA:(?:\*\*)?.*?\n', '', clean_markdown)
        clean_markdown = re.sub(r'^# .*?\n', '', clean_markdown, count=1)
        clean_markdown = clean_markdown.strip()
        
        paragraphs = [line.strip() for line in clean_markdown.split('\n') 
                     if line.strip() and not line.startswith('#') and not line.startswith('-')]
        excerpt = paragraphs[0][:150] + '...' if paragraphs else 'Artículo sobre tendencias'
        
        html_content = self.markdown_to_html(clean_markdown)
        
        filename = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + '.jpg'
        
        return {
            "title": title,
            "excerpt": excerpt,
            "content": html_content,
            "category": category,
            "publishAs": "",
            "tags": "argentina, tendencias, noticias",
            "detectedCategory": category,
            "fileName": filename
        }
    
    def publish_article(self, article_data: Dict[str, Any], trend_title: str, search_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """Publica el artículo en fin.guru con imagen descargada"""
        try:
            cover_image_data = None
            image_source = "none"
            search_attempts = []
        
            search_queries = []
            
            # 1. Título de top story si está disponible
            if isinstance(search_results, dict) and "top_stories" in search_results:
                top_stories = search_results["top_stories"]
                if isinstance(top_stories, list) and top_stories:
                    for story in top_stories[:2]: 
                        if isinstance(story, dict):
                            story_title = story.get('title', '')
                            if story_title:
                                search_queries.append(("top_story", story_title))
            
            # 2. Título de resultado orgánico si está disponible
            if isinstance(search_results, dict) and "organic_results" in search_results:
                organic_results = search_results["organic_results"]
                if isinstance(organic_results, list) and organic_results:
                    for result in organic_results[:2]: 
                        if isinstance(result, dict):
                            result_title = result.get('title', '')
                            if result_title:
                                search_queries.append(("organic_result", result_title))
            
            # 3. Tendencia original
            search_queries.append(("trend_title", trend_title))
            
            # 4. Consultas de fallback más genéricas
            search_queries.append(("generic_argentina", f"argentina noticias {trend_title.split()[0] if trend_title else 'actualidad'}"))
            search_queries.append(("generic_news", f"noticias argentina tendencias"))
            search_queries.append(("fallback", "argentina noticias actualidad"))
            
            print(f"   Intentando buscar imagen con {len(search_queries)} estrategias diferentes...")
            
            # Intentar cada consulta hasta encontrar una imagen válida
            for attempt_num, (source_type, query) in enumerate(search_queries, 1):
                try:
                    print(f"   Intento {attempt_num}/{len(search_queries)}: Buscando con '{query}' ({source_type})")
                    search_attempts.append(f"{attempt_num}. {source_type}: {query[:50]}...")
                    
                    image_url = self.search_google_images(query)
                    if image_url:
                        print(f"   ✅ URL de imagen encontrada: {image_url}")
                        downloaded_data = self.download_image_from_url(image_url)
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
            
            # Si no se pudo obtener imagen después de todos los intentos
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
            
            print(f"   - Enviando datos: {data}")
            print(f"   - Con archivo: {filename}")
            print(f"   - Sin headers manuales (requests genera automáticamente)")
            
            response = requests.post(
                self.api_endpoint,
                files=files,
                data=data,
                # NO incluir headers para multipart/form-data
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
                
                # Manejar el caso donde no hay temas adecuados
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
                selected_trend = self._extract_trend_title(trends_data, topic_position)
                if not selected_trend:
                    return {"status": "error", "message": f"No se pudo extraer título de la tendencia en posición {topic_position}"}
                print(f"   Tendencia seleccionada: {selected_trend}")
            
            print("3. Buscando información adicional...")
            search_results = self.search_google_news(selected_trend)
            
            print("4. Creando prompt...")
            prompt = self.create_prompt(trends_data, search_results, selected_trend, topic_position)
            
            print("5. Generando artículo...")
            article_content = self.generate_article_content(prompt)
            
            if not article_content:
                return {"status": "error", "message": "No se pudo generar contenido"}
            
            print("6. Procesando datos del artículo...")
            article_data = self.process_article_data(article_content)
            
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
                    print(f"{'='*50}")
                    
                    result = agent.run_automated_process_with_shared_trends(shared_trends_data, topic_position)
                    
                    if result.get("status") == "success":
                        result["agent_info"] = {
                            "agent_id": agent.agent_id,
                            "agent_name": agent.agent_name,
                            "personality": agent.personality,
                            "trending": agent.trending_prompt
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
        """Limpia el caché de tendencias manualmente"""
        cls._trends_cache.clear()
        print("Caché de tendencias limpiado manualmente")
    
    @classmethod
    def clear_session_cache(cls):
        """Limpia el caché de sesión de tendencias seleccionadas manualmente"""
        cls._selected_trends_session.clear()
        cls._selected_positions_session.clear()
        print("🔄 Caché de sesión limpiado - tendencias ya seleccionadas reiniciadas")
    
    @classmethod
    def get_cache_status(cls) -> Dict[str, Any]:
        """Obtiene el estado actual del caché"""
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
    
    def _validate_and_parse_data(self, data: Any, data_type: str = "unknown") -> Dict[str, Any]:
        """Valida y convierte datos a diccionario de forma robusta"""
        if data is None:
            print(f"   {data_type} es None")
            return {}
        
        if isinstance(data, dict):
            return data
        
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    return parsed
                else:
                    print(f"   {data_type} JSON no es un objeto: {type(parsed)}")
                    return {}
            except json.JSONDecodeError as e:
                print(f"   Error parseando {data_type} JSON: {str(e)}")
                return {}
        
        print(f"   {data_type} tiene tipo inesperado: {type(data)}")
        return {}
    def _extract_trend_title(self, trends_data: Dict[str, Any], position: int = 1) -> str:
        """Extrae el título del trend en la posición especificada de forma robusta"""
        if not isinstance(trends_data, dict):
            print("   trends_data no es un diccionario válido")
            return ""
        
        trending_topics = trends_data.get("trending_topics", [])
        if not isinstance(trending_topics, list) or not trending_topics:
            print("   No hay trending_topics válidos")
            return ""
        
        if position < 1 or position > len(trending_topics):
            print(f"   Posición {position} fuera de rango. Disponibles: 1-{len(trending_topics)}. Usando posición 1.")
            position = 1
        
        topic_index = position - 1
        selected_topic = trending_topics[topic_index]
        
        print(f"   Seleccionando tópico en posición #{position} (índice {topic_index})")
        
        if isinstance(selected_topic, dict):
            title = selected_topic.get('title', '')
            if isinstance(title, str) and title:
                return title
            
            if isinstance(title, dict):
                query = title.get('query', '')
                if isinstance(query, str) and query:
                    return query
            
            for key in ['query', 'name', 'text']:
                value = selected_topic.get(key, '')
                if isinstance(value, str) and value:
                    return value
                    
        elif isinstance(selected_topic, str):
            return selected_topic
        
        print(f"   No se pudo extraer título del tópico en posición {position}: {selected_topic}")
        return ""

    def select_trending_topic(self, trends_data: Dict[str, Any], user_id: int = None) -> Dict[str, Any]:
        """Permite que ChatGPT seleccione la tendencia más relevante evitando repetir temas de TODOS los agentes"""
        try:
            trends_data = self._validate_and_parse_data(trends_data, "trends_data")
            
            if user_id is None:
                user_id = self.agent_config.get('userId', 5822)
            
            all_recent_articles = self.get_all_agents_recent_articles(limit_per_agent=2)
            recent_articles_text = ""
            
            if all_recent_articles.get("status") == "success" and all_recent_articles.get("articles"):
                recent_articles_text = "\nARTÍCULOS RECIENTES DE TODOS LOS AGENTES (para evitar repetir temas):\n"
                recent_articles_text += f"🔍 Total: {all_recent_articles.get('total', 0)} artículos de {all_recent_articles.get('agents_processed', 0)} agentes\n\n"
                
                for i, article in enumerate(all_recent_articles["articles"][:15], 1):  # Mostrar máximo 15
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
                                categories_text = f" [Categorías: {', '.join(category_names)}]"
                        
                        # Extraer volumen de búsqueda si está disponible
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

📋 CRITERIOS DE SELECCIÓN:
{self.trending_prompt}

🚫 REGLAS ESTRICTAS - NO VIOLAR:
- ❌ PROHIBIDO: NO elijas tendencias marcadas con "❌ [YA SELECCIONADA - NO USAR]"
- ❌ PROHIBIDO: NO elijas tendencias sobre el MISMO evento/persona/noticia específica de los artículos recientes
- ✅ PERMITIDO: Puedes elegir la MISMA CATEGORÍA pero con tema específico diferente
- ✅ OBLIGATORIO: SOLO elige entre las tendencias SIN la marca ❌
- 🔍 VALIDACIÓN: Si NINGUNA tendencia cumple con los criterios, responde "NO_SUITABLE_TOPIC"

🔍 ANÁLISIS REQUERIDO:
1. Revisa cada tendencia disponible (sin ❌)
2. Compara CONTENIDO ESPECÍFICO (no categorías) con los artículos recientes 
3. Evalúa si la tendencia habla del mismo evento/persona/noticia específica
4. Si encuentras una tendencia con contenido específico diferente, elige la más relevante
5. Si NO encuentras ninguna tendencia que valga la pena, responde "NO_SUITABLE_TOPIC"

FORMATO DE RESPUESTA OBLIGATORIO:
POSICIÓN: [número del 1 al 16 O "NO_SUITABLE_TOPIC"]
TÍTULO: [título exacto de la tendencia elegida O "NINGUNO"]
RAZÓN: [explicación detallada de por qué la elegiste y cómo el CONTENIDO ESPECÍFICO es diferente a los artículos recientes, O por qué ninguna tendencia es adecuada]

Ejemplo exitoso:
POSICIÓN: 3
TÍTULO: dólar blue argentina
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
                            if not self._is_topic_similar_to_recent_articles(title, all_articles_list):
                                selected_position = i
                                selected_title = title
                                selected_reason = "Selección automática para evitar duplicados"
                                print(f"   ✅ Alternativa encontrada: Posición #{i} - {title}")
                                break
                else:
                    return {"status": "error", "message": "No hay tendencias disponibles que no se relacionen con artículos recientes de todos los agentes"}
            
            if selected_title and all_recent_articles.get("articles"):
                all_articles_list = all_recent_articles.get("articles", [])
                if self._is_topic_similar_to_recent_articles(selected_title, all_articles_list):
                    print(f"   ⚠️  ADVERTENCIA: La tendencia '{selected_title}' es muy similar a artículos recientes de todos los agentes")
                    
                    trending_topics = trends_data.get("trending_topics", [])
                    for i, topic in enumerate(trending_topics, 1):
                        if i not in self._selected_positions_session:
                            title = self._extract_trend_title(trends_data, i)
                            if title and title not in self._selected_trends_session:
                                if not self._is_topic_similar_to_recent_articles(title, all_articles_list):
                                    selected_position = i
                                    selected_title = title
                                    selected_reason = "Selección automática para evitar repetición temática"
                                    print(f"   ✅ Alternativa sin similitud encontrada: Posición #{i} - {title}")
                                    break
                    else:
                        print(f"   ⚠️  No se encontró alternativa, procediendo con la selección original (puede haber similitud con todos los agentes)")
            
            if selected_position and selected_title:
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
                selected_trend = self._extract_trend_title(trends_data, topic_position)
                if not selected_trend:
                    return {"status": "error", "message": f"No se pudo extraer título de la tendencia en posición {topic_position}"}
                print(f"   Tendencia seleccionada: {selected_trend}")
            
            print("3. Buscando información adicional...")
            search_results = self.search_google_news(selected_trend)
            
            print("4. Creando prompt...")
            prompt = self.create_prompt(trends_data, search_results, selected_trend, topic_position)
            
            print("5. Generando artículo...")
            article_content = self.generate_article_content(prompt)
            
            if not article_content:
                return {"status": "error", "message": "No se pudo generar contenido"}
            
            print("6. Procesando datos del artículo...")
            article_data = self.process_article_data(article_content)
            
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
    
def test_image_validation():
    """Función de prueba para verificar que el sistema de imágenes funciona correctamente"""
    print("🧪 Iniciando prueba de validación de imágenes...")
    
    agent = AutomatedTrendsAgent()
    
    # Simular datos de artículo de prueba
    test_article_data = {
        'fileName': 'test_image.jpg',
        'title': 'Artículo de Prueba',
        'excerpt': 'Prueba de validación de imágenes',
        'content': '<p>Contenido de prueba</p>',
        'category': 'Tecnología e Innovación',
        'tags': 'prueba, test',
        'publishAs': ''
    }
    
    # Probar con imagen vacía (debería fallar)
    print("\n1. Probando con cover_image_data = None (debería fallar):")
    try:
        result = agent._test_publish_validation(test_article_data, None)
        print(f"   Resultado: {result}")
    except Exception as e:
        print(f"   Error: {str(e)}")
    
    # Probar con imagen válida simulada
    print("\n2. Probando con imagen válida simulada:")
    fake_image_data = b'\x89PNG\r\n\x1a\n' + b'0' * 1000  # PNG header + data
    try:
        result = agent._test_publish_validation(test_article_data, fake_image_data)
        print(f"   Resultado: {result}")
    except Exception as e:
        print(f"   Error: {str(e)}")

def _test_publish_validation(self, article_data: Dict[str, Any], cover_image_data: Optional[bytes]) -> Dict[str, Any]:
    """Método de prueba para validar el flujo de imágenes sin hacer POST real"""
    try:
        # Ejecutar las mismas validaciones que publish_article pero sin POST
        if not cover_image_data or len(cover_image_data) == 0:
            return {
                "status": "error", 
                "message": "ERROR: cover_image_data está vacío"
            }
        
        filename = article_data['fileName']
        
        try:
            image_file = io.BytesIO(cover_image_data)
            image_file.name = filename
            
            image_file.seek(0, 2)
            size = image_file.tell()
            image_file.seek(0)
            
            if size == 0:
                return {
                    "status": "error", 
                    "message": "ERROR: El archivo BytesIO está vacío"
                }
            
        except Exception as e:
            return {
                "status": "error", 
                "message": f"ERROR creando archivo: {str(e)}"
            }
        
        files = {
            'cover': (filename, image_file, 'image/jpeg')
        }
        
        if 'cover' not in files or not files['cover']:
            return {
                "status": "error", 
                "message": "ERROR: Estructura de archivos inválida"
            }
        
        return {
            "status": "success", 
            "message": f"Validación exitosa: imagen de {len(cover_image_data)} bytes"
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Agregar método a la clase
AutomatedTrendsAgent._test_publish_validation = _test_publish_validation

def run_trends_agent(topic_position: int = None):
    """Función independiente para ejecutar el agente
    
    Args:
        topic_position: Posición específica (1-10) o None para selección automática por ChatGPT
    """
    agent = AutomatedTrendsAgent()
    return agent.run_automated_process(topic_position)

def run_multi_trends_agents(topic_position: int = None):
    """Función independiente para ejecutar múltiples agentes desde la API
    
    Args:
        topic_position: Posición específica (1-10) o None para selección automática por ChatGPT
    """
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