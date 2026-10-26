# Docker Self-Deployment Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run CT-Viewer v1.0.0 as a Docker container for self-hosted deployment.

**Architecture:** Single-stage Dockerfile using Python 3.11-slim, runs Streamlit on port 8501, starts in demo phantom mode by default.

**Tech Stack:** Python 3.11, Streamlit, pydicom, numpy, plotly, Docker

**Spec:** `docs/plan.md` Phase 4 (T-40 to T-44)

---

## Global Constraints

- Python >=3.11
- Streamlit <1.40.0 (from pyproject.toml)
- No patient data in image
- Non-root user in container
- Image size <400 MiB

---

## Review Focus

- Docker builds without errors
- Container runs without root privileges
- App accessible on localhost:8501
- Demo phantom loads by default when no data mounted

---

### Task 1: Review and Update Dockerfile

**Files:**
- Modify: `Dockerfile`

**Interfaces:**
- Produces: Updated Dockerfile ready for self-deployment

- [ ] **Step 1: Review current Dockerfile**

Run: `cat Dockerfile`
Check: Base image, non-root user, port, health check

- [ ] **Step 2: Add non-root user (if missing)**

If Dockerfile doesn't create/run as non-root user, add:
```dockerfile
# Create non-root user
RUN useradd -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser
```

- [ ] **Step 3: Verify path to app.py in CMD**

The CMD should reference: `src/visualization/app.py` (not `app.py`)

- [ ] **Step 4: Commit Dockerfile changes**

```bash
git add Dockerfile
git commit -m "fix: update Dockerfile for self-deployment"
```

---

### Task 2: Create .dockerignore

**Files:**
- Create: `.dockerignore`

**Interfaces:**
- Produces: Prevents unwanted files in Docker context

- [ ] **Step 1: Create .dockerignore**

```gitignore
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info
dist
build
.venv
venv
env
.git
.gitignore
.pytest_cache
.coverage
htmlcov
*.log
.DS_Store
*.dcm
*.ima
*.npy
*.npz
```

- [ ] **Step 2: Commit .dockerignore**

```bash
git add .dockerignore
git commit -m "feat: add .dockerignore"
```

---

### Task 3: Build and Test Docker Image

**Files:**
- Build: `ct-viewer` image

**Interfaces:**
- Produces: Working Docker image locally

- [ ] **Step 1: Build the Docker image**

Run: `docker build -t ct-viewer:1.0.0 .`
Expected: Build completes without errors, image size <400MB

- [ ] **Step 2: Run container in background**

Run: `docker run -d -p 8501:8501 --name ct-viewer ct-viewer:1.0.0`
Expected: Container starts

- [ ] **Step 3: Wait for health check**

Run: `docker ps` (wait for "healthy" status)
Expected: Container shows "healthy"

- [ ] **Step 4: Verify app is accessible**

Run: `curl -s http://localhost:8501/_stcore/health`
Expected: Returns OK or similar health response

- [ ] **Step 5: Stop container**

Run: `docker stop ct-viewer && docker rm ct-viewer`

---

### Task 4: Create Run Script (Optional)

**Files:**
- Create: `scripts/run-docker.sh`

**Interfaces:**
- Produces: Convenience script for running the container

- [ ] **Step 1: Create run-docker.sh**

```bash
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
```

- [ ] **Step 2: Make script executable**

Run: `chmod +x scripts/run-docker.sh`

- [ ] **Step 3: Commit script**

```bash
git add scripts/run-docker.sh
git commit -m "feat: add docker run script"
```

---

## Summary

| Task | Description | Status |
|------|-------------|--------|
| 1 | Review/update Dockerfile | Pending |
| 2 | Create .dockerignore | Pending |
| 3 | Build and verify image runs | Pending |
| 4 | Create run script | Pending (optional) |

---

## Future: CI Workflow (Not Today)

For future automation, create `.github/workflows/docker.yml`:

```yaml
name: Docker Build

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        run: docker build -t ct-viewer:test .
      - name: Check image size
        run: |
          SIZE=$(docker images ct-viewer:test --format "{{.Size}}")
          echo "Image size: $SIZE"
      - name: Run container
        run: |
          docker run -d -p 8501:8501 --name ct-viewer-test ct-viewer:test
          sleep 10
      - name: Health check
        run: curl -s http://localhost:8501/_stcore/health || exit 1
      - name: Cleanup
        run: docker stop ct-viewer-test && docker rm ct-viewer-test
```

**Estimated time today:** 30-45 minutes
