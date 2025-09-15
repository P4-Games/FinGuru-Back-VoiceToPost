FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app app

# Copia los archivos .env solo si existen, sin causar un error si no están.
COPY --chown=nonroot:nonroot .env* ./

EXPOSE 8080

CMD ["python", "app/start.py"]