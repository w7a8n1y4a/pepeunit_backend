FROM python:3.13.7-slim-trixie

ENV PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

RUN apt update && apt install -y \
    postgresql-client \
    curl \
    cron \
    git \
    gcc \
    g++ \
    make \
    libc-dev \
    python3-dev \
 && apt autoremove -y && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY uv.lock pyproject.toml README.md /app/

RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"

COPY . .

RUN chmod +x /app/entrypoint.sh

CMD ["/bin/bash", "/app/entrypoint.sh"]