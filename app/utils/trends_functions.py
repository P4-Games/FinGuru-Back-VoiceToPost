from datetime import datetime
import os
from dotenv import load_dotenv
from serpapi import GoogleSearch

class TrendsAPI:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("SERPAPI_KEY")
        self.api_key2 = os.getenv("SERPAPI_KEY2")
        self.current_key_index = 0 

    def get_trending_searches_by_category(self, geo='AR', hours=24, language="es-419", no_cache=False, count=10):
        """
        Obtiene las tendencias de búsqueda usando SerpAPI con sistema de fallback.
        
        Args:
            geo: Código de país (ej. AR, US)
            hours: Horas para las tendencias (24 por defecto)
            language: Idioma para los resultados (es-419 por defecto para español latinoamericano)
            no_cache: Si debe desactivar el caché
            count: Número de resultados a devolver
        """
        max_retries = 2  # Intentar con ambas claves
        
        for attempt in range(max_retries):
            try:
                current_key = self._get_current_api_key()
                
                if not current_key:
                    return {"status": "error", "message": "No hay claves API válidas disponibles"}
                
                key_name = "SERPAPI_KEY" if self.current_key_index == 0 else "SERPAPI_KEY2"
                print(f"🔑 Intentando con {key_name} (intento {attempt + 1}/{max_retries})")
                
                params = {
                    "engine": "google_trends_trending_now",
                    "geo": geo,
                    "api_key": current_key
                }
                
                if hours:
                    params["hours"] = str(hours)
                    
                if language:
                    params["hl"] = language
                    
                if no_cache:
                    params["no_cache"] = "true"
                    
                search = GoogleSearch(params)
                results = search.get_dict()
                
                # Verificar si hay error en la respuesta
                if "error" in results:
                    error_msg = results.get("error", "")
                    print(f"❌ Error de SerpAPI con {key_name}: {error_msg}")
                    
                    # Si es error de límite o clave inválida, intentar con la siguiente clave
                    if self._is_rate_limit_error(error_msg) or self._is_api_key_error(error_msg):
                        if self._switch_to_backup_key():
                            continue  # Intentar con la siguiente clave
                        else:
                            return {"status": "error", "message": f"Todas las claves API han fallado. Último error: {error_msg}"}
                    else:
                        return {"status": "error", "message": error_msg}
                
                trending_topics = []
                if "trending_searches" in results:
                    for idx, item in enumerate(results["trending_searches"]):
                        if idx >= count:
                            break
                        
                        # Extraer información completa del item
                        trend_item = {"title": item}
                        
                        # Si el item es un diccionario con más información, extraerla
                        if isinstance(item, dict):
                            trend_item = {
                                "title": item.get("query", item.get("title", str(item))),
                                "query": item.get("query", ""),
                                "start_timestamp": item.get("start_timestamp"),
                                "active": item.get("active", True),
                                "search_volume": item.get("search_volume"),
                                "increase_percentage": item.get("increase_percentage"),
                                "categories": item.get("categories", [])
                            }
                        elif isinstance(item, str):
                            trend_item = {
                                "title": item,
                                "query": item,
                                "categories": []
                            }
                        
                        trending_topics.append(trend_item)
                
                print(f"✅ Éxito con {key_name}! Encontradas {len(trending_topics)} tendencias")
                
                return {
                    "status": "success",
                    "timestamp": datetime.now().isoformat(),
                    "geo": geo,
                    "trending_topics": trending_topics,
                    "count": len(trending_topics),
                    "used_key": key_name
                }
                
            except Exception as e:
                error_msg = str(e)
                key_name = "SERPAPI_KEY" if self.current_key_index == 0 else "SERPAPI_KEY2"
                print(f"❌ Excepción con {key_name}: {error_msg}")
                
                # Si es error de límite o clave inválida, intentar con la siguiente clave
                if self._is_rate_limit_error(error_msg) or self._is_api_key_error(error_msg):
                    if self._switch_to_backup_key():
                        continue  # Intentar con la siguiente clave
                    else:
                        return {"status": "error", "message": f"Todas las claves API han fallado. Último error: {error_msg}"}
                else:
                    # Para otros tipos de errores, fallar inmediatamente
                    return {"status": "error", "message": error_msg}
        
        return {"status": "error", "message": "Se agotaron todos los intentos con las claves API disponibles"}
    
    def _get_current_api_key(self):
        """Obtiene la clave API actual basada en el índice"""
        if self.current_key_index == 0:
            return self.api_key
        elif self.current_key_index == 1:
            return self.api_key2
        return None
    
    def _switch_to_backup_key(self):
        """Cambia a la clave de respaldo"""
        if self.current_key_index == 0 and self.api_key2:
            print("⚠️ SERPAPI_KEY falló, cambiando a SERPAPI_KEY2...")
            self.current_key_index = 1
            return True
        return False

    def _is_rate_limit_error(self, error_message):
        """Detecta si el error es por límite de llamadas"""
        error_indicators = [
            "rate limit", 
            "quota exceeded", 
            "limit exceeded",
            "too many requests",
            "usage limit",
            "monthly limit"
        ]
        return any(indicator in str(error_message).lower() for indicator in error_indicators)

    def _is_api_key_error(self, error_message):
        """Detecta si el error es por clave API inválida"""
        error_indicators = [
            "invalid api key",
            "unauthorized",
            "authentication failed",
            "api key not found"
        ]
        return any(indicator in str(error_message).lower() for indicator in error_indicators)

    def get_api_keys_status(self):
        """Obtiene el estado de las claves API"""
        status = {
            "primary_key": {
                "available": bool(self.api_key),
                "key_name": "SERPAPI_KEY",
                "is_current": self.current_key_index == 0
            },
            "backup_key": {
                "available": bool(self.api_key2),
                "key_name": "SERPAPI_KEY2", 
                "is_current": self.current_key_index == 1
            },
            "current_key_index": self.current_key_index
        }
        return status
    
    def reset_to_primary_key(self):
        """Resetea el índice para usar la clave primaria"""
        self.current_key_index = 0
        print("🔄 Reseteado a SERPAPI_KEY (clave primaria)")
