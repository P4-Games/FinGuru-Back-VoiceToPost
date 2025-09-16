"""
Módulo para el manejo de imágenes del sistema de tendencias automatizado.
Proporciona funcionalidades para validar, descargar y procesar imágenes.
"""

import io
import requests
from typing import Optional


class ImageHandler:
    """Manejador de imágenes para el sistema de tendencias automatizado"""
    
    @staticmethod
    def is_valid_image_url(url: str) -> bool:
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
    
    @staticmethod
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