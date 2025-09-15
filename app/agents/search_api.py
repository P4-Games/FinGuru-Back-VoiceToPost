"""
Módulo para APIs de búsqueda y manejo de contenido externo.
"""

import os
import json
import requests
from typing import Dict, Any, Optional, List
import io
import traceback
import html
import re
import random
from utils.trends_functions import TrendsAPI


class SearchAPI:
    """Manejo de APIs de búsqueda y descarga de contenido externo"""
    
    def __init__(self, serper_api_key: str = None):
        self.serper_api_key = serper_api_key or "59e9db682aa8fd5c126e4fa6def959279d7167d4"
        self.trends_api = TrendsAPI()
        
    def get_trending_topics(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Obtiene temas trending usando TrendsAPI"""
        try:
            print("Obteniendo trending topics usando TrendsAPI...")
            return self.trends_api.get_trending_searches_by_category()
        except Exception as e:
            print(f"Error obteniendo trending topics: {str(e)}")
            return {"status": "error", "message": str(e)}

    def search_google_news(self, query: str) -> Dict[str, Any]:
        """Realiza búsqueda en Google News usando Serper API"""
        try:
            print(f"Realizando búsqueda de noticias con query: '{query}'")
            
            search_url = "https://google.serper.dev/news"
            headers = {
                'X-API-KEY': self.serper_api_key,
                'Content-Type': 'application/json'
            }
            data = {
                'q': query,
                'gl': 'ar',
                'hl': 'es',
                'num': 10,
                'tbm': 'nws'
            }
            
            response = requests.post(search_url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                results = response.json()
                news_results = results.get('news', [])
                
                if news_results:
                    print(f"   ✅ {len(news_results)} noticias encontradas")
                    for i, news in enumerate(news_results[:3], 1):
                        title = news.get('title', 'Sin título')[:80]
                        print(f"      {i}. {title}...")
                else:
                    print("   ⚠️ No se encontraron noticias")
                
                return {"status": "success", "results": results}
            else:
                error_msg = f"Error en API de noticias: {response.status_code}"
                print(f"   ❌ {error_msg}")
                return {"status": "error", "message": error_msg}
                
        except Exception as e:
            error_msg = f"Error realizando búsqueda de noticias: {str(e)}"
            print(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}

    def search_google_images(self, query: str) -> str:
        """Busca y descarga una imagen usando Serper API"""
        try:
            print(f"🔍 Buscando imágenes para: '{query}'")
            
            search_url = "https://google.serper.dev/images"
            headers = {
                'X-API-KEY': self.serper_api_key,
                'Content-Type': 'application/json'
            }
            
            data = {
                'q': query,
                'gl': 'ar',
                'hl': 'es',
                'num': 20,
                'safe': 'off'
            }
            
            response = requests.post(search_url, headers=headers, json=data, timeout=30)
            
            if response.status_code != 200:
                print(f"   ❌ Error en API: {response.status_code}")
                return None
            
            results = response.json()
            images = results.get('images', [])
            
            if not images:
                print("   ⚠️ No se encontraron imágenes")
                return None
            
            print(f"   📸 {len(images)} imágenes encontradas, probando descarga...")
            
            # Intentar descargar la primera imagen válida
            for i, img in enumerate(images):
                img_url = img.get('imageUrl')
                
                if not img_url or not self._is_valid_image_url(img_url):
                    continue
                
                print(f"   Intentando imagen {i+1}: {img_url[:80]}...")
                
                try:
                    image_data = self.download_image_from_url(img_url)
                    if image_data:
                        print(f"   ✅ Imagen descargada exitosamente: {len(image_data)} bytes")
                        return image_data
                except Exception as e:
                    print(f"   ❌ Error descargando imagen {i+1}: {str(e)}")
                    continue
            
            print("   🚫 No se pudo descargar ninguna imagen válida")
            return None
            
        except Exception as e:
            print(f"❌ Error en búsqueda de imágenes: {str(e)}")
            return None

    def _convert_serper_to_serpapi_format(self, serper_results: Dict[str, Any]) -> Dict[str, Any]:
        """Convierte resultados de Serper al formato SerpAPI para compatibilidad"""
        try:
            serpapi_format = {
                "search_metadata": {
                    "status": "Success"
                },
                "search_parameters": {
                    "q": serper_results.get("searchParameters", {}).get("q", ""),
                    "engine": "google"
                },
                "organic_results": []
            }
            
            # Convertir resultados orgánicos
            for result in serper_results.get("organic", []):
                serpapi_result = {
                    "position": result.get("position", 0),
                    "title": result.get("title", ""),
                    "link": result.get("link", ""),
                    "snippet": result.get("snippet", ""),
                    "displayed_link": result.get("displayedLink", "")
                }
                serpapi_format["organic_results"].append(serpapi_result)
            
            # Agregar noticias si existen
            if "news" in serper_results:
                serpapi_format["news_results"] = []
                for news in serper_results["news"]:
                    news_result = {
                        "title": news.get("title", ""),
                        "link": news.get("link", ""),
                        "snippet": news.get("snippet", ""),
                        "date": news.get("date", ""),
                        "source": news.get("source", "")
                    }
                    serpapi_format["news_results"].append(news_result)
            
            return serpapi_format
            
        except Exception as e:
            print(f"Error convirtiendo formato de resultados: {str(e)}")
            return serper_results

    def _is_valid_image_url(self, url: str) -> bool:
        """Valida si una URL es válida para descargar imágenes"""
        if not url or not isinstance(url, str):
            return False
        
        # Debe ser una URL HTTP/HTTPS válida
        if not (url.lower().startswith('http://') or url.lower().startswith('https://')):
            return False
        
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
        
        # Si tiene extensión válida, indicador O dominio conocido, es válida
        if has_valid_extension or has_image_indicator or has_image_domain:
            return True
        
        # Si no tiene nada obvio pero es una URL corta y simple, probablemente es válida
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
            
            # Ser MUCHO más permisivo con el content-type
            content_type = response.headers.get('content-type', '').lower()
            print(f"      📋 Tipo de contenido: {content_type}")
            
            image_data = response.content
            
            # Validaciones de tamaño más flexibles
            if len(image_data) < 100:  # Reducir aún más el mínimo
                print(f"      ❌ Imagen muy pequeña: {len(image_data)} bytes")
                return None
                
            if len(image_data) > 15 * 1024 * 1024:  # Aumentar máximo a 15MB
                print(f"      ❌ Imagen muy grande: {len(image_data)} bytes")
                return None
            
            # Siempre aceptar la imagen sin verificación PIL obligatoria
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

    def generate_search_queries(self, trend_title: str) -> List[tuple]:
        """Genera múltiples consultas de búsqueda para imágenes basadas en un tema trending"""
        queries = []
        
        # Query principal (exacta)
        queries.append((1, trend_title))
        
        # Query simplificada (palabras clave principales)
        keywords = trend_title.split()
        main_keywords = [word for word in keywords if len(word) > 3][:3]
        if main_keywords:
            queries.append((2, " ".join(main_keywords)))
        
        # Query con contexto argentino
        queries.append((3, f"{trend_title} Argentina"))
        
        # Query genérica relacionada
        if "política" in trend_title.lower():
            queries.append((4, "política Argentina noticias"))
        elif "deporte" in trend_title.lower() or "fútbol" in trend_title.lower():
            queries.append((5, "deportes Argentina fútbol"))
        elif "economía" in trend_title.lower() or "económico" in trend_title.lower():
            queries.append((6, "economía Argentina finanzas"))
        else:
            queries.append((7, f"noticias Argentina {main_keywords[0] if main_keywords else ''}"))
        
        return queries

    def search_image_with_multiple_queries(self, trend_title: str) -> Optional[bytes]:
        """Busca imágenes usando múltiples estrategias de búsqueda"""
        search_queries = self.generate_search_queries(trend_title)
        search_attempts = []
        
        for attempt_num, query in search_queries:
            try:
                search_attempts.append(f"Intento {attempt_num}: '{query}'")
                print(f"   🔍 Intento {attempt_num}: Buscando imagen con query '{query}'")
                
                image_data = self.search_google_images(query)
                if image_data:
                    print(f"   ✅ Imagen encontrada en intento {attempt_num} con query: '{query}'")
                    return image_data
                else:
                    print(f"   ❌ No se encontró imagen en intento {attempt_num}")
                    
            except Exception as e:
                print(f"   ❌ Error en intento {attempt_num}: {str(e)}")
                continue
        
        print(f"   🚫 No se pudo obtener imagen después de {len(search_queries)} intentos")
        return None