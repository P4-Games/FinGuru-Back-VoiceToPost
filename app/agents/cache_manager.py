"""
Módulo para el manejo del caché del sistema de tendencias automatizado.
Proporciona funcionalidades para cachear datos de tendencias y gestionar sesiones.
"""

from datetime import datetime, timedelta
from typing import Dict, Any


class CacheManager:
    """Gestor de caché para el sistema de tendencias automatizado"""
    
    # Cache estático para compartir entre instancias
    _trends_cache = {}
    _cache_timeout_minutes = 20
    
    # Cache estático para rastrear tendencias seleccionadas en la sesión multi-agente actual
    _selected_trends_session = set()
    _selected_positions_session = set()
    
    @classmethod
    def clear_trends_cache(cls):
        """Limpia el caché de tendencias manualmente"""
        cls._trends_cache.clear()
        print("Caché de tendencias limpiado manualmente")
    
    @classmethod
    def clear_session_cache(cls):
        """Limpia el caché de sesión de tendencias seleccionadas manualmente"""
        cls._selected_trends_session.clear()
        cls._selected_positions_session.clear()
        print("🔄 Caché de sesión limpiado - tendencias ya seleccionadas reiniciadas")
    
    @classmethod
    def get_cache_status(cls) -> Dict[str, Any]:
        """Obtiene el estado actual del caché"""
        cache_key = "trending_topics_AR"
        current_time = datetime.now()
        
        if cache_key not in cls._trends_cache:
            return {
                "status": "empty",
                "message": "No hay datos en caché"
            }
        
        cached_data = cls._trends_cache[cache_key]
        cache_time = datetime.fromisoformat(cached_data['cache_timestamp'])
        time_diff = current_time - cache_time
        remaining_time = timedelta(minutes=cls._cache_timeout_minutes) - time_diff
        
        return {
            "status": "active" if time_diff < timedelta(minutes=cls._cache_timeout_minutes) else "expired",
            "cached_at": cached_data['cache_timestamp'],
            "time_since_cache": str(time_diff),
            "remaining_time": str(remaining_time) if remaining_time.total_seconds() > 0 else "Expired",
            "cache_timeout_minutes": cls._cache_timeout_minutes,
            "selected_trends_count": len(cls._selected_trends_session),
            "selected_positions_count": len(cls._selected_positions_session)
        }
    
    @classmethod
    def is_cache_valid(cls, cache_key: str) -> bool:
        """Verifica si el caché es válido para una clave específica"""
        if cache_key not in cls._trends_cache:
            return False
        
        cached_data = cls._trends_cache[cache_key]
        cache_time = datetime.fromisoformat(cached_data['cache_timestamp'])
        current_time = datetime.now()
        time_diff = current_time - cache_time
        
        return time_diff < timedelta(minutes=cls._cache_timeout_minutes)
    
    @classmethod
    def get_cached_data(cls, cache_key: str) -> Dict[str, Any]:
        """Obtiene datos del caché si son válidos"""
        if cls.is_cache_valid(cache_key):
            return cls._trends_cache[cache_key]
        return {}
    
    @classmethod
    def set_cached_data(cls, cache_key: str, data: Dict[str, Any]) -> None:
        """Establece datos en el caché con timestamp"""
        cls._trends_cache[cache_key] = {
            **data,
            'cache_timestamp': datetime.now().isoformat()
        }
    
    @classmethod
    def add_selected_trend(cls, trend_title: str) -> None:
        """Añade una tendencia a la sesión de seleccionadas"""
        cls._selected_trends_session.add(trend_title)
    
    @classmethod
    def add_selected_position(cls, position: int) -> None:
        """Añade una posición a la sesión de seleccionadas"""
        cls._selected_positions_session.add(position)
    
    @classmethod
    def is_trend_selected(cls, trend_title: str) -> bool:
        """Verifica si una tendencia ya fue seleccionada en esta sesión"""
        return trend_title in cls._selected_trends_session
    
    @classmethod
    def is_position_selected(cls, position: int) -> bool:
        """Verifica si una posición ya fue seleccionada en esta sesión"""
        return position in cls._selected_positions_session
    
    @classmethod
    def get_selected_trends(cls) -> set:
        """Obtiene el conjunto de tendencias seleccionadas"""
        return cls._selected_trends_session.copy()
    
    @classmethod
    def get_selected_positions(cls) -> set:
        """Obtiene el conjunto de posiciones seleccionadas"""
        return cls._selected_positions_session.copy()