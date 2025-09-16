FROM python:3.11-slim

WORKDIR /app

# Copiar requirements primero para aprovechar el cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY app app

# Cloud Run usa el puerto de la variable de entorno PORT
EXPOSE 8080

# Configurar variables de entorno para producción
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Usar exec form para mejor handling de señales
CMD ["python", "app/start.py"]