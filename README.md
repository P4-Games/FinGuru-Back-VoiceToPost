# FinGurú MultiAgent
Esta API permite generar texto a partir de entradas de texto o audio utilizando un proceso de múltiples agentes. Hay dos endpoints disponibles:

**Nota:** Reemplazar env.example por .env.local con los valores correspondientes

## Instalación:
`pip install -r requirements.txt`

## Ejecutar
`python app/start.py`

## 1. Generación por texto

**Endpoint:** `/convert_text_v2`

**Método:** `POST`

**Descripción:** Este endpoint acepta una entrada de texto y la procesa a través de múltiples agentes para generar un nuevo texto.

### Cuerpo de la solicitud:

```json
{
    "text": "Hubo un choque en callao y santa fe, creo que el conductor estaba ebrio, no hubo muertos, ni heridos"
}
```
text (string): El texto de entrada que se desea procesar.

### Respuesta:
La respuesta será el texto generado en HTML después de pasar por los múltiples agentes.

## 2. Generación a través de un archivo de audio
**Endpoint:** `/convert_audio_v2`

**Método:** `POST`

**Descripción:** Este endpoint acepta un archivo de audio y lo transcribe utilizando Whisper. Luego, el texto transcrito se procesa a través de múltiples agentes para generar un nuevo texto.

**Cuerpo de la solicitud:**

> file (archivo, form-data): El archivo de audio que se desea transcribir y procesar.

### Respuesta:
La respuesta será el texto generado después de transcribir el audio y procesarlo a través de los múltiples agentes.

Tiempo de procesamiento de 1min a 3min

### Notas:
El archivo de audio debe estar en un formato compatible con Whisper (por ejemplo, WAV, MP3, etc.).