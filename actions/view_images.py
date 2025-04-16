import os
import psycopg2
from flask import url_for, render_template, jsonify
from db.mongodb.mongodb_connection import create_mongodb_connection

def get_uploaded_images():
    """
    Get all uploaded images with product details
    """
    # Connect to PostgreSQL to get all product details
    conn = psycopg2.connect(
        host=os.environ["POSTGRESQL_DB_HOST"],
        database=os.environ["POSTGRESQL_DB_DATABASE_NAME"],
        user=os.environ['POSTGRESQL_DB_USERNAME'],
        password=os.environ['POSTGRESQL_DB_PASSWORD']
    )
    cur = conn.cursor()
    
    # Get all products with their details
    cur.execute("""
        SELECT p.id, p.name, p.stock_count, p.image_mongodb_id 
        FROM products p
    """)
    products = cur.fetchall()
    
    # Get all images from MongoDB
    client, database, collection = create_mongodb_connection("file-uploads")
    all_images = list(collection.find({}))
    
    # Create a lookup dictionary for MongoDB images by file_path
    image_lookup = {}
    for img in all_images:
        if 'file_path' in img:
            image_lookup[img['file_path']] = img
    
    # Prepare data for template
    parsed = []
    
    # First, add products with their images
    for product in products:
        product_id = product[0]
        product_name = product[1]
        stock_count = product[2]
        
        # Find matching image for this product
        matching_image = None
        
        # Try to find by product_id in MongoDB
        for img in all_images:
            if 'product_id' in img and str(img['product_id']) == str(product_id):
                matching_image = img
                break
        
        # If no match by product_id, try by image_mongodb_id
        if not matching_image and product[3]:  # If product has image_mongodb_id
            for img in all_images:
                if '_id' in img and str(img['_id']) == product[3]:
                    matching_image = img
                    break
        
        # If we found a matching image
        if matching_image and 'file_path' in matching_image:
            img_url = url_for('download_file', name=matching_image['file_path'])
            
            image_data = {
                "image_url": img_url,
                "product_id": product_id,
                "product_name": product_name,
                "stock_count": stock_count,
                "file_path": matching_image['file_path']
            }
            
            parsed.append(image_data)
    
    # Now add any remaining images that don't have product associations
    for img in all_images:
        if 'file_path' in img:
            # Check if this image is already included
            already_included = False
            for p in parsed:
                if p['file_path'] == img['file_path']:
                    already_included = True
                    break
            
            if not already_included:
                img_url = url_for('download_file', name=img['file_path'])
                
                image_data = {
                    "image_url": img_url,
                    "file_path": img['file_path'],
                    "product_name": "Unassociated Image",
                    "stock_count": 0
                }
                
                parsed.append(image_data)
    
    client.close()
    cur.close()
    conn.close()
    
    return parsed

def render_images_page():
    """
    Render the images gallery page
    """
    images = get_uploaded_images()
    env_mode = os.getenv("ENV_MODE")
    
    if env_mode == "backend":
        return jsonify(images)
    else:
        return render_template('view_images.html', images=images)