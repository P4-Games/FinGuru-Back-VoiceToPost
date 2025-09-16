import json
import re
import html
import string
import random
from typing import Dict, Any, List

def _is_topic_similar_to_recent_articles(topic_title: str, recent_articles: List[Dict]) -> bool:
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
        
        article_keywords = set()
        for word in (article_title + ' ' + article_excerpt).split():
            if word.lower() not in generic_words and len(word) > 2:
                article_keywords.add(word.lower())
        
        common_keywords = topic_keywords.intersection(article_keywords)
        
        if len(common_keywords) >= 3:
            similarity_ratio = len(common_keywords) / max(len(topic_keywords), 1)
            if similarity_ratio > 0.6:
                print(f"   ⚠️ Tópico '{topic_title}' MUY similar a artículo '{article.get('title')}' (similitud: {similarity_ratio:.2f})")
                print(f"   🔑 Palabras específicas en común: {list(common_keywords)}")
                return True
    
    return False

def create_prompt(agent, trends_data: Dict[str, Any], search_results: Dict[str, Any], selected_trend: str, topic_position: int = None) -> str:
    """Crea el prompt para ChatGPT basado en las tendencias y búsquedas"""
    trends_data = _validate_and_parse_data(trends_data, "trends_data")
    search_results = _validate_and_parse_data(search_results, "search_results")
    
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
    
    personality = agent.personality
    trending_instructions = agent.trending_prompt
    format_template = agent.format_markdown
    
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

def generate_article_content(agent, prompt: str) -> str:
    """Genera el contenido del artículo usando ChatGPT"""
    try:
        system_message = agent.personality or "Eres un periodista especializado en tendencias argentinas. Responde ÚNICAMENTE con contenido en formato Markdown."
        
        response = agent.openai_client.chat.completions.create(
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

def markdown_to_html(md: str) -> str:
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

def process_article_data(agent_response: str) -> Dict[str, Any]:
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
    clean_markdown = re.sub(r'(?:\*\*)?CATEGORÍA:(?:\*\*)?.*\n', '', clean_markdown)
    clean_markdown = re.sub(r'^# .*?\n', '', clean_markdown, count=1)
    clean_markdown = clean_markdown.strip()
    
    paragraphs = [line.strip() for line in clean_markdown.split('\n') 
                 if line.strip() and not line.startswith('#') and not line.startswith('-')]
    excerpt = paragraphs[0][:150] + '...' if paragraphs else 'Artículo sobre tendencias'
    
    html_content = markdown_to_html(clean_markdown)
    
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

def _validate_and_parse_data(data: Any, data_type: str = "unknown") -> Dict[str, Any]:
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

def _extract_trend_title(trends_data: Dict[str, Any], position: int = 1) -> str:
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
