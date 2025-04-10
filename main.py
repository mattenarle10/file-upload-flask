import os
import json
import psycopg2

from flask import Flask, flash, request, redirect, url_for, render_template, send_from_directory
from werkzeug.utils import secure_filename
from db.mongodb.mongodb_connection import create_mongodb_connection

UPLOAD_FOLDER = os.getenv("UPLOAD_DIRECTORY")
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
ENV_MODE = os.getenv("ENV_MODE")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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

            result = collection.insert_one({
                "file_path": filename
            })

            client.close()

            # save product_data to PostgreSQL
            conn = psycopg2.connect(
                host=os.environ["POSTGRESQL_DB_HOST"],
                database=os.environ["POSTGRESQL_DB_DATABASE_NAME"],
                user=os.environ['POSTGRESQL_DB_USERNAME'],
                password=os.environ['POSTGRESQL_DB_PASSWORD']
            )
            cur = conn.cursor()

            product_name = request.form.get('product_name')
            image_mongodb_id = "12345"
            stock_count = int(request.form.get('initial_stock_count'))
            review = "Sample Review"

            cur.execute('INSERT INTO products (name, image_mongodb_id, stock_count, review)'
                        'VALUES (%s, %s, %s, %s)',
                        (product_name,
                        image_mongodb_id,
                        stock_count,
                        review)
            )

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
    client, database, collection = create_mongodb_connection("file-uploads")
    data = list(collection.find({}))
    print(data)
    print("===")

    parsed = []
    for d in data:
        img_url = url_for('download_file', name=d['file_path'])

        parsed.append({
            "image_url": img_url
        })
    
    if ENV_MODE == "backend":
        return json.dumps({
            "data": parsed
        })
    else:
        return render_template('view_images.html', images=parsed)

@app.route('/uploads/<name>')
def download_file(name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], name)

# Create Order route
@app.route('/create-order', methods=['GET', 'POST'])
def create_order():
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

            # Process order data here
            # This is a placeholder for order processing logic
            product_id = request.form.get('product_name')  # Using product_name field for product_id
            stock_count = request.form.get('initial_stock_count')
            
            # Redirect to images page after successful order creation
            return redirect(url_for('show_uploaded_images'))
    
    return render_template('create_order.html')

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
