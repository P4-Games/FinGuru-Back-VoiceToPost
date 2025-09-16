import requests
import json
import io
from typing import Dict, Any, Optional

def get_available_agents(agent) -> Dict[str, Any]:
    """Obtiene todos los agentes disponibles desde la API"""
    try:
        print("Obteniendo agentes disponibles desde la API...")
        
        endpoint = f"{agent.next_public_api_url}/agent-ias?populate=*"
        
        headers = {
            "Authorization": f"Bearer {agent.sudo_api_key}",
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
                for agent_item in agents:
                    if isinstance(agent_item, dict):
                        user_id = None
                        user_data = agent_item.get('attributes', {}).get('user', {})
                        if isinstance(user_data, dict) and 'data' in user_data:
                            user_id = user_data.get('data', {}).get('id')
                        elif isinstance(user_data, dict) and 'id' in user_data:
                            user_id = user_data.get('id')
                        
                        processed_agent = {
                            'id': agent_item.get('id'),
                            'name': agent_item.get('attributes', {}).get('name', f"agent-{agent_item.get('id')}"),
                            'personality': agent_item.get('attributes', {}).get('personality', ''),
                            'trending': agent_item.get('attributes', {}).get('trending', ''),
                            'format_markdown': agent_item.get('attributes', {}).get('format_markdown', ''),
                            'userId': user_id,
                            'createdAt': agent_item.get('attributes', {}).get('createdAt', ''),
                            'updatedAt': agent_item.get('attributes', {}).get('updatedAt', ''),
                            'publishedAt': agent_item.get('attributes', {}).get('publishedAt', '')
                        }
                        processed_agents.append(processed_agent)
                agents = processed_agents
        
        print(f"Se encontraron {len(agents)} agentes disponibles")
        for a in agents:
            print(f"   - ID: {a.get('id')}, Nombre: {a.get('name')}")
        
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

def get_all_agents_recent_articles(agent, limit_per_agent: int = 2) -> Dict[str, Any]:
    """Obtiene los artículos recientes de TODOS los agentes para evitar repetir temas"""
    try:
        print(f"Obteniendo últimos {limit_per_agent} artículos de TODOS los agentes...")
        
        agents_response = get_available_agents(agent)
        if agents_response.get('status') != 'success':
            print(f"Error obteniendo agentes: {agents_response.get('message')}")
            return {"status": "error", "message": "No se pudieron obtener agentes", "articles": []}
        
        all_agents = agents_response.get('details', [])
        all_articles = []
        agents_processed = 0
        
        for agent_item in all_agents:
            try:
                agent_id = agent_item.get('id')
                agent_name = agent_item.get('name', f'Agent-{agent_id}')
                user_id = agent_item.get('userId')
                
                if not user_id:
                    print(f"   Agente {agent_name} (ID: {agent_id}) sin userId, saltando...")
                    continue
                
                print(f"   Obteniendo artículos del agente: {agent_name} (UserID: {user_id})")
                
                agent_articles = get_agent_recent_articles(user_id)
                
                if agent_articles.get("status") == "success" and agent_articles.get("articles"):
                    articles = agent_articles.get("articles", [])
                    
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
                print(f"   Error procesando agente {agent_item.get('name', 'unknown')}: {str(e)}")
                continue
        
        all_articles.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
        
        max_total_articles = len(all_agents) * limit_per_agent
        if len(all_articles) > max_total_articles:
            all_articles = all_articles[:max_total_articles]
        
        print(f"RESUMEN: {len(all_articles)} artículos recientes de {agents_processed} agentes")
        print("Últimos artículos encontrados:")
        for i, article in enumerate(all_articles[:10]):
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

def search_google_news(agent, query: str) -> Dict[str, Any]:
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
            'X-API-KEY': agent.serper_api_key,
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        
        results = response.json()
        
        converted_results = _convert_serper_to_serpapi_format(results)
        
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

def search_google_images(agent, query: str) -> str:
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
            'X-API-KEY': agent.serper_api_key,
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        
        results = response.json()
        
        print(f"      Buscando imágenes para: {query[:50]}...")
        
        if "images" in results and len(results["images"]) > 0:
            images_list = results["images"]
            print(f"      {len(images_list)} imágenes encontradas, tomando la primera válida...")
            
            for img_index, image_data in enumerate(images_list):
                try:
                    image_url = image_data.get("imageUrl")
                    
                    if not image_url:
                        print(f"      ❌ Imagen #{img_index + 1}: Sin URL")
                        continue
                    
                    if not (image_url.startswith('http://') or image_url.startswith('https://')):
                        print(f"      ❌ Imagen #{img_index + 1}: URL inválida")
                        continue
                    
                    valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
                    has_valid_extension = any(image_url.lower().endswith(ext) for ext in valid_extensions)
                    
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

def download_image_from_url(url: str) -> Optional[bytes]:
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
        
        content_type = response.headers.get('content-type', '').lower()
        print(f"      📋 Tipo de contenido: {content_type}")
        
        image_data = response.content
        
        if len(image_data) < 100:
            print(f"      ❌ Imagen muy pequeña: {len(image_data)} bytes")
            return None
            
        if len(image_data) > 15 * 1024 * 1024:
            print(f"      ❌ Imagen muy grande: {len(image_data)} bytes")
            return None
        
        print(f"      ✅ Imagen descargada exitosamente: {len(image_data)} bytes")
        
        try:
            from PIL import Image
            img_obj = Image.open(io.BytesIO(image_data))
            img_obj.verify()
            
            width, height = img_obj.size
            if width < 50 or height < 50:
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

def _convert_serper_to_serpapi_format(serper_results: Dict[str, Any]) -> Dict[str, Any]:
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

def _is_valid_image_url(url: str) -> bool:
    """Verifica si la URL de imagen es válida - VERSIÓN MUY PERMISIVA"""
    if not url or len(url) < 10:
        return False
    
    blocked_domains = ['data:', 'javascript:', 'blob:', 'chrome-extension:', 'about:', 'file:']
    if any(url.lower().startswith(blocked) for blocked in blocked_domains):
        return False
    
    if not (url.lower().startswith('http://') or url.lower().startswith('https://')):
        return False
    
    valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.svg', '.tiff', '.ico']
    has_valid_extension = any(url.lower().endswith(ext) for ext in valid_extensions)
    
    image_indicators = ['images', 'img', 'photo', 'pic', 'thumb', 'avatar', 'logo', 'banner', 
                       'media', 'upload', 'content', 'static', 'assets', 'file']
    has_image_indicator = any(indicator in url.lower() for indicator in image_indicators)
    
    image_domains = ['imgur.com', 'flickr.com', 'cloudinary.com', 'amazonaws.com', 'googleusercontent.com', 
                    'fbcdn.net', 'cdninstagram.com', 'pinimg.com', 'wikimedia.org', 'unsplash.com',
                    'pexels.com', 'shutterstock.com', 'getty', 'adobe.com', 'istock']
    has_image_domain = any(domain in url.lower() for domain in image_domains)
    
    if has_valid_extension or has_image_indicator or has_image_domain:
        return True
    
    if len(url) <= 200 and not any(suspicious in url.lower() for suspicious in ['javascript', 'data', 'void', 'null']):
        return True
    
    if len(url) > 500:
        return False
        
    return True
