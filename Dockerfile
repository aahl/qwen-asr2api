FROM ghcr.io/astral-sh/uv:python3.13-alpine

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:/root/.local/bin:$PATH"

RUN apk add --no-cache bash

WORKDIR /app
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

CMD qwen3asr2api
HEALTHCHECK --interval=1m --start-period=10s CMD nc -zn 0.0.0.0 80 || exit 1
