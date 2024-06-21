# FinGurú MultiAgent

Esta API permite generar texto a partir de entradas de texto o audio utilizando un proceso de múltiples agentes. Hay dos endpoints disponibles:

**Nota:** Reemplazar env.example por .env.local con los valores correspondientes

## Instalación:
```
pip install -r requirements.txt
```

## Ejecutar
```
python app/start.py
```

## URL Base
https://multiagent.fin.guru/

## Autenticación

Todos los endpoints requieren autenticación usando un Bearer token. Incluye el siguiente header en todas tus solicitudes:

```
Authorization: Bearer <token>
```

El token debe ser válido y pertenecer a un usuario registrado como tester. Los tokens inválidos o usuarios no autorizados recibirán un error 401.

## Endpoints

### 1. Generación por texto

**Endpoint:** `/convert_text_v2`

**Método:** `POST`

**Descripción:** Este endpoint acepta una entrada de texto y la procesa a través de múltiples agentes para generar un nuevo texto.

#### Cuerpo de la solicitud:

```json
{
    "text": "Hubo un choque en callao y santa fe, creo que el conductor estaba ebrio, no hubo muertos, ni heridos"
}
```

- `text` (string): El texto de entrada que se desea procesar.

#### Headers:
```
Authorization: Bearer <tu_token_aquí>
Content-Type: application/json
```

#### Respuesta:
La respuesta será el texto generado en HTML después de pasar por los múltiples agentes.

### 2. Generación a través de un archivo de audio

**Endpoint:** `/convert_audio_v2`

**Método:** `POST`

**Descripción:** Este endpoint acepta un archivo de audio y lo transcribe utilizando Whisper. Luego, el texto transcrito se procesa a través de múltiples agentes para generar un nuevo texto.

#### Cuerpo de la solicitud:

- `file` (archivo, form-data): El archivo de audio que se desea transcribir y procesar.

#### Headers:
```
Authorization: Bearer <tu_token_aquí>
Content-Type: multipart/form-data
```

#### Respuesta:
La respuesta será el texto generado después de transcribir el audio y procesarlo a través de los múltiples agentes.

Tiempo de procesamiento estimado: de 1 a 3 minutos.

### Notas:
- El archivo de audio debe estar en un formato compatible con Whisper (por ejemplo, WAV, MP3, etc.).
- Asegúrate de incluir el token de autenticación en todas las solicitudes.
- Si recibes un error 401, verifica que tu token sea válido y que tu usuario esté registrado como tester.

