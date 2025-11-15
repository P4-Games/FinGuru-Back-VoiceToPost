import json
import re
import html
import string
import random
from typing import Dict, Any, List
import unicodedata

# LISTA DE PATRONES TEMÁTICOS A EXCLUIR (contextuales, triviales, sin valor investigativo)
EXCLUDED_TOPIC_PATTERNS = {
    # Efemérides y "noches temáticas"
    r'noche de los?\\s+',
    r'día de los?\\s+',
    r'semana de los?\\s+',
    r'mes de los?\\s+',
    r'festival de\\s+',
    r'fiesta de\\s+',
    r'celebración de\\s+',
    r'conmemoración de\\s+',
    
    # Paros y conflictos sin análisis profundo
    r'\\bparo de\\s+',
    r'\\bhuelga de\\s+',
    r'\\bparo nacional',
    r'\\bbloqueo de\\s+',
    r'\\bmarcha de\\s+',
    r'\\bprotesta\\b',
    
    # Eventos superficiales
    r'sorteo de\\s+',
    r'concurso de\\s+',
    r'giveaway',
    r'promo\\b',
    r'promoción\\b',
    
    # Cobertura de noticias puras (sin análisis)
    r'se robaron?\\b',
    r'fue detenido',
    r'murió|muere',
    r'accidente de\\s+',
    r'choque en\\s+',
}

# Lista de palabras clave que indican contenido de análisis profundo
# Expandida para incluir análisis económico, político y de tendencias internacionales
DEEP_ANALYSIS_KEYWORDS = {
    # Palabras de análisis general
    'análisis', 'impacto', 'estrategia', 'estrategias', 'causas', 'consecuencias',
    'investigación', 'investigamos', 'explicamos', 'entendemos', 'cómo', 'por qué',
    'implicaciones', 'perspectiva', 'tendencias', 'proyección', 'futuro',
    'contexto', 'antecedentes', 'comparación', 'diferencia', 'economía',
    
    # Palabras de impacto y relevancia
    'impacto económico', 'impacto social', 'riesgos', 'oportunidades',
    'desafíos', 'soluciones', 'alternativas', 'enfoque', 'abordaje',
    
    # Palabras específicas para análisis económico/político
    'equilibrio fiscal', 'instituciones', 'sostenibilidad', 'inflación',
    'inversión', 'confianza', 'mercado', 'competitividad', 'productividad',
    'crecimiento económico', 'estabilidad', 'reforma', 'política monetaria',
    'política fiscal', 'regulación', 'gobernanza', 'transparencia',
    'deuda pública', 'reservas internacionales', 'tipo de cambio', 'comercio exterior',
    
    # Palabras de ejemplos históricos y comparación internacional
    'comparación internacional', 'ejemplo histórico', 'precedente', 'similar a',
    'como en', 'en países', 'internacionalmente', 'históricamente',
    
    # Palabras que indican análisis de datos y fuentes
    'según', 'informó', 'reportó', 'indicó', 'reveló', 'demostró', 'mostró',
    'evidencia', 'datos', 'cifras', 'estadísticas', 'estudio', 'investigación',
    'encuesta', 'informe', 'análisis', 'conclusión', 'resultado'
}

def _is_topic_trivial_or_contextual(topic_title: str) -> bool:
    """Verifica si un tópico es trivial o contextual (debe ser rechazado).
    Retorna True si debe ser RECHAZADO (es trivial)."""
    topic_lower = topic_title.lower()
    
    # Verificar patrones excluidos
    for pattern in EXCLUDED_TOPIC_PATTERNS:
        if re.search(pattern, topic_lower, re.IGNORECASE):
            print(f"   ❌ Tópico '{topic_title}' rechazado: Patrón trivial detectado")
            return True
    
    # Verificar que no sea solo una cobertura de noticia (muy corto + poca sustancia)
    words = topic_title.split()
    if len(words) <= 3:
        # Validar que tenga al menos palabras que sugieran investigación
        has_analysis_keyword = any(keyword in topic_lower for keyword in DEEP_ANALYSIS_KEYWORDS)
        if not has_analysis_keyword:
            print(f"   ⚠️  Tópico '{topic_title}' muy corto y sin palabras de análisis profundo")
            # No es rechazado pero se marca como advertencia
    
    return False

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

def _normalize_title_capitalization(title: str) -> str:
    """Normaliza capitalización: solo primera letra mayúscula + nombres propios.
    Ejemplo: 'EL DÓLAR BLUE ALCANZA NUEVO MÁXIMO' -> 'El dólar blue alcanza nuevo máximo'"""
    
    if not title or len(title.strip()) == 0:
        return title
    
    # Diccionario de nombres propios comunes en Argentina
    proper_nouns = {
        'argentina', 'buenos aires', 'córdoba', 'mendoza', 'rosario',
        'tucumán', 'salta', 'misiones', 'gpt', 'gpt-4', 'ia', 'eeuu', 'usa',
        'banco central', 'bcra', 'afip', 'indec', 'senado', 'diputados',
        'congreso', 'gobierno', 'casa rosada', 'merval', 'bitcoin', 'ethereum',
        'apple', 'google', 'meta', 'amazon', 'tesla', 'microsoft', 'openai',
        'messi', 'maradona', 'milei', 'cristina'
    }
    
    # Palabras que deben mantenerse en minúsculas
    lowercase_words = {'de', 'la', 'los', 'las', 'el', 'un', 'una', 'y', 'o', 'en', 'a', 'del', 'al', 'por', 'para', 'con', 'sin', 'sobre', 'entre'}
    
    title_normalized = title.strip()
    words = title_normalized.split()
    result = []
    
    for i, word in enumerate(words):
        # Preservar puntuación
        punctuation = ''
        clean_word = word
        while clean_word and clean_word[-1] in '.,!?;:-':
            punctuation = clean_word[-1] + punctuation
            clean_word = clean_word[:-1]
        
        word_lower = clean_word.lower()
        
        # Primera palabra siempre con mayúscula
        if i == 0:
            result.append(clean_word[0].upper() + clean_word[1:].lower() + punctuation if clean_word else '')
        # Nombre propio
        elif word_lower in proper_nouns:
            result.append(clean_word[0].upper() + clean_word[1:].lower() + punctuation if clean_word else '')
        # Palabras a mantener en minúsculas
        elif word_lower in lowercase_words:
            result.append(clean_word.lower() + punctuation)
        # Resto en minúsculas
        else:
            result.append(clean_word.lower() + punctuation)
    
    return ' '.join(result)

def _validate_article_depth(article_content: str) -> Dict[str, Any]:
    """Valida que el artículo sea análisis profundo, no cobertura superficial.
    Versión mejorada con:
    - Peso aumentado en análisis keywords (50 puntos en lugar de 30)
    - Detección de párrafos sustanciales (70+ palabras, no 50+)
    - Validación de longitud mínima de párrafos
    - Mejor detección de contexto y evidencia
    
    Retorna {'is_valid': bool, 'issues': [list], 'depth_score': float}"""
    
    content_lower = article_content.lower()
    issues = []
    depth_score = 0.0
    
    # 1. ANÁLISIS KEYWORDS - Peso aumentado de 30 a 50 puntos
    has_analysis_keywords = sum(1 for keyword in DEEP_ANALYSIS_KEYWORDS if keyword in content_lower)
    # Más keywords = mayor puntuación, máx 50 puntos (3 puntos por keyword)
    analysis_score = min(has_analysis_keywords * 3, 50)
    depth_score += analysis_score
    
    # 2. MÚLTIPLES SECCIONES - 25 puntos si tiene 3+ secciones
    section_count = len(re.findall(r'^##\s+', article_content, re.MULTILINE))
    has_multiple_sections = section_count >= 3
    depth_score += 25 if has_multiple_sections else 0
    
    # 3. ESTADÍSTICAS Y DATOS - 20 puntos si contiene números/cifras
    has_statistics = bool(re.search(r'\d+(%|\$|M|B|k|mil|millones|%)?(?:\s|:|\.|-|,|$)', article_content))
    depth_score += 20 if has_statistics else 0
    
    # 4. CONTEXTO Y EVIDENCIA - 15 puntos
    has_context = bool(re.search(
        r'(según|informó|reportó|indicó|reveló|demostró|mostró|evidencia|'
        r'datos muestran|estudios demuestran|investigación|estudio|encuesta|'
        r'comparación internacional|ejemplo histórico|precedente)',
        content_lower
    ))
    depth_score += 15 if has_context else 0
    
    # 5. PÁRRAFOS SUSTANCIALES - Mejorado: mínimo 70 palabras, no 50
    # Divide el contenido en párrafos "reales" (con mínimo 70 palabras)
    paragraphs = []
    for para in article_content.split('\n\n'):
        para_clean = para.strip()
        # Excluir líneas de encabezado, listas cortas, etc.
        if not para_clean.startswith('#') and not para_clean.startswith('-'):
            word_count = len(para_clean.split())
            # Solo contar párrafos de 70+ palabras como "sustanciales"
            if word_count >= 70:
                paragraphs.append(para_clean)
    
    paragraph_count = len(paragraphs)
    # Máximo 10 puntos por párrafos sustanciales (mínimo 4 de 70+ palabras)
    depth_score += min(max(paragraph_count - 3, 0) * 2, 10)
    
    # 6. VALIDACIONES Y PUNTUACIÓN FINAL
    
    # Validación 1: Profundidad total
    if depth_score < 50:
        issues.append(f"Profundidad baja ({depth_score:.0f}/100): falta análisis profundo")
    
    # Validación 2: Análisis keywords
    if has_analysis_keywords < 8:
        issues.append(f"Análisis insuficiente: solo {has_analysis_keywords} palabras clave de análisis (mín 8)")
    
    # Validación 3: Párrafos sustanciales
    if paragraph_count < 4:
        issues.append(f"Desarrollo insuficiente: solo {paragraph_count} párrafos sustanciales (mín 4 de 70+ palabras)")
    
    # Validación 4: Múltiples secciones
    if not has_multiple_sections:
        issues.append(f"Estructura débil: solo {section_count} secciones (mín 3)")
    
    # Validación 5: Datos/estadísticas
    if not has_statistics:
        issues.append("Falta respaldo empírico: sin datos, cifras o estadísticas")
    
    # Validación 6: Contexto/Evidencia
    if not has_context:
        issues.append("Sin fuentes o contexto verificable")
    
    is_valid = len(issues) == 0 and depth_score >= 50
    
    return {
        'is_valid': is_valid,
        'issues': issues,
        'depth_score': depth_score,
        'analysis_keywords_count': has_analysis_keywords,
        'section_count': section_count,
        'has_multiple_sections': has_multiple_sections,
        'has_statistics': has_statistics,
        'has_context': has_context,
        'substantive_paragraph_count': paragraph_count,
        'analysis_score': analysis_score
    }

def _convert_html_to_markdown(html_content: str) -> str:
    """Convierte HTML a Markdown para el format_markdown del agente.
    Maneja etiquetas comunes de editors HTML (Quill, DraftJS, etc.)"""
    
    if not html_content:
        return ""
    
    # Unescape HTML entities
    md = html.unescape(html_content)
    
    # Convertir tags HTML a Markdown
    conversions = [
        # Párrafos
        (r'<p>(.*?)</p>', r'\1'),
        
        # Títulos
        (r'<h1>(.*?)</h1>', r'# \1'),
        (r'<h2>(.*?)</h2>', r'## \1'),
        (r'<h3>(.*?)</h3>', r'### \1'),
        (r'<h4>(.*?)</h4>', r'#### \1'),
        
        # Énfasis
        (r'<strong>(.*?)</strong>', r'**\1**'),
        (r'<b>(.*?)</b>', r'**\1**'),
        (r'<em>(.*?)</em>', r'*\1*'),
        (r'<i>(.*?)</i>', r'*\1*'),
        
        # Listas
        (r'<li>(.*?)</li>', r'- \1'),
        (r'<ul>(.*?)</ul>', r'\1'),
        (r'<ol>(.*?)</ol>', r'\1'),
        
        # Saltos de línea
        (r'<br\s*/?>', r'\n'),
        (r'<br/>', r'\n'),
        
        # Enlaces (si existen)
        (r'<a\s+href=["\']([^"\']*)["\']>(.*?)</a>', r'[\2](\1)'),
    ]
    
    for pattern, replacement in conversions:
        md = re.sub(pattern, replacement, md, flags=re.IGNORECASE | re.DOTALL)
    
    # Limpiar tags residuales
    md = re.sub(r'<[^>]+>', '', md)
    
    # Limpiar espacios excesivos
    md = re.sub(r'\n{3,}', '\n\n', md)
    md = md.strip()
    
    return md

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
    
    # Mejorada conversión de formato_markdown (HTML → Markdown)
    if format_template and format_template.strip():
        format_template = _convert_html_to_markdown(format_template)
    else:
        # Template por defecto si no está disponible
        format_template = """
# [Título conciso, sobrio]

[Introducción contextual - párrafo que establezca el contexto y la pregunta central]

## 📊 Panorama actual

[Análisis de la situación presente con datos y contexto - 70-100 palabras]

## 🌍 Comparación internacional

[Ejemplos de otros países y cómo han abordado situaciones similares - 70-100 palabras]

## 📈 Implicancias [específicas del tema]

[Análisis de consecuencias sociales, políticas o económicas - 70-100 palabras]

[Conclusión con proyección o advertencia - 70-100 palabras]"""

    # Construcción del prompt mejorado con énfasis en análisis riguroso
    prompt = f"""{personality}

📊 CONTEXTO DE TENDENCIAS (últimas 24h):
{trends_text}

{additional_info}

═══════════════════════════════════════════════════════════════════════════

TÓPICO ASIGNADO PARA ANÁLISIS: "{selected_trend}"

═══════════════════════════════════════════════════════════════════════════

CATEGORÍAS DISPONIBLES (debes elegir UNA):
1. "Economía y Finanzas" - economía, dólar, inflación, bancos, inversiones, mercados, empresas, deuda, política fiscal
2. "Tecnología e Innovación" - tecnología, apps, internet, IA, smartphones, software, startups, transformación digital
3. "Política y Sociedad" - política, gobierno, elecciones, leyes, sociedad, instituciones, gobernanza, regulación
4. "Entretenimiento y Bienestar" - deportes, famosos, música, TV, salud, lifestyle, turismo, bienestar

═══════════════════════════════════════════════════════════════════════════

🎯 MISIÓN CRÍTICA - ANÁLISIS PROFUNDO O RECHAZO:

FinGuru publica SOLO análisis profundo de investigación. Tu artículo SERÁ VALIDADO 
automáticamente y RECHAZADO si:
  ❌ Tiene menos de 4 secciones principales
  ❌ Tiene menos de 1500 palabras totales
  ❌ Tiene párrafos menores a 70 palabras
  ❌ Tiene menos de 5 palabras clave de análisis (análisis, impacto, contexto, estrategia, etc)
  ❌ No incluye mínimo 5 datos, cifras o estadísticas específicas
  ❌ No compara con otros países o precedentes históricos
  ❌ Suena a noticia (cobertura superficial) en lugar de análisis

═══════════════════════════════════════════════════════════════════════════

📋 ESTRUCTURA OBLIGATORIA (EXACTA):

# Título sobrio (máx 12 palabras, primera letra mayúscula)

**CATEGORÍA:** [Economía y Finanzas / Tecnología e Innovación / Política y Sociedad / Entretenimiento y Bienestar]

[INTRODUCCIÓN: 80-120 palabras. Pregunta central + contexto + por qué importa ahora]

## Situación actual y contexto

[80-120 palabras. Datos específicos, cifras verificables, fuentes ("según", "reportó", "indicó"). NO generalizaciones.]

## Análisis de causas y factores

[80-120 palabras. Por qué ocurre esto. Causas raíz. Conexiones causales. Contexto histórico.]

## Comparación internacional e impacto global

[80-120 palabras. OBLIGATORIO: precedentes en otros países, cómo lo manejan, lecciones internacionales. 
Incluir ejemplos específicos con datos (ej: "En Chile..." / "Históricamente en 2019...")]

## Implicancias y consecuencias

[80-120 palabras. Impacto económico/social/político específico. Cómo afecta a Argentina, ciudadanos, empresas.]

## Perspectiva estratégica y outlook futuro

[80-120 palabras. Proyección a futuro. Riesgos y oportunidades. Recomendaciones estratégicas o reflexión final.]

═══════════════════════════════════════════════════════════════════════════

🔥 CONTENIDO REQUERIDO (TODO OBLIGATORIO):

PALABRAS CLAVE DE ANÁLISIS (debes incluir 15+):
✓ análisis / investigación / estudio
✓ impacto / consecuencias / implicaciones
✓ estrategia / contexto / antecedentes
✓ causas / factores / drivers
✓ comparación / internacional / precedente
✓ datos / cifras / estadísticas / demostró / reveló / indicó
✓ evidencia / perspectiva / tendencia
✓ Usa estas palabras naturalmente en cada sección

DATOS Y CIFRAS (MÍNIMO 5):
✓ Cifras específicas con fuente (ej: "según INDEC, la inflación fue X%")
✓ Comparativas numéricas (ej: "50% más que en 2023")
✓ Datos internacionales (ej: "en Brasil alcanzó X, mientras que en Argentina Y")
✓ Históricos (ej: "a diferencia de 2019 cuando fue 20%")
✓ NO números genéricos, TODOS con contexto y fuente

ANÁLISIS PROFUNDO:
✓ Causas: ¿por qué ocurre? ¿qué factores lo provocan?
✓ Contexto: ¿qué pasó antes? ¿precedentes históricos?
✓ Comparación: ¿cómo se maneja en otros países? ¿precedentes internacionales?
✓ Impacto: ¿qué consecuencias tiene? ¿para quién? ¿cuantificable?
✓ Conclusión: ¿qué significa esto? ¿qué esperar?

═══════════════════════════════════════════════════════════════════════════

📐 ESTÁNDARES DE VALIDACIÓN (PARA APROBACIÓN):

Profundidad Score (debe ser 60+):
  + 3 puntos por cada palabra clave de análisis (máx 50 puntos)
  + 25 puntos si tiene 4+ secciones principales
  + 20 puntos si tiene 5+ datos/cifras específicas
  + 15 puntos si incluye contexto internacional o comparativo

Párrafos Sustanciales:
  ✓ Cada párrafo DEBE tener 70-120 palabras (validado automáticamente)
  ✓ Mínimo 4 párrafos de análisis (no contando introducción)
  ✓ NO párrafos cortos, NO listas, NO fragmentos

═══════════════════════════════════════════════════════════════════════════

❌ NO HAGAS (Causará rechazo automático):

• "El dólar subió 2%" → Falta análisis
• Párrafos menores a 70 palabras
• Una sola sección de contenido
• Cobertura de noticias sin contexto
• Datos sin fuente o contexto
• Conclusiones vagas o sin sustancia
• Menos de 4 secciones principales
• Olvida comparación internacional
• Títulos genéricos como "Análisis del tema"
• Artículos menores a 1200 palabras

✅ SÍ HAZ (Será aprobado):

• "Por qué el dólar se devalúa en contextos de inflación dual: comparación vs Brasil, Chile y precedentes históricos"
• Párrafos de 80-120 palabras con datos específicos
• Mínimo 5 secciones temáticas bien desarrolladas
• Análisis de causas, consecuencias, impacto
• Datos con fuente: "según BCRA, las reservas cayeron X%"
• Conclusión con outlook estratégico
• Comparación explícita internacional
• Artículos de 1500+ palabras
• Mínimo 8 palabras clave de análisis distribuidas

═══════════════════════════════════════════════════════════════════════════

🚀 INSTRUCCIONES FINALES:

1. ESTRUCTURA: Escribe exactamente 6 secciones (intro + 5 ## secciones)
2. PROFUNDIDAD: Cada sección 80-120 palabras, 4+ datos/cifras, comparación internacional
3. ANÁLISIS: Incluye causas, contexto, impacto, perspectiva futura
4. PALABRAS CLAVE: Usa naturalmente análisis, impacto, contexto, estrategia, comparación, etc.
5. TOTAL: 1500+ palabras con múltiples datos y cifras
6. FORMATO: Solo Markdown, línea 1 = título, línea 2 = categoría
7. VALIDACIÓN: Tu artículo pasará por análisis de profundidad automático - cumple todo

RECUERDA: Si tu artículo no cumple estos requisitos, será RECHAZADO automáticamente.
Tu misión es generar análisis profundo de 1500+ palabras con mínimo 5 datos/cifras,
comparación internacional, y múltiples secciones temáticas. NO cobertura de noticias.

═══════════════════════════════════════════════════════════════════════════
1. "Economía y Finanzas" - economía, dólar, inflación, bancos, inversiones, mercados, empresas, deuda, política fiscal
2. "Tecnología e Innovación" - tecnología, apps, internet, IA, smartphones, software, startups, transformación digital
3. "Política y Sociedad" - política, gobierno, elecciones, leyes, sociedad, instituciones, gobernanza, regulación
4. "Entretenimiento y Bienestar" - deportes, famosos, música, TV, salud, lifestyle, turismo, bienestar

═══════════════════════════════════════════════════════════════════════════

🎯 ENFOQUE EDITORIAL - ANÁLISIS RIGUROSO, NO COBERTURA DE NOTICIAS:

FinGuru es un portal de ANÁLISIS PROFUNDO E INVESTIGACIÓN, NO de noticias superficiales.
Tu contenido DEBE ser riguroso, equilibrado, fundamentado en datos y perspectiva histórica.

❌ NO ESCRIBAS (Superficial):
   • "El dólar subió 2%" → Coverede vacía de análisis
   • "Se jugó el clásico River-Boca" → Noticia sin contexto investigativo
   • "Messi gana Balón de Oro" → Información sin análisis económico/social
   • Párrafos menores a 70 palabras → Desarrollo insuficiente
   • Un párrafo sobre el tema → Análisis incompleto

✅ ESCRIBE (Análisis riguroso):
   • "Por qué el equilibrio fiscal es prerequisito para la confianza inversora"
   • "Impacto económico del transporte en la estabilidad macroeconómica de regiones"
   • "Cómo los acuerdos internacionales afectan competitividad argentina vs Brasil/Chile"
   • Párrafos de 70-100 palabras con análisis → Desarrollo sustancial
   • Mínimo 5 párrafos argumentativos → Profundidad garantizada

═══════════════════════════════════════════════════════════════════════════

📋 ESTRUCTURA REQUERIDA (Adaptada a tu estilo):

{format_template if format_template and format_template.strip() else '''
# [Título conciso y sobrio - primera letra mayúscula + nombres propios]

[Introducción: Plantea la pregunta central y contexto. 70-100 palabras]

## 📊 Panorama actual

[Análisis de la situación presente con datos concretos. 70-100 palabras. 
Incluir: cifras, hechos verificables, fuentes.]

## 🌍 Comparación internacional

[Ejemplos de otros países. Cómo han abordado situaciones similares. 70-100 palabras.
Incluir: precedentes internacionales, lecciones históricas.]

## 📈 Implicancias [específicas del tema]

[Análisis de consecuencias: sociales, políticas, económicas. 70-100 palabras.
Incluir: impacto calculable, datos de impacto.]

## 🔮 Perspectiva y advertencias futuras

[Conclusión con proyección. Perspectiva de futuro o advertencias. 70-100 palabras.
Incluir: tendencias predictas, recomendaciones, outlook.]
'''}

═══════════════════════════════════════════════════════════════════════════

📐 REGLAS ESTRICTAS DE CALIDAD (NO NEGOCIABLES):

CONTENIDO Y ANÁLISIS:
✓ MUST: Cada sección debe tener 70-100 palabras MÍNIMO (no 50-100)
✓ MUST: Mínimo 5 párrafos sustanciales de análisis (no 4)
✓ MUST: Comparación internacional O ejemplos históricos (obligatorio)
✓ MUST: 3+ datos/cifras concretas con contexto de dónde vienen
✓ MUST: Fuentes verificables ("según", "reportó", "demostró", "datos indican")
✓ MUST: Análisis de causas, contexto, consecuencias e impacto
✓ PROHIBIDO: Párrafos cortos (<70 palabras) o listas superficiales

ESTRUCTURA MARKDOWN:
✓ MUST: Título sobrio (primera letra mayúscula + nombres propios)
✓ MUST: Mínimo 4 secciones ## (no meros ## sin contenido)
✓ MUST: Cada sección debe desarrollar un aspecto diferente del análisis
✓ MUST: Usar **negrita** para datos, cifras, nombres propios, conceptos clave
✓ MUST: Categoría EXACTAMENTE una de las 4 opciones (no inventar)

TONO Y ESTILO:
✓ Formal, profesional, periodístico pero educativo
✓ Crítico pero equilibrado (sin sesgos ideológicos fuertes)
✓ Técnico solo cuando es imprescindible
✓ Directo, pausado, reflexivo
✓ Frases modelo: "Sin instituciones sólidas, no hay confianza"
✓ Evitar exageraciones, mantener rigor analítico

FORMATO FINAL:
✓ 1200-1400 palabras en total (no 1100-1200, necesitas más desarrollo)
✓ Responde ÚNICAMENTE con el Markdown
✓ SIN explicaciones adicionales antes o después
✓ SIN "CATEGORÍA: [...]" dentro del artículo (agrégalo como comentario HTML o en segunda línea)
✓ Línea 1: # Título
✓ Línea 2: **CATEGORÍA:** [exacta]
✓ Línea 3+: Desarrollo

═══════════════════════════════════════════════════════════════════════════

🚀 INSTRUCCIONES FINALES:

1. Lee cuidadosamente el tópico: "{selected_trend}"
2. Elige la CATEGORÍA que mejor se ajuste
3. Analiza profundamente: ¿por qué importa? ¿contexto? ¿comparación? ¿impacto?
4. Busca datos, cifras, precedentes internacionales
5. Estructura con mínimo 5 párrafos sustanciales (70+ palabras cada uno)
6. Escribe solo el Markdown final
7. No incluyas auto-evaluaciones ni explicaciones

RECUERDA: FinGuru requiere ANÁLISIS RIGUROSO, no noticias. Tu trabajo es explicar 
POR QUÉ algo importa, NO simplemente QUÉ pasó.

═══════════════════════════════════════════════════════════════════════════"""

    return prompt

def generate_article_content(agent, prompt: str) -> str:
    """Genera el contenido del artículo usando ChatGPT con parámetros optimizados.
    
    Parámetros ajustados para mayor rigor y consistencia:
    - temperature: 0.6 (más enfocado, menos aleatorio que 0.7)
    - top_p: 0.9 (variedad controlada)
    - frequency_penalty: 0.3 (evita repeticiones)
    - presence_penalty: 0.1 (fomenta nuevo contenido)
    """
    try:
        system_message = agent.personality or "Eres un periodista especializado en tendencias argentinas. Responde ÚNICAMENTE con contenido en formato Markdown."
        
        response = agent.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1400,  # Aumentado de 1200 para permitir más desarrollo
            temperature=0.6,   # Reducido de 0.7 para mayor rigor
            top_p=0.9,         # Controlado para variedad
            frequency_penalty=0.3,  # Evita repeticiones
            presence_penalty=0.1    # Fomenta contenido nuevo
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
    """Procesa la respuesta del agente para la API de fin.guru.
    Incluye normalización de capitalización de títulos."""
    lines = agent_response.split('\n')
    
    title_line = next((line for line in lines if line.startswith('# ')), None)
    title = title_line.replace('# ', '').strip() if title_line else 'Artículo de Tendencia'
    
    # Normalizar capitalización del título (solo 1ª letra mayúscula + nombres propios)
    title = _normalize_title_capitalization(title)
    
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
