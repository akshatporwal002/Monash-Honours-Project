FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.11.12 /uv /uvx /usr/local/bin/

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
COPY app ./app
RUN uv sync --frozen --no-dev --extra quantum --no-editable \
    && uv pip check \
    && rm -rf /root/.cache/uv

COPY alembic.ini ./
COPY migrations ./migrations
COPY docker-entrypoint.sh /usr/local/bin/quantumlearn-entrypoint

RUN groupadd --gid 10001 quantumlearn \
    && useradd \
        --uid 10001 \
        --gid quantumlearn \
        --no-create-home \
        --shell /usr/sbin/nologin \
        quantumlearn \
    && mkdir -p /data/uploads \
    && chown -R quantumlearn:quantumlearn /data \
    && chmod 0755 /usr/local/bin/quantumlearn-entrypoint

USER quantumlearn

EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=5 \
    CMD ["python", "-c", "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2).read()"]

ENTRYPOINT ["quantumlearn-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8000", "--proxy-headers", "--forwarded-allow-ips=*"]
