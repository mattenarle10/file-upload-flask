from pymongo import MongoClient

def create_mongodb_connection(database_name, collection_name):
    try:
        uri = "<connection string URI>"
        client = MongoClient(uri)
        database = client["<database name>"]
        collection = database["<collection name>"]
        # start example code here
        # end example code here
        client.close()
    except Exception as e:
        raise Exception(
            "The following error occurred: ", e)

    return database, collection
