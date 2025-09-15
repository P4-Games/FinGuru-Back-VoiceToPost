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
from agents.automated_trends_agent import run_trends_agent, run_multi_trends_agents
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

@app.post("/test_trends_agent")
async def test_trends_agent(
    data: TestTrendsAgentRequest,
    sudo_check: dict = Depends(check_sudo_api_key)
):
    """
    Endpoint para testear diferentes aspectos del agente de tendencias.
    
    Permite probar por separado cada parte del proceso o el flujo completo
    con métricas de tiempo y configuraciones personalizadas.
    
    Headers requeridos:
        X-SUDO-API-KEY: Clave SUDO para acceso administrativo
    
    Args:
        data: Configuración del test con modo, posición, etc.
        sudo_check: Verificación de SUDO_API_KEY
        
    Returns:
        dict: Resultado detallado del test con métricas y datos generados
    """
    try:
        import time
        from agents.automated_trends_agent import AutomatedTrendsAgent
        
        start_time = time.time()
        test_result = {"status": "success", "test_mode": data.test_mode}
        
        # Crear instancia del agente con configuración personalizada
        agent = AutomatedTrendsAgent(data.agent_config)
        
        if data.test_mode == "trends_only":
            # Solo obtener tendencias
            trends_data = agent.get_trending_topics(force_refresh=data.force_refresh)
            test_result.update({
                "trends_data": trends_data,
                "trends_count": len(trends_data.get("trending_searches_argentina", []))
            })
            
        elif data.test_mode == "generate_only":
            # Solo generar contenido sin publicar
            if not data.topic_title:
                # Obtener tendencias primero
                trends_data = agent.get_trending_topics(force_refresh=data.force_refresh)
                if trends_data.get("status") != "success":
                    raise HTTPException(status_code=400, detail="No se pudieron obtener tendencias")
                    
                trending_searches = trends_data.get("trending_searches_argentina", [])
                if not trending_searches:
                    raise HTTPException(status_code=400, detail="No hay tendencias disponibles")
                    
                # Seleccionar tendencia
                if data.topic_position and 1 <= data.topic_position <= len(trending_searches):
                    selected_trend = trending_searches[data.topic_position - 1]
                    topic_title = selected_trend.get("title", "")
                else:
                    topic_title = trending_searches[0].get("title", "")
            else:
                topic_title = data.topic_title
                trends_data = {"mock": "usando título específico"}
            
            # Buscar información adicional
            search_results = agent.search_api.search_google_news(topic_title)
            
            # Generar contenido
            prompt = agent.content_processor.create_prompt(
                trends_data, search_results, topic_title, 
                data.topic_position or 1, data.agent_config or {}
            )
            
            agent_response = agent.content_processor.generate_article_content(prompt)
            article_result = agent.content_processor.process_article_data(agent_response)
            
            test_result.update({
                "topic_title": topic_title,
                "search_results_count": len(search_results.get("organic_results", [])),
                "article_generated": article_result.get("status") == "success",
                "article_data": article_result.get("data") if article_result.get("status") == "success" else None,
                "generation_prompt_length": len(prompt),
                "raw_response": agent_response if data.include_metrics else "omitido por brevedad"
            })
            
        elif data.test_mode == "complete":
            # Proceso completo pero con dry_run opcional
            if data.dry_run:
                # Simular el proceso completo sin publicar
                result = agent.run_automated_process(data.topic_position)
                # Modificar el resultado para indicar que fue dry_run
                if result.get("status") == "success":
                    result["status"] = "dry_run_success"
                    result["message"] = f"DRY RUN: {result.get('message', '')}"
                    # Remover datos de publicación
                    result.pop("publish_result", None)
                test_result = result
            else:
                # Proceso completo normal
                test_result = agent.run_automated_process(data.topic_position)
                
        elif data.test_mode == "multi_agent":
            # Testear proceso multi-agente
            if data.dry_run:
                raise HTTPException(status_code=400, detail="dry_run no está soportado en modo multi_agent")
            test_result = agent.run_multi_agent_process(data.topic_position)
            
        else:
            raise HTTPException(status_code=400, detail=f"Modo de test no válido: {data.test_mode}")
        
        # Agregar métricas si están habilitadas
        if data.include_metrics:
            end_time = time.time()
            test_result["metrics"] = {
                "execution_time_seconds": round(end_time - start_time, 2),
                "timestamp": datetime.now().isoformat(),
                "test_config": {
                    "test_mode": data.test_mode,
                    "topic_position": data.topic_position,
                    "force_refresh": data.force_refresh,
                    "dry_run": data.dry_run,
                    "has_custom_agent_config": data.agent_config is not None,
                    "custom_topic_title": data.topic_title
                }
            }
        
        return test_result
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"Error en test del agente de tendencias: {str(e)}"
        if data.include_metrics:
            error_detail += f"\n\nTraceback:\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)

@app.get("/test_trends_agent/cache_status")
async def get_trends_cache_status(sudo_check: dict = Depends(check_sudo_api_key)):
    """
    Obtiene el estado actual del caché del agente de tendencias.
    
    Headers requeridos:
        X-SUDO-API-KEY: Clave SUDO para acceso administrativo
        
    Returns:
        dict: Información detallada sobre el estado del caché
    """
    try:
        from agents.automated_trends_agent import get_cache_status
        return get_cache_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo estado del caché: {str(e)}")

@app.post("/test_trends_agent/clear_cache")
async def clear_trends_cache(sudo_check: dict = Depends(check_sudo_api_key)):
    """
    Limpia el caché de tendencias para forzar la obtención de datos frescos.
    
    Headers requeridos:
        X-SUDO-API-KEY: Clave SUDO para acceso administrativo
        
    Returns:
        dict: Confirmación de limpieza del caché
    """
    try:
        from agents.automated_trends_agent import clear_trends_cache
        return clear_trends_cache()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error limpiando caché: {str(e)}")

@app.get("/test_trends_agent/available_agents")
async def get_available_agents_for_test(sudo_check: dict = Depends(check_sudo_api_key)):
    """
    Obtiene la lista de agentes disponibles desde la API.
    
    Headers requeridos:
        X-SUDO-API-KEY: Clave SUDO para acceso administrativo
        
    Returns:
        dict: Lista de agentes disponibles con sus configuraciones
    """
    try:
        from agents.automated_trends_agent import get_available_agents
        return get_available_agents()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo agentes: {str(e)}")

@app.get("/test_trends_agent/recent_articles")
async def get_recent_articles_for_test(
    limit_per_agent: Optional[int] = 2,
    sudo_check: dict = Depends(check_sudo_api_key)
):
    """
    Obtiene artículos recientes de todos los agentes para análisis.
    
    Headers requeridos:
        X-SUDO-API-KEY: Clave SUDO para acceso administrativo
        
    Args:
        limit_per_agent: Número máximo de artículos por agente (default: 2)
        
    Returns:
        dict: Artículos recientes organizados por agente
    """
    try:
        from agents.automated_trends_agent import get_all_agents_recent_articles
        return get_all_agents_recent_articles(limit_per_agent)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo artículos recientes: {str(e)}")