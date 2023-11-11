from fastapi import FastAPI, UploadFile, Response
from fastapi.middleware.cors import CORSMiddleware
import openai
import os
from pathlib import Path

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
   try:
       # Guardar el archivo de audio con su nombre original
       save_path = os.path.join("app", "uploads", file.filename)
       with open(save_path, "wb") as uploaded_file:
           uploaded_file.write(file.file.read())

       # Abrir el archivo de audio guardado
       with open(save_path, "rb") as f:
           # Transcribir el archivo de audio usando Whisper
           transcript = openai.Audio.transcribe(
               model="whisper-1",
               file=f
           )

   except Exception as e:
       print(e)
       return {"error": "Ocurrió un error al procesar el audio.", "error_detail": e.args}

   finally:
       # Eliminar el archivo de audio
       if os.path.exists(save_path):
           os.remove(save_path)

   new_message = iterate_many_times(transcript["text"], 1)
   return new_message

app.post("/transfer_tokens")
async def transfer_tokens(address_to_send:str, tokenAmount:float):
    from algorand_functions import transfer_tokens
    try:
        return transfer_tokens(address_to_send, tokenAmount)
    except Exception as e:
        return {"error": e}