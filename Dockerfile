# =============================================================================
# e-KYC Verification System - Dockerfile
# =============================================================================
# Multi-stage build for production deployment with offline model support.
#
# Build:
#   docker build -t ekyc-api:latest .
#
# Run:
#   docker run -p 8000:8000 -e PERSIST_IMAGES=false ekyc-api:latest
#
# NOTE: Before building, run `python scripts/download_models.py` to download
#       the ML models to the `models/` directory.
# =============================================================================

FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# =============================================================================
# Dependencies Stage
# =============================================================================
FROM base AS deps

# Copy dependency file
COPY pyproject.toml .
# Install dependencies directly from pyproject.toml
# Install build tools needed for InsightFace compilation, then clean up
RUN apt-get update && apt-get install -y --no-install-recommends build-essential python3-dev && \
    pip install --no-cache-dir . && \
    apt-get purge -y --auto-remove build-essential python3-dev && \
    rm -rf /var/lib/apt/lists/*

# =============================================================================
# Production Stage
# =============================================================================
FROM deps AS production

# Set offline model paths
ENV MODELS_DIR=/app/models \
    INSIGHTFACE_HOME=/app/models/insightface \
    PERSIST_IMAGES=false

# Copy application code
COPY . .

# Pre-seed PaddleOCR cache for offline mode (simplest way to make PaddleOCR find models)
# The download script puts them in models/paddleocr. We copy them to expected cache location.
# RUN mkdir -p /root/.paddleocr && \
#     cp -r /app/models/paddleocr/* /root/.paddleocr/ || true
# NOW handled at runtime in ocr_service.py to support external volumes

# Create necessary directories
RUN mkdir -p /app/data/id_cards /app/data/selfies /app/data/processed

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
