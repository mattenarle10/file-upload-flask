import os
import json
import jinja2
from jinja2 import Environment, PackageLoader, select_autoescape, BaseLoader, FileSystemLoader

from flask import Flask, flash, request, redirect, url_for, render_template
from werkzeug.utils import secure_filename
from db.mongodb.mongodb_connection import create_mongodb_connection

UPLOAD_FOLDER = '/tmp'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
ENV_MODE = os.getenv("ENV_MODE")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload-file', methods=['GET', 'POST'])
def upload_file():
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
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            client, database, collection = create_mongodb_connection("file-uploads")

            result = collection.insert_one({
                "file_path": filename
            })

            client.close()
            img_url = url_for('download_file', name=filename)

            if ENV_MODE == "backend":
                return {
                    "filename": filename,
                    "img_url": img_url
                }
            else:
                return f'''
                <!doctype html>
                <html>
                    <h1>{filename}</h1>
                    <img src={img_url}></img>
                </html>
                '''
            
            
            redirect()
    
    return '''
    <!doctype html>
    <title>Upload new File</title>
    <h1>Upload new File</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
    '''

from flask import send_from_directory

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
        return render_template('view_images.html', navigation=parsed)

        # template_dir = os.path.join(".", 'view_images.html')
        # loader = FileSystemLoader(template_dir)

        # rtemplate = Environment(loader=loader)
        # template = rtemplate.get_template("view_images")

        # return template.render(navigation=parsed)



@app.route('/uploads/<name>')
def download_file(name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], name)