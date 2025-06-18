import os
import json
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime
from openai import OpenAI
from utils.trends_functions import TrendsAPI
from load_env import load_env_files
import html

load_env_files()

class AutomatedTrendsAgent:
    def __init__(self, agent_config: Optional[Dict[str, Any]] = None):
        self.openai_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
        self.serpapi_key = os.getenv("SERPAPI_KEY")
        self.serper_api_key = "59e9db682aa8fd5c126e4fa6def959279d7167d4"
        self.trends_api = TrendsAPI()
        self.api_endpoint = "https://fin.guru/api/agent-publish-article"
        
        # Configuración de API para obtener agentes
        self.next_public_api_url = os.getenv("NEXT_PUBLIC_API_URL")
        self.sudo_api_key = os.getenv("SUDO_API_KEY")
        
        # Configuración específica del agente si se proporciona
        self.agent_config = agent_config or {}
        self.agent_id = self.agent_config.get('id')
        self.agent_name = self.agent_config.get('name', 'default-agent')
        self.personality = self.agent_config.get('personality', 'Eres un periodista especializado en tendencias de Argentina que debe crear contenido en Markdown')
        self.trending_prompt = self.agent_config.get('trending', 'Considera: - Relevancia para Argentina - Potencial de generar interés - Actualidad e importancia - Impacto social, económico o cultural')
        self.format_markdown = self.agent_config.get('format_markdown', '')
        
    def get_available_agents(self) -> Dict[str, Any]:
        """Obtiene todos los agentes disponibles desde la API"""
        try:
            print("🔍 Obteniendo agentes disponibles desde la API...")
            
            # Construir el endpoint
            endpoint = f"{self.next_public_api_url}/agent-ias?populate=*"
            
            headers = {
                "Authorization": f"Bearer {self.sudo_api_key}",
                "Content-Type": "application/json",
            }
            
            response = requests.get(endpoint, headers=headers)
            
            if not response.ok:
                raise Exception(f"HTTP error! status: {response.status_code}")
            
            data = response.json()
            
            # Procesar los datos según la estructura proporcionada
            if 'details' in data:
                # Si ya viene en el formato esperado
                agents = data['details']
            else:
                # Si viene en formato Strapi, convertir
                agents = data.get('data', [])
                if isinstance(agents, list) and agents:                    # Convertir formato Strapi a formato esperado
                    processed_agents = []
                    for agent in agents:
                        if isinstance(agent, dict):
                            # Extraer userId del usuario poblado
                            user_id = None
                            user_data = agent.get('attributes', {}).get('user', {})
                            if isinstance(user_data, dict) and 'data' in user_data:
                                # Estructura: user: { data: { id: X } }
                                user_id = user_data.get('data', {}).get('id')
                            elif isinstance(user_data, dict) and 'id' in user_data:
                                # Estructura directa: user: { id: X }
                                user_id = user_data.get('id')
                            
                            processed_agent = {
                                'id': agent.get('id'),
                                'name': agent.get('attributes', {}).get('name', f"agent-{agent.get('id')}"),
                                'personality': agent.get('attributes', {}).get('personality', ''),
                                'trending': agent.get('attributes', {}).get('trending', ''),
                                'format_markdown': agent.get('attributes', {}).get('format_markdown', ''),
                                'userId': user_id,  # Agregar el userId real
                                'createdAt': agent.get('attributes', {}).get('createdAt', ''),
                                'updatedAt': agent.get('attributes', {}).get('updatedAt', ''),
                                'publishedAt': agent.get('attributes', {}).get('publishedAt', '')
                            }
                            processed_agents.append(processed_agent)
                    agents = processed_agents
            
            print(f"✅ Se encontraron {len(agents)} agentes disponibles")
            for agent in agents:
                print(f"   - ID: {agent.get('id')}, Nombre: {agent.get('name')}")
            
            return {
                'status': 'success',
                'details': agents,
                'total': len(agents)
            }
            
        except Exception as e:
            print(f"❌ Error obteniendo agentes desde la API: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'details': [],'total': 0
            }
    
    def initialize_agents(self) -> List['AutomatedTrendsAgent']:
        """Inicializa todos los agentes disponibles con sus configuraciones únicas"""
        try:
            print("🚀 Inicializando agentes múltiples...")
              # Obtener agentes disponibles
            agents_response = self.get_available_agents()
            
            if agents_response.get('status') != 'success':
                print(f"❌ Error obteniendo agentes: {agents_response.get('message')}")
                return []
            
            agents_data = agents_response.get('details', [])
            initialized_agents = []
            
            for agent_data in agents_data:
                try:                    # Decodificar el format_markdown si está HTML encoded
                    format_markdown = agent_data.get('format_markdown', '')
                    if format_markdown:
                        format_markdown = html.unescape(format_markdown)
                    
                    # Obtener userId real del agente (poblado desde la API)
                    agent_id = agent_data.get('id')
                    agent_user_id = agent_data.get('userId')
                    
                    if not agent_user_id:
                        print(f"⚠️ No se encontró userId para el agente {agent_id}, usando ID por defecto")
                        agent_user_id = 5822  # Fallback solo si no hay userId poblado
                    
                    # Crear configuración del agente
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
                      # Crear instancia del agente
                    agent_instance = AutomatedTrendsAgent(agent_config)
                    initialized_agents.append(agent_instance)                      # Mensaje de log más descriptivo
                    user_status = "real (bd)" if agent_data.get('userId') else "fallback"
                    print(f"✅ Agente inicializado: ID {agent_config['id']} - {agent_config['name']} (UserId: {agent_user_id} - {user_status})")
                    
                except Exception as e:
                    print(f"❌ Error inicializando agente {agent_data.get('id', 'unknown')}: {str(e)}")
                    continue
            
            print(f"🎉 Total de agentes inicializados: {len(initialized_agents)}")
            return initialized_agents
            
        except Exception as e:
            print(f"❌ Error general inicializando agentes: {str(e)}")
            return []
    
    def get_trending_topics(self) -> Dict[str, Any]:
        """Obtiene los temas de tendencia actuales"""
        return self.trends_api.get_trending_searches_by_category(
            geo="AR", 
            hours=24,
            language="es-419",
            count=10        
        )
    
    def search_google_news(self, query: str) -> Dict[str, Any]:
        """Busca información adicional sobre el tema en Google usando Serper API"""
        try:
            # Mejorar la query para obtener información más relevante
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
            
            # Convertir formato de Serper a formato compatible con SerpAPI
            converted_results = self._convert_serper_to_serpapi_format(results)
            
            # Debug: mostrar qué encontramos
            print(f"   🔍 Búsqueda realizada con Serper: {enhanced_query}")
            print(f"   📰 Resultados orgánicos encontrados: {len(converted_results.get('organic_results', []))}")
            print(f"   📺 Top stories encontradas: {len(converted_results.get('top_stories', []))}")
            
            # Mostrar algunos títulos para debug
            if "organic_results" in converted_results:
                print("   📄 Primeros resultados orgánicos:")
                for i, result in enumerate(converted_results["organic_results"][:3]):
                    print(f"      {i+1}. {result.get('title', 'Sin título')}")
            
            if "top_stories" in converted_results:
                print("   📢 Top stories:")
                for i, story in enumerate(converted_results["top_stories"][:3]):
                    print(f"      {i+1}. {story.get('title', 'Sin título')}")
            
            return converted_results
            
        except Exception as e:
            print(f"   ❌ Error searching Google with Serper: {str(e)}")
            return {}
    
    def search_google_images(self, query: str) -> str:
        """Busca una imagen relevante usando Serper API"""
        try:
            url = "https://google.serper.dev/images"
            
            payload = json.dumps({
                "q": query,
                "location": "Argentina",
                "gl": "ar",
                "hl": "es-419"
            })
            
            headers = {
                'X-API-KEY': self.serper_api_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            
            results = response.json()
            
            print(f"   🔍 Buscando imágenes con Serper para: {query}")
            
            # Tomar la primera imagen directamente del array images
            if "images" in results and len(results["images"]) > 0:
                print(f"   📊 Total de imágenes encontradas: {len(results['images'])}")
                
                # Tomar la primera imagen del array
                first_image = results["images"][0]
                if first_image.get("imageUrl"):
                    selected_image = first_image["imageUrl"]
                    title = first_image.get("title", "N/A")
                    source = first_image.get("source", "N/A")
                    
                    print(f"   📸 Primera imagen seleccionada:")
                    print(f"      - Título: {title}")
                    print(f"      - Fuente: {source}")
                    print(f"      - URL: {selected_image}")
                    
                    return selected_image
            
            print("   ⚠️ No se encontraron imágenes válidas")
            return ""
            
        except Exception as e:
            print(f"   ❌ Error buscando imágenes con Serper: {str(e)}")
            return ""
    
    def _convert_serper_to_serpapi_format(self, serper_results: Dict[str, Any]) -> Dict[str, Any]:
        """Convierte el formato de Serper al formato esperado por SerpAPI"""
        converted = {
            "organic_results": [],
            "top_stories": []
        }
        
        # Convertir resultados orgánicos
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
        
        # Convertir top stories
        if "topStories" in serper_results and isinstance(serper_results["topStories"], list):
            for story in serper_results["topStories"]:
                converted_story = {
                    "title": story.get("title", ""),
                    "link": story.get("link", ""),
                    "source": story.get("source", ""),
                    "date": story.get("date", ""),
                    "thumbnail": story.get("imageUrl", "")  # Mapear imageUrl a thumbnail
                }
                converted["top_stories"].append(converted_story)
        
        return converted
    
    def _is_valid_image_url(self, url: str) -> bool:
        """Verifica si la URL de imagen es válida"""
        if not url:
            return False
        
        # Verificar extensiones válidas
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        if not any(url.lower().endswith(ext) for ext in valid_extensions):
            # Si no tiene extensión, verificar que sea una URL de imagen común
            if not any(domain in url.lower() for domain in ['images', 'img', 'photo', 'pic']):
                return False
        
        # Evitar URLs problemáticas
        blocked_domains = ['data:', 'javascript:', 'blob:', 'chrome-extension:']
        if any(url.lower().startswith(blocked) for blocked in blocked_domains):
            return False
            
        return True
    
    def download_image_from_url(self, url: str) -> Optional[bytes]:
        """Descarga una imagen desde una URL"""
        try:
            print(f"   📥 Descargando imagen desde: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15, stream=True)
            response.raise_for_status()
            
            # Verificar que sea una imagen
            content_type = response.headers.get('content-type', '').lower()
            if not any(img_type in content_type for img_type in ['image/', 'jpeg', 'jpg', 'png', 'webp']):
                print(f"   ⚠️ Tipo de contenido no válido: {content_type}")
                return None
            
            # Leer el contenido
            image_data = response.content
            
            # Verificar tamaño mínimo (al menos 1KB)
            if len(image_data) < 1024:
                print(f"   ⚠️ Imagen muy pequeña: {len(image_data)} bytes")
                return None
              # Verificar que sea una imagen válida usando PIL si está disponible
            try:
                from PIL import Image
                import io
                Image.open(io.BytesIO(image_data)).verify()
                print(f"   ✅ Imagen descargada exitosamente: {len(image_data)} bytes")
                return image_data
            except ImportError:
                # Si PIL no está disponible, asumir que está bien
                print(f"   ✅ Imagen descargada (sin verificación PIL): {len(image_data)} bytes")
                return image_data
            except Exception as e:
                print(f"   ⚠️ Error verificando imagen con PIL: {str(e)}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Error descargando imagen: {str(e)}")
            return None
        except Exception as e:
            print(f"   ❌ Error inesperado descargando imagen: {str(e)}")            
            return None
    
    def create_prompt(self, trends_data: Dict[str, Any], search_results: Dict[str, Any], selected_trend: str, topic_position: int = None) -> str:
        """Crea el prompt para ChatGPT basado en las tendencias y búsquedas"""
          # Validar y convertir los datos de entrada
        trends_data = self._validate_and_parse_data(trends_data, "trends_data")
        search_results = self._validate_and_parse_data(search_results, "search_results")
        
        # Formatear las tendencias con posición y tráfico
        trends_text = ""
        trending_topics = trends_data.get("trending_topics", [])
        if isinstance(trending_topics, list) and trending_topics:
            for i, topic in enumerate(trending_topics, 1):
                title = ""
                
                if isinstance(topic, dict):
                    title = topic.get('title', '')
                    if isinstance(title, dict):
                        # Si es un objeto complejo, extraer el query
                        title = title.get('query', str(title))
                elif isinstance(topic, str):
                    title = topic
                
                if title:
                    traffic = "N/A"  # Por ahora no tenemos formattedTraffic
                    trends_text += f"{i}. {title} - {traffic}\n"
        
        # Extraer información relevante de organic_results y top_stories
        additional_info = ""
        
        # Agregar información de top_stories (noticias destacadas)
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
        
        # Agregar información de organic_results (resultados de búsqueda general)
        if isinstance(search_results, dict) and "organic_results" in search_results:
            organic_results = search_results["organic_results"]
            if isinstance(organic_results, list) and organic_results:
                additional_info += "INFORMACIÓN ADICIONAL:\n"
                # Filtrar y ordenar por position, tomar solo los primeros 3
                organic_sorted = []
                for result in organic_results:
                    if isinstance(result, dict):
                        organic_sorted.append(result)
                
                # Ordenar por position y tomar los primeros 3
                organic_sorted = sorted(organic_sorted, key=lambda x: x.get('position', 999))[:3]
                
                for i, result in enumerate(organic_sorted, 1):
                    title = result.get('title', 'Sin título')
                    snippet = result.get('snippet', 'Sin descripción')
                    position = result.get('position', 'N/A')
                    # Limitar snippet a 100 caracteres
                    if len(snippet) > 100:
                        snippet = snippet[:97] + "..."
                    additional_info += f"{i}. [Pos. {position}] {title}\n   {snippet}\n"
          # Usar personalidad específica del agente o la por defecto
        personality = self.personality
        trending_instructions = self.trending_prompt
        format_template = self.format_markdown
        
        # Si el agente tiene formato personalizado, usarlo; si no, usar el formato por defecto
        if format_template and format_template.strip():
            # Decodificar HTML entities si es necesario
            format_template = html.unescape(format_template)
            # Convertir HTML a Markdown básico para el template
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
            # Usar la personalidad específica del agente como mensaje del sistema
            system_message = self.personality or "Eres un periodista especializado en tendencias argentinas. Responde ÚNICAMENTE con contenido en formato Markdown."
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1200,  # Aumentar tokens para artículos más detallados
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error generating content: {str(e)}")
            return ""
    
    def markdown_to_html(self, md: str) -> str:
        """Convierte Markdown simple a HTML"""
        html = md
        # Encabezados
        html = html.replace('### ', '<h3>').replace('\n### ', '</h3>\n<h3>')
        html = html.replace('## ', '<h2>').replace('\n## ', '</h2>\n<h2>')
        html = html.replace('# ', '<h1>').replace('\n# ', '</h1>\n<h1>')
        
        # Negritas
        import re
        html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
        
        # Listas
        html = re.sub(r'^- (.*)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        
        # Párrafos
        html = re.sub(r'\n{2,}', '</p>\n<p>', html)
        html = html.replace('\n', '<br>')
        
        # Wrap en párrafos si no empieza con tag
        if not html.startswith('<'):
            html = '<p>' + html
        if not html.endswith('>'):
            html = html + '</p>'
          # Cerrar encabezados abiertos
        html = re.sub(r'<h([123])>([^<]*?)(?=<|$)', r'<h\1>\2</h\1>', html)
        
        return html
    
    def process_article_data(self, agent_response: str) -> Dict[str, Any]:
        """Procesa la respuesta del agente para la API de fin.guru"""
        import re  # Importar re al inicio de la función
        lines = agent_response.split('\n')
        
        # Extraer título
        title_line = next((line for line in lines if line.startswith('# ')), None)
        title = title_line.replace('# ', '').strip() if title_line else 'Artículo de Tendencia'
          # Extraer categoría con formatos flexibles
        category_line = next((line for line in lines if '**CATEGORÍA:**' in line or 'CATEGORÍA:' in line), None)
        category = "Entretenimiento y Bienestar"  # Por defecto        
        if category_line:
            # Buscar ambos formatos: **CATEGORÍA:** o CATEGORÍA:
            category_match = re.search(r'(?:\*\*)?CATEGORÍA:(?:\*\*)?\s*(.+)', category_line)
            if category_match:
                category = category_match.group(1).strip()        
                # Limpiar el markdown (remover la línea de categoría Y el título)
        clean_markdown = agent_response
        # Remover ambos formatos de categoría
        clean_markdown = re.sub(r'(?:\*\*)?CATEGORÍA:(?:\*\*)?.*?\n', '', clean_markdown)
        # Remover la primera línea que empieza con # (el título)
        clean_markdown = re.sub(r'^# .*?\n', '', clean_markdown, count=1)
        clean_markdown = clean_markdown.strip()
        
        # Crear excerpt desde el primer párrafo
        paragraphs = [line.strip() for line in clean_markdown.split('\n') 
                     if line.strip() and not line.startswith('#') and not line.startswith('-')]
        excerpt = paragraphs[0][:150] + '...' if paragraphs else 'Artículo sobre tendencias'
        # Convertir a HTML
        html_content = self.markdown_to_html(clean_markdown)
        
        # Generar nombre de archivo para la imagen
        import random
        import string
        filename = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + '.jpg'
        
        return {
            "title": title,
            "excerpt": excerpt,
            "content": html_content,
            "category": category,  # Usar la categoría original, no la mapeada
            "publishAs": "",
            "tags": "argentina, tendencias, noticias",
            "detectedCategory": category,
            "fileName": filename        }
    
    def publish_article(self, article_data: Dict[str, Any], trend_title: str, search_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """Publica el artículo en fin.guru con imagen descargada"""
        try:
            cover_image_data = None
            image_source = "fallback"
            
            # Asegurar que search_results es un diccionario
            if isinstance(search_results, str):
                try:
                    search_results = json.loads(search_results)
                except json.JSONDecodeError:
                    print("   ❌ Error parseando search_results JSON")
                    search_results = {}              # 1. Buscar título para usar en búsqueda de imágenes
            search_title_for_image = None
            image_source_type = None
            
            # Primero intentar con top_stories
            if isinstance(search_results, dict) and "top_stories" in search_results:
                top_stories = search_results["top_stories"]
                if isinstance(top_stories, list) and top_stories:
                    print("   🔍 Buscando título en top_stories para búsqueda de imagen...")
                    # Tomar el primer top_story que tenga título
                    for i, story in enumerate(top_stories[:3]):
                        if isinstance(story, dict):
                            story_title = story.get('title', '')
                            if story_title:
                                search_title_for_image = story_title
                                image_source_type = "top_story"
                                print(f"   📰 Título seleccionado de top_story #{i+1}: {story_title}")
                                break
            
            # Si no hay top_stories, usar organic_results
            if not search_title_for_image and isinstance(search_results, dict) and "organic_results" in search_results:
                organic_results = search_results["organic_results"]
                if isinstance(organic_results, list) and organic_results:
                    print("   🔍 No hay top_stories, buscando título en organic_results para búsqueda de imagen...")
                    # Tomar el primer organic_result que tenga título
                    for i, result in enumerate(organic_results[:3]):
                        if isinstance(result, dict):
                            result_title = result.get('title', '')
                            if result_title:
                                search_title_for_image = result_title
                                image_source_type = "organic_result"
                                print(f"   📄 Título seleccionado de organic_result #{i+1}: {result_title}")
                                break
            
            # Si aún no hay título, usar el trend_title como fallback
            if not search_title_for_image:
                search_title_for_image = trend_title
                image_source_type = "trend_title"
                print(f"   📈 Usando trend_title como fallback: {trend_title}")
            
            # 2. Buscar y descargar imagen
            print(f"   🔍 Buscando imagen con Google Images para: {search_title_for_image}")
            image_url = self.search_google_images(search_title_for_image)
            if image_url:
                cover_image_data = self.download_image_from_url(image_url)
                if cover_image_data:
                    image_source = f"google_images_from_{image_source_type}"
                    print(f"   ✅ Imagen descargada exitosamente desde Google Images")
                else:
                    print("   ❌ Error descargando imagen desde Google Images")
                    return {"status": "error", "message": "No se pudo descargar imagen para el artículo"}
            else:
                print("   ❌ No se encontró imagen en Google Images")
                return {"status": "error", "message": "No se pudo encontrar imagen para el artículo"}
            
            # 3. Si llegamos aquí, tenemos imagen válida
            
            print(f"   📊 Fuente de imagen utilizada: {image_source}")
            
            # 3. Preparar archivo de imagen
            import io
            filename = article_data['fileName']
            print(f"   📁 Creando archivo: {filename} ({len(cover_image_data)} bytes)")
            
            image_file = io.BytesIO(cover_image_data)
            image_file.name = filename            
            # Preparar FormData exactamente como lo hace el frontend
            files = {
                'cover': (filename, image_file, 'image/jpeg')
            }
            
            data = {
                'title': article_data['title'],
                'excerpt': article_data['excerpt'],
                'content': article_data['content'],
                'category': article_data['category'],
                'tags': article_data['tags'],
                'publishAs': '-1' if not article_data['publishAs'] else str(article_data['publishAs']),
                'userId': str(self.agent_config.get('userId', 5822))  # Agregar userId a los datos del formulario
            }            
            # Headers sin Authorization ya que usamos userId en los datos
            headers = {
                'Content-Type': 'multipart/form-data'
            }
            
            print(f"   - Enviando datos: {data}")
            print(f"   - Con archivo: {filename}")
            print(f"   - Headers: {headers}")
            
            response = requests.post(
                self.api_endpoint,
                files=files,
                data=data,
                # headers=headers  # Comentado para que requests maneje automáticamente multipart/form-data
            )
            
            print(f"   - Response status: {response.status_code}")
            print(f"   - Response headers: {dict(response.headers)}")
            print(f"   - Response text: {response.text}")
            
            if response.status_code == 200:
                return {"status": "success", "message": "Artículo publicado exitosamente"}
            else:
                return {"status": "error", "message": f"Error {response.status_code}: {response.text}"}
                
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"   ❌ Error completo: {error_detail}")
            return {"status": "error", "message": str(e)}
    def run_automated_process(self, topic_position: int = None) -> Dict[str, Any]:
        """Ejecuta el proceso completo automatizado"""
        try:
            print(f"[{datetime.now()}] Iniciando proceso automatizado de tendencias...")
            
            # 1. Obtener tendencias
            print("1. Obteniendo tendencias...")
            trends_data = self.get_trending_topics()
            
            if trends_data.get("status") != "success" or not trends_data.get("trending_topics"):
                return {"status": "error", "message": "No se pudieron obtener tendencias"}
            
            # 2. Determinar la tendencia a usar
            if topic_position is None:
                # Permitir que ChatGPT elija la tendencia más relevante
                print("2. Permitiendo que ChatGPT seleccione la tendencia más relevante...")
                selection_result = self.select_trending_topic(trends_data)
                
                if selection_result.get("status") != "success":
                    return {"status": "error", "message": "No se pudo seleccionar tendencia"}
                
                topic_position = selection_result["selected_position"]
                selected_trend = selection_result["selected_title"]
                selection_reason = selection_result["selected_reason"]
                
                print(f"   🎯 ChatGPT eligió posición #{topic_position}: {selected_trend}")
                print(f"   💡 Razón: {selection_reason}")
            else:
                # Usar la posición especificada manualmente
                print(f"2. Usando tendencia en posición manual #{topic_position}...")
                selected_trend = self._extract_trend_title(trends_data, topic_position)
                if not selected_trend:
                    return {"status": "error", "message": f"No se pudo extraer título de la tendencia en posición {topic_position}"}
                print(f"   📍 Tendencia seleccionada: {selected_trend}")
            
            # 3. Buscar información adicional sobre la tendencia seleccionada
            print("3. Buscando información adicional...")
            search_results = self.search_google_news(selected_trend)            # 4. Crear prompt
            print("4. Creando prompt...")
            prompt = self.create_prompt(trends_data, search_results, selected_trend, topic_position)
            
            # 5. Generar artículo
            print("5. Generando artículo...")
            article_content = self.generate_article_content(prompt)
            
            if not article_content:
                return {"status": "error", "message": "No se pudo generar contenido"}            
            # 6. Procesar datos del artículo
            print("6. Procesando datos del artículo...")
            article_data = self.process_article_data(article_content)              
            # 7. Publicar artículo
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
            print(f"[{datetime.now()}] 🚀 Iniciando proceso multi-agente...")
            
            # Inicializar todos los agentes
            agents = self.initialize_agents()
            
            if not agents:
                return {"status": "error", "message": "No se pudieron inicializar agentes"}
            
            print(f"📊 Ejecutando proceso con {len(agents)} agentes...")
            
            # Resultados de todos los agentes
            all_results = []
            
            for i, agent in enumerate(agents):
                try:
                    print(f"\n{'='*50}")
                    print(f"🤖 Ejecutando Agente {i+1}/{len(agents)}")
                    print(f"   ID: {agent.agent_id}")
                    print(f"   Nombre: {agent.agent_name}")
                    print(f"{'='*50}")
                    
                    # Ejecutar el proceso completo para este agente
                    result = agent.run_automated_process(topic_position)
                    
                    # Agregar información del agente al resultado
                    if result.get("status") == "success":
                        result["agent_info"] = {
                            "agent_id": agent.agent_id,
                            "agent_name": agent.agent_name,
                            "personality": agent.personality,
                            "trending": agent.trending_prompt
                        }
                    
                    all_results.append(result)
                    
                    print(f"✅ Agente {agent.agent_name} completado: {result.get('status')}")
                    
                except Exception as e:
                    print(f"❌ Error ejecutando agente {agent.agent_name}: {str(e)}")
                    all_results.append({
                        "status": "error",
                        "message": str(e),
                        "agent_info": {
                            "agent_id": agent.agent_id,
                            "agent_name": agent.agent_name
                        }
                    })
            
            # Resumen de resultados
            successful_agents = [r for r in all_results if r.get("status") == "success"]
            failed_agents = [r for r in all_results if r.get("status") == "error"]
            
            print(f"\n🎉 RESUMEN MULTI-AGENTE:")
            print(f"   ✅ Exitosos: {len(successful_agents)}")
            print(f"   ❌ Fallidos: {len(failed_agents)}")
            print(f"   📊 Total procesados: {len(all_results)}")
            
            return {
                "status": "success",
                "message": f"Proceso multi-agente completado: {len(successful_agents)}/{len(all_results)} exitosos",
                "results": all_results,
                "summary": {
                    "total_agents": len(all_results),
                    "successful": len(successful_agents),
                    "failed": len(failed_agents)
                }
            }
            
        except Exception as e:
            print(f"❌ Error general en proceso multi-agente: {str(e)}")
            return {
                "status": "error", 
                "message": str(e),
                "results": [],
                "summary": {"total_agents": 0, "successful": 0, "failed": 0}
            }
    
    def _validate_and_parse_data(self, data: Any, data_type: str = "unknown") -> Dict[str, Any]:
        """Valida y convierte datos a diccionario de forma robusta"""
        if data is None:
            print(f"   ⚠️ {data_type} es None")
            return {}
        
        if isinstance(data, dict):
            return data
        
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    return parsed
                else:
                    print(f"   ⚠️ {data_type} JSON no es un objeto: {type(parsed)}")
                    return {}
            except json.JSONDecodeError as e:
                print(f"   ❌ Error parseando {data_type} JSON: {str(e)}")
                return {}
        
        print(f"   ⚠️ {data_type} tiene tipo inesperado: {type(data)}")
        return {}
    def _extract_trend_title(self, trends_data: Dict[str, Any], position: int = 1) -> str:
        """Extrae el título del trend en la posición especificada de forma robusta"""
        if not isinstance(trends_data, dict):
            print("   ❌ trends_data no es un diccionario válido")
            return ""
        
        trending_topics = trends_data.get("trending_topics", [])
        if not isinstance(trending_topics, list) or not trending_topics:
            print("   ❌ No hay trending_topics válidos")
            return ""
        
        # Validar que la posición esté dentro del rango disponible
        if position < 1 or position > len(trending_topics):
            print(f"   ⚠️ Posición {position} fuera de rango. Disponibles: 1-{len(trending_topics)}. Usando posición 1.")
            position = 1
        
        # Convertir posición a índice (1-based a 0-based)
        topic_index = position - 1
        selected_topic = trending_topics[topic_index]
        
        print(f"   📍 Seleccionando tópico en posición #{position} (índice {topic_index})")
          # Manejar diferentes estructuras de datos
        if isinstance(selected_topic, dict):
            # Caso 1: {'title': 'algo'}
            title = selected_topic.get('title', '')
            if isinstance(title, str) and title:
                return title
            
            # Caso 2: {'title': {'query': 'algo'}}
            if isinstance(title, dict):
                query = title.get('query', '')
                if isinstance(query, str) and query:
                    return query
            
            # Caso 3: buscar otras claves posibles
            for key in ['query', 'name', 'text']:
                value = selected_topic.get(key, '')
                if isinstance(value, str) and value:
                    return value
                    
        elif isinstance(selected_topic, str):
            # Caso 4: Es directamente un string
            return selected_topic
        print(f"   ❌ No se pudo extraer título del tópico en posición {position}: {selected_topic}")
        return ""

    def select_trending_topic(self, trends_data: Dict[str, Any]) -> Dict[str, Any]:
        """Permite que ChatGPT seleccione la tendencia más relevante"""
        try:
            # Validar y convertir los datos de entrada
            trends_data = self._validate_and_parse_data(trends_data, "trends_data")
            
            # Formatear las tendencias para el prompt de selección
            trends_text = ""
            trending_topics = trends_data.get("trending_topics", [])
            if isinstance(trending_topics, list) and trending_topics:
                for i, topic in enumerate(trending_topics, 1):
                    title = ""
                    
                    if isinstance(topic, dict):
                        title = topic.get('title', '')
                        if isinstance(title, dict):
                            title = title.get('query', str(title))
                    elif isinstance(topic, str):
                        title = topic
                    
                    if title:
                        trends_text += f"{i}. {title}\n"
            # Prompt corto para selección
            selection_prompt = f"""Eres un editor de noticias especializado en Argentina. Te proporciono las 5 tendencias actuales más populares en Argentina.

TENDENCIAS ACTUALES (últimas 24h):
{trends_text}

Tu tarea es ELEGIR UNA SOLA tendencia que sea más relevante e interesante para el público argentino.

Considera:
{self.trending_prompt}

RESPONDE ÚNICAMENTE EN ESTE FORMATO:
POSICIÓN: [número del 1 al 5]
TÍTULO: [título exacto de la tendencia elegida]
RAZÓN: [una línea explicando por qué la elegiste]

Ejemplo:
POSICIÓN: 3
TÍTULO: dólar blue argentina
RAZÓN: Tema económico de alto interés para los argentinos"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un editor experto en seleccionar noticias relevantes para Argentina. Responde exactamente en el formato solicitado."},
                    {"role": "user", "content": selection_prompt}
                ],
                max_tokens=100,
                temperature=0.3  # Baja temperatura para respuestas más consistentes
            )
            
            selection_response = response.choices[0].message.content.strip()
            print(f"   🤖 Respuesta de selección: {selection_response}")
            
            # Parsear la respuesta
            lines = selection_response.split('\n')
            selected_position = None
            selected_title = None
            selected_reason = None
            
            for line in lines:
                line = line.strip()
                if line.startswith('POSICIÓN:'):
                    try:
                        selected_position = int(line.replace('POSICIÓN:', '').strip())
                    except ValueError:
                        pass
                elif line.startswith('TÍTULO:'):
                    selected_title = line.replace('TÍTULO:', '').strip()
                elif line.startswith('RAZÓN:'):
                    selected_reason = line.replace('RAZÓN:', '').strip()
            
            if selected_position and selected_title:
                print(f"   ✅ ChatGPT eligió: Posición #{selected_position} - {selected_title}")
                print(f"   💡 Razón: {selected_reason}")
                
                return {
                    "status": "success",
                    "selected_position": selected_position,
                    "selected_title": selected_title,
                    "selected_reason": selected_reason
                }
            else:
                print(f"   ❌ No se pudo parsear la respuesta de selección")
                return {"status": "error", "message": "No se pudo parsear la selección"}
                
        except Exception as e:
            print(f"   ❌ Error en selección de tendencia: {str(e)}")
            return {"status": "error", "message": str(e)}

def run_trends_agent(topic_position: int = None):
    """Función independiente para ejecutar el agente
    
    Args:
        topic_position: Posición específica (1-10) o None para selección automática por ChatGPT
    """
    agent = AutomatedTrendsAgent()
    return agent.run_automated_process(topic_position)

def run_multi_trends_agents(topic_position: int = None, token: str = None):
    """Función independiente para ejecutar múltiples agentes desde la API
    
    Args:
        topic_position: Posición específica (1-10) o None para selección automática por ChatGPT
        token: Token de autenticación (opcional, para compatibilidad con la API)
    """
    # Crear una instancia base para coordinar el proceso
    coordinator = AutomatedTrendsAgent()
    return coordinator.run_multi_agent_process(topic_position)

def get_available_agents():
    """Función independiente para obtener agentes disponibles de la API"""
    agent = AutomatedTrendsAgent()
    return agent.get_available_agents()

def initialize_agents_from_api():
    """Función independiente para inicializar agentes desde la API"""
    agent = AutomatedTrendsAgent()
    return agent.initialize_agents()