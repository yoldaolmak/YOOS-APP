FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml README.md LICENSE ./
COPY pennovia/ ./pennovia/
RUN python -m pip install --no-cache-dir . \
    && useradd --uid 10001 --create-home pennovia \
    && mkdir -p /app/examples/output \
    && chown -R pennovia:pennovia /app
USER pennovia
ENTRYPOINT ["pennovia"]
CMD ["--help"]
