FROM python:3.12.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY apps/api/pyproject.toml ./apps/api/pyproject.toml
COPY apps/api/src ./apps/api/src
RUN pip install --no-cache-dir ./apps/api uvicorn==0.38.0

FROM python:3.12.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    PORT=8000 \
    WEB_CONCURRENCY=1 \
    GRACEFUL_SHUTDOWN_TIMEOUT=30

RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv

USER appuser
EXPOSE 8000

# The review service is currently in-memory, so multi-worker deployments are unsafe.
CMD ["sh", "-c", "exec uvicorn dmt_api.main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY} --proxy-headers --timeout-graceful-shutdown ${GRACEFUL_SHUTDOWN_TIMEOUT}"]
