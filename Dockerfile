FROM --platform=$BUILDPLATFORM golang:1.27.3 AS datapipe

# Same ML-KEM handshake failure as BuildKit, here against proxy.golang.org.
ENV GODEBUG=tlsmlkem=0

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

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    postgresql-client \
    git \
    ca-certificates \
 && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY uv.lock pyproject.toml README.md /app/

RUN uv sync --frozen --no-dev \
 && rm -rf /usr/local/lib/python3.14/site-packages/pip* \
           /usr/local/lib/python3.14/ensurepip/_bundled \
           /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.14
ENV PATH="/app/.venv/bin:$PATH" \
    UV_NO_SYNC=1

COPY . .

COPY --from=datapipe /out/data_pipe /app/bin/data_pipe

RUN chmod +x /app/entrypoint.sh /app/bin/data_pipe

RUN groupadd --system --gid 10001 pepeunit \
 && useradd --uid 10001 --gid pepeunit --create-home --home-dir /home/pepeunit pepeunit \
 && mkdir -p /app/tmp /app/repo_cache /app/prometheus_metrics \
 && chown -R pepeunit:pepeunit /app/tmp /app/repo_cache /app/prometheus_metrics

USER pepeunit

CMD ["/bin/bash", "/app/entrypoint.sh"]