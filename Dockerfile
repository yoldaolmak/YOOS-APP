FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml README.md LICENSE ./
COPY yoos_app/ ./yoos_app/
COPY examples/corpus/ ./examples/corpus/
RUN python -m pip install --no-cache-dir . \
    && useradd --uid 10001 --create-home yoosapp \
    && mkdir -p /app/examples/output \
    && chown -R yoosapp:yoosapp /app
USER yoosapp
ENTRYPOINT ["yoos-app"]
CMD ["--help"]
