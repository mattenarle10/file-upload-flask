
from mongodb_connection import create_mongodb_raw_connect
import os

client = create_mongodb_raw_connect()
db_name = os.getenv("MONGODB_DB_NAME")
database = client[db_name]
database.create_collection("file-uploads")

client.close()
