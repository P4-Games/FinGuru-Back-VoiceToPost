FROM python:3.9-slim

WORKDIR /app

COPY app app
COPY requirements.txt requirements.txt

# Copiamos tanto .env como .env.local si existen
COPY .env* ./

RUN pip install -r requirements.txt

EXPOSE 8080

CMD ["python", "app/start.py"]