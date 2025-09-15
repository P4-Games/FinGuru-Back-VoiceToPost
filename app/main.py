import os
from fastapi import FastAPI, UploadFile, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
from agents.agents import iterate_agents
from utils.clean import clean_message
from utils.auth import validate_token
from load_env import load_env_files
from utils.middleware import check_subscription, check_sudo_api_key
from typing import Optional
from utils.trends_functions import TrendsAPI
from agents.automated_trends_agent import run_trends_agent, run_multi_trends_agents, run_trends_agent_with_guaranteed_news
from datetime import datetime

load_env_files()
openai = OpenAI(
  api_key=os.environ['OPENAI_API_KEY'],
)

app = FastAPI(
    title= "Fingurú API",
    version= "0.1"
)

origins = ["*"]  
methods = ["*"]  
headers = ["*"]  

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=methods,
    allow_headers=headers,
    allow_credentials=True,  
    expose_headers=["*"]     
)

from onlygpt import iterate_many_times

@app.get("/")
async def test():
    return "Test working"

@app.post("/convert_audio")
async def convert_audio(file: UploadFile):
    """
    Convert WAV file audio to text using Whisper
    """
    #print(file.content_type)
    save_path = os.path.join("app", file.filename)
    try:
        #listFormats = ["audio/wav","audio/mpeg","video/mp4", "audio/x-m4a"]
        #if (file.content_type not in listFormats):
        #   return Response("Error, el audio no tiene un formato valido", 400)
        
        # Guardar el archivo de audio con su nombre original
        with open(save_path, "wb") as uploaded_file:
            uploaded_file.write(file.file.read())

        # Abrir el archivo de audio guardado
        with open(save_path, "rb") as audio_file:
            transcript = openai.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=audio_file,
                response_format='text'
            )

    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        return Response(str(e), 400)

    finally:
        # Eliminar el archivo de audio
        if os.path.exists(save_path):
            os.remove(save_path)
    try:        
        new_message = iterate_many_times(transcript, 1)
    except Exception as e:
        return e
    return new_message

from algorand_functions import transfer_tokens

@app.post("/transfer_tokens")
async def _transfer_tokens(address_to_send:str, tokenAmount:float):
    return transfer_tokens(address_to_send, tokenAmount)
    
from db import connect_to_mongo
db = connect_to_mongo()
db = db.db

class ParamsToClaimTokens(BaseModel):
    id: int
    viewsAmount: int
    address: str
    
@app.post("/views")
async def views(data:ParamsToClaimTokens):
    id = data.id
    viewsAmount = data.viewsAmount
    address = data.address
    if viewsAmount < 0:
        return Response("Error, views must be greater than 0", 400)
    
    post = db["finguru"].find({"id":id})
    try:
        post = post[0]

        views_to_claim = viewsAmount - post["views"]
        if views_to_claim > 0:
            post["views"] = viewsAmount
            db["finguru"].update_one({"id":id}, {"$set": post})
        else:
            return Response("Error", 400)
    except:
        db["finguru"].insert_one({"id":id, "views":viewsAmount})
        views_to_claim = viewsAmount

    if views_to_claim <= 0:
        return Response("Error, no hay tokens para enviar", status_code=400)
    return transfer_tokens(address, views_to_claim*10**18)
    #return f"{views_to_claim} Tokens transfers to {address}"

class TextInput(BaseModel):
    text: str

class MultiAgentRequest(BaseModel):
    topic_position: Optional[int] = None
    token: Optional[str] = None

class TestTrendsAgentRequest(BaseModel):
    test_mode: str = "complete"  # "trends_only", "generate_only", "complete", "multi_agent"
    topic_position: Optional[int] = None
    force_refresh: Optional[bool] = False
    include_metrics: Optional[bool] = True
    agent_config: Optional[dict] = None
    topic_title: Optional[str] = None  # Para testear con un tópico específico
    dry_run: Optional[bool] = False  # Solo genera, no publica

@app.post("/convert_text_v2")
async def convert_text(data: TextInput, user: dict = Depends(check_subscription)):
    """
    Convierte texto de entrada en un nuevo mensaje procesado por múltiples agentes.

    Esta función toma un texto de entrada, lo procesa a través de una serie de agentes
    y devuelve un mensaje limpio y formateado.

    Args:
        data (TextInput): Un objeto que contiene el texto a procesar.
        user (dict): Información del usuario autenticado (inyectada por validate_token).

    Returns:
        str: El mensaje procesado y limpio.

    Raises:
        HTTPException: Si ocurre un error durante el procesamiento.
    """
    try:
        new_message = iterate_agents(f"Hecho, nota o tema: {data.text}")
    except Exception as e:
        return HTTPException(status_code=400, detail=str(e))
    return clean_message(new_message)

@app.post("/convert_audio_v2")
async def convert_audio(file: UploadFile, user: dict = Depends(check_subscription)):
    """
    Convierte un archivo de audio en texto y luego lo procesa con múltiples agentes.

    Esta función toma un archivo de audio, lo transcribe usando el modelo Whisper de OpenAI,
    y luego procesa la transcripción a través de una serie de agentes para generar un nuevo mensaje.

    Args:
        file (UploadFile): El archivo de audio a procesar.
        user (dict): Información del usuario autenticado (inyectada por validate_token).

    Returns:
        str: El mensaje procesado y limpio basado en la transcripción del audio.

    Raises:
        HTTPException: Si ocurre un error durante el procesamiento del audio o la transcripción.
    """
    save_path = os.path.join("app", file.filename)
    try:
        # Guardar el archivo de audio con su nombre original
        with open(save_path, "wb") as uploaded_file:
            uploaded_file.write(file.file.read())

        # Abrir el archivo de audio guardado
        with open(save_path, "rb") as audio_file:
            transcript = openai.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=audio_file,
                response_format='text'
            )

    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        return Response(str(e), 400)

    finally:
        # Eliminar el archivo de audio
        if os.path.exists(save_path):
            os.remove(save_path)

    try:
        transcript_text = transcript
        print(transcript_text)
        new_message = iterate_agents(f"Hecho, nota o tema: {transcript_text}")
        return clean_message(new_message)
    except Exception as e:
        return Response(str(e), 400)

trends_api = TrendsAPI()

@app.get("/trends")
async def get_trending_topics(
    geo: Optional[str] = "AR", 
    hours: Optional[int] = 24,
    language: Optional[str] = "es-419",
    no_cache: Optional[bool] = False,
    count: Optional[int] = 10,
    user: dict = Depends(check_subscription)
):
    """
    Devuelve los temas de tendencia actuales usando Google Trends a través de SerpAPI.
    
    Args:
        geo: Código de país de dos letras (ej. AR, US, ES)
        hours: Número de horas para las tendencias (24 por defecto)
        language: Código de idioma (es-419 para español de Latinoamérica)
        no_cache: Si se debe deshabilitar el caché
        count: Número de resultados a devolver
        user: Información del usuario autenticado (inyectada por validate_token)
        
    Returns:
        dict: Objeto JSON con las tendencias encontradas
    """
    return trends_api.get_trending_searches_by_category(
        geo=geo, 
        hours=hours,
        language=language,
        no_cache=no_cache,
        count=count
    )

@app.post("/run_trends_agent")
async def execute_trends_agent():
    """
    Ejecuta el agente automatizado que:
    1. Obtiene las tendencias actuales
    2. Busca información adicional del primer tema
    3. Genera un artículo completo usando ChatGPT
    4. Publica el artículo automáticamente en fin.guru
    
    Args:
        user: Información del usuario autenticado (inyectada por validate_token)
        
    Returns:
        dict: Resultado del proceso automatizado
    """
    try:
        result = run_trends_agent()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando agente: {str(e)}")

@app.get("/run_multi_trends_agents")
async def execute_multi_trends_agents(
    topic_position: Optional[int] = None,
    sudo_check: dict = Depends(check_sudo_api_key)
):
    """
    Ejecuta múltiples agentes automatizados que obtienen sus configuraciones desde la API.

    Esta función:
    1. Obtiene los agentes disponibles desde NEXT_PUBLIC_API_URL/agent-ias
    2. Inicializa cada agente con su configuración única (personality, trending, format_markdown)
    3. Ejecuta todos los agentes con la misma tendencia pero usando sus configuraciones específicas
    4. Publica los artículos automáticamente en fin.guru
    
    Headers requeridos:
        X-SUDO-API-KEY: Clave SUDO para acceso administrativo
    
    Args:
        topic_position: Posición específica de tendencia (1-10) o None para auto-selección por ChatGPT
        sudo_check: Verificación de SUDO_API_KEY (inyectada automáticamente)
        
    Returns:
        dict: Resultado del proceso multi-agente con resumen de éxitos y fallos
    """
    try:
        result = run_multi_trends_agents(topic_position=topic_position)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando multi-agentes: {str(e)}")

@app.get("/test_multi_trends_agents")
async def test_execute_multi_trends_agents(
    topic_position: Optional[int] = None,
    sudo_check: dict = Depends(check_sudo_api_key)
):
    """
    [TESTING] Ejecuta múltiples agentes automatizados SIEMPRE con tendencias frescas de Google.
    
    A diferencia de /run_multi_trends_agents, esta ruta de testing:
    - Siempre limpia el caché de tendencias antes de ejecutar
    - Fuerza la obtención de tendencias frescas desde Google
    - Útil para testing y desarrollo cuando se quieren evitar duplicados del caché
    
    Headers requeridos:
        X-SUDO-API-KEY: Clave SUDO para acceso administrativo
    
    Args:
        topic_position: Posición específica de tendencia (1-10) o None para auto-selección por ChatGPT
        sudo_check: Verificación de SUDO_API_KEY (inyectada automáticamente)
        
    Returns:
        dict: Resultado del proceso multi-agente con tendencias frescas
    """
    try:
        # Importar la función para limpiar caché
        from agents.automated_trends_agent import AutomatedTrendsAgent
        
        # Limpiar caché de tendencias antes de ejecutar
        AutomatedTrendsAgent.clear_trends_cache()
        print("🧹 Caché de tendencias limpiado para testing - obteniendo tendencias frescas")
        
        # Ejecutar el proceso con tendencias frescas
        result = run_multi_trends_agents(topic_position=topic_position)
        
        # Agregar información de que fue un test con tendencias frescas
        if isinstance(result, dict):
            result["test_mode"] = True
            result["fresh_trends_used"] = True
            result["cache_cleared"] = True
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando test multi-agentes: {str(e)}")


@app.post("/run_trends_agent_guaranteed_news")
async def execute_trends_agent_guaranteed_news(
    topic_position: Optional[int] = None,
    allow_no_image: Optional[bool] = False,
    sudo_check: dict = Depends(check_sudo_api_key)
):
    """
    🔥 Ejecuta el agente automatizado GARANTIZANDO la obtención de noticias.
    
    Esta función es similar a /run_trends_agent pero con garantías mejoradas:
    1. Obtiene las tendencias actuales
    2. 🚨 GARANTIZA obtener noticias (hasta 8 intentos con diferentes estrategias)
    3. Valida que las noticias tengan contenido suficiente
    4. Genera un artículo completo usando ChatGPT
    5. Publica el artículo automáticamente en fin.guru
    
    Headers requeridos:
        X-SUDO-API-KEY: Clave SUDO para acceso administrativo
        
    Args:
        topic_position: Posición específica de tendencia (1-10) o None para auto-selección
        allow_no_image: Si se permite publicar sin imagen como último recurso
        sudo_check: Verificación de SUDO_API_KEY (inyectada automáticamente)
        
    Returns:
        dict: Resultado del proceso con información de noticias garantizadas
        {
            "status": "success|error",
            "message": "Mensaje descriptivo",
            "trend_title": "Título de la tendencia usada",
            "news_guaranteed": true,
            "news_count": 5,
            "news_query_used": "Query que funcionó para obtener noticias",
            "news_search_type": "Tipo de búsqueda exitosa",
            "article_data": {...},
            "publish_result": {...},
            "timestamp": "2025-09-15T..."
        }
    """
    try:
        result = run_trends_agent_with_guaranteed_news(
            topic_position=topic_position, 
            allow_no_image=allow_no_image
        )
        
        # Agregar información adicional para el endpoint
        if isinstance(result, dict):
            result["endpoint"] = "/run_trends_agent_guaranteed_news"
            result["guaranteed_news_feature"] = True
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando agente con noticias garantizadas: {str(e)}")


@app.get("/test_guaranteed_news")
async def test_guaranteed_news_endpoint(
    topic_position: Optional[int] = None,
    allow_no_image: Optional[bool] = False
):
    """
    🧪 [TESTING] Endpoint GET simple para probar noticias garantizadas sin autenticación SUDO.
    
    Esta es una versión simplificada de /run_trends_agent_guaranteed_news para testing:
    - No requiere headers especiales ni autenticación SUDO
    - Útil para desarrollo y testing rápido
    - Ejecuta el proceso completo con noticias garantizadas
    
    Args:
        topic_position: Posición específica de tendencia (1-10) o None para auto-selección
        allow_no_image: Si se permite publicar sin imagen como último recurso
        
    Returns:
        dict: Resultado del proceso con información detallada de noticias
    
    Ejemplo de uso:
        GET /test_guaranteed_news?topic_position=1&allow_no_image=false
    """
    try:
        print(f"🧪 [TEST] Ejecutando agente con noticias garantizadas...")
        print(f"   Topic position: {topic_position}")
        print(f"   Allow no image: {allow_no_image}")
        
        result = run_trends_agent_with_guaranteed_news(
            topic_position=topic_position, 
            allow_no_image=allow_no_image
        )
        
        # Agregar información de testing
        if isinstance(result, dict):
            result["endpoint"] = "/test_guaranteed_news"
            result["test_mode"] = True
            result["guaranteed_news_feature"] = True
            result["timestamp_request"] = datetime.now().isoformat()
            
        print(f"🧪 [TEST] Resultado: {result.get('status', 'unknown')}")
        
        return result
    except Exception as e:
        error_detail = f"Error en test de agente con noticias garantizadas: {str(e)}"
        print(f"❌ [TEST] {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)
