FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app app
COPY pyproject.toml .
COPY src ./src
RUN pip install --no-cache-dir .
USER app
EXPOSE 8080
CMD ["servicenow-knowledge-mcp"]
