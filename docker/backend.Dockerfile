# Backend image (Prompt 39): FastAPI + detection (OpenCV, Tesseract OCR, YOLO on CPU) + PDF reports.
# Built by docker-compose.yml from the project root:  docker compose build
#
# - PyTorch comes from its CPU-only index (about 1 GB smaller than the default CUDA build; no GPU is used).
# - The database, uploads and avatars live in the /data volume, never in the image.
# - No secrets in the image: .env files are excluded (.dockerignore); settings arrive as environment variables.
ARG PYTHON_IMAGE=python:3.12-slim-bookworm
FROM ${PYTHON_IMAGE}

ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
# Prompt 39A: the versions tested on the project PC (a build months later installs the same)
ARG TORCH_VERSION=2.13.0
ARG TORCHVISION_VERSION=0.28.0
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    YOLO_AUTOINSTALL=False \
    YOLO_OFFLINE=True \
    YOLO_CONFIG_DIR=/tmp/ultralytics

# Tesseract OCR (English) and the system libraries OpenCV needs
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
# dependencies first (cached until requirements.txt changes); CPU PyTorch before ultralytics so it is not replaced
COPY backend/requirements.txt ./requirements.txt
RUN pip install "torch==${TORCH_VERSION}" "torchvision==${TORCHVISION_VERSION}" --index-url "${TORCH_INDEX_URL}" \
 && pip install -r requirements.txt

COPY backend/ ./
COPY models/ /app/models/

# run as an ordinary user; /data is the only place the app writes
RUN useradd --create-home --uid 10001 app \
 && mkdir -p /data/uploads /data/avatars /tmp/ultralytics \
 && chown -R app:app /data /tmp/ultralytics
USER app

ENV APP_ENV=production \
    DATABASE_URL=sqlite:////data/app.db \
    STORAGE_PATH=/data/uploads
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

# One process: SQLite and the in-memory sign-in limits are shared by all requests (FastAPI serves requests on threads).
# --proxy-headers: the visitor's address comes from the web server in front (nginx), which is the only way in.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--timeout-keep-alive", "75"]
