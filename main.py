import os
import json
from bson import ObjectId
import psycopg2
from datetime import datetime

from flask import Flask, flash, request, redirect, url_for, render_template, send_from_directory, jsonify, send_file
from werkzeug.utils import secure_filename
from db.mongodb.mongodb_connection import create_mongodb_connection
from aws_xray_sdk.core import xray_recorder, patch_all
from aws_xray_sdk.ext.flask.middleware import XRayMiddleware

# Import action modules
from actions.upload_image import handle_upload_file, render_upload_page
from actions.view_images import render_images_page
from actions.create_order import process_order, render_order_page
from actions.utils import add_cache_headers, serve_file, get_image_by_id, clear_mongodb_collection

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

@app.after_request
def after_request_handler(response):
    return add_cache_headers(response)

@app.route('/upload-file', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        result = handle_upload_file(request, app)
        if result:
            return result
    
    return render_upload_page()

@app.route('/images', methods=['GET'])
def show_uploaded_images():
    return render_images_page()

@app.route('/uploads/<name>')
def download_file(name):
    return serve_file(app.config, name)

@app.route('/create-order', methods=['GET', 'POST'])
def create_order():
    if request.method == 'POST':
        result = process_order(request, app)
        if result:
            return result
    
    return render_order_page(app)

@app.route('/clear-mongodb', methods=['GET'])
def clear_mongodb():
    return clear_mongodb_collection()

@app.route('/image/<image_id>')
def get_image(image_id):
    return get_image_by_id(image_id)

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

@app.route("/xray-test")
def xray_test():
    from aws_xray_sdk.core import xray_recorder
    seg = xray_recorder.begin_subsegment("manual-test")
    xray_recorder.end_subsegment()
    return "X-Ray test!", 200