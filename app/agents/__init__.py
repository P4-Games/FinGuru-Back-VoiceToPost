"""
Módulo de agentes automatizados para generación de contenido basado en tendencias.

Este módulo proporciona una arquitectura modular para la generación automatizada
de artículos basados en tendencias de Google Trends, utilizando múltiples agentes
especializados y servicios auxiliares.

Componentes principales:
- AutomatedTrendsAgent: Clase principal para el agente automatizado
- CacheManager: Gestión de caché para optimizar el rendimiento
- ArticleManager: Manejo de artículos y validación de contenido
- SearchServices: Servicios de búsqueda (Google News, Google Images)
- ContentProcessor: Procesamiento y generación de contenido
- ImageHandler: Manejo y validación de imágenes
- AgentManager: Gestión de múltiples agentes

Uso básico:
    from agents import AutomatedTrendsAgent
    
    # Proceso de un solo agente
    agent = AutomatedTrendsAgent()
    result = agent.run_automated_process()
    
    # Proceso multi-agente
    result = agent.run_multi_agent_process()

Funciones de conveniencia:
    from agents import (
        run_automated_agent_process,
        run_multi_agent_process,
        get_available_agents,
        clear_trends_cache,
        get_cache_status
    )
"""

from .automated_trends_agent import (
    AutomatedTrendsAgent,
    run_automated_agent_process,
    run_multi_agent_process,
    get_available_agents,
    get_all_agents_recent_articles,
    initialize_agents_from_api,
    clear_trends_cache,
    clear_session_cache,
    get_cache_status,
    get_trending_topics_cached
)

from .cache_manager import CacheManager
from .article_manager import ArticleManager
from .search_services import SearchServices
from .content_processor import ContentProcessor
from .image_handler import ImageHandler
from .agent_manager import AgentManager

# Versión del módulo
__version__ = "2.0.0"

# Exportar todas las clases y funciones principales
__all__ = [
    # Clase principal
    "AutomatedTrendsAgent",
    
    # Funciones de conveniencia
    "run_automated_agent_process",
    "run_multi_agent_process",
    "get_available_agents",
    "get_all_agents_recent_articles",
    "initialize_agents_from_api",
    "clear_trends_cache",
    "clear_session_cache",
    "get_cache_status",
    "get_trending_topics_cached",
    
    # Módulos auxiliares
    "CacheManager",
    "ArticleManager", 
    "SearchServices",
    "ContentProcessor",
    "ImageHandler",
    "AgentManager",
    
    # Información del módulo
    "__version__"
]
