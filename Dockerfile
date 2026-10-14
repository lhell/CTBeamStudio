# CT-Viewer Dockerfile
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
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml first (for better caching)
COPY pyproject.toml /app/

# Install Python dependencies from pyproject.toml
RUN pip install --no-cache-dir -e /app/

# Copy application code
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

# Run Streamlit application
CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0"]
