from pymongo import MongoClient
from src.config import MONGO_DB_URL

def mongo_operation():
    client = MongoClient(MONGO_DB_URL)
    db = client["myntra_reviews"]  # or whatever DB name is appropriate
    return db
