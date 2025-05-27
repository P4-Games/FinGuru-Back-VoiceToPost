import os
from fastapi import FastAPI, UploadFile, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
from agents.agents import iterate_agents
from utils.clean import clean_message
from utils.auth import validate_token
from load_env import load_env_files
from utils.middleware import check_subscription
from typing import Optional
from utils.trends_functions import TrendsAPI

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
    count: Optional[int] = 20
):
    """
    Devuelve los temas de tendencia actuales usando Google Trends a través de SerpAPI.
    
    Args:
        geo: Código de país de dos letras (ej. AR, US, ES)
        hours: Número de horas para las tendencias (24 por defecto)
        language: Código de idioma (es-419 para español de Latinoamérica)
        no_cache: Si se debe deshabilitar el caché
        count: Número de resultados a devolver
        
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