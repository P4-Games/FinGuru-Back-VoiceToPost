"""
Módulo para el procesamiento de contenido del sistema de tendencias automatizado.
Proporciona funcionalidades para generar, procesar y formatear contenido de artículos.
"""

import html
import re
import string
import random
from typing import Dict, Any
from openai import OpenAI


class ContentProcessor:
    """Procesador de contenido para el sistema de tendencias automatizado"""
    
    def __init__(self, openai_client: OpenAI):
        self.openai_client = openai_client
    
    def create_prompt(self, trends_data: Dict[str, Any], search_results: Dict[str, Any], 
                     selected_trend: str, personality: str, trending_prompt: str, 
                     format_markdown: str, topic_position: int = None) -> str:
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
        
        if format_markdown and format_markdown.strip():
            format_template = html.unescape(format_markdown)
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
    
    def generate_article_content(self, prompt: str, personality: str) -> str:
        """Genera el contenido del artículo usando ChatGPT"""
        try:
            system_message = personality or "Eres un periodista especializado en tendencias argentinas. Responde ÚNICAMENTE con contenido en formato Markdown."
            
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
    
    def _validate_and_parse_data(self, data: Any, data_type: str = "unknown") -> Dict[str, Any]:
        """Valida y parsea datos, retornando un diccionario válido"""
        if isinstance(data, dict):
            return data
        
        if isinstance(data, str):
            try:
                import json
                parsed_data = json.loads(data)
                if isinstance(parsed_data, dict):
                    return parsed_data
            except:
                pass
        
        print(f"Warning: {data_type} no es un diccionario válido, usando diccionario vacío")
        return {}