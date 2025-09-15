"""
Utilidades para procesamiento de texto y validación de contenido.
"""

from typing import List, Dict, Any
import string
import re


class TextUtils:
    """Utilidades para manejo y validación de texto"""
    
    @staticmethod
    def fix_title_capitalization(title: str) -> str:
        """
        Corrige la capitalización incorrecta de títulos.
        Solo la primera letra debe ser mayúscula, más los nombres propios.
        """
        if not title or not isinstance(title, str):
            return title
        
        # Lista de palabras que siempre deben estar en mayúsculas (nombres propios comunes)
        proper_nouns = {
            'argentina', 'buenos', 'aires', 'córdoba', 'mendoza', 'rosario', 'santa', 'fe', 
            'tucumán', 'salta', 'neuquén', 'misiones', 'entre', 'ríos', 'río', 'negro',
            'chubut', 'chaco', 'corrientes', 'formosa', 'jujuy', 'la', 'pampa', 'rioja',
            'san', 'juan', 'luis', 'cruz', 'tierra', 'del', 'fuego', 'catamarca',
            'santiago', 'estero', 'boca', 'river', 'racing', 'independiente', 'estudiantes',
            'gimnasia', 'platense', 'lanús', 'banfield', 'arsenal', 'tigre', 'colón',
            'unión', 'newells', 'central', 'talleres', 'belgrano', 'instituto',
            'messi', 'maradona', 'scaloni', 'milei', 'cristina', 'kirchner', 'macri',
            'fernández', 'massa', 'bullrich', 'larreta', 'kicillof', 'vidal',
            'netflix', 'disney', 'amazon', 'google', 'facebook', 'instagram', 'twitter',
            'whatsapp', 'youtube', 'tiktok', 'spotify', 'apple', 'microsoft',
            'mercadolibre', 'mercadopago', 'galicia', 'santander', 'bbva', 'macro',
            'anses', 'afip', 'bcra', 'ypf', 'aerolíneas', 'argentinas', 'aca', 'afa',
            'cgt', 'uia', 'came', 'coninagro', 'sra', 'cepal', 'fmi', 'bid'
        }
        
        # Convertir todo a minúsculas primero
        title = title.lower().strip()
        
        # Dividir en palabras
        words = title.split()
        
        # Procesar cada palabra
        for i, word in enumerate(words):
            # Remover puntuación para comparar
            clean_word = word.strip('.,!?¡¿();:"\'')
            
            if i == 0:
                # Primera palabra siempre con mayúscula inicial
                if clean_word:
                    words[i] = clean_word[0].upper() + clean_word[1:] + word[len(clean_word):]
            elif clean_word.lower() in proper_nouns:
                # Nombres propios con mayúscula inicial
                if clean_word:
                    words[i] = clean_word[0].upper() + clean_word[1:] + word[len(clean_word):]
            # Las demás palabras permanecen en minúsculas
        
        return ' '.join(words)
        
    @staticmethod
    def is_topic_similar_to_recent_articles(topic_title: str, recent_articles: List[Dict]) -> bool:
        """Verifica si un tópico es similar a los artículos recientes usando palabras clave específicas"""
        if not recent_articles or not topic_title:
            return False
        
        generic_words = {
            'argentina', 'argentino', 'argentinos', 'argentinas', 'país', 'nacional', 'gobierno', 
            'política', 'político', 'políticos', 'políticas', 'deportes', 'deporte', 'deportivos',
            'economía', 'económico', 'económicos', 'económicas', 'social', 'sociedad', 'cultura',
            'tecnología', 'nuevo', 'nueva', 'últimas', 'último', 'noticias', 'noticia', 'hoy'
        }
        
        def extract_meaningful_words(text: str, min_length: int = 4) -> set:
            """Extrae palabras significativas del texto, excluyendo palabras genéricas"""
            if not text:
                return set()
            
            # Limpiar y normalizar
            text = text.lower()
            text = re.sub(r'[^\w\s]', ' ', text)
            words = text.split()
            
            # Filtrar palabras significativas
            meaningful = set()
            for word in words:
                if len(word) >= min_length and word not in generic_words:
                    meaningful.add(word)
            
            return meaningful
        
        topic_words = extract_meaningful_words(topic_title)
        if len(topic_words) < 2:  # Si no hay suficientes palabras significativas
            return False
        
        similarity_threshold = 0.4  # 40% de similitud
        
        for article in recent_articles:
            article_title = article.get('title', '')
            article_excerpt = article.get('excerpt', '')
            
            # Combinar título y extracto del artículo
            article_text = f"{article_title} {article_excerpt}"
            article_words = extract_meaningful_words(article_text)
            
            if not article_words:
                continue
            
            # Calcular intersección
            common_words = topic_words.intersection(article_words)
            
            if len(common_words) == 0:
                continue
            
            # Calcular similitud (Jaccard)
            similarity = len(common_words) / len(topic_words.union(article_words))
            
            if similarity >= similarity_threshold:
                print(f"      🔍 Similitud detectada ({similarity:.2%}) con: '{article_title}'")
                print(f"         Palabras comunes: {list(common_words)}")
                return True
        
        return False

    @staticmethod
    def extract_keywords_from_text(text: str, max_keywords: int = 10) -> List[str]:
        """Extrae palabras clave relevantes de un texto"""
        if not text:
            return []
        
        # Palabras irrelevantes comunes
        stop_words = {
            'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'es', 'se', 'no', 'te', 'lo', 'le',
            'da', 'su', 'por', 'son', 'con', 'para', 'al', 'del', 'los', 'las', 'una', 'como',
            'o', 'pero', 'sus', 'le', 'ya', 'todo', 'esta', 'fue', 'han', 'ser', 'está', 'son'
        }
        
        # Limpiar texto
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()
        
        # Filtrar y contar palabras
        word_freq = {}
        for word in words:
            if len(word) >= 4 and word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Ordenar por frecuencia y retornar las más relevantes
        keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in keywords[:max_keywords]]

    @staticmethod
    def clean_html_content(content: str) -> str:
        """Limpia contenido HTML básico"""
        if not content:
            return ""
        
        # Remover tags HTML básicos
        content = re.sub(r'<[^>]+>', '', content)
        # Decodificar entidades HTML básicas
        content = content.replace('&nbsp;', ' ')
        content = content.replace('&amp;', '&')
        content = content.replace('&lt;', '<')
        content = content.replace('&gt;', '>')
        content = content.replace('&quot;', '"')
        
        return content.strip()

    @staticmethod
    def validate_content_length(content: str, min_length: int = 100, max_length: int = 10000) -> bool:
        """Valida que el contenido tenga una longitud apropiada"""
        if not content:
            return False
        
        clean_content = TextUtils.clean_html_content(content)
        return min_length <= len(clean_content) <= max_length

    @staticmethod
    def generate_filename_from_title(title: str, extension: str = "jpg") -> str:
        """Genera un nombre de archivo seguro basado en un título"""
        if not title:
            return f"image.{extension}"
        
        # Limpiar título para nombre de archivo
        filename = title.lower()
        filename = re.sub(r'[^\w\s-]', '', filename)
        filename = re.sub(r'[-\s]+', '-', filename)
        filename = filename.strip('-')
        
        # Limitar longitud
        if len(filename) > 50:
            filename = filename[:50]
        
        return f"{filename}.{extension}"