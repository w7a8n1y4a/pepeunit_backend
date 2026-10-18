FROM --platform=$BUILDPLATFORM golang:1.24.3 AS datapipe

ARG TARGETOS
ARG TARGETARCH

WORKDIR /src

COPY data_pipe/go.mod data_pipe/go.sum ./
RUN go mod download

COPY data_pipe/ ./

RUN CGO_ENABLED=0 GOOS=${TARGETOS:-linux} GOARCH=${TARGETARCH:-amd64} \
    go build -ldflags="-s -w" -o /out/data_pipe .

FROM python:3.14.7-slim-trixie

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
    make \
 && apt autoremove -y && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY uv.lock pyproject.toml README.md /app/

RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"

COPY . .

COPY --from=datapipe /out/data_pipe /app/bin/data_pipe

RUN chmod +x /app/entrypoint.sh /app/bin/data_pipe

CMD ["/bin/bash", "/app/entrypoint.sh"]