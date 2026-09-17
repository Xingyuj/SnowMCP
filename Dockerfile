FROM ghcr.io/astral-sh/uv:0.12.5 AS uv

FROM python:3.12-slim

ARG AZURE_ARTIFACTS_TOKEN

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system --gid 1001 app \
    && adduser --system --uid 1001 --ingroup app --no-create-home app

COPY cacert.crt /usr/local/share/ca-certificates/cacert.crt
RUN update-ca-certificates

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./

RUN if [ -n "$AZURE_ARTIFACTS_TOKEN" ]; then \
        export UV_EXTRA_INDEX_URL="https://build:${AZURE_ARTIFACTS_TOKEN}@pkgs.dev.azure.com/bupaaunz/ebbc46dc-103f-467d-bc6b-a81ad06bb560/_packaging/Bupa.AIfactory.Packages/pypi/simple/"; \
        export PIP_EXTRA_INDEX_URL="$UV_EXTRA_INDEX_URL"; \
    fi \
    && uv sync --frozen --no-dev --no-cache --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev --no-cache

ENV PATH="/app/.venv/bin:$PATH" \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

USER app
EXPOSE 8080

CMD ["servicenowautomation-mcp"]
