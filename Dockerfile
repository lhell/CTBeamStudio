# CTBeamStudio Dockerfile — two targets from one build.
#
#   docker build -t ct-viewer:slim .                # viewer only, ~350 MB
#   docker build -t ct-viewer:full --target full .  # + forward projection, ~1.6 GB
#
# `slim` installs plain pip packages. It renders volumes, MPR and geometry, but
# "Run Forward Projection" returns zeros with a warning, because parallelproj
# and torch are absent (src/backend/forward_project.py:27).
#
# `full` is the image we hand to customers: it adds parallelproj and torch, so
# the projection comparison works. parallelproj ships compiled kernels and
# exists only on conda-forge, therefore the build pulls micromamba in and
# creates a private conda env inside the image. conda is build-time machinery
# here, like apt — the customer machine never needs conda installed.
# Development on a conda env is still the rule; see docs/local-environment.md.

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true

WORKDIR /app

# System libraries for DICOM processing and image decoding.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg-dev \
        zlib1g-dev \
        libpng-dev \
        libgl1 \
        libxrender1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Packaging metadata and source first: pyproject.toml references README.md and
# discovers the packages under src/, so both must exist before the install.
COPY pyproject.toml README.md /app/
COPY src /app/src

# Copy remaining application code (data/docs/tests are excluded via .dockerignore)
COPY . /app/

# Build Guard: fail if data files reached the image.
RUN find /app -type f \( -name "*.dcm" -o -name "*.ima" -o -name "*.npy" -o -name "*.npz" \) | grep -q . \
    && { echo "ERROR: Data files found in repository!"; exit 1; } \
    || echo "Data guard: OK"

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# Non-root runtime for both targets.
# /app/data is created here rather than at runtime: .dockerignore excludes the
# repo's data/ dir, and a named volume mounted onto a path that does not exist
# in the image would come up root-owned and unwritable for appuser
# (visualization/volume_cache.py writes data/.last_loaded.json).
RUN useradd -m -s /bin/bash appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

USER appuser

CMD ["streamlit", "run", "src/visualization/app.py", "--server.address", "0.0.0.0"]


# ---------------------------------------------------------------------------
# full: the customer image. parallelproj (conda-forge) + torch (CPU).
# ---------------------------------------------------------------------------
FROM base AS full

USER root

# curl/bzip2 fetch micromamba; libgomp1 is what torch's CPU kernels link against.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        bzip2 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV MAMBA_ROOT_PREFIX=/opt/micromamba
RUN curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest \
        | tar -xj -C /usr/local bin/micromamba \
    && micromamba create -y -p /opt/env -c conda-forge \
        "python=3.11" \
        parallelproj \
        "libparallelproj=*=cpu*" \
    && micromamba clean --all --yes

ENV PATH=/opt/env/bin:$PATH

# torch comes from PyTorch's CPU index: same kernels as conda's pytorch build,
# a fraction of the download. The app is installed into this same env on
# purpose — one Python, one numpy. Mixing a conda numpy with wheels built
# against a different numpy is the classic import-time crash.
RUN /opt/env/bin/pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu torch \
    && /opt/env/bin/pip install --no-cache-dir -e /app

# Build-time proof that the C library loads and that the backend flips its flag.
# Without this the image builds green and only fails at the customer's first
# projection with "forward projection will return zeros".
RUN python -c "import parallelproj, torch; print('parallelproj cuda:', parallelproj.cuda_present, '| torch:', torch.__version__)" \
    && python -c "from backend.forward_project import PARALLELPROJ_AVAILABLE; assert PARALLELPROJ_AVAILABLE, 'parallelproj/torch not visible to backend'"

USER appuser


# ---------------------------------------------------------------------------
# slim: viewer only. Smallest image, no projection backend.
#
# This is the last stage, so a plain `docker build .` builds slim: that keeps
# the "smallest image by default" promise from T-40/T-73 and never surprises
# anyone with a 1.6 GB build. The customer image needs --target full.
# ---------------------------------------------------------------------------
FROM base AS slim

USER root
RUN pip install --no-cache-dir -e /app
USER appuser
