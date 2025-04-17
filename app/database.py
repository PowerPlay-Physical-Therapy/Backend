from pymongo import MongoClient
from pymongo.server_api import ServerApi
import os

def get_database():
    uri = os.getenv('MONGO_DB_URI')
    client = MongoClient(uri, server_api=ServerApi(version='1'))
    print("✅ Connected to Mongo. Databases:", client.list_database_names())  # DEBUG
    return client["Power_Play"]
