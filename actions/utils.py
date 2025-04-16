import os
from bson import ObjectId
from flask import send_file, send_from_directory, jsonify
from db.mongodb.mongodb_connection import create_mongodb_connection

def allowed_file(filename, allowed_extensions=None):
    """
    Check if a file has an allowed extension
    """
    if allowed_extensions is None:
        allowed_extensions = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def add_cache_headers(response):
    """
    Add cache control headers to a response
    """
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

def serve_file(app_config, name):
    """
    Serve a file from the upload folder
    """
    return send_from_directory(app_config["UPLOAD_FOLDER"], name)

def get_image_by_id(image_id):
    """
    Get an image by its MongoDB ID
    """
    client, database, collection = create_mongodb_connection("file-uploads")
    image_doc = collection.find_one({"_id": ObjectId(image_id)})
    client.close()
    
    if image_doc and "file_path" in image_doc:
        file_path = os.path.join(os.environ["UPLOAD_DIRECTORY"], image_doc["file_path"])
        return send_file(file_path)
    else:
        return "Image not found", 404

def clear_mongodb_collection():
    """
    Clear all documents from the MongoDB collection
    """
    try:
        client, database, collection = create_mongodb_connection("file-uploads")
        result = collection.delete_many({})
        deleted_count = result.deleted_count
        client.close()
        return jsonify({"message": f"Deleted {deleted_count} documents from MongoDB", "success": True})
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}", "success": False})
