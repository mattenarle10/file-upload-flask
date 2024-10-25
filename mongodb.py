from pymongo import MongoClient
import os

def create_mongodb_connection(collection_name):
    db_name = os.getenv("MONGODB_DB_NAME")
    uri = os.getenv("MONGODB_DB_CONNECTION_URI")

    try:
        client = MongoClient(uri)
        database = client[db_name]
        collection = database[collection_name]
        # start example code here
        # end example code here
        client.close()
    except Exception as e:
        raise Exception(
            "The following error occurred: ", e)

    return database, collection
