from fastapi import FastAPI, UploadFile, Response
from fastapi.middleware.cors import CORSMiddleware
import openai
import os

"""
client = openai.OpenAI(
    api_key= "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"
)
"""

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
        with open(save_path, "rb") as f:
            # Transcribir el archivo de audio usando Whisper
            try:
                transcript = openai.Audio.transcribe(
                    model="whisper-1",
                    file=f
                )
            except Exception as e:
                return e

    except Exception as e:
        return Response(e, 400)

    finally:
        # Eliminar el archivo de audio
        if os.path.exists(save_path):
            os.remove(save_path)
    try:        
        new_message = iterate_many_times(transcript["text"], 1)
    except Exception as e:
        return e
    return new_message

app.post("/transfer_tokens")
async def transfer_tokens(address_to_send:str, tokenAmount:float):
    from algorand_functions import transfer_tokens
    try:
        return transfer_tokens(address_to_send, tokenAmount)
    except Exception as e:
        return {"error": e}