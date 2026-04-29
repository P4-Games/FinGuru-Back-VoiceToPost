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
from typing import List, Optional
from utils.trends_functions import TrendsAPI
from agents.automated_trends_agent import (
    run_multi_trends_agents,
    run_multi_trends_agents_v2,
    clear_trends_cache_standalone,
    get_cache_status_standalone,
    get_trending_topics_cached,
)

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

@app.get("/health")
async def health_check():
    """
    Health check endpoint para Cloud Run
    """
    return {
        "status": "healthy",
        "message": "FinGuru API is running",
        "version": "0.1"
    }

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
db = None
try:
    db = connect_to_mongo().db
except Exception as e:
    print(f"⚠️ MongoDB no disponible en arranque: {str(e)}")
    print("⚠️ El endpoint /views quedará deshabilitado hasta que Mongo esté accesible")

class ParamsToClaimTokens(BaseModel):
    id: int
    viewsAmount: int
    address: str
    
@app.post("/views")
async def views(data:ParamsToClaimTokens):
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB no disponible. Endpoint /views deshabilitado en este entorno.")

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


class MultiAgentV2Request(BaseModel):
    topic_position: Optional[int] = None
    dry_run: bool = False
    correlation_id: Optional[str] = None
    agent_ids: Optional[List[int]] = None

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
    ⚠️ ENDPOINT LEGACY: Obtiene tendencias directamente de SerpAPI (consume cuota).
    
    RECOMENDACIÓN: Usa /trends/cached en su lugar para ahorrar llamadas API.
    
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

@app.get("/run_multi_trends_agents")
async def execute_multi_trends_agents(
    topic_position: Optional[int] = None,
    agent_id: Optional[int] = None,
    sudo_check: dict = Depends(check_sudo_api_key)
):
    """
    🚀 ENDPOINT OPTIMIZADO: Ejecuta múltiples agentes con caché inteligente de tendencias.

    Esta función optimizada:
    1. Obtiene los agentes disponibles desde NEXT_PUBLIC_API_URL/agent-ias
    2. Obtiene las tendencias UNA SOLA VEZ y las comparte entre todos los agentes
    3. Inicializa cada agente con su configuración única (personality, trending, format_markdown)
    4. Ejecuta todos los agentes con las mismas tendencias cached (o solo agent_id si se indica)
    5. Publica los artículos automáticamente en fin.guru
    
    ⚡ AHORRO DE API: En lugar de 5+ llamadas a SerpAPI, solo hace 1 llamada cada 30 minutos.
    
    Headers requeridos:
        X-SUDO-API-KEY: Clave SUDO para acceso administrativo
    
    Args:
        topic_position: Posición específica de tendencia (1-10) o None para auto-selección por ChatGPT
        agent_id: Si se informa, ejecuta únicamente ese agente (útil para cronjobs por agente)
        sudo_check: Verificación de SUDO_API_KEY (inyectada automáticamente)
        
    Returns:
        dict: Resultado del proceso multi-agente con resumen de éxitos y fallos
    """
    try:
        agent_ids = [agent_id] if agent_id is not None else None
        # Compatibilidad legacy para Google Scheduler: mismo endpoint, motor v2 interno.
        v2_result = run_multi_trends_agents_v2(
            topic_position=topic_position,
            dry_run=False,
            agent_ids=agent_ids,
        )

        if v2_result.get("status") == "success":
            execution = v2_result.get("execution", {})
            return {
                "status": "success",
                "message": (
                    f"Proceso multi-agente completado: "
                    f"{execution.get('successful', 0)} exitosos, "
                    f"{execution.get('skipped', 0)} omitidos, "
                    f"{execution.get('failed', 0)} fallidos"
                ),
                "results": v2_result.get("results", []),
                "summary": {
                    "total_agents": execution.get("agents_total", 0),
                    "successful": execution.get("successful", 0),
                    "failed": execution.get("failed", 0),
                    "skipped": execution.get("skipped", 0),
                    "requested_agent_ids": execution.get("requested_agent_ids"),
                },
                "legacy_endpoint": True,
                "engine_version": "v2",
                "correlation_id": v2_result.get("correlation_id"),
            }

        # Si se pidió un agente concreto, no usar legacy (ejecutaría a todos).
        if agent_id is not None:
            return v2_result

        # Fallback de seguridad al motor legacy si el v2 falla.
        legacy_result = run_multi_trends_agents(topic_position=topic_position)
        legacy_result["engine_version"] = "legacy-fallback"
        return legacy_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando multi-agentes: {str(e)}")


@app.post("/v2/trends/agents/run")
async def execute_multi_trends_agents_v2(
    payload: MultiAgentV2Request,
    sudo_check: dict = Depends(check_sudo_api_key)
):
    """
    Endpoint v2 (breaking) para ejecución de agentes de tendencias.

    Contrato nuevo con respuesta estructurada:
    - correlation_id por ejecución y por agente
    - metadata de selección de tema
    - prompt fingerprint
    - parámetros efectivos del LLM
    - score de profundidad y policy checks
    - resultado de publicación
    - agent_ids opcional: lista de IDs para ejecutar solo esos agentes (omitir = todos)
    """
    try:
        result = run_multi_trends_agents_v2(
            topic_position=payload.topic_position,
            dry_run=payload.dry_run,
            correlation_id=payload.correlation_id,
            agent_ids=payload.agent_ids,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando multi-agentes v2: {str(e)}")

@app.get("/cache/status")
async def get_cache_status_endpoint(user: dict = Depends(check_subscription)):
    """
    Obtiene el estado actual del caché de tendencias.
    
    Muestra información útil para optimizar el uso de SerpAPI:
    - Si hay datos en caché
    - Cuándo expira el caché actual
    - Número de tendencias almacenadas
    
    Returns:
        dict: Estado completo del caché incluyendo datos y timestamps
    """
    return get_cache_status_standalone()

@app.post("/cache/clear")
async def clear_cache_endpoint(user: dict = Depends(check_subscription)):
    """
    Limpia manualmente el caché de tendencias.
    
    Útil cuando:
    - Quieres forzar una nueva consulta a SerpAPI
    - Has cambiado configuraciones y necesitas datos frescos
    - Hay problemas con datos cached
    
    Returns:
        dict: Confirmación de que el caché fue limpiado
    """
    return clear_trends_cache_standalone()

@app.get("/trends/cached")
async def get_cached_trends(
    geo: Optional[str] = "AR", 
    hours: Optional[int] = 24,
    language: Optional[str] = "es-419",
    count: Optional[int] = 10,
    user: dict = Depends(check_subscription)
):
    """
    🚀 ENDPOINT OPTIMIZADO: Obtiene tendencias usando caché inteligente.
    
    Este endpoint utiliza un sistema de caché de 30 minutos para minimizar las llamadas a SerpAPI.
    Perfecto para conservar tus 100 llamadas mensuales.
    
    Args:
        geo: Código de país de dos letras (ej. AR, US, ES)
        hours: Número de horas para las tendencias (24 por defecto)
        language: Código de idioma (es-419 para español de Latinoamérica)
        count: Número de resultados a devolver
        user: Información del usuario autenticado
        
    Returns:
        dict: Tendencias con información de caché (cached: true/false)
    """
    return get_trending_topics_cached()