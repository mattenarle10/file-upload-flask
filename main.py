import os
import json
import psycopg2
from datetime import datetime

from flask import Flask, flash, request, redirect, url_for, render_template, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from db.mongodb.mongodb_connection import create_mongodb_connection
from aws_xray_sdk.core import xray_recorder, patch_all
from aws_xray_sdk.ext.flask.middleware import XRayMiddleware

UPLOAD_FOLDER = os.getenv("UPLOAD_DIRECTORY")
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
ENV_MODE = os.getenv("ENV_MODE")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")  # Added secret key for flash messages

xray_recorder.configure(service='file-upload-flask') 
XRayMiddleware(app, xray_recorder)
patch_all() 

@app.route("/")
def index():
    # Main landing page with navigation
    return render_template('index.html')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

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
        try:
            # Get form data with validation
            product_id = request.form.get('product_id')
            if not product_id:
                flash('Product ID is required')
                return redirect(request.url)
                
            # Get customer name
            customer_name = request.form.get('customer_name', '').strip()
            if not customer_name:
                flash('Customer name is required')
                return redirect(request.url)
                
            # Safely convert order_quantity to integer
            try:
                order_quantity = int(request.form.get('order_quantity', 1))
                if order_quantity <= 0:
                    flash('Order quantity must be positive')
                    return redirect(request.url)
            except ValueError:
                flash('Invalid order quantity')
                return redirect(request.url)
                
            # Connect to PostgreSQL with error handling
            conn = psycopg2.connect(
                host=os.environ["POSTGRESQL_DB_HOST"],
                database=os.environ["POSTGRESQL_DB_DATABASE_NAME"],
                user=os.environ['POSTGRESQL_DB_USERNAME'],
                password=os.environ['POSTGRESQL_DB_PASSWORD']
            )
            conn.autocommit = False  # Start transaction mode
            cur = conn.cursor()
            
            try:
                # First check if there's enough stock
                cur.execute("SELECT name, stock_count FROM products WHERE id = %s", (product_id,))
                result = cur.fetchone()
                
                if not result:
                    conn.rollback()
                    cur.close()
                    conn.close()
                    flash('Product not found')
                    return redirect(url_for('create_order'))
                    
                product_name, current_stock = result
                
                if current_stock < order_quantity:
                    conn.rollback()
                    cur.close()
                    conn.close()
                    flash(f'Not enough stock available for {product_name}. Available: {current_stock}')
                    return redirect(url_for('create_order'))
                
                # Calculate order total (simple example)
                unit_price = 10.00  # You might want to add a price column to products
                total = unit_price * order_quantity
                
                # Create order record - simplified without tax
                cur.execute("""
                    INSERT INTO orders (customer_name, total, tax, pretax_amount) 
                    VALUES (%s, %s, %s, %s) RETURNING id
                    """, (customer_name, total, 0, total))  # Tax is 0, pretax_amount equals total
                
                order_id = cur.fetchone()[0]
                
                # Create stock movement record
                cur.execute("""
                    INSERT INTO stock_movements (product_id, order_id, quantity) 
                    VALUES (%s, %s, %s)
                    """, (product_id, order_id, order_quantity))
                
                # Update product stock
                new_stock = current_stock - order_quantity
                cur.execute("UPDATE products SET stock_count = %s WHERE id = %s", 
                           (new_stock, product_id))
                
                # Commit the transaction
                conn.commit()
                
                flash(f'Order #{order_id} created successfully for {product_name}')
                
                # Instead of redirecting, we'll render the template directly with the updated data
                # This ensures the new order appears in the list without requiring a refresh
                
                # Close the current connection
                cur.close()
                conn.close()
                
                # Return to the GET part of the function to fetch fresh data
                return redirect(url_for('create_order'))
                
            except psycopg2.Error as e:
                conn.rollback()
                app.logger.error(f"Database error: {e}")
                flash(f'Error creating order: {str(e)}')
                return redirect(request.url)
            finally:
                if cur and not cur.closed:
                    cur.close()
                if conn and not conn.closed:
                    conn.close()
                
        except Exception as e:
            app.logger.error(f"Unexpected error in create_order: {e}")
            flash('An unexpected error occurred')
            return redirect(request.url)
    
    # For GET requests, fetch products with images to display in dropdown
    try:
        conn = psycopg2.connect(
            host=os.environ["POSTGRESQL_DB_HOST"],
            database=os.environ["POSTGRESQL_DB_DATABASE_NAME"],
            user=os.environ['POSTGRESQL_DB_USERNAME'],
            password=os.environ['POSTGRESQL_DB_PASSWORD']
        )
        cur = conn.cursor()
        
        # Get all products with their details including MongoDB image ID
        cur.execute("""
            SELECT p.id, p.name, p.stock_count, p.image_mongodb_id 
            FROM products p
        """)
        products = cur.fetchall()
        
        # Get all images from MongoDB
        client, database, collection = create_mongodb_connection("file-uploads")
        all_images = list(collection.find({}))
        
        # Prepare data for template
        parsed_products = []
        
        # Process products with their images
        for product in products:
            product_id = product[0]
            product_name = product[1]
            stock_count = product[2]
            image_mongodb_id = product[3]
            
            # Find matching image for this product
            matching_image = None
            
            # Try to find by product_id in MongoDB
            for img in all_images:
                if 'product_id' in img and str(img['product_id']) == str(product_id):
                    matching_image = img
                    break
            
            # If no match by product_id, try by image_mongodb_id
            if not matching_image and image_mongodb_id:
                for img in all_images:
                    if '_id' in img and str(img['_id']) == image_mongodb_id:
                        matching_image = img
                        break
            
            # If we found a matching image
            if matching_image and 'file_path' in matching_image:
                img_url = url_for('download_file', name=matching_image['file_path'])
                
                product_data = {
                    "product_id": product_id,
                    "product_name": product_name,
                    "stock_count": stock_count,
                    "image_url": img_url,
                    "file_path": matching_image['file_path']
                }
            else:
                # No matching image found
                product_data = {
                    "product_id": product_id,
                    "product_name": product_name,
                    "stock_count": stock_count,
                    "image_url": "",
                    "file_path": ""
                }
            
            parsed_products.append(product_data)
        
        # Fetch recent orders for display
        orders = []
        try:
            # Get recent orders with product details through stock_movements
            cur.execute("""
                SELECT o.id, sm.product_id, p.name, sm.quantity, o.created_at, p.image_mongodb_id, o.total, o.customer_name 
                FROM orders o
                JOIN stock_movements sm ON o.id = sm.order_id
                JOIN products p ON sm.product_id = p.id
                ORDER BY o.created_at DESC
                LIMIT 10
            """)
            
            recent_orders = cur.fetchall()
            
            # Process orders with product images
            for order in recent_orders:
                order_id = order[0]
                product_id = order[1]
                product_name = order[2]
                quantity = order[3]
                order_date = order[4]
                image_mongodb_id = order[5]
                total = order[6]
                customer_name = order[7]
                
                # Find matching image for this product
                image_url = ""
                
                # Try to find by product_id in MongoDB
                for img in all_images:
                    if 'product_id' in img and str(img['product_id']) == str(product_id):
                        if 'file_path' in img:
                            image_url = url_for('download_file', name=img['file_path'])
                        break
                
                # If no match by product_id, try by image_mongodb_id
                if not image_url and image_mongodb_id:
                    for img in all_images:
                        if '_id' in img and str(img['_id']) == image_mongodb_id:
                            if 'file_path' in img:
                                image_url = url_for('download_file', name=img['file_path'])
                            break
                
                order_data = {
                    "order_id": order_id,
                    "product_id": product_id,
                    "product_name": product_name,
                    "quantity": quantity,
                    "order_date": order_date,
                    "image_url": image_url,
                    "total": total,
                    "customer_name": customer_name
                }
                
                orders.append(order_data)
        except Exception as e:
            app.logger.error(f"Error fetching orders: {e}")
            # Continue without orders if there's an error
        
        client.close()
        cur.close()
        conn.close()
        
        return render_template('create_order.html', products=parsed_products, orders=orders)
        
    except Exception as e:
        app.logger.error(f"Error loading products: {e}")
        flash('Error loading products')
        return render_template('create_order.html', products=[], orders=[])

@app.route('/clear-mongodb', methods=['GET'])
def clear_mongodb():
    try:
        client, database, collection = create_mongodb_connection("file-uploads")
        result = collection.delete_many({})
        deleted_count = result.deleted_count
        client.close()
        return jsonify({"message": f"Deleted {deleted_count} documents from MongoDB", "success": True})
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}", "success": False})

@app.route('/image/<image_id>')
def get_image(image_id):
    client, database, collection = create_mongodb_connection("file-uploads")
    image_doc = collection.find_one({"_id": ObjectId(image_id)})
    client.close()
    
    if image_doc and "file_path" in image_doc:
        file_path = os.path.join(os.environ["UPLOAD_DIRECTORY"], image_doc["file_path"])
        return send_file(file_path)
    else:
        return "Image not found", 404

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

@app.route("/health")
def health():
    return "OK", 200
