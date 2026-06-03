FROM python:3.11-slim

LABEL maintainer="graphova"
LABEL description="Graphova — Universal Author Voice Engine"

WORKDIR /app

# System deps for PDF processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpoppler-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir openai anthropic

# Copy source
COPY graphova/ ./graphova/
COPY yoos_app/ ./yoos_app/
COPY examples/ ./examples/
COPY pyproject.toml .

# Create data directory
RUN mkdir -p /data/uploads /data/outputs

# Non-root user
RUN useradd -m -u 1000 graphova && chown -R graphova:graphova /app /data
USER graphova

# Data volume
VOLUME ["/data"]

ENV GRAPHOVA_DATA_DIR=/data
ENV GRAPHOVA_HOST=0.0.0.0
ENV GRAPHOVA_PORT=8000
ENV GRAPHOVA_LOG_LEVEL=INFO

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["python", "-m", "graphova.app", "--host", "0.0.0.0", "--port", "8000"]
