#!/bin/bash
echo "Starting deployment process..."

# Install dependencies if needed
if ! command -v python3 &> /dev/null; then
    sudo yum -y update
    sudo yum -y install python3 python3-pip
fi

# Backup the current application if it exists
if [ -d /home/ec2-user/file-upload-flask ]; then
    echo "Backing up existing application..."
    timestamp=$(date +%Y%m%d%H%M%S)
    mkdir -p /home/ec2-user/backups
    cp -r /home/ec2-user/file-upload-flask /home/ec2-user/backups/file-upload-flask-$timestamp
    
    # Clean the directory but preserve important files
    echo "Cleaning deployment directory..."
    find /home/ec2-user/file-upload-flask -mindepth 1 \
        -not -path "*/venv/*" \
        -not -path "*/global-bundle.pem" \
        -not -path "*/uploads/*" \
        -delete
else
    # Create directory if it doesn't exist
    echo "Creating deployment directory..."
    mkdir -p /home/ec2-user/file-upload-flask
fi

# Ensure proper ownership
sudo chown -R ec2-user:ec2-user /home/ec2-user/file-upload-flask