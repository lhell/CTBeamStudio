#!/bin/bash
# Run CT-Viewer Docker container
CONTAINER_NAME="ct-viewer"

# Stop existing if running
if [ "$(docker ps -q -f name=$CONTAINER_NAME)" ]; then
    echo "Stopping existing container..."
    docker stop $CONTAINER_NAME
    docker rm $CONTAINER_NAME
fi

# Build and run
echo "Building image..."
docker build -t ct-viewer:latest .

echo "Starting container on port 8501..."
docker run -d -p 8501:8501 --name $CONTAINER_NAME ct-viewer:latest

echo "CT-Viewer running at http://localhost:8501"
