FROM ghcr.io/astral-sh/uv:python3.13-alpine

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN addgroup -S app && adduser -S app -G app

WORKDIR /app
COPY . .
RUN uv sync --locked --no-dev && \
    chown -R app:app /app

USER app
ENV PATH="/app/.venv/bin:$PATH"
CMD qwen3asr2api
HEALTHCHECK --interval=1m --start-period=10s CMD nc -zn 0.0.0.0 80 || exit 1
