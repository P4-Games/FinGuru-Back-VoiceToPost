from fastapi import FastAPI, UploadFile, Response
from fastapi.middleware.cors import CORSMiddleware
import openai
import os
from pathlib import Path

client = openai.OpenAI(
    api_key= "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"
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

@app.post("/convert_audio")
async def convert_audio(file: UploadFile):
    """
    Convert WAV file audio to text using Whisper
    """
    try:
        save_path = os.path.join("app", "uploads", "convert_audio.mp3")
        with open(save_path, "wb") as uploaded_file:
            uploaded_file.write(file.file.read())

        with open(save_path, "rb") as file:
            audio_content = file.read()
        try:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=Path(save_path),
                response_format="text"
            )

            return {"transcript": transcript}
        except Exception as e:
            return Response({"error": "Error de response OpenAI", "error_detail":e.args}, 400)
    except Exception as e:
        print(e)
        return {"error": "Ocurrió un error al procesar el audio.", "error_detail": e}