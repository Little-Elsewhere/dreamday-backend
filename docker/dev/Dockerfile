# syntax=docker/dockerfile:1.7

ARG PYTHON_IMAGE=python:3.15.0rc3-slim-trixie

FROM ghcr.io/astral-sh/uv:0.12.23 AS uv

FROM ${PYTHON_IMAGE} AS dev

COPY --from=uv /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project

COPY . .

EXPOSE 8000

CMD ["fastapi", "dev", "--host", "0.0.0.0", "--port", "8000"]
