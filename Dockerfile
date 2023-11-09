FROM python:3.9-slim

WORKDIR /app

COPY app app
COPY requirements.txt requirements.txt
COPY .env .env

RUN pip install -r requirements.txt

EXPOSE 3000

CMD ["python", "app/start.py"]