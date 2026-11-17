#!/bin/bash
# Run CTBeamStudio Docker container with the forward-projection backend.
#
#   ./scripts/run-docker.sh                 # mounts ./data
#   ./scripts/run-docker.sh /path/to/dicom  # mounts that folder instead
set -euo pipefail

CONTAINER_NAME="ct-viewer"
IMAGE="ct-viewer:full"
# Host folder holding the DICOM series; exposed as /data inside the container.
DATA_DIR="${1:-$(pwd)/data}"

if [ ! -d "$DATA_DIR" ]; then
    echo "ERROR: data folder not found: $DATA_DIR" >&2
    exit 1
fi
DATA_DIR="$(cd "$DATA_DIR" && pwd)"

# Stop existing if running
if [ "$(docker ps -q -f name="$CONTAINER_NAME")" ]; then
    echo "Stopping existing container..."
    docker stop "$CONTAINER_NAME"
    docker rm "$CONTAINER_NAME"
fi

echo "Building image (target: full)..."
docker build -t "$IMAGE" --target full .

echo "Starting container on port 8501 (data: $DATA_DIR -> /data)..."
docker run -d -p 8501:8501 --name "$CONTAINER_NAME" \
    -v "$DATA_DIR:/data:ro" \
    -v "$CONTAINER_NAME-cache:/app/data" \
    "$IMAGE"

echo "CTBeamStudio running at http://localhost:8501"
echo "In the sidebar, enter /data/<your-study> as the DICOM folder."
