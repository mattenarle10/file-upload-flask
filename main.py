import os
import json
import psycopg2
from datetime import datetime

from flask import Flask, flash, request, redirect, url_for, render_template, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from db.mongodb.mongodb_connection import create_mongodb_connection

UPLOAD_FOLDER = os.getenv("UPLOAD_DIRECTORY")
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
ENV_MODE = os.getenv("ENV_MODE")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")  # Added secret key for flash messages

@app.route("/")
def index():
    # Main landing page with navigation
    return render_template('index.html')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload-file', methods=['GET', 'POST'])
def upload_file():
    print("AND THE FORM IS")
    print(request.form)
    if request.method == 'POST':

        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']

        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):

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

            if ENV_MODE == "backend":
                return {
                    "filename": filename,
                    "img_url": img_url
                }
            else:
                return redirect(url_for('show_uploaded_images'))
    
    return render_template('upload_image.html')

@app.route('/images', methods=['GET'])
def show_uploaded_images():
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
    
    if ENV_MODE == "backend":
        return jsonify(parsed)
    else:
        return render_template('view_images.html', images=parsed)

@app.route('/uploads/<name>')
def download_file(name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], name)

# Create Order route
@app.route('/create-order', methods=['GET', 'POST'])
def create_order():
    if request.method == 'POST':
        product_id = request.form.get('product_id')
        order_quantity = int(request.form.get('order_quantity', 1))
        
        if not product_id:
            flash('Product ID is required')
            return redirect(request.url)
            
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=os.environ["POSTGRESQL_DB_HOST"],
            database=os.environ["POSTGRESQL_DB_DATABASE_NAME"],
            user=os.environ['POSTGRESQL_DB_USERNAME'],
            password=os.environ['POSTGRESQL_DB_PASSWORD']
        )
        cur = conn.cursor()
        
        # First check if there's enough stock
        cur.execute("SELECT stock_count FROM products WHERE id = %s", (product_id,))
        result = cur.fetchone()
        
        if not result:
            cur.close()
            conn.close()
            flash('Product not found')
            return redirect(url_for('create_order'))
            
        current_stock = result[0]
        
        if current_stock < order_quantity:
            cur.close()
            conn.close()
            flash('Not enough stock available')
            return redirect(url_for('create_order'))
        
        # Update the stock count by subtracting the order quantity
        new_stock = current_stock - order_quantity
        cur.execute("UPDATE products SET stock_count = %s WHERE id = %s", 
                   (new_stock, product_id))
        
        # Create order record (assuming you have an orders table)
        # If you don't have an orders table yet, you'd need to create it
        try:
            cur.execute("""
                INSERT INTO orders (product_id, quantity, order_date) 
                VALUES (%s, %s, %s)
                """, (product_id, order_quantity, datetime.now()))
        except psycopg2.errors.UndefinedTable:
            # If orders table doesn't exist, create it
            conn.rollback()  # Roll back the failed INSERT
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    product_id INTEGER REFERENCES products(id),
                    quantity INTEGER NOT NULL,
                    order_date TIMESTAMP NOT NULL
                )
            """)
            conn.commit()
            
            # Try insert again
            cur.execute("""
                INSERT INTO orders (product_id, quantity, order_date) 
                VALUES (%s, %s, %s)
                """, (product_id, order_quantity, datetime.now()))
        
        conn.commit()
        cur.close()
        conn.close()
        
        flash('Order created successfully')
        return redirect(url_for('show_uploaded_images'))
    
    # For GET requests, fetch products to display in dropdown
    conn = psycopg2.connect(
        host=os.environ["POSTGRESQL_DB_HOST"],
        database=os.environ["POSTGRESQL_DB_DATABASE_NAME"],
        user=os.environ['POSTGRESQL_DB_USERNAME'],
        password=os.environ['POSTGRESQL_DB_PASSWORD']
    )
    cur = conn.cursor()
    cur.execute("SELECT id, name, stock_count FROM products")
    products = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template('create_order.html', products=products)

# Simple redirect routes for better navigation
@app.route('/home')
def home():
    return redirect(url_for('index'))

@app.route('/gallery')
def gallery():
    return redirect(url_for('show_uploaded_images'))

@app.route('/upload')
def upload():
    return redirect(url_for('upload_file'))

@app.route('/order')
def order():
    return redirect(url_for('create_order'))
