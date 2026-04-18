from datetime import datetime
import os
from dotenv import load_dotenv
from serpapi import GoogleSearch
from typing import Any, Dict, List

class TrendsAPI:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("SERPAPI_KEY")
        self.api_key2 = os.getenv("SERPAPI_KEY2")
        self.current_key_index = 0 
        self.enable_related_context = self._is_truthy_env(
            os.getenv("ENABLE_SERPAPI_RELATED_CONTEXT", "true")
        )
        self.related_cache_ttl_seconds = max(
            60,
            int(os.getenv("RELATED_TRENDS_CACHE_TTL_SECONDS", "1200"))
        )
        self.related_items_limit = max(
            3,
            min(12, int(os.getenv("RELATED_TRENDS_ITEMS_LIMIT", "6")))
        )
        self._related_context_cache: Dict[str, Dict[str, Any]] = {}

    def get_trending_searches_by_category(self, geo='AR', hours=24, language="es-419", no_cache=False, count=16):
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

    @staticmethod
    def _is_truthy_env(value: str) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    def get_related_trend_context(
        self,
        query: str,
        geo: str = "AR",
        language: str = "es-419",
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Obtiene consultas y temas relacionados del trend seleccionado.

        Se consulta el engine google_trends con data_type RELATED_QUERIES y
        RELATED_TOPICS para enriquecer el contexto editorial antes de redactar.
        """
        normalized_query = (query or "").strip()
        if not normalized_query:
            return {
                "status": "error",
                "message": "Query vacía para contexto relacionado",
                "query": "",
                "related_queries": [],
                "related_topics": [],
            }

        if not self.enable_related_context:
            return {
                "status": "disabled",
                "message": "Contexto relacionado deshabilitado por configuración",
                "query": normalized_query,
                "related_queries": [],
                "related_topics": [],
            }

        cache_key = f"{geo}:{language}:{normalized_query.lower()}"
        now = datetime.now()

        if not force_refresh and cache_key in self._related_context_cache:
            cached = self._related_context_cache[cache_key]
            cached_at = cached.get("cached_at")
            if isinstance(cached_at, datetime):
                age_seconds = (now - cached_at).total_seconds()
                if age_seconds < self.related_cache_ttl_seconds:
                    cached_payload = dict(cached.get("payload", {}))
                    cached_payload["cache_hit"] = True
                    return cached_payload

        current_key = self._get_current_api_key()
        if not current_key:
            return {
                "status": "error",
                "message": "No hay claves API válidas disponibles",
                "query": normalized_query,
                "related_queries": [],
                "related_topics": [],
            }

        related_queries = self._fetch_related_items(
            query=normalized_query,
            geo=geo,
            language=language,
            data_type="RELATED_QUERIES",
            api_key=current_key,
        )
        related_topics = self._fetch_related_items(
            query=normalized_query,
            geo=geo,
            language=language,
            data_type="RELATED_TOPICS",
            api_key=current_key,
        )

        status = "success" if (related_queries or related_topics) else "empty"
        payload = {
            "status": status,
            "query": normalized_query,
            "timestamp": now.isoformat(),
            "geo": geo,
            "related_queries": related_queries[: self.related_items_limit],
            "related_topics": related_topics[: self.related_items_limit],
            "source": "serpapi_google_trends",
            "cache_hit": False,
        }

        self._related_context_cache[cache_key] = {
            "cached_at": now,
            "payload": payload,
        }

        return payload

    def _fetch_related_items(
        self,
        query: str,
        geo: str,
        language: str,
        data_type: str,
        api_key: str,
    ) -> List[Dict[str, Any]]:
        try:
            params = {
                "engine": "google_trends",
                "q": query,
                "geo": geo,
                "hl": language,
                "data_type": data_type,
                "api_key": api_key,
            }
            response = GoogleSearch(params).get_dict()
            if "error" in response:
                print(f"⚠️ Error obteniendo {data_type} para '{query}': {response.get('error')}")
                return []
            return self._extract_related_entries(response, data_type)
        except Exception as exc:
            print(f"⚠️ Excepción en {data_type} para '{query}': {str(exc)}")
            return []

    def _extract_related_entries(self, response: Dict[str, Any], data_type: str) -> List[Dict[str, Any]]:
        raw_items: List[Any] = []

        container_keys = ["related_queries", "related_topics", "rising", "top"]
        for key in container_keys:
            value = response.get(key)
            if isinstance(value, list):
                raw_items.extend(value)
            elif isinstance(value, dict):
                for nested_key in ["rising", "top", "queries", "topics", "items"]:
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, list):
                        raw_items.extend(nested_value)

        # Algunos payloads de SerpAPI anidan todo bajo `related_queries` o `related_topics`
        data_root_key = "related_queries" if data_type == "RELATED_QUERIES" else "related_topics"
        root_value = response.get(data_root_key)
        if isinstance(root_value, dict):
            for nested_key in ["rising", "top", "queries", "topics", "items"]:
                nested_value = root_value.get(nested_key)
                if isinstance(nested_value, list):
                    raw_items.extend(nested_value)

        normalized: List[Dict[str, Any]] = []
        seen_terms = set()
        for item in raw_items:
            parsed = self._normalize_related_entry(item)
            if not parsed:
                continue
            term_key = parsed["term"].strip().lower()
            if not term_key or term_key in seen_terms:
                continue
            seen_terms.add(term_key)
            normalized.append(parsed)

        return normalized

    @staticmethod
    def _normalize_related_entry(item: Any) -> Dict[str, Any]:
        if isinstance(item, str):
            term = item.strip()
            return {"term": term} if term else {}

        if not isinstance(item, dict):
            return {}

        term = (
            item.get("query")
            or item.get("topic_title")
            or item.get("title")
            or item.get("name")
            or item.get("topic")
            or item.get("value")
        )

        if isinstance(term, dict):
            term = term.get("query") or term.get("title") or term.get("name")

        if term is None:
            return {}

        term_text = str(term).strip()
        if not term_text:
            return {}

        normalized = {"term": term_text}

        if "value" in item:
            normalized["value"] = item.get("value")
        if "formattedValue" in item:
            normalized["formatted_value"] = item.get("formattedValue")
        if "link" in item:
            normalized["link"] = item.get("link")

        return normalized
