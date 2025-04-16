import os
from datetime import datetime
import psycopg2
from flask import url_for, flash, redirect, request, render_template
from werkzeug.utils import secure_filename
from db.mongodb.mongodb_connection import create_mongodb_connection

def allowed_file(filename, allowed_extensions):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def handle_upload_file(request, app):
    """
    Handle file upload logic
    """
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    file = request.files['file']

    # If the user does not select a file, the browser submits an
    # empty file without a filename.
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    
    allowed_extensions = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
    if file and allowed_file(file.filename, allowed_extensions):
        # Upload the file
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # save image_metadata to MongoDB
        client, database, collection = create_mongodb_connection("file-uploads")

        product_name = request.form.get('product_name')
        stock_count = int(request.form.get('initial_stock_count'))

        # Insert MongoDB record with product details
        result = collection.insert_one({
            "file_path": filename,
            "product_name": product_name,
            "upload_date": datetime.now()
        })

        mongodb_id = str(result.inserted_id)
        client.close()

        # save product_data to PostgreSQL
        conn = psycopg2.connect(
            host=os.environ["POSTGRESQL_DB_HOST"],
            database=os.environ["POSTGRESQL_DB_DATABASE_NAME"],
            user=os.environ['POSTGRESQL_DB_USERNAME'],
            password=os.environ['POSTGRESQL_DB_PASSWORD']
        )
        cur = conn.cursor()

        review = "Sample Review"

        cur.execute('INSERT INTO products (name, image_mongodb_id, stock_count, review)'
                    'VALUES (%s, %s, %s, %s) RETURNING id',
                    (product_name,
                    mongodb_id,
                    stock_count,
                    review)
        )
        
        # Get the newly created product ID
        product_id = cur.fetchone()[0]
        
        # Update MongoDB record with the product ID
        client, database, collection = create_mongodb_connection("file-uploads")
        collection.update_one(
            {"_id": result.inserted_id},
            {"$set": {"product_id": product_id}}
        )
        client.close()

        conn.commit()
        cur.close()
        conn.close()

        img_url = url_for('download_file', name=filename)

        env_mode = os.getenv("ENV_MODE")
        if env_mode == "backend":
            return {
                "filename": filename,
                "img_url": img_url
            }
        else:
            return redirect(url_for('show_uploaded_images'))
    
    return None

def render_upload_page():
    """
    Render the upload page template
    """
    return render_template('upload_image.html')