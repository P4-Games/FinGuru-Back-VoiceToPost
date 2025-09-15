"""
Módulo para procesamiento y generación de contenido.
"""

import os
import json
import random
import string
from typing import Dict, Any, Optional, List
from datetime import datetime
from openai import OpenAI
import html
import re


class ContentProcessor:
    """Procesador de contenido que maneja generación, formateo y validación"""
    
    def __init__(self, openai_api_key: str = None):
        self.openai_client = OpenAI(api_key=openai_api_key or os.environ['OPENAI_API_KEY'])
    
    def create_prompt(self, trends_data: Dict[str, Any], search_results: Dict[str, Any], 
                     selected_trend: str, topic_position: int = None, agent_config: Dict = None) -> str:
        """Crea un prompt optimizado para generar contenido sobre tendencias"""
        try:
            # Datos del agente
            personality = agent_config.get('personality', 'Eres un periodista especializado en tendencias de Argentina que debe crear contenido en Markdown')
            trending_prompt = agent_config.get('trending', 'Considera: - Relevancia para Argentina - Potencial de generar interés - Actualidad e importancia - Impacto social, económico o cultural')
            format_markdown = agent_config.get('format_markdown', '')
            
            prompt = f"""# PERSONALIDAD DEL AGENTE
{personality}

# CONTEXTO DE TRENDING TOPICS
Estás analizando las siguientes tendencias actuales de Argentina:

## TENDENCIAS DISPONIBLES:
"""
            
            # Agregar tendencias
            if trends_data.get("status") == "success":
                trending_searches = trends_data.get("trending_searches_argentina", [])
                if trending_searches:
                    for i, trend in enumerate(trending_searches[:10], 1):
                        trend_title = trend.get("title", "Sin título")
                        traffic = trend.get("formattedTraffic", "N/A")
                        marker = "👉 **SELECCIONADO** " if trend_title == selected_trend else "   "
                        prompt += f"{marker}{i}. **{trend_title}** (Tráfico: {traffic})\n"
                else:
                    prompt += "   No hay tendencias disponibles en este momento.\n"
            
            # Agregar criterios de selección
            prompt += f"""
## CRITERIOS DE SELECCIÓN:
{trending_prompt}

## TENDENCIA SELECCIONADA:
**"{selected_trend}"**
"""
            
            # Agregar posición si está especificada
            if topic_position:
                prompt += f"(Posición en trending: #{topic_position})\n"
            
            # Información de búsqueda
            if search_results and search_results.get("status") == "success":
                results = search_results.get("results", {})
                news_results = results.get("news", [])
                organic_results = results.get("organic", [])
                
                if news_results:
                    prompt += "\n## NOTICIAS RELACIONADAS ENCONTRADAS:\n"
                    for i, news in enumerate(news_results[:5], 1):
                        title = news.get("title", "Sin título")
                        snippet = news.get("snippet", "Sin descripción")
                        source = news.get("source", "Fuente desconocida")
                        date = news.get("date", "Fecha no disponible")
                        
                        prompt += f"""
### {i}. {title}
**Fuente:** {source} | **Fecha:** {date}
**Resumen:** {snippet}
"""
                
                if organic_results:
                    prompt += "\n## INFORMACIÓN ADICIONAL:\n"
                    for i, result in enumerate(organic_results[:3], 1):
                        title = result.get("title", "Sin título")
                        snippet = result.get("snippet", "Sin descripción")
                        
                        prompt += f"""
### {i}. {title}
**Información:** {snippet}
"""
            else:
                prompt += "\n## INFORMACIÓN ADICIONAL:\nNo se encontraron resultados de búsqueda específicos.\n"
            
            # Instrucciones de formato
            base_format = """
# INSTRUCCIONES PARA EL ARTÍCULO:

1. **TÍTULO**: Crea un título atractivo y claro que capture la esencia de la tendencia
2. **EXTRACTO**: Resume en 2-3 oraciones el punto principal del artículo
3. **CONTENIDO**: Desarrolla el tema de manera informativa y engaging
4. **CATEGORÍA**: Asigna una categoría apropiada
5. **ETIQUETAS**: Proporciona 3-5 tags relevantes

## FORMATO DE RESPUESTA REQUERIDO:
```json
{
  "title": "Título del artículo aquí",
  "excerpt": "Extracto/resumen del artículo aquí",
  "content": "Contenido completo en formato Markdown aquí",
  "category": "Categoría apropiada aquí",
  "tags": "tag1, tag2, tag3, tag4, tag5"
}
```

## CATEGORÍAS VÁLIDAS:
- Política y Gobierno
- Economía y Finanzas  
- Deportes
- Entretenimiento y Cultura
- Tecnología e Innovación
- Sociedad y Tendencias
- Salud y Bienestar
- Educación
- Medio Ambiente
- Internacional
- Otros

## FORMATO DE CONTENIDO:
"""
            
            if format_markdown:
                prompt += f"\n{format_markdown}\n"
            else:
                prompt += """
- Usa Markdown para formatear el contenido
- Incluye títulos y subtítulos apropiados
- Mínimo 300 palabras, máximo 1500 palabras
- Estructura clara y fácil de leer
- Información precisa y actualizada
- Tono profesional pero accesible
"""
            
            prompt += """
## IMPORTANTE:
- Responde ÚNICAMENTE con el JSON solicitado
- NO agregues explicaciones adicionales
- El contenido debe estar en español
- Enfócate en la relevancia para Argentina
- Mantén la información actualizada y precisa
"""
            
            return prompt
            
        except Exception as e:
            print(f"Error creando prompt: {str(e)}")
            return f"Error creando prompt: {str(e)}"

    def generate_article_content(self, prompt: str) -> str:
        """Genera contenido de artículo usando OpenAI"""
        try:
            print("🤖 Generando contenido con ChatGPT...")
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            print("✅ Contenido generado exitosamente")
            return content
            
        except Exception as e:
            error_msg = f"Error generando contenido: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg

    def markdown_to_html(self, md: str) -> str:
        """Convierte Markdown básico a HTML"""
        if not md:
            return ""
        
        # Conversiones básicas de Markdown a HTML
        html_content = md
        
        # Headers
        html_content = re.sub(r'^### (.*$)', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'^## (.*$)', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'^# (.*$)', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
        
        # Bold and Italic
        html_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_content)
        html_content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html_content)
        
        # Links
        html_content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html_content)
        
        # Line breaks
        html_content = html_content.replace('\n\n', '</p><p>')
        html_content = html_content.replace('\n', '<br>')
        
        # Wrap in paragraphs if not already wrapped
        if not html_content.startswith('<'):
            html_content = f'<p>{html_content}</p>'
        
        return html_content

    def process_article_data(self, agent_response: str) -> Dict[str, Any]:
        """Procesa la respuesta del agente y extrae datos del artículo"""
        try:
            print("🔄 Procesando respuesta del agente...")
            
            # Limpiar la respuesta
            cleaned_response = agent_response.strip()
            
            # Buscar JSON en la respuesta
            json_match = re.search(r'```json\s*(.*?)\s*```', cleaned_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Si no hay markdown de código, buscar JSON directo
                json_start = cleaned_response.find('{')
                json_end = cleaned_response.rfind('}') + 1
                if json_start != -1 and json_end > json_start:
                    json_str = cleaned_response[json_start:json_end]
                else:
                    raise Exception("No se encontró JSON válido en la respuesta")
            
            # Parsear JSON
            try:
                article_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"   Error parseando JSON: {str(e)}")
                print(f"   JSON problemático: {json_str[:200]}...")
                raise Exception(f"JSON inválido: {str(e)}")
            
            # Validar campos requeridos
            required_fields = ['title', 'excerpt', 'content', 'category', 'tags']
            for field in required_fields:
                if field not in article_data or not article_data[field]:
                    raise Exception(f"Campo requerido faltante o vacío: {field}")
            
            # Procesar y limpiar datos
            from .text_utils import TextUtils
            
            # Corregir capitalización del título
            article_data['title'] = TextUtils.fix_title_capitalization(article_data['title'])
            
            # Convertir contenido de Markdown a HTML
            article_data['content'] = self.markdown_to_html(article_data['content'])
            
            # Limpiar HTML entities
            article_data['content'] = html.unescape(article_data['content'])
            article_data['title'] = html.unescape(article_data['title'])
            article_data['excerpt'] = html.unescape(article_data['excerpt'])
            
            # Generar nombre de archivo para imagen
            article_data['fileName'] = TextUtils.generate_filename_from_title(article_data['title'])
            
            # Establecer publishAs como vacío por defecto
            article_data['publishAs'] = ""
            
            print("✅ Datos del artículo procesados exitosamente:")
            print(f"   📰 Título: {article_data['title']}")
            print(f"   📝 Extracto: {article_data['excerpt'][:100]}...")
            print(f"   📂 Categoría: {article_data['category']}")
            print(f"   🏷️ Tags: {article_data['tags']}")
            
            return {"status": "success", "data": article_data}
            
        except Exception as e:
            error_msg = f"Error procesando datos del artículo: {str(e)}"
            print(f"❌ {error_msg}")
            return {"status": "error", "message": error_msg, "raw_response": agent_response}

    def validate_generated_content(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """Valida el contenido generado"""
        try:
            # Validar título
            title = article_data.get('title', '')
            if len(title) < 10 or len(title) > 200:
                return {"status": "error", "message": "Título debe tener entre 10 y 200 caracteres"}
            
            # Validar extracto
            excerpt = article_data.get('excerpt', '')
            if len(excerpt) < 50 or len(excerpt) > 500:
                return {"status": "error", "message": "Extracto debe tener entre 50 y 500 caracteres"}
            
            # Validar contenido
            content = article_data.get('content', '')
            if len(content) < 300:
                return {"status": "error", "message": "Contenido debe tener al menos 300 caracteres"}
            
            # Validar categoría
            valid_categories = {
                'Política y Gobierno', 'Economía y Finanzas', 'Deportes', 
                'Entretenimiento y Cultura', 'Tecnología e Innovación', 
                'Sociedad y Tendencias', 'Salud y Bienestar', 'Educación', 
                'Medio Ambiente', 'Internacional', 'Otros'
            }
            
            category = article_data.get('category', '')
            if category not in valid_categories:
                # Asignar categoría por defecto
                article_data['category'] = 'Sociedad y Tendencias'
            
            # Validar tags
            tags = article_data.get('tags', '')
            if not tags or len(tags.split(',')) < 2:
                return {"status": "error", "message": "Se requieren al menos 2 tags separados por comas"}
            
            return {"status": "success", "message": "Contenido validado correctamente"}
            
        except Exception as e:
            return {"status": "error", "message": f"Error validando contenido: {str(e)}"}

    def enhance_content_for_seo(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mejora el contenido para SEO"""
        try:
            # Extraer palabras clave del título para SEO
            from .text_utils import TextUtils
            
            keywords = TextUtils.extract_keywords_from_text(article_data['title'])
            
            # Mejorar tags con palabras clave relevantes
            existing_tags = [tag.strip() for tag in article_data['tags'].split(',')]
            enhanced_tags = list(set(existing_tags + keywords[:3]))  # Agregar hasta 3 keywords
            
            # Limitar a máximo 8 tags
            article_data['tags'] = ', '.join(enhanced_tags[:8])
            
            return {"status": "success", "data": article_data}
            
        except Exception as e:
            return {"status": "error", "message": f"Error mejorando SEO: {str(e)}"}

    def create_social_media_snippets(self, article_data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Genera snippets para redes sociales"""
        try:
            title = article_data.get('title', '')
            excerpt = article_data.get('excerpt', '')
            
            # Snippets para Twitter (280 caracteres)
            twitter_snippets = []
            if len(title) <= 250:
                twitter_snippets.append(f"{title} 📰 #Argentina #Noticias")
            
            # Snippet corto del extracto
            short_excerpt = excerpt[:200] + "..." if len(excerpt) > 200 else excerpt
            twitter_snippets.append(f"{short_excerpt} #Trending")
            
            # Snippets para Facebook (más largos)
            facebook_snippets = []
            facebook_snippets.append(f"🔥 {title}\n\n{excerpt}")
            
            # Snippets para Instagram (con hashtags)
            instagram_snippets = []
            tags = article_data.get('tags', '').split(',')
            hashtags = ' '.join([f"#{tag.strip().replace(' ', '')}" for tag in tags[:5]])
            instagram_snippets.append(f"{title}\n\n{hashtags} #Argentina")
            
            return {
                "twitter": twitter_snippets,
                "facebook": facebook_snippets,
                "instagram": instagram_snippets
            }
            
        except Exception as e:
            print(f"Error generando snippets de redes sociales: {str(e)}")
            return {"twitter": [], "facebook": [], "instagram": []}