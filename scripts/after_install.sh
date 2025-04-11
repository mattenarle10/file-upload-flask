#!/bin/bash
cd /home/ec2-user/file-upload-flask
echo "Installing Python dependencies..."

# Create virtual environment if it doesn't exist
if [ ! -d "/home/ec2-user/file-upload-flask/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# Ensure MongoDB TLS certificate exists
if [ ! -f "/home/ec2-user/file-upload-flask/global-bundle.pem" ]; then
    echo "Downloading MongoDB TLS certificate..."
    wget [https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem](https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem) -O /home/ec2-user/file-upload-flask/global-bundle.pem
fi

# Ensure uploads directory exists
if [ ! -d "/efs/uploads" ]; then
    echo "Creating uploads directory..."
    sudo mkdir -p /efs/uploads
    sudo chown -R ec2-user:ec2-user /efs/uploads
fi

# Set proper permissions
echo "Setting permissions..."
chmod -R 755 /home/ec2-user/file-upload-flask