from datetime import datetime
import os
from dotenv import load_dotenv
from serpapi import GoogleSearch

class TrendsAPI:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("SERPAPI_KEY")

    def get_trending_searches_by_category(self, geo='AR', hours=24, language="es-419", no_cache=False, count=10):
        """
        Obtiene las tendencias de búsqueda usando SerpAPI.
        
        Args:
            geo: Código de país (ej. AR, US)
            hours: Horas para las tendencias (24 por defecto)
            language: Idioma para los resultados (es-419 por defecto para español latinoamericano)
            no_cache: Si debe desactivar el caché
            count: Número de resultados a devolver
        """
        try:
            params = {
                "engine": "google_trends_trending_now",
                "geo": geo,
                "api_key": self.api_key
            }
            
            if hours:
                params["hours"] = str(hours)
                
            if language:
                params["hl"] = language
                
            if no_cache:
                params["no_cache"] = "true"
                
            search = GoogleSearch(params)
            results = search.get_dict()
            
            trending_topics = []
            if "trending_searches" in results:
                for idx, item in enumerate(results["trending_searches"]):
                    if idx >= count:
                        break
                    trending_topics.append({"title": item})
            
            return {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "geo": geo,
                "trending_topics": trending_topics,
                "count": len(trending_topics)
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
