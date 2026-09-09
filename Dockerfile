FROM ghcr.io/astral-sh/uv:0.12.5 AS uv

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN addgroup --system --gid 1001 app \
    && adduser --system --uid 1001 --ingroup app --no-create-home app
COPY cacert.crt /usr/local/share/ca-certificates/cacert.crt
RUN update-ca-certificates
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-cache
ENV PATH="/app/.venv/bin:$PATH" \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
USER app
EXPOSE 8080
CMD ["servicenowautomation-mcp"]
