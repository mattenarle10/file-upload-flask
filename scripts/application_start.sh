#!/bin/bash
echo "Starting application..."
cd /home/ec2-user/file-upload-flask

# Reload systemd configuration
sudo systemctl daemon-reload

# Restart the Flask application
sudo systemctl restart flask_app.service

# Restart Nginx
sudo systemctl restart nginx

# Check if services are running
echo "Checking service status..."
sudo systemctl status flask_app.service --no-pager
sudo systemctl status nginx --no-pager

echo "Deployment complete!"