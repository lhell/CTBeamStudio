# CTBeamStudio Dockerfile
# Python 3.11 + Streamlit

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true

# Set working directory
WORKDIR /app

# Install system dependencies for DICOM processing
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libgl1 \
    libxrender1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy packaging metadata and source required for the editable install.
# README.md is referenced by pyproject.toml, src/ is needed for package discovery.
COPY pyproject.toml README.md /app/
COPY src /app/src

# Install Python dependencies and the package itself.
# pyvista is not declared in pyproject.toml (it is optional at import time),
# but it is installed here so the PyVista render mode works in the container.
RUN pip install --no-cache-dir -e /app/ pyvista

# Copy remaining application code (data/docs/tests are excluded via .dockerignore)
COPY . /app/

# Build Guard: Fail if data files exist in repository
RUN find /app -type f \( -name "*.dcm" -o -name "*.ima" -o -name "*.npy" -o -name "*.npz" \) 2>/dev/null | \
    grep -q . && echo "ERROR: Data files found in repository!" && exit 1 || \
    echo "Data guard: OK"

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# Create non-root user
RUN useradd -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Run Streamlit application
CMD ["streamlit", "run", "src/visualization/app.py", "--server.address", "0.0.0.0"]
