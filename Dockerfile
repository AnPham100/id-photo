# V1b: Optimized Docker image for production
# Multi-stage build for smaller image size
# Image size: 4.46 GB

# ----- Builder stage -----

FROM python:3.11-slim-bookworm as builder

# Install build dependencies
# RUN apt-get update --allow-releaseinfo-change && apt-get install -y --no-install-recommends \
#     gcc \
#     g++ \
#     && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ----- Production stage -----

FROM python:3.11-slim-bookworm

# Install only runtime dependencies
RUN apt-get update --allow-releaseinfo-change && apt-get install -y --no-install-recommends \
    # ___ OpenCV dependencies (Debian Bookworm compatible)
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    # ___Utils
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder stage
COPY --from=builder /root/.local /usr/local

# Set environment variables
ENV PATH=/usr/local/bin:$PATH
# To fix Numba caching issues in Docker
ENV NUMBA_CACHE_DIR=/tmp
ENV NUMBA_DISABLE_JIT=1

WORKDIR /app
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/passport-specs || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
