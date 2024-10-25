# ecv-jpm-file-upload-flask

## Basic Setup

```sh
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt


export MONGODB_DB_CONNECTION_URI=mongodb://localhost:27017/
export MONGODB_DB_NAME=ecv-jmp-file-upload-app
export ENV_MODE=frontend
```

## Jamby's corner

```sh
pip install Flask
pip install pymongo
pip install Jinja2
pip freeze > requirements.txt

brew tap mongodb/brew
brew update
brew install mongodb-community@8.0

# https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-os-x/
brew services start mongodb-community@8.0
```