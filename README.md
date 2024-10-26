# ecv-jpm-file-upload-flask

## Basic Setup

```sh
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt


export MONGODB_DB_CONNECTION_URI=mongodb://localhost:27017/
export MONGODB_DB_NAME=ecv-jmp-file-upload-app
export ENV_MODE=frontend
export POSTGRESQL_DB_USERNAME=flask_photo_app_admin
export POSTGRESQL_DB_PASSWORD='sac2c2qec1131DSq@#1'
export POSTGRESQL_DB_DATABASE_NAME=ecv_file_upload_app_psql
export POSTGRESQL_DB_HOST=localhost


# run the app!
flask --app main run
```

## Jamby's corner

```sh
pip install Flask
pip install pymongo
pip install Jinja2
pip install psycopg2-binary
pip freeze > requirements.txt

brew tap mongodb/brew
brew update

# https://www.digitalocean.com/community/tutorials/how-to-use-a-postgresql-database-in-a-flask-application
brew install postgresql@16
brew services start postgresql@16

# setup your postgresql database
echo 'export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"' >> /Users/raphael.jambalos/.zshrc
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"

psql postgres
CREATE ROLE flask_photo_app_admin WITH LOGIN SUPERUSER PASSWORD 'sac2c2qec1131DSq@#1';
CREATE DATABASE ecv_file_upload_app_psql;

# show databases
\l

# use this db
\c ecv_file_upload_app_psql;

# test
select * from stock_movements;
select * from products;

# https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-os-x/
brew install mongodb-community@8.0
brew services start mongodb-community@8.0
```

## Helpful Docs

https://flask.palletsprojects.com/en/stable/quickstart/
http://127.0.0.1:5000/images