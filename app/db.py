from pymongo import MongoClient
from pymongo.database import Database
from fastapi import HTTPException
from load_env import load_env_files
from os import getenv

load_env_files()

MONGO_URI = getenv("MONGODB_URI")
MONGO_DB_NAME= "Finguru"

class MongoDB:
    client: MongoClient = None
    db: Database = None

db = MongoDB()

def get_database() -> Database:
    if db.db:
        return db.db
    raise HTTPException(status_code=500, detail="Database not connected")

def connect_to_mongo():
    db.client = MongoClient(host=MONGO_URI,
                            tls=True,
                            tlsAllowInvalidCertificates=True)
    db.db = db.client["Finguru-posts-db"]
    return db

def close_mongo_connection():
    if db.client:
        db.client.close()