"""
Módulo para servicios de búsqueda del sistema de tendencias automatizado.
Proporciona funcionalidades para buscar información y imágenes usando APIs externas.
"""

import json
import requests
from typing import Dict, Any


class SearchServices:
    """Servicios de búsqueda para el sistema de tendencias automatizado"""
    
    def __init__(self, serper_api_key: str):
        self.serper_api_key = serper_api_key
    
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